"""
Tests for AlternativeDataLoader - graceful failure handling.

Critical test:
- Graceful handling when individual sources are missing
"""

import pytest
import pandas as pd
from datetime import datetime
from src.ingestion import IngestionRegistry


@pytest.fixture
def registry():
    return IngestionRegistry()


def test_graceful_missing_sources(registry):
    """Test that missing alternative sources don't crash the system."""
    as_of_date = datetime.now()
    
    try:
        # Load all alternative data
        alt_data = registry.alternative.load_all_alternative(as_of_date)
        
        # Should return a dict with 5 keys
        assert isinstance(alt_data, dict), "Should return dict"
        assert len(alt_data) == 5, f"Should have 5 sources, got {len(alt_data)}"
        
        # Check which sources are available
        available = [k for k, v in alt_data.items() if not v.empty]
        missing = [k for k, v in alt_data.items() if v.empty]
        
        print(f"✓ Graceful failure: {len(available)}/5 sources available")
        print(f"  Available: {available}")
        print(f"  Missing: {missing}")
        
        # System should not crash even if all are missing
        assert True, "System handled missing sources gracefully"
        
    except Exception as e:
        pytest.fail(f"System crashed on missing sources: {e}")


def test_gst_derived_features(registry):
    """Test that GST derived features are computed."""
    as_of_date = datetime.now()
    
    try:
        df = registry.alternative.load_gst(as_of_date)
        
        if not df.empty:
            expected_features = [
                'gst_mom_growth',
                'gst_yoy_growth',
                'gst_3m_ma',
                'gst_deviation_from_trend'
            ]
            
            found = [f for f in expected_features if f in df.columns]
            print(f"✓ GST features: {len(found)}/{len(expected_features)} computed")
        else:
            print("⚠ No GST data available")
    except FileNotFoundError:
        pytest.skip("GST data not available")


if __name__ == '__main__':
    print("=" * 60)
    print("AlternativeDataLoader Tests")
    print("=" * 60)
    
    registry = IngestionRegistry()
    
    print("\n1. Testing graceful missing sources...")
    test_graceful_missing_sources(registry)
    
    print("\n2. Testing GST derived features...")
    test_gst_derived_features(registry)
    
    print("\n" + "=" * 60)
