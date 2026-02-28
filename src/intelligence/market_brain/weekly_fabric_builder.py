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
import re
from datetime import datetime, timedelta
from sklearn.linear_model import LassoCV
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
import warnings
warnings.filterwarnings('ignore')

# Import existing V3 components
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.intelligence.market_brain.market_tensor import MarketTensorEngine
from src.intelligence.market_brain.weekly_relationship_store import WeeklyRelationshipStore

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
        self.relationship_store = WeeklyRelationshipStore()
        
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
            # Relaxed thresholds for sparse historical windows (used in fallback mode).
            'min_relationship_strength_relaxed': 0.04,
            'min_information_gain_relaxed': 0.20,
            'min_confidence_relaxed': 0.30,
            'lasso_alpha_range': (0.001, 1.0), # LASSO regularization range
            'cv_folds': 5,                  # Cross-validation folds
            'novelty_window': 12,           # Weeks to look back for novelty calculation
            'stability_window': 4,          # Weeks to assess relationship stability
            # Runtime guardrails for M1 safety / anti-freeze behavior.
            'max_feature_columns': 80,
            'max_targets_per_horizon': 12,
            'max_forward_targets': 24,
            'min_target_uniques': 8,
            'min_target_coverage': 0.60,
            'min_target_std': 1e-8,
            'min_samples_for_lasso': 16,
            'min_samples_for_relaxed_fit': 8,
            'lasso_alpha_count': 10,
            'regression_window_weeks': 24,
            'max_seconds_per_week': 8.0,
            'fallback_corr_threshold': 0.25,
            'fallback_beta_threshold': 0.04,
            'fallback_max_edges_per_target': 2,
            'fallback_max_edges_per_horizon': 18,
        }
        
        # Variable categories for causal analysis
        self.variable_categories = {
            'macro': ['rbi_', 'repo', 'rate', 'cpi', 'wpi', 'inflation', 'growth'],
            'fx': ['usdinr', 'fx', 'currency', 'exchange'],
            'flows': ['fii', 'dii', 'flow', 'capital'],
            'credit': ['credit', 'loan', 'deposit', 'banking', 'yield'],
            'liquidity': ['liquidity', 'reserve', 'money', 'supply'],
            'structure': ['volatility', 'corr', 'correlation', 'breadth', 'participation', 'drawdown', 'dispersion'],
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
                tensor = MarketTensorEngine.canonicalize_tensor_frame(tensor)
                
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
                heuristic = self._heuristic_category(col_lower)
                if heuristic:
                    categorized[heuristic].append(col)
                else:
                    uncategorized.append(col)
        
        # Log categorization
        for category, vars in categorized.items():
            if vars:
                print(f"   📊 {category}: {len(vars)} variables")
        
        if uncategorized:
            print(f"   ❓ Uncategorized: {len(uncategorized)} variables")
        
        return categorized, uncategorized

    def _heuristic_category(self, col_lower):
        """Second-pass category mapping for weakly named tensor columns."""
        if any(k in col_lower for k in ['_northstar_score', 'alpha', 'factor', 'signal']):
            return 'corporate'
        if any(k in col_lower for k in ['nifty', 'sensex', 'bankex', 'index']):
            return 'sector'
        if any(k in col_lower for k in ['spread', 'carry', 'curve']):
            return 'credit'
        if any(k in col_lower for k in ['cash', 'funding', 'repo', 'reverse_repo']):
            return 'liquidity'
        if any(k in col_lower for k in ['usd', 'inr', 'dxy']):
            return 'fx'
        return None
    
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

    def _canonical_feature_name(self, name):
        """Normalize feature names so duplicate tensor columns collapse to one identity."""
        s = str(name or "")
        s = re.sub(r"_lag_\d+$", "", s)
        s = re.sub(r"_fwd_\d+w$", "", s)
        s = re.sub(r"_dup_\d+$", "", s)
        return s

    def _drop_duplicate_suffix_columns(self, columns):
        """
        Remove synthetic duplicate columns created during tensor merges.

        Keep original columns and drop `_dup_<n>` variants when both exist.
        """
        cols = [str(c) for c in list(columns)]
        keep = [c for c in cols if not re.search(r"_dup_\d+$", c)]
        return keep if keep else cols

    def _select_forward_target_columns(self, year_data):
        """Pick target columns with enough variation for stable relationship fitting."""
        try:
            numeric = year_data.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
            if numeric.empty:
                return []

            base_cols = self._drop_duplicate_suffix_columns(numeric.columns)
            numeric = numeric[base_cols]

            stats = pd.DataFrame({
                'std': numeric.std(skipna=True),
                'nunique': numeric.nunique(dropna=True),
                'coverage': numeric.notna().mean(),
            })

            min_uniques = int(self.config.get('min_target_uniques', 8))
            min_coverage = float(self.config.get('min_target_coverage', 0.60))
            min_std = float(self.config.get('min_target_std', 1e-8))
            max_targets = int(self.config.get('max_forward_targets', 24))
            min_preferred = max(8, max_targets // 3)

            quality_mask = (
                (stats['coverage'] >= min_coverage) &
                (stats['nunique'] >= min_uniques) &
                (stats['std'] > min_std)
            )

            preferred_name_mask = stats.index.to_series().str.lower().str.contains(
                r"return|performance|sector_|industry_|corp_factor_|nifty|volatility|score|factor",
                regex=True
            )

            preferred = stats[quality_mask & preferred_name_mask].sort_values('std', ascending=False)

            if len(preferred) >= min_preferred:
                selected = preferred.head(max_targets).index.tolist()
                print(f"   🎯 Forward targets (preferred): {len(selected)}")
                return selected

            fallback = stats[quality_mask].sort_values('std', ascending=False)
            selected = fallback.head(max_targets).index.tolist()
            print(f"   🎯 Forward targets (fallback): {len(selected)}")
            return selected

        except Exception as e:
            print(f"⚠️ Target selection failed: {e}")
            return []

    def _compute_forward_target_series(self, series, column_name, horizon):
        """
        Compute forward target aligned for detector indexing.

        Detector reads y at (t + horizon), so this method keeps targets anchored
        at the future timestamp without an additional negative shift.
        """
        s = pd.to_numeric(series, errors='coerce').replace([np.inf, -np.inf], np.nan)
        col = str(column_name).lower()

        if any(token in col for token in ['return', 'performance']):
            # Aggregate last `horizon` returns so value at t+h reflects [t+1, t+h].
            return s.rolling(horizon, min_periods=max(1, min(3, horizon))).sum()

        if any(token in col for token in ['factor', 'score', 'volatility']):
            scale = s.rolling(26, min_periods=4).std().replace(0, np.nan)
            return (s.diff(horizon) / scale).replace([np.inf, -np.inf], np.nan)

        baseline = s.abs().rolling(26, min_periods=4).median().replace(0, np.nan)
        pct = s.pct_change(horizon).replace([np.inf, -np.inf], np.nan)
        diff_norm = s.diff(horizon) / (baseline + 1e-9)
        return pct.where(pct.notna(), diff_norm).replace([np.inf, -np.inf], np.nan)
    
    def compute_forward_returns(self, year_data, horizons):
        """Compute forward returns for different horizons"""
        
        try:
            forward_returns = {}
            numeric_year = year_data.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
            target_cols = self._select_forward_target_columns(numeric_year)

            if not target_cols:
                print("⚠️ No viable target variables found for forward return calculation")
                return {}

            print(f"   📊 Computing forward returns for {len(target_cols)} variables")

            for horizon in horizons:
                horizon_returns = pd.DataFrame(index=year_data.index)
                
                for col in target_cols:
                    forward_col = f"{col}_fwd_{horizon}w"
                    target_series = self._compute_forward_target_series(
                        numeric_year[col],
                        col,
                        int(horizon)
                    )
                    # Drop near-constant targets up front to avoid all-zero fits.
                    if target_series.dropna().nunique() < 4:
                        continue
                    horizon_returns[forward_col] = target_series

                horizon_returns = horizon_returns.dropna(axis=1, how='all')
                if horizon_returns.empty:
                    continue

                forward_returns[horizon] = horizon_returns
                print(f"      {horizon}w: {horizon_returns.shape[1]} forward return series")
            
            return forward_returns
            
        except Exception as e:
            print(f"❌ Error computing forward returns: {e}")
            return {}
    
    def detect_causal_relationships(self, deltas, forward_returns, week_idx, year, week_num):
        """Detect causal relationships for a specific week using LASSO + mutual information"""
        
        try:
            week_runtime_start = datetime.now()
            relationships = []
            
            # Get context window (current + lookback weeks)
            lookback = self.config['lookback_weeks']
            start_idx = max(0, week_idx - lookback)
            end_idx = week_idx + 1
            
            if end_idx - start_idx < 2:
                return relationships
            
            # Get predictor variables (deltas in context window)
            X_window = deltas.iloc[start_idx:end_idx]
            base_predictor_cols = self._drop_duplicate_suffix_columns(X_window.columns)
            X_window = X_window[base_predictor_cols]
            predictor_columns = list(X_window.columns)

            min_samples = int(self.config.get('min_samples_for_lasso', 20))
            regression_window = int(
                self.config.get(
                    'regression_window_weeks',
                    max(min_samples + 4, 24),
                )
            )

            # Keep only the most informative predictor columns to avoid
            # very high-dimensional regressions that can stall on small windows.
            context_len = max(1, (end_idx - start_idx))
            max_features_cfg = int(self.config.get('max_feature_columns', 80))
            max_features_dynamic = max(12, int((regression_window * 1.5) / context_len))
            max_features = min(max_features_cfg, max_features_dynamic)
            if X_window.shape[1] > max_features:
                var_rank = (
                    X_window.apply(pd.to_numeric, errors='coerce')
                    .replace([np.inf, -np.inf], np.nan)
                    .std()
                    .sort_values(ascending=False)
                )
                top_cols = var_rank.head(max_features).index.tolist()
                X_window = X_window[top_cols]
                predictor_columns = top_cols
            
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
                elapsed = (datetime.now() - week_runtime_start).total_seconds()
                if elapsed > float(self.config.get('max_seconds_per_week', 8.0)):
                    break
                horizon_data = forward_returns[horizon]

                if week_idx >= len(horizon_data):
                    continue

                # Skip expensive work until enough history exists.
                if week_idx < min_samples:
                    continue

                # For each target variable (capped for runtime stability)
                target_cols = list(horizon_data.columns)
                max_targets = int(self.config.get('max_targets_per_horizon', 12))
                if len(target_cols) > max_targets:
                    try:
                        window_start = max(0, week_idx - 52)
                        var_rank_t = (
                            horizon_data.iloc[window_start:week_idx + 1][target_cols]
                            .apply(pd.to_numeric, errors='coerce')
                            .replace([np.inf, -np.inf], np.nan)
                            .std()
                            .sort_values(ascending=False)
                        )
                        target_cols = var_rank_t.head(max_targets).index.tolist()
                    except Exception:
                        target_cols = target_cols[:max_targets]

                # Build rolling predictor matrix once per horizon (shared across targets).
                X_roll = []
                roll_weeks = []
                for roll_week in range(max(0, week_idx - regression_window), week_idx):
                    roll_start = max(0, roll_week - lookback)
                    roll_end = roll_week + 1

                    if roll_end - roll_start < 2:
                        continue

                    X_roll_window = deltas.iloc[roll_start:roll_end]
                    # Use the same selected predictor set as current-week features.
                    X_roll_window = X_roll_window[X_window.columns]
                    X_roll_features = []

                    for lag in range(len(X_roll_window)):
                        for col in X_roll_window.columns:
                            X_roll_features.append(X_roll_window.iloc[lag][col])

                    if len(X_roll_features) == len(feature_names):
                        X_roll.append(X_roll_features)
                        roll_weeks.append(roll_week)

                if len(X_roll) < min_samples:
                    continue

                X_roll = np.array(X_roll)
                scaler = StandardScaler()
                X_roll_scaled = scaler.fit_transform(X_roll)

                for target_col in target_cols:
                    elapsed = (datetime.now() - week_runtime_start).total_seconds()
                    if elapsed > float(self.config.get('max_seconds_per_week', 8.0)):
                        break
                    try:
                        # Build target series aligned to valid rolling predictor rows.
                        y_roll = []
                        valid_rows = []

                        for i, roll_week in enumerate(roll_weeks):
                            if roll_week + horizon >= len(horizon_data):
                                continue
                            y_val = horizon_data.iloc[roll_week + horizon][target_col]
                            if np.isnan(y_val) or np.isinf(y_val):
                                continue
                            y_roll.append(y_val)
                            valid_rows.append(i)

                        if len(y_roll) < min_samples:
                            continue

                        X_target = X_roll_scaled[valid_rows]
                        y_target = np.array(y_roll)

                        # Skip near-constant targets (causes all-zero sparse fits).
                        if np.nanstd(y_target) < 1e-10:
                            continue

                        lasso = LassoCV(
                            alphas=np.logspace(-3, 0, int(self.config.get('lasso_alpha_count', 10))),
                            cv=max(2, min(3, len(X_target) // 4)),
                            random_state=42,
                            max_iter=500
                        )
                        lasso.fit(X_target, y_target)

                        significant_features = np.abs(lasso.coef_) > self.config['min_relationship_strength']
                        if not significant_features.any():
                            continue

                        sig_indices = np.where(significant_features)[0]
                        for idx in sig_indices:
                            beta = lasso.coef_[idx]
                            feature_name = feature_names[idx]

                            # Extract source variable and lag
                            if '_lag_' in feature_name:
                                src_name = feature_name.rsplit('_lag_', 1)[0]
                            else:
                                src_name = feature_name
                            src_name = self._canonical_feature_name(src_name)

                            # Calculate mutual information
                            try:
                                mi_score = mutual_info_regression(
                                    X_target[:, idx:idx+1],
                                    y_target,
                                    random_state=42
                                )[0]
                            except Exception:
                                mi_score = 0

                            if mi_score < self.config['min_information_gain']:
                                continue

                            dst_name = self._canonical_feature_name(target_col)
                            if not src_name or not dst_name or src_name == dst_name:
                                continue

                            src_type = self.categorize_single_variable(src_name)
                            dst_type = self.categorize_single_variable(dst_name)

                            # Calculate confidence (R² of the model)
                            try:
                                y_pred = lasso.predict(X_target)
                                confidence = max(0, r2_score(y_target, y_pred))
                            except Exception:
                                confidence = 0

                            if confidence < self.config['min_confidence']:
                                continue

                            relationship = {
                                'date': deltas.index[week_idx],
                                'year': year,
                                'week': week_num,
                                'src_type': src_type,
                                'src_name': src_name,
                                'dst_type': dst_type,
                                'dst_name': dst_name,
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

                    except Exception:
                        continue

            # Sparse historical windows can produce all-zero LASSO fits.
            # Use a bounded correlation fallback to surface usable edges.
            if not relationships:
                relationships = self.detect_correlation_fallback_relationships(
                    deltas=deltas,
                    forward_returns=forward_returns,
                    week_idx=week_idx,
                    year=year,
                    week_num=week_num,
                    predictor_columns=predictor_columns
                )

            return self.deduplicate_relationships(relationships)
            
        except Exception as e:
            print(f"⚠️ Error detecting relationships for week {week_num}: {e}")
            return []

    def detect_correlation_fallback_relationships(
        self,
        deltas,
        forward_returns,
        week_idx,
        year,
        week_num,
        predictor_columns=None
    ):
        """
        Correlation-based fallback for sparse periods where strict LASSO returns no edges.

        This keeps runtime bounded and returns a small, high-signal subset.
        """
        relationships = []

        try:
            regression_window = int(self.config.get('regression_window_weeks', 24))
            min_samples = int(self.config.get('min_samples_for_relaxed_fit', 12))
            min_corr = float(self.config.get('fallback_corr_threshold', 0.25))
            min_beta = float(self.config.get('fallback_beta_threshold', 0.04))
            min_conf = float(self.config.get('min_confidence_relaxed', 0.30))
            max_targets = int(self.config.get('max_targets_per_horizon', 12))
            max_edges_target = int(self.config.get('fallback_max_edges_per_target', 2))
            max_edges_horizon = int(self.config.get('fallback_max_edges_per_horizon', 18))
            max_features = int(self.config.get('max_feature_columns', 80))
            min_info = float(self.config.get('min_information_gain_relaxed', 0.20))

            numeric_deltas = deltas.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
            if numeric_deltas.empty:
                return []

            candidate_predictors = list(predictor_columns or numeric_deltas.columns)
            if len(candidate_predictors) > max_features:
                window_start = max(0, week_idx - regression_window)
                rank = (
                    numeric_deltas.iloc[window_start:week_idx + 1][candidate_predictors]
                    .std(skipna=True)
                    .sort_values(ascending=False)
                )
                candidate_predictors = rank.head(max_features).index.tolist()

            for horizon, horizon_data in forward_returns.items():
                if week_idx < min_samples or week_idx >= len(horizon_data):
                    continue

                numeric_targets = horizon_data.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
                if numeric_targets.empty:
                    continue

                target_cols = list(numeric_targets.columns)
                if len(target_cols) > max_targets:
                    rank_t = (
                        numeric_targets.iloc[max(0, week_idx - 52):week_idx + 1][target_cols]
                        .std(skipna=True)
                        .sort_values(ascending=False)
                    )
                    target_cols = rank_t.head(max_targets).index.tolist()

                horizon_edges = []
                for target_col in target_cols:
                    candidate_edges = []
                    for src_col in candidate_predictors:
                        x_vals = []
                        y_vals = []

                        for roll_week in range(max(0, week_idx - regression_window), week_idx):
                            target_idx = roll_week + horizon
                            if target_idx >= len(numeric_targets):
                                continue

                            x_val = numeric_deltas.iloc[roll_week][src_col]
                            y_val = numeric_targets.iloc[target_idx][target_col]
                            if np.isnan(x_val) or np.isnan(y_val) or np.isinf(x_val) or np.isinf(y_val):
                                continue

                            x_vals.append(float(x_val))
                            y_vals.append(float(y_val))

                        if len(x_vals) < min_samples:
                            continue

                        x_arr = np.array(x_vals)
                        y_arr = np.array(y_vals)

                        if np.nanstd(x_arr) < 1e-12 or np.nanstd(y_arr) < 1e-12:
                            continue

                        corr = float(np.corrcoef(x_arr, y_arr)[0, 1])
                        if not np.isfinite(corr) or abs(corr) < min_corr:
                            continue

                        beta = float(np.cov(x_arr, y_arr)[0, 1] / (np.var(x_arr) + 1e-12))
                        if abs(beta) < min_beta:
                            continue

                        confidence = float(min(1.0, abs(corr)))
                        if confidence < min_conf:
                            continue

                        # Fallback signal quality proxy.
                        info_gain = float(abs(corr))
                        if info_gain < min_info:
                            continue

                        src_name = self._canonical_feature_name(src_col)
                        dst_name = self._canonical_feature_name(target_col)
                        if not src_name or not dst_name or src_name == dst_name:
                            continue

                        src_type = self.categorize_single_variable(src_name)
                        dst_type = self.categorize_single_variable(dst_name)

                        relationship = {
                            'date': deltas.index[week_idx],
                            'year': year,
                            'week': week_num,
                            'src_type': src_type,
                            'src_name': src_name,
                            'dst_type': dst_type,
                            'dst_name': dst_name,
                            'horizon': horizon,
                            'beta': beta,
                            'information_gain': info_gain,
                            'confidence': confidence,
                            'direction': int(np.sign(beta)),
                            'regime_context': 'Unknown',
                            'novelty': 0.0,
                            'stability': confidence
                        }
                        score = abs(beta) * (0.5 + confidence) * (0.5 + info_gain)
                        candidate_edges.append((score, relationship))

                    if candidate_edges:
                        candidate_edges = sorted(candidate_edges, key=lambda x: x[0], reverse=True)
                        horizon_edges.extend([rel for _, rel in candidate_edges[:max_edges_target]])

                if horizon_edges:
                    ranked = sorted(
                        horizon_edges,
                        key=lambda r: abs(float(r.get('beta', 0.0))) * (0.5 + float(r.get('confidence', 0.0))),
                        reverse=True
                    )
                    relationships.extend(ranked[:max_edges_horizon])

            return relationships
        except Exception:
            return []

    def deduplicate_relationships(self, relationships):
        """Keep one strongest edge per (date, src, dst, horizon) key."""
        if not relationships:
            return []

        best_edges = {}
        for rel in relationships:
            key = (
                pd.to_datetime(rel.get('date'), errors='coerce'),
                str(rel.get('src_name', '')),
                str(rel.get('dst_name', '')),
                int(rel.get('horizon', 0)),
            )

            score = (
                abs(float(rel.get('beta', 0.0))) * (0.5 + float(rel.get('confidence', 0.0))) +
                float(rel.get('information_gain', 0.0)) +
                0.1 * float(rel.get('novelty', 0.0))
            )

            prev = best_edges.get(key)
            if prev is None or score > prev[0]:
                best_edges[key] = (score, rel)

        deduped = [v[1] for v in best_edges.values()]
        deduped.sort(
            key=lambda r: (
                pd.to_datetime(r.get('date'), errors='coerce'),
                -abs(float(r.get('beta', 0.0))),
                -float(r.get('confidence', 0.0)),
            )
        )
        return deduped
    
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

            # Route persistence through store so relationship index stays in sync.
            ok = self.relationship_store.save_weekly_relationships(
                relationships=relationships,
                year=year,
                week=week_num
            )
            if not ok:
                return False

            week_file = os.path.join(self.paths['weekly_insights'], str(year), f'week_{week_num:02d}.parquet')
            print(f"   💾 Saved {len(relationships)} relationships: {week_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving relationships: {e}")
            return False
    
    def build_year_fabric(self, year):
        """Build weekly causal fabric for a specific year"""
        
        year_start_time = datetime.now()
        
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
            week_start_time = datetime.now()
            relationships = self.detect_causal_relationships(
                deltas, forward_returns, week_idx, year, week_num
            )
            processing_time = (datetime.now() - week_start_time).total_seconds()
            
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
        print(f"   ⏱️  Processing time: {(datetime.now() - year_start_time).total_seconds():.1f} seconds")
        
        # Show progress towards completion
        modern_years = [y for y in self.get_available_years() if y >= 2000]
        processed_years = [y for y in modern_years if self._is_year_processed(y)]
        
        completed = len(processed_years)
        total_modern = len(modern_years)
        remaining = total_modern - completed
        
        print(f"   🎯 Progress: {completed}/{total_modern} years completed ({completed/total_modern*100:.1f}%)")
        print(f"   ⏳ Remaining: {remaining} years from 2000-2025")
        
        if remaining > 0:
            avg_time_per_year = (datetime.now() - year_start_time).total_seconds()
            estimated_remaining_time = avg_time_per_year * remaining
            hours = int(estimated_remaining_time // 3600)
            minutes = int((estimated_remaining_time % 3600) // 60)
            print(f"   ⏰ Estimated time to complete all: {hours}h {minutes}m")
        
        return True
    
    def build_year_summary(self, year, total_relationships):
        """Build summary for the year"""
        
        try:
            year_dir = os.path.join(self.paths['weekly_insights'], str(year))
            os.makedirs(year_dir, exist_ok=True)
            
            # Collect all weekly files
            weekly_files = [f for f in os.listdir(year_dir) if f.startswith('week_') and f.endswith('.parquet')]
            
            if not weekly_files:
                # Mark the year as processed even when no relationships were discovered.
                metadata = {
                    'year': year,
                    'created_at': datetime.now().isoformat(),
                    'total_relationships': int(total_relationships),
                    'weeks_processed': 0,
                    'avg_relationships_per_week': 0.0,
                    'relationship_types': {},
                    'horizons': {},
                    'config': self.config,
                    'status': 'processed_no_relationships',
                }
                metadata_file = os.path.join(year_dir, 'metadata.json')
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                print(f"   📋 Year summary saved (no relationships): {metadata_file}")
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

    def _is_year_processed(self, year):
        """Treat a year as processed only when metadata or week artifacts exist."""
        try:
            year_dir = os.path.join(self.paths['weekly_insights'], str(year))
            if not os.path.isdir(year_dir):
                return False

            week_files_exist = any(
                name.startswith('week_') and name.endswith('.parquet')
                for name in os.listdir(year_dir)
            )
            if week_files_exist:
                return True

            metadata_path = os.path.join(year_dir, 'metadata.json')
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        md = json.load(f)
                    if int(md.get('total_relationships', 0) or 0) > 0:
                        return True
                except Exception:
                    pass

            return False
        except Exception:
            return False
    
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
        processed_years = [year for year in modern_years if self._is_year_processed(year)]
        
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
