#!/usr/bin/env python3
"""
🎭 REGIME-BASED SCENARIO GENERATOR - NORTHSTAR V3 PHASE 4.2
Advanced market simulation using Phase 3 regime patterns

This creates sophisticated market scenarios that:
1. Use Phase 3 regime memory patterns as scenario templates
2. Generate regime continuation and transition scenarios
3. Create regime breakdown and stress scenarios
4. Preserve Phase 3 regime fingerprint characteristics
5. Enable realistic testing of anticipatory intelligence

Phase 4.2 Enhancement over basic backtesting:
- Uses Phase 3 regime patterns as scenario foundations
- Generates realistic regime transitions and breakdowns
- Preserves statistical characteristics of historical regimes
- Creates scenarios where NO_EDGE detection should trigger
- Validates Phase 3 anticipatory signal generation

Integration with Phase 3:
- Uses RegimeMemorySystem regime fingerprints as templates
- Leverages SimpleTailwindEngine for scenario validation
- Tests NoEdgeDetector trigger conditions
- Validates AnticipatoryCapitalAllocator behavior
- Maintains V3 architecture compatibility

Output: data/shadow_reality/market_scenarios.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class RegimeBasedScenarioGenerator:
    """
    Regime-Based Market Scenario Generator
    
    Creates sophisticated market scenarios using Phase 3 regime patterns:
    - Regime continuation scenarios (extend current regime characteristics)
    - Regime transition scenarios (model transitions between regimes)
    - Regime breakdown scenarios (model failure of regime classification)
    - Stress scenarios (extreme conditions within regime context)
    """
    
    def __init__(self):
        self.name = "Regime-Based Scenario Generator"
        self.version = "4.2"
        
        # Data paths
        self.paths = {
            # Phase 3 inputs
            'regime_memory': 'data/intelligence/regime_memory.parquet',
            'regime_metadata': 'data/intelligence/regime_metadata.json',
            'strategy_tailwinds': 'data/intelligence/strategy_tailwinds.parquet',
            'no_edge_state': 'data/intelligence/no_edge_state.parquet',
            
            # Market data
            'market_state': 'data/processed/market_state.parquet',
            'macro_score': 'data/macro/factors/macro_score.parquet',
            'prices': 'data/processed/prices.parquet',
            
            # Scenario outputs
            'market_scenarios': 'data/shadow_reality/market_scenarios.parquet',
            'scenario_metadata': 'data/shadow_reality/scenario_metadata.json',
            'scenario_validation': 'data/shadow_reality/scenario_validation.parquet'
        }
        
        # Configuration
        self.config = {
            'scenario_length_days': 63,        # ~3 months per scenario
            'n_scenarios_per_type': 5,         # Number of scenarios per type
            'regime_similarity_threshold': 0.7, # Minimum similarity for regime matching
            'stress_multiplier': 2.0,          # Stress scenario intensity
            'transition_probability': 0.15,    # Daily regime transition probability
            'noise_level': 0.1,                # Random noise in scenarios
            'preserve_correlation': True,      # Preserve feature correlations
            'validate_scenarios': True         # Validate scenario realism
        }
        
        # Scenario types
        self.scenario_types = [
            'regime_continuation',    # Extend current regime
            'regime_transition',      # Transition to different regime
            'regime_breakdown',       # Regime classification fails
            'stress_scenario'         # Extreme conditions
        ]
        
        # Phase 3 component data
        self.regime_memory = None
        self.regime_fingerprints = None
        self.regime_transitions = None
        self.scaler = StandardScaler()
    
    def load_phase3_data(self) -> Dict[str, Any]:
        """Load Phase 3 component data for scenario generation"""
        
        print("📊 Loading Phase 3 data for scenario generation...")
        
        phase3_data = {
            'regime_memory': None,
            'regime_metadata': None,
            'current_regime': None,
            'regime_characteristics': {},
            'transition_matrix': None
        }
        
        try:
            # Load regime memory
            if os.path.exists(self.paths['regime_memory']):
                regime_memory = pd.read_parquet(self.paths['regime_memory'])
                phase3_data['regime_memory'] = regime_memory
                self.regime_memory = regime_memory
                print(f"   ✅ Regime memory: {len(regime_memory)} periods")
                
                # Get current regime
                if not regime_memory.empty:
                    current_regime = regime_memory.iloc[-1]['Regime']
                    phase3_data['current_regime'] = current_regime
                    print(f"   📊 Current regime: {current_regime}")
            
            # Load regime metadata
            if os.path.exists(self.paths['regime_metadata']):
                with open(self.paths['regime_metadata'], 'r') as f:
                    regime_metadata = json.load(f)
                    phase3_data['regime_metadata'] = regime_metadata
                    print(f"   ✅ Regime metadata loaded")
            
            # Calculate regime characteristics
            if phase3_data['regime_memory'] is not None:
                regime_chars = self._calculate_regime_characteristics(regime_memory)
                phase3_data['regime_characteristics'] = regime_chars
                print(f"   📈 Regime characteristics: {len(regime_chars)} regimes")
            
            # Calculate transition matrix
            if phase3_data['regime_memory'] is not None:
                transition_matrix = self._calculate_transition_matrix(regime_memory)
                phase3_data['transition_matrix'] = transition_matrix
                print(f"   🔄 Transition matrix calculated")
            
        except Exception as e:
            print(f"   ⚠️ Error loading Phase 3 data: {e}")
        
        return phase3_data
    
    def _calculate_regime_characteristics(self, regime_memory: pd.DataFrame) -> Dict[str, Dict]:
        """Calculate statistical characteristics for each regime"""
        
        regime_characteristics = {}
        
        # Get feature columns (scaled versions for consistency)
        feature_cols = [col for col in regime_memory.columns 
                       if col.endswith('_scaled') or col in ['MacroScore', 'Contrib_G', 'Contrib_I']]
        
        if not feature_cols:
            # Fallback to basic columns
            feature_cols = [col for col in regime_memory.columns 
                           if col not in ['Regime', 'regime_avg_return', 'regime_sharpe']]
        
        for regime in regime_memory['Regime'].unique():
            if pd.isna(regime):
                continue
            
            regime_data = regime_memory[regime_memory['Regime'] == regime]
            
            if len(regime_data) >= 3:  # Need minimum data for statistics
                # Calculate feature statistics
                feature_stats = {}
                for col in feature_cols:
                    if col in regime_data.columns:
                        values = regime_data[col].dropna()
                        if len(values) > 0:
                            feature_stats[col] = {
                                'mean': float(values.mean()),
                                'std': float(values.std()),
                                'min': float(values.min()),
                                'max': float(values.max()),
                                'median': float(values.median())
                            }
                
                # Calculate performance statistics
                perf_stats = {}
                if 'regime_avg_return' in regime_data.columns:
                    perf_stats['avg_return'] = float(regime_data['regime_avg_return'].mean())
                if 'regime_sharpe' in regime_data.columns:
                    perf_stats['avg_sharpe'] = float(regime_data['regime_sharpe'].mean())
                
                regime_characteristics[regime] = {
                    'n_periods': len(regime_data),
                    'frequency': len(regime_data) / len(regime_memory),
                    'feature_stats': feature_stats,
                    'performance_stats': perf_stats,
                    'recent_occurrences': regime_data.tail(3).index.strftime('%Y-%m-%d').tolist()
                }
        
        return regime_characteristics
    
    def _calculate_transition_matrix(self, regime_memory: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Calculate regime transition probabilities"""
        
        regimes = regime_memory['Regime'].values
        unique_regimes = list(regime_memory['Regime'].unique())
        unique_regimes = [r for r in unique_regimes if not pd.isna(r)]
        
        # Initialize transition matrix
        transition_counts = {}
        for from_regime in unique_regimes:
            transition_counts[from_regime] = {}
            for to_regime in unique_regimes:
                transition_counts[from_regime][to_regime] = 0
        
        # Count transitions
        for i in range(len(regimes) - 1):
            current_regime = regimes[i]
            next_regime = regimes[i + 1]
            
            if not pd.isna(current_regime) and not pd.isna(next_regime):
                if current_regime in transition_counts and next_regime in transition_counts[current_regime]:
                    transition_counts[current_regime][next_regime] += 1
        
        # Convert to probabilities
        transition_matrix = {}
        for from_regime in unique_regimes:
            total_transitions = sum(transition_counts[from_regime].values())
            transition_matrix[from_regime] = {}
            
            for to_regime in unique_regimes:
                if total_transitions > 0:
                    prob = transition_counts[from_regime][to_regime] / total_transitions
                else:
                    prob = 1.0 / len(unique_regimes)  # Uniform if no data
                
                transition_matrix[from_regime][to_regime] = prob
        
        return transition_matrix
    
    def generate_regime_continuation_scenario(self, regime: str, 
                                            regime_characteristics: Dict[str, Dict],
                                            length_days: int = 63) -> pd.DataFrame:
        """Generate scenario where current regime continues"""
        
        print(f"🔄 Generating regime continuation scenario for {regime}...")
        
        if regime not in regime_characteristics:
            print(f"   ⚠️ No characteristics found for regime {regime}")
            return pd.DataFrame()
        
        regime_chars = regime_characteristics[regime]
        feature_stats = regime_chars['feature_stats']
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Generate scenario data
        scenario_data = []
        
        for date in dates:
            scenario_point = {'date': date, 'scenario_type': 'regime_continuation', 'regime': regime}
            
            # Generate features based on regime characteristics
            for feature, stats in feature_stats.items():
                # Sample from normal distribution with regime-specific parameters
                value = np.random.normal(stats['mean'], stats['std'])
                
                # Add some persistence (AR(1) process)
                if scenario_data:  # Not first point
                    prev_value = scenario_data[-1].get(feature, stats['mean'])
                    value = 0.7 * prev_value + 0.3 * value  # 70% persistence
                
                # Ensure reasonable bounds
                value = np.clip(value, stats['min'] - stats['std'], stats['max'] + stats['std'])
                scenario_point[feature] = value
            
            scenario_data.append(scenario_point)
        
        scenario_df = pd.DataFrame(scenario_data)
        scenario_df = scenario_df.set_index('date')
        
        print(f"   ✅ Generated {len(scenario_df)} day continuation scenario")
        return scenario_df
    
    def generate_regime_transition_scenario(self, from_regime: str, to_regime: str,
                                          regime_characteristics: Dict[str, Dict],
                                          length_days: int = 63) -> pd.DataFrame:
        """Generate scenario with regime transition"""
        
        print(f"🔄 Generating regime transition scenario: {from_regime} → {to_regime}...")
        
        if from_regime not in regime_characteristics or to_regime not in regime_characteristics:
            print(f"   ⚠️ Missing characteristics for regime transition")
            return pd.DataFrame()
        
        from_chars = regime_characteristics[from_regime]['feature_stats']
        to_chars = regime_characteristics[to_regime]['feature_stats']
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Transition point (randomly in middle third of scenario)
        transition_day = np.random.randint(length_days // 3, 2 * length_days // 3)
        
        scenario_data = []
        
        for i, date in enumerate(dates):
            # Determine current regime and transition progress
            if i < transition_day:
                current_regime = from_regime
                transition_progress = 0.0
            elif i < transition_day + 10:  # 10-day transition period
                current_regime = f"{from_regime}_to_{to_regime}"
                transition_progress = (i - transition_day) / 10.0
            else:
                current_regime = to_regime
                transition_progress = 1.0
            
            scenario_point = {
                'date': date, 
                'scenario_type': 'regime_transition', 
                'regime': current_regime,
                'transition_progress': transition_progress
            }
            
            # Generate features with transition
            common_features = set(from_chars.keys()) & set(to_chars.keys())
            
            for feature in common_features:
                from_stats = from_chars[feature]
                to_stats = to_chars[feature]
                
                # Interpolate between regimes during transition
                mean_value = (1 - transition_progress) * from_stats['mean'] + transition_progress * to_stats['mean']
                std_value = (1 - transition_progress) * from_stats['std'] + transition_progress * to_stats['std']
                
                # Generate value
                value = np.random.normal(mean_value, std_value)
                
                # Add persistence
                if scenario_data:
                    prev_value = scenario_data[-1].get(feature, mean_value)
                    value = 0.6 * prev_value + 0.4 * value  # Less persistence during transition
                
                scenario_point[feature] = value
            
            scenario_data.append(scenario_point)
        
        scenario_df = pd.DataFrame(scenario_data)
        scenario_df = scenario_df.set_index('date')
        
        print(f"   ✅ Generated {len(scenario_df)} day transition scenario (transition on day {transition_day})")
        return scenario_df
    
    def generate_regime_breakdown_scenario(self, regime: str,
                                         regime_characteristics: Dict[str, Dict],
                                         length_days: int = 63) -> pd.DataFrame:
        """Generate scenario where regime classification breaks down"""
        
        print(f"💥 Generating regime breakdown scenario for {regime}...")
        
        if regime not in regime_characteristics:
            print(f"   ⚠️ No characteristics found for regime {regime}")
            return pd.DataFrame()
        
        regime_chars = regime_characteristics[regime]
        feature_stats = regime_chars['feature_stats']
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Breakdown point (randomly in first half)
        breakdown_day = np.random.randint(length_days // 4, length_days // 2)
        
        scenario_data = []
        
        for i, date in enumerate(dates):
            if i < breakdown_day:
                scenario_type = 'regime_breakdown_normal'
                noise_multiplier = 1.0
            else:
                scenario_type = 'regime_breakdown_chaos'
                noise_multiplier = 3.0  # High noise after breakdown
            
            scenario_point = {
                'date': date, 
                'scenario_type': scenario_type, 
                'regime': regime if i < breakdown_day else 'BREAKDOWN',
                'breakdown_intensity': min(1.0, (i - breakdown_day) / 10.0) if i >= breakdown_day else 0.0
            }
            
            # Generate features with increasing chaos
            for feature, stats in feature_stats.items():
                if i < breakdown_day:
                    # Normal regime behavior
                    value = np.random.normal(stats['mean'], stats['std'])
                else:
                    # Breakdown: features become uncorrelated and noisy
                    base_value = np.random.normal(stats['mean'], stats['std'] * noise_multiplier)
                    chaos_component = np.random.normal(0, stats['std'] * 2)
                    value = base_value + chaos_component
                
                # Reduced persistence during breakdown
                if scenario_data:
                    prev_value = scenario_data[-1].get(feature, stats['mean'])
                    persistence = 0.8 if i < breakdown_day else 0.2
                    value = persistence * prev_value + (1 - persistence) * value
                
                scenario_point[feature] = value
            
            scenario_data.append(scenario_point)
        
        scenario_df = pd.DataFrame(scenario_data)
        scenario_df = scenario_df.set_index('date')
        
        print(f"   ✅ Generated {len(scenario_df)} day breakdown scenario (breakdown on day {breakdown_day})")
        return scenario_df
    
    def generate_stress_scenario(self, regime: str,
                               regime_characteristics: Dict[str, Dict],
                               length_days: int = 63) -> pd.DataFrame:
        """Generate extreme stress scenario within regime context"""
        
        print(f"⚡ Generating stress scenario for {regime}...")
        
        if regime not in regime_characteristics:
            print(f"   ⚠️ No characteristics found for regime {regime}")
            return pd.DataFrame()
        
        regime_chars = regime_characteristics[regime]
        feature_stats = regime_chars['feature_stats']
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Stress event timing (multiple stress events)
        stress_events = []
        
        # Adjust number of events based on scenario length to ensure sufficient stress coverage
        if length_days < 15:
            n_events = 1  # Single event for short scenarios
        elif length_days < 30:
            n_events = np.random.randint(1, 3)  # 1-2 events for medium scenarios
        else:
            max_events = max(2, min(4, length_days // 8))  # More events for longer scenarios
            n_events = np.random.randint(2, max_events + 1)  # At least 2 events for long scenarios
        
        for _ in range(n_events):
            # Ensure valid range for event timing
            min_start = max(1, length_days // 15)  # Start earlier
            max_start = max(min_start + 1, length_days - max(2, length_days // 15))  # End later
            
            if min_start < max_start:
                event_day = np.random.randint(min_start, max_start)
            else:
                event_day = min_start
            
            # Event duration based on scenario length - ensure minimum coverage
            min_duration = max(2, length_days // 20)  # Minimum duration
            max_duration = min(max(5, length_days // 4), 12)  # Maximum duration
            event_duration = np.random.randint(min_duration, max_duration + 1)
            
            stress_events.append((event_day, event_duration))
        
        scenario_data = []
        
        for i, date in enumerate(dates):
            # Check if we're in a stress event
            stress_intensity = 0.0
            for event_start, event_duration in stress_events:
                if event_start <= i < event_start + event_duration:
                    # Stress intensity peaks in middle of event
                    event_progress = (i - event_start) / event_duration
                    stress_intensity = max(stress_intensity, 
                                         np.sin(event_progress * np.pi) * self.config['stress_multiplier'])
            
            scenario_point = {
                'date': date, 
                'scenario_type': 'stress_scenario', 
                'regime': regime,
                'stress_intensity': stress_intensity
            }
            
            # Generate features with stress
            for feature, stats in feature_stats.items():
                if stress_intensity > 0:
                    # During stress: push features to extremes
                    if np.random.random() < 0.5:
                        # Push to extreme low
                        extreme_value = stats['min'] - stats['std'] * stress_intensity
                    else:
                        # Push to extreme high
                        extreme_value = stats['max'] + stats['std'] * stress_intensity
                    
                    # Mix normal and extreme
                    normal_value = np.random.normal(stats['mean'], stats['std'])
                    value = (1 - stress_intensity * 0.7) * normal_value + (stress_intensity * 0.7) * extreme_value
                else:
                    # Normal regime behavior
                    value = np.random.normal(stats['mean'], stats['std'])
                
                # Add persistence
                if scenario_data:
                    prev_value = scenario_data[-1].get(feature, stats['mean'])
                    persistence = 0.5 if stress_intensity > 0 else 0.8
                    value = persistence * prev_value + (1 - persistence) * value
                
                scenario_point[feature] = value
            
            scenario_data.append(scenario_point)
        
        scenario_df = pd.DataFrame(scenario_data)
        scenario_df = scenario_df.set_index('date')
        
        print(f"   ✅ Generated {len(scenario_df)} day stress scenario with {len(stress_events)} events")
        return scenario_df
    
    def validate_scenario_realism(self, scenario: pd.DataFrame, 
                                regime_characteristics: Dict[str, Dict]) -> Dict[str, Any]:
        """Validate that generated scenario maintains realistic characteristics"""
        
        validation = {
            'timestamp': datetime.now().isoformat(),
            'scenario_type': scenario.iloc[0]['scenario_type'] if 'scenario_type' in scenario.columns else 'unknown',
            'length_days': len(scenario),
            'realism_score': 0.0,
            'validation_checks': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Get feature columns
            feature_cols = [col for col in scenario.columns 
                           if col not in ['scenario_type', 'regime', 'transition_progress', 
                                        'breakdown_intensity', 'stress_intensity']]
            
            if not feature_cols:
                validation['errors'].append("No feature columns found for validation")
                return validation
            
            checks_passed = 0
            total_checks = 0
            
            # Check 1: Feature ranges are reasonable
            total_checks += 1
            range_violations = 0
            
            for feature in feature_cols:
                if feature in scenario.columns:
                    values = scenario[feature].dropna()
                    if len(values) > 0:
                        # Check for extreme outliers (beyond 5 standard deviations)
                        z_scores = np.abs(stats.zscore(values))
                        outliers = (z_scores > 5).sum()
                        if outliers > len(values) * 0.05:  # More than 5% outliers
                            range_violations += 1
            
            if range_violations == 0:
                validation['validation_checks']['feature_ranges'] = 'PASS'
                checks_passed += 1
            else:
                validation['validation_checks']['feature_ranges'] = 'FAIL'
                validation['warnings'].append(f"{range_violations} features have excessive outliers")
            
            # Check 2: Temporal consistency (no extreme jumps)
            total_checks += 1
            jump_violations = 0
            
            for feature in feature_cols:
                if feature in scenario.columns:
                    values = scenario[feature].dropna()
                    if len(values) > 1:
                        # Check for extreme day-to-day changes
                        daily_changes = values.diff().abs()
                        extreme_changes = daily_changes > (values.std() * 3)
                        if extreme_changes.sum() > len(values) * 0.1:  # More than 10% extreme changes
                            jump_violations += 1
            
            if jump_violations == 0:
                validation['validation_checks']['temporal_consistency'] = 'PASS'
                checks_passed += 1
            else:
                validation['validation_checks']['temporal_consistency'] = 'FAIL'
                validation['warnings'].append(f"{jump_violations} features have excessive daily jumps")
            
            # Check 3: Correlation structure preservation (for non-breakdown scenarios)
            total_checks += 1
            if validation['scenario_type'] != 'regime_breakdown_chaos':
                try:
                    correlation_matrix = scenario[feature_cols].corr()
                    # Check for reasonable correlations (not all zero or all one)
                    off_diagonal = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)]
                    reasonable_correlations = np.abs(off_diagonal) < 0.95
                    
                    if reasonable_correlations.mean() > 0.8:  # 80% of correlations are reasonable
                        validation['validation_checks']['correlation_structure'] = 'PASS'
                        checks_passed += 1
                    else:
                        validation['validation_checks']['correlation_structure'] = 'FAIL'
                        validation['warnings'].append("Correlation structure appears unrealistic")
                except:
                    validation['validation_checks']['correlation_structure'] = 'SKIP'
                    validation['warnings'].append("Could not validate correlation structure")
            else:
                validation['validation_checks']['correlation_structure'] = 'SKIP'
                # Breakdown scenarios are expected to have broken correlations
            
            # Check 4: Scenario-specific validation
            total_checks += 1
            scenario_specific_valid = True
            
            if validation['scenario_type'] == 'regime_transition':
                # Check that transition actually occurs
                if 'transition_progress' in scenario.columns:
                    max_progress = scenario['transition_progress'].max()
                    if max_progress < 0.8:
                        scenario_specific_valid = False
                        validation['warnings'].append("Regime transition did not complete")
            
            elif validation['scenario_type'] == 'regime_breakdown_chaos':
                # Check that breakdown creates increased volatility
                if 'breakdown_intensity' in scenario.columns:
                    breakdown_periods = scenario[scenario['breakdown_intensity'] > 0]
                    if len(breakdown_periods) == 0:
                        scenario_specific_valid = False
                        validation['warnings'].append("No breakdown periods found in breakdown scenario")
            
            elif validation['scenario_type'] == 'stress_scenario':
                # Check that stress events create volatility spikes
                if 'stress_intensity' in scenario.columns:
                    max_stress = scenario['stress_intensity'].max()
                    if max_stress < 1.0:
                        scenario_specific_valid = False
                        validation['warnings'].append("Stress scenario lacks sufficient stress intensity")
            
            if scenario_specific_valid:
                validation['validation_checks']['scenario_specific'] = 'PASS'
                checks_passed += 1
            else:
                validation['validation_checks']['scenario_specific'] = 'FAIL'
            
            # Calculate overall realism score
            validation['realism_score'] = checks_passed / total_checks if total_checks > 0 else 0
            
        except Exception as e:
            validation['errors'].append(f"Validation error: {e}")
        
        return validation
    
    def generate_all_scenarios(self) -> Dict[str, List[pd.DataFrame]]:
        """Generate all types of scenarios for current regime"""
        
        print("🎭 GENERATING REGIME-BASED MARKET SCENARIOS")
        print("=" * 60)
        
        # Load Phase 3 data
        phase3_data = self.load_phase3_data()
        
        if not phase3_data['regime_memory'] is not None:
            print("❌ No Phase 3 regime data available")
            return {}
        
        current_regime = phase3_data['current_regime']
        regime_characteristics = phase3_data['regime_characteristics']
        transition_matrix = phase3_data['transition_matrix']
        
        if not current_regime or not regime_characteristics:
            print("❌ Insufficient regime data for scenario generation")
            return {}
        
        print(f"📊 Generating scenarios for current regime: {current_regime}")
        print(f"   Available regimes: {list(regime_characteristics.keys())}")
        
        all_scenarios = {}
        scenario_validations = []
        
        # Generate regime continuation scenarios
        print(f"\n🔄 Generating regime continuation scenarios...")
        continuation_scenarios = []
        for i in range(self.config['n_scenarios_per_type']):
            scenario = self.generate_regime_continuation_scenario(
                current_regime, regime_characteristics, self.config['scenario_length_days']
            )
            if not scenario.empty:
                continuation_scenarios.append(scenario)
                
                # Validate scenario
                if self.config['validate_scenarios']:
                    validation = self.validate_scenario_realism(scenario, regime_characteristics)
                    scenario_validations.append(validation)
        
        all_scenarios['regime_continuation'] = continuation_scenarios
        print(f"   ✅ Generated {len(continuation_scenarios)} continuation scenarios")
        
        # Generate regime transition scenarios
        print(f"\n🔄 Generating regime transition scenarios...")
        transition_scenarios = []
        
        if transition_matrix and current_regime in transition_matrix:
            # Get most likely transition targets
            transitions = transition_matrix[current_regime]
            likely_targets = [regime for regime, prob in transitions.items() 
                            if prob > 0.1 and regime != current_regime]
            
            for target_regime in likely_targets[:self.config['n_scenarios_per_type']]:
                scenario = self.generate_regime_transition_scenario(
                    current_regime, target_regime, regime_characteristics, 
                    self.config['scenario_length_days']
                )
                if not scenario.empty:
                    transition_scenarios.append(scenario)
                    
                    # Validate scenario
                    if self.config['validate_scenarios']:
                        validation = self.validate_scenario_realism(scenario, regime_characteristics)
                        scenario_validations.append(validation)
        
        all_scenarios['regime_transition'] = transition_scenarios
        print(f"   ✅ Generated {len(transition_scenarios)} transition scenarios")
        
        # Generate regime breakdown scenarios
        print(f"\n💥 Generating regime breakdown scenarios...")
        breakdown_scenarios = []
        for i in range(self.config['n_scenarios_per_type']):
            scenario = self.generate_regime_breakdown_scenario(
                current_regime, regime_characteristics, self.config['scenario_length_days']
            )
            if not scenario.empty:
                breakdown_scenarios.append(scenario)
                
                # Validate scenario
                if self.config['validate_scenarios']:
                    validation = self.validate_scenario_realism(scenario, regime_characteristics)
                    scenario_validations.append(validation)
        
        all_scenarios['regime_breakdown'] = breakdown_scenarios
        print(f"   ✅ Generated {len(breakdown_scenarios)} breakdown scenarios")
        
        # Generate stress scenarios
        print(f"\n⚡ Generating stress scenarios...")
        stress_scenarios = []
        for i in range(self.config['n_scenarios_per_type']):
            scenario = self.generate_stress_scenario(
                current_regime, regime_characteristics, self.config['scenario_length_days']
            )
            if not scenario.empty:
                stress_scenarios.append(scenario)
                
                # Validate scenario
                if self.config['validate_scenarios']:
                    validation = self.validate_scenario_realism(scenario, regime_characteristics)
                    scenario_validations.append(validation)
        
        all_scenarios['stress_scenario'] = stress_scenarios
        print(f"   ✅ Generated {len(stress_scenarios)} stress scenarios")
        
        # Save scenarios and validations
        self.save_scenarios(all_scenarios, scenario_validations, phase3_data)
        
        # Print summary
        total_scenarios = sum(len(scenarios) for scenarios in all_scenarios.values())
        print(f"\n🎯 SCENARIO GENERATION COMPLETE")
        print(f"   Total scenarios: {total_scenarios}")
        print(f"   Scenario types: {len(all_scenarios)}")
        print(f"   Current regime: {current_regime}")
        
        if scenario_validations:
            avg_realism = np.mean([v['realism_score'] for v in scenario_validations])
            print(f"   Average realism score: {avg_realism:.1%}")
        
        return all_scenarios
    
    def save_scenarios(self, all_scenarios: Dict[str, List[pd.DataFrame]], 
                      validations: List[Dict], phase3_data: Dict[str, Any]):
        """Save generated scenarios and metadata"""
        
        print("💾 Saving market scenarios...")
        
        try:
            # Create output directory
            os.makedirs(os.path.dirname(self.paths['market_scenarios']), exist_ok=True)
            
            # Combine all scenarios into single DataFrame
            combined_scenarios = []
            scenario_id = 0
            
            for scenario_type, scenarios in all_scenarios.items():
                for i, scenario in enumerate(scenarios):
                    scenario_copy = scenario.copy()
                    scenario_copy['scenario_id'] = scenario_id
                    scenario_copy['scenario_type'] = scenario_type
                    scenario_copy['scenario_index'] = i
                    combined_scenarios.append(scenario_copy)
                    scenario_id += 1
            
            if combined_scenarios:
                # Combine all scenarios
                scenarios_df = pd.concat(combined_scenarios, ignore_index=False)
                scenarios_df.to_parquet(self.paths['market_scenarios'])
                print(f"   ✅ Saved market scenarios: {len(scenarios_df)} records")
            
            # Save validations
            if validations:
                validations_df = pd.DataFrame(validations)
                validations_df.to_parquet(self.paths['scenario_validation'], index=False)
                print(f"   ✅ Saved scenario validations: {len(validations)} records")
            
            # Save metadata
            metadata = {
                'created_at': datetime.now().isoformat(),
                'version': self.version,
                'config': self.config,
                'phase3_data': {
                    'current_regime': phase3_data.get('current_regime'),
                    'n_regimes': len(phase3_data.get('regime_characteristics', {})),
                    'regime_memory_periods': len(phase3_data.get('regime_memory', [])),
                },
                'scenarios_generated': {
                    scenario_type: len(scenarios) 
                    for scenario_type, scenarios in all_scenarios.items()
                },
                'total_scenarios': sum(len(scenarios) for scenarios in all_scenarios.values()),
                'validation_summary': {
                    'n_validations': len(validations),
                    'avg_realism_score': np.mean([v['realism_score'] for v in validations]) if validations else 0,
                    'validation_warnings': sum(len(v['warnings']) for v in validations),
                    'validation_errors': sum(len(v['errors']) for v in validations)
                }
            }
            
            with open(self.paths['scenario_metadata'], 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            print(f"   ✅ Saved scenario metadata")
            
        except Exception as e:
            print(f"   ⚠️ Error saving scenarios: {e}")

def main():
    """Generate regime-based market scenarios"""
    
    generator = RegimeBasedScenarioGenerator()
    scenarios = generator.generate_all_scenarios()
    
    if scenarios:
        total_scenarios = sum(len(scenario_list) for scenario_list in scenarios.values())
        print(f"\n🎯 Regime-based scenario generation complete!")
        print(f"   Generated {total_scenarios} scenarios across {len(scenarios)} types")
        print(f"   Next step: Write property test for market simulation Phase 3 consistency")
        return True
    else:
        print("❌ Failed to generate scenarios")
        return False

if __name__ == "__main__":
    main()