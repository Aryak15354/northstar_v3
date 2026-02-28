#!/usr/bin/env python3
"""
🧠 MACRO IMPACT ENGINE - DEMONSTRATION SCRIPT
Institutional-grade macro-equity transmission analysis

This script demonstrates the full MIE pipeline:
1. Load RBI macro data + company returns
2. Preprocess and construct lags
3. Run lagged regressions
4. Test Granger causality
5. Estimate rolling betas
6. Aggregate to sector level
7. Generate reports

Usage:
    python examples/macro_impact_engine_demo.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime

# Import MIE components
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


def run_macro_impact_analysis(
    macro_variables: list = None,
    tickers: list = None,
    max_companies: int = 50,  # Limit for demo
    start_date: str = "2018-01-01"
):
    """
    Run complete macro impact analysis
    
    Args:
        macro_variables: List of macro variables to analyze (None = use top 50)
        tickers: List of company tickers (None = use all available)
        max_companies: Maximum number of companies to analyze
        start_date: Start date for analysis
    """
    
    print("=" * 80)
    print("🧠 MACRO IMPACT ENGINE - INSTITUTIONAL ANALYSIS")
    print("=" * 80)
    print(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Start Date: {start_date}")
    print(f"Max Companies: {max_companies}")
    
    # ========================================================================
    # STEP 1: LOAD DATA
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: DATA LOADING")
    print("=" * 80)
    
    loader = MacroDataLoader(target_frequency='W')  # Weekly frequency
    
    # Load all data
    data = loader.load_all(
        macro_variables=macro_variables,
        tickers=tickers,
        start_date=start_date
    )
    
    macro_df = data['macro']
    returns_df = data['returns']
    market_factor = data['market']
    sector_map = data['sector_map']
    
    # Limit companies for demo
    if len(returns_df.columns) > max_companies:
        returns_df = returns_df.iloc[:, :max_companies]
        print(f"\n   ⚠️ Limited to {max_companies} companies for demo")
    
    # ========================================================================
    # STEP 2: PREPROCESSING
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: PREPROCESSING")
    print("=" * 80)
    
    preprocessor = MacroPreprocessor(
        lags=[0, 1, 2, 4, 8, 12],  # 0 to 12 weeks
        winsorize_pct=0.01
    )
    
    # Preprocess macro variables
    macro_processed, macro_metadata = preprocessor.preprocess_macro(
        macro_df,
        make_stationary=True,
        standardize=True,
        winsorize=True,
        construct_lags=True
    )
    
    # Preprocess returns
    returns_processed = preprocessor.preprocess_returns(returns_df)
    
    # ========================================================================
    # STEP 3: LAGGED REGRESSIONS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: LAGGED REGRESSIONS")
    print("=" * 80)
    
    regression_engine = LaggedRegressionEngine(
        fdr_alpha=0.05,
        use_hac_se=True
    )
    
    # Run regressions for all companies
    regression_results = regression_engine.run_all_companies(
        returns_processed,
        macro_processed,
        market_factor,
        max_companies=max_companies
    )
    
    # ========================================================================
    # STEP 4: EXTRACT MACRO BETAS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: EXTRACTING MACRO BETAS")
    print("=" * 80)
    
    # Get list of base macro variables (without lag suffix)
    base_macro_vars = list(set([
        col.rsplit('_lag', 1)[0] 
        for col in macro_processed.columns 
        if '_lag' in col
    ]))
    
    print(f"\n   Base macro variables: {len(base_macro_vars)}")
    
    # Extract betas for top 10 macro variables (by average significance)
    all_betas = []
    for macro_var in base_macro_vars[:10]:  # Top 10 for demo
        beta_df = regression_engine.extract_macro_betas(regression_results, macro_var)
        all_betas.append(beta_df)
    
    if all_betas:
        combined_betas = pd.concat(all_betas, ignore_index=True)
        print(f"   ✓ Extracted {len(combined_betas)} beta estimates")
    else:
        print("   ⚠️ No betas extracted")
        combined_betas = pd.DataFrame()
    
    # ========================================================================
    # STEP 5: SECTOR AGGREGATION
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: SECTOR AGGREGATION")
    print("=" * 80)
    
    if not combined_betas.empty and sector_map:
        aggregator = SectorAggregator()
        
        sector_betas = aggregator.aggregate_to_sector(
            combined_betas,
            sector_map,
            agg_method='median'
        )
        
        print(f"   ✓ Aggregated to {len(sector_betas['sector'].unique())} sectors")
        
        # Create heatmap data
        heatmap_data = aggregator.create_sector_heatmap_data(sector_betas, top_n_vars=10)
        print(f"   ✓ Created sector heatmap: {heatmap_data.shape}")
    else:
        print("   ⚠️ Skipping sector aggregation (no data or sector map)")
        sector_betas = pd.DataFrame()
        heatmap_data = pd.DataFrame()
    
    # ========================================================================
    # STEP 6: GENERATE REPORTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: GENERATING REPORTS")
    print("=" * 80)
    
    report_gen = MacroImpactReportGenerator(output_dir="reports/macro_impact")
    
    # Company fingerprints
    print("\n   Generating company fingerprints...")
    fingerprints = []
    for ticker, results in list(regression_results.items())[:10]:  # Top 10 for demo
        fingerprint = report_gen.generate_company_fingerprint(ticker, results, top_n=5)
        fingerprints.append(fingerprint)
    
    # Save fingerprints
    report_gen.save_report(
        {'fingerprints': fingerprints},
        'company_fingerprints.json'
    )
    
    # Sector reports
    if not sector_betas.empty:
        print("\n   Generating sector reports...")
        sector_reports = []
        for sector in sector_betas['sector'].unique()[:5]:  # Top 5 for demo
            sector_report = report_gen.generate_sector_report(sector, sector_betas, top_n=5)
            sector_reports.append(sector_report)
        
        report_gen.save_report(
            {'sector_reports': sector_reports},
            'sector_macro_sensitivity.json'
        )
    
    # Save beta tables
    if not combined_betas.empty:
        report_gen.save_dataframe(combined_betas, 'company_macro_betas.csv')
    
    if not sector_betas.empty:
        report_gen.save_dataframe(sector_betas, 'sector_macro_betas.csv')
    
    if not heatmap_data.empty:
        report_gen.save_dataframe(heatmap_data, 'sector_macro_heatmap.csv')
    
    # ========================================================================
    # STEP 7: SUMMARY STATISTICS
    # ========================================================================
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    
    successful_regressions = sum(1 for r in regression_results.values() if r.get('success', False))
    
    print(f"\n📊 Data Coverage:")
    print(f"   Macro variables: {len(macro_df.columns)}")
    print(f"   Companies analyzed: {len(returns_processed.columns)}")
    print(f"   Time period: {macro_processed.index.min()} to {macro_processed.index.max()}")
    print(f"   Observations: {len(macro_processed)}")
    
    print(f"\n📐 Regression Results:")
    print(f"   Successful regressions: {successful_regressions}/{len(regression_results)}")
    
    if successful_regressions > 0:
        avg_r2 = np.mean([
            r['r_squared'] for r in regression_results.values() 
            if r.get('success', False)
        ])
        avg_significant = np.mean([
            r['n_significant'] for r in regression_results.values() 
            if r.get('success', False)
        ])
        print(f"   Average R²: {avg_r2:.3f}")
        print(f"   Average significant relationships: {avg_significant:.1f}")
    
    if not combined_betas.empty:
        print(f"\n🏭 Sector Analysis:")
        print(f"   Total beta estimates: {len(combined_betas)}")
        print(f"   Significant relationships: {combined_betas['significant'].sum()}")
        if not sector_betas.empty:
            print(f"   Sectors analyzed: {len(sector_betas['sector'].unique())}")
    
    print("\n" + "=" * 80)
    print("✅ MACRO IMPACT ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\n📁 Reports saved to: reports/macro_impact/")
    
    return {
        'regression_results': regression_results,
        'combined_betas': combined_betas,
        'sector_betas': sector_betas,
        'heatmap_data': heatmap_data
    }


if __name__ == "__main__":
    # Run demo analysis
    results = run_macro_impact_analysis(
        macro_variables=None,  # Use all available
        tickers=None,  # Use all available
        max_companies=50,  # Limit for demo
        start_date="2018-01-01"
    )
    
    print("\n🎉 Demo complete! Check reports/macro_impact/ for outputs.")
