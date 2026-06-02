#!/usr/bin/env python3
"""
Tests for DashboardDataContract

Validates that the data contract:
1. Reads only from approved sources
2. Computes freshness correctly
3. Handles unavailable data gracefully
4. Caches appropriately
5. Provides all required getters
"""

import pytest
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from src.dashboard.data_contract import (
    DashboardDataContract,
    DataFreshness,
    LabeledValue
)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory"""
    temp_dir = tempfile.mkdtemp()
    data_dir = Path(temp_dir) / "data"
    state_dir = data_dir / "state"
    pnl_dir = data_dir / "pnl"
    
    state_dir.mkdir(parents=True)
    pnl_dir.mkdir(parents=True)
    
    yield data_dir
    
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_unified_state(temp_data_dir):
    """Create mock unified state file"""
    state_file = temp_data_dir / "state" / "unified_state.json"
    
    state = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "portfolio": {
            "positions": {
                "RELIANCE": {"quantity": 100, "avg_cost": 2500, "weight_pct": 0.15},
                "TCS": {"quantity": 50, "avg_cost": 3500, "weight_pct": 0.10}
            },
            "options_positions": {},
            "options_net_delta": 150.5,
            "options_net_gamma": 5.2,
            "options_net_vega": 1200.0,
            "options_net_theta": -50.0,
            "last_updated": datetime.now().isoformat()
        },
        "pnl_state": {
            "intraday_pnl": 5000.0,
            "total_return_pct": 0.12,
            "sharpe_ratio": 1.8,
            "max_drawdown_pct": -0.08,
            "current_nav": 1120000.0,
            "last_updated": datetime.now().isoformat()
        },
        "governor_state": {
            "equity_fraction": 0.60,
            "options_fraction": 0.20,
            "cash_fraction": 0.20,
            "current_regime": "STANDARD",
            "decision_rationale": "Market conditions favorable",
            "confidence": 0.75,
            "last_updated": datetime.now().isoformat()
        },
        "market": {
            "regime": "expansion",
            "regime_confidence": 0.80,
            "last_updated": datetime.now().isoformat()
        },
        "sentiment": {
            "regime": "OPTIMISM",
            "market_sentiment_score": 0.65,
            "conviction": 0.70,
            "last_updated": datetime.now().isoformat()
        },
        "alternative_data": {
            "gst_yoy_growth": 0.08,
            "power_yoy_growth": 0.06,
            "credit_upgrade_ratio": 1.5,
            "bulk_net_flow": 0.12,
            "last_updated": datetime.now().isoformat()
        },
        "intelligence_state": {
            "available": True,
            "primary_shock_type": "oil_supply_disruption",
            "shock_severity": "HIGH",
            "shock_direction": "bearish",
            "shock_confidence": 0.82,
            "requires_immediate_hedge": True,
            "requires_portfolio_rebalance": True,
            "options_opportunity_detected": True,
            "selected_option_strategies": [
                {"strategy": "bear_put_spread", "underlying": "NIFTY"}
            ],
            "sector_impacts": {"Services": {"impact_score": -0.85}},
            "computed_at": datetime.now().isoformat()
        },
        "alpha_os": {
            "strategy_weights": {
                "momentum": 0.30,
                "value": 0.25,
                "quality": 0.25,
                "macro": 0.20
            },
            "last_updated": datetime.now().isoformat()
        },
        "health": {
            "overall_health_score": 0.85,
            "health_status": "good",
            "data_fresh": True,
            "data_freshness_hours": 0.5,
            "components_healthy": 8,
            "total_components": 10,
            "component_availability": 0.80,
            "last_updated": datetime.now().isoformat()
        }
    }
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file



def test_freshness_computation():
    """Test that freshness is computed correctly"""
    contract = DashboardDataContract()
    
    # LIVE: < 60 seconds
    now = datetime.now()
    assert contract._compute_freshness(now - timedelta(seconds=30)) == DataFreshness.LIVE
    
    # RECENT: < 5 minutes
    assert contract._compute_freshness(now - timedelta(minutes=3)) == DataFreshness.RECENT
    
    # STALE: < 30 minutes
    assert contract._compute_freshness(now - timedelta(minutes=15)) == DataFreshness.STALE
    
    # OLD: > 30 minutes
    assert contract._compute_freshness(now - timedelta(hours=1)) == DataFreshness.OLD
    
    # UNKNOWN: None
    assert contract._compute_freshness(None) == DataFreshness.UNKNOWN


def test_labeled_value_exposes_source_timestamp_and_age_minutes():
    now = datetime.now() - timedelta(minutes=7)
    labeled = LabeledValue(
        value=1,
        source="test",
        as_of=now,
        freshness=DataFreshness.STALE,
    )

    assert labeled.source_timestamp == now
    assert labeled.age_minutes is not None
    assert 6.0 <= labeled.age_minutes <= 8.0


def test_unavailable_returns_labeled_false(temp_data_dir):
    """Test that unavailable data returns proper LabeledValue"""
    contract = DashboardDataContract(
        state_path=str(temp_data_dir / "state" / "nonexistent.json")
    )
    
    result = contract.get_equity_positions()
    
    assert result.is_available == False
    assert result.unavailability_reason is not None
    assert result.freshness == DataFreshness.UNKNOWN
    assert result.value is None


def test_contract_reads_equity_positions(temp_data_dir, mock_unified_state):
    """Test reading equity positions"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )
    
    result = contract.get_equity_positions()
    
    assert result.is_available == True
    assert isinstance(result.value, dict)
    assert "RELIANCE" in result.value
    assert "TCS" in result.value
    assert result.source == "unified_state.json → portfolio.positions"
    assert result.freshness in [DataFreshness.LIVE, DataFreshness.RECENT]


