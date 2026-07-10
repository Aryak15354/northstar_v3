"""
Position Management System for Options Trading

Tracks open positions, calculates mark-to-market, monitors Greeks,
and implements exit logic with precedence rules.

Philosophy: Disciplined position management with clear exit rules.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, List, Dict, Optional, Tuple
from enum import Enum
import pandas as pd

from src.options.strategy_generator import OptionStrategy, OptionLeg, Greeks
from src.volatility.regime_detector import VolatilityRegime
from src.options.config_loader import ExitRulesConfig, GreekSafetyBandsConfig

logger = logging.getLogger("options.position_manager")

LONG_VOL_HEDGE_STRATEGY_TYPES = {
    "long_straddle",
    "long_strangle",
    "bear_put_spread",
}


class ExitReason(Enum):
    """Exit reasons with precedence order"""
    STOP_LOSS = "stop_loss"  # Highest priority
    GAMMA_ESCALATION = "gamma_escalation"
    REGIME_FLIP = "regime_flip"
    TIME_DECAY = "time_decay"
    PROFIT_TARGET = "profit_target"  # Lowest priority
    GREEK_VIOLATION = "greek_violation"
    MANUAL = "manual"


@dataclass
class PositionLeg:
    """Individual option leg within a position"""
    symbol: str
    strike: float
    option_type: str  # "call" or "put"
    action: str  # "buy" or "sell"
    quantity: int
    entry_premium: float
    current_premium: float
    entry_iv: float
    current_iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    
    def calculate_pnl(self) -> float:
        """Calculate P&L for this leg"""
        if self.action.upper() == "SELL":
            # For SELL: profit when premium decreases
            return (self.entry_premium - self.current_premium) * self.quantity
        else:
            # For BUY: profit when premium increases
            return (self.current_premium - self.entry_premium) * self.quantity
    
    def get_action_multiplier(self) -> int:
        """Get multiplier for P&L calculation (+1 for buy, -1 for sell)"""
        return 1 if self.action.upper() == "BUY" else -1
    
    def calculate_current_value(self) -> float:
        """Calculate current value of this leg (what we would pay/receive to close)"""
        return self.current_premium * self.quantity * self.get_action_multiplier()
    
    def calculate_entry_value(self) -> float:
        """Calculate entry value of this leg (what we paid/received to open)"""
        return self.entry_premium * self.quantity * self.get_action_multiplier()


@dataclass
class Position:
    """Open or closed options position"""
    position_id: str
    strategy_type: str
    regime_at_entry: VolatilityRegime
    legs: List[PositionLeg]
    entry_time: datetime
    expiry: date
    max_loss: float
    max_profit: float
    entry_credit_debit: float
    underlying: str = ""
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: Optional[float] = None
    days_held: int = 0
    greeks: Optional[Greeks] = None
    entry_greeks: Optional[Greeks] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_open(self) -> bool:
        """Check if position is still open"""
        return self.exit_time is None
    
    def is_short_vol(self) -> bool:
        """Check if this is a short-vol strategy"""
        return str(self.strategy_type or "").strip().lower() in {
            "iron_condor",
            "iron_butterfly",
            "short_strangle",
            "calendar_spread",
        }

    def is_long_vol_hedge(self) -> bool:
        """Check if this is a long-vol hedge strategy."""
        return str(self.strategy_type or "").strip().lower() in LONG_VOL_HEDGE_STRATEGY_TYPES
    
    def days_to_expiry(self, current_date: date) -> int:
        """Calculate days to expiry"""
        return (self.expiry - current_date).days
    
    def pnl_pct_of_max_loss(self) -> float:
        """Calculate P&L as percentage of max loss"""
        if self.max_loss == 0:
            return 0.0
        pnl = self.realized_pnl if self.realized_pnl is not None else self.unrealized_pnl
        return pnl / self.max_loss
    
    def pnl_pct_of_max_profit(self) -> float:
        """Calculate P&L as percentage of max profit"""
        if self.max_profit == 0:
            return 0.0
        pnl = self.realized_pnl if self.realized_pnl is not None else self.unrealized_pnl
        return pnl / self.max_profit


@dataclass
class ExitSignal:
    """Signal to exit a position"""
    should_exit: bool
    reason: ExitReason
    details: str
    priority: int  # Lower number = higher priority
    
    @staticmethod
    def get_priority(reason: ExitReason) -> int:
        """Get priority for exit reason (lower = higher priority)"""
        priority_map = {
            ExitReason.STOP_LOSS: 1,
            ExitReason.GAMMA_ESCALATION: 2,
            ExitReason.REGIME_FLIP: 3,
            ExitReason.TIME_DECAY: 4,
            ExitReason.PROFIT_TARGET: 5,
            ExitReason.GREEK_VIOLATION: 6,
            ExitReason.MANUAL: 7
        }
        return priority_map.get(reason, 99)


class PositionManager:
    """
    Manages options positions lifecycle: open, MTM, exit monitoring, close.
    
    Responsibilities:
    - Track open and closed positions
    - Calculate mark-to-market daily
    - Monitor exit conditions with precedence
    - Aggregate portfolio Greeks
    - Enforce Greek safety bands
    """
    
    def __init__(
        self,
        exit_config: ExitRulesConfig,
        greek_config: GreekSafetyBandsConfig
    ):
        """
        Initialize position manager
        
        Args:
            exit_config: Exit rules configuration
            greek_config: Greek safety bands configuration
        """
        self.exit_config = exit_config
        self.greek_config = greek_config
        
        # Position tracking
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        
        
        # Gap 7: State bridge for syncing to UnifiedState
        self.options_bridge = None
        
        logger.info("PositionManager initialized")
    
    def open_position(
        self,
        strategy: OptionStrategy,
        entry_time: datetime
    ) -> Position:
        """
        Open a new position from a strategy
        
        Args:
            strategy: Option strategy to execute
            entry_time: Entry timestamp
        
        Returns:
            Position: Newly opened position
        """
        # Generate position ID with microseconds to ensure uniqueness
        position_id = f"POS_{entry_time.strftime('%Y%m%d_%H%M%S_%f')}_{strategy.strategy_type.value if hasattr(strategy.strategy_type, 'value') else strategy.strategy_type}"
        
        # Convert strategy legs to position legs
        position_legs = []
        for leg in strategy.legs:
            # Create symbol from instrument_key or construct it
            symbol = leg.instrument_key if leg.instrument_key else f"{strategy.underlying}_{leg.strike}_{leg.option_type}"
            
            position_leg = PositionLeg(
                symbol=symbol,
                strike=leg.strike,
                option_type=leg.option_type,
                action=leg.action,
                quantity=leg.quantity,
                entry_premium=leg.premium,
                current_premium=leg.premium,
                entry_iv=0.0,  # IV not stored in OptionLeg, will be updated on MTM
                current_iv=0.0,
                delta=leg.greeks.delta,
                gamma=leg.greeks.gamma,
                theta=leg.greeks.theta,
                vega=leg.greeks.vega
            )
            position_legs.append(position_leg)
        
        # Create position
        position = Position(
            position_id=position_id,
            strategy_type=strategy.strategy_type.value if hasattr(strategy.strategy_type, 'value') else strategy.strategy_type,
            underlying=str(strategy.underlying or ""),
            regime_at_entry=strategy.regime,
            legs=position_legs,
            entry_time=entry_time,
            expiry=strategy.expiry_date.date() if hasattr(strategy.expiry_date, 'date') else strategy.expiry_date,
            max_loss=strategy.max_loss,
            max_profit=strategy.max_profit,
            entry_credit_debit=strategy.net_credit_debit,
            current_value=strategy.net_credit_debit,
            unrealized_pnl=0.0,
            greeks=strategy.portfolio_greeks,
            entry_greeks=strategy.portfolio_greeks,
            days_held=0
        )
        
        # Store position
        self.open_positions[position_id] = position
        
        logger.info(
            f"Opened position {position_id}: {strategy.strategy_type} "
            f"with {len(position_legs)} legs, max loss: ₹{strategy.max_loss:,.0f}"
        )
        
        return position
    
    def update_position_mtm(
        self,
        position: Position,
        current_chain: pd.DataFrame,
        current_time: datetime
    ) -> Position:
        """
        Update position mark-to-market with current option prices
        
        Args:
            position: Position to update
            current_chain: Current option chain data
            current_time: Current timestamp
        
        Returns:
            Position: Updated position
        """
        if not position.is_open():
            logger.warning(f"Cannot update MTM for closed position {position.position_id}")
            return position
        
        # Update each leg with current prices
        total_pnl = 0.0
        portfolio_delta = 0.0
        portfolio_gamma = 0.0
        portfolio_theta = 0.0
        portfolio_vega = 0.0
        
        for leg in position.legs:
            # Prefer exact instrument-key match when available; fallback to
            # strike/type — but MUST also match expiry, otherwise on a chain that
            # carries multiple expiries (weekly + monthly NIFTY is the norm) the
            # strike/type fallback can pick a DIFFERENT expiry's premium (iloc[0]
            # is arbitrary), corrupting this leg's MTM and the exit logic keyed on
            # pnl_pct_of_max_loss.
            chain_row = pd.DataFrame()
            if "instrument_key" in current_chain.columns and leg.symbol:
                chain_row = current_chain[current_chain["instrument_key"] == leg.symbol]
            if chain_row.empty:
                base_mask = (
                    (current_chain['strike'] == leg.strike)
                    & (current_chain['option_type'] == leg.option_type)
                )
                if 'expiry' in current_chain.columns:
                    chain_exp = pd.to_datetime(current_chain['expiry'], errors='coerce').dt.date
                    exp_match = current_chain[base_mask & (chain_exp == position.expiry)]
                    if not exp_match.empty:
                        chain_row = exp_match
                    else:
                        # No exact-expiry row: fall back to strike/type but warn —
                        # marking against the wrong expiry silently is worse.
                        chain_row = current_chain[base_mask]
                        if not chain_row.empty:
                            logger.warning(
                                "MTM fallback used strike/type WITHOUT matching expiry for "
                                "%s %s@%s (position expiry %s not in chain)",
                                leg.option_type, leg.strike, position.underlying, position.expiry,
                            )
                else:
                    chain_row = current_chain[base_mask]

            if not chain_row.empty:
                # Update leg with current data
                row = chain_row.iloc[0]
                def _num_or_default(raw_value: object, default_value: float) -> float:
                    try:
                        parsed = float(raw_value)
                        return default_value if pd.isna(parsed) else parsed
                    except Exception:
                        return default_value

                if 'premium' in row:
                    leg.current_premium = _num_or_default(row['premium'], leg.current_premium)
                elif 'ltp' in row:
                    leg.current_premium = _num_or_default(row['ltp'], leg.current_premium)
                elif 'bid' in row and 'ask' in row:
                    bid = _num_or_default(row['bid'], 0.0)
                    ask = _num_or_default(row['ask'], 0.0)
                    if bid > 0 and ask > 0:
                        leg.current_premium = (bid + ask) / 2.0
                else:
                    leg.current_premium = leg.current_premium
                leg.current_iv = _num_or_default(row.get('iv', leg.current_iv), leg.current_iv)
                leg.delta = _num_or_default(row.get('delta', leg.delta), leg.delta)
                leg.gamma = _num_or_default(row.get('gamma', leg.gamma), leg.gamma)
                leg.theta = _num_or_default(row.get('theta', leg.theta), leg.theta)
                leg.vega = _num_or_default(row.get('vega', leg.vega), leg.vega)

            # Aggregate Greeks (considering action multiplier).
            # If no row is matched, keep last known Greeks instead of zeroing the book.
            multiplier = leg.get_action_multiplier()
            portfolio_delta += leg.delta * leg.quantity * multiplier
            portfolio_gamma += leg.gamma * leg.quantity * multiplier
            portfolio_theta += leg.theta * leg.quantity * multiplier
            portfolio_vega += leg.vega * leg.quantity * multiplier
            
            # Calculate P&L for this leg
            total_pnl += leg.calculate_pnl()
        
        # Update position
        position.current_value = sum(leg.calculate_current_value() for leg in position.legs)
        position.unrealized_pnl = total_pnl
        position.days_held = (current_time.date() - position.entry_time.date()).days
        position.greeks = Greeks(
            delta=portfolio_delta,
            gamma=portfolio_gamma,
            theta=portfolio_theta,
            vega=portfolio_vega
        )
        
        logger.debug(
            f"Updated MTM for {position.position_id}: "
            f"Current value: ₹{position.current_value:,.0f}, "
            f"Unrealized P&L: ₹{position.unrealized_pnl:,.0f}"
        )
        
        return position
    
    def check_exit_conditions(
        self,
        position: Position,
        current_regime: VolatilityRegime,
        current_date: date,
        current_time: Optional[datetime] = None,
        regime_flip_exit_allowed: bool = True,
        minimum_hold_minutes: float = 0.0,
    ) -> Optional[ExitSignal]:
        """
        Check if position should be exited based on exit rules
        
        Args:
            position: Position to check
            current_regime: Current market regime
            current_date: Current date
        
        Returns:
            Optional[ExitSignal]: Exit signal if should exit, None otherwise
        """
        if not position.is_open():
            return None
        
        exit_signals = []
        effective_regime_flip_exit_allowed = bool(regime_flip_exit_allowed)
        if effective_regime_flip_exit_allowed and minimum_hold_minutes > 0.0 and current_time is not None:
            entry_time = position.entry_time
            comparison_time = current_time
            if getattr(entry_time, "tzinfo", None) is None and getattr(comparison_time, "tzinfo", None) is not None:
                tz = comparison_time.tzinfo
                if hasattr(tz, "localize"):
                    entry_time = tz.localize(entry_time)
                else:
                    entry_time = entry_time.replace(tzinfo=tz)
            elif getattr(entry_time, "tzinfo", None) is not None and getattr(comparison_time, "tzinfo", None) is None:
                comparison_time = comparison_time.replace(tzinfo=entry_time.tzinfo)
            held_minutes = max((comparison_time - entry_time).total_seconds() / 60.0, 0.0)
            effective_regime_flip_exit_allowed = held_minutes >= float(minimum_hold_minutes)
        
        # 1. Stop Loss (highest priority)
        stop_loss_threshold = -abs(position.max_loss * self.exit_config.stop_loss_pct)
        if position.unrealized_pnl <= stop_loss_threshold:
            exit_signals.append(ExitSignal(
                should_exit=True,
                reason=ExitReason.STOP_LOSS,
                details=f"Stop loss hit: P&L ₹{position.unrealized_pnl:,.0f} <= ₹{stop_loss_threshold:,.0f}",
                priority=ExitSignal.get_priority(ExitReason.STOP_LOSS)
            ))
        
        # 2. Gamma Escalation
        if position.entry_greeks and position.greeks:
            gamma_spike_threshold = abs(position.entry_greeks.gamma * self.greek_config.gamma_escalation['spike_multiplier'])
            if abs(position.greeks.gamma) > gamma_spike_threshold:
                # Check combined conditions
                if position.greeks.theta < 0:  # Negative theta
                    exit_signals.append(ExitSignal(
                        should_exit=True,
                        reason=ExitReason.GAMMA_ESCALATION,
                        details=f"Gamma spike ({position.greeks.gamma:.2f}) + negative theta",
                        priority=ExitSignal.get_priority(ExitReason.GAMMA_ESCALATION)
                    ))
                elif current_regime != position.regime_at_entry and effective_regime_flip_exit_allowed:  # Regime flip
                    exit_signals.append(ExitSignal(
                        should_exit=True,
                        reason=ExitReason.GAMMA_ESCALATION,
                        details=f"Gamma spike ({position.greeks.gamma:.2f}) + regime flip",
                        priority=ExitSignal.get_priority(ExitReason.GAMMA_ESCALATION)
                    ))
        
        # 3. Regime Flip
        if current_regime != position.regime_at_entry and effective_regime_flip_exit_allowed:
            exit_signals.append(ExitSignal(
                should_exit=True,
                reason=ExitReason.REGIME_FLIP,
                details=f"Regime changed from {position.regime_at_entry.value} to {current_regime.value}",
                priority=ExitSignal.get_priority(ExitReason.REGIME_FLIP)
            ))
        
        # 4. Time Decay (expiry approaching)
        days_to_expiry = position.days_to_expiry(current_date)
        if days_to_expiry <= self.exit_config.days_before_expiry:
            exit_signals.append(ExitSignal(
                should_exit=True,
                reason=ExitReason.TIME_DECAY,
                details=f"Expiry in {days_to_expiry} days (threshold: {self.exit_config.days_before_expiry})",
                priority=ExitSignal.get_priority(ExitReason.TIME_DECAY)
            ))
        
        # 5. Profit Target (lowest priority)
        profit_target = position.max_profit * self.exit_config.profit_target_pct
        if position.unrealized_pnl >= profit_target:
            exit_signals.append(ExitSignal(
                should_exit=True,
                reason=ExitReason.PROFIT_TARGET,
                details=f"Profit target hit: P&L ₹{position.unrealized_pnl:,.0f} >= ₹{profit_target:,.0f}",
                priority=ExitSignal.get_priority(ExitReason.PROFIT_TARGET)
            ))
        
        # 6. Greek Violations
        if position.greeks:
            violations = []
            is_long_vol_hedge = position.is_long_vol_hedge()
            contracts_scale = max(
                1.0,
                float(sum(abs(float(leg.quantity)) for leg in position.legs)),
            )
            norm_delta = float(position.greeks.delta) / contracts_scale
            norm_theta = float(position.greeks.theta) / contracts_scale
            norm_vega = float(position.greeks.vega) / contracts_scale
            delta_min = self.greek_config.delta_min
            delta_max = self.greek_config.delta_max
            if is_long_vol_hedge:
                # Long-vol hedges can carry directional bias by design.
                delta_min = min(delta_min, -0.85)
                delta_max = max(delta_max, 0.45)

            if norm_delta < delta_min:
                violations.append(f"Delta(norm) {norm_delta:.2f} < {delta_min}")
            if norm_delta > delta_max:
                violations.append(f"Delta(norm) {norm_delta:.2f} > {delta_max}")
            if (not is_long_vol_hedge) and norm_theta < self.greek_config.theta_min:
                violations.append(f"Theta(norm) {norm_theta:.2f} < {self.greek_config.theta_min}")
            if norm_vega < self.greek_config.vega_min:
                violations.append(f"Vega(norm) {norm_vega:.2f} < {self.greek_config.vega_min}")
            if (not is_long_vol_hedge) and norm_vega > self.greek_config.vega_max:
                violations.append(f"Vega(norm) {norm_vega:.2f} > {self.greek_config.vega_max}")
            
            if violations:
                exit_signals.append(ExitSignal(
                    should_exit=True,
                    reason=ExitReason.GREEK_VIOLATION,
                    details="; ".join(violations),
                    priority=ExitSignal.get_priority(ExitReason.GREEK_VIOLATION)
                ))
        
        # Return highest priority signal
        if exit_signals:
            exit_signals.sort(key=lambda x: x.priority)
            return exit_signals[0]
        
        return None
    
    def close_position(
        self,
        position: Position,
        exit_time: datetime,
        exit_reason: str,
        exit_prices: Optional[Dict[str, float]] = None
    ) -> Position:
        """
        Close a position and calculate final P&L
        
        Args:
            position: Position to close
            exit_time: Exit timestamp
            exit_reason: Reason for exit
            exit_prices: Optional dict of strike -> exit price
        
        Returns:
            Position: Closed position
        """
        if not position.is_open():
            logger.warning(f"Position {position.position_id} already closed")
            return position
        
        # Update exit prices if provided
        if exit_prices:
            for leg in position.legs:
                key = f"{leg.strike}_{leg.option_type}"
                if key in exit_prices:
                    leg.current_premium = exit_prices[key]
        
        # Calculate final P&L
        final_pnl = sum(leg.calculate_pnl() for leg in position.legs)
        final_value = sum(leg.calculate_current_value() for leg in position.legs)
        
        # Update position
        position.exit_time = exit_time
        position.exit_reason = exit_reason
        position.current_value = final_value
        position.realized_pnl = final_pnl
        position.unrealized_pnl = 0.0
        position.days_held = (exit_time.date() - position.entry_time.date()).days
        
        # Move to closed positions
        if position.position_id in self.open_positions:
            del self.open_positions[position.position_id]
        self.closed_positions.append(position)
        
        logger.info(
            f"Closed position {position.position_id}: "
            f"Realized P&L: ₹{position.realized_pnl:,.0f}, "
            f"Days held: {position.days_held}, "
            f"Reason: {exit_reason}"
        )
        
        return position
    
    def calculate_portfolio_greeks(self) -> Greeks:
        """
        Calculate aggregated Greeks across all open positions
        
        Returns:
            Greeks: Portfolio-level Greeks
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        
        for position in self.open_positions.values():
            if position.greeks:
                total_delta += position.greeks.delta
                total_gamma += position.greeks.gamma
                total_theta += position.greeks.theta
                total_vega += position.greeks.vega
        
        return Greeks(
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega
        )
    
    def get_open_positions(self) -> List[Position]:
        """Get list of all open positions"""
        return list(self.open_positions.values())
    
    def get_closed_positions(self) -> List[Position]:
        """Get list of all closed positions"""
        return self.closed_positions
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        return self.open_positions.get(position_id)
    
    def get_total_open_risk(self) -> float:
        """Calculate total max loss across all open positions"""
        return sum(pos.max_loss for pos in self.open_positions.values())
    
    def get_summary(self) -> Dict:
        """Get summary of position manager state"""
        return {
            "open_positions_count": len(self.open_positions),
            "closed_positions_count": len(self.closed_positions),
            "total_open_risk": self.get_total_open_risk(),
            "portfolio_greeks": self.calculate_portfolio_greeks(),
            "total_unrealized_pnl": sum(pos.unrealized_pnl for pos in self.open_positions.values()),
            "total_realized_pnl": sum(pos.realized_pnl for pos in self.closed_positions if pos.realized_pnl)
        }
