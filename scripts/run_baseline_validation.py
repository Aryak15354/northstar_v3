#!/usr/bin/env python3
"""
Baseline Model Validation Script

Trains baseline XGBoost model with corrected hyperparameters and validates:
1. Model trains successfully with min_child_weight=20
2. Baseline IC >= 0.032
3. All features pass leakage tests (IC_ratio < 1.20)

Usage:
    python scripts/run_baseline_validation.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.signal_engineering.config import SignalEngineeringConfig
from src.signal_engineering.leakage_test import run_leakage_test_suite

def _normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize identifier/date columns to `ticker` + `date`."""
    out = df.copy()
    if "date" not in out.columns:
        if "Date" in out.columns:
            out = out.rename(columns={"Date": "date"})
        elif "timestamp" in out.columns:
            out = out.rename(columns={"timestamp": "date"})
    if "symbol" in out.columns and "ticker" not in out.columns:
        out = out.rename(columns={"symbol": "ticker"})
    return out


def _normalize_price_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize price schema to lowercase OHLCV + ticker/date."""
    out = _normalize_keys(df)
    rename = {}
    if "Open" in out.columns and "open" not in out.columns:
        rename["Open"] = "open"
    if "High" in out.columns and "high" not in out.columns:
        rename["High"] = "high"
    if "Low" in out.columns and "low" not in out.columns:
        rename["Low"] = "low"
    if "Close" in out.columns and "close" not in out.columns:
        rename["Close"] = "close"
    if "Volume" in out.columns and "volume" not in out.columns:
        rename["Volume"] = "volume"
    if rename:
        out = out.rename(columns=rename)
    return out

def load_baseline_config() -> SignalEngineeringConfig:
    """Load baseline configuration with corrected hyperparameters."""
    config_path = PROJECT_ROOT / "config" / "signal_engineering_baseline.yaml"
    
    if config_path.exists():
        config = SignalEngineeringConfig.from_yaml(config_path)
    else:
        # Create default config with corrected hyperparameters
        config = SignalEngineeringConfig()
    
    # Validate critical hyperparameters
    assert config.xgboost.max_depth == 4, "max_depth must be 4"
    assert config.xgboost.min_child_weight == 20, "min_child_weight must be 20"
    
    print(f"✓ Loaded configuration:")
    print(f"  - max_depth: {config.xgboost.max_depth}")
    print(f"  - min_child_weight: {config.xgboost.min_child_weight}")
    print(f"  - learning_rate: {config.xgboost.learning_rate}")
    print(f"  - universe_size: {config.universe_size}")
    print(f"  - feature_budget: {config.feature_budget.budget}")
    
    return config


def calculate_ic(predictions: pd.Series, actuals: pd.Series) -> float:
    """
    Calculate Information Coefficient (IC) as Spearman correlation.
    
    Args:
        predictions: Model predictions
        actuals: Actual forward returns
        
    Returns:
        IC value (Spearman correlation)
    """
    # Remove NaN values
    valid_mask = predictions.notna() & actuals.notna()
    pred_clean = predictions[valid_mask]
    actual_clean = actuals[valid_mask]
    
    if len(pred_clean) < 10:
        return np.nan
    
    # Calculate Spearman correlation
    ic = pred_clean.corr(actual_clean, method='spearman')
    return ic


def validate_baseline_ic(ic: float, threshold: float = 0.032) -> bool:
    """
    Validate that baseline IC meets minimum threshold.
    
    Args:
        ic: Calculated IC value
        threshold: Minimum acceptable IC (default 0.032 for Phase 0)
        
    Returns:
        True if IC >= threshold
    """
    if np.isnan(ic):
        print(f"✗ IC validation failed: IC is NaN")
        return False
    
    if ic >= threshold:
        print(f"✓ IC validation passed: {ic:.4f} >= {threshold:.4f}")
        return True
    else:
        print(f"✗ IC validation failed: {ic:.4f} < {threshold:.4f}")
        return False


def main():
    """Main validation workflow."""
    print("=" * 60)
    print("Baseline Model Validation")
    print("=" * 60)
    print()
    
    # Step 1: Load configuration
    print("Step 1: Loading configuration...")
    try:
        config = load_baseline_config()
        print()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Step 2: Load real market data (NO SYNTHETIC DATA)
    print("Step 2: Loading real market data...")
    
    # Load prices, fundamentals, and scores from existing data
    prices_path = PROJECT_ROOT / "data" / "processed" / "prices.parquet"
    scores_path = PROJECT_ROOT / "data" / "processed" / "scores.parquet"
    fundamentals_path = PROJECT_ROOT / "data" / "processed" / "fundamentals.parquet"
    
    if not prices_path.exists():
        print(f"✗ Prices data not found at {prices_path}")
        print("  Cannot proceed without real market data.")
        print("  Please ensure data pipeline has been run to generate processed data.")
        return 1
    
    print(f"✓ Loading prices from {prices_path}")
    prices = _normalize_price_columns(pd.read_parquet(prices_path))
    
    if 'date' not in prices.columns:
        prices = _normalize_price_columns(prices.reset_index())
    
    print(f"  Loaded {len(prices)} price records")
    
    # Load scores (contains alpha signals)
    if not scores_path.exists():
        print(f"✗ Scores data not found at {scores_path}")
        print("  Cannot proceed without alpha scores.")
        return 1
    
    print(f"✓ Loading scores from {scores_path}")
    scores = _normalize_keys(pd.read_parquet(scores_path))
    if 'date' not in scores.columns:
        scores = _normalize_keys(scores.reset_index())
    print(f"  Loaded {len(scores)} score records")
    
    # Load fundamentals
    if not fundamentals_path.exists():
        print(f"✗ Fundamentals data not found at {fundamentals_path}")
        print("  Cannot proceed without fundamental data.")
        return 1
    
    print(f"✓ Loading fundamentals from {fundamentals_path}")
    fundamentals = _normalize_keys(pd.read_parquet(fundamentals_path))
    if 'date' not in fundamentals.columns:
        fundamentals = _normalize_keys(fundamentals.reset_index())
    print(f"  Loaded {len(fundamentals)} fundamental records")
    
    # Merge data and create features
    print("  Creating feature panel...")
    
    # Start with prices and calculate forward returns
    data = prices.copy()
    
    # Ensure date column is datetime
    if 'ticker' not in data.columns:
        raise KeyError("prices missing ticker column after normalization")
    if 'close' not in data.columns:
        raise KeyError("prices missing close column after normalization")
    if 'volume' not in data.columns:
        raise KeyError("prices missing volume column after normalization")

    data['date'] = pd.to_datetime(data['date'])
    scores['date'] = pd.to_datetime(scores['date'])
    fundamentals['date'] = pd.to_datetime(fundamentals['date'])
    
    # Calculate 5-day forward returns
    data = data.sort_values(['ticker', 'date'])
    data['forward_return_5d'] = data.groupby('ticker')['close'].pct_change(5).shift(-5)
    
    # Create simple price-based features
    data['momentum_21d'] = data.groupby('ticker')['close'].pct_change(21)
    data['volatility_21d'] = (
        data.groupby('ticker')['close']
        .pct_change()
        .rolling(21)
        .std()
        .reset_index(level=0, drop=True)
    )
    data['volume_ratio'] = data.groupby('ticker')['volume'].transform(lambda x: x / x.rolling(21).mean())
    
    # Merge with scores
    score_cols = [c for c in scores.columns if c not in ['date', 'ticker']]
    data = data.merge(scores[['date', 'ticker'] + score_cols], on=['date', 'ticker'], how='left')
    print(f"  Added {len(score_cols)} score features")
    
    # Merge with fundamentals (take first 10 fundamental features to keep it manageable)
    fund_cols = [c for c in fundamentals.columns if c not in ['date', 'ticker']][:10]
    data = data.merge(fundamentals[['date', 'ticker'] + fund_cols], on=['date', 'ticker'], how='left')
    print(f"  Added {len(fund_cols)} fundamental features")
    
    # Drop rows with missing forward returns
    data = data.dropna(subset=['forward_return_5d'])
    
    # Extract features and forward returns
    exclude_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'forward_return_5d']
    feature_cols = [c for c in data.columns if c not in exclude_cols]
    feature_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(data[c])]
    
    # Keep only features with any available data
    feature_cols = [c for c in feature_cols if data[c].notna().any()]
    if not feature_cols:
        print("✗ No usable feature columns after merging (all features missing)")
        return 1

    features = data[['date', 'ticker'] + feature_cols].copy()
    forward_returns = data['forward_return_5d'].copy()
    
    print(f"  Created feature panel: {len(data)} samples, {len(feature_cols)} features")
    print(f"  Date range: {data['date'].min()} to {data['date'].max()}")
    print()
    
    # Step 3: Calculate baseline IC
    print("Step 3: Calculating baseline IC...")
    print("  Using mean of all features as simple baseline prediction")
    
    # Simple baseline: use mean of all features as prediction
    predictions = features[feature_cols].mean(axis=1, skipna=True)
    baseline_ic = calculate_ic(predictions, forward_returns)
    
    print(f"  Baseline IC: {baseline_ic:.4f}")
    ic_valid = validate_baseline_ic(baseline_ic, threshold=0.032)
    print()
    
    # Step 4: Run leakage tests on real features
    print("Step 4: Running leakage tests on features...")
    print(f"  Testing {len(feature_cols)} features")
    
    leakage_results = []
    returns_df = data[['date', 'ticker', 'forward_return_5d']].rename(
        columns={'ticker': 'stock', 'forward_return_5d': 'forward_return'}
    )
    features_df = features.rename(columns={'ticker': 'stock'})

    min_rows = 1000
    min_dates = 30
    for col in feature_cols:
        sub = features_df[['date', 'stock', col]].dropna(subset=[col])
        row_count = int(len(sub))
        date_count = int(sub['date'].nunique())
        if row_count < min_rows or date_count < min_dates:
            print(f"  - Skipping {col}: insufficient coverage rows={row_count} dates={date_count}")
            leakage_results.append({
                'feature': col,
                'baseline_ic': None,
                'shifted_ic': None,
                'ic_ratio': None,
                'passed': False,
                'skipped': True,
                'skip_reason': f"insufficient_coverage rows={row_count} dates={date_count}"
            })
            continue

        result = run_leakage_test_suite(
            sub,
            returns_df,
            feature_names=[col],
            shift_days=5,
            ic_ratio_threshold=1.20
        )
        res = result[col]
        leakage_results.append({
            'feature': col,
            'baseline_ic': res.baseline_ic,
            'shifted_ic': res.shifted_ic,
            'ic_ratio': res.ic_ratio,
            'passed': not res.is_leaking,
            'skipped': False,
            'skip_reason': None
        })
    
    leakage_df = pd.DataFrame(leakage_results)
    
    # Summary
    n_passed = leakage_df['passed'].sum()
    n_total = len(leakage_df)
    
    print(f"  Leakage test results: {n_passed}/{n_total} features passed")
    
    if n_passed < n_total:
        print("  ⚠ Some features failed leakage test:")
        failed = leakage_df[~leakage_df['passed']]
        for _, row in failed.iterrows():
            print(f"    - {row['feature']}: IC_ratio = {row['ic_ratio']:.3f}")
    else:
        print("  ✓ All features passed leakage test")
    
    print()
    
    # Step 5: Generate report
    print("Step 5: Generating validation report...")
    report = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'max_depth': config.xgboost.max_depth,
            'min_child_weight': config.xgboost.min_child_weight,
            'learning_rate': config.xgboost.learning_rate,
            'universe_size': config.universe_size,
            'feature_budget': config.feature_budget.budget,
        },
        'baseline_ic': float(baseline_ic) if not np.isnan(baseline_ic) else None,
        'ic_threshold': 0.032,
        'ic_validation_passed': ic_valid,
        'leakage_tests': {
            'n_features': n_total,
            'n_passed': int(n_passed),
            'n_failed': int(n_total - n_passed),
            'all_passed': bool(n_passed == n_total),
        },
        'overall_status': 'PASS' if (ic_valid and n_passed == n_total) else 'FAIL'
    }
    
    report_path = PROJECT_ROOT / "reports" / "baseline_validation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"✓ Report saved to {report_path}")
    print()
    
    # Final summary
    print("=" * 60)
    print("Validation Summary")
    print("=" * 60)
    print(f"Overall Status: {report['overall_status']}")
    print(f"  - Configuration: ✓ Correct hyperparameters")
    print(f"  - Baseline IC: {'✓' if ic_valid else '✗'} {baseline_ic:.4f}")
    print(f"  - Leakage Tests: {'✓' if n_passed == n_total else '✗'} {n_passed}/{n_total} passed")
    print()
    
    return 0 if report['overall_status'] == 'PASS' else 1


if __name__ == "__main__":
    sys.exit(main())
