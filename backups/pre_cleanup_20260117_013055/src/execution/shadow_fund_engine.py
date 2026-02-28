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
import sys
import os
))

from execution.enhanced_transaction_cost_model import EnhancedTransactionCostModel

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
        
        # File paths
        self.paths = {
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'prices': 'data/processed/prices.parquet',
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
        
        prices_df = pd.read_parquet(self.paths['prices'])
        
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
                
                # Update current positions
                self.current_positions[ticker] = {
                    'shares': target_shares,
                    'avg_price': effective_price,
                    'market_value': target_shares * price,
                    'unrealized_pnl': target_shares * (price - effective_price)
                }
        
        # Update capital after transaction costs
        self.current_capital -= total_transaction_costs
        
        print(f"   ✅ Executed {len(trades)} trades")
        print(f"   💰 Total transaction costs: ₹{total_transaction_costs:,.0f}")
        print(f"   📊 Average cost: {(total_transaction_costs / sum(abs(t['trade_value']) for t in trades) * 10000) if trades else 0:.1f} bps")
        print(f"   💰 Remaining capital: ₹{self.current_capital:,.0f}")
        
        return trades
    
    def calculate_portfolio_pnl(self, current_prices):
        """Calculate current portfolio P&L"""
        
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