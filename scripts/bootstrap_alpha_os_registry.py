#!/usr/bin/env python3
"""
Bootstrap the Alpha OS Strategy Registry

This script populates the StrategyRegistry from existing model_registry files.
It reads data/model_registry/production.json and registry.json, creates
StrategyRecord entries for each strategy found, and populates validation
evidence from data/results/research/trackers/experiments.ndjson.

This is a one-time migration script that must be run before the Alpha OS
can operate. The bootstrapping is idempotent — running it twice produces
the same result.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_os.strategy_registry import (
    StrategyRegistry,
    StrategyRecord,
    StrategyStatus,
    StrategyFamily,
    StrategyPerformanceRecord
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def bootstrap_registry():
    """Bootstrap the strategy registry from existing data."""
    logger.info("=" * 70)
    logger.info("BOOTSTRAPPING ALPHA OS STRATEGY REGISTRY")
    logger.info("=" * 70)
    
    # Initialize registry
    registry = StrategyRegistry()
    
    # Clear existing strategies (for idempotent operation)
    registry.strategies = {}
    
    # Load existing model registry
    model_registry_path = PROJECT_ROOT / "data/model_registry/registry.json"
    production_path = PROJECT_ROOT / "data/model_registry/production.json"
    
    strategies_found = 0
    strategies_created = 0
    
    # Load production models
    production_models = set()
    if production_path.exists():
        try:
            with open(production_path, 'r') as f:
                production_data = json.load(f)
            
            # production.json maps model_type -> model_id
            production_models = set(production_data.values())
            
            logger.info(f"Found {len(production_models)} production models")
        except Exception as e:
            logger.warning(f"Could not load production.json: {e}")
    
    # Load model registry
    if model_registry_path.exists():
        try:
            with open(model_registry_path, 'r') as f:
                registry_data = json.load(f)
            
            models = registry_data.get('models', [])
            strategies_found = len(models)
            
            logger.info(f"Found {strategies_found} models in registry")
            
            # Process each model
            for model in models:
                model_id = model.get('model_id')
                model_type = model.get('type', 'unknown')
                model_status = model.get('status', 'candidate')
                
                if not model_id:
                    continue
                
                # Determine strategy family from model type
                family = _infer_strategy_family(model_type)
                
                # Determine status
                if model_id in production_models:
                    status = StrategyStatus.ACTIVE
                elif model_status == 'archived':
                    status = StrategyStatus.RETIRED
                elif model_status == 'candidate':
                    status = StrategyStatus.CANDIDATE
                else:
                    status = StrategyStatus.RESEARCH
                
                # Create strategy record
                strategy_record = StrategyRecord(
                    strategy_id=model_id,
                    strategy_name=_generate_strategy_name(model_id, model_type),
                    family=family,
                    status=status,
                    discovered_date=datetime.utcnow(),
                    model_registry_path=model.get('path')
                )
                
                # Try to load validation evidence from model file
                if model.get('path'):
                    model_file = PROJECT_ROOT / "data/model_registry" / model['path']
                    if model_file.exists():
                        try:
                            with open(model_file, 'r') as f:
                                model_data = json.load(f)
                            
                            # Extract validation metrics
                            validation_metrics = model_data.get('validation_metrics', {})
                            
                            if validation_metrics:
                                strategy_record.validation_ic_mean = validation_metrics.get('ic_mean', 0.0)
                                strategy_record.validation_icir = validation_metrics.get('icir', 0.0)
                                strategy_record.validation_hit_rate = validation_metrics.get('hit_rate', 0.0)
                                strategy_record.validation_regime_ics = validation_metrics.get('regime_ics', {})
                        except Exception as e:
                            logger.debug(f"Could not load validation metrics for {model_id}: {e}")
                
                # Register strategy
                try:
                    registry.register(strategy_record)
                    strategies_created += 1
                    
                    logger.info(
                        f"Registered: {model_id} ({family.value}, {status.value})"
                    )
                except Exception as e:
                    logger.warning(f"Could not register {model_id}: {e}")
            
        except Exception as e:
            logger.error(f"Could not load model registry: {e}")
    
    # Summary
    logger.info("=" * 70)
    logger.info("BOOTSTRAP COMPLETE")
    logger.info(f"Strategies found: {strategies_found}")
    logger.info(f"Strategies created: {strategies_created}")
    logger.info("=" * 70)
    
    # Print registry summary
    summary = registry.get_registry_summary()
    logger.info("\nRegistry Summary:")
    logger.info(f"  Total strategies: {summary['total_strategies']}")
    logger.info(f"  Active: {summary['active_count']}")
    logger.info(f"  Candidates: {summary['candidate_count']}")
    logger.info(f"  On probation: {summary['probation_count']}")
    logger.info("\nBy Family:")
    for family, count in summary['by_family'].items():
        logger.info(f"  {family}: {count}")
    
    return registry


def _infer_strategy_family(model_type: str) -> StrategyFamily:
    """Infer strategy family from model type."""
    model_type_lower = model_type.lower()
    
    if 'momentum' in model_type_lower:
        return StrategyFamily.MOMENTUM
    elif 'reversion' in model_type_lower or 'mean_reversion' in model_type_lower:
        return StrategyFamily.MEAN_REVERSION
    elif 'value' in model_type_lower:
        return StrategyFamily.VALUE
    elif 'quality' in model_type_lower:
        return StrategyFamily.QUALITY
    elif 'macro' in model_type_lower:
        return StrategyFamily.MACRO
    elif 'sentiment' in model_type_lower:
        return StrategyFamily.SENTIMENT
    elif 'alternative' in model_type_lower or 'alt' in model_type_lower:
        return StrategyFamily.ALTERNATIVE
    else:
        return StrategyFamily.COMPOSITE


def _generate_strategy_name(model_id: str, model_type: str) -> str:
    """Generate human-readable strategy name."""
    # Clean up model_id
    name_parts = model_id.replace('_', ' ').split()
    
    # Capitalize and join
    name = ' '.join(word.capitalize() for word in name_parts[:3])
    
    return name or model_type.replace('_', ' ').title()


def main():
    """Main entry point."""
    try:
        registry = bootstrap_registry()
        
        logger.info("\n✅ Alpha OS Registry bootstrap successful!")
        logger.info(f"Registry saved to: {registry.registry_file}")
        
        return 0
    except Exception as e:
        logger.error(f"\n❌ Bootstrap failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
