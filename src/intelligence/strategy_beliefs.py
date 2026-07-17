#!/usr/bin/env python3
"""
🧠 STRATEGY BELIEFS ENGINE - BAYESIAN INTELLIGENCE
The brain that tracks what we believe about each strategy's skill

This is not performance tracking - this is belief tracking.
"How good do we think each strategy really is?"

Usage:
    try:
    from src.intelligence.strategy_beliefs import StrategyBeliefs
except ImportError:
    from StrategyBeliefs import StrategyBeliefs
    
    beliefs = StrategyBeliefs()
    beliefs.update_beliefs()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from scipy.stats import beta
import warnings
warnings.filterwarnings('ignore')

try:
    from src.intelligence.strategy_surface_policy import (
        is_archived_strategy,
        is_feature_only_strategy,
        overlay_config,
        strategy_overlay_parent,
        strategy_overlay_weight,
    )
except Exception:
    from strategy_surface_policy import (  # type: ignore
        is_archived_strategy,
        is_feature_only_strategy,
        overlay_config,
        strategy_overlay_parent,
        strategy_overlay_weight,
    )

class StrategyBeliefs:
    """
    Bayesian Strategy Belief Engine
    
    Tracks our evolving beliefs about strategy skill using:
    - Alpha/Beta evidence accumulation
    - Regime fitness assessment
    - Confidence measurement
    - Status lifecycle management
    """
    
    def __init__(self):
        self.name = "Strategy Beliefs Engine"
        self.version = "3.0"
        
        # File paths
        self.paths = {
            'beliefs': 'data/processed/strategy_beliefs.parquet',
            'backtests': 'data/processed/backtests',
            'market_state': 'data/processed/market_state.parquet',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'feature_overlays': 'data/processed/strategy_feature_overlays.json'
        }
        self._latest_feature_overlays = {}
        
        # Belief parameters (production-ready thresholds)
        self.params = {
            'skill_threshold': 0.25,      # Below this = FADING (very lenient)
            'suspend_threshold': 0.15,    # Below this = SUSPENDED (very lenient)
            'confidence_threshold': 0.1,  # Minimum confidence for ACTIVE (very lenient)
            'regime_lookback': 90,        # Days for regime fitness
            'evidence_decay': 0.99,       # Daily decay factor (minimal decay)
            'min_observations': 10,       # Minimum trades for belief (reduced)
            'reactivation_threshold': 0.30  # Skill needed to reactivate (lowered)
        }
        
        # Strategy status lifecycle
        self.status_rules = {
            'ACTIVE': 'skill_prob >= 0.45 and confidence >= 0.6',
            'FADING': '0.35 <= skill_prob < 0.45 or confidence < 0.6',
            'SUSPENDED': 'skill_prob < 0.35 or major_failure',
            'REACTIVATED': 'was_suspended and skill_prob >= 0.55'
        }
        
        # Regime boosts for fitness calculation
        self.regime_fitness = {
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
        self.family_regime_fitness = {
            'crisis': {'sentiment': 0.90, 'alternative': 0.92, 'ownership': 0.95},
            'boom': {'sentiment': 1.10, 'alternative': 1.12, 'ownership': 1.05},
            'expansion': {'sentiment': 1.12, 'alternative': 1.08, 'ownership': 1.08},
            'late-expansion': {'sentiment': 1.02, 'alternative': 1.10, 'ownership': 1.12},
            'slowdown': {'sentiment': 0.96, 'alternative': 1.05, 'ownership': 1.08},
            'tightening': {'sentiment': 0.94, 'alternative': 1.00, 'ownership': 1.06},
        }

    @staticmethod
    def _strategy_family(strategy: str) -> str:
        s = str(strategy or "").strip().lower()
        if any(token in s for token in ('ownership', 'shareholding', 'promoter')):
            return 'ownership'
        if any(token in s for token in ('sentiment', 'news')):
            return 'sentiment'
        if any(token in s for token in ('alternative', 'announcement', 'bulk', 'credit', 'pledge')):
            return 'alternative'
        return ''

    def _normalize_existing_beliefs_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize legacy beliefs schemas into the canonical schema used by V3.

        Legacy files in this repo may contain only:
        [strategy, belief_strength, timestamp]
        This method upgrades them in-memory so downstream logic does not break.
        """
        if df is None or df.empty:
            return pd.DataFrame()

        norm = df.copy()

        # Canonical time column
        if 'date' not in norm.columns:
            if 'timestamp' in norm.columns:
                norm['date'] = pd.to_datetime(norm['timestamp'], errors='coerce')
            else:
                norm['date'] = pd.Timestamp.utcnow()
        else:
            norm['date'] = pd.to_datetime(norm['date'], errors='coerce')
        norm['date'] = norm['date'].fillna(pd.Timestamp.utcnow())

        # Canonical key columns
        if 'strategy' not in norm.columns:
            return pd.DataFrame()
        norm['strategy'] = norm['strategy'].astype(str)

        # Map minimal legacy beliefs to Bayesian fields
        if 'skill_prob' not in norm.columns:
            if 'belief_strength' in norm.columns:
                norm['skill_prob'] = pd.to_numeric(norm['belief_strength'], errors='coerce')
            else:
                norm['skill_prob'] = 0.5
        norm['skill_prob'] = pd.to_numeric(norm['skill_prob'], errors='coerce').fillna(0.5).clip(0.01, 0.99)
        if 'belief_strength' not in norm.columns:
            norm['belief_strength'] = norm['skill_prob']
        norm['belief_strength'] = pd.to_numeric(norm['belief_strength'], errors='coerce').fillna(norm['skill_prob']).clip(0.01, 0.99)

        defaults = {
            'confidence': 0.5,
            'effective_skill': norm['skill_prob'],
            'regime_fit': 1.0,
            'sharpe': 0.0,
            'mean_return': 0.0,
            'volatility': 0.0,
            'total_observations': 0,
            'regime': 'neutral',
        }

        for col, default in defaults.items():
            if col not in norm.columns:
                norm[col] = default
            else:
                if isinstance(default, (int, float)):
                    norm[col] = pd.to_numeric(norm[col], errors='coerce').fillna(default)
                else:
                    norm[col] = norm[col].fillna(default)

        # Reconstruct Beta priors if missing
        if 'alpha' not in norm.columns:
            norm['alpha'] = (norm['skill_prob'] * 20.0).clip(lower=1.0)
        else:
            norm['alpha'] = pd.to_numeric(norm['alpha'], errors='coerce').fillna((norm['skill_prob'] * 20.0)).clip(lower=1.0)

        if 'beta' not in norm.columns:
            norm['beta'] = ((1.0 - norm['skill_prob']) * 20.0).clip(lower=1.0)
        else:
            norm['beta'] = pd.to_numeric(norm['beta'], errors='coerce').fillna(((1.0 - norm['skill_prob']) * 20.0)).clip(lower=1.0)

        if 'status' not in norm.columns:
            norm['status'] = np.where(norm['skill_prob'] >= 0.45, 'ACTIVE', 'FADING')
        else:
            status_default = pd.Series(
                np.where(norm['skill_prob'] >= 0.45, 'ACTIVE', 'FADING'),
                index=norm.index
            )
            norm['status'] = norm['status'].where(norm['status'].notna(), status_default)

        if 'strategy' in norm.columns:
            strategy_series = norm['strategy'].astype(str)
            keep_mask = ~strategy_series.map(
                lambda s: is_feature_only_strategy(s) or is_archived_strategy(s)
            )
            norm = norm.loc[keep_mask].copy()

        return norm

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            parsed = float(value)
        except Exception:
            return float(default)
        if not np.isfinite(parsed):
            return float(default)
        return float(parsed)

    def _feature_overlay_signal(self, metrics):
        sharpe = self._safe_float(metrics.get('sharpe', 0.0), 0.0)
        annualized = self._safe_float(metrics.get('mean_return', 0.0), 0.0) * 252.0
        total_return = self._safe_float(metrics.get('total_return', 0.0), 0.0)
        signal = (
            0.55 * np.tanh(sharpe / 3.0) +
            0.30 * np.tanh(annualized / 0.20) +
            0.15 * np.tanh(total_return / 0.20)
        )
        cap = self._safe_float(overlay_config().get('signal_cap', 1.0), 1.0)
        cap = max(0.1, cap)
        return float(np.clip(signal, -cap, cap))

    def _build_feature_overlays(self, feature_metrics):
        overlays_by_parent = {}
        max_impact = self._safe_float(overlay_config().get('max_abs_score_impact', 0.12), 0.12)

        for strategy, metrics in feature_metrics.items():
            parent = strategy_overlay_parent(strategy)
            weight = strategy_overlay_weight(strategy)
            signal = self._feature_overlay_signal(metrics)
            overlays_by_parent.setdefault(parent, []).append({
                'strategy': strategy,
                'weight': weight,
                'signal': signal,
                'family': self._strategy_family(strategy) or 'legacy_feature',
                'sharpe': self._safe_float(metrics.get('sharpe', 0.0), 0.0),
                'mean_return': self._safe_float(metrics.get('mean_return', 0.0), 0.0),
                'total_return': self._safe_float(metrics.get('total_return', 0.0), 0.0),
                'observations': int(self._safe_float(metrics.get('observations', 0), 0)),
            })

        payload = {
            'timestamp': datetime.now().isoformat(),
            'source': 'strategy_beliefs',
            'overlays': {},
        }

        for parent, rows in overlays_by_parent.items():
            total_weight = sum(max(0.0, self._safe_float(row.get('weight', 0.0), 0.0)) for row in rows)
            if total_weight <= 0:
                continue
            raw_signal = sum(
                self._safe_float(row.get('weight', 0.0), 0.0) * self._safe_float(row.get('signal', 0.0), 0.0)
                for row in rows
            ) / total_weight
            overlay_score = float(np.clip(raw_signal * max_impact, -max_impact, max_impact))
            positive_share = sum(
                self._safe_float(row.get('weight', 0.0), 0.0)
                for row in rows
                if self._safe_float(row.get('signal', 0.0), 0.0) > 0
            ) / total_weight
            payload['overlays'][parent] = {
                'parent_strategy': parent,
                'component_count': len(rows),
                'overlay_score': overlay_score,
                'raw_signal': float(np.clip(raw_signal, -1.0, 1.0)),
                'positive_share': float(np.clip(positive_share, 0.0, 1.0)),
                'components': rows,
            }

        return payload

    def _save_feature_overlays(self, payload):
        path = self.paths.get('feature_overlays')
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2, default=str)
    
    def load_existing_beliefs(self):
        """Load existing beliefs or initialize"""
        
        if os.path.exists(self.paths['beliefs']):
            try:
                beliefs_df = pd.read_parquet(self.paths['beliefs'])
                beliefs_df = self._normalize_existing_beliefs_df(beliefs_df)
                if beliefs_df.empty:
                    return {}
                # Get latest beliefs for each strategy
                latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
                return latest_beliefs.set_index('strategy').to_dict('index')
            except Exception as e:
                print(f"   ⚠️ Error loading existing beliefs: {e}")
        
        return {}
    
    def load_strategy_performance(self):
        """Load recent strategy performance for belief updates"""
        
        print("📊 Loading strategy performance for belief updates...")
        
        strategy_data = {}
        feature_metrics = {}
        
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    if is_archived_strategy(strategy_name):
                        continue
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty and len(df) > self.params['min_observations']:
                            # Get recent performance
                            recent_df = df.tail(self.params['regime_lookback'])
                            
                            returns = recent_df['daily_return']
                            equity = recent_df['equity']
                            
                            # Calculate key metrics
                            total_return = equity.iloc[-1] / equity.iloc[0] - 1
                            mean_return = returns.mean()
                            volatility = returns.std() * np.sqrt(252)
                            sharpe = (mean_return * 252) / volatility if volatility > 0 else 0
                            
                            # Win/loss evidence
                            wins = (returns > 0).sum()
                            losses = (returns <= 0).sum()
                            
                            payload = {
                                'returns': returns.tolist(),
                                'mean_return': mean_return,
                                'volatility': volatility,
                                'sharpe': sharpe,
                                'total_return': total_return,
                                'wins': wins,
                                'losses': losses,
                                'observations': len(returns)
                            }
                            if is_feature_only_strategy(strategy_name):
                                feature_metrics[strategy_name] = payload
                            else:
                                strategy_data[strategy_name] = payload
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")

        overlay_payload = self._build_feature_overlays(feature_metrics)
        self._latest_feature_overlays = dict(overlay_payload.get('overlays', {}) or {})
        self._save_feature_overlays(overlay_payload)

        print(f"   ✅ Loaded performance for {len(strategy_data)} standalone strategies")
        if feature_metrics:
            print(f"   🔗 Folded {len(feature_metrics)} legacy sleeves into bounded overlays")
        return strategy_data
    
    def get_current_regime(self):
        """Get current market regime for fitness calculation"""
        
        try:
            if os.path.exists(self.paths['market_state']):
                market_df = pd.read_parquet(self.paths['market_state'])
                if not market_df.empty:
                    latest = market_df.iloc[-1]
                    return latest.get('macro_regime', 'neutral')
        except Exception as e:
            print(f"   ⚠️ Could not load regime: {e}")
        
        return 'neutral'
    
    def calculate_regime_fitness(self, strategy, regime):
        """Calculate how well strategy fits current regime"""
        
        regime_map = self.regime_fitness.get(regime, {})
        base_fitness = regime_map.get(strategy)
        if base_fitness is None:
            family = self._strategy_family(strategy)
            base_fitness = self.family_regime_fitness.get(regime, {}).get(family, 1.0)

        # Real-data-only deterministic fitness: no stochastic perturbation.
        return float(np.clip(base_fitness, 0.5, 2.0))
    
    def update_strategy_belief(self, strategy, existing_belief, performance_data, regime):
        """Update Bayesian belief for a single strategy"""
        
        # Initialize or load existing belief
        if existing_belief:
            alpha = existing_belief.get('alpha', 1.0)
            beta = existing_belief.get('beta', 1.0)
            total_observations = existing_belief.get('total_observations', 0)
        else:
            alpha = 1.0  # Prior success
            beta = 1.0   # Prior failure
            total_observations = 0
        
        # Apply evidence decay to old beliefs
        decay = self.params['evidence_decay'] ** (performance_data['observations'] / 252)
        alpha *= decay
        beta *= decay
        
        # Add new evidence
        new_wins = performance_data['wins']
        new_losses = performance_data['losses']
        
        alpha += new_wins
        beta += new_losses
        total_observations += performance_data['observations']
        
        # Calculate belief metrics
        skill_prob = alpha / (alpha + beta)
        confidence = min(np.sqrt(alpha + beta) / 10, 1.0)  # Normalized confidence
        
        # Performance metrics
        mean_return = performance_data['mean_return']
        volatility = performance_data['volatility']
        sharpe = performance_data['sharpe']
        
        # Regime fitness
        regime_fit = self.calculate_regime_fitness(strategy, regime)
        
        # Effective skill (skill adjusted for regime and performance)
        effective_skill = skill_prob * max(sharpe, 0) * regime_fit
        
        # Determine status
        status = self.determine_status(skill_prob, confidence, effective_skill, existing_belief)
        
        # Create updated belief
        updated_belief = {
            'date': datetime.now(),  # Use datetime object, not date
            'strategy': strategy,
            'belief_strength': skill_prob,
            'alpha': alpha,
            'beta': beta,
            'skill_prob': skill_prob,
            'mean_return': mean_return,
            'volatility': volatility,
            'sharpe': sharpe,
            'regime_fit': regime_fit,
            'confidence': confidence,
            'effective_skill': effective_skill,
            'status': status,
            'total_observations': total_observations,
            'regime': regime
        }
        
        return updated_belief
    
    def determine_status(self, skill_prob, confidence, effective_skill, existing_belief):
        """Determine strategy status based on belief metrics"""
        
        current_status = existing_belief.get('status', 'ACTIVE') if existing_belief else 'ACTIVE'
        
        # Status transition rules
        if current_status == 'SUSPENDED':
            # Can only reactivate if skill is high enough
            if skill_prob >= self.params['reactivation_threshold'] and confidence >= 0.7:
                return 'REACTIVATED'
            else:
                return 'SUSPENDED'
        
        elif skill_prob < self.params['suspend_threshold']:
            return 'SUSPENDED'
        
        elif skill_prob < self.params['skill_threshold'] or confidence < self.params['confidence_threshold']:
            return 'FADING'
        
        else:
            return 'ACTIVE'
    
    def update_all_beliefs(self):
        """Update beliefs for all strategies"""
        
        print("🧠 UPDATING STRATEGY BELIEFS")
        print("=" * 50)
        
        # Load data
        existing_beliefs = self.load_existing_beliefs()
        performance_data = self.load_strategy_performance()
        current_regime = self.get_current_regime()
        
        print(f"📊 Current regime: {current_regime}")
        print(f"🧠 Updating beliefs for {len(performance_data)} strategies")
        
        # Update beliefs
        updated_beliefs = []
        
        for strategy, perf_data in performance_data.items():
            existing = existing_beliefs.get(strategy)
            
            try:
                updated_belief = self.update_strategy_belief(
                    strategy, existing, perf_data, current_regime
                )
                updated_beliefs.append(updated_belief)
                
                # Log status changes
                old_status = existing.get('status', 'NEW') if existing else 'NEW'
                new_status = updated_belief['status']
                
                if old_status != new_status:
                    print(f"   🔄 {strategy}: {old_status} → {new_status} (skill: {updated_belief['skill_prob']:.1%})")
                else:
                    print(f"   ✅ {strategy}: {new_status} (skill: {updated_belief['skill_prob']:.1%}, confidence: {updated_belief['confidence']:.1%})")
                    
            except Exception as e:
                print(f"   ❌ Error updating {strategy}: {e}")
        
        # Save updated beliefs
        if updated_beliefs:
            beliefs_df = pd.DataFrame(updated_beliefs)
            
            # Ensure date column is datetime
            beliefs_df['date'] = pd.to_datetime(beliefs_df['date'])
            
            # Append to existing beliefs (keep history)
            if os.path.exists(self.paths['beliefs']):
                existing_df = pd.read_parquet(self.paths['beliefs'])
                existing_df = self._normalize_existing_beliefs_df(existing_df)
                if not existing_df.empty:
                    existing_df['date'] = pd.to_datetime(existing_df['date'], errors='coerce')
                    beliefs_df = pd.concat([existing_df, beliefs_df], ignore_index=True)
            
            beliefs_df.to_parquet(self.paths['beliefs'], index=False)
            print(f"   ✅ Saved beliefs: {self.paths['beliefs']}")
            
            # Print summary
            latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
            status_counts = latest_beliefs['status'].value_counts()
            print(f"\n📊 BELIEF SUMMARY:")
            for status, count in status_counts.items():
                print(f"   {status}: {count} strategies")
        
        return updated_beliefs
    
    def get_strategy_beliefs(self, strategy=None, latest_only=True):
        """Get beliefs for specific strategy or all strategies"""
        
        if not os.path.exists(self.paths['beliefs']):
            return pd.DataFrame()
        
        beliefs_df = pd.read_parquet(self.paths['beliefs'])
        beliefs_df = self._normalize_existing_beliefs_df(beliefs_df)
        if beliefs_df.empty:
            return pd.DataFrame()
        
        if latest_only:
            beliefs_df = beliefs_df.sort_values('date').groupby('strategy').tail(1)
        
        if strategy:
            beliefs_df = beliefs_df[beliefs_df['strategy'] == strategy]
        
        return beliefs_df
    
    def get_active_strategies(self):
        """Get list of currently active strategies"""
        
        beliefs = self.get_strategy_beliefs(latest_only=True)
        active = beliefs[beliefs['status'] == 'ACTIVE']['strategy'].tolist()
        
        return active

def main():
    """Main execution function"""
    
    beliefs_engine = StrategyBeliefs()
    updated_beliefs = beliefs_engine.update_all_beliefs()
    
    return updated_beliefs

if __name__ == "__main__":
    main()
