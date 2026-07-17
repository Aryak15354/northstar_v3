#!/usr/bin/env python3
"""
🧪 BACKTEST ENGINE - INSTITUTIONAL GRADE
Complete backtesting system that judges all strategies every day

This is the scientific instrument that transforms Northstar from a model
into a self-correcting ecosystem of competing intelligences.

Usage:
    from src.backtesting.backtest_engine import BacktestEngine
    
    engine = BacktestEngine()
    engine.run_all_strategies()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable
import warnings

# =========================== TEMPORAL PROTECTION ENABLED ===========================
# This backtest engine enforces point-in-time constraints to prevent look-ahead bias.
# All data access goes through TemporalGuard to ensure data[timestamp <= current_time].
# =================================================================================

from src.intelligence.temporal_guard import TemporalGuard
from src.intelligence.temporal_signal_engine import TemporalSignalEngine
from src.validation.universe_manager import UniverseManager
from src.runtime import (
    DecisionMode,
    PortfolioRuntimeService,
    ProposalOrigin,
    TradeProposal,
    build_certification_snapshot,
)
from src.runtime.hash_utils import canonical_hash, file_sha256
from src.portfolio.strategies import AVAILABLE_STRATEGIES
from src.data.price_access import canonical_price_path, read_prices_legacy

warnings.filterwarnings('ignore')


def _default_prices_path() -> str:
    return str(canonical_price_path())


class BacktestEngine:
    """
    Complete Backtesting System for Strategy Evaluation
    
    This engine runs every strategy through the same market conditions
    and produces standardized performance metrics for comparison.
    """
    
    def __init__(self):
        self.name = "Northstar Backtest Engine"
        self.version = "3.0"
        
        # File paths
        self.paths = {
            'prices': _default_prices_path(),
            'market_state': 'data/processed/market_state.parquet',
            'strategy_portfolios': 'data/processed/strategy_portfolios',
            'strategy_performance': 'data/processed/strategy_performance',
            'backtests': 'data/processed/backtests',
            'performance_master': 'data/processed/performance/master.parquet'
        }
        
        # Create directories
        for path in ['data/processed/strategy_portfolios', 'data/processed/strategy_performance', 
                     'data/processed/backtests', 'data/processed/performance']:
            os.makedirs(path, exist_ok=True)
        
        # One-way transaction cost applied to turnover on rebalance (brokerage +
        # STT + exchange charges + a conservative market-impact estimate for
        # Indian large/mid-cap equities). Previously this engine charged zero
        # cost anywhere in the loop, structurally inflating every backtested
        # Sharpe/return relative to what's achievable live.
        self.transaction_cost_bps = 15.0

        # Strategy universe
        self.strategies = list(AVAILABLE_STRATEGIES)
        
        # Performance schema
        self.performance_schema = {
            'date': 'datetime64[ns]',
            'strategy': 'string',
            'equity': 'float64',
            'daily_return': 'float64',
            'drawdown': 'float64',
            'vol_20d': 'float64',
            'exposure': 'float64',
            'cash': 'float64',
            'turnover': 'float64',
            'macro_regime': 'string',
            'vol_regime': 'string',
            'liquidity_regime': 'string',
            'risk_on_prob': 'float64',
            'alpha': 'float64',
            'beta_nifty': 'float64',
            'pnl_macro': 'float64',
            'pnl_value': 'float64',
            'pnl_momentum': 'float64',
            'pnl_flows': 'float64',
            'n_positions': 'int64',
            'top5_concentration': 'float64',
            'sector_max': 'float64',
            'effective_positions': 'float64',
            'long_short': 'float64',
            'signal_conviction': 'float64',
            'model_confidence': 'float64',
            'regime_alignment': 'float64',
            'prediction_error': 'float64'
        }

        # Point-in-time universe authority (includes delisted handling).
        self.universe_manager = UniverseManager()
        self.prs = None
        self.prs_context = {}
        self.prs_cert_snapshot_hash = ""
        self._active_prs_strategy = ""
        self._prs_runtime_enabled = str(
            os.getenv("NORTHSTAR_BACKTEST_ENABLE_PRS", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._strict_universe_reconstruction = str(
            os.getenv("NORTHSTAR_STRICT_UNIVERSE_RECONSTRUCTION", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._prebuild_universe_snapshots = str(
            os.getenv("NORTHSTAR_PREBUILD_UNIVERSE_SNAPSHOTS", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._engine_instance_tag = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self._backtest_run_counter = 0

    def _strategy_db_path(self, strategy_name: str) -> str:
        safe = str(strategy_name).replace(" ", "_").lower()
        return str(Path("data/runtime") / f"backtest_{safe}.db")

    def _strategy_materialized_dir(self, strategy_name: str) -> str:
        safe = str(strategy_name).replace(" ", "_").lower()
        return str(Path("data/processed/runtime/backtest") / safe)

    def _build_prs_context(self, strategy_name: str) -> Dict[str, str]:
        prices_path = Path(self.paths['prices'])
        market_state_path = Path(self.paths['market_state'])
        config_hash = ""
        try:
            config_hash = file_sha256(__file__)
        except Exception:
            config_hash = ""
        return {
            "model_hash": canonical_hash({"engine": self.name, "version": self.version, "strategy": strategy_name}),
            "param_hash": canonical_hash({"lookback": 252, "rebalance": "weekly"}),
            "feature_hash": canonical_hash(["prices", "market_state", "strategy_weights"]),
            "data_revision_hash": canonical_hash(
                {
                    "prices_mtime_ns": prices_path.stat().st_mtime_ns if prices_path.exists() else 0,
                    "market_state_mtime_ns": market_state_path.stat().st_mtime_ns if market_state_path.exists() else 0,
                }
            ),
            "config_hash": config_hash,
            "drift_guard_version": "v1",
        }

    def _ensure_prs_for_strategy(self, strategy_name: str) -> None:
        if not self._prs_runtime_enabled:
            self.prs = None
            self.prs_context = {}
            self.prs_cert_snapshot_hash = ""
            self._active_prs_strategy = ""
            return
        if self.prs is not None and self._active_prs_strategy == strategy_name:
            return
        self.prs = PortfolioRuntimeService(
            db_path=self._strategy_db_path(strategy_name),
            materialized_output_dir=self._strategy_materialized_dir(strategy_name),
            starting_cash=1_000_000.0,
        )
        self.prs_context = self._build_prs_context(strategy_name)
        snap = build_certification_snapshot(
            model_hash=str(self.prs_context.get("model_hash", "")),
            param_hash=str(self.prs_context.get("param_hash", "")),
            feature_hash=str(self.prs_context.get("feature_hash", "")),
            data_revision_hash=str(self.prs_context.get("data_revision_hash", "")),
            config_hash=str(self.prs_context.get("config_hash", "")),
            created_at=datetime.utcnow(),
            ttl_days=30,
            drift_guard_version="v1",
        )
        self.prs.register_certification_snapshot(snap)
        self.prs_cert_snapshot_hash = str(snap.snapshot_hash)
        self._active_prs_strategy = strategy_name

    def _emit_rebalance_proposals(
        self,
        strategy_name: str,
        run_id: str,
        date: pd.Timestamp,
        target_weights: pd.Series,
        previous_weights: pd.Series,
        prices_row: pd.Series,
    ) -> int:
        if self.prs is None:
            return 0
        tickers = set(target_weights.index) | set(previous_weights.index)
        emitted = 0
        for ticker in sorted(tickers):
            tgt = float(target_weights.get(ticker, 0.0) or 0.0)
            prev = float(previous_weights.get(ticker, 0.0) or 0.0)
            delta_w = tgt - prev
            if abs(delta_w) < 1e-9:
                continue
            px = float(prices_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0.0:
                continue
            notional = float(abs(delta_w) * 1_000_000.0)
            qty = float(max(1.0, notional / px))
            side = "buy" if delta_w > 0.0 else "sell"
            now_tag = pd.Timestamp(date).strftime("%Y%m%d")
            proposal = TradeProposal(
                proposal_id=f"prop_bt_{strategy_name}_{run_id}_{ticker}_{now_tag}",
                origin=ProposalOrigin.BACKTEST,
                strategy_id=str(strategy_name),
                signal_id=f"sig_bt_{strategy_name}_{run_id}_{ticker}_{now_tag}",
                alpha_type="directional",
                expected_edge=0.0,
                risk_score=float(abs(delta_w)),
                regime_context={
                    "engine": "backtest_engine",
                    "run_id": str(run_id),
                    "date": str(pd.Timestamp(date).date()),
                },
                instrument_plan={
                    "symbol": str(ticker).upper(),
                    "side": side,
                    "price": px,
                    "quantity": qty,
                    "direction": 1.0 if side == "buy" else -1.0,
                    "instrument_type": "equity",
                    "lifecycle_action": "open" if tgt > 0.0 else "close",
                    "position_key": f"backtest:{strategy_name}:{str(ticker).upper()}",
                },
                requested_notional=notional,
                certification_snapshot_hash=str(self.prs_cert_snapshot_hash or ""),
                decision_mode=DecisionMode.AUTO,
                trigger_reason_code="rebalance.backtest.weekly",
                risk_override_flag=False,
            )
            result = self.prs.process_proposal(
                proposal,
                budget_snapshot={"reserve_usage": {}},
                risk_snapshot={"risk_budget_ratio": 0.0, "signal_entropy": 1.0},
                market_snapshot={},
                market_liquidity_snapshot={
                    "adv_notional": float(notional * 20.0),
                    "spread_bps": 5.0,
                    "depth_qty": float(qty * 10.0),
                    "estimated_slippage_bps": 2.0,
                },
                certification_context=dict(self.prs_context),
                auto_fill=True,
            )
            if result.approved:
                emitted += 1
        return emitted
    
    def load_prices(self):
        """Load and prepare price data"""
        
        print("📈 Loading price data for backtesting...")
        
        if not Path(self.paths['prices']).exists():
            raise FileNotFoundError(f"Price data not found: {self.paths['prices']}")

        prices_df = read_prices_legacy(columns=["Date", "ticker", "Close"])

        ticker_col = None
        for candidate in ('ticker', 'Ticker', 'symbol', 'Symbol'):
            if candidate in prices_df.columns:
                ticker_col = candidate
                break

        close_col = None
        for candidate in ('Close', 'close', 'adj_close', 'Adj Close'):
            if candidate in prices_df.columns:
                close_col = candidate
                break

        date_col = None
        for candidate in ('Date', 'date', 'Timestamp', 'timestamp'):
            if candidate in prices_df.columns:
                date_col = candidate
                break

        # Convert long-form OHLCV data into the daily price surface expected by the engine.
        if ticker_col and close_col and date_col:
            norm = prices_df[[date_col, ticker_col, close_col]].copy()
            norm[date_col] = pd.to_datetime(norm[date_col], errors='coerce').dt.normalize()
            norm[ticker_col] = norm[ticker_col].astype(str).str.strip()
            norm[close_col] = pd.to_numeric(norm[close_col], errors='coerce')
            norm = norm.dropna(subset=[date_col, ticker_col, close_col])
            norm = norm.sort_values([date_col, ticker_col])
            prices_pivot = norm.pivot_table(
                index=date_col,
                columns=ticker_col,
                values=close_col,
                aggfunc='last',
            ).sort_index()
            prices_pivot = prices_pivot.ffill().dropna(how='all')
        else:
            prices_pivot = prices_df.copy()
            if not isinstance(prices_pivot.index, pd.DatetimeIndex):
                try:
                    prices_pivot.index = pd.to_datetime(prices_pivot.index, errors='coerce')
                except Exception:
                    pass
            if isinstance(prices_pivot.index, pd.DatetimeIndex):
                prices_pivot.index = prices_pivot.index.normalize()
                prices_pivot = prices_pivot.sort_index()
        
        print(f"   ✅ Loaded {len(prices_pivot)} days × {len(prices_pivot.columns)} assets")
        return prices_pivot
    
    def load_market_state(self):
        """Load market state for regime awareness"""
        
        try:
            if os.path.exists(self.paths['market_state']):
                market_df = pd.read_parquet(self.paths['market_state'])
                date_col = None
                for candidate in ('Date', 'date', 'timestamp', 'Timestamp', 'last_updated'):
                    if candidate in market_df.columns:
                        date_col = candidate
                        break

                if date_col is None:
                    raise KeyError("No date column found in market_state parquet")

                market_df[date_col] = pd.to_datetime(market_df[date_col], errors='coerce').dt.normalize()
                market_df = market_df.dropna(subset=[date_col]).sort_values(date_col)
                market_df = market_df.groupby(date_col, as_index=False).tail(1)

                # Canonicalize field names used across legacy and current components.
                if 'vol_regime' not in market_df.columns and 'volatility_regime' in market_df.columns:
                    market_df['vol_regime'] = market_df['volatility_regime']
                if 'liquidity_regime' not in market_df.columns and 'liquidity_state' in market_df.columns:
                    market_df['liquidity_regime'] = market_df['liquidity_state']
                if 'risk_on_probability' not in market_df.columns and 'risk_on_prob' in market_df.columns:
                    market_df['risk_on_probability'] = market_df['risk_on_prob']

                market_df = market_df.set_index(date_col).sort_index()
                print(f"   ✅ Loaded market state: {len(market_df)} observations")
                return market_df
        except Exception as e:
            print(f"   ⚠️ Could not load market state: {e}")
        
        return pd.DataFrame()
    
    def generate_strategy_weights(self, strategy_name, date=None):
        """Generate weights for a strategy on a specific date"""
        
        try:
            # Add current directory to path
            import sys
            import os
            
            # Import strategy builder
            from src.portfolio.strategies import build_strategy_portfolio
            
            # Build portfolio for this strategy
            portfolio = build_strategy_portfolio(strategy_name, as_of_date=date)
            
            if portfolio.empty or 'weight' not in portfolio.columns:
                return pd.Series(dtype=float)
            
            # Convert to series
            weights = portfolio.set_index('ticker')['weight']
            return weights
            
        except Exception as e:
            print(f"   ⚠️ Error generating {strategy_name} weights: {e}")
            return pd.Series(dtype=float)
    
    def run_backtest(self, strategy_name, prices, market_state, start_date=None, end_date=None):
        """Run backtest for a single strategy"""

        print(f"🧪 Backtesting {strategy_name}...")
        self._ensure_prs_for_strategy(strategy_name)
        self._backtest_run_counter += 1
        run_id = f"{self._engine_instance_tag}_r{self._backtest_run_counter:06d}"
        
        # Set date range
        if start_date is None:
            start_date = prices.index[-252] if len(prices) > 252 else prices.index[0]
        if end_date is None:
            end_date = prices.index[-1]
        
        # Filter data
        backtest_prices = prices.loc[start_date:end_date]
        backtest_market = market_state.loc[start_date:end_date] if not market_state.empty else pd.DataFrame()

        # Optional snapshot artifact generation; disabled by default to keep
        # backtest/property-test runtime within deterministic deadlines.
        if self._prebuild_universe_snapshots:
            try:
                self.universe_manager.build_historical_universe_snapshots(
                    pd.to_datetime(start_date),
                    pd.to_datetime(end_date),
                    apply_liquidity_filter=True,
                    apply_survivorship_filter=True,
                )
            except Exception as e:
                print(f"   ⚠️ Universe snapshot build skipped: {e}")
        
        # Initialize tracking
        equity = 1.0
        results = []
        previous_weights = pd.Series(dtype=float)
        cumulative_delisted_symbols = set()
        current_weights = pd.Series(dtype=float)

        # Daily backtest loop
        for date in backtest_prices.index:
            delisted_today = self.universe_manager.get_delisted_symbols_on_date(
                pd.to_datetime(date).to_pydatetime()
            )
            cumulative_delisted_symbols.update(delisted_today.keys())

            if self._strict_universe_reconstruction:
                universe_pti = self.universe_manager.get_universe_at_date(
                    pd.to_datetime(date).to_pydatetime(),
                    apply_liquidity_filter=True,
                    apply_survivorship_filter=True,
                    verbose=False,
                )
                tradeable_tickers = {
                    t for t, meta in universe_pti.items()
                    if bool(meta.get('tradeable', False))
                }
            else:
                prices_row = backtest_prices.loc[date]
                tradeable_tickers = set(prices_row[prices_row.notna()].index.tolist())
                if cumulative_delisted_symbols:
                    tradeable_tickers = tradeable_tickers - cumulative_delisted_symbols
            
            # 1. Calculate today's return using the weights already held coming
            # into today -- i.e. decided at the LAST rebalance, strictly before
            # today's close. The new weights computed in step 2 below use
            # today's close price/signals and cannot be credited with today's
            # own return: that would mean deciding a position using a price
            # you could not have observed until the close, then also capturing
            # the return that produced that same close -- a same-day
            # look-ahead bias that mechanically flatters momentum/low-vol
            # strategies (whose scores are directly correlated with the very
            # return being captured) on every rebalance day.
            if len(results) > 0:
                price_returns = backtest_prices.loc[date] / backtest_prices.shift(1).loc[date] - 1
                price_returns = price_returns.fillna(0)

                # If held names delist today, apply delisting impact and remove them.
                delist_penalty = 0.0
                if delisted_today:
                    for sym, payload in delisted_today.items():
                        if sym in current_weights.index and current_weights.get(sym, 0.0) > 0:
                            pnl_impact = float(payload.get('pnl_impact', -1.0))
                            delist_penalty += float(current_weights.get(sym, 0.0)) * pnl_impact
                            current_weights.loc[sym] = 0.0

                # Keep stale/untradeable names in cash after delisting.
                if current_weights.sum() > 0:
                    current_weights = current_weights / current_weights.sum()

                # Portfolio return
                portfolio_return = (current_weights * price_returns.reindex(current_weights.index).fillna(0)).sum()
                portfolio_return += delist_penalty
            else:
                portfolio_return = 0.0

            # 2. AFTER crediting today's return to the OLD weights, decide the
            # NEW weights using today's close (as_of_date=date) -- these take
            # effect starting tomorrow, the earliest point they could actually
            # be executed at.
            if len(results) == 0 or len(results) % 5 == 0:  # Weekly rebalancing
                new_weights = self.generate_strategy_weights(strategy_name, date).copy()

                # Align with available prices
                available_tickers = (
                    backtest_prices.columns.intersection(new_weights.index)
                )
                if tradeable_tickers:
                    available_tickers = pd.Index(
                        [t for t in available_tickers if t in tradeable_tickers]
                    )
                new_weights = new_weights.reindex(available_tickers).fillna(0)
                new_weights = new_weights / new_weights.sum() if new_weights.sum() > 0 else new_weights
                _ = self._emit_rebalance_proposals(
                    strategy_name=strategy_name,
                    run_id=run_id,
                    date=pd.Timestamp(date),
                    target_weights=new_weights,
                    previous_weights=current_weights,
                    prices_row=backtest_prices.loc[date],
                )
                current_weights = new_weights

            # Calculate turnover (compares weights held today vs. the newly
            # decided weights taking effect tomorrow -- this IS the trading
            # that occurs today, so it's also the basis for transaction costs).
            if not previous_weights.empty:
                turnover = (current_weights - previous_weights.reindex(current_weights.index).fillna(0)).abs().sum()
            else:
                turnover = current_weights.abs().sum()

            # Transaction costs: charged on turnover the day it's incurred.
            # Previously this engine had no cost model anywhere in the loop,
            # so backtested Sharpe/return numbers were structurally inflated
            # relative to what's achievable live.
            transaction_cost = turnover * (self.transaction_cost_bps / 10000.0)
            portfolio_return -= transaction_cost
            equity *= (1 + portfolio_return)

            # Get market state
            market_row = backtest_market.loc[date] if date in backtest_market.index else {}
            
            # Calculate metrics
            exposure = current_weights.sum()
            cash = 1.0 - exposure
            n_positions = (current_weights > 0.001).sum()
            top5_concentration = current_weights.nlargest(5).sum() if len(current_weights) >= 5 else current_weights.sum()
            effective_positions = 1 / (current_weights ** 2).sum() if (current_weights ** 2).sum() > 0 else 0
            
            # Create result row
            result = {
                'date': date,
                'strategy': strategy_name,
                'equity': equity,
                'daily_return': portfolio_return,
                'drawdown': 0.0,  # Will calculate later
                'vol_20d': 0.0,   # Will calculate later
                'exposure': exposure,
                'cash': cash,
                'turnover': turnover,
                'macro_regime': market_row.get('macro_regime', 'unknown'),
                'vol_regime': market_row.get('vol_regime', 'unknown'),
                'liquidity_regime': market_row.get('liquidity_regime', 'unknown'),
                'risk_on_prob': market_row.get('risk_on_probability', 0.5),
                'alpha': portfolio_return,  # Simplified
                'beta_nifty': 1.0,  # Simplified
                'pnl_macro': 0.0,   # Attribution placeholder
                'pnl_value': 0.0,
                'pnl_momentum': 0.0,
                'pnl_flows': 0.0,
                'n_positions': n_positions,
                'top5_concentration': top5_concentration,
                'sector_max': 0.0,  # Placeholder
                'effective_positions': effective_positions,
                'long_short': exposure,  # All long for now
                'signal_conviction': 0.5,  # Placeholder
                'model_confidence': 0.5,   # Placeholder
                'regime_alignment': 0.5,   # Placeholder
                'prediction_error': 0.0    # Placeholder
            }
            
            results.append(result)
            previous_weights = current_weights.copy()
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        
        # Calculate rolling metrics
        if len(results_df) > 1:
            # Drawdown
            equity_series = results_df['equity']
            running_max = equity_series.expanding().max()
            results_df['drawdown'] = (equity_series / running_max) - 1
            
            # Rolling volatility
            returns_series = results_df['daily_return']
            results_df['vol_20d'] = returns_series.rolling(20, min_periods=5).std() * np.sqrt(252)
        
        return results_df

    def _summarize_strategy_results(self, strategy: str, results: pd.DataFrame) -> Dict[str, float] | None:
        if results is None or results.empty:
            return None
        final_equity = float(results['equity'].iloc[-1])
        total_return = final_equity - 1.0
        returns = pd.to_numeric(results['daily_return'], errors='coerce').fillna(0.0)

        if len(returns) > 1:
            ann_return = (final_equity ** (252 / len(returns))) - 1
            volatility = float(returns.std() * np.sqrt(252))
            sharpe = ann_return / volatility if volatility > 0 else 0.0
            max_dd = float(pd.to_numeric(results['drawdown'], errors='coerce').fillna(0.0).min())
        else:
            ann_return = 0.0
            volatility = 0.0
            sharpe = 0.0
            max_dd = 0.0

        return {
            'strategy': strategy,
            'total_return': float(total_return),
            'ann_return': float(ann_return),
            'volatility': float(volatility),
            'sharpe': float(sharpe),
            'max_drawdown': float(max_dd),
            'final_equity': float(final_equity),
            'avg_exposure': float(pd.to_numeric(results['exposure'], errors='coerce').fillna(0.0).mean()),
            'avg_positions': float(pd.to_numeric(results['n_positions'], errors='coerce').fillna(0.0).mean()),
            'avg_turnover': float(pd.to_numeric(results['turnover'], errors='coerce').fillna(0.0).mean()),
        }

    def _write_summary_artifacts(
        self,
        strategy_summaries: Dict[str, Dict[str, float]],
        all_results: Iterable[pd.DataFrame],
    ) -> None:
        results_list = [df for df in all_results if isinstance(df, pd.DataFrame) and not df.empty]
        if results_list:
            master_results = pd.concat(results_list, ignore_index=True)
            master_results.to_parquet(self.paths['performance_master'], index=False)
            print(f"\n✅ Master performance file saved: {len(master_results)} records")

        if strategy_summaries:
            summary_df = pd.DataFrame(strategy_summaries).T
            summary_df.index.name = 'strategy'
            summary_file = os.path.join(self.paths['strategy_performance'], 'summary.parquet')
            summary_df.to_parquet(summary_file)
            if 'strategy' in summary_df.columns:
                flat_summary = summary_df.reset_index(drop=True)
            else:
                flat_summary = summary_df.reset_index()
            flat_summary.to_parquet('data/processed/strategy_performance.parquet', index=False)

            # Also save as JSON for easy loading
            summary_json = os.path.join(self.paths['strategy_performance'], 'summary.json')
            with open(summary_json, 'w') as f:
                json.dump(strategy_summaries, f, indent=2, default=str)

            print(f"✅ Strategy summaries saved: {len(strategy_summaries)} strategies")

    def rebuild_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Recompute summary artifacts from backtest parquet files already on disk."""
        strategy_summaries: Dict[str, Dict[str, float]] = {}
        all_results = []
        backtests_dir = Path(self.paths['backtests'])
        if not backtests_dir.exists():
            return strategy_summaries

        for path in sorted(backtests_dir.glob("*.parquet")):
            strategy = path.stem
            try:
                results = pd.read_parquet(path)
            except Exception as e:
                print(f"   ⚠️ Could not load backtest {strategy}: {e}")
                continue
            summary = self._summarize_strategy_results(strategy, results)
            if summary is None:
                continue
            strategy_summaries[strategy] = summary
            all_results.append(results)

        self._write_summary_artifacts(strategy_summaries, all_results)
        return strategy_summaries
    
    def run_all_strategies(self, lookback_days=252, strategies=None):
        """Run backtests for all strategies"""
        
        print("🧪 RUNNING COMPLETE STRATEGY BACKTESTS")
        print("=" * 60)
        
        # Load data
        prices = self.load_prices()
        market_state = self.load_market_state()
        
        # Set date range
        end_date = prices.index[-1]
        start_date = prices.index[-lookback_days] if len(prices) > lookback_days else prices.index[0]
        
        print(f"📅 Backtest period: {start_date.date()} to {end_date.date()}")
        strategy_list = list(strategies or self.strategies)
        print(f"🎯 Testing {len(strategy_list)} strategies")
        
        # Run backtests
        all_results = []
        strategy_summaries = {}
        
        for strategy in strategy_list:
            try:
                results = self.run_backtest(strategy, prices, market_state, start_date, end_date)
                
                if not results.empty:
                    # Save individual strategy results
                    strategy_file = os.path.join(self.paths['backtests'], f"{strategy}.parquet")
                    results.to_parquet(strategy_file, index=False)
                    
                    summary = self._summarize_strategy_results(strategy, results)
                    if summary is None:
                        continue
                    strategy_summaries[strategy] = summary
                    all_results.append(results)
                    
                    print(f"   ✅ {strategy}: {summary['ann_return']:.1%} return, {summary['sharpe']:.2f} Sharpe")
                
            except Exception as e:
                print(f"   ❌ {strategy}: Error - {e}")
        
        self._write_summary_artifacts(strategy_summaries, all_results)
        
        print(f"\n🎉 BACKTEST COMPLETE!")
        if strategy_summaries:
            print(f"   Best Strategy: {max(strategy_summaries.keys(), key=lambda x: strategy_summaries[x]['sharpe'])}")
        else:
            print("   Best Strategy: none (no successful backtests)")
        print(f"   Results saved in: {self.paths['backtests']}")
        
        return strategy_summaries
    
    def get_strategy_performance(self, strategy_name):
        """Get performance metrics for a specific strategy"""
        
        try:
            strategy_file = os.path.join(self.paths['backtests'], f"{strategy_name}.parquet")
            if os.path.exists(strategy_file):
                return pd.read_parquet(strategy_file)
        except Exception as e:
            print(f"Error loading {strategy_name} performance: {e}")
        
        return pd.DataFrame()

def main():
    """Main execution function"""
    
    engine = BacktestEngine()
    summaries = engine.run_all_strategies()
    
    return summaries

if __name__ == "__main__":
    main()
