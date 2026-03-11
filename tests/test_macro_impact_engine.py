#!/usr/bin/env python3
"""
🧪 MACRO IMPACT ENGINE - UNIT TESTS
Test all MIE components
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.macro_impact_engine import (
    MacroDataLoader,
    MacroPreprocessor,
    LaggedRegressionEngine,
    GrangerCausalityTester,
    RollingBetaEstimator,
    StabilityAnalyzer,
    SectorAggregator,
    MacroImpactReportGenerator
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_macro_data():
    """Generate sample macro data"""
    dates = pd.date_range('2018-01-01', '2023-12-31', freq='W')
    n_vars = 10
    
    data = {}
    for i in range(n_vars):
        # Random walk + trend
        data[f'macro_var_{i}'] = np.cumsum(np.random.randn(len(dates))) + np.arange(len(dates)) * 0.01
    
    df = pd.DataFrame(data, index=dates)
    return df


@pytest.fixture
def sample_returns_data():
    """Generate sample company returns"""
    dates = pd.date_range('2018-01-01', '2023-12-31', freq='W')
    n_companies = 20
    
    data = {}
    for i in range(n_companies):
        # Random returns with some autocorrelation
        returns = np.random.randn(len(dates)) * 0.02
        data[f'COMPANY_{i}.NS'] = returns
    
    df = pd.DataFrame(data, index=dates)
    return df


@pytest.fixture
def sample_sector_map():
    """Generate sample sector mapping"""
    sector_map = {}
    for i in range(20):
        sector = ['Financials', 'IT', 'Auto', 'FMCG'][i % 4]
        sector_map[f'COMPANY_{i}.NS'] = sector
    return sector_map


# ============================================================================
# TEST PREPROCESSING
# ============================================================================

def test_preprocessor_initialization():
    """Test preprocessor initialization"""
    preprocessor = MacroPreprocessor(lags=[0, 1, 2, 4])
    assert preprocessor.lags == [0, 1, 2, 4]
    assert preprocessor.winsorize_pct == 0.01


def test_macro_percent_normalization_skips_fx_levels():
    df = pd.DataFrame(
        {
            "Policy Repo Rate (%)": [6.5, 6.5, 6.5],
            "Exchange Rate INR per USD": [83.2, 83.5, 83.1],
        }
    )
    norm, log = MacroDataLoader._normalize_percent_like_columns(df)
    assert "Policy Repo Rate (%)" in log
    assert np.isclose(float(norm["Policy Repo Rate (%)"].iloc[0]), 0.065)
    assert "Exchange Rate INR per USD" not in log
    assert np.isclose(float(norm["Exchange Rate INR per USD"].iloc[0]), 83.2)


def test_stationarity_check(sample_macro_data):
    """Test stationarity checking"""
    preprocessor = MacroPreprocessor()
    
    series = sample_macro_data.iloc[:, 0]
    result = preprocessor.check_stationarity(series)
    
    assert 'is_stationary' in result
    assert 'p_value' in result


def test_make_stationary(sample_macro_data):
    """Test stationarity transformation"""
    preprocessor = MacroPreprocessor()
    
    stationary_df, transform_log = preprocessor.make_stationary(sample_macro_data)
    
    assert len(stationary_df.columns) == len(sample_macro_data.columns)
    assert len(transform_log) == len(sample_macro_data.columns)


def test_standardization(sample_macro_data):
    """Test z-score standardization"""
    preprocessor = MacroPreprocessor()
    
    standardized_df, std_params = preprocessor.standardize(sample_macro_data)
    
    # Check mean ≈ 0 and std ≈ 1
    for col in standardized_df.columns:
        series = standardized_df[col].dropna()
        assert abs(series.mean()) < 0.1
        assert abs(series.std() - 1.0) < 0.1


def test_lag_construction(sample_macro_data):
    """Test lag construction"""
    preprocessor = MacroPreprocessor(lags=[0, 1, 2])
    
    lagged_df = preprocessor.construct_lags(sample_macro_data)
    
    # Should have original_vars × n_lags columns
    expected_cols = len(sample_macro_data.columns) * 3
    assert len(lagged_df.columns) == expected_cols


# ============================================================================
# TEST REGRESSION ENGINE
# ============================================================================

def test_regression_engine_initialization():
    """Test regression engine initialization"""
    engine = LaggedRegressionEngine(fdr_alpha=0.05)
    assert engine.fdr_alpha == 0.05
    assert engine.min_observations == 52


def test_design_matrix_preparation(sample_macro_data):
    """Test design matrix construction"""
    engine = LaggedRegressionEngine()
    
    X, column_names = engine.prepare_design_matrix(sample_macro_data, add_intercept=True)
    
    assert X.shape[0] == len(sample_macro_data)
    assert X.shape[1] == len(sample_macro_data.columns) + 1  # +1 for intercept
    assert column_names[0] == 'intercept'


def test_ols_estimation(sample_returns_data, sample_macro_data):
    """Test OLS estimation"""
    engine = LaggedRegressionEngine()
    
    # Prepare data
    y = sample_returns_data.iloc[:, 0].values
    X, column_names = engine.prepare_design_matrix(sample_macro_data)
    
    # Estimate
    results = engine.estimate_ols(y, X, column_names)
    
    assert results['success']
    assert 'coefficients' in results
    assert 'std_errors' in results
    assert 't_stats' in results
    assert 'p_values' in results
    assert 'r_squared' in results


def test_fdr_correction():
    """Test FDR correction"""
    engine = LaggedRegressionEngine()
    
    # Generate p-values
    p_values = np.array([0.001, 0.01, 0.05, 0.1, 0.5, 0.9])
    
    rejected, n_rejected = engine.apply_fdr_correction(p_values, alpha=0.05)
    
    assert len(rejected) == len(p_values)
    assert n_rejected >= 0
    assert n_rejected <= len(p_values)


# ============================================================================
# TEST SECTOR AGGREGATION
# ============================================================================

def test_sector_aggregator_initialization():
    """Test sector aggregator initialization"""
    aggregator = SectorAggregator()
    assert aggregator is not None


def test_sector_aggregation(sample_sector_map):
    """Test aggregation to sector level"""
    aggregator = SectorAggregator()
    
    # Create sample beta DataFrame
    beta_df = pd.DataFrame({
        'ticker': [f'COMPANY_{i}.NS' for i in range(20)],
        'macro_variable': ['macro_var_0'] * 20,
        'lag': [4] * 20,
        'beta': np.random.randn(20),
        't_stat': np.random.randn(20),
        'p_value': np.random.rand(20)
    })
    
    sector_betas = aggregator.aggregate_to_sector(beta_df, sample_sector_map)
    
    assert 'sector' in sector_betas.columns
    assert 'n_companies' in sector_betas.columns
    assert len(sector_betas) > 0


# ============================================================================
# TEST ROLLING BETA
# ============================================================================

def test_rolling_beta_estimator():
    """Test rolling beta estimation"""
    estimator = RollingBetaEstimator(window_sizes=[52, 104])
    
    # Generate correlated series
    dates = pd.date_range('2018-01-01', '2023-12-31', freq='W')
    x = pd.Series(np.random.randn(len(dates)), index=dates)
    y = 0.5 * x + np.random.randn(len(dates)) * 0.5
    
    rolling_beta = estimator.estimate_rolling_beta(y, x, window=52)
    
    assert len(rolling_beta) == len(y)
    assert rolling_beta.dropna().mean() > 0  # Should be positive


def test_stability_computation():
    """Test stability metric computation"""
    estimator = RollingBetaEstimator()
    
    # Generate rolling beta series
    rolling_beta = pd.Series(np.random.randn(100) * 0.1 + 0.5)
    
    stability = estimator.compute_stability(rolling_beta)
    
    assert 'stability' in stability
    assert 'mean_beta' in stability
    assert 'std_beta' in stability


# ============================================================================
# TEST REPORT GENERATOR
# ============================================================================

def test_report_generator_initialization(tmp_path):
    """Test report generator initialization"""
    report_gen = MacroImpactReportGenerator(output_dir=str(tmp_path))
    assert report_gen.output_dir.exists()


def test_company_fingerprint_generation():
    """Test company fingerprint generation"""
    report_gen = MacroImpactReportGenerator()
    
    # Mock regression results
    regression_results = {
        'success': True,
        'n_obs': 260,
        'r_squared': 0.45,
        'adj_r_squared': 0.42,
        'coefficients': np.array([0.1, 0.5, -0.3, 0.2]),
        't_stats': np.array([1.0, 5.0, -3.0, 2.0]),
        'p_values': np.array([0.3, 0.001, 0.003, 0.05]),
        'fdr_rejected': np.array([False, True, True, True]),
        'column_names': ['intercept', 'macro_var_0_lag4', 'macro_var_1_lag8', 'macro_var_2_lag2']
    }
    
    fingerprint = report_gen.generate_company_fingerprint('TEST.NS', regression_results, top_n=3)
    
    assert fingerprint['ticker'] == 'TEST.NS'
    assert 'r_squared' in fingerprint
    assert 'top_drivers' in fingerprint


# ============================================================================
# INTEGRATION TEST
# ============================================================================

def test_full_pipeline_integration(sample_macro_data, sample_returns_data, sample_sector_map):
    """Test full MIE pipeline"""
    
    # 1. Preprocess
    preprocessor = MacroPreprocessor(lags=[0, 1, 2])
    macro_processed, _ = preprocessor.preprocess_macro(
        sample_macro_data,
        make_stationary=False,  # Skip for speed
        construct_lags=True
    )
    returns_processed = preprocessor.preprocess_returns(sample_returns_data)
    
    # 2. Run regressions
    engine = LaggedRegressionEngine()
    results = engine.run_all_companies(
        returns_processed,
        macro_processed,
        market_factor=None,
        max_companies=5  # Limit for speed
    )
    
    assert len(results) == 5
    
    # 3. Extract betas
    beta_df = engine.extract_macro_betas(results, 'macro_var_0')
    
    if not beta_df.empty:
        # 4. Aggregate to sectors
        aggregator = SectorAggregator()
        sector_betas = aggregator.aggregate_to_sector(beta_df, sample_sector_map)
        
        assert len(sector_betas) > 0


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
