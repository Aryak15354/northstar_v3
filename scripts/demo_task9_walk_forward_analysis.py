#!/usr/bin/env python3
"""
Demo script for Task 9: Walk-Forward Analysis Engine.

This script demonstrates the comprehensive walk-forward analysis capabilities
including rolling window analysis, out-of-sample validation, strategy degradation
detection, and strategy evolution insights.
"""

import sys
import time
import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.operation.walk_forward_analysis_engine import WalkForwardAnalysisEngine
from src.operation.base_types import WalkForwardConfig, AlertLevel


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"📈 {title}")
    print(f"{'='*60}")


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n📊 {title}")
    print("-" * 40)


def print_result(key: str, value, indent: int = 0):
    """Print a formatted key-value result."""
    spaces = "  " * indent
    if isinstance(value, dict):
        print(f"{spaces}{key}:")
        for k, v in value.items():
            print_result(k, v, indent + 1)
    elif isinstance(value, list):
        print(f"{spaces}{key}: [{len(value)} items]")
        if len(value) <= 3:
            for item in value:
                print(f"{spaces}  - {item}")
        else:
            for item in value[:2]:
                print(f"{spaces}  - {item}")
            print(f"{spaces}  ... and {len(value) - 2} more")
    else:
        if isinstance(value, float):
            if abs(value) < 0.01:
                print(f"{spaces}{key}: {value:.4f}")
            elif abs(value) < 1:
                print(f"{spaces}{key}: {value:.3f}")
            else:
                print(f"{spaces}{key}: {value:.2f}")
        else:
            print(f"{spaces}{key}: {value}")


def demo_walk_forward_configuration():
    """Demonstrate walk-forward analysis configuration."""
    print_section("WALK-FORWARD ANALYSIS CONFIGURATION")
    
    # Create configuration
    config = WalkForwardConfig(
        training_window=12,  # 12 months training
        testing_window=6,    # 6 months testing
        step_size=3,         # 3 month steps
        optimization_metric="sharpe_ratio",
        minimum_observations=200,
        max_iterations=50
    )
    
    # Initialize engine
    engine = WalkForwardAnalysisEngine(config)
    
    print("🔧 Walk-Forward Analysis Engine Configuration:")
    print(f"   Training Window: {config.training_window} months")
    print(f"   Testing Window: {config.testing_window} months")
    print(f"   Step Size: {config.step_size} months")
    print(f"   Optimization Metric: {config.optimization_metric}")
    print(f"   Minimum Observations: {config.minimum_observations}")
    print(f"   Max Iterations: {config.max_iterations}")
    
    print(f"\n📋 Analysis Capabilities:")
    print(f"   Degradation Detectors: {len(engine.degradation_detectors)}")
    print(f"   Evolution Analyzers: {len(engine.evolution_analyzers)}")
    
    print(f"\n🔍 Degradation Detection Methods:")
    for detector_name in engine.degradation_detectors.keys():
        print(f"     - {detector_name}")
    
    print(f"\n📈 Evolution Analysis Methods:")
    for analyzer_name in engine.evolution_analyzers.keys():
        print(f"     - {analyzer_name}")
    
    return engine


