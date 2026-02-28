#!/usr/bin/env python3
"""
🚨 NO_EDGE STATE DETECTOR - NORTHSTAR V3 PHASE 3
Detects when the system has no edge and should reduce exposure

This creates a NO_EDGE detection system that:
1. Detects low regime similarity (<0.7)
2. Detects conflicting tailwinds across strategies
3. Caps exposure at 20% in NO_EDGE state
4. Logs NO_EDGE transitions for analysis

The NO_EDGE state is a critical risk management feature that prevents
the system from taking large positions when market conditions are
unclear or when the system's models are providing conflicting signals.

Integration with V3:
- Uses RegimeMemorySystem for regime similarity
- Uses SimpleTailwindEngine for tailwind analysis
- Integrates with Capital_Allocator for exposure capping
- Logs state transitions for audit trail

Output: data/intelligence/no_edge_state.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class NoEdgeDetector:
    """
    NO_EDGE State Detection System
    
    Detects conditions where the system should reduce exposure:
    - Low regime similarity (current market doesn't match historical patterns)
    - Conflicting tailwinds (strategies disagree on market direction)
    - Low confidence in regime detection
    - High uncertainty in strategy performance
    """
    
    def __init__(self):
        self.name = "NO_EDGE State Detector"
        self.version = "3.0"
        
        # Data paths
        self.paths = {
            'regime_memory': 'data/intelligence/regime_memory.parquet',
            'strategy_tailwinds': 'data/intelligence/strategy_tailwinds.parquet',
            'market_state': 'data/processed/market_state.parquet',
            'no_edge_state': 'data/intelligence/no_edge_state.parquet',
            'no_edge_log': 'data/intelligence/no_edge_transitions.json'
        }
        
        # Configuration
        self.config = {
            'regime_similarity_threshold': 0.7,    # Below this = NO_EDGE
            'tailwind_conflict_threshold': 1.5,    # Std dev of tailwinds
            'confidence_threshold': 0.6,           # Minimum confidence
            'no_edge_exposure_cap': 0.20,          # 20% max exposure in NO_EDGE
            'normal_exposure_cap': 0.80,           # 80% max exposure normally
            'min_strategies_for_conflict': 3,      # Need 3+ strategies to detect conflict
            'lookback_periods': 5                  # Look at last 5 periods for stability
        }
        
        # State tracking
        self.current_state = 'NORMAL'
        self.state_history = []
        self.no_edge_reasons = []
    
    def detect_regime_similarity_issue(self):
        """Detect if current regime similarity is too low"""
        
        print("🔍 Checking regime similarity...")
        
        try:
            # Load regime memory
            if not os.path.exists(self.paths['regime_memory']):
                print("   ⚠️ No regime memory found")
                return True, "No regime memory available"
            
            regime_memory = pd.read_parquet(self.paths['regime_memory'])
            
            if regime_memory.empty or len(regime_memory) < 2:
                print("   ⚠️ Insufficient regime memory")
                return True, "Insufficient regime memory"
            
            # Get current market state (use latest regime memory as proxy)
            current_regime = regime_memory.iloc[-1]
            
            # Calculate similarity to recent historical regimes
            recent_regimes = regime_memory.iloc[-20:-1]  # Last 20 periods excluding current
            
            if recent_regimes.empty:
                print("   ⚠️ No recent regime history")
                return True, "No recent regime history"
            
            # Use regime features for similarity
            feature_cols = [col for col in regime_memory.columns if col.endswith('_scaled')]
            
            if not feature_cols:
                print("   ⚠️ No regime features for similarity")
                return True, "No regime features available"
            
            # Calculate similarities
            from sklearn.metrics.pairwise import cosine_similarity
            
            current_features = current_regime[feature_cols].values.reshape(1, -1)
            historical_features = recent_regimes[feature_cols].values
            
            similarities = cosine_similarity(current_features, historical_features)[0]
            max_similarity = similarities.max()
            avg_similarity = similarities.mean()
            
            print(f"   📊 Regime similarity - Max: {max_similarity:.3f}, Avg: {avg_similarity:.3f}")
            
            # Check if similarity is too low
            if max_similarity < self.config['regime_similarity_threshold']:
                reason = f"Low regime similarity: {max_similarity:.3f} < {self.config['regime_similarity_threshold']}"
                print(f"   🚨 {reason}")
                return True, reason
            
            print("   ✅ Regime similarity acceptable")
            return False, None
            
        except Exception as e:
            print(f"   ⚠️ Error checking regime similarity: {e}")
            return True, f"Regime similarity check failed: {e}"
    
    def detect_tailwind_conflicts(self):
        """Detect if strategy tailwinds are conflicting"""
        
        print("🌪️ Checking for tailwind conflicts...")
        
        try:
            # Load strategy tailwinds
            if not os.path.exists(self.paths['strategy_tailwinds']):
                print("   ⚠️ No tailwind data found")
                return True, "No tailwind data available"
            
            tailwinds = pd.read_parquet(self.paths['strategy_tailwinds'])
            
            if tailwinds.empty or len(tailwinds) < self.config['min_strategies_for_conflict']:
                print("   ⚠️ Insufficient tailwind data")
                return True, "Insufficient tailwind data"
            
            # Analyze tailwind distribution
            combined_scores = tailwinds['combined_score']
            regime_tailwinds = tailwinds['regime_tailwind']
            
            # Calculate statistics
            score_std = combined_scores.std()
            score_range = combined_scores.max() - combined_scores.min()
            regime_std = regime_tailwinds.std()
            
            print(f"   📊 Tailwind stats - Score std: {score_std:.3f}, Range: {score_range:.3f}, Regime std: {regime_std:.3f}")
            
            # Check for excessive conflict (high standard deviation)
            if score_std > self.config['tailwind_conflict_threshold']:
                reason = f"High tailwind conflict: std {score_std:.3f} > {self.config['tailwind_conflict_threshold']}"
                print(f"   🚨 {reason}")
                return True, reason
            
            # Check for extreme range
            if score_range > 3.0:  # Very wide range of scores
                reason = f"Extreme tailwind range: {score_range:.3f}"
                print(f"   🚨 {reason}")
                return True, reason
            
            print("   ✅ Tailwind conflicts acceptable")
            return False, None
            
        except Exception as e:
            print(f"   ⚠️ Error checking tailwind conflicts: {e}")
            return True, f"Tailwind conflict check failed: {e}"
    
    def detect_low_confidence(self):
        """Detect if overall system confidence is too low"""
        
        print("🎯 Checking system confidence...")
        
        try:
            # Load regime memory for confidence assessment
            if os.path.exists(self.paths['regime_memory']):
                regime_memory = pd.read_parquet(self.paths['regime_memory'])
                
                if not regime_memory.empty:
                    # Check regime stability (how consistent recent regimes are)
                    recent_regimes = regime_memory['Regime'].tail(self.config['lookback_periods'])
                    
                    if len(recent_regimes) > 1:
                        # Calculate regime consistency
                        most_common_regime = recent_regimes.mode().iloc[0] if not recent_regimes.mode().empty else recent_regimes.iloc[-1]
                        consistency = (recent_regimes == most_common_regime).mean()
                        
                        print(f"   📊 Regime consistency: {consistency:.3f}")
                        
                        if consistency < self.config['confidence_threshold']:
                            reason = f"Low regime consistency: {consistency:.3f} < {self.config['confidence_threshold']}"
                            print(f"   🚨 {reason}")
                            return True, reason
            
            # Check tailwind confidence
            if os.path.exists(self.paths['strategy_tailwinds']):
                tailwinds = pd.read_parquet(self.paths['strategy_tailwinds'])
                
                if not tailwinds.empty:
                    # Check if we have reasonable number of strategies with good tailwinds
                    good_tailwinds = (tailwinds['combined_score'] > 1.2).sum()
                    total_strategies = len(tailwinds)
                    
                    good_ratio = good_tailwinds / total_strategies if total_strategies > 0 else 0
                    
                    print(f"   📊 Good tailwind ratio: {good_ratio:.3f} ({good_tailwinds}/{total_strategies})")
                    
                    if good_ratio < 0.3:  # Less than 30% of strategies have good tailwinds
                        reason = f"Low tailwind quality: {good_ratio:.3f} good ratio"
                        print(f"   🚨 {reason}")
                        return True, reason
            
            print("   ✅ System confidence acceptable")
            return False, None
            
        except Exception as e:
            print(f"   ⚠️ Error checking confidence: {e}")
            return True, f"Confidence check failed: {e}"
    
    def detect_no_edge_state(self):
        """Main method to detect NO_EDGE state"""
        
        print("🚨 DETECTING NO_EDGE STATE")
        print("=" * 50)
        
        no_edge_reasons = []
        
        # Check regime similarity
        regime_issue, regime_reason = self.detect_regime_similarity_issue()
        if regime_issue and regime_reason:
            no_edge_reasons.append(regime_reason)
        
        # Check tailwind conflicts
        conflict_issue, conflict_reason = self.detect_tailwind_conflicts()
        if conflict_issue and conflict_reason:
            no_edge_reasons.append(conflict_reason)
        
        # Check system confidence
        confidence_issue, confidence_reason = self.detect_low_confidence()
        if confidence_issue and confidence_reason:
            no_edge_reasons.append(confidence_reason)
        
        # Determine state
        if no_edge_reasons:
            new_state = 'NO_EDGE'
            exposure_cap = self.config['no_edge_exposure_cap']
            print(f"\n🚨 NO_EDGE STATE DETECTED!")
            print(f"   Reasons: {len(no_edge_reasons)}")
            for i, reason in enumerate(no_edge_reasons, 1):
                print(f"     {i}. {reason}")
            print(f"   Exposure cap: {exposure_cap:.0%}")
        else:
            new_state = 'NORMAL'
            exposure_cap = self.config['normal_exposure_cap']
            print(f"\n✅ NORMAL STATE - System has edge")
            print(f"   Exposure cap: {exposure_cap:.0%}")
        
        # Check for state transition
        state_changed = new_state != self.current_state
        
        if state_changed:
            print(f"\n🔄 STATE TRANSITION: {self.current_state} → {new_state}")
            self.log_state_transition(self.current_state, new_state, no_edge_reasons)
        
        # Update state
        self.current_state = new_state
        self.no_edge_reasons = no_edge_reasons
        
        # Save state
        self.save_no_edge_state(new_state, exposure_cap, no_edge_reasons, state_changed)
        
        return {
            'state': new_state,
            'exposure_cap': exposure_cap,
            'reasons': no_edge_reasons,
            'state_changed': state_changed,
            'timestamp': datetime.now().isoformat()
        }
    
    def log_state_transition(self, old_state, new_state, reasons):
        """Log state transitions for audit trail"""
        
        transition = {
            'timestamp': datetime.now().isoformat(),
            'old_state': old_state,
            'new_state': new_state,
            'reasons': reasons,
            'exposure_cap': self.config['no_edge_exposure_cap'] if new_state == 'NO_EDGE' else self.config['normal_exposure_cap']
        }
        
        # Load existing transitions
        transitions = []
        if os.path.exists(self.paths['no_edge_log']):
            try:
                with open(self.paths['no_edge_log'], 'r') as f:
                    transitions = json.load(f)
            except:
                transitions = []
        
        # Add new transition
        transitions.append(transition)
        
        # Keep only last 100 transitions
        transitions = transitions[-100:]
        
        # Save transitions
        os.makedirs(os.path.dirname(self.paths['no_edge_log']), exist_ok=True)
        with open(self.paths['no_edge_log'], 'w') as f:
            json.dump(transitions, f, indent=2, default=str)
        
        print(f"   📝 Logged state transition to {self.paths['no_edge_log']}")
    
    def save_no_edge_state(self, state, exposure_cap, reasons, state_changed):
        """Save current NO_EDGE state"""
        
        # Create state record
        state_record = {
            'date': datetime.now().date(),
            'state': state,
            'exposure_cap': exposure_cap,
            'n_reasons': len(reasons),
            'reasons': '; '.join(reasons) if reasons else '',
            'state_changed': state_changed
        }
        
        # Load existing state history
        if os.path.exists(self.paths['no_edge_state']):
            try:
                state_df = pd.read_parquet(self.paths['no_edge_state'])
                
                # Check if we already have a record for today
                today = datetime.now().date()
                if not state_df.empty and 'date' in state_df.columns:
                    state_df['date'] = pd.to_datetime(state_df['date']).dt.date
                    
                    # Remove today's record if it exists
                    state_df = state_df[state_df['date'] != today]
                
            except:
                state_df = pd.DataFrame()
        else:
            state_df = pd.DataFrame()
        
        # Add new record
        new_record = pd.DataFrame([state_record])
        state_df = pd.concat([state_df, new_record], ignore_index=True)
        
        # Save state history
        os.makedirs(os.path.dirname(self.paths['no_edge_state']), exist_ok=True)
        state_df.to_parquet(self.paths['no_edge_state'], index=False)
        
        print(f"   💾 Saved NO_EDGE state to {self.paths['no_edge_state']}")
    
    def get_current_state(self):
        """Get current NO_EDGE state"""
        
        try:
            if os.path.exists(self.paths['no_edge_state']):
                state_df = pd.read_parquet(self.paths['no_edge_state'])
                
                if not state_df.empty:
                    latest = state_df.iloc[-1]
                    # Canonical schema
                    if 'exposure_cap' in state_df.columns:
                        state_val = str(latest.get('state', 'NORMAL'))
                        reasons_raw = latest.get('reasons', '')
                        reasons = str(reasons_raw).split('; ') if isinstance(reasons_raw, str) and reasons_raw else []
                        date_val = pd.to_datetime(latest.get('date'), errors='coerce')
                        if pd.notna(date_val):
                            age_days = (datetime.now().date() - date_val.date()).days
                            if age_days > 3:
                                return {
                                    'state': 'NORMAL',
                                    'exposure_cap': self.config['normal_exposure_cap'],
                                    'reasons': [f"stale_no_edge_state:{age_days}d"],
                                    'date': datetime.now().date()
                                }
                        return {
                            'state': state_val,
                            'exposure_cap': float(latest.get('exposure_cap', self.config['normal_exposure_cap'])),
                            'reasons': reasons,
                            'date': latest.get('date')
                        }

                    # Legacy schema compatibility:
                    # [date, state, edge_strength, confidence, last_trigger]
                    edge_strength = float(pd.to_numeric(latest.get('edge_strength', np.nan), errors='coerce'))
                    confidence = float(pd.to_numeric(latest.get('confidence', np.nan), errors='coerce'))
                    state_val = str(latest.get('state', 'NORMAL')).upper()
                    if state_val not in {'NORMAL', 'NO_EDGE'}:
                        state_val = 'NO_EDGE' if (
                            (not np.isnan(edge_strength) and edge_strength < 0.45) or
                            (not np.isnan(confidence) and confidence < 0.55)
                        ) else 'NORMAL'
                    exposure_cap = self.config['no_edge_exposure_cap'] if state_val == 'NO_EDGE' else self.config['normal_exposure_cap']
                    reason = latest.get('last_trigger', None)
                    reasons = [str(reason)] if reason not in (None, '', 'None') else []
                    return {
                        'state': state_val,
                        'exposure_cap': exposure_cap,
                        'reasons': reasons,
                        'date': latest.get('date')
                    }
            
            # Default state
            return {
                'state': 'NORMAL',
                'exposure_cap': self.config['normal_exposure_cap'],
                'reasons': [],
                'date': datetime.now().date()
            }
            
        except Exception as e:
            print(f"⚠️ Error getting current state: {e}")
            return {
                'state': 'NORMAL',
                'exposure_cap': self.config['normal_exposure_cap'],
                'reasons': [],
                'date': datetime.now().date()
            }
    
    def get_state_history(self, days=30):
        """Get NO_EDGE state history"""
        
        try:
            if os.path.exists(self.paths['no_edge_state']):
                state_df = pd.read_parquet(self.paths['no_edge_state'])
                
                if not state_df.empty:
                    # Get recent history
                    state_df['date'] = pd.to_datetime(state_df['date'])
                    cutoff_date = datetime.now() - timedelta(days=days)
                    recent_df = state_df[state_df['date'] >= cutoff_date]
                    
                    return recent_df.to_dict('records')
            
            return []
            
        except Exception as e:
            print(f"⚠️ Error getting state history: {e}")
            return []

def main():
    """Detect NO_EDGE state"""
    
    detector = NoEdgeDetector()
    result = detector.detect_no_edge_state()
    
    print(f"\n🎯 NO_EDGE Detection Complete!")
    print(f"   Current State: {result['state']}")
    print(f"   Exposure Cap: {result['exposure_cap']:.0%}")
    if result['reasons']:
        print(f"   Reasons: {len(result['reasons'])}")
    
    return result

if __name__ == "__main__":
    main()
