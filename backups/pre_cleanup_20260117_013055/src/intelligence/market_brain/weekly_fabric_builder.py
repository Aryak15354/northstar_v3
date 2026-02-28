#!/usr/bin/env python3
"""
🧬 WEEKLY CAUSAL FABRIC BUILDER - NORTHSTAR V3 MARKET BRAIN
The Temporal Causality Engine: Learning Weekly Market Relationships

This builds the Weekly Causal Fabric that learns:
"What relationships quietly formed this week, that changed the next 6–12 months?"

This is the layer that turns Northstar from "very good" into unfair.

Integration with V3:
- Uses existing Market Tensor as input
- Processes one year at a time (52 weeks) for M1 safety
- Feeds discovered relationships back into existing systems
- Enhances Capital Allocator with anticipatory signals

Output: data/weekly_insights/{year}/week_{week}.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from sklearn.linear_model import LassoCV
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
import warnings
warnings.filterwarnings('ignore')

# Import existing V3 components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.intelligence.market_brain.market_tensor import MarketTensorEngine

class WeeklyFabricBuilder:
    """
    Weekly Causal Fabric Builder - Temporal Causality Learning
    
    Processes market tensor data to discover:
    - Weekly macro → sector → stock relationships
    - Emerging relationship patterns
    - Causal pressure changes over time
    - Anticipatory signals for regime transitions
    """
    
    def __init__(self):
        self.name = "Weekly Causal Fabric Builder"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'market_tensor': 'data/processed/market_tensor.parquet',
            'weekly_insights': 'data/weekly_insights',
            'fabric_metadata': 'data/weekly_insights/fabric_metadata.json',
            'relationship_summary': 'data/weekly_insights/relationship_summary.parquet'
        }
        
        # Fabric configuration
        self.config = {
            'min_weeks_per_year': 40,      # Minimum weeks needed to process a year
            'lookback_weeks': 4,           # Rolling context window
            'forward_horizons': [1, 4, 12], # 1, 4, 12 weeks forward prediction
            'min_relationship_strength': 0.15, # Minimum beta to consider significant
            'min_information_gain': 0.05,   # Minimum mutual information
            'min_confidence': 0.6,          # Minimum stability across windows
            'lasso_alpha_range': (0.001, 1.0), # LASSO regularization range
            'cv_folds': 5,                  # Cross-validation folds
            'novelty_window': 12,           # Weeks to look back for novelty calculation
            'stability_window': 4           # Weeks to assess relationship stability
        }
        
        # Variable categories for causal analysis
        self.variable_categories = {
            'macro': ['rbi_', 'repo', 'rate', 'cpi', 'wpi', 'inflation', 'growth'],
            'fx': ['usdinr', 'fx', 'currency', 'exchange'],
            'flows': ['fii', 'dii', 'flow', 'capital'],
            'credit': ['credit', 'loan', 'deposit', 'banking', 'yield'],
            'liquidity': ['liquidity', 'reserve', 'money', 'supply'],
            'sector': ['sector_', 'industry_', '_sector', '_industry'],
            'corporate': ['corp_factor_', 'stock_', 'equity_']
        }
        
        # Regime context mapping (from existing regime memory)
        self.regime_contexts = {
            0: 'Crisis',
            1: 'Recovery', 
            2: 'Expansion',
            3: 'Late_Expansion',
            4: 'Peak',
            5: 'Slowdown',
            6: 'Tightening',
            7: 'Neutral'
        }
    
    def load_market_tensor(self):
        """Load market tensor for fabric analysis"""
        
        try:
            if os.path.exists(self.paths['market_tensor']):
                tensor = pd.read_parquet(self.paths['market_tensor'])
                
                if tensor.empty:
                    print("⚠️ Market tensor is empty")
                    return pd.DataFrame()
                
                # Ensure weekly frequency
                if not tensor.index.freq:
                    # Infer frequency
                    tensor = tensor.asfreq('W')
                
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
    
    def categorize_variables(self, columns):
        """Categorize tensor variables by type"""
        
        categorized = {category: [] for category in self.variable_categories.keys()}
        uncategorized = []
        
        for col in columns:
            col_lower = col.lower()
            assigned = False
            
            for category, keywords in self.variable_categories.items():
                if any(keyword in col_lower for keyword in keywords):
                    categorized[category].append(col)
                    assigned = True
                    break
            
            if not assigned:
                uncategorized.append(col)
        
        # Log categorization
        for category, vars in categorized.items():
            if vars:
                print(f"   📊 {category}: {len(vars)} variables")
        
        if uncategorized:
            print(f"   ❓ Uncategorized: {len(uncategorized)} variables")
        
        return categorized, uncategorized
    
    def extract_year_data(self, tensor, year):
        """Extract weekly data for a specific year"""
        
        try:
            # Filter tensor for the specific year
            year_mask = tensor.index.year == year
            year_data = tensor[year_mask].copy()
            
            if year_data.empty:
                print(f"⚠️ No data found for year {year}")
                return pd.DataFrame()
            
            # Ensure we have enough weeks
            if len(year_data) < self.config['min_weeks_per_year']:
                print(f"⚠️ Insufficient data for {year}: {len(year_data)} weeks < {self.config['min_weeks_per_year']} required")
                return pd.DataFrame()
            
            print(f"📅 Extracted {year} data: {len(year_data)} weeks")
            print(f"   Range: {year_data.index[0].date()} to {year_data.index[-1].date()}")
            
            return year_data
            
        except Exception as e:
            print(f"❌ Error extracting {year} data: {e}")
            return pd.DataFrame()
    
    def compute_weekly_deltas(self, year_data):
        """Compute weekly changes for all variables"""
        
        try:
            # Calculate week-over-week changes
            deltas = year_data.pct_change().fillna(0)
            
            # Replace infinite values
            deltas = deltas.replace([np.inf, -np.inf], 0)
            
            # Add absolute change for some variables (like rates)
            rate_vars = [col for col in year_data.columns if any(term in col.lower() for term in ['rate', 'yield', 'repo'])]
            
            for var in rate_vars:
                if var in year_data.columns:
                    abs_change_col = f"{var}_abs_change"
                    deltas[abs_change_col] = year_data[var].diff().fillna(0)
            
            print(f"   📈 Computed deltas: {deltas.shape}")
            return deltas
            
        except Exception as e:
            print(f"❌ Error computing deltas: {e}")
            return pd.DataFrame()
    
    def compute_forward_returns(self, year_data, horizons):
        """Compute forward returns for different horizons"""
        
        try:
            forward_returns = {}
            
            # Identify return variables (sectors and corporate factors)
            return_vars = []
            for category in ['sector', 'corporate']:
                return_vars.extend(self.variable_categories.get(category, []))
            
            # Filter to existing columns
            return_vars = [var for var in return_vars if any(keyword in col.lower() for col in year_data.columns for keyword in [var.lower()])]
            actual_return_cols = []
            
            for col in year_data.columns:
                col_lower = col.lower()
                if any(term in col_lower for term in ['sector_', 'corp_factor_', 'return', 'performance']):
                    actual_return_cols.append(col)
            
            if not actual_return_cols:
                print("⚠️ No return variables found for forward return calculation")
                return {}
            
            print(f"   📊 Computing forward returns for {len(actual_return_cols)} variables")
            
            for horizon in horizons:
                horizon_returns = pd.DataFrame(index=year_data.index)
                
                for col in actual_return_cols:
                    # Calculate forward return
                    forward_col = f"{col}_fwd_{horizon}w"
                    
                    if 'return' in col.lower() or 'performance' in col.lower():
                        # Already a return series, just shift
                        horizon_returns[forward_col] = year_data[col].shift(-horizon)
                    else:
                        # Calculate return from price level
                        horizon_returns[forward_col] = year_data[col].pct_change(horizon).shift(-horizon)
                
                forward_returns[horizon] = horizon_returns.fillna(0)
                print(f"      {horizon}w: {forward_returns[horizon].shape[1]} forward return series")
            
            return forward_returns
            
        except Exception as e:
            print(f"❌ Error computing forward returns: {e}")
            return {}
    
    def detect_causal_relationships(self, deltas, forward_returns, week_idx, year, week_num):
        """Detect causal relationships for a specific week using LASSO + mutual information"""
        
        try:
            relationships = []
            
            # Get context window (current + lookback weeks)
            lookback = self.config['lookback_weeks']
            start_idx = max(0, week_idx - lookback)
            end_idx = week_idx + 1
            
            if end_idx - start_idx < 2:
                return relationships
            
            # Get predictor variables (deltas in context window)
            X_window = deltas.iloc[start_idx:end_idx]
            
            # Flatten context window into feature vector
            X_features = []
            feature_names = []
            
            for lag in range(len(X_window)):
                for col in X_window.columns:
                    X_features.append(X_window.iloc[lag][col])
                    feature_names.append(f"{col}_lag_{lag}")
            
            X = np.array(X_features).reshape(1, -1)
            
            if X.shape[1] == 0:
                return relationships
            
            # For each forward horizon
            for horizon in forward_returns.keys():
                horizon_data = forward_returns[horizon]
                
                if week_idx >= len(horizon_data):
                    continue
                
                # For each target variable
                for target_col in horizon_data.columns:
                    try:
                        # Get target values (we only have one observation per week)
                        if week_idx + horizon < len(horizon_data):
                            y = horizon_data.iloc[week_idx + horizon][target_col]
                            
                            if np.isnan(y) or np.isinf(y):
                                continue
                            
                            # We need multiple observations for regression
                            # Use rolling window approach
                            if week_idx >= 8:  # Need at least 8 weeks of history
                                # Get rolling window of X and y
                                X_roll = []
                                y_roll = []
                                
                                for roll_week in range(max(0, week_idx - 8), week_idx):
                                    # Build X for this week
                                    roll_start = max(0, roll_week - lookback)
                                    roll_end = roll_week + 1
                                    
                                    if roll_end - roll_start >= 2:
                                        X_roll_window = deltas.iloc[roll_start:roll_end]
                                        X_roll_features = []
                                        
                                        for lag in range(len(X_roll_window)):
                                            for col in X_roll_window.columns:
                                                X_roll_features.append(X_roll_window.iloc[lag][col])
                                        
                                        if len(X_roll_features) == len(feature_names):
                                            X_roll.append(X_roll_features)
                                            
                                            # Get corresponding y
                                            if roll_week + horizon < len(horizon_data):
                                                y_val = horizon_data.iloc[roll_week + horizon][target_col]
                                                if not (np.isnan(y_val) or np.isinf(y_val)):
                                                    y_roll.append(y_val)
                                                else:
                                                    X_roll.pop()  # Remove corresponding X
                                
                                if len(X_roll) >= 5 and len(y_roll) >= 5:  # Need minimum samples
                                    X_roll = np.array(X_roll)
                                    y_roll = np.array(y_roll)
                                    
                                    # Standardize features
                                    scaler = StandardScaler()
                                    X_roll_scaled = scaler.fit_transform(X_roll)
                                    
                                    # Apply LASSO regression
                                    lasso = LassoCV(
                                        alphas=np.logspace(-3, 0, 20),
                                        cv=min(3, len(X_roll) // 2),
                                        random_state=42,
                                        max_iter=1000
                                    )
                                    
                                    lasso.fit(X_roll_scaled, y_roll)
                                    
                                    # Get significant coefficients
                                    significant_features = np.abs(lasso.coef_) > self.config['min_relationship_strength']
                                    
                                    if significant_features.any():
                                        # Calculate mutual information for significant features
                                        sig_indices = np.where(significant_features)[0]
                                        
                                        for idx in sig_indices:
                                            beta = lasso.coef_[idx]
                                            feature_name = feature_names[idx]
                                            
                                            # Extract source variable and lag
                                            if '_lag_' in feature_name:
                                                src_name = feature_name.rsplit('_lag_', 1)[0]
                                                lag = int(feature_name.rsplit('_lag_', 1)[1])
                                            else:
                                                src_name = feature_name
                                                lag = 0
                                            
                                            # Calculate mutual information
                                            try:
                                                mi_score = mutual_info_regression(
                                                    X_roll_scaled[:, idx:idx+1], 
                                                    y_roll,
                                                    random_state=42
                                                )[0]
                                            except:
                                                mi_score = 0
                                            
                                            if mi_score >= self.config['min_information_gain']:
                                                # Categorize source and destination
                                                src_type = self.categorize_single_variable(src_name)
                                                dst_type = self.categorize_single_variable(target_col)
                                                
                                                # Calculate confidence (R² of the model)
                                                try:
                                                    y_pred = lasso.predict(X_roll_scaled)
                                                    confidence = max(0, r2_score(y_roll, y_pred))
                                                except:
                                                    confidence = 0
                                                
                                                if confidence >= self.config['min_confidence']:
                                                    relationship = {
                                                        'date': deltas.index[week_idx],
                                                        'year': year,
                                                        'week': week_num,
                                                        'src_type': src_type,
                                                        'src_name': src_name,
                                                        'dst_type': dst_type,
                                                        'dst_name': target_col.replace(f'_fwd_{horizon}w', ''),
                                                        'horizon': horizon,
                                                        'beta': float(beta),
                                                        'information_gain': float(mi_score),
                                                        'confidence': float(confidence),
                                                        'direction': int(np.sign(beta)),
                                                        'regime_context': 'Unknown',  # Will be filled later
                                                        'novelty': 0.0,  # Will be calculated later
                                                        'stability': float(confidence)  # Use confidence as stability proxy
                                                    }
                                                    
                                                    relationships.append(relationship)
                    
                    except Exception as e:
                        continue
            
            return relationships
            
        except Exception as e:
            print(f"⚠️ Error detecting relationships for week {week_num}: {e}")
            return []
    
    def categorize_single_variable(self, var_name):
        """Categorize a single variable"""
        
        var_lower = var_name.lower()
        
        for category, keywords in self.variable_categories.items():
            if any(keyword in var_lower for keyword in keywords):
                return category
        
        return 'other'
    
    def calculate_novelty_and_stability(self, relationships, year, week_num):
        """Calculate novelty and stability for relationships"""
        
        try:
            # Load historical relationships for comparison
            historical_relationships = self.load_historical_relationships(year, week_num)
            
            for rel in relationships:
                # Calculate novelty (how new this relationship is)
                rel['novelty'] = self.calculate_relationship_novelty(
                    rel, historical_relationships
                )
                
                # Stability is already calculated as confidence
                # Could be enhanced with historical stability analysis
            
            return relationships
            
        except Exception as e:
            print(f"⚠️ Error calculating novelty/stability: {e}")
            return relationships
    
    def calculate_relationship_novelty(self, relationship, historical_relationships):
        """Calculate how novel a relationship is compared to history"""
        
        try:
            if not historical_relationships:
                return 1.0  # Completely novel if no history
            
            # Find similar relationships in history
            similar_relationships = []
            
            for hist_rel in historical_relationships:
                if (hist_rel['src_name'] == relationship['src_name'] and
                    hist_rel['dst_name'] == relationship['dst_name'] and
                    hist_rel['horizon'] == relationship['horizon']):
                    similar_relationships.append(hist_rel)
            
            if not similar_relationships:
                return 1.0  # Novel relationship
            
            # Calculate average historical beta
            historical_betas = [rel['beta'] for rel in similar_relationships]
            avg_historical_beta = np.mean(historical_betas)
            
            # Novelty is based on how different current beta is from historical average
            if avg_historical_beta == 0:
                return 1.0
            
            novelty = abs(relationship['beta'] - avg_historical_beta) / (abs(avg_historical_beta) + 0.01)
            return min(1.0, novelty)
            
        except:
            return 0.5  # Default novelty
    
    def load_historical_relationships(self, year, week_num):
        """Load historical relationships for novelty calculation"""
        
        try:
            historical_relationships = []
            novelty_window = self.config['novelty_window']
            
            # Look back through previous weeks
            for w in range(max(1, week_num - novelty_window), week_num):
                week_file = os.path.join(
                    self.paths['weekly_insights'], 
                    str(year), 
                    f'week_{w:02d}.parquet'
                )
                
                if os.path.exists(week_file):
                    try:
                        week_data = pd.read_parquet(week_file)
                        historical_relationships.extend(week_data.to_dict('records'))
                    except:
                        continue
            
            # Also look at same week in previous years
            for prev_year in range(year - 2, year):
                prev_week_file = os.path.join(
                    self.paths['weekly_insights'], 
                    str(prev_year), 
                    f'week_{week_num:02d}.parquet'
                )
                
                if os.path.exists(prev_week_file):
                    try:
                        prev_week_data = pd.read_parquet(prev_week_file)
                        historical_relationships.extend(prev_week_data.to_dict('records'))
                    except:
                        continue
            
            return historical_relationships
            
        except:
            return []
    
    def save_weekly_relationships(self, relationships, year, week_num):
        """Save weekly relationships to parquet file"""
        
        try:
            if not relationships:
                return False
            
            # Create year directory
            year_dir = os.path.join(self.paths['weekly_insights'], str(year))
            os.makedirs(year_dir, exist_ok=True)
            
            # Convert to DataFrame
            relationships_df = pd.DataFrame(relationships)
            
            # Save to parquet
            week_file = os.path.join(year_dir, f'week_{week_num:02d}.parquet')
            relationships_df.to_parquet(week_file)
            
            print(f"   💾 Saved {len(relationships)} relationships: {week_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving relationships: {e}")
            return False
    
    def build_year_fabric(self, year):
        """Build weekly causal fabric for a specific year"""
        
        start_time = datetime.now()
        
        print(f"🧬 BUILDING WEEKLY CAUSAL FABRIC FOR {year}")
        print("=" * 60)
        
        # Load market tensor
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            print("❌ Cannot build fabric without market tensor")
            return False
        
        # Extract year data
        year_data = self.extract_year_data(tensor, year)
        
        if year_data.empty:
            print(f"❌ No data available for {year}")
            return False
        
        # Categorize variables
        categorized_vars, uncategorized = self.categorize_variables(year_data.columns)
        
        # Compute weekly deltas
        print("📈 Computing weekly deltas...")
        deltas = self.compute_weekly_deltas(year_data)
        
        if deltas.empty:
            print("❌ Could not compute weekly deltas")
            return False
        
        # Compute forward returns
        print("🔮 Computing forward returns...")
        forward_returns = self.compute_forward_returns(year_data, self.config['forward_horizons'])
        
        if not forward_returns:
            print("❌ Could not compute forward returns")
            return False
        
        # Process each week
        print(f"🔄 Processing {len(year_data)} weeks with detailed progress...")
        print("=" * 80)
        total_relationships = 0
        
        for week_idx in range(len(year_data)):
            week_date = year_data.index[week_idx]
            week_num = week_date.isocalendar()[1]  # ISO week number
            
            # Progress indicator
            progress_pct = (week_idx + 1) / len(year_data) * 100
            progress_bar = "█" * int(progress_pct / 5) + "░" * (20 - int(progress_pct / 5))
            
            print(f"📅 Week {week_num:2d}/{len(year_data)} [{progress_bar}] {progress_pct:5.1f}% | {week_date.date()}", end=" | ")
            
            # Detect causal relationships
            start_time = datetime.now()
            relationships = self.detect_causal_relationships(
                deltas, forward_returns, week_idx, year, week_num
            )
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if relationships:
                # Calculate novelty and stability
                relationships = self.calculate_novelty_and_stability(
                    relationships, year, week_num
                )
                
                # Save relationships
                if self.save_weekly_relationships(relationships, year, week_num):
                    total_relationships += len(relationships)
                    print(f"✅ {len(relationships):3d} relationships | {processing_time:.1f}s")
                else:
                    print(f"❌ save failed | {processing_time:.1f}s")
            else:
                print(f"⚪ no relationships | {processing_time:.1f}s")
            
            # Show running statistics every 10 weeks
            if (week_idx + 1) % 10 == 0:
                avg_relationships = total_relationships / (week_idx + 1)
                print(f"📊 Progress: {week_idx + 1}/{len(year_data)} weeks | "
                      f"Total: {total_relationships} relationships | "
                      f"Avg: {avg_relationships:.1f} per week")
                print("-" * 80)
        
        # Build year summary
        self.build_year_summary(year, total_relationships)
        
        print("=" * 80)
        print(f"✅ Weekly causal fabric for {year} completed!")
        print(f"   📊 Total relationships discovered: {total_relationships:,}")
        print(f"   📈 Average per week: {total_relationships / len(year_data):.1f}")
        print(f"   ⏱️  Processing time: {(datetime.now() - start_time).total_seconds():.1f} seconds")
        
        # Show progress towards completion
        modern_years = [y for y in self.get_available_years() if y >= 2000]
        processed_years = []
        if os.path.exists(self.paths['weekly_insights']):
            processed_years = [
                int(d) for d in os.listdir(self.paths['weekly_insights'])
                if d.isdigit() and os.path.isdir(os.path.join(self.paths['weekly_insights'], d)) and int(d) >= 2000
            ]
        
        completed = len(processed_years)
        total_modern = len(modern_years)
        remaining = total_modern - completed
        
        print(f"   🎯 Progress: {completed}/{total_modern} years completed ({completed/total_modern*100:.1f}%)")
        print(f"   ⏳ Remaining: {remaining} years from 2000-2025")
        
        if remaining > 0:
            avg_time_per_year = (datetime.now() - start_time).total_seconds()
            estimated_remaining_time = avg_time_per_year * remaining
            hours = int(estimated_remaining_time // 3600)
            minutes = int((estimated_remaining_time % 3600) // 60)
            print(f"   ⏰ Estimated time to complete all: {hours}h {minutes}m")
        
        return True
    
    def build_year_summary(self, year, total_relationships):
        """Build summary for the year"""
        
        try:
            year_dir = os.path.join(self.paths['weekly_insights'], str(year))
            
            if not os.path.exists(year_dir):
                return
            
            # Collect all weekly files
            weekly_files = [f for f in os.listdir(year_dir) if f.startswith('week_') and f.endswith('.parquet')]
            
            if not weekly_files:
                return
            
            # Load all relationships for the year
            all_relationships = []
            
            for week_file in weekly_files:
                try:
                    week_path = os.path.join(year_dir, week_file)
                    week_data = pd.read_parquet(week_path)
                    all_relationships.extend(week_data.to_dict('records'))
                except:
                    continue
            
            if all_relationships:
                # Create summary DataFrame
                summary_df = pd.DataFrame(all_relationships)
                
                # Save year summary
                summary_file = os.path.join(year_dir, 'summary.parquet')
                summary_df.to_parquet(summary_file)
                
                # Create metadata
                metadata = {
                    'year': year,
                    'created_at': datetime.now().isoformat(),
                    'total_relationships': len(all_relationships),
                    'weeks_processed': len(weekly_files),
                    'avg_relationships_per_week': len(all_relationships) / len(weekly_files),
                    'relationship_types': summary_df['src_type'].value_counts().to_dict(),
                    'horizons': summary_df['horizon'].value_counts().to_dict(),
                    'config': self.config
                }
                
                metadata_file = os.path.join(year_dir, 'metadata.json')
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                print(f"   📋 Year summary saved: {summary_file}")
            
        except Exception as e:
            print(f"⚠️ Error building year summary: {e}")
    
    def get_available_years(self):
        """Get years available for processing"""
        
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            return []
        
        available_years = sorted(tensor.index.year.unique())
        
        # Filter years with sufficient data
        valid_years = []
        for year in available_years:
            year_data = self.extract_year_data(tensor, year)
            if not year_data.empty:
                valid_years.append(year)
        
        return valid_years
    
    def process_next_year(self):
        """Process the next available year starting from 2000"""
        
        available_years = self.get_available_years()
        
        if not available_years:
            print("❌ No years available for processing")
            return False
        
        # Filter to start from 2000 onwards (when major market data begins)
        modern_years = [year for year in available_years if year >= 2000]
        
        if not modern_years:
            print("❌ No years from 2000 onwards available for processing")
            return False
        
        # Find the next year to process
        processed_years = []
        
        if os.path.exists(self.paths['weekly_insights']):
            processed_years = [
                int(d) for d in os.listdir(self.paths['weekly_insights'])
                if d.isdigit() and os.path.isdir(os.path.join(self.paths['weekly_insights'], d))
            ]
        
        # Find next unprocessed year from 2000 onwards
        next_year = None
        for year in sorted(modern_years):
            if year not in processed_years:
                next_year = year
                break
        
        if next_year is None:
            print("✅ All available years from 2000 onwards have been processed")
            modern_processed = [y for y in processed_years if y >= 2000]
            print(f"   Processed years (2000+): {sorted(modern_processed)}")
            return True
        
        print(f"🎯 Processing next year: {next_year}")
        print(f"📊 Available modern years (2000+): {len(modern_years)}")
        print(f"📈 Processed so far: {len([y for y in processed_years if y >= 2000])}")
        print(f"⏳ Remaining: {len(modern_years) - len([y for y in processed_years if y >= 2000])}")
        
        return self.build_year_fabric(next_year)

def main():
    """Build weekly causal fabric for next available year"""
    
    builder = WeeklyFabricBuilder()
    
    # Show available years
    available_years = builder.get_available_years()
    print(f"📅 Available years: {available_years}")
    
    # Process next year
    success = builder.process_next_year()
    
    if success:
        print(f"\n🎯 Weekly causal fabric processing completed!")
        print(f"   Next: Run again to process the next year")
        print(f"   Integration: Use WeeklyFabricReader to access relationships")
    else:
        print("❌ Failed to process weekly causal fabric")
    
    return success

if __name__ == "__main__":
    main()