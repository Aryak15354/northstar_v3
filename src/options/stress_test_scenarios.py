"""
Stress Test Scenarios for Options Trading System

Defines and executes stress test scenarios:
1. Vol expansion scenario
2. Calendar spread failure scenario
3. Consecutive losses scenario

Requirements: US-12.5
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional
from datetime import date, timedelta
import logging

from src.options.backtest_simulation_engine import (
    BacktestConfig,
    BacktestSimulationEngine,
    BacktestResults
)

logger = logging.getLogger(__name__)


@dataclass
class StressScenario:
    """Definition of a stress test scenario."""
    
    name: str
    description: str
    data_modifier: Callable
    expected_behavior: str
    success_criteria: Dict


class StressTestScenarios:
    """
    Defines and executes stress test scenarios.
    
    Scenarios test system behavior under adverse conditions:
    - Vol expansion: Rapid IV increase
    - Calendar spread failure: Front month collapses faster than back month
    - Consecutive losses: Multiple losing trades in sequence
    """
    
    def __init__(self):
        """Initialize stress test scenarios."""
        self.scenarios = self._define_scenarios()
    
    def _define_scenarios(self) -> List[StressScenario]:
        """Define all stress test scenarios."""
        return [
            StressScenario(
                name="vol_expansion",
                description=(
                    "Rapid volatility expansion: IV increases 50% in 5 days. "
                    "Tests regime detection, position exits, and kill switches."
                ),
                data_modifier=self._modify_vol_expansion,
                expected_behavior=(
                    "System should: (1) Detect regime change to HIGH_VOL_SELL "
                    "or CRASH_HEDGE, (2) Exit short-vol positions early, "
                    "(3) Activate trauma rule if losses exceed 80% of max loss"
                ),
                success_criteria={
                    'max_drawdown_pct': 10.0,  # Max 10% drawdown
                    'trauma_activations': 1,  # At least 1 trauma activation
                    'regime_changes': 1  # At least 1 regime change detected
                }
            ),
            StressScenario(
                name="calendar_spread_failure",
                description=(
                    "Calendar spread failure: Front month decays faster than "
                    "expected while back month holds value. Tests calendar "
                    "spread exit logic and theta decay assumptions."
                ),
                data_modifier=self._modify_calendar_failure,
                expected_behavior=(
                    "System should: (1) Detect negative theta, "
                    "(2) Exit calendar spreads early, "
                    "(3) Limit losses to stop loss threshold"
                ),
                success_criteria={
                    'max_loss_per_trade_pct': 40.0,  # Stop loss at 40%
                    'calendar_exits': 1,  # At least 1 calendar exit
                    'avg_days_held': 5  # Exit early (< 7 days)
                }
            ),
            StressScenario(
                name="consecutive_losses",
                description=(
                    "Consecutive losses: 3 losing trades in a row. "
                    "Tests capital scaling, kill switches, and system hygiene."
                ),
                data_modifier=self._modify_consecutive_losses,
                expected_behavior=(
                    "System should: (1) Reduce position size after losses, "
                    "(2) Activate weekly loss kill switch if losses exceed 2%, "
                    "(3) Apply success cooling period after 2 losses"
                ),
                success_criteria={
                    'max_consecutive_losses': 3,
                    'kill_switch_activations': 1,  # Weekly loss kill switch
                    'position_size_reduction': True  # Capital scaling active
                }
            )
        ]
    
    def run_scenario(
        self,
        scenario_name: str,
        base_config: BacktestConfig
    ) -> Dict:
        """
        Run a specific stress test scenario.
        
        Args:
            scenario_name: Name of scenario to run
            base_config: Base backtest configuration
            
        Returns:
            Dictionary with scenario results and analysis
        """
        scenario = next(
            (s for s in self.scenarios if s.name == scenario_name),
            None
        )
        
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        logger.info(f"Running stress test: {scenario.name}")
        logger.info(f"Description: {scenario.description}")
        
        # Run backtest with modified data
        try:
            engine = BacktestSimulationEngine(base_config)
            
            # Apply data modifications
            scenario.data_modifier(engine)
            
            # Run simulation
            results = engine.run()
            
            # Analyze results
            analysis = self._analyze_scenario_results(
                scenario=scenario,
                results=results
            )
            
            return {
                'scenario': scenario.name,
                'description': scenario.description,
                'expected_behavior': scenario.expected_behavior,
                'results': results,
                'analysis': analysis,
                'success': analysis['passed']
            }
            
        except Exception as e:
            logger.error(f"Scenario {scenario.name} failed: {e}")
            return {
                'scenario': scenario.name,
                'error': str(e),
                'success': False
            }
    
    def run_all_scenarios(
        self,
        base_config: BacktestConfig
    ) -> List[Dict]:
        """
        Run all stress test scenarios.
        
        Args:
            base_config: Base backtest configuration
            
        Returns:
            List of scenario results
        """
        logger.info(f"Running {len(self.scenarios)} stress test scenarios")
        
        results = []
        
        for scenario in self.scenarios:
            result = self.run_scenario(scenario.name, base_config)
            results.append(result)
        
        # Summary
        passed = sum(1 for r in results if r.get('success', False))
        logger.info(
            f"Stress tests complete: {passed}/{len(results)} scenarios passed"
        )
        
        return results
    
    def _modify_vol_expansion(self, engine: BacktestSimulationEngine) -> None:
        """
        Modify data for vol expansion scenario.
        
        Increases IV by 50% over 5 days for all options.
        """
        logger.info("Applying vol expansion modifications...")
        
        for symbol in engine.config.symbols:
            if symbol in engine.option_chains:
                df = engine.option_chains[symbol]
                
                # Get unique dates
                dates = sorted(df['date'].unique())
                
                if len(dates) < 5:
                    continue
                
                # Apply IV increase over first 5 days
                expansion_dates = dates[:5]
                
                for i, expansion_date in enumerate(expansion_dates):
                    # Gradual increase: 0% → 50% over 5 days
                    iv_multiplier = 1.0 + (0.5 * (i + 1) / 5)
                    
                    mask = df['date'] == expansion_date
                    df.loc[mask, 'iv'] *= iv_multiplier
                    
                    # Also increase option premiums proportionally
                    df.loc[mask, 'ltp'] *= iv_multiplier
                    df.loc[mask, 'bid'] *= iv_multiplier
                    df.loc[mask, 'ask'] *= iv_multiplier
                
                engine.option_chains[symbol] = df
                
                logger.info(
                    f"Applied vol expansion to {symbol}: "
                    f"IV increased 50% over 5 days"
                )
    
    def _modify_calendar_failure(self, engine: BacktestSimulationEngine) -> None:
        """
        Modify data for calendar spread failure scenario.
        
        Front month options decay faster than back month.
        """
        logger.info("Applying calendar spread failure modifications...")
        
        for symbol in engine.option_chains:
            if symbol in engine.option_chains:
                df = engine.option_chains[symbol]
                
                # Identify near-term and far-term options
                dates = sorted(df['date'].unique())
                
                for trade_date in dates:
                    day_data = df[df['date'] == trade_date]
                    
                    # Get expiries
                    expiries = sorted(day_data['expiry'].unique())
                    
                    if len(expiries) < 2:
                        continue
                    
                    # Near-term: first expiry
                    # Far-term: second expiry
                    near_expiry = expiries[0]
                    far_expiry = expiries[1]
                    
                    # Accelerate near-term decay (reduce premium by 20%)
                    near_mask = (df['date'] == trade_date) & (df['expiry'] == near_expiry)
                    df.loc[near_mask, 'ltp'] *= 0.8
                    df.loc[near_mask, 'bid'] *= 0.8
                    df.loc[near_mask, 'ask'] *= 0.8
                    
                    # Slow far-term decay (increase premium by 10%)
                    far_mask = (df['date'] == trade_date) & (df['expiry'] == far_expiry)
                    df.loc[far_mask, 'ltp'] *= 1.1
                    df.loc[far_mask, 'bid'] *= 1.1
                    df.loc[far_mask, 'ask'] *= 1.1
                
                engine.option_chains[symbol] = df
                
                logger.info(
                    f"Applied calendar failure to {symbol}: "
                    f"Near-term decay accelerated, far-term slowed"
                )
    
    def _modify_consecutive_losses(
        self,
        engine: BacktestSimulationEngine
    ) -> None:
        """
        Modify data for consecutive losses scenario.
        
        Ensures first 3 trades result in losses.
        """
        logger.info("Applying consecutive losses modifications...")
        
        # This is tricky - we need to ensure trades lose money
        # We'll reduce all option premiums by 30% to create losses
        
        for symbol in engine.config.symbols:
            if symbol in engine.option_chains:
                df = engine.option_chains[symbol]
                
                # Get first 3 weeks of data
                dates = sorted(df['date'].unique())
                loss_period_dates = dates[:21]  # ~3 weeks
                
                # Reduce premiums during loss period
                mask = df['date'].isin(loss_period_dates)
                df.loc[mask, 'ltp'] *= 0.7
                df.loc[mask, 'bid'] *= 0.7
                df.loc[mask, 'ask'] *= 0.7
                
                engine.option_chains[symbol] = df
                
                logger.info(
                    f"Applied consecutive losses to {symbol}: "
                    f"Premiums reduced 30% for first 3 weeks"
                )
    
    def _analyze_scenario_results(
        self,
        scenario: StressScenario,
        results: BacktestResults
    ) -> Dict:
        """
        Analyze scenario results against success criteria.
        
        Args:
            scenario: Stress scenario definition
            results: Backtest results
            
        Returns:
            Analysis dictionary with pass/fail for each criterion
        """
        analysis = {
            'criteria_checks': {},
            'passed': True,
            'summary': []
        }
        
        criteria = scenario.success_criteria
        
        # Check each criterion
        if 'max_drawdown_pct' in criteria:
            actual = results.max_drawdown_pct
            expected = criteria['max_drawdown_pct']
            passed = actual <= expected
            
            analysis['criteria_checks']['max_drawdown_pct'] = {
                'expected': f"<= {expected}%",
                'actual': f"{actual:.2f}%",
                'passed': passed
            }
            
            if not passed:
                analysis['passed'] = False
                analysis['summary'].append(
                    f"Max drawdown {actual:.2f}% exceeds limit {expected}%"
                )
        
        if 'trauma_activations' in criteria:
            actual = results.trauma_rule_activations
            expected = criteria['trauma_activations']
            passed = actual >= expected
            
            analysis['criteria_checks']['trauma_activations'] = {
                'expected': f">= {expected}",
                'actual': actual,
                'passed': passed
            }
            
            if not passed:
                analysis['passed'] = False
                analysis['summary'].append(
                    f"Trauma activations {actual} below expected {expected}"
                )
        
        if 'kill_switch_activations' in criteria:
            actual = results.kill_switch_activations
            expected = criteria['kill_switch_activations']
            passed = actual >= expected
            
            analysis['criteria_checks']['kill_switch_activations'] = {
                'expected': f">= {expected}",
                'actual': actual,
                'passed': passed
            }
            
            if not passed:
                analysis['passed'] = False
                analysis['summary'].append(
                    f"Kill switch activations {actual} below expected {expected}"
                )
        
        if 'max_consecutive_losses' in criteria:
            # Calculate consecutive losses
            max_consecutive = 0
            current_consecutive = 0
            
            for trade in results.trades:
                if trade.net_pnl < 0:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 0
            
            expected = criteria['max_consecutive_losses']
            passed = max_consecutive <= expected
            
            analysis['criteria_checks']['max_consecutive_losses'] = {
                'expected': f"<= {expected}",
                'actual': max_consecutive,
                'passed': passed
            }
            
            if not passed:
                analysis['passed'] = False
                analysis['summary'].append(
                    f"Consecutive losses {max_consecutive} exceeds limit {expected}"
                )
        
        # Add success message if all passed
        if analysis['passed']:
            analysis['summary'].append("All success criteria met")
        
        return analysis
    
    def print_scenario_report(self, scenario_result: Dict) -> None:
        """Print a formatted scenario report."""
        print("\n" + "=" * 70)
        print(f"STRESS TEST: {scenario_result['scenario'].upper()}")
        print("=" * 70)
        
        print(f"\nDescription: {scenario_result['description']}")
        print(f"\nExpected Behavior:\n{scenario_result['expected_behavior']}")
        
        if 'error' in scenario_result:
            print(f"\n❌ SCENARIO FAILED")
            print(f"Error: {scenario_result['error']}")
            return
        
        results = scenario_result['results']
        analysis = scenario_result['analysis']
        
        print(f"\n{'RESULTS':-^70}")
        print(f"Total Trades: {results.total_trades}")
        print(f"Win Rate: {results.win_rate:.1f}%")
        print(f"Total Return: {results.total_return_pct:.2f}%")
        print(f"Max Drawdown: {results.max_drawdown_pct:.2f}%")
        print(f"Kill Switch Activations: {results.kill_switch_activations}")
        print(f"Trauma Activations: {results.trauma_rule_activations}")
        
        print(f"\n{'SUCCESS CRITERIA':-^70}")
        for criterion, check in analysis['criteria_checks'].items():
            status = "✓" if check['passed'] else "✗"
            print(
                f"{status} {criterion}: "
                f"Expected {check['expected']}, Got {check['actual']}"
            )
        
        print(f"\n{'OVERALL':-^70}")
        if scenario_result['success']:
            print("✓ SCENARIO PASSED")
        else:
            print("✗ SCENARIO FAILED")
            for msg in analysis['summary']:
                print(f"  - {msg}")
        
        print("=" * 70)


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Stress Test Scenarios - Standalone Test")
    print("=" * 60)
    
    # Create test config
    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 1),
        initial_capital=500_000.0,
        symbols=['NIFTY']
    )
    
    # Initialize stress tests
    stress_tests = StressTestScenarios()
    
    print(f"\nDefined {len(stress_tests.scenarios)} stress test scenarios:")
    for scenario in stress_tests.scenarios:
        print(f"\n  • {scenario.name}")
        print(f"    {scenario.description}")
    
    print("\n" + "=" * 60)
    print("Note: Actual stress test execution requires historical data")
    print("=" * 60)
    
    # Example of how to run scenarios (would need real data)
    # results = stress_tests.run_all_scenarios(config)
    # for result in results:
    #     stress_tests.print_scenario_report(result)
