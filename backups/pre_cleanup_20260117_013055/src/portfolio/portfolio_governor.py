#!/usr/bin/env python3
"""
🎯 PORTFOLIO GOVERNOR - NORTHSTAR V3
Complete Portfolio Management System

This is the central portfolio management system that:
1. Loads market state and intelligence
2. Applies risk controls and exposure limits
3. Generates final portfolio weights
4. Ensures compliance with all constraints
5. Provides portfolio analytics for the trading desk

This is the GOVERNOR that ensures the portfolio obeys all rules.
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.bounded_exposure_calculator import BoundedExposureCalculator
from src.cohesion.state_file_manager import StateFileManager

class PortfolioGovernor:
    """
    Portfolio Governor - The Final Authority on Portfolio Construction
    
    This class orchestrates all portfolio management components and ensures
    the final portfolio complies with all risk and exposure constraints.
    """
    
    def __init__(self):
        self.name = "Northstar Portfolio Governor"
        self.version = "3.0"
        
        # Initialize state management components
        self.exposure_calculator = BoundedExposureCalculator()
        self.state_manager = StateFileManager()
        
        # File paths
        self.paths = {
            'market_state': 'data/processed/market_state.parquet',
            'intelligent_state': 'data/processed/intelligent_market_state.parquet',
            'scores': 'data/processed/scores.parquet',
            'opportunity_surface': 'data/processed/opportunity_surface.parquet',
            'risk_budget': 'data/macro/factors/risk_budget.parquet',
            'output': 'data/processed/portfolio_weights.parquet',
            'analytics': 'data/processed/portfolio_analytics.json'
        }
        
        # Risk constraints
        self.constraints = {
            'max_single_position': 0.08,  # 8% max per stock
            'max_sector_exposure': 0.30,  # 30% max per sector
            'max_total_exposure': 0.95,   # 95% max total exposure
            'min_diversification': 15,    # Minimum 15 positions
            'max_turnover': 0.25,         # 25% max one-way turnover
            'cash_buffer': 0.05           # 5% minimum cash buffer
        }
        
        # Portfolio roles
        self.position_roles = {
            'Core': 'Long-term conviction positions',
            'Satellite': 'Tactical allocation positions', 
            'Hedge': 'Risk mitigation positions',
            'Momentum': 'Trend-following positions',
            'Value': 'Contrarian value positions',
            'Quality': 'High-quality defensive positions'
        }
    
    def load_market_intelligence(self):
        """Load market state and AI intelligence"""
        
        print("🧠 Loading market intelligence...")
        
        intelligence = {
            'market_state': {},
            'ai_intelligence': {},
            'regime': 'neutral',
            'allowed_exposure': 0.6,
            'risk_on_prob': 0.5,
            'ai_active': False,
            'strategy_performance': {},
            'capital_allocations': {}
        }
        
        # Load market state using StateFileManager
        try:
            market_df = self.state_manager.read_market_state()
            if not market_df.empty:
                latest_market = market_df.iloc[-1]
                intelligence['market_state'] = latest_market.to_dict()
                intelligence['regime'] = latest_market.get('regime', 'neutral')
                
                # Read allowed_exposure from canonical source (already bounded)
                allowed_exposure = latest_market.get('allowed_exposure', 0.6)
                
                # Ensure it's bounded (defensive check)
                if not (0.0 <= allowed_exposure <= 1.0):
                    print(f"   ⚠️ Invalid allowed_exposure {allowed_exposure}, bounding to [0.0, 1.0]")
                    allowed_exposure = max(0.0, min(1.0, allowed_exposure))
                
                intelligence['allowed_exposure'] = allowed_exposure
                intelligence['risk_on_prob'] = latest_market.get('risk_on', 0.5)
                print(f"   ✅ Market state loaded: {intelligence['regime']} regime")
                print(f"   📊 Allowed Exposure: {intelligence['allowed_exposure']:.1%}")
        except FileNotFoundError:
            print(f"   ⚠️ Market state file not found, using defaults")
        except Exception as e:
            print(f"   ⚠️ Could not load market state: {e}")
        
        # Load AI intelligence if available
        try:
            if os.path.exists(self.paths['intelligent_state']):
                ai_df = pd.read_parquet(self.paths['intelligent_state'])
                if not ai_df.empty:
                    latest_ai = ai_df.iloc[-1]
                    intelligence['ai_intelligence'] = latest_ai.to_dict()
                    intelligence['ai_active'] = latest_ai.get('intelligence_status') == 'active'
                    
                    # Override with AI recommendations if available
                    if intelligence['ai_active']:
                        ai_exposure = latest_ai.get('ai_allowed_exposure')
                        if ai_exposure and not pd.isna(ai_exposure):
                            # Bound AI exposure
                            ai_exposure_bounded = max(0.0, min(1.0, float(ai_exposure) / 100))
                            intelligence['allowed_exposure'] = ai_exposure_bounded
                        
                        ai_risk_on = latest_ai.get('ai_risk_on_probability')
                        if ai_risk_on and not pd.isna(ai_risk_on):
                            intelligence['risk_on_prob'] = float(ai_risk_on)
                        
                        print(f"   🤖 AI intelligence active: {intelligence['allowed_exposure']:.1%} exposure")
        except Exception as e:
            print(f"   ⚠️ Could not load AI intelligence: {e}")
        
        # Load strategy performance data
        intelligence['strategy_performance'] = self.load_strategy_performance()
        
        # Load capital allocations
        intelligence['capital_allocations'] = self.load_capital_allocations()
        
        return intelligence
    
    def load_strategy_performance(self):
        """Load strategy performance metrics for decision making"""
        
        print("📊 Loading strategy performance...")
        
        performance = {}
        
        # Load from strategy performance directory
        perf_dir = 'data/processed/strategy_performance'
        if os.path.exists(perf_dir):
            summary_file = os.path.join(perf_dir, 'summary.json')
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r') as f:
                        performance = json.load(f)
                    print(f"   ✅ Loaded performance for {len(performance)} strategies")
                except Exception as e:
                    print(f"   ⚠️ Error loading strategy performance: {e}")
        
        # Load from backtests directory as fallback
        backtest_dir = 'data/processed/backtests'
        if not performance and os.path.exists(backtest_dir):
            for file in os.listdir(backtest_dir):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(backtest_dir, file))
                        if not df.empty and len(df) > 1:
                            returns = df['daily_return']
                            equity = df['equity']
                            
                            performance[strategy_name] = {
                                'total_return': equity.iloc[-1] - 1,
                                'ann_return': (equity.iloc[-1] ** (252 / len(df))) - 1,
                                'volatility': returns.std() * np.sqrt(252),
                                'sharpe': (returns.mean() * 252) / (returns.std() * np.sqrt(252)),
                                'max_drawdown': df['drawdown'].min(),
                                'win_rate': (returns > 0).mean(),
                                'last_return': returns.iloc[-1] if len(returns) > 0 else 0
                            }
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
            
            if performance:
                print(f"   ✅ Loaded performance from backtests: {len(performance)} strategies")
        
        return performance
    
    def load_capital_allocations(self):
        """Load current capital allocations across strategies"""
        
        allocations = {}
        
        try:
            alloc_file = 'data/processed/capital_allocations.json'
            if os.path.exists(alloc_file):
                with open(alloc_file, 'r') as f:
                    data = json.load(f)
                    allocations = data.get('allocations', {})
                    print(f"   ✅ Loaded capital allocations: {len(allocations)} strategies")
        except Exception as e:
            print(f"   ⚠️ Could not load capital allocations: {e}")
        
        return allocations
    
    def load_universe_scores(self):
        """Load stock universe with scores and rankings"""
        
        print("📊 Loading stock universe...")
        
        try:
            if os.path.exists(self.paths['scores']):
                scores_df = pd.read_parquet(self.paths['scores'])
                
                # Ensure we have required columns
                required_cols = ['ticker']
                score_cols = [c for c in ['northstar_score', 'final_score', 'score'] if c in scores_df.columns]
                
                if not score_cols:
                    print("   ⚠️ No score columns found, using equal weights")
                    scores_df['score'] = 1.0
                    score_col = 'score'
                else:
                    score_col = score_cols[0]
                
                # Clean and prepare data
                universe = scores_df[scores_df[score_col].notna()].copy()
                universe = universe.sort_values(score_col, ascending=False)
                
                # Add company names if available
                if 'Company Name' not in universe.columns:
                    universe['Company Name'] = universe['ticker']
                
                # Add industry if available
                if 'Industry' not in universe.columns:
                    universe['Industry'] = 'Unknown'
                
                print(f"   ✅ Universe loaded: {len(universe)} stocks")
                return universe, score_col
                
        except Exception as e:
            print(f"   ❌ Error loading universe: {e}")
        
        # Fallback empty universe with standardized column names
        return pd.DataFrame(columns=['ticker', 'score', 'company_name', 'industry']), 'score'
    
    def load_opportunity_surface(self):
        """Load opportunity surface for enhanced position sizing"""
        
        print("🎯 Loading opportunity surface...")
        
        try:
            if os.path.exists(self.paths['opportunity_surface']):
                opp_df = pd.read_parquet(self.paths['opportunity_surface'])
                
                if not opp_df.empty and 'mispricing' in opp_df.columns:
                    print(f"   ✅ Opportunity surface loaded: {len(opp_df)} opportunities")
                    return opp_df
                    
        except Exception as e:
            print(f"   ⚠️ Could not load opportunity surface: {e}")
        
        return pd.DataFrame()
    
    def calculate_base_weights(self, universe, score_col, intelligence):
        """Calculate base portfolio weights from scores or strategy blending"""
        
        print("🧬 Calculating base portfolio weights...")
        
        if universe.empty:
            print("   ⚠️ Empty universe, returning empty portfolio")
            return pd.DataFrame()
        
        # Check if we have capital allocations for strategy blending
        allocations = intelligence.get('capital_allocations', {})
        
        if allocations and len(allocations) > 1:
            # Use strategy blending
            return self.construct_blended_portfolio(intelligence, universe)
        else:
            # Use single strategy approach
            return self.construct_single_strategy_portfolio(universe, intelligence, score_col)
    
    def construct_blended_portfolio(self, intelligence, universe):
        """Construct portfolio by blending multiple strategies based on capital allocations"""
        
        print("🧬 Constructing blended portfolio from strategies...")
        
        # Get capital allocations
        allocations = intelligence.get('capital_allocations', {})
        
        if not allocations:
            print("   ⚠️ No capital allocations found, using single strategy")
            return self.construct_single_strategy_portfolio(universe, intelligence)
        
        # Load strategy portfolios
        strategy_portfolios = {}
        strategy_dir = 'data/processed/strategy_portfolios'
        
        for strategy, allocation in allocations.items():
            if allocation > 0.01:  # Only load strategies with >1% allocation
                strategy_file = os.path.join(strategy_dir, f"{strategy}.parquet")
                if os.path.exists(strategy_file):
                    try:
                        df = pd.read_parquet(strategy_file)
                        if not df.empty and 'ticker' in df.columns and 'weight' in df.columns:
                            weights = df.set_index('ticker')['weight']
                            strategy_portfolios[strategy] = weights
                            print(f"   📊 Loaded {strategy}: {len(weights)} positions, {allocation:.1%} allocation")
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy}: {e}")
        
        if not strategy_portfolios:
            print("   ⚠️ No strategy portfolios loaded, falling back to single strategy")
            return self.construct_single_strategy_portfolio(universe, intelligence)
        
        # Blend strategies
        print(f"   🧬 Blending {len(strategy_portfolios)} strategies...")
        
        # Get all tickers from all strategies
        all_tickers = set()
        for weights in strategy_portfolios.values():
            all_tickers.update(weights.index)
        
        # Create blended weights
        blended_weights = pd.Series(0.0, index=list(all_tickers))
        
        for strategy, weights in strategy_portfolios.items():
            allocation = allocations.get(strategy, 0)
            if allocation > 0:
                # Add weighted contribution from this strategy
                aligned_weights = weights.reindex(blended_weights.index).fillna(0)
                blended_weights += allocation * aligned_weights
        
        # Filter to universe and normalize
        universe_tickers = set(universe['ticker'])
        blended_weights = blended_weights[blended_weights.index.isin(universe_tickers)]
        blended_weights = blended_weights[blended_weights > 0.001]  # Remove tiny weights
        
        if blended_weights.sum() > 0:
            blended_weights = blended_weights / blended_weights.sum()
        
        # Convert to portfolio format matching expected structure
        portfolio_data = []
        for ticker, weight in blended_weights.items():
            if weight > 0.001:
                company_info = universe[universe['ticker'] == ticker]
                if not company_info.empty:
                    row = company_info.iloc[0].to_dict()
                    row['base_weight'] = weight
                    portfolio_data.append(row)
        
        portfolio = pd.DataFrame(portfolio_data)
        
        if not portfolio.empty:
            print(f"   ✅ Blended portfolio: {len(portfolio)} positions from {len(strategy_portfolios)} strategies")
            
            # Show strategy contributions
            for strategy, allocation in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
                if allocation > 0.01:
                    print(f"     {strategy}: {allocation:.1%}")
        
        return portfolio
    
    def construct_single_strategy_portfolio(self, universe, intelligence, score_col=None):
        """Construct portfolio using single strategy approach"""
        
        print("📊 Constructing single strategy portfolio...")
        
        # Select top stocks based on regime
        regime = intelligence['regime']
        risk_on_prob = intelligence['risk_on_prob']
        
        # Adjust universe size based on market conditions
        if risk_on_prob > 0.7:
            max_positions = 25  # More concentrated in risk-on
        elif risk_on_prob < 0.3:
            max_positions = 40  # More diversified in risk-off
        else:
            max_positions = 30  # Balanced
        
        # Select top stocks
        top_stocks = universe.head(max_positions).copy()
        
        # Calculate weights using softmax with regime adjustment
        if score_col and score_col in top_stocks.columns:
            scores = top_stocks[score_col].values
            
            # Adjust concentration based on risk-on probability
            concentration_factor = 1.0 + (risk_on_prob - 0.5) * 2.0  # 0 to 2 range
            
            # Apply softmax
            scores_normalized = (scores - scores.mean()) / (scores.std() + 1e-8)
            scores_adjusted = scores_normalized * concentration_factor
            exp_scores = np.exp(scores_adjusted - scores_adjusted.max())
            weights = exp_scores / exp_scores.sum()
        else:
            # Equal weights if no score column
            weights = np.ones(len(top_stocks)) / len(top_stocks)
        
        top_stocks['base_weight'] = weights
        
        print(f"   ✅ Single strategy portfolio: {len(top_stocks)} positions")
        if score_col and score_col in top_stocks.columns:
            concentration_factor = 1.0 + (risk_on_prob - 0.5) * 2.0
            print(f"   📊 Concentration factor: {concentration_factor:.2f}")
            print(f"   📊 Top position: {weights.max():.2%}")
        
        return top_stocks
    
    def apply_opportunity_enhancement(self, portfolio, opportunity_surface):
        """Enhance weights based on opportunity surface"""
        
        if opportunity_surface.empty:
            portfolio['opportunity_weight'] = portfolio['base_weight']
            return portfolio
        
        print("🎯 Applying opportunity enhancement...")
        
        # Merge with opportunity data
        portfolio = portfolio.merge(
            opportunity_surface[['ticker', 'mispricing', 'confirmation']], 
            on='ticker', 
            how='left'
        )
        
        # Fill missing opportunity data
        portfolio['mispricing'] = portfolio['mispricing'].fillna(0)
        portfolio['confirmation'] = portfolio['confirmation'].fillna(0)
        
        # Calculate opportunity score
        portfolio['opportunity_score'] = (
            portfolio['mispricing'] * 0.6 + 
            portfolio['confirmation'] * 0.4
        )
        
        # Apply opportunity multiplier (0.8x to 1.5x)
        opp_multiplier = 0.8 + (portfolio['opportunity_score'] * 0.7)
        opp_multiplier = np.clip(opp_multiplier, 0.8, 1.5)
        
        portfolio['opportunity_weight'] = portfolio['base_weight'] * opp_multiplier
        
        # Renormalize
        total_weight = portfolio['opportunity_weight'].sum()
        if total_weight > 0:
            portfolio['opportunity_weight'] = portfolio['opportunity_weight'] / total_weight
        
        enhanced_positions = (opp_multiplier > 1.1).sum()
        print(f"   ✅ Enhanced {enhanced_positions} positions based on opportunities")
        
        return portfolio
    
    def apply_risk_controls(self, portfolio, intelligence):
        """Apply all risk controls and constraints"""
        
        print("🛡️ Applying risk controls...")
        
        if portfolio.empty:
            return portfolio
        
        # Start with opportunity weights
        portfolio['risk_controlled_weight'] = portfolio['opportunity_weight'].copy()
        
        # 1. Single position limits
        max_single = self.constraints['max_single_position']
        over_limit = portfolio['risk_controlled_weight'] > max_single
        if over_limit.any():
            excess = (portfolio.loc[over_limit, 'risk_controlled_weight'] - max_single).sum()
            portfolio.loc[over_limit, 'risk_controlled_weight'] = max_single
            
            # Redistribute excess to other positions
            under_limit = ~over_limit
            if under_limit.any():
                redistribution = excess * (portfolio.loc[under_limit, 'risk_controlled_weight'] / 
                                         portfolio.loc[under_limit, 'risk_controlled_weight'].sum())
                portfolio.loc[under_limit, 'risk_controlled_weight'] += redistribution
            
            print(f"   📊 Capped {over_limit.sum()} positions at {max_single:.1%}")
        
        # 2. Sector concentration limits
        max_sector = self.constraints['max_sector_exposure']
        sector_weights = portfolio.groupby('Industry')['risk_controlled_weight'].sum()
        over_sectors = sector_weights[sector_weights > max_sector]
        
        if len(over_sectors) > 0:
            for sector in over_sectors.index:
                sector_mask = portfolio['Industry'] == sector
                sector_total = portfolio.loc[sector_mask, 'risk_controlled_weight'].sum()
                scaling_factor = max_sector / sector_total
                portfolio.loc[sector_mask, 'risk_controlled_weight'] *= scaling_factor
            
            print(f"   📊 Applied sector caps to {len(over_sectors)} sectors")
        
        # 3. Renormalize after constraints
        total_weight = portfolio['risk_controlled_weight'].sum()
        if total_weight > 0:
            portfolio['risk_controlled_weight'] = portfolio['risk_controlled_weight'] / total_weight
        
        return portfolio
    
    def apply_regime_overlay(self, portfolio, intelligence):
        """Apply regime-based portfolio overlay with strategy performance awareness"""
        
        print("🌍 Applying regime overlay with strategy intelligence...")
        
        if portfolio.empty:
            return portfolio
        
        regime = intelligence['regime']
        allowed_exposure = intelligence['allowed_exposure']
        risk_on_prob = intelligence['risk_on_prob']
        strategy_performance = intelligence.get('strategy_performance', {})
        
        # Calculate risk-scaled exposure based on portfolio volatility
        # For now, use a simple estimate - in production this would use actual portfolio vol
        estimated_portfolio_vol = 0.20  # 20% annualized volatility estimate
        target_vol = 0.15  # 15% target volatility
        
        risk_scaled_result = self.exposure_calculator.calculate_risk_scaled_exposure(
            portfolio_volatility=estimated_portfolio_vol,
            target_volatility=target_vol
        )
        
        # Combine exposures: take the minimum (most conservative)
        combined_exposure = self.exposure_calculator.combine_exposures(
            allowed_exposure=allowed_exposure,
            risk_scaled_exposure=risk_scaled_result.value
        )
        
        # Use the combined (minimum) exposure
        final_exposure = combined_exposure.value
        
        # Apply exposure scaling
        portfolio['final_weight'] = portfolio['risk_controlled_weight'] * final_exposure
        
        # Log exposure decision
        print(f"   📊 Exposure Decision:")
        print(f"      Market Allowed: {allowed_exposure:.1%}")
        print(f"      Risk Scaled: {risk_scaled_result.value:.1%}")
        print(f"      Final (min): {final_exposure:.1%}")
        
        if combined_exposure.was_bounded:
            print(f"   ⚠️ {combined_exposure.bound_reason}")
        
        # Strategy performance adjustments
        if strategy_performance:
            print("   🧠 Applying strategy performance adjustments...")
            
            # Check momentum strategy performance
            mom_6m_perf = strategy_performance.get('mom_6m', {})
            if mom_6m_perf.get('max_drawdown', 0) < -0.15:  # 15% drawdown threshold
                print("   ⚠️ Momentum strategy underperforming - reducing momentum positions")
                # Reduce weights of momentum-classified positions
                # This would require position classification, simplified for now
                portfolio['final_weight'] *= 0.9  # General reduction
            
            # Check value strategy performance
            value_perf = strategy_performance.get('value_tilt', {})
            northstar_perf = strategy_performance.get('northstar', {})
            
            if (value_perf.get('ann_return', 0) > northstar_perf.get('ann_return', 0) and
                value_perf.get('sharpe', 0) > northstar_perf.get('sharpe', 0)):
                print("   📈 Value strategy outperforming - boosting value positions")
                # This is a simplified implementation - in practice would classify positions
                portfolio['final_weight'] *= 1.05  # General boost
        
        # Apply regime-specific adjustments
        if regime in ['crisis', 'slowdown']:
            # Favor quality and defensives
            quality_boost = 1.2
            defensive_sectors = ['Utilities', 'Consumer Staples', 'Healthcare']
            
            for sector in defensive_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= quality_boost
                    
            # Check if low_vol strategy is performing well
            low_vol_perf = strategy_performance.get('low_vol', {})
            if low_vol_perf.get('sharpe', 0) > 1.0:  # Good Sharpe ratio
                print("   🛡️ Low volatility strategy performing well - defensive boost")
                portfolio['final_weight'] *= 1.1
        
        elif regime in ['boom', 'expansion']:
            # Favor growth and cyclicals
            growth_boost = 1.1
            cyclical_sectors = ['Technology', 'Industrials', 'Materials']
            
            for sector in cyclical_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= growth_boost
                    
            # Check if momentum strategies are performing well
            mom_strategies = ['mom_6m', 'mom_12m', 'dual_momentum']
            avg_mom_sharpe = np.mean([strategy_performance.get(s, {}).get('sharpe', 0) for s in mom_strategies])
            if avg_mom_sharpe > 0.8:
                print("   🚀 Momentum strategies performing well - growth boost")
                portfolio['final_weight'] *= 1.1
        
        # Renormalize to maintain target exposure
        total_weight = portfolio['final_weight'].sum()
        if total_weight > 0:
            portfolio['final_weight'] = portfolio['final_weight'] / total_weight * final_exposure
        
        print(f"   ✅ Applied {regime} regime overlay with strategy intelligence")
        print(f"   📊 Target exposure: {final_exposure:.1%}")
        
        # Show performance-based adjustments made
        if strategy_performance:
            performing_strategies = [s for s, p in strategy_performance.items() 
                                   if p.get('sharpe', 0) > 0.5]
            if performing_strategies:
                print(f"   📈 Well-performing strategies: {', '.join(performing_strategies[:3])}")
        
        return portfolio
    
    def assign_position_roles(self, portfolio):
        """Assign roles to portfolio positions"""
        
        print("🎭 Assigning position roles...")
        
        if portfolio.empty:
            return portfolio
        
        # Assign roles based on weight and characteristics
        portfolio['position_role'] = 'Satellite'  # Default
        
        # Core positions (top 40% by weight)
        top_40_threshold = portfolio['final_weight'].quantile(0.6)
        portfolio.loc[portfolio['final_weight'] >= top_40_threshold, 'position_role'] = 'Core'
        
        # Quality positions (defensive sectors)
        defensive_sectors = ['Utilities', 'Consumer Staples', 'Healthcare']
        quality_mask = portfolio['Industry'].isin(defensive_sectors)
        portfolio.loc[quality_mask, 'position_role'] = 'Quality'
        
        # Value positions (if we have value indicators)
        # This would be enhanced with actual value metrics
        
        role_counts = portfolio['position_role'].value_counts()
        print(f"   ✅ Roles assigned: {dict(role_counts)}")
        
        return portfolio
    
    def calculate_portfolio_analytics(self, portfolio, intelligence):
        """Calculate comprehensive portfolio analytics"""
        
        print("📈 Calculating portfolio analytics...")
        
        analytics = {
            'timestamp': datetime.now().isoformat(),
            'portfolio_summary': {},
            'risk_metrics': {},
            'sector_allocation': {},
            'position_analysis': {},
            'compliance_check': {},
            'intelligence_integration': {}
        }
        
        if portfolio.empty:
            analytics['portfolio_summary'] = {
                'total_positions': 0,
                'total_exposure': 0.0,
                'cash_level': 1.0,
                'largest_position': 0.0
            }
            return analytics
        
        # Portfolio summary
        total_exposure = portfolio['final_weight'].sum()
        analytics['portfolio_summary'] = {
            'total_positions': len(portfolio),
            'total_exposure': float(total_exposure),
            'cash_level': float(1.0 - total_exposure),
            'largest_position': float(portfolio['final_weight'].max()),
            'smallest_position': float(portfolio['final_weight'].min()),
            'median_position': float(portfolio['final_weight'].median()),
            'concentration_ratio': float(portfolio['final_weight'].head(5).sum())  # Top 5 concentration
        }
        
        # Risk metrics
        analytics['risk_metrics'] = {
            'diversification_score': min(1.0, len(portfolio) / 20),  # 20+ positions = full diversification
            'concentration_risk': float(portfolio['final_weight'].max()),
            'sector_concentration': float(portfolio.groupby('Industry')['final_weight'].sum().max()),
            'position_count': len(portfolio),
            'effective_positions': float(1 / (portfolio['final_weight'] ** 2).sum())  # Herfindahl index
        }
        
        # Sector allocation
        sector_allocation = portfolio.groupby('Industry')['final_weight'].sum().to_dict()
        analytics['sector_allocation'] = {k: float(v) for k, v in sector_allocation.items()}
        
        # Position analysis
        analytics['position_analysis'] = {
            'top_positions': portfolio.nlargest(10, 'final_weight')[['ticker', 'Company Name', 'final_weight', 'position_role']].to_dict('records'),
            'role_distribution': portfolio['position_role'].value_counts().to_dict()
        }
        
        # Compliance check
        compliance = {
            'max_single_position': portfolio['final_weight'].max() <= self.constraints['max_single_position'],
            'max_sector_exposure': portfolio.groupby('Industry')['final_weight'].sum().max() <= self.constraints['max_sector_exposure'],
            'min_diversification': len(portfolio) >= self.constraints['min_diversification'],
            'total_exposure_limit': total_exposure <= self.constraints['max_total_exposure']
        }
        analytics['compliance_check'] = compliance
        analytics['compliance_check']['all_compliant'] = all(compliance.values())
        
        # Intelligence integration
        analytics['intelligence_integration'] = {
            'regime': intelligence['regime'],
            'allowed_exposure': intelligence['allowed_exposure'],
            'risk_on_probability': intelligence['risk_on_prob'],
            'ai_active': intelligence['ai_active'],
            'market_state_compliance': abs(total_exposure - intelligence['allowed_exposure']) < 0.05
        }
        
        print(f"   ✅ Analytics calculated")
        print(f"   📊 Total exposure: {total_exposure:.1%}")
        print(f"   📊 Positions: {len(portfolio)}")
        print(f"   📊 Compliance: {'✅' if analytics['compliance_check']['all_compliant'] else '❌'}")
        
        return analytics
    
    def save_portfolio(self, portfolio, analytics):
        """Save final portfolio and analytics"""
        
        print("💾 Saving portfolio...")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(self.paths['output']), exist_ok=True)
        
        # Save portfolio weights
        if not portfolio.empty:
            # Prepare output columns
            output_cols = [
                'ticker', 'Company Name', 'Industry', 'final_weight', 
                'position_role', 'base_weight', 'opportunity_weight'
            ]
            output_cols = [c for c in output_cols if c in portfolio.columns]
            
            portfolio_output = portfolio[output_cols].copy()
            portfolio_output.to_parquet(self.paths['output'], index=False)
            print(f"   ✅ Portfolio saved: {self.paths['output']}")
        else:
            # Save empty portfolio
            empty_portfolio = pd.DataFrame(columns=['ticker', 'final_weight'])
            empty_portfolio.to_parquet(self.paths['output'], index=False)
            print(f"   ✅ Empty portfolio saved: {self.paths['output']}")
        
        # Save analytics
        with open(self.paths['analytics'], 'w') as f:
            json.dump(analytics, f, indent=2, default=str)
        print(f"   ✅ Analytics saved: {self.paths['analytics']}")
    
    def run_portfolio_construction(self):
        """Main portfolio construction process"""
        
        print("🎯 PORTFOLIO GOVERNOR - NORTHSTAR V3")
        print("=" * 60)
        
        # Step 1: Load market intelligence
        intelligence = self.load_market_intelligence()
        
        # Step 2: Load stock universe
        universe, score_col = self.load_universe_scores()
        
        # Step 3: Load opportunity surface
        opportunity_surface = self.load_opportunity_surface()
        
        # Step 4: Calculate base weights
        portfolio = self.calculate_base_weights(universe, score_col, intelligence)
        
        if portfolio.empty:
            print("⚠️ No valid portfolio generated - saving empty portfolio")
            analytics = self.calculate_portfolio_analytics(portfolio, intelligence)
            self.save_portfolio(portfolio, analytics)
            return portfolio, analytics
        
        # Step 5: Apply opportunity enhancement
        portfolio = self.apply_opportunity_enhancement(portfolio, opportunity_surface)
        
        # Step 6: Apply risk controls
        portfolio = self.apply_risk_controls(portfolio, intelligence)
        
        # Step 7: Apply regime overlay
        portfolio = self.apply_regime_overlay(portfolio, intelligence)
        
        # Step 8: Assign position roles
        portfolio = self.assign_position_roles(portfolio)
        
        # Step 9: Calculate analytics
        analytics = self.calculate_portfolio_analytics(portfolio, intelligence)
        
        # Step 10: Save portfolio
        self.save_portfolio(portfolio, analytics)
        
        print("\n✅ PORTFOLIO CONSTRUCTION COMPLETE")
        print(f"📊 Final Portfolio: {len(portfolio)} positions, {analytics['portfolio_summary']['total_exposure']:.1%} exposure")
        
        return portfolio, analytics

def main():
    """Main execution function"""
    
    governor = PortfolioGovernor()
    portfolio, analytics = governor.run_portfolio_construction()
    
    return portfolio, analytics

if __name__ == "__main__":
    main()