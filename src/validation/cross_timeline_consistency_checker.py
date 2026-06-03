#!/usr/bin/env python3
"""
🔄 CROSS-TIMELINE CONSISTENCY CHECKER - SHADOW REALITY PHASE 4.3
Performance Variance Attribution Across Multiple Timelines

This identifies components contributing to performance variance across timelines:
- Measures anticipatory capital allocation performance across periods
- Flags potential overfitting or regime dependence
- Generates variance attribution reports
- Identifies which Phase 3 components contribute to variance

Builds upon Phase3ComponentValidator to provide cross-timeline analysis
and identify consistency patterns across different market conditions.

Integration with Phase 3:
- Analyzes RegimeMemorySystem consistency across periods
- Evaluates SimpleTailwindEngine stability across regimes
- Tests NoEdgeDetector appropriateness across stress levels
- Measures AnticipatoryCapitalAllocator performance variance

Output: data/validation/cross_timeline_consistency.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from scipy import stats
from sklearn.metrics import mean_squared_error
import warnings
warnings.filterwarnings('ignore')

class CrossTimelineConsistencyChecker:
    """
    Cross-Timeline Consistency Checker for Phase 3 Components
    
    Analyzes consistency and variance patterns across multiple historical periods:
    - Identifies components contributing to performance variance
    - Measures anticipatory capital allocation performance across periods
    - Flags potential overfitting or regime dependence
    - Generates variance attribution reports
    - Provides recommendations for component improvements
    """
    
    def __init__(self):
        self.name = "Cross-Timeline Consistency Checker"
        self.version = "4.3.1"
        
        # Data paths
        self.paths = {
            'component_validation_results': 'data/validation/phase3_component_validation.parquet',
            'component_metadata': 'data/validation/phase3_component_metadata.json',
            'consistency_output': 'data/validation/cross_timeline_consistency.parquet',
            'consistency_metadata': 'data/validation/cross_timeline_consistency_metadata.json',
            'variance_attribution': 'data/validation/variance_attribution_report.json'
        }
        
        # Consistency thresholds
        self.thresholds = {
            'consistency': {
                'high_consistency': 0.8,      # CV < 0.2
                'medium_consistency': 0.6,    # CV < 0.4
                'low_consistency': 0.4        # CV < 0.6
            },
            'performance_variance': {
                'acceptable_variance': 0.3,   # Standard deviation of scores
                'high_variance': 0.5,         # Indicates potential issues
                'extreme_variance': 0.7       # Requires investigation
            },
            'regime_dependence': {
                'low_dependence': 0.3,        # Score difference across regimes
                'medium_dependence': 0.5,
                'high_dependence': 0.7
            }
        }
        
        # Component weights for overall consistency scoring
        self.component_weights = {
            'regime_memory': 0.3,
            'tailwind_engine': 0.25,
            'no_edge_detector': 0.2,
            'capital_allocator': 0.25
        }
        
        # Analysis results storage
        self.consistency_results = {}
    
    def load_component_validation_results(self) -> Dict[str, Any]:
        """Load results from Phase3ComponentValidator"""
        
        print("📊 Loading component validation results...")
        
        try:
            # Load validation results
            if os.path.exists(self.paths['component_validation_results']):
                results_df = pd.read_parquet(self.paths['component_validation_results'])
                print(f"   ✅ Loaded validation results: {len(results_df)} records")
            else:
                print("   ⚠️ No component validation results found")
                return {}
            
            # Load metadata
            metadata = {}
            if os.path.exists(self.paths['component_metadata']):
                with open(self.paths['component_metadata'], 'r') as f:
                    metadata = json.load(f)
                print(f"   ✅ Loaded validation metadata")
            
            return {
                'results_df': results_df,
                'metadata': metadata
            }
            
        except Exception as e:
            print(f"   ❌ Error loading component validation results: {e}")
            return {}
    
    def analyze_component_consistency(self, results_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze consistency of each component across timelines"""
        
        print("🔄 Analyzing component consistency across timelines...")
        
        component_consistency = {}
        
        # Get unique components and periods
        components = results_df['component'].unique()
        periods = results_df['period'].unique()
        
        print(f"   📊 Analyzing {len(components)} components across {len(periods)} periods")
        
        for component in components:
            component_data = results_df[results_df['component'] == component]
            
            if len(component_data) < 2:
                continue
            
            # Calculate consistency metrics
            scores = component_data['score'].values
            passed_rates = component_data['validation_passed'].astype(int).values
            
            # Basic statistics
            mean_score = np.mean(scores)
            std_score = np.std(scores)
            cv_score = std_score / mean_score if mean_score > 0 else float('inf')
            
            # Pass rate statistics
            pass_rate = np.mean(passed_rates)
            pass_consistency = 1.0 - np.std(passed_rates)  # Higher is more consistent
            
            # Range analysis
            score_range = np.max(scores) - np.min(scores)
            score_range_normalized = score_range / max(np.max(scores), 0.001)
            
            # Consistency classification
            if cv_score < 0.2:
                consistency_level = 'high'
                consistency_score = 0.9
            elif cv_score < 0.4:
                consistency_level = 'medium'
                consistency_score = 0.7
            elif cv_score < 0.6:
                consistency_level = 'low'
                consistency_score = 0.5
            else:
                consistency_level = 'very_low'
                consistency_score = 0.3
            
            # Period-specific analysis
            period_scores = {}
            for period in periods:
                period_data = component_data[component_data['period'] == period]
                if not period_data.empty:
                    period_scores[period] = {
                        'score': float(period_data['score'].iloc[0]),
                        'passed': bool(period_data['validation_passed'].iloc[0])
                    }
            
            # Identify best and worst performing periods
            if period_scores:
                sorted_periods = sorted(period_scores.items(), key=lambda x: x[1]['score'], reverse=True)
                best_period = sorted_periods[0]
                worst_period = sorted_periods[-1]
            else:
                best_period = worst_period = None
            
            component_consistency[component] = {
                'mean_score': float(mean_score),
                'std_score': float(std_score),
                'cv_score': float(cv_score),
                'score_range': float(score_range),
                'score_range_normalized': float(score_range_normalized),
                'pass_rate': float(pass_rate),
                'pass_consistency': float(pass_consistency),
                'consistency_level': consistency_level,
                'consistency_score': float(consistency_score),
                'period_scores': period_scores,
                'best_period': best_period,
                'worst_period': worst_period,
                'periods_analyzed': len(component_data)
            }
            
            print(f"   📊 {component}: {consistency_level} consistency (CV: {cv_score:.3f}, Pass rate: {pass_rate:.1%})")
        
        return component_consistency
    
    def analyze_regime_dependence(self, results_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze regime dependence of component performance"""
        
        print("🏛️ Analyzing regime dependence patterns...")
        
        # Define regime mappings for periods
        period_regime_mapping = {
            'crisis_2008': 'Crisis',
            'covid_crash_2020': 'Crisis',
            'recovery_2009': 'Expansion',
            'expansion_2014': 'Expansion',
            'inflation_shock_2022': 'Late-Expansion',
            'demonetization_2016': 'Slowdown',
            'current_period': 'Late-Expansion'
        }
        
        # Add regime column to results
        results_df['regime'] = results_df['period'].map(period_regime_mapping)
        
        regime_analysis = {}
        components = results_df['component'].unique()
        regimes = results_df['regime'].dropna().unique()
        
        print(f"   📊 Analyzing {len(components)} components across {len(regimes)} regimes")
        
        for component in components:
            component_data = results_df[results_df['component'] == component]
            
            regime_performance = {}
            regime_scores = []
            
            for regime in regimes:
                regime_data = component_data[component_data['regime'] == regime]
                
                if not regime_data.empty:
                    regime_score = regime_data['score'].mean()
                    regime_pass_rate = regime_data['validation_passed'].astype(int).mean()
                    
                    regime_performance[regime] = {
                        'mean_score': float(regime_score),
                        'pass_rate': float(regime_pass_rate),
                        'periods_count': len(regime_data)
                    }
                    regime_scores.append(regime_score)
            
            # Calculate regime dependence metrics
            if len(regime_scores) > 1:
                regime_variance = np.var(regime_scores)
                regime_range = np.max(regime_scores) - np.min(regime_scores)
                regime_cv = np.std(regime_scores) / np.mean(regime_scores) if np.mean(regime_scores) > 0 else float('inf')
                
                # Classify regime dependence
                if regime_range < 0.3:
                    dependence_level = 'low'
                    dependence_score = 0.9
                elif regime_range < 0.5:
                    dependence_level = 'medium'
                    dependence_score = 0.7
                elif regime_range < 0.7:
                    dependence_level = 'high'
                    dependence_score = 0.5
                else:
                    dependence_level = 'extreme'
                    dependence_score = 0.3
            else:
                regime_variance = 0.0
                regime_range = 0.0
                regime_cv = 0.0
                dependence_level = 'unknown'
                dependence_score = 0.5
            
            # Identify best and worst regimes
            if regime_performance:
                sorted_regimes = sorted(regime_performance.items(), key=lambda x: x[1]['mean_score'], reverse=True)
                best_regime = sorted_regimes[0]
                worst_regime = sorted_regimes[-1]
            else:
                best_regime = worst_regime = None
            
            regime_analysis[component] = {
                'regime_performance': regime_performance,
                'regime_variance': float(regime_variance),
                'regime_range': float(regime_range),
                'regime_cv': float(regime_cv),
                'dependence_level': dependence_level,
                'dependence_score': float(dependence_score),
                'best_regime': best_regime,
                'worst_regime': worst_regime,
                'regimes_analyzed': len(regime_performance)
            }
            
            print(f"   🏛️ {component}: {dependence_level} regime dependence (range: {regime_range:.3f})")
        
        return regime_analysis
    
    def analyze_performance_variance(self, results_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze performance variance patterns across timelines"""
        
        print("📈 Analyzing performance variance patterns...")
        
        variance_analysis = {}
        
        # Overall system variance
        overall_scores = results_df.groupby('period')['score'].mean()
        overall_variance = np.var(overall_scores)
        overall_std = np.std(overall_scores)
        overall_cv = overall_std / np.mean(overall_scores) if np.mean(overall_scores) > 0 else float('inf')
        
        # Component contribution to variance
        components = results_df['component'].unique()
        periods = results_df['period'].unique()
        
        component_variance_contribution = {}
        
        for component in components:
            component_data = results_df[results_df['component'] == component]
            component_scores = []
            
            for period in periods:
                period_data = component_data[component_data['period'] == period]
                if not period_data.empty:
                    component_scores.append(period_data['score'].iloc[0])
            
            if len(component_scores) > 1:
                component_variance = np.var(component_scores)
                component_std = np.std(component_scores)
                
                # Calculate contribution to overall variance
                variance_contribution = component_variance / max(overall_variance, 0.001)
                
                component_variance_contribution[component] = {
                    'variance': float(component_variance),
                    'std': float(component_std),
                    'contribution_to_overall': float(variance_contribution),
                    'scores': component_scores
                }
        
        # Identify high-variance components
        high_variance_components = []
        for component, data in component_variance_contribution.items():
            if data['std'] > self.thresholds['performance_variance']['high_variance']:
                high_variance_components.append(component)
        
        # Calculate variance attribution
        total_contribution = sum(data['contribution_to_overall'] for data in component_variance_contribution.values())
        
        variance_attribution = {}
        for component, data in component_variance_contribution.items():
            attribution_pct = (data['contribution_to_overall'] / max(total_contribution, 0.001)) * 100
            variance_attribution[component] = float(attribution_pct)
        
        variance_analysis = {
            'overall_variance': float(overall_variance),
            'overall_std': float(overall_std),
            'overall_cv': float(overall_cv),
            'component_variance_contribution': component_variance_contribution,
            'high_variance_components': high_variance_components,
            'variance_attribution': variance_attribution,
            'periods_analyzed': len(periods)
        }
        
        print(f"   📊 Overall variance: {overall_variance:.4f} (CV: {overall_cv:.3f})")
        print(f"   ⚠️ High variance components: {len(high_variance_components)}")
        
        return variance_analysis
    
    def identify_overfitting_patterns(self, results_df: pd.DataFrame) -> Dict[str, Any]:
        """Identify potential overfitting or regime dependence patterns"""
        
        print("🔍 Identifying potential overfitting patterns...")
        
        overfitting_analysis = {}
        components = results_df['component'].unique()
        
        for component in components:
            component_data = results_df[results_df['component'] == component]
            
            if len(component_data) < 3:
                continue
            
            scores = component_data['score'].values
            periods = component_data['period'].values
            
            # Check for extreme performance differences
            score_range = np.max(scores) - np.min(scores)
            score_std = np.std(scores)
            
            # Identify outlier periods
            z_scores = np.abs(stats.zscore(scores))
            outlier_threshold = 2.0
            outlier_periods = periods[z_scores > outlier_threshold]
            
            # Check for monotonic trends (potential overfitting to chronological order)
            if len(scores) > 2:
                # Sort by period chronologically (simplified)
                period_order = {'crisis_2008': 1, 'recovery_2009': 2, 'expansion_2014': 3, 
                              'demonetization_2016': 4, 'covid_crash_2020': 5, 
                              'inflation_shock_2022': 6, 'current_period': 7}
                
                ordered_data = [(period_order.get(period, 0), score) for period, score in zip(periods, scores)]
                ordered_data.sort(key=lambda x: x[0])
                
                if len(ordered_data) > 2:
                    ordered_scores = [x[1] for x in ordered_data]
                    correlation_with_time = stats.pearsonr(range(len(ordered_scores)), ordered_scores)[0]
                else:
                    correlation_with_time = 0.0
            else:
                correlation_with_time = 0.0
            
            # Overfitting risk assessment
            overfitting_risk = 0.0
            risk_factors = []
            
            # High variance across periods
            if score_std > 0.4:
                overfitting_risk += 0.3
                risk_factors.append("High variance across periods")
            
            # Extreme outliers
            if len(outlier_periods) > 0:
                overfitting_risk += 0.2 * len(outlier_periods)
                risk_factors.append(f"Outlier performance in {len(outlier_periods)} periods")
            
            # Strong temporal correlation
            if abs(correlation_with_time) > 0.7:
                overfitting_risk += 0.3
                risk_factors.append("Strong temporal correlation")
            
            # Large score range
            if score_range > 0.6:
                overfitting_risk += 0.2
                risk_factors.append("Large performance range")
            
            overfitting_risk = min(1.0, overfitting_risk)
            
            # Risk classification
            if overfitting_risk < 0.3:
                risk_level = 'low'
            elif overfitting_risk < 0.6:
                risk_level = 'medium'
            else:
                risk_level = 'high'
            
            overfitting_analysis[component] = {
                'overfitting_risk': float(overfitting_risk),
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'score_range': float(score_range),
                'score_std': float(score_std),
                'outlier_periods': outlier_periods.tolist(),
                'temporal_correlation': float(correlation_with_time)
            }
            
            print(f"   🔍 {component}: {risk_level} overfitting risk ({overfitting_risk:.3f})")
        
        return overfitting_analysis
    
    def generate_consistency_recommendations(self, component_consistency: Dict, regime_analysis: Dict, 
                                          variance_analysis: Dict, overfitting_analysis: Dict) -> List[Dict[str, Any]]:
        """Generate recommendations for improving component consistency"""
        
        print("💡 Generating consistency improvement recommendations...")
        
        recommendations = []
        
        # Component-specific recommendations
        for component in component_consistency.keys():
            component_recs = []
            
            # Consistency issues
            consistency_data = component_consistency[component]
            if consistency_data['consistency_level'] in ['low', 'very_low']:
                component_recs.append({
                    'type': 'consistency',
                    'priority': 'high',
                    'issue': f"Low consistency across periods (CV: {consistency_data['cv_score']:.3f})",
                    'recommendation': "Review component parameters and consider adaptive thresholds"
                })
            
            # Regime dependence issues
            if component in regime_analysis:
                regime_data = regime_analysis[component]
                if regime_data['dependence_level'] in ['high', 'extreme']:
                    component_recs.append({
                        'type': 'regime_dependence',
                        'priority': 'medium',
                        'issue': f"High regime dependence (range: {regime_data['regime_range']:.3f})",
                        'recommendation': "Consider regime-adaptive parameters or normalization"
                    })
            
            # Overfitting issues
            if component in overfitting_analysis:
                overfitting_data = overfitting_analysis[component]
                if overfitting_data['risk_level'] == 'high':
                    component_recs.append({
                        'type': 'overfitting',
                        'priority': 'high',
                        'issue': f"High overfitting risk ({overfitting_data['overfitting_risk']:.3f})",
                        'recommendation': "Validate on additional out-of-sample periods"
                    })
            
            # Variance contribution issues
            if component in variance_analysis['component_variance_contribution']:
                variance_contrib = variance_analysis['variance_attribution'].get(component, 0)
                if variance_contrib > 40:  # Contributing more than 40% to overall variance
                    component_recs.append({
                        'type': 'variance',
                        'priority': 'medium',
                        'issue': f"High variance contribution ({variance_contrib:.1f}%)",
                        'recommendation': "Investigate component stability and consider regularization"
                    })
            
            if component_recs:
                recommendations.append({
                    'component': component,
                    'recommendations': component_recs
                })
        
        # System-level recommendations
        system_recs = []
        
        # Overall variance issues
        if variance_analysis['overall_cv'] > 0.5:
            system_recs.append({
                'type': 'system_variance',
                'priority': 'high',
                'issue': f"High overall system variance (CV: {variance_analysis['overall_cv']:.3f})",
                'recommendation': "Consider ensemble methods or variance reduction techniques"
            })
        
        # High variance components
        if len(variance_analysis['high_variance_components']) > 2:
            system_recs.append({
                'type': 'multiple_variance',
                'priority': 'medium',
                'issue': f"{len(variance_analysis['high_variance_components'])} components show high variance",
                'recommendation': "Systematic review of component validation thresholds needed"
            })
        
        if system_recs:
            recommendations.append({
                'component': 'system',
                'recommendations': system_recs
            })
        
        print(f"   💡 Generated {len(recommendations)} recommendation categories")
        
        return recommendations
    
    def run_cross_timeline_analysis(self, component_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run comprehensive cross-timeline consistency analysis"""
        
        print("🔄 CROSS-TIMELINE CONSISTENCY CHECKER")
        print("Performance Variance Attribution Across Multiple Timelines")
        print("=" * 70)
        
        # Load component validation results if not provided
        if component_results is None:
            component_results = self.load_component_validation_results()
        
        if not component_results or 'results_df' not in component_results:
            print("❌ No component validation results available")
            return {}
        
        results_df = component_results['results_df']
        
        print(f"📊 Analyzing {len(results_df)} component validation records")
        print(f"   Components: {results_df['component'].nunique()}")
        print(f"   Periods: {results_df['period'].nunique()}")
        
        # Run all analyses
        print(f"\n🔍 Running cross-timeline consistency analysis...")
        
        # 1. Component consistency analysis
        component_consistency = self.analyze_component_consistency(results_df)
        
        # 2. Regime dependence analysis
        regime_analysis = self.analyze_regime_dependence(results_df)
        
        # 3. Performance variance analysis
        variance_analysis = self.analyze_performance_variance(results_df)
        
        # 4. Overfitting pattern identification
        overfitting_analysis = self.identify_overfitting_patterns(results_df)
        
        # 5. Generate recommendations
        recommendations = self.generate_consistency_recommendations(
            component_consistency, regime_analysis, variance_analysis, overfitting_analysis
        )
        
        # Calculate overall consistency score
        component_scores = []
        for component, data in component_consistency.items():
            weighted_score = data['consistency_score'] * self.component_weights.get(component, 0.25)
            component_scores.append(weighted_score)
        
        overall_consistency_score = sum(component_scores) if component_scores else 0.0
        
        # Determine overall consistency level
        if overall_consistency_score >= 0.8:
            overall_consistency_level = 'high'
        elif overall_consistency_score >= 0.6:
            overall_consistency_level = 'medium'
        elif overall_consistency_score >= 0.4:
            overall_consistency_level = 'low'
        else:
            overall_consistency_level = 'very_low'
        
        # Compile final results
        consistency_results = {
            'overall_consistency_score': float(overall_consistency_score),
            'overall_consistency_level': overall_consistency_level,
            'component_consistency': component_consistency,
            'regime_analysis': regime_analysis,
            'variance_analysis': variance_analysis,
            'overfitting_analysis': overfitting_analysis,
            'recommendations': recommendations,
            'analysis_timestamp': datetime.now().isoformat(),
            'analyzer_version': self.version
        }
        
        # Print summary
        print(f"\n" + "="*70)
        print("📊 CROSS-TIMELINE CONSISTENCY SUMMARY")
        print("="*70)
        
        print(f"🎯 Overall Consistency: {overall_consistency_level.upper()} ({overall_consistency_score:.3f})")
        
        print(f"\n📋 Component Consistency:")
        for component, data in component_consistency.items():
            print(f"   {component}: {data['consistency_level']} ({data['consistency_score']:.3f})")
        
        print(f"\n🏛️ Regime Dependence:")
        for component, data in regime_analysis.items():
            print(f"   {component}: {data['dependence_level']} dependence")
        
        print(f"\n⚠️ High Risk Components:")
        high_risk_components = []
        for component, data in overfitting_analysis.items():
            if data['risk_level'] == 'high':
                high_risk_components.append(component)
                print(f"   {component}: {data['risk_level']} overfitting risk")
        
        if not high_risk_components:
            print("   None identified")
        
        print(f"\n💡 Recommendations: {len(recommendations)} categories")
        
        # Store results
        self.consistency_results = consistency_results
        
        return consistency_results
    
    def save_consistency_results(self, results: Dict[str, Any]) -> bool:
        """Save cross-timeline consistency results"""
        
        try:
            # Create output directory
            os.makedirs(os.path.dirname(self.paths['consistency_output']), exist_ok=True)
            
            # Prepare flattened results for parquet
            flattened_results = []
            
            # Component consistency data
            for component, data in results['component_consistency'].items():
                flattened_results.append({
                    'analysis_type': 'consistency',
                    'component': component,
                    'metric': 'consistency_score',
                    'value': data['consistency_score'],
                    'level': data['consistency_level'],
                    'analysis_timestamp': results['analysis_timestamp']
                })
            
            # Regime dependence data
            for component, data in results['regime_analysis'].items():
                flattened_results.append({
                    'analysis_type': 'regime_dependence',
                    'component': component,
                    'metric': 'dependence_score',
                    'value': data['dependence_score'],
                    'level': data['dependence_level'],
                    'analysis_timestamp': results['analysis_timestamp']
                })
            
            # Overfitting risk data
            for component, data in results['overfitting_analysis'].items():
                flattened_results.append({
                    'analysis_type': 'overfitting_risk',
                    'component': component,
                    'metric': 'risk_score',
                    'value': data['overfitting_risk'],
                    'level': data['risk_level'],
                    'analysis_timestamp': results['analysis_timestamp']
                })
            
            # Save to parquet
            if flattened_results:
                results_df = pd.DataFrame(flattened_results)
                results_df.to_parquet(self.paths['consistency_output'], index=False)
                print(f"   💾 Saved consistency results: {self.paths['consistency_output']}")
            
            # Save detailed metadata
            metadata = {
                'overall_consistency_score': results['overall_consistency_score'],
                'overall_consistency_level': results['overall_consistency_level'],
                'variance_analysis': results['variance_analysis'],
                'recommendations': results['recommendations'],
                'analysis_timestamp': results['analysis_timestamp'],
                'analyzer_version': results['analyzer_version']
            }
            
            with open(self.paths['consistency_metadata'], 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"   💾 Saved consistency metadata: {self.paths['consistency_metadata']}")
            
            # Save variance attribution report
            variance_report = {
                'variance_attribution': results['variance_analysis']['variance_attribution'],
                'high_variance_components': results['variance_analysis']['high_variance_components'],
                'overall_variance': results['variance_analysis']['overall_variance'],
                'recommendations': results['recommendations'],
                'analysis_timestamp': results['analysis_timestamp']
            }
            
            with open(self.paths['variance_attribution'], 'w') as f:
                json.dump(variance_report, f, indent=2)
            
            print(f"   💾 Saved variance attribution: {self.paths['variance_attribution']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving consistency results: {e}")
            return False

def main():
    """Run Cross-Timeline Consistency Analysis"""
    
    checker = CrossTimelineConsistencyChecker()
    
    print("🔄 CROSS-TIMELINE CONSISTENCY CHECKER")
    print("Performance Variance Attribution Across Multiple Timelines")
    print("=" * 70)
    
    # Run comprehensive analysis
    results = checker.run_cross_timeline_analysis()
    
    if results:
        # Save results
        checker.save_consistency_results(results)
        
        print(f"\n✅ Cross-timeline consistency analysis completed!")
        print("🎯 Variance attribution and recommendations generated")
        return True
    else:
        print(f"\n❌ Cross-timeline consistency analysis failed")
        print("🔧 Check component validation results availability")
        return False

if __name__ == "__main__":
    main()