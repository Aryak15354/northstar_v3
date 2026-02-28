#!/usr/bin/env python3
"""
Macro Blocks Engine v2 - long-history global PCA de-correlation.

Why this exists:
- v1 block-wise PCA can leave strong collinearity between factors.
- v1 cleaned feed may start only around 2017 in some runs.

v2 builds factors from long-history RBI data (preferred: comprehensive_rbi_data.parquet),
then applies a single global PCA and maps orthogonal components to semantic factors
(G/I/L/S) using anchor-correlation orientation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


DEFAULT_INPUT_CANDIDATES = [
    Path("data/macro/comprehensive_rbi_data.parquet"),
    Path("data/macro/macro_indicators.parquet"),
    Path("data/macro/cleaned/macro_cleaned.parquet"),
]
DEFAULT_OUT_FILE = Path("data/macro/factors/macro_factors_v2.parquet")

FACTOR_ANCHORS: Dict[str, List[str]] = {
    "G": [
        "gross domestic product",
        "gdp",
        "index of industrial production",
        "iip",
        "nifty",
        "sensex",
        "bankex",
        "exports",
    ],
    "I": [
        "consumer price index",
        "cpi",
        "wholesale price index",
        "wpi",
        "policy repo",
        "repo rate",
    ],
    "L": [
        "m3",
        "money supply",
        "bank credit",
        "aggregate deposits",
        "aggregate desposits",
        "foreign exchange reserves",
        "rbi balance sheet",
    ],
    "S": [
        "exchange rate",
        "usd",
        "inr",
        "forward premia",
        "trade balance",
        "current account",
        "external debt",
        "market stress",
    ],
}


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.index, pd.DatetimeIndex):
        out = df.copy()
        out.index = pd.to_datetime(out.index, errors="coerce")
        return out
    for c in ("date", "Date", "Period", "period", "timestamp"):
        if c in df.columns:
            out = df.copy()
            out[c] = pd.to_datetime(out[c], errors="coerce")
            out = out.dropna(subset=[c]).set_index(c)
            return out
    raise ValueError("Could not infer datetime index from input macro frame")


def _pick_input_file(explicit_path: str | None) -> Path:
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")
        return p
    for p in DEFAULT_INPUT_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No macro input file found. Checked: "
        + ", ".join(str(p) for p in DEFAULT_INPUT_CANDIDATES)
    )


def _match_columns(columns: Sequence[str], tokens: Sequence[str]) -> List[str]:
    out: List[str] = []
    for c in columns:
        c_l = str(c).lower()
        if any(t in c_l for t in tokens):
            out.append(c)
    return out


def _select_long_history_columns(
    df: pd.DataFrame,
    min_history_years: int,
    min_observations: int,
    min_coverage: float,
    max_indicators: int,
) -> List[str]:
    end_date = df.index.max()
    cutoff = end_date - pd.DateOffset(years=min_history_years)
    n_rows = max(len(df), 1)

    scored: List[tuple[str, tuple[float, float, float]]] = []
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        first_valid = s.first_valid_index()
        if first_valid is None:
            continue
        obs = int(s.notna().sum())
        coverage = float(obs) / float(n_rows)
        variance = float(s.var(skipna=True))
        if first_valid > cutoff:
            continue
        if obs < min_observations:
            continue
        if coverage < min_coverage:
            continue
        if not np.isfinite(variance) or variance <= 0:
            continue
        span_days = float((end_date - first_valid).days)
        score = (coverage, span_days, np.log1p(obs))
        scored.append((c, score))

    if not scored:
        return []

    scored = sorted(scored, key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max_indicators]]


def _make_anchor_composite(df: pd.DataFrame, cols: Sequence[str]) -> pd.Series:
    if not cols:
        return pd.Series(index=df.index, dtype=float)
    sub = df[list(cols)].apply(pd.to_numeric, errors="coerce").sort_index().ffill().bfill()
    return sub.mean(axis=1)


def build_macro_factors_v2(
    input_file: Path,
    output_file: Path,
    min_history_years: int = 12,
    min_observations: int = 260,
    min_coverage: float = 0.35,
    max_indicators: int = 160,
) -> dict:
    print("🧠 Macro Blocks Engine v2")
    print("=" * 60)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")

    raw = pd.read_parquet(input_file)
    raw = _ensure_datetime_index(raw)
    raw = raw[~raw.index.duplicated(keep="last")].sort_index()
    raw = raw.select_dtypes(include=[np.number]).copy()
    if raw.empty:
        raise RuntimeError("No numeric columns available in macro input")

    # Keep weekly cadence for compatibility with downstream regime scripts.
    raw = raw.resample("W-FRI").last()
    raw = raw.sort_index()
    print(f"Loaded matrix: {len(raw)} weeks × {len(raw.columns)} numeric indicators")
    print(f"Date range: {raw.index.min().date()} -> {raw.index.max().date()}")

    selected_cols = _select_long_history_columns(
        raw,
        min_history_years=min_history_years,
        min_observations=min_observations,
        min_coverage=min_coverage,
        max_indicators=max_indicators,
    )
    if not selected_cols:
        raise RuntimeError(
            "No long-history indicators selected. Relax thresholds "
            f"(years={min_history_years}, min_obs={min_observations}, min_coverage={min_coverage})."
        )

    x = raw[selected_cols].apply(pd.to_numeric, errors="coerce")
    x = x.sort_index().ffill().bfill()
    x = x.fillna(x.median(axis=0, skipna=True))
    valid_cols = [c for c in x.columns if x[c].std(skipna=True) > 0]
    x = x[valid_cols]
    if x.shape[1] < 4:
        raise RuntimeError(f"Need at least 4 valid indicators for global PCA, got {x.shape[1]}")

    scaler = StandardScaler()
    z = scaler.fit_transform(x)
    pca = PCA(n_components=4, random_state=42)
    pcs = pca.fit_transform(z)
    pc_names = [f"PC{i}" for i in range(1, 5)]
    pc_df = pd.DataFrame(index=x.index, data=pcs, columns=pc_names)
    explained = pca.explained_variance_ratio_.tolist()
    print("Global PCA explained variance:", ", ".join(f"{v:.2%}" for v in explained))

    # Assign orthogonal PCs to semantic factors via anchor correlation.
    assignments: Dict[str, str] = {}
    orientation: Dict[str, float] = {}
    remaining = pc_names.copy()
    factor_series: Dict[str, pd.Series] = {}

    for factor in ["G", "I", "L", "S"]:
        anchors = _match_columns(raw.columns, FACTOR_ANCHORS[factor])
        anchor_series = _make_anchor_composite(raw, anchors)
        best_pc = None
        best_corr = 0.0
        for pc in remaining:
            tmp = pd.concat([pc_df[pc], anchor_series.rename("anchor")], axis=1).dropna()
            if len(tmp) < 30:
                corr = 0.0
            else:
                corr = float(tmp[pc].corr(tmp["anchor"]))
                if not np.isfinite(corr):
                    corr = 0.0
            if best_pc is None or abs(corr) > abs(best_corr):
                best_pc = pc
                best_corr = corr
        if best_pc is None:
            best_pc = remaining[0]
            best_corr = 0.0
        sign = 1.0 if best_corr >= 0 else -1.0
        factor_series[factor] = sign * pc_df[best_pc]
        assignments[factor] = best_pc
        orientation[factor] = sign
        remaining.remove(best_pc)

    factors = pd.DataFrame(factor_series, index=pc_df.index).dropna(how="all")
    for c in ["G", "I", "L", "S"]:
        s = pd.to_numeric(factors[c], errors="coerce")
        factors[c] = (s - s.mean()) / (s.std() + 1e-12)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    factors.to_parquet(output_file)
    print(f"✅ Saved: {output_file} ({len(factors)} rows)")

    corr_file = output_file.with_name(output_file.stem + "_correlations.csv")
    factors.corr().to_csv(corr_file)
    print(f"🔗 Correlations: {corr_file}")

    selected_cols_file = output_file.with_name(output_file.stem + "_selected_columns.csv")
    pd.DataFrame({"column": valid_cols}).to_csv(selected_cols_file, index=False)

    meta = {
        "input_file": str(input_file),
        "output_file": str(output_file),
        "date_range": [str(factors.index.min().date()), str(factors.index.max().date())],
        "rows": int(len(factors)),
        "selected_indicator_count": int(len(valid_cols)),
        "pca_explained_variance": explained,
        "factor_pc_assignments": assignments,
        "factor_orientations": orientation,
    }
    meta_file = output_file.with_name(output_file.stem + "_metadata.json")
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"📋 Metadata: {meta_file}")

    return meta


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build long-history macro factors v2 using global PCA")
    p.add_argument("--input-file", type=str, default=None)
    p.add_argument("--output-file", type=str, default=str(DEFAULT_OUT_FILE))
    p.add_argument("--min-history-years", type=int, default=12)
    p.add_argument("--min-observations", type=int, default=260)
    p.add_argument("--min-coverage", type=float, default=0.35)
    p.add_argument("--max-indicators", type=int, default=160)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    input_file = _pick_input_file(args.input_file)
    build_macro_factors_v2(
        input_file=input_file,
        output_file=Path(args.output_file),
        min_history_years=args.min_history_years,
        min_observations=args.min_observations,
        min_coverage=args.min_coverage,
        max_indicators=args.max_indicators,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
