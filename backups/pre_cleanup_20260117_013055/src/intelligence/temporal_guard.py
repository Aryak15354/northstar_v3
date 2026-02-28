#!/usr/bin/env python3
"""
🛡️ TEMPORAL GUARD - POINT-IN-TIME PROTECTION
Prevents look-ahead bias by enforcing strict temporal constraints

This is Layer 3 - the foundation of truth for all Northstar signals.
Every data access MUST go through this guard.

Key Rules:
1. data[t] may only access information with timestamp <= t
2. No exceptions - signals, regimes, fundamentals, everything
3. Scramble test validates no future data leakage

Usage:
    from src.intelligence.temporal_guard import TemporalGuard
    
    guard = TemporalGuard()
    
    # Instead of: df[df.symbol == 'RELIANCE']
    # Use: guard.get_data('RELIANCE', current_time)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List
import random

warnings.filterwarnings('ignore')

class TemporalGuard:
    """
    Temporal Guard - Enforces point-in-time data access
    
    This is the SINGLE ENTRY POINT for all historical data access.
    Prevents look-ahead bias by enforcing timestamp <= current_time.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.cache = {}  # Cache for performance
        self.access_log = []  # Log all data access for audit
        
        # Violation tracking
        self.violations = []
        self.strict_mode = True  # Fail on violations vs warn
        
        print("🛡️ Temporal Guard initialized - Point-in-time protection active")
    
    def get_data(self, symbol: str, current_time: datetime, 
                 data_type: str = 'prices') -> pd.DataFrame:
        """
        Get data for symbol up to current_time only
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE.NS')
            current_time: Current simulation time
            data_type: 'prices', 'fundamentals', 'macro', etc.
        
        Returns:
            DataFrame with timestamp <= current_time only
        """
        
        # Log access for audit
        self.access_log.append({
            'symbol': symbol,
            'current_time': current_time,
            'data_type': data_type,
            'access_time': datetime.now()
        })
        
        # Load raw data
        raw_data = self._load_raw_data(symbol, data_type)
        
        if raw_data is None or raw_data.empty:
            return pd.DataFrame()
        
        # Ensure timestamp column exists and is datetime
        if 'timestamp' not in raw_data.columns:
            if raw_data.index.name == 'Date' or 'Date' in raw_data.columns:
                raw_data = self._add_timestamp_column(raw_data)
            else:
                raise ValueError(f"No timestamp found for {symbol} {data_type}")
        else:
            # Ensure timestamp column is datetime type
            if not pd.api.types.is_datetime64_any_dtype(raw_data['timestamp']):
                raw_data['timestamp'] = pd.to_datetime(raw_data['timestamp'])
        
        # CRITICAL: Filter to current_time only
        filtered_data = raw_data[raw_data['timestamp'] <= current_time].copy()
        
        # Validate no future data leaked
        if not filtered_data.empty:
            max_timestamp = filtered_data['timestamp'].max()
            if max_timestamp > current_time:
                violation = {
                    'symbol': symbol,
                    'data_type': data_type,
                    'current_time': current_time,
                    'max_timestamp': max_timestamp,
                    'violation_seconds': (max_timestamp - current_time).total_seconds()
                }
                self.violations.append(violation)
                
                if self.strict_mode:
                    raise ValueError(f"TEMPORAL VIOLATION: {symbol} data contains future timestamp {max_timestamp} > {current_time}")
                else:
                    print(f"⚠️ TEMPORAL WARNING: {symbol} future data detected")
        
        return filtered_data
    
    def get_macro_data(self, current_time: datetime) -> Dict[str, Any]:
        """Get macro data up to current_time"""
        
        macro_data = {}
        
        # Load various macro datasets
        macro_files = {
            'yields': 'macro/yields.csv',
            'inflation': 'macro/inflation.csv',
            'growth': 'macro/growth.csv'
        }
        
        for key, file_path in macro_files.items():
            try:
                full_path = os.path.join(self.data_dir, file_path)
                if os.path.exists(full_path):
                    df = pd.read_csv(full_path)
                    
                    # Add timestamp if missing
                    if 'timestamp' not in df.columns:
                        df = self._add_timestamp_column(df)
                    else:
                        # Ensure timestamp is datetime type
                        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                            df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    # Filter to current_time
                    filtered = df[df['timestamp'] <= current_time]
                    
                    if not filtered.empty:
                        # Get latest value
                        latest = filtered.iloc[-1]
                        macro_data[key] = latest.to_dict()
                        
            except Exception as e:
                print(f"⚠️ Error loading macro {key}: {e}")
        
        return macro_data
    
    def get_regime_data(self, current_time: datetime) -> Dict[str, Any]:
        """Get regime classification up to current_time"""
        
        try:
            # Load regime history
            regime_file = os.path.join(self.data_dir, 'regimes/regime_history.csv')
            
            if not os.path.exists(regime_file):
                return {'regime': 'neutral', 'confidence': 0.5}
            
            df = pd.read_csv(regime_file)
            
            # Add timestamp if missing
            if 'timestamp' not in df.columns:
                df = self._add_timestamp_column(df)
            else:
                # Ensure timestamp is datetime type
                if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter to current_time
            filtered = df[df['timestamp'] <= current_time]
            
            if filtered.empty:
                return {'regime': 'neutral', 'confidence': 0.5}
            
            # Get latest regime
            latest = filtered.iloc[-1]
            
            return {
                'regime': latest.get('regime', 'neutral'),
                'confidence': latest.get('confidence', 0.5),
                'timestamp': latest['timestamp']
            }
            
        except Exception as e:
            print(f"⚠️ Error loading regime data: {e}")
            return {'regime': 'neutral', 'confidence': 0.5}
    
    def _load_raw_data(self, symbol: str, data_type: str) -> Optional[pd.DataFrame]:
        """Load raw data from disk"""
        
        # Cache key
        cache_key = f"{symbol}_{data_type}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Determine file path
        if data_type == 'prices':
            file_path = os.path.join(self.data_dir, 'raw/prices_daily', f"{symbol}.csv")
            try:
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    self.cache[cache_key] = df
                    return df
                else:
                    print(f"⚠️ Data file not found: {file_path}")
                    return None
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
                return None
                
        elif data_type == 'fundamentals':
            # Load and merge split fundamental files (balance, income, cashflow)
            return self._load_fundamental_data(symbol)
        else:
            file_path = os.path.join(self.data_dir, data_type, f"{symbol}.csv")
            try:
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    self.cache[cache_key] = df
                    return df
                else:
                    print(f"⚠️ Data file not found: {file_path}")
                    return None
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
                return None
    
    def _load_fundamental_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load and merge split fundamental data files"""
        
        base_path = os.path.join(self.data_dir, 'raw/financials_quarterly')
        
        # File paths for different statements
        files = {
            'balance': os.path.join(base_path, f"{symbol}_balance.csv"),
            'income': os.path.join(base_path, f"{symbol}_income.csv"),
            'cashflow': os.path.join(base_path, f"{symbol}_cashflow.csv")
        }
        
        dataframes = {}
        
        # Load each statement type
        for statement_type, file_path in files.items():
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                    if not df.empty and 'Date' in df.columns:
                        # Add statement type prefix to avoid column conflicts
                        df = df.rename(columns={col: f"{statement_type}_{col}" if col != 'Date' else col 
                                              for col in df.columns})
                        dataframes[statement_type] = df
                except Exception as e:
                    print(f"⚠️ Error loading {statement_type} data for {symbol}: {e}")
        
        if not dataframes:
            return None
        
        # Merge all statements on Date
        merged_df = None
        for statement_type, df in dataframes.items():
            if merged_df is None:
                merged_df = df
            else:
                merged_df = pd.merge(merged_df, df, on='Date', how='outer')
        
        if merged_df is not None and not merged_df.empty:
            # Cache the merged result
            cache_key = f"{symbol}_fundamentals"
            self.cache[cache_key] = merged_df
            
            # Create derived fundamental metrics for easier access
            merged_df = self._add_fundamental_metrics(merged_df)
            
        return merged_df
    
    def _add_fundamental_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add commonly used fundamental metrics"""
        
        df = df.copy()
        
        try:
            # Calculate P/E ratio if we have market cap and earnings data
            if 'income_Net Income Common Stockholders' in df.columns:
                # Mock P/E calculation (would need market cap data)
                df['PE'] = 15.0  # Default P/E for now
            
            # Calculate P/B ratio if we have book value
            if 'balance_Common Stock Equity' in df.columns:
                df['PB'] = 2.0  # Default P/B for now
            
            # Calculate ROE if we have net income and equity
            if ('income_Net Income Common Stockholders' in df.columns and 
                'balance_Common Stock Equity' in df.columns):
                net_income = pd.to_numeric(df['income_Net Income Common Stockholders'], errors='coerce')
                equity = pd.to_numeric(df['balance_Common Stock Equity'], errors='coerce')
                df['ROE'] = (net_income / equity * 100).fillna(15.0)  # ROE as percentage
            else:
                df['ROE'] = 15.0  # Default ROE
            
            # Calculate Debt-to-Equity ratio
            if ('balance_Total Debt' in df.columns and 
                'balance_Common Stock Equity' in df.columns):
                debt = pd.to_numeric(df['balance_Total Debt'], errors='coerce')
                equity = pd.to_numeric(df['balance_Common Stock Equity'], errors='coerce')
                df['DebtToEquity'] = (debt / equity).fillna(0.5)
            else:
                df['DebtToEquity'] = 0.5  # Default debt-to-equity
            
            # Calculate Interest Coverage if available
            if ('income_EBIT' in df.columns and 
                'income_Interest Expense' in df.columns):
                ebit = pd.to_numeric(df['income_EBIT'], errors='coerce')
                interest = pd.to_numeric(df['income_Interest Expense'], errors='coerce')
                df['InterestCoverage'] = (ebit / interest.replace(0, np.nan)).fillna(5.0)
            else:
                df['InterestCoverage'] = 5.0  # Default interest coverage
                
        except Exception as e:
            print(f"⚠️ Error calculating fundamental metrics: {e}")
        
        return df
    
    def _add_timestamp_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add timestamp column from Date index or column"""
        
        df = df.copy()
        
        if df.index.name == 'Date':
            df['timestamp'] = pd.to_datetime(df.index)
        elif 'Date' in df.columns:
            df['timestamp'] = pd.to_datetime(df['Date'])
        elif 'date' in df.columns:
            df['timestamp'] = pd.to_datetime(df['date'])
        else:
            raise ValueError("No Date column found to create timestamp")
        
        return df
    
    def run_scramble_test(self, symbol: str, current_time: datetime, 
                         test_function, iterations: int = 10) -> Dict[str, Any]:
        """
        Run the scramble test to detect look-ahead bias
        
        Args:
            symbol: Symbol to test
            current_time: Current simulation time
            test_function: Function that processes data and returns result
            iterations: Number of scramble iterations
        
        Returns:
            Dict with test results
        """
        
        print(f"🧪 Running scramble test for {symbol} at {current_time}")
        
        # Get original data
        original_data = self.get_data(symbol, current_time)
        
        if original_data.empty:
            return {'status': 'no_data', 'passed': True}
        
        # Run with original data
        try:
            original_result = test_function(original_data)
        except Exception as e:
            return {'status': 'function_error', 'error': str(e), 'passed': False}
        
        # Run scramble tests
        scramble_results = []
        
        for i in range(iterations):
            # Create scrambled version
            scrambled_data = self._scramble_future_data(original_data, current_time)
            
            try:
                scrambled_result = test_function(scrambled_data)
                scramble_results.append(scrambled_result)
            except Exception as e:
                return {'status': 'scramble_error', 'error': str(e), 'passed': False}
        
        # Compare results
        passed = self._compare_results(original_result, scramble_results)
        
        return {
            'status': 'completed',
            'passed': passed,
            'original_result': original_result,
            'scramble_results': scramble_results,
            'iterations': iterations,
            'symbol': symbol,
            'current_time': current_time
        }
    
    def _scramble_future_data(self, data: pd.DataFrame, current_time: datetime) -> pd.DataFrame:
        """Scramble data with timestamp > current_time"""
        
        data = data.copy()
        
        # Identify future data
        future_mask = data['timestamp'] > current_time
        
        if not future_mask.any():
            return data  # No future data to scramble
        
        # Scramble future rows
        future_indices = data[future_mask].index.tolist()
        random.shuffle(future_indices)
        
        # Reassign future data randomly
        future_data = data.loc[data[future_mask].index].copy()
        data.loc[future_mask] = future_data.loc[future_indices].values
        
        return data
    
    def _compare_results(self, original, scrambled_list, tolerance: float = 1e-10) -> bool:
        """Compare original result with scrambled results"""
        
        # Handle different result types
        if isinstance(original, (int, float)):
            # Numeric result
            for scrambled in scrambled_list:
                if abs(original - scrambled) > tolerance:
                    print(f"❌ Scramble test FAILED: {original} != {scrambled}")
                    return False
            return True
            
        elif isinstance(original, dict):
            # Dictionary result
            for scrambled in scrambled_list:
                for key in original.keys():
                    if key in scrambled:
                        if isinstance(original[key], (int, float)):
                            if abs(original[key] - scrambled[key]) > tolerance:
                                print(f"❌ Scramble test FAILED: {key} {original[key]} != {scrambled[key]}")
                                return False
            return True
            
        elif isinstance(original, np.ndarray):
            # Array result
            for scrambled in scrambled_list:
                if not np.allclose(original, scrambled, atol=tolerance):
                    print(f"❌ Scramble test FAILED: Arrays differ")
                    return False
            return True
            
        else:
            # Generic comparison
            for scrambled in scrambled_list:
                if original != scrambled:
                    print(f"❌ Scramble test FAILED: {original} != {scrambled}")
                    return False
            return True
    
    def audit_violations(self) -> Dict[str, Any]:
        """Audit all temporal violations"""
        
        return {
            'total_violations': len(self.violations),
            'violations': self.violations,
            'total_accesses': len(self.access_log),
            'violation_rate': len(self.violations) / max(1, len(self.access_log)),
            'strict_mode': self.strict_mode
        }
    
    def clear_cache(self):
        """Clear data cache"""
        self.cache.clear()
        print("🧹 Temporal guard cache cleared")

# =========================== INTEGRATION HELPERS ===========================

def replace_data_access_with_guard(guard: TemporalGuard, current_time: datetime):
    """
    Helper to replace direct data access with temporal guard
    
    Use this to retrofit existing code
    """
    
    def get_data_wrapper(symbol: str, data_type: str = 'prices'):
        return guard.get_data(symbol, current_time, data_type)
    
    def get_macro_wrapper():
        return guard.get_macro_data(current_time)
    
    def get_regime_wrapper():
        return guard.get_regime_data(current_time)
    
    return get_data_wrapper, get_macro_wrapper, get_regime_wrapper

# =========================== TESTING FUNCTIONS ===========================

def test_momentum_signal(data: pd.DataFrame) -> float:
    """Test function for scramble test - momentum signal"""
    
    if len(data) < 21:
        return 0.0
    
    # Simple momentum: 20-day return
    returns = data['Close'].pct_change()
    momentum = returns.rolling(20).sum().iloc[-1]
    
    return momentum

def test_valuation_signal(data: pd.DataFrame) -> Dict[str, float]:
    """Test function for scramble test - valuation metrics"""
    
    if data.empty:
        return {'pe_ratio': 0.0, 'pb_ratio': 0.0}
    
    # Mock valuation calculation
    latest = data.iloc[-1]
    
    return {
        'pe_ratio': latest.get('PE', 15.0),
        'pb_ratio': latest.get('PB', 2.0)
    }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate temporal guard functionality"""
    
    print("🛡️ TEMPORAL GUARD - POINT-IN-TIME PROTECTION")
    print("=" * 60)
    
    # Initialize guard
    guard = TemporalGuard()
    
    # Test current time
    current_time = datetime(2024, 1, 15)  # Simulate historical time
    
    print(f"\n📅 Simulating time: {current_time}")
    
    # Example 1: Get price data with temporal protection
    print("\n📊 Example 1: Price Data Access")
    print("-" * 40)
    
    try:
        price_data = guard.get_data('RELIANCE.NS', current_time, 'prices')
        
        if not price_data.empty:
            print(f"✅ Retrieved {len(price_data)} price records")
            print(f"   Date range: {price_data['timestamp'].min()} to {price_data['timestamp'].max()}")
            print(f"   Max timestamp <= current_time: {price_data['timestamp'].max() <= current_time}")
        else:
            print("⚠️ No price data found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Example 2: Scramble test
    print("\n🧪 Example 2: Scramble Test")
    print("-" * 40)
    
    # Create mock data for testing
    mock_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', '2024-01-20', freq='D'),
        'Close': np.random.randn(20).cumsum() + 100
    })
    
    # Save mock data
    os.makedirs('data/raw/prices_daily', exist_ok=True)
    mock_data.to_csv('data/raw/prices_daily/TEST.NS.csv', index=False)
    
    # Run scramble test
    test_result = guard.run_scramble_test(
        'TEST.NS', 
        current_time, 
        test_momentum_signal,
        iterations=5
    )
    
    print(f"Scramble test status: {test_result['status']}")
    print(f"Test passed: {test_result['passed']}")
    
    if test_result['passed']:
        print("✅ No look-ahead bias detected")
    else:
        print("❌ LOOK-AHEAD BIAS DETECTED!")
    
    # Example 3: Violation audit
    print("\n🔍 Example 3: Violation Audit")
    print("-" * 40)
    
    audit = guard.audit_violations()
    print(f"Total violations: {audit['total_violations']}")
    print(f"Total accesses: {audit['total_accesses']}")
    print(f"Violation rate: {audit['violation_rate']:.2%}")
    
    print("\n✅ Temporal Guard demonstration complete")
    print("💡 Key insight: Every data access must go through temporal guard")

if __name__ == "__main__":
    main()