#!/usr/bin/env python3
"""
Signal Reality Audit - Task 0 (MANDATORY)

This script validates whether your signals contain enough predictive power
to justify building the probabilistic forecasting spine.

DO NOT BUILD INFRASTRUCTURE UNTIL THIS PASSES VALIDATION.

Decision Rules:
- Mean IC < 0.015 → STOP, redesign signals
- Mean IC 0.015-0.025 → Build minimal ridge only
- Mean IC > 0.025 & stable → Proceed with full spine
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
DATA_DIR = Path("data/market")  # Adjust to your data location
OUTPUT_DIR = Path("reports/signal_audit")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Validation thresholds
THRESHOLD_STOP_IC = 0.015
THRESHOLD_MINIMAL_IC = 0.025
THRESHOLD_STABILITY_RATIO = 0.5
CRISIS_PERIODS = [
    ("2008-09-15", "2009-03-09", "2008 Financial Crisis"),
    ("2020-02-20", "2020-04-07", "2020 COVID Crash"),
]


class SignalAuditor:
    """Minimal signal audit - no models, just raw predictive power."""
    
    def __init__(self, data: pd.DataFrame):
        """
        Args:
            data: DataFrame with columns [date, asset_id, price, volume, ...]
        """
        self.data = data
        self.results = {}
        
    def compute_forward_returns(self, horizon: int = 10) -> pd.DataFrame:
        """Compute forward returns for each asset."""
        df = self.data.copy()
        df = df.sort_values(['asset_id', 'date'])
        
        # Compute log returns
        df['return'] = df.groupby('asset_id')['price'].transform(
            lambda x: np.log(x / x.shift(1))
        )
        
        # Compute forward h-day return
        df[f'forward_return_{horizon}d'] = df.groupby('asset_id')['return'].transform(
            lambda x: x.rolling(horizon).sum().shift(-horizon)
        )
        
        # Compute universe mean return (cross-sectional)
        df['universe_mean_return'] = df.groupby('date')[f'forward_return_{horizon}d'].transform('mean')
        
        # Compute excess return (this is the target)
        df['excess_return'] = df[f'forward_return_{horizon}d'] - df['universe_mean_return']
        
        return df
    
    def compute_signal_zscore(self, df: pd.DataFrame, signal_col: str) -> pd.DataFrame:
        """Compute cross-sectional z-score for signal."""
        df[f'{signal_col}_zscore'] = df.groupby('date')[signal_col].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )
        return df
    
    def compute_ic(self, df: pd.DataFrame, signal_col: str, target_col: str = 'excess_return') -> pd.Series:
        """Compute Information Coefficient (cross-sectional correlation)."""
        valid = df[['date', signal_col, target_col]].dropna(subset=[signal_col, target_col])
        ic_series = valid.groupby('date')[[signal_col, target_col]].apply(
            lambda g: self._safe_corr(g[signal_col], g[target_col])
        )
        return ic_series.dropna()

    @staticmethod
    def _safe_corr(x: pd.Series, y: pd.Series) -> float:
        """Numerically stable correlation that avoids divide-by-zero warnings."""
        x_vals = x.to_numpy(dtype=float)
        y_vals = y.to_numpy(dtype=float)
        if len(x_vals) < 3:
            return np.nan

        x_centered = x_vals - np.nanmean(x_vals)
        y_centered = y_vals - np.nanmean(y_vals)
        denom = np.sqrt(np.nansum(x_centered ** 2) * np.nansum(y_centered ** 2))
        if not np.isfinite(denom) or denom <= 1e-12:
            return np.nan

        corr = np.nansum(x_centered * y_centered) / denom
        if not np.isfinite(corr):
            return np.nan
        return float(corr)
    
    def compute_rolling_ic(self, df: pd.DataFrame, signal_col: str, window: int = 252) -> pd.Series:
        """Compute rolling IC."""
        ic_series = self.compute_ic(df, signal_col)
        rolling_ic = ic_series.rolling(window).mean()
        return rolling_ic
    
    def compute_regime_conditional_ic(self, df: pd.DataFrame, signal_col: str) -> Dict[str, float]:
        """Compute IC by market regime."""
        # Simple regime definition: volatility-based
        df['market_vol'] = df.groupby('date')['return'].transform('std')
        df['regime'] = pd.qcut(df['market_vol'], q=3, labels=['low_vol', 'medium_vol', 'high_vol'])
        
        regime_ic = {}
        for regime in ['low_vol', 'medium_vol', 'high_vol']:
            regime_data = df[df['regime'] == regime]
            ic_series = self.compute_ic(regime_data, signal_col)
            regime_ic[regime] = ic_series.mean()
        
        return regime_ic
    
    def compute_crisis_ic(self, df: pd.DataFrame, signal_col: str) -> Dict[str, float]:
        """Compute IC during crisis periods."""
        crisis_ic = {}
        
        for start, end, name in CRISIS_PERIODS:
            crisis_data = df[(df['date'] >= start) & (df['date'] <= end)]
            if len(crisis_data) > 0:
                ic_series = self.compute_ic(crisis_data, signal_col)
                crisis_ic[name] = ic_series.mean()
            else:
                crisis_ic[name] = np.nan
        
        return crisis_ic
    
    def compute_ic_decay(self, df: pd.DataFrame, signal_col: str, horizons: List[int] = [5, 10, 20, 60]) -> Dict[int, float]:
        """Compute IC at multiple horizons."""
        ic_decay = {}
        
        for horizon in horizons:
            # Recompute forward returns for this horizon
            df_h = self.compute_forward_returns(horizon)
            df_h = self.compute_signal_zscore(df_h, signal_col)
            ic_series = self.compute_ic(df_h, f'{signal_col}_zscore')
            ic_decay[horizon] = ic_series.mean()
        
        return ic_decay
    
    def compute_decile_portfolio_sharpe(self, df: pd.DataFrame, signal_col: str) -> float:
        """Compute long-short decile portfolio Sharpe ratio."""
        # Rank assets by signal into deciles
        df['signal_decile'] = df.groupby('date')[signal_col].transform(
            lambda x: pd.qcut(x, q=10, labels=False, duplicates='drop')
        )
        
        # Long top decile, short bottom decile
        long_returns = df[df['signal_decile'] == 9].groupby('date')['excess_return'].mean()
        short_returns = df[df['signal_decile'] == 0].groupby('date')['excess_return'].mean()
        
        portfolio_returns = long_returns - short_returns
        sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)
        
        return sharpe
    
    def audit_signal(self, signal_col: str, horizon: int = 10) -> Dict:
        """Run complete audit for a single signal."""
        print(f"\n{'='*60}")
        print(f"Auditing signal: {signal_col}")
        print(f"{'='*60}")
        
        # Compute forward returns
        df = self.compute_forward_returns(horizon)
        
        # Compute signal z-score
        df = self.compute_signal_zscore(df, signal_col)
        signal_zscore_col = f'{signal_col}_zscore'
        
        # 1. Rolling IC
        ic_series = self.compute_ic(df, signal_zscore_col)
        mean_ic = ic_series.mean()
        std_ic = ic_series.std()
        pct_positive = (ic_series > 0).mean() * 100
        
        print(f"\n1. Rolling IC Statistics:")
        print(f"   Mean IC: {mean_ic:.4f}")
        print(f"   Std IC: {std_ic:.4f}")
        print(f"   % Positive Months: {pct_positive:.1f}%")
        print(f"   Stability Ratio: {mean_ic / std_ic:.2f}")
        
        # 2. Regime-conditional IC
        regime_ic = self.compute_regime_conditional_ic(df, signal_zscore_col)
        print(f"\n2. Regime-Conditional IC:")
        for regime, ic in regime_ic.items():
            print(f"   {regime}: {ic:.4f}")
        
        # 3. Crisis IC
        crisis_ic = self.compute_crisis_ic(df, signal_zscore_col)
        print(f"\n3. Crisis-Period IC:")
        for crisis, ic in crisis_ic.items():
            if not np.isnan(ic):
                print(f"   {crisis}: {ic:.4f}")
        
        # 4. IC Decay
        ic_decay = self.compute_ic_decay(df, signal_col)
        print(f"\n4. IC Decay Curve:")
        for horizon, ic in ic_decay.items():
            print(f"   {horizon}-day: {ic:.4f}")
        
        # 5. Decile Portfolio Sharpe
        sharpe = self.compute_decile_portfolio_sharpe(df, signal_zscore_col)
        print(f"\n5. Long-Short Decile Sharpe: {sharpe:.2f}")
        
        # Store results
        results = {
            'signal': signal_col,
            'mean_ic': mean_ic,
            'std_ic': std_ic,
            'pct_positive_months': pct_positive,
            'stability_ratio': mean_ic / std_ic if std_ic > 0 else 0,
            'regime_ic': regime_ic,
            'crisis_ic': crisis_ic,
            'ic_decay': ic_decay,
            'decile_sharpe': sharpe,
            'ic_time_series': ic_series.to_dict(),
        }
        
        return results
    
    def apply_decision_rules(self, results: Dict) -> Tuple[str, str]:
        """Apply validation rules and return decision."""
        mean_ic = results['mean_ic']
        stability_ratio = results['stability_ratio']
        crisis_ic_values = [v for v in results['crisis_ic'].values() if not np.isnan(v)]
        crisis_ic_flips = any(v < 0 for v in crisis_ic_values) if crisis_ic_values else False
        
        print(f"\n{'='*60}")
        print("DECISION CHECKPOINT")
        print(f"{'='*60}")
        
        # Decision logic
        if mean_ic < THRESHOLD_STOP_IC:
            decision = "STOP"
            reason = f"Mean IC ({mean_ic:.4f}) < {THRESHOLD_STOP_IC}. Signal too weak. REDESIGN SIGNALS."
        elif stability_ratio < THRESHOLD_STABILITY_RATIO:
            decision = "STOP"
            reason = f"Stability ratio ({stability_ratio:.2f}) < {THRESHOLD_STABILITY_RATIO}. Signal too unstable."
        elif crisis_ic_flips and mean_ic < 0.03:
            decision = "STOP"
            reason = "Signal flips sign during crisis and IC not strong enough to justify regime modeling."
        elif mean_ic < THRESHOLD_MINIMAL_IC:
            decision = "PROCEED_MINIMAL"
            reason = f"Mean IC ({mean_ic:.4f}) in range [0.015, 0.025]. Build MINIMAL ridge only. Skip Bayesian."
        elif crisis_ic_flips and mean_ic >= 0.03:
            decision = "PROCEED_WITH_REGIME"
            reason = f"Mean IC ({mean_ic:.4f}) > 0.03 but flips in crisis. Add regime modeling."
        else:
            decision = "PROCEED_FULL"
            reason = f"Mean IC ({mean_ic:.4f}) > {THRESHOLD_MINIMAL_IC} and stable. Proceed with full spine."
        
        print(f"\nDECISION: {decision}")
        print(f"REASON: {reason}")
        print(f"{'='*60}\n")
        
        return decision, reason
    
    def generate_report(self, all_results: List[Dict], output_path: Path):
        """Generate comprehensive audit report."""
        report = {
            'audit_date': datetime.now().isoformat(),
            'signals_audited': len(all_results),
            'signals': all_results,
            'summary': {
                'mean_ic_range': [min(r['mean_ic'] for r in all_results), max(r['mean_ic'] for r in all_results)],
                'best_signal': max(all_results, key=lambda x: x['mean_ic'])['signal'],
                'worst_signal': min(all_results, key=lambda x: x['mean_ic'])['signal'],
            }
        }
        
        # Save JSON report
        with open(output_path / 'signal_audit_report.json', 'w') as f:
            json.dump(self._to_json_safe(report), f, indent=2)
        
        print(f"\nReport saved to: {output_path / 'signal_audit_report.json'}")
        
        # Generate visualizations
        self.plot_ic_time_series(all_results, output_path)
        self.plot_ic_by_regime(all_results, output_path)
        self.plot_ic_decay(all_results, output_path)

    @staticmethod
    def _to_json_safe(obj: Any) -> Any:
        """Recursively convert objects to JSON-safe primitives."""
        if isinstance(obj, dict):
            return {str(k): SignalAuditor._to_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [SignalAuditor._to_json_safe(v) for v in obj]
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if pd.isna(obj):
            return None
        return obj
    
    def plot_ic_time_series(self, all_results: List[Dict], output_path: Path):
        """Plot IC time series for all signals."""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for result in all_results:
            ic_series = pd.Series(result['ic_time_series'])
            ic_series.index = pd.to_datetime(ic_series.index)
            ax.plot(ic_series.rolling(60).mean(), label=result['signal'], alpha=0.7)
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax.axhline(y=THRESHOLD_STOP_IC, color='red', linestyle='--', alpha=0.5, label='Stop Threshold')
        ax.axhline(y=THRESHOLD_MINIMAL_IC, color='green', linestyle='--', alpha=0.5, label='Full Spine Threshold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Rolling 60-day IC')
        ax.set_title('Signal IC Time Series (60-day Rolling)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / 'ic_time_series.png', dpi=150)
        plt.close()
    
    def plot_ic_by_regime(self, all_results: List[Dict], output_path: Path):
        """Plot IC by regime for all signals."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        signals = [r['signal'] for r in all_results]
        regimes = ['low_vol', 'medium_vol', 'high_vol']
        
        x = np.arange(len(signals))
        width = 0.25
        
        for i, regime in enumerate(regimes):
            ic_values = [r['regime_ic'][regime] for r in all_results]
            ax.bar(x + i * width, ic_values, width, label=regime)
        
        ax.set_xlabel('Signal')
        ax.set_ylabel('IC')
        ax.set_title('IC by Market Regime')
        ax.set_xticks(x + width)
        ax.set_xticklabels(signals, rotation=45, ha='right')
        ax.legend()
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(output_path / 'ic_by_regime.png', dpi=150)
        plt.close()
    
    def plot_ic_decay(self, all_results: List[Dict], output_path: Path):
        """Plot IC decay curves for all signals."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for result in all_results:
            horizons = sorted(result['ic_decay'].keys())
            ic_values = [result['ic_decay'][h] for h in horizons]
            ax.plot(horizons, ic_values, marker='o', label=result['signal'])
        
        ax.set_xlabel('Forecast Horizon (days)')
        ax.set_ylabel('IC')
        ax.set_title('IC Decay Curve')
        ax.legend()
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / 'ic_decay.png', dpi=150)
        plt.close()


def load_sample_data() -> pd.DataFrame:
    """
    Load your market data here.
    
    Expected format:
    - date: datetime
    - asset_id: str
    - price: float
    - volume: float
    - [other features for signals]
    
    Returns:
        DataFrame with market data
    """
    print("Loading individual stock CSV files...")
    
    # Load all CSV files from data/raw/prices_daily/
    price_dir = Path("data/raw/prices_daily")
    
    if not price_dir.exists():
        raise FileNotFoundError(f"Price data directory not found: {price_dir}")
    
    all_data = []
    csv_files = list(price_dir.glob("*.csv"))
    
    print(f"Found {len(csv_files)} stock files")
    
    for csv_file in csv_files:
        try:
            # Extract asset_id from filename (e.g., "RELIANCE.NS.csv" -> "RELIANCE.NS")
            asset_id = csv_file.stem
            
            # Load CSV
            df = pd.read_csv(csv_file, parse_dates=['Date'])
            
            # Add asset_id column
            df['asset_id'] = asset_id
            
            # Rename columns to match expected format
            df = df.rename(columns={
                'Date': 'date',
                'Close': 'price',
                'Volume': 'volume',
                'Open': 'open',
                'High': 'high',
                'Low': 'low'
            })
            
            # Select relevant columns
            df = df[['date', 'asset_id', 'price', 'volume', 'open', 'high', 'low']]
            
            # Remove rows with missing prices
            df = df.dropna(subset=['price'])
            
            all_data.append(df)
            
        except Exception as e:
            print(f"Warning: Failed to load {csv_file.name}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data loaded. Check your data directory.")
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Sort by date and asset_id
    combined_df = combined_df.sort_values(['date', 'asset_id']).reset_index(drop=True)
    
    print(f"Loaded {len(combined_df)} rows for {combined_df['asset_id'].nunique()} assets")
    print(f"Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
    
    return combined_df


def compute_candidate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute your top 5 candidate signals.
    
    Args:
        df: Market data DataFrame
    
    Returns:
        DataFrame with signal columns added
    """
    print("Computing candidate signals...")
    
    # Sort by asset and date
    df = df.sort_values(['asset_id', 'date']).copy()
    
    # Compute returns first (needed for signals)
    df['return'] = df.groupby('asset_id')['price'].transform(
        lambda x: np.log(x / x.shift(1))
    )
    
    # 1. MOMENTUM SIGNAL - 1-month (21-day) return
    print("  Computing momentum signal...")
    df['signal_momentum_1m'] = df.groupby('asset_id')['return'].transform(
        lambda x: x.rolling(21, min_periods=10).sum()
    )
    
    # 2. MOMENTUM SIGNAL - 3-month (63-day) return
    print("  Computing momentum_3m signal...")
    df['signal_momentum_3m'] = df.groupby('asset_id')['return'].transform(
        lambda x: x.rolling(63, min_periods=30).sum()
    )
    
    # 3. VOLATILITY SIGNAL - 20-day realized volatility (inverse - low vol anomaly)
    print("  Computing volatility signal...")
    df['signal_low_volatility'] = df.groupby('asset_id')['return'].transform(
        lambda x: -x.rolling(20, min_periods=10).std()  # Negative because low vol is good
    )
    
    # 4. LIQUIDITY SIGNAL - Average volume (higher is more liquid)
    print("  Computing liquidity signal...")
    df['signal_liquidity'] = df.groupby('asset_id')['volume'].transform(
        lambda x: np.log(x.rolling(20, min_periods=10).mean() + 1)
    )
    
    # 5. REVERSAL SIGNAL - Short-term reversal (5-day return, inverted)
    print("  Computing reversal signal...")
    df['signal_reversal_5d'] = df.groupby('asset_id')['return'].transform(
        lambda x: -x.rolling(5, min_periods=3).sum()  # Negative for mean reversion
    )
    
    # Remove rows with NaN signals (warmup period)
    signal_cols = [col for col in df.columns if col.startswith('signal_')]
    df = df.dropna(subset=signal_cols)
    
    print(f"  Computed {len(signal_cols)} signals")
    print(f"  Data after signal computation: {len(df)} rows")
    
    return df


