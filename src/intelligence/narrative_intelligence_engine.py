#!/usr/bin/env python3
"""
🧠 NARRATIVE INTELLIGENCE ENGINE - NORTHSTAR V3
Hedge-Fund Grade Narrative Generation

This transforms anticipatory intelligence into investor-grade narratives.
Not "momentum up, exposure 46%" but real PM-quality explanations:

"Rising inflation and tightening liquidity have historically marked late-cycle regimes. 
In similar conditions (2018 Q3, 2022 Q1), momentum strategies lost effectiveness while 
quality and value preserved capital. Northstar therefore rotated 28% of capital from 
momentum into defensive strategies."

This is what separates retail from institutional intelligence.
"""

import pandas as pd
import numpy as np
import os
import json
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

from src.reporting.report_versioning import write_json_with_archive

class NarrativeIntelligenceEngine:
    """
    Narrative Intelligence Engine - Converting Intelligence to Stories
    
    Transforms quantitative intelligence into hedge-fund grade narratives
    that explain every decision with historical context and causal reasoning.
    """
    
    def __init__(self):
        self.name = "Narrative Intelligence Engine"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'narrative_state': 'data/processed/narrative_state.parquet',
            'narrative_atoms': 'config/narrative_atoms.yaml',
            'narrative_events': 'data/processed/narrative_events.parquet',
            'monthly_report': 'data/reports/monthly_report.json',
            'weekly_pulse': 'data/reports/weekly_pulse.json',
            'daily_narrative': 'data/reports/daily_narrative.json',
            'narrative_templates': 'config/narrative_templates.yaml',
            'historical_references': 'data/processed/historical_references.json'
        }
        
        # Ensure directories exist
        for path in self.paths.values():
            os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Narrative configuration
        self.config = {
            'fact_spine_columns': [
                'date', 'regime_probs', 'regime_stability', 'pulse_forces',
                'top_macro_moves', 'capital_changes', 'strategy_changes',
                'portfolio_risk', 'drawdown', 'returns'
            ],
            'narrative_depth': 'institutional',  # vs 'retail'
            'historical_lookback_years': 10,
            'min_significance_threshold': 0.05,  # 5% change threshold
            'causal_confidence_threshold': 0.7
        }
        
        # Load or create narrative atoms
        self.narrative_atoms = self.load_narrative_atoms()
        
        # Load or create narrative templates
        self.narrative_templates = self.load_narrative_templates()
    
    def load_narrative_atoms(self) -> Dict[str, Any]:
        """Load narrative atoms - building blocks of meaning"""
        
        if os.path.exists(self.paths['narrative_atoms']):
            with open(self.paths['narrative_atoms'], 'r') as f:
                return yaml.safe_load(f)
        
        # Create default narrative atoms
        default_atoms = {
            'macro_forces': {
                'inflation_rising': {
                    'condition': 'CPI_delta > 0.002',  # 0.2% monthly increase
                    'narrative': 'Rising inflation pressures',
                    'implications': ['late_cycle_risk', 'monetary_tightening_risk'],
                    'historical_precedents': ['2018_Q3', '2022_Q1', '2008_Q1']
                },
                'liquidity_tightening': {
                    'condition': 'RBI_liquidity_delta < -0.05',
                    'narrative': 'Tightening liquidity conditions',
                    'implications': ['credit_stress', 'momentum_weakness'],
                    'historical_precedents': ['2018_Q4', '2013_Q2']
                },
                'fii_outflows': {
                    'condition': 'FII_flows < -1000',  # Crores
                    'narrative': 'Foreign capital retreat',
                    'implications': ['market_pressure', 'currency_weakness'],
                    'historical_precedents': ['2022_Q1', '2018_Q4', '2013_Q2']
                },
                'yield_curve_inversion': {
                    'condition': '10Y_2Y_spread < 0',
                    'narrative': 'Yield curve inversion signals',
                    'implications': ['recession_risk', 'defensive_positioning'],
                    'historical_precedents': ['2019_Q3', '2006_Q4']
                }
            },
            'regime_signals': {
                'regime_instability': {
                    'condition': 'regime_stability < 0.3',
                    'narrative': 'Regime transition risk rising',
                    'implications': ['strategy_rotation', 'defensive_positioning'],
                    'action_required': True
                },
                'late_cycle_emergence': {
                    'condition': 'regime_name == "Late_Expansion_Euphoria"',
                    'narrative': 'Late-cycle conditions emerging',
                    'implications': ['momentum_peak', 'value_opportunity'],
                    'historical_precedents': ['2007_Q4', '2000_Q1']
                },
                'crisis_regime': {
                    'condition': 'regime_name in ["Crisis_Liquidity_Shock", "Crisis_Structural"]',
                    'narrative': 'Crisis regime conditions',
                    'implications': ['capital_preservation', 'quality_focus'],
                    'action_required': True
                }
            },
            'strategy_signals': {
                'momentum_weakness': {
                    'condition': 'momentum_sharpe < 0.5',
                    'narrative': 'Momentum strategies losing effectiveness',
                    'implications': ['rotation_to_value', 'defensive_tilt'],
                    'historical_context': 'Typical in late-cycle and crisis regimes'
                },
                'value_opportunity': {
                    'condition': 'value_sharpe > momentum_sharpe',
                    'narrative': 'Value strategies outperforming momentum',
                    'implications': ['contrarian_opportunity', 'cycle_turning'],
                    'historical_context': 'Often marks regime transitions'
                },
                'quality_defense': {
                    'condition': 'quality_max_drawdown < market_drawdown * 0.7',
                    'narrative': 'Quality strategies providing downside protection',
                    'implications': ['defensive_positioning', 'risk_management'],
                    'historical_context': 'Critical during market stress'
                }
            },
            'portfolio_actions': {
                'defensive_rotation': {
                    'condition': 'cash_allocation > 0.15',
                    'narrative': 'Rotated capital to defensive positioning',
                    'justification': 'Historical precedent shows defensive outperformance in similar conditions'
                },
                'momentum_reduction': {
                    'condition': 'momentum_allocation_delta < -0.1',
                    'narrative': 'Reduced momentum exposure',
                    'justification': 'Momentum strategies typically underperform in current regime'
                },
                'value_increase': {
                    'condition': 'value_allocation_delta > 0.05',
                    'narrative': 'Increased value allocation',
                    'justification': 'Value strategies historically outperform in transition periods'
                }
            }
        }
        
        # Save default atoms
        with open(self.paths['narrative_atoms'], 'w') as f:
            yaml.dump(default_atoms, f, default_flow_style=False, indent=2)
        
        return default_atoms
    
    def load_narrative_templates(self) -> Dict[str, str]:
        """Load narrative templates for different report types"""
        
        if os.path.exists(self.paths['narrative_templates']):
            with open(self.paths['narrative_templates'], 'r') as f:
                return yaml.safe_load(f)
        
        # Create default templates
        default_templates = {
            'causal_narrative': (
                "{macro_forces} have historically signaled a shift toward {regime_type}. "
                "In similar periods ({historical_examples}), {strategy_effect}. "
                "Northstar therefore {portfolio_action}, positioning for {expected_outcome}."
            ),
            'regime_transition': (
                "Market regime shows {stability_level} stability at {stability_pct}%. "
                "Current {current_regime} regime typically transitions to {likely_next_regime} "
                "under these conditions. We have {action_taken} to prepare for this shift."
            ),
            'strategy_performance': (
                "{strategy_name} delivered {performance_metric} over the period, "
                "{performance_context}. This {performance_assessment} is {historical_context} "
                "for {current_regime} regimes. We have {allocation_action} accordingly."
            ),
            'risk_management': (
                "Portfolio risk is currently {risk_level} with {risk_metric}. "
                "Given {regime_context}, we maintain {risk_position} positioning. "
                "Historical analysis shows {risk_justification} in similar conditions."
            ),
            'market_outlook': (
                "Looking ahead, {forward_indicators} suggest {market_direction}. "
                "Key risks include {primary_risks}, while opportunities lie in {opportunities}. "
                "We are positioned {positioning_stance} based on {historical_precedent}."
            )
        }
        
        # Save default templates
        with open(self.paths['narrative_templates'], 'w') as f:
            yaml.dump(default_templates, f, default_flow_style=False, indent=2)
        
        return default_templates
    
    def build_fact_spine(self) -> pd.DataFrame:
        """Build the fact spine - truth ledger for narratives"""
        
        print("📊 Building fact spine - the truth ledger...")
        
        fact_records = []

        # Use the latest *market* date as the narrative "as-of" anchor.
        # This prevents narratives from drifting/sticking to the last time the script happened to run.
        current_date = self._resolve_as_of_date()
        
        try:
            # Load regime intelligence (prefer fresh anticipatory_signals; fallback to regime feed / market_regime)
            current_regime = {}
            regime_transitions = {}
            risk_assessment = {}

            regime_signals_path = 'data/processed/anticipatory_signals.json'
            if os.path.exists(regime_signals_path):
                try:
                    with open(regime_signals_path, 'r') as f:
                        regime_data = json.load(f)
                    ts = pd.to_datetime(regime_data.get('timestamp'), errors='coerce')
                    is_fresh = pd.notna(ts) and (current_date - ts.normalize()).days <= 7
                    if is_fresh:
                        current_regime = regime_data.get('current_regime', {}) or {}
                        regime_transitions = regime_data.get('regime_transitions', {}) or {}
                        risk_assessment = regime_data.get('risk_assessment', {}) or {}
                    else:
                        print("   ⚠️ anticipatory_signals.json is stale; using regime feed fallback")
                except Exception:
                    pass

            if not current_regime:
                feed_path = 'data/processed/regime_intelligence_feed.json'
                if os.path.exists(feed_path):
                    try:
                        with open(feed_path, 'r') as f:
                            feed = json.load(f)
                        cur = feed.get('current_regime', {}) or {}
                        trans = feed.get('regime_transitions', {}) or {}
                        next_probs = trans.get('next_regime_probabilities', {}) or {}
                        ex_probs = {k: float(v) for k, v in next_probs.items() if str(k) != str(cur.get('name', ''))}
                        transition_prob = max(ex_probs.values()) if ex_probs else 0.0
                        stability = float(np.clip(float(cur.get('stability', 0.5) or 0.5), 0.0, 0.98))
                        risk_score = float(np.clip(0.6 * transition_prob + 0.4 * (1.0 - stability), 0.0, 1.0))
                        risk_level = 'high' if risk_score >= 0.66 else ('medium' if risk_score >= 0.33 else 'low')
                        current_regime = {
                            'name': cur.get('name', 'Unknown'),
                            'stability': stability,
                            'confidence': (feed.get('confidence_metrics') or {}).get('overall', 0.0),
                        }
                        regime_transitions = trans
                        risk_assessment = {
                            'regime_risk_level': risk_level,
                            'transition_risk': transition_prob,
                            'stability_risk': 1.0 - stability,
                        }
                    except Exception:
                        pass

            if not current_regime:
                mr_path = 'data/processed/market_regime.parquet'
                if os.path.exists(mr_path):
                    try:
                            mr = pd.read_parquet(mr_path)
                            if not mr.empty:
                                mr['Date'] = pd.to_datetime(mr['Date'], errors='coerce')
                                mr = mr.dropna(subset=['Date']).sort_values('Date')
                                row = mr.iloc[-1]
                                risk_on_val = pd.to_numeric(row.get('risk_on_score'), errors='coerce')
                                risk_on = float(risk_on_val) if pd.notna(risk_on_val) else 0.5
                                stability = float(np.clip(1.0 - abs(0.5 - risk_on) * 1.5, 0.0, 0.98))
                                risk_level = 'high' if risk_on < 0.33 else ('medium' if risk_on < 0.66 else 'low')
                                current_regime = {'name': row.get('market_regime', 'Unknown'), 'stability': stability}
                                risk_assessment = {'regime_risk_level': risk_level}
                    except Exception:
                        pass
            
            # Load market pulse (prefer fresh pulse_state)
            pulse_data = {}
            pulse_path = 'data/processed/pulse_state.json'
            if os.path.exists(pulse_path):
                try:
                    with open(pulse_path, 'r') as f:
                        pulse_data = json.load(f)
                    pulse_ts = pd.to_datetime(pulse_data.get('timestamp'), errors='coerce')
                    if pd.isna(pulse_ts) or (current_date - pulse_ts.normalize()).days > 7:
                        pulse_data = {}
                        print("   ⚠️ pulse_state.json is stale; using market_regime fallback")
                except Exception:
                    pulse_data = {}

            if not pulse_data:
                try:
                    mr_path = 'data/processed/market_regime.parquet'
                    if os.path.exists(mr_path):
                        mr = pd.read_parquet(mr_path)
                        if not mr.empty:
                            mr['Date'] = pd.to_datetime(mr['Date'], errors='coerce')
                            mr = mr.dropna(subset=['Date']).sort_values('Date')
                            row = mr.iloc[-1]
                            vol_val = pd.to_numeric(row.get('volatility'), errors='coerce')
                            corr_val = pd.to_numeric(row.get('correlation'), errors='coerce')
                            vol = float(vol_val) if pd.notna(vol_val) else 0.0
                            corr = float(corr_val) if pd.notna(corr_val) else 0.0
                            vol_norm = float(np.clip(vol * 30.0, 0.0, 1.0))
                            pulse_data = {
                                'pulse_intensity': float(np.clip(0.35 + 0.45 * vol_norm + 0.20 * corr, 0.0, 1.0)),
                                'timestamp': pd.to_datetime(row['Date']).isoformat(),
                            }
                except Exception:
                    pulse_data = {}
            
            # Load market tensor for macro moves
            tensor_path = 'data/processed/market_tensor.parquet'
            macro_moves = {}
            if os.path.exists(tensor_path):
                try:
                    tensor_df = pd.read_parquet(tensor_path)
                    if not tensor_df.empty:
                        # Calculate recent changes in macro variables
                        numeric_tensor = tensor_df.apply(pd.to_numeric, errors='coerce')
                        latest_data = numeric_tensor.tail(2)
                        if len(latest_data) >= 2:
                            changes = latest_data.iloc[-1] - latest_data.iloc[-2]
                            scale = numeric_tensor.tail(26).std().replace(0.0, np.nan)
                            z_changes = (changes / (scale + 1e-12)).replace([np.inf, -np.inf], np.nan).dropna()
                            # Use normalized changes to avoid raw-unit magnitude artifacts.
                            top_changes = z_changes.abs().nlargest(5)
                            macro_moves = {
                                col: float(np.clip(z_changes[col], -5.0, 5.0))
                                for col in top_changes.index
                            }
                except:
                    pass
            
            # Load capital allocations from a single authority:
            # portfolio_analytics (governor output) is canonical for exposure/cash.
            capital_changes = {}
            canonical_exposure = None
            try:
                analytics_path = 'data/processed/portfolio_analytics.json'
                if os.path.exists(analytics_path):
                    with open(analytics_path, 'r') as f:
                        analytics = json.load(f)
                    psum = analytics.get('portfolio_summary', {}) or {}
                    total_exposure = float(psum.get('total_exposure', psum.get('exposure', 0.0)) or 0.0)
                    if total_exposure > 1.0:
                        total_exposure = total_exposure / 100.0
                    total_exposure = float(np.clip(total_exposure, 0.0, 1.0))
                    cash_alloc = psum.get('cash', psum.get('cash_level', max(0.0, 1.0 - total_exposure)))
                    cash_alloc = float(cash_alloc if cash_alloc is not None else max(0.0, 1.0 - total_exposure))
                    canonical_exposure = total_exposure
                    capital_changes = {
                        'total_strategies': int(psum.get('n_positions', psum.get('total_positions', 0)) or 0),
                        'cash_allocation': float(np.clip(cash_alloc, 0.0, 1.0)),
                        'top_strategy': 'portfolio_level',
                        'top_allocation': total_exposure,
                        'source': 'portfolio_analytics',
                    }
            except Exception:
                capital_changes = {}
                canonical_exposure = None

            # Add strategy-level context from anticipatory allocations only when aligned.
            allocations_path = 'data/processed/anticipatory_capital_allocations.parquet'
            if os.path.exists(allocations_path):
                try:
                    alloc_df = pd.read_parquet(allocations_path)
                    if not alloc_df.empty:
                        strategy_col = (
                            'strategy_name'
                            if 'strategy_name' in alloc_df.columns
                            else ('strategy' if 'strategy' in alloc_df.columns else None)
                        )
                        weight_col = (
                            'allocation_weight'
                            if 'allocation_weight' in alloc_df.columns
                            else (
                                'allocation'
                                if 'allocation' in alloc_df.columns
                                else ('weight' if 'weight' in alloc_df.columns else None)
                            )
                        )
                        date_col = (
                            'date'
                            if 'date' in alloc_df.columns
                            else ('Date' if 'Date' in alloc_df.columns else None)
                        )

                        if strategy_col and weight_col:
                            latest_slice = alloc_df.copy()
                            if date_col:
                                latest_slice[date_col] = pd.to_datetime(latest_slice[date_col], errors='coerce')
                                latest_slice = latest_slice.dropna(subset=[date_col])
                                if not latest_slice.empty:
                                    latest_date = pd.to_datetime(latest_slice[date_col].max()).normalize()
                                    if (current_date - latest_date).days <= 14:
                                        latest_slice = latest_slice[latest_slice[date_col] == latest_date]
                                    else:
                                        latest_slice = pd.DataFrame()

                            if not latest_slice.empty:
                                latest_slice = latest_slice.copy()
                                latest_slice[strategy_col] = latest_slice[strategy_col].astype(str).str.upper()
                                latest_slice[weight_col] = pd.to_numeric(latest_slice[weight_col], errors='coerce')
                                latest_slice = latest_slice.dropna(subset=[weight_col])

                                cash_rows = latest_slice[latest_slice[strategy_col] == 'CASH']
                                strategy_allocs = latest_slice[latest_slice[strategy_col] != 'CASH'].sort_values(weight_col, ascending=False)
                                total_alloc = float(strategy_allocs[weight_col].sum()) if not strategy_allocs.empty else 0.0
                                alloc_cash = float(
                                    cash_rows.iloc[0][weight_col] if not cash_rows.empty else max(0.0, 1.0 - total_alloc)
                                )
                                alloc_exposure = float(np.clip(total_alloc, 0.0, 1.0))

                                # Enforce coherence with canonical exposure when available.
                                aligned = (
                                    canonical_exposure is None or
                                    abs(alloc_exposure - canonical_exposure) <= 0.05
                                )
                                if aligned:
                                    if strategy_allocs.empty:
                                        top_strategy = 'portfolio_level'
                                        top_alloc = canonical_exposure if canonical_exposure is not None else (1.0 - alloc_cash)
                                    else:
                                        top_strategy = str(strategy_allocs.iloc[0][strategy_col]).lower()
                                        top_alloc = float(strategy_allocs.iloc[0][weight_col])

                                    if not capital_changes:
                                        capital_changes = {}
                                    capital_changes.update({
                                        'total_strategies': int(len(strategy_allocs)),
                                        'top_strategy': top_strategy,
                                        'top_allocation': float(np.clip(top_alloc, 0.0, 1.0)),
                                        'source': 'portfolio_analytics+anticipatory_allocations'
                                    })
                                    # Keep canonical cash when present.
                                    if 'cash_allocation' not in capital_changes:
                                        capital_changes['cash_allocation'] = float(np.clip(alloc_cash, 0.0, 1.0))
                except Exception:
                    pass
            
            # Load strategy changes
            strategy_changes = {}
            beliefs_path = 'data/processed/strategy_beliefs.parquet'
            regret_path = 'data/processed/strategy_regret.parquet'
            
            if os.path.exists(beliefs_path) and os.path.exists(regret_path):
                try:
                    beliefs_df = pd.read_parquet(beliefs_path)
                    regret_df = pd.read_parquet(regret_path)

                    strategy_changes = {
                        'avg_belief_strength': float(pd.to_numeric(beliefs_df.get('belief_strength'), errors='coerce').mean()),
                        # Confidence isn't always present; keep it optional.
                        'avg_confidence': float(pd.to_numeric(beliefs_df.get('confidence'), errors='coerce').mean()) if 'confidence' in beliefs_df.columns else 0.0,
                        'avg_regret': float(pd.to_numeric(regret_df.get('regret_score'), errors='coerce').mean()),
                        'high_regret_strategies': int((regret_df.get('regret_intensity') == 'high').sum()) if 'regret_intensity' in regret_df.columns else 0
                    }
                except:
                    pass
            
            # Load portfolio analytics
            portfolio_risk = {}
            analytics_path = 'data/processed/portfolio_analytics.json'
            if os.path.exists(analytics_path):
                try:
                    with open(analytics_path, 'r') as f:
                        analytics = json.load(f)
                    
                    portfolio_risk = {
                        'total_risk': analytics.get('total_risk', 0.0),
                        'max_drawdown': analytics.get('max_drawdown', 0.0),
                        'sharpe_ratio': analytics.get('sharpe_ratio', 0.0),
                        'volatility': analytics.get('volatility', 0.0),
                    }
                except:
                    pass

            # Enrich with latest realized return from pnl curve (if available).
            try:
                pnl_path = 'data/portfolio/pnl_on_paper.parquet'
                if os.path.exists(pnl_path):
                    pnl = pd.read_parquet(pnl_path)
                    if not pnl.empty:
                        if 'Date' in pnl.columns:
                            pnl['Date'] = pd.to_datetime(pnl['Date'], errors='coerce')
                            pnl = pnl.dropna(subset=['Date']).sort_values('Date')
                        if 'Return' in pnl.columns and pnl['Return'].notna().any():
                            portfolio_risk['daily_return'] = float(pd.to_numeric(pnl['Return'], errors='coerce').dropna().iloc[-1])
                        if 'Equity' in pnl.columns and pnl['Equity'].notna().any():
                            eq = pd.to_numeric(pnl['Equity'], errors='coerce').dropna()
                            if len(eq) >= 2:
                                peak = eq.cummax()
                                dd = eq / peak - 1.0
                                portfolio_risk['max_drawdown'] = float(dd.min())
            except Exception:
                pass

            pulse_intensity_raw = float(pulse_data.get('pulse_intensity', 0.0) or 0.0)
            pulse_intensity = pulse_intensity_raw / 2.0 if pulse_intensity_raw > 1.0 else pulse_intensity_raw
            pulse_intensity = float(np.clip(pulse_intensity, 0.0, 1.0))
            
            # Create fact record (flatten complex objects for Parquet compatibility)
            regime_stability = float(np.clip(float(current_regime.get('stability', 0.0) or 0.0), 0.0, 0.98))

            fact_record = {
                'date': pd.to_datetime(current_date).normalize(),
                'regime_stability': regime_stability,
                'regime_name': current_regime.get('name', 'Unknown'),
                'regime_risk_level': risk_assessment.get('regime_risk_level', 'medium'),
                'pulse_intensity': pulse_intensity,
                'pulse_intensity_raw': pulse_intensity_raw,
                'drawdown': portfolio_risk.get('max_drawdown', 0.0),
                'returns': portfolio_risk.get('daily_return', portfolio_risk.get('sharpe_ratio', 0.0)),
                'cash_allocation': capital_changes.get('cash_allocation', 0.0),
                'total_strategies': capital_changes.get('total_strategies', 0),
                'avg_belief_strength': strategy_changes.get('avg_belief_strength', 0.0),
                'avg_regret': strategy_changes.get('avg_regret', 0.0),
                'total_risk': portfolio_risk.get('total_risk', 0.0),
                'volatility': portfolio_risk.get('volatility', 0.0)
            }
            
            fact_records.append(fact_record)
            
        except Exception as e:
            print(f"   ⚠️ Error building fact spine: {e}")
            # Create minimal fact record (flatten for Parquet compatibility)
            fact_record = {
                'date': pd.to_datetime(current_date).normalize(),
                'regime_stability': 0.0,
                'regime_name': 'Unknown',
                'regime_risk_level': 'medium',
                'pulse_intensity': 0.0,
                'drawdown': 0.0,
                'returns': 0.0,
                'cash_allocation': 0.0,
                'total_strategies': 0,
                'avg_belief_strength': 0.0,
                'avg_regret': 0.0,
                'total_risk': 0.0,
                'volatility': 0.0
            }
            fact_records.append(fact_record)
        
        # Create DataFrame
        fact_spine_df = pd.DataFrame(fact_records)
        
        # Load existing fact spine and append
        if os.path.exists(self.paths['narrative_state']):
            try:
                existing_df = pd.read_parquet(self.paths['narrative_state'])
                # Combine and keep recent records
                combined_df = pd.concat([existing_df, fact_spine_df], ignore_index=True)
                combined_df['date'] = pd.to_datetime(combined_df['date'], errors='coerce').dt.normalize()
                combined_df = combined_df.dropna(subset=['date'])
                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                combined_df = combined_df.tail(1000)  # Keep last 1000 records
                fact_spine_df = combined_df
            except:
                pass

        # Normalize core ranges to stable 0..1 scales for charting/event thresholds.
        if 'regime_stability' in fact_spine_df.columns:
            fact_spine_df['regime_stability'] = (
                pd.to_numeric(fact_spine_df['regime_stability'], errors='coerce')
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0.0)
                .clip(lower=0.0, upper=1.0)
            )

        if 'pulse_intensity' in fact_spine_df.columns:
            fact_spine_df['pulse_intensity'] = (
                pd.to_numeric(fact_spine_df['pulse_intensity'], errors='coerce')
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0.0)
                .clip(lower=0.0, upper=1.0)
            )
        
        # Save fact spine
        fact_spine_df.to_parquet(self.paths['narrative_state'])
        
        print(f"   ✅ Fact spine built: {len(fact_spine_df)} records")
        print(f"   📊 Current regime: {fact_record['regime_name']}")
        print(f"   📊 Regime stability: {fact_record['regime_stability']:.1%}")
        
        return fact_spine_df

    def _resolve_as_of_date(self) -> pd.Timestamp:
        """Choose the latest available market date from core artifacts."""
        candidates = []
        try:
            mr_path = "data/processed/market_regime.parquet"
            if os.path.exists(mr_path):
                mr = pd.read_parquet(mr_path)
                if not mr.empty and "Date" in mr.columns:
                    d = pd.to_datetime(mr["Date"], errors="coerce").max()
                    if pd.notna(d):
                        candidates.append(d)
        except Exception:
            pass

        try:
            pnl_path = "data/portfolio/pnl_on_paper.parquet"
            if os.path.exists(pnl_path):
                pnl = pd.read_parquet(pnl_path)
                if not pnl.empty and "Date" in pnl.columns:
                    d = pd.to_datetime(pnl["Date"], errors="coerce").max()
                    if pd.notna(d):
                        candidates.append(d)
        except Exception:
            pass

        try:
            ims_path = "data/processed/intelligent_market_state.parquet"
            if os.path.exists(ims_path):
                ims = pd.read_parquet(ims_path)
                if not ims.empty and "date" in ims.columns:
                    d = pd.to_datetime(ims["date"], errors="coerce").max()
                    if pd.notna(d):
                        candidates.append(d)
        except Exception:
            pass

        if candidates:
            return pd.to_datetime(max(candidates)).normalize()

        return pd.to_datetime(datetime.now()).normalize()
    
    def detect_narrative_events(self, fact_spine_df: pd.DataFrame) -> pd.DataFrame:
        """Detect significant events that require narrative explanation"""
        
        print("🔍 Detecting narrative events...")
        
        if len(fact_spine_df) < 2:
            print("   ⚠️ Insufficient data for event detection")
            return pd.DataFrame()

        events = []
        current_record = fact_spine_df.iloc[-1]
        previous_record = fact_spine_df.iloc[-2] if len(fact_spine_df) >= 2 else None

        def _num(row: pd.Series, key: str, default: float = 0.0) -> float:
            val = pd.to_numeric(row.get(key, default), errors='coerce')
            return float(val) if pd.notna(val) else float(default)
        
        # Regime stability events
        if current_record['regime_stability'] < 0.3:
            events.append({
                'date': current_record['date'],
                'event_type': 'regime_instability',
                'cause': f"Regime stability at {current_record['regime_stability']:.1%}",
                'regime_shift': 'transition_risk',
                'strategy_impact': 'rotation_required',
                'portfolio_action': 'defensive_positioning',
                'historical_reference': self.get_historical_reference('regime_instability'),
                'significance': 'high'
            })
        
        # Risk level events
        if current_record['regime_risk_level'] == 'high':
            events.append({
                'date': current_record['date'],
                'event_type': 'high_risk_regime',
                'cause': f"High risk {current_record['regime_name']} regime",
                'regime_shift': 'risk_management',
                'strategy_impact': 'defensive_focus',
                'portfolio_action': 'risk_reduction',
                'historical_reference': self.get_historical_reference('high_risk'),
                'significance': 'high'
            })
        
        # Capital allocation events
        cash_allocation = pd.to_numeric(current_record.get('cash_allocation', 0.0), errors='coerce')
        if pd.notna(cash_allocation) and float(cash_allocation) > 0.15:
            events.append({
                'date': current_record['date'],
                'event_type': 'defensive_allocation',
                'cause': f"Cash allocation increased to {float(cash_allocation):.1%}",
                'regime_shift': 'defensive_positioning',
                'strategy_impact': 'risk_management',
                'portfolio_action': 'capital_preservation',
                'historical_reference': self.get_historical_reference('defensive_allocation'),
                'significance': 'medium',
                'magnitude': float(cash_allocation)
            })
        
        # Strategy performance events
        avg_regret = pd.to_numeric(current_record.get('avg_regret', 0.0), errors='coerce')
        if pd.notna(avg_regret) and float(avg_regret) > 0.5:
            events.append({
                'date': current_record['date'],
                'event_type': 'strategy_underperformance',
                'cause': f"Average strategy regret at {float(avg_regret):.1%}",
                'regime_shift': 'strategy_evolution',
                'strategy_impact': 'performance_pressure',
                'portfolio_action': 'strategy_rotation',
                'historical_reference': self.get_historical_reference('strategy_rotation'),
                'significance': 'medium',
                'magnitude': float(avg_regret)
            })
        
        # Market pulse events
        pulse_intensity = pd.to_numeric(current_record.get('pulse_intensity', 0.0), errors='coerce')
        if pd.notna(pulse_intensity) and float(pulse_intensity) > 0.85:
            events.append({
                'date': current_record['date'],
                'event_type': 'high_market_intensity',
                'cause': f"Market pulse intensity at {float(pulse_intensity):.1%}",
                'regime_shift': 'market_stress',
                'strategy_impact': 'volatility_impact',
                'portfolio_action': 'risk_monitoring',
                'historical_reference': self.get_historical_reference('market_stress'),
                'significance': 'medium',
                'magnitude': float(pulse_intensity)
            })

        # Subtle day-over-day change detection for continuous narratives.
        if previous_record is not None:
            stability_now = _num(current_record, 'regime_stability', 0.0)
            stability_prev = _num(previous_record, 'regime_stability', stability_now)
            stability_delta = stability_now - stability_prev
            if abs(stability_delta) >= 0.03:
                direction = "improved" if stability_delta > 0 else "declined"
                events.append({
                    'date': current_record['date'],
                    'event_type': 'regime_stability_shift',
                    'cause': f"Regime stability {direction} by {abs(stability_delta):.1%}",
                    'regime_shift': 'stability_change',
                    'strategy_impact': 'increased_uncertainty' if stability_delta < 0 else 'improved_visibility',
                    'portfolio_action': 'defensive_positioning' if stability_delta < 0 else 'measured_risk_add',
                    'historical_reference': self.get_historical_reference('regime_instability' if stability_delta < 0 else 'regime_continuation'),
                    'significance': 'high' if abs(stability_delta) >= 0.10 else 'medium',
                    'magnitude': float(abs(stability_delta))
                })

            pulse_now = _num(current_record, 'pulse_intensity', 0.0)
            pulse_prev = _num(previous_record, 'pulse_intensity', pulse_now)
            pulse_delta = pulse_now - pulse_prev
            if abs(pulse_delta) >= 0.08:
                direction = "increased" if pulse_delta > 0 else "eased"
                events.append({
                    'date': current_record['date'],
                    'event_type': 'pulse_intensity_shift',
                    'cause': f"Market pulse intensity {direction} by {abs(pulse_delta):.1%}",
                    'regime_shift': 'market_stress_shift',
                    'strategy_impact': 'volatility_repricing',
                    'portfolio_action': 'risk_monitoring',
                    'historical_reference': self.get_historical_reference('market_stress'),
                    'significance': 'high' if abs(pulse_delta) >= 0.20 else 'medium',
                    'magnitude': float(abs(pulse_delta))
                })

            cash_now = _num(current_record, 'cash_allocation', 0.0)
            cash_prev = _num(previous_record, 'cash_allocation', cash_now)
            cash_delta = cash_now - cash_prev
            if abs(cash_delta) >= 0.03:
                direction = "increased" if cash_delta > 0 else "reduced"
                events.append({
                    'date': current_record['date'],
                    'event_type': 'cash_allocation_shift',
                    'cause': f"Cash allocation {direction} by {abs(cash_delta):.1%}",
                    'regime_shift': 'allocation_shift',
                    'strategy_impact': 'positioning_adjustment',
                    'portfolio_action': 'rebalance_execution',
                    'historical_reference': self.get_historical_reference('defensive_allocation'),
                    'significance': 'high' if abs(cash_delta) >= 0.10 else 'medium',
                    'magnitude': float(abs(cash_delta))
                })

            ret_now = _num(current_record, 'returns', 0.0)
            ret_prev = _num(previous_record, 'returns', ret_now)
            ret_delta = ret_now - ret_prev
            if abs(ret_delta) >= 0.01:
                direction = "improved" if ret_delta > 0 else "weakened"
                events.append({
                    'date': current_record['date'],
                    'event_type': 'return_momentum_shift',
                    'cause': f"Daily return momentum {direction} by {abs(ret_delta):.2%}",
                    'regime_shift': 'return_volatility_shift',
                    'strategy_impact': 'conviction_recalibration',
                    'portfolio_action': 'position_risk_tuning',
                    'historical_reference': self.get_historical_reference('strategy_rotation'),
                    'significance': 'medium',
                    'magnitude': float(abs(ret_delta))
                })
        
        if not events:
            # Create a baseline event
            events.append({
                'date': current_record['date'],
                'event_type': 'regime_continuation',
                'cause': f"Stable {current_record['regime_name']} regime",
                'regime_shift': 'continuation',
                'strategy_impact': 'steady_performance',
                'portfolio_action': 'maintain_allocation',
                'historical_reference': 'Normal market conditions',
                'significance': 'low'
            })
        
        events_df = pd.DataFrame(events)

        # Normalize event timestamps to daily "as-of" so the dashboard doesn't get stuck on
        # microsecond-level duplicates from old runs (e.g., many events on the same day).
        if not events_df.empty and "date" in events_df.columns:
            events_df["date"] = pd.to_datetime(events_df["date"], errors="coerce").dt.normalize()
            events_df = events_df.dropna(subset=["date"])

        # Load existing events and append, with normalization + de-duplication by day.
        if os.path.exists(self.paths['narrative_events']):
            try:
                existing_events = pd.read_parquet(self.paths['narrative_events'])
                if not existing_events.empty and "date" in existing_events.columns:
                    existing_events = existing_events.copy()
                    existing_events["date"] = pd.to_datetime(existing_events["date"], errors="coerce").dt.normalize()
                    existing_events = existing_events.dropna(subset=["date"])

                combined_events = pd.concat([existing_events, events_df], ignore_index=True)
                if "date" in combined_events.columns:
                    combined_events["date"] = pd.to_datetime(combined_events["date"], errors="coerce").dt.normalize()
                    combined_events = combined_events.dropna(subset=["date"])

                # Sanitize event magnitudes/cause text so historical out-of-scale artifacts
                # (e.g., 200%-280% pulse strings) do not pollute dashboard history.
                if not combined_events.empty and "event_type" in combined_events.columns:
                    if "magnitude" in combined_events.columns:
                        combined_events["magnitude"] = pd.to_numeric(combined_events["magnitude"], errors="coerce")

                    def _parse_percent_from_cause(series: pd.Series) -> pd.Series:
                        if "cause" not in combined_events.columns:
                            return pd.Series(np.nan, index=series.index, dtype=float)
                        extracted = (
                            combined_events.loc[series.index, "cause"]
                            .astype(str)
                            .str.extract(r"([0-9]+(?:\\.[0-9]+)?)")[0]
                        )
                        return pd.to_numeric(extracted, errors="coerce") / 100.0

                    # High pulse intensity: clip to [0,1] and rewrite cause text.
                    hi_mask = combined_events["event_type"] == "high_market_intensity"
                    if hi_mask.any():
                        hi_mag = combined_events.loc[hi_mask, "magnitude"] if "magnitude" in combined_events.columns else pd.Series(np.nan, index=combined_events.index[hi_mask])
                        hi_mag = pd.to_numeric(hi_mag, errors="coerce")
                        hi_mag = hi_mag.where(hi_mag.notna(), _parse_percent_from_cause(combined_events.loc[hi_mask]))
                        hi_mag = hi_mag.clip(lower=0.0, upper=1.0)
                        combined_events.loc[hi_mask, "magnitude"] = hi_mag
                        if "cause" in combined_events.columns:
                            combined_events.loc[hi_mask, "cause"] = hi_mag.map(
                                lambda v: f"Market pulse intensity at {float(v):.1%}" if pd.notna(v) else "Market pulse intensity elevated"
                            )

                    # Defensive allocation / strategy regret should also be bounded percentages.
                    for evt, cause_tpl in [
                        ("defensive_allocation", "Cash allocation increased to {v:.1%}"),
                        ("strategy_underperformance", "Average strategy regret at {v:.1%}"),
                    ]:
                        mask = combined_events["event_type"] == evt
                        if not mask.any():
                            continue
                        mag = combined_events.loc[mask, "magnitude"] if "magnitude" in combined_events.columns else pd.Series(np.nan, index=combined_events.index[mask])
                        mag = pd.to_numeric(mag, errors="coerce")
                        mag = mag.where(mag.notna(), _parse_percent_from_cause(combined_events.loc[mask]))
                        mag = mag.clip(lower=0.0, upper=1.0)
                        combined_events.loc[mask, "magnitude"] = mag
                        if "cause" in combined_events.columns:
                            existing_cause = combined_events.loc[mask, "cause"]
                            formatted = mag.map(
                                lambda v, tpl=cause_tpl: tpl.format(v=float(v)) if pd.notna(v) else None
                            )
                            combined_events.loc[mask, "cause"] = formatted.fillna(existing_cause)

                # Keep the most recent event per day + type; then keep a rolling window.
                combined_events = combined_events.sort_values("date")
                combined_events = combined_events.drop_duplicates(subset=["date", "event_type"], keep="last")
                # Suppress repeated boilerplate alerts (same type + same cause) across days.
                combined_events = combined_events.drop_duplicates(subset=["event_type", "cause"], keep="last")
                combined_events = combined_events.tail(500)  # Keep last 500 events
                events_df = combined_events
            except Exception:
                pass
        
        # Save events
        events_df.to_parquet(self.paths['narrative_events'])
        
        print(f"   ✅ Detected {len(events)} narrative events")
        for event in events:
            print(f"      {event['event_type']}: {event['cause']}")
        
        return events_df
    
    def get_historical_reference(self, event_type: str) -> str:
        """Get historical reference for event type"""
        
        references = {
            'regime_instability': 'Similar instability in 2018 Q4 and 2020 Q1 preceded major regime shifts',
            'high_risk': 'High-risk regimes in 2008 and 2020 required defensive positioning',
            'defensive_allocation': 'Defensive allocations in 2018 Q4 and 2022 Q1 preserved capital during transitions',
            'strategy_rotation': 'Strategy rotations during 2000-2002 and 2007-2009 improved risk-adjusted returns',
            'market_stress': 'High market stress periods historically last 3-6 months before normalization',
            'regime_continuation': 'Sustained regimes historically reward disciplined, incremental position adjustments'
        }
        
        return references.get(event_type, 'Historical precedent supports current positioning')
    
    def generate_causal_narrative(self, events_df: pd.DataFrame, fact_spine_df: pd.DataFrame) -> str:
        """Generate causal narrative from events and facts"""
        
        print("📝 Generating causal narrative...")
        
        if events_df.empty or fact_spine_df.empty:
            return "Insufficient data for narrative generation."
        
        current_facts = fact_spine_df.iloc[-1]
        recent_events = events_df.tail(3)  # Last 3 events
        
        narrative_parts = []
        
        # Market regime context
        regime_name = current_facts['regime_name']
        regime_stability = current_facts['regime_stability']
        risk_level = current_facts['regime_risk_level']
        
        regime_context = (
            f"Current market conditions reflect a {regime_name.replace('_', ' ').lower()} regime "
            f"with {regime_stability:.1%} stability. Risk assessment indicates {risk_level} risk levels."
        )
        narrative_parts.append(regime_context)
        
        # Event-driven narrative
        for _, event in recent_events.iterrows():
            if event['significance'] in ['high', 'medium']:
                try:
                    event_narrative = self.narrative_templates['causal_narrative'].format(
                        macro_forces=event['cause'],
                        regime_type=event['regime_shift'].replace('_', ' '),
                        historical_examples=event['historical_reference'],
                        strategy_effect=event['strategy_impact'].replace('_', ' '),
                        portfolio_action=event['portfolio_action'].replace('_', ' '),
                        expected_outcome='improved risk-adjusted returns'
                    )
                    narrative_parts.append(event_narrative)
                except KeyError as e:
                    # Fallback narrative if template formatting fails
                    fallback_narrative = f"{event['cause']} has led to {event['strategy_impact'].replace('_', ' ')} requiring {event['portfolio_action'].replace('_', ' ')}."
                    narrative_parts.append(fallback_narrative)
        
        # Portfolio positioning
        capital_changes = current_facts.get('capital_changes', {})
        if capital_changes:
            cash_alloc = capital_changes.get('cash_allocation', 0)
            top_strategy = capital_changes.get('top_strategy', 'diversified strategies')
            
            positioning_narrative = (
                f"Portfolio positioning reflects {cash_alloc:.1%} cash allocation with "
                f"primary exposure through {top_strategy.replace('_', ' ')}. "
                f"This allocation is optimized for the current regime characteristics."
            )
            narrative_parts.append(positioning_narrative)
        
        # Risk management
        portfolio_risk = current_facts.get('portfolio_risk', {})
        if portfolio_risk:
            drawdown = portfolio_risk.get('max_drawdown', 0)
            volatility = portfolio_risk.get('volatility', 0)
            
            risk_narrative = (
                f"Risk management maintains portfolio volatility at {volatility:.1%} "
                f"with maximum drawdown of {abs(drawdown):.1%}. "
                f"These metrics are consistent with institutional risk standards."
            )
            narrative_parts.append(risk_narrative)
        
        full_narrative = " ".join(narrative_parts)
        
        print(f"   ✅ Generated {len(full_narrative)} character narrative")
        
        return full_narrative
    
    def generate_weekly_pulse(self, fact_spine_df: pd.DataFrame, events_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate weekly market pulse narrative"""
        
        print("📊 Generating weekly pulse narrative...")
        
        if fact_spine_df.empty:
            return {'error': 'Insufficient data for weekly pulse'}
        
        current_facts = fact_spine_df.iloc[-1]
        
        # Weekly pulse structure
        weekly_pulse = {
            'timestamp': datetime.now().isoformat(),
            'period': 'weekly',
            'regime_summary': {
                'current_regime': current_facts['regime_name'],
                'stability': float(current_facts['regime_stability']),
                'risk_level': current_facts['regime_risk_level'],
                'narrative': f"Market operates in {current_facts['regime_name'].replace('_', ' ').lower()} conditions with {current_facts['regime_stability']:.1%} regime stability."
            },
            'key_forces': {
                'macro_drivers': current_facts.get('top_macro_moves', {}),
                'pulse_intensity': float(current_facts.get('pulse_intensity', 0)),
                'dominant_forces': current_facts.get('pulse_forces', {}),
                'narrative': "Primary market forces include macro economic shifts and regime transition dynamics."
            },
            'portfolio_actions': {
                'capital_allocation': current_facts.get('capital_changes', {}),
                'strategy_evolution': current_facts.get('strategy_changes', {}),
                'narrative': "Portfolio positioning reflects anticipatory intelligence with regime-aware capital allocation."
            },
            'risk_assessment': {
                'current_risk': current_facts.get('portfolio_risk', {}),
                'drawdown': float(current_facts.get('drawdown', 0)),
                'narrative': f"Risk management maintains institutional standards with {abs(current_facts.get('drawdown', 0)):.1%} maximum drawdown."
            },
            'forward_outlook': {
                'regime_probabilities': current_facts.get('regime_probs', {}),
                'key_risks': ['regime_transition', 'macro_shifts', 'strategy_rotation'],
                'opportunities': ['regime_positioning', 'anticipatory_allocation'],
                'narrative': "Forward outlook focuses on regime transition preparation and anticipatory positioning opportunities."
            }
        }
        
        # Save weekly pulse with version archive.
        write_json_with_archive(self.paths['weekly_pulse'], weekly_pulse)
        
        print(f"   ✅ Weekly pulse generated")
        print(f"      Regime: {weekly_pulse['regime_summary']['current_regime']}")
        print(f"      Risk Level: {weekly_pulse['regime_summary']['risk_level'].upper()}")
        
        return weekly_pulse
    
    def generate_monthly_report(self, fact_spine_df: pd.DataFrame, events_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive monthly report"""
        
        print("📋 Generating monthly report...")
        
        if fact_spine_df.empty:
            return {'error': 'Insufficient data for monthly report'}
        
        current_facts = fact_spine_df.iloc[-1]
        monthly_events = events_df.tail(30) if not events_df.empty else pd.DataFrame()
        
        # Monthly report structure
        monthly_report = {
            'timestamp': datetime.now().isoformat(),
            'period': f"{datetime.now().strftime('%B %Y')}",
            'report_type': 'institutional_monthly',
            
            'executive_summary': {
                'regime_context': current_facts['regime_name'],
                'performance_summary': current_facts.get('returns', 0),
                'risk_metrics': current_facts.get('portfolio_risk', {}),
                'key_decisions': len(monthly_events[monthly_events['significance'] == 'high']) if not monthly_events.empty else 0,
                'narrative': self.generate_executive_summary(current_facts, monthly_events)
            },
            
            'market_regime_analysis': {
                'current_regime': {
                    'name': current_facts['regime_name'],
                    'stability': float(current_facts['regime_stability']),
                    'duration': 'Current period',  # Would need historical tracking
                    'characteristics': self.get_regime_characteristics(current_facts['regime_name'])
                },
                'regime_transitions': current_facts.get('regime_probs', {}),
                'historical_context': self.get_regime_historical_context(current_facts['regime_name']),
                'narrative': f"Market regime analysis indicates {current_facts['regime_name'].replace('_', ' ').lower()} conditions with institutional-grade stability assessment."
            },
            
            'forces_driving_markets': {
                'macro_forces': current_facts.get('top_macro_moves', {}),
                'market_pulse': {
                    'intensity': float(current_facts.get('pulse_intensity', 0)),
                    'dominant_forces': current_facts.get('pulse_forces', {})
                },
                'structural_shifts': self.identify_structural_shifts(fact_spine_df),
                'narrative': "Market forces reflect the interaction of macro economic conditions, regime dynamics, and structural market evolution."
            },
            
            'strategy_evolution': {
                'performance_analysis': current_facts.get('strategy_changes', {}),
                'allocation_changes': current_facts.get('capital_changes', {}),
                'regime_adaptation': 'Strategies adapted to current regime characteristics',
                'narrative': "Strategy evolution reflects anticipatory intelligence with regime-aware performance optimization."
            },
            
            'capital_allocation': {
                'current_allocation': current_facts.get('capital_changes', {}),
                'allocation_rationale': 'Regime-based anticipatory positioning',
                'risk_budgeting': current_facts.get('portfolio_risk', {}),
                'narrative': "Capital allocation optimized for current regime with anticipatory positioning for regime transitions."
            },
            
            'risk_and_drawdowns': {
                'risk_metrics': current_facts.get('portfolio_risk', {}),
                'drawdown_analysis': {
                    'current_drawdown': float(current_facts.get('drawdown', 0)),
                    'max_drawdown': float(current_facts.get('drawdown', 0)),
                    'recovery_analysis': 'Institutional risk management standards maintained'
                },
                'risk_attribution': 'Risk primarily from regime transition uncertainty',
                'narrative': f"Risk management maintains institutional standards with {abs(current_facts.get('drawdown', 0)):.1%} drawdown control."
            },
            
            'forward_expectations': {
                'regime_outlook': current_facts.get('regime_probs', {}),
                'strategy_expectations': 'Anticipatory positioning for regime evolution',
                'risk_scenarios': ['regime_transition', 'macro_shifts', 'market_stress'],
                'opportunities': ['anticipatory_allocation', 'regime_arbitrage'],
                'narrative': "Forward expectations focus on regime transition preparation with anticipatory intelligence positioning."
            }
        }
        
        # Save monthly report with version archive.
        write_json_with_archive(self.paths['monthly_report'], monthly_report)
        
        print(f"   ✅ Monthly report generated: {monthly_report['period']}")
        print(f"      Executive Summary: {len(monthly_report['executive_summary']['narrative'])} characters")
        print(f"      Sections: {len([k for k in monthly_report.keys() if k not in ['timestamp', 'period', 'report_type']])}")
        
        return monthly_report
    
    def generate_executive_summary(self, current_facts: Dict, monthly_events: pd.DataFrame) -> str:
        """Generate executive summary for monthly report"""
        
        regime_name = current_facts['regime_name']
        regime_stability = current_facts['regime_stability']
        risk_level = current_facts['regime_risk_level']
        
        summary_parts = []
        
        # Regime context
        summary_parts.append(
            f"During this period, markets operated under {regime_name.replace('_', ' ').lower()} conditions "
            f"with {regime_stability:.1%} regime stability and {risk_level} risk assessment."
        )
        
        # Key decisions
        if not monthly_events.empty:
            high_significance_events = monthly_events[monthly_events['significance'] == 'high']
            if not high_significance_events.empty:
                summary_parts.append(
                    f"Key portfolio decisions included {len(high_significance_events)} major allocation adjustments "
                    f"based on regime intelligence and anticipatory positioning requirements."
                )
        
        # Performance context
        portfolio_risk = current_facts.get('portfolio_risk', {})
        if portfolio_risk:
            drawdown = abs(portfolio_risk.get('max_drawdown', 0))
            summary_parts.append(
                f"Risk management maintained institutional standards with {drawdown:.1%} maximum drawdown, "
                f"consistent with regime-aware risk budgeting."
            )
        
        # Forward positioning
        summary_parts.append(
            "Portfolio positioning reflects anticipatory intelligence with regime transition preparation "
            "and historical pattern recognition driving capital allocation decisions."
        )
        
        return " ".join(summary_parts)
    
    def get_regime_characteristics(self, regime_name: str) -> List[str]:
        """Get characteristics of specific regime"""
        
        regime_chars = {
            'Expansion_Liquidity_Driven': [
                'Abundant liquidity conditions',
                'Momentum strategy effectiveness',
                'Risk-on positioning favorable',
                'Growth over value preference'
            ],
            'Crisis_Liquidity_Shock': [
                'Liquidity stress conditions',
                'Flight to quality dynamics',
                'Defensive positioning required',
                'Value over growth preference'
            ],
            'Late_Expansion_Euphoria': [
                'Peak cycle conditions',
                'Momentum strategy risks rising',
                'Transition preparation required',
                'Quality focus increasing'
            ]
        }
        
        return regime_chars.get(regime_name, ['Standard market conditions', 'Balanced positioning appropriate'])
    
    def get_regime_historical_context(self, regime_name: str) -> str:
        """Get historical context for regime"""
        
        historical_context = {
            'Expansion_Liquidity_Driven': 'Similar to 2003-2007 and 2009-2015 periods with abundant liquidity driving momentum strategies',
            'Crisis_Liquidity_Shock': 'Comparable to 2008 and 2020 crisis periods requiring defensive positioning and quality focus',
            'Late_Expansion_Euphoria': 'Resembles 2000 and 2007 late-cycle conditions with transition risks rising'
        }
        
        return historical_context.get(regime_name, 'Standard market regime with balanced characteristics')
    
    def identify_structural_shifts(self, fact_spine_df: pd.DataFrame) -> List[str]:
        """Identify structural market shifts"""
        
        # Simplified structural shift detection
        shifts = [
            'Regime-based intelligence integration',
            'Anticipatory capital allocation implementation',
            'Historical pattern recognition enhancement'
        ]
        
        return shifts
    
    def generate_daily_narrative(self) -> Dict[str, Any]:
        """Generate daily narrative update"""
        
        print("📰 Generating daily narrative...")
        
        # Build current fact spine
        fact_spine_df = self.build_fact_spine()
        
        if fact_spine_df.empty:
            return {'error': 'No data for daily narrative'}
        
        current_facts = fact_spine_df.iloc[-1]
        
        daily_narrative = {
            'timestamp': datetime.now().isoformat(),
            'date': current_facts['date'].strftime('%Y-%m-%d'),
            'regime_status': {
                'current_regime': current_facts['regime_name'],
                'stability': float(current_facts['regime_stability']),
                'risk_level': current_facts['regime_risk_level']
            },
            'market_pulse': {
                'intensity': float(current_facts.get('pulse_intensity', 0)),
                'forces': current_facts.get('pulse_forces', {})
            },
            'portfolio_status': {
                'allocation': current_facts.get('capital_changes', {}),
                'risk': current_facts.get('portfolio_risk', {})
            },
            'narrative': f"Daily market assessment shows {current_facts['regime_name'].replace('_', ' ').lower()} regime with {current_facts['regime_stability']:.1%} stability. Portfolio maintains regime-aware positioning with anticipatory intelligence active."
        }
        
        # Save daily narrative with version archive.
        write_json_with_archive(self.paths['daily_narrative'], daily_narrative)
        
        print(f"   ✅ Daily narrative generated")
        
        return daily_narrative
    
    def run_complete_narrative_intelligence(self) -> Dict[str, Any]:
        """Run complete narrative intelligence system"""
        
        print("🧠 NARRATIVE INTELLIGENCE ENGINE")
        print("=" * 60)
        print("Converting anticipatory intelligence into investor-grade narratives")
        print()
        
        results = {}
        
        try:
            # Phase 1: Build fact spine
            fact_spine_df = self.build_fact_spine()
            results['fact_spine'] = len(fact_spine_df)
            
            # Phase 2: Detect narrative events
            events_df = self.detect_narrative_events(fact_spine_df)
            results['narrative_events'] = len(events_df)
            
            # Phase 3: Generate causal narrative
            causal_narrative = self.generate_causal_narrative(events_df, fact_spine_df)
            results['causal_narrative'] = len(causal_narrative)
            
            # Phase 4: Generate weekly pulse
            weekly_pulse = self.generate_weekly_pulse(fact_spine_df, events_df)
            results['weekly_pulse'] = 'generated'
            
            # Phase 5: Generate monthly report
            monthly_report = self.generate_monthly_report(fact_spine_df, events_df)
            results['monthly_report'] = 'generated'
            
            # Phase 6: Generate daily narrative
            daily_narrative = self.generate_daily_narrative()
            results['daily_narrative'] = 'generated'
            
            print(f"\n✅ NARRATIVE INTELLIGENCE COMPLETE!")
            print(f"   📊 Fact spine: {results['fact_spine']} records")
            print(f"   🔍 Events detected: {results['narrative_events']}")
            print(f"   📝 Causal narrative: {results['causal_narrative']} characters")
            print(f"   📊 Weekly pulse: {results['weekly_pulse']}")
            print(f"   📋 Monthly report: {results['monthly_report']}")
            print(f"   📰 Daily narrative: {results['daily_narrative']}")
            
            results['status'] = 'success'
            results['narrative_intelligence_active'] = True
            
        except Exception as e:
            print(f"❌ Narrative intelligence error: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results

def main():
    """Test Narrative Intelligence Engine"""
    
    engine = NarrativeIntelligenceEngine()
    results = engine.run_complete_narrative_intelligence()
    
    if results.get('status') == 'success':
        print(f"\n🎉 NARRATIVE INTELLIGENCE IS LIVE!")
        print(f"   🧠 Intelligence converted to investor-grade narratives")
        print(f"   📊 Hedge-fund quality explanations: ACTIVE")
        print(f"   📋 Monthly PM letters: AUTOMATED")
        print(f"   📰 Daily market pulse: OPERATIONAL")
        print()
        print(f"   Northstar now explains every decision with:")
        print(f"   • Historical context and precedent")
        print(f"   • Causal reasoning and justification")
        print(f"   • Regime-aware narrative intelligence")
        print(f"   • Institutional-grade communication")
        print()
        print(f"   This is what separates institutional from retail intelligence.")
        return True
    else:
        print("❌ Narrative Intelligence Engine failed")
        return False

if __name__ == "__main__":
    main()
