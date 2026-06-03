#!/usr/bin/env python3
"""
📊 UNIFIED STATE MANAGER - NORTHSTAR V3
Single Source of Truth for All System State

This replaces 3 separate state systems with one unified state model that
serves as the single source of truth for all Northstar V3 components.

State Components:
1. Market State (regime, risk-on probability, allowed exposure)
2. Intelligence State (beliefs, confidence, conviction)
3. Portfolio State (holdings, weights, performance)
4. Risk State (system stress, survival mode, emergency status)

Integration Points:
- Market State Spine → Market State
- Intelligence Stack + Market Brain → Intelligence State
- Portfolio Governor → Portfolio State
- Risk Systems → Risk State

Usage:
from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

    from src.state.unified_state_manager import UnifiedStateManager
    
    state_manager = UnifiedStateManager()
    state_manager.update_all_state()
    unified_state = state_manager.get_unified_state()
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.state_file_manager import StateFileManager
from src.sentiment.context_loader import load_sentiment_context


def _coerce_float(value, default=0.0) -> float:
    x = pd.to_numeric(value, errors='coerce')
    return float(x) if pd.notna(x) else float(default)


class UnifiedStateManager:
    """
    Unified State Manager - Single Source of Truth (READ-ONLY)
    
    This manager reads from canonical state files managed by StateFileManager.
    It NEVER writes state - it only aggregates and presents state from
    canonical sources.
    
    Canonical Sources:
    - Market state: data/processed/market_state.parquet (via StateFileManager)
    - Portfolio weights: data/processed/portfolio_weights.parquet (via StateFileManager)
    - Risk state: data/processed/risk_state.parquet (via StateFileManager)
    - Portfolio analytics: data/processed/portfolio_analytics.json (via StateFileManager)
    
    This ensures single source of truth - all writes go through StateFileManager,
    all reads go through UnifiedStateManager.
    """
    
    def __init__(self):
        self.name = "Unified State Manager (Read-Only)"
        self.version = "2.0"
        
        # Initialize StateFileManager for reading canonical files
        self.state_manager = StateFileManager()
        
        # State components (read-only views)
        self.market_state = {}
        self.intelligence_state = {}
        self.portfolio_state = {}
        self.risk_state = {}
        
        # State history
        self.state_history = []
        
        # Output file paths (for aggregated views only)
        self.state_file = 'data/processed/unified_state.json'
        self.state_parquet = 'data/processed/unified_state.parquet'
        self.state_history_file = 'data/processed/unified_state_history.parquet'
        
        # Source file paths
        self.source_paths = {
            'market_state_spine': 'data/processed/market_state.parquet',
            'intelligent_market_state': 'data/processed/intelligent_market_state.parquet',
            'market_brain_state': 'data/processed/market_brain_state.json',
            'pulse_state': 'data/processed/pulse_state.json',
            'regime_intelligence_feed': 'data/processed/regime_intelligence_feed.json',
            'survival_state': 'data/processed/system_stress.json',
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'portfolio_analytics': 'data/processed/portfolio_analytics.json',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'strategy_beliefs': 'data/processed/strategy_beliefs.json',
            'intelligence_state': 'data/intelligence/intelligence_state.json',
            'emergency_brake': 'data/processed/emergency_brake_state.json',
            'options_dashboard_state': 'data/options/live/options_dashboard_state.json',
            'sentiment_summary': 'data/sentiment/v3/v3_sentiment_summary.json',
            'sentiment_market': 'data/sentiment/v3/market_sentiment_india.parquet',
        }
        
        # Ensure directories exist
        for path in [self.state_file, self.state_parquet, self.state_history_file]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
    
    def update_market_state(self):
        """Update market state by reading from canonical source (READ-ONLY)"""
        
        try:
            market_state = {}
            
            # Load Market State from canonical source via StateFileManager
            try:
                spine_df = self.state_manager.read_market_state()
                if not spine_df.empty:
                    latest = spine_df.iloc[-1]

                    regime = latest.get('regime', latest.get('macro_regime', 'unknown'))
                    risk_on = latest.get('risk_on', latest.get('risk_on_probability', 0.5))
                    stress_score = latest.get('stress_score', latest.get('stress_level', 0.0))
                    date_value = latest.get('date', latest.get('timestamp', datetime.now()))
                    if hasattr(date_value, 'isoformat'):
                        last_updated = date_value.isoformat()
                    else:
                        last_updated = str(date_value)

                    market_state.update({
                        'regime': regime,
                        'risk_on': risk_on,
                        'allowed_exposure': latest.get('allowed_exposure', 0.35),
                        'stress_score': stress_score,
                        'last_updated': last_updated,
                        # Enhanced market-state fields for dashboard/intelligence panels.
                        'macro_score': latest.get('macro_score', 0.0),
                        'macro_regime': latest.get('macro_regime', regime),
                        'macro_momentum': latest.get('macro_momentum', 0.0),
                        'health_score': latest.get('health_score', 0.0),
                        'breadth_pct': latest.get('breadth_pct', 50.0),
                        'participation_score': latest.get('participation_score', 0.0),
                        'volatility_regime': latest.get('volatility_regime', 'unknown'),
                        'risk_on_probability': latest.get('risk_on_probability', risk_on),
                        'confidence': latest.get('confidence', latest.get('regime_confidence', 0.0)),
                        'pulse_intensity': latest.get('pulse_intensity', 0.0),
                        'market_phase': latest.get('market_phase', 'neutral'),
                        # Canonical sentiment fields from market_state spine.
                        'sentiment_available': bool(latest.get('sentiment_available', False)),
                        'sentiment_status': latest.get('sentiment_status', 'missing'),
                        'sentiment_polarity': _coerce_float(latest.get('sentiment_polarity', 0.0), 0.0),
                        'sentiment_uncertainty': _coerce_float(latest.get('sentiment_uncertainty', 0.0), 0.0),
                        'sentiment_conviction': _coerce_float(latest.get('sentiment_conviction', 1.0), 1.0),
                        'sentiment_conflict': _coerce_float(latest.get('sentiment_conflict', 0.0), 0.0),
                        'sentiment_bias': _coerce_float(latest.get('sentiment_bias', 0.0), 0.0),
                        'sentiment_event_shock': _coerce_float(latest.get('sentiment_event_shock', 0.0), 0.0),
                        'sentiment_alert_level': str(latest.get('sentiment_alert_level', 'normal') or 'normal'),
                        'sentiment_news_signal': _coerce_float(latest.get('sentiment_news_signal', 0.0), 0.0),
                        'sentiment_dominant_theme': str(latest.get('sentiment_dominant_theme', '') or ''),
                        'sentiment_negative_company_count': _coerce_float(latest.get('sentiment_negative_company_count', 0.0), 0.0),
                        'sentiment_event_impact_count': _coerce_float(latest.get('sentiment_event_impact_count', 0.0), 0.0),
                        'sentiment_summary_age_minutes': _coerce_float(latest.get('sentiment_summary_age_minutes', np.nan), np.nan),
                        'sentiment_market_age_minutes': _coerce_float(latest.get('sentiment_market_age_minutes', np.nan), np.nan),
                    })
            except FileNotFoundError:
                print("   ⚠️ Market state file not found")
            
            # Load additional market intelligence from other sources
            if os.path.exists(self.source_paths['intelligent_market_state']):
                intelligent_df = pd.read_parquet(self.source_paths['intelligent_market_state'])
                if not intelligent_df.empty:
                    latest = intelligent_df.iloc[-1]
                    market_state.update({
                        'intelligent_regime': latest.get('regime', 'unknown'),
                        'regime_confidence': latest.get('regime_confidence', 0.5),
                        'trend_strength': latest.get('trend_strength', 0.0),
                        'momentum_score': latest.get('momentum_score', 0.0)
                    })
            
            # Load Market Brain State
            if os.path.exists(self.source_paths['market_brain_state']):
                with open(self.source_paths['market_brain_state'], 'r') as f:
                    brain_state = json.load(f)
                    
                    intelligence_summary = brain_state.get('intelligence_summary', {})
                    
                    # Market pulse
                    pulse = intelligence_summary.get('market_pulse', {})
                    market_state.update({
                        'pulse_intensity': pulse.get('intensity', 0.0),
                        'market_phase': pulse.get('phase', 'neutral'),
                        'pulse_risk_level': pulse.get('risk_level', 'low'),
                        'pulse_narrative': pulse.get('narrative', 'No narrative available')
                    })
                    
                    # Regime intelligence
                    regime = intelligence_summary.get('regime_intelligence', {})
                    market_state.update({
                        'brain_regime': regime.get('current_regime', 'Unknown'),
                        'regime_similarity': regime.get('similarity', 0.0),
                        'regime_confidence_brain': regime.get('confidence', 'low')
                    })
            
            # Load Pulse State (direct)
            if os.path.exists(self.source_paths['pulse_state']):
                with open(self.source_paths['pulse_state'], 'r') as f:
                    pulse_state = json.load(f)
                    market_state.update({
                        'pulse_timestamp': pulse_state.get('timestamp', ''),
                        'dominant_forces': len(pulse_state.get('dominant_forces', [])),
                        'opportunity_zones': len(pulse_state.get('opportunity_zones', []))
                    })

            # Load AlphaOS regime snapshot from canonical regime feed.
            if os.path.exists(self.source_paths['regime_intelligence_feed']):
                with open(self.source_paths['regime_intelligence_feed'], 'r') as f:
                    regime_feed = json.load(f)
                alpha_os = regime_feed.get('alpha_os', {}) if isinstance(regime_feed, dict) else {}
                if isinstance(alpha_os, dict):
                    market_state.update({
                        'alpha_os_mode': alpha_os.get('mode', ''),
                        'alpha_os_regime_confidence': alpha_os.get('confidence', 0.0),
                        'alpha_os_regime_probabilities': alpha_os.get('probabilities', {}),
                        'alpha_os_regime_stale': bool(alpha_os.get('stale', False)),
                    })

            # Fallback sentiment context for resilience when market_state is stale/missing fields.
            try:
                sentiment = load_sentiment_context(now=datetime.now())
                if isinstance(sentiment, dict):
                    has_canonical_sentiment = bool(market_state.get('sentiment_available', False))
                    if not has_canonical_sentiment:
                        market_state.update({
                            'sentiment_available': bool(sentiment.get('available', False)),
                            'sentiment_status': str(sentiment.get('status', 'missing') or 'missing'),
                            'sentiment_polarity': float(sentiment.get('polarity', 0.0) or 0.0),
                            'sentiment_uncertainty': float(sentiment.get('uncertainty', 0.0) or 0.0),
                            'sentiment_conviction': float(sentiment.get('conviction', 1.0) or 1.0),
                            'sentiment_bias': float(sentiment.get('sentiment_bias', 0.0) or 0.0),
                            'sentiment_event_shock': float(sentiment.get('event_shock_score', 0.0) or 0.0),
                            'sentiment_alert_level': str(sentiment.get('alert_level', 'normal') or 'normal'),
                            'sentiment_news_signal': float(sentiment.get('news_signal_score', 0.0) or 0.0),
                            'sentiment_dominant_theme': str(sentiment.get('dominant_theme', '') or ''),
                            'sentiment_negative_company_count': float(len(sentiment.get('negative_trending_companies', []) or [])),
                            'sentiment_event_impact_count': float(len(sentiment.get('event_company_impacts', []) or [])),
                        })
                    summary_age = sentiment.get('summary_age_minutes')
                    market_age = sentiment.get('market_age_minutes')
                    if summary_age is not None:
                        market_state['sentiment_summary_age_minutes'] = float(summary_age)
                    if market_age is not None:
                        market_state['sentiment_market_age_minutes'] = float(market_age)
                    market_state['sentiment_fresh'] = bool(sentiment.get('fresh', False))
            except Exception:
                pass
            
            self.market_state = market_state
            
        except Exception as e:
            print(f"⚠️ Error updating market state: {e}")
            self.market_state = {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def update_intelligence_state(self):
        """Update intelligence state from all intelligence systems"""
        
        try:
            intelligence_state = {}
            
            # Load Intelligence Stack state
            if os.path.exists(self.source_paths['intelligence_state']):
                with open(self.source_paths['intelligence_state'], 'r') as f:
                    intel_state = json.load(f)
                    
                    # Valuation beliefs
                    valuation = intel_state.get('valuation_beliefs', {})
                    intelligence_state.update({
                        'valuation_conviction': valuation.get('conviction', 0.0),
                        'undervaluation_score': valuation.get('undervaluation_score', 0.0),
                        'valuation_confidence': valuation.get('confidence', 0.0)
                    })
                    
                    # Market beliefs
                    market_beliefs = intel_state.get('market_beliefs', {})
                    intelligence_state.update({
                        'market_conviction': market_beliefs.get('conviction', 0.0),
                        'trend_belief': market_beliefs.get('trend_belief', 0.0),
                        'momentum_belief': market_beliefs.get('momentum_belief', 0.0)
                    })
                    
                    # Narrative
                    narrative = intel_state.get('narrative', {})
                    intelligence_state.update({
                        'market_narrative': narrative.get('summary', 'No narrative available'),
                        'narrative_conviction': narrative.get('conviction', 0.0)
                    })
            
            # Load Strategy Beliefs
            if os.path.exists(self.source_paths['strategy_beliefs']):
                with open(self.source_paths['strategy_beliefs'], 'r') as f:
                    strategy_beliefs = json.load(f)
                    
                    intelligence_state.update({
                        'strategy_conviction': strategy_beliefs.get('overall_conviction', 0.0),
                        'strategy_regret': strategy_beliefs.get('overall_regret', 0.0),
                        'active_strategies': len(strategy_beliefs.get('strategy_beliefs', {}))
                    })
            
            # Load Market Brain Intelligence Summary
            if os.path.exists(self.source_paths['market_brain_state']):
                with open(self.source_paths['market_brain_state'], 'r') as f:
                    brain_state = json.load(f)
                    
                    intelligence_summary = brain_state.get('intelligence_summary', {})
                    
                    # Causal intelligence
                    causal = intelligence_summary.get('causal_intelligence', {})
                    intelligence_state.update({
                        'causal_relationships': causal.get('relationships', 0),
                        'causal_variables': causal.get('variables', 0),
                        'network_density': causal.get('network_density', 0.0)
                    })

            # Load AlphaOS intent diagnostics from canonical capital allocations artifact.
            if os.path.exists(self.source_paths['capital_allocations']):
                with open(self.source_paths['capital_allocations'], 'r') as f:
                    alloc_payload = json.load(f)
                alpha_os = alloc_payload.get('alpha_os', {}) if isinstance(alloc_payload, dict) else {}
                if isinstance(alpha_os, dict):
                    intelligence_state.update({
                        'alpha_os_mode': alpha_os.get('mode', ''),
                        'alpha_os_used_fallback': bool(alpha_os.get('used_fallback', False)),
                        'alpha_os_fallback_level': alpha_os.get('fallback_level', ''),
                        'alpha_os_reason_codes': alpha_os.get('reason_codes', []),
                        'alpha_os_effective_strategy_weights': alpha_os.get('effective_strategy_weights', {}),
                    })

            # Integrate canonical sentiment controls from the market state snapshot.
            sentiment_event_shock = float(self.market_state.get('sentiment_event_shock', 0.0) or 0.0)
            sentiment_alert = str(self.market_state.get('sentiment_alert_level', 'normal') or 'normal').strip().lower()
            sentiment_conviction = float(self.market_state.get('sentiment_conviction', 1.0) or 1.0)
            sentiment_bias = float(self.market_state.get('sentiment_bias', 0.0) or 0.0)
            sentiment_fresh = bool(self.market_state.get('sentiment_fresh', False))
            sentiment_available = bool(self.market_state.get('sentiment_available', False))

            if sentiment_available:
                sentiment_conviction_guard = max(
                    0.45,
                    min(
                        1.05,
                        1.0
                        - 0.65 * sentiment_event_shock
                        - 0.10 * max(0.0, -sentiment_bias)
                        + 0.04 * max(0.0, sentiment_bias),
                    ),
                )
            else:
                sentiment_conviction_guard = 1.0

            intelligence_state.update({
                'sentiment_available': sentiment_available,
                'sentiment_fresh': sentiment_fresh,
                'sentiment_event_shock': sentiment_event_shock,
                'sentiment_alert_level': sentiment_alert,
                'sentiment_conviction': sentiment_conviction,
                'sentiment_bias': sentiment_bias,
                'sentiment_conviction_guard': sentiment_conviction_guard,
            })
            
            # Compute unified conviction
            convictions = [
                intelligence_state.get('valuation_conviction', 0.0),
                intelligence_state.get('market_conviction', 0.0),
                intelligence_state.get('strategy_conviction', 0.0),
                intelligence_state.get('narrative_conviction', 0.0)
            ]
            
            valid_convictions = [c for c in convictions if c > 0]
            if valid_convictions:
                intelligence_state['unified_conviction'] = np.mean(valid_convictions)
            else:
                intelligence_state['unified_conviction'] = 0.0

            # Apply sentiment-aware guard after base conviction synthesis.
            pre_guard_conviction = float(intelligence_state.get('unified_conviction', 0.0) or 0.0)
            intelligence_state['unified_conviction_pre_sentiment'] = pre_guard_conviction
            guard = float(intelligence_state.get('sentiment_conviction_guard', 1.0) or 1.0)
            intelligence_state['unified_conviction'] = max(0.0, min(1.0, pre_guard_conviction * guard))
            
            self.intelligence_state = intelligence_state
            
        except Exception as e:
            print(f"⚠️ Error updating intelligence state: {e}")
            self.intelligence_state = {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def update_portfolio_state(self):
        """Update portfolio state by reading from canonical source (READ-ONLY)"""
        
        try:
            portfolio_state = {}
            
            # Load Portfolio Weights from canonical source via StateFileManager
            try:
                weights_df = self.state_manager.read_portfolio_weights()
                if not weights_df.empty:
                    # Use standardized column names from StateFileManager schema
                    weight_col = 'weight'
                    exposure_col = 'exposure'
                    
                    if weight_col in weights_df.columns:
                        portfolio_state.update({
                            'total_positions': len(weights_df),
                            'total_exposure': weights_df[exposure_col].sum() if exposure_col in weights_df.columns else weights_df[weight_col].sum(),
                            'max_position': weights_df[weight_col].max(),
                            'min_position': weights_df[weight_col].min(),
                            'position_concentration': (weights_df[weight_col] > 0.05).sum(),  # Positions > 5%
                            'long_positions': (weights_df[weight_col] > 0).sum(),
                            'short_positions': (weights_df[weight_col] < 0).sum()
                        })
            except FileNotFoundError:
                print("   ⚠️ Portfolio weights file not found")
            
            # Load Portfolio Analytics from canonical source via StateFileManager
            try:
                analytics = self.state_manager.read_portfolio_analytics()
                
                summary = analytics.get('portfolio_summary', {})
                portfolio_state.update({
                    'expected_return': summary.get('expected_return', 0.0),
                    'expected_volatility': summary.get('expected_volatility', 0.0),
                    'sharpe_ratio': summary.get('sharpe_ratio', 0.0),
                    'max_drawdown': summary.get('max_drawdown', 0.0)
                })
                
                # Compliance
                compliance = analytics.get('compliance_check', {})
                portfolio_state.update({
                    'compliance_status': compliance.get('all_compliant', False),
                    'compliance_violations': len(compliance.get('violations', []))
                })
            except FileNotFoundError:
                print("   ⚠️ Portfolio analytics file not found")
            
            # Load Capital Allocations
            if os.path.exists(self.source_paths['capital_allocations']):
                with open(self.source_paths['capital_allocations'], 'r') as f:
                    allocations = json.load(f)

                    alloc_data = allocations.get('allocations', {})
                    if not isinstance(alloc_data, dict) or not alloc_data:
                        alloc_data = allocations.get('strategy_allocations', {})
                    if not isinstance(alloc_data, dict):
                        alloc_data = {}
                    alpha_os = allocations.get('alpha_os', {}) if isinstance(allocations, dict) else {}
                    portfolio_state.update({
                        'active_strategies': len(alloc_data),
                        'strategy_allocations': alloc_data,
                        'allocation_timestamp': allocations.get('timestamp', ''),
                        'alpha_os_mode': alpha_os.get('mode', '') if isinstance(alpha_os, dict) else '',
                        'alpha_os_effective_strategy_weights': (
                            alpha_os.get('effective_strategy_weights', {})
                            if isinstance(alpha_os, dict)
                            else {}
                        ),
                    })
            
            self.portfolio_state = portfolio_state
            
        except Exception as e:
            print(f"⚠️ Error updating portfolio state: {e}")
            self.portfolio_state = {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def update_risk_state(self):
        """Update risk state from all risk systems"""
        
        try:
            risk_state = {}
            
            # Load Survival State
            if os.path.exists(self.source_paths['survival_state']):
                with open(self.source_paths['survival_state'], 'r') as f:
                    survival_state = json.load(f)
                    
                    risk_state.update({
                        'survival_mode': survival_state.get('survival_mode', 'normal'),
                        'system_stress': survival_state.get('system_stress', 0.0),
                        'emergency_triggered': survival_state.get('emergency_triggered', False),
                        'exposure_multiplier': survival_state.get('action_parameters', {}).get('exposure_multiplier', 1.0),
                        'survival_timestamp': survival_state.get('timestamp', '')
                    })
            
            # Load Emergency Brake State
            if os.path.exists(self.source_paths['emergency_brake']):
                with open(self.source_paths['emergency_brake'], 'r') as f:
                    brake_state = json.load(f)
                    
                    risk_state.update({
                        'emergency_brake_active': brake_state.get('emergency_triggered', False),
                        'brake_conditions': len(brake_state.get('triggered_conditions', [])),
                        'brake_timestamp': brake_state.get('timestamp', '')
                    })
            
            # Load Market Brain Survival Status
            if os.path.exists(self.source_paths['market_brain_state']):
                with open(self.source_paths['market_brain_state'], 'r') as f:
                    brain_state = json.load(f)
                    
                    intelligence_summary = brain_state.get('intelligence_summary', {})
                    survival = intelligence_summary.get('survival_status', {})
                    
                    risk_state.update({
                        'brain_survival_mode': survival.get('mode', 'normal'),
                        'brain_emergency': survival.get('emergency', False),
                        'brain_exposure_multiplier': survival.get('exposure_multiplier', 1.0)
                    })
            
            # Compute overall risk level
            stress_indicators = [
                risk_state.get('system_stress', 0.0),
                1.0 if risk_state.get('emergency_triggered', False) else 0.0,
                1.0 if risk_state.get('emergency_brake_active', False) else 0.0,
                1.0 if risk_state.get('brain_emergency', False) else 0.0
            ]
            
            risk_state['overall_risk_level'] = np.mean(stress_indicators)
            
            # Determine risk status
            if risk_state['overall_risk_level'] > 0.8:
                risk_state['risk_status'] = 'critical'
            elif risk_state['overall_risk_level'] > 0.5:
                risk_state['risk_status'] = 'elevated'
            elif risk_state['overall_risk_level'] > 0.2:
                risk_state['risk_status'] = 'moderate'
            else:
                risk_state['risk_status'] = 'normal'
            
            self.risk_state = risk_state
            
        except Exception as e:
            print(f"⚠️ Error updating risk state: {e}")
            self.risk_state = {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def get_unified_state(self):
        """Get complete unified state"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'market': self.market_state,
            'intelligence': self.intelligence_state,
            'portfolio': self.portfolio_state,
            'risk': self.risk_state,
            'system_health': self.compute_system_health()
        }
    
    def compute_system_health(self):
        """Compute overall system health metrics"""
        
        try:
            health = {}
            
            # Data freshness
            market_updated = self.market_state.get('last_updated', '')
            if market_updated:
                try:
                    last_update = pd.to_datetime(market_updated)
                    hours_since_update = (datetime.now() - last_update).total_seconds() / 3600
                    health['data_freshness_hours'] = hours_since_update
                    health['data_fresh'] = hours_since_update < 24
                except:
                    health['data_fresh'] = False
            else:
                health['data_fresh'] = False
            
            # Component availability
            components = ['market', 'intelligence', 'portfolio', 'risk']
            available_components = sum(1 for comp in components if 
                                     getattr(self, f'{comp}_state') and 
                                     not getattr(self, f'{comp}_state').get('error'))
            
            health['component_availability'] = available_components / len(components)
            health['components_healthy'] = available_components
            health['total_components'] = len(components)
            
            # Risk status
            risk_status = self.risk_state.get('risk_status', 'unknown')
            health['risk_status'] = risk_status
            health['risk_level'] = self.risk_state.get('overall_risk_level', 0.0)
            
            # Portfolio health
            portfolio_exposure = self.portfolio_state.get('total_exposure', 0.0)
            health['portfolio_exposure'] = portfolio_exposure
            health['portfolio_active'] = portfolio_exposure > 0.01
            
            # Intelligence health
            unified_conviction = self.intelligence_state.get('unified_conviction', 0.0)
            health['intelligence_conviction'] = unified_conviction
            health['intelligence_active'] = unified_conviction > 0.1
            
            # Overall health score
            health_factors = [
                1.0 if health['data_fresh'] else 0.0,
                health['component_availability'],
                1.0 if risk_status in ['normal', 'moderate'] else 0.0,
                1.0 if health['portfolio_active'] else 0.0,
                1.0 if health['intelligence_active'] else 0.0
            ]
            
            health['overall_health_score'] = np.mean(health_factors)
            
            # Health status
            if health['overall_health_score'] > 0.8:
                health['health_status'] = 'excellent'
            elif health['overall_health_score'] > 0.6:
                health['health_status'] = 'good'
            elif health['overall_health_score'] > 0.4:
                health['health_status'] = 'fair'
            else:
                health['health_status'] = 'poor'
            
            return health
            
        except Exception as e:
            return {'error': str(e), 'health_status': 'unknown'}
    
    def update_all_state(self):
        """Update all state components"""
        
        print("📊 Updating unified state...")
        
        try:
            # Update all components
            self.update_market_state()
            self.update_intelligence_state()
            self.update_portfolio_state()
            self.update_risk_state()
            
            # Save state
            self.save_state()
            
            print("   ✅ Unified state updated successfully")
            return True
            
        except Exception as e:
            print(f"   ❌ Unified state update failed: {e}")
            return False
    
    def save_state(self):
        """Save unified state to files"""
        
        try:
            state = self.get_unified_state()
            
            # Save to JSON (human readable)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            # Save to Parquet (fast loading)
            state_df = pd.DataFrame([self.flatten_state(state)])
            state_df.to_parquet(self.state_parquet, index=False)
            
            # Update history
            self.update_state_history(state)
            
        except Exception as e:
            print(f"⚠️ Error saving state: {e}")
    
    def flatten_state(self, state):
        """Flatten nested state for DataFrame storage"""
        
        flattened = {'timestamp': state['timestamp'], 'version': state['version']}
        
        # Flatten each component
        for component, data in state.items():
            if isinstance(data, dict) and component not in ['timestamp', 'version']:
                for key, value in data.items():
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        flattened[f"{component}_{key}"] = value
                    elif isinstance(value, dict):
                        # Handle nested dicts (like sector_exposure)
                        flattened[f"{component}_{key}_count"] = len(value)
                    elif isinstance(value, list):
                        flattened[f"{component}_{key}_count"] = len(value)
        
        return flattened
    
    def update_state_history(self, state):
        """Update state history"""
        
        try:
            # Load existing history
            if os.path.exists(self.state_history_file):
                history_df = pd.read_parquet(self.state_history_file)
            else:
                history_df = pd.DataFrame()
            
            # Add current state
            current_state_df = pd.DataFrame([self.flatten_state(state)])
            
            if not history_df.empty:
                history_df = pd.concat([history_df, current_state_df], ignore_index=True)
            else:
                history_df = current_state_df
            
            # Keep only recent history (last 1000 records)
            history_df = history_df.tail(1000)
            
            # Save history
            history_df.to_parquet(self.state_history_file, index=False)
            
        except Exception as e:
            print(f"⚠️ Error updating state history: {e}")
    
    def get_state_for_dashboard(self):
        """Get state formatted for dashboard consumption"""
        
        state = self.get_unified_state()
        
        # Format for dashboard
        dashboard_state = {
            'timestamp': state['timestamp'],
            'system_health': state['system_health'],
            'command_bar': {
                'regime': state['market'].get('regime', 'unknown'),
                'risk_level': state['risk'].get('risk_status', 'unknown'),
                'exposure': state['portfolio'].get('total_exposure', 0.0) * 100,
                'drawdown': state['portfolio'].get('max_drawdown', 0.0) * 100,
                'volatility': state['market'].get('market_stress', 0.0) * 100,
                'liquidity': state['market'].get('market_phase', 'unknown'),
                'ai_conviction': state['intelligence'].get('unified_conviction', 0.0) * 100,
                'ai_active': state['intelligence'].get('unified_conviction', 0.0) > 0.1
            },
            'market_state': state['market'],
            'intelligence_state': state['intelligence'],
            'portfolio_state': state['portfolio'],
            'risk_state': state['risk']
        }
        
        return dashboard_state
    
    def load_state(self):
        """Load existing unified state"""
        
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                    self.market_state = state.get('market', {})
                    self.intelligence_state = state.get('intelligence', {})
                    self.portfolio_state = state.get('portfolio', {})
                    self.risk_state = state.get('risk', {})
                    
                    return True
            else:
                return False
                
        except Exception as e:
            print(f"⚠️ Error loading state: {e}")
            return False

