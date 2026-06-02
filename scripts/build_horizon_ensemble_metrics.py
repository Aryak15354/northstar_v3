#!/usr/bin/env python3
"""Build weighted horizon-ensemble metrics from regime IC run JSON outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _load(path: Path) -> Dict:
    return dict(json.loads(path.read_text()))


def _ret_series(payload: Dict) -> pd.Series:
    rows = list(payload.get("portfolio_return_series", []) or [])
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    if "date" not in df.columns or "return" not in df.columns:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["return"] = pd.to_numeric(df["return"], errors="coerce")
    df = df.dropna(subset=["date", "return"]).sort_values("date")
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["return"].to_numpy(dtype=float), index=pd.DatetimeIndex(df["date"]))


def _max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    r = np.clip(np.nan_to_num(returns, nan=0.0, posinf=1.0, neginf=-0.999), -0.999, 1.0)
    curve = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(curve)
    dd = (curve / np.maximum(peak, 1e-12)) - 1.0
    return float(abs(np.min(dd)))


def _compute_metrics(returns: pd.Series) -> Dict[str, float]:
    r = returns.to_numpy(dtype=float)
    if len(r) == 0:
        return {"days": 0.0, "avg_daily_return": 0.0, "daily_vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    mu = float(np.mean(r))
    vol = float(np.std(r))
    sharpe = float((mu / (vol + 1e-12)) * np.sqrt(252.0))
    return {
        "days": float(len(r)),
        "avg_daily_return": mu,
        "daily_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(r),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Combine horizon runs into weighted ensemble metrics")
    ap.add_argument("--h5-json", required=True)
    ap.add_argument("--h10-json", required=True)
    ap.add_argument("--h30-json", required=True)
    ap.add_argument("--weights", default="0.3,0.4,0.3", help="w5,w10,w30")
    ap.add_argument("--output-json", default="data/results/research/reports/horizon_ensemble_metrics_latest.json")
    args = ap.parse_args()

    w_parts = [float(x.strip()) for x in str(args.weights).split(",") if str(x).strip()]
    if len(w_parts) != 3:
        raise ValueError("--weights must have exactly 3 values: w5,w10,w30")
    w = np.asarray(w_parts, dtype=float)
    w = w / max(1e-12, float(np.sum(np.abs(w))))

    p5 = _load(Path(args.h5_json))
    p10 = _load(Path(args.h10_json))
    p30 = _load(Path(args.h30_json))

    s5 = _ret_series(p5)
    s10 = _ret_series(p10)
    s30 = _ret_series(p30)

    all_idx = s5.index.union(s10.index).union(s30.index).sort_values()
    s5 = s5.reindex(all_idx, fill_value=0.0)
    s10 = s10.reindex(all_idx, fill_value=0.0)
    s30 = s30.reindex(all_idx, fill_value=0.0)

    ens = (w[0] * s5) + (w[1] * s10) + (w[2] * s30)
    metrics = _compute_metrics(ens)

    ic5 = float((p5.get("aggregate_metrics", {}) or {}).get("ic_mean", 0.0) or 0.0)
    ic10 = float((p10.get("aggregate_metrics", {}) or {}).get("ic_mean", 0.0) or 0.0)
    ic30 = float((p30.get("aggregate_metrics", {}) or {}).get("ic_mean", 0.0) or 0.0)
    weighted_ic_proxy = float(w[0] * ic5 + w[1] * ic10 + w[2] * ic30)

    out = {
        "inputs": {
            "h5_json": str(args.h5_json),
            "h10_json": str(args.h10_json),
            "h30_json": str(args.h30_json),
            "weights": {"h5": float(w[0]), "h10": float(w[1]), "h30": float(w[2])},
        },
        "component_ic_mean": {"h5": ic5, "h10": ic10, "h30": ic30},
        "weighted_ic_proxy": weighted_ic_proxy,
        "ensemble_metrics": metrics,
        "ensemble_return_series": [
            {"date": pd.Timestamp(d).isoformat(), "return": float(v)}
            for d, v in zip(all_idx.tolist(), ens.to_numpy(dtype=float).tolist())
        ],
    }

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[horizon-ensemble] wrote {out_path}")
    print(f"[horizon-ensemble] weighted_ic_proxy={weighted_ic_proxy:.4f} sharpe={metrics['sharpe']:.4f} max_dd={metrics['max_drawdown']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

