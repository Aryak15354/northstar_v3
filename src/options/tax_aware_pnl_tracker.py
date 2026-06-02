"""
Tax-Aware P&L Tracker for Options Trading

Calculates accurate post-tax P&L including all costs and India's 30% VDA tax.
Critical for understanding true profitability of options trades.

Philosophy: Tax reality - all P&L must account for India's 30% flat tax on profits.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime

from src.options.position_manager import Position, PositionLeg
from src.options.config_loader import CostsConfig, TaxConfig

logger = logging.getLogger("options.pnl_tracker")

# Keep status computation aligned with kill-switch tolerance handling.
TAX_BUFFER_STATUS_TOLERANCE_INR = 1.0
TAX_BUFFER_STATUS_TOLERANCE_PCT = 0.005


@dataclass
class TradeCosts:
    """Complete cost breakdown for a trade"""
    brokerage: float  # ₹20 per leg
    exchange_charges: float  # 0.05% of turnover
    sebi_charges: float  # ₹10 per crore
    stamp_duty: float  # 0.003% on buy side
    gst: float  # 18% on (brokerage + exchange charges)
    total: float
    
    def __str__(self) -> str:
        return (
            f"Brokerage: ₹{self.brokerage:,.0f}, "
            f"Exchange: ₹{self.exchange_charges:,.0f}, "
            f"SEBI: ₹{self.sebi_charges:,.0f}, "
            f"Stamp: ₹{self.stamp_duty:,.0f}, "
            f"GST: ₹{self.gst:,.0f}, "
            f"Total: ₹{self.total:,.0f}"
        )


@dataclass
class TradePnL:
    """Complete P&L breakdown for a trade"""
    gross_pnl: float
    costs: TradeCosts
    tax: float
    net_pnl: float
    
    def __str__(self) -> str:
        return (
            f"Gross P&L: ₹{self.gross_pnl:,.0f}, "
            f"Costs: ₹{self.costs.total:,.0f}, "
            f"Tax: ₹{self.tax:,.0f}, "
            f"Net P&L: ₹{self.net_pnl:,.0f}"
        )


class TaxAwarePnLTracker:
    """
    Tracks P&L with full cost and tax accounting.
    
    Responsibilities:
    - Calculate gross P&L (exit value - entry value)
    - Calculate all trading costs (brokerage, exchange, SEBI, stamp, GST)
    - Calculate tax (30% on gross profits only, applied on close date)
    - Calculate net P&L (gross - costs - tax)
    - Track YTD tax liability
    - Enforce minimum profitability filter
    
    Critical: Tax is applied ONLY on closed trades, not on unrealized MTM.
    """
    
    def __init__(self, costs_config: CostsConfig, tax_config: TaxConfig):
        """
        Initialize P&L tracker
        
        Args:
            costs_config: Trading costs configuration
            tax_config: Tax configuration
        """
        self.costs_config = costs_config
        self.tax_config = tax_config
        
        # YTD tracking
        self.ytd_tax_liability: float = 0.0
        self.ytd_gross_profits: float = 0.0
        self.ytd_gross_losses: float = 0.0
        self.ytd_total_costs: float = 0.0
        
        logger.info(
            f"TaxAwarePnLTracker initialized with tax rate: {tax_config.rate:.1%}"
        )
    
    def calculate_gross_pnl(
        self,
        entry_credit_debit: float,
        exit_value: float
    ) -> float:
        """
        Calculate gross P&L before costs and tax
        
        Formula: exit_value - entry_credit_debit
        
        For credit spreads (iron condor):
        - Entry: Receive credit (positive)
        - Exit: Pay to close (negative)
        - Gross P&L = exit_value - entry_credit
        
        For debit spreads (calendar, straddle):
        - Entry: Pay debit (negative)
        - Exit: Receive to close (positive)
        - Gross P&L = exit_value - entry_debit
        
        Args:
            entry_credit_debit: Entry value (positive for credit, negative for debit)
            exit_value: Exit value
        
        Returns:
            float: Gross P&L
        """
        gross_pnl = exit_value - entry_credit_debit
        return gross_pnl
    
    def calculate_costs(self, legs: List[PositionLeg]) -> TradeCosts:
        """
        Calculate all trading costs for a position
        
        Costs include:
        - Brokerage: ₹20 per leg (entry + exit = 2x)
        - Exchange charges: 0.05% of turnover
        - SEBI charges: ₹10 per ₹1 crore turnover
        - Stamp duty: 0.003% on buy-side premium
        - GST: 18% on (brokerage + exchange charges)
        
        Args:
            legs: List of position legs
        
        Returns:
            TradeCosts: Complete cost breakdown
        """
        # Brokerage: ₹20 per leg, entry + exit
        num_legs = len(legs)
        brokerage = self.costs_config.brokerage_per_leg * num_legs * 2  # Entry + exit
        
        # Calculate turnover (sum of all premiums × quantities)
        total_turnover = 0.0
        buy_side_premium = 0.0
        
        for leg in legs:
            premium = self._leg_premium(leg)
            quantity = self._leg_quantity(leg)
            leg_turnover = premium * quantity
            total_turnover += leg_turnover
            
            # Track buy-side premium for stamp duty
            if self._leg_action(leg) == "buy":
                buy_side_premium += leg_turnover
        
        # Exchange charges: 0.05% of turnover (entry + exit)
        exchange_charges = total_turnover * self.costs_config.exchange_charges_pct * 2
        
        # SEBI charges: ₹10 per ₹1 crore turnover (entry + exit)
        sebi_charges = (total_turnover * 2 / 10000000) * self.costs_config.sebi_charges_per_crore
        
        # Stamp duty: 0.003% on buy-side premium (entry only)
        stamp_duty = buy_side_premium * self.costs_config.stamp_duty_pct
        
        # GST: 18% on (brokerage + exchange charges)
        gst = (brokerage + exchange_charges) * self.costs_config.gst_pct
        
        # Total costs
        total = brokerage + exchange_charges + sebi_charges + stamp_duty + gst
        
        return TradeCosts(
            brokerage=brokerage,
            exchange_charges=exchange_charges,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            gst=gst,
            total=total
        )

    @staticmethod
    def _leg_action(leg: Any) -> str:
        return str(getattr(leg, "action", "buy") or "buy").strip().lower()

    @staticmethod
    def _leg_quantity(leg: Any) -> float:
        try:
            quantity = float(getattr(leg, "quantity", 0.0) or 0.0)
        except Exception:
            return 0.0
        return max(0.0, quantity)

    @staticmethod
    def _leg_premium(leg: Any) -> float:
        raw = getattr(leg, "entry_premium", None)
        if raw is None:
            raw = getattr(leg, "premium", 0.0)
        try:
            premium = float(raw or 0.0)
        except Exception:
            return 0.0
        return max(0.0, premium)

    def estimate_slippage_cost(self, legs: List[Any], slippage_bps: float) -> float:
        """
        Estimate round-trip slippage cost from expected turnover.

        Slippage is applied on total premium turnover for both entry and exit.
        """
        bps = max(0.0, float(slippage_bps or 0.0))
        if bps <= 0.0:
            return 0.0

        total_turnover = 0.0
        for leg in legs:
            total_turnover += self._leg_premium(leg) * self._leg_quantity(leg)

        return float(total_turnover * 2.0 * (bps / 10_000.0))

    def estimate_trade_economics(
        self,
        *,
        legs: List[Any],
        expected_gross_pnl: float,
        max_loss: float,
        slippage_bps: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Estimate all-in trade economics before execution.

        Returns expected net P&L after Indian charges, GST, tax, and slippage,
        plus a conservative max-loss figure that includes execution friction.
        """
        costs = self.calculate_costs(legs)
        slippage_cost = self.estimate_slippage_cost(legs, slippage_bps=slippage_bps)
        tax = self.calculate_tax(expected_gross_pnl)
        expected_net_pnl = self.calculate_net_pnl(
            expected_gross_pnl,
            TradeCosts(
                brokerage=costs.brokerage,
                exchange_charges=costs.exchange_charges,
                sebi_charges=costs.sebi_charges,
                stamp_duty=costs.stamp_duty,
                gst=costs.gst,
                total=costs.total + slippage_cost,
            ),
            tax,
        )
        base_max_loss = max(0.0, float(max_loss or 0.0))
        friction_total = float(costs.total + slippage_cost)
        net_max_loss = float(base_max_loss + friction_total)
        cost_to_max_loss_ratio = float(friction_total / max(base_max_loss, 1.0))

        return {
            "expected_gross_pnl": float(expected_gross_pnl),
            "expected_tax": float(tax),
            "expected_net_pnl": float(expected_net_pnl),
            "slippage_bps": float(max(0.0, float(slippage_bps or 0.0))),
            "slippage_cost": float(slippage_cost),
            "costs": costs,
            "friction_total": friction_total,
            "net_max_loss": net_max_loss,
            "cost_to_max_loss_ratio": cost_to_max_loss_ratio,
        }
    
    def calculate_tax(self, gross_pnl: float) -> float:
        """
        Calculate tax on gross profit (India VDA regime)
        
        Tax rules:
        - 30% flat tax on gross profits
        - 0% on losses (no loss offset)
        - Applied ONLY on closed trades (not on unrealized MTM)
        - No loss offset across financial years
        
        Args:
            gross_pnl: Gross P&L before costs and tax
        
        Returns:
            float: Tax amount (0 if loss)
        """
        if gross_pnl > 0:
            tax = gross_pnl * self.tax_config.rate
            return tax
        else:
            return 0.0
    
    def calculate_net_pnl(
        self,
        gross_pnl: float,
        costs: TradeCosts,
        tax: float
    ) -> float:
        """
        Calculate net P&L after costs and tax
        
        Formula: Net P&L = Gross P&L - Total Costs - Tax
        
        Args:
            gross_pnl: Gross P&L
            costs: Trading costs
            tax: Tax amount
        
        Returns:
            float: Net P&L
        """
        net_pnl = gross_pnl - costs.total - tax
        return net_pnl
    
    def calculate_trade_pnl(self, position: Position) -> TradePnL:
        """
        Calculate complete P&L for a closed position
        
        Args:
            position: Closed position
        
        Returns:
            TradePnL: Complete P&L breakdown
        
        Raises:
            ValueError: If position is not closed
        """
        if position.is_open():
            raise ValueError(f"Cannot calculate P&L for open position {position.position_id}")
        
        if position.realized_pnl is None:
            raise ValueError(f"Position {position.position_id} has no realized P&L")
        
        # Calculate gross P&L
        gross_pnl = self.calculate_gross_pnl(
            position.entry_credit_debit,
            position.current_value
        )
        
        # Calculate costs
        costs = self.calculate_costs(position.legs)
        
        # Calculate tax (only on profits)
        tax = self.calculate_tax(gross_pnl)
        
        # Calculate net P&L
        net_pnl = self.calculate_net_pnl(gross_pnl, costs, tax)
        
        logger.info(
            f"Calculated P&L for {position.position_id}: "
            f"Gross: ₹{gross_pnl:,.0f}, Costs: ₹{costs.total:,.0f}, "
            f"Tax: ₹{tax:,.0f}, Net: ₹{net_pnl:,.0f}"
        )
        
        return TradePnL(
            gross_pnl=gross_pnl,
            costs=costs,
            tax=tax,
            net_pnl=net_pnl
        )
    
    def check_minimum_profitability(
        self,
        expected_gross_pnl: float,
        legs: List[PositionLeg]
    ) -> bool:
        """
        Check if expected net P&L meets minimum profitability threshold
        
        Rule: Expected net P&L ≥ 1.5 × total costs
        
        This prevents churning for marginal gains and ensures trades
        are worth the execution risk and costs.
        
        Args:
            expected_gross_pnl: Expected gross P&L
            legs: Position legs for cost calculation
        
        Returns:
            bool: True if meets threshold, False otherwise
        """
        # Calculate costs
        costs = self.calculate_costs(legs)
        
        # Calculate expected tax
        tax = self.calculate_tax(expected_gross_pnl)
        
        # Calculate expected net P&L
        expected_net_pnl = expected_gross_pnl - costs.total - tax
        
        # Check threshold
        min_threshold = costs.total * self.tax_config.min_profitability_multiplier
        
        meets_threshold = expected_net_pnl >= min_threshold
        
        if not meets_threshold:
            logger.warning(
                f"Trade fails minimum profitability: "
                f"Expected net P&L ₹{expected_net_pnl:,.0f} < "
                f"Threshold ₹{min_threshold:,.0f} (1.5× costs)"
            )
        
        return meets_threshold
    
    def update_ytd_tracking(self, trade_pnl: TradePnL) -> None:
        """
        Update year-to-date tracking with new trade
        
        Args:
            trade_pnl: Trade P&L to add to YTD
        """
        # Update YTD tax liability
        self.ytd_tax_liability += trade_pnl.tax
        
        # Update YTD profits/losses
        if trade_pnl.gross_pnl > 0:
            self.ytd_gross_profits += trade_pnl.gross_pnl
        else:
            self.ytd_gross_losses += abs(trade_pnl.gross_pnl)
        
        # Update YTD costs
        self.ytd_total_costs += trade_pnl.costs.total
        
        logger.info(
            f"Updated YTD tracking: "
            f"Tax liability: ₹{self.ytd_tax_liability:,.0f}, "
            f"Gross profits: ₹{self.ytd_gross_profits:,.0f}, "
            f"Gross losses: ₹{self.ytd_gross_losses:,.0f}"
        )
    
    def get_ytd_summary(self) -> Dict:
        """
        Get year-to-date summary
        
        Returns:
            Dict: YTD summary with all metrics
        """
        ytd_net_pnl = (
            self.ytd_gross_profits - 
            self.ytd_gross_losses - 
            self.ytd_total_costs - 
            self.ytd_tax_liability
        )
        
        # Calculate cash buffer (30% of gross profits)
        cash_buffer = self.ytd_gross_profits * 0.30
        tolerance = max(
            TAX_BUFFER_STATUS_TOLERANCE_INR,
            abs(cash_buffer) * TAX_BUFFER_STATUS_TOLERANCE_PCT,
        )
        buffer_gap = self.ytd_tax_liability - cash_buffer
        buffer_status = "OK" if buffer_gap <= tolerance else "CRITICAL"
        
        return {
            "ytd_gross_profits": self.ytd_gross_profits,
            "ytd_gross_losses": self.ytd_gross_losses,
            "ytd_total_costs": self.ytd_total_costs,
            "ytd_tax_liability": self.ytd_tax_liability,
            "ytd_net_pnl": ytd_net_pnl,
            "cash_buffer": cash_buffer,
            "tax_buffer_gap": buffer_gap,
            "tax_buffer_tolerance": tolerance,
            "tax_buffer_status": buffer_status,
        }
    
    def reset_ytd(self) -> None:
        """Reset YTD tracking (call at start of new financial year)"""
        self.ytd_tax_liability = 0.0
        self.ytd_gross_profits = 0.0
        self.ytd_gross_losses = 0.0
        self.ytd_total_costs = 0.0
        logger.info("YTD tracking reset for new financial year")
