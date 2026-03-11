#!/usr/bin/env python3
"""Load raw Screener scrape outputs into processed pipeline-ready datasets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DEFAULT_RAW_DIR = Path("data/raw/screener")
DEFAULT_OUTPUT_DIR = Path("data/processed")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_ticker(raw: Any) -> str:
    s = _clean_text(raw).upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _metric_to_column(metric: Any) -> str:
    out = _clean_text(metric).lower()
    out = out.replace("&", " and ")
    out = out.replace("%", " pct ")
    out = out.replace("/", " ")
    out = re.sub(r"[^a-z0-9]+", "_", out)
    out = re.sub(r"_+", "_", out).strip("_")
    return out


def _parse_fiscal_year(period: Any) -> Optional[int]:
    s = _clean_text(period)
    if not s:
        return None

    m = re.search(r"(20\d{2}|19\d{2})$", s)
    if m:
        return int(m.group(1))

    fy4 = re.search(r"fy\s*[- ]?(20\d{2}|19\d{2})", s, flags=re.IGNORECASE)
    if fy4:
        return int(fy4.group(1))

    fy2 = re.search(r"fy\s*[- ]?(\d{2})$", s, flags=re.IGNORECASE)
    if fy2:
        yy = int(fy2.group(1))
        return 2000 + yy if yy < 80 else 1900 + yy
    return None


def _parse_quarter_end(period: Any) -> pd.Timestamp:
    s = _clean_text(period)
    if not s:
        return pd.NaT

    q_match = re.match(r"Q([1-4])[-\s]?((?:19|20)\d{2})$", s, flags=re.IGNORECASE)
    if q_match:
        q = int(q_match.group(1))
        y = int(q_match.group(2))
        month = q * 3
        return pd.Timestamp(year=y, month=month, day=1) + pd.offsets.MonthEnd(0)

    parsed = pd.to_datetime(f"1 {s}", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(s, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed.year, parsed.month, 1) + pd.offsets.MonthEnd(0)


def _quarter_label(dt: pd.Timestamp) -> str:
    q = int(((dt.month - 1) // 3) + 1)
    return f"Q{q}-{dt.year}"


def _read_long_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["ticker", "metric", "period", "value"])
    df = pd.read_csv(path)
    for c in ["ticker", "metric", "period", "value"]:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[["ticker", "metric", "period", "value"]].copy()
    df["ticker"] = df["ticker"].map(_normalize_ticker)
    df["metric"] = df["metric"].map(_clean_text)
    df["period"] = df["period"].map(_clean_text)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[(df["ticker"] != "") & (df["metric"] != "") & (df["period"] != "")]
    return df.reset_index(drop=True)


def _concat_long(paths: list[Path]) -> pd.DataFrame:
    frames = [_read_long_csv(p) for p in paths]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["ticker", "metric", "period", "value"])
    out = pd.concat(frames, ignore_index=True)
    return out.reset_index(drop=True)


def _build_annual(financials_dir: Path) -> pd.DataFrame:
    long_df = _concat_long(
        [
            *sorted(financials_dir.glob("*_annual_pl.csv")),
            *sorted(financials_dir.glob("*_annual_bs.csv")),
            *sorted(financials_dir.glob("*_annual_cf.csv")),
            *sorted(financials_dir.glob("*_annual_ratios.csv")),
        ]
    )
    if long_df.empty:
        return pd.DataFrame(columns=["ticker", "fiscal_year", "availability_date"])

    work = long_df.copy()
    work["fiscal_year"] = work["period"].map(_parse_fiscal_year)
    work = work.dropna(subset=["fiscal_year"]).copy()
    if work.empty:
        return pd.DataFrame(columns=["ticker", "fiscal_year", "availability_date"])
    work["fiscal_year"] = work["fiscal_year"].astype(int)
    work["column_name"] = work["metric"].map(_metric_to_column)

    wide = (
        work.pivot_table(
            index=["ticker", "fiscal_year"],
            columns="column_name",
            values="value",
            aggfunc="last",
        )
        .reset_index()
        .sort_values(["ticker", "fiscal_year"])
    )
    wide.columns.name = None
    wide["availability_date"] = (
        pd.to_datetime(wide["fiscal_year"].astype(str) + "-12-31", errors="coerce") + pd.Timedelta(days=60)
    )

    core = ["ticker", "fiscal_year", "availability_date"]
    others = sorted([c for c in wide.columns if c not in core])
    return wide[core + others]


def _build_quarterly(financials_dir: Path) -> pd.DataFrame:
    long_df = _concat_long(sorted(financials_dir.glob("*_quarterly_pl.csv")))
    if long_df.empty:
        return pd.DataFrame(columns=["ticker", "quarter", "availability_date"])

    work = long_df.copy()
    work["quarter_end"] = work["period"].map(_parse_quarter_end)
    work = work.dropna(subset=["quarter_end"]).copy()
    if work.empty:
        return pd.DataFrame(columns=["ticker", "quarter", "availability_date"])
    work["quarter"] = work["quarter_end"].map(_quarter_label)
    work["column_name"] = work["metric"].map(_metric_to_column)

    wide = (
        work.pivot_table(
            index=["ticker", "quarter", "quarter_end"],
            columns="column_name",
            values="value",
            aggfunc="last",
        )
        .reset_index()
        .sort_values(["ticker", "quarter_end"])
    )
    wide.columns.name = None
    wide["availability_date"] = pd.to_datetime(wide["quarter_end"], errors="coerce") + pd.Timedelta(days=45)

    core = ["ticker", "quarter", "availability_date"]
    others = sorted([c for c in wide.columns if c not in set(core + ["quarter_end"])])
    return wide[core + others]


def _shareholding_metric_name(raw_metric: Any) -> str:
    n = re.sub(r"[^a-z0-9]+", "", _clean_text(raw_metric).lower())
    if "promoter" in n:
        return "promoter_pct"
    if n in {"fii", "fiis"} or "foreigninstitutional" in n:
        return "fii_pct"
    if n in {"dii", "diis"} or "domesticinstitutional" in n:
        return "dii_pct"
    if "public" in n:
        return "public_pct"
    if "government" in n or n in {"govt", "govtshareholding"}:
        return "govt_pct"
    if "shareholder" in n:
        return "n_shareholders"
    return ""


def _build_shareholding(shareholding_dir: Path) -> pd.DataFrame:
    long_df = _concat_long(sorted(shareholding_dir.glob("*_shareholding.csv")))
    if long_df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "quarter",
                "availability_date",
                "promoter_pct",
                "fii_pct",
                "dii_pct",
                "public_pct",
                "govt_pct",
                "n_shareholders",
            ]
        )

    work = long_df.copy()
    work["quarter_end"] = work["period"].map(_parse_quarter_end)
    work["metric_name"] = work["metric"].map(_shareholding_metric_name)
    work = work.dropna(subset=["quarter_end"])
    work = work[work["metric_name"] != ""].copy()
    if work.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "quarter",
                "availability_date",
                "promoter_pct",
                "fii_pct",
                "dii_pct",
                "public_pct",
                "govt_pct",
                "n_shareholders",
            ]
        )

    work["quarter"] = work["quarter_end"].map(_quarter_label)
    wide = (
        work.pivot_table(
            index=["ticker", "quarter", "quarter_end"],
            columns="metric_name",
            values="value",
            aggfunc="last",
        )
        .reset_index()
        .sort_values(["ticker", "quarter_end"])
    )
    wide.columns.name = None
    wide["availability_date"] = pd.to_datetime(wide["quarter_end"], errors="coerce") + pd.Timedelta(days=45)

    ordered_cols = [
        "ticker",
        "quarter",
        "availability_date",
        "promoter_pct",
        "fii_pct",
        "dii_pct",
        "public_pct",
        "govt_pct",
        "n_shareholders",
    ]
    for col in ordered_cols:
        if col not in wide.columns:
            wide[col] = pd.NA
    return wide[ordered_cols]


def _build_metadata(metadata_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(metadata_dir.glob("*_metadata.json")):
        payload: dict[str, Any]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        ticker = _normalize_ticker(payload.get("ticker") or path.stem.replace("_metadata", ""))
        rows.append(
            {
                "ticker": ticker,
                "company_name": payload.get("company_name", ""),
                "bse_code": payload.get("bse_code", ""),
                "nse_code": payload.get("nse_code", ""),
                "sector": payload.get("sector", ""),
                "industry": payload.get("industry", ""),
                "about_text": payload.get("about_text", payload.get("about", "")),
                "website": payload.get("website", ""),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["ticker", "company_name", "bse_code", "nse_code", "sector", "industry", "about_text", "website"]
        )
    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["ticker"], keep="last").sort_values("ticker").reset_index(drop=True)
    return out


def build_pipeline_files(raw_dir: Path, output_dir: Path) -> dict[str, pd.DataFrame]:
    metadata_dir = raw_dir / "metadata"
    financials_dir = raw_dir / "financials"
    shareholding_dir = raw_dir / "shareholding"

    output_dir.mkdir(parents=True, exist_ok=True)

    annual = _build_annual(financials_dir)
    quarterly = _build_quarterly(financials_dir)
    shareholding = _build_shareholding(shareholding_dir)
    metadata = _build_metadata(metadata_dir)

    annual.to_csv(output_dir / "screener_fundamentals_annual.csv", index=False)
    quarterly.to_csv(output_dir / "screener_fundamentals_quarterly.csv", index=False)
    shareholding.to_csv(output_dir / "screener_shareholding.csv", index=False)
    metadata.to_csv(output_dir / "screener_metadata.csv", index=False)

    return {
        "annual": annual,
        "quarterly": quarterly,
        "shareholding": shareholding,
        "metadata": metadata,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Load raw Screener scrape data into processed pipeline CSVs.")
    p.add_argument("--raw-dir", type=str, default=str(DEFAULT_RAW_DIR), help="Raw Screener directory.")
    p.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Processed output directory.")
    return p


def _year_range_text(df: pd.DataFrame) -> str:
    if df.empty or "fiscal_year" not in df.columns:
        return "NA-NA"
    mn = int(pd.to_numeric(df["fiscal_year"], errors="coerce").min())
    mx = int(pd.to_numeric(df["fiscal_year"], errors="coerce").max())
    return f"{mn}-{mx}"


def _quarter_range_text(df: pd.DataFrame) -> str:
    if df.empty or "quarter" not in df.columns:
        return "NA to NA"
    work = df.copy()
    qparts = work["quarter"].astype(str).str.extract(r"Q([1-4])-(\d{4})")
    work["qnum"] = pd.to_numeric(qparts[0], errors="coerce")
    work["year"] = pd.to_numeric(qparts[1], errors="coerce")
    work = work.dropna(subset=["qnum", "year"])
    if work.empty:
        return "NA to NA"
    work["sort_key"] = work["year"] * 10 + work["qnum"]
    min_row = work.loc[work["sort_key"].idxmin()]
    max_row = work.loc[work["sort_key"].idxmax()]
    min_q = f"Q{int(min_row['qnum'])}-{int(min_row['year'])}"
    max_q = f"Q{int(max_row['qnum'])}-{int(max_row['year'])}"
    return f"{min_q} to {max_q}"


def main() -> int:
    args = _build_parser().parse_args()
    raw_dir = Path(args.raw_dir)
    output_dir = Path(args.output_dir)
    built = build_pipeline_files(raw_dir=raw_dir, output_dir=output_dir)

    annual = built["annual"]
    quarterly = built["quarterly"]
    shareholding = built["shareholding"]
    metadata = built["metadata"]

    print(
        f"[loader] annual fundamentals: {annual['ticker'].nunique() if 'ticker' in annual.columns else 0} tickers, "
        f"year range {_year_range_text(annual)}"
    )
    print(
        f"[loader] quarterly fundamentals: {quarterly['ticker'].nunique() if 'ticker' in quarterly.columns else 0} tickers, "
        f"quarter range {_quarter_range_text(quarterly)}"
    )
    print(
        f"[loader] shareholding: {shareholding['ticker'].nunique() if 'ticker' in shareholding.columns else 0} tickers"
    )
    print(f"[loader] metadata: {metadata['ticker'].nunique() if 'ticker' in metadata.columns else 0} tickers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
