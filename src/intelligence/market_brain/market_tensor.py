#!/usr/bin/env python3
"""
🧠 MARKET TENSOR ENGINE - NORTHSTAR V3 MARKET BRAIN
The Sensory Cortex: Unified Market State Representation

This transforms scattered market data into one synchronized tensor that becomes
the sensory input for all market brain components.

Integration with V3:
- Feeds into existing Market State Spine
- Enhances market_state.py with tensor representation
- Maintains backward compatibility with existing systems

Output: market_tensor.parquet (T × N matrix where N ≈ 400-1000 variables)
"""

import pandas as pd
import numpy as np
import os
import glob
import json
from datetime import datetime, timedelta
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# Import the unified RBI data handler
import sys
import os
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.utils.rbi_data_handler import rbi_handler
except ImportError:
    rbi_handler = None

class MarketTensorEngine:
    """
    Market Tensor Engine - The Sensory Cortex
    
    Converts all market forces into a single synchronized tensor:
    - Monetary forces (RBI, rates, liquidity)
    - Yield curve & credit spreads
    - Liquidity & flows (FII, DII, FX)
    - Market structure (breadth, volatility)
    - Sector forces (rotation, strength)
    - Corporate forces (compressed from 500 stocks)
    """
    
    def __init__(self):
        self.name = "Market Tensor Engine"
        self.version = "1.0"
        self._rbi_handler_available = rbi_handler is not None
        
        # Data paths - integrate with comprehensive RBI data
        self.paths = {
            'rbi_data': 'data/macro/factors/macro_score.parquet',
            'rbi_comprehensive': 'data/macro/comprehensive_rbi_data.parquet',
            'rbi_raw': 'data/macro/raw/',
            'yields': 'data/macro/yields_enhanced.csv',  # Use enhanced yield data
            'macro_indicators': 'data/macro/macro_indicators.parquet',  # Key macro variables
            'flows': 'data/processed/sector_flows.parquet',
            'market_data': 'data/options/live/market_data_latest.json',
            'prices': 'data/market/daily_prices.parquet',
            'prices_daily': 'data/raw/prices_daily/',
            'sectors': 'data/processed/sector_flows.parquet',
            'sector_mapping': 'data/processed/sector_mapping.csv',
            'nifty': 'data/processed/nifty.parquet',
            'output': 'data/processed/market_tensor.parquet',
            'metadata': 'data/processed/market_tensor_metadata.json'
        }
        
        # Tensor configuration
        self.config = {
            'resample_freq': 'W',  # Weekly resampling
            'lookback_days': 1260,  # 5 years of data
            'pca_components': 30,   # Compress stocks to 30 factors
            'min_data_points': 50,  # Minimum data points for inclusion
            'fill_method': 'forward'  # Forward fill missing values
        }
        
        # Component weights for tensor construction
        self.component_weights = {
            'monetary': 0.25,    # RBI, rates, liquidity
            'credit': 0.15,      # Yield curve, spreads
            'flows': 0.20,       # FII, DII, FX flows
            'structure': 0.15,   # Market breadth, volatility
            'sectors': 0.15,     # Sector rotation
            'corporate': 0.10    # Corporate system (PCA compressed)
        }

    @staticmethod
    def canonicalize_tensor_frame(tensor: pd.DataFrame) -> pd.DataFrame:
        """Normalize loaded tensor to datetime index + numeric feature columns."""
        if tensor is None or tensor.empty:
            return pd.DataFrame()

        frame = tensor.copy()
        date_col = "date" if "date" in frame.columns else ("Date" if "Date" in frame.columns else None)

        if date_col is not None:
            date_idx = pd.to_datetime(frame[date_col], errors="coerce")
            frame = frame.drop(columns=[date_col], errors="ignore")
            valid = ~date_idx.isna()
            frame = frame.loc[valid].copy()
            date_idx = pd.DatetimeIndex(date_idx[valid])
        else:
            date_idx = pd.to_datetime(frame.index, errors="coerce")
            valid = ~date_idx.isna()
            frame = frame.loc[valid].copy()
            date_idx = pd.DatetimeIndex(date_idx[valid])

        if date_idx.tz is not None:
            date_idx = date_idx.tz_localize(None)

        frame.index = date_idx
        frame = frame.sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame.index.name = "date"

        return frame
    
    def load_and_resample(self, path, col_map, date_col='Date'):
        """Safely load and resample data to weekly frequency using unified RBI handler for RBI files"""
        
        try:
            # Check if this is an RBI file
            is_rbi_file = 'rbi_' in os.path.basename(path).lower() or 'macro' in path.lower()
            
            if is_rbi_file and path.endswith('.csv'):
                # Check if this is the enhanced yield file (already has proper headers)
                if 'yields_enhanced' in path:
                    # This file already has proper headers, load normally
                    df = pd.read_csv(path, parse_dates=['Date'])
                    if not df.empty and 'Date' in df.columns:
                        df = df.set_index('Date')
                        # Apply column mapping if provided
                        if col_map:
                            existing_col_map = {k: v for k, v in col_map.items() if k in df.columns}
                            if existing_col_map:
                                df = df.rename(columns=existing_col_map)
                        # Resample to target frequency
                        df = df.resample(self.config['resample_freq']).last()
                        return df
                    else:
                        return pd.DataFrame()
                else:
                    # Use unified RBI handler for raw RBI files
                    if not self._rbi_handler_available:
                        raise RuntimeError(
                            "RBI handler unavailable for raw RBI file loading; placeholder RBI fallback is disabled."
                        )
                    print(f"   🏛️ Using RBI handler for {path}")
                    df = rbi_handler.load_rbi_file(path)
                    
                    if df.empty:
                        return pd.DataFrame()
                    
                    # Apply column mapping if provided
                    if col_map:
                        # Only map columns that exist
                        existing_col_map = {k: v for k, v in col_map.items() if k in df.columns}
                        if existing_col_map:
                            df = df.rename(columns=existing_col_map)
                    
                    # Resample to target frequency
                    df = rbi_handler.resample_rbi_data(df, self.config['resample_freq'])
                    
                    return df
            
            else:
                # Use standard loading for non-RBI files
                if path.endswith('.parquet'):
                    df = pd.read_parquet(path)
                else:
                    df = pd.read_csv(path, parse_dates=[date_col] if date_col in pd.read_csv(path, nrows=0).columns else None)
                
                if df.empty:
                    return pd.DataFrame()
                
                # Rename columns
                if col_map:
                    df = df.rename(columns=col_map)
                
                # Set date index
                if date_col in df.columns:
                    df = df.set_index(date_col)
                elif not isinstance(df.index, pd.DatetimeIndex):
                    # Try to convert index to datetime
                    try:
                        df.index = pd.to_datetime(df.index)
                    except:
                        print(f"⚠️ Could not convert index to datetime for {path}")
                        return pd.DataFrame()
                
                # Ensure all columns are Series, not DataFrames
                for col in df.columns:
                    if isinstance(df[col], pd.DataFrame):
                        # If column is a DataFrame, take the first column
                        df[col] = df[col].iloc[:, 0] if not df[col].empty else pd.Series(dtype=float, index=df.index)
                
                # Convert to numeric where possible
                for col in df.columns:
                    try:
                        if not pd.api.types.is_numeric_dtype(df[col]):
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    except:
                        pass
                
                # Sort and resample
                df = df.sort_index()
                df = df.resample(self.config['resample_freq']).last()
                
                return df
            
        except Exception as e:
            print(f"⚠️ Error loading {path}: {e}")
            return pd.DataFrame()
    
    def build_monetary_forces(self):
        """Build monetary forces tensor component using comprehensive RBI data"""
        
        print("💰 Building monetary forces...")
        
        monetary_data = []
        used_columns = set()  # Track columns to avoid duplicates
        
        # 1. RBI Processed Data (primary source)
        rbi_df = self.load_and_resample(self.paths['rbi_data'], {
            'MacroScore': 'rbi_macro_score',
            'Contrib_L': 'rbi_liquidity',
            'Contrib_G': 'rbi_growth', 
            'Contrib_I': 'rbi_inflation',
            'Contrib_S': 'rbi_stability'
        })
        
        if not rbi_df.empty:
            monetary_data.append(rbi_df)
            used_columns.update(rbi_df.columns)
            print(f"   ✅ RBI processed data: {len(rbi_df)} periods")
        
        # 2. Comprehensive RBI Data (NEW - 151 variables!)
        try:
            if os.path.exists(self.paths['rbi_comprehensive']):
                comprehensive_rbi = pd.read_parquet(self.paths['rbi_comprehensive'])
                
                # Select key monetary policy variables, excluding duplicates
                monetary_vars = []
                for col in comprehensive_rbi.columns:
                    col_lower = col.lower()
                    if any(term in col_lower for term in [
                        'repo', 'rate', 'policy', 'crr', 'slr', 'msf', 'bank_rate',
                        'reserve', 'liquidity', 'facility'
                    ]) and col not in used_columns:  # Avoid duplicates
                        monetary_vars.append(col)
                
                if monetary_vars:
                    monetary_comprehensive = comprehensive_rbi[monetary_vars].copy()
                    
                    # Resample to weekly
                    monetary_comprehensive = monetary_comprehensive.resample(self.config['resample_freq']).last()
                    
                    monetary_data.append(monetary_comprehensive)
                    used_columns.update(monetary_vars)
                    print(f"   ✅ Comprehensive RBI monetary data: {len(monetary_vars)} variables, {len(monetary_comprehensive)} periods")
                else:
                    print("   ℹ️ No new monetary variables found in comprehensive data")
            else:
                print("   ℹ️ Comprehensive RBI data not available")
        except Exception as e:
            print(f"   ⚠️ Could not load comprehensive RBI data: {e}")
        
        # 3. Macro Indicators (key variables subset), excluding duplicates
        try:
            if os.path.exists(self.paths['macro_indicators']):
                macro_indicators = pd.read_parquet(self.paths['macro_indicators'])
                
                # Filter out columns that are already used
                unique_macro_cols = [col for col in macro_indicators.columns if col not in used_columns]
                
                if unique_macro_cols:
                    macro_indicators_unique = macro_indicators[unique_macro_cols].copy()
                    
                    # Resample to weekly
                    macro_indicators_unique = macro_indicators_unique.resample(self.config['resample_freq']).last()
                    
                    monetary_data.append(macro_indicators_unique)
                    used_columns.update(unique_macro_cols)
                    print(f"   ✅ Macro indicators: {len(unique_macro_cols)} unique variables, {len(macro_indicators_unique)} periods")
                else:
                    print("   ℹ️ No unique macro indicator variables found")
            else:
                print("   ℹ️ Macro indicators not available")
        except Exception as e:
            print(f"   ⚠️ Could not load macro indicators: {e}")
        
        # Combine all monetary data (now without duplicates)
        if monetary_data:
            monetary_tensor = pd.concat(monetary_data, axis=1, sort=True)
            monetary_tensor = monetary_tensor.ffill().fillna(0)
            print(f"   📊 Monetary tensor shape: {monetary_tensor.shape}")
            print(f"   📊 Total unique columns: {len(used_columns)}")
            return monetary_tensor
        
        return pd.DataFrame()
    
    def build_credit_forces(self):
        """Build credit and yield curve forces from enhanced RBI data"""
        
        print("📈 Building credit forces...")
        
        credit_data = []
        used_columns = set()  # Track columns to avoid duplicates
        
        # 1. Enhanced yield curve data (18 yield series!) - now with proper Date column
        if os.path.exists(self.paths['yields']):
            yields_df = self.load_and_resample(self.paths['yields'], {}, date_col='Date')
            
            if not yields_df.empty:
                # Calculate yield curve metrics
                yield_cols = list(yields_df.columns)
                
                # Calculate spreads if we have multiple yields
                if len(yield_cols) >= 2:
                    for i, col1 in enumerate(yield_cols):
                        for col2 in yield_cols[i+1:]:
                            if 'rate' in col1.lower() and 'rate' in col2.lower():
                                spread_name = f"{col1}_{col2}_spread"
                                yields_df[spread_name] = yields_df[col1] - yields_df[col2]
                
                credit_data.append(yields_df)
                used_columns.update(yields_df.columns)
                print(f"   ✅ Enhanced yield data: {len(yields_df.columns)} series, {len(yields_df)} periods")
            else:
                print("   ⚠️ Enhanced yield data is empty")
        else:
            print("   ℹ️ Enhanced yield data not available - will be created from RBI data")
        
        # 2. Credit-related variables from comprehensive RBI data, excluding duplicates
        try:
            if os.path.exists(self.paths['rbi_comprehensive']):
                comprehensive_rbi = pd.read_parquet(self.paths['rbi_comprehensive'])
                
                # Select credit-related variables, excluding duplicates
                credit_vars = []
                for col in comprehensive_rbi.columns:
                    col_lower = col.lower()
                    if any(term in col_lower for term in [
                        'credit', 'loan', 'deposit', 'banking', 'commercial',
                        'certificate', 'borrowing'
                    ]) and col not in used_columns:  # Avoid duplicates
                        credit_vars.append(col)
                
                if credit_vars:
                    credit_comprehensive = comprehensive_rbi[credit_vars].copy()
                    
                    # Resample to weekly using RBI handler
                    credit_comprehensive = rbi_handler.resample_rbi_data(credit_comprehensive, self.config['resample_freq'])
                    
                    credit_data.append(credit_comprehensive)
                    used_columns.update(credit_vars)
                    print(f"   ✅ Comprehensive credit data: {len(credit_vars)} unique variables, {len(credit_comprehensive)} periods")
                else:
                    print("   ℹ️ No new credit variables found in comprehensive data")
        except Exception as e:
            print(f"   ⚠️ Could not load comprehensive credit data: {e}")
        
        # Combine credit data (now without duplicates)
        if credit_data:
            credit_tensor = pd.concat(credit_data, axis=1, sort=True)
            credit_tensor = credit_tensor.ffill().fillna(0)
            print(f"   📊 Credit tensor shape: {credit_tensor.shape}")
            print(f"   📊 Total unique columns: {len(used_columns)}")
            return credit_tensor
        
        return pd.DataFrame()
    
    def build_flow_forces(self):
        """Build liquidity and flow forces from sector flows data"""
        
        print("💧 Building flow forces...")
        
        flow_data = []
        
        # 1. Sector flows (your actual data)
        flows_df = self.load_and_resample(self.paths['flows'], {
            'capital_flow': 'sector_capital_flow',
            'flow_strength': 'sector_flow_strength',
            'flow_10d': 'sector_flow_10d',
            'flow_30d': 'sector_flow_30d'
        }, date_col='Date')
        
        if not flows_df.empty:
            # Aggregate sector flows to market-level flows
            if 'sector_capital_flow' in flows_df.columns:
                # Group by date and aggregate
                market_flows = flows_df.groupby(flows_df.index).agg({
                    'sector_capital_flow': 'sum',
                    'sector_flow_strength': 'mean',
                    'sector_flow_10d': 'sum',
                    'sector_flow_30d': 'sum'
                })
                
                # Rename for clarity
                market_flows = market_flows.rename(columns={
                    'sector_capital_flow': 'market_capital_flow',
                    'sector_flow_strength': 'avg_flow_strength',
                    'sector_flow_10d': 'market_flow_10d',
                    'sector_flow_30d': 'market_flow_30d'
                })
                
                flow_data.append(market_flows)
                print(f"   ✅ Sector flow data: {len(market_flows)} periods")
            else:
                print("   ⚠️ Sector flows data missing expected columns")
        else:
            print("   ⚠️ No sector flow data found - flow forces unavailable")
        
        # 2. FX and reserves (if available in the future)
        # This would be added when FX reserve data becomes available
        
        # Combine flow data
        if flow_data:
            flow_tensor = pd.concat(flow_data, axis=1, sort=True)
            flow_tensor = flow_tensor.ffill().fillna(0)
            print(f"   📊 Flow tensor shape: {flow_tensor.shape}")
            return flow_tensor
        
        return pd.DataFrame()
    
    def build_market_structure_forces(self):
        """Build market structure and health forces"""
        
        print("🏗️ Building market structure forces...")
        
        structure_data = []
        
        # 1. Market data from options pipeline
        try:
            with open(self.paths['market_data'], 'r') as f:
                market_json = json.load(f)
            
            # Extract market health metrics
            if 'market_health' in market_json:
                health = market_json['market_health']
                
                # Create single-row DataFrame for latest data
                latest_date = pd.Timestamp.now().normalize()
                health_df = pd.DataFrame({
                    'breadth_pct': [health.get('breadth_pct', 50)],
                    'participation_score': [health.get('participation_score', 0.5)],
                    'correlation': [health.get('correlation', 0.5)],
                    'volatility_regime': [1 if health.get('volatility_regime') == 'high' else 0]
                }, index=[latest_date])
                
                structure_data.append(health_df)
                print(f"   ✅ Market health data loaded")
        except Exception as e:
            print(f"   ⚠️ Could not load market health data: {e}")
        
        # 2. NIFTY Data (try to create from existing data if not available)
        nifty_df = self.load_and_resample(self.paths['nifty'], {
            'Close': 'nifty_close',
            'Volume': 'nifty_volume'
        })
        
        if not nifty_df.empty:
            # Calculate structure metrics
            if 'close' in nifty_df.columns:
                nifty_df['nifty_return'] = nifty_df['close'].pct_change()
                nifty_df['nifty_volatility'] = nifty_df['nifty_return'].rolling(12).std()
                
                # Remove price level, keep only derived metrics
                structure_metrics = nifty_df[['nifty_return', 'nifty_volatility']].copy()
                structure_data.append(structure_metrics)
                print(f"   ✅ NIFTY structure metrics: {len(structure_metrics)} periods")
            else:
                print(f"   ⚠️ NIFTY data missing 'close' column, available: {list(nifty_df.columns)}")
        else:
            # Try to create NIFTY proxy from consolidated price data
            try:
                prices_df = pd.read_parquet(self.paths['prices'])
                if not prices_df.empty and 'ticker' in prices_df.columns:
                    # Create market index from top stocks
                    price_pivot = prices_df.pivot_table(
                        index='Date',
                        columns='ticker', 
                        values='Close',
                        aggfunc='last'
                    )
                    
                    # Calculate equal-weighted market return as NIFTY proxy
                    market_returns = price_pivot.pct_change().mean(axis=1)
                    market_returns.index = pd.to_datetime(market_returns.index)
                    market_returns = market_returns.resample(self.config['resample_freq']).last()
                    
                    nifty_proxy = pd.DataFrame({
                        'nifty_return': market_returns,
                        'nifty_volatility': market_returns.rolling(12).std()
                    })
                    
                    structure_data.append(nifty_proxy)
                    print(f"   ✅ NIFTY proxy from stock data: {len(nifty_proxy)} periods")
                    
            except Exception as e:
                print(f"   ⚠️ Could not create NIFTY proxy: {e}")
        
        # 3. No synthetic structure data - only use real data
        if not structure_data:
            print("   ⚠️ No structure data found - market structure forces unavailable")
        
        # Combine structure data
        if structure_data:
            structure_tensor = pd.concat(structure_data, axis=1, sort=True)
            structure_tensor = structure_tensor.ffill().fillna(0)
            print(f"   📊 Structure tensor shape: {structure_tensor.shape}")
            return structure_tensor
        
        return pd.DataFrame()
    
    def build_sector_forces(self):
        """Build sector rotation and strength forces from sector flows data"""
        
        print("🏭 Building sector forces...")
        
        sector_data = []
        
        # Load sector flows data (your actual data)
        try:
            sector_flows_df = self.load_and_resample(self.paths['sectors'], {
                'relative_performance': 'relative_performance',
                'volume_growth': 'volume_growth', 
                'trend_strength': 'trend_strength',
                'northstar_score': 'northstar_score',
                'volatility': 'volatility',
                'relative_return': 'relative_return'
            }, date_col='Date')
            
            if not sector_flows_df.empty:
                # Pivot by industry to get sector-specific columns
                if 'Industry' in pd.read_parquet(self.paths['sectors']).columns:
                    # Load raw data to get industry info
                    raw_sector_data = pd.read_parquet(self.paths['sectors'])
                    
                    # Create pivot table for each metric
                    metrics = ['relative_performance', 'trend_strength', 'northstar_score', 'volatility']
                    
                    for metric in metrics:
                        if metric in raw_sector_data.columns:
                            pivot_data = raw_sector_data.pivot_table(
                                index='Date', 
                                columns='Industry', 
                                values=metric,
                                aggfunc='mean'
                            )
                            
                            # Rename columns to include metric name
                            pivot_data.columns = [f"{col}_{metric}" for col in pivot_data.columns]
                            
                            # Resample to weekly
                            pivot_data.index = pd.to_datetime(pivot_data.index)
                            pivot_data = pivot_data.resample(self.config['resample_freq']).last()
                            
                            sector_data.append(pivot_data)
                
                if sector_data:
                    print(f"   ✅ Loaded sector data with {len(sector_data)} metrics")
                else:
                    print("   ⚠️ Could not pivot sector data")
            else:
                print("   ⚠️ Sector flows data is empty")
                
        except Exception as e:
            print(f"   ⚠️ Error loading sector data: {e}")
        
        # No synthetic sector data - only use real data
        if not sector_data:
            print("   ⚠️ No sector data found - sector forces unavailable")
        
        # Combine sector data
        if sector_data:
            sector_tensor = pd.concat(sector_data, axis=1, sort=True)
            sector_tensor = sector_tensor.ffill().fillna(0)
            print(f"   📊 Sector tensor shape: {sector_tensor.shape}")
            return sector_tensor
        
        return pd.DataFrame()
    
    def build_corporate_forces(self):
        """Build corporate system forces from consolidated price data"""
        
        print("🏢 Building corporate forces...")
        
        # Try consolidated price data first
        try:
            prices_df = pd.read_parquet(self.paths['prices'])
            
            if not prices_df.empty and 'ticker' in prices_df.columns and 'Close' in prices_df.columns:
                print(f"   📊 Loaded consolidated price data: {len(prices_df)} records")
                
                # Pivot to get ticker columns
                price_pivot = prices_df.pivot_table(
                    index='Date',
                    columns='ticker', 
                    values='Close',
                    aggfunc='last'
                )
                
                # Calculate returns
                returns_df = price_pivot.pct_change().dropna()
                
                # Resample to weekly
                returns_df.index = pd.to_datetime(returns_df.index)
                returns_df = returns_df.resample(self.config['resample_freq']).last()
                
                print(f"   📈 Processed returns for {len(returns_df.columns)} stocks")
                
                # Apply PCA compression if we have enough stocks and time periods
                min_samples = min(len(returns_df), len(returns_df.columns))
                max_components = min(self.config['pca_components'], min_samples - 1)
                
                if len(returns_df.columns) > max_components and len(returns_df) > max_components and max_components > 0:
                    try:
                        scaler = StandardScaler()
                        returns_scaled = scaler.fit_transform(returns_df.fillna(0))
                        
                        pca = PCA(n_components=max_components)
                        corporate_factors = pca.fit_transform(returns_scaled)
                        
                        corporate_tensor = pd.DataFrame(
                            corporate_factors,
                            index=returns_df.index,
                            columns=[f'corp_factor_{i}' for i in range(max_components)]
                        )
                        
                        print(f"   🔬 PCA compression: {len(returns_df.columns)} → {max_components} factors")
                        print(f"   📊 Explained variance: {pca.explained_variance_ratio_.sum():.3f}")
                        
                        return corporate_tensor
                        
                    except Exception as e:
                        print(f"   ⚠️ PCA failed: {e}, using raw returns")
                        # Use top stocks by volume/activity
                        max_stocks = min(len(returns_df.columns), max_components)
                        top_stocks = returns_df.iloc[:, :max_stocks]
                        return top_stocks
                else:
                    print(f"   📊 Using all {len(returns_df.columns)} stocks (insufficient data for PCA: min_samples={min_samples}, max_components={max_components})")
                    return returns_df
                    
        except Exception as e:
            print(f"   ⚠️ Error with consolidated price data: {e}")
        
        # Fallback to individual stock files
        print("   🔄 Falling back to individual stock files...")
        stock_files = glob.glob(os.path.join(self.paths['prices_daily'], '*.csv'))
        
        if not stock_files:
            print("   ⚠️ No stock price files found - corporate forces unavailable")
            return pd.DataFrame()
        
        # Load and process stock returns (limit for performance)
        stock_returns = []
        processed_count = 0
        
        for file_path in stock_files[:100]:  # Limit to first 100 stocks for performance
            try:
                ticker = os.path.basename(file_path).replace('.csv', '')
                
                stock_df = self.load_and_resample(file_path, {
                    'Close': 'close'
                })
                
                if not stock_df.empty and len(stock_df) > self.config['min_data_points']:
                    stock_df['return'] = stock_df['close'].pct_change()
                    stock_returns.append(stock_df[['return']].rename(columns={'return': ticker}))
                    processed_count += 1
                    
                    if processed_count >= 50:  # Process at least 50 stocks
                        break
                        
            except Exception as e:
                continue
        
        if not stock_returns:
            print("   ⚠️ Could not process stock data - corporate forces unavailable")
            return pd.DataFrame()
        
        # Combine stock returns
        returns_matrix = pd.concat(stock_returns, axis=1, sort=True)
        returns_matrix = returns_matrix.fillna(0)
        
        print(f"   📈 Processed {processed_count} stocks from individual files")
        
        # Apply PCA compression
        min_samples = min(len(returns_matrix), len(returns_matrix.columns))
        max_components = min(self.config['pca_components'], min_samples - 1)
        
        if len(returns_matrix.columns) > max_components and max_components > 0:
            try:
                scaler = StandardScaler()
                returns_scaled = scaler.fit_transform(returns_matrix.fillna(0))
                
                pca = PCA(n_components=max_components)
                corporate_factors = pca.fit_transform(returns_scaled)
                
                corporate_tensor = pd.DataFrame(
                    corporate_factors,
                    index=returns_matrix.index,
                    columns=[f'corp_factor_{i}' for i in range(max_components)]
                )
                
                print(f"   🔬 PCA compression: {len(returns_matrix.columns)} → {max_components} factors")
                print(f"   📊 Explained variance: {pca.explained_variance_ratio_.sum():.3f}")
                
            except Exception as e:
                print(f"   ⚠️ PCA failed: {e}, using raw returns")
                corporate_tensor = returns_matrix.iloc[:, :max_components] if max_components > 0 else returns_matrix
        else:
            corporate_tensor = returns_matrix
        
        print(f"   📊 Corporate tensor shape: {corporate_tensor.shape}")
        return corporate_tensor
    
    def build_market_tensor(self):
        """Build complete market tensor from all components"""
        
        print("🧠 BUILDING COMPLETE MARKET TENSOR")
        print("=" * 60)
        
        # Build all tensor components
        components = {}
        
        components['monetary'] = self.build_monetary_forces()
        components['credit'] = self.build_credit_forces()
        components['flows'] = self.build_flow_forces()
        components['structure'] = self.build_market_structure_forces()
        components['sectors'] = self.build_sector_forces()
        components['corporate'] = self.build_corporate_forces()
        
        # Filter out empty components
        valid_components = {k: v for k, v in components.items() if not v.empty}
        
        if not valid_components:
            print("❌ No valid tensor components found")
            return pd.DataFrame()
        
        print(f"\n📊 Valid components: {list(valid_components.keys())}")
        
        # Combine all components with proper alignment
        print("\n🔗 Combining tensor components...")
        
        if not valid_components:
            print("❌ No valid tensor components found")
            return pd.DataFrame()
        
        # Find the common date range across all components
        date_ranges = []
        for name, component in valid_components.items():
            if not component.empty:
                date_ranges.append((component.index.min(), component.index.max()))
                print(f"   📅 {name}: {component.index.min().date()} to {component.index.max().date()} ({len(component)} periods)")
        
        if not date_ranges:
            print("❌ No valid date ranges found")
            return pd.DataFrame()
        
        # Instead of finding common range, use the longest available range and forward-fill
        # This allows components with different date ranges to contribute
        all_dates = set()
        for name, component in valid_components.items():
            if not component.empty:
                all_dates.update(component.index)
        
        if not all_dates:
            print("❌ No valid dates found across components")
            return pd.DataFrame()
        
        # Create full date range
        full_date_range = pd.date_range(min(all_dates), max(all_dates), freq=self.config['resample_freq'])
        print(f"   📅 Full date range: {min(all_dates).date()} to {max(all_dates).date()} ({len(full_date_range)} periods)")
        
        # Align all components to full date range with forward fill
        aligned_components = {}
        for name, component in valid_components.items():
            if not component.empty:
                try:
                    # Ensure all columns in component are Series
                    for col in list(component.columns):
                        try:
                            if isinstance(component[col], pd.DataFrame):
                                component[col] = component[col].iloc[:, 0] if not component[col].empty else pd.Series(dtype=float, index=component.index)
                            
                            # Ensure proper Series structure and handle multi-dimensional data
                            if not isinstance(component[col], pd.Series):
                                # If it's a numpy array, flatten it
                                if isinstance(component[col], np.ndarray):
                                    if component[col].ndim > 1:
                                        # Take the first column if multi-dimensional
                                        component[col] = component[col][:, 0] if component[col].shape[1] > 0 else component[col].flatten()
                                    component[col] = pd.Series(component[col], index=component.index)
                                else:
                                    component[col] = pd.Series(component[col], index=component.index)
                            
                            # Ensure the Series has the correct index and is truly 1-dimensional
                            if len(component[col]) != len(component.index):
                                # Truncate or extend to match index
                                if len(component[col]) > len(component.index):
                                    component[col] = component[col][:len(component.index)]
                                else:
                                    # Extend with NaN
                                    extended_values = np.full(len(component.index), np.nan)
                                    extended_values[:len(component[col])] = component[col].values
                                    component[col] = pd.Series(extended_values, index=component.index)
                            
                            # Final check: ensure it's truly 1-dimensional
                            if hasattr(component[col], 'values') and component[col].values.ndim > 1:
                                # If still multi-dimensional, take the first column
                                component[col] = pd.Series(component[col].values[:, 0], index=component.index)
                        except Exception as e:
                            print(f"      ⚠️ Issue with column {col} in {name}: {e}")
                            # Remove problematic column
                            try:
                                component = component.drop(columns=[col])
                            except:
                                pass
                    
                    # Reindex to full range and forward fill
                    aligned = component.reindex(full_date_range, method='nearest')
                    aligned = aligned.ffill().bfill().fillna(0)
                    
                    # Only keep if we have some real data (not all NaN)
                    if not aligned.isna().all().all():
                        aligned_components[name] = aligned
                        real_data_points = (~component.isna().all(axis=1)).sum()
                        print(f"   ✅ {name}: {len(aligned)} periods ({real_data_points} with real data)")
                    else:
                        print(f"   ⚠️ {name}: All data is NaN after alignment")
                except Exception as e:
                    print(f"   ⚠️ Error aligning {name}: {e}")
                    continue
        
        if not aligned_components:
            print("❌ No components have valid data after alignment")
            return pd.DataFrame()
        
        # Combine aligned components with comprehensive duplicate prevention
        print("   🔗 Combining tensor components with duplicate prevention...")
        
        # Collect all components with their column tracking
        all_components = []
        all_used_columns = set()
        
        for name, component in aligned_components.items():
            if not component.empty:
                # Check for and resolve any duplicate columns before adding
                clean_component = component.copy()
                columns_to_rename = {}
                
                for col in clean_component.columns:
                    if col in all_used_columns:
                        # Generate unique name
                        base_name = col
                        counter = 1
                        new_name = f"{base_name}_dup_{counter}"
                        while new_name in all_used_columns:
                            counter += 1
                            new_name = f"{base_name}_dup_{counter}"
                        columns_to_rename[col] = new_name
                        print(f"      🔄 Renaming duplicate column: {col} → {new_name}")
                
                # Apply renames
                if columns_to_rename:
                    clean_component = clean_component.rename(columns=columns_to_rename)
                
                # Track all columns
                all_used_columns.update(clean_component.columns)
                all_components.append(clean_component)
                
                print(f"   ✅ {name}: {len(clean_component.columns)} unique columns")
        
        if not all_components:
            print("❌ No valid components to combine")
            return pd.DataFrame()
        
        # Now concatenate with no duplicate columns
        market_tensor = pd.concat(all_components, axis=1, sort=True)
        print(f"   📊 Combined tensor shape: {market_tensor.shape}")
        
        # Verify no multi-dimensional columns exist
        multi_dim_cols = []
        for col in market_tensor.columns:
            if hasattr(market_tensor[col], 'values') and market_tensor[col].values.ndim > 1:
                multi_dim_cols.append(col)
        
        if multi_dim_cols:
            print(f"   ⚠️ Found {len(multi_dim_cols)} multi-dimensional columns after concatenation - removing them")
            market_tensor = market_tensor.drop(columns=multi_dim_cols)
        else:
            print("   ✅ No multi-dimensional columns detected after concatenation")
        
        # Handle missing values
        market_tensor = market_tensor.ffill().bfill().fillna(0)
        
        # Remove any remaining infinite values
        market_tensor = market_tensor.replace([np.inf, -np.inf], 0)
        
        # Ensure all data is numeric and properly formatted
        market_tensor = market_tensor.select_dtypes(include=[np.number])
        
        # Convert any remaining object columns to numeric
        for col in list(market_tensor.columns):  # Convert to list to avoid iteration issues
            try:
                # Check if column exists and is a Series (not DataFrame)
                if col in market_tensor.columns:
                    column_data = market_tensor[col]
                    
                    # Ensure we're working with a Series, not DataFrame
                    if isinstance(column_data, pd.DataFrame):
                        # If it's a DataFrame, take the first column
                        column_data = column_data.iloc[:, 0] if not column_data.empty else pd.Series(dtype=float, index=market_tensor.index)
                        market_tensor[col] = column_data
                    
                    # Ensure it's a proper Series with correct index and 1-dimensional
                    if not isinstance(market_tensor[col], pd.Series):
                        # Convert to Series if it's not already
                        market_tensor[col] = pd.Series(market_tensor[col], index=market_tensor.index)
                    
                    # Final check: ensure it's truly 1-dimensional
                    if hasattr(market_tensor[col], 'values') and market_tensor[col].values.ndim > 1:
                        # If still multi-dimensional, take the first column
                        market_tensor[col] = pd.Series(market_tensor[col].values[:, 0], index=market_tensor.index)
                    
                    # Now check if it's numeric and convert if needed
                    if not pd.api.types.is_numeric_dtype(market_tensor[col]):
                        # Convert to numeric, handling any remaining issues
                        numeric_values = pd.to_numeric(market_tensor[col], errors='coerce')
                        market_tensor[col] = numeric_values
            except Exception as e:
                print(f"   ⚠️ Could not process column {col}: {e}")
                # Remove problematic column
                try:
                    market_tensor = market_tensor.drop(columns=[col])
                except:
                    pass
                continue
        
        # Remove any remaining NaN values
        market_tensor = market_tensor.fillna(0)
        
        # Remove any columns that are all zeros (no useful information)
        non_zero_cols = []
        for col in market_tensor.columns:
            if market_tensor[col].abs().sum() > 0:  # Keep columns with some non-zero values
                non_zero_cols.append(col)
        
        if len(non_zero_cols) < len(market_tensor.columns):
            removed_count = len(market_tensor.columns) - len(non_zero_cols)
            market_tensor = market_tensor[non_zero_cols]
            print(f"   🧹 Removed {removed_count} zero-only columns")
        
        # Ensure we have reasonable data - no synthetic extension
        if len(market_tensor) < 10:
            print("⚠️ Insufficient data points - Market Brain requires more historical data")
            print(f"   Current: {len(market_tensor)} periods, minimum recommended: 50+ periods")
            # Don't extend with synthetic data - return what we have
        
        print(f"\n✅ Market tensor built successfully!")
        print(f"   Shape: {market_tensor.shape}")
        print(f"   Date range: {market_tensor.index[0].date()} to {market_tensor.index[-1].date()}")
        print(f"   Variables: {len(market_tensor.columns)}")
        
        # Save tensor and metadata
        self.save_market_tensor(market_tensor, valid_components)
        
        return market_tensor
    
    def save_market_tensor(self, tensor, components_info):
        """Save market tensor and metadata"""
        
        # Create output directory
        os.makedirs(os.path.dirname(self.paths['output']), exist_ok=True)
        
        tensor_to_save = tensor.copy()
        if "date" in tensor_to_save.columns:
            tensor_to_save = tensor_to_save.drop(columns=["date"])
        if "Date" in tensor_to_save.columns:
            tensor_to_save = tensor_to_save.drop(columns=["Date"])

        date_idx = pd.to_datetime(tensor_to_save.index, errors="coerce")
        if date_idx.tz is not None:
            date_idx = date_idx.tz_localize(None)
        valid_dates = ~date_idx.isna()
        tensor_to_save = tensor_to_save.loc[valid_dates].copy()
        tensor_to_save.insert(0, "date", pd.DatetimeIndex(date_idx[valid_dates]))

        # Save tensor with canonical explicit date column
        tensor_to_save.to_parquet(self.paths['output'])
        print(f"💾 Saved market tensor: {self.paths['output']}")
        
        # Save metadata
        metadata = {
            'created_at': datetime.now().isoformat(),
            'version': self.version,
            'shape': list(tensor.shape),
            'date_range': {
                'start': tensor.index[0].isoformat(),
                'end': tensor.index[-1].isoformat()
            },
            'components': {
                name: {
                    'variables': len(df.columns),
                    'weight': self.component_weights.get(name, 0.1)
                }
                for name, df in components_info.items()
            },
            'config': self.config,
            'column_names': list(tensor.columns)
        }
        
        with open(self.paths['metadata'], 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"📋 Saved metadata: {self.paths['metadata']}")
    
    def load_market_tensor(self):
        """Load existing market tensor"""
        
        try:
            if os.path.exists(self.paths['output']):
                tensor = pd.read_parquet(self.paths['output'])
                tensor = self.canonicalize_tensor_frame(tensor)
                print(f"📊 Loaded market tensor: {tensor.shape}")
                return tensor
        except Exception as e:
            print(f"⚠️ Could not load market tensor: {e}")
        
        return pd.DataFrame()
    
    def get_latest_tensor_state(self):
        """Get latest market tensor state for real-time use"""
        
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            return {}
        
        latest = tensor.iloc[-1]
        
        return {
            'date': latest.name.isoformat(),
            'tensor_state': latest.to_dict(),
            'shape': list(tensor.shape),
            'components_summary': self.summarize_tensor_components(latest)
        }
    
    def summarize_tensor_components(self, tensor_row):
        """Summarize tensor components for interpretation"""
        
        summary = {}
        
        # Group variables by component type
        for component, weight in self.component_weights.items():
            component_vars = [col for col in tensor_row.index if component in col.lower()]
            
            if component_vars:
                component_values = tensor_row[component_vars]
                summary[component] = {
                    'mean': float(component_values.mean()),
                    'std': float(component_values.std()),
                    'variables': len(component_vars),
                    'weight': weight
                }
        
        return summary

def main():
    """Build market tensor"""
    
    engine = MarketTensorEngine()
    tensor = engine.build_market_tensor()
    
    if not tensor.empty:
        print(f"\n🎯 Market tensor ready for causal analysis!")
        print(f"   Next step: Build causal graph from this tensor")
        return True
    else:
        print("❌ Failed to build market tensor")
        return False

if __name__ == "__main__":
    main()
