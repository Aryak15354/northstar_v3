"""
ExecutionQualityMonitor — Measures trading execution quality

Compares actual execution prices to benchmark prices (shadow system).
Primary execution benchmarks: VWAP, TWAP, Arrival price, Market-on-close.

Implementation market: India (NSE/BSE)
Exchange-specific costs included in measurement.
"""

from datetime import datetime
from typing import Dict
from pathlib import Path
import pandas as pd
import numpy as np
import logging

from .ledger import UnifiedPnLLedger, LedgerBook

logger = logging.getLogger(__name__)


class ExecutionQualityMonitor:
    """Measures trading execution quality via live vs shadow comparison"""
    
    def __init__(self, ledger: UnifiedPnLLedger, config: dict = None):
        self.ledger = ledger
        self.config = config or {}
    
    def compute_daily_slippage(self, date: datetime) -> pd.DataFrame:
        """
        For each trade executed on the given date, computes slippage.
        Returns trade-level DataFrame with slippage metrics.
        """
        logger.info(f"Computing daily slippage for {date.date()}")
        
        # Get live trades
        live_df = self.ledger.query(
            start_date=date,
            end_date=date,
            books=[LedgerBook.EQUITY, LedgerBook.OPTIONS]
        )
        
        # Get shadow trades
        shadow_df = self.ledger.query(
            start_date=date,
            end_date=date,
            books=[LedgerBook.SHADOW]
        )
        
        if len(live_df) == 0 or len(shadow_df) == 0:
            logger.warning("No live or shadow trades for slippage computation")
            return pd.DataFrame()
        
        # Match live and shadow trades by ticker and quantity
        slippage_rows = []
        
        for _, live_trade in live_df.iterrows():
            ticker = live_trade['ticker']
            quantity = live_trade['quantity']
            live_price = live_trade['price']
            
            # Find matching shadow trade
            shadow_match = shadow_df[
                (shadow_df['ticker'] == ticker) &
                (shadow_df['quantity'] == quantity)
            ]
            
            if len(shadow_match) == 0:
                continue
            
            shadow_price = shadow_match.iloc[0]['price']
            
            # Compute slippage
            # For buys: positive slippage = paid more than expected (bad)
            # For sells: positive slippage = received less than expected (bad)
            if quantity > 0:  # Buy
                slippage_inr = (live_price - shadow_price) * quantity
            else:  # Sell
                slippage_inr = (shadow_price - live_price) * abs(quantity)
            
            slippage_bps = (slippage_inr / (shadow_price * abs(quantity)) * 10000) if shadow_price > 0 else 0
            
            slippage_rows.append({
                'ticker': ticker,
                'quantity': quantity,
                'expected_price': shadow_price,
                'actual_price': live_price,
                'slippage_bps': slippage_bps,
                'slippage_inr': slippage_inr,
                'notional': abs(quantity * shadow_price),
            })
        
        slippage_df = pd.DataFrame(slippage_rows)
        
        if len(slippage_df) > 0:
            avg_slippage = slippage_df['slippage_bps'].mean()
            logger.info(f"Average slippage: {avg_slippage:.2f} bps")
        
        return slippage_df
    
    def compute_implementation_shortfall(self, date: datetime) -> float:
        """
        Implementation shortfall: total cost of execution relative to decision price.
        Returns total IS in basis points for the day.
        """
        slippage_df = self.compute_daily_slippage(date)
        
        if len(slippage_df) == 0:
            return 0.0
        
        # Implementation shortfall is weighted average slippage
        total_notional = slippage_df['notional'].sum()
        if total_notional == 0:
            return 0.0
        
        weighted_slippage = (slippage_df['slippage_inr'].sum() / total_notional * 10000)
        
        return weighted_slippage
    
    def compute_fill_rate(self, date: datetime) -> Dict:
        """
        Measures what fraction of intended trades actually got executed.
        """
        # Get shadow trades (intended)
        shadow_df = self.ledger.query(
            start_date=date,
            end_date=date,
            books=[LedgerBook.SHADOW]
        )
        
        # Get live trades (executed)
        live_df = self.ledger.query(
            start_date=date,
            end_date=date,
            books=[LedgerBook.EQUITY, LedgerBook.OPTIONS]
        )
        
        intended_count = len(shadow_df)
        executed_count = len(live_df)
        
        fill_rate = executed_count / intended_count if intended_count > 0 else 0
        
        # Find unfilled trades
        shadow_tickers = set(shadow_df['ticker'].unique())
        live_tickers = set(live_df['ticker'].unique())
        unfilled_tickers = list(shadow_tickers - live_tickers)
        
        # Find partial fills (quantity mismatch)
        partial_fills = 0
        for ticker in shadow_tickers & live_tickers:
            shadow_qty = shadow_df[shadow_df['ticker'] == ticker]['quantity'].sum()
            live_qty = live_df[live_df['ticker'] == ticker]['quantity'].sum()
            if abs(shadow_qty - live_qty) > 0.01:
                partial_fills += 1
        
        return {
            'intended_trade_count': intended_count,
            'executed_trade_count': executed_count,
            'fill_rate': fill_rate,
            'partial_fills': partial_fills,
            'unfilled_trades': unfilled_tickers,
        }
    
    def compute_period_execution_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Rolling period execution quality summary"""
        logger.info(f"Computing execution summary from {start_date.date()} to {end_date.date()}")
        
        # Compute daily slippage for each day
        date_range = pd.date_range(start_date, end_date, freq='D')
        
        daily_slippages = []
        daily_is = []
        daily_fill_rates = []
        
        for date in date_range:
            slippage_df = self.compute_daily_slippage(date)
            if len(slippage_df) > 0:
                daily_slippages.append(slippage_df['slippage_bps'].mean())
                daily_is.append(self.compute_implementation_shortfall(date))
                
                fill_info = self.compute_fill_rate(date)
                daily_fill_rates.append(fill_info['fill_rate'])
        
        if len(daily_slippages) == 0:
            return {}
        
        # Aggregate metrics
        avg_slippage_bps = np.mean(daily_slippages)
        avg_is_bps = np.mean(daily_is)
        avg_fill_rate = np.mean(daily_fill_rates)
        
        # Find best/worst days
        best_day_idx = np.argmin(daily_slippages)
        worst_day_idx = np.argmax(daily_slippages)
        
        best_day = date_range[best_day_idx]
        worst_day = date_range[worst_day_idx]
        
        # Trend analysis (simple linear regression)
        if len(daily_slippages) > 5:
            x = np.arange(len(daily_slippages))
            slope = np.polyfit(x, daily_slippages, 1)[0]
            
            if slope < -0.5:
                trend = "IMPROVING"
            elif slope > 0.5:
                trend = "DETERIORATING"
            else:
                trend = "STABLE"
        else:
            trend = "INSUFFICIENT_DATA"
        
        # Total cost vs shadow
        live_pnl = self.ledger.get_total_pnl(end_date, book=LedgerBook.EQUITY)
        shadow_pnl = self.ledger.get_total_pnl(end_date, book=LedgerBook.SHADOW)
        cost_vs_shadow = live_pnl - shadow_pnl
        
        summary = {
            'avg_slippage_bps': avg_slippage_bps,
            'total_slippage_cost_inr': cost_vs_shadow,
            'avg_implementation_shortfall_bps': avg_is_bps,
            'avg_fill_rate': avg_fill_rate,
            'best_execution_day': best_day,
            'worst_execution_day': worst_day,
            'slippage_trend': trend,
            'cost_vs_shadow_total_inr': cost_vs_shadow,
        }
        
        logger.info(f"Execution summary: Avg slippage={avg_slippage_bps:.2f}bps, Trend={trend}")
        
        return summary
    
    def write_daily_execution_quality(self, date: datetime) -> None:
        """
        Computes and appends daily execution quality metrics to file.
        Called by eod_rebalance.py every evening.
        """
        logger.info(f"Writing daily execution quality for {date.date()}")
        
        # Compute metrics
        slippage_df = self.compute_daily_slippage(date)
        is_bps = self.compute_implementation_shortfall(date)
        fill_info = self.compute_fill_rate(date)
        
        # Create summary row
        row = {
            'date': date,
            'avg_slippage_bps': slippage_df['slippage_bps'].mean() if len(slippage_df) > 0 else 0,
            'total_slippage_inr': slippage_df['slippage_inr'].sum() if len(slippage_df) > 0 else 0,
            'implementation_shortfall_bps': is_bps,
            'fill_rate': fill_info['fill_rate'],
            'partial_fills': fill_info['partial_fills'],
            'unfilled_count': len(fill_info['unfilled_trades']),
            'trade_count': fill_info['executed_trade_count'],
        }
        
        # Append to file
        output_path = Path("data/pnl/execution_quality.parquet")
        
        if output_path.exists():
            existing_df = pd.read_parquet(output_path)
            new_df = pd.DataFrame([row])
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = pd.DataFrame([row])
        
        combined_df.to_parquet(output_path, index=False)
        
        logger.info(f"Wrote execution quality to {output_path}")
