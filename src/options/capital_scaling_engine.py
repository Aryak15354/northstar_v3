"""
Capital Scaling Engine for Options Trading System

Dynamically adjusts position size based on performance:
- Scales UP with profit milestones (+0.25% risk per 8% profit)
- Scales DOWN with drawdowns (-0.25% at 3%, -0.50% at 5%)
- Enforces hard ceiling (1.5% max risk per trade)
- Requires 8 consecutive weeks before first scaling
- Requires recovery conditions before re-scaling after drawdown

This is performance-based risk adjustment - earn the right to risk more.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Any
from types import SimpleNamespace

logger = logging.getLogger(__name__)


@dataclass
class ScalingState:
    """Current capital scaling state"""
    current_risk_pct: float           # Current risk per trade (%)
    equity_high_water_mark: float     # Highest equity reached
    current_equity: float              # Current equity
    current_drawdown_pct: float        # Current drawdown from HWM
    
    # Profit scaling tracking
    profit_milestones_achieved: int   # Number of 8% milestones hit
    last_milestone_equity: float      # Equity at last milestone
    
    # Drawdown tracking
    in_drawdown: bool                  # Currently in drawdown state
    drawdown_level: int                # 0=none, 1=3%, 2=5%
    recovery_equity_target: float      # Equity needed for recovery
    recovery_profitable_trades: int    # Profitable trades since recovery started
    
    # Time tracking
    trading_start_date: datetime       # When trading started
    weeks_trading: int                 # Consecutive weeks of trading
    can_scale: bool                    # Whether scaling is allowed (8+ weeks)
    
    # Metadata
    last_updated: datetime
    scaling_history: List[Tuple[datetime, float, str]]  # (timestamp, risk_pct, reason)

    @property
    def risk_per_trade_pct(self) -> float:
        """
        Legacy alias in decimal form (e.g., 0.01 for 1%).
        Supports both percent-point and decimal internal states.
        """
        raw = float(self.current_risk_pct)
        return raw / 100.0 if raw >= 0.2 else raw

    @property
    def scaling_factor(self) -> float:
        """Legacy alias used by older integration tests."""
        if not self.scaling_history:
            return 1.0
        base_raw = float(self.scaling_history[0][1])
        base = base_raw / 100.0 if base_raw >= 0.2 else base_raw
        if base <= 1e-9:
            return 1.0
        return max(0.0, self.risk_per_trade_pct / base)

    @property
    def weeks_live(self) -> int:
        """Legacy alias for weeks trading."""
        return int(self.weeks_trading)

    @weeks_live.setter
    def weeks_live(self, value: int) -> None:
        self.weeks_trading = int(value)

    @property
    def consecutive_profitable_trades(self) -> int:
        """Legacy alias for recovery trade counter."""
        return int(self.recovery_profitable_trades)

    @consecutive_profitable_trades.setter
    def consecutive_profitable_trades(self, value: int) -> None:
        self.recovery_profitable_trades = int(value)


class CapitalScalingEngine:
    """
    Manages dynamic capital scaling based on performance
    
    Rules:
    1. Base risk: 1.0% per trade
    2. Profit scaling: +0.25% per 8% net profit milestone
    3. Risk ceiling: 1.5% max (hard cap)
    4. Drawdown de-scaling:
       - 3% drawdown: -0.25% risk
       - 5% drawdown: -0.50% risk
    5. Recovery condition: Equity at previous HWM + 2 profitable trades
    6. Time requirement: 8 consecutive weeks before first scaling
    """
    
    def __init__(self, config: Any = None, **legacy_kwargs: Any):
        """
        Initialize capital scaling engine
        
        Args:
            config: Capital scaling configuration
        """
        if config is None and legacy_kwargs:
            self.config = self._build_legacy_config(legacy_kwargs)
        else:
            self.config = config

        self.state: Optional[ScalingState] = None

        # Legacy constructor path keeps internal mutable state initialized.
        if legacy_kwargs:
            base_capital = float(legacy_kwargs.get("base_capital", 500000.0))
            self.state = self.initialize_state(
                starting_capital=base_capital,
                trading_start_date=datetime.utcnow(),
            )
        logger.info("CapitalScalingEngine initialized")

    def _build_legacy_config(self, params: Any) -> Any:
        """Build unified config object from legacy keyword arguments."""
        capital = SimpleNamespace(
            base_risk_pct=float(params.get("base_risk_pct", 1.0)),
            max_risk_pct=float(params.get("max_risk_pct", 1.5)),
            min_risk_pct=float(params.get("min_risk_pct", 0.5)),
        )
        scaling = SimpleNamespace(
            profit_milestone_pct=float(params.get("profit_milestone_pct", 0.08)),
            profit_scaling_increment=float(params.get("profit_scaling_increment", 0.25)),
            drawdown_threshold_1=self._normalize_threshold_decimal(
                float(params.get("drawdown_threshold_1", 0.03))
            ),
            drawdown_threshold_2=self._normalize_threshold_decimal(
                float(params.get("drawdown_threshold_2", 0.05))
            ),
            drawdown_descaling_1=float(params.get("drawdown_descaling_1", 0.25)),
            drawdown_descaling_2=float(params.get("drawdown_descaling_2", 0.50)),
            min_weeks_before_scaling=int(params.get("min_weeks_before_scaling", 8)),
            recovery_profitable_trades=int(params.get("recovery_profitable_trades", 2)),
        )
        return SimpleNamespace(capital=capital, capital_scaling=scaling)

    @staticmethod
    def _normalize_risk_value(value: float, *, reference: float) -> float:
        """
        Normalize absolute or delta risk values to the same representation as
        `reference`.

        Supported inputs:
        - percent-points (1.5 means 1.5%)
        - decimal fractions (0.015 means 1.5%)
        """
        v = float(value)
        reference_value = float(reference)
        if abs(reference_value) >= 0.2:
            return v * 100.0 if 0.0 < abs(v) < 0.2 else v
        return v / 100.0 if abs(v) >= 0.2 else v

    @staticmethod
    def _normalize_threshold_decimal(value: float) -> float:
        """
        Normalize drawdown thresholds expressed either as:
        - decimal (0.03 means 3%)
        - percent (3 means 3%)
        """
        v = float(value)
        return v / 100.0 if abs(v) > 1.0 else v

    def _capital_cfg(self) -> Any:
        cfg = self.config
        if hasattr(cfg, "capital"):
            return cfg.capital
        # Some callers pass capital_scaling-only config objects.
        return SimpleNamespace(
            base_risk_pct=float(getattr(cfg, "base_risk_pct", 1.0)),
            max_risk_pct=float(getattr(cfg, "max_risk_pct", 1.5)),
            min_risk_pct=float(getattr(cfg, "min_risk_pct", 0.5)),
        )

    def _scaling_cfg(self) -> Any:
        cfg = self.config
        if hasattr(cfg, "capital_scaling"):
            return cfg.capital_scaling
        return cfg
    
    def initialize_state(
        self,
        starting_capital: float,
        trading_start_date: datetime
    ) -> ScalingState:
        """
        Initialize scaling state for new trading account
        
        Args:
            starting_capital: Initial capital
            trading_start_date: When trading started
        
        Returns:
            Initial ScalingState
        """
        capital_cfg = self._capital_cfg()
        # Ensure trading_start_date is timezone-naive
        if trading_start_date.tzinfo:
            trading_start_date = trading_start_date.replace(tzinfo=None)
        
        state = ScalingState(
            current_risk_pct=float(capital_cfg.base_risk_pct),
            equity_high_water_mark=starting_capital,
            current_equity=starting_capital,
            current_drawdown_pct=0.0,
            profit_milestones_achieved=0,
            last_milestone_equity=starting_capital,
            in_drawdown=False,
            drawdown_level=0,
            recovery_equity_target=starting_capital,
            recovery_profitable_trades=0,
            trading_start_date=trading_start_date,
            weeks_trading=0,
            can_scale=False,
            last_updated=datetime.utcnow(),
            scaling_history=[(datetime.utcnow(), float(capital_cfg.base_risk_pct), "Initial state")]
        )
        self.state = state
        logger.info(f"Initialized scaling state: capital={starting_capital:,.0f}, risk={state.current_risk_pct}%")
        return state
    
    def update_state(
        self,
        state: ScalingState,
        current_equity: float,
        last_trade_profitable: Optional[bool] = None,
        recent_trades_profitable: Optional[int] = None
    ) -> ScalingState:
        """
        Update scaling state based on current equity
        
        Args:
            state: Current scaling state
            current_equity: Current account equity
            last_trade_profitable: Whether last trade was profitable (for recovery tracking)
        
        Returns:
            Updated ScalingState
        """
        logger.info(f"Updating scaling state: equity={current_equity:,.0f}, HWM={state.equity_high_water_mark:,.0f}")
        
        # Update current equity
        state.current_equity = current_equity
        
        # Update weeks trading
        scaling_cfg = self._scaling_cfg()
        capital_cfg = self._capital_cfg()

        # Preserve explicit legacy overrides (tests/manual simulation) while
        # still advancing naturally from trading_start_date in production.
        calculated_weeks = self._calculate_weeks_trading(state.trading_start_date)
        state.weeks_trading = max(int(state.weeks_trading), int(calculated_weeks))
        state.can_scale = state.weeks_trading >= int(getattr(scaling_cfg, "min_weeks_before_scaling", 8))
        
        # Update high water mark if new high
        if current_equity > state.equity_high_water_mark:
            logger.info(f"New high water mark: {current_equity:,.0f} (previous: {state.equity_high_water_mark:,.0f})")
            state.equity_high_water_mark = current_equity
            
            # Exit drawdown state if we were in one
            if state.in_drawdown:
                logger.info("Exited drawdown state - new high water mark")
                state.in_drawdown = False
                state.drawdown_level = 0
        
        # Calculate current drawdown
        state.current_drawdown_pct = (state.equity_high_water_mark - current_equity) / state.equity_high_water_mark
        
        # Check for profit milestones
        self._check_profit_milestones(state)
        
        # Check for drawdown de-scaling
        self._check_drawdown_descaling(state)
        
        # Check for recovery
        if recent_trades_profitable is not None and recent_trades_profitable > 0:
            state.recovery_profitable_trades += int(recent_trades_profitable)
            # Already counted as a batch; do not double-increment below.
            last_trade_profitable = False
        if state.in_drawdown:
            self._check_recovery(state, last_trade_profitable)
        
        # Enforce risk ceiling
        state.current_risk_pct = min(
            state.current_risk_pct,
            self._normalize_risk_value(
                float(capital_cfg.max_risk_pct),
                reference=float(capital_cfg.base_risk_pct),
            ),
        )
        
        state.last_updated = datetime.utcnow()
        self.state = state
        
        logger.info(
            f"State updated: risk={state.current_risk_pct}%, drawdown={state.current_drawdown_pct:.1%}, "
            f"milestones={state.profit_milestones_achieved}, can_scale={state.can_scale}"
        )
        
        return state
    
    def get_position_size(
        self,
        state: ScalingState,
        strategy_max_loss: float
    ) -> float:
        """
        Calculate position size based on current risk percentage
        
        Args:
            state: Current scaling state
            strategy_max_loss: Max loss for the strategy (per lot)
        
        Returns:
            Position size (number of lots)
        """
        # Risk amount = current_equity × risk%
        risk_amount = state.current_equity * self._risk_pct_decimal(state.current_risk_pct)
        
        # Position size = risk_amount / max_loss_per_lot
        if strategy_max_loss <= 0:
            logger.warning("Invalid strategy max loss, using minimum position size")
            return 1.0
        
        position_size = risk_amount / strategy_max_loss
        
        # Round to nearest lot (minimum 1)
        position_size = max(1.0, round(position_size))
        
        logger.debug(
            f"Position size: {position_size:.0f} lots "
            f"(risk={state.current_risk_pct}%, amount={risk_amount:,.0f}, max_loss={strategy_max_loss:,.0f})"
        )
        
        return position_size
    
    def _calculate_weeks_trading(self, start_date: datetime) -> int:
        """Calculate number of consecutive weeks trading"""
        # Ensure both datetimes are naive for comparison
        now = datetime.utcnow().replace(tzinfo=None)
        start = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        weeks = (now - start).days // 7
        return max(0, weeks)

    @staticmethod
    def _risk_pct_decimal(risk_pct: float) -> float:
        """
        Normalize risk representation:
        - 1.0 means 1%
        - 0.01 means 1%
        """
        raw = float(risk_pct)
        return raw / 100.0 if raw >= 0.2 else raw
    
    def _check_profit_milestones(self, state: ScalingState) -> None:
        """
        Check if profit milestones have been achieved
        
        Milestone: 8% net profit from last milestone
        Reward: +0.25% risk per milestone
        """
        if not state.can_scale:
            return
        
        if state.in_drawdown:
            # No scaling up during drawdown
            return
        
        scaling_cfg = self._scaling_cfg()
        capital_cfg = self._capital_cfg()
        milestone_pct = float(getattr(scaling_cfg, "profit_milestone_pct", 0.08))
        scaling_increment = self._normalize_risk_value(
            float(getattr(scaling_cfg, "profit_scaling_increment", 0.25)),
            reference=float(capital_cfg.base_risk_pct),
        )
        
        # Apply one or more milestone steps if equity has moved enough in a
        # single update (legacy tests expect this behavior for large jumps).
        max_risk = self._normalize_risk_value(
            float(capital_cfg.max_risk_pct),
            reference=float(capital_cfg.base_risk_pct),
        )
        while state.last_milestone_equity > 0:
            profit_since_milestone = (
                state.current_equity - state.last_milestone_equity
            ) / state.last_milestone_equity
            if profit_since_milestone < milestone_pct:
                break

            state.profit_milestones_achieved += 1

            # Advance milestone anchor in fixed steps; clamp at current equity.
            next_anchor = state.last_milestone_equity * (1.0 + milestone_pct)
            state.last_milestone_equity = min(next_anchor, state.current_equity)

            old_risk = state.current_risk_pct
            state.current_risk_pct = min(state.current_risk_pct + scaling_increment, max_risk)

            reason = (
                f"Profit milestone {state.profit_milestones_achieved}: "
                f"+{milestone_pct:.1%} step"
            )
            state.scaling_history.append((datetime.utcnow(), state.current_risk_pct, reason))

            logger.info(
                f"PROFIT MILESTONE ACHIEVED: {state.profit_milestones_achieved} "
                f"(risk: {old_risk}% → {state.current_risk_pct}%)"
            )

            # No further scaling once ceiling reached.
            if state.current_risk_pct >= max_risk:
                break
    
    def _check_drawdown_descaling(self, state: ScalingState) -> None:
        """
        Check if drawdown requires de-scaling
        
        Thresholds:
        - 3% drawdown: -0.25% risk
        - 5% drawdown: -0.50% risk (total)
        """
        scaling_cfg = self._scaling_cfg()
        capital_cfg = self._capital_cfg()
        threshold_1 = self._normalize_threshold_decimal(
            float(getattr(scaling_cfg, "drawdown_threshold_1", 0.03))
        )
        threshold_2 = self._normalize_threshold_decimal(
            float(getattr(scaling_cfg, "drawdown_threshold_2", 0.05))
        )
        descaling_1 = self._normalize_risk_value(
            float(getattr(scaling_cfg, "drawdown_descaling_1", 0.25)),
            reference=float(capital_cfg.base_risk_pct),
        )
        descaling_2 = self._normalize_risk_value(
            float(getattr(scaling_cfg, "drawdown_descaling_2", 0.50)),
            reference=float(capital_cfg.base_risk_pct),
        )
        base_risk = self._normalize_risk_value(
            float(capital_cfg.base_risk_pct),
            reference=float(capital_cfg.base_risk_pct),
        )
        min_risk = self._normalize_risk_value(
            float(capital_cfg.min_risk_pct),
            reference=float(capital_cfg.base_risk_pct),
        )
        
        # Check 5% drawdown (more severe)
        if state.current_drawdown_pct >= threshold_2 and state.drawdown_level < 2:
            old_risk = state.current_risk_pct
            state.current_risk_pct = base_risk - descaling_2
            state.current_risk_pct = max(state.current_risk_pct, min_risk)
            
            state.in_drawdown = True
            state.drawdown_level = 2
            state.recovery_equity_target = state.equity_high_water_mark
            state.recovery_profitable_trades = 0
            
            reason = f"Drawdown de-scaling: {state.current_drawdown_pct:.1%} drawdown (5% threshold)"
            state.scaling_history.append((datetime.utcnow(), state.current_risk_pct, reason))
            
            logger.warning(
                f"DRAWDOWN DE-SCALING (5%): drawdown={state.current_drawdown_pct:.1%}, "
                f"risk: {old_risk}% → {state.current_risk_pct}%"
            )
        
        # Check 3% drawdown (less severe)
        elif state.current_drawdown_pct >= threshold_1 and state.drawdown_level < 1:
            old_risk = state.current_risk_pct
            state.current_risk_pct = base_risk - descaling_1
            state.current_risk_pct = max(state.current_risk_pct, min_risk)
            
            state.in_drawdown = True
            state.drawdown_level = 1
            state.recovery_equity_target = state.equity_high_water_mark
            state.recovery_profitable_trades = 0
            
            reason = f"Drawdown de-scaling: {state.current_drawdown_pct:.1%} drawdown (3% threshold)"
            state.scaling_history.append((datetime.utcnow(), state.current_risk_pct, reason))
            
            logger.warning(
                f"DRAWDOWN DE-SCALING (3%): drawdown={state.current_drawdown_pct:.1%}, "
                f"risk: {old_risk}% → {state.current_risk_pct}%"
            )
    
    def _check_recovery(self, state: ScalingState, last_trade_profitable: Optional[bool]) -> None:
        """
        Check if recovery conditions are met
        
        Recovery conditions:
        1. Equity back at previous high water mark
        2. 2 profitable trades since recovery started
        """
        scaling_cfg = self._scaling_cfg()
        capital_cfg = self._capital_cfg()
        required_profitable_trades = int(getattr(scaling_cfg, "recovery_profitable_trades", 2))
        
        # Track profitable trades
        if last_trade_profitable:
            state.recovery_profitable_trades += 1
            logger.info(f"Recovery progress: {state.recovery_profitable_trades}/{required_profitable_trades} profitable trades")
        
        # Check recovery conditions
        equity_recovered = state.current_equity >= state.recovery_equity_target
        trades_recovered = state.recovery_profitable_trades >= required_profitable_trades
        
        if equity_recovered and trades_recovered:
            # Recovery complete!
            old_risk = state.current_risk_pct
            state.current_risk_pct = self._normalize_risk_value(
                float(capital_cfg.base_risk_pct),
                reference=float(capital_cfg.base_risk_pct),
            )
            
            state.in_drawdown = False
            state.drawdown_level = 0
            state.recovery_profitable_trades = 0
            
            # Reset milestone tracking
            state.last_milestone_equity = state.current_equity
            
            reason = "Recovery complete: equity recovered + 2 profitable trades"
            state.scaling_history.append((datetime.utcnow(), state.current_risk_pct, reason))
            
            logger.info(
                f"RECOVERY COMPLETE: equity={state.current_equity:,.0f}, "
                f"risk: {old_risk}% → {state.current_risk_pct}%"
            )

    # ---------- Legacy compatibility helpers ----------
    def get_state(self) -> ScalingState:
        """Legacy API: return mutable internal state."""
        if self.state is None:
            self.state = self.initialize_state(
                starting_capital=500000.0,
                trading_start_date=datetime.utcnow(),
            )
        return self.state

    def update_equity(self, current_equity: float) -> ScalingState:
        """Legacy API wrapper around update_state."""
        state = self.get_state()
        self.state = self.update_state(state, current_equity=current_equity)
        return self.state

    def record_trade_result(self, was_profitable: bool) -> None:
        """Legacy API to increment recovery trade counter."""
        state = self.get_state()
        if was_profitable:
            state.recovery_profitable_trades += 1
        else:
            state.recovery_profitable_trades = 0
        self.state = state

    def calculate_position_size(self, max_loss: float, lot_size: int) -> int:
        """
        Legacy API: returns quantity rounded to lot size.
        """
        state = self.get_state()
        lots = self.get_position_size(state, strategy_max_loss=max_loss)
        quantity = max(lot_size, int(round(lots)) * int(lot_size))
        return quantity

    def get_summary(self) -> dict:
        """Legacy API summary view."""
        state = self.get_state()
        return {
            "current_risk_pct": state.current_risk_pct,
            "equity_high_water_mark": state.equity_high_water_mark,
            "current_equity": state.current_equity,
            "weeks_live": state.weeks_trading,
            "drawdown_pct": state.current_drawdown_pct,
            "can_scale": state.can_scale,
            "in_drawdown": state.in_drawdown,
        }


if __name__ == "__main__":
    # Test capital scaling engine
    import logging
    from src.options.config_loader import get_config
    
    logging.basicConfig(level=logging.INFO)
    
    config = get_config()
    engine = CapitalScalingEngine(config)
    
    # Initialize state
    starting_capital = 500000
    start_date = datetime.utcnow() - timedelta(weeks=10)  # 10 weeks ago
    
    state = engine.initialize_state(starting_capital, start_date)
    
    print(f"\nInitial State:")
    print(f"  Capital: ₹{state.current_equity:,.0f}")
    print(f"  Risk: {state.current_risk_pct}%")
    print(f"  Can Scale: {state.can_scale}")
    
    # Simulate profit milestone
    print(f"\n--- Simulating 8% Profit ---")
    new_equity = starting_capital * 1.08
    state = engine.update_state(state, new_equity)
    
    print(f"  New Equity: ₹{state.current_equity:,.0f}")
    print(f"  New Risk: {state.current_risk_pct}%")
    print(f"  Milestones: {state.profit_milestones_achieved}")
    
    # Simulate drawdown
    print(f"\n--- Simulating 5% Drawdown ---")
    drawdown_equity = state.equity_high_water_mark * 0.95
    state = engine.update_state(state, drawdown_equity)
    
    print(f"  New Equity: ₹{state.current_equity:,.0f}")
    print(f"  Drawdown: {state.current_drawdown_pct:.1%}")
    print(f"  New Risk: {state.current_risk_pct}%")
    print(f"  In Drawdown: {state.in_drawdown}")
    
    # Simulate recovery
    print(f"\n--- Simulating Recovery ---")
    recovery_equity = state.equity_high_water_mark
    state = engine.update_state(state, recovery_equity, last_trade_profitable=True)
    state = engine.update_state(state, recovery_equity, last_trade_profitable=True)
    
    print(f"  New Equity: ₹{state.current_equity:,.0f}")
    print(f"  New Risk: {state.current_risk_pct}%")
    print(f"  In Drawdown: {state.in_drawdown}")
    print(f"  Recovery Trades: {state.recovery_profitable_trades}")
    
    # Test position sizing
    print(f"\n--- Position Sizing ---")
    strategy_max_loss = 10000
    position_size = engine.get_position_size(state, strategy_max_loss)
    print(f"  Strategy Max Loss: ₹{strategy_max_loss:,.0f}")
    print(f"  Position Size: {position_size:.0f} lots")
    print(f"  Risk Amount: ₹{state.current_equity * (state.current_risk_pct / 100):,.0f}")