def main():
    """Test Unified State Manager"""
    
    print("📊 TESTING UNIFIED STATE MANAGER")
    print("=" * 40)
    
    state_manager = UnifiedStateManager()
    
    # Test state update
    success = state_manager.update_all_state()
    
    if success:
        # Get unified state
        unified_state = state_manager.get_unified_state()
        
        print(f"\n🎯 Unified State Summary:")
        print(f"   Market State: {len(unified_state['market'])} metrics")
        print(f"   Intelligence State: {len(unified_state['intelligence'])} metrics")
        print(f"   Portfolio State: {len(unified_state['portfolio'])} metrics")
        print(f"   Risk State: {len(unified_state['risk'])} metrics")
        
        # System health
        health = unified_state['system_health']
        print(f"\n🏥 System Health: {health['health_status'].upper()}")
        print(f"   Health Score: {health['overall_health_score']:.1%}")
        print(f"   Components Healthy: {health['components_healthy']}/{health['total_components']}")
        print(f"   Risk Status: {health['risk_status'].upper()}")
        
        # Dashboard state
        dashboard_state = state_manager.get_state_for_dashboard()
        command_bar = dashboard_state['command_bar']
        
        print(f"\n🖥️ Dashboard Command Bar:")
        print(f"   Regime: {command_bar['regime']}")
        print(f"   Risk: {command_bar['risk_level']}")
        print(f"   Exposure: {command_bar['exposure']:.1f}%")
        print(f"   AI Conviction: {command_bar['ai_conviction']:.1f}%")
        print(f"   AI Active: {'✅' if command_bar['ai_active'] else '❌'}")
        
        print(f"\n✅ Unified State Manager test successful!")
        return True
    else:
        print(f"\n❌ Unified State Manager test failed!")
        return False

if __name__ == "__main__":
    main()
