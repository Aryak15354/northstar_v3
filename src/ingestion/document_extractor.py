#!/usr/bin/env python3
"""Extract sector metrics from filing PDFs (Phase 4).

Consumes the PDFs downloaded by ``filings_document_fetcher`` and pulls the metrics
that only exist in prose/tables, never in XBRL or Screener:

* IT (press releases / transcripts): deal TCV / order book ($bn), LTM attrition %,
  net headcount change.
* Banks/NBFCs (investor presentations): NIM %, CASA %, PCR %, slippages, Stage-3 %,
  AUM.

Each extracted value is emitted as a row with ``source_doc`` and a ``confidence``
score, and — where an independent XBRL figure exists — cross-checked so a bad
extraction flags the extractor rather than silently entering the dataset.

This module ships deterministic regex/keyword extractors (high precision, lower
recall). Values that need judgement (ambiguous transcript phrasing) are left to a
clearly-marked LLM seam (``extract_with_llm``) that a caller can wire to Claude.

    python -m src.ingestion.document_extractor --limit 50
    python -m src.ingestion.document_extractor --path data/raw/vendors/nse_filings/TCS/xxx.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FILINGS_INDEX = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "filings_index.parquet"
EXTRACT_OUT = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "extracted_metrics.parquet"

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise ImportError("document_extractor requires pdfplumber") from exc


@dataclass
class Extraction:
    symbol: str
    period_hint: str
    metric: str
    value: float
    unit: str
    confidence: float
    source_doc: str
    context: str


# --- text extraction --------------------------------------------------------

def pdf_text(path: Path, max_pages: int = 12) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages[:max_pages])
    except Exception as exc:  # noqa: BLE001
        print(f"[extractor] pdf_read_error {Path(path).name}: {exc}")
        return ""


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError):
        return None


# metric -> list of (regex, unit, confidence, group_index). Regexes are anchored on
# the reporting vocabulary Indian issuers actually use in these documents.
IT_PATTERNS = {
    "attrition_pct": [
        (r"attrition\s+rate\s+(?:at|of|was|is)?\s*([0-9]{1,2}\.?[0-9]?)\s*%", "pct", 0.9),
        (r"(?:LTM|ltm)[^%]{0,40}?attrition[^%]{0,20}?([0-9]{1,2}\.?[0-9]?)\s*%", "pct", 0.85),
    ],
    "tcv_usd_bn": [
        (r"(?:TCV|total contract value|order book)[^$]{0,30}?\$?\s*([0-9]{1,3}\.?[0-9]?)\s*billion", "usd_bn", 0.85),
        (r"\$\s*([0-9]{1,3}\.?[0-9]?)\s*billion[^.]{0,30}?(?:TCV|order book|deal)", "usd_bn", 0.75),
    ],
    "headcount": [
        (r"(?:total\s+)?(?:headcount|employees?|workforce)[^0-9]{0,25}?([0-9]{2,3}(?:,[0-9]{3})+)", "count", 0.7),
    ],
    "net_headcount_change": [
        (r"net\s+(?:addition|reduction|headcount)[^0-9\-]{0,20}?(-?[0-9]{1,3}(?:,[0-9]{3})*)", "count", 0.7),
    ],
}

BANK_PATTERNS = {
    "nim_pct": [
        (r"(?:net interest margin|NIM)[^0-9]{0,25}?([0-9]\.?[0-9]{0,2})\s*%", "pct", 0.85),
    ],
    "casa_pct": [
        (r"CASA\s*(?:ratio)?[^0-9]{0,20}?([0-9]{1,2}\.?[0-9]?)\s*%", "pct", 0.85),
    ],
    "pcr_pct": [
        (r"(?:PCR|provision coverage(?: ratio)?)[^0-9]{0,20}?([0-9]{1,2}\.?[0-9]?)\s*%", "pct", 0.8),
    ],
    "stage3_pct": [
        (r"(?:stage[\s-]?3|GS3|gross stage 3)[^0-9]{0,20}?([0-9]{1,2}\.?[0-9]?)\s*%", "pct", 0.75),
    ],
    "aum_cr": [
        (r"AUM[^0-9]{0,25}?(?:Rs\.?|₹|INR)?\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*(?:cr|crore)", "inr_cr", 0.7),
    ],
}

DOC_CLASS_PATTERNS = {
    "press_release": {**IT_PATTERNS},
    "earnings_transcript": {**IT_PATTERNS},
    "investor_presentation": {**IT_PATTERNS, **BANK_PATTERNS},
}


def extract_from_text(text: str, symbol: str, doc_class: str, source_doc: str,
                      period_hint: str = "") -> list[Extraction]:
    out: list[Extraction] = []
    patterns = DOC_CLASS_PATTERNS.get(doc_class, {**IT_PATTERNS, **BANK_PATTERNS})
    flat = re.sub(r"\s+", " ", text)
    for metric, specs in patterns.items():
        for spec in specs:
            rx, unit, conf = spec[0], spec[1], spec[2]
            m = re.search(rx, flat, flags=re.IGNORECASE)
            if not m:
                continue
            val = _num(m.group(1))
            if val is None:
                continue
            ctx = flat[max(0, m.start() - 40): m.end() + 40].strip()
            out.append(Extraction(symbol, period_hint, metric, val, unit, conf, source_doc, ctx))
            break  # first (highest-confidence) hit per metric wins
    return out


def extract_with_llm(text: str, symbol: str, doc_class: str, metrics: list[str]):  # pragma: no cover
    """LLM-extraction seam for values the regexes can't reliably capture.

    Intentionally not wired to a provider here: the caller supplies a callable that
    takes (text, metrics) and returns [{metric, value, unit, confidence, context}].
    Kept explicit so it is obvious this path needs a model to run.
    """
    raise NotImplementedError(
        "Wire this to Claude (see docs/claude-api skill) to extract ambiguous "
        "transcript metrics; regex extractors cover the high-precision cases."
    )


# --- cross-check ------------------------------------------------------------

def cross_check(extractions: pd.DataFrame) -> pd.DataFrame:
    """Flag extracted bank ratios that disagree with the XBRL credit dataset.

    Only a sanity guard: where an extracted metric has an XBRL analogue (e.g. an
    extracted GNPA/PCR vs the XBRL-derived PCR), a >2% relative gap sets
    ``xbrl_conflict=True`` so the row can be quarantined instead of trusted.
    """
    credit_path = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "credit_quarterly.parquet"
    extractions = extractions.copy()
    extractions["xbrl_conflict"] = False
    if not credit_path.exists() or extractions.empty:
        return extractions
    credit = pd.read_parquet(credit_path)
    # PCR is the one metric present in both (derived in XBRL, sometimes stated in decks)
    pcr_xbrl = (
        credit.dropna(subset=["provision_coverage_ratio"])
        .groupby("symbol")["provision_coverage_ratio"].last() * 100.0
    )
    for i, r in extractions.iterrows():
        if r["metric"] == "pcr_pct" and r["symbol"] in pcr_xbrl.index:
            ref = pcr_xbrl[r["symbol"]]
            if ref and abs(r["value"] - ref) / ref > 0.02:
                extractions.at[i, "xbrl_conflict"] = True
    return extractions


# --- orchestration ----------------------------------------------------------

def extract_all(limit: int = 0) -> pd.DataFrame:
    if not FILINGS_INDEX.exists():
        raise FileNotFoundError(f"{FILINGS_INDEX} not found — run filings_document_fetcher first")
    idx = pd.read_parquet(FILINGS_INDEX)
    idx = idx[(idx["download_status"].isin(["downloaded", "cached"])) & (idx["local_path"].astype(str).str.len() > 0)]
    rows: list[dict] = []
    n = 0
    for _, r in idx.iterrows():
        if limit and n >= limit:
            break
        path = Path(r["local_path"])
        if not path.exists():
            continue
        text = pdf_text(path)
        if not text:
            continue
        period_hint = str(pd.to_datetime(r["date"]).date()) if pd.notna(r.get("date")) else ""
        ex = extract_from_text(text, r["symbol"], r["doc_class"], path.name, period_hint)
        rows.extend(asdict(e) for e in ex)
        n += 1
    result = pd.DataFrame(rows)
    if not result.empty:
        result = cross_check(result)
        EXTRACT_OUT.parent.mkdir(parents=True, exist_ok=True)
        result.to_parquet(EXTRACT_OUT, index=False)
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract metrics from filing PDFs (Phase 4).")
    p.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0 = all).")
    p.add_argument("--path", type=str, default=None, help="Extract a single PDF (debug).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.path:
        path = Path(args.path)
        doc_class = "press_release" if "press_release" in path.name else (
            "investor_presentation" if "investor_presentation" in path.name else "earnings_transcript")
        symbol = path.parent.name
        ex = extract_from_text(pdf_text(path), symbol, doc_class, path.name)
        for e in ex:
            print(f"  {e.metric:22s} {e.value} {e.unit} (conf {e.confidence}) :: {e.context[:70]}")
        print(f"[extractor] {len(ex)} metrics from {path.name}")
        return 0
    result = extract_all(limit=args.limit)
    print(f"[extractor] {len(result)} metric rows from PDFs")
    if not result.empty:
        print(result["metric"].value_counts().to_string())
        conflicts = int(result.get("xbrl_conflict", pd.Series(dtype=bool)).sum())
        print(f"[extractor] xbrl_conflicts={conflicts}; wrote {EXTRACT_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
