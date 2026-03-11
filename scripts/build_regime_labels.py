#!/usr/bin/env python3
"""Build canonical Northstar regime labels for the full historical period."""

from __future__ import annotations

import argparse
import os
import re
import warnings
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.research.regime_engine import RegimeEngine

warnings.filterwarnings(
    "ignore",
    message="Workbook contains no default style, apply openpyxl's default",
    category=UserWarning,
)


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _candidate_excel_paths() -> tuple[list[Path], list[Path]]:
    p50 = [
        Path("data/raw/50_Macroeconomic_Indicators.xlsx"),
        Path("data/raw/50 Macroeconomic Indicators.xlsx"),
        Path("data/macro/raw/50 Macroeconomic Indicators.xlsx"),
    ]
    pother = [
        Path("data/raw/Other_Macroeconomic_Indicators.xlsx"),
        Path("data/raw/Other Macroeconomic Indicators.xlsx"),
        Path("data/macro/raw/Other Macroeconomic Indicators.xlsx"),
    ]

    # Include current backup naming convention.
    p50 += sorted(Path("data/macro/raw").glob("50*Macroeconomic*Indicators*.xlsx*"), reverse=True)
    pother += sorted(Path("data/macro/raw").glob("Other*Macroeconomic*Indicators*.xlsx*"), reverse=True)
    return p50, pother


def _normalize_name(value: object) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "col"


def _looks_like_date_token(value: object) -> bool:
    s = str(value or "").strip()
    if not s:
        return False
    # Common month-year style tokens found in these workbooks.
    if re.match(r"^[A-Za-z]{3}[-_/ ]\d{2,4}$", s):
        return True
    ts = _to_datetime_mixed(pd.Series([s])).iloc[0]
    return bool(pd.notna(ts))


def parse_dates_safe(series: pd.Series) -> pd.Series:
    """
    Try common Indian date formats explicitly before falling back.
    
    This prevents "Could not infer format" UserWarnings when parsing
    heterogeneous date columns in RBI macro Excel files.
    """
    for fmt in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%b-%Y", "%B %Y", "%Y"]:
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            if parsed.notna().mean() > 0.8:
                return parsed
        except Exception:
            continue
    return pd.to_datetime(series, errors="coerce")


def _to_datetime_mixed(values: object) -> pd.Series:
    """
    Parse heterogeneous date formats without repeated format-inference warnings.

    We avoid broad inference in tight loops by trying explicit formats first,
    then falling back once with warnings suppressed.
    """
    s = pd.Series(values) if not isinstance(values, pd.Series) else values.copy()
    if s.empty:
        return pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None)

    raw = s.astype(str).str.strip()
    # Use object staging to safely hold both tz-aware and tz-naive parses.
    out = pd.Series(pd.NaT, index=s.index, dtype="object")

    # Fast path for Excel serial dates.
    numeric = pd.to_numeric(raw, errors="coerce")
    serial_mask = out.isna() & numeric.notna() & (numeric >= 20000) & (numeric <= 90000)
    if bool(serial_mask.any()):
        out.loc[serial_mask] = pd.Timestamp("1899-12-30") + pd.to_timedelta(
            numeric.loc[serial_mask], unit="D"
        )

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%b-%Y",
        "%b %Y",
        "%Y-%m",
    ]
    for fmt in formats:
        mask = out.isna() & raw.ne("") & raw.ne("nan")
        if not bool(mask.any()):
            break
        parsed = pd.to_datetime(raw.loc[mask], errors="coerce", format=fmt)
        out.loc[mask] = parsed

    mask = out.isna() & raw.ne("") & raw.ne("nan")
    if bool(mask.any()):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            out.loc[mask] = pd.to_datetime(raw.loc[mask], errors="coerce", yearfirst=True, dayfirst=False)

    mask = out.isna() & raw.ne("") & raw.ne("nan")
    if bool(mask.any()):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            out.loc[mask] = pd.to_datetime(raw.loc[mask], errors="coerce", dayfirst=True)
    out = pd.to_datetime(out, errors="coerce", utc=True)
    return out.dt.tz_localize(None)


