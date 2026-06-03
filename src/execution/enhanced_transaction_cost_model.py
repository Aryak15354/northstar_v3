#!/usr/bin/env python3
"""
💰 ENHANCED TRANSACTION COST MODEL
Brutal reality of trading costs with crisis multipliers

This is what separates backtests from reality.
Every basis point matters when you're managing real money.

Usage:
    from src.execution.enhanced_transaction_cost_model import EnhancedTransactionCostModel
    
    cost_model = EnhancedTransactionCostModel()
    total_cost = cost_model.calculate_total_cost(symbol, shares, price, market_conditions)
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

class EnhancedTransactionCostModel:
    """
    Enhanced Transaction Cost Model
    
    Implements brutal reality of trading costs:
    - Base transaction costs (brokerage, taxes, fees)
    - Crisis multipliers (2x during stress periods)
    - Progressive slippage penalties for large positions
    - Market impact modeling with liquidity constraints
    - Overnight funding costs and short borrow fees
    - AUM-aware position sizing with ADV limits
    """
    
    def __init__(self):
        self.name = "Enhanced Transaction Cost Model"
        self.version = "1.0"
        
        # Base cost structure (Indian market)
        self.base_costs = {
            'brokerage': 0.0003,        # 3 bps brokerage
            'stt': 0.001,               # 10 bps STT on equity delivery
            'stamp_duty': 0.00003,      # 0.3 bps stamp duty
            'gst': 0.00018,             # 1.8 bps GST on brokerage
            'sebi_charges': 0.000001,   # 0.01 bps SEBI charges
            'exchange_charges': 0.0000345, # 0.345 bps exchange charges
            'dp_charges': 13.5,         # ₹13.5 per scrip DP charges
        }
        
        # Crisis multipliers
        self.crisis_multipliers = {
            'normal': 1.0,
            'stress': 1.5,
            'crisis': 2.0,
            'extreme_crisis': 3.0
        }
        
        # Market impact parameters
        self.market_impact_params = {
            'base_impact': 0.0005,      # 5 bps base market impact
            'liquidity_exponent': 0.8,  # More aggressive scaling than square root
            'volatility_multiplier': 3.0, # Higher volatility sensitivity
            'adv_threshold': 0.05,      # 5% of ADV threshold
            'large_trade_penalty': 0.005 # 50 bps penalty for large trades
        }
        
        # Funding and borrowing costs
        self.funding_costs = {
            'overnight_rate': 0.06,     # 6% annual overnight funding rate
            'short_borrow_rate': 0.12,  # 12% annual short borrow rate
            'margin_requirement': 0.20, # 20% margin requirement
            'haircut': 0.15            # 15% haircut on collateral
        }
        
        # File paths
        self.paths = {
            'cost_history': 'data/execution/transaction_cost_history.parquet',
            'market_regimes': 'data/execution/market_regimes.parquet',
            'liquidity_data': 'data/universe/liquidity_history.parquet'
        }
        
        # Create execution directory
        os.makedirs('data/execution', exist_ok=True)
        
        # Cost tracking
        self.cost_history = []
    
    def detect_market_regime(self, market_conditions: Dict) -> str:
        """Detect current market regime for crisis multiplier"""
        
        volatility = market_conditions.get('volatility', 0.15)
        vix = market_conditions.get('vix', 20)
        market_stress = market_conditions.get('market_stress', 0.0)
        liquidity_ratio = market_conditions.get('liquidity_ratio', 1.0)
        
        # Crisis detection logic (more sensitive thresholds)
        if volatility > 0.35 or vix > 35 or market_stress > 0.7:
            return 'extreme_crisis'
        elif volatility > 0.28 or vix > 28 or market_stress > 0.5:
            return 'crisis'
        elif volatility > 0.22 or vix > 22 or market_stress > 0.3 or liquidity_ratio < 0.8:
            return 'stress'
        else:
            return 'normal'
    
    def calculate_base_transaction_costs(self, trade_value: float, shares: int) -> Dict[str, float]:
        """Calculate base transaction costs"""
        
        costs = {}
        
        # Percentage-based costs
        for cost_type, rate in self.base_costs.items():
            if cost_type == 'dp_charges':
                costs[cost_type] = self.base_costs['dp_charges']  # Fixed per scrip
            else:
                costs[cost_type] = trade_value * rate
        
        # Total base cost
        costs['total_base_cost'] = sum(costs.values())
        costs['total_base_cost_bps'] = (costs['total_base_cost'] / trade_value) * 10000
        
        return costs
    
    def calculate_market_impact(self, symbol: str, shares: int, price: float, 
                              market_conditions: Dict, liquidity_data: Optional[Dict] = None) -> Dict[str, float]:
        """Calculate market impact based on trade size and liquidity"""
        
        trade_value = abs(shares * price)
        
        # Get liquidity information
        if liquidity_data:
            adv_60d = liquidity_data.get('adv_60d', 10_000_000)  # Default ₹1 crore ADV
            market_cap = liquidity_data.get('market_cap', 100_000_000)  # Default ₹10 crore market cap
        else:
            # Estimate based on symbol (simplified)
            if any(major in symbol for major in ['RELIANCE', 'TCS', 'INFY', 'HDFC']):
                adv_60d = 100_000_000  # ₹10 crore for major stocks
                market_cap = 1_000_000_000  # ₹100 crore
            else:
                adv_60d = 5_000_000   # ₹50 lakh for smaller stocks
                market_cap = 50_000_000  # ₹5 crore
        
        # Calculate trade size as percentage of ADV
        adv_percentage = trade_value / adv_60d
        
        # Base market impact
        base_impact = self.market_impact_params['base_impact']
        
        # Liquidity-based scaling (square root law)
        liquidity_impact = base_impact * (adv_percentage ** self.market_impact_params['liquidity_exponent'])
        
        # Volatility adjustment (more aggressive scaling)
        volatility = market_conditions.get('volatility', 0.15)
        volatility_adjustment = (volatility / 0.15) ** self.market_impact_params['volatility_multiplier']
        
        # Large trade penalty
        large_trade_penalty = 0.0
        if adv_percentage > self.market_impact_params['adv_threshold']:
            excess_percentage = adv_percentage - self.market_impact_params['adv_threshold']
            large_trade_penalty = excess_percentage * self.market_impact_params['large_trade_penalty']
        
        # Total market impact
        total_impact = (liquidity_impact * volatility_adjustment + large_trade_penalty)
        
        # Market impact cost in rupees
        impact_cost = trade_value * total_impact
        
        return {
            'adv_percentage': adv_percentage,
            'base_impact_bps': base_impact * 10000,
            'liquidity_impact_bps': liquidity_impact * 10000,
            'volatility_adjustment': volatility_adjustment,
            'large_trade_penalty_bps': large_trade_penalty * 10000,
            'total_impact_bps': total_impact * 10000,
            'impact_cost': impact_cost,
            'effective_price': price * (1 + total_impact if shares > 0 else 1 - total_impact)
        }
    
    def calculate_funding_costs(self, shares: int, price: float, holding_period_days: int = 1) -> Dict[str, float]:
        """Calculate overnight funding and short borrowing costs"""
        
        trade_value = abs(shares * price)
        
        if shares > 0:
            # Long position - overnight funding cost
            daily_funding_rate = self.funding_costs['overnight_rate'] / 365
            funding_cost = trade_value * self.funding_costs['margin_requirement'] * daily_funding_rate * holding_period_days
            
            return {
                'position_type': 'long',
                'funding_cost': funding_cost,
                'daily_rate': daily_funding_rate,
                'margin_requirement': self.funding_costs['margin_requirement'],
                'funding_cost_bps': (funding_cost / trade_value) * 10000
            }
        else:
            # Short position - borrowing cost
            daily_borrow_rate = self.funding_costs['short_borrow_rate'] / 365
            borrow_cost = trade_value * daily_borrow_rate * holding_period_days
            
            # Additional haircut cost
            haircut_cost = trade_value * self.funding_costs['haircut'] * daily_borrow_rate * holding_period_days
            
            total_cost = borrow_cost + haircut_cost
            
            return {
                'position_type': 'short',
                'borrow_cost': borrow_cost,
                'haircut_cost': haircut_cost,
                'total_funding_cost': total_cost,
                'daily_rate': daily_borrow_rate,
                'funding_cost_bps': (total_cost / trade_value) * 10000
            }
    
    def apply_crisis_multiplier(self, base_costs: Dict[str, float], market_regime: str) -> Dict[str, float]:
        """Apply crisis multiplier to transaction costs"""
        
        multiplier = self.crisis_multipliers.get(market_regime, 1.0)
        
        # Apply multiplier to variable costs (not fixed costs like DP charges)
        crisis_adjusted_costs = {}
        
        for cost_type, cost_value in base_costs.items():
            if cost_type == 'dp_charges':
                # Fixed cost - no multiplier
                crisis_adjusted_costs[cost_type] = cost_value
            else:
                # Variable cost - apply multiplier
                crisis_adjusted_costs[cost_type] = cost_value * multiplier
        
        crisis_adjusted_costs['crisis_multiplier'] = multiplier
        crisis_adjusted_costs['market_regime'] = market_regime
        
        return crisis_adjusted_costs
    
    def calculate_total_cost(self, symbol: str, shares: int, price: float, 
                           market_conditions: Dict, liquidity_data: Optional[Dict] = None,
                           holding_period_days: int = 1) -> Dict[str, any]:
        """Calculate total transaction cost including all components"""
        
        trade_value = abs(shares * price)
        
        # Step 1: Detect market regime
        market_regime = self.detect_market_regime(market_conditions)
        
        # Step 2: Calculate base transaction costs
        base_costs = self.calculate_base_transaction_costs(trade_value, shares)
        
        # Step 3: Apply crisis multiplier
        crisis_adjusted_costs = self.apply_crisis_multiplier(base_costs, market_regime)
        
        # Step 4: Calculate market impact
        market_impact = self.calculate_market_impact(symbol, shares, price, market_conditions, liquidity_data)
        
        # Step 5: Calculate funding costs
        funding_costs = self.calculate_funding_costs(shares, price, holding_period_days)
        
        # Step 6: Combine all costs
        total_transaction_cost = (
            crisis_adjusted_costs['total_base_cost'] + 
            market_impact['impact_cost'] + 
            funding_costs.get('funding_cost', funding_costs.get('total_funding_cost', 0))
        )
        
        total_cost_bps = (total_transaction_cost / trade_value) * 10000
        
        # Effective execution price
        if shares > 0:
            effective_price = price + (total_transaction_cost / abs(shares))
        else:
            effective_price = price - (total_transaction_cost / abs(shares))
        
        # Comprehensive cost breakdown
        cost_breakdown = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'shares': shares,
            'price': price,
            'trade_value': trade_value,
            'market_regime': market_regime,
            'crisis_multiplier': crisis_adjusted_costs['crisis_multiplier'],
            
            # Base costs
            'base_costs': base_costs,
            'crisis_adjusted_costs': crisis_adjusted_costs,
            
            # Market impact
            'market_impact': market_impact,
            
            # Funding costs
            'funding_costs': funding_costs,
            
            # Total costs
            'total_transaction_cost': total_transaction_cost,
            'total_cost_bps': total_cost_bps,
            'effective_price': effective_price,
            'cost_as_percentage_of_trade': total_transaction_cost / trade_value * 100,
            
            # Performance impact
            'performance_drag_annual': total_cost_bps * 252 / 10000,  # Assuming daily trading
            'breakeven_return_required': total_cost_bps / 10000 * 2  # Round trip cost
        }
        
        # Log cost for analysis
        self.cost_history.append(cost_breakdown)
        
        return cost_breakdown
    
    def analyze_cost_impact(self, portfolio_trades: List[Dict]) -> Dict[str, any]:
        """Analyze the impact of transaction costs on portfolio performance"""
        
        if not portfolio_trades:
            return {'error': 'No trades provided'}
        
        total_trade_value = sum(abs(trade['shares'] * trade['price']) for trade in portfolio_trades)
        total_costs = 0
        regime_costs = {'normal': 0, 'stress': 0, 'crisis': 0, 'extreme_crisis': 0}
        impact_sources = {'base_costs': 0, 'market_impact': 0, 'funding_costs': 0}
        
        for trade in portfolio_trades:
            cost_breakdown = self.calculate_total_cost(
                trade['symbol'], trade['shares'], trade['price'], 
                trade['market_conditions'], trade.get('liquidity_data')
            )
            
            total_costs += cost_breakdown['total_transaction_cost']
            regime = cost_breakdown['market_regime']
            regime_costs[regime] += cost_breakdown['total_transaction_cost']
            
            # Break down cost sources
            impact_sources['base_costs'] += cost_breakdown['crisis_adjusted_costs']['total_base_cost']
            impact_sources['market_impact'] += cost_breakdown['market_impact']['impact_cost']
            impact_sources['funding_costs'] += cost_breakdown['funding_costs'].get(
                'funding_cost', cost_breakdown['funding_costs'].get('total_funding_cost', 0)
            )
        
        # Calculate portfolio-level metrics
        portfolio_cost_bps = (total_costs / total_trade_value) * 10000
        annual_drag = portfolio_cost_bps * 252 / 10000  # Assuming daily rebalancing
        
        analysis = {
            'portfolio_summary': {
                'total_trades': len(portfolio_trades),
                'total_trade_value': total_trade_value,
                'total_transaction_costs': total_costs,
                'portfolio_cost_bps': portfolio_cost_bps,
                'annual_performance_drag': annual_drag,
                'cost_as_percentage': total_costs / total_trade_value * 100
            },
            'cost_by_regime': {
                regime: {'cost': cost, 'percentage': cost / total_costs * 100}
                for regime, cost in regime_costs.items() if cost > 0
            },
            'cost_by_source': {
                source: {'cost': cost, 'percentage': cost / total_costs * 100}
                for source, cost in impact_sources.items()
            },
            'recommendations': []
        }
        
        # Generate recommendations
        if portfolio_cost_bps > 50:  # > 50 bps
            analysis['recommendations'].append("HIGH COST: Portfolio transaction costs exceed 50 bps - review trade sizing")
        
        if regime_costs['crisis'] + regime_costs['extreme_crisis'] > total_costs * 0.3:
            analysis['recommendations'].append("CRISIS IMPACT: High proportion of costs during crisis - consider defensive positioning")
        
        if impact_sources['market_impact'] > total_costs * 0.4:
            analysis['recommendations'].append("LIQUIDITY ISSUE: High market impact costs - reduce position sizes or improve timing")
        
        if annual_drag > 0.02:  # > 2% annual drag
            analysis['recommendations'].append("PERFORMANCE DRAG: Annual cost drag exceeds 2% - optimize trading frequency")
        
        return analysis
    
    def save_cost_history(self):
        """Save transaction cost history for analysis"""
        
        if not self.cost_history:
            return
        
        # Convert to DataFrame
        cost_df = pd.DataFrame(self.cost_history)
        
        # Save to parquet
        cost_df.to_parquet(self.paths['cost_history'], index=False)
        
        print(f"💰 Saved {len(self.cost_history)} cost records to {self.paths['cost_history']}")
    
    def load_cost_history(self) -> pd.DataFrame:
        """Load historical cost data for analysis"""
        
        if os.path.exists(self.paths['cost_history']):
            return pd.read_parquet(self.paths['cost_history'])
        else:
            return pd.DataFrame()


def main():
    """Demonstrate enhanced transaction cost model"""
    
    print("💰 ENHANCED TRANSACTION COST MODEL")
    print("=" * 60)
    
    cost_model = EnhancedTransactionCostModel()
    
    # Example trades in different market conditions
    test_trades = [
        {
            'symbol': 'RELIANCE.NS',
            'shares': 1000,
            'price': 2500,
            'market_conditions': {'volatility': 0.15, 'vix': 20, 'market_stress': 0.2},
            'liquidity_data': {'adv_60d': 100_000_000, 'market_cap': 1_000_000_000}
        },
        {
            'symbol': 'SMALLCAP.NS',
            'shares': 5000,
            'price': 100,
            'market_conditions': {'volatility': 0.35, 'vix': 35, 'market_stress': 0.7},  # Crisis
            'liquidity_data': {'adv_60d': 2_000_000, 'market_cap': 50_000_000}
        },
        {
            'symbol': 'TCS.NS',
            'shares': -500,  # Short position
            'price': 3500,
            'market_conditions': {'volatility': 0.20, 'vix': 25, 'market_stress': 0.3},
            'liquidity_data': {'adv_60d': 80_000_000, 'market_cap': 800_000_000}
        }
    ]
    
    print("\n📊 Individual Trade Analysis:")
    print("-" * 40)
    
    for i, trade in enumerate(test_trades, 1):
        print(f"\nTrade {i}: {trade['symbol']}")
        print(f"  Size: {trade['shares']} shares @ ₹{trade['price']}")
        print(f"  Value: ₹{abs(trade['shares'] * trade['price']):,}")
        
        cost_breakdown = cost_model.calculate_total_cost(
            trade['symbol'], trade['shares'], trade['price'],
            trade['market_conditions'], trade['liquidity_data']
        )
        
        print(f"  Market Regime: {cost_breakdown['market_regime']}")
        print(f"  Crisis Multiplier: {cost_breakdown['crisis_multiplier']:.1f}x")
        print(f"  Total Cost: ₹{cost_breakdown['total_transaction_cost']:,.0f} ({cost_breakdown['total_cost_bps']:.1f} bps)")
        print(f"  Market Impact: {cost_breakdown['market_impact']['total_impact_bps']:.1f} bps")
        print(f"  Effective Price: ₹{cost_breakdown['effective_price']:.2f}")
    
    # Portfolio-level analysis
    print(f"\n📈 Portfolio-Level Analysis:")
    print("-" * 40)
    
    portfolio_analysis = cost_model.analyze_cost_impact(test_trades)
    
    summary = portfolio_analysis['portfolio_summary']
    print(f"  Total Trades: {summary['total_trades']}")
    print(f"  Total Trade Value: ₹{summary['total_trade_value']:,.0f}")
    print(f"  Total Transaction Costs: ₹{summary['total_transaction_costs']:,.0f}")
    print(f"  Portfolio Cost: {summary['portfolio_cost_bps']:.1f} bps")
    print(f"  Annual Performance Drag: {summary['annual_performance_drag']:.2%}")
    
    print(f"\n💡 Cost Breakdown by Source:")
    for source, data in portfolio_analysis['cost_by_source'].items():
        print(f"  {source.replace('_', ' ').title()}: {data['percentage']:.1f}%")
    
    print(f"\n🌡️ Cost Breakdown by Market Regime:")
    for regime, data in portfolio_analysis['cost_by_regime'].items():
        print(f"  {regime.replace('_', ' ').title()}: {data['percentage']:.1f}%")
    
    if portfolio_analysis['recommendations']:
        print(f"\n⚠️ Recommendations:")
        for rec in portfolio_analysis['recommendations']:
            print(f"  • {rec}")
    
    # Save cost history
    cost_model.save_cost_history()
    
    print(f"\n✅ Enhanced transaction cost model demonstration complete")
    print(f"💡 Real trading costs are brutal - every basis point matters")


if __name__ == "__main__":
    main()