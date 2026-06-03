#!/usr/bin/env python3
"""
Macro Blocks Engine - Step 2 of Northstar Macro Engine
Builds Growth, Inflation, Liquidity, Stress latent factors using PCA.

This version dynamically maps RBI column variants (v1/v2/.../vN naming),
so factor construction remains robust when upstream schema labels drift.
"""

import os
import re

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

IN_FILE = "data/macro/cleaned/macro_cleaned.parquet"
OUT_FILE = "data/macro/factors/macro_factors.parquet"

os.makedirs("data/macro/factors", exist_ok=True)


FACTOR_PATTERNS = {
    "G": [
        "treasury bill",
        "g-sec yield",
        "index of industrial production",
        "gross domestic product",
        "nifty",
        "sensex",
        "bankex",
        "foreign trade exports",
    ],
    "I": [
        "policy repo rate",
        "reverse repo rate",
        "bank rate",
        "marginal standing facility",
        "standing deposit facility",
        "consumer price index",
        "wholesale price index",
    ],
    "L": [
        "cash reserve ratio",
        "statutory liquidity ratio",
        "foreign exchange reserves",
        "m3",
        "bank credit",
        "aggregate desposits",
        "aggregate deposits",
        "non food credit",
        "certificates of deposit",
    ],
    "S": [
        "forward premia",
        "exchange rate of indian rupee vis-à-vis us dollar",
        "trade balance",
        "overall balance of payments",
        "external debt",
        "international investment position",
    ],
}


