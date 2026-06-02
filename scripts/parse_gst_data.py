#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


def _month_end(dt: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(dt).to_period("M").to_timestamp("M")


def _to_numeric_series(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce")


def _parse_gstr1_file(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None)
    if raw.empty:
        return pd.DataFrame()

    def find_header_index() -> int | None:
        best = None
        for i in range(min(30, len(raw))):
            row = raw.iloc[i]
            dt_count = pd.to_datetime(row, errors="coerce").notna().sum()
            has_state = row.astype(str).str.contains("STATE", case=False, na=False).any()
            if dt_count >= 2 and has_state:
                best = i
                break
        if best is None:
            for i in range(min(30, len(raw))):
                row = raw.iloc[i].astype(str).str.upper()
                if row.str.contains("STATE").any():
                    return i
        return best

    header_idx = find_header_index()
    if header_idx is None or header_idx + 1 >= len(raw):
        return pd.DataFrame()

    header_row = raw.iloc[header_idx]
    subheader_row = raw.iloc[header_idx + 1]

    # Find Grand Total row.
    mask = raw.astype(str).apply(lambda s: s.str.contains("GRAND TOTAL", case=False, na=False))
    if not mask.any(axis=1).any():
        return pd.DataFrame()
    gt_row = raw.loc[mask.any(axis=1)].iloc[0]

    # Map each column to its month (carry forward last date in header row).
    month_for_col: dict[int, pd.Timestamp] = {}
    last_month = None
    for col_idx, val in header_row.items():
        month = pd.to_datetime(val, errors="coerce")
        if pd.notna(month):
            last_month = pd.Timestamp(month).normalize()
        if last_month is not None:
            month_for_col[col_idx] = last_month

    records: list[dict[str, object]] = []
    for col_idx, sub in subheader_row.items():
        if isinstance(sub, str) and "total returns filed" in sub.lower():
            month = month_for_col.get(col_idx)
            if month is None:
                continue
            val = pd.to_numeric(gt_row[col_idx], errors="coerce")
            if pd.isna(val):
                continue
            records.append(
                {
                    "date": _month_end(month),
                    "gst_collection_cr": float(val),
                    "source": "gstr1_total_returns_filed",
                    "source_file": path.name,
                }
            )

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def _parse_pre_gst_pdf(path: Path) -> pd.DataFrame:
    try:
        import pdfplumber
    except Exception as exc:
        raise RuntimeError("pdfplumber is required to parse the pre-GST PDF") from exc

    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return pd.DataFrame()
        tables = pdf.pages[0].extract_tables()
        if not tables:
            return pd.DataFrame()
        table = tables[0]

    if len(table) < 2:
        return pd.DataFrame()

    header = table[0]
    df = pd.DataFrame(table[1:], columns=header)

    year_cols = [c for c in df.columns if re.search(r"20\d{2}-\d{2}", str(c))]
    if not year_cols:
        return pd.DataFrame()

    records: list[dict[str, object]] = []
    for col in year_cols:
        label = str(col)
        m = re.search(r"(20\d{2})-(\d{2})", label)
        if not m:
            continue
        start_year = int(m.group(1))
        months = 12 if "till" not in label.lower() else 3
        vals = pd.to_numeric(df[col].replace("*", np.nan), errors="coerce")
        total = float(vals.sum(skipna=True))
        if total <= 0:
            continue
        start = pd.Timestamp(start_year, 4, 1)
        monthly_value = total / months
        for i in range(months):
            records.append(
                {
                    "date": _month_end(start + pd.DateOffset(months=i)),
                    "gst_collection_cr": monthly_value,
                    "source": "pre_gst_pdf_annual",
                    "source_file": path.name,
                }
            )

    return pd.DataFrame(records)


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("date", kind="mergesort").reset_index(drop=True)
    out["gst_collection_cr"] = _to_numeric_series(out["gst_collection_cr"])
    out["mom_growth"] = out["gst_collection_cr"].pct_change() * 100.0
    out["yoy_growth"] = out["gst_collection_cr"].pct_change(12) * 100.0
    out["gst_mom_pct"] = out["mom_growth"]
    out["gst_yoy_pct"] = out["yoy_growth"]
    out["gst_yoy_growth"] = out["yoy_growth"]
    roll = out["gst_collection_cr"].rolling(12, min_periods=6)
    mean = roll.mean()
    std = roll.std().replace(0.0, np.nan)
    out["gst_zscore_12m"] = (out["gst_collection_cr"] - mean) / std
    trend = out["gst_collection_cr"].rolling(3, min_periods=2).apply(
        lambda x: 1.0 if x.iloc[-1] > x.iloc[0] else (-1.0 if x.iloc[-1] < x.iloc[0] else 0.0),
        raw=False,
    )
    out["gst_3m_trend"] = trend
    out["availability_date"] = out["date"] + pd.Timedelta(days=30)
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parse GST datasets into a monthly time series.")
    p.add_argument(
        "--input-dir",
        type=str,
        default=str(Path("~/Downloads").expanduser()),
        help="Directory containing GSTR-1 Excel files and the pre-GST PDF.",
    )
    p.add_argument(
        "--output",
        type=str,
        default="data/processed/gst_monthly.parquet",
        help="Output parquet path.",
    )
    p.add_argument(
        "--include-pre-gst",
        action="store_true",
        help="Include the pre-GST PDF baseline (2012-2017).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    gstr_files = sorted(input_dir.glob("GSTR-1-*.xlsx"))
    gstr_files = [f for f in gstr_files if not f.name.startswith("~$")]
    if not gstr_files:
        print(f"[gst] no GSTR-1 files found in {input_dir}")

    parts: list[pd.DataFrame] = []
    for f in gstr_files:
        df = _parse_gstr1_file(f)
        if df.empty:
            print(f"[gst] skipped {f.name} (no usable rows)")
            continue
        print(f"[gst] parsed {f.name}: rows={len(df)}")
        parts.append(df)

    if args.include_pre_gst:
        pdf_path = input_dir / "Yearwise-Pre-GST-revenue.pdf"
        if pdf_path.exists():
            pdf_df = _parse_pre_gst_pdf(pdf_path)
            if not pdf_df.empty:
                print(f"[gst] parsed pre-GST PDF: rows={len(pdf_df)}")
                parts.append(pdf_df)
        else:
            print(f"[gst] pre-GST PDF not found at {pdf_path}")

    if not parts:
        print("[gst] no data parsed")
        return 1

    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = (
        df.groupby("date", as_index=False)
        .agg(
            gst_collection_cr=("gst_collection_cr", "mean"),
            source=("source", "last"),
            source_file=("source_file", "last"),
        )
        .sort_values("date", kind="mergesort")
        .reset_index(drop=True)
    )

    df = _build_features(df)
    df.to_parquet(output, index=False)
    print(f"[gst] wrote {output} rows={len(df)} min_date={df['date'].min().date()} max_date={df['date'].max().date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
