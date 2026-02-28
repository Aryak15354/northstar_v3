#!/usr/bin/env python3
"""
💧 LIQUIDITY-BASED CASH MANAGER - TASK 11 ENHANCEMENT
Enhanced liquidity-based cash management and correlation stress response

This enhances Task 11 with comprehensive liquidity management:
- Dynamic cash allocation based on market liquidity
- Correlation stress detection and response
- Liquidity-adjusted position sizing
- Emergency cash reserves management
- Cross-asset correlation monitoring

Usage:
    from src.validation.liquidity_cash_manager import LiquidityCashManager
    
    manager = LiquidityCashManager()
    cash_allocation = manager.calculate_optimal_cash_allocation(market_data, portfolio)
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

import sys
))

@dataclass
class LiquidityMetrics:
    """Liquidity metrics for cash management"""
    market_liquidity_score: float      # 0-1, higher is more liquid
    bid_ask_spread_avg: float          # Average bid-ask spread
    volume_shock_indicator: float      # Volume shock level (0-1)
    correlation_stress_level: float    # Cross-asset correlation stress (0-1)
    liquidity_risk_score: float       # Overall liquidity risk (0-1)
    recommended_cash_pct: float        # Recommended cash percentage (0-1)
    emergency_reserves_pct: float      # Emergency reserves percentage (0-1)

@dataclass
class CorrelationStressMetrics:
    """Correlation stress metrics"""
    avg_correlation: float             # Average cross-asset correlation
    correlation_spike: float           # Recent correlation increase
    stress_level: str                  # LOW, MEDIUM, HIGH, CRITICAL
    affected_assets: List[str]         # Assets showing high correlation
    diversification_breakdown: float   # Diversification effectiveness (0-1)
    recommended_action: str            # Recommended portfolio action

class LiquidityRegime(Enum):
    """Market liquidity regimes"""
    ABUNDANT = "abundant"      # High liquidity, low spreads
    NORMAL = "normal"          # Normal market conditions
    STRESSED = "stressed"      # Reduced liquidity, wider spreads
    CRISIS = "crisis"          # Severe liquidity shortage

class LiquidityCashManager:
    """
    Liquidity-Based Cash Manager for Task 11 Enhancement
    
    Manages cash allocation based on:
    1. Market liquidity conditions
    2. Cross-asset correlation stress
    3. Portfolio liquidity needs
    4. Emergency reserve requirements
    5. Dynamic position sizing adjustments
    """
    
    def __init__(self):
        self.name = "Liquidity-Based Cash Manager"
        self.version = "1.0"
        
        # Cash allocation parameters
        self.base_cash_allocation = 0.05      # 5% base cash allocation
        self.max_cash_allocation = 0.30       # 30% maximum cash allocation
        self.emergency_reserve_min = 0.02     # 2% minimum emergency reserves
        self.emergency_reserve_max = 0.15     # 15% maximum emergency reserves
        
        # Liquidity thresholds
        self.liquidity_thresholds = {
            'abundant': {'min_score': 0.8, 'cash_pct': 0.05},
            'normal': {'min_score': 0.6, 'cash_pct': 0.10},
            'stressed': {'min_score': 0.4, 'cash_pct': 0.20},
            'crisis': {'min_score': 0.0, 'cash_pct': 0.30}
        }
        
        # Correlation stress thresholds
        self.correlation_thresholds = {
            'low': {'max_correlation': 0.3, 'cash_adjustment': 0.0},
            'medium': {'max_correlation': 0.5, 'cash_adjustment': 0.05},
            'high': {'max_correlation': 0.7, 'cash_adjustment': 0.10},
            'critical': {'max_correlation': 1.0, 'cash_adjustment': 0.15}
        }
        
        # Historical data for analysis
        self.liquidity_history = []
        self.correlation_history = []
        
        print("💧 Liquidity-Based Cash Manager initialized - Dynamic cash management active")
    
    def calculate_market_liquidity_score(self, market_data: Dict[str, Any]) -> float:
        """Calculate overall market liquidity score"""
        
        # Extract liquidity indicators
        bid_ask_spreads = market_data.get('bid_ask_spreads', {})
        volumes = market_data.get('volumes', {})
        volatility = market_data.get('volatility', 0.15)
        
        # Calculate average bid-ask spread
        avg_spread = np.mean(list(bid_ask_spreads.values())) if bid_ask_spreads else 0.002
        
        # Calculate volume shock (deviation from normal)
        avg_volume = np.mean(list(volumes.values())) if volumes else 1000000
        normal_volume = market_data.get('normal_volume', avg_volume)
        volume_shock = abs(avg_volume - normal_volume) / max(normal_volume, 1)
        
        # Liquidity score components
        spread_score = max(0, 1 - (avg_spread / 0.01))  # Normalize to 1% spread
        volume_score = max(0, 1 - volume_shock)
        volatility_score = max(0, 1 - (volatility / 0.30))  # Normalize to 30% volatility
        
        # Weighted liquidity score
        liquidity_score = (
            0.4 * spread_score +
            0.3 * volume_score +
            0.3 * volatility_score
        )
        
        return np.clip(liquidity_score, 0, 1)
    
    def detect_correlation_stress(self, returns_data: pd.DataFrame, 
                                lookback_days: int = 60) -> CorrelationStressMetrics:
        """Detect correlation stress across assets"""
        
        if returns_data.empty or len(returns_data.columns) < 2:
            return CorrelationStressMetrics(
                avg_correlation=0.0,
                correlation_spike=0.0,
                stress_level="LOW",
                affected_assets=[],
                diversification_breakdown=0.0,
                recommended_action="MAINTAIN"
            )
        
        # Calculate recent correlation matrix
        recent_returns = returns_data.tail(lookback_days)
        correlation_matrix = recent_returns.corr()
        
        # Calculate average correlation (excluding diagonal)
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
        correlations = correlation_matrix.where(mask).stack()
        # Filter out NaN values and ensure we have valid correlations
        valid_correlations = correlations.dropna()
        avg_correlation = valid_correlations.mean() if len(valid_correlations) > 0 else 0.0
        
        # Ensure correlation is in valid range
        avg_correlation = np.clip(avg_correlation, -1.0, 1.0)
        
        # Calculate historical baseline
        if len(returns_data) > lookback_days * 2:
            historical_returns = returns_data.iloc[:-lookback_days]
            historical_corr = historical_returns.corr()
            historical_avg = historical_corr.where(mask).stack().mean()
            correlation_spike = avg_correlation - historical_avg
        else:
            correlation_spike = 0.0
        
        # Identify highly correlated assets
        high_corr_threshold = 0.7
        affected_assets = []
        
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                if abs(correlation_matrix.iloc[i, j]) > high_corr_threshold:
                    affected_assets.extend([
                        correlation_matrix.columns[i], 
                        correlation_matrix.columns[j]
                    ])
        
        affected_assets = list(set(affected_assets))
        
        # Determine stress level
        if avg_correlation >= 0.8:
            stress_level = "CRITICAL"
            recommended_action = "REDUCE_RISK"
        elif avg_correlation >= 0.6:
            stress_level = "HIGH"
            recommended_action = "INCREASE_CASH"
        elif avg_correlation >= 0.4:
            stress_level = "MEDIUM"
            recommended_action = "MONITOR"
        else:
            stress_level = "LOW"
            recommended_action = "MAINTAIN"
        
        # Calculate diversification breakdown
        max_possible_correlation = 1.0
        diversification_breakdown = max(0.0, avg_correlation / max_possible_correlation)
        
        return CorrelationStressMetrics(
            avg_correlation=avg_correlation,
            correlation_spike=correlation_spike,
            stress_level=stress_level,
            affected_assets=affected_assets,
            diversification_breakdown=diversification_breakdown,
            recommended_action=recommended_action
        )
    
    def determine_liquidity_regime(self, liquidity_score: float) -> LiquidityRegime:
        """Determine current liquidity regime"""
        
        if liquidity_score >= self.liquidity_thresholds['abundant']['min_score']:
            return LiquidityRegime.ABUNDANT
        elif liquidity_score >= self.liquidity_thresholds['normal']['min_score']:
            return LiquidityRegime.NORMAL
        elif liquidity_score >= self.liquidity_thresholds['stressed']['min_score']:
            return LiquidityRegime.STRESSED
        else:
            return LiquidityRegime.CRISIS
    
    def calculate_optimal_cash_allocation(self, market_data: Dict[str, Any], 
                                        portfolio_data: Dict[str, Any],
                                        returns_data: Optional[pd.DataFrame] = None) -> LiquidityMetrics:
        """Calculate optimal cash allocation based on liquidity and correlation stress"""
        
        # Calculate market liquidity score
        liquidity_score = self.calculate_market_liquidity_score(market_data)
        
        # Determine liquidity regime
        liquidity_regime = self.determine_liquidity_regime(liquidity_score)
        
        # Base cash allocation from regime
        base_cash_pct = self.liquidity_thresholds[liquidity_regime.value]['cash_pct']
        
        # Detect correlation stress
        correlation_stress = self.detect_correlation_stress(returns_data) if returns_data is not None else None
        
        # Adjust for correlation stress
        correlation_adjustment = 0.0
        if correlation_stress:
            for level, params in self.correlation_thresholds.items():
                if correlation_stress.avg_correlation <= params['max_correlation']:
                    correlation_adjustment = params['cash_adjustment']
                    break
        
        # Calculate portfolio-specific adjustments
        portfolio_adjustment = self._calculate_portfolio_adjustment(portfolio_data)
        
        # Total recommended cash allocation
        recommended_cash_pct = min(
            self.max_cash_allocation,
            base_cash_pct + correlation_adjustment + portfolio_adjustment
        )
        
        # Emergency reserves calculation
        emergency_reserves_pct = self._calculate_emergency_reserves(
            liquidity_score, correlation_stress
        )
        
        # Additional metrics
        bid_ask_spread_avg = np.mean(list(market_data.get('bid_ask_spreads', {}).values())) or 0.002
        volume_shock = self._calculate_volume_shock(market_data)
        correlation_stress_level = correlation_stress.diversification_breakdown if correlation_stress else 0.0
        
        # Overall liquidity risk score
        liquidity_risk_score = 1 - liquidity_score + correlation_stress_level
        liquidity_risk_score = np.clip(liquidity_risk_score, 0, 1)
        
        return LiquidityMetrics(
            market_liquidity_score=liquidity_score,
            bid_ask_spread_avg=bid_ask_spread_avg,
            volume_shock_indicator=volume_shock,
            correlation_stress_level=correlation_stress_level,
            liquidity_risk_score=liquidity_risk_score,
            recommended_cash_pct=recommended_cash_pct,
            emergency_reserves_pct=emergency_reserves_pct
        )
    
    def adjust_position_sizes_for_liquidity(self, target_positions: Dict[str, float],
                                          liquidity_metrics: LiquidityMetrics,
                                          asset_liquidity: Dict[str, float]) -> Dict[str, float]:
        """Adjust position sizes based on individual asset liquidity"""
        
        adjusted_positions = {}
        total_adjustment = 0.0
        
        for asset, target_size in target_positions.items():
            asset_liq = asset_liquidity.get(asset, 0.5)  # Default to medium liquidity
            
            # Reduce position size for illiquid assets
            if asset_liq < 0.3:  # Low liquidity
                adjustment_factor = 0.5
            elif asset_liq < 0.6:  # Medium liquidity
                adjustment_factor = 0.8
            else:  # High liquidity
                adjustment_factor = 1.0
            
            # Additional adjustment for overall market liquidity stress
            if liquidity_metrics.liquidity_risk_score > 0.7:
                adjustment_factor *= 0.8
            
            adjusted_size = target_size * adjustment_factor
            adjusted_positions[asset] = adjusted_size
            total_adjustment += (target_size - adjusted_size)
        
        # Allocate freed-up capital to cash
        cash_increase = total_adjustment
        
        return adjusted_positions, cash_increase
    
    def generate_liquidity_alerts(self, liquidity_metrics: LiquidityMetrics,
                                correlation_stress: Optional[CorrelationStressMetrics] = None) -> List[Dict[str, Any]]:
        """Generate liquidity-based alerts and recommendations"""
        
        alerts = []
        
        # Liquidity risk alerts
        if liquidity_metrics.liquidity_risk_score > 0.8:
            alerts.append({
                'type': 'CRITICAL',
                'message': f'Critical liquidity risk detected ({liquidity_metrics.liquidity_risk_score:.1%})',
                'recommendation': f'Increase cash to {liquidity_metrics.recommended_cash_pct:.1%}',
                'urgency': 'HIGH'
            })
        elif liquidity_metrics.liquidity_risk_score > 0.6:
            alerts.append({
                'type': 'WARNING',
                'message': f'Elevated liquidity risk ({liquidity_metrics.liquidity_risk_score:.1%})',
                'recommendation': f'Consider increasing cash allocation',
                'urgency': 'MEDIUM'
            })
        
        # Volume shock alerts
        if liquidity_metrics.volume_shock_indicator > 0.5:
            alerts.append({
                'type': 'WARNING',
                'message': f'Volume shock detected ({liquidity_metrics.volume_shock_indicator:.1%})',
                'recommendation': 'Monitor position sizing and execution',
                'urgency': 'MEDIUM'
            })
        
        # Correlation stress alerts
        if correlation_stress and correlation_stress.stress_level in ['HIGH', 'CRITICAL']:
            alerts.append({
                'type': 'WARNING' if correlation_stress.stress_level == 'HIGH' else 'CRITICAL',
                'message': f'{correlation_stress.stress_level} correlation stress detected',
                'recommendation': correlation_stress.recommended_action,
                'urgency': 'HIGH' if correlation_stress.stress_level == 'CRITICAL' else 'MEDIUM',
                'affected_assets': correlation_stress.affected_assets
            })
        
        return alerts
    
    def _calculate_portfolio_adjustment(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate portfolio-specific cash adjustment"""
        
        # Portfolio concentration adjustment
        concentration = portfolio_data.get('concentration_score', 0.5)
        concentration_adjustment = max(0, (concentration - 0.7) * 0.1)
        
        # Portfolio volatility adjustment
        portfolio_vol = portfolio_data.get('volatility', 0.15)
        volatility_adjustment = max(0, (portfolio_vol - 0.20) * 0.2)
        
        # Leverage adjustment
        leverage = portfolio_data.get('leverage', 1.0)
        leverage_adjustment = max(0, (leverage - 1.5) * 0.05)
        
        return concentration_adjustment + volatility_adjustment + leverage_adjustment
    
    def _calculate_emergency_reserves(self, liquidity_score: float,
                                    correlation_stress: Optional[CorrelationStressMetrics]) -> float:
        """Calculate required emergency reserves"""
        
        base_reserves = self.emergency_reserve_min
        
        # Adjust for liquidity conditions
        liquidity_adjustment = (1 - liquidity_score) * 0.10
        
        # Adjust for correlation stress
        correlation_adjustment = 0.0
        if correlation_stress and correlation_stress.stress_level in ['HIGH', 'CRITICAL']:
            correlation_adjustment = 0.05
        
        total_reserves = min(
            self.emergency_reserve_max,
            base_reserves + liquidity_adjustment + correlation_adjustment
        )
        
        return total_reserves
    
    def _calculate_volume_shock(self, market_data: Dict[str, Any]) -> float:
        """Calculate volume shock indicator"""
        
        volumes = market_data.get('volumes', {})
        if not volumes:
            return 0.0
        
        current_volume = np.mean(list(volumes.values()))
        normal_volume = market_data.get('normal_volume', current_volume)
        
        if normal_volume == 0:
            return 0.0
        
        volume_shock = abs(current_volume - normal_volume) / normal_volume
        return min(1.0, volume_shock)


