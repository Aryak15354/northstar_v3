#!/usr/bin/env python3
"""
🧬 FULL BETA DRIFT FABRIC - PHASE 6: ENHANCEMENT LAYER
Complete beta drift fabric with 52-week rolling betas and significance testing

This implements the full beta drift fabric requirements for Phase 6 (Enhancement)
of the institutional validation framework. It computes 52-week rolling betas for
all stock-macro pairs and detects significant drift (>1.5 std dev).

CRITICAL PRINCIPLE: Full Market Structure Detection
- Compute 52-week rolling betas for all stock-macro pairs
- Detect significant drift (>1.5 std dev from historical mean)
- Store weekly fabric files with complete market structure
- Integrate with tailwind engine for anticipatory allocation
- Provide comprehensive beta drift monitoring

Usage:
    from src.validation.beta_drift_fabric_full import FullBetaDriftFabric
    
    fabric = FullBetaDriftFabric()
    fabric.build_full_fabric_for_year(2024)
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import warnings
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

# Import existing components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.intelligence.market_brain.beta_drift_fabric import BetaDriftFabric
except ImportError:
    # Fallback: create minimal base class if import fails
    class BetaDriftFabric:
        def __init__(self):
            self.config = {
                'n_macro_factors': 12,
                'rolling_window': 26,
                'min_observations': 20,
                'drift_threshold': 0.01,
                'confidence_threshold': 0.1,
                'max_stocks_per_week': 100
            }
            
        def load_market_tensor(self):
            return pd.DataFrame()
            
        def extract_macro_factors(self, tensor):
            return pd.DataFrame(), pd.DataFrame(), np.array([])
            
        def get_available_years(self):
            return [2023, 2024]


@dataclass
class BetaDriftSignificance:
    """
    Beta drift significance record for tracking significant changes
    
    Complete significance information with statistical testing.
    """
    date: datetime
    stock: str
    factor: str
    beta_current: float
    beta_52w_mean: float
    beta_52w_std: float
    drift_magnitude: float
    drift_zscore: float
    is_significant: bool  # >1.5 std dev
    confidence_level: float  # Statistical confidence
    observations: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['date'] = result['date'].isoformat()
        return result
    
    def validate(self) -> List[str]:
        """Validate significance record"""
        errors = []
        
        if not isinstance(self.beta_current, (int, float)):
            errors.append("Beta current must be numeric")
        
        if not isinstance(self.drift_zscore, (int, float)):
            errors.append("Drift z-score must be numeric")
        
        if self.observations < 10:
            errors.append("Insufficient observations for significance testing")
        
        if not (0.0 <= self.confidence_level <= 1.0):
            errors.append("Confidence level must be between 0.0 and 1.0")
        
        return errors


class FullBetaDriftFabric(BetaDriftFabric):
    """
    Full Beta Drift Fabric - Phase 6: Enhancement Layer
    
    Extends the base beta drift fabric with full 52-week rolling analysis
    and statistical significance testing for institutional validation.
    
    ENFORCES REQUIREMENTS:
    - 8.1-8.6: Full beta drift fabric with 52-week rolling betas
    
    V3 INTEGRATION:
    - Extends existing BetaDriftFabric (Requirement 14.1)
    - Integrates with tailwind engine (Requirement 14.6)
    - Provides comprehensive market structure monitoring
    """
    
    def __init__(self, base_dir: str = "data/validation"):
        """
        Initialize Full Beta Drift Fabric
        
        Args:
            base_dir: Base directory for fabric data
        """
        super().__init__()
        
        self.base_dir = base_dir
        self.fabric_dir = os.path.join(base_dir, "beta_drift_fabric")
        
        # Create directories
        os.makedirs(self.fabric_dir, exist_ok=True)
        
        # Enhanced configuration for full fabric
        self.full_config = {
            'rolling_window_weeks': 52,  # Full year of data
            'significance_threshold': 1.5,  # Standard deviations for significance
            'min_historical_weeks': 26,  # Minimum history for significance testing
            'confidence_level': 0.95,  # Statistical confidence level
            'max_stocks_full': 500,  # Process more stocks in full version
            'fabric_update_frequency': 'weekly',  # Update frequency
            'store_all_betas': True,  # Store complete beta history
            'compute_correlations': True,  # Compute factor correlations
        }
        
        # Update base config
        self.config.update(self.full_config)
        
        print("🧬 Full Beta Drift Fabric initialized")
        print(f"   Output: {self.fabric_dir}/")
        print(f"   Rolling window: {self.config['rolling_window_weeks']} weeks")
        print(f"   Significance threshold: {self.config['significance_threshold']} std dev")
        print(f"   Max stocks: {self.config['max_stocks_full']}")
    
    def compute_52week_rolling_betas(self, factors_df: pd.DataFrame, 
                                   stock_returns: pd.DataFrame, 
                                   year: int) -> pd.DataFrame:
        """
        Compute 52-week rolling betas for all stock-macro pairs
        
        VALIDATES REQUIREMENTS 8.1, 8.2
        
        Args:
            factors_df: Macro factors DataFrame
            stock_returns: Stock returns DataFrame
            year: Year to process
            
        Returns:
            DataFrame with 52-week rolling betas
        """
        
        print(f"📈 Computing 52-week rolling betas for {year}...")
        
        # Filter data for the specific year
        year_mask = factors_df.index.year == year
        year_factors = factors_df[year_mask]
        year_stocks = stock_returns[year_mask]
        
        if len(year_factors) < self.config['rolling_window_weeks']:
            print(f"⚠️ Insufficient data for {year}: {len(year_factors)} weeks (need {self.config['rolling_window_weeks']})")
            return pd.DataFrame()
        
        # Limit stocks for performance
        max_stocks = min(len(year_stocks.columns), self.config['max_stocks_full'])
        selected_stocks = year_stocks.columns[:max_stocks]
        year_stocks = year_stocks[selected_stocks]
        
        print(f"   📊 Processing {len(year_factors)} weeks, {len(selected_stocks)} stocks, {len(year_factors.columns)} factors")
        
        beta_records = []
        window_size = self.config['rolling_window_weeks']
        
        # Process each week with 52-week rolling window
        for week_idx in range(window_size, len(year_factors)):
            week_date = year_factors.index[week_idx]
            week_num = week_date.isocalendar()[1]
            
            # Progress tracking
            weeks_completed = week_idx - window_size
            total_weeks = len(year_factors) - window_size
            progress_pct = (weeks_completed / total_weeks) * 100
            
            print(f"   📅 Week {week_num:2d} ({week_date.date()}) | Progress: {progress_pct:5.1f}%")
            
            # Get 52-week rolling window
            start_idx = week_idx - window_size + 1
            end_idx = week_idx + 1
            
            window_factors = year_factors.iloc[start_idx:end_idx]
            window_stocks = year_stocks.iloc[start_idx:end_idx]
            
            # Compute betas for each stock-factor pair
            for stock in selected_stocks:
                stock_returns_window = window_stocks[stock].values
                
                # Skip if insufficient data
                if np.isnan(stock_returns_window).sum() > window_size * 0.2:  # Allow 20% missing
                    continue
                
                for factor in year_factors.columns:
                    factor_values = window_factors[factor].values
                    
                    try:
                        # Linear regression: stock_return = alpha + beta * factor
                        X = factor_values.reshape(-1, 1)
                        y = stock_returns_window
                        
                        # Remove NaN values
                        valid_mask = ~(np.isnan(X.flatten()) | np.isnan(y))
                        if valid_mask.sum() < self.config['min_observations']:
                            continue
                        
                        X_clean = X[valid_mask]
                        y_clean = y[valid_mask]
                        
                        # Fit regression
                        reg = LinearRegression()
                        reg.fit(X_clean, y_clean)
                        
                        # Calculate statistics
                        r2 = reg.score(X_clean, y_clean)
                        
                        # Calculate standard error and t-statistic
                        y_pred = reg.predict(X_clean)
                        residuals = y_clean - y_pred
                        mse = np.mean(residuals**2)
                        
                        # Standard error of beta coefficient
                        x_centered = X_clean - np.mean(X_clean)
                        se_beta = np.sqrt(mse / np.sum(x_centered**2))
                        
                        # t-statistic for beta
                        t_stat = reg.coef_[0] / se_beta if se_beta > 0 else 0
                        
                        # p-value (two-tailed test)
                        df = len(X_clean) - 2
                        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df)) if df > 0 else 1.0
                        
                        if r2 >= self.config['confidence_threshold']:
                            beta_record = {
                                'date': week_date,
                                'year': year,
                                'week': week_num,
                                'stock': stock,
                                'factor': factor,
                                'beta': float(reg.coef_[0]),
                                'alpha': float(reg.intercept_),
                                'r_squared': float(r2),
                                'standard_error': float(se_beta),
                                't_statistic': float(t_stat),
                                'p_value': float(p_value),
                                'observations': int(valid_mask.sum()),
                                'window_weeks': window_size
                            }
                            beta_records.append(beta_record)
                    
                    except Exception as e:
                        continue
        
        if beta_records:
            betas_df = pd.DataFrame(beta_records)
            print(f"   ✅ Computed {len(beta_records):,} 52-week beta relationships")
            return betas_df
        else:
            print(f"   ⚠️ No valid 52-week beta relationships found")
            return pd.DataFrame()
    
    def detect_significant_drift(self, betas_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect significant beta drift (>1.5 std dev from historical mean)
        
        VALIDATES REQUIREMENTS 8.2, 8.3
        
        Args:
            betas_df: DataFrame with rolling betas
            
        Returns:
            DataFrame with significant drift records
        """
        
        print("🔍 Detecting significant beta drift (>1.5 std dev)...")
        
        if betas_df.empty:
            return pd.DataFrame()
        
        significance_records = []
        total_pairs = 0
        significant_pairs = 0
        
        # Group by stock-factor pairs
        for (stock, factor), group in betas_df.groupby(['stock', 'factor']):
            total_pairs += 1
            
            if len(group) < self.config['min_historical_weeks']:
                continue
            
            # Sort by date
            group_sorted = group.sort_values('date')
            
            # Calculate rolling statistics for significance testing
            for i in range(self.config['min_historical_weeks'], len(group_sorted)):
                current_row = group_sorted.iloc[i]
                historical_data = group_sorted.iloc[:i]
                
                # Calculate historical mean and std
                historical_betas = historical_data['beta'].values
                beta_mean = np.mean(historical_betas)
                beta_std = np.std(historical_betas)
                
                if beta_std == 0:
                    continue
                
                # Calculate z-score for current beta
                current_beta = current_row['beta']
                z_score = abs(current_beta - beta_mean) / beta_std
                
                # Check if drift is significant
                is_significant = z_score > self.config['significance_threshold']
                
                if is_significant:
                    significant_pairs += 1
                    
                    # Calculate confidence level based on z-score
                    confidence = 2 * (1 - stats.norm.cdf(z_score))  # Two-tailed p-value
                    confidence_level = 1 - confidence
                    
                    significance_record = BetaDriftSignificance(
                        date=current_row['date'],
                        stock=stock,
                        factor=factor,
                        beta_current=float(current_beta),
                        beta_52w_mean=float(beta_mean),
                        beta_52w_std=float(beta_std),
                        drift_magnitude=float(abs(current_beta - beta_mean)),
                        drift_zscore=float(z_score),
                        is_significant=True,
                        confidence_level=float(confidence_level),
                        observations=len(historical_betas)
                    )
                    
                    # Validate record
                    validation_errors = significance_record.validate()
                    if not validation_errors:
                        significance_records.append(significance_record.to_dict())
        
        print(f"   📊 Total stock-factor pairs: {total_pairs}")
        print(f"   🔍 Significant drift pairs: {significant_pairs}")
        print(f"   📈 Significance threshold: {self.config['significance_threshold']} std dev")
        
        if significance_records:
            significance_df = pd.DataFrame(significance_records)
            print(f"   ✅ Detected {len(significance_records)} significant beta drifts")
            
            # Show statistics
            print(f"   📊 Z-score range: {significance_df['drift_zscore'].min():.2f} to {significance_df['drift_zscore'].max():.2f}")
            print(f"   📊 Average confidence: {significance_df['confidence_level'].mean():.3f}")
            
            return significance_df
        else:
            print("   ⚠️ No significant beta drifts detected")
            return pd.DataFrame()
    
    def store_weekly_fabric_files(self, betas_df: pd.DataFrame, 
                                 significance_df: pd.DataFrame, 
                                 year: int) -> bool:
        """
        Store weekly fabric files with complete beta information
        
        VALIDATES REQUIREMENTS 8.4, 8.5
        
        Args:
            betas_df: Complete beta relationships
            significance_df: Significant drift records
            year: Year being processed
            
        Returns:
            Success status
        """
        
        print(f"💾 Storing weekly fabric files for {year}...")
        
        # Create year directory
        year_dir = os.path.join(self.fabric_dir, str(year))
        os.makedirs(year_dir, exist_ok=True)
        
        try:
            # Store complete beta fabric
            fabric_file = os.path.join(year_dir, f"beta_fabric_{year}.parquet")
            betas_df.to_parquet(fabric_file, index=False)
            
            # Store significant drifts
            if not significance_df.empty:
                significance_file = os.path.join(year_dir, f"significant_drifts_{year}.parquet")
                significance_df.to_parquet(significance_file, index=False)
            
            # Store weekly files for integration
            unique_weeks = sorted(betas_df['week'].unique())
            
            for week in unique_weeks:
                week_betas = betas_df[betas_df['week'] == week]
                week_significance = significance_df[significance_df['date'].dt.isocalendar().week == week] if not significance_df.empty else pd.DataFrame()
                
                # Create weekly fabric record
                weekly_fabric = {
                    'year': year,
                    'week': week,
                    'total_betas': len(week_betas),
                    'significant_drifts': len(week_significance),
                    'top_drifts': week_significance.nlargest(10, 'drift_zscore').to_dict('records') if not week_significance.empty else [],
                    'factor_summary': week_betas.groupby('factor')['beta'].agg(['mean', 'std', 'count']).to_dict('index'),
                    'created_at': datetime.now().isoformat()
                }
                
                week_file = os.path.join(year_dir, f"week_{week:02d}_fabric.json")
                with open(week_file, 'w') as f:
                    json.dump(weekly_fabric, f, indent=2, default=str)
            
            print(f"   ✅ Stored fabric files: {len(unique_weeks)} weeks")
            print(f"   📁 Complete fabric: {fabric_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error storing fabric files: {e}")
            return False
    
    def integrate_with_tailwind_engine(self, significance_df: pd.DataFrame, year: int) -> Dict[str, Any]:
        """
        Integrate beta drift fabric with tailwind engine
        
        VALIDATES REQUIREMENTS 8.6
        
        Args:
            significance_df: Significant drift records
            year: Year being processed
            
        Returns:
            Integration summary
        """
        
        print(f"🔗 Integrating with tailwind engine for {year}...")
        
        if significance_df.empty:
            return {'status': 'no_significant_drifts', 'year': year}
        
        try:
            # Create tailwind signals from significant drifts
            tailwind_signals = {}
            
            # Group by factor to identify macro themes
            for factor, factor_group in significance_df.groupby('factor'):
                # Calculate factor-level drift intensity
                avg_zscore = factor_group['drift_zscore'].mean()
                max_zscore = factor_group['drift_zscore'].max()
                affected_stocks = len(factor_group['stock'].unique())
                
                # Create tailwind signal
                tailwind_signals[factor] = {
                    'drift_intensity': float(avg_zscore),
                    'max_drift': float(max_zscore),
                    'affected_stocks': affected_stocks,
                    'signal_strength': min(1.0, avg_zscore / 3.0),  # Normalize to 0-1
                    'confidence': float(factor_group['confidence_level'].mean()),
                    'top_stocks': factor_group.nlargest(5, 'drift_zscore')['stock'].tolist()
                }
            
            # Create year directory if it doesn't exist
            year_dir = os.path.join(self.fabric_dir, str(year))
            os.makedirs(year_dir, exist_ok=True)
            
            # Save tailwind integration data
            integration_file = os.path.join(year_dir, f"tailwind_integration_{year}.json")
            integration_data = {
                'year': year,
                'created_at': datetime.now().isoformat(),
                'total_significant_drifts': len(significance_df),
                'factors_with_drift': len(tailwind_signals),
                'tailwind_signals': tailwind_signals,
                'integration_summary': {
                    'strongest_factor': max(tailwind_signals.keys(), key=lambda x: tailwind_signals[x]['drift_intensity']),
                    'most_affected_stocks': sum(s['affected_stocks'] for s in tailwind_signals.values()),
                    'average_signal_strength': np.mean([s['signal_strength'] for s in tailwind_signals.values()])
                }
            }
            
            with open(integration_file, 'w') as f:
                json.dump(integration_data, f, indent=2, default=str)
            
            print(f"   ✅ Tailwind integration complete")
            print(f"   🎯 Factors with drift: {len(tailwind_signals)}")
            print(f"   📈 Strongest factor: {integration_data['integration_summary']['strongest_factor']}")
            
            return integration_data
            
        except Exception as e:
            print(f"❌ Error integrating with tailwind engine: {e}")
            return {'status': 'error', 'error': str(e), 'year': year}
    
    def build_full_fabric_for_year(self, year: int) -> bool:
        """
        Build complete beta drift fabric for a specific year
        
        VALIDATES REQUIREMENTS 8.1-8.6
        
        Args:
            year: Year to process
            
        Returns:
            Success status
        """
        
        print(f"🧬 BUILDING FULL BETA DRIFT FABRIC FOR {year}")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Load market tensor
        print("📊 STEP 1/6: Loading market tensor...")
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            print("❌ Cannot build fabric without market tensor")
            return False
        
        # Extract macro factors and stock returns
        print("🧠 STEP 2/6: Extracting macro factors...")
        factors_df, stock_returns, explained_var = self.extract_macro_factors(tensor)
        
        if factors_df.empty or stock_returns.empty:
            print("❌ Could not extract factors or stock returns")
            return False
        
        # Compute 52-week rolling betas
        print("📈 STEP 3/6: Computing 52-week rolling betas...")
        betas_df = self.compute_52week_rolling_betas(factors_df, stock_returns, year)
        
        if betas_df.empty:
            print("❌ Could not compute 52-week rolling betas")
            return False
        
        # Detect significant drift
        print("🔍 STEP 4/6: Detecting significant drift...")
        significance_df = self.detect_significant_drift(betas_df)
        
        # Store weekly fabric files
        print("💾 STEP 5/6: Storing weekly fabric files...")
        if not self.store_weekly_fabric_files(betas_df, significance_df, year):
            print("❌ Failed to store fabric files")
            return False
        
        # Integrate with tailwind engine
        print("🔗 STEP 6/6: Integrating with tailwind engine...")
        integration_result = self.integrate_with_tailwind_engine(significance_df, year)
        
        # Final summary
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print("=" * 60)
        print(f"✅ FULL BETA DRIFT FABRIC COMPLETE FOR {year}")
        print(f"   📊 Total beta relationships: {len(betas_df):,}")
        print(f"   🔍 Significant drifts: {len(significance_df):,}")
        print(f"   🎯 Factors with drift: {integration_result.get('factors_with_drift', 0)}")
        print(f"   ⏱️  Processing time: {processing_time:.1f} seconds")
        
        return True


def main():
    """Demonstrate Full Beta Drift Fabric"""
    
    print("🧬 FULL BETA DRIFT FABRIC - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize full fabric
    fabric = FullBetaDriftFabric()
    
    # Get available years
    available_years = fabric.get_available_years()
    
    if not available_years:
        print("❌ No years available for processing")
        return False
    
    # Process most recent year as demonstration
    target_year = max(available_years)
    print(f"🎯 Processing {target_year} as demonstration...")
    
    success = fabric.build_full_fabric_for_year(target_year)
    
    if success:
        print(f"\n✅ Full beta drift fabric demonstration complete!")
        print(f"   📁 Output: data/validation/beta_drift_fabric/{target_year}/")
        print(f"   🔗 Integration: Ready for tailwind engine")
    else:
        print("❌ Failed to build full beta drift fabric")
    
    return success


if __name__ == "__main__":
    main()