def _normalize_metric_name(col: str) -> str:
    s = str(col)
    s = re.sub(r"^core_macro_[a-z]+_[a-z]+_v\d+_", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^core_macro_[a-z]+_[a-z]+_", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^core_macro_[a-z]+_v\d+_", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^core_macro_[a-z]+_", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def _extract_version(col: str) -> int:
    m = re.search(r"_v(\d+)_", str(col), flags=re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _select_columns(df: pd.DataFrame, patterns: list[str], max_cols: int = 16) -> list[str]:
    candidates = []
    for c in df.columns:
        c_l = str(c).lower()
        if not any(p in c_l for p in patterns):
            continue

        s = pd.to_numeric(df[c], errors="coerce")
        non_null = int(s.notna().sum())
        if non_null < 24:
            continue
        variance = float(s.var(skipna=True)) if non_null > 1 else 0.0
        if not np.isfinite(variance) or variance <= 0:
            continue
        candidates.append((c, non_null, variance, _extract_version(c), _normalize_metric_name(c)))

    if not candidates:
        return []

    # Deduplicate versioned variants by normalized metric name.
    best_by_metric = {}
    for col, non_null, variance, version, metric_key in candidates:
        prev = best_by_metric.get(metric_key)
        # Prefer higher non-null count, then higher version.
        score = (non_null, version, variance)
        if prev is None or score > prev[1]:
            best_by_metric[metric_key] = (col, score)

    chosen = [v[0] for v in best_by_metric.values()]
    chosen = sorted(
        chosen,
        key=lambda c: (pd.to_numeric(df[c], errors="coerce").notna().sum(), _extract_version(c)),
        reverse=True,
    )
    return chosen[:max_cols]


def _prepare_block(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    x = df[cols].apply(pd.to_numeric, errors="coerce").copy()

    # Keep rows with sufficient observed indicators in the block.
    coverage = x.notna().mean(axis=1)
    x = x[coverage >= 0.50]
    if x.empty:
        return x

    # Robust fill for mixed-frequency macro data.
    x = x.sort_index().ffill().bfill()
    med = x.median(axis=0, skipna=True)
    x = x.fillna(med)

    # Drop any degenerate columns post-fill.
    valid_cols = []
    for c in x.columns:
        s = x[c]
        if s.notna().sum() >= 24 and s.std(skipna=True) > 0:
            valid_cols.append(c)
    return x[valid_cols]


def make_factor(df: pd.DataFrame, factor_code: str, factor_label: str) -> pd.Series:
    patterns = FACTOR_PATTERNS[factor_code]
    available_cols = _select_columns(df, patterns)

    if not available_cols:
        print(f"   ⚠️  No data available for {factor_label} factor")
        return pd.Series(index=df.index, dtype=float)

    print(f"   📊 {factor_label}: Using {len(available_cols)} indicators")
    for c in available_cols[:10]:
        print(f"      - {c}")
    if len(available_cols) > 10:
        print(f"      ... (+{len(available_cols) - 10} more)")

    x = _prepare_block(df, available_cols)
    if len(x) < 24 or x.shape[1] < 2:
        print(f"   ⚠️  Insufficient usable data for {factor_label} ({len(x)} rows, {x.shape[1]} cols)")
        return pd.Series(index=df.index, dtype=float)

    scaler = StandardScaler()
    z = scaler.fit_transform(x)

    pca = PCA(n_components=1, random_state=42)
    factor_values = pca.fit_transform(z).flatten()
    factor_series = pd.Series(index=x.index, data=factor_values).reindex(df.index)

    explained_var = pca.explained_variance_ratio_[0]
    print(f"      Explained variance: {explained_var:.1%}")
    return factor_series


def validate_factors(factors_df: pd.DataFrame) -> None:
    print("\n📊 Factor Validation:")
    print("=" * 30)
    for factor in factors_df.columns:
        series = pd.to_numeric(factors_df[factor], errors="coerce").dropna()
        if len(series) > 0:
            print(f"{factor}:")
            print(f"  Observations: {len(series)}")
            print(f"  Mean: {series.mean():.3f}")
            print(f"  Std: {series.std():.3f}")
            print(f"  Range: [{series.min():.3f}, {series.max():.3f}]")
        else:
            print(f"{factor}: No valid data")
        print()


def _resolve_anchor_cols(df: pd.DataFrame, tokens: list[str], max_cols: int = 8) -> list[str]:
    chosen = []
    for token in tokens:
        t = token.lower()
        exact = [c for c in df.columns if str(c).lower() == t]
        if exact:
            chosen.extend(exact)
            continue
        partial = [c for c in df.columns if t in str(c).lower()]
        chosen.extend(partial)
    # Deduplicate while preserving order.
    seen = set()
    uniq = []
    for c in chosen:
        if c in seen:
            continue
        seen.add(c)
        uniq.append(c)
    # Prefer columns with higher coverage.
    uniq = sorted(uniq, key=lambda c: pd.to_numeric(df[c], errors="coerce").notna().sum(), reverse=True)
    return uniq[:max_cols]


def _orient_factor(series: pd.Series, raw_df: pd.DataFrame, anchor_tokens: list[str], default_sign: float = 1.0) -> pd.Series:
    anchors = _resolve_anchor_cols(raw_df, anchor_tokens)
    if not anchors or series.dropna().empty:
        return series * default_sign

    tmp = pd.concat([raw_df[anchors], series.rename("factor")], axis=1).dropna()
    if tmp.empty:
        return series * default_sign

    anchor_comp = tmp[anchors].mean(axis=1)
    corr = anchor_comp.corr(tmp["factor"])
    if pd.isna(corr):
        return series * default_sign
    if corr < 0:
        return -series
    return series


def run() -> None:
    print("🧠 Macro Blocks Engine - Step 2")
    print("=" * 50)

    print("📥 Loading cleaned macro data...")
    if not os.path.exists(IN_FILE):
        print(f"❌ Cleaned macro data not found: {IN_FILE}")
        print("   Run macro_cleaner.py first!")
        return

    macro = pd.read_parquet(IN_FILE)
    if not isinstance(macro.index, pd.DatetimeIndex):
        macro.index = pd.to_datetime(macro.index, errors="coerce")
    macro = macro.sort_index()

    print(f"   Loaded: {len(macro)} weeks × {len(macro.columns)} indicators")
    print(f"   Date range: {macro.index.min()} to {macro.index.max()}")

    factors = pd.DataFrame(index=macro.index)

    print("\n🏗️  Building macro factors...")
    print("\n1️⃣  GROWTH Factor (G)")
    print("   Theory: Economic growth expectations from activity + yields")
    factors["G"] = make_factor(macro, "G", "Growth")

    print("\n2️⃣  INFLATION Factor (I)")
    print("   Theory: Policy + price pressure dynamics")
    factors["I"] = make_factor(macro, "I", "Inflation")

    print("\n3️⃣  LIQUIDITY Factor (L)")
    print("   Theory: System liquidity and money-credit conditions")
    factors["L"] = make_factor(macro, "L", "Liquidity")

    print("\n4️⃣  STRESS Factor (S)")
    print("   Theory: FX/BoP/forward-premia stress channels")
    factors["S"] = make_factor(macro, "S", "Stress")

    factors = factors.dropna(how="all")
    print(f"\n📊 Final factor dataset: {len(factors)} observations")

    validate_factors(factors)

    print("🔗 Factor Correlations:")
    corr_matrix = factors.corr()
    print(corr_matrix.round(3))

    # Deterministic orientation by macro anchors.
    factors["G"] = _orient_factor(
        factors["G"], macro, ["nifty", "gross domestic product", "index of industrial production", "10-year g-sec yield"], 1.0
    )
    factors["I"] = _orient_factor(
        factors["I"], macro, ["consumer price index", "wholesale price index", "policy repo rate"], 1.0
    )
    factors["L"] = _orient_factor(
        factors["L"], macro, ["m3", "bank credit", "aggregate desposits", "foreign exchange reserves"], 1.0
    )
    factors["S"] = _orient_factor(
        factors["S"], macro, ["exchange rate of indian rupee vis-à-vis us dollar", "forward premia", "trade balance"], 1.0
    )

    factors.to_parquet(OUT_FILE)
    print(f"\n✅ Saved macro factors: {OUT_FILE}")

    summary_file = OUT_FILE.replace(".parquet", "_summary.csv")
    factors.describe().to_csv(summary_file)
    print(f"📋 Factor summary: {summary_file}")

    corr_file = OUT_FILE.replace(".parquet", "_correlations.csv")
    corr_matrix.to_csv(corr_file)
    print(f"🔗 Correlations: {corr_file}")


if __name__ == "__main__":
    run()
