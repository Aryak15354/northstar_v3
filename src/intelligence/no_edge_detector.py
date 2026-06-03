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
import argparse
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
            'no_edge_log': 'data/intelligence/no_edge_transitions.json',
            'no_edge_status_json': 'data/intelligence/no_edge_detector.json',
        }
        
        # Configuration
        self.config = {
            'regime_similarity_threshold': 0.7,    # Below this = NO_EDGE
            'tailwind_conflict_threshold': 1.5,    # Std dev of tailwinds
            'confidence_threshold': 0.6,           # Minimum confidence
            'no_edge_exposure_cap': 0.20,          # 20% max exposure in NO_EDGE
            'normal_exposure_cap': 0.80,           # 80% max exposure normally
            'tailwind_good_threshold': 1.03,       # Neutral canonical tailwind = 1.0
            'min_good_tailwind_ratio': 0.25,       # Need at least 25% of live strategies above neutral
            'min_strategies_for_conflict': 3,      # Need 3+ strategies to detect conflict
            'lookback_periods': 5,                 # Look at last 5 periods for stability
            'auto_recovery_enabled': True,
            'auto_recovery_tailwind_ratio': 0.30,
            'auto_recovery_confidence_threshold': 0.60,
            'auto_recovery_risk_on_floor': 0.35,
            'auto_recovery_allowed_exposure_floor': 0.30,
        }
        
        # State tracking
        self.current_state = 'NORMAL'
        self.state_history = []
        self.no_edge_reasons = []

    @staticmethod
    def _normalize_tailwind_frame(tailwinds: pd.DataFrame) -> pd.DataFrame:
        if tailwinds is None or tailwinds.empty:
            return pd.DataFrame()

        df = tailwinds.copy()
        if 'strategy' not in df.columns and 'strategy_id' in df.columns:
            df['strategy'] = df['strategy_id'].astype(str)
        if 'combined_score' not in df.columns and 'tailwind_score' in df.columns:
            df['combined_score'] = pd.to_numeric(df['tailwind_score'], errors='coerce')
        if 'regime_tailwind' not in df.columns and 'tailwind_score' in df.columns:
            df['regime_tailwind'] = pd.to_numeric(df['tailwind_score'], errors='coerce')
        if 'date' not in df.columns and 'as_of_date' in df.columns:
            df['date'] = pd.to_datetime(df['as_of_date'], errors='coerce')
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        if 'combined_score' in df.columns:
            df['combined_score'] = df['combined_score'].apply(NoEdgeDetector._tailwind_multiplier)
        if 'regime_tailwind' in df.columns:
            df['regime_tailwind'] = df['regime_tailwind'].apply(NoEdgeDetector._tailwind_multiplier)
        return df

    @staticmethod
    def _tailwind_multiplier(raw_score):
        """Normalize heterogeneous tailwind scores to a neutral-around-1 multiplier."""
        parsed = pd.to_numeric(raw_score, errors='coerce')
        if pd.isna(parsed):
            return np.nan
        score = float(parsed)
        if -0.50 <= score <= 0.50:
            score = 1.0 + score
        return float(np.clip(score, 0.70, 1.50))

    @staticmethod
    def _normalize_regime_label(label: str) -> str:
        s = str(label or "").replace("_", " ").replace("-", " ").strip().lower()
        return " ".join(s.split()) if s else "unknown"

    def _current_regime_label(self) -> str:
        """Best-effort current regime resolution for filtering tailwind rows."""
        try:
            if os.path.exists(self.paths['market_state']):
                market_state = pd.read_parquet(self.paths['market_state'])
                if not market_state.empty:
                    latest = market_state.iloc[-1]
                    for key in ('regime', 'regime_name', 'macro_regime'):
                        val = latest.get(key)
                        if val not in (None, '', 'None'):
                            return self._normalize_regime_label(val)
        except Exception:
            pass

        try:
            if os.path.exists(self.paths['regime_memory']):
                regime_memory = pd.read_parquet(self.paths['regime_memory'])
                if not regime_memory.empty and 'Regime' in regime_memory.columns:
                    return self._normalize_regime_label(regime_memory.iloc[-1].get('Regime'))
        except Exception:
            pass

        return "unknown"

    def _select_live_tailwind_rows(self, tailwinds: pd.DataFrame) -> pd.DataFrame:
        """
        Reduce tailwinds to one live row per strategy.

        Canonical tailwind files may contain one row per strategy/regime pair. The
        detector should judge today's live regime, not every regime scenario at once.
        """
        df = self._normalize_tailwind_frame(tailwinds)
        if df.empty:
            return df

        current_regime = self._current_regime_label()
        if 'regime' in df.columns and current_regime != "unknown":
            regime_mask = (
                df['regime']
                .astype(str)
                .map(self._normalize_regime_label)
                .eq(current_regime)
            )
            if bool(regime_mask.any()):
                df = df.loc[regime_mask].copy()

        if 'strategy' in df.columns:
            if 'date' in df.columns:
                df = df.sort_values('date').groupby('strategy', dropna=False).tail(1)
            else:
                df = df.groupby('strategy', dropna=False).tail(1)

        return df.reset_index(drop=True)

    def _regime_consistency_score(self):
        try:
            if not os.path.exists(self.paths['regime_memory']):
                return None
            regime_memory = pd.read_parquet(self.paths['regime_memory'])
            if regime_memory.empty or 'Regime' not in regime_memory.columns:
                return None
            recent_regimes = regime_memory['Regime'].tail(self.config['lookback_periods'])
            if len(recent_regimes) < 2:
                return None
            most_common_regime = (
                recent_regimes.mode().iloc[0]
                if not recent_regimes.mode().empty
                else recent_regimes.iloc[-1]
            )
            return float((recent_regimes == most_common_regime).mean())
        except Exception:
            return None

    def _tailwind_good_ratio(self):
        try:
            if not os.path.exists(self.paths['strategy_tailwinds']):
                return None
            tailwinds = self._select_live_tailwind_rows(pd.read_parquet(self.paths['strategy_tailwinds']))
            if tailwinds.empty or 'combined_score' not in tailwinds.columns:
                return None
            live_scores = pd.to_numeric(tailwinds['combined_score'], errors='coerce').dropna()
            if len(live_scores) < 2:
                return None
            good_threshold = float(self.config['tailwind_good_threshold'])
            return float((live_scores >= good_threshold).mean())
        except Exception:
            return None

    def _market_recovery_snapshot(self):
        try:
            if not os.path.exists(self.paths['market_state']):
                return {}
            market_state = pd.read_parquet(self.paths['market_state'])
            if market_state.empty:
                return {}
            latest = market_state.iloc[-1]
            risk_on = pd.to_numeric(
                latest.get('risk_on_probability', latest.get('risk_on')), errors='coerce'
            )
            allowed_exposure = pd.to_numeric(latest.get('allowed_exposure'), errors='coerce')
            if pd.notna(allowed_exposure) and float(allowed_exposure) > 1.0:
                allowed_exposure = float(allowed_exposure) / 100.0
            return {
                'risk_on_probability': float(risk_on) if pd.notna(risk_on) else None,
                'allowed_exposure': float(allowed_exposure) if pd.notna(allowed_exposure) else None,
                'regime': latest.get('regime'),
            }
        except Exception:
            return {}

    def _maybe_auto_recover(self, latest_state: dict):
        """Auto-reset NO_EDGE once live evidence shows the system has regained edge."""
        if not bool(self.config.get('auto_recovery_enabled', True)):
            return None
        if str(latest_state.get('state', 'NORMAL')).upper() != 'NO_EDGE':
            return None

        tailwind_ratio = self._tailwind_good_ratio()
        regime_consistency = self._regime_consistency_score()
        market_snapshot = self._market_recovery_snapshot()
        risk_on_prob = market_snapshot.get('risk_on_probability')
        allowed_exposure = market_snapshot.get('allowed_exposure')

        if tailwind_ratio is None:
            return None
        if tailwind_ratio < float(self.config['auto_recovery_tailwind_ratio']):
            return None
        if regime_consistency is not None and regime_consistency < float(
            self.config['auto_recovery_confidence_threshold']
        ):
            return None

        risk_signal_ok = False
        if risk_on_prob is not None and risk_on_prob >= float(self.config['auto_recovery_risk_on_floor']):
            risk_signal_ok = True
        if allowed_exposure is not None and allowed_exposure >= float(
            self.config['auto_recovery_allowed_exposure_floor']
        ):
            risk_signal_ok = True
        if not risk_signal_ok:
            return None

        reason_bits = [f"auto_recovered_good_tailwinds:{tailwind_ratio:.3f}"]
        if regime_consistency is not None:
            reason_bits.append(f"regime_consistency:{regime_consistency:.3f}")
        if risk_on_prob is not None:
            reason_bits.append(f"risk_on:{risk_on_prob:.3f}")
        if allowed_exposure is not None:
            reason_bits.append(f"allowed_exposure:{allowed_exposure:.3f}")
        reason = ", ".join(reason_bits)

        self.log_state_transition('NO_EDGE', 'NORMAL', [reason])
        self.save_no_edge_state(
            'NORMAL',
            self.config['normal_exposure_cap'],
            [reason],
            True,
        )
        return {
            'state': 'NORMAL',
            'exposure_cap': self.config['normal_exposure_cap'],
            'reasons': [reason],
            'date': datetime.now().date(),
        }
    
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
            
            tailwinds = self._select_live_tailwind_rows(pd.read_parquet(self.paths['strategy_tailwinds']))
            
            if tailwinds.empty or len(tailwinds) < self.config['min_strategies_for_conflict']:
                print("   ⚠️ Insufficient tailwind data")
                return True, "Insufficient tailwind data"
            
            # Analyze tailwind distribution
            combined_scores = pd.to_numeric(tailwinds['combined_score'], errors='coerce').dropna()
            regime_tailwinds = pd.to_numeric(tailwinds['regime_tailwind'], errors='coerce').dropna()
            
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
                tailwinds = self._select_live_tailwind_rows(pd.read_parquet(self.paths['strategy_tailwinds']))
                
                if not tailwinds.empty:
                    live_scores = pd.to_numeric(tailwinds['combined_score'], errors='coerce').dropna()
                    if len(live_scores) < 2:
                        print("   ⚠️ Insufficient live tailwind rows for confidence check")
                        return False, None

                    # Canonical tailwind scores are neutral around 1.0.
                    good_threshold = float(self.config['tailwind_good_threshold'])
                    good_tailwinds = (live_scores >= good_threshold).sum()
                    total_strategies = len(tailwinds)
                    
                    good_ratio = good_tailwinds / total_strategies if total_strategies > 0 else 0
                    
                    print(
                        f"   📊 Good tailwind ratio: {good_ratio:.3f} "
                        f"({good_tailwinds}/{total_strategies}, threshold={good_threshold:.2f})"
                    )
                    
                    if good_ratio < float(self.config['min_good_tailwind_ratio']):
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
        self._write_status_json(state, exposure_cap, reasons, state_changed)
        
        print(f"   💾 Saved NO_EDGE state to {self.paths['no_edge_state']}")

    def _write_status_json(self, state, exposure_cap, reasons, state_changed):
        """Write a JSON compatibility surface for operators and runtime checks."""
        payload = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().date().isoformat(),
            'state': str(state),
            'no_edge_active': str(state).upper() == 'NO_EDGE',
            'exposure_cap': float(exposure_cap),
            'reasons': list(reasons or []),
            'state_changed': bool(state_changed),
        }
        os.makedirs(os.path.dirname(self.paths['no_edge_status_json']), exist_ok=True)
        with open(self.paths['no_edge_status_json'], 'w') as f:
            json.dump(payload, f, indent=2, default=str)

    def force_reset(self, reason: str) -> dict:
        """
        Force-reset NO_EDGE state after a material system repair or stale-state event.
        """
        previous = self.get_current_state()
        state_changed = previous.get('state') == 'NO_EDGE'
        if state_changed:
            self.log_state_transition('NO_EDGE', 'NORMAL', [reason])
        self.save_no_edge_state(
            'NORMAL',
            self.config['normal_exposure_cap'],
            [reason],
            state_changed,
        )
        return self.get_current_state()
    
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
                        current_state = {
                            'state': state_val,
                            'exposure_cap': float(latest.get('exposure_cap', self.config['normal_exposure_cap'])),
                            'reasons': reasons,
                            'date': latest.get('date')
                        }
                        auto_recovered = self._maybe_auto_recover(current_state)
                        return auto_recovered or current_state

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
                    current_state = {
                        'state': state_val,
                        'exposure_cap': exposure_cap,
                        'reasons': reasons,
                        'date': latest.get('date')
                    }
                    auto_recovered = self._maybe_auto_recover(current_state)
                    return auto_recovered or current_state
            
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
    parser = argparse.ArgumentParser(description="Detect NO_EDGE state")
    parser.add_argument("--recalculate", action="store_true", help="Accepted for compatibility; detection is always fresh.")
    parser.add_argument("--date", default=None, help="Optional as-of date for operator traceability.")
    args = parser.parse_args()

    detector = NoEdgeDetector()
    result = detector.detect_no_edge_state()
    if args.date:
        result['requested_date'] = args.date
    
    print(f"\n🎯 NO_EDGE Detection Complete!")
    print(f"   Current State: {result['state']}")
    print(f"   Exposure Cap: {result['exposure_cap']:.0%}")
    if result['reasons']:
        print(f"   Reasons: {len(result['reasons'])}")
    
    return result

if __name__ == "__main__":
    main()
