#!/usr/bin/env python3
"""
🧠 V3 SENTIMENT LOADER
Loads NS-USO sentiment artifacts for Market Brain integration

This module:
✅ Loads V3-specific sentiment artifacts
✅ Provides safe integration with Market Brain
✅ Preserves all validation guarantees
✅ Never creates signals, only modulates confidence
"""

import json
import warnings
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

class V3SentimentLoader:
    """Loads and processes V3 sentiment artifacts for Market Brain"""
    
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/sentiment/v3")
        self.last_load_time = None
        self.cached_sentiment = None
        
    def load_v3_sentiment(self, run_date=None):
        """Load V3 sentiment artifacts"""
        
        try:
            # Check if artifacts exist
            market_file = self.data_dir / "market_sentiment_india.parquet"
            sector_file = self.data_dir / "sector_narratives.parquet"
            policy_file = self.data_dir / "policy_context.json"
            
            if not all([market_file.exists(), sector_file.exists(), policy_file.exists()]):
                return None
            
            # Load market sentiment
            market_df = pd.read_parquet(market_file)
            if market_df.empty:
                return None
            
            market_sentiment = market_df.iloc[-1].to_dict()  # Latest record
            
            # Load sector narratives
            sector_df = pd.read_parquet(sector_file)
            sector_narratives = sector_df.to_dict('records') if not sector_df.empty else []
            
            # Load policy context
            with open(policy_file, 'r') as f:
                policy_context = json.load(f)
            
            # Combine into V3 sentiment object
            v3_sentiment = V3SentimentData(
                market_sentiment=market_sentiment,
                sector_narratives=sector_narratives,
                policy_context=policy_context
            )
            
            self.cached_sentiment = v3_sentiment
            self.last_load_time = datetime.now()
            
            return v3_sentiment
            
        except Exception as e:
            print(f"⚠️ Error loading V3 sentiment: {e}")
            return None
    
    def _get_neutral_sentiment(self):
        """Deprecated: neutral sentiment is not injected when no data is available."""
        return None
    
    def is_sentiment_fresh(self, max_age_hours=24):
        """Check if cached sentiment is fresh"""
        
        if not self.last_load_time or not self.cached_sentiment:
            return False
        
        age = datetime.now() - self.last_load_time
        return age.total_seconds() < (max_age_hours * 3600)
    
    def get_cached_sentiment(self):
        """Get cached sentiment if fresh, otherwise reload"""
        
        if self.is_sentiment_fresh():
            return self.cached_sentiment
        else:
            return self.load_v3_sentiment()

class V3SentimentData:
    """Container for V3 sentiment data with safe access methods"""
    
    def __init__(self, market_sentiment, sector_narratives, policy_context):
        self.market_sentiment = market_sentiment
        self.sector_narratives = sector_narratives
        self.policy_context = policy_context
        
        # Derived properties for Market Brain integration
        self._compute_derived_metrics()
    
    def _compute_derived_metrics(self):
        """Compute derived metrics for Market Brain"""
        
        # Conviction multiplier (0.5 to 1.5 range for safety)
        raw_conviction = self.market_sentiment.get('conviction', 0.5)
        self.conviction = 0.5 + (raw_conviction * 1.0)  # Scale to 0.5-1.5
        
        # Narrative cohesion (affects belief inertia)
        self.narrative_cohesion = self.market_sentiment.get('narrative_cohesion', 0.5)
        
        # Uncertainty (adds to regime uncertainty)
        raw_uncertainty = self.market_sentiment.get('uncertainty', 0.5)
        self.uncertainty = raw_uncertainty * 0.3  # Cap at 30% additional uncertainty
        
        # Policy weight (affects confidence ceiling)
        self.policy_weight = self.market_sentiment.get('policy_weight', 0.0)
        
        # Sentiment polarity (for display only, not trading)
        self.polarity = self.market_sentiment.get('polarity', 0.0)
        
        # Dominant theme for Brain Window
        self.dominant_theme = self.market_sentiment.get('dominant_theme', 'neutral')
    
    @property
    def belief_strength_multiplier(self):
        """Multiplier for belief strength (conservative range)"""
        return np.clip(self.conviction, 0.7, 1.3)
    
    @property
    def belief_inertia_multiplier(self):
        """Multiplier for belief inertia based on narrative cohesion"""
        return np.clip(self.narrative_cohesion, 0.8, 1.2)
    
    @property
    def uncertainty_addition(self):
        """Additional uncertainty to add to regime uncertainty"""
        return np.clip(self.uncertainty, 0.0, 0.2)
    
    @property
    def confidence_ceiling_adjustment(self):
        """Adjustment to confidence ceiling based on policy weight"""
        # High policy weight slightly reduces confidence ceiling
        return -0.1 * self.policy_weight if self.policy_weight > 0.5 else 0.0
    
    def get_sector_sentiment(self, sector):
        """Get sentiment for specific sector"""
        
        for sector_data in self.sector_narratives:
            if sector_data.get('sector', '').upper() == sector.upper():
                return sector_data.get('sentiment_score', 0.0)
        
        return 0.0  # Neutral if sector not found
    
    def get_policy_stance_numeric(self):
        """Convert policy stance to numeric value"""
        
        stance_map = {
            'hawkish': 0.3,
            'neutral_hawkish': 0.1,
            'neutral': 0.0,
            'neutral_accommodative': -0.1,
            'accommodative': -0.3
        }
        
        stance = self.policy_context.get('rbi_stance', 'neutral')
        return stance_map.get(stance, 0.0)
    
    def to_brain_window_dict(self):
        """Convert to dictionary for Brain Window display"""
        
        return {
            'india_semantic_context': {
                'rbi_stance': self.policy_context.get('rbi_stance', 'neutral'),
                'dominant_theme': self.dominant_theme,
                'uncertainty_gauge': f"{self.uncertainty:.1%}"
            },
            'regime_confidence': {
                'price_confidence': "Market-driven",  # Placeholder
                'sentiment_adjusted': f"{self.conviction:.2f}x",
                'divergence_indicator': abs(self.polarity) > 0.2
            },
            'narrative_health': {
                'cohesion': f"{self.narrative_cohesion:.1%}",
                'contradiction_alerts': len(self.policy_context.get('regulatory_stress_flags', []))
            }
        }

# Convenience function for Market Brain integration
def load_v3_sentiment_for_market_brain(data_dir=None):
    """Load V3 sentiment for Market Brain integration"""
    
    loader = V3SentimentLoader(data_dir=data_dir)
    return loader.load_v3_sentiment()

# Test function
def test_v3_sentiment_loader():
    """Test the V3 sentiment loader"""
    
    print("🧪 Testing V3 Sentiment Loader...")
    
    loader = V3SentimentLoader()
    sentiment = loader.load_v3_sentiment()
    
    print(f"   Conviction multiplier: {sentiment.belief_strength_multiplier:.2f}")
    print(f"   Inertia multiplier: {sentiment.belief_inertia_multiplier:.2f}")
    print(f"   Uncertainty addition: {sentiment.uncertainty_addition:.3f}")
    print(f"   Dominant theme: {sentiment.dominant_theme}")
    
    brain_window_data = sentiment.to_brain_window_dict()
    print(f"   Brain Window data: {json.dumps(brain_window_data, indent=2)}")
    
    return True

if __name__ == "__main__":
    test_v3_sentiment_loader()
