"""
System Hygiene Rules for Options Trading

Prevents over-trading and revenge trading through:
1. Strategy concentration limits (no 3rd consecutive same strategy)
2. Success cooling periods (pause after 2 consecutive wins)

Philosophy: Discipline over activity - selectivity prevents overtrading.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from collections import deque

logger = logging.getLogger("options.system_hygiene")


@dataclass
class TradeRecord:
    """Minimal trade record for hygiene tracking"""
    trade_id: str
    timestamp: datetime
    strategy_type: str
    regime: Any
    was_profitable: bool
    net_pnl: float


@dataclass
class HygieneCheckResult:
    """Result of hygiene check"""
    allowed: bool
    reason: str
    details: str


class SystemHygieneRules:
    """
    Enforces system hygiene rules to prevent overtrading
    
    Rules:
    1. Strategy Concentration Limit:
       - Track last 2 trades
       - Reject 3rd consecutive trade of same strategy type
       - Prevents fixation on single strategy
    
    2. Success Cooling Period:
       - Track last 2 trades
       - Skip signal after 2 consecutive wins
       - Exception: Allow if IV rank extreme (>90% or <10%)
       - Prevents overconfidence and revenge trading
    
    These rules enforce discipline and prevent emotional trading.
    """
    
    def __init__(
        self,
        concentration_lookback: int = 2,
        cooling_lookback: int = 2,
        cooling_period_days: int = 0,
        iv_rank_extreme_threshold: float = 0.90,
        iv_rank_extreme_low: float = 0.10
    ):
        """
        Initialize system hygiene rules
        
        Args:
            concentration_lookback: Number of recent trades to check for concentration
            cooling_lookback: Number of recent trades to check for cooling
            cooling_period_days: Legacy alias used by older integration tests
            iv_rank_extreme_threshold: IV rank above which cooling is bypassed
            iv_rank_extreme_low: IV rank below which cooling is bypassed
        """
        self.concentration_lookback = concentration_lookback
        self.cooling_lookback = cooling_lookback if cooling_lookback > 0 else max(1, cooling_period_days)
        self.iv_rank_extreme_threshold = iv_rank_extreme_threshold
        self.iv_rank_extreme_low = iv_rank_extreme_low
        
        # Track recent trades (limited deque for efficiency)
        self.recent_trades: deque[TradeRecord] = deque(maxlen=10)
        
        logger.info(
            f"SystemHygieneRules initialized: "
            f"concentration_lookback={concentration_lookback}, "
            f"cooling_lookback={cooling_lookback}"
        )
    
    def add_trade(
        self,
        trade_id: Any,
        timestamp: Any = None,
        strategy_type: Any = None,
        regime: Any = "NEUTRAL",
        was_profitable: Any = False,
        net_pnl: Any = 0.0
    ) -> None:
        """
        Add completed trade to history
        
        Args:
            trade_id: Trade identifier
            timestamp: Trade close timestamp
            strategy_type: Strategy type
            regime: Market regime at entry
            was_profitable: Whether trade was profitable
            net_pnl: Net P&L
        """
        # Legacy dict payload support:
        # add_trade({"strategy_type": "...", "timestamp": ..., "outcome": "win"})
        if isinstance(trade_id, dict) and timestamp is None:
            payload = trade_id
            trade_id = payload.get("trade_id", f"trade_{len(self.recent_trades) + 1}")
            timestamp = payload.get("timestamp", datetime.now())
            strategy_type = payload.get("strategy_type", "UNKNOWN")
            regime = payload.get("regime", "NEUTRAL")
            outcome = str(payload.get("outcome", "")).strip().lower()
            if "was_profitable" in payload:
                was_profitable = bool(payload.get("was_profitable"))
            else:
                was_profitable = outcome in {"win", "profit", "profitable", "true", "1"}
            net_pnl = float(payload.get("net_pnl", 0.0))

        trade_record = TradeRecord(
            trade_id=str(trade_id),
            timestamp=timestamp if isinstance(timestamp, datetime) else datetime.now(),
            strategy_type=str(strategy_type) if strategy_type is not None else "UNKNOWN",
            regime=regime,
            was_profitable=bool(was_profitable),
            net_pnl=float(net_pnl),
        )
        
        self.recent_trades.append(trade_record)
        
        logger.debug(
            f"Added trade to hygiene tracker: {trade_id}, "
            f"strategy={strategy_type}, profitable={was_profitable}"
        )
    
    def check_strategy_concentration(
        self,
        proposed_strategy_type: str
    ) -> HygieneCheckResult:
        """
        Check if proposed strategy violates concentration limit
        
        Rule: Reject 3rd consecutive trade of same strategy type
        
        Args:
            proposed_strategy_type: Strategy type being proposed
        
        Returns:
            HygieneCheckResult: Whether trade is allowed
        """
        if len(self.recent_trades) < self.concentration_lookback:
            # Not enough history, allow
            return HygieneCheckResult(
                allowed=True,
                reason="insufficient_history",
                details=f"Only {len(self.recent_trades)} recent trades"
            )
        
        # Get last N trades
        last_n_trades = list(self.recent_trades)[-self.concentration_lookback:]
        
        # Check if all last N trades are same strategy
        all_same_strategy = all(
            trade.strategy_type == proposed_strategy_type
            for trade in last_n_trades
        )
        
        if all_same_strategy:
            # Would be 3rd consecutive - reject
            return HygieneCheckResult(
                allowed=False,
                reason="strategy_concentration",
                details=(
                    f"Last {self.concentration_lookback} trades were all "
                    f"{proposed_strategy_type}. Rejecting 3rd consecutive."
                )
            )
        
        # Allowed
        return HygieneCheckResult(
            allowed=True,
            reason="concentration_ok",
            details=f"Strategy diversity maintained"
        )
    
    def check_success_cooling(
        self,
        iv_rank: float
    ) -> HygieneCheckResult:
        """
        Check if success cooling period is active
        
        Rule: Skip signal after 2 consecutive wins (unless IV extreme)
        
        Args:
            iv_rank: Current IV rank (0-1)
        
        Returns:
            HygieneCheckResult: Whether trade is allowed
        """
        if len(self.recent_trades) < self.cooling_lookback:
            # Not enough history, allow
            return HygieneCheckResult(
                allowed=True,
                reason="insufficient_history",
                details=f"Only {len(self.recent_trades)} recent trades"
            )
        
        # Get last N trades
        last_n_trades = list(self.recent_trades)[-self.cooling_lookback:]
        
        # Check if all last N trades were profitable
        all_profitable = all(trade.was_profitable for trade in last_n_trades)
        
        if not all_profitable:
            # Not in cooling period
            return HygieneCheckResult(
                allowed=True,
                reason="no_cooling_needed",
                details="Not all recent trades were profitable"
            )
        
        # In cooling period - check for IV extreme exception
        if iv_rank >= self.iv_rank_extreme_threshold:
            # Extreme high IV - allow despite cooling
            return HygieneCheckResult(
                allowed=True,
                reason="iv_extreme_high",
                details=(
                    f"IV rank {iv_rank:.1%} >= {self.iv_rank_extreme_threshold:.1%} "
                    f"(extreme high) - bypassing cooling period"
                )
            )
        
        if iv_rank <= self.iv_rank_extreme_low:
            # Extreme low IV - allow despite cooling
            return HygieneCheckResult(
                allowed=True,
                reason="iv_extreme_low",
                details=(
                    f"IV rank {iv_rank:.1%} <= {self.iv_rank_extreme_low:.1%} "
                    f"(extreme low) - bypassing cooling period"
                )
            )
        
        # In cooling period, no exception - reject
        return HygieneCheckResult(
            allowed=False,
            reason="success_cooling",
            details=(
                f"Last {self.cooling_lookback} trades were all profitable. "
                f"Cooling period active (IV rank {iv_rank:.1%} not extreme)."
            )
        )

    def check_success_cooling_period(self, iv_rank: float) -> HygieneCheckResult:
        """Legacy alias for older integration tests."""
        return self.check_success_cooling(iv_rank)
    
    def check_all_hygiene_rules(
        self,
        proposed_strategy_type: str,
        iv_rank: float
    ) -> HygieneCheckResult:
        """
        Check all hygiene rules
        
        Args:
            proposed_strategy_type: Strategy type being proposed
            iv_rank: Current IV rank (0-1)
        
        Returns:
            HygieneCheckResult: Combined result (fails if any rule fails)
        """
        # Check concentration
        concentration_result = self.check_strategy_concentration(proposed_strategy_type)
        if not concentration_result.allowed:
            return concentration_result
        
        # Check cooling
        cooling_result = self.check_success_cooling(iv_rank)
        if not cooling_result.allowed:
            return cooling_result
        
        # All checks passed
        return HygieneCheckResult(
            allowed=True,
            reason="all_checks_passed",
            details="All hygiene checks passed"
        )
    
    def get_recent_trades_summary(self) -> dict:
        """
        Get summary of recent trades
        
        Returns:
            dict: Summary statistics
        """
        if not self.recent_trades:
            return {
                'total_trades': 0,
                'profitable_trades': 0,
                'win_rate': 0.0,
                'consecutive_wins': 0,
                'consecutive_losses': 0,
                'strategy_distribution': {}
            }
        
        trades_list = list(self.recent_trades)
        
        # Calculate metrics
        total_trades = len(trades_list)
        profitable_trades = sum(1 for t in trades_list if t.was_profitable)
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
        
        # Count consecutive wins/losses from most recent
        consecutive_wins = 0
        consecutive_losses = 0
        
        for trade in reversed(trades_list):
            if trade.was_profitable:
                consecutive_wins += 1
            else:
                break
        
        if consecutive_wins == 0:
            for trade in reversed(trades_list):
                if not trade.was_profitable:
                    consecutive_losses += 1
                else:
                    break
        
        # Strategy distribution
        strategy_distribution = {}
        for trade in trades_list:
            strategy_distribution[trade.strategy_type] = \
                strategy_distribution.get(trade.strategy_type, 0) + 1
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': win_rate,
            'consecutive_wins': consecutive_wins,
            'consecutive_losses': consecutive_losses,
            'strategy_distribution': strategy_distribution
        }
    
    def reset(self) -> None:
        """Reset hygiene tracker (e.g., at start of new period)"""
        self.recent_trades.clear()
        logger.info("System hygiene tracker reset")


# Backward-compatible alias expected by some fixtures/tests.
SystemHygiene = SystemHygieneRules
