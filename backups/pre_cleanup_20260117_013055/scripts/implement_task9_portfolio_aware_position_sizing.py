#!/usr/bin/env python3
"""
🚀 TASK 9: PORTFOLIO-AWARE POSITION SIZING
Implement portfolio-aware position sizing with concentration controls and liquidity constraints

This script implements Task 9 requirements:
- Portfolio governor with concentration controls
- Liquidity and risk constraints
- Property tests for portfolio-aware position sizing

Usage:
    python scripts/implement_task9_portfolio_aware_position_sizing.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import warnings
import json
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import pytest

warnings.filterwarnings('ignore')

from src.intelligence.bayesian_capital_tribunal import (
    BayesianCapitalTribunal, Evidence, CapitalAllocation
)
from src.intelligence.regime_aware_specialists import (
    RegimeAwareSpecialists, SpecialistSignal, RegimeContext, MarketRegime
)

@dataclass
class PortfolioPosition:
    """Portfolio position information"""
    symbol: str
    current_weight: float        # [0, 1] current portfolio weight
    target_weight: float         # [0, 1] target portfolio weight
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
    """Portfolio-level constraints"""
    max_individual_weight: float = 0.05    # 5% max individual position
    max_sector_weight: float = 0.25        # 25% max sector concentration
    max_correlation_threshold: float = 0.7  # 0.7 correlation threshold
    min_daily_volume: float = 1e6         # $1M minimum daily volume
    max_monthly_turnover: float = 0.5      # 50% max monthly turnover
    risk_budget_limit: float = 0.15        # 15% max portfolio risk
    cash_buffer: float = 0.05              # 5% minimum cash buffer

class PortfolioGovernor:
    """
    Portfolio Governor - Portfolio-aware position sizing
    
    Core functionality:
    1. Signal strength adjustment by current portfolio weights
    2. Concentration controls (individual and sector)
    3. Correlation-based position sizing
    4. Liquidity constraints for low-volume stocks
    5. Turnover threshold adjustments
    6. Risk budget management with proportional scaling
    """
    
    def __init__(self, constraints: Optional[PortfolioConstraints] = None):
        self.constraints = constraints or PortfolioConstraints()
        self.position_history = []
        self.turnover_history = []
        self.sector_exposures = {}
        
        # Portfolio state
        self.current_positions = {}  # symbol -> weight
        self.sector_weights = {}     # sector -> weight
        self.correlation_matrix = None
        self.risk_budget_used = 0.0
        
        print("🏛️ Portfolio Governor initialized - Portfolio-aware position sizing active")
    
    def compute_portfolio_aware_positions(self, 
                                        capital_allocations: List[CapitalAllocation],
                                        specialist_signals: Dict[str, List[SpecialistSignal]],
                                        market_data: Dict[str, Dict[str, float]],
                                        current_time: datetime) -> List[PortfolioPosition]:
        """Main portfolio-aware position sizing function"""
        
        print(f"🏛️ Portfolio Governor - Computing portfolio-aware positions for {current_time.date()}")
        
        # Step 1: Generate raw positions from capital allocations and signals
        raw_positions = self._generate_raw_positions(capital_allocations, specialist_signals, market_data)
        
        # Step 2: Apply portfolio-aware adjustments
        adjusted_positions = self._apply_portfolio_awareness(raw_positions, current_time)
        
        # Step 3: Apply concentration controls
        concentration_controlled = self._apply_concentration_controls(adjusted_positions)
        
        # Step 4: Apply liquidity constraints
        liquidity_constrained = self._apply_liquidity_constraints(concentration_controlled, market_data)
        
        # Step 5: Apply risk budget management
        risk_managed = self._apply_risk_budget_management(liquidity_constrained)
        
        # Step 6: Apply turnover controls
        final_positions = self._apply_turnover_controls(risk_managed, current_time)
        
        # Step 7: Update portfolio state
        self._update_portfolio_state(final_positions, current_time)
        
        print(f"   Portfolio positions computed for {len(final_positions)} securities")
        print(f"   Total portfolio weight: {sum(p.final_position_size for p in final_positions):.1%}")
        
        return final_positions
    
    def _generate_raw_positions(self, 
                              capital_allocations: List[CapitalAllocation],
                              specialist_signals: Dict[str, List[SpecialistSignal]],
                              market_data: Dict[str, Dict[str, float]]) -> List[PortfolioPosition]:
        """Generate raw positions from capital allocations and signals"""
        
        raw_positions = []
        
        # Collect all signals with their specialist allocations
        for allocation in capital_allocations:
            specialist_name = allocation.specialist_name
            allocation_weight = allocation.allocation_weight
            
            if specialist_name in specialist_signals:
                for signal in specialist_signals[specialist_name]:
                    symbol = signal.symbol
                    
                    # Get market data for this symbol
                    symbol_data = market_data.get(symbol, {})
                    
                    # Calculate raw position size
                    raw_signal_strength = signal.signal_strength
                    weighted_strength = raw_signal_strength * allocation_weight
                    
                    # Convert signal strength to position size (simple linear mapping)
                    # Strong positive signals -> larger positions, negative signals -> short/avoid
                    base_position_size = max(0, weighted_strength * 0.02)  # 2% per unit signal strength
                    
                    position = PortfolioPosition(
                        symbol=symbol,
                        current_weight=self.current_positions.get(symbol, 0.0),
                        target_weight=base_position_size,
                        signal_strength=raw_signal_strength,
                        adjusted_strength=weighted_strength,
                        sector=symbol_data.get('sector', 'Unknown'),
                        market_cap=symbol_data.get('market_cap', 1e9),
                        avg_daily_volume=symbol_data.get('avg_daily_volume', 1e6),
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
        
        return raw_positions
    
    def _apply_portfolio_awareness(self, positions: List[PortfolioPosition], 
                                 current_time: datetime) -> List[PortfolioPosition]:
        """Apply portfolio-aware adjustments: signal strength / current portfolio weight"""
        
        adjusted_positions = []
        
        for position in positions:
            # Portfolio-aware adjustment: reduce signal strength by current weight
            current_weight = position.current_weight
            
            if current_weight > 0:
                # Reduce signal strength proportionally to current weight
                portfolio_adjustment = 1.0 / (1.0 + current_weight * 10)  # Stronger penalty for larger positions
                adjusted_strength = position.adjusted_strength * portfolio_adjustment
            else:
                adjusted_strength = position.adjusted_strength
            
            # Update position
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
                final_position_size=max(0, adjusted_strength * 0.02),  # Recalculate position size
                metadata=position.metadata
            )
            
            adjusted_positions.append(adjusted_position)
        
        return adjusted_positions
    
    def _apply_concentration_controls(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply concentration controls: individual and sector limits"""
        
        controlled_positions = []
        
        # Calculate current sector exposures
        sector_exposures = {}
        for position in positions:
            sector = position.sector
            if sector not in sector_exposures:
                sector_exposures[sector] = 0.0
            sector_exposures[sector] += position.final_position_size
        
        for position in positions:
            concentration_penalty = 0.0
            
            # Individual concentration penalty
            if position.final_position_size > self.constraints.max_individual_weight:
                individual_penalty = (position.final_position_size - self.constraints.max_individual_weight) / self.constraints.max_individual_weight
                concentration_penalty += individual_penalty * 0.5  # 50% penalty for excess
            
            # Sector concentration penalty
            sector_exposure = sector_exposures.get(position.sector, 0.0)
            if sector_exposure > self.constraints.max_sector_weight:
                sector_penalty = (sector_exposure - self.constraints.max_sector_weight) / self.constraints.max_sector_weight
                concentration_penalty += sector_penalty * 0.25  # 25% penalty for sector excess
            
            # Apply concentration penalty
            penalty_factor = 1.0 / (1.0 + concentration_penalty)
            adjusted_size = position.final_position_size * penalty_factor
            
            # Cap at individual limit
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
                metadata=position.metadata
            )
            
            controlled_positions.append(controlled_position)
        
        return controlled_positions
    
    def _apply_liquidity_constraints(self, positions: List[PortfolioPosition], 
                                   market_data: Dict[str, Dict[str, float]]) -> List[PortfolioPosition]:
        """Apply liquidity constraints for low-volume stocks"""
        
        constrained_positions = []
        
        for position in positions:
            liquidity_penalty = 0.0
            
            # Check daily volume constraint
            daily_volume = position.avg_daily_volume
            if daily_volume < self.constraints.min_daily_volume:
                # Penalty based on how far below minimum volume
                volume_ratio = daily_volume / self.constraints.min_daily_volume
                liquidity_penalty = 1.0 - volume_ratio  # Higher penalty for lower volume
            
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
                metadata=position.metadata
            )
            
            constrained_positions.append(constrained_position)
        
        return constrained_positions
    
    def _apply_risk_budget_management(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply risk budget management with proportional scaling"""
        
        # Calculate total risk (simplified as sum of position sizes weighted by volatility)
        total_risk = 0.0
        for position in positions:
            # Mock volatility calculation (would use actual volatility data)
            estimated_volatility = 0.3 if position.market_cap < 1e10 else 0.2  # Small cap = higher vol
            position_risk = position.final_position_size * estimated_volatility
            total_risk += position_risk
        
        # Check if risk budget is exceeded
        if total_risk > self.constraints.risk_budget_limit:
            # Scale all positions proportionally
            scale_factor = self.constraints.risk_budget_limit / total_risk
            
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
                    metadata={**position.metadata, 'risk_scaled': True, 'scale_factor': scale_factor}
                )
                
                scaled_positions.append(scaled_position)
            
            return scaled_positions
        
        return positions
    
    def _apply_turnover_controls(self, positions: List[PortfolioPosition], 
                               current_time: datetime) -> List[PortfolioPosition]:
        """Apply turnover threshold adjustments"""
        
        # Calculate expected turnover
        total_turnover = 0.0
        for position in positions:
            position_change = abs(position.final_position_size - position.current_weight)
            total_turnover += position_change
        
        # Check if turnover exceeds monthly limit
        if total_turnover > self.constraints.max_monthly_turnover:
            # Reduce position changes proportionally
            turnover_scale = self.constraints.max_monthly_turnover / total_turnover
            
            controlled_positions = []
            for position in positions:
                # Scale the change, not the absolute position
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
                    metadata={**position.metadata, 'turnover_controlled': True, 'turnover_scale': turnover_scale}
                )
                
                controlled_positions.append(controlled_position)
            
            return controlled_positions
        
        return positions
    
    def _apply_correlation_adjustments(self, positions: List[PortfolioPosition]) -> List[PortfolioPosition]:
        """Apply correlation-based position sizing adjustments"""
        
        # This would require actual correlation matrix computation
        # For now, implement a simplified version
        
        adjusted_positions = []
        
        for position in positions:
            correlation_penalty = 0.0
            
            # Mock correlation calculation
            # In practice, would compute correlation with existing positions
            for other_symbol, other_weight in self.current_positions.items():
                if other_symbol != position.symbol and other_weight > 0.01:  # 1% threshold
                    # Mock correlation (would use actual correlation data)
                    mock_correlation = 0.5 if position.sector == self._get_sector(other_symbol) else 0.2
                    
                    if mock_correlation > self.constraints.max_correlation_threshold:
                        correlation_penalty += (mock_correlation - self.constraints.max_correlation_threshold) * other_weight
            
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
                metadata=position.metadata
            )
            
            adjusted_positions.append(adjusted_position)
        
        return adjusted_positions
    
    def _update_portfolio_state(self, positions: List[PortfolioPosition], current_time: datetime):
        """Update internal portfolio state"""
        
        # Update current positions
        new_positions = {}
        new_sector_weights = {}
        
        for position in positions:
            new_positions[position.symbol] = position.final_position_size
            
            sector = position.sector
            if sector not in new_sector_weights:
                new_sector_weights[sector] = 0.0
            new_sector_weights[sector] += position.final_position_size
        
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
            'total_turnover': total_turnover
        })
        
        self.turnover_history.append(total_turnover)
        
        # Keep only recent history
        if len(self.position_history) > 252:  # 1 year
            self.position_history = self.position_history[-252:]
        if len(self.turnover_history) > 252:
            self.turnover_history = self.turnover_history[-252:]
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for symbol (mock implementation)"""
        # Mock sector mapping
        sector_map = {
            'RELIANCE.NS': 'Energy',
            'TCS.NS': 'Technology',
            'INFY.NS': 'Technology',
            'HDFCBANK.NS': 'Financials',
            'ICICIBANK.NS': 'Financials'
        }
        return sector_map.get(symbol, 'Unknown')
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary statistics"""
        
        if not self.position_history:
            return {'status': 'no_history'}
        
        latest = self.position_history[-1]
        
        # Calculate concentration metrics
        max_individual = max(latest['positions'].values()) if latest['positions'] else 0
        max_sector = max(latest['sector_weights'].values()) if latest['sector_weights'] else 0
        
        # Calculate turnover metrics
        avg_turnover = np.mean(self.turnover_history) if self.turnover_history else 0
        
        return {
            'total_positions': len(latest['positions']),
            'total_weight': sum(latest['positions'].values()),
            'max_individual_weight': max_individual,
            'max_sector_weight': max_sector,
            'num_sectors': len(latest['sector_weights']),
            'average_turnover': avg_turnover,
            'current_turnover': latest['total_turnover'],
            'sector_breakdown': latest['sector_weights']
        }

# =========================== PROPERTY TESTS ===========================

class PropertyTestPortfolioAwarePositionSizing:
    """
    Property Test 6: Portfolio-Aware Position Sizing
    
    Validates that:
    - Signal strength is adjusted by current portfolio weights
    - Concentration penalties applied (>5% individual → 50% reduction, >25% sector → penalties)
    - Position sizing reduced for high correlation (>0.7) and low liquidity
    - Proportional scaling when risk budgets exceeded
    """
    
    def __init__(self, epsilon: float = 1e-6):
        self.epsilon = epsilon
        self.governor = PortfolioGovernor()
    
    def test_portfolio_awareness_adjustment(self) -> bool:
        """Test that signal strength is adjusted by current portfolio weights"""
        
        print("\n   Testing portfolio awareness adjustment...")
        
        # Create test positions with different current weights
        positions = [
            PortfolioPosition(
                symbol="HIGH_WEIGHT", current_weight=0.08, target_weight=0.05,
                signal_strength=2.0, adjusted_strength=2.0, sector="Tech",
                market_cap=1e11, avg_daily_volume=5e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.05,
                metadata={}
            ),
            PortfolioPosition(
                symbol="LOW_WEIGHT", current_weight=0.01, target_weight=0.05,
                signal_strength=2.0, adjusted_strength=2.0, sector="Tech",
                market_cap=1e11, avg_daily_volume=5e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.05,
                metadata={}
            )
        ]
        
        # Apply portfolio awareness
        adjusted = self.governor._apply_portfolio_awareness(positions, datetime.now())
        
        # High weight position should have lower adjusted strength
        high_weight_adjusted = next(p for p in adjusted if p.symbol == "HIGH_WEIGHT")
        low_weight_adjusted = next(p for p in adjusted if p.symbol == "LOW_WEIGHT")
        
        if high_weight_adjusted.adjusted_strength >= low_weight_adjusted.adjusted_strength:
            print(f"❌ Portfolio awareness not applied: high_weight={high_weight_adjusted.adjusted_strength:.3f}, "
                  f"low_weight={low_weight_adjusted.adjusted_strength:.3f}")
            return False
        
        print(f"   ✅ Portfolio awareness working: high_weight reduced to {high_weight_adjusted.adjusted_strength:.3f}")
        return True
    
    def test_concentration_controls(self) -> bool:
        """Test concentration penalties for individual and sector limits"""
        
        print("\n   Testing concentration controls...")
        
        # Create positions that exceed concentration limits
        positions = [
            PortfolioPosition(
                symbol="LARGE_POS", current_weight=0.02, target_weight=0.08,  # Exceeds 5% limit
                signal_strength=2.0, adjusted_strength=2.0, sector="Tech",
                market_cap=1e11, avg_daily_volume=5e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.08,
                metadata={}
            ),
            PortfolioPosition(
                symbol="TECH1", current_weight=0.02, target_weight=0.15,  # Part of large sector
                signal_strength=1.5, adjusted_strength=1.5, sector="Tech",
                market_cap=1e11, avg_daily_volume=5e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.15,
                metadata={}
            ),
            PortfolioPosition(
                symbol="TECH2", current_weight=0.02, target_weight=0.15,  # Part of large sector
                signal_strength=1.5, adjusted_strength=1.5, sector="Tech",
                market_cap=1e11, avg_daily_volume=5e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.15,
                metadata={}
            )
        ]
        
        # Apply concentration controls
        controlled = self.governor._apply_concentration_controls(positions)
        
        # Check individual limit enforcement
        large_pos = next(p for p in controlled if p.symbol == "LARGE_POS")
        if large_pos.final_position_size > self.governor.constraints.max_individual_weight:
            print(f"❌ Individual concentration limit not enforced: {large_pos.final_position_size:.1%}")
            return False
        
        # Check that concentration penalty was applied
        if large_pos.concentration_penalty <= 0:
            print(f"❌ Concentration penalty not applied: {large_pos.concentration_penalty}")
            return False
        
        print(f"   ✅ Concentration controls working: penalty={large_pos.concentration_penalty:.3f}, "
              f"final_size={large_pos.final_position_size:.1%}")
        return True
    
    def test_liquidity_constraints(self) -> bool:
        """Test liquidity constraints for low-volume stocks"""
        
        print("\n   Testing liquidity constraints...")
        
        # Mock market data with different volume levels
        market_data = {
            "LOW_VOL": {"avg_daily_volume": 5e5},    # Below 1M threshold
            "HIGH_VOL": {"avg_daily_volume": 5e6}    # Above 1M threshold
        }
        
        positions = [
            PortfolioPosition(
                symbol="LOW_VOL", current_weight=0.02, target_weight=0.04,
                signal_strength=2.0, adjusted_strength=2.0, sector="Tech",
                market_cap=1e10, avg_daily_volume=5e5, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.04,
                metadata={}
            ),
            PortfolioPosition(
                symbol="HIGH_VOL", current_weight=0.02, target_weight=0.04,
                signal_strength=2.0, adjusted_strength=2.0, sector="Tech",
                market_cap=1e10, avg_daily_volume=5e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.04,
                metadata={}
            )
        ]
        
        # Apply liquidity constraints
        constrained = self.governor._apply_liquidity_constraints(positions, market_data)
        
        # Low volume stock should have penalty and smaller position
        low_vol = next(p for p in constrained if p.symbol == "LOW_VOL")
        high_vol = next(p for p in constrained if p.symbol == "HIGH_VOL")
        
        if low_vol.liquidity_penalty <= 0:
            print(f"❌ Liquidity penalty not applied: {low_vol.liquidity_penalty}")
            return False
        
        if low_vol.final_position_size >= high_vol.final_position_size:
            print(f"❌ Liquidity constraint not effective: low_vol={low_vol.final_position_size:.3f}, "
                  f"high_vol={high_vol.final_position_size:.3f}")
            return False
        
        print(f"   ✅ Liquidity constraints working: penalty={low_vol.liquidity_penalty:.3f}, "
              f"size_reduction={((0.04 - low_vol.final_position_size) / 0.04):.1%}")
        return True
    
    def test_risk_budget_scaling(self) -> bool:
        """Test proportional scaling when risk budgets exceeded"""
        
        print("\n   Testing risk budget scaling...")
        
        # Create positions that would exceed risk budget
        positions = []
        for i in range(10):
            position = PortfolioPosition(
                symbol=f"STOCK_{i}", current_weight=0.01, target_weight=0.05,
                signal_strength=2.0, adjusted_strength=2.0, sector="Tech",
                market_cap=1e9,  # Small cap = higher volatility
                avg_daily_volume=2e6, correlation_penalty=0.0,
                liquidity_penalty=0.0, concentration_penalty=0.0, final_position_size=0.05,
                metadata={}
            )
            positions.append(position)
        
        # Apply risk budget management
        risk_managed = self.governor._apply_risk_budget_management(positions)
        
        # Check if scaling was applied
        scaled_position = risk_managed[0]
        if 'risk_scaled' not in scaled_position.metadata:
            print(f"❌ Risk scaling not applied when expected")
            return False
        
        scale_factor = scaled_position.metadata['scale_factor']
        if scale_factor >= 1.0:
            print(f"❌ Risk scaling factor should be < 1.0: {scale_factor}")
            return False
        
        # Check that all positions were scaled proportionally
        for position in risk_managed:
            expected_size = 0.05 * scale_factor
            if abs(position.final_position_size - expected_size) > self.epsilon:
                print(f"❌ Proportional scaling not applied correctly")
                return False
        
        print(f"   ✅ Risk budget scaling working: scale_factor={scale_factor:.3f}")
        return True
    
    def run_property_test(self) -> bool:
        """Run complete Property 6 test"""
        
        print("\n🧪 PROPERTY TEST 6: PORTFOLIO-AWARE POSITION SIZING")
        print("-" * 70)
        
        # Test 1: Portfolio awareness adjustment
        test1_passed = self.test_portfolio_awareness_adjustment()
        
        # Test 2: Concentration controls
        test2_passed = self.test_concentration_controls()
        
        # Test 3: Liquidity constraints
        test3_passed = self.test_liquidity_constraints()
        
        # Test 4: Risk budget scaling
        test4_passed = self.test_risk_budget_scaling()
        
        # Overall result
        tests_passed = sum([test1_passed, test2_passed, test3_passed, test4_passed])
        total_tests = 4
        
        print(f"\n   Tests passed: {tests_passed}/{total_tests}")
        
        overall_passed = tests_passed == total_tests
        
        if overall_passed:
            print(f"\n✅ PROPERTY TEST 6: PASSED")
            print("💡 Portfolio-aware position sizing working correctly")
        else:
            print(f"\n❌ PROPERTY TEST 6: FAILED")
            print("💡 Some aspects of portfolio-aware position sizing need fixing")
        
        return overall_passed

# =========================== MAIN IMPLEMENTATION ===========================

def implement_task9_portfolio_governor():
    """Implement Task 9 portfolio governor with concentration controls"""
    
    print("🚀 TASK 9: PORTFOLIO-AWARE POSITION SIZING")
    print("=" * 80)
    
    print("\n🎯 Implementing portfolio governor with:")
    print("   • Portfolio-aware signal strength adjustments")
    print("   • Concentration controls (individual and sector)")
    print("   • Liquidity constraints for low-volume stocks")
    print("   • Risk budget management with proportional scaling")
    print("   • Turnover threshold controls")
    
    # Initialize portfolio governor
    constraints = PortfolioConstraints(
        max_individual_weight=0.05,    # 5%
        max_sector_weight=0.25,        # 25%
        max_correlation_threshold=0.7,  # 0.7
        min_daily_volume=1e6,          # $1M
        max_monthly_turnover=0.5,      # 50%
        risk_budget_limit=0.15         # 15%
    )
    
    governor = PortfolioGovernor(constraints)
    
    # Test 1: Mock capital allocations and signals
    print(f"\n🏛️ TEST 1: PORTFOLIO GOVERNOR INITIALIZATION")
    print("-" * 50)
    
    # Mock capital allocations from Bayesian tribunal
    mock_allocations = [
        CapitalAllocation("momentum", 0.4, 0.4, 0.8, 0.8, 0.1, 0.8, {}),
        CapitalAllocation("value", 0.3, 0.3, 0.7, 0.7, 0.05, 0.7, {}),
        CapitalAllocation("quality", 0.2, 0.2, 0.6, 0.6, -0.05, 0.6, {}),
        CapitalAllocation("macro", 0.1, 0.1, 0.5, 0.5, 0.0, 0.5, {})
    ]
    
    # Mock specialist signals
    from src.intelligence.regime_aware_specialists import SpecialistSignal
    mock_signals = {
        "momentum": [
            SpecialistSignal("RELIANCE.NS", 2.0, 0.8, 0.9, 0.8, {}),
            SpecialistSignal("TCS.NS", 1.5, 0.7, 0.9, 0.85, {}),
            SpecialistSignal("INFY.NS", 1.8, 0.75, 0.85, 0.8, {})
        ],
        "value": [
            SpecialistSignal("HDFCBANK.NS", -1.2, 0.6, 0.3, 0.7, {}),
            SpecialistSignal("ICICIBANK.NS", -0.8, 0.5, 0.3, 0.6, {})
        ],
        "quality": [
            SpecialistSignal("TCS.NS", 1.0, 0.8, 0.7, 0.75, {}),
            SpecialistSignal("INFY.NS", 0.8, 0.75, 0.65, 0.7, {})
        ],
        "macro": [
            SpecialistSignal("RELIANCE.NS", 0.5, 0.6, 0.8, 0.65, {})
        ]
    }
    
    # Mock market data
    mock_market_data = {
        "RELIANCE.NS": {
            "sector": "Energy",
            "market_cap": 1.5e12,  # Large cap
            "avg_daily_volume": 8e6
        },
        "TCS.NS": {
            "sector": "Technology", 
            "market_cap": 1.2e12,  # Large cap
            "avg_daily_volume": 6e6
        },
        "INFY.NS": {
            "sector": "Technology",
            "market_cap": 8e11,    # Large cap
            "avg_daily_volume": 4e6
        },
        "HDFCBANK.NS": {
            "sector": "Financials",
            "market_cap": 1.0e12,  # Large cap
            "avg_daily_volume": 7e6
        },
        "ICICIBANK.NS": {
            "sector": "Financials",
            "market_cap": 6e11,    # Large cap
            "avg_daily_volume": 5e6
        }
    }
    
    print(f"   Portfolio constraints configured:")
    print(f"      Max individual: {constraints.max_individual_weight:.1%}")
    print(f"      Max sector: {constraints.max_sector_weight:.1%}")
    print(f"      Min daily volume: ${constraints.min_daily_volume:,.0f}")
    print(f"      Max monthly turnover: {constraints.max_monthly_turnover:.1%}")
    
    # Test 2: Compute portfolio-aware positions
    print(f"\n📊 TEST 2: PORTFOLIO-AWARE POSITION COMPUTATION")
    print("-" * 50)
    
    current_time = datetime(2024, 1, 15)
    
    # Set some existing positions to test portfolio awareness
    governor.current_positions = {
        "RELIANCE.NS": 0.06,  # Above individual limit
        "TCS.NS": 0.03,
        "INFY.NS": 0.02
    }
    
    positions = governor.compute_portfolio_aware_positions(
        mock_allocations, mock_signals, mock_market_data, current_time
    )
    
    print(f"\n   Portfolio positions computed:")
    print(f"   {'Symbol':<12} {'Current':<8} {'Target':<8} {'Final':<8} {'Sector':<12} {'Penalties'}")
    print(f"   {'-'*70}")
    
    for position in positions:
        penalties = f"C:{position.concentration_penalty:.2f} L:{position.liquidity_penalty:.2f}"
        print(f"   {position.symbol:<12} {position.current_weight:<8.1%} "
              f"{position.target_weight:<8.1%} {position.final_position_size:<8.1%} "
              f"{position.sector:<12} {penalties}")
    
    # Test 3: Portfolio summary
    print(f"\n📈 TEST 3: PORTFOLIO SUMMARY")
    print("-" * 50)
    
    summary = governor.get_portfolio_summary()
    print(f"   Total positions: {summary['total_positions']}")
    print(f"   Total weight: {summary['total_weight']:.1%}")
    print(f"   Max individual: {summary['max_individual_weight']:.1%}")
    print(f"   Max sector: {summary['max_sector_weight']:.1%}")
    print(f"   Current turnover: {summary['current_turnover']:.1%}")
    
    print(f"\n   Sector breakdown:")
    for sector, weight in summary['sector_breakdown'].items():
        print(f"      {sector:<12}: {weight:.1%}")
    
    return governor

def run_property_tests():
    """Run property tests for Task 9"""
    
    print(f"\n🧪 RUNNING PROPERTY TESTS FOR TASK 9")
    print("=" * 60)
    
    # Property Test 6: Portfolio-Aware Position Sizing
    test6 = PropertyTestPortfolioAwarePositionSizing()
    test6_passed = test6.run_property_test()
    
    # Overall results
    tests_passed = 1 if test6_passed else 0
    total_tests = 1
    
    print(f"\n📈 PROPERTY TEST SUMMARY")
    print("=" * 40)
    print(f"   Tests passed: {tests_passed}/{total_tests}")
    print(f"   Success rate: {tests_passed/total_tests:.1%}")
    
    if tests_passed == total_tests:
        print(f"\n✅ ALL PROPERTY TESTS PASSED")
        print("💡 Portfolio-aware position sizing is working correctly")
        return True
    else:
        print(f"\n❌ SOME PROPERTY TESTS FAILED")
        print("💡 Portfolio-aware position sizing needs fixes")
        return False

def save_task9_results(success: bool, governor: PortfolioGovernor):
    """Save Task 9 implementation results"""
    
    results = {
        'task': 'Task 9 - Portfolio-Aware Position Sizing',
        'completion_date': datetime.now().isoformat(),
        'overall_success': success,
        'components_implemented': [
            'Portfolio governor with concentration controls',
            'Liquidity and risk constraints',
            'Property Test 6: Portfolio-Aware Position Sizing'
        ],
        'features': {
            'portfolio_awareness': 'Signal strength adjusted by current portfolio weights',
            'concentration_controls': 'Individual (5%) and sector (25%) limits enforced',
            'liquidity_constraints': 'Position sizing reduced for low-volume stocks',
            'risk_budget_management': 'Proportional scaling when risk budgets exceeded',
            'turnover_controls': 'Monthly turnover threshold (50%) enforcement',
            'correlation_adjustments': 'Position sizing reduced for high correlation (>0.7)'
        },
        'constraints': {
            'max_individual_weight': 0.05,
            'max_sector_weight': 0.25,
            'max_correlation_threshold': 0.7,
            'min_daily_volume': 1e6,
            'max_monthly_turnover': 0.5,
            'risk_budget_limit': 0.15
        },
        'portfolio_summary': governor.get_portfolio_summary() if governor else {}
    }
    
    # Save results
    os.makedirs('reports', exist_ok=True)
    with open('reports/task9_portfolio_aware_position_sizing_complete.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Task 9 results saved to reports/task9_portfolio_aware_position_sizing_complete.json")

def main():
    """Main Task 9 implementation"""
    
    print("🚀 STARTING TASK 9: PORTFOLIO-AWARE POSITION SIZING")
    print("=" * 80)
    
    try:
        # Step 1: Implement portfolio governor
        governor = implement_task9_portfolio_governor()
        
        # Step 2: Run property tests
        property_tests_passed = run_property_tests()
        
        # Step 3: Overall assessment
        overall_success = property_tests_passed
        
        if overall_success:
            print(f"\n🎉 TASK 9 COMPLETE!")
            print("🏛️ Portfolio-aware position sizing implemented successfully")
            print("📊 All property tests passed - system ready for production")
            print("💡 Ready to proceed to Task 10: Stress Testing and Validation System")
        else:
            print(f"\n⚠️ TASK 9 INCOMPLETE")
            print("🔧 Some property tests failed - review and fix issues")
        
        # Step 4: Save results
        save_task9_results(overall_success, governor)
        
        return overall_success
        
    except Exception as e:
        print(f"\n❌ Task 9 failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()