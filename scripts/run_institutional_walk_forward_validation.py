#!/usr/bin/env python3
"""
Execute Institutional Walk-Forward Validation

This script runs the rigorous 12-month walk-forward validation under
strict institutional rules. NO OPTIMIZATION ALLOWED.

This is historical behavior verification under frozen rules.
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.validation.institutional_walk_forward_validator import (
    InstitutionalWalkForwardValidator, 
    FrozenRules
)


def main():
    """Execute institutional walk-forward validation"""
    
    # Setup logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'institutional_walk_forward.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    print("🔒 NORTHSTAR V3 INSTITUTIONAL WALK-FORWARD VALIDATION")
    print("="*70)
    print("⚠️  CRITICAL: This is NOT backtesting or optimization")
    print("⚠️  This is historical behavior verification under FROZEN rules")
    print("⚠️  NO parameters will be changed after seeing results")
    print("="*70)
    
    # Confirm user understands the rules
    print("\n📋 VALIDATION RULES:")
    print("1. ❌ NO parameter optimization")
    print("2. ❌ NO threshold tweaking") 
    print("3. ❌ NO cherry-picking periods")
    print("4. ❌ NO future information leakage")
    print("5. ✅ COMPLETE temporal discipline")
    print("6. ✅ Rules are FROZEN and immutable")
    
    confirmation = input("\n🤔 Do you understand and accept these rules? (yes/no): ").lower().strip()
    
    if confirmation != 'yes':
        print("❌ Validation cancelled - rules not accepted")
        return
    
    try:
        logger.info("🚀 Starting institutional walk-forward validation")
        
        # Define FROZEN rules - IMMUTABLE after this point
        print("\n🔒 FREEZING SYSTEM RULES...")
        frozen_rules = FrozenRules(
            # Regime Logic (FROZEN)
            regime_detection_window=252,
            regime_confidence_threshold=0.7,
            regime_persistence_days=21,
            
            # Trend Logic (FROZEN)  
            trend_short_window=21,
            trend_long_window=63,
            trend_confirmation_days=5,
            
            # Exposure States & Bands (FROZEN)
            risk_on_max_exposure=0.8,
            risk_off_max_exposure=0.3,
            neutral_max_exposure=0.5,
            
            # Position Sizing Rules (FROZEN)
            max_single_position=0.1,
            max_sector_exposure=0.3,
            position_size_increment=0.02,
            
            # Exit Logic (FROZEN)
            stop_loss_threshold=0.15,
            profit_target_multiple=3.0,
            trend_exit_confirmation=3,
            
            # Drawdown Covenant (FROZEN)
            max_portfolio_drawdown=0.2,
            daily_var_limit=0.03,
            
            # Evaluation Cadence (FROZEN)
            rebalance_frequency="weekly",
            evaluation_day="friday"
        )
        
        print("✅ Rules frozen and immutable")
        logger.warning("RULES ARE NOW FROZEN - NO MODIFICATIONS ALLOWED")
        
        # Initialize validator
        print("\n🏗️  Initializing validator...")
        validator = InstitutionalWalkForwardValidator(frozen_rules)
        
        # Run validation
        print("\n🔄 Running walk-forward validation...")
        print("   This will test 8 years (2018-2025) with 12-month windows")
        print("   Each window is fully out-of-sample with 12-month warmup")
        
        validation_summary = validator.run_validation(
            start_year=2018,
            end_year=2025
        )
        
        # Display results
        print("\n" + "="*70)
        print("🏆 INSTITUTIONAL WALK-FORWARD VALIDATION COMPLETE")
        print("="*70)
        
        print(f"\n📊 VALIDATION SUMMARY:")
        print(f"   Validation ID: {validation_summary.validation_id}")
        print(f"   Total Windows: {validation_summary.total_windows}")
        print(f"   Successful Windows: {validation_summary.successful_windows}")
        print(f"   Validation Status: {'✅ PASSED' if validation_summary.validation_passed else '❌ FAILED'}")
        
        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"   Total Period Return: {validation_summary.total_period_return:.2%}")
        print(f"   Average Annual Return: {validation_summary.average_annual_return:.2%}")
        print(f"   Aggregate Sharpe Ratio: {validation_summary.aggregate_sharpe:.2f}")
        
        print(f"\n⚠️  RISK METRICS (PRIMARY FOCUS):")
        print(f"   Worst Drawdown: {validation_summary.worst_drawdown:.2%}")
        print(f"   Average Drawdown: {validation_summary.average_drawdown:.2%}")
        print(f"   Longest Drawdown: {validation_summary.longest_drawdown_days} days")
        
        print(f"\n🎯 CONVICTION INTEGRITY (CRITICAL):")
        print(f"   Average Exposure: {validation_summary.average_exposure_all_windows:.1%}")
        print(f"   Regime Accuracy: {validation_summary.regime_accuracy:.1%}")
        print(f"   Discipline Score: {validation_summary.discipline_score:.1%}")
        
        print(f"\n😰 PAIN ANALYSIS:")
        print(f"   Worst 12M Return: {validation_summary.worst_12m_return:.2%}")
        print(f"   Worst 12M Sharpe: {validation_summary.worst_12m_sharpe:.2f}")
        print(f"   Worst 12M Drawdown: {validation_summary.worst_12m_drawdown:.2%}")
        
        print(f"\n🔍 SYSTEM BEHAVIOR VALIDATION:")
        behavior_checks = [
            ("Behaved as designed", validation_summary.behaved_as_designed),
            ("Stayed exposed when uncomfortable", validation_summary.stayed_exposed_when_uncomfortable),
            ("Exited only for structural reasons", validation_summary.exited_only_for_structural_reasons),
            ("Drawdowns within covenant", validation_summary.drawdowns_within_covenant),
            ("Shows payoff asymmetry", validation_summary.shows_payoff_asymmetry)
        ]
        
        for check_name, passed in behavior_checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
        
        # Critical question
        print(f"\n🤔 CRITICAL QUESTION:")
        print(f"   'What was the worst 12-month experience this system delivered,")
        print(f"    and could I live with it again?'")
        print(f"   ")
        print(f"   ANSWER: The worst period was {validation_summary.worst_12m_return:.2%} return")
        print(f"           with {validation_summary.worst_12m_drawdown:.2%} drawdown.")
        
        if validation_summary.worst_12m_return > -0.25:
            print(f"   ✅ This is within acceptable institutional risk parameters.")
        else:
            print(f"   ❌ This exceeds comfortable risk tolerance.")
            print(f"      Consider reducing initial capital or leverage.")
        
        # Final recommendation
        print(f"\n🎯 FINAL RECOMMENDATION:")
        
        if validation_summary.validation_passed:
            print(f"   ✅ PROCEED LIVE - System demonstrates institutional discipline")
            print(f"   ✅ The system behaved exactly as designed")
            print(f"   ✅ Conviction mechanisms maintained discipline under stress")
            print(f"   ❌ DO NOT TWEAK - Any modifications invalidate this validation")
        else:
            print(f"   ❌ DO NOT PROCEED - Address issues before live deployment")
            print(f"   ⚠️  System failed to meet institutional standards")
            print(f"   🔧 Review discipline score and behavior validation failures")
        
        # Report locations
        print(f"\n📋 DETAILED REPORTS:")
        print(f"   Institutional Report: data/validation/walk_forward/reports/")
        print(f"   Raw Results: data/validation/walk_forward/results/")
        print(f"   Validation Logs: logs/institutional_walk_forward.log")
        
        print("\n" + "="*70)
        
        if validation_summary.validation_passed:
            print("🎉 VALIDATION PASSED - SYSTEM READY FOR LIVE DEPLOYMENT")
            logger.info("🎉 Institutional validation PASSED")
        else:
            print("⚠️  VALIDATION FAILED - SYSTEM NOT READY FOR LIVE DEPLOYMENT")
            logger.warning("⚠️ Institutional validation FAILED")
        
        print("="*70)
        
        # Stress test one brutal period
        print(f"\n🔥 STRESS TEST RECOMMENDATION:")
        print(f"   Consider running detailed stress test on worst period:")
        print(f"   - 2020 (COVID crash)")
        print(f"   - 2018 (Volatility spike)")  
        print(f"   - 2022 (Rate hike cycle)")
        print(f"   Use: python scripts/stress_test_brutal_period.py --year 2020")
        
    except Exception as e:
        logger.error(f"Institutional walk-forward validation failed: {e}")
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise


if __name__ == "__main__":
    main()