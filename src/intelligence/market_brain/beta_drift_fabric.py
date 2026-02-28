#!/usr/bin/env python3
"""
🧬 BETA DRIFT FABRIC - NORTHSTAR V3 MARKET BRAIN
The Market Nervous System: Detecting Sensitivity Shifts Before Price Moves

This is the corrected approach that measures:
"Which stocks became sensitive to which macro forces this week?"

Instead of: macro_delta(t) → stock_return(t+4w) [IMPOSSIBLE]
We measure: macro_factor(t) ↔ stock_sensitivity(t) [REAL SIGNAL]

This detects sensitivity shifts that precede price moves by weeks.

Integration with V3:
- Replaces the failed regression approach
- Measures rolling beta drift between stocks and macro factors
- Detects when market structure is rewiring itself
- Provides anticipatory signals for capital allocation
"""

import pandas as pd
import numpy as np
import os
import glob
import json
from datetime import datetime, timedelta
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Import existing V3 components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.intelligence.market_brain.market_tensor import MarketTensorEngine

class BetaDriftFabric:
    """
    Beta Drift Fabric - The Market Nervous System
    
    Detects when stocks become more/less sensitive to macro factors:
    - Builds macro factors from 261 market variables
    - Computes rolling stock betas to each factor
    - Measures beta drift (sensitivity changes)
    - Identifies structural market rewiring
    """
    
    def __init__(self):
        self.name = "Beta Drift Fabric"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'market_tensor': 'data/processed/market_tensor.parquet',
            'beta_drift_insights': 'data/beta_drift_insights',
            'macro_factors': 'data/processed/macro_factors.parquet',
            'stock_betas': 'data/processed/stock_betas.parquet',
            'fabric_metadata': 'data/beta_drift_insights/fabric_metadata.json'
        }
        
        # Configuration
        self.config = {
            'n_macro_factors': 12,          # Number of macro factors to extract
            'rolling_window': 26,           # 6 months of weekly data for beta estimation
            'min_observations': 20,         # Minimum observations for beta calculation
            'drift_threshold': 0.01,        # Minimum beta change to consider significant (reduced from 0.05)
            'novelty_window': 12,           # Weeks to look back for novelty calculation
            'confidence_threshold': 0.1,    # Minimum R² for beta estimation (reduced from 0.3)
            'max_stocks_per_week': 100      # Limit stocks processed per week for performance
        }
        
        # Macro factor interpretations
        self.factor_names = {
            0: 'Liquidity',
            1: 'Inflation', 
            2: 'FX_Pressure',
            3: 'Credit_Stress',
            4: 'Growth',
            5: 'Rates',
            6: 'Risk_Appetite',
            7: 'Monetary_Policy',
            8: 'External_Sector',
            9: 'Banking_Health',
            10: 'Commodity_Pressure',
            11: 'Market_Structure'
        }
    
    def load_market_tensor(self):
        """Load market tensor for beta drift analysis"""
        
        try:
            if os.path.exists(self.paths['market_tensor']):
                tensor = pd.read_parquet(self.paths['market_tensor'])
                tensor = MarketTensorEngine.canonicalize_tensor_frame(tensor)
                
                if tensor.empty:
                    print("⚠️ Market tensor is empty")
                    return pd.DataFrame()
                
                print(f"📊 Loaded market tensor: {tensor.shape}")
                print(f"   Date range: {tensor.index[0].date()} to {tensor.index[-1].date()}")
                return tensor
            else:
                print("⚠️ Market tensor not found, building it first...")
                
                # Build tensor using existing engine
                tensor_engine = MarketTensorEngine()
                tensor = tensor_engine.build_market_tensor()
                
                return tensor
                
        except Exception as e:
            print(f"❌ Error loading market tensor: {e}")
            return pd.DataFrame()
    
    def extract_macro_factors(self, tensor):
        """Extract macro factors from market tensor using PCA and load real stock data"""
        
        try:
            print("🧠 Extracting macro factors from market tensor...")
            
            # Separate macro variables from stock variables
            macro_vars = []
            stock_vars = []
            
            for col in tensor.columns:
                col_lower = col.lower()
                if any(term in col_lower for term in [
                    'rbi_', 'repo', 'rate', 'cpi', 'wpi', 'inflation', 'growth',
                    'usdinr', 'fx', 'currency', 'exchange',
                    'fii', 'dii', 'flow', 'capital',
                    'credit', 'loan', 'deposit', 'banking', 'yield',
                    'liquidity', 'reserve', 'money', 'supply'
                ]):
                    macro_vars.append(col)
                elif 'corp_factor_' in col_lower:
                    stock_vars.append(col)
            
            print(f"   📊 Macro variables: {len(macro_vars)}")
            print(f"   📈 Stock variables in tensor: {len(stock_vars)}")
            
            if len(macro_vars) < self.config['n_macro_factors']:
                print(f"⚠️ Only {len(macro_vars)} macro variables available, reducing factors to {len(macro_vars)}")
                n_factors = len(macro_vars)
            else:
                n_factors = self.config['n_macro_factors']
            
            # Extract macro factors using PCA
            macro_data = tensor[macro_vars].fillna(0)
            
            # Standardize
            scaler = StandardScaler()
            macro_scaled = scaler.fit_transform(macro_data)
            
            # Apply PCA
            pca = PCA(n_components=n_factors)
            macro_factors = pca.fit_transform(macro_scaled)
            
            # Create factor DataFrame
            factor_names = [self.factor_names.get(i, f'Factor_{i}') for i in range(n_factors)]
            factors_df = pd.DataFrame(
                macro_factors,
                index=tensor.index,
                columns=factor_names
            )
            
            # Save factors
            factors_df.to_parquet(self.paths['macro_factors'])
            
            print(f"   ✅ Extracted {n_factors} macro factors")
            print(f"   📊 Explained variance: {pca.explained_variance_ratio_.sum():.3f}")
            
            # Load REAL stock returns from individual files (use extended folder for historical data)
            print("   📈 Loading real stock data from extended historical files...")
            stock_files = glob.glob(os.path.join('data/raw/prices_daily_extended/', '*.csv'))
            
            if not stock_files:
                print("   ⚠️ No extended stock files found, trying regular folder...")
                stock_files = glob.glob(os.path.join('data/raw/prices_daily/', '*.csv'))
                
                if not stock_files:
                    print("   ⚠️ No stock files found, using tensor stock data")
                    if stock_vars:
                        stock_returns = tensor[stock_vars].fillna(0)
                        print(f"   📈 Using tensor stock variables: {len(stock_vars)}")
                    else:
                        print("   ⚠️ No stock data available")
                        return factors_df, pd.DataFrame(), pca.explained_variance_ratio_
            
            print(f"   📁 Found {len(stock_files)} stock files")
            
            # Load stock returns (limit for performance)
            stock_returns_list = []
            processed_count = 0
            max_stocks = min(len(stock_files), 200)  # Process up to 200 stocks
            
            for file_path in stock_files[:max_stocks]:
                try:
                    ticker = os.path.basename(file_path).replace('.csv', '').replace('.NS', '')
                    
                    # Load stock data
                    stock_df = pd.read_csv(file_path, parse_dates=['Date'])
                    
                    if len(stock_df) < 50:  # Skip stocks with insufficient data
                        continue
                    
                    stock_df = stock_df.set_index('Date')
                    stock_df = stock_df.sort_index()
                    
                    # Calculate returns
                    stock_df['return'] = stock_df['Close'].pct_change()
                    
                    # Resample to weekly to match tensor frequency
                    weekly_returns = stock_df['return'].resample('W').last()
                    
                    # Only keep if we have sufficient data
                    if len(weekly_returns.dropna()) >= 20:
                        stock_returns_list.append(weekly_returns.rename(ticker))
                        processed_count += 1
                        
                        if processed_count >= 100:  # Limit to 100 stocks for performance
                            break
                            
                except Exception as e:
                    continue
            
            if stock_returns_list:
                # Combine all stock returns
                stock_returns = pd.concat(stock_returns_list, axis=1, sort=True)
                
                # Align with tensor date range - this is crucial
                stock_returns = stock_returns.reindex(tensor.index, method='nearest')
                stock_returns = stock_returns.fillna(0)
                
                print(f"   ✅ Loaded {len(stock_returns.columns)} real stocks with returns")
                print(f"   📅 Aligned to tensor range: {stock_returns.index[0].date()} to {stock_returns.index[-1].date()}")
                
                # Show sample of actual return values
                sample_stock = stock_returns.columns[0]
                sample_returns = stock_returns[sample_stock]
                non_zero_returns = sample_returns[sample_returns != 0]
                if len(non_zero_returns) > 0:
                    print(f"   🔍 Sample returns for {sample_stock}: mean={non_zero_returns.mean():.4f}, std={non_zero_returns.std():.4f}")
                    print(f"   📊 Non-zero data points: {len(non_zero_returns)}/{len(sample_returns)} ({len(non_zero_returns)/len(sample_returns)*100:.1f}%)")
                else:
                    print(f"   ⚠️ Sample stock {sample_stock} has no non-zero returns (data may not cover requested period)")
            else:
                print("   ⚠️ Could not load any stock data, falling back to tensor data")
                if stock_vars:
                    stock_returns = tensor[stock_vars].fillna(0)
                    print(f"   📈 Using tensor stock variables: {len(stock_vars)}")
                else:
                    print("   ❌ No stock data available at all")
                    return factors_df, pd.DataFrame(), pca.explained_variance_ratio_
            
            return factors_df, stock_returns, pca.explained_variance_ratio_
            
        except Exception as e:
            print(f"❌ Error extracting macro factors: {e}")
            return pd.DataFrame(), pd.DataFrame(), np.array([])
    
    def compute_rolling_betas(self, factors_df, stock_returns, year):
        """Compute rolling betas between stocks and macro factors with detailed progress tracking"""
        
        try:
            print(f"📈 Computing rolling betas for {year}...")
            
            # Filter data for the specific year
            year_mask = factors_df.index.year == year
            year_factors = factors_df[year_mask]
            year_stocks = stock_returns[year_mask]
            
            if len(year_factors) < self.config['min_observations']:
                print(f"⚠️ Insufficient data for {year}: {len(year_factors)} weeks")
                return pd.DataFrame()
            
            print(f"   📊 Processing {len(year_factors)} weeks, {len(year_stocks.columns)} stocks, {len(year_factors.columns)} factors")
            
            # Limit stocks for performance
            max_stocks = min(len(year_stocks.columns), self.config['max_stocks_per_week'])
            selected_stocks = year_stocks.columns[:max_stocks]
            year_stocks = year_stocks[selected_stocks]
            
            beta_records = []
            window_size = self.config['rolling_window']
            
            # Calculate total operations for progress tracking
            total_weeks = len(year_factors) - window_size
            total_operations = total_weeks * len(selected_stocks) * len(year_factors.columns)
            
            print(f"   🎯 Total operations: {total_operations:,} (beta calculations)")
            print(f"   ⏱️  Estimated time: {total_operations / 10000:.1f} minutes")
            print()
            
            start_time = datetime.now()
            completed_operations = 0
            
            # Process each week with detailed progress
            for week_idx in range(window_size, len(year_factors)):
                week_date = year_factors.index[week_idx]
                week_num = week_date.isocalendar()[1]
                
                # Progress calculation
                weeks_completed = week_idx - window_size
                progress_pct = (weeks_completed / total_weeks) * 100
                
                # Time estimation
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if weeks_completed > 0:
                    avg_time_per_week = elapsed_time / weeks_completed
                    remaining_weeks = total_weeks - weeks_completed
                    eta_seconds = remaining_weeks * avg_time_per_week
                    eta_minutes = eta_seconds / 60
                    eta_str = f"ETA: {eta_minutes:.1f}m"
                else:
                    eta_str = "ETA: calculating..."
                
                print(f"   📅 Week {week_num:2d} ({week_date.date()}) | Progress: {progress_pct:5.1f}% | {eta_str}", end=" | ")
                
                # Get rolling window data
                start_idx = week_idx - window_size + 1
                end_idx = week_idx + 1
                
                window_factors = year_factors.iloc[start_idx:end_idx]
                window_stocks = year_stocks.iloc[start_idx:end_idx]
                
                week_betas = 0
                week_start_time = datetime.now()
                
                # Compute betas for each stock-factor pair
                for stock in selected_stocks:
                    stock_returns_window = window_stocks[stock].values
                    
                    # Skip if insufficient data
                    if np.isnan(stock_returns_window).sum() > window_size * 0.3:
                        completed_operations += len(year_factors.columns)
                        continue
                    
                    for factor in year_factors.columns:
                        completed_operations += 1
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
                            
                            # Calculate R²
                            r2 = reg.score(X_clean, y_clean)
                            
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
                                    'observations': int(valid_mask.sum())
                                }
                                beta_records.append(beta_record)
                                week_betas += 1
                        
                        except Exception as e:
                            continue
                
                # Week completion stats
                week_time = (datetime.now() - week_start_time).total_seconds()
                print(f"{week_betas} betas | {week_time:.1f}s")
            
            # Final processing stats
            total_time = (datetime.now() - start_time).total_seconds()
            
            if beta_records:
                betas_df = pd.DataFrame(beta_records)
                print(f"   ✅ Computed {len(beta_records):,} beta relationships in {total_time:.1f}s")
                print(f"   📊 Processing rate: {len(beta_records) / total_time:.0f} betas/second")
                
                # Show sample beta values for debugging
                if len(betas_df) > 0:
                    sample_stock = betas_df['stock'].iloc[0]
                    sample_factor = betas_df['factor'].iloc[0]
                    sample_data = betas_df[(betas_df['stock'] == sample_stock) & (betas_df['factor'] == sample_factor)].head(5)
                    print(f"   🔍 Sample betas for {sample_stock} vs {sample_factor}:")
                    for _, row in sample_data.iterrows():
                        print(f"      Week {row['week']}: β={row['beta']:.4f}, R²={row['r_squared']:.3f}")
                
                return betas_df
            else:
                print(f"   ⚠️ No valid beta relationships found in {total_time:.1f}s")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error computing rolling betas: {e}")
            return pd.DataFrame()
    
    def compute_beta_drift(self, betas_df):
        """Compute beta drift (sensitivity changes) from rolling betas"""
        
        try:
            print("🔄 Computing beta drift (sensitivity changes)...")
            
            if betas_df.empty:
                return pd.DataFrame()
            
            print(f"   📊 Input betas: {len(betas_df)} relationships")
            print(f"   📈 Unique stocks: {betas_df['stock'].nunique()}")
            print(f"   🧠 Unique factors: {betas_df['factor'].nunique()}")
            
            drift_records = []
            total_pairs = 0
            pairs_with_drift = 0
            all_drifts = []  # Track all drifts for debugging
            
            # Group by stock-factor pairs
            for (stock, factor), group in betas_df.groupby(['stock', 'factor']):
                total_pairs += 1
                
                if len(group) < 2:
                    continue
                
                # Sort by date
                group_sorted = group.sort_values('date')
                
                # Compute beta drift
                for i in range(1, len(group_sorted)):
                    current_row = group_sorted.iloc[i]
                    previous_row = group_sorted.iloc[i-1]
                    
                    beta_current = current_row['beta']
                    beta_previous = previous_row['beta']
                    beta_drift = beta_current - beta_previous
                    
                    all_drifts.append(abs(beta_drift))  # Track for debugging
                    
                    # Check if drift is significant
                    if abs(beta_drift) >= self.config['drift_threshold']:
                        pairs_with_drift += 1
                        
                        # Calculate novelty (how unusual this drift is)
                        novelty = self.calculate_drift_novelty(
                            group_sorted.iloc[:i], beta_drift
                        )
                        
                        drift_record = {
                            'date': current_row['date'],
                            'year': current_row['year'],
                            'week': current_row['week'],
                            'stock': stock,
                            'factor': factor,
                            'beta_current': float(beta_current),
                            'beta_previous': float(beta_previous),
                            'beta_drift': float(beta_drift),
                            'drift_magnitude': float(abs(beta_drift)),
                            'direction': int(np.sign(beta_drift)),
                            'r_squared': float(current_row['r_squared']),
                            'novelty': float(novelty),
                            'confidence': float(current_row['r_squared'])  # Use R² as confidence
                        }
                        drift_records.append(drift_record)
            
            print(f"   📊 Total stock-factor pairs: {total_pairs}")
            print(f"   🔄 Pairs with significant drift: {pairs_with_drift}")
            print(f"   📈 Drift threshold: {self.config['drift_threshold']}")
            
            # Show drift statistics
            if all_drifts:
                all_drifts = np.array(all_drifts)
                print(f"   📊 All drift magnitudes - Min: {all_drifts.min():.4f}, Max: {all_drifts.max():.4f}, Mean: {all_drifts.mean():.4f}")
                print(f"   📊 Drifts above threshold ({self.config['drift_threshold']}): {np.sum(all_drifts >= self.config['drift_threshold'])}/{len(all_drifts)}")
            
            if drift_records:
                drift_df = pd.DataFrame(drift_records)
                print(f"   ✅ Detected {len(drift_records)} significant beta drifts")
                
                # Show some statistics
                print(f"   📊 Drift magnitude range: {drift_df['drift_magnitude'].min():.3f} to {drift_df['drift_magnitude'].max():.3f}")
                print(f"   📊 Average drift magnitude: {drift_df['drift_magnitude'].mean():.3f}")
                
                return drift_df
            else:
                print("   ⚠️ No significant beta drifts detected")
                
                # Show some debugging info
                if total_pairs > 0 and all_drifts:
                    suggested_threshold = np.percentile(all_drifts, 90)  # 90th percentile
                    print(f"   🔍 Suggested threshold (90th percentile): {suggested_threshold:.4f}")
                
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error computing beta drift: {e}")
            return pd.DataFrame()
    
    def calculate_drift_novelty(self, historical_group, current_drift):
        """Calculate how novel/unusual this beta drift is"""
        
        try:
            if len(historical_group) < 3:
                return 1.0  # Novel if no history
            
            # Get historical drifts
            historical_betas = historical_group['beta'].values
            historical_drifts = np.diff(historical_betas)
            
            if len(historical_drifts) == 0:
                return 1.0
            
            # Calculate z-score of current drift vs historical
            mean_drift = np.mean(historical_drifts)
            std_drift = np.std(historical_drifts)
            
            if std_drift == 0:
                return 1.0 if current_drift != mean_drift else 0.0
            
            z_score = abs(current_drift - mean_drift) / std_drift
            
            # Convert z-score to novelty (0-1 scale)
            novelty = min(1.0, z_score / 3.0)  # 3-sigma normalization
            
            return novelty
            
        except:
            return 0.5  # Default moderate novelty
    
    def save_weekly_beta_drift(self, drift_df, year, week):
        """Save weekly beta drift data"""
        
        try:
            if drift_df.empty:
                return False
            
            # Create year directory
            year_dir = os.path.join(self.paths['beta_drift_insights'], str(year))
            os.makedirs(year_dir, exist_ok=True)
            
            # Filter for specific week
            week_data = drift_df[drift_df['week'] == week]
            
            if week_data.empty:
                return False
            
            # Save to parquet
            week_file = os.path.join(year_dir, f'week_{week:02d}.parquet')
            week_data.to_parquet(week_file, index=False)
            
            print(f"   💾 Saved {len(week_data)} beta drifts: week_{week:02d}.parquet")
            return True
            
        except Exception as e:
            print(f"❌ Error saving beta drift: {e}")
            return False
    
    def build_year_beta_fabric(self, year):
        """Build beta drift fabric for a specific year with comprehensive progress tracking"""
        
        start_time = datetime.now()
        
        print(f"🧬 BUILDING BETA DRIFT FABRIC FOR {year}")
        print("=" * 60)
        print(f"🎯 Starting from year 2000 (when major market data becomes available)")
        print(f"📅 Current year: {year}")
        print()
        
        # Load market tensor
        print("📊 STEP 1/6: Loading market tensor...")
        tensor_start = datetime.now()
        tensor = self.load_market_tensor()
        tensor_time = (datetime.now() - tensor_start).total_seconds()
        
        if tensor.empty:
            print("❌ Cannot build fabric without market tensor")
            return False
        
        print(f"   ✅ Market tensor loaded in {tensor_time:.1f}s")
        print(f"   📊 Shape: {tensor.shape}")
        print()
        
        # Extract macro factors and stock returns
        print("🧠 STEP 2/6: Extracting macro factors...")
        factors_start = datetime.now()
        factors_df, stock_returns, explained_var = self.extract_macro_factors(tensor)
        factors_time = (datetime.now() - factors_start).total_seconds()
        
        if factors_df.empty or stock_returns.empty:
            print("❌ Could not extract factors or stock returns")
            return False
        
        print(f"   ✅ Macro factors extracted in {factors_time:.1f}s")
        print(f"   🧠 Factors: {len(factors_df.columns)}")
        print(f"   📈 Stocks: {len(stock_returns.columns)}")
        print(f"   📊 Explained variance: {explained_var.sum():.3f}")
        print()
        
        # Compute rolling betas (this is the heavy computation)
        print("📈 STEP 3/6: Computing rolling betas (main computation)...")
        betas_start = datetime.now()
        betas_df = self.compute_rolling_betas(factors_df, stock_returns, year)
        betas_time = (datetime.now() - betas_start).total_seconds()
        
        if betas_df.empty:
            print("❌ Could not compute rolling betas")
            return False
        
        print(f"   ✅ Rolling betas computed in {betas_time:.1f}s")
        print(f"   📊 Beta relationships: {len(betas_df):,}")
        print()
        
        # Compute beta drift
        print("🔄 STEP 4/6: Computing beta drift (sensitivity changes)...")
        drift_start = datetime.now()
        drift_df = self.compute_beta_drift(betas_df)
        drift_time = (datetime.now() - drift_start).total_seconds()
        
        if drift_df.empty:
            print("❌ No beta drift detected")
            return False
        
        print(f"   ✅ Beta drift computed in {drift_time:.1f}s")
        print(f"   🔄 Significant drifts: {len(drift_df):,}")
        print()
        
        # Save weekly beta drift files
        print("💾 STEP 5/6: Saving weekly beta drift files...")
        save_start = datetime.now()
        total_saved = 0
        unique_weeks = sorted(drift_df['week'].unique())
        
        print(f"   📁 Saving {len(unique_weeks)} weekly files...")
        for i, week in enumerate(unique_weeks):
            week_progress = (i + 1) / len(unique_weeks) * 100
            print(f"      Week {week:2d}: ", end="")
            if self.save_weekly_beta_drift(drift_df, year, week):
                total_saved += 1
                print(f"✅ ({week_progress:5.1f}%)")
            else:
                print(f"⚠️ ({week_progress:5.1f}%)")
        
        save_time = (datetime.now() - save_start).total_seconds()
        print(f"   ✅ Weekly files saved in {save_time:.1f}s")
        print()
        
        # Build year summary
        print("📋 STEP 6/6: Building year summary...")
        summary_start = datetime.now()
        self.build_year_summary(year, drift_df, explained_var)
        summary_time = (datetime.now() - summary_start).total_seconds()
        print(f"   ✅ Year summary built in {summary_time:.1f}s")
        print()
        
        # Final statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print("=" * 60)
        print(f"✅ BETA DRIFT FABRIC FOR {year} COMPLETED!")
        print(f"   📊 Total beta drifts detected: {len(drift_df):,}")
        print(f"   📁 Weekly files saved: {total_saved}")
        print(f"   ⏱️  Total processing time: {processing_time:.1f} seconds ({processing_time/60:.1f} minutes)")
        print(f"   🧠 Macro factors explained variance: {explained_var.sum():.3f}")
        print()
        print("⏱️  TIME BREAKDOWN:")
        print(f"   📊 Market tensor loading: {tensor_time:.1f}s ({tensor_time/processing_time*100:.1f}%)")
        print(f"   🧠 Factor extraction: {factors_time:.1f}s ({factors_time/processing_time*100:.1f}%)")
        print(f"   📈 Beta computation: {betas_time:.1f}s ({betas_time/processing_time*100:.1f}%)")
        print(f"   🔄 Drift detection: {drift_time:.1f}s ({drift_time/processing_time*100:.1f}%)")
        print(f"   💾 File saving: {save_time:.1f}s ({save_time/processing_time*100:.1f}%)")
        print(f"   📋 Summary building: {summary_time:.1f}s ({summary_time/processing_time*100:.1f}%)")
        
        return True
    
    def build_year_summary(self, year, drift_df, explained_var):
        """Build summary for the year"""
        
        try:
            year_dir = os.path.join(self.paths['beta_drift_insights'], str(year))
            os.makedirs(year_dir, exist_ok=True)
            
            # Save year summary
            summary_file = os.path.join(year_dir, 'summary.parquet')
            drift_df.to_parquet(summary_file, index=False)
            
            # Create metadata
            metadata = {
                'year': year,
                'created_at': datetime.now().isoformat(),
                'total_beta_drifts': len(drift_df),
                'weeks_processed': len(drift_df['week'].unique()),
                'stocks_analyzed': len(drift_df['stock'].unique()),
                'factors_used': len(drift_df['factor'].unique()),
                'avg_drifts_per_week': len(drift_df) / len(drift_df['week'].unique()) if len(drift_df['week'].unique()) > 0 else 0,
                'factor_distribution': drift_df['factor'].value_counts().to_dict(),
                'explained_variance': explained_var.tolist(),
                'config': self.config
            }
            
            metadata_file = os.path.join(year_dir, 'metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"   📋 Year summary saved: {summary_file}")
            
        except Exception as e:
            print(f"⚠️ Error building year summary: {e}")
    
    def get_available_years(self):
        """Get years available for processing starting from 2000, considering both tensor and stock data availability"""
        
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            return []
        
        # Get years from tensor
        tensor_years = sorted(tensor.index.year.unique())
        
        # Check what years have actual stock data (try extended folder first)
        stock_files = glob.glob(os.path.join('data/raw/prices_daily_extended/', '*.csv'))
        if not stock_files:
            stock_files = glob.glob(os.path.join('data/raw/prices_daily/', '*.csv'))
        
        stock_years = set()
        
        if stock_files:
            # Sample a few stock files to determine date range
            for file_path in stock_files[:5]:  # Check first 5 files
                try:
                    sample_df = pd.read_csv(file_path, parse_dates=['Date'], nrows=100)
                    if not sample_df.empty:
                        stock_years.update(sample_df['Date'].dt.year.unique())
                except:
                    continue
        
        # Find intersection of tensor years and stock years, starting from 2000
        if stock_years:
            available_years = []
            for year in tensor_years:
                if year >= 2000 and year in stock_years:
                    year_data = tensor[tensor.index.year == year]
                    if len(year_data) >= self.config['min_observations']:
                        available_years.append(year)
            
            print(f"📅 Available years (2000+ with stock data): {len(available_years)} years")
            if available_years:
                print(f"   Range: {min(available_years)} to {max(available_years)}")
                print(f"   Stock data coverage: {min(stock_years)} to {max(stock_years)}")
            else:
                print(f"   ⚠️ No overlap between tensor years (2000+) and stock data years ({min(stock_years)}-{max(stock_years)})")
        else:
            # Fallback to tensor data only (use corporate factors from tensor)
            available_years = []
            for year in tensor_years:
                if year >= 2000:
                    year_data = tensor[tensor.index.year == year]
                    if len(year_data) >= self.config['min_observations']:
                        available_years.append(year)
            
            print(f"📅 Available years (2000+ tensor only): {len(available_years)} years")
            if available_years:
                print(f"   Range: {min(available_years)} to {max(available_years)}")
                print(f"   ⚠️ Using tensor corporate factors (no individual stock files)")
        
        return available_years
    
    def process_next_year(self):
        """Process the next available year starting from 2000 with comprehensive progress tracking"""
        
        available_years = self.get_available_years()
        
        if not available_years:
            print("❌ No years available for processing from 2000 onwards")
            return False
        
        # Find the next year to process
        processed_years = []
        
        if os.path.exists(self.paths['beta_drift_insights']):
            processed_years = [
                int(d) for d in os.listdir(self.paths['beta_drift_insights'])
                if d.isdigit() and os.path.isdir(os.path.join(self.paths['beta_drift_insights'], d))
            ]
        
        # Find next unprocessed year
        next_year = None
        for year in sorted(available_years):
            if year not in processed_years:
                next_year = year
                break
        
        if next_year is None:
            print("✅ All available years from 2000 onwards have been processed")
            print(f"   Processed years: {sorted(processed_years)}")
            return True
        
        # Show comprehensive progress overview
        remaining_years = [y for y in available_years if y not in processed_years]
        total_years = len(available_years)
        completed_years = len(processed_years)
        completion_pct = (completed_years / total_years) * 100 if total_years > 0 else 0
        
        print(f"🎯 PROCESSING NEXT YEAR: {next_year}")
        print("=" * 50)
        print(f"📊 OVERALL PROGRESS:")
        print(f"   📅 Available years (2000+): {total_years} ({min(available_years)}-{max(available_years)})")
        print(f"   ✅ Completed: {completed_years} years ({completion_pct:.1f}%)")
        print(f"   ⏳ Remaining: {len(remaining_years)} years")
        print(f"   🎯 Current target: {next_year}")
        print(f"   📈 Next up: {remaining_years[1:6] if len(remaining_years) > 1 else 'None'}")
        print()
        
        # Estimate total time remaining
        if completed_years > 0:
            # Rough estimate: 2-5 minutes per year depending on data size
            avg_time_per_year = 3.5  # minutes
            remaining_time = len(remaining_years) * avg_time_per_year
            print(f"⏱️  ESTIMATED TIME:")
            print(f"   Current year: ~3-5 minutes")
            print(f"   Remaining years: ~{remaining_time:.0f} minutes ({remaining_time/60:.1f} hours)")
            print()
        
        return self.build_year_beta_fabric(next_year)

def main():
    """Build beta drift fabric for next available year starting from 2000"""
    
    fabric = BetaDriftFabric()
    
    print("🧬 BETA DRIFT FABRIC BUILDER - THE MARKET NERVOUS SYSTEM")
    print("Detecting sensitivity shifts that precede price moves")
    print("=" * 70)
    
    # Show available years from 2000 onwards
    available_years = fabric.get_available_years()
    
    print(f"📅 Available years (2000+): {len(available_years)} ({min(available_years) if available_years else 'None'}-{max(available_years) if available_years else 'None'})")
    
    if not available_years:
        print("❌ No years from 2000 onwards available for processing")
        return False
    
    # Show processed years
    processed_years = []
    if os.path.exists('data/beta_drift_insights'):
        processed_years = [
            int(d) for d in os.listdir('data/beta_drift_insights')
            if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
        ]
    
    if processed_years:
        print(f"✅ Already processed: {sorted(processed_years)}")
    
    remaining_years = [year for year in available_years if year not in processed_years]
    if remaining_years:
        print(f"⏳ Remaining to process: {len(remaining_years)} years ({min(remaining_years)}-{max(remaining_years)})")
        next_year = min(remaining_years)
        print(f"🎯 Next year to process: {next_year}")
    else:
        print("🎉 All years have been processed!")
        return True
    
    print()
    
    # Process next year
    success = fabric.process_next_year()
    
    if success:
        print(f"\n🎯 Beta drift fabric processing completed!")
        print(f"   Next: Run again to process the next year")
        print(f"   Integration: Beta drift data ready for capital allocation")
        
        # Show final progress
        updated_processed = []
        if os.path.exists('data/beta_drift_insights'):
            updated_processed = [
                int(d) for d in os.listdir('data/beta_drift_insights')
                if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
            ]
        
        completed_pct = len(updated_processed) / len(available_years) * 100
        print(f"   📊 Overall progress: {len(updated_processed)}/{len(available_years)} years ({completed_pct:.1f}%)")
        
    else:
        print("❌ Failed to process beta drift fabric")
    
    return success

if __name__ == "__main__":
    main()
