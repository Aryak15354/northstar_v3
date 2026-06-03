#!/usr/bin/env python3
"""Stage exact market series required by the Northstar V3 plan-signal audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.tseries.offsets import BDay, MonthEnd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.cross_asset_data import update_symbol_history, write_cross_asset_outputs  # noqa: E402

FRED_COAL_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCOALAUUSDM"

PLAN_SIGNAL_SERIES = [
    {
        "signal": "dxy_4w_return",
        "asset_class": "indices",
        "symbol": "DX-Y.NYB",
        "notes": "US Dollar Index.",
    },
    {
        "signal": "steel_4w_return",
        "asset_class": "commodities",
        "symbol": "HRC=F",
        "notes": "U.S. Midwest Domestic Hot-Rolled Coil futures.",
    },
    {
        "signal": "coal_4w_return",
        "asset_class": "commodities",
        "symbol": "MTF=F",
        "notes": "Coal (API2) CIF ARA futures.",
    },
    {
        "signal": "us_10y_4w",
        "asset_class": "rates",
        "symbol": "^TNX",
        "notes": "CBOE 10-Year Treasury yield index.",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage exact market series for the strict plan-signal audit.")
    parser.add_argument("--start-date", type=str, default="2018-01-01")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--raw-root", type=Path, default=PROJECT_ROOT / "data" / "raw")
    parser.add_argument(
        "--panel-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "canonical" / "macro" / "cross_asset_prices_daily.parquet",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "shared" / "market_data" / "cross_asset_manifest.json",
    )
    parser.add_argument(
        "--india-vix-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "india_vix.parquet",
    )
    parser.add_argument(
        "--coal-benchmark-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "macro" / "coal_benchmark_daily.parquet",
    )
    parser.add_argument("--timeout-seconds", type=int, default=20)
    return parser.parse_args()


def _save_india_vix(*, out_path: Path, start_date: str, end_date: str | None) -> dict[str, Any]:
    try:
        import yfinance as yf
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"yfinance_not_available:{exc}") from exc

    end = str(end_date or "").strip() or None
    frame = yf.download("^INDIAVIX", start=start_date, end=end, progress=False, threads=False, auto_adjust=False)
    if frame is None or frame.empty:
        raise SystemExit("india_vix_download_empty")

    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [col[0] if isinstance(col, tuple) else col for col in frame.columns]
    work = frame.reset_index()
    if "Date" not in work.columns:
        work = work.rename(columns={str(work.columns[0]): "Date"})
    work = work.rename(columns={"Date": "date", "Close": "vix"})
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    work["vix"] = pd.to_numeric(work["vix"], errors="coerce")
    work = work.dropna(subset=["date", "vix"]).sort_values("date", kind="mergesort").drop_duplicates("date", keep="last")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    work[["date", "vix"]].to_parquet(out_path, index=False)
    work[["date", "vix"]].to_csv(out_path.with_suffix(".csv"), index=False)

    return {
        "path": str(out_path),
        "csv_path": str(out_path.with_suffix(".csv")),
        "rows": int(len(work)),
        "date_min": None if work.empty else work["date"].min().date().isoformat(),
        "date_max": None if work.empty else work["date"].max().date().isoformat(),
        "symbol": "^INDIAVIX",
    }


def _save_coal_benchmark_fallback(*, out_path: Path, start_date: str, end_date: str | None) -> dict[str, Any]:
    raw = pd.read_csv(FRED_COAL_URL)
    if raw.empty or "observation_date" not in raw.columns or "PCOALAUUSDM" not in raw.columns:
        raise SystemExit("coal_benchmark_download_empty")

    work = raw.rename(columns={"PCOALAUUSDM": "coal_price_usd_per_ton"}).copy()
    work["observation_date"] = pd.to_datetime(work["observation_date"], errors="coerce").dt.normalize()
    work["coal_price_usd_per_ton"] = pd.to_numeric(work["coal_price_usd_per_ton"], errors="coerce")
    work = work.dropna(subset=["observation_date", "coal_price_usd_per_ton"]).sort_values(
        "observation_date", kind="mergesort"
    )
    if work.empty:
        raise SystemExit("coal_benchmark_no_valid_rows")

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize() if end_date else pd.Timestamp.utcnow().tz_localize(None).normalize()
    work = work[work["observation_date"] >= (start_ts - MonthEnd(2))].copy()
    work["availability_date"] = (work["observation_date"] + MonthEnd(1) + BDay(1)).dt.normalize()
    work["source"] = "fred:PCOALAUUSDM"
    effective = work[["availability_date", "coal_price_usd_per_ton", "observation_date", "source"]].copy()
    effective = effective.drop_duplicates(subset=["availability_date"], keep="last").sort_values(
        "availability_date", kind="mergesort"
    )

    daily = pd.DataFrame({"date": pd.date_range(start=effective["availability_date"].min(), end=end_ts, freq="B")})
    daily = pd.merge_asof(
        daily.sort_values("date"),
        effective.rename(columns={"availability_date": "effective_date"}).sort_values("effective_date"),
        left_on="date",
        right_on="effective_date",
        direction="backward",
    )
    daily = daily.drop(columns=["effective_date"], errors="ignore")
    daily = daily[daily["date"] >= start_ts].copy()
    daily = daily.dropna(subset=["coal_price_usd_per_ton"]).sort_values("date", kind="mergesort").reset_index(drop=True)
    if daily.empty:
        raise SystemExit("coal_benchmark_daily_projection_empty")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_path, index=False)
    daily.to_csv(out_path.with_suffix(".csv"), index=False)

    return {
        "path": str(out_path),
        "csv_path": str(out_path.with_suffix(".csv")),
        "rows": int(len(daily)),
        "date_min": daily["date"].min().date().isoformat(),
        "date_max": daily["date"].max().date().isoformat(),
        "series_id": "PCOALAUUSDM",
        "source": "FRED",
    }


def main() -> int:
    args = parse_args()
    raw_root = args.raw_root.expanduser().resolve()
    updates: list[dict[str, Any]] = []

    for item in PLAN_SIGNAL_SERIES:
        asset_dir = raw_root / str(item["asset_class"])
        path = asset_dir / f"{item['symbol']}.csv"
        result = update_symbol_history(
            symbol=str(item["symbol"]),
            path=path,
            start_date=args.start_date,
            end_date=args.end_date,
            timeout_seconds=args.timeout_seconds,
        )
        result["asset_class"] = str(item["asset_class"])
        result["signal"] = str(item["signal"])
        result["notes"] = str(item["notes"])
        updates.append(result)
        print(
            f"[plan-signal-data] {item['signal']} <- {item['symbol']} "
            f"rows={result['rows']} date_max={result['date_max']} downloaded_rows={result['downloaded_rows']}",
            flush=True,
        )

    vix_result = _save_india_vix(
        out_path=args.india_vix_path.expanduser().resolve(),
        start_date=args.start_date,
        end_date=args.end_date,
    )
    coal_benchmark_result = _save_coal_benchmark_fallback(
        out_path=args.coal_benchmark_path.expanduser().resolve(),
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(
        f"[plan-signal-data] vix_india_4w <- ^INDIAVIX rows={vix_result['rows']} date_max={vix_result['date_max']}",
        flush=True,
    )
    print(
        "[plan-signal-data] coal benchmark fallback <- FRED/PCOALAUUSDM "
        f"rows={coal_benchmark_result['rows']} date_max={coal_benchmark_result['date_max']}",
        flush=True,
    )

    manifest = write_cross_asset_outputs(
        raw_root=raw_root,
        panel_path=args.panel_path.expanduser().resolve(),
        manifest_path=args.manifest_path.expanduser().resolve(),
    )
    manifest["plan_signal_updates"] = updates
    manifest["india_vix"] = vix_result
    manifest["coal_benchmark_fallback"] = coal_benchmark_result
    args.manifest_path.expanduser().resolve().write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "raw_root": str(raw_root),
                "panel_path": str(args.panel_path.expanduser().resolve()),
                "india_vix_path": str(args.india_vix_path.expanduser().resolve()),
                "coal_benchmark_path": str(args.coal_benchmark_path.expanduser().resolve()),
                "symbols_staged": [item["symbol"] for item in PLAN_SIGNAL_SERIES] + ["^INDIAVIX"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
