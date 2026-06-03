"""
PnLAttributor — Decomposes total P&L into contributing sources

Attribution hierarchy:
Level 1: Book (Equity vs Options)
Level 2: Strategy (which Alpha OS strategy drove each position)
Level 3: Regime (what was the market regime when P&L was generated)
Level 4: Sector (which sectors contributed P&L)
Level 5: Factor (which factors drove P&L)
"""

from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
import pandas as pd
import logging

from .ledger import UnifiedPnLLedger, LedgerBook

logger = logging.getLogger(__name__)


class PnLAttributor:
    """Decomposes total P&L into its contributing sources"""
    
    def __init__(self, ledger: UnifiedPnLLedger, registry=None, config: dict = None):
        self.ledger = ledger
        self.registry = registry  # StrategyRegistry from Alpha OS
        self.config = config or {}
    
    def compute_strategy_attribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Returns Strategy-indexed DataFrame with P&L attribution by strategy.
        """
        logger.info(f"Computing strategy attribution from {start_date.date()} to {end_date.date()}")
        
        # Get all ledger entries
        df = self.ledger.query(start_date=start_date, end_date=end_date)
        
        if len(df) == 0:
            logger.warning("No ledger entries for attribution")
            return pd.DataFrame()
        
        # Group by strategy_id
        strategy_groups = df.groupby('strategy_id')
        
        attribution_rows = []
        
        for strategy_id, group in strategy_groups:
            if strategy_id is None or pd.isna(strategy_id):
                strategy_id = "UNATTRIBUTED"
            
            # Gross P&L (before costs)
            gross_pnl = group['realized_pnl'].sum() + group['unrealized_pnl_change'].sum()
            
            # Transaction costs
            transaction_costs = group['transaction_cost'].sum()
            
            # Net P&L
            net_pnl = group['net_pnl'].sum()
            
            # Trade count (exclude MTM entries)
            mtm_types = ['EQUITY_MTM', 'OPTIONS_MTM', 'SHADOW_MTM']
            trades = group[~group['entry_type'].isin(mtm_types)]
            trade_count = len(trades)
            
            # Win rate (for closed positions with realized P&L)
            closed_trades = trades[trades['realized_pnl'] != 0]
            winning_trades = closed_trades[closed_trades['realized_pnl'] > 0]
            win_rate = len(winning_trades) / len(closed_trades) if len(closed_trades) > 0 else 0
            
            # Average win/loss
            avg_win = winning_trades['realized_pnl'].mean() if len(winning_trades) > 0 else 0
            losing_trades = closed_trades[closed_trades['realized_pnl'] < 0]
            avg_loss = losing_trades['realized_pnl'].mean() if len(losing_trades) > 0 else 0
            
            # Profit factor
            total_wins = winning_trades['realized_pnl'].sum() if len(winning_trades) > 0 else 0
            total_losses = abs(losing_trades['realized_pnl'].sum()) if len(losing_trades) > 0 else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
            
            # P&L per trade
            pnl_per_trade = net_pnl / trade_count if trade_count > 0 else 0
            
            # Capital allocation (would need position tracking for accuracy)
            capital_weight_avg = 0.0  # TODO: compute from position book
            
            # Return on allocated capital
            return_on_capital = 0.0  # TODO: net_pnl / capital_weight_avg
            
            # Contribution to total return
            total_pnl = df['net_pnl'].sum()
            contribution_pct = (net_pnl / total_pnl * 100) if total_pnl != 0 else 0
            
            attribution_rows.append({
                'strategy_id': strategy_id,
                'gross_pnl_inr': gross_pnl,
                'transaction_costs_inr': transaction_costs,
                'net_pnl_inr': net_pnl,
                'trade_count': trade_count,
                'win_rate': win_rate,
                'avg_win_inr': avg_win,
                'avg_loss_inr': avg_loss,
                'profit_factor': profit_factor,
                'pnl_per_trade_inr': pnl_per_trade,
                'capital_weight_avg': capital_weight_avg,
                'return_on_allocated_capital': return_on_capital,
                'contribution_to_total_return_pct': contribution_pct,
            })
        
        attribution_df = pd.DataFrame(attribution_rows)
        attribution_df.set_index('strategy_id', inplace=True)
        
        logger.info(f"Computed attribution for {len(attribution_df)} strategies")
        
        return attribution_df
    
    def compute_regime_attribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Returns Regime-indexed DataFrame with P&L attribution by market regime.
        """
        logger.info(f"Computing regime attribution from {start_date.date()} to {end_date.date()}")
        
        # Load regime labels
        regime_path = Path("data/processed/regime_labels.parquet")
        if not regime_path.exists():
            logger.warning("Regime labels not found, skipping regime attribution")
            return pd.DataFrame()
        
        regime_df = pd.read_parquet(regime_path)
        regime_df['Date'] = pd.to_datetime(regime_df['Date'])
        regime_df.set_index('Date', inplace=True)
        
        # Get ledger entries
        df = self.ledger.query(start_date=start_date, end_date=end_date)
        
        if len(df) == 0:
            return pd.DataFrame()
        
        # Ensure trade_date is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # Join with regime labels
        df['date'] = df['trade_date'].dt.date
        df['date'] = pd.to_datetime(df['date'])
        df = df.merge(regime_df[['regime']], left_on='date', right_index=True, how='left')
        df['regime'] = df['regime'].fillna('UNKNOWN')
        
        # Group by regime
        regime_groups = df.groupby('regime')
        
        attribution_rows = []
        
        for regime, group in regime_groups:
            days_in_regime = group['date'].nunique()
            pnl_in_regime = group['net_pnl'].sum()
            
            # Annualized return (rough estimate)
            annualized_return = (pnl_in_regime / days_in_regime * 252) if days_in_regime > 0 else 0
            
            # P&L per day
            pnl_per_day = pnl_in_regime / days_in_regime if days_in_regime > 0 else 0
            
            # Strategy breakdown
            strategy_breakdown = group.groupby('strategy_id')['net_pnl'].sum().to_dict()
            
            attribution_rows.append({
                'regime': regime,
                'days_in_regime': days_in_regime,
                'pnl_in_regime_inr': pnl_in_regime,
                'annualized_return_in_regime': annualized_return,
                'pnl_per_day_inr': pnl_per_day,
                'strategy_breakdown': strategy_breakdown,
            })
        
        attribution_df = pd.DataFrame(attribution_rows)
        attribution_df.set_index('regime', inplace=True)
        
        logger.info(f"Computed attribution for {len(attribution_df)} regimes")
        
        return attribution_df
    
    def compute_sector_attribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Returns Sector-indexed DataFrame with P&L attribution by sector.
        """
        logger.info(f"Computing sector attribution from {start_date.date()} to {end_date.date()}")
        
        # Get ledger entries
        df = self.ledger.query(start_date=start_date, end_date=end_date)
        
        if len(df) == 0:
            logger.warning("No ledger entries for sector attribution")
            return pd.DataFrame()
        
        # Load sector mappings
        sector_mapping_path = Path("data/metadata/ticker_sector_mapping.csv")
        if not sector_mapping_path.exists():
            logger.warning("Sector mapping file not found, cannot compute sector attribution")
            return pd.DataFrame()
        
        try:
            sector_map = pd.read_csv(sector_mapping_path)
            sector_dict = dict(zip(sector_map['ticker'], sector_map['sector']))
        except Exception as e:
            logger.error(f"Error loading sector mapping: {e}")
            return pd.DataFrame()
        
        # Map tickers to sectors
        df['sector'] = df['ticker'].map(sector_dict)
        
        # Filter out entries without sector mapping
        df_with_sector = df[df['sector'].notna()].copy()
        
        if len(df_with_sector) == 0:
            logger.warning("No entries with sector mapping found")
            return pd.DataFrame()
        
        # Group by sector
        sector_groups = df_with_sector.groupby('sector')
        
        attribution_rows = []
        
        for sector, group in sector_groups:
            # Gross P&L
            gross_pnl = group['realized_pnl'].sum() + group['unrealized_pnl_change'].sum()
            
            # Transaction costs
            transaction_costs = group['transaction_cost'].sum()
            
            # Net P&L
            net_pnl = group['net_pnl'].sum()
            
            # Trade count (exclude MTM entries)
            mtm_types = ['EQUITY_MTM', 'OPTIONS_MTM', 'SHADOW_MTM']
            trades = group[~group['entry_type'].isin(mtm_types)]
            trade_count = len(trades)
            
            # Win rate
            closed_trades = trades[trades['realized_pnl'] != 0]
            winning_trades = closed_trades[closed_trades['realized_pnl'] > 0]
            win_rate = len(winning_trades) / len(closed_trades) if len(closed_trades) > 0 else 0
            
            # Contribution to total return
            total_pnl = df_with_sector['net_pnl'].sum()
            contribution_pct = (net_pnl / total_pnl * 100) if total_pnl != 0 else 0
            
            # Number of unique tickers in sector
            unique_tickers = group['ticker'].nunique()
            
            # Average P&L per ticker
            pnl_per_ticker = net_pnl / unique_tickers if unique_tickers > 0 else 0
            
            attribution_rows.append({
                'sector': sector,
                'gross_pnl_inr': gross_pnl,
                'transaction_costs_inr': transaction_costs,
                'net_pnl_inr': net_pnl,
                'trade_count': trade_count,
                'win_rate': win_rate,
                'contribution_to_total_return_pct': contribution_pct,
                'unique_tickers': unique_tickers,
                'pnl_per_ticker_inr': pnl_per_ticker,
            })
        
        attribution_df = pd.DataFrame(attribution_rows)
        attribution_df.set_index('sector', inplace=True)
        
        logger.info(f"Computed attribution for {len(attribution_df)} sectors")
        
        return attribution_df
    
    def compute_cost_attribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Breaks down total transaction costs by type and book.
        """
        logger.info(f"Computing cost attribution from {start_date.date()} to {end_date.date()}")
        
        # Get all entries with costs
        df = self.ledger.query(start_date=start_date, end_date=end_date)
        
        if len(df) == 0:
            return {}
        
        # Total costs
        total_costs = abs(df['transaction_cost'].sum())
        
        # By book
        costs_by_book = df.groupby('book')['transaction_cost'].sum().abs().to_dict()
        
        # Cost as % of gross P&L
        gross_pnl = df['realized_pnl'].sum() + df['unrealized_pnl_change'].sum()
        cost_pct = (total_costs / abs(gross_pnl) * 100) if gross_pnl != 0 else 0
        
        # Average cost per trade
        trades = df[~df['entry_type'].str.contains('MTM')]
        avg_cost_per_trade = total_costs / len(trades) if len(trades) > 0 else 0
        
        # Detailed breakdown (would need more granular cost tracking)
        cost_breakdown = {
            'total_costs_inr': total_costs,
            'by_type': {
                'brokerage': 0.0,  # TODO: break down from transaction_cost
                'stt': 0.0,
                'exchange_fees': 0.0,
                'stamp_duty': 0.0,
                'gst_on_brokerage': 0.0,
                'sebi_fees': 0.0,
                'estimated_slippage': 0.0,
            },
            'by_book': costs_by_book,
            'cost_as_pct_of_gross_pnl': cost_pct,
            'avg_cost_per_trade_inr': avg_cost_per_trade,
        }
        
        return cost_breakdown
    
    def generate_attribution_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Generates comprehensive attribution report combining all dimensions.
        """
        logger.info(f"Generating attribution report from {start_date.date()} to {end_date.date()}")
        
        report = {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'strategy_attribution': self.compute_strategy_attribution(start_date, end_date).to_dict('index'),
            'regime_attribution': self.compute_regime_attribution(start_date, end_date).to_dict('index'),
            'cost_attribution': self.compute_cost_attribution(start_date, end_date),
            'generated_at': datetime.now().isoformat(),
        }
        
        return report
    
    def write_daily_attribution(self, date: datetime) -> None:
        """
        Computes single-day attribution and appends to daily file.
        Called by eod_rebalance.py every evening.
        """
        logger.info(f"Writing daily attribution for {date.date()}")
        
        # Compute attribution for the single day
        attribution = self.generate_attribution_report(date, date)
        
        # Convert to flat DataFrame row
        row = {
            'date': date,
            'generated_at': datetime.now(),
        }
        
        # Add strategy attribution summary
        strategy_attr = attribution.get('strategy_attribution', {})
        for strategy_id, metrics in strategy_attr.items():
            row[f'strategy_{strategy_id}_net_pnl'] = metrics.get('net_pnl_inr', 0)
        
        # Add cost attribution
        cost_attr = attribution.get('cost_attribution', {})
        row['total_costs'] = cost_attr.get('total_costs_inr', 0)
        
        # Append to file
        output_path = Path("data/pnl/attribution_daily.parquet")
        
        if output_path.exists():
            existing_df = pd.read_parquet(output_path)
            new_df = pd.DataFrame([row])
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = pd.DataFrame([row])
        
        combined_df.to_parquet(output_path, index=False)
        
        logger.info(f"Wrote daily attribution to {output_path}")
