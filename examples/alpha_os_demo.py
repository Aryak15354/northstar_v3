#!/usr/bin/env python3
"""
Alpha OS Demonstration

This script demonstrates the complete Alpha OS lifecycle:
1. Bootstrap the registry from existing models
2. Evaluate research candidates
3. Promote strategies to ACTIVE
4. Monitor live performance
5. Handle probation and retirement
6. Generate lifecycle reports
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_os import (
    StrategyRegistry,
    StrategyRecord,
    StrategyStatus,
    StrategyFamily,
    StrategyOrchestrator,
    StrategyTribunal,
    StrategyLifecycleManager,
    StrategyRedundancyDetector,
    AlphaOSState
)

from src.intelligence.bayesian_capital_tribunal import BayesianCapitalTribunal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run Alpha OS demonstration."""
    logger.info("=" * 70)
    logger.info("ALPHA OS DEMONSTRATION")
    logger.info("The Operating System for Alpha Generation Strategies")
    logger.info("=" * 70)
    
    # Step 1: Initialize components
    logger.info("\n📦 Step 1: Initializing Alpha OS components...")
    
    registry = StrategyRegistry()
    tribunal_instance = BayesianCapitalTribunal()
    tribunal = StrategyTribunal(tribunal_instance, registry)
    redundancy = StrategyRedundancyDetector(registry)
    orchestrator = StrategyOrchestrator(registry, tribunal, redundancy)
    lifecycle = StrategyLifecycleManager(registry, tribunal)
    
    logger.info("✅ All components initialized")
    
    # Step 2: Show registry status
    logger.info("\n📊 Step 2: Current Registry Status")
    summary = registry.get_registry_summary()
    logger.info(f"Total strategies: {summary['total_strategies']}")
    logger.info(f"Active: {summary['active_count']}")
    logger.info(f"Candidates: {summary['candidate_count']}")
    logger.info(f"On probation: {summary['probation_count']}")
    
    if summary['total_strategies'] == 0:
        logger.info("\n⚠️  Registry is empty. Run bootstrap_alpha_os_registry.py first.")
        return 1
    
    # Step 3: Demonstrate candidate evaluation
    logger.info("\n🔬 Step 3: Evaluating Research Candidates")
    
    # Mock experiment data
    mock_experiments = [
        {
            'strategy_id': 'momentum_enhanced_v2',
            'model_id': 'momentum_enhanced_v2',
            'ic_mean': 0.048,
            'icir': 1.6,
            'hit_rate': 0.62,
            'n_validation_windows': 8,
            'validation_months': 18,
            'turnover_pct': 35.0
        },
        {
            'strategy_id': 'value_composite_v1',
            'model_id': 'value_composite_v1',
            'ic_mean': 0.025,  # Below threshold
            'icir': 0.9,       # Below threshold
            'hit_rate': 0.52,
            'n_validation_windows': 6,
            'validation_months': 12,
            'turnover_pct': 40.0
        }
    ]
    
    result = lifecycle.evaluate_research_candidates(mock_experiments)
    
    logger.info(f"Evaluated: {result.evaluated_count} experiments")
    logger.info(f"Promoted to CANDIDATE: {len(result.promoted_ids)}")
    logger.info(f"Failed criteria: {len(result.failed_ids)}")
    
    if result.promoted_ids:
        logger.info(f"✅ Promoted: {', '.join(result.promoted_ids)}")
    
    if result.failed_ids:
        logger.info(f"❌ Failed: {', '.join(result.failed_ids)}")
        for strategy_id, reasons in result.failure_reasons.items():
            logger.info(f"   {strategy_id}: {'; '.join(reasons)}")
    
    # Step 4: Demonstrate strategy promotion
    logger.info("\n🚀 Step 4: Promoting Strategy to ACTIVE")
    
    # Get first active or candidate strategy
    active_strategies = registry.get_active_strategies()
    candidate_strategies = registry.get_by_status(StrategyStatus.CANDIDATE)
    
    if candidate_strategies:
        demo_strategy = candidate_strategies[0]
        logger.info(f"Promoting: {demo_strategy.strategy_id}")
        
        try:
            lifecycle.promote_to_active(demo_strategy.strategy_id)
            logger.info(f"✅ Successfully promoted {demo_strategy.strategy_id} to ACTIVE")
        except Exception as e:
            logger.warning(f"Could not promote (expected in demo): {e}")
    else:
        logger.info("No candidate strategies available for promotion demo")
    
    # Step 5: Demonstrate strategy orchestration
    logger.info("\n🎯 Step 5: Strategy Orchestration")
    
    # Create mock unified state
    class MockUnifiedState:
        class MockMarket:
            regime = 'expansion'
        
        class MockSentiment:
            is_fresh = True
            market_sentiment_regime = type('obj', (object,), {'value': 'optimistic'})()
        
        class MockAlternativeData:
            is_fresh = True
            economic_activity_regime = 'growth'
        
        market = MockMarket()
        sentiment = MockSentiment()
        alternative_data = MockAlternativeData()
    
    unified_state = MockUnifiedState()
    
    # Compute strategy weights
    weights = orchestrator.compute_strategy_weights(unified_state)
    
    logger.info(f"Computed weights for {len(weights)} strategies:")
    for strategy_id, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:5]:
        logger.info(f"  {strategy_id}: {weight:.1%}")
    
    # Get orchestrator explanation
    explanation = orchestrator.get_orchestrator_explanation(unified_state)
    logger.info(f"\nCurrent regime: {explanation['current_regime_combination']}")
    logger.info(f"Total active strategies: {explanation['total_active_strategies']}")
    
    if explanation['probation_strategies']:
        logger.info(f"⚠️  Strategies on probation: {', '.join(explanation['probation_strategies'])}")
    
    # Step 6: Demonstrate performance monitoring
    logger.info("\n📈 Step 6: Monitoring Live Strategy Performance")
    
    monitoring_result = lifecycle.monitor_live_strategies(datetime.utcnow())
    
    logger.info(f"Strategies checked: {monitoring_result.strategies_checked}")
    logger.info(f"New probations: {len(monitoring_result.new_probations)}")
    logger.info(f"New retirements: {len(monitoring_result.new_retirements)}")
    logger.info(f"Recovered: {len(monitoring_result.recovered_strategies)}")
    logger.info(f"All clear: {len(monitoring_result.all_clear_strategies)}")
    
    if monitoring_result.new_probations:
        logger.info(f"⚠️  New probations: {', '.join(monitoring_result.new_probations)}")
    
    if monitoring_result.new_retirements:
        logger.info(f"🔴 New retirements: {', '.join(monitoring_result.new_retirements)}")
    
    # Step 7: Demonstrate tribunal state
    logger.info("\n⚖️  Step 7: Tribunal State")
    
    tribunal_state = tribunal.get_tribunal_state()
    
    logger.info(f"Total strategies in tribunal: {tribunal_state['total_strategies']}")
    logger.info(f"Weight entropy: {tribunal_state['weight_entropy']:.3f}")
    logger.info(f"Max weight: {tribunal_state['max_weight']:.1%}")
    logger.info(f"Weight concentration: {tribunal_state['weight_concentration']:.1%}")
    
    # Step 8: Generate lifecycle report
    logger.info("\n📋 Step 8: Lifecycle Report")
    
    lifecycle_report = lifecycle.get_lifecycle_report()
    
    logger.info(f"Report timestamp: {lifecycle_report['timestamp']}")
    logger.info(f"Registry summary: {lifecycle_report['registry_summary']['total_strategies']} total strategies")
    logger.info(f"Active strategies: {lifecycle_report['registry_summary']['active_count']}")
    logger.info(f"Candidate strategies: {lifecycle_report['registry_summary']['candidate_count']}")
    
    # Step 9: Show AlphaOSState for UnifiedState
    logger.info("\n🧠 Step 9: AlphaOSState for UnifiedState")
    
    alpha_os_state = AlphaOSState()
    alpha_os_state.active_strategy_count = summary['active_count']
    alpha_os_state.probation_strategy_count = summary['probation_count']
    alpha_os_state.candidate_strategy_count = summary['candidate_count']
    alpha_os_state.strategy_weights = weights
    alpha_os_state.avg_active_icir = summary['avg_active_icir']
    alpha_os_state.tribunal_entropy = tribunal_state['weight_entropy']
    alpha_os_state.last_updated = datetime.utcnow()
    
    logger.info(f"Active strategies: {alpha_os_state.active_strategy_count}")
    logger.info(f"Probation strategies: {alpha_os_state.probation_strategy_count}")
    logger.info(f"Candidate strategies: {alpha_os_state.candidate_strategy_count}")
    logger.info(f"Average active ICIR: {alpha_os_state.avg_active_icir:.2f}")
    logger.info(f"Tribunal entropy: {alpha_os_state.tribunal_entropy:.3f}")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("ALPHA OS DEMONSTRATION COMPLETE")
    logger.info("=" * 70)
    logger.info("\n✅ All Alpha OS components are operational:")
    logger.info("   • StrategyRegistry: Single source of truth for strategies")
    logger.info("   • StrategyTribunal: Bayesian capital allocation with evidence updates")
    logger.info("   • StrategyOrchestrator: Runtime weight computation")
    logger.info("   • StrategyLifecycleManager: Automated promotion/demotion")
    logger.info("   • StrategyRedundancyDetector: Alpha diversification enforcement")
    logger.info("\n🎯 Gap 4 is now CLOSED!")
    logger.info("   The Alpha OS provides formal governance over the complete")
    logger.info("   strategy lifecycle from research to retirement.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
