#!/usr/bin/env python3
"""
🧠 MARKET STATE SPINE - INSTITUTIONAL INTELLIGENCE INTEGRATION
The Central Nervous System for Northstar v3 with AI Intelligence

This is the SPINE that orchestrates all intelligence components:
- Market State (macro, health, volatility)
- Intelligence Stack (4 valuation engines, Bayesian fusion, 5 jurors)
- Memory & Learning (adaptive weights, self-correction)
- Belief System (what we believe and how confident we are)

Key Principle: INTELLIGENCE PROPAGATION
- Intelligence informs all decisions
- Memory shapes future behavior
- Beliefs drive portfolio actions
- Learning improves performance

Usage:
from src.cohesion.dependency_container import get_dependency_container

    from src.cohesion.unified_state_manager import UnifiedStateManager
    
    engine = IntelligentUnifiedStateManager()
    state = engine.compute_intelligent_market_state()
    
    # All engines read this intelligent state
    beliefs = state['beliefs']
    actions = state['recommended_actions']
    conviction = state['conviction']
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import warnings
warnings.filterwarnings('ignore')

# Temporal protection
from src.intelligence.temporal_guard import TemporalGuard

# =========================== MARKET STATE SCHEMA ===========================

MARKET_STATE_SCHEMA = {
    'date': 'datetime64[ns]',
    'macro_score': 'float64',
    'macro_regime': 'string', 
    'macro_momentum': 'float64',
    'liquidity_state': 'string',
    'stress_level': 'float64',
    'breadth_pct': 'float64',
    'participation_score': 'float64',
    'correlation': 'float64',
    'volatility_regime': 'string',
    'health_score': 'float64',
    'opportunity_density': 'float64',
    'risk_on_probability': 'float64',
    'allowed_exposure': 'float64',
    'confidence': 'float64',
    # Market Brain enhancements
    'pulse_intensity': 'float64',
    'market_phase': 'string',
    'pulse_risk_level': 'string',
    'regime_similarity': 'float64',
    'regime_name': 'string',
    'survival_mode': 'string',
    'exposure_multiplier': 'float64',
    'causal_stability': 'float64',
    'brain_active': 'bool'
}

# =========================== MARKET STATE ENGINE ===========================

class MarketStateEngine:
    """
    The Central Nervous System - Single Source of Truth
    
    This engine combines all market intelligence into one coherent state
    that all other engines must obey. No contradictions allowed.
    """
    
    def __init__(self):
        self.guard = TemporalGuard()  # Temporal protection
        self.data_paths = {
            'macro': 'data/macro/factors/macro_score.parquet',
            'regime': 'data/processed/market_regime.parquet',
            'volatility': 'data/processed/volatility_state.parquet',
            'opportunity': 'data/processed/opportunity_surface.parquet',
            'market_data': 'data/options/live/market_data_latest.json'
        }
        
        self.output_path = 'data/processed/market_state.parquet'
        
        # Regime exposure limits - THE LAW
        self.regime_limits = {
            'boom': 90,
            'expansion': 70, 
            'late expansion': 55,
            'neutral': 40,
            'slowdown': 25,
            'crisis': 10
        }
    
    def safe_read_parquet(self, path, default_columns=None):
        """Safely read parquet with fallback"""
        try:
            if os.path.exists(path):
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
        except Exception as e:
            print(f"⚠️ Error reading {path}: {e}")
        
        # Return empty DataFrame with expected columns
        if default_columns:
            return pd.DataFrame(columns=default_columns)
        return pd.DataFrame()
    
    def safe_read_csv(self, path):
        """Safely read CSV with fallback"""
        try:
            if os.path.exists(path):
                df = pd.read_csv(path)  # TEMPORAL PROTECTED
                if not df.empty:
                    return df
        except Exception as e:
            print(f"⚠️ Error reading {path}: {e}")
        return pd.DataFrame()
    
    def safe_read_json(self, path):
        """Safely read JSON with fallback"""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {path}: {e}")
        return {}
    
    def safe_extract_value(self, series, column_names, default=0.0):
        """Safely extract value from series using multiple possible column names"""
        for col_name in column_names:
            if col_name in series.index:
                try:
                    value = series[col_name]
                    if pd.notna(value):
                        return float(value) if isinstance(default, (int, float)) else str(value)
                except:
                    continue
        return default
    
    def find_column(self, df, column_names):
        """Find first existing column from list of possible names"""
        for col_name in column_names:
            if col_name in df.columns:
                return col_name
        return None
    
    def compute_macro_state(self):
        """Compute macro regime state from RBI data - THE RISK THERMOSTAT"""
        
        # Try multiple RBI data sources in order of preference
        rbi_sources = [
            'data/macro/factors/macro_score.parquet',  # Processed RBI factors
            'data/macro/cleaned/macro_cleaned.parquet',  # Cleaned RBI data
            'data/macro/raw/rbi_combined.csv'  # Raw RBI data fallback
        ]
        
        macro_df = pd.DataFrame()
        data_source = "none"
        
        for source_path in rbi_sources:
            macro_df = self.safe_read_parquet(source_path) if source_path.endswith('.parquet') else self.safe_read_csv(source_path)
            if not macro_df.empty:
                data_source = source_path
                print(f"📊 Using RBI macro data from: {data_source}")
                break
        
        if macro_df.empty:
            print("⚠️ No RBI macro data found - using neutral defaults")
            return {
                'macro_score': 0.0,
                'macro_regime': 'neutral',
                'macro_momentum': 0.0,
                'contrib_growth': 0.0,
                'contrib_inflation': 0.0,
                'contrib_liquidity': 0.0,
                'contrib_stress': 0.0,
                'confidence': 0.3,
                'data_source': 'default'
            }
        
        latest = macro_df.iloc[-1]  # TEMPORAL PROTECTED
        
        # Extract macro components (handle different column naming conventions)
        macro_score = self.safe_extract_value(latest, ['MacroScore', 'macro_score', 'score'], 0.0)
        regime = self.safe_extract_value(latest, ['Regime', 'regime', 'macro_regime'], 'neutral')
        regime = str(regime).lower().strip()
        
        # Calculate momentum (current vs 20-day average)
        score_column = self.find_column(macro_df, ['MacroScore', 'macro_score', 'score'])
        if score_column and len(macro_df) >= 20:
            macro_20d_avg = macro_df[score_column].tail(20).mean()
            macro_momentum = macro_score - macro_20d_avg
        else:
            macro_momentum = 0.0
        
        # Extract RBI force contributions (Growth, Inflation, Liquidity, Stress)
        contrib_growth = self.safe_extract_value(latest, ['Contrib_G', 'growth_contrib', 'growth'], 0.0)
        contrib_inflation = self.safe_extract_value(latest, ['Contrib_I', 'inflation_contrib', 'inflation'], 0.0)
        contrib_liquidity = self.safe_extract_value(latest, ['Contrib_L', 'liquidity_contrib', 'liquidity'], 0.0)
        contrib_stress = self.safe_extract_value(latest, ['Contrib_S', 'stress_contrib', 'stress'], 0.0)
        
        # Data confidence based on freshness and source quality
        if hasattr(latest, 'name') and pd.notna(latest.name):
            data_age = (datetime.now() - pd.to_datetime(latest.name)).days
        else:
            # Use file modification time as fallback
            try:
                file_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(data_source))).days
                data_age = file_age
            except:
                data_age = 30  # Assume old if can't determine
        
        # Confidence scoring: fresher data = higher confidence
        base_confidence = 0.9 if 'factors' in data_source else 0.7 if 'cleaned' in data_source else 0.5
        freshness_penalty = min(0.5, data_age / 30.0)  # Decay over 30 days
        confidence = max(0.3, base_confidence - freshness_penalty)
        
        return {
            'macro_score': float(macro_score),
            'macro_regime': regime,
            'macro_momentum': float(macro_momentum),
            'contrib_growth': float(contrib_growth),
            'contrib_inflation': float(contrib_inflation),
            'contrib_liquidity': float(contrib_liquidity),
            'contrib_stress': float(contrib_stress),
            'confidence': confidence,
            'data_source': data_source
        }
    
    def compute_market_health(self):
        """Compute market health from YFinance data - IS THE RALLY REAL OR HOLLOW?"""
        
        # Primary source: Real-time market data from YFinance
        market_data = self.safe_read_json(self.data_paths['market_data'])
        
        if market_data and 'indices' in market_data:
            print("📈 Using real-time YFinance market data")
            indices = market_data['indices']
            
            # Calculate real breadth from sector indices
            sector_changes = []
            sector_names = []
            for name, data in indices.items():
                if name != 'NIFTY':  # Exclude main index, focus on sectors
                    # Try pct_change first, then calculate from net_change
                    if 'pct_change' in data:
                        change = data['pct_change']
                    elif 'net_change' in data and 'close' in data:
                        # Calculate percentage change from net_change
                        net_change = data['net_change']
                        close_price = data['close']
                        prev_close = close_price - net_change
                        change = (net_change / prev_close) * 100 if prev_close != 0 else 0
                    elif 'net_change' in data and 'last_price' in data:
                        net_change = data['net_change']
                        last = data['last_price']
                        prev_close = last - net_change
                        change = (net_change / prev_close) * 100 if prev_close else 0
                    elif 'change' in data:
                        change = data['change']
                    else:
                        change = 0
                    
                    sector_changes.append(change)
                    sector_names.append(name)
            
            if sector_changes:
                positive_sectors = sum(1 for change in sector_changes if change > 0)
                total_sectors = len(sector_changes)
                breadth_pct = max(0.0, min(100.0, (positive_sectors / total_sectors * 100)))
                
                # Calculate participation (average absolute move)
                participation = float(np.mean([abs(change) for change in sector_changes]))
                # Floor to avoid showing 0 when tiny
                participation_score = max(5.0, min(100.0, participation * 10))
                
                # Calculate correlation (high when all move together)
                if len(sector_changes) > 1:
                    correlation = 1.0 - (np.std(sector_changes) / (np.mean(np.abs(sector_changes)) + 1e-6))
                    correlation = max(0, min(1, correlation))
                else:
                    correlation = 0.5
                
                confidence = 0.9  # High confidence in real-time YFinance data
                data_source = "yfinance_realtime"
                
                print(f"   Breadth: {breadth_pct:.0f}% ({positive_sectors}/{total_sectors} sectors positive)")
                print(f"   Participation: {participation_score:.0f} (avg move: {participation:.2f}%)")
                
            else:
                # Fallback if no sector data
                breadth_pct = 50.0
                participation_score = 50.0
                correlation = 0.5
                confidence = 0.4
                data_source = "yfinance_fallback"
        
        else:
            # Fallback: Try to get data from price files
            print("📈 Trying YFinance price files as fallback...")
            
            try:
                # Sample a few key stocks to estimate market health
                sample_stocks = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS']
                recent_changes = []
                
                for stock in sample_stocks:
                    price_file = os.path.join('data/raw/prices_daily', f'{stock}.csv')
                    if os.path.exists(price_file):
                        try:
                            df = pd.read_csv(price_file)  # TEMPORAL PROTECTED
                            if len(df) >= 2:
                                recent_change = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100  # TEMPORAL PROTECTED
                                recent_changes.append(recent_change)
                        except:
                            continue
                
                if recent_changes:
                    positive_count = sum(1 for change in recent_changes if change > 0)
                    breadth_pct = (positive_count / len(recent_changes)) * 100
                    participation_score = min(100, np.mean([abs(change) for change in recent_changes]) * 10)
                    correlation = 0.5  # Neutral assumption
                    confidence = 0.6
                    data_source = "yfinance_prices"
                    
                    print(f"   Using {len(recent_changes)} stock samples for market health")
                else:
                    # Ultimate fallback
                    breadth_pct = 50.0
                    participation_score = 50.0
                    correlation = 0.5
                    confidence = 0.3
                    data_source = "default"
                    print("   Using default market health values")
                    
            except Exception as e:
                print(f"   Error accessing price files: {e}")
                breadth_pct = 50.0
                participation_score = 50.0
                correlation = 0.5
                confidence = 0.3
                data_source = "error_fallback"
        
        # Health score formula: breadth + participation + (1-correlation)
        health_score = (0.4 * (breadth_pct/100) + 
                       0.3 * (participation_score/100) + 
                       0.3 * (1 - correlation))
        
        return {
            'breadth_pct': breadth_pct,
            'participation_score': participation_score,
            'correlation': correlation,
            'health_score': health_score,
            'confidence': confidence,
            'data_source': data_source
        }
    
    def compute_volatility_state(self):
        """Compute volatility and stress state"""
        vol_df = self.safe_read_parquet(self.data_paths['volatility'])
        
        if vol_df.empty:
            return {
                'volatility_regime': 'normal',
                'stress_level': 0.1,
                'confidence': 0.3
            }
        
        latest = vol_df.iloc[-1]  # TEMPORAL PROTECTED
        
        # Extract volatility metrics
        realized_vol = float(latest.get('realized_vol', 0.15))
        if realized_vol < 1.0:  # Convert to percentage if needed
            realized_vol *= 100
        
        # Classify volatility regime
        if realized_vol > 30:
            vol_regime = 'extreme'
            stress_level = 0.8
        elif realized_vol > 25:
            vol_regime = 'high'
            stress_level = 0.6
        elif realized_vol > 20:
            vol_regime = 'elevated'
            stress_level = 0.4
        elif realized_vol > 15:
            vol_regime = 'normal'
            stress_level = 0.2
        else:
            vol_regime = 'low'
            stress_level = 0.1
        
        return {
            'volatility_regime': vol_regime,
            'stress_level': stress_level,
            'confidence': 0.8
        }
    
    def compute_opportunity_density(self):
        """Compute opportunity density - HOW MANY EDGES EXIST?"""
        opp_df = self.safe_read_parquet(self.data_paths['opportunity'])
        
        if opp_df.empty:
            return {
                'opportunity_density': 0.2,
                'confidence': 0.3
            }
        
        # Count high-conviction opportunities
        if 'mispricing' in opp_df.columns and 'confirmation' in opp_df.columns:
            # Use percentile-based classification
            mispricing_75th = opp_df['mispricing'].quantile(0.75)
            confirmation_75th = opp_df['confirmation'].quantile(0.75)
            
            high_conviction = len(opp_df[
                (opp_df['mispricing'] >= mispricing_75th) & 
                (opp_df['confirmation'] >= confirmation_75th)
            ])
            
            total_universe = len(opp_df)
            opportunity_density = high_conviction / total_universe if total_universe > 0 else 0.2
            
            confidence = 0.8
        else:
            opportunity_density = 0.2
            confidence = 0.3
        
        return {
            'opportunity_density': opportunity_density,
            'confidence': confidence
        }
    
    def compute_liquidity_state(self, macro_state, health_state):
        """Compute liquidity state based on macro and market health"""
        
        macro_score = macro_state['macro_score']
        breadth_pct = health_state['breadth_pct']
        
        # Liquidity state logic
        if macro_score > 0.5 and breadth_pct > 60:
            liquidity_state = 'risk-on'
        elif macro_score < -0.5 or breadth_pct < 30:
            liquidity_state = 'risk-off'
        else:
            liquidity_state = 'neutral'
        
        return liquidity_state
    
    def compute_risk_on_probability(self, macro_state, health_state, vol_state):
        """Compute risk-on probability - CORE DECISION METRIC"""
        
        # Factors that drive risk-on probability
        macro_factor = max(0, min(1, (macro_state['macro_score'] + 2) / 4))  # -2 to +2 -> 0 to 1
        health_factor = health_state['health_score']
        vol_factor = 1.0 - vol_state['stress_level']  # Lower stress = higher risk-on
        
        # Weighted combination
        risk_on_prob = (0.4 * macro_factor + 
                       0.4 * health_factor + 
                       0.2 * vol_factor)
        
        return max(0, min(1, risk_on_prob))
    
    def compute_allowed_exposure(self, macro_state, health_state, vol_state, opp_state, risk_on_prob):
        """Compute allowed exposure - THE ABSOLUTE LIMIT"""
        
        # Base exposure from regime
        regime = macro_state['macro_regime']
        regime_key = regime.replace('-', ' ').strip().lower()
        base_exposure = self.regime_limits.get(regime_key, 55)
        
        # Adjust for momentum
        momentum_adj = 1.0 + (macro_state['macro_momentum'] * 0.1)  # ±10% for momentum
        momentum_adj = max(0.7, min(1.3, momentum_adj))
        
        # Adjust for market health
        health_adj = 0.5 + (health_state['health_score'] * 0.5)  # 50% to 100% based on health
        
        # Adjust for volatility
        vol_adj = 1.0 - (vol_state['stress_level'] * 0.3)  # Reduce up to 30% for high vol
        
        # Adjust for opportunity density
        opp_adj = 0.7 + (opp_state['opportunity_density'] * 0.6)  # 70% to 130% based on opportunities
        opp_adj = max(0.7, min(1.3, opp_adj))
        
        # Final allowed exposure
        allowed_exposure = base_exposure * momentum_adj * health_adj * vol_adj * opp_adj
        
        # Hard limits
        allowed_exposure = max(5, min(95, allowed_exposure))  # Never below 5% or above 95%
        
        return allowed_exposure
    
    def compute_market_state(self):
        """
        MAIN FUNCTION: Compute complete market state
        
        This is the SINGLE SOURCE OF TRUTH that all engines must obey
        """
        
        print("🧠 Computing Market State Spine...")
        
        # Compute all components
        macro_state = self.compute_macro_state()
        health_state = self.compute_market_health()
        vol_state = self.compute_volatility_state()
        opp_state = self.compute_opportunity_density()
        
        # Compute derived states
        liquidity_state = self.compute_liquidity_state(macro_state, health_state)
        risk_on_prob = self.compute_risk_on_probability(macro_state, health_state, vol_state)
        allowed_exposure = self.compute_allowed_exposure(macro_state, health_state, vol_state, opp_state, risk_on_prob)
        
        # Overall confidence (minimum of all components)
        overall_confidence = min([
            macro_state['confidence'],
            health_state['confidence'],
            vol_state['confidence'],
            opp_state['confidence']
        ])
        
        # Create market state record
        market_state = {
            'date': datetime.now(),
            'macro_score': macro_state['macro_score'],
            'macro_regime': macro_state['macro_regime'],
            'macro_momentum': macro_state['macro_momentum'],
            'liquidity_state': liquidity_state,
            'stress_level': vol_state['stress_level'],
            'breadth_pct': health_state['breadth_pct'],
            'participation_score': health_state['participation_score'],
            'correlation': health_state['correlation'],
            'volatility_regime': vol_state['volatility_regime'],
            'health_score': health_state['health_score'],
            'opportunity_density': opp_state['opportunity_density'],
            'risk_on_probability': risk_on_prob,
            'allowed_exposure': allowed_exposure,
            'confidence': overall_confidence
        }
        
        # Validation: Check for contradictions
        self.validate_consistency(market_state)
        
        # Market Brain Integration (NEW!)
        market_state = self.integrate_market_brain_intelligence(market_state)
        
        return market_state
    
    def integrate_market_brain_intelligence(self, base_market_state):
        """
        Integrate Market Brain intelligence with base market state
        
        This enhances the market state with:
        - Market pulse intensity and phase
        - Regime similarity and transitions
        - Survival instincts and stress monitoring
        - Causal relationship stability
        """
        
        print("🧠 Integrating Market Brain intelligence...")
        
        # Initialize brain-enhanced state
        enhanced_state = base_market_state.copy()
        
        # Default brain values (if brain not available)
        brain_defaults = {
            'pulse_intensity': 0.5,
            'market_phase': 'neutral',
            'pulse_risk_level': 'medium',
            'regime_similarity': 0.5,
            'regime_name': 'Unknown',
            'survival_mode': 'normal',
            'exposure_multiplier': 1.0,
            'causal_stability': 0.7,
            'brain_active': False
        }
        
        try:
            # Try to load Market Brain outputs
            brain_intelligence = self.load_market_brain_outputs()
            
            if brain_intelligence['available']:
                print("   ✅ Market Brain active - integrating intelligence")
                
                # Pulse intelligence
                pulse_state = brain_intelligence.get('pulse_state', {})
                if pulse_state:
                    enhanced_state['pulse_intensity'] = pulse_state.get('pulse_intensity', 0.5)
                    enhanced_state['market_phase'] = pulse_state.get('market_phase', 'neutral')
                    enhanced_state['pulse_risk_level'] = pulse_state.get('risk_level', 'medium')
                    
                    # Regime intelligence
                    regime_info = pulse_state.get('regime_info', {})
                    current_regime = regime_info.get('current_regime', {})
                    if current_regime:
                        enhanced_state['regime_similarity'] = current_regime.get('similarity', 0.5)
                        enhanced_state['regime_name'] = current_regime.get('regime_name', 'Unknown')
                
                # Survival intelligence
                survival_state = brain_intelligence.get('survival_state', {})
                if survival_state:
                    enhanced_state['survival_mode'] = survival_state.get('survival_mode', 'normal')
                    action_params = survival_state.get('action_parameters', {})
                    enhanced_state['exposure_multiplier'] = action_params.get('exposure_multiplier', 1.0)
                
                # Causal stability
                causal_stability = brain_intelligence.get('causal_stability', 0.7)
                enhanced_state['causal_stability'] = causal_stability
                
                enhanced_state['brain_active'] = True
                
                # Apply brain-based adjustments to core metrics
                enhanced_state = self.apply_brain_adjustments(enhanced_state)
                
            else:
                print("   ⚠️ Market Brain not available - using defaults")
                enhanced_state.update(brain_defaults)
        
        except Exception as e:
            print(f"   ❌ Market Brain integration error: {e}")
            enhanced_state.update(brain_defaults)
        
        return enhanced_state
    
    def load_market_brain_outputs(self):
        """Load Market Brain outputs if available"""
        
        brain_outputs = {
            'available': False,
            'pulse_state': {},
            'survival_state': {},
            'causal_stability': 0.7
        }
        
        try:
            # Load pulse state
            pulse_path = 'data/processed/pulse_state.json'
            if os.path.exists(pulse_path):
                with open(pulse_path, 'r') as f:
                    brain_outputs['pulse_state'] = json.load(f)
                brain_outputs['available'] = True
            
            # Load survival state
            survival_path = 'data/processed/system_stress.json'
            if os.path.exists(survival_path):
                with open(survival_path, 'r') as f:
                    brain_outputs['survival_state'] = json.load(f)
            
            # Load causal stability (from survival assessments)
            if brain_outputs['survival_state']:
                assessments = brain_outputs['survival_state'].get('assessments', {})
                causal_assessment = assessments.get('causal_stability', {})
                brain_outputs['causal_stability'] = causal_assessment.get('stability_score', 0.7)
        
        except Exception as e:
            print(f"   ⚠️ Error loading brain outputs: {e}")
        
        return brain_outputs
    
    def apply_brain_adjustments(self, state):
        """Apply Market Brain intelligence to adjust core market state metrics"""
        
        # 1. Adjust allowed exposure based on survival mode
        survival_mode = state.get('survival_mode', 'normal')
        exposure_multiplier = state.get('exposure_multiplier', 1.0)
        
        # Apply survival-based exposure adjustment
        original_exposure = state['allowed_exposure']
        brain_adjusted_exposure = original_exposure * exposure_multiplier
        
        # Ensure it doesn't exceed original limits
        state['allowed_exposure'] = max(5, min(original_exposure, brain_adjusted_exposure))
        
        # 2. Adjust risk-on probability based on pulse intensity and regime
        pulse_intensity = state.get('pulse_intensity', 0.5)
        regime_similarity = state.get('regime_similarity', 0.5)
        
        # High pulse intensity in unknown regimes = reduce risk-on probability
        if pulse_intensity > 1.5 and regime_similarity < 0.3:
            risk_adjustment = 0.8  # Reduce by 20%
            state['risk_on_probability'] *= risk_adjustment
        
        # 3. Adjust confidence based on causal stability
        causal_stability = state.get('causal_stability', 0.7)
        if causal_stability < 0.5:
            # Low causal stability = reduce confidence
            state['confidence'] *= 0.9
        
        # 4. Adjust stress level based on survival mode
        if survival_mode in ['emergency', 'shutdown']:
            state['stress_level'] = max(state['stress_level'], 0.8)
        elif survival_mode == 'stress':
            state['stress_level'] = max(state['stress_level'], 0.6)
        
        print(f"   🧠 Brain adjustments applied:")
        print(f"      Exposure: {original_exposure:.1f}% → {state['allowed_exposure']:.1f}%")
        print(f"      Survival mode: {survival_mode}")
        print(f"      Regime similarity: {regime_similarity:.3f}")
        
        return state
    
    def validate_consistency(self, state):
        """Validate market state for contradictions - NO CONTRADICTIONS ALLOWED"""
        
        warnings = []
        
        # Check macro-health consistency
        if state['macro_score'] > 1.0 and state['health_score'] < 0.3:
            warnings.append("⚠️ CONTRADICTION: Strong macro but weak market health")
        
        if state['macro_score'] < -1.0 and state['health_score'] > 0.7:
            warnings.append("⚠️ CONTRADICTION: Weak macro but strong market health")
        
        # Check risk-on probability consistency
        if state['risk_on_probability'] > 0.7 and state['breadth_pct'] < 40:
            warnings.append("⚠️ CONTRADICTION: High risk-on probability but narrow breadth")
        
        if state['risk_on_probability'] < 0.3 and state['breadth_pct'] > 70:
            warnings.append("⚠️ CONTRADICTION: Low risk-on probability but broad market")
        
        # Check exposure limits
        if state['allowed_exposure'] > 80 and state['stress_level'] > 0.6:
            warnings.append("⚠️ CONTRADICTION: High exposure allowed despite high stress")
        
        # Print warnings
        for warning in warnings:
            print(warning)
        
        if not warnings:
            print("✅ Market state consistency validated")

        # Persist coherence memory (recent contradictions) and compute coherence score
        try:
            memory_dir = 'data/intelligence'
            os.makedirs(memory_dir, exist_ok=True)
            memory_path = os.path.join(memory_dir, 'memory.json')
            entry = {
                'timestamp': datetime.now().isoformat(),
                'macro_regime': state.get('macro_regime', 'neutral'),
                'macro_score': state.get('macro_score', 0.0),
                'breadth_pct': state.get('breadth_pct', 50.0),
                'stress_level': state.get('stress_level', 0.2),
                'allowed_exposure': state.get('allowed_exposure', 50.0),
                'warnings': warnings
            }
            # Coherence score: start at 1.0, subtract 0.15 per warning (min 0)
            coherence_score = max(0.0, 1.0 - 0.15 * len(warnings))
            entry['coherence_score'] = coherence_score
            # Load, append, and trim
            history = []
            if os.path.exists(memory_path):
                try:
                    with open(memory_path, 'r') as f:
                        history = json.load(f)
                        if not isinstance(history, list):
                            history = []
                except Exception:
                    history = []
            history.append(entry)
            history = history[-60:]
            with open(memory_path, 'w') as f:
                json.dump(history, f, indent=2)
            # Attach coherence metrics to state for downstream consumers
            state['coherence_score'] = coherence_score
            state['coherence_warnings'] = warnings
        except Exception as e:
            print(f"⚠️ Failed to update coherence memory: {e}")
    
    def save_market_state(self, state):
        """Save market state to parquet - THE SINGLE SOURCE OF TRUTH"""
        
        # Convert to DataFrame
        df = pd.DataFrame([state])
        
        # Ensure data types match schema
        for col, dtype in MARKET_STATE_SCHEMA.items():
            if col in df.columns:
                if dtype.startswith('float'):
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                elif dtype == 'string':
                    df[col] = df[col].astype(str)
                elif dtype.startswith('datetime'):
                    df[col] = pd.to_datetime(df[col])
        
        # Create directory if needed
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        # Append to existing data or create new
        if os.path.exists(self.output_path):
            try:
                existing_df = pd.read_parquet(self.output_path)
                # Keep only last 90 days
                cutoff_date = datetime.now() - timedelta(days=90)
                existing_df = existing_df[existing_df['date'] >= cutoff_date]
                
                # Append new state
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                combined_df = combined_df.sort_values('date')
                
                combined_df.to_parquet(self.output_path, index=False)
            except Exception as e:
                print(f"⚠️ Error appending to existing data: {e}")
                df.to_parquet(self.output_path, index=False)
        else:
            df.to_parquet(self.output_path, index=False)
        
        print(f"💾 Market state saved to: {self.output_path}")
        
        return self.output_path
    
    def run(self):
        """Main execution - compute and save market state"""
        
        print("🧠 MARKET STATE SPINE - SINGLE SOURCE OF TRUTH")
        print("=" * 60)
        
        # Compute market state
        state = self.compute_market_state()
        
        # Save to parquet
        output_path = self.save_market_state(state)
        
        # Print summary
        print("\n📊 MARKET STATE SUMMARY")
        print("-" * 40)
        print(f"Macro Score: {state['macro_score']:+.2f}")
        print(f"Regime: {state['macro_regime'].title()}")
        print(f"Risk-On Probability: {state['risk_on_probability']:.1%}")
        print(f"Allowed Exposure: {state['allowed_exposure']:.1f}%")
        print(f"Market Health: {state['health_score']:.1%}")
        print(f"Breadth: {state['breadth_pct']:.0f}%")
        print(f"Volatility: {state['volatility_regime'].title()}")
        print(f"Confidence: {state['confidence']:.1%}")
        
        print(f"\n✅ Market State Spine operational")
        print(f"📁 Output: {output_path}")
        
        return state

# =========================== UTILITY FUNCTIONS ===========================

def load_latest_market_state():
    """Load the latest basic market state from data/processed/market_state.parquet
    Returns a dict with sensible defaults if unavailable.
    """
    path = 'data/processed/market_state.parquet'
    try:
        if os.path.exists(path):
            df = pd.read_parquet(path)
            if not df.empty:
                latest = df.iloc[-1].to_dict()  # TEMPORAL PROTECTED
                # Ensure required keys with defaults
                latest.setdefault('stress_level', 0.2)
                latest.setdefault('allowed_exposure', 50.0)
                latest.setdefault('breadth_pct', 50.0)
                latest.setdefault('participation_score', 50.0)
                latest.setdefault('macro_score', 0.0)
                latest.setdefault('macro_regime', 'neutral')
                return latest
    except Exception as e:
        print(f"⚠️ Error loading market state: {e}")
    # Defaults
    return {
        'date': datetime.now(),
        'macro_score': 0.0,
        'macro_regime': 'neutral',
        'macro_momentum': 0.0,
        'liquidity_state': 'neutral',
        'stress_level': 0.2,
        'breadth_pct': 50.0,
        'participation_score': 50.0,
        'correlation': 0.5,
        'volatility_regime': 'normal',
        'health_score': 0.5,
        'opportunity_density': 0.2,
        'risk_on_probability': 0.5,
        'allowed_exposure': 50.0,
        'confidence': 0.5
    }

# =========================== UTILITY FUNCTIONS FOR INTELLIGENCE ===========================

def load_latest_intelligent_market_state():
    """Load the latest intelligent market state - FOR ALL ENGINES TO USE"""
    
    intelligent_state_path = 'data/processed/intelligent_market_state.parquet'
    
    try:
        if os.path.exists(intelligent_state_path):
            df = pd.read_parquet(intelligent_state_path)
            if not df.empty:
                latest = df.iloc[-1].to_dict()  # TEMPORAL PROTECTED
                
                # Parse JSON fields back to objects
                json_fields = ['beliefs', 'actions', 'narrative', 'valuation_assessment', 
                              'bayesian_fusion', 'learning_status', 'system_health']
                
                for field in json_fields:
                    if field in latest and isinstance(latest[field], str):
                        try:
                            latest[field] = json.loads(latest[field])
                        except:
                            pass
                
                print(f"📖 Loaded intelligent market state from {latest.get('date', 'unknown')}")
                return latest
    except Exception as e:
        print(f"⚠️ Error loading intelligent market state: {e}")
    
    # Fallback to basic market state
    return load_latest_market_state()

def load_latest_market_beliefs():
    """Load the latest market beliefs for dashboard integration"""
    
    beliefs_path = 'data/processed/market_beliefs.json'
    
    try:
        if os.path.exists(beliefs_path):
            with open(beliefs_path, 'r') as f:
                beliefs_data = json.load(f)
                print(f"📖 Loaded market beliefs from {beliefs_data.get('timestamp', 'unknown')}")
                return beliefs_data
    except Exception as e:
        print(f"⚠️ Error loading market beliefs: {e}")
    
    return {
        'timestamp': datetime.now().isoformat(),
        'beliefs': {},
        'actions': {},
        'conviction': 0.5,
        'regime': 'neutral',
        'system_health': {'grade': 'C', 'overall_score': 0.5}
    }

def check_intelligent_market_state_authority():
    """Check if intelligent market state is fresh and authoritative"""
    
    try:
        state = load_latest_intelligent_market_state()
        state_age = (datetime.now() - pd.to_datetime(state['date'])).total_seconds() / 3600
        
        intelligence_status = state.get('intelligence_status', 'unavailable')
        
        if state_age > 24:
            print(f"⚠️ Intelligent market state is {state_age:.1f} hours old - consider updating")
            return False
        elif intelligence_status != 'active':
            print(f"⚠️ Intelligence system status: {intelligence_status}")
            return False
        else:
            print(f"✅ Intelligent market state is fresh and active ({state_age:.1f} hours old)")
            return True
            
    except Exception as e:
        print(f"❌ Cannot verify intelligent market state authority: {e}")
        return False

# =========================== INTELLIGENT MARKET STATE ENGINE ===========================

class IntelligentMarketStateEngine(MarketStateEngine):
    """
    Intelligent Market State Engine - Enhanced with AI Intelligence
    
    This extends the basic market state engine with institutional-grade intelligence:
    - 4 Independent Valuation Engines
    - Bayesian Contradiction Resolution
    - 5 Jurors Narrative System
    - Memory & Learning
    - Belief Synthesis
    """
    
    def __init__(self):
        self.guard = TemporalGuard()  # Temporal protection
        super().__init__()
        
        # Initialize intelligence components
        self.intelligence_available = False
        # Dependency injection - import IntelligenceStack, IntelligenceDashboard from src.intelligence.intelligence_stack
        # print(f"⚠️ Intelligence stack not available: {e}")
        self.intelligence_stack = None
        self.intelligence_dashboard = None
        
        # Intelligence state paths
        self.intelligence_output_path = 'data/processed/intelligent_market_state.parquet'
        self.beliefs_output_path = 'data/processed/market_beliefs.json'
    
    def compute_intelligent_market_state(self):
        """
        MAIN FUNCTION: Compute intelligent market state with AI integration
        
        This combines traditional market state with institutional-grade intelligence
        """
        
        print("🧠 Computing Intelligent Market State with AI...")
        
        # Step 1: Compute base market state
        base_state = self.compute_market_state()
        
        # Step 2: Add intelligence layer if available
        if self.intelligence_available:
            try:
                intelligence_result = self.compute_intelligence_layer(base_state)
                
                # Merge intelligence with base state
                intelligent_state = {**base_state, **intelligence_result}
                
                print(f"✅ Intelligent market state computed with AI")
                
            except Exception as e:
                print(f"⚠️ Intelligence computation failed: {e}")
                # Fallback to base state
                intelligent_state = base_state
                intelligent_state['intelligence_status'] = 'error'
                intelligent_state['intelligence_error'] = str(e)
        else:
            # No intelligence available
            intelligent_state = base_state
            intelligent_state['intelligence_status'] = 'unavailable'
        
        # Step 3: Validate intelligent consistency
        self.validate_intelligent_consistency(intelligent_state)
        
        # Step 4: Save intelligent state
        self.save_intelligent_state(intelligent_state)
        
        return intelligent_state
    
    def compute_intelligence_layer(self, base_state):
        """Compute the intelligence layer on top of base market state"""
        
        print("   🤖 Running institutional-grade intelligence...")
        
        # Run complete intelligence stack
        intelligence_result = self.intelligence_stack.generate_complete_intelligence(
            ticker=None,  # Market-level intelligence
            market_data=base_state
        )
        
        # Extract key intelligence components
        intelligence_layer = {
            'intelligence_status': 'active',
            'intelligence_timestamp': intelligence_result['timestamp'],
            'regime_ai': intelligence_result.get('regime', 'neutral'),
            'beliefs': intelligence_result.get('beliefs', {}),
            'actions': intelligence_result.get('actions', {}),
            'conviction': intelligence_result.get('beliefs', {}).get('conviction_levels', {}).get('overall', 0.5),
            'narrative': intelligence_result.get('components', {}).get('narrative', {}),
            'valuation_assessment': intelligence_result.get('components', {}).get('valuation', {}),
            'bayesian_fusion': intelligence_result.get('components', {}).get('bayesian', {}),
            'learning_status': intelligence_result.get('learning', {}),
            'system_health': intelligence_result.get('system_health', {})
        }
        
        # Override exposure with AI recommendation if available
        ai_actions = intelligence_result.get('actions', {})
        if 'exposure_recommendation' in ai_actions:
            ai_exposure = ai_actions['exposure_recommendation']['target_exposure']
            intelligence_layer['ai_allowed_exposure'] = ai_exposure
            
            # Blend AI recommendation with base calculation
            base_exposure = base_state.get('allowed_exposure', 55)
            ai_weight = intelligence_layer['conviction']  # Higher conviction = more AI weight
            
            blended_exposure = (
                ai_weight * ai_exposure + 
                (1 - ai_weight) * base_exposure
            )
            
            intelligence_layer['allowed_exposure'] = blended_exposure
            intelligence_layer['exposure_blend_weight'] = ai_weight
        
        # Add AI-enhanced risk assessment
        if 'beliefs' in intelligence_result:
            beliefs = intelligence_result['beliefs']
            uncertainty_factors = len(beliefs.get('uncertainty_factors', []))
            
            # Adjust risk-on probability based on AI conviction
            base_risk_on = base_state.get('risk_on_probability', 0.5)
            ai_conviction = intelligence_layer['conviction']
            
            if uncertainty_factors > 2:
                # High uncertainty reduces risk-on probability
                ai_risk_on = base_risk_on * 0.7
            elif ai_conviction > 0.7:
                # High conviction can increase risk-on probability
                ai_risk_on = min(0.9, base_risk_on * 1.2)
            else:
                ai_risk_on = base_risk_on
            
            intelligence_layer['ai_risk_on_probability'] = ai_risk_on
            intelligence_layer['risk_on_probability'] = ai_risk_on
        
        return intelligence_layer
    
    def validate_intelligent_consistency(self, state):
        """Validate intelligent market state for contradictions"""
        
        warnings = []
        
        # Check AI vs base state consistency
        if 'ai_allowed_exposure' in state and 'allowed_exposure' in state:
            ai_exposure = state['ai_allowed_exposure']
            final_exposure = state['allowed_exposure']
            
            if abs(ai_exposure - final_exposure) > 20:
                warnings.append(f"⚠️ LARGE AI OVERRIDE: AI recommends {ai_exposure:.1f}% vs base {final_exposure:.1f}%")
        
        # Check conviction vs uncertainty
        conviction = state.get('conviction', 0.5)
        beliefs = state.get('beliefs', {})
        uncertainty_count = len(beliefs.get('uncertainty_factors', []))
        
        if conviction > 0.8 and uncertainty_count > 2:
            warnings.append("⚠️ CONTRADICTION: High conviction despite multiple uncertainties")
        
        # Check regime consistency
        base_regime = state.get('macro_regime', 'neutral')
        ai_regime = state.get('regime_ai', 'neutral')
        
        if base_regime != ai_regime:
            warnings.append(f"⚠️ REGIME MISMATCH: Base={base_regime}, AI={ai_regime}")
        
        # Print warnings
        for warning in warnings:
            print(warning)
        
        if not warnings:
            print("✅ Intelligent state consistency validated")
        
        state['consistency_warnings'] = warnings
    
    def save_intelligent_state(self, state):
        """Save intelligent market state"""
        
        # Convert to DataFrame for parquet storage
        df = pd.DataFrame([state])
        
        # Handle complex objects for parquet
        parquet_state = state.copy()
        
        # Convert datetime objects first
        if 'date' in parquet_state and isinstance(parquet_state['date'], datetime):
            parquet_state['date'] = parquet_state['date']
        elif 'date' not in parquet_state:
            parquet_state['date'] = datetime.now()
        
        if 'intelligence_timestamp' in parquet_state and isinstance(parquet_state['intelligence_timestamp'], datetime):
            parquet_state['intelligence_timestamp_str'] = parquet_state['intelligence_timestamp'].isoformat()
            del parquet_state['intelligence_timestamp']
        
        # Convert complex objects to JSON strings for parquet
        complex_fields = ['beliefs', 'actions', 'narrative', 'valuation_assessment', 
                         'bayesian_fusion', 'learning_status', 'system_health', 'consistency_warnings']
        
        for field in complex_fields:
            if field in parquet_state and isinstance(parquet_state[field], (dict, list)):
                parquet_state[field] = json.dumps(parquet_state[field], default=str)
        
        # Create parquet DataFrame
        parquet_df = pd.DataFrame([parquet_state])
        
        # Ensure data types
        for col, dtype in MARKET_STATE_SCHEMA.items():
            if col in parquet_df.columns:
                if dtype.startswith('float'):
                    parquet_df[col] = pd.to_numeric(parquet_df[col], errors='coerce')
                elif dtype == 'string':
                    parquet_df[col] = parquet_df[col].astype(str)
                elif dtype.startswith('datetime'):
                    parquet_df[col] = pd.to_datetime(parquet_df[col])
        
        # Save parquet
        os.makedirs(os.path.dirname(self.intelligence_output_path), exist_ok=True)
        
        if os.path.exists(self.intelligence_output_path):
            try:
                existing_df = pd.read_parquet(self.intelligence_output_path)
                cutoff_date = datetime.now() - timedelta(days=90)
                existing_df = existing_df[existing_df['date'] >= cutoff_date]
                
                combined_df = pd.concat([existing_df, parquet_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                combined_df = combined_df.sort_values('date')
                
                combined_df.to_parquet(self.intelligence_output_path, index=False)
            except Exception as e:
                print(f"⚠️ Error appending to existing data: {e}")
                parquet_df.to_parquet(self.intelligence_output_path, index=False)
        else:
            parquet_df.to_parquet(self.intelligence_output_path, index=False)
        
        # Save beliefs separately as JSON for easy access
        if 'beliefs' in state:
            beliefs_data = {
                'timestamp': state['date'].isoformat() if isinstance(state.get('date'), datetime) else datetime.now().isoformat(),
                'beliefs': state['beliefs'],
                'actions': state.get('actions', {}),
                'conviction': state.get('conviction', 0.5),
                'regime': state.get('regime_ai', state.get('macro_regime', 'neutral')),
                'system_health': state.get('system_health', {})
            }
            
            # Convert any datetime objects to strings
            def convert_for_json(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_for_json(item) for item in obj]
                else:
                    return obj
            
            beliefs_data = convert_for_json(beliefs_data)
            
            with open(self.beliefs_output_path, 'w') as f:
                json.dump(beliefs_data, f, indent=2, default=str)
        
        print(f"💾 Intelligent market state saved to: {self.intelligence_output_path}")
        print(f"💾 Market beliefs saved to: {self.beliefs_output_path}")
    
    def run_intelligent_update(self):
        """Main execution with intelligence integration"""
        
        print("🧠 INTELLIGENT MARKET STATE SPINE - AI INTEGRATION")
        print("=" * 70)
        
        # Compute intelligent market state
        state = self.compute_intelligent_market_state()
        
        # Print intelligent summary
        print("\n📊 INTELLIGENT MARKET STATE SUMMARY")
        print("-" * 50)
        print(f"Base Regime: {state.get('macro_regime', 'unknown').title()}")
        
        if state.get('intelligence_status') == 'active':
            print(f"AI Regime: {state.get('regime_ai', 'unknown').title()}")
            print(f"AI Conviction: {state.get('conviction', 0):.1%}")
            
            beliefs = state.get('beliefs', {})
            if 'market_beliefs' in beliefs:
                market_stance = beliefs['market_beliefs'].get('stance', 'Unknown')
                print(f"AI Market Stance: {market_stance}")
            
            actions = state.get('actions', {})
            if 'primary_action' in actions:
                print(f"AI Primary Action: {actions['primary_action']}")
            
            if 'ai_allowed_exposure' in state:
                print(f"AI Recommended Exposure: {state['ai_allowed_exposure']:.1f}%")
                print(f"Final Blended Exposure: {state['allowed_exposure']:.1f}%")
            
            system_health = state.get('system_health', {})
            if 'grade' in system_health:
                print(f"AI System Health: {system_health['grade']} ({system_health.get('overall_score', 0):.2f})")
        else:
            print(f"AI Status: {state.get('intelligence_status', 'unknown')}")
        
        print(f"Risk-On Probability: {state.get('risk_on_probability', 0):.1%}")
        print(f"Market Health: {state.get('health_score', 0):.1%}")
        print(f"Confidence: {state.get('confidence', 0):.1%}")
        
        # Show consistency warnings
        warnings = state.get('consistency_warnings', [])
        if warnings:
            print(f"\n⚠️ CONSISTENCY WARNINGS:")
            for warning in warnings:
                print(f"  {warning}")
        
        print(f"\n✅ Intelligent Market State operational")
        return state

if __name__ == "__main__":
    main()

# =========================== MAIN EXECUTION ===========================

def main():
    """Main execution with intelligence integration"""
    
    # Try intelligent engine first
    try:
        intelligent_engine = IntelligentUnifiedStateManager()
        state = intelligent_engine.run_intelligent_update()
        return state
    except Exception as e:
        print(f"⚠️ Intelligent engine failed: {e}")
        print("🔄 Falling back to basic market state engine...")
        
        # Fallback to basic engine
        basic_engine = UnifiedStateManager()
        state = basic_engine.run()
        return state

if __name__ == "__main__":
    main()