def _extract_table_with_header_detection(path: Path, sheet_name: str) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, engine="openpyxl")
    if raw.empty:
        return pd.DataFrame()

    raw = raw.dropna(axis=1, how="all").dropna(axis=0, how="all")
    if raw.empty:
        return pd.DataFrame()

    best_df = pd.DataFrame()
    best_score = -1.0
    best_hr = -1
    best_hdr: list[str] = []
    max_header = min(12, max(1, len(raw) - 1))
    for hr in range(max_header):
        try:
            hdr = [_normalize_name(x) for x in raw.iloc[hr].tolist()]
            nonblank_hdr = [h for h in hdr if h and h not in {"nan", "none", "col"}]
            if len(nonblank_hdr) < 3:
                continue
            unnamed_ratio = 1.0 - (float(len(nonblank_hdr)) / float(max(len(hdr), 1)))
            body = raw.iloc[hr + 1 :].copy()
            if body.empty:
                continue
            body.columns = hdr
            body = body.dropna(how="all")
            if body.empty:
                continue
            date_col = None
            for c in body.columns:
                if any(k in str(c) for k in ["period", "date", "reporting"]):
                    date_col = c
                    break
            if date_col is None:
                date_col = str(body.columns[0])
            # Disallow "header" rows that are actually data rows (e.g., "dec_2025").
            if _looks_like_date_token(date_col):
                continue
            d = _to_datetime_mixed(body[date_col])
            date_cov = float(d.notna().mean())
            if date_cov < 0.25:
                continue
            date_header_bonus = 0.20 if any(k in str(date_col) for k in ["period", "date", "reporting"]) else 0.0
            numeric_cols = 0
            for c in body.columns:
                if c == date_col:
                    continue
                v = pd.to_numeric(body[c], errors="coerce")
                if float(v.notna().mean()) >= 0.20:
                    numeric_cols += 1
            score = date_cov + date_header_bonus + min(0.40, 0.02 * float(numeric_cols)) - (0.15 * unnamed_ratio)
            if score > best_score:
                best_score = score
                best_df = body.copy()
                best_hr = int(hr)
                best_hdr = hdr
        except Exception:
            continue
    if bool(int(os.environ.get("NORTHSTAR_MACRO_DEBUG_HEADERS", "0") or 0)):
        hdr_preview = best_hdr[:10] if best_hdr else []
        print(
            f"[macro-header] file={path.name} sheet={sheet_name} "
            f"selected_header_row={best_hr} score={best_score:.4f} cols={hdr_preview}"
        )
    return best_df if best_score >= 0.20 else pd.DataFrame()


def _infer_freq(sheet_name: str, dates: pd.Series) -> str:
    s = str(sheet_name or "").lower()
    if "daily" in s:
        return "daily"
    if "monthly" in s:
        return "monthly"
    if "quarter" in s:
        return "quarterly"
    if dates.notna().sum() < 5:
        return "daily"
    ds = _to_datetime_mixed(dates).dropna().sort_values().drop_duplicates()
    if len(ds) < 5:
        return "daily"
    med_days = float(ds.diff().dt.days.dropna().median())
    if med_days >= 70:
        return "quarterly"
    if med_days >= 25:
        return "monthly"
    return "daily"


def _sheet_to_lagged_daily(path: Path, sheet_name: str) -> pd.DataFrame:
    tbl = _extract_table_with_header_detection(path, sheet_name)
    if tbl.empty:
        return pd.DataFrame()

    date_col = None
    for c in tbl.columns:
        if any(k in str(c) for k in ["period", "date", "reporting"]):
            date_col = str(c)
            break
    if date_col is None:
        date_col = str(tbl.columns[0])

    d = _to_datetime_mixed(tbl[date_col])
    freq = _infer_freq(sheet_name, d)
    work = tbl.copy()
    work["date"] = d
    work = work.dropna(subset=["date"]).sort_values("date", kind="mergesort")
    if work.empty:
        return pd.DataFrame()

    # PIT safety:
    # - daily macro series: conservative +1 day
    # - monthly macro series: +30 days
    # - quarterly macro series: +45 days
    lag_days = 1
    if freq == "monthly":
        lag_days = 30
    elif freq == "quarterly":
        lag_days = 45

    work["date"] = _to_datetime_mixed(work["date"]) + pd.Timedelta(days=lag_days)

    prefix = _normalize_name(path.stem) + "_" + _normalize_name(sheet_name)
    keep_cols: dict[str, str] = {}
    for c in work.columns:
        if c in {date_col, "date"}:
            continue
        v = pd.to_numeric(work[c], errors="coerce")
        if float(v.notna().mean()) < 0.20:
            continue
        cname = f"{prefix}_{_normalize_name(c)}"
        work[cname] = v
        keep_cols[cname] = c

    if not keep_cols:
        return pd.DataFrame()

    out = work[["date"] + list(keep_cols.keys())].copy()
    out = out.drop_duplicates(subset=["date"], keep="last").sort_values("date", kind="mergesort")
    return out


