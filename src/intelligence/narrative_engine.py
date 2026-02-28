#!/usr/bin/env python3
"""
📖 NARRATIVE ENGINE - 5 JURORS SYSTEM
Institutional-Grade Market Narrative Intelligence for Northstar V3

Instead of "bullish/bearish", make 5 jurors vote:

Juror          | What it says
---------------|------------------------------------------
Macro          | Liquidity, rates, inflation
Earnings       | Revisions, margins  
Flows          | FII, sector rotation
Technicals     | Trend & momentum
Valuation      | Cheap or expensive

Each juror votes: +1 bullish, 0 neutral, -1 bearish

Market narrative = sum of votes
Conviction = agreement between jurors

Example:
Macro: -1, Earnings: +1, Flows: -1, Technicals: -1, Valuation: +1
Net = -1, Conviction = low (they disagree)
Result: Market is bearish, but uncertainty is high → reduce exposure

This is how BlackRock, Bridgewater, AQR actually think about markets.

Usage:
    try:
    from intelligence.narrative_engine import NarrativeEngine
except ImportError:
    from NarrativeEngine import NarrativeEngine
    
    engine = NarrativeEngine()
    narrative = engine.generate_market_narrative()
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import warnings
warnings.filterwarnings('ignore')

# =========================== NARRATIVE ENGINE CORE ===========================

class NarrativeEngine:
    """
    5 Jurors Market Narrative System
    
    Each juror independently evaluates market conditions and votes.
    The narrative emerges from the collective wisdom (or disagreement).
    """
    
    def __init__(self):
        self.name = "Narrative Engine - 5 Jurors"
        
        # Juror definitions
        self.jurors = {
            'macro': MacroJuror(),
            'earnings': EarningsJuror(), 
            'flows': FlowsJuror(),
            'technicals': TechnicalsJuror(),
            'valuation': ValuationJuror()
        }
        
        # Vote interpretation
        self.vote_meanings = {
            1: 'Bullish',
            0: 'Neutral', 
            -1: 'Bearish'
        }
        
        # Conviction thresholds
        self.conviction_thresholds = {
            'very_high': 0.9,   # Almost all jurors agree
            'high': 0.7,        # Strong agreement
            'moderate': 0.5,    # Some agreement
            'low': 0.3,         # Significant disagreement
            'very_low': 0.1     # Complete chaos
        }
    
    def generate_market_narrative(self, market_data=None):
        """
        Generate complete market narrative from 5 jurors
        
        Returns comprehensive narrative with votes, conviction, and implications
        """
        
        print("📖 Generating market narrative from 5 jurors...")
        
        # Collect votes from all jurors
        juror_votes = {}
        juror_details = {}
        
        for juror_name, juror in self.jurors.items():
            try:
                vote_result = juror.cast_vote(market_data)
                juror_votes[juror_name] = vote_result['vote']
                juror_details[juror_name] = vote_result
                print(f"  {juror_name.title()}: {vote_result['vote']:+d} ({vote_result['reasoning']})")
            except Exception as e:
                print(f"  {juror_name.title()}: ERROR ({e})")
                juror_votes[juror_name] = 0  # Neutral vote on error
                juror_details[juror_name] = {
                    'vote': 0,
                    'confidence': 0.3,
                    'reasoning': f'Error: {e}',
                    'status': 'error'
                }
        
        # Calculate aggregate narrative
        total_votes = sum(juror_votes.values())
        num_jurors = len(juror_votes)
        
        # Calculate conviction (agreement between jurors)
        conviction = self.calculate_conviction(juror_votes, juror_details)
        
        # Generate narrative text
        narrative_text = self.synthesize_narrative(
            juror_votes, juror_details, total_votes, conviction
        )
        
        # Determine market stance
        if total_votes >= 2:
            market_stance = 'Bullish'
        elif total_votes <= -2:
            market_stance = 'Bearish'
        else:
            market_stance = 'Neutral'
        
        # Calculate exposure recommendation
        exposure_recommendation = self.calculate_exposure_recommendation(
            total_votes, conviction, num_jurors
        )
        
        return {
            'timestamp': datetime.now(),
            'juror_votes': juror_votes,
            'juror_details': juror_details,
            'total_votes': total_votes,
            'market_stance': market_stance,
            'conviction': conviction,
            'conviction_level': self.get_conviction_level(conviction),
            'narrative_text': narrative_text,
            'exposure_recommendation': exposure_recommendation,
            'agreement_analysis': self.analyze_agreement(juror_votes),
            'key_themes': self.extract_key_themes(juror_details)
        }
    
    def calculate_conviction(self, votes, details):
        """
        Calculate conviction based on juror agreement
        
        High conviction = jurors agree (all vote same direction)
        Low conviction = jurors disagree (votes scattered)
        """
        
        vote_values = list(votes.values())
        confidences = [d.get('confidence', 0.5) for d in details.values()]
        
        # Method 1: Vote agreement
        if len(vote_values) == 0:
            return 0.3
        
        # Calculate vote dispersion
        vote_std = np.std(vote_values)
        max_std = np.sqrt(2)  # Maximum std for votes in {-1, 0, 1}
        
        # Agreement score (lower std = higher agreement)
        agreement_score = 1 - (vote_std / max_std)
        
        # Method 2: Confidence-weighted agreement
        avg_confidence = np.mean(confidences)
        
        # Method 3: Directional consistency
        positive_votes = sum(1 for v in vote_values if v > 0)
        negative_votes = sum(1 for v in vote_values if v < 0)
        neutral_votes = sum(1 for v in vote_values if v == 0)
        
        # Directional conviction (how many agree on direction)
        max_directional = max(positive_votes, negative_votes, neutral_votes)
        directional_conviction = max_directional / len(vote_values)
        
        # Combined conviction
        conviction = (
            0.4 * agreement_score +
            0.3 * avg_confidence +
            0.3 * directional_conviction
        )
        
        return max(0.1, min(1.0, conviction))
    
    def get_conviction_level(self, conviction):
        """Convert conviction score to descriptive level"""
        
        if conviction >= self.conviction_thresholds['very_high']:
            return 'Very High'
        elif conviction >= self.conviction_thresholds['high']:
            return 'High'
        elif conviction >= self.conviction_thresholds['moderate']:
            return 'Moderate'
        elif conviction >= self.conviction_thresholds['low']:
            return 'Low'
        else:
            return 'Very Low'
    
    def synthesize_narrative(self, votes, details, total_votes, conviction):
        """Synthesize human-readable narrative from juror votes"""
        
        # Overall market assessment
        if total_votes >= 2:
            overall = "BULLISH"
        elif total_votes <= -2:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        # Conviction assessment
        conviction_level = self.get_conviction_level(conviction)
        
        # Start narrative
        narrative = f"Market narrative: {overall} with {conviction_level.upper()} conviction. "
        
        # Vote breakdown
        bullish_jurors = [name for name, vote in votes.items() if vote > 0]
        bearish_jurors = [name for name, vote in votes.items() if vote < 0]
        neutral_jurors = [name for name, vote in votes.items() if vote == 0]
        
        if bullish_jurors:
            narrative += f"Bullish: {', '.join(bullish_jurors).title()}. "
        if bearish_jurors:
            narrative += f"Bearish: {', '.join(bearish_jurors).title()}. "
        if neutral_jurors:
            narrative += f"Neutral: {', '.join(neutral_jurors).title()}. "
        
        # Key insights from highest confidence jurors
        high_confidence_insights = []
        for name, detail in details.items():
            if detail.get('confidence', 0) > 0.7:
                vote_desc = self.vote_meanings[detail['vote']]
                reasoning = detail.get('reasoning', 'No reason given')
                high_confidence_insights.append(f"{name.title()}: {vote_desc} ({reasoning})")
        
        if high_confidence_insights:
            narrative += f"Key insights: {'; '.join(high_confidence_insights[:2])}. "
        
        # Conviction implications
        if conviction < 0.4:
            narrative += "High uncertainty suggests defensive positioning. "
        elif conviction > 0.7:
            narrative += "Strong consensus enables confident positioning. "
        
        return narrative
    
    def calculate_exposure_recommendation(self, total_votes, conviction, num_jurors):
        """
        Calculate recommended exposure based on narrative
        
        This is where narrative translates to portfolio action
        """
        
        # Base exposure from vote direction
        vote_ratio = total_votes / num_jurors  # -1 to +1
        
        # Base exposure (50% neutral, adjust by vote ratio)
        base_exposure = 50 + (vote_ratio * 30)  # 20% to 80% range
        
        # Adjust by conviction
        if conviction > 0.7:
            # High conviction: can take larger positions
            conviction_multiplier = 1.2
        elif conviction > 0.5:
            # Moderate conviction: normal positions
            conviction_multiplier = 1.0
        elif conviction > 0.3:
            # Low conviction: reduce positions
            conviction_multiplier = 0.8
        else:
            # Very low conviction: minimal positions
            conviction_multiplier = 0.6
        
        # Final exposure recommendation
        recommended_exposure = base_exposure * conviction_multiplier
        
        # Clamp to reasonable range
        recommended_exposure = max(20, min(80, recommended_exposure))
        
        return {
            'recommended_exposure': recommended_exposure,
            'base_exposure': base_exposure,
            'conviction_multiplier': conviction_multiplier,
            'vote_ratio': vote_ratio,
            'reasoning': f"Votes: {total_votes}/{num_jurors}, Conviction: {conviction:.2f}"
        }
    
    def analyze_agreement(self, votes):
        """Analyze patterns in juror agreement/disagreement"""
        
        vote_counts = {-1: 0, 0: 0, 1: 0}
        for vote in votes.values():
            vote_counts[vote] += 1
        
        total_jurors = len(votes)
        
        analysis = {
            'unanimous': len(set(votes.values())) == 1,
            'majority_bullish': vote_counts[1] > total_jurors / 2,
            'majority_bearish': vote_counts[-1] > total_jurors / 2,
            'split_decision': vote_counts[1] == vote_counts[-1],
            'vote_distribution': vote_counts,
            'consensus_strength': max(vote_counts.values()) / total_jurors
        }
        
        return analysis
    
    def extract_key_themes(self, juror_details):
        """Extract key themes from juror reasoning"""
        
        themes = []
        
        for juror_name, details in juror_details.items():
            reasoning = details.get('reasoning', '')
            vote = details.get('vote', 0)
            confidence = details.get('confidence', 0.5)
            
            if confidence > 0.6:  # Only include high-confidence themes
                theme = {
                    'juror': juror_name,
                    'theme': reasoning,
                    'direction': 'bullish' if vote > 0 else 'bearish' if vote < 0 else 'neutral',
                    'confidence': confidence
                }
                themes.append(theme)
        
        # Sort by confidence
        themes.sort(key=lambda x: x['confidence'], reverse=True)
        
        return themes[:3]  # Top 3 themes

# =========================== INDIVIDUAL JURORS ===========================

class MacroJuror:
    """
    Juror 1: Macro Environment
    Votes based on: Liquidity, rates, inflation, growth
    """
    
    def __init__(self):
        self.name = "Macro"
        self.data_sources = [
            'data/macro/factors/macro_score.parquet',
            'data/processed/market_state.parquet'
        ]
    
    def load_macro_data(self):
        """Load latest macro data"""
        try:
            # Try macro score first
            macro_path = 'data/macro/factors/macro_score.parquet'
            if os.path.exists(macro_path):
                df = pd.read_parquet(macro_path)
                if not df.empty:
                    return df.iloc[-1].to_dict()
            
            # Try market state as fallback
            state_path = 'data/processed/market_state.parquet'
            if os.path.exists(state_path):
                df = pd.read_parquet(state_path)
                if not df.empty:
                    return df.iloc[-1].to_dict()
        except Exception as e:
            pass
        
        return None
    
    def cast_vote(self, market_data=None):
        """Cast macro vote based on liquidity, rates, inflation"""
        
        macro_data = self.load_macro_data()
        
        if macro_data is None:
            return {
                'vote': 0,
                'confidence': 0.3,
                'reasoning': 'No macro data available',
                'status': 'no_data'
            }
        
        # Extract macro components
        macro_score = macro_data.get('MacroScore', macro_data.get('macro_score', 0.0))
        liquidity = macro_data.get('Contrib_L', macro_data.get('liquidity', 0.0))
        inflation = macro_data.get('Contrib_I', macro_data.get('inflation', 0.0))
        growth = macro_data.get('Contrib_G', macro_data.get('growth', 0.0))
        
        # Macro voting logic
        if macro_score > 0.5:
            vote = 1  # Bullish
            reasoning = f"Positive macro (score: {macro_score:.2f})"
        elif macro_score < -0.5:
            vote = -1  # Bearish
            reasoning = f"Negative macro (score: {macro_score:.2f})"
        else:
            vote = 0  # Neutral
            reasoning = f"Neutral macro (score: {macro_score:.2f})"
        
        # Confidence based on data quality and signal strength
        confidence = min(0.9, 0.5 + abs(macro_score) * 0.3)
        
        # Add detail to reasoning
        components = []
        if liquidity > 0.2:
            components.append("loose liquidity")
        elif liquidity < -0.2:
            components.append("tight liquidity")
        
        if growth > 0.2:
            components.append("strong growth")
        elif growth < -0.2:
            components.append("weak growth")
        
        if components:
            reasoning += f" - {', '.join(components)}"
        
        return {
            'vote': vote,
            'confidence': confidence,
            'reasoning': reasoning,
            'macro_score': macro_score,
            'components': {
                'liquidity': liquidity,
                'inflation': inflation,
                'growth': growth
            },
            'status': 'active'
        }

class EarningsJuror:
    """
    Juror 2: Earnings Environment  
    Votes based on: Earnings revisions, margins, guidance
    """
    
    def __init__(self):
        self.name = "Earnings"
        self.data_sources = [
            'data/processed/scores.parquet',
            'data/processed/fundamentals.parquet'
        ]
    
    def load_earnings_data(self):
        """Load earnings-related data"""
        try:
            scores_path = 'data/processed/scores.parquet'
            if os.path.exists(scores_path):
                df = pd.read_parquet(scores_path)
                if not df.empty:
                    return df
        except Exception as e:
            pass
        
        return pd.DataFrame()
    
    def cast_vote(self, market_data=None):
        """Cast earnings vote based on earnings trends"""
        
        earnings_df = self.load_earnings_data()
        
        if earnings_df.empty:
            return {
                'vote': 0,
                'confidence': 0.3,
                'reasoning': 'No earnings data available',
                'status': 'no_data'
            }
        
        # Analyze earnings metrics
        earnings_metrics = {}
        
        # ROE analysis
        if 'roe' in earnings_df.columns:
            roe_data = earnings_df['roe'].dropna()
            if not roe_data.empty:
                avg_roe = roe_data.mean()
                earnings_metrics['avg_roe'] = avg_roe
        
        # Revenue growth analysis
        if 'revenue_growth' in earnings_df.columns:
            growth_data = earnings_df['revenue_growth'].dropna()
            if not growth_data.empty:
                avg_growth = growth_data.mean()
                earnings_metrics['avg_revenue_growth'] = avg_growth
        
        # Margin analysis (if available)
        if 'operating_margin' in earnings_df.columns:
            margin_data = earnings_df['operating_margin'].dropna()
            if not margin_data.empty:
                avg_margin = margin_data.mean()
                earnings_metrics['avg_margin'] = avg_margin
        
        # Earnings voting logic
        positive_signals = 0
        negative_signals = 0
        
        # ROE assessment
        avg_roe = earnings_metrics.get('avg_roe', 15)
        if avg_roe > 18:
            positive_signals += 1
        elif avg_roe < 12:
            negative_signals += 1
        
        # Growth assessment
        avg_growth = earnings_metrics.get('avg_revenue_growth', 10)
        if avg_growth > 15:
            positive_signals += 1
        elif avg_growth < 5:
            negative_signals += 1
        
        # Margin assessment
        avg_margin = earnings_metrics.get('avg_margin', 15)
        if avg_margin > 20:
            positive_signals += 1
        elif avg_margin < 10:
            negative_signals += 1
        
        # Vote determination
        if positive_signals > negative_signals:
            vote = 1
            reasoning = f"Strong earnings (ROE: {avg_roe:.1f}%, Growth: {avg_growth:.1f}%)"
        elif negative_signals > positive_signals:
            vote = -1
            reasoning = f"Weak earnings (ROE: {avg_roe:.1f}%, Growth: {avg_growth:.1f}%)"
        else:
            vote = 0
            reasoning = f"Mixed earnings (ROE: {avg_roe:.1f}%, Growth: {avg_growth:.1f}%)"
        
        # Confidence based on data availability
        data_points = len([m for m in earnings_metrics.values() if not pd.isna(m)])
        confidence = min(0.8, 0.4 + data_points * 0.15)
        
        return {
            'vote': vote,
            'confidence': confidence,
            'reasoning': reasoning,
            'earnings_metrics': earnings_metrics,
            'positive_signals': positive_signals,
            'negative_signals': negative_signals,
            'status': 'active'
        }

class FlowsJuror:
    """
    Juror 3: Capital Flows
    Votes based on: FII flows, sector rotation, breadth
    """
    
    def __init__(self):
        self.name = "Flows"
        self.data_sources = [
            'data/options/live/market_data_latest.json',
            'data/processed/market_state.parquet'
        ]
    
    def load_flows_data(self):
        """Load market flows and breadth data"""
        flows_data = {}
        
        # Try market data
        try:
            market_path = 'data/options/live/market_data_latest.json'
            if os.path.exists(market_path):
                with open(market_path, 'r') as f:
                    market_data = json.load(f)
                    flows_data['market_data'] = market_data
        except Exception as e:
            pass
        
        # Try market state
        try:
            state_path = 'data/processed/market_state.parquet'
            if os.path.exists(state_path):
                df = pd.read_parquet(state_path)
                if not df.empty:
                    flows_data['market_state'] = df.iloc[-1].to_dict()
        except Exception as e:
            pass
        
        return flows_data
    
    def cast_vote(self, market_data=None):
        """Cast flows vote based on breadth and sector rotation"""
        
        flows_data = self.load_flows_data()
        
        if not flows_data:
            return {
                'vote': 0,
                'confidence': 0.3,
                'reasoning': 'No flows data available',
                'status': 'no_data'
            }
        
        # Analyze market breadth
        breadth_pct = 50  # Default
        
        if 'market_state' in flows_data:
            breadth_pct = flows_data['market_state'].get('breadth_pct', 50)
        elif 'market_data' in flows_data:
            # Calculate breadth from sector data
            indices = flows_data['market_data'].get('indices', {})
            if indices:
                positive_sectors = sum(1 for data in indices.values() 
                                     if data.get('net_change', 0) > 0)
                total_sectors = len(indices)
                breadth_pct = (positive_sectors / total_sectors * 100) if total_sectors > 0 else 50
        
        # Analyze sector rotation
        rotation_strength = 0
        if 'market_data' in flows_data:
            indices = flows_data['market_data'].get('indices', {})
            if indices:
                changes = [data.get('net_change', 0) for data in indices.values()]
                if changes:
                    rotation_strength = np.std(changes)  # Higher std = more rotation
        
        # Flows voting logic
        if breadth_pct > 60:
            vote = 1
            reasoning = f"Broad market strength ({breadth_pct:.0f}% sectors positive)"
        elif breadth_pct < 40:
            vote = -1
            reasoning = f"Narrow market weakness ({breadth_pct:.0f}% sectors positive)"
        else:
            vote = 0
            reasoning = f"Mixed flows ({breadth_pct:.0f}% sectors positive)"
        
        # Confidence based on data quality
        confidence = 0.7 if 'market_data' in flows_data else 0.5
        
        return {
            'vote': vote,
            'confidence': confidence,
            'reasoning': reasoning,
            'breadth_pct': breadth_pct,
            'rotation_strength': rotation_strength,
            'status': 'active'
        }

class TechnicalsJuror:
    """
    Juror 4: Technical Analysis
    Votes based on: Trend, momentum, support/resistance
    """
    
    def __init__(self):
        self.name = "Technicals"
        self.data_sources = [
            'data/processed/market_state.parquet',
            'data/options/live/market_data_latest.json'
        ]
    
    def load_technical_data(self):
        """Load technical analysis data"""
        try:
            # Market state for momentum
            state_path = 'data/processed/market_state.parquet'
            if os.path.exists(state_path):
                df = pd.read_parquet(state_path)
                if not df.empty:
                    return df.iloc[-1].to_dict()
        except Exception as e:
            pass
        
        return None
    
    def cast_vote(self, market_data=None):
        """Cast technical vote based on trend and momentum"""
        
        technical_data = self.load_technical_data()
        
        if technical_data is None:
            return {
                'vote': 0,
                'confidence': 0.3,
                'reasoning': 'No technical data available',
                'status': 'no_data'
            }
        
        # Extract technical indicators
        momentum = technical_data.get('macro_momentum', 0.0)
        health_score = technical_data.get('health_score', 0.5)
        volatility = technical_data.get('stress_level', 0.2)
        
        # Technical voting logic
        technical_score = 0
        
        # Momentum component
        if momentum > 0.3:
            technical_score += 1
        elif momentum < -0.3:
            technical_score -= 1
        
        # Health component
        if health_score > 0.6:
            technical_score += 1
        elif health_score < 0.4:
            technical_score -= 1
        
        # Volatility component (high vol is bearish)
        if volatility < 0.2:
            technical_score += 0.5
        elif volatility > 0.6:
            technical_score -= 1
        
        # Final vote
        if technical_score > 0.5:
            vote = 1
            reasoning = f"Positive technicals (momentum: {momentum:+.2f}, health: {health_score:.2f})"
        elif technical_score < -0.5:
            vote = -1
            reasoning = f"Negative technicals (momentum: {momentum:+.2f}, health: {health_score:.2f})"
        else:
            vote = 0
            reasoning = f"Mixed technicals (momentum: {momentum:+.2f}, health: {health_score:.2f})"
        
        # Confidence based on signal strength
        confidence = min(0.8, 0.5 + abs(technical_score) * 0.2)
        
        return {
            'vote': vote,
            'confidence': confidence,
            'reasoning': reasoning,
            'technical_score': technical_score,
            'momentum': momentum,
            'health_score': health_score,
            'volatility': volatility,
            'status': 'active'
        }

class ValuationJuror:
    """
    Juror 5: Valuation
    Votes based on: Cheap or expensive relative to fundamentals
    """
    
    def __init__(self):
        self.name = "Valuation"
        self.data_sources = [
            'data/processed/valuation_engines.parquet',
            'data/processed/opportunity_surface.parquet'
        ]
    
    def load_valuation_data(self):
        """Load valuation data"""
        try:
            # Try valuation engines first
            val_path = 'data/processed/valuation_engines.parquet'
            if os.path.exists(val_path):
                df = pd.read_parquet(val_path)
                if not df.empty:
                    return df
            
            # Try opportunity surface as fallback
            opp_path = 'data/processed/opportunity_surface.parquet'
            if os.path.exists(opp_path):
                df = pd.read_parquet(opp_path)
                if not df.empty:
                    return df
        except Exception as e:
            pass
        
        return pd.DataFrame()
    
    def cast_vote(self, market_data=None):
        """Cast valuation vote based on market-wide valuation"""
        
        valuation_df = self.load_valuation_data()
        
        if valuation_df.empty:
            return {
                'vote': 0,
                'confidence': 0.3,
                'reasoning': 'No valuation data available',
                'status': 'no_data'
            }
        
        # Analyze market-wide valuation
        valuation_metrics = {}
        
        # Composite valuation (if available)
        if 'composite_z' in valuation_df.columns:
            composite_z = valuation_df['composite_z'].mean()
            valuation_metrics['composite_z'] = composite_z
        
        # Mispricing (if available)
        if 'mispricing' in valuation_df.columns:
            avg_mispricing = valuation_df['mispricing'].mean()
            valuation_metrics['avg_mispricing'] = avg_mispricing
        
        # Fundamental valuation (if available)
        if 'fundamental_z' in valuation_df.columns:
            fundamental_z = valuation_df['fundamental_z'].mean()
            valuation_metrics['fundamental_z'] = fundamental_z
        
        # Valuation voting logic
        valuation_signal = 0
        
        # Use best available metric
        if 'composite_z' in valuation_metrics:
            valuation_signal = valuation_metrics['composite_z']
            metric_name = 'composite valuation'
        elif 'avg_mispricing' in valuation_metrics:
            valuation_signal = valuation_metrics['avg_mispricing']
            metric_name = 'mispricing'
        elif 'fundamental_z' in valuation_metrics:
            valuation_signal = valuation_metrics['fundamental_z']
            metric_name = 'fundamental valuation'
        else:
            return {
                'vote': 0,
                'confidence': 0.3,
                'reasoning': 'No usable valuation metrics',
                'status': 'no_metrics'
            }
        
        # Vote based on valuation signal
        if valuation_signal > 0.5:
            vote = 1  # Market is cheap (bullish)
            reasoning = f"Market undervalued ({metric_name}: {valuation_signal:+.2f})"
        elif valuation_signal < -0.5:
            vote = -1  # Market is expensive (bearish)
            reasoning = f"Market overvalued ({metric_name}: {valuation_signal:+.2f})"
        else:
            vote = 0  # Fair value
            reasoning = f"Market fairly valued ({metric_name}: {valuation_signal:+.2f})"
        
        # Confidence based on signal strength and data quality
        confidence = min(0.8, 0.5 + abs(valuation_signal) * 0.2)
        
        return {
            'vote': vote,
            'confidence': confidence,
            'reasoning': reasoning,
            'valuation_signal': valuation_signal,
            'metric_used': metric_name,
            'valuation_metrics': valuation_metrics,
            'status': 'active'
        }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate narrative engine functionality"""
    
    print("📖 NARRATIVE ENGINE - 5 JURORS SYSTEM")
    print("=" * 60)
    
    # Initialize narrative engine
    engine = NarrativeEngine()
    
    # Generate market narrative
    narrative_result = engine.generate_market_narrative()
    
    print("\n🗳️ JUROR VOTES")
    print("-" * 30)
    for juror, vote in narrative_result['juror_votes'].items():
        detail = narrative_result['juror_details'][juror]
        confidence = detail.get('confidence', 0.5)
        reasoning = detail.get('reasoning', 'No reason')
        
        vote_symbol = "🟢" if vote > 0 else "🔴" if vote < 0 else "🟡"
        print(f"{vote_symbol} {juror.title()}: {vote:+d} (conf: {confidence:.2f}) - {reasoning}")
    
    print(f"\n📊 NARRATIVE SUMMARY")
    print("-" * 30)
    print(f"Total Votes: {narrative_result['total_votes']}")
    print(f"Market Stance: {narrative_result['market_stance']}")
    print(f"Conviction: {narrative_result['conviction']:.3f} ({narrative_result['conviction_level']})")
    print(f"Recommended Exposure: {narrative_result['exposure_recommendation']['recommended_exposure']:.1f}%")
    
    print(f"\n📖 MARKET NARRATIVE")
    print("-" * 30)
    print(narrative_result['narrative_text'])
    
    print(f"\n🎯 KEY THEMES")
    print("-" * 30)
    for theme in narrative_result['key_themes']:
        direction_symbol = "🟢" if theme['direction'] == 'bullish' else "🔴" if theme['direction'] == 'bearish' else "🟡"
        print(f"{direction_symbol} {theme['juror'].title()}: {theme['theme']} (conf: {theme['confidence']:.2f})")
    
    print(f"\n🤝 AGREEMENT ANALYSIS")
    print("-" * 30)
    agreement = narrative_result['agreement_analysis']
    print(f"Consensus Strength: {agreement['consensus_strength']:.1%}")
    print(f"Vote Distribution: Bullish={agreement['vote_distribution'][1]}, "
          f"Neutral={agreement['vote_distribution'][0]}, "
          f"Bearish={agreement['vote_distribution'][-1]}")
    
    if agreement['unanimous']:
        print("🎯 UNANIMOUS DECISION!")
    elif agreement['split_decision']:
        print("⚖️ SPLIT DECISION - High uncertainty")
    
    print("\n✅ Narrative engine operational - 5 jurors voting system active")

if __name__ == "__main__":
    main()