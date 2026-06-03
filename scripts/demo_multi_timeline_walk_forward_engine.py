#!/usr/bin/env python3
"""
🔄 MULTI-TIMELINE WALK-FORWARD ENGINE DEMO - SHADOW REALITY PHASE 4.3
Demo script for testing the MultiTimelineWalkForwardEngine

This demonstrates the enhanced walk-forward validation capabilities:
- Multi-timeline validation across different historical periods
- Integration with existing walk-forward validation infrastructure
- Phase 3 component validation integration
- Cross-timeline consistency checking
- Enhanced temporal discipline and data leakage prevention
"""

import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def run_multi_timeline_walk_forward_demo():
    """Run the MultiTimelineWalkForwardEngine demo"""
    
    print("🔄 MULTI-TIMELINE WALK-FORWARD ENGINE DEMO")
    print("Enhanced Walk-Forward Validation with Multi-Timeline Capabilities")
    print("=" * 70)
    
    try:
        # Import the engine
        from validation.multi_timeline_walk_forward_engine import (
            MultiTimelineWalkForwardEngine, 
            MultiTimelineWalkForwardConfig,
            create_default_config
        )
        
        print("✅ Successfully imported MultiTimelineWalkForwardEngine")
        
        # Create configuration
        config = create_default_config()
        print(f"✅ Created configuration with {len(config.validation_periods)} periods")
        
        # Initialize engine
        engine = MultiTimelineWalkForwardEngine(config)
        print("✅ Initialized multi-timeline walk-forward engine")
        
        # Run complete validation
        print(f"\n🚀 Running complete multi-timeline validation...")
        validation_result, consistency_results = engine.run_complete_validation()
        
        if validation_result:
            print(f"\n✅ Multi-timeline walk-forward validation completed!")
            print(f"   🎯 Overall Status: {validation_result.overall_validation_status.value}")
            print(f"   📈 Consistency Score: {validation_result.overall_consistency_score:.3f}")
            print(f"   📊 Success Rate: {validation_result.success_rate:.1%}")
            print(f"   🔧 Periods Tested: {validation_result.periods_tested}")
            
            if consistency_results:
                print(f"   🔄 Consistency Analysis: Completed")
                print(f"   📊 Overall Consistency: {consistency_results.get('overall_consistency_level', 'unknown')}")
            
            return True
        else:
            print(f"\n❌ Multi-timeline walk-forward validation failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔧 Make sure the MultiTimelineWalkForwardEngine is properly implemented")
        return False
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main demo function"""
    
    print("🔄 MULTI-TIMELINE WALK-FORWARD ENGINE DEMO")
    print("Testing Enhanced Walk-Forward Validation with Multi-Timeline Capabilities")
    print("=" * 70)
    
    success = run_multi_timeline_walk_forward_demo()
    
    if success:
        print(f"\n✅ Demo completed successfully!")
        print("🎯 MultiTimelineWalkForwardEngine is working correctly")
        print("📊 Enhanced walk-forward validation with multi-timeline capabilities functional")
        print("🔧 Integration with existing walk-forward infrastructure successful")
    else:
        print(f"\n❌ Demo failed - check implementation")
    
    return success

if __name__ == "__main__":
    main()