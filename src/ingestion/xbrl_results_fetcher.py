#!/usr/bin/env python3
"""NSE quarterly financial-results XBRL fetcher and parser (EXP-13 core).

NSE publishes structured XBRL for every quarterly result filed on the exchange.
Unlike the generic yfinance income statements (which carry no banking line items),
these filings contain the credit factors EXP-13 needs — GNPA, NNPA, their ratios,
ROA, interest earned/expended, provisions, and capital ratios — with ~20 years of
per-symbol history. This module lists filings, downloads the immutable XBRL, parses
the BANKING / NBFC / generic Ind-AS taxonomies, and emits a PIT-safe quarterly
credit dataset keyed on the exchange broadcast (dissemination) date.

Design notes
------------
* Raw XBRL under ``data/raw/vendors/nse_xbrl/{SYMBOL}/`` is immutable and cached;
  any parser change is replayable without re-hitting NSE.
* The current-quarter context is anchored on the context referenced by the
  ``Symbol`` / ``DateOfEndOfReportingPeriod`` fact, not on heuristic period math,
  so comparative (prior-year) and dimensional (segment) contexts are ignored.
* Facts are matched by XBRL *local name* so a taxonomy namespace-version bump does
  not silently drop fields.
* ``availability_date`` is the exchange ``broadCastDate`` — the true point in time
  the market could act on the filing — never the period end.

CLI
---
    python -m src.ingestion.xbrl_results_fetcher --symbols HDFCBANK ICICIBANK
    python -m src.ingestion.xbrl_results_fetcher --universe-financials   # all 95
    python -m src.ingestion.xbrl_results_fetcher --symbols TCS --list-only
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_csv_scraper_common import (  # noqa: E402
    create_nse_session,
    nse_request,
)

try:
    from lxml import etree  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise ImportError("xbrl_results_fetcher requires lxml (pip install lxml)") from exc


RESULTS_API = "https://www.nseindia.com/api/corporates-financial-results"
RESULTS_REFERER = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"

RAW_XBRL_DIR = PROJECT_ROOT / "data" / "raw" / "vendors" / "nse_xbrl"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "sector_financials"
UNIVERSE_FILE = PROJECT_ROOT / "universe" / "nifty500.csv"

XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"


# --- taxonomy field maps (canonical_name -> XBRL local name) ---------------

BANKING_FIELDS = {
    "gross_npa": "GrossNonPerformingAssets",
    "net_npa": "NonPerformingAssets",
    "gnpa_pct": "PercentageOfGrossNpa",
    "nnpa_pct": "PercentageOfNpa",
    "roa": "ReturnOnAssets",
    "interest_earned": "InterestEarned",
    "interest_expended": "InterestExpended",
    "interest_on_advances": "InterestOrDiscountOnAdvancesOrBills",
    "provisions": "ProvisionsOtherThanTaxAndContingencies",
    "operating_profit_pre_prov": "OperatingProfitBeforeProvisionAndContingencies",
    "cet1_ratio": "CET1Ratio",
    "at1_ratio": "AdditionalTier1Ratio",
    "profit_after_tax": "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
    "paid_up_equity": "PaidUpValueOfEquityShareCapital",
    "face_value": "FaceValueOfEquityShareCapital",
}

NBFC_FIELDS = {
    "interest_earned": "InterestEarned",
    "impairment_financial": "ImpairmentOnFinancialInstruments",
    "revenue_from_ops": "RevenueFromOperations",
    "total_income": "Income",
    "fees_commission_income": "FeesAndCommissionIncome",
    "other_income": "OtherIncome",
    "profit_before_tax": "ProfitBeforeTax",
    "profit_for_period": "ProfitLossForPeriod",
    "profit_owners": "ProfitOrLossAttributableToOwnersOfParent",
    "paid_up_equity": "PaidUpValueOfEquityShareCapital",
    "face_value": "FaceValueOfEquityShareCapital",
}

GENERIC_FIELDS = {
    "revenue_from_ops": "RevenueFromOperations",
    "total_income": "Income",
    "other_income": "OtherIncome",
    "profit_before_tax": "ProfitBeforeTax",
    "profit_before_exceptional_tax": "ProfitBeforeExceptionalItemsAndTax",
    "profit_for_period": "ProfitLossForPeriod",
    "profit_owners": "ProfitOrLossAttributableToOwnersOfParent",
    "total_expenses": "Expenses",
    "paid_up_equity": "PaidUpValueOfEquityShareCapital",
    "face_value": "FaceValueOfEquityShareCapital",
}

# metadata facts common to every taxonomy
META_FIELDS = {
    "symbol": "Symbol",
    "company_name": "NameOfTheCompany",
    "period_start": "DateOfStartOfReportingPeriod",
    "period_end": "DateOfEndOfReportingPeriod",
}


@dataclass
class Filing:
    symbol: str
    period_from: str
    period_to: str
    relating_to: str
    consolidated: str  # "Consolidated" / "Non-Consolidated"
    is_bank: str  # "Y" / "N" / "B"
    broadcast_date: str
    filing_date: str
    seq_number: str
    xbrl_url: str
    audited: str = ""

    @property
    def basis(self) -> str:
        return "consolidated" if str(self.consolidated).lower().startswith("cons") else "standalone"


@dataclass
class ParsedFiling:
    symbol: str
    company_name: str
    period_start: Optional[str]
    period_end: Optional[str]
    taxonomy: str
    facts: dict = field(default_factory=dict)


def _taxonomy_from_url(url: str) -> str:
    base = url.rsplit("/", 1)[-1].upper()
    if base.startswith("BANKING"):
        return "banking"
    if base.startswith("NBFC"):
        return "nbfc"
    if base.startswith("INS"):
        return "insurance"
    return "generic"


# --- listing ----------------------------------------------------------------

def list_results(symbol: str, session=None, period: str = "Quarterly") -> list[Filing]:
    """Return all quarterly-result filings NSE holds for a symbol (newest first)."""
    session = session or create_nse_session(referer=RESULTS_REFERER)
    resp = nse_request(
        session,
        RESULTS_API,
        params={"index": "equities", "period": period, "symbol": symbol.upper()},
        referer=RESULTS_REFERER,
        max_attempts=4,
    )
    try:
        data = resp.json()
    except Exception:
        return []
    filings: list[Filing] = []
    for rec in data:
        xbrl = str(rec.get("xbrl") or "").strip()
        if not xbrl or xbrl.endswith("/-") or not xbrl.lower().endswith(".xml"):
            continue
        filings.append(
            Filing(
                symbol=symbol.upper(),
                period_from=str(rec.get("fromDate") or ""),
                period_to=str(rec.get("toDate") or ""),
                relating_to=str(rec.get("relatingTo") or ""),
                consolidated=str(rec.get("consolidated") or ""),
                is_bank=str(rec.get("bank") or ""),
                broadcast_date=str(rec.get("broadCastDate") or ""),
                filing_date=str(rec.get("filingDate") or ""),
                seq_number=str(rec.get("seqNumber") or ""),
                xbrl_url=xbrl,
                audited=str(rec.get("audited") or ""),
            )
        )
    return filings


# --- download ---------------------------------------------------------------

def download_xbrl(filing: Filing, session=None, force: bool = False) -> Optional[Path]:
    """Download (and cache) the XBRL for a filing. Immutable — cached files are trusted."""
    dest_dir = RAW_XBRL_DIR / filing.symbol
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = filing.xbrl_url.rsplit("/", 1)[-1]
    dest = dest_dir / fname
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest
    session = session or create_nse_session(referer=RESULTS_REFERER)
    try:
        resp = nse_request(session, filing.xbrl_url, referer=RESULTS_REFERER, max_attempts=3)
    except Exception as exc:  # noqa: BLE001
        print(f"[xbrl] download_failed {filing.symbol} {fname}: {exc}")
        return None
    body = resp.content
    if b"<xbrl" not in body[:4000] and b"xbrli:xbrl" not in body[:4000]:
        print(f"[xbrl] not_xbrl {filing.symbol} {fname} (len={len(body)})")
        return None
    dest.write_bytes(body)
    return dest


# --- parse ------------------------------------------------------------------

def _localname(tag: str) -> str:
    return etree.QName(tag).localname


def parse_xbrl(path: Path, taxonomy_hint: Optional[str] = None) -> Optional[ParsedFiling]:
    """Parse one XBRL file into a ParsedFiling of canonical quarterly facts."""
    try:
        root = etree.fromstring(Path(path).read_bytes())
    except Exception as exc:  # noqa: BLE001
        print(f"[xbrl] parse_error {path.name}: {exc}")
        return None

    # 1) index contexts: id -> dict(start,end,instant,has_dim)
    contexts: dict[str, dict] = {}
    for ctx in root.iter(f"{{{XBRLI}}}context"):
        cid = ctx.get("id")
        period = ctx.find(f"{{{XBRLI}}}period")
        if period is None:
            continue
        start = period.findtext(f"{{{XBRLI}}}startDate")
        end = period.findtext(f"{{{XBRLI}}}endDate")
        instant = period.findtext(f"{{{XBRLI}}}instant")
        has_dim = ctx.find(f".//{{{XBRLDI}}}explicitMember") is not None
        contexts[cid] = {"start": start, "end": end, "instant": instant, "has_dim": has_dim}

    # 2) collect all facts: localname -> list[(contextRef, value)]
    facts: dict[str, list[tuple[str, str]]] = {}
    for el in root.iter():
        cref = el.get("contextRef")
        if not cref or el.text is None:
            continue
        facts.setdefault(_localname(el), []).append((cref, el.text.strip()))

    # 3) anchor the current-quarter context on the Symbol / period-end fact
    anchor_ctx = None
    for anchor_tag in ("Symbol", "DateOfEndOfReportingPeriod", "NameOfTheCompany"):
        for cref, _ in facts.get(anchor_tag, []):
            c = contexts.get(cref, {})
            if not c.get("has_dim"):
                anchor_ctx = cref
                break
        if anchor_ctx:
            break
    if anchor_ctx is None:
        return None

    period_end = contexts.get(anchor_ctx, {}).get("end")
    period_start = contexts.get(anchor_ctx, {}).get("start")
    # instant context (balance-sheet stocks) whose date == period_end
    instant_ctx = next(
        (cid for cid, c in contexts.items()
         if not c["has_dim"] and c.get("instant") and c["instant"] == period_end),
        None,
    )

    taxonomy = taxonomy_hint or "generic"
    field_map = {"banking": BANKING_FIELDS, "nbfc": NBFC_FIELDS}.get(taxonomy, GENERIC_FIELDS)
    all_fields = {**META_FIELDS, **field_map}

    def _pick(local_name: str) -> Optional[str]:
        rows = facts.get(local_name)
        if not rows:
            return None
        by_ctx = {cref: val for cref, val in rows}
        for cid in (anchor_ctx, instant_ctx):
            if cid and cid in by_ctx:
                return by_ctx[cid]
        # last resort: first non-dimensional context value
        for cref, val in rows:
            if not contexts.get(cref, {}).get("has_dim"):
                return val
        return None

    out_facts: dict = {}
    for canon, local_name in all_fields.items():
        if canon in ("symbol", "company_name", "period_start", "period_end"):
            continue
        raw = _pick(local_name)
        if raw is None:
            continue
        try:
            out_facts[canon] = float(raw)
        except (TypeError, ValueError):
            out_facts[canon] = raw

    symbol = _pick(META_FIELDS["symbol"]) or ""
    company = _pick(META_FIELDS["company_name"]) or ""
    return ParsedFiling(
        symbol=str(symbol).upper(),
        company_name=str(company),
        period_start=period_start,
        period_end=period_end,
        taxonomy=taxonomy,
        facts=out_facts,
    )


def _derive(row: dict) -> dict:
    """Add derived credit metrics where the inputs are present."""
    ie, iexp = row.get("interest_earned"), row.get("interest_expended")
    if isinstance(ie, (int, float)) and isinstance(iexp, (int, float)):
        row["net_interest_income"] = ie - iexp
    g, n = row.get("gross_npa"), row.get("net_npa")
    if isinstance(g, (int, float)) and isinstance(n, (int, float)) and g:
        row["provision_coverage_ratio"] = (g - n) / g
    prov, nii = row.get("provisions"), row.get("net_interest_income")
    if isinstance(prov, (int, float)) and isinstance(nii, (int, float)) and nii:
        row["credit_cost_to_nii"] = prov / nii
    return row


# --- orchestration ----------------------------------------------------------

def fetch_symbol(
    symbol: str,
    session=None,
    prefer_basis: str = "standalone",
    sleep_range: tuple[float, float] = (1.0, 2.0),
    force_download: bool = False,
) -> pd.DataFrame:
    """List, download, and parse every quarterly filing for one symbol."""
    session = session or create_nse_session(referer=RESULTS_REFERER)
    print(f"[xbrl] {symbol}: listing NSE quarterly results...", flush=True)
    filings = list_results(symbol, session=session)
    print(f"[xbrl] {symbol}: {len(filings)} XBRL filing links found", flush=True)
    rows: list[dict] = []
    for idx, filing in enumerate(filings, 1):
        taxonomy = _taxonomy_from_url(filing.xbrl_url)
        if taxonomy == "insurance":
            continue  # insurers file a different template; handled via IR/PDF layer
        fname = filing.xbrl_url.rstrip("/").split("/")[-1]
        cached = (RAW_XBRL_DIR / filing.symbol / fname).exists()
        path = download_xbrl(filing, session=session, force=force_download)
        if path is None:
            continue
        if (not cached) or idx == 1 or idx % 10 == 0 or idx == len(filings):
            state = "cached" if cached else "downloaded"
            print(
                f"[xbrl] {symbol}: {idx}/{len(filings)} {state} {path.name}",
                flush=True,
            )
        parsed = parse_xbrl(path, taxonomy_hint=taxonomy)
        if parsed is None or not parsed.facts:
            continue
        row = {
            "symbol": parsed.symbol or symbol.upper(),
            "company_name": parsed.company_name,
            "period_start": parsed.period_start,
            "period_end": parsed.period_end,
            "basis": filing.basis,
            "taxonomy": parsed.taxonomy,
            "availability_date": filing.broadcast_date,
            "relating_to": filing.relating_to,
            "audited": filing.audited,
            "xbrl_url": filing.xbrl_url,
            "source_file": path.name,
        }
        row.update(_derive(dict(parsed.facts)))
        rows.append(row)
        if path.stat().st_mtime > time.time() - 5:  # only sleep after a real download
            time.sleep(random.uniform(*sleep_range))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")
    df["availability_date"] = pd.to_datetime(df["availability_date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["period_end"])
    # prefer the requested basis, keep the other only when preferred is missing
    df["_basis_rank"] = (df["basis"] == prefer_basis).astype(int)
    df = (
        df.sort_values(["period_end", "_basis_rank"])
        .drop_duplicates(subset=["symbol", "period_end", "basis"], keep="last")
        .drop(columns="_basis_rank")
        .sort_values("period_end")
        .reset_index(drop=True)
    )
    return df


def _load_financials_universe() -> list[str]:
    df = pd.read_csv(UNIVERSE_FILE)
    fin = df[df["Industry"] == "Financial Services"]
    return sorted(str(s).strip().upper() for s in fin["Symbol"].dropna())


def _load_nonfinancials_universe() -> list[str]:
    df = pd.read_csv(UNIVERSE_FILE)
    nonfin = df[df["Industry"] != "Financial Services"]
    return sorted(str(s).strip().upper() for s in nonfin["Symbol"].dropna())


def _load_all_universe() -> list[str]:
    df = pd.read_csv(UNIVERSE_FILE)
    return sorted(str(s).strip().upper() for s in df["Symbol"].dropna())


def build_credit_dataset(
    symbols: Iterable[str],
    out_path: Optional[Path] = None,
    prefer_basis: str = "standalone",
) -> pd.DataFrame:
    """Fetch every symbol and write the consolidated quarterly credit parquet."""
    session = create_nse_session(referer=RESULTS_REFERER)
    frames: list[pd.DataFrame] = []
    symbols = list(symbols)
    for i, sym in enumerate(symbols, 1):
        print(f"[xbrl] START ({i}/{len(symbols)}) {sym}", flush=True)
        try:
            df = fetch_symbol(sym, session=session, prefer_basis=prefer_basis)
        except Exception as exc:  # noqa: BLE001
            print(f"[xbrl] {sym} FAILED: {exc}", flush=True)
            continue
        n = 0 if df.empty else len(df)
        gnpa = 0 if df.empty or "gnpa_pct" not in df else int(df["gnpa_pct"].notna().sum())
        tax = "-" if df.empty else df["taxonomy"].mode().iat[0]
        print(f"[xbrl] DONE  ({i}/{len(symbols)}) {sym}: {n} quarters, gnpa_pct={gnpa}, taxonomy={tax}", flush=True)
        if not df.empty:
            frames.append(df)
    if not frames:
        print("[xbrl] no data collected", flush=True)
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True).sort_values(["symbol", "period_end"])
    out_path = out_path or (OUTPUT_DIR / "credit_quarterly.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)
    combined.to_csv(out_path.with_suffix(".csv"), index=False)
    print(f"[xbrl] wrote {len(combined)} rows for {combined['symbol'].nunique()} symbols -> {out_path}", flush=True)
    return combined


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NSE XBRL quarterly-results fetcher (EXP-13).")
    p.add_argument("--symbols", nargs="*", default=None, help="Explicit NSE symbols.")
    p.add_argument("--universe-financials", action="store_true", help="Use all Financial Services names.")
    p.add_argument("--universe-nonfinancials", action="store_true", help="Use all non-Financial Services Nifty 500 names.")
    p.add_argument("--universe-all", action="store_true", help="Use the full Nifty 500 universe.")
    p.add_argument("--list-only", action="store_true", help="List filings without downloading.")
    p.add_argument("--basis", choices=["standalone", "consolidated"], default="standalone")
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.universe_financials:
        symbols = _load_financials_universe()
    elif args.universe_nonfinancials:
        symbols = _load_nonfinancials_universe()
    elif args.universe_all:
        symbols = _load_all_universe()
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:
        print("Provide --symbols, --universe-financials, --universe-nonfinancials, or --universe-all")
        return 2

    if args.list_only:
        session = create_nse_session(referer=RESULTS_REFERER)
        for sym in symbols:
            fl = list_results(sym, session=session)
            taxes = sorted({_taxonomy_from_url(f.xbrl_url) for f in fl})
            print(f"{sym}: {len(fl)} filings with xbrl, taxonomies={taxes}")
        return 0

    build_credit_dataset(symbols, out_path=Path(args.out) if args.out else None, prefer_basis=args.basis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
