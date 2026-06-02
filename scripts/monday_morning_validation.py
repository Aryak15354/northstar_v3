#!/usr/bin/env python3
"""
Monday Morning Validation Script

Run this before market open to ensure everything is ready.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("MONDAY MORNING VALIDATION")
print("=" * 80)
print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

validation_results = []

def check(name, condition, details=""):
    """Helper to track validation results"""
    status = "✅ PASS" if condition else "❌ FAIL"
    validation_results.append((name, condition))
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")
    return condition

# 1. Check Upstox Token
print("\n1. UPSTOX TOKEN")
print("-" * 80)
try:
    env_file = Path('.env.options')
    if env_file.exists():
        with open(env_file) as f:
            content = f.read()
            has_token = 'UPSTOX_ACCESS_TOKEN=' in content
            token_line = [l for l in content.split('\n') if 'UPSTOX_ACCESS_TOKEN=' in l]
            if token_line:
                token = token_line[0].split('=')[1].strip()
                token_length = len(token)
                check("Token exists", has_token, f"Length: {token_length} characters")
            else:
                check("Token exists", False, "Token not found in .env.options")
    else:
        check("Token file exists", False, ".env.options not found")
except Exception as e:
    check("Token check", False, str(e))

# 2. Check Critical Data Files
print("\n2. CRITICAL DATA FILES")
print("-" * 80)

critical_files = {
    'Options Data': 'data/options/complete/nifty_all_options_latest.parquet',
    'Portfolio Greeks': 'data/processed/runtime/portfolio_risk_greeks.parquet',
    'Portfolio Positions': 'data/processed/runtime/portfolio_positions_current.parquet',
    'Ledger Events': 'data/processed/runtime/portfolio_ledger_events.parquet',
    'Sentiment Data': 'data/processed/sentiment/daily_sentiment_aggregated.parquet',
    'Power Data': 'data/processed/macro/cea_power_daily.parquet',
    'Benchmark': 'data/processed/benchmark/nifty50.parquet',
}

for name, path in critical_files.items():
    file_path = Path(path)
    if file_path.exists():
        try:
            df = pd.read_parquet(file_path)
            check(name, True, f"{len(df)} records")
        except:
            check(name, False, "File exists but cannot be read")
    else:
        check(name, False, "File not found")

# 3. Check System Components
print("\n3. SYSTEM COMPONENTS")
print("-" * 80)

components = [
    ('PositionManager', 'src.options.position_manager', 'PositionManager'),
    ('ModeController', 'src.options.mode_controller', 'ModeController'),
    ('GreeksAggregator', 'src.volatility.greeks_aggregator', 'GreeksAggregator'),
    ('StrategyGenerator', 'src.volatility.strategy_generator', 'StrategyGenerator'),
    ('UnifiedRiskAuthority', 'src.volatility.risk_authority', 'UnifiedRiskAuthority'),
    ('OptionsStateBridge', 'src.core.state_bridges.options_bridge', 'OptionsStateBridge'),
    ('ShadowStateBridge', 'src.core.state_bridges.shadow_bridge', 'ShadowStateBridge'),
    ('ValuationStateBridge', 'src.core.state_bridges.valuation_bridge', 'ValuationStateBridge'),
    ('RuntimeStateBridge', 'src.core.state_bridges.runtime_bridge', 'RuntimeStateBridge'),
    ('DashboardDataContract', 'src.dashboard.data_contract', 'DashboardDataContract'),
]

for name, module, cls in components:
    try:
        exec(f"from {module} import {cls}")
        check(name, True, "Imported successfully")
    except Exception as e:
        check(name, False, str(e))

# 4. Check Configuration Files
print("\n4. CONFIGURATION FILES")
print("-" * 80)

config_files = {
    'Options Config': '.env.options',
    'Dashboard Config': 'config/dashboard_config.yaml',
    'Sentiment Config': 'config/sentiment_config.yaml',
    'Governor Config': 'config/portfolio_governor_config.yaml',
    'Ingestion Config': 'config/ingestion_config.yaml',
}

for name, path in config_files.items():
    check(name, Path(path).exists(), path)

# 5. Check Live System Scripts
print("\n5. LIVE SYSTEM SCRIPTS")
print("-" * 80)

scripts = {
    'Live Engine': 'scripts/run_live_engine.py',
    'Options Monitor': 'scripts/monitor_options.py',
    'Health Check': 'scripts/health_check.py',
    'Status Check': 'scripts/status.py',
    'Emergency Reduce': 'scripts/emergency_reduce.py',
    'Dashboard Launch': 'launch_dashboard.sh',
}

for name, path in scripts.items():
    file_path = Path(path)
    if file_path.exists():
        is_executable = os.access(file_path, os.X_OK) or path.endswith('.py')
        check(name, True, f"{'Executable' if is_executable else 'Found'}")
    else:
        check(name, False, "Not found")

# 6. Check Logs Directory
print("\n6. LOGS DIRECTORY")
print("-" * 80)

logs_dir = Path('logs')
if logs_dir.exists():
    is_writable = os.access(logs_dir, os.W_OK)
    check("Logs directory", is_writable, "Writable" if is_writable else "Not writable")
else:
    check("Logs directory", False, "Does not exist")

# 7. Test API Connection (if possible)
print("\n7. API CONNECTION TEST")
print("-" * 80)

try:
    from dotenv import load_dotenv
    import requests
    
    load_dotenv('.env.options')
    token = os.getenv('UPSTOX_ACCESS_TOKEN')
    
    if token:
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(
            'https://api.upstox.com/v2/user/profile',
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            user_name = data.get('data', {}).get('user_name', 'Unknown')
            check("API Connection", True, f"Connected as {user_name}")
        else:
            check("API Connection", False, f"Status code: {response.status_code}")
    else:
        check("API Connection", False, "Token not found")
        
except Exception as e:
    check("API Connection", False, str(e))

# Summary
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

total = len(validation_results)
passed = sum(1 for _, result in validation_results if result)
failed = total - passed

print(f"\nTotal Checks: {total}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
print(f"Success Rate: {passed/total*100:.1f}%")

if failed == 0:
    print("\n🎉 ALL CHECKS PASSED - SYSTEM READY FOR TRADING!")
    print("\nNext Steps:")
    print("1. Wait for market open (9:15 AM)")
    print("2. Run: python scripts/run_live_engine.py")
    print("3. Run: python scripts/monitor_options.py")
    print("4. Run: bash launch_dashboard.sh")
    sys.exit(0)
else:
    print("\n⚠️  SOME CHECKS FAILED - REVIEW ISSUES ABOVE")
    print("\nFailed Checks:")
    for name, result in validation_results:
        if not result:
            print(f"  - {name}")
    sys.exit(1)
