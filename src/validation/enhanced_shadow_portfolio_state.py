#!/usr/bin/env python3
"""
📊 ENHANCED SHADOW PORTFOLIO STATE - NORTHSTAR V3 PHASE 4
Comprehensive data model for shadow portfolio state tracking

This creates a sophisticated data model that:
1. Tracks positions, Phase 3 regime, tailwinds, NO_EDGE state
2. Includes anticipatory signals and execution quality
3. Adds reality consistency scoring
4. Includes performance attribution data
5. Provides institutional-grade state management

Phase 4 Enhancement Features:
- Complete Phase 3 intelligence integration
- Advanced execution quality tracking
- Multi-dimensional performance attribution
- Reality consistency validation
- Temporal state evolution tracking
- Institutional-grade audit trail

Data Model Components:
- Portfolio positions and target allocations
- Phase 3 regime classification and confidence
- Strategy tailwinds and regime fit scores
- NO_EDGE state and exposure constraints
- Execution quality and transaction costs
- Performance attribution by component
- Reality consistency and validation scores

Output: Comprehensive shadow portfolio state for institutional analysis
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class RegimeType(Enum):
    """Phase 3 regime classifications"""
    LATE_EXPANSION = "Late-Expansion"
    SLOWDOWN = "Slowdown"
    CRISIS = "Crisis"
    EXPANSION = "Expansion"
    UNKNOWN = "Unknown"

class NoEdgeState(Enum):
    """NO_EDGE detector states"""
    NORMAL = "NORMAL"
    NO_EDGE = "NO_EDGE"
    UNKNOWN = "UNKNOWN"

class ExecutionQuality(Enum):
    """Execution quality classifications"""
    EXCELLENT = "EXCELLENT"  # >95%
    GOOD = "GOOD"           # 85-95%
    FAIR = "FAIR"           # 70-85%
    POOR = "POOR"           # <70%

@dataclass
class RegimeState:
    """Phase 3 regime state information"""
    regime: RegimeType = RegimeType.UNKNOWN
    confidence: float = 0.0
    similarity: float = 0.0
    expected_return: float = 0.0
    expected_sharpe: float = 0.0
    match_date: Optional[str] = None
    age_days: int = 999
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'regime': self.regime.value,
            'confidence': self.confidence,
            'similarity': self.similarity,
            'expected_return': self.expected_return,
            'expected_sharpe': self.expected_sharpe,
            'match_date': self.match_date,
            'age_days': self.age_days,
            'source': self.source
        }

@dataclass
class StrategyTailwind:
    """Strategy tailwind information"""
    strategy: str
    combined_score: float = 1.0
    sharpe: float = 0.0
    regime_tailwind: float = 0.0
    regime: str = "Unknown"
    percentile_rank: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'strategy': self.strategy,
            'combined_score': self.combined_score,
            'sharpe': self.sharpe,
            'regime_tailwind': self.regime_tailwind,
            'regime': self.regime,
            'percentile_rank': self.percentile_rank
        }

@dataclass
class NoEdgeStateInfo:
    """NO_EDGE state information"""
    state: NoEdgeState = NoEdgeState.UNKNOWN
    exposure_cap: float = 0.8
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.1
    age_days: int = 999
    transitions_today: int = 0
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'state': self.state.value,
            'exposure_cap': self.exposure_cap,
            'reasons': self.reasons,
            'confidence': self.confidence,
            'age_days': self.age_days,
            'transitions_today': self.transitions_today,
            'source': self.source
        }

@dataclass
class PositionInfo:
    """Individual position information"""
    strategy: str
    target_weight: float = 0.0
    current_weight: float = 0.0
    executed_weight: float = 0.0
    trade_size: float = 0.0
    execution_error: float = 0.0
    transaction_cost: float = 0.0
    market_impact: float = 0.0
    tailwind_score: float = 1.0
    regime_fit: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class ExecutionResult:
    """Execution result information"""
    timestamp: str
    total_trades: int = 0
    successful_trades: int = 0
    execution_quality_score: float = 0.0
    execution_quality: ExecutionQuality = ExecutionQuality.POOR
    total_transaction_costs: float = 0.0
    total_market_impact: float = 0.0
    reality_consistency: float = 0.0
    execution_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp,
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'execution_quality_score': self.execution_quality_score,
            'execution_quality': self.execution_quality.value,
            'total_transaction_costs': self.total_transaction_costs,
            'total_market_impact': self.total_market_impact,
            'reality_consistency': self.reality_consistency,
            'execution_errors': self.execution_errors
        }

@dataclass
class PerformanceAttribution:
    """Performance attribution by Phase 3 components"""
    timestamp: str
    total_performance: float = 0.0
    regime_contribution: float = 0.0
    tailwind_contribution: float = 0.0
    no_edge_contribution: float = 0.0
    execution_contribution: float = 0.0
    unexplained_alpha: float = 0.0
    strategy_attributions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class ValidationResult:
    """Reality consistency validation result"""
    timestamp: str
    consistency_score: float = 0.0
    validation_checks: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class EnhancedShadowPortfolioState:
    """
    Enhanced Shadow Portfolio State
    
    Comprehensive state tracking for Phase 4 shadow portfolio execution
    with deep Phase 3 intelligence integration and institutional-grade
    performance attribution and validation.
    """
    
    # Core identification
    timestamp: str
    date: str
    version: str = "4.0"
    
    # Phase 3 Intelligence State
    regime_state: RegimeState = field(default_factory=RegimeState)
    strategy_tailwinds: Dict[str, StrategyTailwind] = field(default_factory=dict)
    no_edge_state: NoEdgeStateInfo = field(default_factory=NoEdgeStateInfo)
    intelligence_confidence: float = 0.0
    
    # Portfolio State
    positions: Dict[str, PositionInfo] = field(default_factory=dict)
    total_exposure: float = 0.0
    n_positions: int = 0
    target_exposure: float = 0.0
    exposure_utilization: float = 0.0
    
    # Execution State
    execution_result: ExecutionResult = field(default_factory=lambda: ExecutionResult(timestamp=datetime.now().isoformat()))
    
    # Performance Attribution
    performance_attribution: PerformanceAttribution = field(default_factory=lambda: PerformanceAttribution(timestamp=datetime.now().isoformat()))
    
    # Validation and Quality
    validation_result: ValidationResult = field(default_factory=lambda: ValidationResult(timestamp=datetime.now().isoformat()))
    
    # Metadata
    data_sources: Dict[str, bool] = field(default_factory=dict)
    integration_quality: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization processing"""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.date:
            self.date = datetime.now().date().isoformat()
    
    def add_position(self, strategy: str, target_weight: float, current_weight: float = 0.0,
                    tailwind_score: float = 1.0, regime_fit: float = 0.5) -> None:
        """Add a position to the portfolio"""
        
        position = PositionInfo(
            strategy=strategy,
            target_weight=target_weight,
            current_weight=current_weight,
            tailwind_score=tailwind_score,
            regime_fit=regime_fit
        )
        
        self.positions[strategy] = position
        self._update_portfolio_metrics()
    
    def update_execution_result(self, strategy: str, executed_weight: float, 
                              transaction_cost: float = 0.0, market_impact: float = 0.0,
                              execution_error: float = 0.0) -> None:
        """Update execution result for a strategy"""
        
        if strategy in self.positions:
            position = self.positions[strategy]
            position.executed_weight = executed_weight
            position.trade_size = executed_weight - position.current_weight
            position.transaction_cost = transaction_cost
            position.market_impact = market_impact
            position.execution_error = execution_error
            
            self._update_portfolio_metrics()
    
    def set_regime_state(self, regime: RegimeType, confidence: float, similarity: float = 0.0,
                        expected_return: float = 0.0, expected_sharpe: float = 0.0,
                        match_date: Optional[str] = None, age_days: int = 0, source: str = "unknown") -> None:
        """Set regime state information"""
        
        self.regime_state = RegimeState(
            regime=regime,
            confidence=confidence,
            similarity=similarity,
            expected_return=expected_return,
            expected_sharpe=expected_sharpe,
            match_date=match_date,
            age_days=age_days,
            source=source
        )
    
    def add_strategy_tailwind(self, strategy: str, combined_score: float, sharpe: float = 0.0,
                            regime_tailwind: float = 0.0, regime: str = "Unknown") -> None:
        """Add strategy tailwind information"""
        
        # Calculate percentile rank among all tailwinds
        all_scores = [tw.combined_score for tw in self.strategy_tailwinds.values()]
        if all_scores:
            percentile_rank = sum(1 for score in all_scores if score < combined_score) / len(all_scores)
        else:
            percentile_rank = 0.5
        
        tailwind = StrategyTailwind(
            strategy=strategy,
            combined_score=combined_score,
            sharpe=sharpe,
            regime_tailwind=regime_tailwind,
            regime=regime,
            percentile_rank=percentile_rank
        )
        
        self.strategy_tailwinds[strategy] = tailwind
        
        # Update percentile ranks for all strategies
        self._update_tailwind_percentiles()
    
    def set_no_edge_state(self, state: NoEdgeState, exposure_cap: float, reasons: List[str] = None,
                         confidence: float = 0.9, age_days: int = 0, transitions_today: int = 0,
                         source: str = "unknown") -> None:
        """Set NO_EDGE state information"""
        
        self.no_edge_state = NoEdgeStateInfo(
            state=state,
            exposure_cap=exposure_cap,
            reasons=reasons or [],
            confidence=confidence,
            age_days=age_days,
            transitions_today=transitions_today,
            source=source
        )
    
    def set_performance_attribution(self, total_performance: float, regime_contribution: float,
                                  tailwind_contribution: float, no_edge_contribution: float,
                                  execution_contribution: float, strategy_attributions: Dict[str, Dict[str, float]] = None) -> None:
        """Set performance attribution"""
        
        unexplained_alpha = total_performance - (regime_contribution + tailwind_contribution + 
                                               no_edge_contribution + execution_contribution)
        
        self.performance_attribution = PerformanceAttribution(
            timestamp=self.timestamp,
            total_performance=total_performance,
            regime_contribution=regime_contribution,
            tailwind_contribution=tailwind_contribution,
            no_edge_contribution=no_edge_contribution,
            execution_contribution=execution_contribution,
            unexplained_alpha=unexplained_alpha,
            strategy_attributions=strategy_attributions or {}
        )
    
    def set_validation_result(self, consistency_score: float, validation_checks: Dict[str, str],
                            warnings: List[str] = None, errors: List[str] = None) -> None:
        """Set validation result"""
        
        self.validation_result = ValidationResult(
            timestamp=self.timestamp,
            consistency_score=consistency_score,
            validation_checks=validation_checks,
            warnings=warnings or [],
            errors=errors or []
        )
    
    def _update_portfolio_metrics(self) -> None:
        """Update portfolio-level metrics"""
        
        if not self.positions:
            self.total_exposure = 0.0
            self.n_positions = 0
            self.target_exposure = 0.0
            self.exposure_utilization = 0.0
            return
        
        # Calculate metrics
        self.total_exposure = sum(pos.executed_weight for pos in self.positions.values())
        self.n_positions = len([pos for pos in self.positions.values() if pos.executed_weight > 0])
        self.target_exposure = sum(pos.target_weight for pos in self.positions.values())
        
        # Calculate exposure utilization vs NO_EDGE cap
        exposure_cap = self.no_edge_state.exposure_cap
        if exposure_cap > 0:
            self.exposure_utilization = self.total_exposure / exposure_cap
        else:
            self.exposure_utilization = 0.0
    
    def _update_tailwind_percentiles(self) -> None:
        """Update percentile ranks for all strategy tailwinds"""
        
        if len(self.strategy_tailwinds) <= 1:
            return
        
        all_scores = [tw.combined_score for tw in self.strategy_tailwinds.values()]
        
        for strategy, tailwind in self.strategy_tailwinds.items():
            percentile_rank = sum(1 for score in all_scores if score < tailwind.combined_score) / len(all_scores)
            tailwind.percentile_rank = percentile_rank
    
    def calculate_intelligence_confidence(self) -> float:
        """Calculate overall intelligence confidence"""
        
        confidence_factors = []
        
        # Regime confidence
        confidence_factors.append(self.regime_state.confidence)
        
        # Tailwind confidence (based on number of strategies)
        tailwind_confidence = min(1.0, len(self.strategy_tailwinds) / 10.0)
        confidence_factors.append(tailwind_confidence)
        
        # NO_EDGE confidence
        confidence_factors.append(self.no_edge_state.confidence)
        
        # Data freshness confidence
        max_age = max(self.regime_state.age_days, self.no_edge_state.age_days)
        freshness_confidence = max(0.1, 1.0 - (max_age / 7.0))  # 7 day decay
        confidence_factors.append(freshness_confidence)
        
        self.intelligence_confidence = sum(confidence_factors) / len(confidence_factors)
        return self.intelligence_confidence
    
    def get_top_positions(self, n: int = 5) -> List[Tuple[str, PositionInfo]]:
        """Get top N positions by executed weight"""
        
        sorted_positions = sorted(
            self.positions.items(),
            key=lambda x: x[1].executed_weight,
            reverse=True
        )
        
        return sorted_positions[:n]
    
    def get_top_tailwinds(self, n: int = 5) -> List[Tuple[str, StrategyTailwind]]:
        """Get top N strategies by tailwind score"""
        
        sorted_tailwinds = sorted(
            self.strategy_tailwinds.items(),
            key=lambda x: x[1].combined_score,
            reverse=True
        )
        
        return sorted_tailwinds[:n]
    
    def get_execution_quality_summary(self) -> Dict[str, Any]:
        """Get execution quality summary"""
        
        if not self.positions:
            return {'quality': 'NO_POSITIONS', 'score': 0.0}
        
        # Calculate execution quality metrics
        total_positions = len(self.positions)
        successful_executions = sum(1 for pos in self.positions.values() 
                                  if pos.execution_error < 0.05)  # <5% error
        
        quality_score = successful_executions / total_positions if total_positions > 0 else 0.0
        
        if quality_score >= 0.95:
            quality = ExecutionQuality.EXCELLENT
        elif quality_score >= 0.85:
            quality = ExecutionQuality.GOOD
        elif quality_score >= 0.70:
            quality = ExecutionQuality.FAIR
        else:
            quality = ExecutionQuality.POOR
        
        return {
            'quality': quality.value,
            'score': quality_score,
            'successful_executions': successful_executions,
            'total_positions': total_positions,
            'total_transaction_costs': sum(pos.transaction_cost for pos in self.positions.values()),
            'total_market_impact': sum(pos.market_impact for pos in self.positions.values())
        }
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get risk metrics summary"""
        
        return {
            'total_exposure': self.total_exposure,
            'exposure_cap': self.no_edge_state.exposure_cap,
            'exposure_utilization': self.exposure_utilization,
            'no_edge_state': self.no_edge_state.state.value,
            'regime_confidence': self.regime_state.confidence,
            'intelligence_confidence': self.intelligence_confidence,
            'consistency_score': self.validation_result.consistency_score,
            'n_warnings': len(self.validation_result.warnings),
            'n_errors': len(self.validation_result.errors)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert complete state to dictionary"""
        
        return {
            'timestamp': self.timestamp,
            'date': self.date,
            'version': self.version,
            'regime_state': self.regime_state.to_dict(),
            'strategy_tailwinds': {k: v.to_dict() for k, v in self.strategy_tailwinds.items()},
            'no_edge_state': self.no_edge_state.to_dict(),
            'intelligence_confidence': self.intelligence_confidence,
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
            'total_exposure': self.total_exposure,
            'n_positions': self.n_positions,
            'target_exposure': self.target_exposure,
            'exposure_utilization': self.exposure_utilization,
            'execution_result': self.execution_result.to_dict(),
            'performance_attribution': self.performance_attribution.to_dict(),
            'validation_result': self.validation_result.to_dict(),
            'data_sources': self.data_sources,
            'integration_quality': self.integration_quality
        }
    
    def to_dataframe_record(self) -> Dict[str, Any]:
        """Convert to flat dictionary suitable for DataFrame"""
        
        # Calculate summary metrics
        execution_summary = self.get_execution_quality_summary()
        risk_metrics = self.get_risk_metrics()
        
        # Create flat record
        record = {
            'date': self.date,
            'timestamp': self.timestamp,
            'version': self.version,
            
            # Regime state
            'regime': self.regime_state.regime.value,
            'regime_confidence': self.regime_state.confidence,
            'regime_similarity': self.regime_state.similarity,
            'regime_expected_return': self.regime_state.expected_return,
            'regime_expected_sharpe': self.regime_state.expected_sharpe,
            'regime_age_days': self.regime_state.age_days,
            
            # NO_EDGE state
            'no_edge_state': self.no_edge_state.state.value,
            'exposure_cap': self.no_edge_state.exposure_cap,
            'no_edge_confidence': self.no_edge_state.confidence,
            'no_edge_age_days': self.no_edge_state.age_days,
            'no_edge_transitions_today': self.no_edge_state.transitions_today,
            
            # Portfolio metrics
            'total_exposure': self.total_exposure,
            'target_exposure': self.target_exposure,
            'exposure_utilization': self.exposure_utilization,
            'n_positions': self.n_positions,
            'n_tailwinds': len(self.strategy_tailwinds),
            
            # Execution quality
            'execution_quality': execution_summary['quality'],
            'execution_quality_score': execution_summary['score'],
            'total_transaction_costs': execution_summary['total_transaction_costs'],
            'total_market_impact': execution_summary['total_market_impact'],
            
            # Performance attribution
            'total_performance': self.performance_attribution.total_performance,
            'regime_contribution': self.performance_attribution.regime_contribution,
            'tailwind_contribution': self.performance_attribution.tailwind_contribution,
            'no_edge_contribution': self.performance_attribution.no_edge_contribution,
            'execution_contribution': self.performance_attribution.execution_contribution,
            'unexplained_alpha': self.performance_attribution.unexplained_alpha,
            
            # Validation
            'consistency_score': self.validation_result.consistency_score,
            'n_validation_warnings': len(self.validation_result.warnings),
            'n_validation_errors': len(self.validation_result.errors),
            
            # Intelligence
            'intelligence_confidence': self.intelligence_confidence
        }
        
        # Add top positions
        top_positions = self.get_top_positions(3)
        for i, (strategy, position) in enumerate(top_positions):
            record[f'top_position_{i+1}_strategy'] = strategy
            record[f'top_position_{i+1}_weight'] = position.executed_weight
            record[f'top_position_{i+1}_tailwind'] = position.tailwind_score
        
        # Add top tailwinds
        top_tailwinds = self.get_top_tailwinds(3)
        for i, (strategy, tailwind) in enumerate(top_tailwinds):
            record[f'top_tailwind_{i+1}_strategy'] = strategy
            record[f'top_tailwind_{i+1}_score'] = tailwind.combined_score
            record[f'top_tailwind_{i+1}_percentile'] = tailwind.percentile_rank
        
        return record
    
    def save_to_json(self, filepath: str) -> None:
        """Save state to JSON file"""
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
    
    def save_to_parquet(self, filepath: str, append: bool = True) -> None:
        """Save state to Parquet file (suitable for time series)"""
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Convert to DataFrame record
        record = self.to_dataframe_record()
        new_df = pd.DataFrame([record])
        
        if append and os.path.exists(filepath):
            # Load existing data and append
            existing_df = pd.read_parquet(filepath)
            
            # Remove today's record if it exists
            if 'date' in existing_df.columns:
                existing_df['date'] = pd.to_datetime(existing_df['date']).dt.date
                today = pd.to_datetime(self.date).date()
                existing_df = existing_df[existing_df['date'] != today]
            
            # Combine and save
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df.to_parquet(filepath, index=False)
        else:
            # Save new file
            new_df.to_parquet(filepath, index=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedShadowPortfolioState':
        """Create state from dictionary"""
        
        # Create base state
        state = cls(
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            date=data.get('date', datetime.now().date().isoformat()),
            version=data.get('version', '4.0')
        )
        
        # Set regime state
        regime_data = data.get('regime_state', {})
        if regime_data:
            state.regime_state = RegimeState(
                regime=RegimeType(regime_data.get('regime', 'Unknown')),
                confidence=regime_data.get('confidence', 0.0),
                similarity=regime_data.get('similarity', 0.0),
                expected_return=regime_data.get('expected_return', 0.0),
                expected_sharpe=regime_data.get('expected_sharpe', 0.0),
                match_date=regime_data.get('match_date'),
                age_days=regime_data.get('age_days', 999),
                source=regime_data.get('source', 'unknown')
            )
        
        # Set strategy tailwinds
        tailwinds_data = data.get('strategy_tailwinds', {})
        for strategy, tw_data in tailwinds_data.items():
            state.strategy_tailwinds[strategy] = StrategyTailwind(
                strategy=strategy,
                combined_score=tw_data.get('combined_score', 1.0),
                sharpe=tw_data.get('sharpe', 0.0),
                regime_tailwind=tw_data.get('regime_tailwind', 0.0),
                regime=tw_data.get('regime', 'Unknown'),
                percentile_rank=tw_data.get('percentile_rank', 0.5)
            )
        
        # Set NO_EDGE state
        no_edge_data = data.get('no_edge_state', {})
        if no_edge_data:
            state.no_edge_state = NoEdgeStateInfo(
                state=NoEdgeState(no_edge_data.get('state', 'UNKNOWN')),
                exposure_cap=no_edge_data.get('exposure_cap', 0.8),
                reasons=no_edge_data.get('reasons', []),
                confidence=no_edge_data.get('confidence', 0.1),
                age_days=no_edge_data.get('age_days', 999),
                transitions_today=no_edge_data.get('transitions_today', 0),
                source=no_edge_data.get('source', 'unknown')
            )
        
        # Set positions
        positions_data = data.get('positions', {})
        for strategy, pos_data in positions_data.items():
            state.positions[strategy] = PositionInfo(
                strategy=strategy,
                target_weight=pos_data.get('target_weight', 0.0),
                current_weight=pos_data.get('current_weight', 0.0),
                executed_weight=pos_data.get('executed_weight', 0.0),
                trade_size=pos_data.get('trade_size', 0.0),
                execution_error=pos_data.get('execution_error', 0.0),
                transaction_cost=pos_data.get('transaction_cost', 0.0),
                market_impact=pos_data.get('market_impact', 0.0),
                tailwind_score=pos_data.get('tailwind_score', 1.0),
                regime_fit=pos_data.get('regime_fit', 0.5)
            )
        
        # Set other fields
        state.intelligence_confidence = data.get('intelligence_confidence', 0.0)
        state.data_sources = data.get('data_sources', {})
        state.integration_quality = data.get('integration_quality', {})
        
        # Update calculated metrics
        state._update_portfolio_metrics()
        
        return state
    
    @classmethod
    def from_json(cls, filepath: str) -> 'EnhancedShadowPortfolioState':
        """Load state from JSON file"""
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def print_summary(self) -> None:
        """Print comprehensive state summary"""
        
        print(f"🎭 ENHANCED SHADOW PORTFOLIO STATE SUMMARY")
        print(f"=" * 60)
        print(f"   Date: {self.date}")
        print(f"   Version: {self.version}")
        print(f"   Intelligence Confidence: {self.intelligence_confidence:.1%}")
        
        print(f"\n🧠 PHASE 3 INTELLIGENCE STATE")
        print(f"   Regime: {self.regime_state.regime.value} (confidence: {self.regime_state.confidence:.1%})")
        print(f"   NO_EDGE State: {self.no_edge_state.state.value} (cap: {self.no_edge_state.exposure_cap:.0%})")
        print(f"   Strategy Tailwinds: {len(self.strategy_tailwinds)}")
        
        print(f"\n📊 PORTFOLIO STATE")
        print(f"   Total Exposure: {self.total_exposure:.1%}")
        print(f"   Target Exposure: {self.target_exposure:.1%}")
        print(f"   Exposure Utilization: {self.exposure_utilization:.1%}")
        print(f"   Active Positions: {self.n_positions}")
        
        # Show top positions
        top_positions = self.get_top_positions(3)
        if top_positions:
            print(f"\n🏆 TOP POSITIONS")
            for strategy, position in top_positions:
                print(f"   {strategy}: {position.executed_weight:.1%} (tailwind: {position.tailwind_score:.2f})")
        
        # Show top tailwinds
        top_tailwinds = self.get_top_tailwinds(3)
        if top_tailwinds:
            print(f"\n🌬️ TOP TAILWINDS")
            for strategy, tailwind in top_tailwinds:
                print(f"   {strategy}: {tailwind.combined_score:.2f} ({tailwind.percentile_rank:.0%}ile)")
        
        # Show execution quality
        execution_summary = self.get_execution_quality_summary()
        print(f"\n⚡ EXECUTION QUALITY")
        print(f"   Quality: {execution_summary['quality']}")
        print(f"   Score: {execution_summary['score']:.1%}")
        print(f"   Transaction Costs: {execution_summary['total_transaction_costs']:.4f}")
        
        # Show performance attribution
        print(f"\n📈 PERFORMANCE ATTRIBUTION")
        print(f"   Total Performance: {self.performance_attribution.total_performance:.4f}")
        print(f"   Regime: {self.performance_attribution.regime_contribution:.4f}")
        print(f"   Tailwind: {self.performance_attribution.tailwind_contribution:.4f}")
        print(f"   NO_EDGE: {self.performance_attribution.no_edge_contribution:.4f}")
        print(f"   Execution: {self.performance_attribution.execution_contribution:.4f}")
        
        # Show validation
        print(f"\n🔍 VALIDATION")
        print(f"   Consistency Score: {self.validation_result.consistency_score:.1%}")
        print(f"   Warnings: {len(self.validation_result.warnings)}")
        print(f"   Errors: {len(self.validation_result.errors)}")

def main():
    """Test Enhanced Shadow Portfolio State"""
    
    print("🎭 Testing Enhanced Shadow Portfolio State...")
    
    # Create test state
    state = EnhancedShadowPortfolioState(
        timestamp=datetime.now().isoformat(),
        date=datetime.now().date().isoformat()
    )
    
    # Set regime state
    state.set_regime_state(
        regime=RegimeType.LATE_EXPANSION,
        confidence=0.85,
        similarity=0.72,
        expected_return=0.08,
        expected_sharpe=0.65,
        age_days=2,
        source="regime_memory"
    )
    
    # Add strategy tailwinds
    strategies = [
        ("sector_tilt_mom", 2.19, 0.45, 0.85),
        ("regime_conditional", 1.87, 0.38, 0.72),
        ("momentum_factor", 1.65, 0.42, 0.58),
        ("value_factor", 1.23, 0.28, 0.45),
        ("quality_factor", 1.15, 0.32, 0.38)
    ]
    
    for strategy, combined_score, sharpe, regime_tailwind in strategies:
        state.add_strategy_tailwind(strategy, combined_score, sharpe, regime_tailwind, "Late-Expansion")
    
    # Set NO_EDGE state
    state.set_no_edge_state(
        state=NoEdgeState.NORMAL,
        exposure_cap=0.8,
        confidence=0.9,
        age_days=0,
        source="no_edge_detector"
    )
    
    # Add positions
    allocations = [
        ("regime_conditional", 0.117, 0.105),
        ("sector_tilt_mom", 0.115, 0.108),
        ("momentum_factor", 0.112, 0.098),
        ("value_factor", 0.089, 0.085),
        ("quality_factor", 0.067, 0.064)
    ]
    
    for strategy, target, executed in allocations:
        tailwind_score = next((s[1] for s in strategies if s[0] == strategy), 1.0)
        state.add_position(strategy, target, 0.0, tailwind_score, 0.7)
        state.update_execution_result(strategy, executed, 0.0001, 0.0002, abs(executed - target) / target)
    
    # Set performance attribution
    state.set_performance_attribution(
        total_performance=0.0045,
        regime_contribution=0.0012,
        tailwind_contribution=0.0018,
        no_edge_contribution=0.0000,
        execution_contribution=-0.0003
    )
    
    # Set validation result
    state.set_validation_result(
        consistency_score=0.92,
        validation_checks={
            'execution_quality': 'PASS',
            'transaction_costs': 'PASS',
            'market_impact': 'PASS',
            'reality_consistency': 'PASS'
        },
        warnings=[],
        errors=[]
    )
    
    # Calculate intelligence confidence
    state.calculate_intelligence_confidence()
    
    # Print summary
    state.print_summary()
    
    # Test serialization
    print(f"\n💾 Testing serialization...")
    
    # Save to JSON
    json_path = "data/shadow_reality/test_state.json"
    state.save_to_json(json_path)
    print(f"   ✅ Saved to JSON: {json_path}")
    
    # Save to Parquet
    parquet_path = "data/shadow_reality/test_state.parquet"
    state.save_to_parquet(parquet_path, append=False)
    print(f"   ✅ Saved to Parquet: {parquet_path}")
    
    # Test loading
    loaded_state = EnhancedShadowPortfolioState.from_json(json_path)
    print(f"   ✅ Loaded from JSON successfully")
    
    # Verify data integrity
    assert loaded_state.regime_state.regime == state.regime_state.regime
    assert loaded_state.total_exposure == state.total_exposure
    assert len(loaded_state.positions) == len(state.positions)
    print(f"   ✅ Data integrity verified")
    
    print(f"\n🎯 Enhanced Shadow Portfolio State test complete!")
    return state

if __name__ == "__main__":
    main()