def main():
    """Demonstrate Liquidity-Based Cash Manager"""
    
    print("💧 LIQUIDITY-BASED CASH MANAGER - TASK 11 ENHANCEMENT")
    print("=" * 70)
    
    manager = LiquidityCashManager()
    
    # Mock market data
    market_data = {
        'bid_ask_spreads': {'STOCK1': 0.001, 'STOCK2': 0.002, 'STOCK3': 0.005},
        'volumes': {'STOCK1': 1000000, 'STOCK2': 500000, 'STOCK3': 100000},
        'volatility': 0.20,
        'normal_volume': 600000
    }
    
    # Mock portfolio data
    portfolio_data = {
        'concentration_score': 0.6,
        'volatility': 0.18,
        'leverage': 1.2
    }
    
    # Mock returns data
    returns_data = pd.DataFrame({
        'STOCK1': np.random.normal(0.001, 0.02, 100),
        'STOCK2': np.random.normal(0.0005, 0.015, 100),
        'STOCK3': np.random.normal(0.0008, 0.025, 100)
    })
    
    # Calculate optimal cash allocation
    liquidity_metrics = manager.calculate_optimal_cash_allocation(
        market_data, portfolio_data, returns_data
    )
    
    # Detect correlation stress
    correlation_stress = manager.detect_correlation_stress(returns_data)
    
    # Generate alerts
    alerts = manager.generate_liquidity_alerts(liquidity_metrics, correlation_stress)
    
    print(f"\n📊 LIQUIDITY ANALYSIS RESULTS")
    print("=" * 40)
    print(f"   Market liquidity score: {liquidity_metrics.market_liquidity_score:.3f}")
    print(f"   Liquidity risk score: {liquidity_metrics.liquidity_risk_score:.3f}")
    print(f"   Recommended cash allocation: {liquidity_metrics.recommended_cash_pct:.1%}")
    print(f"   Emergency reserves: {liquidity_metrics.emergency_reserves_pct:.1%}")
    
    print(f"\n🔗 CORRELATION STRESS ANALYSIS")
    print("=" * 40)
    print(f"   Average correlation: {correlation_stress.avg_correlation:.3f}")
    print(f"   Stress level: {correlation_stress.stress_level}")
    print(f"   Diversification breakdown: {correlation_stress.diversification_breakdown:.1%}")
    print(f"   Recommended action: {correlation_stress.recommended_action}")
    
    if alerts:
        print(f"\n⚠️ LIQUIDITY ALERTS")
        print("=" * 40)
        for alert in alerts:
            print(f"   {alert['type']}: {alert['message']}")
            print(f"      → {alert['recommendation']}")
    
    print(f"\n✅ Liquidity-Based Cash Manager demonstration complete")


if __name__ == "__main__":
    main()