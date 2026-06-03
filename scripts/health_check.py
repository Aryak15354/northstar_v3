#!/usr/bin/env python3
"""
Health Check Script - Unified Volatility Engine

Validates system health and component status.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.volatility.state_engine import VolatilityStateEngine
from src.volatility.greeks_aggregator import GreeksAggregator
from src.volatility.risk_authority import UnifiedRiskAuthority
from src.volatility.regime_detector import RegimeDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_component(name, check_func):
    """Check a single component"""
    try:
        check_func()
        print(f"✅ {name}: OK")
        return True
    except Exception as e:
        print(f"❌ {name}: FAILED - {e}")
        return False


def check_state_engine():
    """Check state engine"""
    engine = VolatilityStateEngine()
    state = engine.get_state()
    assert state is not None


def check_greeks_aggregator():
    """Check Greeks aggregator"""
    agg = GreeksAggregator()
    assert agg is not None


def check_risk_authority():
    """Check risk authority"""
    risk = UnifiedRiskAuthority(
        position_limits={"per_underlying": 100, "total": 500},
        greeks_limits={"delta": 1000, "gamma": 500, "vega": 10000},
        concentration_limits={"max_pct_per_underlying": 0.2},
        margin_buffer=1.5
    )
    assert risk is not None


def check_regime_detector():
    """Check regime detector"""
    detector = RegimeDetector()
    regime = detector.detect_regime(vix=18, realized_vol=0.16, correlation=0.65)
    assert regime is not None


def check_disk_space():
    """Check disk space"""
    import shutil
    stat = shutil.disk_usage('.')
    free_gb = stat.free / (1024**3)
    if free_gb < 10:
        raise RuntimeError(f"Low disk space: {free_gb:.1f}GB free")


def check_memory():
    """Check memory"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            raise RuntimeError(f"High memory usage: {mem.percent}%")
    except ImportError:
        logger.warning("psutil not installed, skipping memory check")


def main():
    print("=" * 60)
    print("Unified Volatility Engine - Health Check")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    checks = [
        ("State Engine", check_state_engine),
        ("Greeks Aggregator", check_greeks_aggregator),
        ("Risk Authority", check_risk_authority),
        ("Regime Detector", check_regime_detector),
        ("Disk Space", check_disk_space),
        ("Memory", check_memory),
    ]
    
    results = []
    for name, check_func in checks:
        results.append(check_component(name, check_func))
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ System Health: GOOD")
        return 0
    else:
        print("❌ System Health: DEGRADED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
