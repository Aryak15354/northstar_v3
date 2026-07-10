"""
PnLReconciler — Detects and reports P&L discrepancies across the system

Three reconciliation checks, run daily:
1. EQUITY vs OPTIONS reconciliation: Does total balance?
2. LIVE vs SHADOW reconciliation: Execution quality gap
3. LEDGER vs LEGACY reconciliation: Migration period validation
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import json
import pandas as pd
import logging

from .ledger import UnifiedPnLLedger, LedgerBook
from .nav_calculator import NAVCalculator

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """Result of daily reconciliation checks"""
    date: datetime
    equity_options_balanced: bool
    equity_options_discrepancy_inr: float
    
    live_shadow_discrepancy_inr: float
    live_shadow_discrepancy_pct: float
    live_shadow_flag: bool
    
    legacy_migration_discrepancies: List[Dict]
    
    overall_status: str  # "CLEAN", "WARNING", "CRITICAL"
    action_required: List[str]


class PnLReconciler:
    """Automated reconciliation system for P&L discrepancies"""
    
    def __init__(
        self,
        ledger: UnifiedPnLLedger,
        nav_calculator: NAVCalculator,
        config: dict = None
    ):
        self.ledger = ledger
        self.nav_calculator = nav_calculator
        self.config = config or {}
        
        # Tolerances
        recon_config = self.config.get('pnl', {}).get('reconciliation', {})
        self.equity_options_tolerance = recon_config.get('equity_options_tolerance_inr', 100)
        self.live_shadow_threshold_pct = recon_config.get('live_shadow_threshold_pct', 0.5)
        self.legacy_tolerance = recon_config.get('legacy_tolerance_inr', 1000)

    def _nav_as_of(self, date: datetime) -> pd.DataFrame:
        start_date = getattr(self.nav_calculator, "inception_date", None)
        if start_date is None:
            start_date = date
        return self.nav_calculator.compute_daily_nav(start_date, date)
    
    def run_daily_reconciliation(self, date: datetime) -> ReconciliationResult:
        """
        Runs all three reconciliation checks for the given date.
        Returns ReconciliationResult with status and actions.
        """
        logger.info(f"Running daily reconciliation for {date.date()}")
        
        # Check 1: Equity + Options balance
        equity_balanced, equity_discrepancy = self.reconcile_equity_options(date)
        
        # Check 2: Live vs Shadow
        shadow_discrepancy_inr, shadow_discrepancy_pct = self.reconcile_live_vs_shadow(date)
        shadow_flag = abs(shadow_discrepancy_pct) > self.live_shadow_threshold_pct
        
        # Check 3: Accounting integrity
        integrity_failures = self.detect_accounting_integrity_failure(date)
        
        # Determine overall status
        if not equity_balanced or shadow_flag or len(integrity_failures) > 0:
            overall_status = "CRITICAL"
        elif abs(equity_discrepancy) > self.equity_options_tolerance / 2:
            overall_status = "WARNING"
        else:
            overall_status = "CLEAN"
        
        # Action required
        actions = []
        if not equity_balanced:
            actions.append(f"CRITICAL: Equity/Options balance off by ₹{equity_discrepancy:.2f}")
        if shadow_flag:
            actions.append(f"WARNING: Live/Shadow gap is {shadow_discrepancy_pct:.2f}% of NAV")
        if integrity_failures:
            actions.extend(integrity_failures)
        
        result = ReconciliationResult(
            date=date,
            equity_options_balanced=equity_balanced,
            equity_options_discrepancy_inr=equity_discrepancy,
            live_shadow_discrepancy_inr=shadow_discrepancy_inr,
            live_shadow_discrepancy_pct=shadow_discrepancy_pct,
            live_shadow_flag=shadow_flag,
            legacy_migration_discrepancies=[],  # Empty after migration complete
            overall_status=overall_status,
            action_required=actions
        )
        
        logger.info(f"Reconciliation status: {overall_status}")
        
        return result
    
    def reconcile_equity_options(self, date: datetime) -> tuple[bool, float]:
        """
        Verifies that: equity_nav + options_pnl + cash = total_portfolio_value
        Returns (is_balanced, discrepancy_amount)
        """
        # Get P&L by book
        equity_pnl = self.ledger.get_total_pnl(date, book=LedgerBook.EQUITY)
        options_pnl = self.ledger.get_total_pnl(date, book=LedgerBook.OPTIONS)
        cash_pnl = self.ledger.get_total_pnl(date, book=LedgerBook.CASH)
        
        # Sum should equal total NAV change
        book_sum = equity_pnl + options_pnl + cash_pnl
        
        # Get total NAV from calculator
        nav_df = self._nav_as_of(date)
        if len(nav_df) == 0:
            logger.warning("No NAV data for reconciliation")
            return True, 0.0
        
        total_nav_change = nav_df['nav_combined'].iloc[-1] - self.nav_calculator.starting_capital
        
        # Compute discrepancy
        discrepancy = book_sum - total_nav_change
        
        is_balanced = abs(discrepancy) <= self.equity_options_tolerance
        
        if not is_balanced:
            logger.warning(f"Equity/Options balance discrepancy: ₹{discrepancy:.2f}")
        
        return is_balanced, discrepancy
    
    def reconcile_live_vs_shadow(self, date: datetime) -> tuple[float, float]:
        """
        Compares live vs shadow P&L to measure execution quality.
        Returns (absolute_discrepancy_inr, discrepancy_pct_of_nav)
        """
        # Get live P&L (equity + options)
        live_equity = self.ledger.get_total_pnl(date, book=LedgerBook.EQUITY)
        live_options = self.ledger.get_total_pnl(date, book=LedgerBook.OPTIONS)
        live_total = live_equity + live_options
        
        # Get shadow P&L
        shadow_total = self.ledger.get_total_pnl(date, book=LedgerBook.SHADOW)
        
        # Discrepancy
        discrepancy_inr = live_total - shadow_total
        
        # As % of NAV
        shadow_df = self.ledger.query(end_date=date, books=[LedgerBook.SHADOW])
        if len(shadow_df) == 0:
            return 0.0, 0.0

        nav_df = self._nav_as_of(date)
        if len(nav_df) > 0:
            current_nav = nav_df['nav_combined'].iloc[-1]
            discrepancy_pct = (discrepancy_inr / current_nav * 100) if current_nav > 0 else 0
        else:
            discrepancy_pct = 0
        
        if abs(discrepancy_pct) > self.live_shadow_threshold_pct:
            logger.warning(f"Live/Shadow discrepancy: ₹{discrepancy_inr:.2f} ({discrepancy_pct:.2f}% of NAV)")
        
        return discrepancy_inr, discrepancy_pct
    
    def detect_accounting_integrity_failure(self, date: datetime) -> List[str]:
        """
        Runs accounting consistency checks.
        Returns list of detected integrity failures.
        """
        failures = []
        
        # Get ledger entries for the date
        df = self.ledger.query(start_date=date, end_date=date)
        
        if len(df) == 0:
            return failures
        
        # Check 1: No negative quantities for equity long-only
        equity_df = df[df['book'] == 'EQUITY']
        if len(equity_df) > 0:
            # For long-only, all positions should be non-negative after aggregation
            # (individual sells can be negative, but net position should be >= 0).
            # Uses the full ledger history up to `date`, not just this single
            # day's entries, since a net-negative position can only be
            # detected by aggregating buys/sells across a ticker's whole
            # history (get_open_positions already does this correctly).
            equity_positions = self.ledger.get_open_positions(as_of_date=date, book=LedgerBook.EQUITY)
            if not equity_positions.empty:
                negative_positions = equity_positions[equity_positions['quantity'] < 0]
                if not negative_positions.empty:
                    tickers = ', '.join(negative_positions['ticker'].astype(str).tolist())
                    failures.append(
                        f"Long-only equity book has net negative position(s) as of {date.date()}: {tickers}"
                    )

        # Check 2: Transaction costs must be negative
        positive_costs = df[df['transaction_cost'] > 0]
        if len(positive_costs) > 0:
            failures.append(f"Found {len(positive_costs)} entries with positive transaction costs")
        
        # Check 3: MTM + realized should equal daily P&L change
        mtm_entries = df[df['entry_type'].str.contains('MTM')]
        realized_entries = df[~df['entry_type'].str.contains('MTM')]
        
        mtm_pnl = mtm_entries['net_pnl'].sum()
        realized_pnl = realized_entries['net_pnl'].sum()
        total_pnl = df['net_pnl'].sum()
        
        if abs((mtm_pnl + realized_pnl) - total_pnl) > 1.0:  # ₹1 tolerance for rounding
            failures.append(f"MTM + realized P&L doesn't match total: {mtm_pnl + realized_pnl:.2f} vs {total_pnl:.2f}")
        
        # Check 4: the immutable ledger and its POSITION MATERIALISATION must agree.
        #
        # Reconcile against data/pnl/current_positions.parquet — the authoritative
        # materialisation of THIS ledger's book (written by the paper-fund engine
        # from the same ledger). A per-ticker mismatch there is a real
        # materialisation bug worth a CRITICAL.
        #
        # We deliberately do NOT reconcile against data/portfolio/
        # current_positions.json here: that file is the LIVE/advisory runtime view
        # (what is actually executed — 0 in advisory mode), a DIFFERENT book from
        # the paper-fund simulation the ledger records. Comparing the simulated
        # ledger against the (correctly empty / independently-updated) live tracker
        # produced dozens of misleading "position mismatch" CRITICALs that were
        # really just the sim-vs-live gap, not accounting corruption.
        positions_parquet = Path("data/pnl/current_positions.parquet")
        if positions_parquet.exists():
            try:
                materialised = pd.read_parquet(positions_parquet)
            except Exception as e:
                failures.append(f"Could not read current_positions.parquet for reconciliation: {e}")
                materialised = None

            if materialised is not None and "ticker" in materialised.columns:
                mat_qty = dict(zip(
                    materialised["ticker"].astype(str),
                    pd.to_numeric(materialised.get("quantity"), errors="coerce").fillna(0.0),
                ))
                ledger_positions = self.ledger.get_open_positions(as_of_date=date, book=LedgerBook.EQUITY)
                ledger_qty_by_ticker = (
                    dict(zip(ledger_positions['ticker'].astype(str), ledger_positions['quantity']))
                    if not ledger_positions.empty else {}
                )
                qty_tolerance = 1.0  # shares; absorbs rounding, not real drift
                for ticker in sorted(set(ledger_qty_by_ticker) | set(mat_qty)):
                    lq = float(ledger_qty_by_ticker.get(ticker, 0.0))
                    mq = float(mat_qty.get(ticker, 0.0))
                    if abs(lq - mq) > qty_tolerance:
                        failures.append(
                            f"Position materialisation mismatch for {ticker}: ledger {lq:.2f} shares "
                            f"vs current_positions.parquet {mq:.2f} shares"
                        )

        return failures
    
    def write_reconciliation_log(self, result: ReconciliationResult) -> None:
        """Appends reconciliation result to log file"""
        output_path = Path("data/pnl/reconciliation_log.parquet")
        
        # Convert to dict
        row = {
            'date': result.date,
            'equity_options_balanced': result.equity_options_balanced,
            'equity_options_discrepancy_inr': result.equity_options_discrepancy_inr,
            'live_shadow_discrepancy_inr': result.live_shadow_discrepancy_inr,
            'live_shadow_discrepancy_pct': result.live_shadow_discrepancy_pct,
            'live_shadow_flag': result.live_shadow_flag,
            'overall_status': result.overall_status,
            'action_count': len(result.action_required),
            'actions': '; '.join(result.action_required) if result.action_required else '',
        }
        
        # Append to file
        if output_path.exists():
            existing_df = pd.read_parquet(output_path)
            new_df = pd.DataFrame([row])
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = pd.DataFrame([row])
        
        combined_df.to_parquet(output_path, index=False)
        
        logger.info(f"Wrote reconciliation log to {output_path}")
