#!/usr/bin/env python3
"""
🔄 CROSS-TIMELINE CONSISTENCY CHECKER DEMO - SHADOW REALITY PHASE 4.3
Demo script for testing the CrossTimelineConsistencyChecker

This demonstrates the cross-timeline consistency analysis capabilities:
- Loads component validation results from Phase3ComponentValidator
- Analyzes consistency patterns across multiple timelines
- Identifies components contributing to performance variance
- Flags potential overfitting or regime dependence
- Generates variance attribution reports and recommendations

Integration with Phase 3:
- Uses results from Phase3ComponentValidator
- Analyzes RegimeMemorySystem, SimpleTailwindEngine, NoEdgeDetector, AnticipatoryCapitalAllocator
- Provides cross-timeline consistency scoring and recommendations
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import json

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def create_mock_component_validation_data():
    """Create mock component validation data for testing"""
    
    print("🔧 Creating mock component validation data...")
    
    # Define periods and components
    periods = ['crisis_2008', 'recovery_2009', 'expansion_2014', 'covid_crash_2020', 'inflation_shock_2022']
    components = ['regime_memory_system', 'simple_tailwind_engine', 'no_edge_detector', 'anticipatory_capital_allocator']
    
    # Create mock validation results
    validation_data = []
    
    for period in periods:
        for component in components:
            # Create realistic but varied performance across periods
            base_score = np.random.uniform(0.4, 0.9)
            
            # Add period-specific adjustments
            if period == 'crisis_2008':
                if component == 'no_edge_detector':
                    base_score = np.random.uniform(0.7, 0.9)  # Should perform well in crisis
                elif component == 'regime_memory_system':
                    base_score = np.random.uniform(0.6, 0.8)  # Moderate performance
                else:
                    base_score = np.random.uniform(0.3, 0.6)  # Lower performance in crisis
            
            elif period == 'covid_crash_2020':
                if component == 'no_edge_detector':
                    base_score = np.random.uniform(0.8, 0.95)  # Excellent in extreme crisis
                elif component == 'anticipatory_capital_allocator':
                    base_score = np.random.uniform(0.2, 0.5)  # Struggled with unprecedented event
                else:
                    base_score = np.random.uniform(0.4, 0.7)
            
            elif period in ['recovery_2009', 'expansion_2014']:
                if component == 'simple_tailwind_engine':
                    base_score = np.random.uniform(0.7, 0.9)  # Good in trending markets
                elif component == 'anticipatory_capital_allocator':
                    base_score = np.random.uniform(0.6, 0.85)  # Good allocation opportunities
                else:
                    base_score = np.random.uniform(0.5, 0.8)
            
            else:  # inflation_shock_2022
                # Mixed performance across components
                base_score = np.random.uniform(0.4, 0.8)
            
            validation_data.append({
                'period': period,
                'component': component,
                'validation_passed': base_score > 0.5,
                'score': base_score,
                'issues_count': np.random.randint(0, 3),
                'validation_timestamp': datetime.now().isoformat()
            })
    
    # Create DataFrame
    results_df = pd.DataFrame(validation_data)
    
    print(f"   ✅ Created {len(validation_data)} validation records")
    print(f"   📊 Periods: {len(periods)}, Components: {len(components)}")
    
    return results_df

def create_mock_metadata():
    """Create mock metadata for component validation"""
    
    return {
        'validation_summary': {
            'periods_tested': 5,
            'periods_passed': 4,
            'success_rate': 0.8,
            'validation_passed': True
        },
        'component_statistics': {
            'regime_memory_system': {'periods_passed': 4, 'total_periods': 5, 'success_rate': 0.8},
            'simple_tailwind_engine': {'periods_passed': 3, 'total_periods': 5, 'success_rate': 0.6},
            'no_edge_detector': {'periods_passed': 5, 'total_periods': 5, 'success_rate': 1.0},
            'anticipatory_capital_allocator': {'periods_passed': 3, 'total_periods': 5, 'success_rate': 0.6}
        },
        'validation_timestamp': datetime.now().isoformat(),
        'validator_version': '4.3.1'
    }

def run_consistency_checker_demo():
    """Run the CrossTimelineConsistencyChecker demo"""
    
    print("🔄 CROSS-TIMELINE CONSISTENCY CHECKER DEMO")
    print("Performance Variance Attribution Across Multiple Timelines")
    print("=" * 70)
    
    try:
        # Import the consistency checker
        from validation.cross_timeline_consistency_checker import CrossTimelineConsistencyChecker
        
        # Create temporary directory for demo data
        temp_dir = tempfile.mkdtemp()
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Create mock data
        mock_results_df = create_mock_component_validation_data()
        mock_metadata = create_mock_metadata()
        
        # Save mock data to temporary files
        component_validation_path = os.path.join(temp_dir, 'phase3_component_validation.parquet')
        component_metadata_path = os.path.join(temp_dir, 'phase3_component_metadata.json')
        
        mock_results_df.to_parquet(component_validation_path, index=False)
        
        with open(component_metadata_path, 'w') as f:
            json.dump(mock_metadata, f, indent=2)
        
        print(f"   💾 Saved mock validation data: {component_validation_path}")
        print(f"   💾 Saved mock metadata: {component_metadata_path}")
        
        # Initialize consistency checker with temporary paths
        checker = CrossTimelineConsistencyChecker()
        
        # Update paths to use temporary directory
        checker.paths['component_validation_results'] = component_validation_path
        checker.paths['component_metadata'] = component_metadata_path
        checker.paths['consistency_output'] = os.path.join(temp_dir, 'cross_timeline_consistency.parquet')
        checker.paths['consistency_metadata'] = os.path.join(temp_dir, 'cross_timeline_consistency_metadata.json')
        checker.paths['variance_attribution'] = os.path.join(temp_dir, 'variance_attribution_report.json')
        
        # Prepare component results
        component_results = {
            'results_df': mock_results_df,
            'metadata': mock_metadata
        }
        
        print(f"\n🔍 Running cross-timeline consistency analysis...")
        
        # Run the consistency analysis
        consistency_results = checker.run_cross_timeline_analysis(component_results)
        
        if consistency_results:
            print(f"\n✅ Cross-timeline consistency analysis completed successfully!")
            
            # Save results
            success = checker.save_consistency_results(consistency_results)
            
            if success:
                print(f"💾 Results saved successfully")
                
                # Display key findings
                print(f"\n📊 KEY FINDINGS:")
                print(f"   🎯 Overall Consistency: {consistency_results['overall_consistency_level'].upper()}")
                print(f"   📈 Consistency Score: {consistency_results['overall_consistency_score']:.3f}")
                
                print(f"\n📋 Component Consistency:")
                for component, data in consistency_results['component_consistency'].items():
                    print(f"   • {component}: {data['consistency_level']} ({data['consistency_score']:.3f})")
                
                print(f"\n🏛️ Regime Dependence:")
                for component, data in consistency_results['regime_analysis'].items():
                    print(f"   • {component}: {data['dependence_level']} dependence")
                
                print(f"\n⚠️ High Variance Components:")
                high_variance = consistency_results['variance_analysis']['high_variance_components']
                if high_variance:
                    for component in high_variance:
                        print(f"   • {component}")
                else:
                    print("   None identified")
                
                print(f"\n💡 Recommendations:")
                recommendations = consistency_results['recommendations']
                if recommendations:
                    for rec_category in recommendations:
                        component = rec_category['component']
                        rec_count = len(rec_category['recommendations'])
                        print(f"   • {component}: {rec_count} recommendations")
                else:
                    print("   No specific recommendations needed")
                
                # Show variance attribution
                print(f"\n📊 Variance Attribution:")
                variance_attr = consistency_results['variance_analysis']['variance_attribution']
                for component, contribution in variance_attr.items():
                    print(f"   • {component}: {contribution:.1f}%")
                
                return True
            else:
                print(f"❌ Failed to save results")
                return False
        else:
            print(f"❌ Cross-timeline consistency analysis failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔧 Make sure the CrossTimelineConsistencyChecker is properly implemented")
        return False
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup temporary directory
        try:
            import shutil
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir)
                print(f"🧹 Cleaned up temporary directory")
        except:
            pass

def main():
    """Main demo function"""
    
    print("🔄 CROSS-TIMELINE CONSISTENCY CHECKER DEMO")
    print("Testing Performance Variance Attribution Analysis")
    print("=" * 70)
    
    success = run_consistency_checker_demo()
    
    if success:
        print(f"\n✅ Demo completed successfully!")
        print("🎯 CrossTimelineConsistencyChecker is working correctly")
        print("📊 Variance attribution and consistency analysis functional")
    else:
        print(f"\n❌ Demo failed - check implementation")
    
    return success

if __name__ == "__main__":
    main()