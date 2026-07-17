#!/usr/bin/env python3
"""Build canonical cross-source datasets for research and live integration."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.load_screener_to_pipeline import (  # noqa: E402
    _build_annual,
    _build_quarterly,
    _build_shareholding,
    _parse_quarter_end,
)
from src.signals.credit_ratings import rating_to_numeric  # noqa: E402


# 1 crore = 1e7 rupees. Screener quarterly values are reported in ₹ crores;
# yfinance reports in absolute rupees, so its monetary fields are divided by
# this to align units before the two sources are merged.
_RUPEES_PER_CRORE = 1e7
_YFINANCE_QUARTERLY_PATH = REPO_ROOT / "data/processed/fundamentals.parquet"
# Indian quarterly results are filed ~45 days after quarter-end; screener rows
# use exactly this lag for availability_date, so match it for yfinance rows.
_QUARTERLY_REPORT_LAG_DAYS = 45

# The native yfinance fundamentals panel is QUARTERLY. To build a true ANNUAL
# figure we must aggregate the four fiscal-year quarters correctly: income-
# statement / cash-flow FLOWS are summed over the year, while balance-sheet
# STOCKS (and share counts) are point-in-time and take the fiscal-year-end
# value. Treating the Jan–Mar quarter as "the year" (the historical bug)
# understated every recent annual by ~4x and broke YoY growth.
_NATIVE_FLOW_COLS = frozenset({
    "revenue", "gross_profit", "cost_of_revenue", "ebitda", "operating_income",
    "net_income", "tax_provision", "other_income", "restructuring_charges",
    "impairment_charges", "bad_debt_expense", "operating_cash_flow", "capex",
    "free_cash_flow", "depreciation_amortization", "depreciation", "amortization",
    "interest_expense", "change_in_working_capital", "interest_paid_cfo",
    "interest_received_cfo", "cash_dividends_paid",
})
_NATIVE_STOCK_COLS = frozenset({
    "total_assets", "equity", "total_debt", "minority_interest",
    "cash_and_equivalents", "receivables", "inventory", "payables",
    "working_capital", "deferred_revenue", "lease_liabilities", "gross_ppe",
    "shares_outstanding",
})


def _build_quarterly_yfinance(path: Path = _YFINANCE_QUARTERLY_PATH) -> "pd.DataFrame":
    """Map the yfinance processed fundamentals (data/processed/fundamentals.parquet,
    produced by src/processing/fundamental_processor.py) into the same
    pre-normalization schema the screener quarterly path yields, so the two can
    be merged in build_fundamentals_quarterly. Monetary fields are converted
    from absolute rupees to ₹ crores; EPS is derived as net_income /
    shares_outstanding (already ₹/share, no scaling). Returns empty if the file
    is absent."""
    if not path.exists():
        return pd.DataFrame()
    try:
        raw = pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    if raw.empty or "ticker" not in raw.columns or "date" not in raw.columns:
        return pd.DataFrame()

    df = raw.copy()
    qend = pd.to_datetime(df["date"], errors="coerce")
    df = df[qend.notna()].copy()
    qend = qend[qend.notna()]
    # Keep only calendar quarter-ends (Mar/Jun/Sep/Dec) to align to screener quarters.
    keep = qend.dt.month.isin([3, 6, 9, 12])
    df = df[keep.values].copy()
    qend = qend[keep.values]
    if df.empty:
        return pd.DataFrame()

    qnum = ((qend.dt.month - 1) // 3 + 1).astype(int)
    out = pd.DataFrame(index=df.index)
    out["ticker"] = df["ticker"].map(_normalize_ticker)
    out["quarter"] = ["Q%d-%d" % (q, y) for q, y in zip(qnum.values, qend.dt.year.values)]
    out["availability_date"] = (qend + pd.to_timedelta(_QUARTERLY_REPORT_LAG_DAYS, unit="D")).dt.normalize().values

    def _cr(col: str):
        return pd.to_numeric(df[col], errors="coerce") / _RUPEES_PER_CRORE if col in df.columns else np.nan

    out["revenue"] = _cr("revenue")
    out["sales"] = _cr("revenue")
    out["net_profit"] = _cr("net_income")
    out["operating_profit"] = _cr("operating_income")
    out["other_income"] = _cr("other_income")
    out["interest"] = _cr("interest_expense")
    out["depreciation"] = _cr("depreciation")

    ni = pd.to_numeric(df.get("net_income"), errors="coerce")
    sh = pd.to_numeric(df.get("shares_outstanding"), errors="coerce")
    out["eps_in_rs"] = np.where((sh.notna()) & (sh != 0), ni / sh, np.nan)

    out["record_origin"] = "yfinance"
    out = out[out["ticker"] != ""].copy()
    return out.reset_index(drop=True)


def _annualize_native_quarterly(native_q: "pd.DataFrame") -> "pd.DataFrame":
    """Aggregate the QUARTERLY native yfinance panel into true ANNUAL rows.

    Indian fiscal year ends 31 March: quarters ending Jun/Sep/Dec of calendar
    year Y-1 and Mar of year Y all belong to fiscal_year = Y. FLOW items are
    summed over the year; STOCK (balance-sheet) items and share counts take the
    fiscal-year-end (latest quarter in the FY) value. A flow is only emitted for
    a COMPLETE fiscal year (all four quarter-ends present with values); an
    incomplete recent year yields NaN flows rather than a partial-year
    understatement — the caller then falls back to the screener annual or NaN.

    Expects `native_q` already in ₹ crores (monetary) with a normalized
    `report_date` (quarter-end) and normalized `ticker`.
    """
    if native_q is None or native_q.empty:
        return pd.DataFrame(columns=["ticker", "fiscal_year", "report_date", "native_availability_date"])
    work = native_q.dropna(subset=["ticker", "report_date"]).copy()
    work = work[work["ticker"] != ""]
    if work.empty:
        return pd.DataFrame(columns=["ticker", "fiscal_year", "report_date", "native_availability_date"])
    month = work["report_date"].dt.month
    work["fiscal_year"] = (work["report_date"].dt.year + (month > 3).astype(int)).astype(int)
    if "availability_date" in work.columns:
        avail = _as_dates(work["availability_date"]).dt.normalize()
    else:
        avail = pd.Series(pd.NaT, index=work.index)
    work["_avail"] = avail.fillna(work["report_date"] + pd.Timedelta(days=_QUARTERLY_REPORT_LAG_DAYS))

    reserved = {"ticker", "report_date", "date", "availability_date", "fiscal_year", "_avail"}
    value_cols = [c for c in work.columns if c not in reserved]
    flow_cols = [c for c in value_cols if c in _NATIVE_FLOW_COLS]
    # Anything not classified as a flow is treated as point-in-time (safe: never
    # inflates by summing a balance). shares_outstanding sits here too.
    stock_cols = [c for c in value_cols if c not in _NATIVE_FLOW_COLS]

    rows: list[dict[str, Any]] = []
    work = work.sort_values(["ticker", "fiscal_year", "report_date"], kind="mergesort")
    for (ticker, fiscal_year), grp in work.groupby(["ticker", "fiscal_year"], sort=False):
        n_quarters = int(grp["report_date"].dt.month.nunique())
        complete_year = n_quarters >= 4
        rec: dict[str, Any] = {
            "ticker": ticker,
            "fiscal_year": int(fiscal_year),
            "report_date": pd.Timestamp(year=int(fiscal_year), month=3, day=31),
            "native_availability_date": grp["_avail"].max(),
        }
        for col in flow_cols:
            vals = pd.to_numeric(grp[col], errors="coerce")
            rec[col] = float(vals.sum()) if (complete_year and int(vals.notna().sum()) >= 4) else np.nan
        for col in stock_cols:
            vals = pd.to_numeric(grp[col], errors="coerce").dropna()
            rec[col] = float(vals.iloc[-1]) if len(vals) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_ticker(value: Any) -> str:
    s = _clean_text(value).upper()
    if not s or s in {"NAN", "NONE", "NULL", "<NA>"}:
        return ""
    if "|" in s:
        s = s.split("|", 1)[-1]
    if ":" in s:
        s = s.split(":", 1)[-1]
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    s = s.replace(" ", "")
    if not s or s in {"NAN", "NONE", "NULL"}:
        return ""
    return f"{s}.NS"


def _ticker_stem(value: Any) -> str:
    s = _clean_text(value).upper()
    if not s or s in {"NAN", "NONE", "NULL", "<NA>"}:
        return ""
    if "|" in s:
        s = s.split("|", 1)[-1]
    if ":" in s:
        s = s.split(":", 1)[-1]
    if s.endswith(".NS") or s.endswith(".BO"):
        s = s.rsplit(".", 1)[0]
    elif "." in s:
        s = s.split(".", 1)[0]
    return s.replace(" ", "")


def _as_dates(series: Any, *, dayfirst: bool = False) -> pd.Series:
    out = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)
    try:
        out = out.dt.tz_localize(None)
    except Exception:
        try:
            out = out.dt.tz_convert(None)
        except Exception:
            pass
    return out


def _next_business_day(series: pd.Series) -> pd.Series:
    base = _as_dates(series)
    out = base + BDay(1)
    return pd.to_datetime(out, errors="coerce")


def _numeric(series: Any) -> pd.Series:
    if isinstance(series, pd.Series):
        src = series.astype(str).str.replace(",", "", regex=False)
        return pd.to_numeric(src, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def _slug(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _coalesce(df: pd.DataFrame, *cols: str, default: Any = np.nan) -> pd.Series:
    out = pd.Series(np.nan, index=df.index)
    for col in cols:
        if col in df.columns:
            candidate = df[col]
            if isinstance(candidate, pd.DataFrame):
                candidate = candidate.iloc[:, 0]
            elif not isinstance(candidate, pd.Series):
                candidate = pd.Series(candidate, index=df.index)
            out = out.where(out.notna(), candidate)
    if isinstance(default, pd.DataFrame):
        default = default.iloc[:, 0]
    if isinstance(default, pd.Series):
        out = out.where(out.notna(), default)
    else:
        try:
            is_missing_default = bool(pd.isna(default))
        except Exception:
            is_missing_default = False
        if not is_missing_default:
            out = out.fillna(default)
    return out


def _first_existing(df: pd.DataFrame, names: Iterable[str]) -> Optional[str]:
    lower_map = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name in df.columns:
            return str(name)
        hit = lower_map.get(str(name).lower())
        if hit is not None:
            return str(hit)
    return None


def _extract_timestamp_from_name(path: Path) -> str:
    m = re.search(r"_(\d{8}_\d{6})$", path.name)
    return m.group(1) if m else ""


def _latest_path(pattern: str) -> Optional[Path]:
    paths = list((REPO_ROOT / "data").glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda p: (p.stat().st_mtime, p.name))


def _extract_unit(label: Any) -> str:
    text = _clean_text(label)
    if not text:
        return ""
    m = re.search(r"\(([^)]{1,120})\)", text)
    return _clean_text(m.group(1)) if m else ""


def _strip_unit(label: Any) -> str:
    text = _clean_text(label)
    if not text:
        return ""
    text = re.sub(r"\([^)]{1,120}\)", "", text)
    return _clean_text(text)


class CanonicalDatasetBuilder:
    def __init__(self, canonical_root: Path):
        self.root = canonical_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.frames: dict[str, pd.DataFrame] = {}
        self.manifest: dict[str, Any] = {
            "generated_at": datetime.now(tz=pd.Timestamp.utcnow().tz).isoformat(),
            "canonical_root": str(self.root.relative_to(REPO_ROOT)),
            "outputs": {},
            "warnings": [],
            "source_artifacts": {},
        }

    def _warn(self, msg: str) -> None:
        print(f"[canonical] warning: {msg}")
        self.manifest["warnings"].append(str(msg))

    def _record_source(self, key: str, path: Path | None) -> None:
        self.manifest["source_artifacts"][key] = str(path.relative_to(REPO_ROOT)) if path else None

    def _profile(
        self,
        df: pd.DataFrame,
        *,
        date_cols: Iterable[str] = ("date", "availability_date"),
        entity_col: str | None = "ticker",
    ) -> dict[str, Any]:
        profile: dict[str, Any] = {
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
        }
        if entity_col and entity_col in df.columns:
            profile["unique_entities"] = int(df[entity_col].astype(str).replace("", np.nan).dropna().nunique())
        for col in date_cols:
            if col in df.columns:
                d = pd.to_datetime(df[col], errors="coerce")
                if d.notna().any():
                    profile[f"{col}_min"] = str(d.min())
                    profile[f"{col}_max"] = str(d.max())
        return profile

    def _ensure_unique_columns(self, key: str, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        if not df.columns.duplicated().any():
            return df
        dupes = pd.Index(df.columns[df.columns.duplicated()]).astype(str).tolist()
        self._warn(f"{key} duplicate columns removed: {sorted(set(dupes))}")
        return df.loc[:, ~df.columns.duplicated()].copy()

    def _write_parquet(
        self,
        key: str,
        df: pd.DataFrame,
        rel_path: str,
        *,
        date_cols: Iterable[str] = ("date", "availability_date"),
        entity_col: str | None = "ticker",
    ) -> Path:
        df = self._ensure_unique_columns(key, df)
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        self.frames[key] = df
        self.manifest["outputs"][key] = {
            "path": str(path.relative_to(REPO_ROOT)),
            **self._profile(df, date_cols=date_cols, entity_col=entity_col),
        }
        print(f"[canonical] wrote {key}: {path.relative_to(REPO_ROOT)} rows={len(df):,}")
        return path

    def _write_csv(
        self,
        key: str,
        df: pd.DataFrame,
        rel_path: str,
        *,
        date_cols: Iterable[str] = ("date", "availability_date"),
        entity_col: str | None = "ticker",
    ) -> Path:
        df = self._ensure_unique_columns(key, df)
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        self.frames[key] = df
        self.manifest["outputs"][key] = {
            "path": str(path.relative_to(REPO_ROOT)),
            **self._profile(df, date_cols=date_cols, entity_col=entity_col),
        }
        print(f"[canonical] wrote {key}: {path.relative_to(REPO_ROOT)} rows={len(df):,}")
        return path

    def _write_bundle(
        self,
        key: str,
        df: pd.DataFrame,
        rel_stem: str,
        *,
        date_cols: Iterable[str] = ("date", "availability_date"),
        entity_col: str | None = "ticker",
        write_csv: bool = True,
    ) -> None:
        df = self._ensure_unique_columns(key, df)
        parquet_path = self.root / f"{rel_stem}.parquet"
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)
        csv_path = None
        if write_csv:
            csv_path = self.root / f"{rel_stem}.csv"
            df.to_csv(csv_path, index=False)
        self.frames[key] = df
        self.manifest["outputs"][key] = {
            "path": str(parquet_path.relative_to(REPO_ROOT)),
            "csv_path": str(csv_path.relative_to(REPO_ROOT)) if csv_path else None,
            **self._profile(df, date_cols=date_cols, entity_col=entity_col),
        }
        print(f"[canonical] wrote {key}: {parquet_path.relative_to(REPO_ROOT)} rows={len(df):,}")

    def _load_optional_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, low_memory=False)

    def _merge_active_and_delisted(
        self,
        *,
        active: pd.DataFrame,
        delisted: pd.DataFrame,
        key_cols: list[str],
        sort_cols: list[str],
        active_label: str,
        delisted_label: str,
    ) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        if isinstance(active, pd.DataFrame) and not active.empty:
            active_work = active.copy()
            active_work["is_delisted"] = False
            active_work["record_origin"] = str(active_label)
            frames.append(active_work)
        if isinstance(delisted, pd.DataFrame) and not delisted.empty:
            delisted_work = delisted.copy()
            delisted_work["is_delisted"] = True
            delisted_work["record_origin"] = str(delisted_label)
            frames.append(delisted_work)
        if not frames:
            return pd.DataFrame()

        merged = pd.concat(frames, ignore_index=True, sort=False)
        keep_keys = [col for col in key_cols if col in merged.columns]
        if keep_keys:
            merged = merged.drop_duplicates(subset=keep_keys, keep="first")
        keep_sort = [col for col in sort_cols if col in merged.columns]
        if keep_sort:
            merged = merged.sort_values(keep_sort, kind="mergesort")
        return merged.reset_index(drop=True)

    def _build_delisted_price_backfill(self) -> pd.DataFrame:
        output_path = REPO_ROOT / "data/processed/delisted_prices.parquet"
        raw_dir = REPO_ROOT / "data/raw/prices_daily"
        delist_path = REPO_ROOT / "data/universe/delisting_database.parquet"
        self._record_source("prices_delisting_database", delist_path if delist_path.exists() else None)
        self._record_source("prices_raw_daily_dir", raw_dir if raw_dir.exists() else None)

        empty = pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "availability_date",
                "source",
                "raw_symbol",
                "raw_source_path",
                "delisting_date",
                "source_exchange",
            ]
        )

        if not raw_dir.exists() or not delist_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            empty.to_parquet(output_path, index=False)
            self.manifest["outputs"]["delisted_price_backfill"] = {
                "path": str(output_path.relative_to(REPO_ROOT)),
                **self._profile(empty, date_cols=("date", "availability_date", "delisting_date"), entity_col="ticker"),
            }
            return empty

        delist = pd.read_parquet(delist_path)
        if delist.empty:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            empty.to_parquet(output_path, index=False)
            self.manifest["outputs"]["delisted_price_backfill"] = {
                "path": str(output_path.relative_to(REPO_ROOT)),
                **self._profile(empty, date_cols=("date", "availability_date", "delisting_date"), entity_col="ticker"),
            }
            return empty

        lookup_rows: list[dict[str, Any]] = []
        delist = delist.copy()
        delist["canonical_ticker"] = delist.get("symbol", "").map(_normalize_ticker)
        delist["delisting_date"] = _as_dates(delist.get("delisting_date")).dt.normalize()
        for _, row in delist.iterrows():
            canonical_ticker = _normalize_ticker(row.get("canonical_ticker", row.get("symbol", "")))
            if not canonical_ticker:
                continue
            keys = {
                _ticker_stem(canonical_ticker),
                _ticker_stem(row.get("symbol", "")),
                _ticker_stem(row.get("original_symbol", "")),
            }
            for key in keys:
                if not key:
                    continue
                lookup_rows.append(
                    {
                        "match_key": key,
                        "ticker": canonical_ticker,
                        "delisting_date": row.get("delisting_date"),
                    }
                )
        lookup = pd.DataFrame(lookup_rows)
        if lookup.empty:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            empty.to_parquet(output_path, index=False)
            self.manifest["outputs"]["delisted_price_backfill"] = {
                "path": str(output_path.relative_to(REPO_ROOT)),
                **self._profile(empty, date_cols=("date", "availability_date", "delisting_date"), entity_col="ticker"),
            }
            return empty

        lookup = (
            lookup.sort_values(["match_key", "ticker", "delisting_date"], kind="mergesort")
            .drop_duplicates(subset=["match_key"], keep="first")
            .set_index("match_key")
        )

        frames: list[pd.DataFrame] = []
        for path in sorted(raw_dir.rglob("*.csv")):
            match_key = _ticker_stem(path.stem)
            if not match_key or match_key not in lookup.index:
                continue
            try:
                raw = pd.read_csv(path, low_memory=False)
            except Exception:
                continue
            date_col = _first_existing(raw, ["Date", "date"])
            if date_col is None:
                continue

            work = raw.copy()
            work["date"] = _as_dates(work.get(date_col)).dt.normalize()
            for src, dst in [
                ("Open", "open"),
                ("High", "high"),
                ("Low", "low"),
                ("Close", "close"),
                ("Adj Close", "adj_close"),
                ("AdjClose", "adj_close"),
                ("Adj_Close", "adj_close"),
                ("Volume", "volume"),
            ]:
                col = _first_existing(work, [src, dst])
                work[dst] = _numeric(work.get(col)) if col is not None else np.nan

            if work["close"].isna().all() and work["adj_close"].notna().any():
                work["close"] = work["adj_close"]

            work = work.dropna(subset=["date"])
            work = work[
                work[["open", "high", "low", "close", "adj_close", "volume"]].notna().any(axis=1)
            ].copy()
            if work.empty:
                continue

            meta = lookup.loc[match_key]
            if isinstance(meta, pd.DataFrame):
                meta = meta.iloc[0]
            canonical_ticker = _normalize_ticker(meta.get("ticker", ""))
            if not canonical_ticker:
                continue
            delisting_date = pd.to_datetime(meta.get("delisting_date"), errors="coerce")
            if pd.notna(delisting_date):
                work = work[work["date"] <= delisting_date.normalize()].copy()
            if work.empty:
                continue

            work["ticker"] = canonical_ticker
            work["availability_date"] = work["date"]
            work["raw_symbol"] = path.stem
            work["raw_source_path"] = str(path.relative_to(REPO_ROOT))
            work["delisting_date"] = delisting_date.normalize() if pd.notna(delisting_date) else pd.NaT
            work["source_exchange"] = "NS" if path.stem.upper().endswith(".NS") else ("BO" if path.stem.upper().endswith(".BO") else "UNK")
            work["source"] = "delisted_raw_price_backfill"
            covers_delist = bool(pd.notna(delisting_date) and work["date"].max() >= (delisting_date.normalize() - pd.Timedelta(days=10)))
            work["_covers_delist"] = 0 if covers_delist else 1
            work["_exchange_priority"] = work["source_exchange"].map({"NS": 0, "BO": 1, "UNK": 2}).fillna(3).astype(int)
            work["_history_rank"] = -int(work["close"].notna().sum())
            frames.append(
                work[
                    [
                        "date",
                        "ticker",
                        "open",
                        "high",
                        "low",
                        "close",
                        "adj_close",
                        "volume",
                        "availability_date",
                        "source",
                        "raw_symbol",
                        "raw_source_path",
                        "delisting_date",
                        "source_exchange",
                        "_covers_delist",
                        "_exchange_priority",
                        "_history_rank",
                    ]
                ].copy()
            )

        backfill = pd.concat(frames, ignore_index=True, sort=False) if frames else empty.copy()
        if not backfill.empty:
            backfill = (
                backfill.sort_values(
                    ["ticker", "date", "_covers_delist", "_exchange_priority", "_history_rank", "raw_source_path"],
                    kind="mergesort",
                )
                .drop_duplicates(subset=["ticker", "date"], keep="first")
                .drop(columns=["_covers_delist", "_exchange_priority", "_history_rank"], errors="ignore")
                .sort_values(["ticker", "date"], kind="mergesort")
                .reset_index(drop=True)
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        backfill.to_parquet(output_path, index=False)
        self.manifest["outputs"]["delisted_price_backfill"] = {
            "path": str(output_path.relative_to(REPO_ROOT)),
            **self._profile(backfill, date_cols=("date", "availability_date", "delisting_date"), entity_col="ticker"),
        }
        print(f"[canonical] wrote delisted_price_backfill: {output_path.relative_to(REPO_ROOT)} rows={len(backfill):,}")
        return backfill

    def build_prices(self) -> pd.DataFrame:
        canonical_existing_path = REPO_ROOT / "data/canonical/prices/equity_prices_daily.parquet"
        primary_path = REPO_ROOT / "data/processed/prices.parquet"
        generated_delisted = self._build_delisted_price_backfill()
        delisted_candidates = [
            REPO_ROOT / "data/processed/delisted_prices.parquet",
            REPO_ROOT / "data/universe/delisted_price_backfill.parquet",
            REPO_ROOT / "data/universe/delisted_prices.parquet",
        ]
        delisted_path = next((p for p in delisted_candidates if p.exists()), None)
        self._record_source("prices_existing_canonical", canonical_existing_path if canonical_existing_path.exists() else None)
        self._record_source("prices", primary_path if primary_path.exists() else None)
        self._record_source("prices_delisted_backfill", delisted_path if delisted_path and delisted_path.exists() else None)
        if not canonical_existing_path.exists() and not primary_path.exists() and delisted_path is None:
            self._warn("processed prices parquet missing")
            out = pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume", "availability_date", "source"])
            self._write_parquet("prices_daily", out, "prices/equity_prices_daily.parquet")
            return out

        def _standardize_price_frame(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
            rename_map = {
                "Date": "date",
                "Ticker": "ticker",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
            work = df.rename(columns=rename_map).copy()
            work["date"] = _as_dates(work.get("date")).dt.normalize()
            work["ticker"] = work.get("ticker", "").map(_normalize_ticker)
            for col in ["open", "high", "low", "close", "volume"]:
                work[col] = _numeric(work.get(col))
            work = work.dropna(subset=["date"])
            work = work[work["ticker"] != ""].copy()
            if "availability_date" in work.columns:
                availability = _as_dates(work.get("availability_date")).dt.normalize()
                work["availability_date"] = availability.fillna(work["date"])
            else:
                work["availability_date"] = work["date"]
            if "source" not in work.columns:
                work["source"] = str(source_label)
            work["source"] = work["source"].fillna(str(source_label)).astype(str)
            priority = {"processed_prices": 0, "existing_canonical_prices": 1}.get(str(source_label), 2)
            work["source_priority"] = priority
            keep = ["date", "ticker", "open", "high", "low", "close", "volume", "availability_date", "source"]
            return work[keep + ["source_priority"]].reset_index(drop=True)

        frames: list[pd.DataFrame] = []
        if canonical_existing_path.exists():
            frames.append(_standardize_price_frame(pd.read_parquet(canonical_existing_path), "existing_canonical_prices"))
        if primary_path.exists():
            frames.append(_standardize_price_frame(pd.read_parquet(primary_path), "processed_prices"))
        if not generated_delisted.empty:
            frames.append(_standardize_price_frame(generated_delisted, "delisted_price_backfill"))
        elif delisted_path is not None and delisted_path.exists():
            frames.append(_standardize_price_frame(pd.read_parquet(delisted_path), "delisted_price_backfill"))
        work = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
        work = (
            work.sort_values(["ticker", "date", "source_priority"], kind="mergesort")
            .drop_duplicates(["ticker", "date"], keep="first")
            .drop(columns=["source_priority"], errors="ignore")
        )
        # Enforce the trading-clean invariant at the canonical layer too. The
        # clean processed panel wins on shared (ticker, date), but the stale
        # existing_canonical still contributes fabricated NSE-holiday/weekend rows
        # on dates the clean panel no longer has (only the corrupt mega-caps ever
        # had them), which would otherwise survive the merge. Drop them here so
        # equity_prices_daily can never re-inject the corruption fixed upstream.
        # See src/data/price_sanitizer + scripts/ci/check_price_integrity.
        if not work.empty:
            from src.processing.price_processor import drop_non_session_rows, trim_frozen_runs
            # Trim forward-filled frozen runs (post-delisting fills from the
            # existing-canonical / backfill sources; active names move daily and
            # are untouched), then drop fabricated non-session rows.
            work, n_frozen = trim_frozen_runs(work, date_col="date", ticker_col="ticker")
            if n_frozen:
                self._warn(f"prices_daily: trimmed {n_frozen} forward-filled frozen rows")
            work, n_non_session = drop_non_session_rows(work, date_col="date", ticker_col="ticker")
            if n_non_session:
                self._warn(f"prices_daily: dropped {n_non_session} fabricated non-session rows")
        self._write_parquet("prices_daily", work.reset_index(drop=True), "prices/equity_prices_daily.parquet")
        return work

    def build_fundamentals_annual(self) -> pd.DataFrame:
        native_path = REPO_ROOT / "data/processed/fundamentals.parquet"
        screener_csv = REPO_ROOT / "data/processed/screener_fundamentals_annual.csv"
        screener_delisted_csv = REPO_ROOT / "data/processed/screener_delisted/screener_fundamentals_annual.csv"
        screener_raw_dir = REPO_ROOT / "data/raw/vendors/screener/financials"
        self._record_source("fundamentals_native", native_path if native_path.exists() else None)
        self._record_source("fundamentals_screener_processed", screener_csv if screener_csv.exists() else None)
        self._record_source(
            "fundamentals_screener_delisted_processed",
            screener_delisted_csv if screener_delisted_csv.exists() else None,
        )

        native = pd.read_parquet(native_path) if native_path.exists() else pd.DataFrame()
        if not native.empty:
            native = native.copy()
            # CRITICAL UNIT ALIGNMENT: the native yfinance panel
            # (data/processed/fundamentals.parquet) reports every monetary field
            # in ABSOLUTE RUPEES, whereas the screener panel — and every
            # downstream consumer of this annual panel — works in ₹ CRORES. The
            # quarterly builder already converts via _build_quarterly_yfinance's
            # _cr() helper; the annual path historically did NOT, so native rows
            # entered the coalesced panel 1e7x larger than screener rows in the
            # SAME columns (revenue/net_income/total_assets/…), corrupting every
            # growth/margin/leverage factor at the native↔screener boundary
            # (TCS FY2024=₹240,893cr → FY2025=6.4e11). Convert here, once, before
            # the native_ prefix + coalesce so both sources share the ₹cr unit.
            # shares_outstanding is a COUNT, not money — never scale it.
            _native_non_monetary = {"ticker", "date", "availability_date", "shares_outstanding"}
            for _col in native.columns:
                if _col in _native_non_monetary:
                    continue
                _vals = pd.to_numeric(native[_col], errors="coerce")
                if _vals.notna().any():
                    native[_col] = _vals / _RUPEES_PER_CRORE
            native["ticker"] = native.get("ticker", "").map(_normalize_ticker)
            native["report_date"] = _as_dates(native.get("date")).dt.normalize()
            # The native panel is QUARTERLY. Aggregate it into true fiscal-year
            # annuals (sum flows over the 4 quarters, take year-end balances)
            # instead of the old bug of treating the Jan–Mar quarter as the year.
            native = _annualize_native_quarterly(native)
            native = native.dropna(subset=["report_date", "fiscal_year"])
            native = native[native["ticker"] != ""].copy()
            native = native.sort_values(["ticker", "fiscal_year", "native_availability_date", "report_date"], kind="mergesort")
            native = native.drop_duplicates(["ticker", "fiscal_year"], keep="last")
            native = native.rename(
                columns={
                    c: f"native_{c}"
                    for c in native.columns
                    if c not in {"ticker", "fiscal_year", "report_date", "native_availability_date"}
                }
            )
        else:
            native = pd.DataFrame(columns=["ticker", "fiscal_year", "report_date", "native_availability_date"])

        active_screener = self._load_optional_csv(screener_csv) if screener_csv.exists() else (
            _build_annual(screener_raw_dir) if screener_raw_dir.exists() else pd.DataFrame()
        )
        delisted_screener = self._load_optional_csv(screener_delisted_csv)
        screener = self._merge_active_and_delisted(
            active=active_screener,
            delisted=delisted_screener,
            key_cols=["ticker", "fiscal_year"],
            sort_cols=["ticker", "fiscal_year"],
            active_label="active_screener",
            delisted_label="delisted_screener",
        )
        if not screener.empty:
            screener = screener.copy()
            screener["ticker"] = screener.get("ticker", "").map(_normalize_ticker)
            screener["fiscal_year"] = _numeric(screener.get("fiscal_year")).astype("Int64")
            screener["screener_availability_date"] = _as_dates(
                screener.get("availability_date"),
            ).dt.normalize()
            screener["screener_report_date"] = _as_dates(screener.get("report_date")).dt.normalize()
            missing_report = screener["screener_report_date"].isna()
            fallback_report = pd.to_datetime(screener["fiscal_year"].astype(str) + "-03-31", errors="coerce")
            screener.loc[missing_report, "screener_report_date"] = fallback_report.loc[missing_report]
            screener = screener[(screener["ticker"] != "") & screener["fiscal_year"].notna()].copy()
            screener = screener.drop(columns=["availability_date", "report_date"], errors="ignore")
            screener = screener.rename(
                columns={
                    c: f"screener_{c}"
                    for c in screener.columns
                    if c not in {"ticker", "fiscal_year", "screener_availability_date", "screener_report_date"}
                }
            )
        else:
            screener = pd.DataFrame(columns=["ticker", "fiscal_year", "screener_availability_date", "screener_report_date"])

        merged = native.merge(screener, on=["ticker", "fiscal_year"], how="outer")
        merged["fiscal_year"] = _numeric(merged.get("fiscal_year")).astype("Int64")
        merged["report_date"] = _coalesce(
            merged,
            "report_date",
            "screener_report_date",
            default=pd.to_datetime(merged["fiscal_year"].astype(str) + "-12-31", errors="coerce"),
        )
        merged["report_date"] = _as_dates(merged["report_date"]).dt.normalize()
        merged["availability_date"] = _coalesce(
            merged,
            "native_availability_date",
            "screener_availability_date",
            default=pd.to_datetime(merged["report_date"], errors="coerce") + pd.Timedelta(days=60),
        )
        merged["availability_date"] = _as_dates(merged["availability_date"]).dt.normalize()
        merged["is_delisted"] = _coalesce(merged, "screener_is_delisted", default=False).fillna(False).astype(bool)
        merged["record_origin"] = _coalesce(merged, "screener_record_origin", default="native").fillna("native").astype(str)

        standard_map = {
            "revenue": ["native_revenue", "screener_revenue", "screener_sales"],
            "gross_profit": ["native_gross_profit"],
            "ebitda": ["native_ebitda"],
            "operating_income": ["native_operating_income", "screener_operating_profit"],
            "net_income": ["native_net_income", "screener_net_profit"],
            "operating_cash_flow": ["native_operating_cash_flow", "screener_cash_from_operating_activity"],
            "free_cash_flow": ["native_free_cash_flow"],
            "total_assets": ["native_total_assets", "screener_total_assets"],
            "equity": ["native_equity"],
            "total_debt": ["native_total_debt", "screener_borrowings", "screener_borrowing"],
            "interest_expense": ["native_interest_expense", "screener_interest"],
            "depreciation": ["native_depreciation", "screener_depreciation"],
            "working_capital": ["native_working_capital"],
            "roce_pct": ["screener_roce_pct"],
            "roe_pct": ["screener_roe_pct"],
            "opm_pct": ["screener_opm_pct"],
            "tax_pct": ["screener_tax_pct"],
        }
        for out_col, candidates in standard_map.items():
            merged[out_col] = _coalesce(merged, *candidates)

        native_cols = [c for c in merged.columns if c.startswith("native_")]
        screener_cols = [c for c in merged.columns if c.startswith("screener_")]
        merged["native_non_null_fields"] = merged[native_cols].notna().sum(axis=1) if native_cols else 0
        merged["screener_non_null_fields"] = merged[screener_cols].notna().sum(axis=1) if screener_cols else 0
        merged["source_count"] = (
            (merged["native_non_null_fields"] > 0).astype(int)
            + (merged["screener_non_null_fields"] > 0).astype(int)
        )
        merged["source_labels"] = np.where(
            (merged["native_non_null_fields"] > 0) & (merged["screener_non_null_fields"] > 0),
            "native+screener",
            np.where(merged["native_non_null_fields"] > 0, "native", "screener"),
        )

        core = [
            "ticker",
            "fiscal_year",
            "report_date",
            "availability_date",
            "revenue",
            "gross_profit",
            "ebitda",
            "operating_income",
            "net_income",
            "operating_cash_flow",
            "free_cash_flow",
            "total_assets",
            "equity",
            "total_debt",
            "interest_expense",
            "depreciation",
            "working_capital",
            "roce_pct",
            "roe_pct",
            "opm_pct",
            "tax_pct",
            "native_non_null_fields",
            "screener_non_null_fields",
            "source_count",
            "source_labels",
            "is_delisted",
            "record_origin",
        ]
        extras = sorted(c for c in merged.columns if c not in core)
        out = merged[core + extras].sort_values(["ticker", "fiscal_year"], kind="mergesort").reset_index(drop=True)
        self._write_bundle("fundamentals_annual", out, "fundamentals/fundamentals_annual_panel")
        return out

    def build_fundamentals_quarterly(self) -> pd.DataFrame:
        screener_csv = REPO_ROOT / "data/processed/screener_fundamentals_quarterly.csv"
        screener_delisted_csv = REPO_ROOT / "data/processed/screener_delisted/screener_fundamentals_quarterly.csv"
        screener_raw_dir = REPO_ROOT / "data/raw/vendors/screener/financials"
        self._record_source("fundamentals_quarterly_screener", screener_csv if screener_csv.exists() else None)
        self._record_source(
            "fundamentals_quarterly_screener_delisted",
            screener_delisted_csv if screener_delisted_csv.exists() else None,
        )
        active_df = self._load_optional_csv(screener_csv) if screener_csv.exists() else (
            _build_quarterly(screener_raw_dir) if screener_raw_dir.exists() else pd.DataFrame()
        )
        delisted_df = self._load_optional_csv(screener_delisted_csv)
        df = self._merge_active_and_delisted(
            active=active_df,
            delisted=delisted_df,
            key_cols=["ticker", "quarter"],
            sort_cols=["ticker", "quarter"],
            active_label="active_screener",
            delisted_label="delisted_screener",
        )

        # Hybrid source: screener is the historical backbone; layer yfinance
        # (data/processed/fundamentals.parquet) on top for recent quarters and
        # its cleaner/richer fields. On any (ticker, quarter) present in both,
        # yfinance wins (see the source-ranked dedup below).
        yfinance_df = _build_quarterly_yfinance()
        self._record_source(
            "fundamentals_quarterly_yfinance",
            _YFINANCE_QUARTERLY_PATH if not yfinance_df.empty else None,
        )
        if not yfinance_df.empty:
            if df.empty:
                df = yfinance_df
            else:
                if "record_origin" not in df.columns:
                    df = df.copy()
                    df["record_origin"] = "active_screener"
                df = pd.concat([df, yfinance_df], ignore_index=True, sort=False)

        if df.empty:
            out = pd.DataFrame(columns=["ticker", "quarter", "quarter_end", "availability_date"])
            self._write_bundle("fundamentals_quarterly", out, "fundamentals/fundamentals_quarterly_panel")
            return out

        work = df.copy()
        work["ticker"] = work.get("ticker", "").map(_normalize_ticker)
        work["quarter"] = work.get("quarter", "").map(_clean_text)
        work["quarter_end"] = work["quarter"].map(_parse_quarter_end)
        work["availability_date"] = _as_dates(work.get("availability_date")).dt.normalize()
        for col in work.columns:
            if col not in {"ticker", "quarter", "quarter_end", "availability_date", "record_origin", "is_delisted"}:
                work[col] = _numeric(work[col])

        work["revenue"] = _coalesce(work, "revenue", "sales")
        work["net_income"] = _coalesce(work, "net_profit")
        work["operating_income"] = _coalesce(work, "operating_profit")
        work["eps"] = _coalesce(work, "eps_in_rs")
        work["is_delisted"] = _coalesce(work, "is_delisted", default=False).fillna(False).astype(bool)
        work["record_origin"] = _coalesce(work, "record_origin", default="active_screener").fillna("active_screener").astype(str)
        work = work[(work["ticker"] != "") & work["quarter_end"].notna()].copy()
        # Field-level source coalescing for overlapping (ticker, quarter_end):
        # yfinance (2) > delisted screener (1) > active screener (0). We sort by
        # this rank ascending and take groupby.last() per column, which skips
        # NaN -- so each field takes the highest-priority source that actually
        # has a value. This is deliberately NOT a row-level replacement:
        # yfinance's EPS is derivable only ~36% of the time, so wholesale row
        # replacement would wipe screener's EPS on most overlapping quarters
        # and corrupt eps_sue_decay. Coalescing keeps screener's value wherever
        # yfinance is null.
        _src_rank = {"yfinance": 2, "delisted_screener": 1, "active_screener": 0}
        work["_src_rank"] = work["record_origin"].map(_src_rank).fillna(0).astype(int)
        work = work.sort_values(["ticker", "quarter_end", "_src_rank"], kind="mergesort")
        _agg_cols = [c for c in work.columns if c not in {"ticker", "quarter_end", "_src_rank"}]
        work = work.groupby(["ticker", "quarter_end"], as_index=False, sort=False)[_agg_cols].last()
        self._write_bundle("fundamentals_quarterly", work.reset_index(drop=True), "fundamentals/fundamentals_quarterly_panel")
        return work

    def build_shareholding(self) -> pd.DataFrame:
        share_csv = REPO_ROOT / "data/processed/screener_shareholding.csv"
        share_delisted_csv = REPO_ROOT / "data/processed/screener_delisted/screener_shareholding.csv"
        share_raw_dir = REPO_ROOT / "data/raw/vendors/screener/shareholding"
        self._record_source("shareholding_screener", share_csv if share_csv.exists() else None)
        self._record_source("shareholding_screener_delisted", share_delisted_csv if share_delisted_csv.exists() else None)
        active_df = self._load_optional_csv(share_csv) if share_csv.exists() else (
            _build_shareholding(share_raw_dir) if share_raw_dir.exists() else pd.DataFrame()
        )
        delisted_df = self._load_optional_csv(share_delisted_csv)
        df = self._merge_active_and_delisted(
            active=active_df,
            delisted=delisted_df,
            key_cols=["ticker", "quarter"],
            sort_cols=["ticker", "quarter"],
            active_label="active_screener",
            delisted_label="delisted_screener",
        )

        if df.empty:
            out = pd.DataFrame(columns=["ticker", "quarter", "quarter_end", "availability_date"])
            self._write_bundle("shareholding_quarterly", out, "fundamentals/shareholding_quarterly")
            return out

        work = df.copy()
        work["ticker"] = work.get("ticker", "").map(_normalize_ticker)
        work["quarter"] = work.get("quarter", "").map(_clean_text)
        work["quarter_end"] = work["quarter"].map(_parse_quarter_end)
        work["availability_date"] = _as_dates(work.get("availability_date")).dt.normalize()
        for col in ["promoter_pct", "fii_pct", "dii_pct", "public_pct", "govt_pct", "n_shareholders"]:
            work[col] = _numeric(work.get(col))
        work["is_delisted"] = _coalesce(work, "is_delisted", default=False).fillna(False).astype(bool)
        work["record_origin"] = _coalesce(work, "record_origin", default="active_screener").fillna("active_screener").astype(str)
        work["institutional_pct"] = work[["fii_pct", "dii_pct"]].sum(axis=1, min_count=1)
        work["free_float_pct"] = 100.0 - _numeric(work.get("promoter_pct"))
        work = work[(work["ticker"] != "") & work["quarter_end"].notna()].copy()
        work = work.sort_values(["ticker", "quarter_end"], kind="mergesort")
        work["promoter_pct_change_1q"] = work.groupby("ticker", sort=False)["promoter_pct"].diff()
        work["fii_pct_change_1q"] = work.groupby("ticker", sort=False)["fii_pct"].diff()
        work["dii_pct_change_1q"] = work.groupby("ticker", sort=False)["dii_pct"].diff()
        work["public_pct_change_1q"] = work.groupby("ticker", sort=False)["public_pct"].diff()
        work = work.drop_duplicates(["ticker", "quarter_end"], keep="last")
        self._write_bundle("shareholding_quarterly", work.reset_index(drop=True), "fundamentals/shareholding_quarterly")
        return work

    def build_company_news(self) -> pd.DataFrame:
        primary_path = REPO_ROOT / "data/processed/news/news_dataset.parquet"
        legacy_path = REPO_ROOT / "data/processed/news/legacy_news_clean.parquet"
        self._record_source("company_news_primary", primary_path if primary_path.exists() else None)
        self._record_source("company_news_legacy", legacy_path if legacy_path.exists() else None)

        frames: list[pd.DataFrame] = []
        if primary_path.exists():
            df = pd.read_parquet(primary_path)
            work = pd.DataFrame(
                {
                    "date": _as_dates(df.get("date")).dt.normalize(),
                    "ticker": df.get("ticker", "").map(_normalize_ticker),
                    "company": df.get("company", "").map(_clean_text),
                    "headline": df.get("headline", "").map(_clean_text),
                    "summary": df.get("summary", "").map(_clean_text),
                    "url": df.get("url", "").map(_clean_text),
                    "source": df.get("source", "").map(_clean_text),
                    "source_type": df.get("source_type", "").map(_clean_text),
                    "keywords": df.get("keywords", "").astype(str) if "keywords" in df.columns else "",
                    "sentiment_score": _numeric(df.get("sentiment")),
                    "sentiment_conviction": _numeric(df.get("sentiment_conviction")),
                    "sentiment_label": df.get("sentiment_label", "").map(_clean_text),
                    "dataset_source": "news_dataset",
                }
            )
            frames.append(work)
        if legacy_path.exists():
            df = pd.read_parquet(legacy_path)
            work = pd.DataFrame(
                {
                    "date": _as_dates(df.get("date")).dt.normalize(),
                    "ticker": df.get("ticker", "").map(_normalize_ticker),
                    "company": df.get("company", "").map(_clean_text),
                    "headline": df.get("headline", "").map(_clean_text),
                    "summary": df.get("summary", "").map(_clean_text),
                    "url": df.get("url", "").map(_clean_text),
                    "source": df.get("source", "").map(_clean_text),
                    "source_type": df.get("source_type", "").map(_clean_text),
                    "keywords": "",
                    "sentiment_score": np.nan,
                    "sentiment_conviction": np.nan,
                    "sentiment_label": "",
                    "dataset_source": "legacy_news_clean",
                }
            )
            frames.append(work)

        if not frames:
            out = pd.DataFrame(columns=["date", "availability_date", "ticker", "headline"])
            self._write_parquet("company_news_history", out, "news/company_news_history.parquet")
            return out

        out = pd.concat(frames, ignore_index=True)
        out["availability_date"] = _next_business_day(out["date"])
        out = out[(out["ticker"] != "") & out["date"].notna()].copy()
        out = out[out["headline"].astype(str).str.len() > 0].copy()
        out = out.sort_values(["ticker", "date", "headline"], kind="mergesort")
        out = out.drop_duplicates(["date", "ticker", "headline", "url"], keep="last")
        order = [
            "date",
            "availability_date",
            "ticker",
            "company",
            "headline",
            "summary",
            "url",
            "source",
            "source_type",
            "keywords",
            "sentiment_score",
            "sentiment_conviction",
            "sentiment_label",
            "dataset_source",
        ]
        out = out[order].reset_index(drop=True)
        self._write_parquet("company_news_history", out, "news/company_news_history.parquet")
        return out

    def build_market_news(self) -> pd.DataFrame:
        path = REPO_ROOT / "data/processed/news/unified_indian_news_dataset_final.parquet"
        self._record_source("market_news", path if path.exists() else None)
        if not path.exists():
            out = pd.DataFrame(columns=["date", "availability_date", "headline"])
            self._write_parquet("market_news_history", out, "news/market_news_history.parquet", entity_col=None)
            return out

        df = pd.read_parquet(path)
        date_col = _first_existing(df, ["published_date", "date"])
        work = pd.DataFrame(
            {
                "date": _as_dates(df.get(date_col) if date_col else pd.Series(dtype="object")).dt.normalize(),
                "headline": _coalesce(df, "title", "summary", default="").map(_clean_text),
                "content": df.get("content", "").map(_clean_text),
                "summary": df.get("summary", "").map(_clean_text),
                "url": df.get("url", "").map(_clean_text),
                "source": df.get("source", "").map(_clean_text),
                "category": df.get("category", "").map(_clean_text),
                "sentiment_label": df.get("sentiment", "").map(_clean_text),
                "author": df.get("author", "").map(_clean_text),
                "keywords": df.get("keywords", "").astype(str) if "keywords" in df.columns else "",
                "content_hash": df.get("content_hash", "").astype(str) if "content_hash" in df.columns else "",
                "dataset_source": "unified_indian_news_dataset_final",
            }
        )
        max_valid = pd.Timestamp.utcnow().tz_localize(None).normalize() + pd.Timedelta(days=7)
        work = work[work["date"].notna()].copy()
        work = work[work["date"] <= max_valid].copy()
        work["availability_date"] = _next_business_day(work["date"])
        work = work[work["headline"].astype(str).str.len() > 0].copy()
        work = work.sort_values(["date", "headline"], kind="mergesort").drop_duplicates(["date", "headline", "url"], keep="last")
        order = [
            "date",
            "availability_date",
            "headline",
            "summary",
            "content",
            "url",
            "source",
            "category",
            "sentiment_label",
            "author",
            "keywords",
            "content_hash",
            "dataset_source",
        ]
        out = work[order].reset_index(drop=True)
        self._write_parquet("market_news_history", out, "news/market_news_history.parquet", entity_col=None)
        return out

    def build_sentiment(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        company_path = REPO_ROOT / "data/processed/sentiment/ticker_sentiment_daily.parquet"
        market_path = REPO_ROOT / "data/processed/sentiment/market_sentiment_daily.parquet"
        impacts_path = REPO_ROOT / "data/sentiment/v3/event_company_impact.parquet"
        self._record_source("company_sentiment", company_path if company_path.exists() else None)
        self._record_source("market_sentiment", market_path if market_path.exists() else None)
        self._record_source("event_company_impacts", impacts_path if impacts_path.exists() else None)

        company = pd.read_parquet(company_path) if company_path.exists() else pd.DataFrame()
        if not company.empty:
            company = company.copy()
            company["ticker"] = company.get("ticker", "").map(_normalize_ticker)
            company["date"] = _as_dates(company.get("date")).dt.normalize()
            company["availability_date"] = _as_dates(company.get("availability_date")).dt.normalize()
            company = company[(company["ticker"] != "") & company["date"].notna()].copy()
            company = company.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates(["ticker", "date"], keep="last")
        self._write_parquet("company_sentiment_daily", company, "sentiment/company_sentiment_daily.parquet")

        market = pd.read_parquet(market_path) if market_path.exists() else pd.DataFrame()
        if not market.empty:
            market = market.copy()
            market["date"] = _as_dates(market.get("date")).dt.normalize()
            market["availability_date"] = _as_dates(market.get("availability_date")).dt.normalize()
            market = market[market["date"].notna()].copy()
            market = market.sort_values("date", kind="mergesort").drop_duplicates(["date"], keep="last")
        self._write_parquet("market_sentiment_daily", market, "sentiment/market_sentiment_daily.parquet", entity_col=None)

        impacts = pd.read_parquet(impacts_path) if impacts_path.exists() else pd.DataFrame()
        if not impacts.empty:
            impacts = impacts.copy()
            impacts["timestamp"] = _as_dates(impacts.get("timestamp"))
            impacts["date"] = impacts["timestamp"].dt.normalize()
            impacts["availability_date"] = _next_business_day(impacts["date"])
            impacts["ticker"] = impacts.get("ticker", "").map(_normalize_ticker)
            impacts = impacts.sort_values(["date", "ticker"], kind="mergesort").drop_duplicates(["timestamp", "ticker", "event_type"], keep="last")
        self._write_parquet("event_company_impacts", impacts, "sentiment/event_company_impacts.parquet")
        return company, market, impacts

    def _parse_macro_workbook(self, path: Path, workbook_group: str) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        rows: list[dict[str, Any]] = []
        xl = pd.ExcelFile(path, engine="openpyxl")
        version = _extract_timestamp_from_name(path)
        for sheet in xl.sheet_names:
            raw = xl.parse(sheet, header=None)
            raw = raw.dropna(axis=1, how="all")
            if raw.empty:
                continue
            header_idx = None
            for idx in range(min(len(raw), 10)):
                labels = [str(v).strip().lower() for v in raw.iloc[idx].tolist()]
                if any(lbl in {"period", "reporting date"} for lbl in labels):
                    header_idx = idx
                    break
            if header_idx is None:
                continue
            header = [_clean_text(v) for v in raw.iloc[header_idx].tolist()]
            header = [h if h else f"col_{i}" for i, h in enumerate(header)]
            data_start = None
            for idx in range(header_idx + 1, min(len(raw), header_idx + 8)):
                candidate = pd.to_datetime(raw.iloc[idx, 0], errors="coerce")
                if pd.notna(candidate):
                    data_start = idx
                    break
            if data_start is None:
                continue
            unit_row_idx = data_start - 1 if data_start - 1 > header_idx else None
            units = [_clean_text(v) for v in raw.iloc[unit_row_idx].tolist()] if unit_row_idx is not None else [""] * len(header)
            data = raw.iloc[data_start:].copy()
            data.columns = header
            date_col = header[0]
            data[date_col] = pd.to_datetime(data[date_col], errors="coerce", dayfirst=True)
            data = data[data[date_col].notna()].copy()
            for _, row in data.iterrows():
                period_date = pd.to_datetime(row.get(date_col), errors="coerce")
                if pd.isna(period_date):
                    continue
                for idx, indicator in enumerate(header[1:], start=1):
                    if not indicator or indicator.startswith("col_"):
                        continue
                    raw_value = row.iloc[idx] if idx < len(row) else None
                    value = _numeric(pd.Series([raw_value])).iloc[0]
                    if pd.isna(value):
                        continue
                    rows.append(
                        {
                            "date": period_date.normalize(),
                            "frequency": str(sheet).strip().lower(),
                            "indicator": _strip_unit(indicator),
                            "indicator_slug": _slug(indicator),
                            "unit": units[idx] if idx < len(units) else "",
                            "value": float(value),
                            "workbook_group": workbook_group,
                            "workbook_file": path.name,
                            "workbook_version": version,
                        }
                    )
        out = pd.DataFrame(rows)
        if out.empty:
            return out
        out = out.sort_values(["workbook_group", "frequency", "indicator_slug", "date", "workbook_version"], kind="mergesort")
        out = out.drop_duplicates(["workbook_group", "frequency", "indicator_slug", "date"], keep="last")
        return out.reset_index(drop=True)

    def build_rbi_macro(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        fifty_path = _latest_path("macro/archive/50 Macroeconomic Indicators*.xlsx*")
        other_path = _latest_path("macro/archive/Other Macroeconomic Indicators*.xlsx*")
        self._record_source("rbi_macro_50", fifty_path)
        self._record_source("rbi_macro_other", other_path)

        frames = []
        if fifty_path:
            frames.append(self._parse_macro_workbook(fifty_path, "rbi_50_macro_indicators"))
        if other_path:
            frames.append(self._parse_macro_workbook(other_path, "rbi_other_macro_indicators"))
        long_df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
        if long_df.empty:
            wide_df = pd.DataFrame()
        else:
            wide_df = (
                long_df.pivot_table(
                    index=["date", "frequency"],
                    columns=["workbook_group", "indicator_slug"],
                    values="value",
                    aggfunc="last",
                )
                .reset_index()
                .sort_values(["date", "frequency"], kind="mergesort")
            )
            wide_df.columns = [
                "__".join([str(x) for x in col if str(x) != ""]).strip("_")
                if isinstance(col, tuple)
                else str(col)
                for col in wide_df.columns
            ]
        self._write_parquet("rbi_macro_long", long_df, "macro/rbi_macro_long.parquet", entity_col=None)
        self._write_parquet("rbi_macro_wide", wide_df, "macro/rbi_macro_wide.parquet", entity_col=None)
        return long_df, wide_df

    def build_macro_regime_features(self) -> pd.DataFrame:
        path = REPO_ROOT / "data/processed/macro/macro_regime_features.parquet"
        self._record_source("macro_regime_features", path if path.exists() else None)
        df = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        if not df.empty:
            df = df.copy()
            df["date"] = _as_dates(df.get("date")).dt.normalize()
            df["availability_date"] = _as_dates(df.get("availability_date")).dt.normalize()
            if "ticker" in df.columns:
                df["ticker"] = df["ticker"].astype(str)
            df = self._merge_gst_growth(df)
            df = self._weekly_macro_regime(df)
        self._write_parquet("macro_regime_features", df, "macro/macro_regime_features.parquet")
        return df

    @staticmethod
    def _merge_gst_growth(df: pd.DataFrame) -> pd.DataFrame:
        """Backfill the gst_* columns from the real monthly GST series.

        `build_regime_labels.py` populated macro_regime_features' gst_* columns
        from the wrong file (`gst_ewaybill_monthly.parquet` — 6 rows, 2026-only,
        no growth columns), so those columns came out ~0% populated even though
        the true series (`data/processed/gst_monthly.parquet`, 165 months back to
        2012) was sitting right there with yoy growth at 93%. Rather than re-run
        the whole regime pipeline, we merge the good series here, PIT-safely:
        each macro row takes the latest GST reading already *published*
        (availability_date = collection month-end + ~1 month) as of that date."""
        gst_path = REPO_ROOT / "data/processed/gst_monthly.parquet"
        if not gst_path.exists():
            return df
        g = pd.read_parquet(gst_path)
        if g.empty or "gst_yoy_growth" not in g.columns:
            return df
        g = g.copy()
        avail = _as_dates(g.get("availability_date"))
        gdate = _as_dates(g.get("date"))
        avail = avail.fillna(gdate + pd.offsets.MonthEnd(1)).dt.normalize()
        yoy = pd.to_numeric(g.get("gst_yoy_growth"), errors="coerce")
        src = pd.DataFrame({
            "availability_date": avail,
            # gst_yoy_growth is the clean same-month YoY %; the raw collection
            # level alternates (quarterly cumulation artifact) so value-growth is
            # mapped to the same clean YoY rather than recomputed from the level.
            "gst_yoy_growth": yoy,
            "gst_value_growth": yoy,
            "gst_mom_growth": pd.to_numeric(g.get("mom_growth"), errors="coerce"),
            "gst_3m_trend": pd.to_numeric(g.get("gst_3m_trend"), errors="coerce"),
        }).dropna(subset=["availability_date"]).sort_values("availability_date")
        gst_cols = ["gst_yoy_growth", "gst_value_growth", "gst_mom_growth", "gst_3m_trend"]
        df = df.drop(columns=[c for c in gst_cols if c in df.columns]).sort_values("date")
        merged = pd.merge_asof(
            df, src, left_on="date", right_on="availability_date",
            direction="backward", suffixes=("", "_gst"))
        if "availability_date_gst" in merged.columns:
            merged = merged.drop(columns=["availability_date_gst"])
        return merged.reset_index(drop=True)

    @staticmethod
    def _weekly_macro_regime(df: pd.DataFrame) -> pd.DataFrame:
        """Resample the MARKET macro-regime features from month-end to the weekly
        Friday grid the equity panel uses. The source is monthly (~87 rows), but
        the research panel is weekly and load_macro requires a non-trivial
        artifact; a monthly series as-of joined to weekly forward-fills each
        reading until the next month is *released*. Alignment is on
        availability_date (month-end + publication lag), so no look-ahead: a
        Friday only sees a macro reading already published by then. Idempotent —
        if the input is already ~weekly it is returned unchanged."""
        gaps = df.sort_values("date")["date"].diff().dt.days.dropna()
        if gaps.empty or gaps.median() <= 10:
            return df  # already weekly/denser
        feat_cols = [c for c in df.columns
                     if c not in ("date", "availability_date", "ticker")]
        src = df.sort_values("availability_date")
        grid = pd.date_range(df["date"].min(), df["date"].max(), freq="W-FRI")
        base = pd.DataFrame({"date": grid})
        merged = pd.merge_asof(base, src.rename(columns={"date": "source_date"}),
                               left_on="date", right_on="availability_date",
                               direction="backward")
        merged = merged.dropna(subset=["source_date"]).copy()
        merged["ticker"] = "MARKET"
        # availability_date on the weekly grid is the grid Friday itself (the data
        # was already released as of source availability_date <= this Friday).
        merged["availability_date"] = merged["date"]
        return merged[["date", "availability_date", "ticker"] + feat_cols].reset_index(drop=True)

    def build_cea_power_daily(self) -> pd.DataFrame:
        processed_path = REPO_ROOT / "data/processed/macro/cea_power_daily.parquet"
        raw_dir = REPO_ROOT / "data/raw/macro/cea_power"
        self._record_source("cea_power_daily_processed", processed_path if processed_path.exists() else None)
        if processed_path.exists():
            df = pd.read_parquet(processed_path)
        else:
            frames = []
            for path in sorted(raw_dir.glob("power_*.csv")):
                try:
                    frame = pd.read_csv(path, low_memory=False)
                except Exception:
                    continue
                if not frame.empty:
                    frames.append(frame)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not df.empty:
            df = df.copy()
            df["date"] = _as_dates(df.get("date")).dt.normalize()
            df["availability_date"] = _as_dates(df.get("availability_date")).dt.normalize()
            df["region"] = df.get("region", "").map(_clean_text)
            for col in ["energy_met_mu", "peak_met_gw", "energy_requirement_mu", "deficit_pct"]:
                df[col] = _numeric(df.get(col))
            df = df.sort_values(["region", "date"], kind="mergesort").drop_duplicates(["region", "date"], keep="last")
        self._write_parquet("cea_power_daily", df, "macro/cea_power_daily.parquet", entity_col="region")
        return df

    def build_cea_power_state_yearly(self) -> pd.DataFrame:
        power_dir = REPO_ROOT / "data/raw/shared/alternative/power_yearly"
        files = sorted(power_dir.glob("State Wise Deep Dive *.xlsx"))
        self._record_source("cea_power_state_yearly_dir", power_dir if power_dir.exists() else None)
        rows: list[dict[str, Any]] = []
        for path in files:
            m = re.search(r"State Wise Deep Dive (\d{4})-(\d{2})", path.name)
            if not m:
                continue
            fy_start = int(m.group(1))
            fy_end = 2000 + int(m.group(2))
            xl = pd.ExcelFile(path, engine="openpyxl")
            for sheet in xl.sheet_names:
                try:
                    df = xl.parse(sheet)
                except Exception:
                    continue
                if df.empty:
                    continue
                first_col = df.columns[0]
                renamed = df.rename(columns={first_col: "metric_raw"}).copy()
                renamed["metric_raw"] = renamed["metric_raw"].map(_clean_text)
                renamed = renamed[renamed["metric_raw"] != ""].copy()
                for col in renamed.columns:
                    if col == "metric_raw":
                        continue
                    state = _clean_text(col)
                    if not state:
                        continue
                    series = renamed[["metric_raw", col]].copy()
                    for _, row in series.iterrows():
                        metric_raw = row.get("metric_raw")
                        value = _numeric(pd.Series([row.get(col)])).iloc[0]
                        rows.append(
                            {
                                "fiscal_year_label": f"{fy_start}-{str(fy_end)[-2:]}",
                                "fiscal_year_start": fy_start,
                                "fiscal_year_end": fy_end,
                                "sheet": _clean_text(sheet),
                                "state": state,
                                "metric": _strip_unit(metric_raw),
                                "metric_slug": _slug(metric_raw),
                                "unit": _extract_unit(metric_raw),
                                "value": value,
                                "source_file": path.name,
                            }
                        )
        out = pd.DataFrame(rows)
        if not out.empty:
            out = out.dropna(subset=["value"]).sort_values(
                ["fiscal_year_start", "sheet", "metric_slug", "state"], kind="mergesort"
            )
        self._write_parquet("cea_power_state_yearly", out, "macro/cea_power_state_yearly.parquet", entity_col="state", date_cols=())
        return out

    def build_gst_panels(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        raw_dir = REPO_ROOT / "data/raw/macro/gst_ewaybill"
        processed_path = REPO_ROOT / "data/processed/macro/gst_ewaybill_monthly.parquet"
        self._record_source("gst_ewaybill_raw_dir", raw_dir if raw_dir.exists() else None)
        self._record_source("gst_ewaybill_processed", processed_path if processed_path.exists() else None)

        frames = []
        for path in sorted(raw_dir.glob("ewaybill_*.csv")):
            try:
                frame = pd.read_csv(path, low_memory=False)
            except Exception:
                continue
            if frame.empty:
                continue
            frame["source_file"] = path.name
            frames.append(frame)
        if frames:
            state_df = pd.concat(frames, ignore_index=True)
        elif processed_path.exists():
            state_df = pd.read_parquet(processed_path)
        else:
            state_df = pd.DataFrame()

        if not state_df.empty:
            state_df = state_df.copy()
            state_df["year_month"] = state_df.get("year_month", "").astype(str)
            state_df["state"] = state_df.get("state", "").map(_clean_text)
            state_df["category"] = state_df.get("category", "").map(_clean_text)
            state_df["date"] = _as_dates(state_df.get("date")).dt.normalize()
            state_df["availability_date"] = _as_dates(state_df.get("availability_date")).dt.normalize()
            state_df["eway_bills_generated"] = _numeric(state_df.get("eway_bills_generated"))
            state_df["eway_bill_value_crore"] = _numeric(state_df.get("eway_bill_value_crore"))
            state_df = state_df.drop_duplicates(["year_month", "state", "category"], keep="last")
            state_df = state_df.sort_values(["year_month", "state", "category"], kind="mergesort")

        market_df = pd.DataFrame()
        if not state_df.empty:
            piv = (
                state_df.pivot_table(
                    index=["year_month", "state", "date", "availability_date"],
                    columns="category",
                    values="eway_bills_generated",
                    aggfunc="sum",
                )
                .reset_index()
            )
            piv.columns = [
                _slug(col) if not isinstance(col, tuple) else "_".join(_slug(x) for x in col if str(x))
                for col in piv.columns
            ]
            for col in piv.columns:
                if col in {"inter_state", "intra_state"}:
                    piv[f"{col}_bills"] = _numeric(piv[col])
            cat_cols = [c for c in piv.columns if c.endswith("_bills")]
            piv["total_eway_bills"] = piv[cat_cols].sum(axis=1, min_count=1) if cat_cols else np.nan
            market_df = piv.sort_values(["year_month", "state"], kind="mergesort").reset_index(drop=True)

        self._write_parquet("gst_ewaybill_state_monthly", state_df, "macro/gst_ewaybill_state_monthly.parquet", entity_col="state", date_cols=("date", "availability_date"))
        self._write_parquet("gst_ewaybill_market_monthly", market_df, "macro/gst_ewaybill_market_monthly.parquet", entity_col="state", date_cols=("date", "availability_date"))
        return state_df, market_df

    def build_alternative(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        alt_dir = REPO_ROOT / "data/processed/alternative"
        files = {
            "bulk": alt_dir / "bulk_deals_nse_all.parquet",
            "ratings": alt_dir / "credit_ratings_nse_all.parquet",
            "pledge": alt_dir / "promoter_pledge_all.parquet",
            "announcements": alt_dir / "announcements_all.parquet",
            "earnings_dates": alt_dir / "earnings_dates_all.csv",
        }
        for key, path in files.items():
            self._record_source(f"alternative_{key}", path if path.exists() else None)

        bulk = pd.read_parquet(files["bulk"]) if files["bulk"].exists() else pd.DataFrame()
        if not bulk.empty:
            bulk = bulk.copy()
            bulk["date"] = _as_dates(bulk.get("date")).dt.normalize()
            bulk["availability_date"] = _next_business_day(bulk["date"])
            bulk["nse_ticker"] = _coalesce(bulk, "nse_ticker", default=bulk.get("symbol", "")).map(_normalize_ticker)
            bulk["quantity"] = _numeric(bulk.get("quantity"))
            bulk["price"] = _numeric(bulk.get("price"))
            bulk["notional"] = bulk["quantity"] * bulk["price"]
            bulk["signed_notional"] = np.where(
                bulk.get("deal_type", "").astype(str).str.upper().eq("BUY"),
                1.0,
                -1.0,
            ) * bulk["notional"]
            bulk = bulk.sort_values(["date", "nse_ticker"], kind="mergesort").drop_duplicates(
                ["date", "nse_ticker", "client_name", "deal_type", "quantity", "price"],
                keep="last",
            )
        self._write_bundle("alternative_bulk_deals", bulk, "alternative/bulk_deals_nse_all")

        ratings = pd.read_parquet(files["ratings"]) if files["ratings"].exists() else pd.DataFrame()
        if not ratings.empty:
            ratings = ratings.copy()
            ratings["date"] = _as_dates(ratings.get("date"), dayfirst=True).dt.normalize()
            ratings["availability_date"] = _next_business_day(ratings["date"])
            ratings["nse_ticker"] = ratings.get("nse_ticker", "").map(_normalize_ticker)
            ratings["rating_numeric"] = ratings.get("new_rating", "").map(rating_to_numeric)
            ratings["outlook"] = ratings.get("outlook", "").map(_clean_text)
            ratings["action_type"] = ratings.get("action_type", "").map(_clean_text)
            ratings = ratings[(ratings["nse_ticker"] != "") & ratings["date"].notna()].copy()
            ratings = ratings.sort_values(["date", "nse_ticker"], kind="mergesort").drop_duplicates(
                ["date", "nse_ticker", "new_rating", "action_type", "agency"],
                keep="last",
            )
        self._write_bundle("alternative_credit_ratings", ratings, "alternative/credit_ratings_nse_all")

        pledge = pd.read_parquet(files["pledge"]) if files["pledge"].exists() else pd.DataFrame()
        if not pledge.empty:
            pledge = pledge.copy()
            pledge["date"] = _as_dates(pledge.get("date")).dt.normalize()
            pledge["broadcast_datetime"] = _as_dates(pledge.get("broadcast_datetime"))
            pledge["availability_date"] = np.where(
                pledge["broadcast_datetime"].notna(),
                _next_business_day(pledge["broadcast_datetime"].dt.normalize()),
                pd.to_datetime(pledge["date"], errors="coerce") + pd.Timedelta(days=45),
            )
            pledge["availability_date"] = _as_dates(pledge["availability_date"]).dt.normalize()
            pledge["nse_ticker"] = pledge.get("nse_ticker", "").map(_normalize_ticker)
            pledge["pledge_pct"] = _numeric(pledge.get("pledge_pct"))
            pledge["pledge_value_cr"] = _numeric(pledge.get("pledge_value_cr"))
            pledge = pledge[(pledge["nse_ticker"] != "") & pledge["date"].notna()].copy()
            pledge = pledge.sort_values(["nse_ticker", "date"], kind="mergesort").drop_duplicates(
                ["date", "nse_ticker", "pledge_pct", "shares_pledged"],
                keep="last",
            )
        self._write_bundle("alternative_promoter_pledge", pledge, "alternative/promoter_pledge_all")

        announcements = pd.read_parquet(files["announcements"]) if files["announcements"].exists() else pd.DataFrame()
        if not announcements.empty:
            announcements = announcements.copy()
            announcements["event_timestamp"] = _coalesce(
                announcements,
                "broadcast_datetime",
                "receipt_datetime",
                "dissemination_datetime",
                "date",
            )
            announcements["date"] = _as_dates(announcements["event_timestamp"]).dt.normalize()
            announcements["availability_date"] = _next_business_day(announcements["date"])
            announcements["nse_ticker"] = _coalesce(announcements, "nse_ticker", "symbol").map(_normalize_ticker)
            announcements["category"] = announcements.get("category", "").map(_clean_text)
            announcements["headline"] = announcements.get("headline", "").map(_clean_text)
            announcements = announcements[(announcements["nse_ticker"] != "") & announcements["date"].notna()].copy()
            announcements = announcements.sort_values(["date", "nse_ticker"], kind="mergesort").drop_duplicates(
                ["date", "nse_ticker", "headline"],
                keep="last",
            )
        self._write_bundle("alternative_announcements", announcements, "alternative/announcements_all")

        earnings_out = self.root / "alternative/earnings_dates_all.csv"
        earnings_out.parent.mkdir(parents=True, exist_ok=True)
        if files["earnings_dates"].exists():
            earnings_df = pd.read_csv(files["earnings_dates"], low_memory=False)
            earnings_df.to_csv(earnings_out, index=False)
        else:
            pd.DataFrame().to_csv(earnings_out, index=False)

        event_frames: list[pd.DataFrame] = []
        if not bulk.empty:
            b = bulk.copy()
            b["signal_strength"] = np.tanh(_numeric(b["signed_notional"]).fillna(0.0) / 5.0e8)
            event_frames.append(
                pd.DataFrame(
                    {
                        "event_family": "bulk_deals",
                        "ticker": b["nse_ticker"],
                        "company_name": b.get("company_name", "").map(_clean_text),
                        "event_date": b["date"],
                        "availability_date": b["availability_date"],
                        "signal_direction": np.where(b["signal_strength"] >= 0.0, "bullish", "bearish"),
                        "signal_strength": b["signal_strength"],
                        "headline": ("Bulk deal: " + b.get("company_name", "").astype(str).str.strip()).str.strip(),
                        "category": b.get("deal_type", "").astype(str).str.lower(),
                        "source": b.get("source", "").astype(str),
                    }
                )
            )
        if not ratings.empty:
            r = ratings.copy()
            score = pd.Series(0.0, index=r.index, dtype=float)
            score = score + np.where(r["action_type"].astype(str).str.contains("upgrade|positive", case=False, na=False), 0.75, 0.0)
            score = score - np.where(r["action_type"].astype(str).str.contains("downgrade|watch_negative|suspend", case=False, na=False), 0.85, 0.0)
            score = score + np.where(r["outlook"].astype(str).str.contains("positive", case=False, na=False), 0.15, 0.0)
            score = score - np.where(r["outlook"].astype(str).str.contains("negative", case=False, na=False), 0.20, 0.0)
            event_frames.append(
                pd.DataFrame(
                    {
                        "event_family": "credit_ratings",
                        "ticker": r["nse_ticker"],
                        "company_name": r.get("company_name", "").map(_clean_text),
                        "event_date": r["date"],
                        "availability_date": r["availability_date"],
                        "signal_direction": np.where(score >= 0.0, "bullish", "bearish"),
                        "signal_strength": score.clip(-1.0, 1.0),
                        "headline": ("Credit rating: " + r.get("company_name", "").astype(str).str.strip()).str.strip(),
                        "category": r.get("action_type", "").astype(str).str.lower(),
                        "source": r.get("source", "").astype(str),
                    }
                )
            )
        if not pledge.empty:
            p = pledge.copy()
            score = -np.clip(_numeric(p.get("pledge_pct")).fillna(0.0) / 100.0, 0.0, 1.0)
            event_frames.append(
                pd.DataFrame(
                    {
                        "event_family": "promoter_pledge",
                        "ticker": p["nse_ticker"],
                        "company_name": p.get("company_name", "").map(_clean_text),
                        "event_date": p["date"],
                        "availability_date": p["availability_date"],
                        "signal_direction": "bearish",
                        "signal_strength": score,
                        "headline": ("Promoter pledge: " + p.get("company_name", "").astype(str).str.strip()).str.strip(),
                        "category": "pledge",
                        "source": p.get("source", "").astype(str),
                    }
                )
            )
        if not announcements.empty:
            a = announcements.copy()
            score = pd.Series(0.0, index=a.index, dtype=float)
            cat = a.get("category", "").astype(str)
            headline = a.get("headline", "").astype(str)
            score = score + np.where(cat.str.contains("order win", case=False, na=False), 0.60, 0.0)
            score = score + np.where(cat.str.contains("capacity expansion", case=False, na=False), 0.35, 0.0)
            score = score + np.where(cat.str.contains("acquisition|merger", case=False, na=False), 0.25, 0.0)
            score = score + np.where(cat.str.contains("insider trading", case=False, na=False) & headline.str.contains(r"\bbuy|purchase|acquire\b", case=False, regex=True, na=False), 0.35, 0.0)
            score = score - np.where(cat.str.contains("insider trading", case=False, na=False) & headline.str.contains(r"\bsell|sale|disposed\b", case=False, regex=True, na=False), 0.35, 0.0)
            event_frames.append(
                pd.DataFrame(
                    {
                        "event_family": "announcements",
                        "ticker": a["nse_ticker"],
                        "company_name": a.get("company_name", "").map(_clean_text),
                        "event_date": a["date"],
                        "availability_date": a["availability_date"],
                        "signal_direction": np.where(score >= 0.0, "bullish", "bearish"),
                        "signal_strength": score.clip(-1.0, 1.0),
                        "headline": a.get("headline", "").map(_clean_text),
                        "category": cat.map(_clean_text),
                        "source": a.get("source", "").astype(str),
                    }
                )
            )

        unified = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame(
            columns=["event_family", "ticker", "company_name", "event_date", "availability_date", "signal_direction", "signal_strength", "headline", "category", "source"]
        )
        if not unified.empty:
            unified = unified[(unified["ticker"].astype(str) != "") & unified["event_date"].notna()].copy()
            unified = unified.sort_values(["event_date", "ticker", "event_family"], kind="mergesort").drop_duplicates(
                ["event_family", "ticker", "event_date", "headline"],
                keep="last",
            )
        self._write_parquet("nse_alternative_events", unified.reset_index(drop=True), "alternative/nse_alternative_events.parquet")
        return bulk, ratings, pledge, announcements, unified

    def build_reference_master(self) -> pd.DataFrame:
        prices = self.frames.get("prices_daily", pd.DataFrame())
        annual = self.frames.get("fundamentals_annual", pd.DataFrame())
        quarterly = self.frames.get("fundamentals_quarterly", pd.DataFrame())
        share = self.frames.get("shareholding_quarterly", pd.DataFrame())
        sentiment = self.frames.get("company_sentiment_daily", pd.DataFrame())
        alt = self.frames.get("nse_alternative_events", pd.DataFrame())

        sector_map_path = REPO_ROOT / "data/processed/sector_mapping.csv"
        universe_path = REPO_ROOT / "universe/nifty500.csv"
        screener_meta_path = REPO_ROOT / "data/processed/screener_metadata.csv"
        screener_delisted_meta_path = REPO_ROOT / "data/processed/screener_delisted/screener_metadata.csv"
        delisting_db_path = REPO_ROOT / "data/universe/delisting_database.parquet"
        universe_snapshots_path = REPO_ROOT / "data/universe/universe_snapshots.parquet"
        self._record_source("reference_sector_mapping", sector_map_path if sector_map_path.exists() else None)
        self._record_source("reference_nifty500", universe_path if universe_path.exists() else None)
        self._record_source("reference_screener_metadata", screener_meta_path if screener_meta_path.exists() else None)
        self._record_source(
            "reference_screener_delisted_metadata",
            screener_delisted_meta_path if screener_delisted_meta_path.exists() else None,
        )
        self._record_source("reference_delisting_database", delisting_db_path if delisting_db_path.exists() else None)
        self._record_source("reference_universe_snapshots", universe_snapshots_path if universe_snapshots_path.exists() else None)

        tickers: set[str] = set()
        for frame, col in [
            (prices, "ticker"),
            (annual, "ticker"),
            (quarterly, "ticker"),
            (share, "ticker"),
            (sentiment, "ticker"),
            (alt, "ticker"),
        ]:
            if col in frame.columns:
                tickers.update(str(x) for x in frame[col].dropna().astype(str).tolist() if str(x))

        active_meta = self._load_optional_csv(screener_meta_path)
        delisted_meta = self._load_optional_csv(screener_delisted_meta_path)
        meta = self._merge_active_and_delisted(
            active=active_meta,
            delisted=delisted_meta,
            key_cols=["ticker"],
            sort_cols=["ticker"],
            active_label="active_screener",
            delisted_label="delisted_screener",
        )
        if not meta.empty:
            meta["ticker"] = meta.get("ticker", "").map(_normalize_ticker)
            meta = meta[meta["ticker"] != ""].drop_duplicates(["ticker"], keep="first").copy()
            tickers.update(str(x) for x in meta["ticker"].dropna().astype(str).tolist() if str(x))

        delist_df = pd.DataFrame()
        if delisting_db_path.exists():
            delist_df = pd.read_parquet(delisting_db_path)
            sym_col = "symbol" if "symbol" in delist_df.columns else ("ticker" if "ticker" in delist_df.columns else None)
            if sym_col is not None:
                delist_df = delist_df.copy()
                delist_df["ticker"] = delist_df[sym_col].map(_normalize_ticker)
                delist_df = delist_df[delist_df["ticker"] != ""].copy()
                tickers.update(str(x) for x in delist_df["ticker"].dropna().astype(str).tolist() if str(x))

        ref = pd.DataFrame({"ticker": sorted(tickers)})
        ref["symbol"] = ref["ticker"].str.replace(".NS", "", regex=False)
        for flag_name, frame in [
            ("has_price_history", prices),
            ("has_fundamentals_annual", annual),
            ("has_fundamentals_quarterly", quarterly),
            ("has_shareholding", share),
            ("has_sentiment", sentiment),
            ("has_alternative_events", alt),
        ]:
            values = set(frame["ticker"].dropna().astype(str)) if "ticker" in frame.columns else set()
            ref[flag_name] = ref["ticker"].isin(values)

        if sector_map_path.exists():
            sm = pd.read_csv(sector_map_path, low_memory=False)
            sm = sm.copy()
            sm["ticker"] = sm.get("ticker", "").map(_normalize_ticker)
            sm = sm[sm["ticker"] != ""].drop_duplicates(["ticker"], keep="last")
            keep = [c for c in ["ticker", "sector", "industry", "state"] if c in sm.columns]
            ref = ref.merge(sm[keep], on="ticker", how="left")
        if universe_path.exists():
            nf = pd.read_csv(universe_path, low_memory=False)
            nf = nf.copy()
            nf["ticker"] = _coalesce(nf, "Symbol", "NSE Symbol", default="").map(_normalize_ticker)
            nf = nf[nf["ticker"] != ""].drop_duplicates(["ticker"], keep="last")
            merge_cols = {
                "Symbol": "symbol_nifty500",
                "NSE Symbol": "symbol_nifty500",
                "Industry": "industry_nifty500",
                "NIFTY500 Broad Sector": "industry_nifty500",
                "Company Name": "company_name",
                "Subsector": "subsector",
                "HQ City": "hq_city",
                "Conglomerate / Group": "conglomerate_group",
                "International Brand / MNC Subsidiary": "international_brand_mnc_subsidiary",
                "Intl Brand / MNC": "international_brand_mnc_subsidiary",
                "Commodity Sensitivities": "commodity_sensitivities",
                "Sector & Macro Sensitivities": "sector_macro_sensitivities",
                "Key Interconnections & Peers": "key_interconnections_peers",
                "Data Enrichment Status": "data_enrichment_status",
            }
            take = ["ticker"] + [c for c in merge_cols if c in nf.columns]
            subset = nf[take].rename(columns=merge_cols)
            ref = ref.merge(subset, on="ticker", how="left")
            if "industry_nifty500" in ref.columns:
                ref["industry"] = _coalesce(ref, "industry", "industry_nifty500")
                ref = ref.drop(columns=["industry_nifty500"], errors="ignore")
            if "symbol_nifty500" in ref.columns:
                ref["symbol"] = _coalesce(ref, "symbol", "symbol_nifty500", default="")
                ref = ref.drop(columns=["symbol_nifty500"], errors="ignore")

        if not meta.empty:
            meta_take = [c for c in [
                "ticker",
                "company_name",
                "sector",
                "industry",
                "about_text",
                "website",
                "is_delisted",
                "record_origin",
            ] if c in meta.columns]
            meta_subset = meta[meta_take].rename(
                columns={
                    "is_delisted": "is_delisted_screener_metadata",
                    "record_origin": "metadata_record_origin",
                }
            )
            ref = ref.merge(meta_subset, on="ticker", how="left")
            ref["company_name"] = _coalesce(ref, "company_name_x", "company_name_y", "company_name", default="")
            ref["sector"] = _coalesce(ref, "sector_x", "sector_y", "sector", default="")
            ref["industry"] = _coalesce(ref, "industry_x", "industry_y", "industry", default="")
            ref = ref.drop(
                columns=[c for c in ["company_name_x", "company_name_y", "sector_x", "sector_y", "industry_x", "industry_y"] if c in ref.columns],
                errors="ignore",
            )

        if not delist_df.empty:
            keep = [c for c in ["ticker", "delisting_date", "delisting_type_original", "reason", "final_price", "takeover_price", "pnl_impact"] if c in delist_df.columns]
            delist_subset = delist_df[keep].copy()
            delist_subset["delisting_date"] = _as_dates(delist_subset.get("delisting_date")).dt.normalize()
            dtype_raw = delist_df.get("delisting_type_original", pd.Series("", index=delist_df.index)).astype(str).str.lower()
            reason_raw = delist_df.get("reason", pd.Series("", index=delist_df.index)).astype(str).str.lower()
            delist_subset["delisting_class"] = np.where(
                reason_raw.isin({"financial_distress", "regulatory"})
                | dtype_raw.str.contains("compulsory|liquidation|insolvency", regex=True, na=False),
                "forced",
                "voluntary",
            )
            delist_subset["has_delisting_record"] = True
            delist_subset = delist_subset.drop_duplicates(["ticker"], keep="first")
            ref = ref.merge(delist_subset, on="ticker", how="left")
        else:
            ref["has_delisting_record"] = False

        if not prices.empty and {"ticker", "date"}.issubset(set(prices.columns)):
            price_span = (
                prices.assign(date=_as_dates(prices.get("date")).dt.normalize())
                .dropna(subset=["date"])
                .groupby("ticker", as_index=False)["date"]
                .agg(["min", "max"])
                .reset_index()
                .rename(columns={"min": "price_history_start", "max": "price_history_end"})
            )
            ref = ref.merge(price_span, on="ticker", how="left")

        if universe_snapshots_path.exists():
            snapshots = pd.read_parquet(universe_snapshots_path)
            if {"ticker", "date"}.issubset(set(snapshots.columns)):
                snapshots = snapshots.copy()
                snapshots["ticker"] = snapshots.get("ticker", "").map(_normalize_ticker)
                snapshots["date"] = _as_dates(snapshots.get("date")).dt.normalize()
                snapshots = snapshots[(snapshots["ticker"] != "") & snapshots["date"].notna()].copy()
                if not snapshots.empty:
                    universe_span = (
                        snapshots.groupby("ticker", as_index=False)["date"]
                        .agg(["min", "max"])
                        .reset_index()
                        .rename(columns={"min": "universe_first_seen", "max": "universe_last_seen"})
                    )
                    ref = ref.merge(universe_span, on="ticker", how="left")

        ref["sector"] = ref.get("sector", pd.Series(dtype="object")).fillna("")
        ref["industry"] = ref.get("industry", pd.Series(dtype="object")).fillna("")
        ref["state"] = ref.get("state", pd.Series(dtype="object")).fillna("")
        ref["company_name"] = ref.get("company_name", pd.Series(dtype="object")).fillna("")
        ref["website"] = ref.get("website", pd.Series(dtype="object")).fillna("")
        ref["about_text"] = ref.get("about_text", pd.Series(dtype="object")).fillna("")
        ref["metadata_record_origin"] = ref.get("metadata_record_origin", pd.Series(dtype="object")).fillna("")
        ref["is_delisted_screener_metadata"] = ref.get("is_delisted_screener_metadata", False).fillna(False).astype(bool)
        ref["has_delisting_record"] = ref.get("has_delisting_record", False).fillna(False).astype(bool)
        for col in [
            "subsector",
            "hq_city",
            "conglomerate_group",
            "international_brand_mnc_subsidiary",
            "commodity_sensitivities",
            "sector_macro_sensitivities",
            "key_interconnections_peers",
            "data_enrichment_status",
        ]:
            ref[col] = ref.get(col, pd.Series(dtype="object")).fillna("")
        ref = ref.sort_values("ticker", kind="mergesort").reset_index(drop=True)
        self._write_parquet("ticker_master", ref, "reference/ticker_master.parquet")
        return ref

    def finalize(self) -> None:
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest, indent=2, default=str))
        print(f"[canonical] wrote manifest: {manifest_path.relative_to(REPO_ROOT)}")

    def build_all(self) -> None:
        self.build_prices()
        self.build_fundamentals_annual()
        self.build_fundamentals_quarterly()
        self.build_shareholding()
        self.build_company_news()
        self.build_market_news()
        self.build_sentiment()
        self.build_rbi_macro()
        self.build_macro_regime_features()
        self.build_cea_power_daily()
        self.build_cea_power_state_yearly()
        self.build_gst_panels()
        self.build_alternative()
        self.build_reference_master()
        self.finalize()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical cross-source training datasets.")
    parser.add_argument(
        "--canonical-root",
        default="data/canonical",
        help="Root directory for canonical outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    canonical_root = REPO_ROOT / str(args.canonical_root)
    builder = CanonicalDatasetBuilder(canonical_root=canonical_root)
    builder.build_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
