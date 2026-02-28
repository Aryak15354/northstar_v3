#!/usr/bin/env python3
"""
Daily update runner for coherence pipeline.
Runs, in order:
  1) market_internals.py  -> builds data/macro/factors/market_stress.parquet
  2) macro_regime.py      -> computes MacroScore and regimes
  3) coherence_audit.py   -> generates reports/coherence_audit_*.md
"""
import subprocess
import sys
from datetime import datetime
import os
import json

CMDS = [
    [sys.executable, 'src/preprocessing/market_internals.py'],
    [sys.executable, 'src/models/macro_regime.py'],
    [sys.executable, 'src/diagnostics/coherence_audit.py'],
]

def main():
    status = {'started': datetime.now().isoformat(), 'steps': []}
    # Integrated data pipeline (prices + macro)
    try:
        idp_cmd = [sys.executable, 'src/ingestion/integrated_data_pipeline.py']
        print(f"➡️ Integrated Data Pipeline: {' '.join(idp_cmd)}")
        res = subprocess.run(idp_cmd, capture_output=True, text=True)
        ok = (res.returncode == 0)
        status['steps'].append({'name': 'integrated_data_pipeline', 'ok': ok, 'time': datetime.now().isoformat()})
        if not ok:
            print(res.stdout)
            print(res.stderr)
            print("⚠️ Integrated data pipeline failed — continuing with last data")
        else:
            print(res.stdout)
    except Exception as e:
        print(f"⚠️ Integrated data pipeline error: {e}")
        status['steps'].append({'name': 'integrated_data_pipeline', 'ok': False, 'time': datetime.now().isoformat(), 'error': str(e)})

    for cmd in CMDS:
        print(f"➡️ Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            _write_status(status)
            raise SystemExit(f"Command failed: {' '.join(cmd)}")
        else:
            print(res.stdout)
        status['steps'].append({'name': os.path.basename(cmd[1]), 'ok': True, 'time': datetime.now().isoformat()})
    # Run portfolio governor weekly (Monday)
    if datetime.now().weekday() == 0:
        gov_cmd = [sys.executable, 'src/portfolio/run_governor.py']
        print(f"➡️ Weekly Governor: {' '.join(gov_cmd)}")
        res = subprocess.run(gov_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            _write_status(status)
            raise SystemExit("Governor weekly run failed")
        else:
            print(res.stdout)
        status['steps'].append({'name': 'governor', 'ok': True, 'time': datetime.now().isoformat()})
        # Weekly fundamentals fetch + process
        try:
            fin_cmd = [sys.executable, 'src/ingestion/financials_fetcher.py']
            print(f"➡️ Weekly Financials Fetcher: {' '.join(fin_cmd)}")
            res = subprocess.run(fin_cmd, capture_output=True, text=True)
            print(res.stdout)
            status['steps'].append({'name': 'financials_fetch', 'ok': (res.returncode == 0), 'time': datetime.now().isoformat()})
            proc_cmd = [sys.executable, 'src/processing/fundamental_processor.py']
            print(f"➡️ Fundamentals Processor: {' '.join(proc_cmd)}")
            res = subprocess.run(proc_cmd, capture_output=True, text=True)
            print(res.stdout)
            status['steps'].append({'name': 'fundamentals_process', 'ok': (res.returncode == 0), 'time': datetime.now().isoformat()})
        except Exception as e:
            print(f"⚠️ Weekly fundamentals step error: {e}")
            status['steps'].append({'name': 'fundamentals', 'ok': False, 'time': datetime.now().isoformat(), 'error': str(e)})
    # Light hyperparameter tuning daily
    tune_cmd = [sys.executable, 'src/portfolio/tuning.py']
    print(f"➡️ Hyperparameter Tuning: {' '.join(tune_cmd)}")
    res = subprocess.run(tune_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        _write_status(status)
        raise SystemExit("Tuning run failed")
    else:
        print(res.stdout)
    status['steps'].append({'name': 'tuning', 'ok': True, 'time': datetime.now().isoformat()})
    # Update PnL-on-paper and KPIs daily (uses latest weekly portfolio and prices)
    pnl_cmd = [sys.executable, 'src/portfolio/pnl_paper.py']
    print(f"➡️ Build PnL-on-paper: {' '.join(pnl_cmd)}")
    res = subprocess.run(pnl_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        _write_status(status)
        raise SystemExit("PnL-on-paper run failed")
    else:
        print(res.stdout)
    status['steps'].append({'name': 'pnl_on_paper', 'ok': True, 'time': datetime.now().isoformat()})

    kpi_cmd = [sys.executable, 'src/portfolio/backtest_weekly.py']
    print(f"➡️ Compute KPIs: {' '.join(kpi_cmd)}")
    res = subprocess.run(kpi_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        _write_status(status)
        raise SystemExit("KPI run failed")
    else:
        print(res.stdout)
    status['steps'].append({'name': 'kpis', 'ok': True, 'time': datetime.now().isoformat()})
    status['completed'] = datetime.now().isoformat()
    _write_status(status)
    print("✅ Daily coherence update complete")

def _write_status(status: dict):
    try:
        os.makedirs('data/portfolio', exist_ok=True)
        with open('data/portfolio/run_status.json', 'w') as f:
            json.dump(status, f, indent=2)
    except Exception:
        pass

if __name__ == '__main__':
    main()
