# HARDCODED REFERENCES MIGRATION REPORT
============================================================

## SUMMARY
- Total hardcoded references found: 124
- Files affected: 17
- Reference types: path, market

## REFERENCES BY TYPE

### PATH (53 references)
- `data/validation/`: 23 occurrences
- `data/processed/`: 14 occurrences
- `data/simulation/`: 8 occurrences
- `data/raw/`: 2 occurrences
- `reports/`: 2 occurrences
- `data/integrity/`: 2 occurrences
- `data/execution/`: 1 occurrences
- `logs/`: 1 occurrences

### MARKET (71 references)
- `.NS`: 40 occurrences
- `₹`: 18 occurrences
- `09:30`: 5 occurrences
- `NSE`: 4 occurrences
- `$`: 3 occurrences
- `NIFTY`: 1 occurrences

## FILES WITH MOST REFERENCES

### src/validation/universe_manager.py (38 references)

**Line 58:**
- `data/raw/` (path)
  - Suggestion: Use get_data_path("raw", filename)
  - Code: `'price_data_dir': 'data/raw/prices_daily_extended'...`

**Line 66:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `'min_market_cap': 10_000_000,       # ₹1 crore minimum market cap (reduced)...`

**Line 67:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `'min_adv_60d': 100_000,             # ₹1 lakh minimum 60-day ADV (reduced)...`

**Line 94:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `if not symbol.endswith('.NS'):...`

**Line 95:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `symbol = f"{symbol}.NS"...`

**Line 117:**
- `NSE` (market)
  - Suggestion: Use market_config.data_sources.primary_provider
  - Code: `print(f"   ⚠️ Official NSE delisting data not found at {official_delisting_path}...`

**Line 139:**
- `NSE` (market)
  - Suggestion: Use market_config.data_sources.primary_provider
  - Code: `print(f"   📊 Loaded {len(delisting_entries)} official NSE delisting records")...`

**Line 156:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `{'symbol': 'UNITECH.NS', 'delisting_date': '2017-12-28', 'reason': 'financial_di...`

**Line 158:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `{'symbol': 'SUZLON.NS', 'delisting_date': '2019-04-30', 'reason': 'financial_dis...`

**Line 162:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `{'symbol': 'CAIRN.NS', 'delisting_date': '2011-08-21', 'reason': 'takeover',...`

### src/validation/reality_check_engine.py (19 references)

**Line 77:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'validation_results': 'data/validation/reality_check_results.json',...`

**Line 78:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'constraint_history': 'data/validation/constraint_history.parquet',...`

**Line 79:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'failure_analysis': 'data/validation/failure_analysis.json',...`

**Line 80:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'crisis_periods': 'data/validation/crisis_periods.json',...`

**Line 81:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'regime_analysis': 'data/validation/regime_analysis.parquet'...`

**Line 256:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'SAMPLE.NS', 1000, avg_trade_size / 1000,...`

**Line 849:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'delisted_stocks': ['BHARTIARTL.NS', 'IDEA.NS'],...`
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'delisted_stocks': ['BHARTIARTL.NS', 'IDEA.NS'],...`

**Line 864:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'RELIANCE.NS': 40000000,...`

**Line 865:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'TCS.NS': 35000000,...`

**Line 866:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'INFY.NS': 30000000,...`

### src/validation/enhanced_portfolio_simulator.py (10 references)

**Line 59:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'daily_metrics': 'data/simulation/daily_portfolio_metrics.parquet',...`

**Line 60:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'regime_performance': 'data/simulation/regime_performance_tracking.parquet',...`

**Line 61:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'drawdown_analysis': 'data/simulation/drawdown_analysis.parquet',...`

**Line 62:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'specialist_attribution': 'data/simulation/specialist_attribution.parquet',...`

**Line 63:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'risk_events': 'data/simulation/risk_events.parquet',...`

**Line 64:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'audit_trail': 'data/simulation/complete_audit_trail.parquet',...`

**Line 65:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `'simulation_summary': 'data/simulation/simulation_summary.json'...`

**Line 320:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `print(f"💰 Initial Capital: ₹{self.fund_params['initial_capital']:,.0f}")...`

**Line 390:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `print(f"   📊 Portfolio Value: ₹{portfolio_value:,.0f}")...`

**Line 671:**
- `data/simulation/` (path)
  - Suggestion: Use get_data_path("simulation", filename)
  - Code: `print(f"✅ Saved complete tracking data to data/simulation/")...`

### src/validation/production_readiness_certificate.py (9 references)

**Line 38:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'certificate': 'data/validation/NORTHSTAR_PRODUCTION_CERTIFICATE.json',...`

