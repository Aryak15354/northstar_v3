#!/usr/bin/env python3
"""
📊 ENHANCED PORTFOLIO SIMULATOR - COMPLETE TRACKING
Fund-grade portfolio simulation with comprehensive tracking and attribution

This enhances the Shadow Fund Engine with:
- Complete daily recording of all portfolio metrics
- Regime-specific performance tracking
- Enhanced drawdown measurement and recovery analysis
- Performance attribution to individual specialists
- Complete audit trail integration
- Risk event logging and analysis

Usage:
    from src.validation.enhanced_portfolio_simulator import EnhancedPortfolioSimulator
    
    simulator = EnhancedPortfolioSimulator()
    results = simulator.run_complete_simulation(start_date, end_date)
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.execution.shadow_fund_engine import ShadowFundEngine
from src.validation.universe_manager import UniverseManager

class EnhancedPortfolioSimulator(ShadowFundEngine):
    """
    Enhanced Portfolio Simulator with Complete Tracking
    
    Extends Shadow Fund Engine with:
    - Daily portfolio metrics recording
    - Regime performance attribution
    - Enhanced drawdown analysis
    - Specialist contribution tracking
    - Complete audit trail
    - Risk event correlation
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Enhanced Portfolio Simulator"
        self.version = "1.0"
        
        # Initialize components
        self.universe_manager = UniverseManager()
        
        # Enhanced tracking paths
        self.tracking_paths = {
            'daily_metrics': 'data/simulation/daily_portfolio_metrics.parquet',
            'regime_performance': 'data/simulation/regime_performance_tracking.parquet',
            'drawdown_analysis': 'data/simulation/drawdown_analysis.parquet',
            'specialist_attribution': 'data/simulation/specialist_attribution.parquet',
            'risk_events': 'data/simulation/risk_events.parquet',
            'audit_trail': 'data/simulation/complete_audit_trail.parquet',
            'simulation_summary': 'data/simulation/simulation_summary.json'
        }
        
        # Create simulation directory
        os.makedirs('data/simulation', exist_ok=True)
        
        # Tracking state
        self.daily_records = []
        self.regime_records = []
        self.drawdown_records = []
        self.specialist_records = []
        self.risk_event_records = []
        self.audit_records = []
        
        # Performance tracking
        self.peak_portfolio_value = self.fund_params['initial_capital']
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.drawdown_start_date = None
        self.drawdown_recovery_date = None
        
        # Regime tracking
        self.current_regime = None
        self.regime_start_date = None
        self.regime_performance = {}
        
    def record_daily_metrics(self, date: datetime, portfolio_value: float, 
                           positions: Dict, market_data: Dict, 
                           specialist_signals: Dict) -> Dict:
        """Record comprehensive daily portfolio metrics"""
        
        # Calculate returns
        daily_return = (portfolio_value / self.peak_portfolio_value) - 1 if self.peak_portfolio_value > 0 else 0.0
        
        # Update peak and drawdown
        if portfolio_value > self.peak_portfolio_value:
            # New peak - end any current drawdown
            if self.current_drawdown < 0:
                self.drawdown_recovery_date = date
                self._record_drawdown_recovery()
            
            self.peak_portfolio_value = portfolio_value
            self.current_drawdown = 0.0
            self.drawdown_start_date = None
        else:
            # Calculate current drawdown
            new_drawdown = (portfolio_value / self.peak_portfolio_value) - 1
            
            if new_drawdown < self.current_drawdown:
                # Drawdown deepening
                if self.current_drawdown == 0.0:
                    self.drawdown_start_date = date
                
                self.current_drawdown = new_drawdown
                self.max_drawdown = min(self.max_drawdown, new_drawdown)
        
        # Calculate portfolio metrics
        total_positions = len([p for p in positions.values() if p['shares'] != 0])
        long_positions = len([p for p in positions.values() if p['shares'] > 0])
        short_positions = len([p for p in positions.values() if p['shares'] < 0])
        
        gross_exposure = sum(abs(p['market_value']) for p in positions.values())
        net_exposure = sum(p['market_value'] for p in positions.values())
        
        leverage = gross_exposure / portfolio_value if portfolio_value > 0 else 0.0
        
        # Calculate sector/style exposures (simplified)
        sector_exposures = self._calculate_sector_exposures(positions)
        
        # Record daily metrics
        daily_record = {
            'date': date,
            'portfolio_value': portfolio_value,
            'daily_return': daily_return,
            'cumulative_return': (portfolio_value / self.fund_params['initial_capital']) - 1,
            'peak_value': self.peak_portfolio_value,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'drawdown_days': (date - self.drawdown_start_date).days if self.drawdown_start_date else 0,
            'total_positions': total_positions,
            'long_positions': long_positions,
            'short_positions': short_positions,
            'gross_exposure': gross_exposure,
            'net_exposure': net_exposure,
            'leverage': leverage,
            'cash_position': self.current_capital,
            'volatility_20d': self._calculate_rolling_volatility(20),
            'sharpe_ratio_20d': self._calculate_rolling_sharpe(20),
            'turnover': self._calculate_daily_turnover(),
            **sector_exposures,
            **self._extract_market_metrics(market_data),
            **self._extract_specialist_metrics(specialist_signals)
        }
        
        self.daily_records.append(daily_record)
        return daily_record
    
    def record_regime_performance(self, date: datetime, current_regime: str, 
                                regime_confidence: float, portfolio_value: float) -> Dict:
        """Record regime-specific performance tracking"""
        
        # Check for regime change
        if current_regime != self.current_regime:
            # End previous regime tracking
            if self.current_regime is not None:
                self._finalize_regime_period(date, portfolio_value)
            
            # Start new regime tracking
            self.current_regime = current_regime
            self.regime_start_date = date
            self.regime_performance[current_regime] = {
                'start_date': date,
                'start_value': portfolio_value,
                'regime_confidence': regime_confidence
            }
        
        # Update current regime performance
        if self.current_regime in self.regime_performance:
            regime_data = self.regime_performance[self.current_regime]
            regime_return = (portfolio_value / regime_data['start_value']) - 1
            regime_days = max(0, (date - regime_data['start_date']).days)  # Ensure non-negative
            
            regime_record = {
                'date': date,
                'regime': current_regime,
                'regime_confidence': regime_confidence,
                'regime_start_date': regime_data['start_date'],
                'regime_days': regime_days,
                'regime_return': regime_return,
                'annualized_return': regime_return * (365.25 / max(1, regime_days)),
                'portfolio_value': portfolio_value,
                'regime_volatility': self._calculate_regime_volatility(current_regime),
                'regime_sharpe': self._calculate_regime_sharpe(current_regime),
                'regime_max_drawdown': self._calculate_regime_max_drawdown(current_regime)
            }
            
            self.regime_records.append(regime_record)
            return regime_record
        
        return {}
    
    def record_drawdown_analysis(self, date: datetime, portfolio_value: float) -> Dict:
        """Record enhanced drawdown measurement and recovery analysis"""
        
        if self.current_drawdown < 0:  # In drawdown
            drawdown_days = (date - self.drawdown_start_date).days if self.drawdown_start_date else 0
            
            # Analyze drawdown characteristics
            drawdown_record = {
                'date': date,
                'drawdown_start': self.drawdown_start_date,
                'drawdown_days': drawdown_days,
                'current_drawdown': self.current_drawdown,
                'max_drawdown': self.max_drawdown,
                'peak_value': self.peak_portfolio_value,
                'current_value': portfolio_value,
                'recovery_needed': (self.peak_portfolio_value / portfolio_value) - 1,
                'drawdown_severity': self._classify_drawdown_severity(self.current_drawdown),
                'estimated_recovery_days': self._estimate_recovery_time(self.current_drawdown),
                'drawdown_regime': self.current_regime,
                'underwater_curve': self.current_drawdown
            }
            
            self.drawdown_records.append(drawdown_record)
            return drawdown_record
        
        return {}
    
    def record_specialist_attribution(self, date: datetime, specialist_signals: Dict, 
                                   portfolio_return: float) -> Dict:
        """Record performance attribution to individual specialists"""
        
        attribution_record = {
            'date': date,
            'portfolio_return': portfolio_return
        }
        
        # Calculate specialist contributions
        total_signal_strength = sum(abs(signal.get('strength', 0)) for signal in specialist_signals.values())
        
        for specialist_name, signal_data in specialist_signals.items():
            signal_strength = signal_data.get('strength', 0)
            signal_direction = 1 if signal_strength > 0 else -1
            
            # Estimate specialist contribution (simplified attribution)
            if total_signal_strength > 0:
                weight = abs(signal_strength) / total_signal_strength
                attributed_return = portfolio_return * weight * signal_direction
            else:
                attributed_return = 0.0
            
            attribution_record[f'{specialist_name}_signal_strength'] = signal_strength
            attribution_record[f'{specialist_name}_attributed_return'] = attributed_return
            attribution_record[f'{specialist_name}_confidence'] = signal_data.get('confidence', 0)
            attribution_record[f'{specialist_name}_regime_fit'] = signal_data.get('regime_fit', 0)
        
        self.specialist_records.append(attribution_record)
        return attribution_record
    
    def record_risk_events(self, date: datetime, risk_events: List[Dict]) -> List[Dict]:
        """Record risk events and their portfolio impact"""
        
        recorded_events = []
        
        for event in risk_events:
            risk_record = {
                'date': date,
                'event_type': event.get('type', 'unknown'),
                'severity': event.get('severity', 'low'),
                'description': event.get('description', ''),
                'portfolio_impact': event.get('portfolio_impact', 0.0),
                'positions_affected': event.get('positions_affected', 0),
                'action_taken': event.get('action_taken', 'none'),
                'recovery_time': event.get('recovery_time', None),
                'regime_context': self.current_regime
            }
            
            self.risk_event_records.append(risk_record)
            recorded_events.append(risk_record)
        
        return recorded_events
    
    def create_complete_audit_trail(self, date: datetime, trades: List[Dict], 
                                  decisions: Dict, market_data: Dict) -> Dict:
        """Create complete audit trail for all decisions and actions"""
        
        audit_record = {
            'timestamp': datetime.now(),
            'simulation_date': date,
            'trade_count': len(trades),
            'total_trade_value': sum(abs(t.get('trade_value', 0)) for t in trades),
            'regime': self.current_regime,
            'market_conditions': str(market_data.get('conditions', {})),
            'risk_level': decisions.get('risk_level', 'normal'),
            'confidence_level': decisions.get('confidence_level', 0.5),
            'total_positions': len(self.current_positions),
            'gross_exposure': sum(abs(p['market_value']) for p in self.current_positions.values()),
            'cash_position': self.current_capital,
            'leverage': self._calculate_current_leverage(),
            'risk_checks_count': len(decisions.get('risk_checks', [])),
            'constraints_count': len(decisions.get('constraints', [])),
            'specialist_inputs_count': len(decisions.get('specialist_inputs', {})),
            'bayesian_updates_count': len(decisions.get('bayesian_updates', {}))
        }
        
        self.audit_records.append(audit_record)
        return audit_record
    
    def run_complete_simulation(self, start_date: datetime, end_date: datetime, 
                              initial_portfolio: Optional[Dict] = None) -> Dict:
        """Run complete portfolio simulation with comprehensive tracking"""
        
        print(f"🚀 ENHANCED PORTFOLIO SIMULATION")
        print(f"=" * 50)
        print(f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"💰 Initial Capital: ₹{self.fund_params['initial_capital']:,.0f}")
        
        # Initialize simulation
        current_date = start_date
        simulation_days = 0
        
        while current_date <= end_date:
            simulation_days += 1
            
            # Skip weekends (simplified)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            print(f"\n📅 Simulating {current_date.strftime('%Y-%m-%d')} (Day {simulation_days})")
            
            # Get universe for this date
            universe = self.universe_manager.get_universe_at_date(current_date)
            
            # Get market data and conditions
            market_data = self._get_market_data(current_date)
            
            # Get specialist signals
            specialist_signals = self._get_specialist_signals(current_date, universe, market_data)
            
            # Get regime information
            current_regime = market_data.get('regime', 'normal')
            regime_confidence = market_data.get('regime_confidence', 0.5)
            
            # Generate portfolio decisions
            decisions = self._generate_portfolio_decisions(specialist_signals, market_data, universe)
            
            # Execute trades (if any)
            trades = []
            if decisions.get('rebalance_needed', False):
                target_portfolio = decisions.get('target_portfolio', {})
                current_prices = self._get_current_prices(current_date, universe)
                trades = self.execute_trades(target_portfolio, current_prices, market_data)
            
            # Calculate current portfolio value
            portfolio_value = self._calculate_portfolio_value(current_date, universe)
            
            # Record all tracking data
            daily_metrics = self.record_daily_metrics(
                current_date, portfolio_value, self.current_positions, 
                market_data, specialist_signals
            )
            
            regime_performance = self.record_regime_performance(
                current_date, current_regime, regime_confidence, portfolio_value
            )
            
            drawdown_analysis = self.record_drawdown_analysis(current_date, portfolio_value)
            
            specialist_attribution = self.record_specialist_attribution(
                current_date, specialist_signals, daily_metrics['daily_return']
            )
            
            # Check for risk events
            risk_events = self._check_risk_events(current_date, daily_metrics, market_data)
            if risk_events:
                self.record_risk_events(current_date, risk_events)
            
            # Create audit trail
            audit_trail = self.create_complete_audit_trail(
                current_date, trades, decisions, market_data
            )
            
            # Progress reporting
            if simulation_days % 30 == 0:  # Monthly progress
                print(f"   📊 Portfolio Value: ₹{portfolio_value:,.0f}")
                print(f"   📈 Return: {daily_metrics['cumulative_return']:.2%}")
                print(f"   📉 Max Drawdown: {self.max_drawdown:.2%}")
                print(f"   🎯 Positions: {daily_metrics['total_positions']}")
            
            current_date += timedelta(days=1)
        
        # Finalize simulation
        simulation_results = self._finalize_simulation_results(start_date, end_date)
        
        # Save all tracking data
        self._save_complete_tracking_data()
        
        print(f"\n✅ SIMULATION COMPLETE")
        print(f"📊 Total Days: {simulation_days}")
        print(f"📈 Final Return: {simulation_results['total_return']:.2%}")
        print(f"📉 Max Drawdown: {simulation_results['max_drawdown']:.2%}")
        print(f"📊 Sharpe Ratio: {simulation_results['sharpe_ratio']:.2f}")
        
        return simulation_results
    
    def _calculate_sector_exposures(self, positions: Dict) -> Dict:
        """Calculate sector exposures (simplified)"""
        # Simplified sector mapping - in reality would use proper sector data
        return {
            'financials_exposure': 0.0,
            'technology_exposure': 0.0,
            'healthcare_exposure': 0.0,
            'consumer_exposure': 0.0,
            'industrial_exposure': 0.0
        }
    
    def _calculate_rolling_volatility(self, days: int) -> float:
        """Calculate rolling volatility"""
        if len(self.daily_records) < days:
            return 0.0
        
        recent_returns = [r['daily_return'] for r in self.daily_records[-days:]]
        return np.std(recent_returns) * np.sqrt(252)  # Annualized
    
    def _calculate_rolling_sharpe(self, days: int) -> float:
        """Calculate rolling Sharpe ratio"""
        if len(self.daily_records) < days:
            return 0.0
        
        recent_returns = [r['daily_return'] for r in self.daily_records[-days:]]
        mean_return = np.mean(recent_returns) * 252  # Annualized
        volatility = np.std(recent_returns) * np.sqrt(252)  # Annualized
        
        return mean_return / volatility if volatility > 0 else 0.0
    
    def _calculate_daily_turnover(self) -> float:
        """Calculate daily portfolio turnover"""
        # Simplified turnover calculation
        return 0.0
    
    def _extract_market_metrics(self, market_data: Dict) -> Dict:
        """Extract market-related metrics"""
        return {
            'market_regime': market_data.get('regime', 'normal'),
            'market_volatility': market_data.get('volatility', 0.0),
            'market_return': market_data.get('return', 0.0)
        }
    
    def _extract_specialist_metrics(self, specialist_signals: Dict) -> Dict:
        """Extract specialist-related metrics"""
        metrics = {}
        for name, signal in specialist_signals.items():
            metrics[f'{name}_strength'] = signal.get('strength', 0)
            metrics[f'{name}_confidence'] = signal.get('confidence', 0)
        return metrics
    
    def _finalize_regime_period(self, end_date: datetime, end_value: float):
        """Finalize regime period tracking"""
        if self.current_regime in self.regime_performance:
            regime_data = self.regime_performance[self.current_regime]
            regime_data['end_date'] = end_date
            regime_data['end_value'] = end_value
            regime_data['total_return'] = (end_value / regime_data['start_value']) - 1
    
    def _record_drawdown_recovery(self):
        """Record drawdown recovery event"""
        if self.drawdown_start_date and self.drawdown_recovery_date:
            recovery_days = (self.drawdown_recovery_date - self.drawdown_start_date).days
            print(f"   🔄 Drawdown Recovery: {recovery_days} days, {self.max_drawdown:.2%} max DD")
    
    def _classify_drawdown_severity(self, drawdown: float) -> str:
        """Classify drawdown severity"""
        if drawdown > -0.05:
            return 'minor'
        elif drawdown > -0.10:
            return 'moderate'
        elif drawdown > -0.20:
            return 'significant'
        else:
            return 'severe'
    
    def _estimate_recovery_time(self, drawdown: float) -> int:
        """Estimate recovery time based on historical patterns"""
        # Simplified estimation
        if drawdown > -0.05:
            return 30
        elif drawdown > -0.10:
            return 90
        elif drawdown > -0.20:
            return 180
        else:
            return 365
    
    def _calculate_regime_volatility(self, regime: str) -> float:
        """Calculate volatility for current regime"""
        regime_returns = [r['daily_return'] for r in self.daily_records 
                         if r.get('market_regime') == regime]
        return np.std(regime_returns) * np.sqrt(252) if regime_returns else 0.0
    
    def _calculate_regime_sharpe(self, regime: str) -> float:
        """Calculate Sharpe ratio for current regime"""
        regime_returns = [r['daily_return'] for r in self.daily_records 
                         if r.get('market_regime') == regime]
        if not regime_returns:
            return 0.0
        
        mean_return = np.mean(regime_returns) * 252
        volatility = np.std(regime_returns) * np.sqrt(252)
        return mean_return / volatility if volatility > 0 else 0.0
    
    def _calculate_regime_max_drawdown(self, regime: str) -> float:
        """Calculate max drawdown for current regime"""
        regime_records = [r for r in self.daily_records if r.get('market_regime') == regime]
        if not regime_records:
            return 0.0
        
        peak = regime_records[0]['portfolio_value']
        max_dd = 0.0
        
        for record in regime_records:
            if record['portfolio_value'] > peak:
                peak = record['portfolio_value']
            else:
                dd = (record['portfolio_value'] / peak) - 1
                max_dd = min(max_dd, dd)
        
        return max_dd
    
    def _get_market_data(self, date: datetime) -> Dict:
        """Get market data for simulation (mock implementation)"""
        return {
            'regime': 'normal',
            'regime_confidence': 0.7,
            'volatility': 0.15,
            'return': np.random.normal(0.0008, 0.02),  # Mock daily return
            'conditions': {'crisis_mode': False, 'liquidity': 'normal'}
        }
    
    def _get_specialist_signals(self, date: datetime, universe: Dict, market_data: Dict) -> Dict:
        """Get specialist signals (mock implementation)"""
        return {
            'momentum_specialist': {'strength': np.random.normal(0, 0.5), 'confidence': 0.6},
            'mean_reversion_specialist': {'strength': np.random.normal(0, 0.3), 'confidence': 0.7},
            'volatility_specialist': {'strength': np.random.normal(0, 0.4), 'confidence': 0.5}
        }
    
    def _generate_portfolio_decisions(self, specialist_signals: Dict, market_data: Dict, universe: Dict) -> Dict:
        """Generate portfolio decisions based on signals"""
        return {
            'rebalance_needed': np.random.random() < 0.1,  # 10% chance of rebalance
            'target_portfolio': {},
            'risk_level': 'normal',
            'confidence_level': 0.6
        }
    
    def _get_current_prices(self, date: datetime, universe: Dict) -> Dict:
        """Get current prices (mock implementation)"""
        return {symbol: np.random.uniform(50, 500) for symbol in list(universe.keys())[:10]}
    
    def _calculate_portfolio_value(self, date: datetime, universe: Dict) -> float:
        """Calculate current portfolio value"""
        total_value = self.current_capital
        
        for ticker, position in self.current_positions.items():
            # Mock price movement
            current_price = position.get('avg_price', 100) * (1 + np.random.normal(0, 0.02))
            total_value += position['shares'] * current_price
        
        return total_value
    
    def _calculate_current_leverage(self) -> float:
        """Calculate current portfolio leverage"""
        gross_exposure = sum(abs(p['market_value']) for p in self.current_positions.values())
        portfolio_value = self.current_capital + sum(p['unrealized_pnl'] for p in self.current_positions.values())
        return gross_exposure / portfolio_value if portfolio_value > 0 else 0.0
    
    def _check_risk_events(self, date: datetime, daily_metrics: Dict, market_data: Dict) -> List[Dict]:
        """Check for risk events"""
        risk_events = []
        
        # Check for significant drawdown
        if daily_metrics['current_drawdown'] < -0.10:
            risk_events.append({
                'type': 'significant_drawdown',
                'severity': 'high',
                'description': f"Portfolio in {daily_metrics['current_drawdown']:.2%} drawdown",
                'portfolio_impact': daily_metrics['current_drawdown']
            })
        
        return risk_events
    
    def _finalize_simulation_results(self, start_date: datetime, end_date: datetime) -> Dict:
        """Finalize and summarize simulation results"""
        
        if not self.daily_records:
            return {}
        
        final_record = self.daily_records[-1]
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'simulation_days': len(self.daily_records),
            'initial_capital': self.fund_params['initial_capital'],
            'final_value': final_record['portfolio_value'],
            'total_return': final_record['cumulative_return'],
            'annualized_return': final_record['cumulative_return'] * (365.25 / len(self.daily_records)),
            'max_drawdown': self.max_drawdown,
            'volatility': self._calculate_rolling_volatility(len(self.daily_records)),
            'sharpe_ratio': self._calculate_rolling_sharpe(len(self.daily_records)),
            'total_trades': len([r for r in self.audit_records if r.get('trade_count', 0) > 0]),
            'avg_positions': np.mean([r['total_positions'] for r in self.daily_records]),
            'regime_breakdown': self._calculate_regime_breakdown()
        }
    
    def _calculate_regime_breakdown(self) -> Dict:
        """Calculate performance breakdown by regime"""
        regime_stats = {}
        
        for regime in set(r.get('market_regime', 'unknown') for r in self.daily_records):
            regime_records = [r for r in self.daily_records if r.get('market_regime') == regime]
            if regime_records:
                regime_returns = [r['daily_return'] for r in regime_records]
                regime_stats[regime] = {
                    'days': len(regime_records),
                    'total_return': sum(regime_returns),
                    'avg_return': np.mean(regime_returns),
                    'volatility': np.std(regime_returns) * np.sqrt(252)
                }
        
        return regime_stats
    
    def _save_complete_tracking_data(self):
        """Save all tracking data to files"""
        
        # Save daily metrics
        if self.daily_records:
            daily_df = pd.DataFrame(self.daily_records)
            daily_df.to_parquet(self.tracking_paths['daily_metrics'], index=False)
        
        # Save regime performance
        if self.regime_records:
            regime_df = pd.DataFrame(self.regime_records)
            regime_df.to_parquet(self.tracking_paths['regime_performance'], index=False)
        
        # Save drawdown analysis
        if self.drawdown_records:
            drawdown_df = pd.DataFrame(self.drawdown_records)
            drawdown_df.to_parquet(self.tracking_paths['drawdown_analysis'], index=False)
        
        # Save specialist attribution
        if self.specialist_records:
            specialist_df = pd.DataFrame(self.specialist_records)
            specialist_df.to_parquet(self.tracking_paths['specialist_attribution'], index=False)
        
        # Save risk events
        if self.risk_event_records:
            risk_df = pd.DataFrame(self.risk_event_records)
            risk_df.to_parquet(self.tracking_paths['risk_events'], index=False)
        
        # Save audit trail
        if self.audit_records:
            audit_df = pd.DataFrame(self.audit_records)
            audit_df.to_parquet(self.tracking_paths['audit_trail'], index=False)
        
        print(f"✅ Saved complete tracking data to data/simulation/")


def main():
    """Main execution function for testing"""
    
    print("📊 ENHANCED PORTFOLIO SIMULATOR - COMPLETE TRACKING")
    print("=" * 60)
    
    simulator = EnhancedPortfolioSimulator()
    
    # Run a short simulation for testing
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 31)  # One month test
    
    results = simulator.run_complete_simulation(start_date, end_date)
    
    print(f"\n📊 SIMULATION RESULTS:")
    for key, value in results.items():
        if isinstance(value, float):
            if 'return' in key or 'drawdown' in key:
                print(f"   {key}: {value:.2%}")
            else:
                print(f"   {key}: {value:.4f}")
        else:
            print(f"   {key}: {value}")


if __name__ == "__main__":
    main()
