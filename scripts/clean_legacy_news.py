#!/usr/bin/env python3
"""Audit and clean legacy per-ticker news CSVs."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.progress_resume import Progress


STOP_TOKENS = {
    "ltd",
    "limited",
    "inc",
    "co",
    "company",
    "industries",
    "india",
    "ind",
    "plc",
    "corp",
    "corporation",
    "sa",
    "ag",
    "the",
    "and",
    "of",
    "pvt",
    "private",
}


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _company_tokens(name: str) -> list[str]:
    raw = [t for t in re.split(r"[^a-z0-9]+", _normalize_text(name)) if t]
    return [t for t in raw if t not in STOP_TOKENS and len(t) >= 3]


def _build_pattern(tokens: list[str]) -> re.Pattern | None:
    if not tokens:
        return None
    inner = "|".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?:^|[^a-z0-9])(?:{inner})(?:$|[^a-z0-9])")


def _is_equity_symbol(symbol: str) -> bool:
    if not symbol:
        return False
    if "=" in symbol or symbol.endswith((".X", "=X", "=F")):
        return False
    if symbol.startswith("^"):
        return False
    return True


def _pick_col(df: pd.DataFrame, names: list[str]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    for col in df.columns:
        if col.lower() in [x.lower() for x in names]:
            return col
    return None


def _parse_date_col(df: pd.DataFrame) -> pd.Series:
    date_col = _pick_col(df, ["date", "Date", "published_date", "published", "timestamp"])
    if date_col is None:
        return pd.to_datetime(pd.Series([pd.NaT] * len(df)))
    d = pd.to_datetime(df[date_col], errors="coerce")
    try:
        d = d.dt.tz_convert(None)
    except Exception:
        try:
            d = d.dt.tz_localize(None)
        except Exception:
            pass
    return d


def _row_relevance(
    text: pd.Series,
    ticker_pat: re.Pattern | None,
    company_pat: re.Pattern | None,
) -> pd.Series:
    hit = pd.Series(False, index=text.index)
    if ticker_pat is not None:
        hit = hit | text.str.contains(ticker_pat, na=False)
    if company_pat is not None:
        hit = hit | text.str.contains(company_pat, na=False)
    return hit


def _clean_file(path: Path, min_file_relevance: float) -> tuple[pd.DataFrame, dict]:
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(), {"rows": 0, "relevant": 0, "pct": None, "kept": 0}

    if df.empty:
        return pd.DataFrame(), {"rows": 0, "relevant": 0, "pct": None, "kept": 0}

    title_col = _pick_col(df, ["title", "headline"])
    desc_col = _pick_col(df, ["description", "summary", "snippet", "desc"])
    url_col = _pick_col(df, ["url", "link"])
    symbol_col = _pick_col(df, ["symbol", "ticker", "Symbol"])
    comp_col = _pick_col(df, ["company_name", "company"])

    ticker = ""
    if symbol_col and df[symbol_col].notna().any():
        ticker = str(df[symbol_col].dropna().iloc[0])
    else:
        ticker = path.stem
    ticker = ticker.replace(".NS", "")
    if not _is_equity_symbol(ticker):
        return pd.DataFrame(), {"rows": len(df), "relevant": 0, "pct": 0.0, "kept": 0}

    company = ""
    if comp_col and df[comp_col].notna().any():
        company = str(df[comp_col].dropna().iloc[0])
    else:
        company = path.stem

    tokens = _company_tokens(company)
    comp_pat = _build_pattern(tokens)
    ticker_pat = _build_pattern([ticker.lower()]) if ticker else None

    title = df[title_col].astype(str) if title_col else ""
    desc = df[desc_col].astype(str) if desc_col else ""
    text = (title.fillna("") + " " + desc.fillna("")).map(_normalize_text)

    relevant = _row_relevance(text, ticker_pat, comp_pat)
    rel_rows = int(relevant.sum())
    rows = int(len(df))
    pct = (100.0 * rel_rows / rows) if rows else 0.0

    if pct < float(min_file_relevance):
        # Keep only relevant rows for low-quality files.
        keep_mask = relevant
    else:
        keep_mask = relevant

    kept = int(keep_mask.sum())
    if kept == 0:
        return pd.DataFrame(), {"rows": rows, "relevant": rel_rows, "pct": pct, "kept": 0}

    out = pd.DataFrame(
        {
            "date": _parse_date_col(df).dt.normalize(),
            "ticker": f"{ticker}.NS",
            "company": company,
            "headline": title if title_col else "",
            "summary": desc if desc_col else "",
            "url": df[url_col] if url_col else "",
            "source": df[_pick_col(df, ["source"])] if _pick_col(df, ["source"]) else "",
            "source_type": "legacy_csv",
            "raw_file": path.name,
        }
    )
    out = out.loc[keep_mask].copy()
    out["headline"] = out["headline"].astype(str)
    out["summary"] = out["summary"].astype(str)
    out["url"] = out["url"].astype(str)
    out["source"] = out["source"].astype(str)
    out = out.dropna(subset=["date"]).drop_duplicates(
        subset=["date", "ticker", "headline", "url"], keep="last"
    )
    return out.reset_index(drop=True), {"rows": rows, "relevant": rel_rows, "pct": pct, "kept": kept}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit and clean legacy news CSVs.")
    p.add_argument("--news-dir", type=str, default="data/news/equities")
    p.add_argument("--backup-dir", type=str, default="data/news_backup/news_old/equities")
    p.add_argument("--out-dir", type=str, default="data/processed/news")
    p.add_argument("--report-dir", type=str, default="reports")
    p.add_argument("--min-file-relevance", type=float, default=30.0, help="Min %% relevance for file quality reporting.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(args.news_dir), Path(args.backup_dir)]
    out_dir = Path(args.out_dir)
    report_dir = Path(args.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.glob("*.csv")))

    audit_rows: list[dict] = []
    cleaned_parts: list[pd.DataFrame] = []

    with Progress(total=len(files), desc="legacy_news_audit", unit="file") as pbar:
        for fp in files:
            cleaned, stats = _clean_file(fp, float(args.min_file_relevance))
            audit_rows.append(
                {
                    "dir": str(fp.parent),
                    "file": fp.name,
                    "rows": stats.get("rows", 0),
                    "relevant": stats.get("relevant", 0),
                    "relevance_pct": stats.get("pct", 0.0),
                    "kept": stats.get("kept", 0),
                }
            )
            if not cleaned.empty:
                cleaned_parts.append(cleaned)
            pbar.update(1)

    audit_df = pd.DataFrame(audit_rows)
    audit_path = report_dir / "news_relevance_audit.csv"
    audit_df.to_csv(audit_path, index=False)

    merged = pd.concat(cleaned_parts, ignore_index=True) if cleaned_parts else pd.DataFrame()
    out_parquet = out_dir / "legacy_news_clean.parquet"
    out_csv = out_dir / "legacy_news_clean.csv"
    if not merged.empty:
        merged = merged.sort_values(["date", "ticker"], kind="mergesort")
        merged.to_parquet(out_parquet, index=False)
        merged.to_csv(out_csv, index=False)

    print(f"[legacy-news] files={len(files)} kept_rows={len(merged)} audit={audit_path}")
    if not merged.empty:
        print(
            f"[legacy-news] date_range={merged['date'].min().date()} to {merged['date'].max().date()} "
            f"tickers={merged['ticker'].nunique()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
