#!/usr/bin/env python3
"""
Position Governor - ADV-Scaled Position Sizing

This module enforces liquidity-realistic position sizing by limiting positions
to α × ADV where α varies by asset class. This prevents the system from taking
unrealistic positions that would be impossible to execute in real markets.

Key Features:
- α × ADV position limits by asset class
- Liquidity tier classification and enforcement
- Position rejection for insufficient liquidity
- Integration with Signal Quality Gate and Regime-Locked Capital Allocator
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from src.intelligence.adv_database import ADVData, ADVDatabase, LiquidityTier

@dataclass
class PositionLimits:
    """Position limits for a symbol"""
    symbol: str
    max_position_value: float    # Maximum position value in currency
    alpha_factor: float          # α factor used (% of ADV)
    adv_used: float             # ADV value used for calculation
    liquidity_tier: LiquidityTier
    limit_reason: str           # Reason for the limit
    is_rejected: bool = False   # Position completely rejected

@dataclass
class GovernorConfig:
    """Configuration for Position Governor"""
    # α factors by asset class (% of ADV)
    alpha_factors: Dict[str, float] = None
    
    # Position sizing limits
    min_position_value: float = 100_000      # ₹1 Lakh minimum position
    max_position_value: float = 500_000_000  # ₹50 Crore maximum position
    
    # Risk controls
    max_single_position_pct: float = 0.05   # 5% max of total portfolio
    total_illiquid_limit_pct: float = 0.20  # 20% max in small-cap positions
    
    # Integration settings
    respect_regime_limits: bool = True      # Respect regime capital limits
    apply_signal_quality_filter: bool = True  # Apply signal quality filtering
    
    def __post_init__(self):
        if self.alpha_factors is None:
            self.alpha_factors = {
                'large_cap': 0.05,    # 5% of ADV for large-cap
                'mid_cap': 0.03,      # 3% of ADV for mid-cap
                'small_cap': 0.01,    # 1% of ADV for small-cap
                'default': 0.02       # 2% default
            }

class PositionGovernor:
    """
    ADV-scaled position governor that enforces liquidity-realistic position sizing.
    
    This is the gatekeeper that prevents unrealistic positions from entering
    the portfolio. Every position must pass through liquidity constraints.
    """
    
    def __init__(self, 
                 adv_database: ADVDatabase,
                 config: GovernorConfig = None):
        self.adv_database = adv_database
        self.config = config or GovernorConfig()
        self.name = "Position Governor"
        self.version = "1.0"
        
        # Tracking metrics
        self.positions_processed = 0
        self.positions_rejected = 0
        self.positions_capped = 0
        self.rejection_reasons: Dict[str, int] = {}
        
        print(f"🏛️ {self.name} initialized")
        print(f"   Alpha factors: {self.config.alpha_factors}")
        print(f"   Min position: ₹{self.config.min_position_value:,.0f}")
        print(f"   Max position: ₹{self.config.max_position_value:,.0f}")
    
    def calculate_max_position(self, 
                             symbol: str, 
                             adv_data: ADVData = None,
                             asset_class: str = None,
                             as_of_date: datetime = None) -> PositionLimits:
        """
        Calculate maximum allowable position size for a symbol.
        
        Args:
            symbol: Stock symbol
            adv_data: Pre-calculated ADV data (optional)
            asset_class: Asset class override (optional)
            as_of_date: Date for calculation
            
        Returns:
            PositionLimits object with sizing constraints
        """
        
        self.positions_processed += 1
        
        # Get ADV data if not provided
        if adv_data is None:
            adv_data = self.adv_database.calculate_rolling_adv(symbol, as_of_date)
        
        # Check if ADV data is available
        if adv_data is None:
            self.positions_rejected += 1
            self._track_rejection("no_adv_data")
            return PositionLimits(
                symbol=symbol,
                max_position_value=0.0,
                alpha_factor=0.0,
                adv_used=0.0,
                liquidity_tier=LiquidityTier.MICRO_CAP,
                limit_reason="No ADV data available",
                is_rejected=True
            )
        
        # Check data quality and staleness
        if adv_data.is_stale or adv_data.data_quality < 0.5:
            self.positions_rejected += 1
            self._track_rejection("poor_data_quality")
            return PositionLimits(
                symbol=symbol,
                max_position_value=0.0,
                alpha_factor=0.0,
                adv_used=adv_data.adv_21d,
                liquidity_tier=adv_data.liquidity_tier,
                limit_reason=f"Poor data quality: {adv_data.data_quality:.2f}, stale: {adv_data.is_stale}",
                is_rejected=True
            )
        
        # Reject micro-cap positions (below minimum ADV threshold)
        if adv_data.liquidity_tier == LiquidityTier.MICRO_CAP:
            self.positions_rejected += 1
            self._track_rejection("insufficient_liquidity")
            return PositionLimits(
                symbol=symbol,
                max_position_value=0.0,
                alpha_factor=0.0,
                adv_used=adv_data.adv_21d,
                liquidity_tier=adv_data.liquidity_tier,
                limit_reason=f"Insufficient liquidity: ₹{adv_data.adv_21d:,.0f} < minimum threshold",
                is_rejected=True
            )
        
        # Determine α factor
        alpha_factor = self._get_alpha_factor(adv_data.liquidity_tier, asset_class)
        
        # Calculate maximum position value
        max_position_value = alpha_factor * adv_data.adv_21d
        
        # Apply absolute limits
        max_position_value = max(max_position_value, self.config.min_position_value)
        max_position_value = min(max_position_value, self.config.max_position_value)
        
        # Create position limits
        position_limits = PositionLimits(
            symbol=symbol,
            max_position_value=max_position_value,
            alpha_factor=alpha_factor,
            adv_used=adv_data.adv_21d,
            liquidity_tier=adv_data.liquidity_tier,
            limit_reason=f"α={alpha_factor:.1%} × ADV=₹{adv_data.adv_21d:,.0f}",
            is_rejected=False
        )
        
        return position_limits
    
    def _get_alpha_factor(self, 
                         liquidity_tier: LiquidityTier, 
                         asset_class: str = None) -> float:
        """Get α factor based on liquidity tier and asset class"""
        
        # Use asset class if provided
        if asset_class and asset_class in self.config.alpha_factors:
            return self.config.alpha_factors[asset_class]
        
        # Map liquidity tier to α factor
        tier_mapping = {
            LiquidityTier.LARGE_CAP: self.config.alpha_factors.get('large_cap', 0.05),
            LiquidityTier.MID_CAP: self.config.alpha_factors.get('mid_cap', 0.03),
            LiquidityTier.SMALL_CAP: self.config.alpha_factors.get('small_cap', 0.01),
            LiquidityTier.MICRO_CAP: 0.0  # Rejected
        }
        
        return tier_mapping.get(liquidity_tier, self.config.alpha_factors.get('default', 0.02))
    
    def apply_liquidity_constraints(self, 
                                  target_weights: Dict[str, float],
                                  portfolio_value: float = 1_000_000,
                                  as_of_date: datetime = None) -> Dict[str, float]:
        """
        Apply liquidity constraints to target portfolio weights.
        
        Args:
            target_weights: Dictionary of symbol -> target weight
            portfolio_value: Total portfolio value for position sizing
            as_of_date: Date for ADV calculations
            
        Returns:
            Dictionary of symbol -> constrained weight
        """
        
        print(f"🏛️ Applying liquidity constraints to {len(target_weights)} positions")
        
        constrained_weights = {}
        total_rejected_weight = 0.0
        total_capped_weight = 0.0
        
        # Get ADV data for all symbols
        symbols = list(target_weights.keys())
        adv_data_map = self.adv_database.get_adv_for_symbols(symbols, as_of_date)
        
        # Process each position
        for symbol, target_weight in target_weights.items():
            if target_weight == 0.0:
                constrained_weights[symbol] = 0.0
                continue
            
            # Calculate position limits
            adv_data = adv_data_map.get(symbol)
            position_limits = self.calculate_max_position(symbol, adv_data, as_of_date=as_of_date)
            
            # Check if position is rejected
            if position_limits.is_rejected:
                constrained_weights[symbol] = 0.0
                total_rejected_weight += abs(target_weight)
                continue
            
            # Calculate target position value
            target_position_value = abs(target_weight) * portfolio_value
            
            # Apply position limit
            if target_position_value > position_limits.max_position_value:
                # Cap the position
                capped_weight = (position_limits.max_position_value / portfolio_value) * np.sign(target_weight)
                constrained_weights[symbol] = capped_weight
                total_capped_weight += abs(target_weight) - abs(capped_weight)
                self.positions_capped += 1
                
                print(f"   📏 Capped {symbol}: {target_weight:.3f} → {capped_weight:.3f} "
                      f"(₹{target_position_value:,.0f} → ₹{position_limits.max_position_value:,.0f})")
            else:
                # Position is within limits
                constrained_weights[symbol] = target_weight
        
        # Handle redistributed weight
        total_constrained_weight = total_rejected_weight + total_capped_weight
        
        if total_constrained_weight > 0.001:  # Significant constraint
            print(f"   ⚠️  Total weight constrained: {total_constrained_weight:.3f}")
            print(f"      Rejected: {total_rejected_weight:.3f}")
            print(f"      Capped: {total_capped_weight:.3f}")
            
            # Option 1: Redistribute to liquid positions (simple approach)
            # Option 2: Return to cash (conservative approach)
            # For now, we'll return to cash (weight goes to 0)
        
        return constrained_weights
    
    def get_liquidity_tier(self, symbol: str, as_of_date: datetime = None) -> Optional[LiquidityTier]:
        """Get liquidity tier for a symbol"""
        
        adv_data = self.adv_database.calculate_rolling_adv(symbol, as_of_date)
        return adv_data.liquidity_tier if adv_data else None
    
    def validate_portfolio_liquidity(self, 
                                   weights: Dict[str, float],
                                   portfolio_value: float = 1_000_000,
                                   as_of_date: datetime = None) -> Dict:
        """
        Validate entire portfolio against liquidity constraints.
        
        Returns comprehensive liquidity analysis.
        """
        
        analysis = {
            'total_positions': len([w for w in weights.values() if w != 0]),
            'liquidity_breakdown': {tier.value: 0 for tier in LiquidityTier},
            'weight_by_tier': {tier.value: 0.0 for tier in LiquidityTier},
            'violations': [],
            'total_violation_weight': 0.0,
            'is_valid': True
        }
        
        # Analyze each position
        for symbol, weight in weights.items():
            if weight == 0.0:
                continue
            
            position_limits = self.calculate_max_position(symbol, as_of_date=as_of_date)
            tier = position_limits.liquidity_tier
            
            # Update tier counts
            analysis['liquidity_breakdown'][tier.value] += 1
            analysis['weight_by_tier'][tier.value] += abs(weight)
            
            # Check for violations
            position_value = abs(weight) * portfolio_value
            if position_limits.is_rejected or position_value > position_limits.max_position_value:
                violation = {
                    'symbol': symbol,
                    'weight': weight,
                    'position_value': position_value,
                    'max_allowed': position_limits.max_position_value,
                    'tier': tier.value,
                    'reason': position_limits.limit_reason
                }
                analysis['violations'].append(violation)
                analysis['total_violation_weight'] += abs(weight)
                analysis['is_valid'] = False
        
        return analysis
    
    def _track_rejection(self, reason: str):
        """Track rejection reasons for analysis"""
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
    
    def get_governor_metrics(self) -> Dict:
        """Get position governor performance metrics"""
        
        total_processed = self.positions_processed
        rejection_rate = self.positions_rejected / total_processed if total_processed > 0 else 0
        capping_rate = self.positions_capped / total_processed if total_processed > 0 else 0
        
        return {
            'positions_processed': total_processed,
            'positions_rejected': self.positions_rejected,
            'positions_capped': self.positions_capped,
            'rejection_rate': rejection_rate,
            'capping_rate': capping_rate,
            'rejection_reasons': self.rejection_reasons.copy(),
            'pass_rate': 1.0 - rejection_rate - capping_rate
        }

def main():
    """Test the Position Governor"""
    
    print("🧪 TESTING POSITION GOVERNOR")
    print("=" * 60)
    
    # Initialize ADV database with test data
    # Dependency injection - import ADVDatabase, ADVConfig from src.adv_database
# from adv_database import ADVDatabase, ADVConfig
    
    adv_config = ADVConfig(
        min_adv_threshold=10_000_000,    # ₹1 Crore minimum
        large_cap_threshold=500_000_000, # ₹50 Crore for large cap
        mid_cap_threshold=50_000_000     # ₹5 Crore for mid cap
    )
    
    adv_db = ADVDatabase(adv_config)
    
    # Add test volume data for Indian market
    np.random.seed(42)
    test_symbols = {
        'RELIANCE': {'volume': 8_000_000, 'price': 2500},    # Large cap oil & gas
        'TCS': {'volume': 3_000_000, 'price': 3500},         # Large cap IT
        'HDFCBANK': {'volume': 5_000_000, 'price': 1600},    # Large cap banking
        'INFY': {'volume': 4_000_000, 'price': 1400},        # Large cap IT
        'BAJFINANCE': {'volume': 1_500_000, 'price': 6500},  # Mid cap finance
        'MARUTI': {'volume': 800_000, 'price': 10000},       # Mid cap auto
        'SMALLCAP1': {'volume': 100_000, 'price': 200},      # Small cap
        'SMALLCAP2': {'volume': 80_000, 'price': 150},       # Small cap
        'MICROCAP1': {'volume': 20_000, 'price': 50}         # Micro cap (rejected)
    }
    
    dates = pd.date_range(start='2025-01-01', end='2026-01-03', freq='D')
    
    for symbol, params in test_symbols.items():
        volume_noise = np.random.normal(1.0, 0.2, len(dates))
        price_noise = np.random.normal(1.0, 0.05, len(dates))
        
        volume_data = pd.DataFrame({
            'date': dates,
            'volume': params['volume'] * volume_noise
        })
        
        price_data = pd.DataFrame({
            'date': dates,
            'close': params['price'] * price_noise
        })
        
        adv_db.add_volume_data(symbol, volume_data, price_data)
    
    # Initialize Position Governor
    governor_config = GovernorConfig(
        alpha_factors={
            'large_cap': 0.05,   # 5% of ADV
            'mid_cap': 0.03,     # 3% of ADV
            'small_cap': 0.01,   # 1% of ADV
            'default': 0.02
        }
    )
    
    governor = PositionGovernor(adv_db, governor_config)
    
    # Test individual position limits
    print(f"\n🏛️ TESTING POSITION LIMITS")
    print("=" * 40)
    
    test_date = datetime(2026, 1, 3)
    
    for symbol in test_symbols.keys():
        limits = governor.calculate_max_position(symbol, as_of_date=test_date)
        
        print(f"\n{symbol}:")
        print(f"   Max Position: ₹{limits.max_position_value:,.0f}")
        print(f"   Alpha Factor: {limits.alpha_factor:.1%}")
        print(f"   ADV Used: ₹{limits.adv_used:,.0f}")
        print(f"   Tier: {limits.liquidity_tier.value}")
        print(f"   Rejected: {limits.is_rejected}")
        print(f"   Reason: {limits.limit_reason}")
    
    # Test portfolio constraint application
    print(f"\n📊 TESTING PORTFOLIO CONSTRAINTS")
    print("=" * 40)
    
    # Create test portfolio with Indian stocks
    target_weights = {
        'RELIANCE': 0.15,      # Large position in large cap oil & gas
        'TCS': 0.10,           # Medium position in large cap IT
        'HDFCBANK': 0.08,      # Medium position in large cap banking
        'INFY': 0.05,          # Small position in large cap IT
        'BAJFINANCE': 0.03,    # Small position in mid cap finance
        'MARUTI': 0.02,        # Tiny position in mid cap auto
        'SMALLCAP1': 0.01,     # Position in small cap
        'MICROCAP1': 0.005     # Position in micro cap (should be rejected)
    }
    
    portfolio_value = 100_000_000  # ₹10 Crore portfolio
    
    print(f"Target portfolio (₹{portfolio_value:,.0f}):")
    for symbol, weight in target_weights.items():
        position_value = weight * portfolio_value
        print(f"   {symbol}: {weight:.1%} (₹{position_value:,.0f})")
    
    # Apply constraints
    constrained_weights = governor.apply_liquidity_constraints(
        target_weights, 
        portfolio_value, 
        test_date
    )
    
    print(f"\nConstrained portfolio:")
    total_constrained = 0.0
    for symbol, weight in constrained_weights.items():
        position_value = weight * portfolio_value
        original_weight = target_weights[symbol]
        change = weight - original_weight
        
        if abs(change) > 0.001:
            print(f"   {symbol}: {weight:.1%} (₹{position_value:,.0f}) "
                  f"[{change:+.1%}]")
        else:
            print(f"   {symbol}: {weight:.1%} (₹{position_value:,.0f})")
        
        total_constrained += weight
    
    print(f"\nTotal constrained weight: {total_constrained:.1%}")
    
    # Portfolio validation
    print(f"\n🔍 PORTFOLIO VALIDATION")
    print("=" * 40)
    
    validation = governor.validate_portfolio_liquidity(
        constrained_weights, 
        portfolio_value, 
        test_date
    )
    
    print(f"Portfolio valid: {validation['is_valid']}")
    print(f"Total positions: {validation['total_positions']}")
    print(f"Violations: {len(validation['violations'])}")
    
    if validation['violations']:
        print(f"\nViolations:")
        for violation in validation['violations']:
            print(f"   {violation['symbol']}: {violation['reason']}")
    
    print(f"\nLiquidity breakdown:")
    for tier, count in validation['liquidity_breakdown'].items():
        weight = validation['weight_by_tier'][tier]
        if count > 0:
            print(f"   {tier}: {count} positions, {weight:.1%} weight")
    
    # Governor metrics
    print(f"\n📈 GOVERNOR METRICS")
    print("=" * 40)
    
    metrics = governor.get_governor_metrics()
    for key, value in metrics.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"   {sub_key}: {sub_value}")
        elif isinstance(value, float):
            if 'rate' in key:
                print(f"{key}: {value:.1%}")
            else:
                print(f"{key}: {value:.3f}")
        else:
            print(f"{key}: {value}")

if __name__ == "__main__":
    main()
