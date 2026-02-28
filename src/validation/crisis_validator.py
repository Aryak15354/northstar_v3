#!/usr/bin/env python3
"""
🚨 CRISIS VALIDATOR - PRE-CRISIS ANALYSIS ENGINE
The component that validates system behavior during historical market crises

This implements crisis period validation with pre-crisis positioning analysis:
- 2008 Financial Crisis validation
- 2020 COVID crash analysis  
- 2022 Inflation shock testing
- Pre-crisis positioning analysis (30-day exposure tracking)
- Defensive positioning scoring
- Anticipatory de-risking detection
- Crisis survival metrics

Usage:
    from src.validation.crisis_validator import CrisisValidator
    
    validator = CrisisValidator()
    crisis_report = validator.validate_crisis_performance(simulation_results)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

warnings.filterwarnings('ignore')

import sys
from src.volatility.regime_detector import VolatilityRegime
from src.risk.portfolio_kill_switches import PortfolioKillSwitches

class CrisisType(Enum):
    """Types of market crises"""
    FINANCIAL_CRISIS = "financial_crisis"
    PANDEMIC_SHOCK = "pandemic_shock"
    INFLATION_SHOCK = "inflation_shock"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    GEOPOLITICAL_SHOCK = "geopolitical_shock"

@dataclass
@dataclass
class CrisisMetrics:
    """Crisis performance metrics"""
    crisis_name: str
    period: Tuple[datetime, datetime]
    
    # Performance during crisis
    max_drawdown: float
    recovery_time_days: int
    crisis_sharpe: float
    total_return: float
    
    # Pre-crisis positioning (CRITICAL)
    exposure_30d_before: float
    risk_reduction_rate: float
    defensive_positioning_score: float
    anticipatory_de_risking: bool
    
    # Risk management effectiveness
    emergency_triggers_activated: int
    position_size_reductions: int
    regime_adaptation_speed_days: float
    
    # Survival metrics
    survived_without_intervention: bool
    maximum_leverage_during_crisis: float
    cash_reserves_maintained: float
    
    # Additional metrics
    volatility_during_crisis: float
    correlation_with_market: float
    downside_capture_ratio: float

@dataclass
class CrisisReport:
    """Complete crisis validation report"""
    validation_timestamp: datetime
    total_crises_analyzed: int
    crisis_metrics: Dict[str, CrisisMetrics]
    overall_survival_score: float
    pre_crisis_positioning_score: float
    risk_management_effectiveness: float
    recommendations: List[str]

class CrisisValidator:
    """
    Crisis Validator - Validates system behavior during historical market crises
    
    This component analyzes how the system would have performed during major
    historical crises, with special focus on pre-crisis positioning and
    anticipatory risk management.
    """
    
    def __init__(self):
        self.name = "Crisis Validator"
        self.version = "1.0"
        
        # Historical crisis periods (start, end)
        self.crisis_periods = {
            'financial_crisis_2008': {
                'type': CrisisType.FINANCIAL_CRISIS,
                'period': (datetime(2007, 7, 1), datetime(2009, 3, 31)),
                'pre_crisis_start': datetime(2007, 6, 1),  # 30 days before
                'description': '2008 Financial Crisis - Subprime mortgage collapse',
                'market_decline': -0.57,  # S&P 500 peak to trough
                'duration_months': 20
            },
            'covid_crash_2020': {
                'type': CrisisType.PANDEMIC_SHOCK,
                'period': (datetime(2020, 2, 1), datetime(2020, 5, 31)),
                'pre_crisis_start': datetime(2020, 1, 1),  # 30 days before
                'description': '2020 COVID Pandemic - Global lockdowns',
                'market_decline': -0.34,  # S&P 500 peak to trough
                'duration_months': 4
            },
            'inflation_shock_2022': {
                'type': CrisisType.INFLATION_SHOCK,
                'period': (datetime(2022, 1, 1), datetime(2022, 12, 31)),
                'pre_crisis_start': datetime(2021, 12, 1),  # 30 days before
                'description': '2022 Inflation Shock - Fed tightening cycle',
                'market_decline': -0.25,  # S&P 500 peak to trough
                'duration_months': 12
            }
        }
        
        # Crisis detection thresholds
        self.crisis_thresholds = {
            'market_decline_threshold': -0.10,  # 10%+ decline
            'volatility_spike_threshold': 0.35,  # 35%+ annualized volatility
            'correlation_spike_threshold': 0.80,  # 80%+ correlation
            'liquidity_dry_up_threshold': 0.30   # 30% liquidity reduction
        }
        
        # Pre-crisis analysis window
        self.pre_crisis_window = 30  # Days before crisis to analyze
        
        # Defensive asset classes and sectors
        self.defensive_assets = {
            'sectors': ['Utilities', 'Consumer Staples', 'Healthcare'],
            'asset_classes': ['Government Bonds', 'Gold', 'Cash'],
            'factors': ['Low Volatility', 'Quality', 'Dividend Yield']
        }
        
        # Initialize kill switches for emergency detection
        self.kill_switches = PortfolioKillSwitches()
        
        print("🚨 Crisis Validator initialized - Historical crisis analysis ready")
    
    def detect_crisis_periods(self, market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect crisis periods in market data using quantitative criteria
        
        Args:
            market_data: DataFrame with columns ['date', 'price', 'volume']
            
        Returns:
            List of detected crisis periods with metadata
        """
        
        if market_data.empty:
            return []
        
        market_data = market_data.sort_values('date').copy()
        market_data['returns'] = market_data['price'].pct_change()
        market_data['volatility'] = market_data['returns'].rolling(21).std() * np.sqrt(252)
        
        # Calculate rolling drawdowns
        market_data['peak'] = market_data['price'].expanding().max()
        market_data['drawdown'] = (market_data['price'] - market_data['peak']) / market_data['peak']
        
        detected_crises = []
        
        # Detect crisis periods based on thresholds
        crisis_mask = (
            (market_data['drawdown'] <= self.crisis_thresholds['market_decline_threshold']) |
            (market_data['volatility'] >= self.crisis_thresholds['volatility_spike_threshold'])
        )
        
        # Group consecutive crisis days
        crisis_periods = []
        in_crisis = False
        crisis_start = None
        
        for idx, row in market_data.iterrows():
            if crisis_mask.loc[idx] and not in_crisis:
                # Crisis starts
                in_crisis = True
                crisis_start = row['date']
            elif not crisis_mask.loc[idx] and in_crisis:
                # Crisis ends
                in_crisis = False
                if crisis_start is not None:
                    crisis_periods.append((crisis_start, row['date']))
        
        # Convert to crisis metadata
        for i, (start_date, end_date) in enumerate(crisis_periods):
            crisis_data = market_data[
                (market_data['date'] >= start_date) & 
                (market_data['date'] <= end_date)
            ]
            
            if len(crisis_data) > 5:  # Minimum 5 days for a crisis
                max_drawdown = crisis_data['drawdown'].min()
                max_volatility = crisis_data['volatility'].max()
                
                detected_crises.append({
                    'crisis_id': f'detected_crisis_{i+1}',
                    'type': CrisisType.LIQUIDITY_CRISIS,  # Default type
                    'period': (start_date, end_date),
                    'max_drawdown': max_drawdown,
                    'max_volatility': max_volatility,
                    'duration_days': (end_date - start_date).days,
                    'description': f'Detected crisis {i+1}: {max_drawdown:.1%} drawdown'
                })
        
        return detected_crises
    
    def analyze_pre_crisis_positioning(self, portfolio_data: pd.DataFrame, 
                                     crisis_start: datetime) -> Dict[str, float]:
        """
        Analyze portfolio positioning in the 30 days before a crisis
        
        This is the MOST CRITICAL metric - did the system de-risk before the crash?
        """
        
        pre_crisis_end = crisis_start
        pre_crisis_start = crisis_start - timedelta(days=self.pre_crisis_window)
        
        # Filter to pre-crisis period
        pre_crisis_data = portfolio_data[
            (portfolio_data['date'] >= pre_crisis_start) & 
            (portfolio_data['date'] < pre_crisis_end)
        ].copy()
        
        if pre_crisis_data.empty:
            return {
                'exposure_30d_before': 0.5,
                'risk_reduction_rate': 0.0,
                'defensive_positioning_score': 0.0,
                'anticipatory_de_risking': False,
                'cash_buildup_rate': 0.0
            }
        
        pre_crisis_data = pre_crisis_data.sort_values('date')
        
        # Calculate exposure trend
        if 'total_exposure' in pre_crisis_data.columns:
            exposures = pre_crisis_data['total_exposure'].values
        else:
            # Fallback: calculate from position weights
            exposures = pre_crisis_data.get('gross_exposure', [0.5] * len(pre_crisis_data))
        
        # Risk reduction rate (negative = reducing risk)
        if len(exposures) > 1:
            risk_reduction_rate = (exposures[0] - exposures[-1]) / exposures[0]
        else:
            risk_reduction_rate = 0.0
        
        # Final exposure level
        exposure_30d_before = exposures[-1] if len(exposures) > 0 else 0.5
        
        # Defensive positioning score
        defensive_score = self._calculate_defensive_positioning_score(pre_crisis_data)
        
        # Anticipatory de-risking detection
        anticipatory_de_risking = bool(
            exposure_30d_before < 0.7 and  # Less than 70% exposed
            risk_reduction_rate > 0.1      # Reduced risk by 10%+
        )
        
        # Cash buildup rate
        if 'cash_weight' in pre_crisis_data.columns:
            cash_weights = pre_crisis_data['cash_weight'].values
            if len(cash_weights) > 1:
                cash_buildup_rate = cash_weights[-1] - cash_weights[0]
            else:
                cash_buildup_rate = 0.0
        else:
            cash_buildup_rate = 1.0 - exposure_30d_before  # Assume rest is cash
        
        return {
            'exposure_30d_before': exposure_30d_before,
            'risk_reduction_rate': risk_reduction_rate,
            'defensive_positioning_score': defensive_score,
            'anticipatory_de_risking': anticipatory_de_risking,
            'cash_buildup_rate': cash_buildup_rate
        }
    
    def _calculate_defensive_positioning_score(self, portfolio_data: pd.DataFrame) -> float:
        """Calculate how defensively positioned the portfolio was"""
        
        if portfolio_data.empty:
            return 0.0
        
        defensive_score = 0.0
        
        # Check for defensive sector weights
        for sector in self.defensive_assets['sectors']:
            sector_col = f'{sector.lower().replace(" ", "_")}_weight'
            if sector_col in portfolio_data.columns:
                avg_weight = portfolio_data[sector_col].mean()
                defensive_score += avg_weight * 0.3  # 30% weight for sectors
        
        # Check for cash and bonds
        if 'cash_weight' in portfolio_data.columns:
            avg_cash = portfolio_data['cash_weight'].mean()
            defensive_score += avg_cash * 0.4  # 40% weight for cash
        
        if 'bond_weight' in portfolio_data.columns:
            avg_bonds = portfolio_data['bond_weight'].mean()
            defensive_score += avg_bonds * 0.3  # 30% weight for bonds
        
        # Penalize high-risk positions
        if 'high_beta_weight' in portfolio_data.columns:
            avg_high_beta = portfolio_data['high_beta_weight'].mean()
            defensive_score -= avg_high_beta * 0.2  # Penalty for high beta
        
        return np.clip(defensive_score, 0.0, 1.0)
    
    def analyze_crisis_performance(self, portfolio_data: pd.DataFrame, 
                                 crisis_period: Tuple[datetime, datetime],
                                 crisis_name: str) -> CrisisMetrics:
        """
        Analyze portfolio performance during a specific crisis period
        """
        
        crisis_start, crisis_end = crisis_period
        
        # Filter to crisis period
        crisis_data = portfolio_data[
            (portfolio_data['date'] >= crisis_start) & 
            (portfolio_data['date'] <= crisis_end)
        ].copy()
        
        if crisis_data.empty:
            # Return default metrics if no data
            return CrisisMetrics(
                crisis_name=crisis_name,
                period=crisis_period,
                max_drawdown=0.0,
                recovery_time_days=0,
                crisis_sharpe=0.0,
                total_return=0.0,
                exposure_30d_before=0.5,
                risk_reduction_rate=0.0,
                defensive_positioning_score=0.0,
                anticipatory_de_risking=False,
                emergency_triggers_activated=0,
                position_size_reductions=0,
                regime_adaptation_speed_days=0.0,
                survived_without_intervention=True,
                maximum_leverage_during_crisis=0.0,
                cash_reserves_maintained=0.5,
                volatility_during_crisis=0.0,
                correlation_with_market=0.0,
                downside_capture_ratio=0.0
            )
        
        crisis_data = crisis_data.sort_values('date')
        
        # Calculate performance metrics
        if 'daily_return' in crisis_data.columns:
            returns = crisis_data['daily_return'].values
        else:
            # Fallback: calculate from equity curve
            if 'equity' in crisis_data.columns:
                equity = crisis_data['equity'].values
                returns = np.diff(equity) / equity[:-1]
            else:
                returns = np.array([0.0])
        
        # Performance metrics
        total_return = np.prod(1 + returns) - 1 if len(returns) > 0 else 0.0
        
        if len(returns) > 1:
            volatility = np.std(returns) * np.sqrt(252)
            sharpe = np.mean(returns) * 252 / (volatility + 1e-8)
        else:
            volatility = 0.0
            sharpe = 0.0
        
        # Drawdown calculation
        if 'equity' in crisis_data.columns:
            equity = crisis_data['equity'].values
            peak = np.maximum.accumulate(equity)
            drawdown = (equity - peak) / peak
            max_drawdown = np.min(drawdown)
        else:
            max_drawdown = 0.0
        
        # Recovery time (simplified)
        recovery_time_days = max(0, (crisis_end - crisis_start).days)
        
        # Pre-crisis positioning analysis
        pre_crisis_metrics = self.analyze_pre_crisis_positioning(portfolio_data, crisis_start)
        
        # Risk management metrics
        emergency_triggers = self._count_emergency_triggers(crisis_data)
        position_reductions = self._count_position_reductions(crisis_data)
        
        # Survival metrics
        survived = max_drawdown > -0.50  # Survived if drawdown < 50%
        max_leverage = crisis_data.get('leverage', [0.0]).max() if 'leverage' in crisis_data.columns else 0.0
        final_cash = crisis_data['cash_weight'].iloc[-1] if 'cash_weight' in crisis_data.columns else 0.5
        
        # Market correlation (mock calculation)
        correlation_with_market = 0.7  # Would calculate vs market index
        downside_capture = abs(total_return) / 0.3 if total_return < 0 else 0.0  # vs 30% market decline
        
        return CrisisMetrics(
            crisis_name=crisis_name,
            period=crisis_period,
            max_drawdown=max_drawdown,
            recovery_time_days=recovery_time_days,
            crisis_sharpe=sharpe,
            total_return=total_return,
            exposure_30d_before=pre_crisis_metrics['exposure_30d_before'],
            risk_reduction_rate=pre_crisis_metrics['risk_reduction_rate'],
            defensive_positioning_score=pre_crisis_metrics['defensive_positioning_score'],
            anticipatory_de_risking=pre_crisis_metrics['anticipatory_de_risking'],
            emergency_triggers_activated=emergency_triggers,
            position_size_reductions=position_reductions,
            regime_adaptation_speed_days=7.0,  # Mock: 7 days to adapt
            survived_without_intervention=survived,
            maximum_leverage_during_crisis=max_leverage,
            cash_reserves_maintained=final_cash,
            volatility_during_crisis=volatility,
            correlation_with_market=correlation_with_market,
            downside_capture_ratio=downside_capture
        )
    
    def _count_emergency_triggers(self, crisis_data: pd.DataFrame) -> int:
        """Count emergency risk management triggers during crisis"""
        
        triggers = 0
        
        # Check for drawdown triggers
        if 'drawdown' in crisis_data.columns:
            max_dd = crisis_data['drawdown'].min()
            if max_dd < -0.15:  # 15% drawdown trigger
                triggers += 1
        
        # Check for volatility triggers
        if 'volatility' in crisis_data.columns:
            max_vol = crisis_data['volatility'].max()
            if max_vol > 0.30:  # 30% volatility trigger
                triggers += 1
        
        # Check for exposure reductions
        if 'total_exposure' in crisis_data.columns:
            exposures = crisis_data['total_exposure'].values
            if len(exposures) > 1:
                max_reduction = max(exposures) - min(exposures)
                if max_reduction > 0.20:  # 20% exposure reduction
                    triggers += 1
        
        return triggers
    
    def _count_position_reductions(self, crisis_data: pd.DataFrame) -> int:
        """Count position size reductions during crisis"""
        
        reductions = 0
        
        if 'total_exposure' in crisis_data.columns:
            exposures = crisis_data['total_exposure'].values
            
            # Count days where exposure was reduced
            for i in range(1, len(exposures)):
                if exposures[i] < exposures[i-1] * 0.95:  # 5% reduction
                    reductions += 1
        
        return reductions
    
    def validate_crisis_performance(self, portfolio_data: pd.DataFrame) -> CrisisReport:
        """
        Validate portfolio performance across all historical crises
        
        Args:
            portfolio_data: DataFrame with portfolio performance data
            
        Returns:
            Complete crisis validation report
        """
        
        print("🚨 CRISIS VALIDATOR - HISTORICAL CRISIS ANALYSIS")
        print("=" * 70)
        
        crisis_metrics = {}
        
        # Analyze each historical crisis
        for crisis_name, crisis_info in self.crisis_periods.items():
            print(f"\n📊 Analyzing {crisis_info['description']}")
            
            crisis_period = crisis_info['period']
            metrics = self.analyze_crisis_performance(
                portfolio_data, crisis_period, crisis_name
            )
            
            crisis_metrics[crisis_name] = metrics
            
            # Display key metrics
            print(f"   Max Drawdown: {metrics.max_drawdown:.1%}")
            print(f"   Crisis Sharpe: {metrics.crisis_sharpe:.2f}")
            print(f"   Pre-crisis Exposure: {metrics.exposure_30d_before:.1%}")
            print(f"   Anticipatory De-risking: {'✅' if metrics.anticipatory_de_risking else '❌'}")
            print(f"   Survived Crisis: {'✅' if metrics.survived_without_intervention else '❌'}")
        
        # Calculate overall scores
        overall_survival_score = self._calculate_survival_score(crisis_metrics)
        pre_crisis_score = self._calculate_pre_crisis_score(crisis_metrics)
        risk_mgmt_score = self._calculate_risk_management_score(crisis_metrics)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(crisis_metrics)
        
        print(f"\n🎯 CRISIS VALIDATION SUMMARY:")
        print(f"   Overall Survival Score: {overall_survival_score:.1%}")
        print(f"   Pre-Crisis Positioning: {pre_crisis_score:.1%}")
        print(f"   Risk Management: {risk_mgmt_score:.1%}")
        
        return CrisisReport(
            validation_timestamp=datetime.now(),
            total_crises_analyzed=len(crisis_metrics),
            crisis_metrics=crisis_metrics,
            overall_survival_score=overall_survival_score,
            pre_crisis_positioning_score=pre_crisis_score,
            risk_management_effectiveness=risk_mgmt_score,
            recommendations=recommendations
        )
    
    def _calculate_survival_score(self, crisis_metrics: Dict[str, CrisisMetrics]) -> float:
        """Calculate overall survival score across all crises"""
        
        if not crisis_metrics:
            return 0.0
        
        survival_scores = []
        
        for metrics in crisis_metrics.values():
            # More realistic survival components
            # Drawdown score: 0% DD = 1.0, -50% DD = 0.5, -100% DD = 0.0
            drawdown_score = max(0, 1 + metrics.max_drawdown)  # Linear penalty
            
            # Return score: 0% loss = 1.0, -50% loss = 0.5, -100% loss = 0.0
            return_score = max(0, 1 + metrics.total_return)
            
            # Survival flag: Binary bonus for surviving without intervention
            survival_flag = 0.5 if metrics.survived_without_intervention else 0.0
            
            # Weight the components: drawdown and returns are most important
            crisis_score = (drawdown_score * 0.4 + return_score * 0.4 + survival_flag * 0.2)
            survival_scores.append(crisis_score)
        
        return np.mean(survival_scores)
    
    def _calculate_pre_crisis_score(self, crisis_metrics: Dict[str, CrisisMetrics]) -> float:
        """Calculate pre-crisis positioning score"""
        
        if not crisis_metrics:
            return 0.0
        
        pre_crisis_scores = []
        
        for metrics in crisis_metrics.values():
            # Pre-crisis components
            exposure_score = 1.0 - metrics.exposure_30d_before  # Lower exposure = better
            reduction_score = min(1.0, metrics.risk_reduction_rate * 2)  # Risk reduction bonus
            defensive_score = metrics.defensive_positioning_score
            anticipatory_bonus = 0.2 if metrics.anticipatory_de_risking else 0.0
            
            crisis_score = (exposure_score + reduction_score + defensive_score + anticipatory_bonus) / 3.2
            pre_crisis_scores.append(crisis_score)
        
        return np.mean(pre_crisis_scores)
    
    def _calculate_risk_management_score(self, crisis_metrics: Dict[str, CrisisMetrics]) -> float:
        """Calculate risk management effectiveness score"""
        
        if not crisis_metrics:
            return 0.0
        
        risk_scores = []
        
        for metrics in crisis_metrics.values():
            # Risk management components
            trigger_score = min(1.0, metrics.emergency_triggers_activated / 3)  # Appropriate triggers
            reduction_score = min(1.0, metrics.position_size_reductions / 5)   # Position management
            cash_score = metrics.cash_reserves_maintained  # Cash preservation
            
            crisis_score = (trigger_score + reduction_score + cash_score) / 3
            risk_scores.append(crisis_score)
        
        return np.mean(risk_scores)
    
    def _generate_recommendations(self, crisis_metrics: Dict[str, CrisisMetrics]) -> List[str]:
        """Generate recommendations based on crisis analysis"""
        
        recommendations = []
        
        # Check for common issues
        high_drawdowns = [m for m in crisis_metrics.values() if m.max_drawdown < -0.30]
        poor_pre_crisis = [m for m in crisis_metrics.values() if not m.anticipatory_de_risking]
        low_survival = [m for m in crisis_metrics.values() if not m.survived_without_intervention]
        
        if high_drawdowns:
            recommendations.append(
                f"⚠️ High drawdowns detected in {len(high_drawdowns)} crises. "
                "Consider tighter risk controls and position sizing."
            )
        
        if poor_pre_crisis:
            recommendations.append(
                f"🔍 Poor pre-crisis positioning in {len(poor_pre_crisis)} crises. "
                "Enhance regime detection and early warning systems."
            )
        
        if low_survival:
            recommendations.append(
                f"🚨 Survival issues in {len(low_survival)} crises. "
                "Implement stronger emergency protocols and kill switches."
            )
        
        # Positive recommendations
        good_performers = [m for m in crisis_metrics.values() if m.anticipatory_de_risking and m.max_drawdown > -0.20]
        if good_performers:
            recommendations.append(
                f"✅ Strong performance in {len(good_performers)} crises. "
                "Current risk management approach is effective."
            )
        
        if not recommendations:
            recommendations.append("✅ No major issues detected. System shows good crisis resilience.")
        
        return recommendations