def _outer_join_on_date(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for frame in frames:
        if not isinstance(frame, pd.DataFrame) or frame.empty or "date" not in frame.columns:
            continue
        work = frame.copy()
        work["date"] = _to_datetime_mixed(work["date"])
        work = work.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
        if work.empty:
            continue
        work = work.sort_values("date", kind="mergesort")
        work = work.loc[:, ~work.columns.duplicated(keep="last")]
        parts.append(work.set_index("date"))

    if not parts:
        return pd.DataFrame()

    merged = pd.concat(parts, axis=1, join="outer", copy=False)
    merged = merged.loc[:, ~merged.columns.duplicated(keep="last")]
    merged = merged.sort_index(kind="mergesort")
    merged = merged.reset_index().rename(columns={"index": "date"})
    return merged


def _load_macro_from_excel(path: Path) -> pd.DataFrame:
    try:
        xls = pd.ExcelFile(path, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for sh in xls.sheet_names:
        low = str(sh).lower()
        if not any(k in low for k in ["daily", "monthly", "quarter"]):
            continue
        try:
            f = _sheet_to_lagged_daily(path, sh)
        except Exception:
            f = pd.DataFrame()
        if not f.empty:
            frames.append(f)

    if not frames:
        return pd.DataFrame()

    merged = _outer_join_on_date(frames)
    if merged.empty:
        return merged
    return merged.reset_index(drop=True)


def _read_csv_macro_file(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()

    date_col = None
    for c in ["Period", "date", "Date", "Reporting Date", "Unnamed: 1"]:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        return pd.DataFrame()

    d = _to_datetime_mixed(df[date_col])
    out = pd.DataFrame({"date": d})

    name_low = str(path.name).lower()
    # PIT safety for CSV fallback:
    # treat unlabeled/daily series conservatively as T+1.
    lag_days = 1
    if "monthly" in name_low:
        lag_days = 30
    elif "quarter" in name_low:
        lag_days = 45
    out["date"] = out["date"] + pd.Timedelta(days=lag_days)

    prefix = _normalize_name(path.stem)
    for c in df.columns:
        if c == date_col:
            continue
        v = pd.to_numeric(df[c], errors="coerce")
        if float(v.notna().mean()) < 0.20:
            continue
        out[f"{prefix}_{_normalize_name(c)}"] = v

    out = out.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
    return out.sort_values("date", kind="mergesort").reset_index(drop=True)


def _load_macro_df() -> pd.DataFrame:
    p50_cands, pother_cands = _candidate_excel_paths()
    p50 = _first_existing(p50_cands)
    pother = _first_existing(pother_cands)

    frames: list[pd.DataFrame] = []
    if p50 is not None:
        f = _load_macro_from_excel(p50)
        if not f.empty:
            frames.append(f)
    if pother is not None:
        f = _load_macro_from_excel(pother)
        if not f.empty:
            frames.append(f)

    # CSV augmentation/fallback (current repo reality has rich standardized CSVs).
    csv_paths = sorted(Path("data/macro/raw").glob("core_macro_*.csv"))
    base_csv_paths = [p for p in csv_paths if not re.search(r"_v\d+\.csv$", p.name)]
    for p in (base_csv_paths or csv_paths):
        f = _read_csv_macro_file(p)
        if not f.empty:
            frames.append(f)

    if not frames:
        return pd.DataFrame()

    merged = _outer_join_on_date(frames)
    if merged.empty:
        return merged
    return merged.reset_index(drop=True)


def _load_prices(prices_path: Path) -> pd.DataFrame:
    cols = ["Date", "date", "ticker", "Close", "close", "NSE S&P CNX NIFTY", "NIFTY 50"]
    try:
        df = pd.read_parquet(prices_path)
    except Exception as exc:
        raise RuntimeError(f"could_not_read_prices:{prices_path}:{exc}") from exc

    keep = [c for c in cols if c in df.columns]
    if keep:
        return df[keep].copy()
    return df.copy()


def _load_optional(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return None
    except Exception:
        return None


def _load_macro_regime_market() -> pd.DataFrame:
    path = Path("data/processed/macro/macro_regime_features.parquet")
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "ticker" in out.columns:
        out = out[out["ticker"].astype(str).str.upper() == "MARKET"].copy()
    if out.empty:
        return pd.DataFrame()
    out["date"] = _to_datetime_mixed(out.get("date"))
    out["availability_date"] = _to_datetime_mixed(out.get("availability_date", out.get("date")))
    out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort")
    return out


def _load_power_with_fallback(path: Path) -> pd.DataFrame | None:
    direct = _load_optional(path)
    if isinstance(direct, pd.DataFrame) and not direct.empty:
        return direct

    raw_files = sorted(Path("data/raw/macro/cea_power").glob("power_*.csv"))
    if raw_files:
        frames: list[pd.DataFrame] = []
        for f in raw_files:
            try:
                x = pd.read_csv(f)
            except Exception:
                continue
            if x.empty:
                continue
            x["date"] = _to_datetime_mixed(x.get("date"))
            x["availability_date"] = _to_datetime_mixed(x.get("availability_date"))
            miss = x["availability_date"].isna()
            x.loc[miss, "availability_date"] = x.loc[miss, "date"] + pd.Timedelta(days=1)
            frames.append(x)
        if frames:
            out = pd.concat(frames, ignore_index=True)
            out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort")
            if not out.empty:
                return out

    market = _load_macro_regime_market()
    if market.empty:
        return None
    keep = [c for c in ["date", "availability_date", "power_yoy_growth"] if c in market.columns]
    if "power_yoy_growth" not in keep:
        return None
    return market[keep].copy()


def _load_gst_with_fallback(path: Path) -> pd.DataFrame | None:
    direct = _load_optional(path)
    if isinstance(direct, pd.DataFrame) and not direct.empty:
        direct = _normalize_gst_frame(direct)
        if not direct.empty:
            return direct

    raw_files = sorted(Path("data/raw/macro/gst_ewaybill").glob("ewaybill_*.csv"))
    if raw_files:
        frames: list[pd.DataFrame] = []
        for f in raw_files:
            try:
                x = pd.read_csv(f)
            except Exception:
                continue
            if x.empty:
                continue
            x = _normalize_gst_frame(x)
            if x.empty:
                continue
            x["date"] = _to_datetime_mixed(x.get("date"))
            x["availability_date"] = _to_datetime_mixed(x.get("availability_date"))
            miss = x["availability_date"].isna()
            x.loc[miss, "availability_date"] = x.loc[miss, "date"] + pd.Timedelta(days=30)
            frames.append(x)
        if frames:
            out = pd.concat(frames, ignore_index=True)
            out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort")
            if not out.empty:
                return out

    market = _load_macro_regime_market()
    if market.empty:
        return None
    keep = [c for c in ["date", "availability_date", "gst_yoy_growth"] if c in market.columns]
    if "gst_yoy_growth" not in keep:
        return None
    return market[keep].copy()


def _normalize_gst_frame(frame: pd.DataFrame) -> pd.DataFrame:
    f = frame.copy()
    if "state" in f.columns:
        f = f[f["state"].astype(str).str.lower().eq("all india")]
    if "category" in f.columns:
        cats = f["category"].astype(str).str.lower()
        if cats.eq("total").any():
            f = f[cats.eq("total")]
    return f


def _load_sentiment_with_fallback(path: Path) -> pd.DataFrame | None:
    parts: list[pd.DataFrame] = []

    # 1) Primary processed market sentiment (v3 schema).
    direct = _load_optional(path)
    if isinstance(direct, pd.DataFrame) and not direct.empty:
        out = pd.DataFrame()
        out["date"] = _to_datetime_mixed(direct.get("date", direct.get("timestamp"))).dt.normalize()
        out["availability_date"] = _to_datetime_mixed(
            direct.get("availability_date", direct.get("date", direct.get("timestamp")))
        ).dt.normalize()
        miss = out["availability_date"].isna()
        out.loc[miss, "availability_date"] = out.loc[miss, "date"] + BDay(1)
        out["india_market_polarity"] = pd.to_numeric(
            direct.get("india_market_polarity", direct.get("polarity")), errors="coerce"
        )
        out["source_priority"] = 5
        parts.append(out)

    # 2) v3 market fallback.
    market_v3_path = Path("data/sentiment/v3/market_sentiment_india.parquet")
    if market_v3_path.exists():
        try:
            m = pd.read_parquet(market_v3_path)
        except Exception:
            m = pd.DataFrame()
        if not m.empty:
            out = pd.DataFrame()
            out["date"] = _to_datetime_mixed(m.get("date", m.get("timestamp"))).dt.normalize()
            out["availability_date"] = out["date"] + BDay(1)
            out["india_market_polarity"] = pd.to_numeric(
                m.get("india_market_polarity", m.get("polarity")), errors="coerce"
            )
            out["source_priority"] = 4
            parts.append(out)

    # 3) Processed ticker sentiment -> aggregate to market.
    ticker_proc_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
    if ticker_proc_path.exists():
        try:
            t = pd.read_parquet(ticker_proc_path)
        except Exception:
            t = pd.DataFrame()
        if not t.empty:
            d = _to_datetime_mixed(t.get("date", t.get("timestamp"))).dt.normalize()
            ad = _to_datetime_mixed(t.get("availability_date", t.get("date", t.get("timestamp")))).dt.normalize()
            pol = pd.to_numeric(t.get("sentiment_polarity", t.get("sentiment_score")), errors="coerce")
            out = (
                pd.DataFrame({"date": d, "availability_date": ad, "india_market_polarity": pol})
                .dropna(subset=["date"])
                .groupby("date", as_index=False)
                .agg(
                    availability_date=("availability_date", "max"),
                    india_market_polarity=("india_market_polarity", "mean"),
                )
                .sort_values("date", kind="mergesort")
            )
            miss = out["availability_date"].isna()
            out.loc[miss, "availability_date"] = out.loc[miss, "date"] + BDay(1)
            out["source_priority"] = 3
            parts.append(out)

    # 4) v3 ticker fallback -> aggregate to market.
    ticker_v3_path = Path("data/sentiment/v3/company_sentiment_trends.parquet")
    if ticker_v3_path.exists():
        try:
            t = pd.read_parquet(ticker_v3_path)
        except Exception:
            t = pd.DataFrame()
        if not t.empty:
            d = _to_datetime_mixed(t.get("timestamp", t.get("date"))).dt.normalize()
            pol = pd.to_numeric(t.get("sentiment_score", t.get("sentiment_polarity")), errors="coerce")
            out = (
                pd.DataFrame({"date": d, "india_market_polarity": pol})
                .dropna(subset=["date"])
                .groupby("date", as_index=False)["india_market_polarity"]
                .mean()
                .sort_values("date", kind="mergesort")
            )
            out["availability_date"] = out["date"] + BDay(1)
            out["source_priority"] = 2
            parts.append(out)

    # 5) News dataset fallback -> aggregate sentiment if available.
    for p in [Path("data/processed/news/news_dataset.parquet"), Path("data/processed/news/news_dataset.csv")]:
        if not p.exists():
            continue
        try:
            n = pd.read_parquet(p) if p.suffix.lower() == ".parquet" else pd.read_csv(p)
        except Exception:
            continue
        if n.empty or "sentiment" not in n.columns:
            continue
        d = _to_datetime_mixed(n.get("date", n.get("timestamp"))).dt.normalize()
        pol = pd.to_numeric(n.get("sentiment"), errors="coerce")
        out = (
            pd.DataFrame({"date": d, "india_market_polarity": pol})
            .dropna(subset=["date"])
            .groupby("date", as_index=False)["india_market_polarity"]
            .mean()
            .sort_values("date", kind="mergesort")
        )
        out["availability_date"] = out["date"] + BDay(1)
        out["source_priority"] = 1
        parts.append(out)
        break

    if not parts:
        return None
    merged = pd.concat(parts, ignore_index=True)
    merged["date"] = _to_datetime_mixed(merged["date"]).dt.normalize()
    merged["availability_date"] = _to_datetime_mixed(merged["availability_date"]).dt.normalize()
    merged["india_market_polarity"] = pd.to_numeric(merged["india_market_polarity"], errors="coerce")
    merged = merged.dropna(subset=["date"])
    merged = merged.sort_values(["date", "source_priority"], kind="mergesort")
    merged = merged.drop_duplicates(subset=["date"], keep="last")
    return merged[["date", "availability_date", "india_market_polarity"]].reset_index(drop=True)


def _print_summary(labels: pd.DataFrame) -> None:
    total = int(len(labels))
    dist = labels["regime"].astype(str).value_counts(dropna=False)
    macro_cov = float(pd.to_numeric(labels["macro_activity_score"], errors="coerce").notna().mean())
    power_series = pd.to_numeric(labels["power_yoy_growth"], errors="coerce")
    gst_series = pd.to_numeric(labels["gst_yoy_growth"], errors="coerce")
    sent_series = pd.to_numeric(labels["sentiment_polarity"], errors="coerce")
    power_cov = float(power_series.notna().mean())
    gst_cov = float(gst_series.notna().mean())
    sent_cov = float(sent_series.notna().mean())

    def _window_cov(series: pd.Series) -> tuple[pd.Timestamp | None, float]:
        if not series.notna().any():
            return None, 0.0
        first = pd.to_datetime(labels.loc[series.notna(), "date"].min())
        window = labels.loc[labels["date"] >= first, series.name].notna().mean()
        return first, float(window)

    power_first, power_cov_window = _window_cov(power_series)
    gst_first, gst_cov_window = _window_cov(gst_series)
    sent_first, sent_cov_window = _window_cov(sent_series)

    print("=== Regime Label Summary ===")
    print(f"Total dates: {total}")
    print("Regime distribution:")
    for regime, n in dist.items():
        pct = (float(n) / float(max(total, 1))) * 100.0
        print(f"  {str(regime):<35} {int(n):>6} dates ({pct:>5.1f}%)")
    print("")
    print(f"Macro coverage: {macro_cov * 100.0:.1f}% of dates have macro dimension")
    print(f"CEA coverage: {power_cov * 100.0:.1f}% of dates have power data")
    if power_first is not None:
        print(f"CEA coverage (since {power_first.date()}): {power_cov_window * 100.0:.1f}%")
    print(f"GST coverage: {gst_cov * 100.0:.1f}% of dates have GST data")
    if gst_first is not None:
        print(f"GST coverage (since {gst_first.date()}): {gst_cov_window * 100.0:.1f}%")
    print(f"Sentiment coverage: {sent_cov * 100.0:.1f}% of dates have sentiment data")
    if sent_first is not None:
        print(f"Sentiment coverage (since {sent_first.date()}): {sent_cov_window * 100.0:.1f}%")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build canonical Northstar regime labels.")
    p.add_argument("--prices-path", type=str, default="data/processed/prices.parquet")
    p.add_argument("--output-path", type=str, default="data/processed/regime_labels.parquet")
    p.add_argument("--power-path", type=str, default="data/processed/macro/cea_power_daily.parquet")
    p.add_argument("--gst-path", type=str, default="data/processed/gst_monthly.parquet")
    p.add_argument(
        "--sentiment-path",
        type=str,
        default="data/processed/sentiment/market_sentiment_daily.parquet",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    prices_path = Path(args.prices_path)
    output_path = Path(args.output_path)

    prices_df = _load_prices(prices_path)
    macro_df = _load_macro_df()
    power_df = _load_power_with_fallback(Path(args.power_path))
    gst_df = _load_gst_with_fallback(Path(args.gst_path))
    sentiment_df = _load_sentiment_with_fallback(Path(args.sentiment_path))

    print(
        "[regime-labels] optional_sources "
        f"power_rows={0 if power_df is None else int(len(power_df))} "
        f"gst_rows={0 if gst_df is None else int(len(gst_df))} "
        f"sentiment_rows={0 if sentiment_df is None else int(len(sentiment_df))}"
    )

    engine = RegimeEngine(config={"regime_labels_path": str(output_path)})
    labels = engine.build_historical_regimes(
        prices_df=prices_df,
        macro_df=macro_df if isinstance(macro_df, pd.DataFrame) and not macro_df.empty else None,
        power_df=power_df,
        gst_df=gst_df,
        sentiment_df=sentiment_df,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels.to_parquet(output_path, index=False)

    _print_summary(labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