**Line 39:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'certificate_report': 'data/validation/NORTHSTAR_PRODUCTION_REPORT.md',...`

**Line 40:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'hardening_report': 'data/validation/production_hardening_report.json',...`

**Line 41:**
- `data/execution/` (path)
  - Suggestion: Use get_data_path("execution", filename)
  - Code: `'shadow_fund_report': 'data/execution/shadow_fund_report.json',...`

**Line 42:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'deduplication_log': 'data/validation/strategy_deduplication.json'...`

**Line 181:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `print(f"      Portfolio value: ₹{portfolio_value:,.0f}")...`

**Line 184:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `return True, f"Shadow fund operational with ₹{portfolio_value:,.0f} portfolio"...`

**Line 265:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `1. Begin with small capital allocation (₹10-50 lakhs)...`

**Line 348:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `"Begin with small capital allocation (₹10-50 lakhs)",...`

### src/validation/reality_check_engine_backup.py (8 references)

**Line 77:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'validation_results': 'data/validation/reality_check_results.json',...`

**Line 78:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'constraint_history': 'data/validation/constraint_history.parquet',...`

**Line 79:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'failure_analysis': 'data/validation/failure_analysis.json',...`

**Line 80:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'crisis_periods': 'data/validation/crisis_periods.json',...`

**Line 81:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'regime_analysis': 'data/validation/regime_analysis.parquet'...`

**Line 206:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `shares=int(avg_trade_size / 1000),  # Assume ₹1000 per share...`

**Line 499:**
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'delisted_stocks': ['BHARTIARTL.NS', 'IDEA.NS'],...`
- `.NS` (market)
  - Suggestion: Use market_config.data_sources.format_symbol()
  - Code: `'delisted_stocks': ['BHARTIARTL.NS', 'IDEA.NS'],...`

### src/validation/enhanced_walk_forward_engine.py (6 references)

**Line 172:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'simulation_results': 'data/validation/enhanced_simulation_results',...`

**Line 173:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'simulation_states': 'data/validation/simulation_states',...`

**Line 174:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'simulation_logs': 'data/validation/simulation_logs',...`

**Line 175:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'benchmark_data': 'data/validation/benchmark_data'...`

**Line 227:**
- `$` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `self.logger.info(f"Initial Capital: ${initial_capital:,.0f}")...`

**Line 540:**
- `$` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `print(f"💰 Initial Capital: ${initial_capital:,.0f}")...`

### src/validation/production_hardening.py (5 references)

**Line 41:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'hardening_report': 'data/validation/production_hardening_report.json',...`

**Line 42:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'readiness_certificate': 'data/validation/production_readiness_certificate.json'...`

**Line 198:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `perf_file = 'data/processed/performance/master.parquet'...`

**Line 203:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `backtest_dir = 'data/processed/backtests'...`

**Line 234:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `beliefs_file = 'data/processed/strategy_beliefs.parquet'...`

### src/validation/data_integrity.py (5 references)

**Line 41:**
- `data/integrity/` (path)
  - Suggestion: Use get_data_path("integrity", filename)
  - Code: `'release_calendar': 'data/integrity/data_release_calendar.parquet',...`

**Line 42:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'scores': 'data/processed/scores.parquet',...`

**Line 43:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'prices': 'data/processed/prices.parquet',...`

**Line 44:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'market_state': 'data/processed/market_state.parquet',...`

**Line 45:**
- `data/integrity/` (path)
  - Suggestion: Use get_data_path("integrity", filename)
  - Code: `'integrity_log': 'data/integrity/integrity_violations.parquet'...`

### src/validation/walk_forward_engine.py (5 references)

**Line 42:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'performance_master': 'data/processed/performance/master.parquet',...`

**Line 43:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'strategy_beliefs': 'data/processed/strategy_beliefs.parquet',...`

**Line 44:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'strategy_regret': 'data/processed/strategy_regret.parquet',...`

**Line 45:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'walk_forward_results': 'data/validation/walk_forward_results.parquet',...`

**Line 46:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'temporal_splits': 'data/validation/temporal_splits.json'...`

### src/validation/strategy_deduplication.py (5 references)

**Line 38:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'backtests': 'data/processed/backtests',...`

