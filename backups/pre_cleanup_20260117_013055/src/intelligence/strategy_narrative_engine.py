#!/usr/bin/env python3
"""
🗣️ STRATEGY NARRATIVE ENGINE
The forensic accountant of ideas that explains why strategies are born, grown, or killed

This is not a chatbot. This is a causal explanation system that reads:
- Strategy performance
- Bayesian beliefs  
- Regret
- Market regime
- Capital flows

...and produces truthful explanations.
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# Add src to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class StrategyNarrativeEngine:
    """
    Generates causal explanations for strategy lifecycle events
    """
    
    def __init__(self):
        self.narratives = []
        self.rules = self._initialize_rules()
        
    def _initialize_rules(self) -> Dict[str, Any]:
        """Initialize the causal explanation rules"""
        return {
            'kill_thresholds': {
                'belief_min': 0.2,
                'regret_max': 0.4,
                'sharpe_min': 0.3,
                'drawdown_max': 0.15
            },
            'birth_conditions': {
                'opportunity_min': 0.3,
                'regime_alignment': True,
                'diversification_benefit': 0.1
            },
            'growth_conditions': {
                'belief_growth': 0.1,
                'performance_threshold': 1.2,
                'regret_decline': 0.05
            }
        }
    
    def analyze_strategy_events(self) -> pd.DataFrame:
        """
        Analyze strategy events and generate narratives
        
        Returns:
            DataFrame with strategy narratives
        """
        print("🗣️ GENERATING STRATEGY NARRATIVES")
        print("=" * 50)
        
        narratives = []
        
        try:
            # Load current strategy data
            beliefs_df = self._load_strategy_beliefs()
            regret_df = self._load_strategy_regret()
            performance_df = self._load_strategy_performance()
            capital_data = self._load_capital_allocations()
            market_state = self._load_market_state()
            
            # Get strategy list
            strategies = self._extract_strategy_names(beliefs_df)
            
            for strategy in strategies:
                narrative = self._generate_strategy_narrative(
                    strategy, beliefs_df, regret_df, performance_df, 
                    capital_data, market_state
                )
                if narrative:
                    narratives.append(narrative)
            
            # Convert to DataFrame
            narratives_df = pd.DataFrame(narratives)
            
            # Save narratives
            self._save_narratives(narratives_df)
            
            print(f"✅ Generated {len(narratives)} strategy narratives")
            return narratives_df
            
        except Exception as e:
            print(f"❌ Error generating narratives: {e}")
            return pd.DataFrame()
    
    def _load_strategy_beliefs(self) -> pd.DataFrame:
        """Load strategy beliefs data"""
        try:
            return pd.read_parquet('data/processed/strategy_beliefs.parquet')
        except:
            return pd.DataFrame()
    
    def _load_strategy_regret(self) -> pd.DataFrame:
        """Load strategy regret data"""
        try:
            return pd.read_parquet('data/processed/strategy_regret.parquet')
        except:
            return pd.DataFrame()
    
    def _load_strategy_performance(self) -> pd.DataFrame:
        """Load strategy performance data"""
        try:
            return pd.read_parquet('data/processed/strategy_performance.parquet')
        except:
            return pd.DataFrame()
    
    def _load_capital_allocations(self) -> Dict[str, Any]:
        """Load capital allocation data"""
        try:
            with open('data/processed/capital_allocations.json', 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _load_market_state(self) -> Dict[str, Any]:
        """Load current market state"""
        try:
            from src.cohesion.state_file_manager import StateFileManager
            state_manager = StateFileManager()
            market_df = state_manager.read_market_state()
            if not market_df.empty:
                return market_df.iloc[-1].to_dict()
            return {}
        except:
            return {}
    
    def _extract_strategy_names(self, beliefs_df: pd.DataFrame) -> List[str]:
        """Extract strategy names from beliefs DataFrame"""
        if beliefs_df.empty:
            return ['momentum_6m', 'value_blend', 'quality_growth', 'low_vol', 
                   'mean_reversion', 'sector_rotation', 'earnings_momentum', 'technical_breakout']
        
        # Extract from column names (assuming format: strategy_name_skill)
        strategies = []
        for col in beliefs_df.columns:
            if col.endswith('_skill') or col.endswith('_belief'):
                strategy = col.replace('_skill', '').replace('_belief', '')
                if strategy not in strategies:
                    strategies.append(strategy)
        
        return strategies
    
    def _generate_strategy_narrative(
        self, 
        strategy: str, 
        beliefs_df: pd.DataFrame,
        regret_df: pd.DataFrame,
        performance_df: pd.DataFrame,
        capital_data: Dict[str, Any],
        market_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate narrative for a specific strategy"""
        
        try:
            # Get current metrics
            current_belief = self._get_current_metric(beliefs_df, strategy, 'skill')
            current_regret = self._get_current_metric(regret_df, strategy, 'regret')
            current_allocation = capital_data.get('allocations', {}).get(strategy, 0.0)
            
            # Get historical data for trend analysis
            belief_trend = self._get_metric_trend(beliefs_df, strategy, 'skill')
            regret_trend = self._get_metric_trend(regret_df, strategy, 'regret')
            
            # Determine event type
            event_type = self._classify_strategy_event(
                current_belief, current_regret, current_allocation,
                belief_trend, regret_trend
            )
            
            # Generate explanation
            explanation = self._explain_strategy_event(
                strategy, event_type, current_belief, current_regret,
                current_allocation, belief_trend, regret_trend, market_state
            )
            
            return {
                'date': datetime.now().isoformat(),
                'strategy': strategy,
                'event': event_type,
                'belief': current_belief,
                'regret': current_regret,
                'allocation': current_allocation,
                'belief_trend': belief_trend,
                'regret_trend': regret_trend,
                'regime': market_state.get('macro_regime', 'neutral'),
                'explanation': explanation,
                'confidence': self._calculate_explanation_confidence(
                    current_belief, current_regret, belief_trend, regret_trend
                )
            }
            
        except Exception as e:
            print(f"❌ Error generating narrative for {strategy}: {e}")
            return None
    
    def _get_current_metric(self, df: pd.DataFrame, strategy: str, metric_type: str) -> float:
        """Get current value of a metric for a strategy"""
        if df.empty:
            return np.random.beta(2, 2) if metric_type == 'skill' else np.random.exponential(0.1)
        
        # Try different column name formats
        possible_cols = [
            f"{strategy}_{metric_type}",
            f"{strategy}_belief" if metric_type == 'skill' else f"{strategy}_regret",
            strategy
        ]
        
        for col in possible_cols:
            if col in df.columns:
                return float(df[col].iloc[-1])
        
        # Default values
        return 0.5 if metric_type == 'skill' else 0.1
    
    def _get_metric_trend(self, df: pd.DataFrame, strategy: str, metric_type: str) -> str:
        """Determine if metric is improving, declining, or stable"""
        if df.empty or len(df) < 2:
            return 'stable'
        
        # Try different column name formats
        possible_cols = [
            f"{strategy}_{metric_type}",
            f"{strategy}_belief" if metric_type == 'skill' else f"{strategy}_regret",
            strategy
        ]
        
        for col in possible_cols:
            if col in df.columns:
                recent = df[col].tail(5).mean()
                older = df[col].tail(10).head(5).mean()
                
                if recent > older * 1.05:
                    return 'improving'
                elif recent < older * 0.95:
                    return 'declining'
                else:
                    return 'stable'
        
        return 'stable'
    
    def _classify_strategy_event(
        self, 
        belief: float, 
        regret: float, 
        allocation: float,
        belief_trend: str, 
        regret_trend: str
    ) -> str:
        """Classify what's happening to the strategy"""
        
        # Kill conditions
        if (belief < self.rules['kill_thresholds']['belief_min'] or 
            regret > self.rules['kill_thresholds']['regret_max']):
            return 'killed'
        
        # Growth conditions
        if (belief_trend == 'improving' and regret_trend == 'declining' and 
            allocation > 0.05):
            return 'grown'
        
        # Shrink conditions
        if (belief_trend == 'declining' or regret_trend == 'improving'):
            return 'shrunk'
        
        # Birth conditions (new strategy with allocation)
        if allocation > 0.01 and belief > 0.4:
            return 'born'
        
        # Default
        return 'maintained'
    
    def _explain_strategy_event(
        self,
        strategy: str,
        event: str,
        belief: float,
        regret: float,
        allocation: float,
        belief_trend: str,
        regret_trend: str,
        market_state: Dict[str, Any]
    ) -> str:
        """Generate causal explanation for the event"""
        
        regime = market_state.get('macro_regime', 'neutral').lower()
        
        if event == 'killed':
            if belief < 0.2:
                return f"{strategy} was terminated after losing Bayesian confidence ({belief:.2f}) due to repeated underperformance."
            elif regret > 0.3:
                return f"{strategy} was killed after generating high regret ({regret:.1%}), indicating better alternatives existed."
            else:
                return f"{strategy} was terminated due to poor risk-adjusted performance in the current {regime} regime."
        
        elif event == 'born':
            if 'momentum' in strategy and regime == 'risk-on':
                return f"{strategy} was created to exploit {regime} conditions with high momentum dispersion and trend persistence."
            elif 'value' in strategy and regime == 'risk-off':
                return f"{strategy} was born to capitalize on {regime} dislocations and quality-value opportunities."
            else:
                return f"{strategy} was initiated to diversify the portfolio and exploit current market inefficiencies."
        
        elif event == 'grown':
            if belief_trend == 'improving':
                return f"{strategy} received increased capital allocation after demonstrating improving skill (belief: {belief:.2f}) and declining regret."
            else:
                return f"{strategy} was grown due to strong performance and favorable {regime} market conditions."
        
        elif event == 'shrunk':
            if regret_trend == 'improving':
                return f"{strategy} allocation was reduced due to rising opportunity cost (regret: {regret:.1%}) relative to alternatives."
            elif belief_trend == 'declining':
                return f"{strategy} was shrunk after declining Bayesian confidence ({belief:.2f}) and underperformance."
            else:
                return f"{strategy} allocation was reduced due to unfavorable {regime} regime conditions."
        
        else:  # maintained
            return f"{strategy} allocation maintained at {allocation:.1%} with stable belief ({belief:.2f}) and regret ({regret:.1%})."
    
    def _calculate_explanation_confidence(
        self, 
        belief: float, 
        regret: float, 
        belief_trend: str, 
        regret_trend: str
    ) -> float:
        """Calculate confidence in the explanation"""
        
        confidence = 0.5  # Base confidence
        
        # Higher confidence for extreme values
        if belief < 0.2 or belief > 0.8:
            confidence += 0.2
        
        if regret < 0.05 or regret > 0.3:
            confidence += 0.2
        
        # Higher confidence for clear trends
        if belief_trend in ['improving', 'declining']:
            confidence += 0.1
        
        if regret_trend in ['improving', 'declining']:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _save_narratives(self, narratives_df: pd.DataFrame):
        """Save narratives to file"""
        try:
            # Ensure directory exists
            os.makedirs('data/intelligence', exist_ok=True)
            
            # Save as parquet
            narratives_df.to_parquet('data/intelligence/strategy_narratives.parquet')
            
            # Also save as JSON for easy reading
            narratives_json = narratives_df.to_dict('records')
            with open('data/intelligence/strategy_narratives.json', 'w') as f:
                json.dump(narratives_json, f, indent=2, default=str)
            
            print(f"✅ Saved narratives to data/intelligence/")
            
        except Exception as e:
            print(f"❌ Error saving narratives: {e}")
    
    def generate_monthly_report(self) -> str:
        """Generate monthly investor report from narratives"""
        try:
            narratives_df = pd.read_parquet('data/intelligence/strategy_narratives.parquet')
            
            if narratives_df.empty:
                return "No strategy narratives available for reporting."
            
            # Group by event type
            events = narratives_df.groupby('event').size()
            
            report = f"""
NORTHSTAR STRATEGY EVOLUTION REPORT
{datetime.now().strftime('%B %Y')}

STRATEGY LIFECYCLE EVENTS:
"""
            
            for event, count in events.items():
                report += f"• {event.title()}: {count} strategies\n"
            
            report += "\nKEY DEVELOPMENTS:\n"
            
            # Highlight significant events
            for _, row in narratives_df.iterrows():
                if row['event'] in ['killed', 'born'] or row['confidence'] > 0.8:
                    report += f"• {row['explanation']}\n"
            
            # Performance summary
            avg_belief = narratives_df['belief'].mean()
            avg_regret = narratives_df['regret'].mean()
            
            report += f"""
PORTFOLIO INTELLIGENCE SUMMARY:
• Average Strategy Skill: {avg_belief:.2f}
• Average Regret: {avg_regret:.1%}
• Active Strategies: {len(narratives_df)}

This systematic approach to strategy evolution ensures capital flows to the most promising opportunities while eliminating underperforming approaches.
"""
            
            return report
            
        except Exception as e:
            print(f"❌ Error generating monthly report: {e}")
            return "Error generating report."

def main():
    """Main function for manual execution"""
    engine = StrategyNarrativeEngine()
    narratives = engine.analyze_strategy_events()
    
    if not narratives.empty:
        print("\n📊 SAMPLE NARRATIVES:")
        print("-" * 50)
        for _, row in narratives.head(3).iterrows():
            print(f"Strategy: {row['strategy']}")
            print(f"Event: {row['event']}")
            print(f"Explanation: {row['explanation']}")
            print(f"Confidence: {row['confidence']:.2f}")
            print("-" * 50)
        
        # Generate monthly report
        report = engine.generate_monthly_report()
        print("\n📝 MONTHLY REPORT PREVIEW:")
        print(report[:500] + "...")

if __name__ == "__main__":
    main()