def test_contract_reads_options_greeks(temp_data_dir, mock_unified_state):
    """Test reading options Greeks"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )
    
    result = contract.get_options_greeks()
    
    assert result.is_available == True
    assert isinstance(result.value, dict)
    assert 'delta' in result.value
    assert 'gamma' in result.value
    assert 'vega' in result.value
    assert 'theta' in result.value
    assert result.value['delta'] == 150.5


def test_contract_reads_governor_state(temp_data_dir, mock_unified_state):
    """Test reading Governor capital structure"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )
    
    result = contract.get_capital_structure()
    
    assert result.is_available == True
    assert result.value['equity_fraction'] == 0.60
    assert result.value['options_fraction'] == 0.20
    assert result.value['cash_fraction'] == 0.20


def test_contract_reads_sentiment(temp_data_dir, mock_unified_state):
    """Test reading sentiment state"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )
    
    result = contract.get_sentiment_state()
    
    assert result.is_available == True
    assert result.value['regime'] == "OPTIMISM"
    assert result.value['market_sentiment_score'] == 0.65


def test_contract_reads_market_intelligence(temp_data_dir, mock_unified_state):
    """Test reading news brain intelligence state"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )

    result = contract.get_market_intelligence()

    assert result.is_available == True
    assert result.value['primary_shock_type'] == "oil_supply_disruption"
    assert result.value['shock_severity'] == "HIGH"
    assert result.value['requires_immediate_hedge'] is True


def test_contract_exposes_new_alternative_data_keys(temp_data_dir, mock_unified_state):
    """Test corrected alt-data field names reach the dashboard contract"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )

    result = contract.get_alternative_data_state()

    assert result.is_available == True
    assert result.value['credit_upgrade_ratio'] == 1.5
    assert result.value['bulk_net_flow'] == 0.12


def test_cache_does_not_reload_within_30s(temp_data_dir, mock_unified_state):
    """Test that state is cached and not reloaded within TTL"""
    contract = DashboardDataContract(
        state_path=str(mock_unified_state)
    )
    
    # First load
    result1 = contract.get_equity_positions()
    cache_time1 = contract._state_cache_time
    
    # Second load (should use cache)
    result2 = contract.get_equity_positions()
    cache_time2 = contract._state_cache_time
    
    # Cache time should be the same (no reload)
    assert cache_time1 == cache_time2
    assert result1.value == result2.value


def test_all_getters_exist():
    """Test that all documented getters exist on DashboardDataContract"""
    contract = DashboardDataContract()
    
    # Live Trading tab methods
    assert hasattr(contract, 'get_equity_positions')
    assert hasattr(contract, 'get_options_positions')
    assert hasattr(contract, 'get_intraday_pnl')
    assert hasattr(contract, 'get_options_greeks')
    
    # Portfolio & Governor tab methods
    assert hasattr(contract, 'get_capital_structure')
    assert hasattr(contract, 'get_governor_regime')
    assert hasattr(contract, 'get_strategy_weights')
    
    # Intelligence & Regime tab methods
    assert hasattr(contract, 'get_market_regime')
    assert hasattr(contract, 'get_sentiment_state')
    assert hasattr(contract, 'get_alternative_data_state')
    assert hasattr(contract, 'get_market_intelligence')
    
    # Performance tab methods
    assert hasattr(contract, 'get_nav_history')
    assert hasattr(contract, 'get_performance_metrics')
    assert hasattr(contract, 'get_paper_fund_status')
    
    # System Operations tab methods
    assert hasattr(contract, 'get_system_health')
    assert hasattr(contract, 'get_state_reconciliation_status')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