def main():
    """Run signal reality audit."""
    print("="*60)
    print("SIGNAL REALITY AUDIT - TASK 0")
    print("="*60)
    print("\nThis audit validates whether your signals justify building")
    print("the probabilistic forecasting spine infrastructure.")
    print("\nDO NOT PROCEED TO TASK 1 WITHOUT PASSING THIS AUDIT.\n")
    
    # Load data
    print("Loading market data...")
    try:
        df = load_sample_data()
    except NotImplementedError as e:
        print(f"\nERROR: {e}")
        print("\nPlease implement load_sample_data() in this script.")
        return
    
    # Compute signals
    print("Computing candidate signals...")
    df = compute_candidate_signals(df)
    
    # Identify signal columns
    signal_cols = [col for col in df.columns if col.startswith('signal_')]
    
    if len(signal_cols) == 0:
        print("\nERROR: No signals found. Please implement compute_candidate_signals().")
        return
    
    print(f"Found {len(signal_cols)} signals: {signal_cols}")
    
    # Run audit
    auditor = SignalAuditor(df)
    all_results = []
    
    for signal_col in signal_cols:
        try:
            results = auditor.audit_signal(signal_col)
            all_results.append(results)
            
            # Apply decision rules
            decision, reason = auditor.apply_decision_rules(results)
            results['decision'] = decision
            results['decision_reason'] = reason
            
        except Exception as e:
            print(f"\nERROR auditing {signal_col}: {e}")
            continue
    
    # Generate report
    if all_results:
        print("\nGenerating comprehensive report...")
        auditor.generate_report(all_results, OUTPUT_DIR)
        
        # Final summary
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        
        decisions = [r['decision'] for r in all_results]
        if any(d == 'STOP' for d in decisions):
            print("\n⚠️  AT LEAST ONE SIGNAL FAILED VALIDATION")
            print("    DO NOT PROCEED TO TASK 1")
            print("    REDESIGN SIGNALS OR PIVOT TO VOLATILITY FORECASTING")
        elif all(d == 'PROCEED_MINIMAL' for d in decisions):
            print("\n✓  Signals pass minimal threshold")
            print("    Proceed with MINIMAL ridge regression only")
            print("    Skip Bayesian hierarchical models")
        elif any(d == 'PROCEED_FULL' for d in decisions):
            print("\n✓✓ Signals pass full validation")
            print("    Proceed with full probabilistic forecasting spine")
        
        print(f"\nDetailed report: {OUTPUT_DIR / 'signal_audit_report.json'}")
        print(f"Visualizations: {OUTPUT_DIR}/")
    else:
        print("\nERROR: No signals successfully audited.")


if __name__ == "__main__":
    main()
