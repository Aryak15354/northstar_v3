#!/usr/bin/env python3
"""
🧠 RUN MACRO IMPACT ANALYSIS
Production script for running macro-equity transmission analysis

This script:
1. Loads latest RBI macro data
2. Loads company returns from market data
3. Runs full macro impact analysis
4. Generates institutional reports
5. Saves results for V3 integration

Usage:
    python scripts/run_macro_impact_analysis.py
    python scripts/run_macro_impact_analysis.py --companies 100 --start-date 2020-01-01
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import pandas as pd
import numpy as np
from datetime import datetime
import json
import shutil

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


def _select_top_macros_scale_safe(
    macro_df: pd.DataFrame,
    returns_df: pd.DataFrame,
    top_n: int,
) -> tuple[list[str], pd.DataFrame]:
    """
    Select macro variables with a scale-invariant score.

    Score mixes:
    - absolute correlation vs equal-weighted return proxy (unit-invariant)
    - robust normalized activity (median abs first-diff after robust scaling)
    - coverage multiplier
    """
    if top_n <= 0:
        return [], pd.DataFrame()
    if macro_df.empty:
        return [], pd.DataFrame()
    if len(macro_df.columns) <= top_n:
        meta = pd.DataFrame({"macro_variable": list(macro_df.columns), "score": 1.0})
        return list(macro_df.columns), meta

    common = macro_df.index.intersection(returns_df.index)
    if len(common) < 20:
        cols = list(macro_df.columns)[:top_n]
        return cols, pd.DataFrame({"macro_variable": cols, "score": np.nan, "reason": "insufficient_overlap"})

    ret = returns_df.loc[common].apply(pd.to_numeric, errors="coerce")
    proxy = ret.mean(axis=1, skipna=True).rename("proxy_return")

    rows = []
    for col in macro_df.columns:
        s = pd.to_numeric(macro_df.loc[common, col], errors="coerce")
        pair = pd.concat([s.rename("x"), proxy], axis=1).dropna()
        coverage = float(pair.shape[0]) / float(max(len(common), 1))

        corr_abs = np.nan
        if len(pair) >= 26:
            corr = pair["x"].corr(pair["proxy_return"])
            if pd.notna(corr):
                corr_abs = float(abs(corr))

        clean = s.dropna()
        activity = np.nan
        if len(clean) >= 26:
            q75, q25 = np.nanpercentile(clean.values, [75, 25])
            iqr = float(q75 - q25)
            scale = iqr if np.isfinite(iqr) and iqr > 1e-9 else float(np.nanstd(clean.values))
            if not np.isfinite(scale) or scale <= 1e-9:
                scale = 1.0
            norm = (clean - float(np.nanmedian(clean.values))) / scale
            activity = float(np.nanmedian(np.abs(np.diff(norm.values)))) if len(norm) > 1 else np.nan
            if np.isfinite(activity):
                activity = float(np.clip(activity, 0.0, 3.0))

        score = 0.0
        if np.isfinite(corr_abs):
            score += 0.7 * corr_abs
        if np.isfinite(activity):
            score += 0.3 * activity
        score *= float(np.clip(coverage, 0.0, 1.0))

        rows.append(
            {
                "macro_variable": str(col),
                "score": float(score),
                "coverage": coverage,
                "abs_corr_proxy_return": corr_abs,
                "activity_score": activity,
            }
        )

    meta = pd.DataFrame(rows).sort_values("score", ascending=False)
    selected = meta["macro_variable"].head(top_n).astype(str).tolist()
    return selected, meta


def parse_args():
    parser = argparse.ArgumentParser(description='Run Macro Impact Analysis')
    parser.add_argument('--companies', type=int, default=None,
                       help='Maximum number of companies to analyze (default: all)')
    parser.add_argument('--start-date', type=str, default='2018-01-01',
                       help='Start date for analysis (YYYY-MM-DD)')
    parser.add_argument('--frequency', type=str, default='W',
                       choices=['D', 'W', 'M'],
                       help='Data frequency: D=daily, W=weekly, M=monthly')
    parser.add_argument('--top-macros', type=int, default=50,
                       help='Number of top macro variables to analyze')
    parser.add_argument('--output-dir', type=str, default='reports/macro_impact',
                       help='Output directory for reports')
    parser.add_argument(
        '--processed-output-dir',
        type=str,
        default='data/processed/macro_impact',
        help='Directory to mirror artifacts for V3 integration'
    )
    parser.add_argument(
        '--lags',
        type=str,
        default='0,1,2,4,8,12,26',
        help='Comma-separated lags for macro transmission (in periods)'
    )
    parser.add_argument(
        '--light-mode',
        action='store_true',
        help='M1-safe mode: cap dimensions, disable heavy optional steps'
    )
    parser.add_argument('--run-granger', action='store_true',
                       help='Run Granger causality tests (slower)')
    parser.add_argument('--run-rolling', action='store_true',
                       help='Run rolling beta estimation (slower)')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        lag_list = sorted({int(x.strip()) for x in str(args.lags).split(",") if x.strip() != ""})
        if not lag_list:
            raise ValueError("empty lag list")
    except Exception as e:
        print(f"\n❌ Invalid --lags argument: {e}")
        return 2

    if args.light_mode:
        if args.companies is None:
            args.companies = 120
        args.top_macros = min(int(args.top_macros), 30)
        lag_list = [l for l in lag_list if l <= 8] or [0, 1, 2, 4, 8]
        args.run_granger = False
        args.run_rolling = False
    
    print("=" * 80)
    print("🧠 MACRO IMPACT ENGINE - PRODUCTION RUN")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Start Date: {args.start_date}")
    print(f"  Frequency: {args.frequency}")
    print(f"  Max Companies: {args.companies or 'All'}")
    print(f"  Top Macros: {args.top_macros}")
    print(f"  Lags: {lag_list}")
    print(f"  Output Dir: {args.output_dir}")
    print(f"  Processed Mirror Dir: {args.processed_output_dir}")
    print(f"  Light Mode: {args.light_mode}")
    print(f"  Run Granger Tests: {args.run_granger}")
    print(f"  Run Rolling Betas: {args.run_rolling}")
    
    # ========================================================================
    # STEP 1: LOAD DATA
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: LOADING DATA")
    print("=" * 80)
    
    loader = MacroDataLoader(target_frequency=args.frequency)
    
    try:
        data = loader.load_all(start_date=args.start_date)
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        print("\nPlease ensure:")
        print("  1. RBI macro data exists at: data/macro/comprehensive_rbi_data.parquet")
        print("  2. Company returns data exists in: data/market/")
        print("  3. Sector mapping exists at: config/sector_rules.json")
        return 1
    
    macro_df = data['macro']
    returns_df = data['returns']
    market_factor = data['market']
    sector_map = data['sector_map']

    # Keep feature count in a statistically safe zone after lag expansion.
    # Conservative effective sample approximation accounts for lag burn-in and
    # transformations that reduce usable rows.
    obs_n = int(len(macro_df))
    lag_n = max(len(lag_list), 1)
    max_lag = max(lag_list) if lag_list else 0
    effective_obs = max(obs_n - (2 * max_lag) - 10, 30)
    safe_top_macros = max(5, int((effective_obs - 20) / lag_n))
    if args.top_macros > safe_top_macros:
        print(
            f"\n   ⚠️ top-macros={args.top_macros} is too high for {obs_n} observations and {lag_n} lags. "
            f"Capping to {safe_top_macros} for regression stability."
        )
        args.top_macros = safe_top_macros
    
    # Limit companies if specified
    if args.companies and len(returns_df.columns) > args.companies:
        returns_df = returns_df.iloc[:, :args.companies]
        print(f"\n   ⚠️ Limited to {args.companies} companies")
    
    # Select top macro variables by variance
    if len(macro_df.columns) > args.top_macros:
        top_macro_cols, top_macro_meta = _select_top_macros_scale_safe(
            macro_df=macro_df,
            returns_df=returns_df,
            top_n=int(args.top_macros),
        )
        if not top_macro_cols:
            macro_variance = macro_df.var().sort_values(ascending=False)
            top_macro_cols = macro_variance.head(args.top_macros).index.tolist()
            print(f"\n   ⚠️ Scale-safe selection unavailable; fell back to variance ranking")
        else:
            preview = top_macro_meta.head(5)[["macro_variable", "score"]].to_dict("records")
            print(f"\n   ✓ Scale-safe macro selection enabled (corr/activity/coverage)")
            print(f"   Top macro score preview: {preview}")
        macro_df = macro_df[top_macro_cols]
        print(f"\n   ⚠️ Selected top {args.top_macros} macro variables using scale-safe ranking")
    
    # ========================================================================
    # STEP 2: PREPROCESSING
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: PREPROCESSING")
    print("=" * 80)
    
    preprocessor = MacroPreprocessor(
        lags=lag_list,
        winsorize_pct=0.01
    )
    
    macro_processed, macro_metadata = preprocessor.preprocess_macro(macro_df)
    returns_processed = preprocessor.preprocess_returns(returns_df)
    
    # ========================================================================
    # STEP 3: LAGGED REGRESSIONS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: LAGGED REGRESSIONS")
    print("=" * 80)
    
    regression_engine = LaggedRegressionEngine(fdr_alpha=0.05, use_hac_se=True)
    
    regression_results = regression_engine.run_all_companies(
        returns_processed,
        macro_processed,
        market_factor,
        max_companies=args.companies
    )
    
    # ========================================================================
    # STEP 4: EXTRACT BETAS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: EXTRACTING MACRO BETAS")
    print("=" * 80)
    
    # Get base macro variables
    base_macro_vars = list(set([
        col.rsplit('_lag', 1)[0] 
        for col in macro_processed.columns 
        if '_lag' in col
    ]))
    
    print(f"\n   Extracting betas for {len(base_macro_vars)} macro variables...")
    
    all_betas = []
    for i, macro_var in enumerate(base_macro_vars):
        if (i + 1) % 10 == 0:
            print(f"   Progress: {i+1}/{len(base_macro_vars)}")
        
        beta_df = regression_engine.extract_macro_betas(regression_results, macro_var)
        if not beta_df.empty:
            all_betas.append(beta_df)
    
    combined_betas = pd.concat(all_betas, ignore_index=True) if all_betas else pd.DataFrame()
    print(f"\n   ✓ Extracted {len(combined_betas)} beta estimates")
    
    # ========================================================================
    # STEP 5: SECTOR AGGREGATION
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: SECTOR AGGREGATION")
    print("=" * 80)
    
    sector_betas = pd.DataFrame()
    heatmap_data = pd.DataFrame()
    
    if not combined_betas.empty and sector_map:
        aggregator = SectorAggregator()
        sector_betas = aggregator.aggregate_to_sector(combined_betas, sector_map)
        heatmap_data = aggregator.create_sector_heatmap_data(sector_betas, top_n_vars=20)
        print(f"   ✓ Aggregated to {len(sector_betas['sector'].unique())} sectors")
    
    # ========================================================================
    # STEP 6: OPTIONAL ANALYSES
    # ========================================================================
    
    granger_results = pd.DataFrame()
    if args.run_granger:
        print("\n" + "=" * 80)
        print("STEP 6A: GRANGER CAUSALITY TESTS")
        print("=" * 80)
        
        tester = GrangerCausalityTester(max_lags=12)
        
        # Test top 5 companies × top 10 macros
        test_tickers = returns_processed.columns[:5]
        test_macros = macro_df.columns[:10]
        
        granger_list = []
        for ticker in test_tickers:
            for macro_var in test_macros:
                result = tester.granger_test(returns_processed[ticker], macro_df[macro_var])
                if result['success']:
                    granger_list.append({
                        'ticker': ticker,
                        'macro_variable': macro_var,
                        'granger_causes': result['granger_causes'],
                        'best_lag': result['best_lag'],
                        'p_value': result['best_p_value']
                    })
        
        granger_results = pd.DataFrame(granger_list)
        print(f"   ✓ Completed {len(granger_results)} Granger tests")
    
    rolling_results = {}
    if args.run_rolling:
        print("\n" + "=" * 80)
        print("STEP 6B: ROLLING BETA ESTIMATION")
        print("=" * 80)
        
        estimator = RollingBetaEstimator(window_sizes=[156, 260])
        
        # Estimate for top 5 companies × top 5 macros
        test_tickers = returns_processed.columns[:5]
        test_macros = macro_df.columns[:5]
        
        for ticker in test_tickers:
            for macro_var in test_macros:
                key = f"{ticker}_{macro_var}"
                rolling_results[key] = estimator.estimate_all_windows(
                    returns_processed[ticker],
                    macro_df[macro_var]
                )
        
        print(f"   ✓ Completed rolling estimation for {len(rolling_results)} pairs")
    
    # ========================================================================
    # STEP 7: GENERATE REPORTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 7: GENERATING REPORTS")
    print("=" * 80)
    
    report_gen = MacroImpactReportGenerator(output_dir=args.output_dir)
    
    # Company fingerprints
    print("\n   Generating company fingerprints...")
    fingerprints = []
    for ticker, results in regression_results.items():
        fingerprint = report_gen.generate_company_fingerprint(ticker, results, top_n=10)
        fingerprints.append(fingerprint)
    
    report_gen.save_report({'fingerprints': fingerprints}, 'company_fingerprints.json')
    
    # Sector reports
    if not sector_betas.empty:
        print("   Generating sector reports...")
        sector_reports = []
        for sector in sector_betas['sector'].unique():
            sector_report = report_gen.generate_sector_report(sector, sector_betas, top_n=10)
            sector_reports.append(sector_report)
        
        report_gen.save_report({'sector_reports': sector_reports}, 'sector_macro_sensitivity.json')
    
    # Save data tables
    if not combined_betas.empty:
        report_gen.save_dataframe(combined_betas, 'company_macro_betas.csv')
        report_gen.output_dir.joinpath('company_macro_betas.parquet').parent.mkdir(parents=True, exist_ok=True)
        combined_betas.to_parquet(report_gen.output_dir / 'company_macro_betas.parquet', index=False)
    
    if not sector_betas.empty:
        report_gen.save_dataframe(sector_betas, 'sector_macro_betas.csv')
        report_gen.save_dataframe(heatmap_data, 'sector_macro_heatmap.csv')
        sector_betas.to_parquet(report_gen.output_dir / 'sector_macro_betas.parquet', index=False)
        if isinstance(heatmap_data, pd.DataFrame) and not heatmap_data.empty:
            heatmap_data.to_parquet(report_gen.output_dir / 'sector_macro_heatmap.parquet')
    
    if not granger_results.empty:
        report_gen.save_dataframe(granger_results, 'granger_causality_results.csv')
        granger_results.to_parquet(report_gen.output_dir / 'granger_causality_results.parquet', index=False)
    
    # Save metadata
    metadata = {
        'run_date': datetime.now().isoformat(),
        'configuration': vars(args),
        'data_coverage': {
            'macro_variables': len(macro_df.columns),
            'companies': len(returns_processed.columns),
            'start_date': str(macro_processed.index.min()),
            'end_date': str(macro_processed.index.max()),
            'observations': len(macro_processed)
        },
        'results_summary': {
            'successful_regressions': sum(1 for r in regression_results.values() if r.get('success', False)),
            'total_beta_estimates': len(combined_betas),
            'significant_relationships': int(combined_betas['significant'].sum()) if not combined_betas.empty else 0,
            'sectors_analyzed': len(sector_betas['sector'].unique()) if not sector_betas.empty else 0
        }
    }
    
    report_gen.save_report(metadata, 'analysis_metadata.json')

    # Mirror artifacts into processed dir for dashboard/system consumption.
    processed_dir = Path(args.processed_output_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    for src in Path(args.output_dir).glob("*"):
        if src.is_file():
            try:
                shutil.copy2(src, processed_dir / src.name)
            except Exception as e:
                print(f"   ⚠️ Could not mirror {src.name}: {e}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ MACRO IMPACT ANALYSIS COMPLETE")
    print("=" * 80)
    
    print(f"\n📊 Results Summary:")
    print(f"   Companies analyzed: {metadata['data_coverage']['companies']}")
    print(f"   Macro variables: {metadata['data_coverage']['macro_variables']}")
    print(f"   Successful regressions: {metadata['results_summary']['successful_regressions']}")
    print(f"   Total beta estimates: {metadata['results_summary']['total_beta_estimates']}")
    print(f"   Significant relationships: {metadata['results_summary']['significant_relationships']}")
    
    print(f"\n📁 Reports saved to: {args.output_dir}/")
    print(f"📁 Mirrored for V3 to: {processed_dir}/")
    print(f"   - company_fingerprints.json")
    print(f"   - sector_macro_sensitivity.json")
    print(f"   - company_macro_betas.csv")
    print(f"   - sector_macro_betas.csv")
    print(f"   - analysis_metadata.json")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
