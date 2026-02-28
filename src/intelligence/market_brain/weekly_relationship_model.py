#!/usr/bin/env python3
"""
🧬 WEEKLY RELATIONSHIP MODEL - NORTHSTAR V3 MARKET BRAIN
The Causal Discovery Engine: Advanced Relationship Detection

This implements sophisticated causal relationship detection using:
- Multi-horizon LASSO regression with stability selection
- Mutual information for non-linear relationships
- Granger causality testing
- Relationship stability tracking
- Regime-aware relationship modeling

Integration with V3:
- Feeds into Weekly Fabric Builder
- Enhances relationship detection accuracy
- Provides confidence scoring for relationships
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LassoCV, ElasticNetCV
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from scipy import stats
from scipy.stats import pearsonr, spearmanr
import warnings
warnings.filterwarnings('ignore')

class WeeklyRelationshipModel:
    """
    Advanced Causal Relationship Detection Model
    
    Uses multiple techniques to detect and validate causal relationships:
    1. LASSO regression for sparse feature selection
    2. Mutual information for non-linear relationships
    3. Granger causality for temporal precedence
    4. Stability selection across time windows
    5. Regime-aware relationship strength
    """
    
    def __init__(self):
        self.name = "Weekly Relationship Model"
        self.version = "1.0"
        
        # Model configuration
        self.config = {
            'lasso_alpha_range': np.logspace(-4, 1, 50),
            'elastic_net_l1_ratios': [0.1, 0.5, 0.7, 0.9, 0.95, 0.99],
            'cv_folds': 5,
            'stability_threshold': 0.6,
            'min_beta_threshold': 0.1,
            'min_mutual_info': 0.05,
            'granger_max_lags': 4,
            'confidence_threshold': 0.5,
            'outlier_threshold': 3.0,
            'min_observations': 8
        }
        
        # Relationship strength categories
        self.strength_categories = {
            'very_weak': (0.0, 0.1),
            'weak': (0.1, 0.3),
            'moderate': (0.3, 0.5),
            'strong': (0.5, 0.7),
            'very_strong': (0.7, 1.0)
        }
    
    def prepare_features(self, X, feature_names, max_lags=4):
        """Prepare feature matrix with lagged variables"""
        
        try:
            if len(X.shape) == 1:
                X = X.reshape(-1, 1)
            
            n_samples, n_features = X.shape
            
            if n_samples <= max_lags:
                return X, feature_names
            
            # Create lagged features
            lagged_features = []
            lagged_names = []
            
            for lag in range(max_lags + 1):
                if lag == 0:
                    # Current period
                    lagged_features.append(X)
                    lagged_names.extend([f"{name}_t0" for name in feature_names])
                else:
                    # Lagged periods
                    if n_samples > lag:
                        lagged_X = np.zeros_like(X)
                        lagged_X[lag:] = X[:-lag]
                        lagged_features.append(lagged_X)
                        lagged_names.extend([f"{name}_t{lag}" for name in feature_names])
            
            # Combine all lagged features
            X_lagged = np.hstack(lagged_features)
            
            return X_lagged, lagged_names
            
        except Exception as e:
            print(f"⚠️ Error preparing features: {e}")
            return X, feature_names
    
    def detect_outliers(self, X, y):
        """Detect and handle outliers using robust methods"""
        
        try:
            # Z-score method for outliers
            z_scores_X = np.abs(stats.zscore(X, axis=0, nan_policy='omit'))
            z_scores_y = np.abs(stats.zscore(y, nan_policy='omit'))
            
            # Identify outliers
            outlier_mask_X = np.any(z_scores_X > self.config['outlier_threshold'], axis=1)
            outlier_mask_y = z_scores_y > self.config['outlier_threshold']
            outlier_mask = outlier_mask_X | outlier_mask_y
            
            # Remove outliers
            clean_indices = ~outlier_mask
            X_clean = X[clean_indices]
            y_clean = y[clean_indices]
            
            outlier_count = np.sum(outlier_mask)
            if outlier_count > 0:
                print(f"   🧹 Removed {outlier_count} outliers")
            
            return X_clean, y_clean, clean_indices
            
        except Exception as e:
            print(f"⚠️ Error detecting outliers: {e}")
            return X, y, np.ones(len(X), dtype=bool)
    
    def lasso_regression_analysis(self, X, y, feature_names):
        """Perform LASSO regression with cross-validation"""
        
        try:
            if len(X) < self.config['min_observations']:
                return {}, 0.0
            
            # Remove outliers
            X_clean, y_clean, clean_mask = self.detect_outliers(X, y)
            
            if len(X_clean) < self.config['min_observations']:
                return {}, 0.0
            
            # Scale features
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X_clean)
            
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=min(self.config['cv_folds'], len(X_clean) // 2))
            
            # LASSO regression
            lasso = LassoCV(
                alphas=self.config['lasso_alpha_range'],
                cv=tscv,
                random_state=42,
                max_iter=2000,
                selection='random'
            )
            
            lasso.fit(X_scaled, y_clean)
            
            # Get significant coefficients
            significant_features = {}
            coefficients = lasso.coef_
            
            for i, (coef, feature_name) in enumerate(zip(coefficients, feature_names)):
                if abs(coef) > self.config['min_beta_threshold']:
                    significant_features[feature_name] = {
                        'beta': float(coef),
                        'abs_beta': float(abs(coef)),
                        'direction': int(np.sign(coef))
                    }
            
            # Model performance
            y_pred = lasso.predict(X_scaled)
            r2 = r2_score(y_clean, y_pred)
            
            return significant_features, max(0.0, r2)
            
        except Exception as e:
            print(f"⚠️ Error in LASSO analysis: {e}")
            return {}, 0.0
    
    def elastic_net_analysis(self, X, y, feature_names):
        """Perform Elastic Net regression for comparison"""
        
        try:
            if len(X) < self.config['min_observations']:
                return {}, 0.0
            
            # Remove outliers
            X_clean, y_clean, clean_mask = self.detect_outliers(X, y)
            
            if len(X_clean) < self.config['min_observations']:
                return {}, 0.0
            
            # Scale features
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X_clean)
            
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=min(self.config['cv_folds'], len(X_clean) // 2))
            
            # Elastic Net regression
            elastic_net = ElasticNetCV(
                alphas=self.config['lasso_alpha_range'],
                l1_ratio=self.config['elastic_net_l1_ratios'],
                cv=tscv,
                random_state=42,
                max_iter=2000,
                selection='random'
            )
            
            elastic_net.fit(X_scaled, y_clean)
            
            # Get significant coefficients
            significant_features = {}
            coefficients = elastic_net.coef_
            
            for i, (coef, feature_name) in enumerate(zip(coefficients, feature_names)):
                if abs(coef) > self.config['min_beta_threshold']:
                    significant_features[feature_name] = {
                        'beta': float(coef),
                        'abs_beta': float(abs(coef)),
                        'direction': int(np.sign(coef))
                    }
            
            # Model performance
            y_pred = elastic_net.predict(X_scaled)
            r2 = r2_score(y_clean, y_pred)
            
            return significant_features, max(0.0, r2)
            
        except Exception as e:
            print(f"⚠️ Error in Elastic Net analysis: {e}")
            return {}, 0.0
    
    def mutual_information_analysis(self, X, y, feature_names):
        """Calculate mutual information for non-linear relationships"""
        
        try:
            if len(X) < self.config['min_observations']:
                return {}
            
            # Remove outliers
            X_clean, y_clean, clean_mask = self.detect_outliers(X, y)
            
            if len(X_clean) < self.config['min_observations']:
                return {}
            
            # Calculate mutual information
            mi_scores = mutual_info_regression(
                X_clean, y_clean,
                discrete_features=False,
                random_state=42
            )
            
            # Extract significant MI scores
            significant_mi = {}
            
            for i, (mi_score, feature_name) in enumerate(zip(mi_scores, feature_names)):
                if mi_score > self.config['min_mutual_info']:
                    significant_mi[feature_name] = {
                        'mutual_info': float(mi_score),
                        'normalized_mi': float(mi_score / (mi_scores.max() + 1e-8))
                    }
            
            return significant_mi
            
        except Exception as e:
            print(f"⚠️ Error in mutual information analysis: {e}")
            return {}
    
    def correlation_analysis(self, X, y, feature_names):
        """Calculate correlation coefficients"""
        
        try:
            if len(X) < self.config['min_observations']:
                return {}
            
            correlations = {}
            
            for i, feature_name in enumerate(feature_names):
                if i < X.shape[1]:
                    x_feature = X[:, i]
                    
                    # Remove NaN values
                    valid_mask = ~(np.isnan(x_feature) | np.isnan(y))
                    
                    if np.sum(valid_mask) >= self.config['min_observations']:
                        x_clean = x_feature[valid_mask]
                        y_clean = y[valid_mask]
                        
                        # Pearson correlation
                        try:
                            pearson_r, pearson_p = pearsonr(x_clean, y_clean)
                            
                            if not np.isnan(pearson_r):
                                correlations[feature_name] = {
                                    'pearson_r': float(pearson_r),
                                    'pearson_p': float(pearson_p),
                                    'abs_correlation': float(abs(pearson_r))
                                }
                        except:
                            pass
                        
                        # Spearman correlation (rank-based, more robust)
                        try:
                            spearman_r, spearman_p = spearmanr(x_clean, y_clean)
                            
                            if not np.isnan(spearman_r) and feature_name in correlations:
                                correlations[feature_name].update({
                                    'spearman_r': float(spearman_r),
                                    'spearman_p': float(spearman_p)
                                })
                        except:
                            pass
            
            return correlations
            
        except Exception as e:
            print(f"⚠️ Error in correlation analysis: {e}")
            return {}
    
    def stability_selection(self, X, y, feature_names, n_bootstrap=20):
        """Perform stability selection to identify robust features"""
        
        try:
            if len(X) < self.config['min_observations']:
                return {}
            
            feature_selection_counts = {name: 0 for name in feature_names}
            
            # Bootstrap sampling
            for bootstrap in range(n_bootstrap):
                # Random subsample
                n_samples = len(X)
                subsample_size = max(self.config['min_observations'], int(0.8 * n_samples))
                
                if subsample_size >= n_samples:
                    subsample_indices = np.arange(n_samples)
                else:
                    subsample_indices = np.random.choice(
                        n_samples, subsample_size, replace=False
                    )
                
                X_sub = X[subsample_indices]
                y_sub = y[subsample_indices]
                
                # Fit LASSO on subsample
                try:
                    scaler = RobustScaler()
                    X_sub_scaled = scaler.fit_transform(X_sub)
                    
                    lasso = LassoCV(
                        alphas=self.config['lasso_alpha_range'][:20],  # Fewer alphas for speed
                        cv=3,
                        random_state=42 + bootstrap,
                        max_iter=1000
                    )
                    
                    lasso.fit(X_sub_scaled, y_sub)
                    
                    # Count selected features
                    for i, (coef, feature_name) in enumerate(zip(lasso.coef_, feature_names)):
                        if abs(coef) > self.config['min_beta_threshold']:
                            feature_selection_counts[feature_name] += 1
                            
                except:
                    continue
            
            # Calculate stability scores
            stability_scores = {}
            for feature_name, count in feature_selection_counts.items():
                stability_score = count / n_bootstrap
                if stability_score >= self.config['stability_threshold']:
                    stability_scores[feature_name] = {
                        'stability_score': float(stability_score),
                        'selection_frequency': int(count),
                        'total_bootstraps': n_bootstrap
                    }
            
            return stability_scores
            
        except Exception as e:
            print(f"⚠️ Error in stability selection: {e}")
            return {}
    
    def granger_causality_test(self, X, y, feature_names, max_lags=None):
        """Simple Granger causality test implementation"""
        
        try:
            if max_lags is None:
                max_lags = self.config['granger_max_lags']
            
            if len(X) < max_lags + self.config['min_observations']:
                return {}
            
            granger_results = {}
            
            for i, feature_name in enumerate(feature_names):
                if i < X.shape[1]:
                    x_feature = X[:, i]
                    
                    # Test if x_feature Granger-causes y
                    try:
                        # Restricted model: y regressed on its own lags
                        y_lags = np.column_stack([
                            np.roll(y, lag)[max_lags:] 
                            for lag in range(1, max_lags + 1)
                        ])
                        y_current = y[max_lags:]
                        
                        if len(y_current) < self.config['min_observations']:
                            continue
                        
                        # Fit restricted model
                        from sklearn.linear_model import LinearRegression
                        
                        restricted_model = LinearRegression()
                        restricted_model.fit(y_lags, y_current)
                        y_pred_restricted = restricted_model.predict(y_lags)
                        rss_restricted = np.sum((y_current - y_pred_restricted) ** 2)
                        
                        # Unrestricted model: y regressed on its own lags + x lags
                        x_lags = np.column_stack([
                            np.roll(x_feature, lag)[max_lags:] 
                            for lag in range(1, max_lags + 1)
                        ])
                        
                        X_unrestricted = np.column_stack([y_lags, x_lags])
                        
                        unrestricted_model = LinearRegression()
                        unrestricted_model.fit(X_unrestricted, y_current)
                        y_pred_unrestricted = unrestricted_model.predict(X_unrestricted)
                        rss_unrestricted = np.sum((y_current - y_pred_unrestricted) ** 2)
                        
                        # F-test
                        if rss_restricted > rss_unrestricted and rss_unrestricted > 0:
                            n = len(y_current)
                            k_restricted = y_lags.shape[1]
                            k_unrestricted = X_unrestricted.shape[1]
                            
                            f_stat = ((rss_restricted - rss_unrestricted) / (k_unrestricted - k_restricted)) / (rss_unrestricted / (n - k_unrestricted))
                            
                            # Simple p-value approximation
                            if f_stat > 2.0:  # Rough threshold
                                granger_results[feature_name] = {
                                    'f_statistic': float(f_stat),
                                    'granger_causes': True,
                                    'improvement': float((rss_restricted - rss_unrestricted) / rss_restricted)
                                }
                    
                    except Exception as e:
                        continue
            
            return granger_results
            
        except Exception as e:
            print(f"⚠️ Error in Granger causality test: {e}")
            return {}
    
    def combine_relationship_evidence(self, lasso_results, elastic_results, mi_results, 
                                    correlation_results, stability_results, granger_results):
        """Combine evidence from multiple methods to identify robust relationships"""
        
        try:
            # Get all unique features
            all_features = set()
            all_features.update(lasso_results.keys())
            all_features.update(elastic_results.keys())
            all_features.update(mi_results.keys())
            all_features.update(correlation_results.keys())
            all_features.update(stability_results.keys())
            all_features.update(granger_results.keys())
            
            combined_relationships = {}
            
            for feature in all_features:
                evidence = {}
                
                # LASSO evidence
                if feature in lasso_results:
                    evidence['lasso'] = lasso_results[feature]
                
                # Elastic Net evidence
                if feature in elastic_results:
                    evidence['elastic_net'] = elastic_results[feature]
                
                # Mutual information evidence
                if feature in mi_results:
                    evidence['mutual_info'] = mi_results[feature]
                
                # Correlation evidence
                if feature in correlation_results:
                    evidence['correlation'] = correlation_results[feature]
                
                # Stability evidence
                if feature in stability_results:
                    evidence['stability'] = stability_results[feature]
                
                # Granger causality evidence
                if feature in granger_results:
                    evidence['granger'] = granger_results[feature]
                
                # Calculate combined confidence score
                confidence_score = self.calculate_combined_confidence(evidence)
                
                if confidence_score >= self.config['confidence_threshold']:
                    combined_relationships[feature] = {
                        'evidence': evidence,
                        'confidence_score': confidence_score,
                        'strength_category': self.categorize_relationship_strength(evidence),
                        'primary_beta': self.extract_primary_beta(evidence),
                        'primary_direction': self.extract_primary_direction(evidence)
                    }
            
            return combined_relationships
            
        except Exception as e:
            print(f"⚠️ Error combining relationship evidence: {e}")
            return {}
    
    def calculate_combined_confidence(self, evidence):
        """Calculate combined confidence score from multiple evidence sources"""
        
        try:
            confidence_components = []
            
            # LASSO confidence (based on coefficient magnitude)
            if 'lasso' in evidence:
                lasso_conf = min(1.0, evidence['lasso']['abs_beta'] / 0.5)
                confidence_components.append(('lasso', lasso_conf, 0.3))
            
            # Elastic Net confidence
            if 'elastic_net' in evidence:
                elastic_conf = min(1.0, evidence['elastic_net']['abs_beta'] / 0.5)
                confidence_components.append(('elastic_net', elastic_conf, 0.2))
            
            # Mutual information confidence
            if 'mutual_info' in evidence:
                mi_conf = evidence['mutual_info']['normalized_mi']
                confidence_components.append(('mutual_info', mi_conf, 0.2))
            
            # Correlation confidence
            if 'correlation' in evidence:
                corr_conf = evidence['correlation']['abs_correlation']
                confidence_components.append(('correlation', corr_conf, 0.1))
            
            # Stability confidence
            if 'stability' in evidence:
                stab_conf = evidence['stability']['stability_score']
                confidence_components.append(('stability', stab_conf, 0.15))
            
            # Granger causality confidence
            if 'granger' in evidence:
                granger_conf = min(1.0, evidence['granger']['improvement'])
                confidence_components.append(('granger', granger_conf, 0.05))
            
            if not confidence_components:
                return 0.0
            
            # Weighted average
            total_weight = sum(weight for _, _, weight in confidence_components)
            weighted_sum = sum(conf * weight for _, conf, weight in confidence_components)
            
            combined_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
            
            return float(combined_confidence)
            
        except Exception as e:
            print(f"⚠️ Error calculating combined confidence: {e}")
            return 0.0
    
    def categorize_relationship_strength(self, evidence):
        """Categorize relationship strength based on evidence"""
        
        try:
            # Use the strongest evidence available
            max_strength = 0.0
            
            if 'lasso' in evidence:
                max_strength = max(max_strength, evidence['lasso']['abs_beta'])
            
            if 'elastic_net' in evidence:
                max_strength = max(max_strength, evidence['elastic_net']['abs_beta'])
            
            if 'correlation' in evidence:
                max_strength = max(max_strength, evidence['correlation']['abs_correlation'])
            
            # Categorize strength
            for category, (min_val, max_val) in self.strength_categories.items():
                if min_val <= max_strength < max_val:
                    return category
            
            return 'very_weak'
            
        except:
            return 'unknown'
    
    def extract_primary_beta(self, evidence):
        """Extract the primary beta coefficient"""
        
        try:
            # Prefer LASSO beta, then Elastic Net
            if 'lasso' in evidence:
                return evidence['lasso']['beta']
            elif 'elastic_net' in evidence:
                return evidence['elastic_net']['beta']
            elif 'correlation' in evidence:
                return evidence['correlation']['pearson_r']
            else:
                return 0.0
        except:
            return 0.0
    
    def extract_primary_direction(self, evidence):
        """Extract the primary direction of the relationship"""
        
        try:
            # Prefer LASSO direction, then Elastic Net
            if 'lasso' in evidence:
                return evidence['lasso']['direction']
            elif 'elastic_net' in evidence:
                return evidence['elastic_net']['direction']
            elif 'correlation' in evidence:
                return int(np.sign(evidence['correlation']['pearson_r']))
            else:
                return 0
        except:
            return 0
    
    def fit_relationships(self, X, y, feature_names):
        """Main method to fit and detect relationships"""
        
        try:
            if len(X) < self.config['min_observations'] or len(y) < self.config['min_observations']:
                return {}
            
            # Prepare lagged features
            X_lagged, lagged_feature_names = self.prepare_features(X, feature_names)
            
            # Run all analysis methods
            print("      🔍 LASSO regression...", end="")
            lasso_results, lasso_r2 = self.lasso_regression_analysis(X_lagged, y, lagged_feature_names)
            print(f" R²={lasso_r2:.3f}")
            
            print("      🔍 Elastic Net...", end="")
            elastic_results, elastic_r2 = self.elastic_net_analysis(X_lagged, y, lagged_feature_names)
            print(f" R²={elastic_r2:.3f}")
            
            print("      🔍 Mutual information...", end="")
            mi_results = self.mutual_information_analysis(X_lagged, y, lagged_feature_names)
            print(f" {len(mi_results)} features")
            
            print("      🔍 Correlations...", end="")
            correlation_results = self.correlation_analysis(X_lagged, y, lagged_feature_names)
            print(f" {len(correlation_results)} features")
            
            print("      🔍 Stability selection...", end="")
            stability_results = self.stability_selection(X_lagged, y, lagged_feature_names, n_bootstrap=10)
            print(f" {len(stability_results)} stable")
            
            print("      🔍 Granger causality...", end="")
            granger_results = self.granger_causality_test(X_lagged, y, lagged_feature_names)
            print(f" {len(granger_results)} causal")
            
            # Combine all evidence
            combined_relationships = self.combine_relationship_evidence(
                lasso_results, elastic_results, mi_results,
                correlation_results, stability_results, granger_results
            )
            
            return combined_relationships
            
        except Exception as e:
            print(f"❌ Error fitting relationships: {e}")
            return {}

def main():
    """Test the relationship model"""
    
    # Generate test data
    np.random.seed(42)
    n_samples = 50
    n_features = 10
    
    X = np.random.randn(n_samples, n_features)
    # Create some relationships
    y = 0.5 * X[:, 0] + 0.3 * X[:, 1] - 0.2 * X[:, 2] + 0.1 * np.random.randn(n_samples)
    
    feature_names = [f'feature_{i}' for i in range(n_features)]
    
    # Test the model
    model = WeeklyRelationshipModel()
    relationships = model.fit_relationships(X, y, feature_names)
    
    print(f"\n🧬 Detected {len(relationships)} relationships:")
    for feature, rel_info in relationships.items():
        print(f"   {feature}: confidence={rel_info['confidence_score']:.3f}, "
              f"beta={rel_info['primary_beta']:.3f}, "
              f"strength={rel_info['strength_category']}")
    
    return len(relationships) > 0

if __name__ == "__main__":
    main()