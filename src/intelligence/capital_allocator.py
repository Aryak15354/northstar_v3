#!/usr/bin/env python3
"""
🧠 CAPITAL ALLOCATOR - BAYESIAN MODEL ALLOCATION ENGINE
Institutional-Grade Capital Allocation with Regret Minimization

This is the brain that decides which strategies get money today.
Uses Thompson Sampling and Bayesian updating to allocate capital
across competing strategies based on their skill and regime fit.

This is how Bridgewater, Citadel, and Two Sigma actually operate:
They don't pick stocks. They allocate capital to models.

Usage:
    try:
    from intelligence.capital_allocator import CapitalAllocator
except ImportError:
    from CapitalAllocator import CapitalAllocator
    
    allocator = CapitalAllocator()
    allocations = allocator.allocate_capital()
"""

import pandas as pd
import numpy as np
import os
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from scipy.stats import beta
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

class CapitalAllocator:
    """
    Bayesian Capital Allocation Engine with Regret Minimization
    
    This system decides how to split capital across strategies using:
    1. Bayesian skill estimation (Thompson Sampling)
    2. Regime awareness
    3. Regret tracking
    4. Risk management overlays
    """
    
    def __init__(self):
        self.name = "Northstar Capital Allocator"
        self.version = "3.0"
        
        # File paths
        self.paths = {
            'strategy_performance': 'data/processed/strategy_performance',
            'backtests': 'data/processed/backtests',
            'market_state': 'data/processed/market_state.parquet',
            'strategy_beliefs': 'data/processed/strategy_beliefs.parquet',
            'strategy_regret': 'data/processed/strategy_regret.parquet',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'allocation_history': 'data/processed/allocation_history.parquet',
            'edge_half_life': 'data/processed/edge_half_life.json',
            'model_freeze_state': 'data/processed/model_freeze_state.json',
            'parameter_version': 'data/processed/parameter_version.json',
        }
        
        # Allocation parameters
        self.params = {
            'min_allocation': 0.05,    # 5% minimum per strategy
            'max_allocation': 0.50,    # 50% maximum per strategy
            'temperature': 0.75,       # Softmax temperature (lower = more concentrated)
            'confidence_threshold': 0.4,  # Minimum skill probability
            'regret_penalty': 0.3,     # Regret penalty weight
            'lookback_days': 90,       # Days to consider for allocation
            'min_trades': 10,          # Minimum trades for skill estimation
            'kill_switch_dd': 0.20,    # 20% drawdown kills strategy
            'kill_switch_regret': 0.70,  # Top 70% regret kills strategy
            'edge_decay_alpha': 2.0,
            # High-conviction gates (pre-allocation filtering)
            'min_alive_score': 0.05,
            'min_alive_skill_prob': 0.52,
            'min_alive_confidence': 0.20,
            'min_alive_tailwind': 0.85,
            'max_live_strategies': 8,
            'fabric_multiplier_strength': 0.35,
            # Allocator hardening parameters
            'risk_lookback_days': 60,
            'covariance_shrinkage': 0.35,
            'covariance_eigen_floor': 1e-6,
            'optimizer_risk_aversion': 3.5,
            'allocation_turnover_cap': 0.20,  # one-way allocation turnover cap
            'transaction_cost_bps': 10.0,
            'freeze_max_exposure': 0.15,
        }
        self.last_optimizer_diagnostics = {}
        
        # Regime boosts
        self.regime_boosts = {
            'crisis': {
                'low_vol': 1.5, 'quality_tilt': 1.3, 'value_tilt': 1.2,
                'mom_6m': 0.7, 'mom_12m': 0.7, 'dual_momentum': 0.8
            },
            'boom': {
                'mom_6m': 1.4, 'mom_12m': 1.3, 'dual_momentum': 1.2,
                'low_vol': 0.8, 'quality_tilt': 0.9
            },
            'expansion': {
                'mom_6m': 1.2, 'quality_tilt': 1.1, 'northstar': 1.1,
                'value_tilt': 0.9
            },
            'late-expansion': {
                'quality_tilt': 1.2, 'low_vol': 1.1, 'northstar': 1.0,
                'mom_6m': 0.9, 'value_tilt': 1.1
            },
            'slowdown': {
                'value_tilt': 1.3, 'quality_tilt': 1.2, 'low_vol': 1.1,
                'mom_6m': 0.8, 'mom_12m': 0.8
            },
            'tightening': {
                'low_vol': 1.4, 'value_tilt': 1.3, 'quality_tilt': 1.2,
                'mom_6m': 0.7, 'dual_momentum': 0.8
            }
        }

    def load_weekly_fabric_insights(self):
        """Load weekly causal-fabric insights for allocation-time conditioning."""
        try:
            try:
                from src.intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader
            except Exception:
                from intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader
            reader = WeeklyFabricReader()
            insights = reader.get_capital_allocation_insights() or {}
            multipliers = insights.get('strategy_fitness_multipliers', {}) or {}
            print(f"🧬 Weekly fabric insights loaded: {len(multipliers)} multipliers")
            return insights
        except Exception as e:
            print(f"   ⚠️ Weekly fabric insights unavailable: {e}")
            return {}

    @staticmethod
    def _strategy_fabric_tags(strategy_name: str):
        s = str(strategy_name or "").lower()
        tags = set()
        if any(k in s for k in ['mom', 'momentum', 'growth', 'trend', 'northstar']):
            tags.add('growth_strategies')
            tags.add('cyclicals')
        if any(k in s for k in ['quality', 'low_vol', 'defensive']):
            tags.add('defensive_strategies')
            tags.add('quality_defensives')
        if any(k in s for k in ['value', 'contrarian']):
            tags.add('quality_defensives')
            tags.add('credit_sensitive')
        if any(k in s for k in ['export']):
            tags.add('export_focused')
        if any(k in s for k in ['import']):
            tags.add('import_dependent')
        return tags

    def apply_weekly_fabric_conditioning(self, health_scores, fabric_insights):
        """
        Condition health scores with weekly causal-fabric multipliers.
        This wires anticipatory relationships into the allocator directly.
        """
        if not health_scores:
            return health_scores

        multipliers = (fabric_insights or {}).get('strategy_fitness_multipliers', {}) or {}
        if not multipliers:
            return health_scores

        strength = float(self.params.get('fabric_multiplier_strength', 0.35))
        for strategy, metrics in health_scores.items():
            tags = self._strategy_fabric_tags(strategy)
            if not tags:
                metrics['fabric_multiplier'] = 1.0
                continue

            vals = [float(multipliers.get(tag, 1.0) or 1.0) for tag in tags]
            if not vals:
                metrics['fabric_multiplier'] = 1.0
                continue

            raw_mult = float(np.mean(vals))
            effective_mult = float(np.clip(1.0 + strength * (raw_mult - 1.0), 0.80, 1.20))
            metrics['health_score'] = float(metrics.get('health_score', 0.0)) * effective_mult
            metrics['fabric_multiplier'] = effective_mult

        return health_scores

    def load_model_freeze_state(self):
        """Load automatic freeze-state controls from institutional hardening layer."""
        path = self.paths.get('model_freeze_state')
        if not path or not os.path.exists(path):
            return {'freeze_active': False, 'actions': {}}
        try:
            with open(path, 'r') as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return {'freeze_active': False, 'actions': {}}
            payload.setdefault('freeze_active', False)
            payload.setdefault('actions', {})
            return payload
        except Exception as e:
            print(f"   ⚠️ Could not load model freeze state: {e}")
            return {'freeze_active': False, 'actions': {}}

    def _load_previous_allocations(self):
        """Load previous strategy allocations for turnover control."""
        try:
            if os.path.exists(self.paths['capital_allocations']):
                with open(self.paths['capital_allocations'], 'r') as f:
                    payload = json.load(f)
                allocs = payload.get('allocations', {})
                if isinstance(allocs, dict):
                    out = {}
                    for k, v in allocs.items():
                        x = float(v)
                        if np.isfinite(x):
                            out[str(k)] = max(0.0, x)
                    return out
        except Exception:
            pass
        return {}

    def _build_strategy_return_matrix(self, strategy_data, strategies):
        """
        Build aligned strategy return matrix for covariance estimation.
        Returns shape: [lookback, n_strategies].
        """
        series = {}
        min_len = None
        lookback = max(20, int(self.params.get('risk_lookback_days', 60)))

        for strategy in strategies:
            raw = strategy_data.get(strategy, {}).get('recent_returns', []) or []
            if len(raw) < 20:
                continue
            s = pd.to_numeric(pd.Series(raw), errors='coerce').dropna()
            if len(s) < 20:
                continue
            arr = s.values.astype(float)
            if np.all(~np.isfinite(arr)):
                continue
            arr = arr[np.isfinite(arr)]
            if len(arr) < 20:
                continue
            series[strategy] = arr
            min_len = len(arr) if min_len is None else min(min_len, len(arr))

        if not series or min_len is None or min_len < 20:
            return pd.DataFrame()

        n = min(min_len, lookback)
        aligned = {k: v[-n:] for k, v in series.items()}
        mat = pd.DataFrame(aligned)
        mat = mat.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how='any')
        if mat.shape[0] < 20:
            return pd.DataFrame()
        return mat

    def _estimate_shrunk_covariance(self, returns_df):
        """Estimate a numerically stable covariance matrix with diagonal shrinkage."""
        if returns_df.empty:
            return np.array([[]], dtype=float), np.array([], dtype=float), np.inf

        cov = returns_df.cov().values.astype(float)
        cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
        diag = np.diag(np.diag(cov))
        shrink = float(np.clip(self.params.get('covariance_shrinkage', 0.35), 0.0, 1.0))
        shrunk = (1.0 - shrink) * cov + shrink * diag

        # Eigenvalue clipping protects inversion from near-singularity.
        floor = float(max(1e-10, self.params.get('covariance_eigen_floor', 1e-6)))
        try:
            eigvals, eigvecs = np.linalg.eigh(shrunk)
            eigvals = np.clip(eigvals, floor, None)
            shrunk = eigvecs @ np.diag(eigvals) @ eigvecs.T
            shrunk = 0.5 * (shrunk + shrunk.T)
            cond = float(np.linalg.cond(shrunk))
        except Exception:
            n = shrunk.shape[0]
            shrunk = np.eye(n) * floor
            eigvals = np.full(n, floor, dtype=float)
            cond = np.inf
        return shrunk, eigvals, cond

    def _risk_normalized_optimizer(
        self,
        alive_strategies,
        health_scores,
        strategy_data,
        exposure_cap,
        previous_allocations,
        freeze_state,
    ):
        """
        Allocate via risk-normalized mean-variance proxy:
        w ~ inv(Sigma) * (mu / sigma), long-only with turnover cap.
        """
        if not alive_strategies:
            return {}

        strat_list = list(alive_strategies.keys())
        ret_mat = self._build_strategy_return_matrix(strategy_data, strat_list)

        if ret_mat.empty or ret_mat.shape[1] < 1:
            return {}

        used = [c for c in ret_mat.columns if c in alive_strategies]
        ret_mat = ret_mat[used]
        if ret_mat.empty:
            return {}

        cov, eigvals, cond = self._estimate_shrunk_covariance(ret_mat)
        vols = np.sqrt(np.clip(np.diag(cov), 1e-12, None))

        mu_raw = []
        avg_turnover = []
        for s in used:
            h = health_scores.get(s, {})
            base_alpha = float(
                h.get('health_score', 0.0) *
                h.get('skill_prob', 0.5) *
                max(0.5, h.get('tailwind_score', 1.0))
            )
            tc_penalty = float(self.params.get('transaction_cost_bps', 10.0)) / 10000.0
            strat_turnover = float(strategy_data.get(s, {}).get('avg_turnover', 0.0) or 0.0)
            mu_raw.append(base_alpha - tc_penalty * strat_turnover)
            avg_turnover.append(strat_turnover)
        mu_raw = np.asarray(mu_raw, dtype=float)
        mu_raw = np.nan_to_num(mu_raw, nan=0.0, posinf=0.0, neginf=0.0)
        mu_rn = mu_raw / np.clip(vols, 1e-8, None)
        mu_rn = np.nan_to_num(mu_rn, nan=0.0, posinf=0.0, neginf=0.0)

        freeze_actions = (freeze_state or {}).get('actions', {}) if isinstance(freeze_state, dict) else {}
        risk_mult = float(freeze_actions.get('risk_aversion_multiplier', 1.0) or 1.0)
        risk_aversion = float(max(1e-6, self.params.get('optimizer_risk_aversion', 3.5) * risk_mult))

        try:
            # Mean-variance first-order condition (unconstrained), then long-only projection.
            precision = np.linalg.pinv(cov + np.eye(cov.shape[0]) * (1.0 / risk_aversion))
            raw = precision @ mu_rn
        except Exception:
            raw = mu_rn.copy()

        raw = np.clip(raw, 0.0, None)
        if raw.sum() <= 1e-12:
            raw = np.clip(mu_rn, 0.0, None)
        if raw.sum() <= 1e-12:
            raw = np.ones_like(raw)

        w = raw / np.clip(raw.sum(), 1e-12, None)

        # Hard max allocation per strategy.
        w = np.minimum(w, float(self.params.get('max_allocation', 0.50)))
        if w.sum() <= 1e-12:
            w = np.ones_like(w) / len(w)
        else:
            w = w / w.sum()

        target = {s: float(w[i] * exposure_cap) for i, s in enumerate(used)}

        # Turnover governance: limit one-way reallocation each cycle.
        all_keys = sorted(set(target.keys()) | set(previous_allocations.keys()))
        prev_vec = np.array([float(previous_allocations.get(k, 0.0)) for k in all_keys], dtype=float)
        new_vec = np.array([float(target.get(k, 0.0)) for k in all_keys], dtype=float)
        turnover = 0.5 * float(np.abs(new_vec - prev_vec).sum())
        turnover_cap = float(max(0.01, self.params.get('allocation_turnover_cap', 0.20)))
        if turnover > turnover_cap and turnover > 1e-12:
            blend = turnover_cap / turnover
            adj_vec = prev_vec + blend * (new_vec - prev_vec)
            new_vec = np.clip(adj_vec, 0.0, None)
            ssum = float(new_vec.sum())
            if ssum > 1e-12:
                new_vec = new_vec / ssum * exposure_cap
            target = {k: float(v) for k, v in zip(all_keys, new_vec) if v > 1e-8}

        self.last_optimizer_diagnostics = {
            'method': 'risk_normalized_mean_variance',
            'n_strategies': int(len(used)),
            'lookback_rows': int(ret_mat.shape[0]),
            'covariance_condition_number': float(cond),
            'covariance_shrinkage': float(self.params.get('covariance_shrinkage', 0.35)),
            'covariance_min_eigenvalue': float(np.min(eigvals)) if len(eigvals) else None,
            'risk_aversion': risk_aversion,
            'estimated_turnover': turnover,
            'turnover_cap': turnover_cap,
            'avg_strategy_turnover': float(np.mean(avg_turnover)) if avg_turnover else 0.0,
        }
        return target
    
    def load_strategy_performance(self):
        """Load recent strategy performance data"""
        
        print("📊 Loading strategy performance data...")
        
        strategy_data = {}
        
        # Load backtest results
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty:
                            # Get recent performance
                            recent_df = df.tail(self.params['lookback_days'])
                            
                            if len(recent_df) > 1:
                                returns = recent_df['daily_return']
                                equity = recent_df['equity']
                                
                                # Calculate metrics
                                total_return = equity.iloc[-1] / equity.iloc[0] - 1
                                ann_return = (equity.iloc[-1] / equity.iloc[0]) ** (252 / len(recent_df)) - 1
                                volatility = returns.std() * np.sqrt(252)
                                sharpe = ann_return / volatility if volatility > 0 else 0
                                max_dd = recent_df['drawdown'].min()
                                
                                # Win rate and other metrics
                                win_rate = (returns > 0).mean()
                                avg_exposure = recent_df['exposure'].mean()
                                avg_turnover = recent_df['turnover'].mean()
                                
                                strategy_data[strategy_name] = {
                                    'total_return': total_return,
                                    'ann_return': ann_return,
                                    'volatility': volatility,
                                    'sharpe': sharpe,
                                    'max_drawdown': max_dd,
                                    'win_rate': win_rate,
                                    'avg_exposure': avg_exposure,
                                    'avg_turnover': avg_turnover,
                                    'n_observations': len(recent_df),
                                    'last_equity': equity.iloc[-1],
                                    'recent_returns': returns.tolist()
                                }
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
        
        print(f"   ✅ Loaded performance for {len(strategy_data)} strategies")
        return strategy_data
    
    def load_market_regime(self):
        """Load current market regime"""
        
        try:
            if os.path.exists(self.paths['market_state']):
                market_df = pd.read_parquet(self.paths['market_state'])
                if not market_df.empty:
                    latest = market_df.iloc[-1]
                    regime = latest.get('macro_regime', 'neutral')
                    vol_regime = latest.get('vol_regime', 'mid')
                    liquidity_regime = latest.get('liquidity_regime', 'neutral')
                    risk_on_prob = latest.get('risk_on_probability', 0.5)
                    
                    print(f"   📊 Current regime: {regime} (risk-on: {risk_on_prob:.1%})")
                    
                    return {
                        'macro_regime': regime,
                        'vol_regime': vol_regime,
                        'liquidity_regime': liquidity_regime,
                        'risk_on_prob': risk_on_prob
                    }
        except Exception as e:
            print(f"   ⚠️ Could not load market regime: {e}")
        
        return {
            'macro_regime': 'neutral',
            'vol_regime': 'mid',
            'liquidity_regime': 'neutral',
            'risk_on_prob': 0.5
        }
    
    def load_strategy_beliefs(self):
        """Load strategy beliefs from the beliefs engine"""
        
        print("🧠 Loading strategy beliefs...")
        
        beliefs = {}
        beliefs_file = 'data/processed/strategy_beliefs.parquet'
        
        if os.path.exists(beliefs_file):
            try:
                beliefs_df = pd.read_parquet(beliefs_file)
                if beliefs_df.empty:
                    return beliefs

                # Backward compatibility: legacy beliefs files used `timestamp`
                # and sometimes only [strategy, belief_strength].
                if 'date' not in beliefs_df.columns:
                    if 'timestamp' in beliefs_df.columns:
                        beliefs_df['date'] = pd.to_datetime(beliefs_df['timestamp'], errors='coerce')
                    else:
                        beliefs_df['date'] = pd.Timestamp.utcnow()
                beliefs_df['date'] = pd.to_datetime(beliefs_df['date'], errors='coerce').fillna(pd.Timestamp.utcnow())

                if 'strategy' not in beliefs_df.columns:
                    return beliefs

                if 'skill_prob' not in beliefs_df.columns and 'belief_strength' in beliefs_df.columns:
                    beliefs_df['skill_prob'] = pd.to_numeric(beliefs_df['belief_strength'], errors='coerce')

                # Ensure canonical numeric fields exist
                beliefs_df['skill_prob'] = pd.to_numeric(
                    beliefs_df.get('skill_prob', 0.5), errors='coerce'
                ).fillna(0.5).clip(0.01, 0.99)
                beliefs_df['confidence'] = pd.to_numeric(
                    beliefs_df.get('confidence', 0.5), errors='coerce'
                ).fillna(0.5).clip(0.01, 1.0)
                beliefs_df['effective_skill'] = pd.to_numeric(
                    beliefs_df.get('effective_skill', beliefs_df['skill_prob']), errors='coerce'
                ).fillna(beliefs_df['skill_prob'])
                beliefs_df['regime_fit'] = pd.to_numeric(
                    beliefs_df.get('regime_fit', 1.0), errors='coerce'
                ).fillna(1.0)
                beliefs_df['sharpe'] = pd.to_numeric(
                    beliefs_df.get('sharpe', 0.0), errors='coerce'
                ).fillna(0.0)
                beliefs_df['alpha'] = pd.to_numeric(
                    beliefs_df.get('alpha', beliefs_df['skill_prob'] * 20.0), errors='coerce'
                ).fillna(beliefs_df['skill_prob'] * 20.0)
                beliefs_df['beta'] = pd.to_numeric(
                    beliefs_df.get('beta', (1.0 - beliefs_df['skill_prob']) * 20.0), errors='coerce'
                ).fillna((1.0 - beliefs_df['skill_prob']) * 20.0)
                beliefs_df['status'] = beliefs_df.get('status', np.where(beliefs_df['skill_prob'] >= 0.45, 'ACTIVE', 'FADING'))
                beliefs_df['status'] = beliefs_df['status'].fillna('ACTIVE')

                # Get latest beliefs for each strategy
                latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
                
                for _, row in latest_beliefs.iterrows():
                    beliefs[row['strategy']] = {
                        'skill_prob': float(row['skill_prob']),
                        'confidence': float(row['confidence']),
                        'effective_skill': float(row['effective_skill']),
                        'regime_fit': float(row['regime_fit']),
                        'status': str(row['status']),
                        'sharpe': float(row['sharpe']),
                        'alpha': float(row['alpha']),
                        'beta': float(row['beta'])
                    }
                
                print(f"   ✅ Loaded beliefs for {len(beliefs)} strategies")
                
            except Exception as e:
                print(f"   ⚠️ Error loading beliefs: {e}")
        
        return beliefs

    def load_edge_half_life(self):
        """Load edge half-life health scores if available."""
        try:
            if os.path.exists(self.paths['edge_half_life']):
                with open(self.paths['edge_half_life'], 'r') as f:
                    payload = json.load(f)
                strategies = payload.get('strategies', {})
                return {k: v.get('edge_health', 1.0) for k, v in strategies.items()}
        except Exception as e:
            print(f"   ⚠️ Could not load edge half-life: {e}")
        return {}
    
    def load_strategy_tailwinds(self):
        """Load strategy tailwinds from the tailwind engine"""
        
        print("🌬️ Loading strategy tailwinds...")
        
        tailwinds = {}
        
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            from intelligence.simple_tailwind_engine import SimpleTailwindEngine
            
            tailwind_engine = SimpleTailwindEngine()
            all_tailwinds = tailwind_engine.get_all_tailwinds()
            
            if all_tailwinds:
                tailwinds = all_tailwinds
                print(f"   ✅ Loaded tailwinds for {len(tailwinds)} strategies")
                
                # Show top tailwinds
                sorted_tailwinds = sorted(tailwinds.items(), 
                                        key=lambda x: x[1]['combined_score'], reverse=True)
                print(f"   🌬️ Top 3 tailwinds:")
                for strategy, data in sorted_tailwinds[:3]:
                    print(f"      {strategy}: {data['combined_score']:.3f}")
            else:
                print("   ⚠️ No tailwind data available")
                
        except Exception as e:
            print(f"   ⚠️ Error loading tailwinds: {e}")
            
            # Fallback: try to load directly from file
            try:
                tailwind_file = 'data/intelligence/strategy_tailwinds.parquet'
                if os.path.exists(tailwind_file):
                    tailwind_df = pd.read_parquet(tailwind_file)
                    
                    for _, row in tailwind_df.iterrows():
                        tailwinds[row['strategy']] = {
                            'combined_score': float(row['combined_score']),
                            'sharpe': float(row['sharpe']),
                            'regime_tailwind': float(row['regime_tailwind']),
                            'regime': row['regime']
                        }
                    
                    print(f"   ✅ Loaded tailwinds from file for {len(tailwinds)} strategies")
                    
            except Exception as e2:
                print(f"   ⚠️ Fallback loading also failed: {e2}")
        
        return tailwinds
    def load_strategy_regret(self):
        """Load strategy regret from the regret engine"""
        
        print("😈 Loading strategy regret...")
        
        regret = {}
        regret_file = 'data/processed/strategy_regret.parquet'
        
        if os.path.exists(regret_file):
            try:
                regret_df = pd.read_parquet(regret_file)
                if regret_df.empty or 'strategy' not in regret_df.columns:
                    return regret

                # Legacy compatibility:
                # Some runs only store [strategy, cumulative_regret].
                if 'cum_regret' not in regret_df.columns and 'cumulative_regret' in regret_df.columns:
                    regret_df = regret_df.rename(columns={'cumulative_regret': 'cum_regret'})

                if 'date' in regret_df.columns:
                    latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
                else:
                    latest_regret = regret_df.groupby('strategy').tail(1)

                # Derive missing normalized fields when absent.
                if 'cum_regret' not in latest_regret.columns:
                    latest_regret['cum_regret'] = 0.0
                latest_regret['cum_regret'] = pd.to_numeric(latest_regret['cum_regret'], errors='coerce').fillna(0.0)

                rmin = float(latest_regret['cum_regret'].min())
                rmax = float(latest_regret['cum_regret'].max())
                if rmax > rmin:
                    inferred_norm = (latest_regret['cum_regret'] - rmin) / (rmax - rmin)
                else:
                    inferred_norm = pd.Series(0.5, index=latest_regret.index)

                if 'normalized_regret' not in latest_regret.columns:
                    latest_regret['normalized_regret'] = inferred_norm
                else:
                    latest_regret['normalized_regret'] = pd.to_numeric(
                        latest_regret['normalized_regret'], errors='coerce'
                    ).fillna(inferred_norm)

                if 'penalty_score' not in latest_regret.columns:
                    latest_regret['penalty_score'] = latest_regret['normalized_regret']
                else:
                    latest_regret['penalty_score'] = pd.to_numeric(
                        latest_regret['penalty_score'], errors='coerce'
                    ).fillna(latest_regret['normalized_regret'])
                if 'regret_30d' not in latest_regret.columns:
                    latest_regret['regret_30d'] = latest_regret['cum_regret']
                if 'regret_90d' not in latest_regret.columns:
                    latest_regret['regret_90d'] = latest_regret['cum_regret']
                if 'drawdown' not in latest_regret.columns:
                    latest_regret['drawdown'] = 0.0
                
                for _, row in latest_regret.iterrows():
                    regret[row['strategy']] = {
                        'cum_regret': float(row['cum_regret']),
                        'regret_30d': float(row['regret_30d']),
                        'regret_90d': float(row['regret_90d']),
                        'normalized_regret': float(row['normalized_regret']),
                        'penalty_score': float(row['penalty_score']),
                        'drawdown': float(row['drawdown'])
                    }
                
                print(f"   ✅ Loaded regret for {len(regret)} strategies")
                
            except Exception as e:
                print(f"   ⚠️ Error loading regret: {e}")
        
        return regret
    
    def load_no_edge_state(self):
        """Load NO_EDGE state from detector"""
        
        print("🚨 Loading NO_EDGE state...")
        
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            from intelligence.no_edge_detector import NoEdgeDetector
            
            detector = NoEdgeDetector()
            current_state = detector.get_current_state()
            
            print(f"   📊 Current state: {current_state['state']}")
            print(f"   📊 Exposure cap: {current_state['exposure_cap']:.0%}")
            if current_state['reasons']:
                print(f"   📊 Reasons: {len(current_state['reasons'])}")
            
            return current_state
            
        except Exception as e:
            print(f"   ⚠️ Error loading NO_EDGE state: {e}")
            
            # Fallback: try to load directly from file
            try:
                no_edge_file = 'data/intelligence/no_edge_state.parquet'
                if os.path.exists(no_edge_file):
                    state_df = pd.read_parquet(no_edge_file)
                    
                    if not state_df.empty:
                        latest = state_df.iloc[-1]
                        # Canonical schema
                        if 'exposure_cap' in state_df.columns:
                            reasons_raw = latest.get('reasons', '')
                            reasons = reasons_raw.split('; ') if isinstance(reasons_raw, str) and reasons_raw else []
                            return {
                                'state': latest.get('state', 'NORMAL'),
                                'exposure_cap': float(latest.get('exposure_cap', 0.8)),
                                'reasons': reasons,
                                'date': latest.get('date')
                            }

                        # Legacy schema compatibility
                        state_val = str(latest.get('state', 'NORMAL')).upper()
                        if state_val not in {'NORMAL', 'NO_EDGE'}:
                            edge_strength = float(pd.to_numeric(latest.get('edge_strength', np.nan), errors='coerce'))
                            confidence = float(pd.to_numeric(latest.get('confidence', np.nan), errors='coerce'))
                            state_val = 'NO_EDGE' if (
                                (not np.isnan(edge_strength) and edge_strength < 0.45) or
                                (not np.isnan(confidence) and confidence < 0.55)
                            ) else 'NORMAL'
                        return {
                            'state': state_val,
                            'exposure_cap': 0.2 if state_val == 'NO_EDGE' else 0.8,
                            'reasons': [],
                            'date': latest['date']
                        }
                
            except Exception as e2:
                print(f"   ⚠️ Fallback loading also failed: {e2}")
            
            # Ultimate fallback
            return {
                'state': 'NORMAL',
                'exposure_cap': 0.8,
                'reasons': [],
                'date': datetime.now().date()
            }
    def calculate_regret(self, strategy_data):
        """Calculate and update regret for each strategy"""
        
        print("😈 Calculating strategy regret...")
        
        # Load existing regret or initialize
        if os.path.exists(self.paths['strategy_regret']):
            regret_df = pd.read_parquet(self.paths['strategy_regret'])
            regret = regret_df.set_index('strategy')['cumulative_regret'].to_dict()
        else:
            regret = {}
        
        # Find best performer each day
        all_returns = {}
        max_length = 0
        
        for strategy, data in strategy_data.items():
            returns = data.get('recent_returns', [])
            if returns:
                all_returns[strategy] = returns
                max_length = max(max_length, len(returns))
        
        if not all_returns:
            return regret
        
        # Calculate daily regret
        for i in range(max_length):
            daily_returns = {}
            for strategy, returns in all_returns.items():
                if i < len(returns):
                    daily_returns[strategy] = returns[i]
            
            if daily_returns:
                best_return = max(daily_returns.values())
                
                for strategy, return_val in daily_returns.items():
                    if strategy not in regret:
                        regret[strategy] = 0.0
                    regret[strategy] += max(0, best_return - return_val)
        
        # Save regret
        regret_df = pd.DataFrame(list(regret.items()), columns=['strategy', 'cumulative_regret'])
        regret_df.to_parquet(self.paths['strategy_regret'], index=False)
        
        print(f"   ✅ Updated regret for {len(regret)} strategies")
        return regret
    
    def calculate_health_scores(self, strategy_data, beliefs, regret, regime, tailwinds):
        """Calculate comprehensive health scores using beliefs, regret, and tailwinds"""
        
        print("⚖️ Calculating strategy health scores with beliefs, regret, and tailwinds...")
        
        health_scores = {}
        
        for strategy, data in strategy_data.items():
            # Get beliefs data
            belief_data = beliefs.get(strategy, {})
            regret_data = regret.get(strategy, {})
            tailwind_data = tailwinds.get(strategy, {})
            
            # Skip if strategy is not ACTIVE or FADING
            if belief_data.get('status') not in ['ACTIVE', 'FADING']:
                # But don't completely kill strategies with good Sharpe ratios or tailwinds
                sharpe = data.get('sharpe', 0)
                tailwind_score = tailwind_data.get('combined_score', 0)
                
                if sharpe > 1.0 or tailwind_score > 1.5:  # Give high-performing strategies a chance
                    print(f"   🔄 Rescuing high-performing strategy: {strategy} (Sharpe: {sharpe:.2f}, Tailwind: {tailwind_score:.2f})")
                    # Override status for allocation - continue processing this strategy
                    belief_data = dict(belief_data)
                    belief_data['status'] = 'FADING'
                    # Don't skip - let it continue to health calculation
                else:
                    health_scores[strategy] = {
                        'health_score': -999,  # Kill non-active strategies
                        'effective_skill': 0,
                        'regret_penalty': 1.0,
                        'tailwind_score': tailwind_score,
                        'status': belief_data.get('status', 'UNKNOWN'),
                        'alive': False
                    }
                    continue
            
            # Core belief metrics
            effective_skill = belief_data.get('effective_skill', 0.1)
            skill_prob = belief_data.get('skill_prob', 0.5)
            confidence = belief_data.get('confidence', 0.1)
            regime_fit = belief_data.get('regime_fit', 1.0)
            
            # Regret penalties
            normalized_regret = regret_data.get('normalized_regret', 0.5)
            penalty_score = regret_data.get('penalty_score', 0.5)
            drawdown = abs(regret_data.get('drawdown', 0))
            
            # Tailwind enhancement
            tailwind_score = tailwind_data.get('combined_score', 1.0)
            regime_tailwind = tailwind_data.get('regime_tailwind', 1.0)
            
            # Performance metrics
            sharpe = data.get('sharpe', 0)
            ann_return = data.get('ann_return', 0)
            
            # Calculate final score using beliefs + regret + tailwinds
            base_score = (
                effective_skill -
                0.3 * normalized_regret -
                0.2 * drawdown
            )
            
            # Apply tailwind boost (30% weight on tailwinds)
            tailwind_boost = 0.3 * (tailwind_score - 1.0)  # Neutral tailwind = 1.0
            final_score = base_score + tailwind_boost
            
            # Apply legacy regime boost (for backward compatibility)
            current_regime = regime.get('macro_regime', 'neutral')
            legacy_regime_boost = self.regime_boosts.get(current_regime, {}).get(strategy, 1.0)
            final_score *= legacy_regime_boost
            
            # Determine if strategy is alive (enhanced criteria with tailwinds)
            is_alive = (
                (
                    final_score >= self.params['min_alive_score'] and
                    skill_prob >= self.params['min_alive_skill_prob'] and
                    confidence >= self.params['min_alive_confidence'] and
                    tailwind_score >= self.params['min_alive_tailwind']
                ) or
                (
                    sharpe > 1.25 and tailwind_score >= 0.95
                )
            )

            health_scores[strategy] = {
                'health_score': final_score,
                'base_score': base_score,
                'tailwind_boost': tailwind_boost,
                'effective_skill': effective_skill,
                'skill_prob': skill_prob,
                'confidence': confidence,
                'regime_fit': regime_fit,
                'normalized_regret': normalized_regret,
                'penalty_score': penalty_score,
                'regime_boost': legacy_regime_boost,
                'tailwind_score': tailwind_score,
                'regime_tailwind': regime_tailwind,
                'sharpe': sharpe,
                'ann_return': ann_return,
                'drawdown': drawdown,
                'status': belief_data.get('status', 'ACTIVE'),
                'alive': is_alive
            }
        
        print(f"   ✅ Calculated health scores for {len(health_scores)} strategies")
        
        # Show enhanced filtering
        active_count = sum(1 for h in health_scores.values() if h['status'] == 'ACTIVE')
        alive_count = sum(1 for h in health_scores.values() if h['alive'])
        tailwind_boosted = sum(1 for h in health_scores.values() if h.get('tailwind_boost', 0) > 0)
        
        print(f"   📊 Active strategies: {active_count}")
        print(f"   📊 Alive strategies: {alive_count}")
        print(f"   🌬️ Tailwind boosted: {tailwind_boosted}")
        
        return health_scores
    
    def allocate_capital(self, health_scores, no_edge_state, edge_health=None, strategy_data=None, freeze_state=None):
        """Allocate capital using risk-normalized optimization with turnover governance."""
        
        print("🎯 Allocating capital across strategies...")
        edge_health = edge_health or {}
        strategy_data = strategy_data or {}
        freeze_state = freeze_state or {'freeze_active': False, 'actions': {}}
        
        # Apply NO_EDGE exposure capping
        exposure_cap = float(no_edge_state.get('exposure_cap', 0.8))
        if freeze_state.get('freeze_active'):
            freeze_cap = float((freeze_state.get('actions') or {}).get(
                'target_max_exposure',
                self.params.get('freeze_max_exposure', 0.15),
            ))
            exposure_cap = min(exposure_cap, freeze_cap)
            no_edge_state = dict(no_edge_state)
            no_edge_state['exposure_cap'] = exposure_cap

        is_no_edge = no_edge_state.get('state') == 'NO_EDGE'
        
        if is_no_edge:
            print(f"   🚨 NO_EDGE state detected - capping exposure at {exposure_cap:.0%}")
            print(f"   🚨 Reasons: {', '.join(no_edge_state.get('reasons', []))}")
        if freeze_state.get('freeze_active'):
            print(f"   🧊 Freeze mode active - exposure clamped to {exposure_cap:.0%}")
        
        # Filter alive strategies
        alive_strategies = {k: v for k, v in health_scores.items() if v['alive']}

        # Keep only the strongest conviction set to reduce dilution.
        max_live = max(1, int(self.params.get('max_live_strategies', 8)))
        if len(alive_strategies) > max_live:
            ranked = sorted(
                alive_strategies.items(),
                key=lambda kv: (
                    kv[1].get('health_score', 0.0) *
                    kv[1].get('skill_prob', 0.5) *
                    max(0.5, kv[1].get('tailwind_score', 1.0)) *
                    max(0.25, edge_health.get(kv[0], 1.0))
                ),
                reverse=True,
            )
            alive_strategies = dict(ranked[:max_live])
            print(f"   🎯 High-conviction concentration: keeping top {len(alive_strategies)} strategies")
        
        if not alive_strategies:
            print("   ⚠️ No strategies alive! Using fallback allocation...")
            
            # Fallback: allocate to strategies with best raw performance
            fallback_strategies = {}
            for strategy, data in health_scores.items():
                if data.get('sharpe', 0) > 0.5:  # Positive Sharpe strategies
                    fallback_strategies[strategy] = data
            
            if fallback_strategies:
                print(f"   🔄 Using {len(fallback_strategies)} fallback strategies")
                alive_strategies = fallback_strategies
            else:
                # Ultimate fallback: equal weight top 3 by Sharpe
                sorted_by_sharpe = sorted(health_scores.items(), 
                                        key=lambda x: x[1].get('sharpe', -999), reverse=True)
                top_3 = dict(sorted_by_sharpe[:3])
                
                # Apply NO_EDGE capping to fallback allocation
                equal_weight = exposure_cap / len(top_3)
                allocations = {k: equal_weight for k in top_3.keys()}
                
                print(f"   🆘 Emergency allocation: equal weight to top 3 strategies (capped at {exposure_cap:.0%})")
                return allocations

        previous_allocations = self._load_previous_allocations()
        allocations = self._risk_normalized_optimizer(
            alive_strategies=alive_strategies,
            health_scores=health_scores,
            strategy_data=strategy_data,
            exposure_cap=exposure_cap,
            previous_allocations=previous_allocations,
            freeze_state=freeze_state,
        )

        # Fallback path if optimizer lacks enough return history.
        if not allocations:
            print("   ⚠️ Optimizer fallback: insufficient return matrix, using softmax conviction allocation")
            scored = {}
            for strategy, data in alive_strategies.items():
                score = float(max(0.0, data.get('health_score', 0.0)) * data.get('skill_prob', 0.5))
                if score > 0:
                    scored[strategy] = score
            if not scored:
                scored = {k: 1.0 for k in alive_strategies.keys()}
            vals = np.array(list(scored.values()), dtype=float)
            exp_vals = np.exp(vals / max(1e-6, float(self.params.get('temperature', 0.75))))
            raw = exp_vals / np.clip(exp_vals.sum(), 1e-12, None)
            allocations = {
                s: float(raw[i] * exposure_cap)
                for i, s in enumerate(scored.keys())
            }
            self.last_optimizer_diagnostics = {
                'method': 'softmax_fallback',
                'n_strategies': len(allocations),
            }

        # Apply edge half-life decay (capital decay)
        if allocations:
            alpha = self.params.get('edge_decay_alpha', 2.0)
            allocations = {
                k: v * (edge_health.get(k, 1.0) ** alpha) for k, v in allocations.items()
            }
            total_alloc = sum(allocations.values())
            if total_alloc > 0:
                scale_factor = min(1.0, exposure_cap / total_alloc)
                allocations = {k: v * scale_factor for k, v in allocations.items()}
        
        final_exposure = sum(allocations.values())
        print(f"   ✅ Allocated capital across {len(allocations)} strategies")
        print(f"   📊 Total exposure: {final_exposure:.1%} (cap: {exposure_cap:.0%})")
        if self.last_optimizer_diagnostics:
            method = self.last_optimizer_diagnostics.get('method', 'unknown')
            print(f"   🧮 Allocator method: {method}")
        
        return allocations
    
    def save_allocations(self, allocations, regime, health_scores, no_edge_state, freeze_state=None):
        """Save capital allocations and history with NO_EDGE state"""
        
        timestamp = datetime.now()
        freeze_state = freeze_state or {'freeze_active': False, 'actions': {}}
        parameter_version = {}
        try:
            p = self.paths.get('parameter_version')
            if p and os.path.exists(p):
                with open(p, 'r') as f:
                    parameter_version = json.load(f)
        except Exception:
            parameter_version = {}
        
        # Current allocation
        allocation_data = {
            'timestamp': timestamp.isoformat(),
            'date': timestamp.date().isoformat(),
            'regime': regime,
            'no_edge_state': no_edge_state,
            'freeze_state': freeze_state,
            'allocations': allocations,
            'strategy_health': {k: v['health_score'] for k, v in health_scores.items()},
            'strategy_fabric_multipliers': {k: float(v.get('fabric_multiplier', 1.0)) for k, v in health_scores.items()},
            'edge_health': self.load_edge_half_life(),
            'optimizer_diagnostics': self.last_optimizer_diagnostics,
            'parameter_version': {
                'version_id': parameter_version.get('version_id', 'unknown'),
                'git_commit': parameter_version.get('git_commit', 'unknown'),
            },
            'total_strategies': len(allocations),
            'alive_strategies': sum(1 for v in health_scores.values() if v['alive']),
            'total_exposure': sum(allocations.values()),
            'exposure_cap': no_edge_state.get('exposure_cap', 0.8)
        }
        
        # Save current allocations
        with open(self.paths['capital_allocations'], 'w') as f:
            json.dump(allocation_data, f, indent=2, default=str)
        
        # Update allocation history
        history_row = {
            'date': timestamp.date(),
            'regime': regime.get('macro_regime', 'neutral'),
            'no_edge_state': no_edge_state.get('state', 'NORMAL'),
            'freeze_active': bool(freeze_state.get('freeze_active', False)),
            'exposure_cap': no_edge_state.get('exposure_cap', 0.8),
            'total_exposure': sum(allocations.values()),
            **allocations
        }
        
        if os.path.exists(self.paths['allocation_history']):
            history_df = pd.read_parquet(self.paths['allocation_history'])
            history_df = pd.concat([history_df, pd.DataFrame([history_row])], ignore_index=True)
        else:
            history_df = pd.DataFrame([history_row])
        
        history_df.to_parquet(self.paths['allocation_history'], index=False)
        
        print(f"   ✅ Saved allocations: {self.paths['capital_allocations']}")
        print(f"   📊 NO_EDGE state: {no_edge_state.get('state', 'NORMAL')}")
        print(f"   📊 Exposure cap: {no_edge_state.get('exposure_cap', 0.8):.0%}")
    
    def run_allocation(self):
        """Main allocation process with beliefs and regret integration"""
        
        print("🧠 CAPITAL ALLOCATOR - BAYESIAN MODEL ALLOCATION")
        print("=" * 60)
        
        # Load data
        strategy_data = self.load_strategy_performance()
        regime = self.load_market_regime()
        
        if not strategy_data:
            print("❌ No strategy performance data available")
            return {}
        
        # Load beliefs, regret, tailwinds, NO_EDGE state, and edge decay (FULLY ENHANCED!)
        beliefs = self.load_strategy_beliefs()
        regret = self.load_strategy_regret()
        tailwinds = self.load_strategy_tailwinds()
        fabric_insights = self.load_weekly_fabric_insights()
        no_edge_state = self.load_no_edge_state()
        edge_health = self.load_edge_half_life()
        freeze_state = self.load_model_freeze_state()

        if freeze_state.get('freeze_active'):
            freeze_cap = float((freeze_state.get('actions') or {}).get(
                'target_max_exposure',
                self.params.get('freeze_max_exposure', 0.15),
            ))
            original_cap = float(no_edge_state.get('exposure_cap', 0.8))
            no_edge_state = dict(no_edge_state)
            no_edge_state['exposure_cap'] = min(original_cap, freeze_cap)
            reasons = list(no_edge_state.get('reasons', []))
            reasons.append("model_freeze_active")
            no_edge_state['reasons'] = reasons
            print(
                f"   🧊 Freeze governance active: exposure cap "
                f"{original_cap:.0%} -> {no_edge_state['exposure_cap']:.0%}"
            )
        
        # Calculate health scores using beliefs, regret, and tailwinds
        health_scores = self.calculate_health_scores(strategy_data, beliefs, regret, regime, tailwinds)
        health_scores = self.apply_weekly_fabric_conditioning(health_scores, fabric_insights)
        
        # Allocate capital with NO_EDGE exposure capping
        allocations = self.allocate_capital(
            health_scores,
            no_edge_state,
            edge_health,
            strategy_data=strategy_data,
            freeze_state=freeze_state,
        )
        
        # Save results
        if allocations:
            self.save_allocations(allocations, regime, health_scores, no_edge_state, freeze_state=freeze_state)
            
            # Print fully enhanced summary
            print(f"\n📊 FULLY ENHANCED CAPITAL ALLOCATION SUMMARY (WITH NO_EDGE)")
            print(f"   Regime: {regime.get('macro_regime', 'neutral')}")
            print(f"   NO_EDGE State: {no_edge_state.get('state', 'NORMAL')}")
            print(f"   Freeze State: {'ACTIVE' if freeze_state.get('freeze_active') else 'inactive'}")
            print(f"   Exposure Cap: {no_edge_state.get('exposure_cap', 0.8):.0%}")
            print(f"   Total Exposure: {sum(allocations.values()):.1%}")
            print(f"   Active Strategies: {len(allocations)}")
            print(f"\n   Top Allocations (with beliefs + tailwinds + NO_EDGE):")
            
            sorted_allocs = sorted(allocations.items(), key=lambda x: x[1], reverse=True)
            for strategy, allocation in sorted_allocs[:5]:
                health = health_scores.get(strategy, {})
                skill = health.get('skill_prob', 0)
                regret = health.get('normalized_regret', 0)
                tailwind = health.get('tailwind_score', 0)
                status = health.get('status', 'UNKNOWN')
                
                print(f"     {strategy}: {allocation:.1%} "
                      f"(skill: {skill:.1%}, regret: {regret:.1%}, tailwind: {tailwind:.2f}, {status})")
            
            if no_edge_state.get('reasons'):
                print(f"\n   🚨 NO_EDGE Reasons:")
                for i, reason in enumerate(no_edge_state['reasons'], 1):
                    print(f"     {i}. {reason}")
        
        return allocations

def main():
    """Main execution function"""
    
    allocator = CapitalAllocator()
    allocations = allocator.run_allocation()
    
    return allocations

if __name__ == "__main__":
    main()
