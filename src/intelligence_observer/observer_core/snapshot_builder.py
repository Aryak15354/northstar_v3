#!/usr/bin/env python3
"""
Snapshot Builder - Creates Immutable Observer Snapshots

This module builds immutable snapshots of system state for the Intelligence Observer.
All data is lagged and aggregated to prevent any possibility of live decision influence.

CRITICAL DESIGN PRINCIPLES:
1. All data is lagged by at least 1 hour
2. No current positions or live P&L
3. Only aggregated, statistical summaries
4. Immutable snapshots only
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import json
import uuid
import warnings
warnings.filterwarnings('ignore')

from .observer_context import (
    ObserverSnapshot, MarketStateSummary, EngineStateHistory,
    LaggedPortfolioStats, HistoricalContext
)

class SnapshotBuilder:
    """
    Builds immutable snapshots for Intelligence Observer
    
    This class reads historical system state and creates lagged,
    aggregated snapshots that are safe for Observer consumption.
    """
    
    def __init__(self):
        self.name = "Observer Snapshot Builder"
        self.version = "1.0.0"
        
        # Data paths (read-only)
        self.data_paths = {
            'market_state': 'data/processed/market_state.parquet',
            'intelligent_state': 'data/processed/intelligent_market_state.parquet',
            'portfolio_analytics': 'data/processed/portfolio_analytics.json',
            'performance_history': 'data/processed/performance_summary.parquet',
            'engine_history': 'data/intelligence/engine_decisions.parquet',
            'regime_history': 'data/intelligence/regime_transitions.parquet',
            'risk_events': 'data/risk/emergency_signal.parquet'
        }
        
        # Lag requirements (minimum delays)
        self.min_lag_hours = 1.0  # Minimum 1 hour lag
        self.portfolio_lag_hours = 24.0  # Portfolio stats lagged 24 hours
        
        # Data quality thresholds
        self.quality_thresholds = {
            'min_completeness': 0.8,
            'max_staleness_hours': 48.0,
            'min_data_points': 20
        }
        
        print(f"📸 {self.name} v{self.version} - Lagged Snapshot Creation")
    
    def build_snapshot(self, cutoff_time: Optional[datetime] = None) -> Optional[ObserverSnapshot]:
        """
        Build immutable snapshot for Observer consumption
        
        Args:
            cutoff_time: Data cutoff time (default: now - min_lag_hours)
            
        Returns:
            ObserverSnapshot or None if data insufficient
        """
        
        if cutoff_time is None:
            cutoff_time = datetime.now() - timedelta(hours=self.min_lag_hours)
        
        try:
            # Build snapshot components
            market_summary = self._build_market_summary(cutoff_time)
            engine_history = self._build_engine_history(cutoff_time)
            portfolio_stats = self._build_portfolio_stats(cutoff_time)
            historical_context = self._build_historical_context(cutoff_time)
            
            # Calculate data quality metrics
            quality_score = self._calculate_data_quality(
                market_summary, engine_history, portfolio_stats, historical_context
            )
            
            completeness_score = self._calculate_completeness(
                market_summary, engine_history, portfolio_stats, historical_context
            )
            
            staleness_hours = (datetime.now() - cutoff_time).total_seconds() / 3600
            
            # Validate quality thresholds
            if quality_score < self.quality_thresholds['min_completeness']:
                print(f"⚠️ Data quality too low: {quality_score}")
                return None
            
            if staleness_hours > self.quality_thresholds['max_staleness_hours']:
                print(f"⚠️ Data too stale: {staleness_hours} hours")
                return None
            
            # Create immutable snapshot
            snapshot = ObserverSnapshot(
                snapshot_id=str(uuid.uuid4()),
                creation_time=datetime.now(),
                data_cutoff_time=cutoff_time,
                market_state=market_summary,
                engine_states=engine_history,
                portfolio_stats=portfolio_stats,
                historical_context=historical_context,
                data_quality_score=quality_score,
                completeness_score=completeness_score,
                staleness_hours=staleness_hours
            )
            
            print(f"📸 Snapshot created: {snapshot.snapshot_id}")
            print(f"   Quality: {quality_score:.2f}, Completeness: {completeness_score:.2f}")
            print(f"   Staleness: {staleness_hours:.1f} hours")
            
            return snapshot
            
        except Exception as e:
            print(f"❌ Snapshot creation failed: {e}")
            return None
    
    def _build_market_summary(self, cutoff_time: datetime) -> MarketStateSummary:
        """Build market state summary from historical data"""
        
        try:
            # Load market state data
            if os.path.exists(self.data_paths['market_state']):
                market_df = pd.read_parquet(self.data_paths['market_state'])
                market_df = market_df[market_df.index <= cutoff_time]
                
                if len(market_df) > 0:
                    latest = market_df.iloc[-1]
                    
                    # Calculate derived metrics
                    returns = market_df['market_return'].tail(60)
                    volatility_20d = returns.tail(20).std() * np.sqrt(252) if len(returns) >= 20 else 0.15
                    volatility_60d = returns.std() * np.sqrt(252) if len(returns) >= 60 else 0.15
                    
                    # Calculate drawdown
                    equity_curve = (1 + returns).cumprod()
                    running_max = equity_curve.expanding().max()
                    drawdown = (equity_curve / running_max - 1).iloc[-1] if len(equity_curve) > 0 else 0.0
                    
                    # Calculate trend strength
                    trend_strength = returns.mean() / (returns.std() + 1e-8) if len(returns) > 0 else 0.0
                    
                    return MarketStateSummary(
                        timestamp=latest.name,
                        regime=latest.get('regime', 'unknown'),
                        volatility_regime=latest.get('volatility_regime', 'normal'),
                        risk_on_probability=latest.get('risk_on_probability', 0.5),
                        allowed_exposure=latest.get('allowed_exposure', 0.35),
                        market_stress=latest.get('market_stress', 0.0),
                        breadth_pct=latest.get('breadth_pct', 50.0),
                        correlation=latest.get('correlation', 0.5),
                        volatility_20d=volatility_20d,
                        volatility_60d=volatility_60d,
                        drawdown_current=drawdown,
                        trend_strength=trend_strength
                    )
        
        except Exception as e:
            print(f"⚠️ Error building market summary: {e}")
        
        # Fallback to default values
        return MarketStateSummary(
            timestamp=cutoff_time,
            regime='unknown',
            volatility_regime='normal',
            risk_on_probability=0.5,
            allowed_exposure=0.35,
            market_stress=0.0,
            breadth_pct=50.0,
            correlation=0.5,
            volatility_20d=0.15,
            volatility_60d=0.15,
            drawdown_current=0.0,
            trend_strength=0.0
        )
    
    def _build_engine_history(self, cutoff_time: datetime) -> EngineStateHistory:
        """Build engine state history from historical decisions"""
        
        try:
            # Load engine decision history
            engine_data = {}
            
            # Try to load from multiple sources
            for path in [self.data_paths['engine_history'], 
                        'data/intelligence/dual_engine_decisions.parquet',
                        'data/processed/intelligent_market_state.parquet']:
                if os.path.exists(path):
                    df = pd.read_parquet(path)
                    df = df[df.index <= cutoff_time]
                    if len(df) > 0:
                        engine_data = df.iloc[-1].to_dict()
                        break
            
            # Calculate regime transition metrics
            regime_changes_30d = 0
            regime_stability_score = 0.8
            last_regime_change = None
            
            if os.path.exists(self.data_paths['regime_history']):
                regime_df = pd.read_parquet(self.data_paths['regime_history'])
                regime_df = regime_df[regime_df.index <= cutoff_time]
                
                if len(regime_df) >= 30:
                    recent_regimes = regime_df['regime'].tail(30)
                    regime_changes_30d = (recent_regimes != recent_regimes.shift(1)).sum()
                    regime_stability_score = 1.0 - (regime_changes_30d / 30.0)
                    
                    # Find last regime change
                    regime_changes = regime_df[regime_df['regime'] != regime_df['regime'].shift(1)]
                    if len(regime_changes) > 0:
                        last_regime_change = regime_changes.index[-1]
            
            return EngineStateHistory(
                timestamp=cutoff_time,
                active_engine=engine_data.get('active_engine', 'none'),
                regime_classification=engine_data.get('regime_classification', 'neutral'),
                regime_confidence=engine_data.get('regime_confidence', 0.5),
                trend_allocation=engine_data.get('trend_allocation', 0.0),
                crisis_allocation=engine_data.get('crisis_allocation', 0.0),
                trend_engine_active_days=engine_data.get('trend_engine_active_days', 0),
                crisis_engine_active_days=engine_data.get('crisis_engine_active_days', 0),
                trend_engine_last_return=engine_data.get('trend_engine_last_return'),
                crisis_engine_last_return=engine_data.get('crisis_engine_last_return'),
                regime_changes_30d=regime_changes_30d,
                regime_stability_score=regime_stability_score,
                last_regime_change=last_regime_change
            )
            
        except Exception as e:
            print(f"⚠️ Error building engine history: {e}")
            
            # Fallback to default values
            return EngineStateHistory(
                timestamp=cutoff_time,
                active_engine='none',
                regime_classification='neutral',
                regime_confidence=0.5,
                trend_allocation=0.0,
                crisis_allocation=0.0,
                trend_engine_active_days=0,
                crisis_engine_active_days=0,
                trend_engine_last_return=None,
                crisis_engine_last_return=None,
                regime_changes_30d=0,
                regime_stability_score=0.8,
                last_regime_change=None
            )
    
    def _build_portfolio_stats(self, cutoff_time: datetime) -> LaggedPortfolioStats:
        """Build lagged portfolio statistics - NO CURRENT POSITIONS"""
        
        # Portfolio stats are lagged by 24 hours minimum
        portfolio_cutoff = cutoff_time - timedelta(hours=self.portfolio_lag_hours)
        
        try:
            # Load performance history
            if os.path.exists(self.data_paths['performance_history']):
                perf_df = pd.read_parquet(self.data_paths['performance_history'])
                perf_df = perf_df[perf_df.index <= portfolio_cutoff]
                
                if len(perf_df) >= 30:
                    # Calculate lagged performance metrics
                    returns = perf_df['net_return'].tail(30)
                    
                    return LaggedPortfolioStats(
                        timestamp=portfolio_cutoff,
                        total_return_1d=returns.iloc[-1] if len(returns) >= 1 else 0.0,
                        total_return_7d=returns.tail(7).sum() if len(returns) >= 7 else 0.0,
                        total_return_30d=returns.sum(),
                        volatility_30d=returns.std() * np.sqrt(252),
                        sharpe_ratio_30d=(returns.mean() * 252) / (returns.std() * np.sqrt(252) + 1e-8),
                        max_drawdown_30d=perf_df['drawdown'].tail(30).min(),
                        avg_exposure_7d=perf_df['exposure'].tail(7).mean() if 'exposure' in perf_df.columns else 0.35,
                        avg_exposure_30d=perf_df['exposure'].tail(30).mean() if 'exposure' in perf_df.columns else 0.35,
                        turnover_7d=perf_df['turnover'].tail(7).mean() if 'turnover' in perf_df.columns else 0.05,
                        var_95_1d=returns.quantile(0.05),
                        concentration_score=0.3,  # Placeholder - would calculate from holdings
                        sector_concentration_max=0.25  # Placeholder - would calculate from sector exposure
                    )
        
        except Exception as e:
            print(f"⚠️ Error building portfolio stats: {e}")
        
        # Fallback to default values
        return LaggedPortfolioStats(
            timestamp=portfolio_cutoff,
            total_return_1d=0.0,
            total_return_7d=0.0,
            total_return_30d=0.0,
            volatility_30d=0.15,
            sharpe_ratio_30d=0.5,
            max_drawdown_30d=-0.05,
            avg_exposure_7d=0.35,
            avg_exposure_30d=0.35,
            turnover_7d=0.05,
            var_95_1d=-0.02,
            concentration_score=0.3,
            sector_concentration_max=0.25
        )
    
    def _build_historical_context(self, cutoff_time: datetime) -> HistoricalContext:
        """Build historical context for pattern matching"""
        
        try:
            # Load 1 year of historical data
            lookback_date = cutoff_time - timedelta(days=365)
            
            regime_history = []
            volatility_history = []
            return_history = []
            correlation_history = []
            breadth_history = []
            
            # Load market state history
            if os.path.exists(self.data_paths['market_state']):
                market_df = pd.read_parquet(self.data_paths['market_state'])
                market_df = market_df[(market_df.index >= lookback_date) & (market_df.index <= cutoff_time)]
                
                if len(market_df) > 0:
                    regime_history = market_df['regime'].tolist()
                    correlation_history = market_df['correlation'].tolist()
                    breadth_history = market_df['breadth_pct'].tolist()
                    
                    # Calculate volatility and returns
                    if 'market_return' in market_df.columns:
                        returns = market_df['market_return']
                        return_history = returns.tolist()
                        
                        # Rolling volatility
                        volatility_history = (returns.rolling(20).std() * np.sqrt(252)).tolist()
            
            # Identify crisis and stress periods
            crisis_periods = []
            stress_periods = []
            
            if len(volatility_history) > 0:
                vol_series = pd.Series(volatility_history)
                
                # Crisis periods (vol > 30%)
                crisis_mask = vol_series > 0.30
                crisis_periods = self._identify_periods(crisis_mask, 'crisis')
                
                # Stress periods (vol > 20%)
                stress_mask = vol_series > 0.20
                stress_periods = self._identify_periods(stress_mask, 'stress')
            
            # Build regime transition matrix
            regime_transition_matrix = {}
            avg_regime_duration = {}
            
            if len(regime_history) > 1:
                regime_transition_matrix, avg_regime_duration = self._calculate_regime_transitions(regime_history)
            
            return HistoricalContext(
                timestamp=cutoff_time,
                regime_history_1y=regime_history[-252:],  # Max 1 year daily
                volatility_history_1y=volatility_history[-252:],
                return_history_1y=return_history[-252:],
                crisis_periods=crisis_periods,
                stress_periods=stress_periods,
                regime_transition_matrix=regime_transition_matrix,
                avg_regime_duration=avg_regime_duration,
                correlation_history_1y=correlation_history[-252:],
                breadth_history_1y=breadth_history[-252:]
            )
            
        except Exception as e:
            print(f"⚠️ Error building historical context: {e}")
            
            # Fallback to minimal context
            return HistoricalContext(
                timestamp=cutoff_time,
                regime_history_1y=['neutral'] * 100,
                volatility_history_1y=[0.15] * 100,
                return_history_1y=[0.0005] * 100,
                crisis_periods=[],
                stress_periods=[],
                regime_transition_matrix={},
                avg_regime_duration={},
                correlation_history_1y=[0.5] * 100,
                breadth_history_1y=[50.0] * 100
            )
    
    def _identify_periods(self, mask: pd.Series, period_type: str) -> List[Dict[str, Any]]:
        """Identify continuous periods from boolean mask"""
        periods = []
        
        if mask.any():
            # Find start and end of continuous periods
            diff = mask.astype(int).diff()
            starts = mask.index[diff == 1].tolist()
            ends = mask.index[diff == -1].tolist()
            
            # Handle edge cases
            if mask.iloc[0]:
                starts = [mask.index[0]] + starts
            if mask.iloc[-1]:
                ends = ends + [mask.index[-1]]
            
            # Create period records
            for i, start in enumerate(starts):
                end = ends[i] if i < len(ends) else mask.index[-1]
                periods.append({
                    'type': period_type,
                    'start_idx': start,
                    'end_idx': end,
                    'duration': end - start + 1,
                    'max_value': mask.loc[start:end].sum()
                })
        
        return periods
    
    def _calculate_regime_transitions(self, regime_history: List[str]) -> tuple:
        """Calculate regime transition matrix and average durations"""
        
        regimes = list(set(regime_history))
        transition_matrix = {r1: {r2: 0.0 for r2 in regimes} for r1 in regimes}
        regime_durations = {r: [] for r in regimes}
        
        # Count transitions
        for i in range(1, len(regime_history)):
            prev_regime = regime_history[i-1]
            curr_regime = regime_history[i]
            transition_matrix[prev_regime][curr_regime] += 1
        
        # Normalize to probabilities
        for r1 in regimes:
            total = sum(transition_matrix[r1].values())
            if total > 0:
                for r2 in regimes:
                    transition_matrix[r1][r2] /= total
        
        # Calculate average durations
        current_regime = regime_history[0]
        current_duration = 1
        
        for i in range(1, len(regime_history)):
            if regime_history[i] == current_regime:
                current_duration += 1
            else:
                regime_durations[current_regime].append(current_duration)
                current_regime = regime_history[i]
                current_duration = 1
        
        # Add final duration
        regime_durations[current_regime].append(current_duration)
        
        # Calculate averages
        avg_regime_duration = {}
        for regime, durations in regime_durations.items():
            avg_regime_duration[regime] = np.mean(durations) if durations else 1.0
        
        return transition_matrix, avg_regime_duration
    
    def _calculate_data_quality(self, market_summary, engine_history, portfolio_stats, historical_context) -> float:
        """Calculate overall data quality score"""
        
        quality_factors = []
        
        # Market data quality
        if market_summary.regime != 'unknown':
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.5)
        
        # Engine data quality
        if engine_history.active_engine != 'none':
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.7)
        
        # Portfolio data quality
        if portfolio_stats.volatility_30d > 0:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.6)
        
        # Historical context quality
        if len(historical_context.regime_history_1y) >= 100:
            quality_factors.append(1.0)
        else:
            quality_factors.append(0.8)
        
        return np.mean(quality_factors)
    
    def _calculate_completeness(self, market_summary, engine_history, portfolio_stats, historical_context) -> float:
        """Calculate data completeness score"""
        
        completeness_factors = []
        
        # Check for non-null/default values
        completeness_factors.append(1.0 if market_summary.regime != 'unknown' else 0.5)
        completeness_factors.append(1.0 if engine_history.regime_confidence > 0 else 0.5)
        completeness_factors.append(1.0 if portfolio_stats.total_return_30d != 0 else 0.7)
        completeness_factors.append(1.0 if len(historical_context.regime_history_1y) > 50 else 0.6)
        
        return np.mean(completeness_factors)