"""Refresh and verify raw forex and commodities datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Symbol"]


def _utc_today() -> pd.Timestamp:
    return pd.Timestamp.utcnow().tz_localize(None).normalize()


def normalize_download_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    work = frame.copy()
    if isinstance(work.columns, pd.MultiIndex):
        work.columns = [col[0] if isinstance(col, tuple) else col for col in work.columns]
    work = work.reset_index()
    if "Date" not in work.columns:
        first_col = str(work.columns[0])
        work = work.rename(columns={first_col: "Date"})
    rename_map = {
        "AdjClose": "Adj Close",
        "Adj_Close": "Adj Close",
    }
    work = work.rename(columns=rename_map)
    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        if col not in work.columns:
            work[col] = pd.NA
    work["Date"] = pd.to_datetime(work["Date"], errors="coerce").dt.normalize()
    work["Symbol"] = symbol
    work = work.dropna(subset=["Date"]).copy()
    work = work[EXPECTED_COLUMNS].sort_values("Date", kind="mergesort").drop_duplicates("Date", keep="last")
    work["Date"] = work["Date"].dt.strftime("%Y-%m-%d")
    return work.reset_index(drop=True)


def load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    frame = pd.read_csv(path)
    for col in EXPECTED_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    frame = frame[EXPECTED_COLUMNS].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["Date"]).sort_values("Date", kind="mergesort").drop_duplicates("Date", keep="last")
    return frame.reset_index(drop=True)


def discover_symbols(raw_root: Path, asset_classes: Iterable[str]) -> dict[str, list[str]]:
    discovered: dict[str, list[str]] = {}
    for asset_class in asset_classes:
        asset_dir = raw_root / asset_class
        discovered[asset_class] = sorted(path.stem for path in asset_dir.glob("*.csv"))
    return discovered


def update_symbol_history(
    *,
    symbol: str,
    path: Path,
    start_date: str | None = None,
    end_date: str | None = None,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    existing = load_history(path)
    requested_start = pd.Timestamp(start_date).normalize() if start_date else None
    requested_end = pd.Timestamp(end_date).normalize() if end_date else _utc_today()

    if existing.empty:
        download_start = requested_start or pd.Timestamp("1996-01-01")
    else:
        last_date = pd.to_datetime(existing["Date"], errors="coerce").dropna().max()
        download_start = max(last_date + pd.Timedelta(days=1), requested_start) if requested_start is not None else last_date + pd.Timedelta(days=1)

    if download_start <= requested_end:
        data = yf.download(
            symbol,
            start=download_start.strftime("%Y-%m-%d"),
            end=(requested_end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=max(1, int(timeout_seconds)),
        )
        downloaded = normalize_download_frame(data, symbol)
    else:
        downloaded = pd.DataFrame(columns=EXPECTED_COLUMNS)

    parts = []
    if not existing.empty:
        parts.append(existing.assign(Date=pd.to_datetime(existing["Date"], errors="coerce").dt.strftime("%Y-%m-%d")))
    if not downloaded.empty:
        parts.append(downloaded)

    parts = [part for part in parts if not part.empty]
    if parts:
        combined = pd.concat(parts, ignore_index=True)
        combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce").dt.normalize()
        combined = combined.dropna(subset=["Date"]).sort_values("Date", kind="mergesort").drop_duplicates("Date", keep="last")
    else:
        combined = pd.DataFrame(columns=EXPECTED_COLUMNS)

    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")
    combined["Symbol"] = symbol
    combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    path.parent.mkdir(parents=True, exist_ok=True)
    combined[EXPECTED_COLUMNS].to_csv(path, index=False)

    dates = pd.to_datetime(combined["Date"], errors="coerce").dropna()
    latest = dates.max() if not dates.empty else pd.NaT
    return {
        "symbol": symbol,
        "path": str(path),
        "rows": int(len(combined)),
        "date_min": None if dates.empty else str(dates.min().date()),
        "date_max": None if dates.empty else str(latest.date()),
        "download_start": str(download_start.date()) if download_start is not None else None,
        "requested_end": str(requested_end.date()),
        "downloaded_rows": int(len(downloaded)),
        "stale_days": None if pd.isna(latest) else int((requested_end - latest).days),
    }


def build_cross_asset_panel(raw_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for asset_class in ["commodities", "forex"]:
        asset_dir = raw_root / asset_class
        for path in sorted(asset_dir.glob("*.csv")):
            frame = load_history(path)
            if frame.empty:
                continue
            frame = frame.copy()
            frame["date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
            frame["symbol"] = frame.get("Symbol", path.stem).astype(str)
            frame["asset_class"] = asset_class
            frame = frame.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                }
            )
            keep = ["date", "symbol", "asset_class", "open", "high", "low", "close", "adj_close", "volume"]
            frames.append(frame[keep])
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "asset_class", "open", "high", "low", "close", "adj_close", "volume"])
    panel = pd.concat(frames, ignore_index=True)
    panel = panel.sort_values(["asset_class", "symbol", "date"], kind="mergesort").drop_duplicates(
        ["asset_class", "symbol", "date"],
        keep="last",
    )
    return panel.reset_index(drop=True)


def build_coverage_manifest(raw_root: Path, *, as_of: pd.Timestamp | None = None) -> dict[str, Any]:
    as_of = (as_of or _utc_today()).normalize()
    assets = []
    for asset_class in ["commodities", "forex"]:
        for path in sorted((raw_root / asset_class).glob("*.csv")):
            frame = load_history(path)
            dates = pd.to_datetime(frame["Date"], errors="coerce").dropna()
            latest = dates.max() if not dates.empty else pd.NaT
            assets.append(
                {
                    "asset_class": asset_class,
                    "symbol": path.stem,
                    "path": str(path),
                    "rows": int(len(frame)),
                    "date_min": None if dates.empty else str(dates.min().date()),
                    "date_max": None if dates.empty else str(latest.date()),
                    "stale_days": None if pd.isna(latest) else int((as_of - latest).days),
                }
            )
    return {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "as_of": str(as_of.date()),
        "assets": assets,
    }


def write_cross_asset_outputs(
    *,
    raw_root: Path,
    panel_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    panel = build_cross_asset_panel(raw_root)
    panel_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(panel_path, index=False)
    panel.to_csv(panel_path.with_suffix(".csv"), index=False)
    manifest = build_coverage_manifest(raw_root)
    manifest["panel_path"] = str(panel_path)
    manifest["panel_csv_path"] = str(panel_path.with_suffix(".csv"))
    manifest["panel_rows"] = int(len(panel))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
