#!/usr/bin/env python3
"""
COMPREHENSIVE GAPS 1-5 INTEGRATION AUDIT

This script performs end-to-end testing of all components from Gaps 1-5
to ensure proper integration and identify any cascading issues.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
import sys

print('=' * 80)
print('COMPREHENSIVE GAPS 1-5 INTEGRATION AUDIT')
print('=' * 80)
print(f'Audit Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

issues = []
warnings = []
passed = []

# ============================================================================
# GAP 1: INGESTION LAYER
# ============================================================================
print('=' * 80)
print('GAP 1: INGESTION LAYER')
print('=' * 80)

try:
    from src.ingestion import IngestionRegistry
    
    registry = IngestionRegistry()
    as_of = datetime.now()
    
    # Test all loaders
    print('\n1. Testing Data Loaders...')
    
    # Market data
    try:
        prices = registry.market.load(as_of, tickers=['RELIANCE'])
        if len(prices) > 0:
            passed.append('GAP1: Market loader working')
            print(f'   ✓ Market: {len(prices)} rows')
        else:
            warnings.append('GAP1: Market loader returned 0 rows')
            print('   ⚠ Market: 0 rows')
    except Exception as e:
        issues.append(f'GAP1: Market loader failed: {e}')
        print(f'   ✗ Market: {e}')
    
    # Fundamentals
    try:
        fundamentals = registry.fundamentals.load_financials(as_of, tickers=['RELIANCE'])
        passed.append('GAP1: Fundamental loader working')
        print(f'   ✓ Fundamentals: Loaded')
    except Exception as e:
        issues.append(f'GAP1: Fundamental loader failed: {e}')
        print(f'   ✗ Fundamentals: {e}')
    
    # Macro
    try:
        macro = registry.macro.load_rbi_data(as_of)
        if len(macro) > 0:
            passed.append('GAP1: Macro loader working')
            print(f'   ✓ Macro: {len(macro)} indicators')
        else:
            warnings.append('GAP1: Macro loader returned 0 indicators')
            print('   ⚠ Macro: 0 indicators')
    except Exception as e:
        issues.append(f'GAP1: Macro loader failed: {e}')
        print(f'   ✗ Macro: {e}')
    
    # GST
    try:
        gst = registry.alternative.load_gst(as_of)
        if len(gst) > 0:
            passed.append('GAP1: GST loader working')
            print(f'   ✓ GST: {len(gst)} months')
        else:
            warnings.append('GAP1: GST loader returned 0 rows')
            print('   ⚠ GST: 0 rows')
    except Exception as e:
        issues.append(f'GAP1: GST loader failed: {e}')
        print(f'   ✗ GST: {e}')
    
    # Power
    try:
        power = registry.alternative.load_power_consumption(as_of)
        if len(power) > 0:
            passed.append('GAP1: Power loader working')
            print(f'   ✓ Power: {len(power)} days')
        else:
            warnings.append('GAP1: Power loader returned 0 rows')
            print('   ⚠ Power: 0 rows')
    except Exception as e:
        issues.append(f'GAP1: Power loader failed: {e}')
        print(f'   ✗ Power: {e}')
    
    # Credit Ratings
    try:
        ratings = registry.alternative.load_credit_ratings(as_of)
        if len(ratings) > 0:
            passed.append('GAP1: Credit ratings loader working')
            print(f'   ✓ Credit Ratings: {len(ratings)} actions')
        else:
            warnings.append('GAP1: Credit ratings loader returned 0 rows')
            print('   ⚠ Credit Ratings: 0 actions')
    except Exception as e:
        issues.append(f'GAP1: Credit ratings loader failed: {e}')
        print(f'   ✗ Credit Ratings: {e}')
    
    # Bulk Deals
    try:
        bulk = registry.alternative.load_bulk_deals(as_of, lookback_days=90)
        if len(bulk) > 0:
            passed.append('GAP1: Bulk deals loader working')
            print(f'   ✓ Bulk Deals: {len(bulk)} tickers')
        else:
            warnings.append('GAP1: Bulk deals loader returned 0 tickers')
            print('   ⚠ Bulk Deals: 0 tickers')
    except Exception as e:
        issues.append(f'GAP1: Bulk deals loader failed: {e}')
        print(f'   ✗ Bulk Deals: {e}')
    
    # Promoter Pledges
    try:
        pledges = registry.alternative.load_promoter_pledges(as_of)
        if len(pledges) > 0:
            passed.append('GAP1: Promoter pledges loader working')
            print(f'   ✓ Promoter Pledges: {len(pledges)} records')
        else:
            warnings.append('GAP1: Promoter pledges loader returned 0 records')
            print('   ⚠ Promoter Pledges: 0 records')
    except Exception as e:
        issues.append(f'GAP1: Promoter pledges loader failed: {e}')
        print(f'   ✗ Promoter Pledges: {e}')
    
    # Sentiment
    try:
        sentiment = registry.sentiment.load_company_sentiment(as_of, lookback_days=7)
        if len(sentiment) > 0:
            passed.append('GAP1: Sentiment loader working')
            print(f'   ✓ Sentiment: {len(sentiment)} records')
        else:
            warnings.append('GAP1: Sentiment loader returned 0 records')
            print('   ⚠ Sentiment: 0 records')
    except Exception as e:
        issues.append(f'GAP1: Sentiment loader failed: {e}')
        print(f'   ✗ Sentiment: {e}')
    
    # Options
    try:
        options = registry.options.load_historical_chains(as_of)
        passed.append('GAP1: Options loader working')
        print(f'   ✓ Options: Loaded')
    except Exception as e:
        issues.append(f'GAP1: Options loader failed: {e}')
        print(f'   ✗ Options: {e}')
    
except Exception as e:
    issues.append(f'GAP1: IngestionRegistry failed: {e}')
    print(f'✗ IngestionRegistry: {e}')

# ============================================================================
# GAP 2: SENTIMENT SYSTEM
# ============================================================================
print('\n' + '=' * 80)
print('GAP 2: SENTIMENT SYSTEM')
print('=' * 80)

try:
    from src.sentiment.sentiment_state import SentimentState, SentimentRegime
    from src.sentiment.sentiment_feature_block import SentimentFeatureBlock
    from src.sentiment.sentiment_regime import SentimentRegimeClassifier
    
    print('\n1. Testing Sentiment Components...')
    
    # SentimentState
    try:
        state = SentimentState()
        passed.append('GAP2: SentimentState instantiates')
        print(f'   ✓ SentimentState: {type(state).__name__}')
    except Exception as e:
        issues.append(f'GAP2: SentimentState failed: {e}')
        print(f'   ✗ SentimentState: {e}')
    
    # SentimentFeatureBlock
    try:
        from src.ingestion import IngestionRegistry
        registry = IngestionRegistry()
        block = SentimentFeatureBlock(registry, {})
        features = block.get_feature_names()
        if len(features) == 14:
            passed.append('GAP2: SentimentFeatureBlock working (14 features)')
            print(f'   ✓ SentimentFeatureBlock: 14 features')
        else:
            warnings.append(f'GAP2: SentimentFeatureBlock has {len(features)} features, expected 14')
            print(f'   ⚠ SentimentFeatureBlock: {len(features)} features')
    except Exception as e:
        issues.append(f'GAP2: SentimentFeatureBlock failed: {e}')
        print(f'   ✗ SentimentFeatureBlock: {e}')
    
    # SentimentRegimeClassifier
    try:
        classifier = SentimentRegimeClassifier({})
        passed.append('GAP2: SentimentRegimeClassifier instantiates')
        print(f'   ✓ SentimentRegimeClassifier: Ready')
    except Exception as e:
        issues.append(f'GAP2: SentimentRegimeClassifier failed: {e}')
        print(f'   ✗ SentimentRegimeClassifier: {e}')
    
    # Check sentiment data freshness
    try:
        sentiment_path = Path('data/sentiment/v3/company_sentiment_trends.parquet')
        if sentiment_path.exists():
            df = pd.read_parquet(sentiment_path)
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            latest = df['date'].max()
            days_ago = (datetime.now() - latest).days
            if days_ago <= 7:
                passed.append(f'GAP2: Sentiment data fresh ({days_ago} days)')
                print(f'   ✓ Sentiment Data: {days_ago} days stale')
            else:
                warnings.append(f'GAP2: Sentiment data is {days_ago} days stale')
                print(f'   ⚠ Sentiment Data: {days_ago} days stale')
        else:
            issues.append('GAP2: Sentiment data file not found')
            print(f'   ✗ Sentiment Data: File not found')
    except Exception as e:
        issues.append(f'GAP2: Sentiment data check failed: {e}')
        print(f'   ✗ Sentiment Data: {e}')
    
except Exception as e:
    issues.append(f'GAP2: Import failed: {e}')
    print(f'✗ GAP2 imports: {e}')

# ============================================================================
# GAP 3: ALTERNATIVE DATA INTEGRATION
# ============================================================================
print('\n' + '=' * 80)
print('GAP 3: ALTERNATIVE DATA INTEGRATION')
print('=' * 80)

try:
    from src.alternative_data.alternative_state import AlternativeDataState
    from src.alternative_data.alternative_feature_block import AlternativeFeatureBlock
    
    print('\n1. Testing Alternative Data Components...')
    
    # AlternativeDataState
    try:
        state = AlternativeDataState()
        passed.append('GAP3: AlternativeDataState instantiates')
        print(f'   ✓ AlternativeDataState: {type(state).__name__}')
    except Exception as e:
        issues.append(f'GAP3: AlternativeDataState failed: {e}')
        print(f'   ✗ AlternativeDataState: {e}')
    
    # AlternativeFeatureBlock
    try:
        from src.ingestion import IngestionRegistry
        registry = IngestionRegistry()
        block = AlternativeFeatureBlock(registry, {})
        features = block.get_company_feature_names()
        if len(features) >= 15:
            passed.append(f'GAP3: AlternativeFeatureBlock working ({len(features)} features)')
            print(f'   ✓ AlternativeFeatureBlock: {len(features)} features')
        else:
            warnings.append(f'GAP3: AlternativeFeatureBlock has {len(features)} features, expected >=15')
            print(f'   ⚠ AlternativeFeatureBlock: {len(features)} features')
    except Exception as e:
        issues.append(f'GAP3: AlternativeFeatureBlock failed: {e}')
        print(f'   ✗ AlternativeFeatureBlock: {e}')
    
    # Check alternative data files
    print('\n2. Checking Alternative Data Files...')
    alt_files = {
        'GST': 'data/processed/gst_monthly.parquet',
        'Power': 'data/processed/macro/cea_power_daily.parquet',
        'Bulk Deals': 'data/processed/alternative/bulk_deals_nse_all.parquet',
        'Credit Ratings': 'data/processed/alternative/credit_ratings_nse_all.csv',
    }
    
    for name, path in alt_files.items():
        p = Path(path)
        if p.exists():
            size_kb = p.stat().st_size / 1024
            passed.append(f'GAP3: {name} file exists ({size_kb:.1f} KB)')
            print(f'   ✓ {name}: {size_kb:.1f} KB')
        else:
            issues.append(f'GAP3: {name} file missing')
            print(f'   ✗ {name}: Missing')
    
except Exception as e:
    issues.append(f'GAP3: Import failed: {e}')
    print(f'✗ GAP3 imports: {e}')

# ============================================================================
# GAP 4: ALPHA OS
# ============================================================================
print('\n' + '=' * 80)
print('GAP 4: ALPHA OS')
print('=' * 80)

try:
    from src.alpha_os.strategy_registry import StrategyRegistry
    from src.alpha_os.alpha_os_state import AlphaOSState
    
    print('\n1. Testing Alpha OS Components...')
    
    # AlphaOSState
    try:
        state = AlphaOSState()
        passed.append('GAP4: AlphaOSState instantiates')
        print(f'   ✓ AlphaOSState: {type(state).__name__}')
    except Exception as e:
        issues.append(f'GAP4: AlphaOSState failed: {e}')
        print(f'   ✗ AlphaOSState: {e}')
    
    # StrategyRegistry
    try:
        registry = StrategyRegistry()
        num_strategies = len(registry.strategies)
        if num_strategies > 0:
            passed.append(f'GAP4: StrategyRegistry working ({num_strategies} strategies)')
            print(f'   ✓ StrategyRegistry: {num_strategies} strategies')
        else:
            warnings.append('GAP4: StrategyRegistry has 0 strategies')
            print(f'   ⚠ StrategyRegistry: 0 strategies')
    except Exception as e:
        issues.append(f'GAP4: StrategyRegistry failed: {e}')
        print(f'   ✗ StrategyRegistry: {e}')
    
    # Check model registry files
    print('\n2. Checking Model Registry Files...')
    model_files = {
        'Registry': 'data/model_registry/registry.json',
        'Production': 'data/model_registry/production.json',
        'Strategy Registry': 'data/model_registry/strategy_registry.json',
    }
    
    for name, path in model_files.items():
        p = Path(path)
        if p.exists():
            size_kb = p.stat().st_size / 1024
            passed.append(f'GAP4: {name} file exists ({size_kb:.1f} KB)')
            print(f'   ✓ {name}: {size_kb:.1f} KB')
        else:
            issues.append(f'GAP4: {name} file missing')
            print(f'   ✗ {name}: Missing')
    
except Exception as e:
    issues.append(f'GAP4: Import failed: {e}')
    print(f'✗ GAP4 imports: {e}')

# ============================================================================
# GAP 5: P&L LEDGER
# ============================================================================
print('\n' + '=' * 80)
print('GAP 5: P&L LEDGER')
print('=' * 80)

try:
    from src.pnl.ledger import UnifiedPnLLedger
    from src.pnl.nav_calculator import NAVCalculator
    from src.pnl.pnl_state import PnLState
    
    print('\n1. Testing P&L Components...')
    
    # PnLState
    try:
        state = PnLState()
        passed.append('GAP5: PnLState instantiates')
        print(f'   ✓ PnLState: {type(state).__name__} ({len(state.__dataclass_fields__)} fields)')
    except Exception as e:
        issues.append(f'GAP5: PnLState failed: {e}')
        print(f'   ✗ PnLState: {e}')
    
    # UnifiedPnLLedger
    try:
        ledger = UnifiedPnLLedger()
        num_entries = len(ledger.ledger_df)
        if num_entries > 0:
            passed.append(f'GAP5: UnifiedPnLLedger working ({num_entries} entries)')
            print(f'   ✓ UnifiedPnLLedger: {num_entries} entries')
        else:
            warnings.append('GAP5: UnifiedPnLLedger has 0 entries')
            print(f'   ⚠ UnifiedPnLLedger: 0 entries')
    except Exception as e:
        issues.append(f'GAP5: UnifiedPnLLedger failed: {e}')
        print(f'   ✗ UnifiedPnLLedger: {e}')
    
    # NAV Calculator
    try:
        ledger = UnifiedPnLLedger()
        nav_calc = NAVCalculator(ledger, {})
        nav_data = nav_calc.compute_daily_nav(
            start_date=datetime(2025, 12, 31),
            end_date=datetime.now()
        )
        if len(nav_data) > 0 and 'nav_combined' in nav_data.columns:
            current_nav = nav_data['nav_combined'].iloc[-1]
            starting_nav = nav_data['nav_combined'].iloc[0]
            return_pct = ((current_nav / starting_nav) - 1) * 100
            
            # Verify NAV is correct (should be ~₹10,045,877)
            if 10000000 <= current_nav <= 11000000:
                passed.append(f'GAP5: NAVCalculator working (NAV: ₹{current_nav:,.0f}, Return: {return_pct:.2f}%)')
                print(f'   ✓ NAVCalculator: ₹{current_nav:,.0f} ({return_pct:.2f}%)')
            else:
                issues.append(f'GAP5: NAV seems incorrect: ₹{current_nav:,.0f}')
                print(f'   ✗ NAVCalculator: ₹{current_nav:,.0f} (seems wrong)')
        else:
            issues.append('GAP5: NAVCalculator returned invalid data')
            print(f'   ✗ NAVCalculator: Invalid data')
    except Exception as e:
        issues.append(f'GAP5: NAVCalculator failed: {e}')
        print(f'   ✗ NAVCalculator: {e}')
    
    # Check P&L data files
    print('\n2. Checking P&L Data Files...')
    pnl_files = {
        'Master Ledger': 'data/pnl/master_ledger.parquet',
        'NAV History': 'data/pnl/nav_history.parquet',
        'Reconciliation Log': 'data/pnl/reconciliation_log.parquet',
        'Execution Quality': 'data/pnl/execution_quality.parquet',
        'Rebuild Report': 'data/pnl/rebuild_report.json',
    }
    
    for name, path in pnl_files.items():
        p = Path(path)
        if p.exists():
            size_kb = p.stat().st_size / 1024
            passed.append(f'GAP5: {name} file exists ({size_kb:.1f} KB)')
            print(f'   ✓ {name}: {size_kb:.1f} KB')
        else:
            issues.append(f'GAP5: {name} file missing')
            print(f'   ✗ {name}: Missing')
    
except Exception as e:
    issues.append(f'GAP5: Import failed: {e}')
    print(f'✗ GAP5 imports: {e}')

# ============================================================================
# UNIFIED STATE INTEGRATION
# ============================================================================
print('\n' + '=' * 80)
print('UNIFIED STATE INTEGRATION')
print('=' * 80)

try:
    from src.core.state import UnifiedState
    
    print('\n1. Testing UnifiedState...')
    
    try:
        state = UnifiedState()
        passed.append('UnifiedState: Instantiates correctly')
        print(f'   ✓ UnifiedState: Created')
        
        # Check all state components
        components = {
            'sentiment': 'SentimentState',
            'alternative_data': 'AlternativeDataState',
            'alpha_os': 'AlphaOSState',
            'pnl_state': 'PnLState',
        }
        
        for attr, expected_type in components.items():
            if hasattr(state, attr):
                actual_type = type(getattr(state, attr)).__name__
                passed.append(f'UnifiedState: {attr} present ({actual_type})')
                print(f'   ✓ {attr}: {actual_type}')
            else:
                issues.append(f'UnifiedState: Missing {attr}')
                print(f'   ✗ {attr}: Missing')
    except Exception as e:
        issues.append(f'UnifiedState: Failed to instantiate: {e}')
        print(f'   ✗ UnifiedState: {e}')
    
except Exception as e:
    issues.append(f'UnifiedState: Import failed: {e}')
    print(f'✗ UnifiedState imports: {e}')

# ============================================================================
# SUMMARY
# ============================================================================
print('\n' + '=' * 80)
print('AUDIT SUMMARY')
print('=' * 80)

print(f'\n✓ PASSED: {len(passed)}')
print(f'⚠ WARNINGS: {len(warnings)}')
print(f'✗ ISSUES: {len(issues)}')

if warnings:
    print(f'\nWARNINGS ({len(warnings)}):')
    for w in warnings:
        print(f'  ⚠ {w}')

if issues:
    print(f'\nISSUES ({len(issues)}):')
    for i in issues:
        print(f'  ✗ {i}')
    print(f'\n❌ AUDIT FAILED - {len(issues)} issues found')
    sys.exit(1)
else:
    print(f'\n✅ AUDIT PASSED - All Gaps 1-5 working correctly!')
    sys.exit(0)