**Line 39:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `'strategy_portfolios': 'data/processed/strategy_portfolios',...`

**Line 40:**
- `data/validation/` (path)
  - Suggestion: Use get_data_path("validation", filename)
  - Code: `'deduplication_log': 'data/validation/strategy_deduplication.json'...`

**Line 208:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `beliefs_file = 'data/processed/strategy_beliefs.parquet'...`

**Line 217:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `regret_file = 'data/processed/strategy_regret.parquet'...`

### src/automation/northstar_scheduler.py (5 references)

**Line 205:**
- `09:30` (market)
  - Suggestion: Use market_config.trading_hours
  - Code: `schedule.every().monday.at("09:30").do(self.daily_check)...`

**Line 206:**
- `09:30` (market)
  - Suggestion: Use market_config.trading_hours
  - Code: `schedule.every().tuesday.at("09:30").do(self.daily_check)...`

**Line 207:**
- `09:30` (market)
  - Suggestion: Use market_config.trading_hours
  - Code: `schedule.every().wednesday.at("09:30").do(self.daily_check)...`

**Line 208:**
- `09:30` (market)
  - Suggestion: Use market_config.trading_hours
  - Code: `schedule.every().thursday.at("09:30").do(self.daily_check)...`

**Line 209:**
- `09:30` (market)
  - Suggestion: Use market_config.trading_hours
  - Code: `schedule.every().friday.at("09:30").do(self.daily_check)...`

### src/validation/performance_benchmarking_system.py (2 references)

**Line 150:**
- `NSE` (market)
  - Suggestion: Use market_config.data_sources.primary_provider
  - Code: `'description': 'NSE Nifty 50 Index',...`

**Line 156:**
- `NSE` (market)
  - Suggestion: Use market_config.data_sources.primary_provider
  - Code: `'description': 'NSE Nifty 500 Index',...`

### src/automation/snapshot_scheduler.py (2 references)

**Line 23:**
- `logs/` (path)
  - Suggestion: Use get_log_path("system", filename)
  - Code: `logging.FileHandler('data/logs/snapshot_scheduler.log'),...`

**Line 70:**
- `data/processed/` (path)
  - Suggestion: Use get_data_path("processed", filename)
  - Code: `market_state_path = 'data/processed/market_state.parquet'...`

### src/preprocessing/macro_cleaner.py (2 references)

**Line 210:**
- `₹` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `clean_name = clean_name.replace('%', 'pct').replace('₹', 'inr').replace('$', 'us...`
- `$` (market)
  - Suggestion: Use market_config.currency.currency_symbol
  - Code: `clean_name = clean_name.replace('%', 'pct').replace('₹', 'inr').replace('$', 'us...`

### src/validation/final_checkpoint_validation.py (1 references)

**Line 766:**
- `reports/` (path)
  - Suggestion: Use get_report_path("system", filename)
  - Code: `report_path = "reports/FINAL_CHECKPOINT_VALIDATION_REPORT.md"...`

### src/validation/final_system_validation_certification.py (1 references)

**Line 398:**
- `reports/` (path)
  - Suggestion: Use get_report_path("system", filename)
  - Code: `report_path = "reports/FINAL_SYSTEM_VALIDATION_CERTIFICATION_REPORT.md"...`

### src/preprocessing/market_internals.py (1 references)

**Line 35:**
- `NIFTY` (market)
  - Suggestion: Use market_config.benchmark_indices
  - Code: `if name == 'NIFTY':...`

## MIGRATION RECOMMENDATIONS

### 1. Market Configuration Migration
```python
from src.cohesion.market_configuration import get_active_market_config

# Replace hardcoded market values
market_config = get_active_market_config()
currency = market_config.currency.base_currency  # Instead of 'INR' or 'USD'
symbol_suffix = market_config.data_sources.symbol_suffix  # Instead of '.NS'
trading_hours = market_config.trading_hours  # Instead of hardcoded times
```

### 2. Path Configuration Migration
```python
from src.cohesion.path_configuration import get_data_path, get_report_path

# Replace hardcoded paths
validation_path = get_data_path('validation', 'report.json')  # Instead of 'data/validation/report.json'
report_path = get_report_path('system', 'summary.md')  # Instead of 'reports/summary.md'
```

### 3. Currency Formatting Migration
```python
# Replace hardcoded currency formatting
formatted_amount = market_config.currency.format_amount(1000000)  # Instead of f'₹{amount:,.2f}'
```
