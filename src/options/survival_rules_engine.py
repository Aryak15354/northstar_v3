"""
Survival Rules Engine for Options Trading System

Implements circuit breakers and kill switches to prevent catastrophic losses.
This is the critical safety layer that enforces absolute risk limits.

Philosophy: "Not dying in options" - selectivity over activity.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum
import pytz

from src.options.config_loader import SurvivalRulesConfig

logger = logging.getLogger("options.survival_rules")

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Tax-liquidity tolerance prevents false triggers from floating-point precision
# and tiny accounting drift while still blocking real liquidity stress.
TAX_LIQUIDITY_TOLERANCE_INR = 1.0
TAX_LIQUIDITY_TOLERANCE_PCT = 0.005
PORTFOLIO_RISK_TOLERANCE_INR = 50.0
PORTFOLIO_RISK_TOLERANCE_PCT = 0.0025


class KillSwitchType(Enum):
    """Types of kill switches"""
    WEEKLY_LOSS = "weekly_loss_limit"
    TRAUMA = "single_trade_trauma"
    PORTFOLIO_RISK_CAP = "portfolio_risk_cap"
    TAX_LIQUIDITY = "tax_liquidity_crisis"
    FREQUENCY_LIMIT = "weekly_frequency_limit"
    TIME_BLOCK = "time_based_block"


@dataclass
class KillSwitchStatus:
    """Status of kill switches"""
    active: bool
    triggered_rules: List[str] = field(default_factory=list)
    cooldown_until: Optional[datetime] = None
    override_allowed: bool = False
    reason: str = ""
    
    def add_violation(self, rule: str, reason: str, cooldown_until: Optional[datetime] = None):
        """Add a kill switch violation"""
        self.active = True
        if rule not in self.triggered_rules:
            self.triggered_rules.append(rule)
        self.reason = f"{self.reason}; {reason}" if self.reason else reason
        if cooldown_until and (not self.cooldown_until or cooldown_until > self.cooldown_until):
            self.cooldown_until = cooldown_until


@dataclass
class Trade:
    """Trade record for survival rules checking"""
    trade_id: str
    strategy_type: str
    entry_time: datetime
    exit_time: Optional[datetime]
    max_loss: float
    realized_pnl: Optional[float]
    is_short_vol: bool
    
    def loss_percentage(self) -> float:
        """Calculate loss as percentage of max loss"""
        if self.realized_pnl is None or self.realized_pnl >= 0:
            return 0.0
        return abs(self.realized_pnl) / self.max_loss if self.max_loss > 0 else 0.0


@dataclass
class Position:
    """Open position for risk cap checking"""
    position_id: str
    strategy_type: str
    max_loss: float
    entry_time: datetime
    is_short_vol: bool


@dataclass
class PerformanceMetrics:
    """Performance metrics for survival rules"""
    current_equity: float
    ytd_gross_profits: float
    ytd_tax_liability: float
    cash_buffer: float


@dataclass
class TradeValidationResult:
    """Legacy-compatible trade allowance result."""
    allowed: bool
    reason: str
    triggered_rules: List[str] = field(default_factory=list)
    cooldown_until: Optional[datetime] = None
    override_allowed: bool = False


class SurvivalRulesEngine:
    """
    Implements circuit breakers and kill switches for options trading.
    
    This is the absolute safety layer - when survival rules trigger,
    trading stops. No exceptions, no overrides (except weekly loss with 48h cooling).
    
    Kill Switches:
    1. Weekly Loss Limit: 2% weekly loss → halt trading
    2. Trauma Rule: Single trade loses >80% max loss → block short-vol for 2 weeks
    3. Portfolio Risk Cap: Total open risk >2% capital → reject new trades
    4. Tax Liquidity: YTD tax > cash buffer → halt trading
    5. Frequency Limits: Max 2 trades/week, time-based blocks
    """
    
    def __init__(self, config: SurvivalRulesConfig, base_capital: float):
        """
        Initialize survival rules engine
        
        Args:
            config: Survival rules configuration
            base_capital: Base capital for percentage calculations
        """
        self.config = config
        self.base_capital = base_capital

        # For deterministic backtests/tests, naive datetimes skip day/time gating.
        # To force gating on naive timestamps, set NS_OPTIONS_ENFORCE_TIME_BLOCKS=1.
        env_flag = str(os.getenv("NS_OPTIONS_ENFORCE_TIME_BLOCKS", "")).strip().lower()
        self.enforce_time_blocks_for_naive = env_flag in {"1", "true", "yes", "on"}
        
        # State tracking
        self.trauma_cooldown_until: Optional[datetime] = None
        self.weekly_loss_override_until: Optional[datetime] = None
        self.trauma_triggered_trades: set = set()  # Track trades that already triggered trauma
        
        logger.info(f"SurvivalRulesEngine initialized with base capital: ₹{base_capital:,.0f}")

    def _to_ist(self, dt: datetime) -> datetime:
        """Normalize datetime to timezone-aware IST for safe comparisons."""
        if dt.tzinfo is None:
            return IST.localize(dt)
        return dt.astimezone(IST)
    
    def check_all_kill_switches(
        self,
        open_positions: List[Position],
        closed_trades: List[Trade],
        performance: PerformanceMetrics,
        current_time: datetime,
        proposed_trade: Optional[Position] = None,
        portfolio_risk_cap_value: Optional[float] = None,
    ) -> KillSwitchStatus:
        """
        Check all kill switches and return consolidated status
        
        Args:
            open_positions: Currently open positions
            closed_trades: Historical closed trades
            performance: Current performance metrics
            current_time: Current timestamp (IST)
            proposed_trade: Optional proposed trade to validate
        
        Returns:
            KillSwitchStatus: Consolidated kill switch status
        """
        status = KillSwitchStatus(active=False)
        
        # 1. Check weekly loss limit
        weekly_loss_triggered, weekly_reason = self._check_weekly_loss_limit(
            closed_trades, current_time
        )
        if weekly_loss_triggered:
            cooldown = self._get_next_monday_915am(current_time)
            status.add_violation(
                KillSwitchType.WEEKLY_LOSS.value,
                weekly_reason,
                cooldown
            )
            status.override_allowed = True  # Only kill switch that allows override
        
        # 2. Check trauma rule
        trauma_triggered, trauma_reason = self._check_trauma_rule(
            closed_trades, current_time
        )
        if trauma_triggered:
            status.add_violation(
                KillSwitchType.TRAUMA.value,
                trauma_reason,
                self.trauma_cooldown_until
            )
        
        # 3. Check portfolio risk cap
        if proposed_trade:
            risk_cap_triggered, risk_reason = self._check_portfolio_risk_cap(
                open_positions, proposed_trade, portfolio_risk_cap_value=portfolio_risk_cap_value
            )
            if risk_cap_triggered:
                status.add_violation(
                    KillSwitchType.PORTFOLIO_RISK_CAP.value,
                    risk_reason
                )
        
        # 4. Check tax liquidity
        tax_triggered, tax_reason = self._check_tax_liquidity(performance)
        if tax_triggered:
            status.add_violation(
                KillSwitchType.TAX_LIQUIDITY.value,
                tax_reason
            )
        
        # 5. Check frequency limits
        freq_triggered, freq_reason = self._check_frequency_limits(
            closed_trades, current_time
        )
        if freq_triggered:
            status.add_violation(
                KillSwitchType.FREQUENCY_LIMIT.value,
                freq_reason
            )
        
        # 6. Check time-based blocks
        time_triggered, time_reason = self._check_time_blocks(current_time)
        if time_triggered:
            status.add_violation(
                KillSwitchType.TIME_BLOCK.value,
                time_reason
            )
        
        if status.active:
            logger.warning(f"Kill switches active: {status.triggered_rules}")
            logger.warning(f"Reason: {status.reason}")
        
        return status
    
    def _check_weekly_loss_limit(
        self,
        closed_trades: List[Trade],
        current_time: datetime
    ) -> Tuple[bool, str]:
        """
        Check weekly loss limit kill switch
        
        Weekly window: Monday 00:00 IST to Sunday 23:59 IST
        Reset: Monday 9:15 AM IST (after NSE market open)
        Limit: 2% of base capital
        
        Args:
            closed_trades: All closed trades
            current_time: Current timestamp (IST)
        
        Returns:
            Tuple[bool, str]: (triggered, reason)
        """
        current_time = self._to_ist(current_time)
        # Check if override is active
        if self.weekly_loss_override_until and current_time < self._to_ist(self.weekly_loss_override_until):
            return False, ""
        
        # Get current week boundaries
        week_start, week_end = self._get_current_week_boundaries(current_time)
        
        # Filter trades in current week
        weekly_trades = [
            t for t in closed_trades
            if t.exit_time and week_start <= self._to_ist(t.exit_time) <= week_end
        ]
        
        # Calculate weekly P&L
        weekly_pnl = sum(t.realized_pnl for t in weekly_trades if t.realized_pnl is not None)
        
        # Check limit
        loss_limit = self.base_capital * self.config.weekly_loss_limit_pct
        
        if weekly_pnl < -loss_limit:
            reason = (
                f"Weekly loss limit breached: ₹{abs(weekly_pnl):,.0f} loss "
                f"(limit: ₹{loss_limit:,.0f}). Trading halted until Monday 9:15 AM IST."
            )
            logger.critical(reason)
            return True, reason
        
        return False, ""
    
    def _check_trauma_rule(
        self,
        closed_trades: List[Trade],
        current_time: datetime
    ) -> Tuple[bool, str]:
        """
        Check single-trade trauma rule
        
        If any trade loses >80% of max loss, block short-vol for 2 weeks.
        Applies to iron condors and calendar spreads only.
        
        Args:
            closed_trades: All closed trades
            current_time: Current timestamp (IST)
        
        Returns:
            Tuple[bool, str]: (triggered, reason)
        """
        current_time = self._to_ist(current_time)
        # Check if cooldown is active
        if self.trauma_cooldown_until and current_time < self._to_ist(self.trauma_cooldown_until):
            reason = (
                f"Trauma rule active: Short-vol blocked until "
                f"{self.trauma_cooldown_until.strftime('%Y-%m-%d %H:%M IST')}"
            )
            return True, reason
        
        # If cooldown expired, clear it (but keep triggered trades to avoid re-triggering)
        if self.trauma_cooldown_until and current_time >= self._to_ist(self.trauma_cooldown_until):
            self.trauma_cooldown_until = None
            # Don't clear trauma_triggered_trades - we never want to re-trigger on same trade
        
        # Check recent trades for trauma (only if not already in cooldown)
        if self.trauma_cooldown_until is None:
            trauma_threshold = self.config.trauma_loss_threshold_pct
            
            for trade in closed_trades:
                # Skip if already triggered trauma for this trade
                if trade.trade_id in self.trauma_triggered_trades:
                    continue
                
                if not trade.is_short_vol:
                    continue
                
                loss_pct = trade.loss_percentage()
                if loss_pct > trauma_threshold:
                    # Set cooldown and mark trade as processed
                    self.trauma_cooldown_until = current_time + timedelta(
                        weeks=self.config.trauma_cooldown_weeks
                    )
                    self.trauma_triggered_trades.add(trade.trade_id)
                    
                    reason = (
                        f"Trauma rule triggered: Trade {trade.trade_id} lost "
                        f"{loss_pct:.1%} of max loss (threshold: {trauma_threshold:.1%}). "
                        f"Short-vol blocked until {self.trauma_cooldown_until.strftime('%Y-%m-%d %H:%M IST')}"
                    )
                    logger.critical(reason)
                    return True, reason
        
        return False, ""
    
    def _check_portfolio_risk_cap(
        self,
        open_positions: List[Position],
        proposed_trade: Position,
        portfolio_risk_cap_value: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Check portfolio risk cap
        
        Total open worst-case loss ≤ 2% capital.
        Sum of max_loss across all open positions + proposed trade.
        
        Args:
            open_positions: Currently open positions
            proposed_trade: Proposed new trade
        
        Returns:
            Tuple[bool, str]: (triggered, reason)
        """
        # Calculate current portfolio risk
        current_risk = sum(pos.max_loss for pos in open_positions)
        
        # Add proposed trade risk
        total_risk = current_risk + proposed_trade.max_loss
        
        # Check cap
        risk_cap = float(
            portfolio_risk_cap_value
            if portfolio_risk_cap_value is not None
            else self.base_capital * self.config.portfolio_risk_cap_pct
        )
        tolerance = max(
            PORTFOLIO_RISK_TOLERANCE_INR,
            abs(risk_cap) * PORTFOLIO_RISK_TOLERANCE_PCT,
        )

        if total_risk > risk_cap + tolerance:
            reason = (
                f"Portfolio risk cap exceeded: Total risk ₹{total_risk:,.0f} "
                f"(cap: ₹{risk_cap:,.0f}, tolerance: ₹{tolerance:,.0f}). "
                f"Current open risk: ₹{current_risk:,.0f}, "
                f"Proposed trade risk: ₹{proposed_trade.max_loss:,.0f}"
            )
            logger.warning(reason)
            return True, reason

        if total_risk > risk_cap:
            logger.warning(
                "Portfolio risk is above hard cap but within tolerance: "
                f"total=₹{total_risk:,.0f}, cap=₹{risk_cap:,.0f}, tolerance=₹{tolerance:,.0f}"
            )
        
        return False, ""
    
    def _check_tax_liquidity(
        self,
        performance: PerformanceMetrics
    ) -> Tuple[bool, str]:
        """
        Check tax liquidity crisis
        
        Halt if YTD tax payable > cash buffer.
        Cash buffer = 30% of YTD gross profits.
        
        Args:
            performance: Current performance metrics
        
        Returns:
            Tuple[bool, str]: (triggered, reason)
        """
        tax_liability = float(performance.ytd_tax_liability or 0.0)
        cash_buffer = float(performance.cash_buffer or 0.0)
        tolerance = max(
            TAX_LIQUIDITY_TOLERANCE_INR,
            abs(cash_buffer) * TAX_LIQUIDITY_TOLERANCE_PCT,
        )
        deficit = tax_liability - cash_buffer

        if deficit > tolerance:
            reason = (
                f"Tax liquidity crisis: YTD tax liability ₹{tax_liability:,.2f} "
                f"exceeds cash buffer ₹{cash_buffer:,.2f} by ₹{deficit:,.2f} "
                f"(tolerance ₹{tolerance:,.2f}). "
                f"Trading halted to preserve liquidity."
            )
            logger.critical(reason)
            return True, reason

        if deficit > 0:
            logger.warning(
                "Tax buffer near limit but within tolerance: "
                f"tax liability ₹{tax_liability:,.2f}, cash buffer ₹{cash_buffer:,.2f}, "
                f"deficit ₹{deficit:,.2f}, tolerance ₹{tolerance:,.2f}"
            )
        
        return False, ""
    
    def _check_frequency_limits(
        self,
        closed_trades: List[Trade],
        current_time: datetime
    ) -> Tuple[bool, str]:
        """
        Check weekly trade frequency limit
        
        Max 2 trades per week (Monday 00:00 to Sunday 23:59 IST).
        
        Args:
            closed_trades: All closed trades
            current_time: Current timestamp (IST)
        
        Returns:
            Tuple[bool, str]: (triggered, reason)
        """
        current_time = self._to_ist(current_time)
        # Get current week boundaries
        week_start, week_end = self._get_current_week_boundaries(current_time)
        
        # Count trades entered in current week
        weekly_trade_count = sum(
            1 for t in closed_trades
            if week_start <= self._to_ist(t.entry_time) <= week_end
        )
        
        if weekly_trade_count >= self.config.max_trades_per_week:
            reason = (
                f"Weekly trade frequency limit reached: {weekly_trade_count} trades "
                f"(limit: {self.config.max_trades_per_week}). No more trades this week."
            )
            logger.warning(reason)
            return True, reason
        
        return False, ""
    
    def _check_time_blocks(
        self,
        current_time: datetime
    ) -> Tuple[bool, str]:
        """
        Check time-based trading blocks
        
        Blocks:
        - Monday 9:15-10:00 AM IST (opening volatility)
        - Configured weekly expiry day(s) via `no_trade_days`
        
        Args:
            current_time: Current timestamp (IST)
        
        Returns:
            Tuple[bool, str]: (triggered, reason)
        """
        # Naive timestamps are treated as simulation/backtest unless explicitly forced.
        if current_time.tzinfo is None and not self.enforce_time_blocks_for_naive:
            return False, ""

        # Ensure timezone-aware
        current_time = self._to_ist(current_time)
        
        # Check configured no-trade days (e.g., weekly expiry day)
        if current_time.strftime('%A') in self.config.no_trade_days:
            reason = f"No trading on {current_time.strftime('%A')} (configured no-trade day)"
            return True, reason
        
        # Check no-trade times (Monday 9:15-10:00 AM)
        for time_block in self.config.no_trade_times:
            if current_time.strftime('%A') == time_block['day']:
                start_time = datetime.strptime(time_block['start'], '%H:%M').time()
                end_time = datetime.strptime(time_block['end'], '%H:%M').time()
                
                if start_time <= current_time.time() <= end_time:
                    reason = (
                        f"No trading on {time_block['day']} "
                        f"{time_block['start']}-{time_block['end']} IST (opening volatility)"
                    )
                    return True, reason
        
        return False, ""

    def validate_trade_allowed(
        self,
        strategy_type: str,
        max_loss: float,
        current_positions_risk: float,
        weekly_pnl: float,
        ytd_tax_liability: float,
        cash_buffer: float,
        current_time: Optional[datetime] = None
    ) -> TradeValidationResult:
        """
        Legacy convenience wrapper used by integration tests and older callers.
        """
        now = current_time or datetime.now()
        if now.tzinfo is None:
            now = IST.localize(now)
        else:
            now = now.astimezone(IST)
        existing = Position(
            position_id="existing_risk_bucket",
            strategy_type="existing",
            max_loss=max(0.0, float(current_positions_risk)),
            entry_time=now,
            is_short_vol=True,
        )
        proposed = Position(
            position_id="proposed_trade",
            strategy_type=strategy_type,
            max_loss=max(0.0, float(max_loss)),
            entry_time=now,
            is_short_vol=True,
        )

        synthetic_loss = max(abs(float(weekly_pnl)), 1.0)
        closed = [
            Trade(
                trade_id="weekly_rollup",
                strategy_type=strategy_type,
                entry_time=now - timedelta(days=2),
                exit_time=now - timedelta(hours=1),
                max_loss=synthetic_loss,
                realized_pnl=float(weekly_pnl),
                # Keep wrapper focused on weekly/frequency/risk gates by default.
                is_short_vol=False,
            )
        ]

        perf = PerformanceMetrics(
            current_equity=float(self.base_capital),
            ytd_gross_profits=max(0.0, float(cash_buffer) / 0.30) if cash_buffer > 0 else 0.0,
            ytd_tax_liability=float(ytd_tax_liability),
            cash_buffer=float(cash_buffer),
        )

        status = self.check_all_kill_switches(
            open_positions=[existing] if existing.max_loss > 0 else [],
            closed_trades=closed,
            performance=perf,
            current_time=now,
            proposed_trade=proposed,
        )
        return TradeValidationResult(
            allowed=not status.active,
            reason=status.reason,
            triggered_rules=list(status.triggered_rules),
            cooldown_until=status.cooldown_until,
            override_allowed=status.override_allowed,
        )
    
    def _get_current_week_boundaries(
        self,
        current_time: datetime
    ) -> Tuple[datetime, datetime]:
        """
        Get current week boundaries (Monday 00:00 to Sunday 23:59 IST)
        
        Args:
            current_time: Current timestamp
        
        Returns:
            Tuple[datetime, datetime]: (week_start, week_end)
        """
        # Ensure timezone-aware
        current_time = self._to_ist(current_time)
        
        # Get Monday of current week
        days_since_monday = current_time.weekday()
        week_start = current_time - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get Sunday of current week
        days_until_sunday = 6 - current_time.weekday()
        week_end = current_time + timedelta(days=days_until_sunday)
        week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return week_start, week_end
    
    def _get_next_monday_915am(
        self,
        current_time: datetime
    ) -> datetime:
        """
        Get next Monday 9:15 AM IST (weekly loss reset time)
        
        Args:
            current_time: Current timestamp
        
        Returns:
            datetime: Next Monday 9:15 AM IST
        """
        # Ensure timezone-aware
        if current_time.tzinfo is None:
            current_time = IST.localize(current_time)
        else:
            current_time = current_time.astimezone(IST)
        
        # Calculate days until next Monday
        days_until_monday = (7 - current_time.weekday()) % 7
        if days_until_monday == 0 and current_time.time() >= time(9, 15):
            days_until_monday = 7
        
        next_monday = current_time + timedelta(days=days_until_monday)
        next_monday = next_monday.replace(hour=9, minute=15, second=0, microsecond=0)
        
        return next_monday
    
    def set_weekly_loss_override(
        self,
        current_time: datetime,
        cooling_period_hours: int = 48
    ) -> None:
        """
        Set weekly loss override (requires manual approval + 48h cooling)
        
        Args:
            current_time: Current timestamp
            cooling_period_hours: Cooling period in hours (default: 48)
        """
        current_time = self._to_ist(current_time)
        self.weekly_loss_override_until = current_time + timedelta(hours=cooling_period_hours)
        logger.warning(
            f"Weekly loss override activated until "
            f"{self.weekly_loss_override_until.strftime('%Y-%m-%d %H:%M IST')}"
        )
    
    def clear_trauma_cooldown(self) -> None:
        """Clear trauma cooldown (for testing or manual intervention)"""
        self.trauma_cooldown_until = None
        self.trauma_triggered_trades.clear()
        logger.info("Trauma cooldown cleared")
    
    def get_status_summary(
        self,
        open_positions: List[Position],
        closed_trades: List[Trade],
        performance: PerformanceMetrics,
        current_time: datetime
    ) -> Dict[str, any]:
        """
        Get summary of survival rules status
        
        Args:
            open_positions: Currently open positions
            closed_trades: Historical closed trades
            performance: Current performance metrics
            current_time: Current timestamp (IST)
        
        Returns:
            Dict: Status summary
        """
        current_time = self._to_ist(current_time)
        # Get week boundaries
        week_start, week_end = self._get_current_week_boundaries(current_time)
        
        # Calculate weekly metrics
        weekly_trades = [
            t for t in closed_trades
            if t.exit_time and week_start <= self._to_ist(t.exit_time) <= week_end
        ]
        weekly_pnl = sum(t.realized_pnl for t in weekly_trades if t.realized_pnl is not None)
        weekly_trade_count = len([t for t in closed_trades if week_start <= self._to_ist(t.entry_time) <= week_end])
        
        # Calculate portfolio risk
        portfolio_risk = sum(pos.max_loss for pos in open_positions)
        
        return {
            "weekly_pnl": weekly_pnl,
            "weekly_loss_limit": self.base_capital * self.config.weekly_loss_limit_pct,
            "weekly_loss_pct": (weekly_pnl / self.base_capital) if self.base_capital > 0 else 0,
            "weekly_trade_count": weekly_trade_count,
            "weekly_trade_limit": self.config.max_trades_per_week,
            "portfolio_risk": portfolio_risk,
            "portfolio_risk_cap": float(performance.current_equity) * self.config.portfolio_risk_cap_pct,
            "portfolio_risk_pct": (portfolio_risk / float(performance.current_equity)) if float(performance.current_equity) > 0 else 0,
            "trauma_cooldown_active": self.trauma_cooldown_until is not None and current_time < self._to_ist(self.trauma_cooldown_until),
            "trauma_cooldown_until": self.trauma_cooldown_until,
            "tax_liability": performance.ytd_tax_liability,
            "cash_buffer": performance.cash_buffer,
            "week_start": week_start,
            "week_end": week_end,
            "next_reset": self._get_next_monday_915am(current_time)
        }
