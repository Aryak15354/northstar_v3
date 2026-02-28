#!/usr/bin/env python3
"""
Debug script to understand why no positions are being generated
"""

import sys
import os
from src.intelligence.institutional_alpha_engine import InstitutionalAlphaEngine, AlphaEngineConfig

def debug_position_sizing():
    """Debug the position sizing issue"""
    
    print("🔍 DEBUGGING POSITION SIZING")
    print("=" * 50)
    
    # Initialize engine
    config = AlphaEngineConfig(log_level="WARNING")
    engine = InstitutionalAlphaEngine(config)
    
    # Simple market data
    market_data = {
        'regime': 'expansion',
        'regime_confidence': 85.0,
        'volatility': 0.15,
        'liquidity': 0.80,
        'sentiment': 0.65
    }
    
    # Small universe
    universe = ['RELIANCE.NS', 'TCS.NS']
    
    # Generate positions
    result = engine.generate_alpha_positions(market_data, universe)
    
    print(f"\n📊 RESULTS:")
    print(f"Allocations: {result.allocations}")
    print(f"Positions: {result.positions}")
    print(f"Performance Metrics: {result.performance_metrics}")
    print(f"Alerts: {result.alerts}")
    
    return result

if __name__ == "__main__":
    debug_position_sizing()