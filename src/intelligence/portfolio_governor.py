#!/usr/bin/env python3
"""
🏛️ PORTFOLIO GOVERNOR - LAYER 6
Portfolio-aware position sizing with concentration controls and liquidity constraints

This implements Layer 6 of the institutional alpha engine:
- Signal strength adjustment by current portfolio weights
- Concentration controls (individual and sector limits)
- Correlation-based position sizing
- Liquidity constraints for low-volume stocks
- Risk budget management with proportional scaling
- Turnover threshold controls

Key Features:
1. Portfolio-aware signal adjustments
2. Individual and sector concentration limits
3. Liquidity-based position sizing
4. Risk budget enforcement
5. Turnover controls
6. Correlation penalty system

Usage:
    try:
    from intelligence.portfolio_governor import PortfolioGovernor
except ImportError:
    from PortfolioGovernor import PortfolioGovernor
    
    governor = PortfolioGovernor()
    positions = governor.compute_portfolio_aware_positions(allocations, signals, market_data, current_time)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import json

warnings.filterwarnings('ignore')

import sys
@dataclass
class PortfolioPosition:
    """Portfolio position with all adjustments applied"""
    symbol: str
    current_weight: float        # [0, 1] current portfolio weight
    target_weight: float         # [0, 1] target portfolio weight from signals
    signal_strength: float       # [-3, +3] raw signal strength
    adjusted_strength: float     # [-3, +3] portfolio-adjusted signal strength
    sector: str                  # Sector classification
    market_cap: float           # Market capitalization
    avg_daily_volume: float     # Average daily trading volume
    correlation_penalty: float   # [0, 1] correlation-based penalty
    liquidity_penalty: float    # [0, 1] liquidity-based penalty
    concentration_penalty: float # [0, 1] concentration-based penalty
    final_position_size: float   # [0, 1] final position size after all adjustments
    metadata: Dict[str, Any]

@dataclass
class PortfolioConstraints:
    """Portfolio-level constraints and limits"""
    max_individual_weight: float = 0.05    # 5% max individual position
    max_sector_weight: float = 0.25        # 25% max sector concentration
    max_correlation_threshold: float = 0.7  # 0.7 correlation threshold
    min_daily_volume: float = 1e6         # $1M minimum daily volume
    max_monthly_turnover: float = 0.5      # 50% max monthly turnover
    risk_budget_limit: float = 0.15        # 15% max portfolio risk
    cash_buffer: float = 0.05              # 5% minimum cash buffer
    
    # Penalty parameters
    concentration_penalty_rate: float = 0.5   # 50% penalty for concentration excess
    sector_penalty_rate: float = 0.25         # 25% penalty for sector excess
    correlation_penalty_rate: float = 0.3     # 30% penalty for high correlation
    liquidity_penalty_rate: float = 1.0       # 100% penalty for liquidity deficit

class PortfolioGovernor:
    """
    Portfolio Governor - Institutional-grade position sizing
    
    Transforms capital allocations and specialist signals into risk-adjusted
    portfolio positions with comprehensive constraints and controls.
    
    Core Functions:
    1. Portfolio-aware signal adjustments (reduce strength by current weight)
    2. Concentration controls (individual 5%, sector 25% limits)
    3. Correlation-based position sizing (>0.7 threshold)
    4. Liquidity constraints (minimum volume requirements)
    5. Risk budget management (proportional scaling)
    6. Turnover controls (monthly limits)
    """
    
    def __init__(self, constraints: Optional[PortfolioConstraints] = None):
        self.constraints = constraints or PortfolioConstraints()
        
        # Portfolio state tracking
        self.current_positions = {}      # symbol -> current weight
        self.sector_weights = {}         # sector -> total weight
        self.correlation_matrix = {}     # symbol pairs -> correlation
        self.position_history = []       # historical positions
        self.turnover_history = []       # historical turnover
        
        # Risk tracking
        self.risk_budget_used = 0.0
        self.volatility_estimates = {}   # symbol -> volatility estimate
        
        print("🏛️ Portfolio Governor initialized")
        print(f"   Max individual: {self.constraints.max_individual_weight:.1%}")
        print(f"   Max sector: {self.constraints.max_sector_weight:.1%}")
        print(f"   Min daily volume: ${self.constraints.min_daily_volume:,.0f}")
        print(f"   Max monthly turnover: {self.constraints.max_monthly_turnover:.1%}")
    
    def compute_portfolio_aware_positions(self, 
                                        capital_allocations: List,  # CapitalAllocation objects
                                        specialist_signals: Dict[str, List],  # SpecialistSignal objects
                                        market_data: Dict[str, Dict[str, float]],
                                        current_time: datetime) -> List[PortfolioPosition]:
        """
        Main portfolio-aware position sizing function
        
        Transforms capital allocations and signals into final portfolio positions
        with all constraints and adjustments applied.
        """
        
        print(f"🏛️ Portfolio Governor - Computing positions for {current_time.date()}")
        
        # Step 1: Generate raw positions from capital allocations and signals
        raw_positions = self._generate_raw_positions(
            capital_allocations, specialist_signals, market_data
        )
        
        # Step 2: Apply portfolio-aware adjustments
        portfolio_adjusted = self._apply_portfolio_awareness(raw_positions)
        
        # Step 3: Apply concentration controls
        concentration_controlled = self._apply_concentration_controls(portfolio_adjusted)
        
        # Step 4: Apply correlation adjustments
        correlation_adjusted = self._apply_correlation_adjustments(concentration_controlled)
        
        # Step 5: Apply liquidity constraints
        liquidity_constrained = self._apply_liquidity_constraints(
            correlation_adjusted, market_data
        )
        
        # Step 6: Apply risk budget management
        risk_managed = self._apply_risk_budget_management(liquidity_constrained)
        
        # Step 7: Apply turnover controls
        final_positions = self._apply_turnover_controls(risk_managed, current_time)
        
        # Step 8: Update portfolio state
        self._update_portfolio_state(final_positions, current_time)
        
        # Step 9: Validate final positions
        self._validate_final_positions(final_positions)
        
        print(f"   Final positions: {len(final_positions)} securities")
        print(f"   Total weight: {sum(p.final_position_size for p in final_positions):.1%}")
        print(f"   Largest position: {max(p.final_position_size for p in final_positions):.1%}")
        
        return final_positions
    
    def _generate_raw_positions(self, 
                              capital_allocations: List,
                              specialist_signals: Dict[str, List],
                              market_data: Dict[str, Dict[str, float]]) -> List[PortfolioPosition]:
        """Generate raw positions from capital allocations and specialist signals"""
        
        raw_positions = []
        
        # Create allocation weight mapping
        allocation_weights = {alloc.specialist_name: alloc.allocation_weight 
                            for alloc in capital_allocations}
        
        print(f"   Allocation weights: {allocation_weights}")
        
        # Process each specialist's signals
        for specialist_name, signals in specialist_signals.items():
            allocation_weight = allocation_weights.get(specialist_name, 0.0)
            
            print(f"   Processing {specialist_name}: {len(signals)} signals, weight: {allocation_weight:.1%}")
            
            if allocation_weight == 0.0:
                continue
            
            for signal in signals:
                symbol = signal.symbol
                
                # Get market data
                symbol_data = market_data.get(symbol, {})
                sector = symbol_data.get('sector', 'Unknown')
                market_cap = symbol_data.get('market_cap', 1e9)
                avg_volume = symbol_data.get('avg_daily_volume', 1e6)
                
                # Calculate raw position size
                # Signal strength * allocation weight * base sizing factor
                raw_strength = signal.signal_strength
                weighted_strength = raw_strength * allocation_weight
                
                # Convert to position size (5% per unit of weighted strength)
                base_position_size = max(0, weighted_strength * 0.05)
                
                print(f"     {symbol}: signal={raw_strength:.3f}, weighted={weighted_strength:.3f}, size={base_position_size:.3f}")
                
                # Create position object
                position = PortfolioPosition(
                    symbol=symbol,
                    current_weight=self.current_positions.get(symbol, 0.0),
                    target_weight=base_position_size,
                    signal_strength=raw_strength,
                    adjusted_strength=weighted_strength,
                    sector=sector,
                    market_cap=market_cap,
                    avg_daily_volume=avg_volume,
                    correlation_penalty=0.0,
                    liquidity_penalty=0.0,
                    concentration_penalty=0.0,
                    final_position_size=base_position_size,
                    metadata={
                        'specialist': specialist_name,
                        'allocation_weight': allocation_weight,
                        'signal_confidence': signal.confidence,
                        'regime_fit': signal.regime_fit
                    }
                )
                
                raw_positions.append(position)
        
        print(f"   Generated {len(raw_positions)} raw positions")
        return raw_positions
    
    def _apply_portfolio_awareness(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply portfolio-aware adjustments: signal strength / current portfolio weight"""
        
        adjusted_positions = []
        
        for position in positions:
            current_weight = position.current_weight
            
            # Portfolio awareness: reduce signal strength by current weight
            if current_weight > 0:
                # Stronger penalty for larger existing positions
                portfolio_penalty = current_weight * 10  # 10x penalty factor
                adjustment_factor = 1.0 / (1.0 + portfolio_penalty)
                adjusted_strength = position.adjusted_strength * adjustment_factor
            else:
                adjusted_strength = position.adjusted_strength
            
            # Recalculate position size with adjusted strength
            adjusted_size = max(0, adjusted_strength * 0.05)
            
            adjusted_position = PortfolioPosition(
                symbol=position.symbol,
                current_weight=position.current_weight,
                target_weight=position.target_weight,
                signal_strength=position.signal_strength,
                adjusted_strength=adjusted_strength,
                sector=position.sector,
                market_cap=position.market_cap,
                avg_daily_volume=position.avg_daily_volume,
                correlation_penalty=position.correlation_penalty,
                liquidity_penalty=position.liquidity_penalty,
                concentration_penalty=position.concentration_penalty,
                final_position_size=adjusted_size,
                metadata={**position.metadata, 'portfolio_adjusted': True}
            )
            
            adjusted_positions.append(adjusted_position)
        
        return adjusted_positions
    
    def _apply_concentration_controls(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply concentration controls: individual and sector limits"""
        
        controlled_positions = []
        
        # Calculate sector exposures
        sector_exposures = {}
        for position in positions:
            sector = position.sector
            sector_exposures[sector] = sector_exposures.get(sector, 0.0) + position.final_position_size
        
        for position in positions:
            concentration_penalty = 0.0
            
            # Individual concentration penalty
            if position.final_position_size > self.constraints.max_individual_weight:
                excess = position.final_position_size - self.constraints.max_individual_weight
                individual_penalty = (excess / self.constraints.max_individual_weight) * self.constraints.concentration_penalty_rate
                concentration_penalty += individual_penalty
            
            # Sector concentration penalty
            sector_exposure = sector_exposures.get(position.sector, 0.0)
            if sector_exposure > self.constraints.max_sector_weight:
                sector_excess = sector_exposure - self.constraints.max_sector_weight
                sector_penalty = (sector_excess / self.constraints.max_sector_weight) * self.constraints.sector_penalty_rate
                concentration_penalty += sector_penalty
            
            # Apply concentration penalty
            penalty_factor = 1.0 / (1.0 + concentration_penalty)
            adjusted_size = position.final_position_size * penalty_factor
            
            # Hard cap at individual limit
            final_size = min(adjusted_size, self.constraints.max_individual_weight)
            
            controlled_position = PortfolioPosition(
                symbol=position.symbol,
                current_weight=position.current_weight,
                target_weight=position.target_weight,
                signal_strength=position.signal_strength,
                adjusted_strength=position.adjusted_strength,
                sector=position.sector,
                market_cap=position.market_cap,
                avg_daily_volume=position.avg_daily_volume,
                correlation_penalty=position.correlation_penalty,
                liquidity_penalty=position.liquidity_penalty,
                concentration_penalty=concentration_penalty,
                final_position_size=final_size,
                metadata={**position.metadata, 'concentration_controlled': True}
            )
            
            controlled_positions.append(controlled_position)
        
        return controlled_positions
    
    def _apply_correlation_adjustments(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply correlation-based position sizing adjustments"""
        
        adjusted_positions = []
        
        for position in positions:
            correlation_penalty = 0.0
            
            # Check correlation with existing positions
            for other_symbol, other_weight in self.current_positions.items():
                if other_symbol != position.symbol and other_weight > 0.01:  # 1% threshold
                    
                    # Get correlation (mock implementation - would use real correlation matrix)
                    correlation = self._get_correlation(position.symbol, other_symbol)
                    
                    if correlation > self.constraints.max_correlation_threshold:
                        excess_correlation = correlation - self.constraints.max_correlation_threshold
                        corr_penalty = excess_correlation * other_weight * self.constraints.correlation_penalty_rate
                        correlation_penalty += corr_penalty
            
            # Apply correlation penalty
            penalty_factor = 1.0 / (1.0 + correlation_penalty)
            adjusted_size = position.final_position_size * penalty_factor
            
            adjusted_position = PortfolioPosition(
                symbol=position.symbol,
                current_weight=position.current_weight,
                target_weight=position.target_weight,
                signal_strength=position.signal_strength,
                adjusted_strength=position.adjusted_strength,
                sector=position.sector,
                market_cap=position.market_cap,
                avg_daily_volume=position.avg_daily_volume,
                correlation_penalty=correlation_penalty,
                liquidity_penalty=position.liquidity_penalty,
                concentration_penalty=position.concentration_penalty,
                final_position_size=adjusted_size,
                metadata={**position.metadata, 'correlation_adjusted': True}
            )
            
            adjusted_positions.append(adjusted_position)
        
        return adjusted_positions
    
    def _apply_liquidity_constraints(self, positions: List[PortfolioPosition], 
                                   market_data: Dict[str, Dict[str, float]]) -> List[PortfolioPosition]:
        """Apply liquidity constraints for low-volume stocks"""
        
        constrained_positions = []
        
        for position in positions:
            liquidity_penalty = 0.0
            
            # Check volume constraint
            daily_volume = position.avg_daily_volume
            if daily_volume < self.constraints.min_daily_volume:
                volume_deficit = (self.constraints.min_daily_volume - daily_volume) / self.constraints.min_daily_volume
                liquidity_penalty = volume_deficit * self.constraints.liquidity_penalty_rate
            
            # Apply liquidity penalty
            penalty_factor = 1.0 / (1.0 + liquidity_penalty)
            adjusted_size = position.final_position_size * penalty_factor
            
            constrained_position = PortfolioPosition(
                symbol=position.symbol,
                current_weight=position.current_weight,
                target_weight=position.target_weight,
                signal_strength=position.signal_strength,
                adjusted_strength=position.adjusted_strength,
                sector=position.sector,
                market_cap=position.market_cap,
                avg_daily_volume=position.avg_daily_volume,
                correlation_penalty=position.correlation_penalty,
                liquidity_penalty=liquidity_penalty,
                concentration_penalty=position.concentration_penalty,
                final_position_size=adjusted_size,
                metadata={**position.metadata, 'liquidity_constrained': True}
            )
            
            constrained_positions.append(constrained_position)
        
        return constrained_positions
    
    def _apply_risk_budget_management(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply risk budget management with proportional scaling"""
        
        # Calculate total portfolio risk
        total_risk = 0.0
        for position in positions:
            # Estimate volatility based on market cap (smaller = more volatile)
            volatility = self._estimate_volatility(position.symbol, position.market_cap)
            position_risk = position.final_position_size * volatility
            total_risk += position_risk
        
        # Check if risk budget exceeded
        if total_risk <= self.constraints.risk_budget_limit:
            return positions  # No scaling needed
        
        # Calculate scale factor
        scale_factor = self.constraints.risk_budget_limit / total_risk
        
        # Apply proportional scaling
        scaled_positions = []
        for position in positions:
            scaled_size = position.final_position_size * scale_factor
            
            scaled_position = PortfolioPosition(
                symbol=position.symbol,
                current_weight=position.current_weight,
                target_weight=position.target_weight,
                signal_strength=position.signal_strength,
                adjusted_strength=position.adjusted_strength,
                sector=position.sector,
                market_cap=position.market_cap,
                avg_daily_volume=position.avg_daily_volume,
                correlation_penalty=position.correlation_penalty,
                liquidity_penalty=position.liquidity_penalty,
                concentration_penalty=position.concentration_penalty,
                final_position_size=scaled_size,
                metadata={
                    **position.metadata, 
                    'risk_scaled': True, 
                    'scale_factor': scale_factor,
                    'original_risk': total_risk,
                    'target_risk': self.constraints.risk_budget_limit
                }
            )
            
            scaled_positions.append(scaled_position)
        
        print(f"   Risk budget scaling applied: {scale_factor:.3f} (risk: {total_risk:.1%} → {self.constraints.risk_budget_limit:.1%})")
        return scaled_positions
    
    def _apply_turnover_controls(self, positions: List[PortfolioPosition], 
                               current_time: datetime) -> List[PortfolioPosition]:
        """Apply turnover threshold adjustments"""
        
        # Calculate expected turnover
        total_turnover = 0.0
        for position in positions:
            position_change = abs(position.final_position_size - position.current_weight)
            total_turnover += position_change
        
        # Check if turnover exceeds limit
        if total_turnover <= self.constraints.max_monthly_turnover:
            return positions  # No turnover control needed
        
        # Calculate turnover scale factor
        turnover_scale = self.constraints.max_monthly_turnover / total_turnover
        
        # Apply turnover scaling to position changes only
        controlled_positions = []
        for position in positions:
            position_change = position.final_position_size - position.current_weight
            scaled_change = position_change * turnover_scale
            controlled_size = position.current_weight + scaled_change
            
            controlled_position = PortfolioPosition(
                symbol=position.symbol,
                current_weight=position.current_weight,
                target_weight=position.target_weight,
                signal_strength=position.signal_strength,
                adjusted_strength=position.adjusted_strength,
                sector=position.sector,
                market_cap=position.market_cap,
                avg_daily_volume=position.avg_daily_volume,
                correlation_penalty=position.correlation_penalty,
                liquidity_penalty=position.liquidity_penalty,
                concentration_penalty=position.concentration_penalty,
                final_position_size=max(0, controlled_size),
                metadata={
                    **position.metadata, 
                    'turnover_controlled': True, 
                    'turnover_scale': turnover_scale,
                    'original_turnover': total_turnover
                }
            )
            
            controlled_positions.append(controlled_position)
        
        print(f"   Turnover control applied: {turnover_scale:.3f} (turnover: {total_turnover:.1%} → {self.constraints.max_monthly_turnover:.1%})")
        return controlled_positions
    
    def _update_portfolio_state(self, positions: List[PortfolioPosition], current_time: datetime):
        """Update internal portfolio state tracking"""
        
        # Update current positions
        new_positions = {}
        new_sector_weights = {}
        
        for position in positions:
            new_positions[position.symbol] = position.final_position_size
            
            sector = position.sector
            new_sector_weights[sector] = new_sector_weights.get(sector, 0.0) + position.final_position_size
        
        # Calculate turnover
        total_turnover = 0.0
        for symbol, new_weight in new_positions.items():
            old_weight = self.current_positions.get(symbol, 0.0)
            total_turnover += abs(new_weight - old_weight)
        
        # Update state
        self.current_positions = new_positions
        self.sector_weights = new_sector_weights
        
        # Store history
        self.position_history.append({
            'timestamp': current_time,
            'positions': new_positions.copy(),
            'sector_weights': new_sector_weights.copy(),
            'total_turnover': total_turnover,
            'num_positions': len(new_positions),
            'total_weight': sum(new_positions.values())
        })
        
        self.turnover_history.append(total_turnover)
        
        # Keep only recent history (1 year)
        if len(self.position_history) > 252:
            self.position_history = self.position_history[-252:]
        if len(self.turnover_history) > 252:
            self.turnover_history = self.turnover_history[-252:]
    
    def _validate_final_positions(self, positions: List[PortfolioPosition]):
        """Validate final positions meet all constraints"""
        
        # Check individual limits
        for position in positions:
            if position.final_position_size > self.constraints.max_individual_weight + 1e-6:
                print(f"⚠️ Individual limit violation: {position.symbol} = {position.final_position_size:.1%}")
        
        # Check sector limits
        sector_totals = {}
        for position in positions:
            sector = position.sector
            sector_totals[sector] = sector_totals.get(sector, 0.0) + position.final_position_size
        
        for sector, total in sector_totals.items():
            if total > self.constraints.max_sector_weight + 1e-6:
                print(f"⚠️ Sector limit violation: {sector} = {total:.1%}")
        
        # Check total weight
        total_weight = sum(p.final_position_size for p in positions)
        if total_weight > 1.0 + 1e-6:
            print(f"⚠️ Total weight > 100%: {total_weight:.1%}")
    
    def _get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols (mock implementation)"""
        
        # Mock correlation based on sector similarity
        sector1 = self._get_sector(symbol1)
        sector2 = self._get_sector(symbol2)
        
        if sector1 == sector2:
            return 0.6  # High correlation within sector
        else:
            return 0.2  # Low correlation across sectors
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for symbol (mock implementation)"""
        
        sector_map = {
            'RELIANCE.NS': 'Energy',
            'TCS.NS': 'Technology',
            'INFY.NS': 'Technology',
            'HDFCBANK.NS': 'Financials',
            'ICICIBANK.NS': 'Financials',
            'WIPRO.NS': 'Technology',
            'BHARTIARTL.NS': 'Telecom',
            'ITC.NS': 'Consumer',
            'HINDUNILVR.NS': 'Consumer',
            'KOTAKBANK.NS': 'Financials'
        }
        
        return sector_map.get(symbol, 'Unknown')
    
    def _estimate_volatility(self, symbol: str, market_cap: float) -> float:
        """Estimate volatility based on market cap and other factors"""
        
        # Simple volatility model: smaller companies = higher volatility
        if market_cap > 1e12:      # Large cap (>$1T)
            base_vol = 0.20
        elif market_cap > 1e11:    # Mid cap ($100B-$1T)
            base_vol = 0.25
        else:                      # Small cap (<$100B)
            base_vol = 0.35
        
        # Add some randomness
        noise = np.random.normal(0, 0.05)
        return max(0.1, base_vol + noise)
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary"""
        
        if not self.position_history:
            return {'status': 'no_history'}
        
        latest = self.position_history[-1]
        
        # Calculate metrics
        max_individual = max(latest['positions'].values()) if latest['positions'] else 0
        max_sector = max(latest['sector_weights'].values()) if latest['sector_weights'] else 0
        avg_turnover = np.mean(self.turnover_history) if self.turnover_history else 0
        
        # Constraint compliance
        individual_compliant = max_individual <= self.constraints.max_individual_weight
        sector_compliant = max_sector <= self.constraints.max_sector_weight
        turnover_compliant = latest['total_turnover'] <= self.constraints.max_monthly_turnover
        
        return {
            'timestamp': latest['timestamp'].isoformat(),
            'total_positions': latest['num_positions'],
            'total_weight': latest['total_weight'],
            'max_individual_weight': max_individual,
            'max_sector_weight': max_sector,
            'num_sectors': len(latest['sector_weights']),
            'current_turnover': latest['total_turnover'],
            'average_turnover': avg_turnover,
            'sector_breakdown': latest['sector_weights'],
            'constraint_compliance': {
                'individual_limit': individual_compliant,
                'sector_limit': sector_compliant,
                'turnover_limit': turnover_compliant
            },
            'constraints': {
                'max_individual': self.constraints.max_individual_weight,
                'max_sector': self.constraints.max_sector_weight,
                'max_turnover': self.constraints.max_monthly_turnover,
                'min_volume': self.constraints.min_daily_volume,
                'risk_budget': self.constraints.risk_budget_limit
            }
        }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate Portfolio Governor"""
    
    print("🏛️ PORTFOLIO GOVERNOR - LAYER 6")
    print("=" * 70)
    
    # Initialize portfolio governor
    constraints = PortfolioConstraints(
        max_individual_weight=0.05,
        max_sector_weight=0.25,
        max_correlation_threshold=0.7,
        min_daily_volume=1e6,
        max_monthly_turnover=0.5,
        risk_budget_limit=0.15
    )
    
    governor = PortfolioGovernor(constraints)
    
    # Mock data for demonstration
    from dataclasses import dataclass
    
    @dataclass
    class MockCapitalAllocation:
        specialist_name: str
        allocation_weight: float
    
    @dataclass
    class MockSpecialistSignal:
        symbol: str
        signal_strength: float
        confidence: float
        regime_fit: float
    
    # Mock capital allocations
    mock_allocations = [
        MockCapitalAllocation("momentum", 0.4),
        MockCapitalAllocation("value", 0.3),
        MockCapitalAllocation("quality", 0.2),
        MockCapitalAllocation("macro", 0.1)
    ]
    
    # Mock specialist signals
    mock_signals = {
        "momentum": [
            MockSpecialistSignal("RELIANCE.NS", 2.0, 0.8, 0.9),
            MockSpecialistSignal("TCS.NS", 1.5, 0.7, 0.85),
            MockSpecialistSignal("INFY.NS", 1.8, 0.75, 0.8)
        ],
        "value": [
            MockSpecialistSignal("HDFCBANK.NS", -1.2, 0.6, 0.7),
            MockSpecialistSignal("ICICIBANK.NS", -0.8, 0.5, 0.6)
        ],
        "quality": [
            MockSpecialistSignal("TCS.NS", 1.0, 0.8, 0.75),
            MockSpecialistSignal("WIPRO.NS", 0.8, 0.7, 0.7)
        ],
        "macro": [
            MockSpecialistSignal("BHARTIARTL.NS", 0.5, 0.6, 0.65)
        ]
    }
    
    # Mock market data
    mock_market_data = {
        "RELIANCE.NS": {"sector": "Energy", "market_cap": 1.5e12, "avg_daily_volume": 8e6},
        "TCS.NS": {"sector": "Technology", "market_cap": 1.2e12, "avg_daily_volume": 6e6},
        "INFY.NS": {"sector": "Technology", "market_cap": 8e11, "avg_daily_volume": 4e6},
        "HDFCBANK.NS": {"sector": "Financials", "market_cap": 1.0e12, "avg_daily_volume": 7e6},
        "ICICIBANK.NS": {"sector": "Financials", "market_cap": 6e11, "avg_daily_volume": 5e6},
        "WIPRO.NS": {"sector": "Technology", "market_cap": 3e11, "avg_daily_volume": 2e6},
        "BHARTIARTL.NS": {"sector": "Telecom", "market_cap": 4e11, "avg_daily_volume": 3e6}
    }
    
    # Set existing positions to test portfolio awareness
    governor.current_positions = {
        "RELIANCE.NS": 0.06,  # Above individual limit
        "TCS.NS": 0.03,
        "INFY.NS": 0.02
    }
    
    current_time = datetime(2024, 1, 15)
    
    print(f"\n🏛️ Computing portfolio-aware positions for {current_time.date()}")
    
    # Compute positions
    positions = governor.compute_portfolio_aware_positions(
        mock_allocations, mock_signals, mock_market_data, current_time
    )
    
    # Display results
    print(f"\n📊 PORTFOLIO POSITIONS")
    print("-" * 80)
    print(f"{'Symbol':<12} {'Current':<8} {'Target':<8} {'Final':<8} {'Sector':<12} {'Penalties'}")
    print("-" * 80)
    
    for position in positions:
        penalties = f"C:{position.concentration_penalty:.2f} L:{position.liquidity_penalty:.2f} R:{position.correlation_penalty:.2f}"
        print(f"{position.symbol:<12} {position.current_weight:<8.1%} "
              f"{position.target_weight:<8.1%} {position.final_position_size:<8.1%} "
              f"{position.sector:<12} {penalties}")
    
    # Portfolio summary
    print(f"\n📈 PORTFOLIO SUMMARY")
    print("-" * 50)
    
    summary = governor.get_portfolio_summary()
    print(f"Total positions: {summary['total_positions']}")
    print(f"Total weight: {summary['total_weight']:.1%}")
    print(f"Max individual: {summary['max_individual_weight']:.1%} (limit: {summary['constraints']['max_individual']:.1%})")
    print(f"Max sector: {summary['max_sector_weight']:.1%} (limit: {summary['constraints']['max_sector']:.1%})")
    print(f"Current turnover: {summary['current_turnover']:.1%} (limit: {summary['constraints']['max_turnover']:.1%})")
    
    print(f"\nSector breakdown:")
    for sector, weight in summary['sector_breakdown'].items():
        print(f"   {sector:<12}: {weight:.1%}")
    
    print(f"\nConstraint compliance:")
    for constraint, compliant in summary['constraint_compliance'].items():
        status = "✅" if compliant else "❌"
        print(f"   {constraint}: {status}")
    
    print(f"\n✅ Portfolio Governor demonstration complete")

if __name__ == "__main__":
    main()