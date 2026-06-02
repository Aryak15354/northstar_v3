#!/usr/bin/env python3
"""
Start Engine Script

Starts the Unified Volatility Engine with specified configuration.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import yaml
from pathlib import Path
from datetime import datetime
from src.volatility.state_engine import VolatilityStateEngine
from src.volatility.strategy_generator import StrategyGenerator
from src.volatility.greeks_aggregator import GreeksAggregator
from src.volatility.risk_authority import UnifiedRiskAuthority
from src.volatility.dispersion_module import DispersionModule
from src.volatility.gamma_scalper import GammaScalper
from src.volatility.volatility_capital_allocator import CapitalAllocator
from src.volatility.monte_carlo_engine import MonteCarloEngine
from src.volatility.regime_detector import RegimeDetector
from src.volatility.execution_interface import ExecutionInterface
from src.volatility.performance_monitor import PerformanceMonitor
from src.volatility.unified_engine import UnifiedVolatilityEngine
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path):
    """Load configuration from file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def initialize_components(config):
    """Initialize all engine components"""
    logger.info("Initializing components...")
    
    # State engine
    state_engine = VolatilityStateEngine()
    
    # Strategy generator
    strategy_generator = StrategyGenerator(state_engine=state_engine)
    
    # Greeks aggregator
    greeks_aggregator = GreeksAggregator()
    
    # Risk authority
    risk_authority = UnifiedRiskAuthority(
        position_limits=config['position_limits'],
        greeks_limits=config['greeks_limits'],
        concentration_limits=config.get('concentration_limits', {}),
        margin_buffer=config.get('margin_buffer', 1.5)
    )
    
    # Dispersion module
    dispersion_module = DispersionModule(state_engine=state_engine)
    
    # Gamma scalper
    gamma_scalper = GammaScalper(state_engine=state_engine)
    
    # Capital allocator
    capital_allocator = CapitalAllocator()
    
    # Monte Carlo engine
    monte_carlo_engine = MonteCarloEngine(n_workers=config.get('monte_carlo_workers', 4))
    
    # Regime detector
    regime_detector = RegimeDetector()
    
    # Execution interface
    execution_interface = ExecutionInterface(
        venues=config.get('execution', {}).get('preferred_venues', ['CBOE'])
    )
    
    # Performance monitor
    performance_monitor = PerformanceMonitor()
    
    logger.info("✅ All components initialized")
    
    return {
        'state_engine': state_engine,
        'strategy_generator': strategy_generator,
        'greeks_aggregator': greeks_aggregator,
        'risk_authority': risk_authority,
        'dispersion_module': dispersion_module,
        'gamma_scalper': gamma_scalper,
        'capital_allocator': capital_allocator,
        'monte_carlo_engine': monte_carlo_engine,
        'regime_detector': regime_detector,
        'execution_interface': execution_interface,
        'performance_monitor': performance_monitor
    }


def start_engine(config_path, state_path=None):
    """Start the unified engine"""
    print("=" * 60)
    print("Unified Volatility Engine - Starting")
    print(f"Time: {datetime.now()}")
    print(f"Config: {config_path}")
    print("=" * 60)
    
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("snapshots", exist_ok=True)
    
    # Load configuration
    logger.info(f"Loading configuration from: {config_path}")
    config = load_config(config_path)
    
    # Initialize components
    components = initialize_components(config)
    
    # Create unified engine
    logger.info("Creating unified engine...")
    engine = UnifiedVolatilityEngine(**components)
    
    # Load state if provided
    if state_path and Path(state_path).exists():
        logger.info(f"Loading state from: {state_path}")
        components['state_engine'].load_state(state_path)
    
    # Save PID for shutdown script
    pid_file = "engine.pid"
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    print("\n✅ Engine started successfully")
    print(f"PID: {os.getpid()}")
    print(f"PID file: {pid_file}")
    print("\nEngine is running. Press Ctrl+C to stop.")
    
    try:
        # Keep running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        if Path(pid_file).exists():
            os.remove(pid_file)
        print("✅ Engine stopped")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Start Unified Volatility Engine')
    parser.add_argument('--config', required=True, help='Configuration file path')
    parser.add_argument('--state', help='State file to load')
    args = parser.parse_args()
    
    if not Path(args.config).exists():
        print(f"❌ Configuration file not found: {args.config}")
        return 1
    
    success = start_engine(args.config, args.state)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