def main():
    """Demonstrate crisis validator"""
    
    print("🚨 CRISIS VALIDATOR - DEMONSTRATION")
    print("=" * 50)
    
    # Initialize validator
    validator = CrisisValidator()
    
    # Create mock portfolio data for testing
    dates = pd.date_range('2007-01-01', '2023-12-31', freq='D')
    
    # Simulate portfolio performance with crisis impacts
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.015, len(dates))  # Daily returns
    
    # Add crisis impacts
    for crisis_name, crisis_info in validator.crisis_periods.items():
        crisis_start, crisis_end = crisis_info['period']
        crisis_mask = (dates >= crisis_start) & (dates <= crisis_end)
        
        # Simulate crisis impact
        crisis_returns = np.random.normal(-0.002, 0.025, crisis_mask.sum())
        returns[crisis_mask] = crisis_returns
    
    # Build portfolio data
    equity = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    
    portfolio_data = pd.DataFrame({
        'date': dates,
        'daily_return': returns,
        'equity': equity,
        'drawdown': drawdown,
        'total_exposure': 0.8 + 0.2 * np.sin(np.arange(len(dates)) / 252 * 2 * np.pi),  # Varying exposure
        'cash_weight': 0.2 - 0.1 * np.sin(np.arange(len(dates)) / 252 * 2 * np.pi),     # Varying cash
        'volatility': pd.Series(returns).rolling(21).std() * np.sqrt(252)
    })
    
    # Run crisis validation
    crisis_report = validator.validate_crisis_performance(portfolio_data)
    
    print(f"\n📋 CRISIS VALIDATION COMPLETE")
    print(f"   Crises Analyzed: {crisis_report.total_crises_analyzed}")
    print(f"   Recommendations: {len(crisis_report.recommendations)}")
    
    for rec in crisis_report.recommendations:
        print(f"   {rec}")
    
    return crisis_report

if __name__ == "__main__":
    main()