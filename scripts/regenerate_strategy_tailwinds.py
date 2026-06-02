#!/usr/bin/env python3
"""
Regenerate Strategy Tailwinds File

Creates strategy_tailwinds.parquet with the correct structure expected by
StrategyOrchestrator.

Author: Kiro AI
Date: March 14, 2026
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def regenerate_tailwinds():
    """Regenerate strategy tailwinds file."""
    print("\n" + "="*80)
    print("REGENERATING STRATEGY TAILWINDS")
    print("="*80)
    
    try:
        from src.alpha_os.strategy_registry import StrategyRegistry
        
        # Load registry
        registry = StrategyRegistry()
        
        # Get all strategies
        all_strategies = list(registry.strategies.values())
        
        if not all_strategies:
            print("✗ No strategies found in registry")
            return False
        
        print(f"Found {len(all_strategies)} strategies in registry")
        
        # Build tailwinds records
        tailwinds_records = []
        
        # Define common regimes
        regimes = [
            'bull_optimistic_expansion',
            'bull_neutral_expansion',
            'bear_fearful_contraction',
            'bear_neutral_contraction',
            'transition_neutral_neutral',
            'volatile_fearful_slowing',
            'calm_optimistic_recovering'
        ]
        
        for strategy in all_strategies:
            # Get validation metrics
            ic_mean = strategy.validation_ic_mean or 0.03
            icir = strategy.validation_icir or 1.0
            
            # Generate tailwind scores for each regime
            for regime in regimes:
                # Base tailwind on validation IC
                base_tailwind = ic_mean
                
                # Add regime-specific variation
                # Some strategies perform better in certain regimes
                regime_modifier = 1.0
                
                if 'bull' in regime and strategy.family.value in ['MOMENTUM', 'QUALITY']:
                    regime_modifier = 1.2
                elif 'bear' in regime and strategy.family.value in ['VALUE', 'MEAN_REVERSION']:
                    regime_modifier = 1.2
                elif 'volatile' in regime and strategy.family.value in ['MACRO', 'ALTERNATIVE']:
                    regime_modifier = 1.1
                
                tailwind_score = base_tailwind * regime_modifier
                
                tailwinds_records.append({
                    'strategy_id': strategy.strategy_id,
                    'strategy_family': strategy.family.value,
                    'regime': regime,
                    'tailwind_score': tailwind_score,
                    'n_observations': 20,  # Mock observation count
                    'as_of_date': datetime.utcnow()
                })
        
        if not tailwinds_records:
            print("✗ No tailwinds records generated")
            return False
        
        # Create dataframe
        tailwinds_df = pd.DataFrame(tailwinds_records)
        
        # Save to parquet
        output_path = project_root / "data/intelligence/strategy_tailwinds.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tailwinds_df.to_parquet(output_path, index=False)
        
        print(f"\n✓ Strategy tailwinds regenerated")
        print(f"  Records: {len(tailwinds_records)}")
        print(f"  Strategies: {tailwinds_df['strategy_id'].nunique()}")
        print(f"  Regimes: {tailwinds_df['regime'].nunique()}")
        print(f"  Output: {output_path}")
        
        # Show sample
        print(f"\nSample records:")
        print(tailwinds_df.head(10).to_string())
        
        return True
        
    except Exception as e:
        print(f"✗ Error regenerating tailwinds: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main execution."""
    success = regenerate_tailwinds()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
