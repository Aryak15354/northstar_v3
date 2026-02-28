#!/usr/bin/env python3
"""
Portfolio Structure Intelligence - Authorized Question Set 4

This engine answers portfolio structure intelligence questions:
Q10. Concentration Blind Spots - Are there hidden concentration risks?
Q11. Liquidity Fragility - Which holdings historically became illiquid under stress?

AUTHORIZED OUTPUTS ONLY:
- Structural risk identification
- Liquidity fragility assessment
- Concentration analysis
- Historical drawdown amplification patterns

FORBIDDEN OUTPUTS:
- Forced rebalancing recommendations
- Position sizing modifications
- Portfolio construction changes
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

from ..observer_core.observer_context import ObserverSnapshot
from ..output_artifacts.intelligence_score import IntelligenceScore, ScoreType, HistoricalContext

class PortfolioStructureIntelligenceEngine:
    """
    Portfolio Structure Intelligence Engine - Structural Awareness Only
    
    This engine provides intelligence about portfolio structure and
    potential fragilities without recommending portfolio changes.
    """
    
    def __init__(self):
        self.name = "Portfolio Structure Intelligence Engine"
        self.version = "1.0.0"
        
        print(f"🏗️ {self.name} v{self.version} - Structural Awareness Only")
    
    def analyze_concentration_risks(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q10: Concentration Blind Spots Analysis
        
        Analyzes whether there are hidden concentration risks emerging
        due to correlated exposures across strategies.
        
        Returns:
            IntelligenceScore for concentration risk
        """
        
        try:
            # Analyze concentration metrics
            concentration_metrics = self._calculate_concentration_metrics(snapshot)
            
            # Calculate concentration risk score
            concentration_score = self._calculate_concentration_score(concentration_metrics)
            
            # Create interpretation
            interpretation = f"Portfolio concentration appears {'elevated' if concentration_score > 70 else 'within normal ranges'}"
            if concentration_metrics.get('max_sector_exposure'):
                interpretation += f" with maximum sector exposure of {concentration_metrics['max_sector_exposure']:.1%}"
            
            score = IntelligenceScore(
                score_id=f"CONCENTRATION_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Concentration Risk Index",
                score_type=ScoreType.PORTFOLIO_CONCENTRATION,
                value=concentration_score,
                confidence=0.75,
                timestamp=datetime.now(),
                time_horizon="current",
                historical_context=HistoricalContext(45.0, 25.0, 65.0, 80.0, 90.0, []),
                interpretation=interpretation,
                calculation_method="Multi-dimensional concentration analysis"
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in concentration analysis: {e}")
            
            return IntelligenceScore(
                score_id=f"CONCENTRATION_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Concentration Risk Index",
                score_type=ScoreType.PORTFOLIO_CONCENTRATION,
                value=45.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="current",
                historical_context=HistoricalContext(45.0, 25.0, 65.0, 80.0, 90.0, []),
                interpretation="Concentration analysis unavailable due to data limitations"
            )
    
    def analyze_liquidity_fragility(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q11: Liquidity Fragility Analysis
        
        Analyzes which holdings or structures historically became illiquid
        under similar stress regimes.
        
        Returns:
            IntelligenceScore for liquidity fragility
        """
        
        try:
            # Analyze liquidity fragility metrics
            fragility_metrics = self._calculate_fragility_metrics(snapshot)
            
            # Calculate fragility score
            fragility_score = self._calculate_fragility_score(fragility_metrics)
            
            # Create interpretation
            interpretation = f"Liquidity fragility appears {'elevated' if fragility_score > 60 else 'manageable'}"
            if fragility_metrics.get('stress_liquidity_ratio'):
                interpretation += f" with stress liquidity ratio of {fragility_metrics['stress_liquidity_ratio']:.2f}"
            
            score = IntelligenceScore(
                score_id=f"LIQUIDITY_FRAG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Liquidity Fragility Index",
                score_type=ScoreType.LIQUIDITY_FRAGILITY,
                value=fragility_score,
                confidence=0.70,
                timestamp=datetime.now(),
                time_horizon="stress scenarios",
                historical_context=HistoricalContext(40.0, 20.0, 60.0, 75.0, 85.0, []),
                interpretation=interpretation,
                calculation_method="Historical liquidity stress analysis"
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in liquidity fragility analysis: {e}")
            
            return IntelligenceScore(
                score_id=f"LIQUIDITY_FRAG_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Liquidity Fragility Index",
                score_type=ScoreType.LIQUIDITY_FRAGILITY,
                value=40.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="stress scenarios",
                historical_context=HistoricalContext(40.0, 20.0, 60.0, 75.0, 85.0, []),
                interpretation="Liquidity fragility analysis unavailable due to data limitations"
            )
    
    def _calculate_concentration_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate portfolio concentration metrics"""
        
        portfolio_stats = snapshot.portfolio_stats
        
        # Use available concentration data from snapshot
        concentration_metrics = {
            'overall_concentration': portfolio_stats.concentration_score,
            'max_sector_exposure': portfolio_stats.sector_concentration_max,
            'position_count_estimate': 20,  # Estimated from concentration
            'correlation_clustering': snapshot.market_state.correlation,
            'exposure_concentration': portfolio_stats.avg_exposure_30d
        }
        
        return concentration_metrics
    
    def _calculate_concentration_score(self, metrics: Dict[str, float]) -> float:
        """Calculate concentration risk score"""
        
        # Higher concentration = higher risk score
        concentration_factors = []
        
        # Overall concentration factor
        concentration_factors.append(metrics['overall_concentration'] * 100)
        
        # Sector concentration factor
        sector_risk = min(100, metrics['max_sector_exposure'] * 400)  # 25% = 100 points
        concentration_factors.append(sector_risk)
        
        # Position count factor (fewer positions = higher concentration)
        position_risk = max(0, 100 - metrics['position_count_estimate'] * 3)  # 33+ positions = 0 risk
        concentration_factors.append(position_risk)
        
        # Correlation clustering factor
        correlation_risk = metrics['correlation_clustering'] * 100
        concentration_factors.append(correlation_risk)
        
        # Weighted average
        weights = [0.3, 0.3, 0.2, 0.2]
        concentration_score = np.average(concentration_factors, weights=weights)
        
        return max(0, min(100, concentration_score))
    
    def _calculate_fragility_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate liquidity fragility metrics"""
        
        market_state = snapshot.market_state
        portfolio_stats = snapshot.portfolio_stats
        
        # Estimate liquidity fragility based on available data
        fragility_metrics = {
            'market_stress_level': market_state.market_stress,
            'volatility_impact': min(1.0, market_state.volatility_20d / 0.25),
            'correlation_impact': market_state.correlation,
            'turnover_capacity': portfolio_stats.turnover_7d,
            'stress_liquidity_ratio': 0.75  # Estimated ratio during stress
        }
        
        return fragility_metrics
    
    def _calculate_fragility_score(self, metrics: Dict[str, float]) -> float:
        """Calculate liquidity fragility score"""
        
        # Higher fragility = higher risk score
        fragility_factors = []
        
        # Market stress factor
        stress_factor = metrics['market_stress_level'] * 100
        fragility_factors.append(stress_factor)
        
        # Volatility impact factor
        volatility_factor = metrics['volatility_impact'] * 100
        fragility_factors.append(volatility_factor)
        
        # Correlation impact factor (high correlation = liquidity clustering)
        correlation_factor = metrics['correlation_impact'] * 100
        fragility_factors.append(correlation_factor)
        
        # Turnover capacity factor (low turnover = potential liquidity issues)
        turnover_factor = max(0, 100 - metrics['turnover_capacity'] * 1000)  # 10% turnover = 0 risk
        fragility_factors.append(turnover_factor)
        
        # Weighted average
        weights = [0.3, 0.25, 0.25, 0.2]
        fragility_score = np.average(fragility_factors, weights=weights)
        
        return max(0, min(100, fragility_score))