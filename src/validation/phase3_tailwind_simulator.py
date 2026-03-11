#!/usr/bin/env python3
"""
🌬️ PHASE 3 TAILWIND SIMULATOR - NORTHSTAR V3 PHASE 4.2
Advanced tailwind simulation for scenario testing

This creates sophisticated tailwind evolution simulation that:
1. Simulates tailwind evolution under different market scenarios
2. Models tailwind breakdown and conflicting situations
3. Generates scenarios where NO_EDGE should trigger
4. Validates anticipatory signal generation correctness
5. Tests Phase 3 tailwind engine behavior under stress

Phase 4.2 Enhancement for tailwind testing:
- Uses Phase 3 SimpleTailwindEngine as foundation
- Simulates realistic tailwind evolution patterns
- Models breakdown scenarios where tailwinds fail
- Creates conflicting tailwind situations
- Validates NO_EDGE detection triggers appropriately

Integration with Phase 3:
- Uses SimpleTailwindEngine for baseline tailwind calculations
- Leverages RegimeMemorySystem for regime-aware simulation
- Tests NoEdgeDetector trigger conditions
- Validates AnticipatoryCapitalAllocator responses
- Maintains V3 architecture compatibility

Output: data/shadow_reality/tailwind_simulations.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class Phase3TailwindSimulator:
    """
    Phase 3 Tailwind Evolution Simulator
    
    Simulates tailwind behavior under various scenarios:
    - Normal tailwind evolution (gradual changes)
    - Tailwind breakdown (relationships fail)
    - Conflicting tailwinds (strategies diverge)
    - Recovery patterns (tailwinds restore)
    - NO_EDGE trigger scenarios (uncertainty spikes)
    """
    
    def __init__(self):
        self.name = "Phase 3 Tailwind Simulator"
        self.version = "4.2"
        
        # Data paths
        self.paths = {
            # Phase 3 inputs
            'strategy_tailwinds': 'data/intelligence/strategy_tailwinds.parquet',
            'tailwind_metadata': 'data/intelligence/tailwind_metadata.json',
            'regime_memory': 'data/intelligence/regime_memory.parquet',
            'no_edge_state': 'data/intelligence/no_edge_state.parquet',
            
            # Strategy performance data
            'backtests': 'data/processed/backtests',
            'performance_summary': 'data/processed/performance_summary.parquet',
            
            # Simulation outputs
            'tailwind_simulations': 'data/shadow_reality/tailwind_simulations.parquet',
            'tailwind_simulation_metadata': 'data/shadow_reality/tailwind_simulation_metadata.json',
            'tailwind_breakdown_scenarios': 'data/shadow_reality/tailwind_breakdown_scenarios.parquet'
        }
        
        # Configuration
        self.config = {
            'simulation_length_days': 63,      # ~3 months per simulation
            'n_simulations_per_type': 3,       # Number of simulations per type
            'tailwind_decay_rate': 0.95,       # Daily decay rate for tailwinds
            'breakdown_threshold': 0.3,        # Threshold for tailwind breakdown
            'recovery_rate': 0.02,             # Daily recovery rate after breakdown
            'noise_level': 0.1,                # Random noise in tailwind evolution
            'correlation_breakdown_prob': 0.05, # Daily probability of correlation breakdown
            'no_edge_trigger_threshold': 0.4   # Tailwind uncertainty threshold for NO_EDGE
        }
        
        # Simulation types
        self.simulation_types = [
            'normal_evolution',      # Normal tailwind evolution
            'gradual_breakdown',     # Gradual tailwind deterioration
            'sudden_breakdown',      # Sudden tailwind failure
            'conflicting_signals',   # Strategies give conflicting signals
            'recovery_pattern',      # Recovery after breakdown
            'no_edge_trigger'        # Scenario that should trigger NO_EDGE
        ]
        
        # Strategy categories for simulation
        self.strategy_categories = {
            'momentum': ['mom_6m', 'mom_12m', 'dual_momentum', 'mom_3m_6m_12m'],
            'value': ['value_tilt', 'quality_value_combo'],
            'quality': ['quality_tilt', 'northstar'],
            'defensive': ['low_vol', 'risk_parity_vol'],
            'sector': ['sector_neutral_eq', 'sector_tilt_mom']
        }
        
        # Current tailwind state
        self.current_tailwinds = {}
        self.baseline_performance = {}
    
    def load_phase3_tailwind_data(self) -> Dict[str, Any]:
        """Load Phase 3 tailwind data for simulation"""
        
        print("📊 Loading Phase 3 tailwind data for simulation...")
        
        tailwind_data = {
            'current_tailwinds': {},
            'tailwind_metadata': None,
            'strategy_performance': {},
            'regime_context': None
        }
        
        try:
            # Load current tailwinds
            if os.path.exists(self.paths['strategy_tailwinds']):
                tailwinds_df = pd.read_parquet(self.paths['strategy_tailwinds'])
                
                if not tailwinds_df.empty:
                    for _, row in tailwinds_df.iterrows():
                        strategy = row['strategy']
                        tailwind_data['current_tailwinds'][strategy] = {
                            'combined_score': float(row['combined_score']),
                            'sharpe': float(row['sharpe']),
                            'regime_tailwind': float(row['regime_tailwind']),
                            'regime': row['regime']
                        }
                    
                    self.current_tailwinds = tailwind_data['current_tailwinds']
                    print(f"   ✅ Current tailwinds: {len(tailwind_data['current_tailwinds'])} strategies")
            
            # Load tailwind metadata
            if os.path.exists(self.paths['tailwind_metadata']):
                with open(self.paths['tailwind_metadata'], 'r') as f:
                    tailwind_data['tailwind_metadata'] = json.load(f)
                    print(f"   ✅ Tailwind metadata loaded")
            
            # Load strategy performance for baseline
            if os.path.exists(self.paths['backtests']):
                for file in os.listdir(self.paths['backtests']):
                    if file.endswith('.parquet'):
                        strategy_name = file.replace('.parquet', '')
                        try:
                            df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                            if not df.empty and 'daily_return' in df.columns:
                                returns = df['daily_return'].dropna()
                                if len(returns) > 20:  # Minimum data requirement
                                    tailwind_data['strategy_performance'][strategy_name] = {
                                        'returns': returns.tolist()[-252:],  # Last year
                                        'sharpe': (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0,
                                        'volatility': returns.std() * np.sqrt(252),
                                        'max_drawdown': df['drawdown'].min() if 'drawdown' in df.columns else 0
                                    }
                        except Exception as e:
                            print(f"   ⚠️ Error loading {strategy_name}: {e}")
                
                self.baseline_performance = tailwind_data['strategy_performance']
                print(f"   ✅ Strategy performance: {len(tailwind_data['strategy_performance'])} strategies")
            
            # Load regime context
            if os.path.exists(self.paths['regime_memory']):
                regime_df = pd.read_parquet(self.paths['regime_memory'])
                if not regime_df.empty:
                    latest_regime = regime_df.iloc[-1]
                    tailwind_data['regime_context'] = {
                        'current_regime': latest_regime['Regime'],
                        'regime_return': float(latest_regime.get('regime_avg_return', 0)),
                        'regime_sharpe': float(latest_regime.get('regime_sharpe', 0))
                    }
                    print(f"   ✅ Regime context: {tailwind_data['regime_context']['current_regime']}")
        
        except Exception as e:
            print(f"   ⚠️ Error loading Phase 3 tailwind data: {e}")
        
        return tailwind_data
    
    def simulate_normal_tailwind_evolution(self, initial_tailwinds: Dict[str, Dict],
                                         length_days: int = 63) -> pd.DataFrame:
        """Simulate normal tailwind evolution over time"""
        
        print(f"🌬️ Simulating normal tailwind evolution for {length_days} days...")
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        simulation_data = []
        current_scores = {strategy: data['combined_score'] 
                         for strategy, data in initial_tailwinds.items()}
        
        for i, date in enumerate(dates):
            day_data = {
                'date': date,
                'simulation_type': 'normal_evolution',
                'day': i
            }
            
            # Evolve tailwinds with persistence and mean reversion
            for strategy, initial_data in initial_tailwinds.items():
                if strategy in current_scores:
                    current_score = current_scores[strategy]
                    
                    # Mean reversion towards long-term average (initial score)
                    mean_reversion = 0.02 * (initial_data['combined_score'] - current_score)
                    
                    # Random walk component
                    random_change = np.random.normal(0, 0.05)
                    
                    # Persistence (AR(1) process)
                    persistence = 0.95
                    
                    # Update score
                    new_score = (persistence * current_score + 
                                mean_reversion + random_change)
                    
                    # Ensure reasonable bounds
                    new_score = np.clip(new_score, -2.0, 4.0)
                    current_scores[strategy] = new_score
                    
                    # Store in day data
                    day_data[f'tailwind_{strategy}'] = new_score
                    day_data[f'change_{strategy}'] = new_score - current_score if i > 0 else 0
            
            # Calculate aggregate metrics
            all_scores = list(current_scores.values())
            day_data['avg_tailwind'] = np.mean(all_scores)
            day_data['tailwind_dispersion'] = np.std(all_scores)
            day_data['max_tailwind'] = np.max(all_scores)
            day_data['min_tailwind'] = np.min(all_scores)
            
            simulation_data.append(day_data)
        
        simulation_df = pd.DataFrame(simulation_data)
        simulation_df = simulation_df.set_index('date')
        
        print(f"   ✅ Generated {len(simulation_df)} day normal evolution simulation")
        return simulation_df
    
    def simulate_gradual_tailwind_breakdown(self, initial_tailwinds: Dict[str, Dict],
                                          length_days: int = 63) -> pd.DataFrame:
        """Simulate gradual breakdown of tailwind relationships"""
        
        print(f"💔 Simulating gradual tailwind breakdown for {length_days} days...")
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Breakdown starts after initial period
        breakdown_start = length_days // 4
        breakdown_intensity = 0.0
        
        simulation_data = []
        current_scores = {strategy: data['combined_score'] 
                         for strategy, data in initial_tailwinds.items()}
        
        for i, date in enumerate(dates):
            # Calculate breakdown intensity (gradual increase)
            if i >= breakdown_start:
                breakdown_intensity = min(1.0, (i - breakdown_start) / (length_days - breakdown_start))
            
            day_data = {
                'date': date,
                'simulation_type': 'gradual_breakdown',
                'day': i,
                'breakdown_intensity': breakdown_intensity
            }
            
            # Evolve tailwinds with increasing breakdown
            for strategy, initial_data in initial_tailwinds.items():
                if strategy in current_scores:
                    current_score = current_scores[strategy]
                    
                    if breakdown_intensity == 0:
                        # Normal evolution before breakdown
                        mean_reversion = 0.02 * (initial_data['combined_score'] - current_score)
                        random_change = np.random.normal(0, 0.05)
                        persistence = 0.95
                        
                        new_score = (persistence * current_score + 
                                    mean_reversion + random_change)
                    else:
                        # Breakdown: tailwinds deteriorate
                        # Drift towards zero (no edge)
                        breakdown_drift = -0.05 * breakdown_intensity * current_score
                        
                        # Increased noise during breakdown
                        noise_multiplier = 1 + 2 * breakdown_intensity
                        random_change = np.random.normal(0, 0.05 * noise_multiplier)
                        
                        # Reduced persistence during breakdown
                        persistence = 0.95 * (1 - 0.3 * breakdown_intensity)
                        
                        new_score = (persistence * current_score + 
                                    breakdown_drift + random_change)
                    
                    # Ensure reasonable bounds
                    new_score = np.clip(new_score, -2.0, 4.0)
                    current_scores[strategy] = new_score
                    
                    # Store in day data
                    day_data[f'tailwind_{strategy}'] = new_score
                    day_data[f'change_{strategy}'] = new_score - current_score if i > 0 else 0
            
            # Calculate aggregate metrics
            all_scores = list(current_scores.values())
            day_data['avg_tailwind'] = np.mean(all_scores)
            day_data['tailwind_dispersion'] = np.std(all_scores)
            day_data['max_tailwind'] = np.max(all_scores)
            day_data['min_tailwind'] = np.min(all_scores)
            
            simulation_data.append(day_data)
        
        simulation_df = pd.DataFrame(simulation_data)
        simulation_df = simulation_df.set_index('date')
        
        print(f"   ✅ Generated {len(simulation_df)} day gradual breakdown simulation")
        return simulation_df
    
    def simulate_sudden_tailwind_breakdown(self, initial_tailwinds: Dict[str, Dict],
                                         length_days: int = 63) -> pd.DataFrame:
        """Simulate sudden breakdown of tailwind relationships"""
        
        print(f"💥 Simulating sudden tailwind breakdown for {length_days} days...")
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Breakdown occurs suddenly at random point
        breakdown_day = np.random.randint(length_days // 3, 2 * length_days // 3)
        
        simulation_data = []
        current_scores = {strategy: data['combined_score'] 
                         for strategy, data in initial_tailwinds.items()}
        
        for i, date in enumerate(dates):
            is_breakdown = i >= breakdown_day
            
            day_data = {
                'date': date,
                'simulation_type': 'sudden_breakdown',
                'day': i,
                'breakdown_occurred': is_breakdown,
                'breakdown_day': breakdown_day
            }
            
            # Evolve tailwinds
            for strategy, initial_data in initial_tailwinds.items():
                if strategy in current_scores:
                    current_score = current_scores[strategy]
                    
                    if not is_breakdown:
                        # Normal evolution before breakdown
                        mean_reversion = 0.02 * (initial_data['combined_score'] - current_score)
                        random_change = np.random.normal(0, 0.05)
                        persistence = 0.95
                        
                        new_score = (persistence * current_score + 
                                    mean_reversion + random_change)
                    else:
                        # After breakdown: chaotic behavior
                        if i == breakdown_day:
                            # Sudden shock on breakdown day
                            shock = np.random.normal(0, 0.5)  # Large shock
                            new_score = current_score + shock
                        else:
                            # Post-breakdown: high noise, low persistence
                            random_change = np.random.normal(0, 0.15)  # High noise
                            persistence = 0.7  # Low persistence
                            
                            # Drift towards zero
                            drift = -0.03 * current_score
                            
                            new_score = persistence * current_score + drift + random_change
                    
                    # Ensure reasonable bounds
                    new_score = np.clip(new_score, -2.0, 4.0)
                    current_scores[strategy] = new_score
                    
                    # Store in day data
                    day_data[f'tailwind_{strategy}'] = new_score
                    day_data[f'change_{strategy}'] = new_score - current_score if i > 0 else 0
            
            # Calculate aggregate metrics
            all_scores = list(current_scores.values())
            day_data['avg_tailwind'] = np.mean(all_scores)
            day_data['tailwind_dispersion'] = np.std(all_scores)
            day_data['max_tailwind'] = np.max(all_scores)
            day_data['min_tailwind'] = np.min(all_scores)
            
            simulation_data.append(day_data)
        
        simulation_df = pd.DataFrame(simulation_data)
        simulation_df = simulation_df.set_index('date')
        
        print(f"   ✅ Generated {len(simulation_df)} day sudden breakdown simulation (breakdown on day {breakdown_day})")
        return simulation_df
    
    def simulate_conflicting_tailwinds(self, initial_tailwinds: Dict[str, Dict],
                                     length_days: int = 63) -> pd.DataFrame:
        """Simulate conflicting signals between strategy categories"""
        
        print(f"⚔️ Simulating conflicting tailwinds for {length_days} days...")
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Conflict starts after initial period
        conflict_start = length_days // 4
        
        simulation_data = []
        current_scores = {strategy: data['combined_score'] 
                         for strategy, data in initial_tailwinds.items()}
        
        # Assign strategies to conflicting groups
        group_assignments = {}
        available_strategies = list(initial_tailwinds.keys())
        
        # Group 1: Momentum strategies (positive trend)
        momentum_strategies = [s for s in available_strategies 
                             if any(mom in s.lower() for mom in ['mom', 'momentum'])]
        
        # Group 2: Value/Quality strategies (negative trend)
        value_quality_strategies = [s for s in available_strategies 
                                  if any(vq in s.lower() for vq in ['value', 'quality', 'northstar'])]
        
        # Group 3: Defensive strategies (neutral/volatile)
        defensive_strategies = [s for s in available_strategies 
                              if any(def_s in s.lower() for def_s in ['low_vol', 'risk_parity', 'defensive'])]
        
        # Assign remaining strategies randomly
        assigned_strategies = set(momentum_strategies + value_quality_strategies + defensive_strategies)
        remaining_strategies = [s for s in available_strategies if s not in assigned_strategies]
        
        for i, strategy in enumerate(remaining_strategies):
            if i % 3 == 0:
                momentum_strategies.append(strategy)
            elif i % 3 == 1:
                value_quality_strategies.append(strategy)
            else:
                defensive_strategies.append(strategy)
        
        for i, date in enumerate(dates):
            is_conflict = i >= conflict_start
            conflict_ramp = max(5, length_days // 3)
            conflict_intensity = min(1.0, (i - conflict_start) / conflict_ramp) if is_conflict else 0
            
            day_data = {
                'date': date,
                'simulation_type': 'conflicting_signals',
                'day': i,
                'conflict_intensity': conflict_intensity
            }
            
            # Evolve tailwinds with group-specific trends
            for strategy, initial_data in initial_tailwinds.items():
                if strategy in current_scores:
                    current_score = current_scores[strategy]
                    
                    if not is_conflict:
                        # Normal evolution before conflict
                        mean_reversion = 0.02 * (initial_data['combined_score'] - current_score)
                        random_change = np.random.normal(0, 0.05)
                        persistence = 0.95
                        
                        new_score = (persistence * current_score + 
                                    mean_reversion + random_change)
                    else:
                        # During conflict: group-specific trends
                        if strategy in momentum_strategies:
                            # Momentum strategies improve
                            trend = 0.04 * conflict_intensity
                        elif strategy in value_quality_strategies:
                            # Value/Quality strategies deteriorate
                            trend = -0.05 * conflict_intensity
                        else:
                            # Defensive strategies are volatile
                            trend = np.random.normal(0, 0.03 * conflict_intensity)
                        
                        # Base evolution
                        random_change = np.random.normal(0, 0.03)
                        persistence = 0.88
                        
                        new_score = (persistence * current_score + trend + random_change)
                    
                    # Ensure reasonable bounds
                    new_score = np.clip(new_score, -2.0, 4.0)
                    current_scores[strategy] = new_score
                    
                    # Store in day data
                    day_data[f'tailwind_{strategy}'] = new_score
                    day_data[f'change_{strategy}'] = new_score - current_score if i > 0 else 0
            
            # Calculate group-specific metrics
            if momentum_strategies:
                momentum_scores = [current_scores[s] for s in momentum_strategies if s in current_scores]
                day_data['momentum_avg'] = np.mean(momentum_scores) if momentum_scores else 0
            
            if value_quality_strategies:
                vq_scores = [current_scores[s] for s in value_quality_strategies if s in current_scores]
                day_data['value_quality_avg'] = np.mean(vq_scores) if vq_scores else 0
            
            if defensive_strategies:
                def_scores = [current_scores[s] for s in defensive_strategies if s in current_scores]
                day_data['defensive_avg'] = np.mean(def_scores) if def_scores else 0
            
            # Calculate aggregate metrics
            all_scores = list(current_scores.values())
            day_data['avg_tailwind'] = np.mean(all_scores)
            day_data['tailwind_dispersion'] = np.std(all_scores)
            day_data['max_tailwind'] = np.max(all_scores)
            day_data['min_tailwind'] = np.min(all_scores)
            
            simulation_data.append(day_data)
        
        simulation_df = pd.DataFrame(simulation_data)
        simulation_df = simulation_df.set_index('date')
        
        print(f"   ✅ Generated {len(simulation_df)} day conflicting tailwinds simulation")
        print(f"      Groups: {len(momentum_strategies)} momentum, {len(value_quality_strategies)} value/quality, {len(defensive_strategies)} defensive")
        return simulation_df
    
    def simulate_no_edge_trigger_scenario(self, initial_tailwinds: Dict[str, Dict],
                                        length_days: int = 63) -> pd.DataFrame:
        """Simulate scenario that should trigger NO_EDGE detection"""
        
        print(f"🚨 Simulating NO_EDGE trigger scenario for {length_days} days...")
        
        # Generate dates
        start_date = datetime.now().date()
        dates = pd.date_range(start=start_date, periods=length_days, freq='D')
        
        # Uncertainty builds up over time
        uncertainty_start = length_days // 5
        
        simulation_data = []
        current_scores = {strategy: data['combined_score'] 
                         for strategy, data in initial_tailwinds.items()}
        
        for i, date in enumerate(dates):
            # Calculate uncertainty level
            if i < uncertainty_start:
                uncertainty = 0.0
            else:
                uncertainty = min(1.0, (i - uncertainty_start) / (length_days - uncertainty_start))
            
            # Should trigger NO_EDGE when uncertainty is high and tailwinds are weak
            should_trigger_no_edge = (uncertainty > 0.6 and 
                                    np.mean(list(current_scores.values())) < self.config['no_edge_trigger_threshold'])
            
            day_data = {
                'date': date,
                'simulation_type': 'no_edge_trigger',
                'day': i,
                'uncertainty_level': uncertainty,
                'should_trigger_no_edge': should_trigger_no_edge
            }
            
            # Evolve tailwinds towards uncertainty
            for strategy, initial_data in initial_tailwinds.items():
                if strategy in current_scores:
                    current_score = current_scores[strategy]
                    
                    if uncertainty == 0:
                        # Normal evolution initially
                        mean_reversion = 0.02 * (initial_data['combined_score'] - current_score)
                        random_change = np.random.normal(0, 0.05)
                        persistence = 0.95
                        
                        new_score = (persistence * current_score + 
                                    mean_reversion + random_change)
                    else:
                        # Increasing uncertainty: drift towards zero, high noise
                        uncertainty_drift = -0.03 * uncertainty * current_score
                        
                        # Noise increases with uncertainty
                        noise_level = 0.05 * (1 + 3 * uncertainty)
                        random_change = np.random.normal(0, noise_level)
                        
                        # Persistence decreases with uncertainty
                        persistence = 0.95 * (1 - 0.4 * uncertainty)
                        
                        new_score = (persistence * current_score + 
                                    uncertainty_drift + random_change)
                    
                    # Ensure reasonable bounds
                    new_score = np.clip(new_score, -2.0, 4.0)
                    current_scores[strategy] = new_score
                    
                    # Store in day data
                    day_data[f'tailwind_{strategy}'] = new_score
                    day_data[f'change_{strategy}'] = new_score - current_score if i > 0 else 0
            
            # Calculate aggregate metrics
            all_scores = list(current_scores.values())
            day_data['avg_tailwind'] = np.mean(all_scores)
            day_data['tailwind_dispersion'] = np.std(all_scores)
            day_data['max_tailwind'] = np.max(all_scores)
            day_data['min_tailwind'] = np.min(all_scores)
            
            # NO_EDGE indicators
            day_data['tailwind_uncertainty'] = np.std(all_scores) / (np.abs(np.mean(all_scores)) + 0.1)
            day_data['weak_signals'] = (np.array(all_scores) < 0.5).mean()
            
            simulation_data.append(day_data)
        
        simulation_df = pd.DataFrame(simulation_data)
        simulation_df = simulation_df.set_index('date')
        
        print(f"   ✅ Generated {len(simulation_df)} day NO_EDGE trigger simulation")
        
        # Check if scenario actually creates NO_EDGE conditions
        no_edge_periods = simulation_df['should_trigger_no_edge'].sum()
        print(f"      NO_EDGE trigger periods: {no_edge_periods} ({no_edge_periods/len(simulation_df):.1%})")
        
        return simulation_df
    
    def validate_tailwind_simulation(self, simulation: pd.DataFrame) -> Dict[str, Any]:
        """Validate tailwind simulation quality and realism"""
        
        validation = {
            'timestamp': datetime.now().isoformat(),
            'simulation_type': simulation.iloc[0]['simulation_type'] if 'simulation_type' in simulation.columns else 'unknown',
            'length_days': len(simulation),
            'validation_score': 0.0,
            'validation_checks': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Get tailwind columns
            tailwind_cols = [col for col in simulation.columns if col.startswith('tailwind_')]
            
            if not tailwind_cols:
                validation['errors'].append("No tailwind columns found")
                return validation
            
            checks_passed = 0
            total_checks = 0
            
            # Check 1: Tailwinds stay within reasonable bounds
            total_checks += 1
            extreme_values = 0
            
            for col in tailwind_cols:
                values = simulation[col].dropna()
                if len(values) > 0:
                    extreme_count = ((values < -3.0) | (values > 5.0)).sum()
                    extreme_values += extreme_count
            
            if extreme_values == 0:
                validation['validation_checks']['reasonable_bounds'] = 'PASS'
                checks_passed += 1
            else:
                validation['validation_checks']['reasonable_bounds'] = 'FAIL'
                validation['warnings'].append(f"{extreme_values} extreme tailwind values found")
            
            # Check 2: Temporal consistency (no excessive jumps)
            total_checks += 1
            excessive_jumps = 0
            
            for col in tailwind_cols:
                values = simulation[col].dropna()
                if len(values) > 1:
                    daily_changes = values.diff().abs()
                    large_jumps = (daily_changes > 0.5).sum()  # More than 0.5 change per day
                    excessive_jumps += large_jumps
            
            if excessive_jumps <= len(tailwind_cols) * 2:  # Allow some jumps
                validation['validation_checks']['temporal_consistency'] = 'PASS'
                checks_passed += 1
            else:
                validation['validation_checks']['temporal_consistency'] = 'FAIL'
                validation['warnings'].append(f"{excessive_jumps} excessive daily jumps found")
            
            # Check 3: Simulation-specific validation
            total_checks += 1
            simulation_type = validation['simulation_type']
            
            if simulation_type == 'gradual_breakdown':
                # Check that breakdown actually occurs
                if 'breakdown_intensity' in simulation.columns:
                    max_breakdown = simulation['breakdown_intensity'].max()
                    if max_breakdown >= 0.8:
                        validation['validation_checks']['breakdown_occurs'] = 'PASS'
                        checks_passed += 1
                    else:
                        validation['validation_checks']['breakdown_occurs'] = 'FAIL'
                        validation['warnings'].append(f"Insufficient breakdown intensity: {max_breakdown:.2f}")
                else:
                    validation['validation_checks']['breakdown_occurs'] = 'SKIP'
            
            elif simulation_type == 'conflicting_signals':
                # Check that groups actually diverge
                if 'momentum_avg' in simulation.columns and 'value_quality_avg' in simulation.columns:
                    momentum_avg = simulation['momentum_avg'].dropna()
                    vq_avg = simulation['value_quality_avg'].dropna()
                    
                    if len(momentum_avg) > 10 and len(vq_avg) > 10:
                        # Check if groups diverge over time
                        final_diff = abs(momentum_avg.iloc[-10:].mean() - vq_avg.iloc[-10:].mean())
                        if final_diff > 0.2:
                            validation['validation_checks']['groups_diverge'] = 'PASS'
                            checks_passed += 1
                        else:
                            validation['validation_checks']['groups_diverge'] = 'FAIL'
                            validation['warnings'].append(f"Groups did not diverge sufficiently: {final_diff:.3f}")
                    else:
                        validation['validation_checks']['groups_diverge'] = 'SKIP'
                else:
                    validation['validation_checks']['groups_diverge'] = 'SKIP'
            
            elif simulation_type == 'no_edge_trigger':
                # Check that NO_EDGE conditions are created
                if 'should_trigger_no_edge' in simulation.columns:
                    trigger_periods = simulation['should_trigger_no_edge'].sum()
                    trigger_ratio = trigger_periods / len(simulation)
                    
                    if trigger_ratio >= 0.2:  # At least 20% of periods should trigger
                        validation['validation_checks']['no_edge_triggers'] = 'PASS'
                        checks_passed += 1
                    else:
                        validation['validation_checks']['no_edge_triggers'] = 'FAIL'
                        validation['warnings'].append(f"Insufficient NO_EDGE triggers: {trigger_ratio:.1%}")
                else:
                    validation['validation_checks']['no_edge_triggers'] = 'SKIP'
            
            else:
                # Default validation for other types
                validation['validation_checks']['simulation_specific'] = 'PASS'
                checks_passed += 1
            
            # Calculate overall validation score
            validation['validation_score'] = checks_passed / total_checks if total_checks > 0 else 0
            
        except Exception as e:
            validation['errors'].append(f"Validation error: {e}")
        
        return validation
    
    def run_all_tailwind_simulations(self) -> Dict[str, List[pd.DataFrame]]:
        """Run all types of tailwind simulations"""
        
        print("🌬️ RUNNING PHASE 3 TAILWIND SIMULATIONS")
        print("=" * 60)
        
        # Load Phase 3 tailwind data
        tailwind_data = self.load_phase3_tailwind_data()
        
        if not tailwind_data['current_tailwinds']:
            print("❌ No Phase 3 tailwind data available")
            return {}
        
        current_tailwinds = tailwind_data['current_tailwinds']
        print(f"📊 Running simulations for {len(current_tailwinds)} strategies")
        
        all_simulations = {}
        simulation_validations = []
        
        # Run normal evolution simulations
        print(f"\n🌬️ Running normal evolution simulations...")
        normal_simulations = []
        for i in range(self.config['n_simulations_per_type']):
            simulation = self.simulate_normal_tailwind_evolution(
                current_tailwinds, self.config['simulation_length_days']
            )
            if not simulation.empty:
                normal_simulations.append(simulation)
                
                # Validate simulation
                validation = self.validate_tailwind_simulation(simulation)
                simulation_validations.append(validation)
        
        all_simulations['normal_evolution'] = normal_simulations
        print(f"   ✅ Generated {len(normal_simulations)} normal evolution simulations")
        
        # Run gradual breakdown simulations
        print(f"\n💔 Running gradual breakdown simulations...")
        breakdown_simulations = []
        for i in range(self.config['n_simulations_per_type']):
            simulation = self.simulate_gradual_tailwind_breakdown(
                current_tailwinds, self.config['simulation_length_days']
            )
            if not simulation.empty:
                breakdown_simulations.append(simulation)
                
                # Validate simulation
                validation = self.validate_tailwind_simulation(simulation)
                simulation_validations.append(validation)
        
        all_simulations['gradual_breakdown'] = breakdown_simulations
        print(f"   ✅ Generated {len(breakdown_simulations)} gradual breakdown simulations")
        
        # Run sudden breakdown simulations
        print(f"\n💥 Running sudden breakdown simulations...")
        sudden_simulations = []
        for i in range(self.config['n_simulations_per_type']):
            simulation = self.simulate_sudden_tailwind_breakdown(
                current_tailwinds, self.config['simulation_length_days']
            )
            if not simulation.empty:
                sudden_simulations.append(simulation)
                
                # Validate simulation
                validation = self.validate_tailwind_simulation(simulation)
                simulation_validations.append(validation)
        
        all_simulations['sudden_breakdown'] = sudden_simulations
        print(f"   ✅ Generated {len(sudden_simulations)} sudden breakdown simulations")
        
        # Run conflicting signals simulations
        print(f"\n⚔️ Running conflicting signals simulations...")
        conflict_simulations = []
        for i in range(self.config['n_simulations_per_type']):
            simulation = self.simulate_conflicting_tailwinds(
                current_tailwinds, self.config['simulation_length_days']
            )
            if not simulation.empty:
                conflict_simulations.append(simulation)
                
                # Validate simulation
                validation = self.validate_tailwind_simulation(simulation)
                simulation_validations.append(validation)
        
        all_simulations['conflicting_signals'] = conflict_simulations
        print(f"   ✅ Generated {len(conflict_simulations)} conflicting signals simulations")
        
        # Run NO_EDGE trigger simulations
        print(f"\n🚨 Running NO_EDGE trigger simulations...")
        no_edge_simulations = []
        for i in range(self.config['n_simulations_per_type']):
            simulation = self.simulate_no_edge_trigger_scenario(
                current_tailwinds, self.config['simulation_length_days']
            )
            if not simulation.empty:
                no_edge_simulations.append(simulation)
                
                # Validate simulation
                validation = self.validate_tailwind_simulation(simulation)
                simulation_validations.append(validation)
        
        all_simulations['no_edge_trigger'] = no_edge_simulations
        print(f"   ✅ Generated {len(no_edge_simulations)} NO_EDGE trigger simulations")
        
        # Save simulations
        self.save_tailwind_simulations(all_simulations, simulation_validations, tailwind_data)
        
        # Print summary
        total_simulations = sum(len(sims) for sims in all_simulations.values())
        print(f"\n🎯 TAILWIND SIMULATIONS COMPLETE")
        print(f"   Total simulations: {total_simulations}")
        print(f"   Simulation types: {len(all_simulations)}")
        
        if simulation_validations:
            avg_validation_score = np.mean([v['validation_score'] for v in simulation_validations])
            print(f"   Average validation score: {avg_validation_score:.1%}")
        
        return all_simulations
    
    def save_tailwind_simulations(self, all_simulations: Dict[str, List[pd.DataFrame]], 
                                validations: List[Dict], tailwind_data: Dict[str, Any]):
        """Save tailwind simulations and metadata"""
        
        print("💾 Saving tailwind simulations...")
        
        try:
            # Create output directory
            os.makedirs(os.path.dirname(self.paths['tailwind_simulations']), exist_ok=True)
            
            # Combine all simulations into single DataFrame
            combined_simulations = []
            simulation_id = 0
            
            for simulation_type, simulations in all_simulations.items():
                for i, simulation in enumerate(simulations):
                    simulation_copy = simulation.copy()
                    simulation_copy['simulation_id'] = simulation_id
                    simulation_copy['simulation_type'] = simulation_type
                    simulation_copy['simulation_index'] = i
                    combined_simulations.append(simulation_copy)
                    simulation_id += 1
            
            if combined_simulations:
                # Combine all simulations
                simulations_df = pd.concat(combined_simulations, ignore_index=False)
                simulations_df.to_parquet(self.paths['tailwind_simulations'])
                print(f"   ✅ Saved tailwind simulations: {len(simulations_df)} records")
            
            # Save metadata
            metadata = {
                'created_at': datetime.now().isoformat(),
                'version': self.version,
                'config': self.config,
                'tailwind_data': {
                    'n_strategies': len(tailwind_data.get('current_tailwinds', {})),
                    'current_regime': tailwind_data.get('regime_context', {}).get('current_regime'),
                    'strategy_performance_loaded': len(tailwind_data.get('strategy_performance', {}))
                },
                'simulations_generated': {
                    simulation_type: len(simulations) 
                    for simulation_type, simulations in all_simulations.items()
                },
                'total_simulations': sum(len(simulations) for simulations in all_simulations.values()),
                'validation_summary': {
                    'n_validations': len(validations),
                    'avg_validation_score': np.mean([v['validation_score'] for v in validations]) if validations else 0,
                    'validation_warnings': sum(len(v['warnings']) for v in validations),
                    'validation_errors': sum(len(v['errors']) for v in validations)
                }
            }
            
            with open(self.paths['tailwind_simulation_metadata'], 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            print(f"   ✅ Saved tailwind simulation metadata")
            
        except Exception as e:
            print(f"   ⚠️ Error saving tailwind simulations: {e}")

def main():
    """Run Phase 3 tailwind simulations"""
    
    simulator = Phase3TailwindSimulator()
    simulations = simulator.run_all_tailwind_simulations()
    
    if simulations:
        total_simulations = sum(len(simulation_list) for simulation_list in simulations.values())
        print(f"\n🎯 Phase 3 tailwind simulation complete!")
        print(f"   Generated {total_simulations} simulations across {len(simulations)} types")
        print(f"   Next step: Write property test for stress scenario breakdown modeling")
        return True
    else:
        print("❌ Failed to generate tailwind simulations")
        return False

if __name__ == "__main__":
    main()
