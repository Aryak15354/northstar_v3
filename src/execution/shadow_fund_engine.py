#!/usr/bin/env python3
"""
🧬 SHADOW FUND EXECUTION ENGINE
Paper trading with real market prices - the final validation

This runs Northstar as a shadow fund with virtual capital
but real market prices, slippage, and execution constraints.

Usage:
    from src.execution.shadow_fund_engine import ShadowFundEngine
    
    shadow_fund = ShadowFundEngine()
    shadow_fund.run_shadow_trading()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.execution.enhanced_transaction_cost_model import EnhancedTransactionCostModel
from src.data.price_access import canonical_price_path, read_prices_legacy
from src.runtime import DecisionMode, PortfolioRuntimeService, ProposalOrigin, TradeProposal, build_certification_snapshot
from src.runtime.hash_utils import canonical_hash, file_sha256

class ShadowFundEngine:
    """
    Shadow Fund Execution Engine
    
    Simulates real fund execution with:
    - Virtual capital (₹1 crore)
    - Real market prices
    - Transaction costs and slippage
    - Position limits and constraints
    - Daily P&L tracking
    """
    
    def __init__(self):
        self.name = "Northstar Shadow Fund"
        self.version = "2.0"  # Enhanced with advanced transaction costs
        
        # Enhanced transaction cost model
        self.cost_model = EnhancedTransactionCostModel()
        
        # Shadow fund parameters
        self.fund_params = {
            'initial_capital': 10000000,    # ₹1 crore virtual capital
            'max_position_size': 0.05,      # 5% max position size
            'min_trade_size': 10000,        # ₹10,000 minimum trade
            'cash_buffer': 0.05             # 5% cash buffer
        }
        
        # File paths. Prices point at the canonical, point-in-time-safe
        # contract (equity_prices_daily) rather than the stale legacy
        # data/processed/prices.parquet -- this is the shadow-fund execution
        # path, so it must not size positions off missing/stale tickers.
        self.paths = {
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'prices': str(canonical_price_path()),
            'shadow_positions': 'data/execution/shadow_positions.parquet',
            'shadow_trades': 'data/execution/shadow_trades.parquet',
            'shadow_pnl': 'data/execution/shadow_pnl.parquet',
            'shadow_fund_report': 'data/execution/shadow_fund_report.json'
        }
        
        # Create execution directory
        os.makedirs('data/execution', exist_ok=True)
        
        # Current fund state
        self.current_capital = self.fund_params['initial_capital']
        self.current_positions = {}
        self.execution_log = []
        self.prs = None
        self.prs_context = {}
        self.prs_cert_snapshot_hash = ""
        self._init_prs_runtime()

    def _runtime_db_path(self) -> str:
        rel = str(
            os.getenv(
                "NORTHSTAR_PRS_SHADOW_FUND_DB",
                "data/runtime/shadow_fund_runtime.db",
            )
            or "data/runtime/shadow_fund_runtime.db"
        )
        base = Path(rel)
        if os.getenv("PYTEST_CURRENT_TEST"):
            return str(base.with_name(f"{base.stem}_{os.getpid()}_{id(self)}{base.suffix}"))
        return str(base)

    def _runtime_materialized_dir(self) -> str:
        rel = str(
            os.getenv(
                "NORTHSTAR_PRS_SHADOW_FUND_MATERIALIZED",
                "data/processed/runtime/shadow_fund",
            )
            or "data/processed/runtime/shadow_fund"
        )
        base = Path(rel)
        if os.getenv("PYTEST_CURRENT_TEST"):
            return str(base.with_name(f"{base.name}_{os.getpid()}_{id(self)}"))
        return str(base)

    def _build_prs_context(self) -> dict:
        prices_path = Path(self.paths["prices"])
        weights_path = Path(self.paths["portfolio_weights"])
        config_hash = ""
        try:
            config_hash = file_sha256(__file__)
        except Exception:
            config_hash = ""
        return {
            "model_hash": canonical_hash({"engine": self.name, "version": self.version}),
            "param_hash": canonical_hash(self.fund_params),
            "feature_hash": canonical_hash(["final_weight", "Close"]),
            "data_revision_hash": canonical_hash(
                {
                    "prices_mtime_ns": prices_path.stat().st_mtime_ns if prices_path.exists() else 0,
                    "weights_mtime_ns": weights_path.stat().st_mtime_ns if weights_path.exists() else 0,
                }
            ),
            "config_hash": config_hash,
            "drift_guard_version": "v1",
        }

    def _refresh_prs_certification_snapshot(self) -> str:
        if self.prs is None:
            return ""
        now = datetime.utcnow()
        ctx = dict(self.prs_context)
        snap = build_certification_snapshot(
            model_hash=str(ctx.get("model_hash", "")),
            param_hash=str(ctx.get("param_hash", "")),
            feature_hash=str(ctx.get("feature_hash", "")),
            data_revision_hash=str(ctx.get("data_revision_hash", "")),
            config_hash=str(ctx.get("config_hash", "")),
            created_at=now,
            ttl_days=30,
            drift_guard_version=str(ctx.get("drift_guard_version", "v1") or "v1"),
        )
        self.prs.register_certification_snapshot(snap)
        return str(snap.snapshot_hash)

    def _init_prs_runtime(self) -> None:
        self.prs = PortfolioRuntimeService(
            db_path=self._runtime_db_path(),
            materialized_output_dir=self._runtime_materialized_dir(),
            starting_cash=float(self.current_capital),
        )
        self.prs_context = self._build_prs_context()
        self.prs_cert_snapshot_hash = self._refresh_prs_certification_snapshot()

    def close(self) -> None:
        prs = getattr(self, "prs", None)
        if prs is None:
            return
        try:
            prs.close()
        except Exception:
            pass
        self.prs = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _sync_positions_from_prs(self, current_prices: pd.Series) -> None:
        if self.prs is None:
            return
        snap = self.prs.get_portfolio_state().to_dict()
        holdings = dict(snap.get("holdings", {}) or {})
        synced = {}
        for ticker, payload in holdings.items():
            qty = float(payload.get("quantity", 0.0) or 0.0)
            if abs(qty) <= 0.0:
                continue
            price = float(current_prices.get(ticker, payload.get("last_price", 0.0)) or 0.0)
            avg_price = float(payload.get("avg_price", 0.0) or 0.0)
            synced[str(ticker)] = {
                "shares": qty,
                "avg_price": avg_price,
                "market_value": qty * price,
                "unrealized_pnl": qty * (price - avg_price),
            }
        self.current_positions = synced
        self.current_capital = float(snap.get("cash", self.current_capital) or self.current_capital)
    
    def load_target_portfolio(self):
        """Load target portfolio weights"""
        
        print("📊 Loading target portfolio...")
        
        if not os.path.exists(self.paths['portfolio_weights']):
            print("   ❌ No portfolio weights found")
            return pd.DataFrame()
        
        portfolio_df = pd.read_parquet(self.paths['portfolio_weights'])
        
        if portfolio_df.empty:
            print("   ❌ Empty portfolio")
            return pd.DataFrame()
        
        # Ensure we have the required columns
        if 'final_weight' not in portfolio_df.columns:
            print("   ❌ No final_weight column found")
            return pd.DataFrame()
        
        print(f"   ✅ Loaded portfolio: {len(portfolio_df)} positions")
        print(f"   📊 Total target exposure: {portfolio_df['final_weight'].abs().sum():.1%}")
        
        return portfolio_df
    
    def load_current_prices(self):
        """Load current market prices"""
        
        print("💰 Loading current market prices...")
        
        if not os.path.exists(self.paths['prices']):
            print("   ❌ No price data found")
            return pd.DataFrame()

        # read_prices_legacy returns the canonical prices in the legacy
        # Date/ticker/Close column shape this method expects.
        prices_df = read_prices_legacy()

        if prices_df.empty:
            print("   ❌ Empty price data")
            return pd.DataFrame()

        # Get latest prices
        latest_prices = prices_df.sort_values('Date').groupby('ticker').tail(1)
        latest_prices = latest_prices.set_index('ticker')['Close']
        
        print(f"   ✅ Loaded prices for {len(latest_prices)} stocks")
        
        return latest_prices
    
    def calculate_target_positions(self, portfolio_df, current_prices):
        """Calculate target positions in shares"""
        
        print("🎯 Calculating target positions...")
        
        target_positions = {}
        total_target_value = 0
        
        available_capital = self.current_capital * (1 - self.fund_params['cash_buffer'])
        
        for _, row in portfolio_df.iterrows():
            ticker = row['ticker']
            target_weight = row['final_weight']
            
            if ticker in current_prices.index and target_weight != 0:
                price = current_prices[ticker]
                target_value = available_capital * abs(target_weight)
                
                # Apply position size limits
                max_position_value = self.current_capital * self.fund_params['max_position_size']
                target_value = min(target_value, max_position_value)
                
                # Calculate shares (considering minimum trade size)
                if target_value >= self.fund_params['min_trade_size']:
                    target_shares = int(target_value / price)
                    
                    # Apply sign based on weight direction
                    if target_weight < 0:
                        target_shares = -target_shares
                    
                    if target_shares != 0:
                        target_positions[ticker] = {
                            'shares': target_shares,
                            'price': price,
                            'value': target_shares * price,
                            'weight': target_weight
                        }
                        total_target_value += abs(target_shares * price)
        
        print(f"   ✅ Target positions: {len(target_positions)} stocks")
        print(f"   📊 Total target value: ₹{total_target_value:,.0f}")
        print(f"   📊 Target exposure: {total_target_value/self.current_capital:.1%}")
        
        return target_positions
    
    def execute_trades(self, target_positions, current_prices, market_conditions):
        """Execute trades to reach target positions using enhanced cost model"""
        
        print("⚡ Executing shadow trades with enhanced cost model...")
        
        trades = []
        total_transaction_costs = 0
        
        for ticker, target in target_positions.items():
            current_shares = self.current_positions.get(ticker, {}).get('shares', 0)
            target_shares = target['shares']
            price = target['price']
            
            # Calculate trade size
            trade_shares = target_shares - current_shares
            
            if trade_shares != 0:
                # Get liquidity data for this stock
                liquidity_data = {
                    'adv_60d': target.get('adv_60d', 10_000_000),  # Default ₹1 crore ADV
                    'market_cap': target.get('market_cap', 100_000_000)  # Default ₹10 crore
                }
                
                # Calculate enhanced transaction costs
                cost_breakdown = self.cost_model.calculate_total_cost(
                    ticker, trade_shares, price, market_conditions, liquidity_data
                )
                
                # Extract key cost components
                total_cost = cost_breakdown['total_transaction_cost']
                effective_price = cost_breakdown['effective_price']
                
                # Record trade with enhanced cost information
                trade = {
                    'timestamp': datetime.now(),
                    'ticker': ticker,
                    'shares': trade_shares,
                    'price': price,
                    'effective_price': effective_price,
                    'trade_value': trade_shares * effective_price,
                    'total_cost': total_cost,
                    'cost_bps': cost_breakdown['total_cost_bps'],
                    'market_regime': cost_breakdown['market_regime'],
                    'crisis_multiplier': cost_breakdown['crisis_multiplier'],
                    'market_impact_bps': cost_breakdown['market_impact']['total_impact_bps'],
                    'trade_type': 'BUY' if trade_shares > 0 else 'SELL',
                    'cost_breakdown': cost_breakdown
                }
                
                trades.append(trade)
                total_transaction_costs += total_cost

                side = "buy" if trade_shares > 0 else "sell"
                qty = float(abs(trade_shares))
                requested_notional = float(abs(qty * effective_price))
                proposal = TradeProposal(
                    proposal_id=f"prop_shadow_{ticker}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
                    origin=ProposalOrigin.SHADOW,
                    strategy_id="shadow_fund_execution",
                    signal_id=f"sig_shadow_{ticker}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
                    alpha_type="directional",
                    expected_edge=0.0,
                    risk_score=float(requested_notional / max(1.0, float(self.current_capital))),
                    regime_context={
                        "market_regime": str(cost_breakdown.get("market_regime", "unknown") or "unknown"),
                        "engine": "shadow_fund_engine",
                    },
                    instrument_plan={
                        "symbol": str(ticker).upper(),
                        "side": side,
                        "price": float(effective_price),
                        "quantity": qty,
                        "direction": 1.0 if side == "buy" else -1.0,
                        "sector": str(target.get("sector", "") or "").lower(),
                        "instrument_type": "equity",
                        "lifecycle_action": "open" if target_shares != 0 else "close",
                        "position_key": f"shadow_fund:{str(ticker).upper()}",
                    },
                    requested_notional=requested_notional,
                    certification_snapshot_hash=str(self.prs_cert_snapshot_hash or ""),
                    decision_mode=DecisionMode.AUTO,
                    trigger_reason_code="rebalance.shadow_fund.daily",
                    risk_override_flag=False,
                )
                prs_result = self.prs.process_proposal(
                    proposal,
                    budget_snapshot={"reserve_usage": {}},
                    risk_snapshot={"risk_budget_ratio": 0.0, "signal_entropy": 1.0},
                    market_snapshot={},
                    market_liquidity_snapshot={
                        "adv_notional": float(liquidity_data.get("adv_60d", 0.0) or 0.0),
                        "spread_bps": float(cost_breakdown.get("total_cost_bps", 0.0) or 0.0),
                        "depth_qty": float(abs(trade_shares)),
                        "estimated_slippage_bps": float(cost_breakdown.get("total_cost_bps", 0.0) or 0.0),
                    },
                    certification_context=dict(self.prs_context),
                    auto_fill=True,
                )
                trade["prs_result"] = prs_result.to_dict()
                if not prs_result.approved:
                    trade["execution_status"] = "rejected_prs"
                    continue
                trade["execution_status"] = "executed_prs"

        self._sync_positions_from_prs(current_prices)
        
        print(f"   ✅ Executed {len(trades)} trades")
        print(f"   💰 Total transaction costs: ₹{total_transaction_costs:,.0f}")
        print(f"   📊 Average cost: {(total_transaction_costs / sum(abs(t['trade_value']) for t in trades) * 10000) if trades else 0:.1f} bps")
        print(f"   💰 Remaining capital: ₹{self.current_capital:,.0f}")
        
        return trades
    
    def calculate_portfolio_pnl(self, current_prices):
        """Calculate current portfolio P&L"""
        self._sync_positions_from_prs(current_prices)
        
        total_market_value = 0
        total_unrealized_pnl = 0
        position_count = 0
        
        for ticker, position in self.current_positions.items():
            if ticker in current_prices.index:
                current_price = current_prices[ticker]
                shares = position['shares']
                avg_price = position['avg_price']
                
                market_value = shares * current_price
                unrealized_pnl = shares * (current_price - avg_price)
                
                # Update position
                position['market_value'] = market_value
                position['unrealized_pnl'] = unrealized_pnl
                
                total_market_value += abs(market_value)
                total_unrealized_pnl += unrealized_pnl
                position_count += 1
        
        # Calculate portfolio metrics
        total_portfolio_value = self.current_capital + total_unrealized_pnl
        portfolio_return = (total_portfolio_value / self.fund_params['initial_capital']) - 1
        exposure = total_market_value / total_portfolio_value if total_portfolio_value > 0 else 0
        
        pnl_summary = {
            'timestamp': datetime.now(),
            'cash': self.current_capital,
            'market_value': total_market_value,
            'unrealized_pnl': total_unrealized_pnl,
            'total_portfolio_value': total_portfolio_value,
            'portfolio_return': portfolio_return,
            'exposure': exposure,
            'position_count': position_count
        }
        
        return pnl_summary
    
    def save_shadow_fund_data(self, trades, pnl_summary):
        """Save shadow fund execution data"""
        
        # Save trades
        if trades:
            trades_df = pd.DataFrame(trades)
            trades_df.to_parquet(self.paths['shadow_trades'], index=False)
        
        # Save positions
        positions_data = []
        for ticker, position in self.current_positions.items():
            position_record = {
                'timestamp': datetime.now(),
                'ticker': ticker,
                **position
            }
            positions_data.append(position_record)
        
        if positions_data:
            positions_df = pd.DataFrame(positions_data)
            positions_df.to_parquet(self.paths['shadow_positions'], index=False)
        
        # Save P&L
        pnl_df = pd.DataFrame([pnl_summary])
        pnl_df.to_parquet(self.paths['shadow_pnl'], index=False)
        
        # Save comprehensive report
        shadow_report = {
            'fund_name': self.name,
            'timestamp': datetime.now().isoformat(),
            'fund_parameters': self.fund_params,
            'current_state': pnl_summary,
            'execution_summary': {
                'trades_executed': len(trades),
                'positions_held': len(self.current_positions),
                'total_transaction_costs': sum(t.get('total_cost', 0) for t in trades)
            },
            'performance_metrics': {
                'total_return': pnl_summary['portfolio_return'],
                'current_exposure': pnl_summary['exposure'],
                'cash_position': pnl_summary['cash'] / pnl_summary['total_portfolio_value']
            }
        }
        
        with open(self.paths['shadow_fund_report'], 'w') as f:
            json.dump(shadow_report, f, indent=2, default=str)
        
        return shadow_report
    
    def run_shadow_trading(self):
        """Run complete shadow fund trading simulation"""
        
        print("🧬 NORTHSTAR SHADOW FUND EXECUTION ENGINE")
        print("=" * 70)
        print(f"Virtual Capital: ₹{self.fund_params['initial_capital']:,}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load target portfolio
        portfolio_df = self.load_target_portfolio()
        if portfolio_df.empty:
            print("❌ Cannot execute without target portfolio")
            return False
        
        # Load current prices
        current_prices = self.load_current_prices()
        if current_prices.empty:
            print("❌ Cannot execute without price data")
            return False
        
        # Calculate target positions
        target_positions = self.calculate_target_positions(portfolio_df, current_prices)
        if not target_positions:
            print("❌ No valid target positions calculated")
            return False
        
        # Create market conditions for cost model
        market_conditions = {
            'volatility': 0.20,  # Default market volatility
            'vix': 25,          # Default VIX level
            'market_stress': 0.3, # Default stress level
            'liquidity_ratio': 0.8 # Default liquidity ratio
        }
        
        # Execute trades with enhanced cost model
        trades = self.execute_trades(target_positions, current_prices, market_conditions)
        
        # Calculate P&L
        pnl_summary = self.calculate_portfolio_pnl(current_prices)
        
        # Save all data
        shadow_report = self.save_shadow_fund_data(trades, pnl_summary)
        
        # Print summary
        print(f"\n🧬 SHADOW FUND EXECUTION COMPLETE")
        print("=" * 70)
        print(f"💰 Portfolio Value: ₹{pnl_summary['total_portfolio_value']:,.0f}")
        print(f"📊 Portfolio Return: {pnl_summary['portfolio_return']:+.2%}")
        print(f"📊 Current Exposure: {pnl_summary['exposure']:.1%}")
        print(f"📊 Cash Position: {pnl_summary['cash']/pnl_summary['total_portfolio_value']:.1%}")
        print(f"📊 Positions Held: {pnl_summary['position_count']}")
        print(f"⚡ Trades Executed: {len(trades)}")
        
        if pnl_summary['portfolio_return'] >= 0:
            print(f"\n✅ SHADOW FUND IS PROFITABLE!")
        else:
            print(f"\n⚠️ Shadow fund showing losses - monitor closely")
        
        print(f"\n📋 Shadow fund report: {self.paths['shadow_fund_report']}")
        
        return True

def main():
    """Main execution function"""
    
    shadow_fund = ShadowFundEngine()
    success = shadow_fund.run_shadow_trading()
    
    return success

if __name__ == "__main__":
    main()