def demo_rolling_window_generation(engine: WalkForwardAnalysisEngine):
    """Demonstrate rolling window generation."""
    print_section("ROLLING WINDOW GENERATION")
    
    # Test different date ranges
    test_scenarios = [
        {
            "name": "Short-term Analysis",
            "start_date": datetime(2020, 1, 1),
            "end_date": datetime(2021, 12, 31),
            "description": "2-year analysis period"
        },
        {
            "name": "Medium-term Analysis",
            "start_date": datetime(2019, 1, 1),
            "end_date": datetime(2022, 12, 31),
            "description": "4-year analysis period"
        },
        {
            "name": "Long-term Analysis",
            "start_date": datetime(2018, 1, 1),
            "end_date": datetime(2023, 12, 31),
            "description": "6-year analysis period"
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n📅 {scenario['name']} ({scenario['description']}):")
        
        start_date = scenario["start_date"]
        end_date = scenario["end_date"]
        
        # Generate windows
        windows = engine._generate_analysis_windows(start_date, end_date)
        
        print(f"   Date Range: {start_date.date()} to {end_date.date()}")
        print(f"   Windows Generated: {len(windows)}")
        
        if windows:
            print(f"   First Window:")
            print(f"     Training: {windows[0].training_start.date()} to {windows[0].training_end.date()}")
            print(f"     Testing: {windows[0].testing_start.date()} to {windows[0].testing_end.date()}")
            print(f"     Training Observations: {windows[0].training_observations}")
            print(f"     Testing Observations: {windows[0].testing_observations}")
            
            if len(windows) > 1:
                print(f"   Last Window:")
                print(f"     Training: {windows[-1].training_start.date()} to {windows[-1].training_end.date()}")
                print(f"     Testing: {windows[-1].testing_start.date()} to {windows[-1].testing_end.date()}")
                
                # Show window progression
                step_size_days = (windows[1].training_start - windows[0].training_start).days
                print(f"   Window Step Size: {step_size_days} days (~{step_size_days/30:.1f} months)")
        else:
            print(f"   ⚠️  No windows generated (date range too short)")
    
    return windows


def demo_comprehensive_walk_forward_analysis(engine: WalkForwardAnalysisEngine):
    """Demonstrate comprehensive walk-forward analysis."""
    print_section("COMPREHENSIVE WALK-FORWARD ANALYSIS")
    
    # Define analysis parameters
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2022, 12, 31)
    strategies = [
        "momentum_strategy",
        "mean_reversion_strategy", 
        "value_strategy",
        "quality_strategy",
        "combined_strategy"
    ]
    
    print(f"🚀 Running comprehensive walk-forward analysis...")
    print(f"   Analysis Period: {start_date.date()} to {end_date.date()}")
    print(f"   Strategies: {len(strategies)}")
    for strategy in strategies:
        print(f"     - {strategy}")
    
    # Execute analysis
    analysis_start = time.time()
    results = engine.run_comprehensive_walk_forward_analysis(start_date, end_date, strategies)
    analysis_duration = time.time() - analysis_start
    
    print(f"\n📊 Analysis Results:")
    print(f"   Windows Analyzed: {len(results)}")
    print(f"   Total Analysis Time: {analysis_duration:.2f} seconds")
    print(f"   Average Time per Window: {analysis_duration/len(results):.2f} seconds" if results else "   N/A")
    
    # Show window results summary
    if results:
        print(f"\n📈 Window Results Summary:")
        
        for i, result in enumerate(results[:3]):  # Show first 3 windows
            print(f"\n   Window {i+1}: {result.window_id}")
            print(f"     Training: {result.training_start.date()} to {result.training_end.date()}")
            print(f"     Testing: {result.testing_start.date()} to {result.testing_end.date()}")
            print(f"     Strategies Analyzed: {len(result.strategy_results)}")
            
            # Show strategy performance
            for strategy_result in result.strategy_results:
                strategy_name = strategy_result["strategy_name"]
                oos_return = strategy_result["out_of_sample_return"]
                oos_sharpe = strategy_result["out_of_sample_sharpe"]
                
                print(f"       {strategy_name}:")
                print(f"         Out-of-Sample Return: {oos_return:.2%}")
                print(f"         Out-of-Sample Sharpe: {oos_sharpe:.3f}")
        
        if len(results) > 3:
            print(f"   ... and {len(results) - 3} more windows")
        
        # Calculate aggregate statistics
        all_returns = []
        all_sharpes = []
        strategy_performance = {}
        
        for result in results:
            for strategy_result in result.strategy_results:
                strategy_name = strategy_result["strategy_name"]
                oos_return = strategy_result["out_of_sample_return"]
                oos_sharpe = strategy_result["out_of_sample_sharpe"]
                
                all_returns.append(oos_return)
                all_sharpes.append(oos_sharpe)
                
                if strategy_name not in strategy_performance:
                    strategy_performance[strategy_name] = {"returns": [], "sharpes": []}
                
                strategy_performance[strategy_name]["returns"].append(oos_return)
                strategy_performance[strategy_name]["sharpes"].append(oos_sharpe)
        
        print(f"\n📊 Aggregate Performance Statistics:")
        print(f"   Overall Average Return: {np.mean(all_returns):.2%}")
        print(f"   Overall Average Sharpe: {np.mean(all_sharpes):.3f}")
        print(f"   Return Volatility: {np.std(all_returns):.2%}")
        print(f"   Sharpe Volatility: {np.std(all_sharpes):.3f}")
        
        print(f"\n🏆 Strategy Performance Ranking:")
        strategy_avg_returns = {
            strategy: np.mean(perf["returns"]) 
            for strategy, perf in strategy_performance.items()
        }
        
        sorted_strategies = sorted(strategy_avg_returns.items(), key=lambda x: x[1], reverse=True)
        
        for rank, (strategy, avg_return) in enumerate(sorted_strategies, 1):
            avg_sharpe = np.mean(strategy_performance[strategy]["sharpes"])
            consistency = 1.0 / (np.std(strategy_performance[strategy]["returns"]) + 1e-6)
            
            print(f"   {rank}. {strategy}:")
            print(f"      Average Return: {avg_return:.2%}")
            print(f"      Average Sharpe: {avg_sharpe:.3f}")
            print(f"      Consistency Score: {consistency:.1f}")
    
    return results


def demo_strategy_degradation_detection(engine: WalkForwardAnalysisEngine):
    """Demonstrate strategy degradation detection."""
    print_section("STRATEGY DEGRADATION DETECTION")
    
    print("🔍 Testing degradation detection capabilities...")
    
    # Test different degradation scenarios
    degradation_scenarios = [
        {
            "name": "Stable Strategy",
            "description": "Consistent performance over time",
            "pattern": "stable"
        },
        {
            "name": "Gradually Declining Strategy",
            "description": "Slow performance degradation",
            "pattern": "gradual_decline"
        },
        {
            "name": "Sudden Drop Strategy",
            "description": "Abrupt performance deterioration",
            "pattern": "sudden_drop"
        },
        {
            "name": "Volatile Strategy",
            "description": "Highly variable performance",
            "pattern": "volatile"
        }
    ]
    
    degradation_results = []
    
    for scenario in degradation_scenarios:
        strategy_name = scenario["name"].lower().replace(" ", "_")
        pattern = scenario["pattern"]
        
        print(f"\n🧪 Testing {scenario['name']}:")
        print(f"   Description: {scenario['description']}")
        
        # Generate mock performance history based on pattern
        mock_history = generate_mock_performance_history(pattern, 10)
        engine.strategy_performance_history[strategy_name] = mock_history
        
        # Detect degradation
        degradation_result = engine.detect_strategy_degradation(strategy_name)
        degradation_results.append((scenario, degradation_result))
        
        # Show results
        print(f"   Degradation Detected: {'✅ YES' if degradation_result.degradation_detected else '❌ NO'}")
        
        if degradation_result.degradation_detected:
            print(f"   Severity: {degradation_result.degradation_severity}")
            print(f"   Performance Decline: {degradation_result.performance_decline_pct:.1f}%")
            print(f"   Statistical Significance: {degradation_result.statistical_significance:.3f}")
            print(f"   Degradation Start: {degradation_result.degradation_start_date.date() if degradation_result.degradation_start_date else 'Unknown'}")
            
            print(f"   Recommended Actions:")
            for action in degradation_result.recommended_actions[:3]:
                print(f"     - {action}")
            
            if len(degradation_result.recommended_actions) > 3:
                print(f"     ... and {len(degradation_result.recommended_actions) - 3} more")
        else:
            print(f"   Status: Performance within normal parameters")
    
    # Show degradation alerts
    if engine.degradation_alerts:
        print(f"\n⚠️  Degradation Alerts Generated: {len(engine.degradation_alerts)}")
        
        alert_counts = {}
        for alert in engine.degradation_alerts:
            level = alert.level.value
            alert_counts[level] = alert_counts.get(level, 0) + 1
        
        for level, count in alert_counts.items():
            print(f"     {level.upper()}: {count}")
        
        # Show recent alerts
        print(f"\n📢 Recent Degradation Alerts:")
        for alert in engine.degradation_alerts[-3:]:
            print(f"     - {alert.level.value.upper()}: {alert.message}")
    
    return degradation_results


def demo_strategy_evolution_analysis(engine: WalkForwardAnalysisEngine):
    """Demonstrate strategy evolution analysis."""
    print_section("STRATEGY EVOLUTION ANALYSIS")
    
    print("📈 Analyzing strategy evolution patterns...")
    
    # Test evolution analysis for strategies with sufficient history
    strategies_to_analyze = [
        "momentum_strategy",
        "mean_reversion_strategy",
        "value_strategy"
    ]
    
    evolution_results = []
    
    for strategy_name in strategies_to_analyze:
        print(f"\n🔬 Analyzing {strategy_name} evolution:")
        
        # Generate evolution insights
        evolution_result = engine.generate_strategy_evolution_insights(strategy_name)
        evolution_results.append(evolution_result)
        
        print(f"   Analysis Period: {evolution_result.analysis_period_start.date()} to {evolution_result.analysis_period_end.date()}")
        print(f"   Evolution Detected: {'✅ YES' if evolution_result.evolution_detected else '❌ NO'}")
        print(f"   Confidence Score: {evolution_result.confidence_score:.3f}")
        
        if evolution_result.evolution_detected and evolution_result.evolution_insights:
            print(f"   Evolution Insights:")
            
            for insight_type, insights in evolution_result.evolution_insights.items():
                if insights.get("detected", False):
                    print(f"     {insight_type.replace('_', ' ').title()}:")
                    for insight in insights.get("insights", [])[:2]:
                        print(f"       - {insight}")
        
        print(f"   Recommendations:")
        for rec in evolution_result.recommendations[:3]:
            print(f"     - {rec}")
        
        if len(evolution_result.recommendations) > 3:
            print(f"     ... and {len(evolution_result.recommendations) - 3} more")
    
    # Show evolution summary
    print(f"\n📊 Evolution Analysis Summary:")
    total_strategies = len(evolution_results)
    evolved_strategies = len([r for r in evolution_results if r.evolution_detected])
    
    print(f"   Strategies Analyzed: {total_strategies}")
    print(f"   Strategies with Evolution: {evolved_strategies}")
    print(f"   Evolution Rate: {evolved_strategies / total_strategies:.1%}" if total_strategies > 0 else "   Evolution Rate: N/A")
    
    if evolution_results:
        avg_confidence = np.mean([r.confidence_score for r in evolution_results])
        print(f"   Average Confidence Score: {avg_confidence:.3f}")
    
    return evolution_results


def demo_walk_forward_metrics_and_reporting(engine: WalkForwardAnalysisEngine):
    """Demonstrate walk-forward metrics calculation and reporting."""
    print_section("WALK-FORWARD METRICS & REPORTING")
    
    print("📊 Generating comprehensive walk-forward metrics...")
    
    # Get comprehensive metrics
    metrics = engine.get_walk_forward_metrics()
    
    # Show analysis statistics
    print(f"\n📈 Analysis Statistics:")
    analysis_stats = metrics["analysis_statistics"]
    print_result("Total Analyses", analysis_stats["total_analyses"])
    print_result("Total Windows", analysis_stats["total_windows"])
    print_result("Average Windows per Analysis", analysis_stats["avg_windows_per_analysis"])
    print_result("Analysis Success Rate", f"{analysis_stats['analysis_success_rate']:.1%}")
    
    # Show strategy statistics
    if metrics["strategy_statistics"]:
        print(f"\n🎯 Strategy Statistics:")
        for strategy, stats in metrics["strategy_statistics"].items():
            print(f"   {strategy}:")
            print(f"     Windows Analyzed: {stats['windows']}")
            print(f"     Average Performance: {stats['avg_performance']:.2%}")
            if "degradation_rate" in stats:
                print(f"     Degradation Rate: {stats['degradation_rate']:.1%}")
    
    # Show degradation statistics
    print(f"\n💥 Degradation Statistics:")
    degradation_stats = metrics["degradation_statistics"]
    print_result("Total Degradations", degradation_stats["total_degradations"])
    print_result("Critical Degradations", degradation_stats["critical_degradations"])
    print_result("Strategies with Degradation", degradation_stats["strategies_with_degradation"])
    
    # Show evolution statistics
    print(f"\n📈 Evolution Statistics:")
    evolution_stats = metrics["evolution_statistics"]
    print_result("Total Evolution Analyses", evolution_stats["total_evolution_analyses"])
    print_result("Strategies with Evolution", evolution_stats["strategies_with_evolution"])
    
    # Show configuration
    print(f"\n⚙️  Window Configuration:")
    window_config = metrics["window_configuration"]
    print_result("Training Window", f"{window_config['training_window_months']} months")
    print_result("Testing Window", f"{window_config['testing_window_months']} months")
    print_result("Step Size", f"{window_config['step_size_months']} months")
    print_result("Minimum Observations", window_config["minimum_observations"])
    
    print_result("Alerts Generated", metrics["alerts_generated"])
    print_result("Metrics Timestamp", metrics["metrics_timestamp"])
    
    return metrics


def generate_mock_performance_history(pattern: str, num_periods: int) -> list:
    """Generate mock performance history based on pattern."""
    history = []
    base_return = 0.12  # 12% base return
    base_sharpe = 1.5   # 1.5 base Sharpe
    
    for i in range(num_periods):
        timestamp = datetime(2020, 1, 1) + timedelta(days=i*90)
        
        if pattern == "stable":
            # Stable performance with small random variations
            return_val = base_return + np.random.normal(0, 0.02)
            sharpe_val = base_sharpe + np.random.normal(0, 0.1)
            volatility = 0.15 + np.random.normal(0, 0.01)
            drawdown = 0.08 + np.random.normal(0, 0.01)
            
        elif pattern == "gradual_decline":
            # Gradual decline over time
            decline_factor = 1.0 - (i * 0.08)  # 8% decline per period
            return_val = base_return * decline_factor + np.random.normal(0, 0.01)
            sharpe_val = base_sharpe * decline_factor + np.random.normal(0, 0.05)
            volatility = 0.15 + (i * 0.02) + np.random.normal(0, 0.01)
            drawdown = 0.08 + (i * 0.015) + np.random.normal(0, 0.005)
            
        elif pattern == "sudden_drop":
            # Sudden drop after period 6
            if i < 6:
                return_val = base_return + np.random.normal(0, 0.02)
                sharpe_val = base_sharpe + np.random.normal(0, 0.1)
                volatility = 0.15 + np.random.normal(0, 0.01)
                drawdown = 0.08 + np.random.normal(0, 0.01)
            else:
                return_val = base_return * 0.3 + np.random.normal(0, 0.03)  # Drop to 30%
                sharpe_val = base_sharpe * 0.2 + np.random.normal(0, 0.1)   # Drop to 20%
                volatility = 0.25 + np.random.normal(0, 0.02)
                drawdown = 0.18 + np.random.normal(0, 0.02)
                
        elif pattern == "volatile":
            # High volatility in performance
            return_val = base_return + np.random.normal(0, 0.08)  # High variance
            sharpe_val = base_sharpe + np.random.normal(0, 0.5)   # High variance
            volatility = 0.15 + abs(np.random.normal(0, 0.05))
            drawdown = 0.08 + abs(np.random.normal(0, 0.04))
        
        else:
            # Default to stable
            return_val = base_return + np.random.normal(0, 0.02)
            sharpe_val = base_sharpe + np.random.normal(0, 0.1)
            volatility = 0.15 + np.random.normal(0, 0.01)
            drawdown = 0.08 + np.random.normal(0, 0.01)
        
        # Ensure reasonable bounds
        return_val = max(-0.5, min(0.5, return_val))
        sharpe_val = max(-2.0, min(5.0, sharpe_val))
        volatility = max(0.05, min(0.5, volatility))
        drawdown = max(0.01, min(0.3, abs(drawdown)))
        
        history.append({
            "window_id": f"WF_{i:03d}",
            "timestamp": timestamp,
            "out_of_sample_return": return_val,
            "out_of_sample_sharpe": sharpe_val,
            "testing_performance": {
                "total_return": return_val,
                "volatility": volatility,
                "max_drawdown": drawdown,
                "sharpe_ratio": sharpe_val
            }
        })
    
    return history


def main():
    """Run the complete Walk-Forward Analysis Engine demonstration."""
    print_header("NORTHSTAR V3 WALK-FORWARD ANALYSIS ENGINE DEMO")
    
    print("This demonstration showcases the comprehensive walk-forward analysis")
    print("capabilities including rolling window analysis, out-of-sample validation,")
    print("strategy degradation detection, and strategy evolution insights.")
    
    try:
        # 1. Configuration
        engine = demo_walk_forward_configuration()
        
        # 2. Rolling Window Generation
        windows = demo_rolling_window_generation(engine)
        
        # 3. Comprehensive Walk-Forward Analysis
        analysis_results = demo_comprehensive_walk_forward_analysis(engine)
        
        # 4. Strategy Degradation Detection
        degradation_results = demo_strategy_degradation_detection(engine)
        
        # 5. Strategy Evolution Analysis
        evolution_results = demo_strategy_evolution_analysis(engine)
        
        # 6. Metrics and Reporting
        final_metrics = demo_walk_forward_metrics_and_reporting(engine)
        
        # Final Summary
        print_header("DEMO COMPLETION SUMMARY")
        
        print(f"✅ Configuration: Walk-forward engine configured successfully")
        print(f"📅 Window Generation: {len(windows) if windows else 0} windows generated")
        print(f"📊 Analysis Results: {len(analysis_results)} windows analyzed")
        print(f"🔍 Degradation Detection: {len(degradation_results)} strategies tested")
        print(f"📈 Evolution Analysis: {len(evolution_results)} strategies analyzed")
        
        # Show final statistics
        if final_metrics:
            analysis_stats = final_metrics["analysis_statistics"]
            print(f"📈 Total Windows Processed: {analysis_stats['total_windows']}")
            print(f"⚠️  Total Alerts Generated: {final_metrics['alerts_generated']}")
            
            degradation_stats = final_metrics["degradation_statistics"]
            print(f"💥 Degradations Detected: {degradation_stats['total_degradations']}")
            
            evolution_stats = final_metrics["evolution_statistics"]
            print(f"📈 Evolution Analyses: {evolution_stats['total_evolution_analyses']}")
        
        print(f"\n🎉 Walk-Forward Analysis Engine demonstration completed successfully!")
        print(f"The system demonstrated comprehensive walk-forward validation capabilities")
        print(f"with robust degradation detection and strategy evolution analysis.")
        
    except Exception as e:
        print(f"\n💥 Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()