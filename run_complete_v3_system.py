#!/usr/bin/env python3
"""
🚀 COMPLETE NORTHSTAR V3 SYSTEM RUNNER
Comprehensive orchestrator for all facets of the Northstar V3 system

This script runs the complete pipeline:
1. Data Ingestion (RBI + Market Data)
2. System Update (Intelligence + Portfolio)
3. Backtesting & Validation
4. Shadow Trading
5. Performance Analysis
6. Integration Alignment (V3 + Options + Narratives + Regime/Risk hooks)
7. Dashboard Launch

Usage:
    python run_complete_v3_system.py                    # Full pipeline
    python run_complete_v3_system.py --quick            # Quick update only
    python run_complete_v3_system.py --data-only        # Data ingestion only
    python run_complete_v3_system.py --backtest-only    # Backtesting only
    python run_complete_v3_system.py --dashboard-only   # Launch dashboard only
    python run_complete_v3_system.py --macro-heavy      # Full macro impact/transmission profile
    python run_complete_v3_system.py --update-quarterly-financials  # Include quarterly financial refresh
"""

import argparse
import subprocess
import sys
import os
import time
import json
import select
import shlex
from datetime import datetime
from pathlib import Path


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _archive_isolation_check() -> tuple[bool, str]:
    archive_hits = [p for p in sys.path if "archive" in str(p).replace("\\", "/").lower()]
    if archive_hits:
        return False, f"archive path present in sys.path: {archive_hits[:3]}"
    for _, module in list(sys.modules.items()):
        module_file = getattr(module, "__file__", None)
        if module_file and "/archive/" in str(module_file).replace("\\", "/").lower():
            return False, f"archived module imported: {module_file}"
    return True, ""


PHASE_REQUIRED_ARTIFACTS = {
    "data_ingestion": [
        "data/macro/raw/",
        "data/raw/prices_daily/",
        "data/processed/market_state.parquet",
    ],
    "system_update": [
        "data/processed/strategy_beliefs.parquet",
        "data/processed/portfolio_weights.parquet",
        "data/processed/market_state.parquet",
        "data/processed/system_status.json",
        "data/processed/integrity/v3_integrity_report_latest.json",
        "data/processed/dashboard_view_model_live.pkl",
        "data/processed/dashboard_view_model_live.json",
        "data/processed/dashboard_view_model_research.pkl",
        "data/processed/dashboard_view_model_research.json",
        "reports/research/formula_lineage_and_unit_integrity_latest.json",
        "data/options/live/options_dashboard_state.json",
        "data/options/trade_ledger.parquet",
    ],
    "shadow_trading": [
        "data/live/shadow_trading/positions/",
        "data/live/shadow_trading/pnl/",
        "data/live/shadow_trading/decisions/",
    ],
    "integration_alignment": [
        "data/processed/unified_portfolio.parquet",
        "data/processed/regime_momentum.parquet",
        "data/processed/latest_narrative_change.json",
        "data/sentiment/v3/v3_sentiment_summary.json",
        "reports/capacity/capacity_walk_forward_report.json",
    ],
}


class NorthstarV3SystemRunner:
    """Complete system runner for all Northstar V3 facets"""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.strict_mode = _env_flag("NORTHSTAR_STRICT_MODE", default=False)
        self.start_time = datetime.now()
        self.execution_log = []
        self.project_root = Path(__file__).resolve().parent
        self.python = self._resolve_python()
        self.dashboard_port = None
        self.dashboard_type = None
        self.quick_mode = False
        self.no_dashboard = False
        self.skip_integration_alignment = False
        
        # Execution phases
        self.phases = {
            'real_data_policy': {'duration': 0, 'status': 'pending', 'details': []},
            'data_ingestion': {'duration': 0, 'status': 'pending', 'details': []},
            'system_update': {'duration': 0, 'status': 'pending', 'details': []},
            'backtesting': {'duration': 0, 'status': 'pending', 'details': []},
            'shadow_trading': {'duration': 0, 'status': 'pending', 'details': []},
            'performance_analysis': {'duration': 0, 'status': 'pending', 'details': []},
            'alpha_generation': {'duration': 0, 'status': 'pending', 'details': []},
            'integration_alignment': {'duration': 0, 'status': 'pending', 'details': []},
            'dashboard_launch': {'duration': 0, 'status': 'pending', 'details': []}
        }

    def _resolve_python(self) -> str:
        """Pick a working Python interpreter even if the active venv is corrupted."""

        candidates = []
        if sys.executable:
            candidates.append(sys.executable)
        # If we're inside a venv, try the base interpreter path explicitly (not via PATH).
        try:
            base_prefix = getattr(sys, "base_prefix", None)
            if base_prefix and base_prefix != sys.prefix:
                if os.name == "nt":
                    base_exe = str(Path(base_prefix) / "Scripts" / "python.exe")
                else:
                    base_exe = str(Path(base_prefix) / "bin" / "python3")
                candidates.append(base_exe)
        except Exception:
            pass
        # Fall back to common shims if the current interpreter can't import deps (broken venv).
        candidates.extend(["python3", "python"])

        probe = "import pandas, numpy, yfinance, streamlit, pytz"
        for exe in candidates:
            try:
                r = subprocess.run(
                    [exe, "-c", probe],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if r.returncode == 0:
                    if self.verbose and exe != sys.executable:
                        print(f"⚠️ Using alternate Python interpreter: {exe}")
                    return exe
            except Exception:
                continue

        # As a last resort, return the current interpreter and let downstream commands surface errors.
        return sys.executable

    def _normalize_command(self, command) -> list[str]:
        if isinstance(command, str):
            return shlex.split(command)
        return [str(part) for part in command]

    def _resolve_script_target(self, command: list[str]) -> Path | None:
        if len(command) < 2:
            return None

        exe = Path(command[0]).name.lower()
        if "python" not in exe:
            return None

        arg1 = command[1]
        if arg1 in {"-m", "-c"}:
            return None
        if not arg1.endswith(".py"):
            return None

        script_path = Path(arg1)
        if not script_path.is_absolute():
            script_path = self.project_root / script_path
        return script_path

    def _verify_phase_artifacts(self, phase: str) -> bool:
        artifacts = PHASE_REQUIRED_ARTIFACTS.get(phase, [])
        if not artifacts:
            return True

        ok = True
        for rel_path in artifacts:
            path = Path(rel_path)
            resolved = path if path.is_absolute() else (self.project_root / path)
            if resolved.exists():
                self.log_phase(phase, "success", f"Verified artifact: {rel_path}")
            else:
                ok = False
                self.log_phase(phase, "failed", f"Required artifact missing: {rel_path}")
        return ok
    
    def log_phase(self, phase, status, message="", duration=0):
        """Log phase execution"""
        
        self.phases[phase]['status'] = status
        self.phases[phase]['duration'] = duration
        if message:
            self.phases[phase]['details'].append(message)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        self.execution_log.append(entry)
        
        if self.verbose:
            status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️" if status == 'warning' else "🔄"
            print(f"   {status_icon} {phase}: {message}")
    
    
    def run_alpha_generation(self):
        """Run alpha generation snapshot (real-data-only).

        For real-data-only governance, alpha generation stays artifact-driven:
        scores + current portfolio + allocator outputs.
        """
        
        if self.verbose:
            print("\n🧠 Running Alpha Generation Pipeline...")
        
        try:
            from pathlib import Path
            import pandas as pd

            # Build cohesive alpha feed first (real artifacts only).
            cohesive_build_cmd = [
                self.python,
                "scripts/build_cohesive_alpha_feed.py",
                "--output",
                "data/processed/cohesive_alpha_feed.parquet",
            ]
            build_proc = subprocess.run(cohesive_build_cmd, capture_output=True, text=True, timeout=600)
            if build_proc.returncode != 0:
                raise RuntimeError(
                    f"cohesive_alpha_feed build failed: {(build_proc.stderr or build_proc.stdout)[:220]}"
                )
            scores_path = Path("data/processed/cohesive_alpha_feed.parquet")
            if not scores_path.exists():
                raise RuntimeError("cohesive_alpha_feed artifact missing after build")
            weights_path = Path("data/processed/portfolio_weights.parquet")
            alloc_path = Path("data/processed/capital_allocations.json")
            regime_path = Path("data/processed/regime_intelligence_feed.json")

            positions: dict[str, float] = {}
            if weights_path.exists():
                wdf = pd.read_parquet(weights_path)
                tick_col = "ticker" if "ticker" in wdf.columns else ("symbol" if "symbol" in wdf.columns else None)
                wcol = None
                for c in ["weight", "final_weight", "w", "allocation"]:
                    if c in wdf.columns:
                        wcol = c
                        break
                if tick_col and wcol:
                    tmp = wdf[[tick_col, wcol]].copy()
                    tmp[tick_col] = tmp[tick_col].astype(str).str.strip()
                    tmp[wcol] = pd.to_numeric(tmp[wcol], errors="coerce")
                    tmp = tmp.dropna(subset=[tick_col, wcol])
                    positions = {k: float(v) for k, v in zip(tmp[tick_col].tolist(), tmp[wcol].tolist())}
                else:
                    # Fallback: wide matrix format (date index + ticker columns)
                    numeric_cols = []
                    for c in wdf.columns:
                        lc = str(c).lower()
                        if lc.startswith(("applied_", "total_", "max_", "risk_")):
                            continue
                        try:
                            pd.to_numeric(wdf[c], errors="raise")
                            numeric_cols.append(c)
                        except Exception:
                            continue
                    if numeric_cols and len(wdf) > 0:
                        latest_row = wdf[numeric_cols].tail(1).iloc[0]
                        latest_row = pd.to_numeric(latest_row, errors="coerce").dropna()
                        latest_row = latest_row[latest_row.abs() > 0]
                        positions = {str(k): float(v) for k, v in latest_row.to_dict().items()}

            candidates = []
            if scores_path.exists():
                sdf = pd.read_parquet(scores_path)
                score_col = None
                for c in ["cohesive_alpha_score", "adjusted_alpha", "northstar_score", "score", "raw_score"]:
                    if c in sdf.columns:
                        score_col = c
                        break
                if score_col and "ticker" in sdf.columns:
                    sdf = sdf.copy()
                    sdf[score_col] = pd.to_numeric(sdf[score_col], errors="coerce")
                    sdf = sdf.dropna(subset=["ticker", score_col]).sort_values(score_col, ascending=False)
                    candidates = [
                        {"ticker": str(r["ticker"]), "score": float(r[score_col])}
                        for _, r in sdf.head(25).iterrows()
                    ]

            allocations = {}
            if alloc_path.exists():
                try:
                    allocations = json.loads(alloc_path.read_text()).get("allocations", {})
                except Exception:
                    allocations = {}

            regime_state = {}
            if regime_path.exists():
                try:
                    regime_state = json.loads(regime_path.read_text()).get("current_regime", {})
                except Exception:
                    regime_state = {}

            os.makedirs("data/alpha", exist_ok=True)
            alpha_results = {
                "timestamp": datetime.now().isoformat(),
                "positions": positions,
                "allocations": allocations,
                "regime_state": regime_state,
                "alpha_candidates": candidates,
                "score_source": str(scores_path),
                "notes": "Real-data-only alpha snapshot derived from V3 artifacts (cohesive/scores/weights/allocations).",
            }

            with open("data/alpha/latest_alpha_results.json", "w") as f:
                json.dump(alpha_results, f, indent=2)

            self.log_phase(
                "alpha_generation",
                "success",
                f"Alpha snapshot saved ({len(positions)} positions, {len(candidates)} candidates)",
            )
            return True
            
        except Exception as e:
            self.log_phase('alpha_generation', 'failed', f"Alpha generation failed: {e}")
            return False

    def run_command(self, command, phase, description, timeout=1800, cwd=None):
        """Run a command and log results"""

        command = self._normalize_command(command)
        if not command:
            self.log_phase(phase, "failed", f"{description} failed: empty command")
            return False

        script_target = self._resolve_script_target(command)
        if script_target is not None and not script_target.exists():
            self.log_phase(phase, "failed", f"{description} failed: missing script {script_target}")
            return False

        run_cwd = str(Path(cwd).resolve()) if cwd else str(self.project_root)

        if self.verbose:
            print(f"\n🔄 {description}")
            print(f"   Command: {' '.join(shlex.quote(part) for part in command)}")
            print(f"   CWD: {run_cwd}")
        
        start_time = time.time()

        try:
            env = os.environ.copy()
            env.setdefault("PYTHONUNBUFFERED", "1")

            # Stream stdout/stderr live so long-running steps don't look hung.
            proc = subprocess.Popen(
                command,
                cwd=run_cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            tail_lines = []
            max_tail = 200

            try:
                # Avoid blocking on readline() when the child process is quiet.
                # We use select() to check for available output.
                last_heartbeat = time.time()
                while True:
                    if proc.poll() is not None:
                        # Drain remaining output
                        if proc.stdout:
                            for line in proc.stdout.read().splitlines():
                                if not line:
                                    continue
                                print(f"   {line}")
                                tail_lines.append(line)
                                if len(tail_lines) > max_tail:
                                    tail_lines = tail_lines[-max_tail:]
                        break

                    if proc.stdout:
                        rlist, _, _ = select.select([proc.stdout], [], [], 0.25)
                        if rlist:
                            line = proc.stdout.readline()
                            if line:
                                line = line.rstrip("\n")
                                if line:
                                    print(f"   {line}")
                                    tail_lines.append(line)
                                    if len(tail_lines) > max_tail:
                                        tail_lines = tail_lines[-max_tail:]

                    # Heartbeat every ~15s so "silent" steps are still visibly running.
                    if time.time() - last_heartbeat >= 15:
                        elapsed = time.time() - start_time
                        print(f"   ⏳ Still running... ({elapsed:.0f}s elapsed)")
                        last_heartbeat = time.time()
            except KeyboardInterrupt:
                proc.terminate()
                raise

            rc = proc.wait(timeout=max(1, int(timeout - (time.time() - start_time))))
            duration = time.time() - start_time

            if rc == 0:
                self.log_phase(phase, 'success', f"{description} completed", duration)
                return True

            err_preview = " | ".join(tail_lines[-8:])[:140]
            self.log_phase(phase, 'failed', f"{description} failed: {err_preview}", duration)
            return False
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.log_phase(phase, 'failed', f"{description} timed out after {timeout}s", duration)
            return False
        except Exception as e:
            duration = time.time() - start_time
            self.log_phase(phase, 'failed', f"{description} error: {str(e)}", duration)
            return False
    
    def phase_1_data_ingestion(self, force_update=False):
        """Phase 1: Complete data ingestion (RBI + Market Data)"""
        
        print("\n" + "="*60)
        print("🔄 PHASE 1: DATA INGESTION")
        print("="*60)
        
        success = True

        # Strict runtime graph: deterministic validation path with hard failures.
        if self.strict_mode:
            success &= self.run_command(
                [self.python, "scripts/ci/strict_data_ingestion_check.py"],
                'data_ingestion',
                "Strict data ingestion validation",
                timeout=600,
            )
            return success
        
        # Step 0: Update index data first (yfinance-based)
        success &= self.run_command(
            [self.python, "scripts/update_index_data.py", "--period", "5y"],
            'data_ingestion',
            "Index data update (NIFTY benchmarks)",
            timeout=900
        )
        
        # Step 1: Integrated macro + market + spine update (single pass)
        pipeline_cmd = [self.python, "src/ingestion/integrated_data_pipeline.py"]

        # RBI series can be revised retrospectively; allow explicit forced refresh.
        if force_update:
            pipeline_cmd.append("--force-macro")

        success &= self.run_command(
            pipeline_cmd,
            'data_ingestion',
            "Integrated data update (RBI macro + YFinance + Market State Spine)",
            timeout=2400
        )
        
        # Verify data availability
        success &= self._verify_phase_artifacts("data_ingestion")

        return success
    
    def phase_2_system_update(
        self,
        quick: bool = False,
        sentiment_cycles: int = 1,
        sentiment_interval_minutes: int = 180,
        block_on_sentiment_cycles: bool = False,
        skip_options_cycle: bool = False,
        update_financials: bool = False,
        financials_tickers: str = "",
        financials_max_tickers: int = 0,
        macro_heavy: bool = False,
        skip_macro_impact: bool = False,
        skip_macro_transmission: bool = False,
        macro_impact_companies: int = 120,
        macro_impact_top_macros: int = 30,
        macro_transmission_companies: int = 120,
        macro_transmission_macros: int = 20,
        skip_integrity_audit: bool = False,
    ):
        """Phase 2: System update (Intelligence + Portfolio)"""
        
        print("\n" + "="*60)
        print("🧠 PHASE 2: SYSTEM UPDATE")
        print("="*60)
        
        success = True

        # Strict runtime graph: deterministic update/runtime validation with hard failures.
        if self.strict_mode:
            success &= self.run_command(
                [self.python, "scripts/ci/strict_system_update_check.py"],
                'system_update',
                "Strict system update validation",
                timeout=600,
            )
            success &= self.run_command(
                [self.python, "scripts/ci/strict_options_runtime_check.py"],
                "system_update",
                "Strict options runtime validation",
                timeout=600,
            )
            return success
        
        # Step 2.1: NS-USO V3 Batch Ingestion (support multiple intraday cycles)
        if not quick:  # Skip sentiment in quick mode
            cycles = max(1, int(sentiment_cycles))
            wait_seconds = max(0, int(sentiment_interval_minutes)) * 60

            for cycle in range(cycles):
                cycle_desc = (
                    f"NS-USO V3 batch sentiment ingestion (cycle {cycle + 1}/{cycles})"
                    if cycles > 1
                    else "NS-USO V3 batch sentiment ingestion (India-specific)"
                )
                success &= self.run_command(
                    [self.python, "ns_uso/scripts/run_v3_sentiment_cycle.py"],
                    'system_update',
                    cycle_desc,
                    timeout=600
                )

                # Classify sentiment ingestion outcome (success vs no_data).
                summary_path = Path("data/sentiment/v3/v3_sentiment_summary.json")
                sentiment_status = None
                sentiment_msg = ""
                if summary_path.exists():
                    try:
                        summary = json.loads(summary_path.read_text())
                        sentiment_status = str(summary.get("status", "")).strip().lower()
                        if not sentiment_status and isinstance(summary, dict):
                            # Legacy NS-USO summary schema (no explicit status field).
                            if summary.get("artifacts_created") or summary.get("processing_summary"):
                                sentiment_status = "success"
                        sentiment_msg = str(summary.get("message", "")).strip()
                    except Exception:
                        sentiment_status = None

                if sentiment_status and sentiment_status != "success":
                    self.log_phase(
                        "system_update",
                        "warning",
                        (
                            f"NS-USO status `{sentiment_status}` after cycle {cycle + 1}/{cycles}. "
                            f"{sentiment_msg or 'No artifacts were synced.'}"
                        ),
                    )
                    # Avoid repeating identical no-data cycles in the same run.
                    if sentiment_status == "no_data" and cycle < cycles - 1:
                        self.log_phase(
                            "system_update",
                            "warning",
                            "Stopping remaining sentiment cycles for this run (no source exports detected).",
                        )
                        break

                if cycle < cycles - 1 and wait_seconds > 0:
                    if not block_on_sentiment_cycles:
                        wait_minutes = wait_seconds // 60
                        remaining = cycles - (cycle + 1)
                        self.log_phase(
                            'system_update',
                            'warning',
                            (
                                f"Non-blocking mode: completed cycle {cycle + 1}/{cycles}. "
                                f"Deferring remaining {remaining} cycle(s) that were configured "
                                f"at {wait_minutes}m intervals."
                            )
                        )
                        break

                    wait_minutes = wait_seconds // 60
                    self.log_phase(
                        'system_update',
                        'warning',
                        f"Waiting {wait_minutes}m before next sentiment cycle"
                    )
                    time.sleep(wait_seconds)
        
        # Step 2.2: Portfolio + basic state update (lightweight, real artifacts).
        # Note: Phase 1 already refreshed raw data; we run the update in quick mode
        # to avoid re-downloading, unless the user explicitly runs this script alone.
        update_cmd = [self.python, "scripts/runners/simple_system_update.py"]
        if quick:
            update_cmd.append("--quick")
        
        success &= self.run_command(
            update_cmd,
            'system_update',
            "Simple system update (Data + Portfolio)",
            timeout=1800
        )

        # Step 2.3: Refresh all V3 dashboard artifacts (prices/technicals/regimes/pnl/narratives).
        refresh_cmd = [self.python, "scripts/runners/refresh_v3_artifacts.py"]
        if quick:
            refresh_cmd.append("--quick")
        if update_financials:
            refresh_cmd.append("--update-financials")
        if financials_tickers.strip():
            refresh_cmd.extend(["--financials-tickers", financials_tickers.strip()])
        if financials_max_tickers and int(financials_max_tickers) > 0:
            refresh_cmd.extend(["--financials-max-tickers", str(int(financials_max_tickers))])
        if skip_macro_impact:
            refresh_cmd.append("--skip-macro-impact")
        if skip_macro_transmission:
            refresh_cmd.append("--skip-macro-transmission")
        if macro_heavy:
            refresh_cmd.append("--macro-heavy")
        if int(macro_impact_companies) > 0:
            refresh_cmd.extend(["--macro-impact-companies", str(int(macro_impact_companies))])
        if int(macro_impact_top_macros) > 0:
            refresh_cmd.extend(["--macro-impact-top-macros", str(int(macro_impact_top_macros))])
        if int(macro_transmission_companies) > 0:
            refresh_cmd.extend(["--macro-transmission-companies", str(int(macro_transmission_companies))])
        if int(macro_transmission_macros) > 0:
            refresh_cmd.extend(["--macro-transmission-macros", str(int(macro_transmission_macros))])
        if skip_integrity_audit:
            refresh_cmd.append("--skip-integrity-audit")
        success &= self.run_command(
            refresh_cmd,
            "system_update",
            "Refresh V3 artifacts (real-data pipeline for dashboard)",
            timeout=3600,
        )

        # Step 2.3B: Build canonical dashboard view model artifacts (live + research split).
        success &= self.run_command(
            [self.python, "scripts/runners/build_dashboard_view_model.py", "--mode", "both"],
            "system_update",
            "Build canonical dashboard view model artifacts",
            timeout=900,
        )

        # Step 2.4: Run integrated options paper cycle (V3-aligned).
        if skip_options_cycle:
            self.log_phase(
                "system_update",
                "success",
                "Integrated options paper-trading cycle disabled by --skip-options-cycle",
            )
        else:
            options_cmd = [
                self.python,
                "scripts/run_integrated_options_paper_engine.py",
                "--mode",
                "single",
                "--underlyings",
                "NIFTY,BANKNIFTY,FINNIFTY",
                "--aggressive",
            ]
            success &= self.run_command(
                options_cmd,
                "system_update",
                "Integrated options paper-trading cycle",
                timeout=900,
            )
        
        # Verify system state files
        success &= self._verify_phase_artifacts("system_update")
        
        return success
    
    def phase_3_backtesting(self):
        """Phase 3: Backtesting & Validation"""
        
        print("\n" + "="*60)
        print("🧪 PHASE 3: BACKTESTING & VALIDATION")
        print("="*60)
        
        success = True
        
        # Run institutional 12-month validation
        success &= self.run_command(
            [self.python, "scripts/institutional_12month_real_data.py"],
            'backtesting',
            "12-month institutional validation",
            timeout=3600
        )
        
        # Run enhanced stress tests
        success &= self.run_command(
            [self.python, "scripts/demo_enhanced_stress_tests.py"],
            'backtesting',
            "Enhanced stress tests (2008, COVID, 2022)",
            timeout=1800
        )
        
        # Run walk-forward validation
        success &= self.run_command(
            [self.python, "scripts/simple_walk_forward_validation.py"],
            'backtesting',
            "Walk-forward out-of-sample validation",
            timeout=2400
        )
        
        return success
    
    def phase_4_shadow_trading(self):
        """Phase 4: Shadow Trading Validation"""
        
        print("\n" + "="*60)
        print("📊 PHASE 4: SHADOW TRADING")
        print("="*60)
        
        success = True
        
        # Run shadow trading for 1 day
        success &= self.run_command(
            [self.python, "scripts/launch_comprehensive_shadow_trading.py", "--mode", "manual", "--days", "1"],
            'shadow_trading',
            "Shadow trading validation (1 day)",
            timeout=600
        )
        
        # Verify shadow trading outputs
        success &= self._verify_phase_artifacts("shadow_trading")
        
        return success
    
    def phase_5_performance_analysis(self):
        """Phase 5: Performance Analysis & Reporting"""
        
        print("\n" + "="*60)
        print("📈 PHASE 5: PERFORMANCE ANALYSIS")
        print("="*60)
        
        success = True
        
        # Generate 12-month performance report
        success &= self.run_command(
            [self.python, "scripts/generate_12month_performance_report.py"],
            'performance_analysis',
            "12-month performance report generation",
            timeout=600
        )
        
        # Run final institutional validation
        success &= self.run_command(
            [self.python, "scripts/simple_institutional_validation.py"],
            'performance_analysis',
            "Final institutional validation",
            timeout=1200
        )

        # Generate fund-grade institutional report
        success &= self.run_command(
            [self.python, "scripts/generate_institutional_report_complete.py"],
            'performance_analysis',
            "Fund-grade institutional report generation",
            timeout=1200
        )
        
        return success
    
    def phase_5b_integration_alignment(self, quick: bool = False):
        """
        Phase 5B: Integration alignment between legacy V3 and options system.

        Covers portfolio analysis, rebalance hooks, regime/wave updates,
        options-v3 bridge health, and narrative delta tracking artifacts.
        """
        
        print("\n" + "="*60)
        print("🧩 PHASE 5B: INTEGRATION ALIGNMENT")
        print("="*60)
        
        success = True
        
        # Core alignment checks (fast, should run even in quick mode)
        success &= self.run_command(
            [self.python, "src/portfolio/unified_portfolio_coordinator.py"],
            'integration_alignment',
            "Unified portfolio construction + analytics",
            timeout=1800
        )
        
        success &= self.run_command(
            [self.python, "src/processing/regime_momentum.py"],
            'integration_alignment',
            "Regime wave/momentum update",
            timeout=600
        )

        success &= self.run_command(
            [self.python, "scripts/runners/run_liquidity_risk.py"],
            'integration_alignment',
            "Portfolio risk measurement refresh",
            timeout=900
        )
        
        success &= self.run_command(
            [self.python, "src/live/weekly_rebalance.py"],
            'integration_alignment',
            "Weekly rebalance integration check",
            timeout=600
        )
        
        success &= self.run_command(
            [
                self.python,
                "-c",
                (
                    "import json; "
                    "from src.options.v3_risk_integration import create_v3_risk_integration; "
                    "s=create_v3_risk_integration(1000000.0).get_integrated_risk_summary(); "
                    "print(json.dumps(s['v3_integration']))"
                ),
            ],
            'integration_alignment',
            "Options ↔ V3 risk bridge health check",
            timeout=600
        )
        
        success &= self.run_command(
            [self.python, "scripts/test_stock_options_integration.py"],
            'integration_alignment',
            "Stock options integration validation",
            timeout=900
        )

        success &= self.run_command(
            [self.python, "scripts/run_capacity_walk_forward.py", "--aum", "100000000"],
            'integration_alignment',
            "Capacity-constrained walk-forward integration",
            timeout=1200
        )
        
        # Heavier integration only in full mode
        if not quick:
            success &= self.run_command(
                [self.python, "scripts/build_weekly_causal_fabric.py"],
                'integration_alignment',
                "Causal cluster analysis refresh",
                timeout=3600
            )
            
            success &= self.run_command(
                [self.python, "scripts/run_enhanced_northstar_with_narratives.py"],
                'integration_alignment',
                "Enhanced narrative system refresh",
                timeout=1800
            )

            success &= self.run_command(
                [self.python, "scripts/discover_northstar_capacity.py"],
                'integration_alignment',
                "Institutional capacity discovery report",
                timeout=1200
            )
        else:
            self.log_phase(
                "integration_alignment",
                "success",
                "Heavy cluster/narrative refresh disabled by --quick mode",
            )
        
        # Verify key integration artifacts
        success &= self._verify_phase_artifacts("integration_alignment")
        
        return success
    
    def phase_6_dashboard_launch(self, dashboard_type="brain", port: int = 8517):
        """Phase 6: Dashboard Launch"""
        
        print("\n" + "="*60)
        print("🖥️ PHASE 6: DASHBOARD LAUNCH")
        print("="*60)
        
        # Launch official V3 dashboard (Streamlit)
        print(f"🚀 Launching V3 dashboard ({dashboard_type})...")
        print(f"   This will open in your browser at http://localhost:{port}...")
        
        try:
            dash_map = {
                "brain": "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py",
                "unified": "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py",
                "professional": "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py",
            }
            dash_file = dash_map.get(dashboard_type, dash_map["brain"])
            dash_path = Path(__file__).parent / dash_file
            if not dash_path.exists():
                self.log_phase('dashboard_launch', 'failed', f"Dashboard file missing: {dash_file}")
                return None

            dashboard_cmd = [
                self.python,
                "-m",
                "streamlit",
                "run",
                str(dash_path),
                "--server.port",
                str(port),
            ]
            
            if self.verbose:
                print(f"   Command: {' '.join(dashboard_cmd)}")
                print("   Dashboard will launch in browser...")
                print("   Press Ctrl+C to stop the dashboard when done")
            
            # Start dashboard process
            process = subprocess.Popen(dashboard_cmd, cwd=str(Path(__file__).parent))

            # Health guard: ensure process didn't crash immediately.
            time.sleep(2)
            if process.poll() is not None:
                self.log_phase(
                    'dashboard_launch',
                    'failed',
                    f"Dashboard process exited early with code {process.returncode}",
                )
                return None

            self.log_phase('dashboard_launch', 'success', f"V3 dashboard launched (PID: {process.pid})")
            self.dashboard_port = port
            self.dashboard_type = dashboard_type
            
            return process
            
        except Exception as e:
            self.log_phase('dashboard_launch', 'failed', f"Dashboard launch error: {str(e)}")
            return None
    
    def generate_execution_report(self):
        """Generate comprehensive execution report"""
        
        total_duration = (datetime.now() - self.start_time).total_seconds()
        
        report = {
            'execution_summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_duration_seconds': total_duration,
                'total_duration_minutes': round(total_duration / 60, 2)
            },
            'phase_results': self.phases,
            'execution_log': self.execution_log,
            'system_status': {
                'data_fresh': self.phases['data_ingestion']['status'] == 'success',
                'system_updated': self.phases['system_update']['status'] == 'success',
                'backtests_complete': self.phases['backtesting']['status'] == 'success',
                'shadow_trading_active': self.phases['shadow_trading']['status'] == 'success',
                'performance_analyzed': self.phases['performance_analysis']['status'] == 'success',
                'integration_aligned': self.phases['integration_alignment']['status'] == 'success',
                'dashboard_running': self.phases['dashboard_launch']['status'] == 'success'
            }
        }

        # Include freeze-state governance in top-level status.
        freeze_path = Path("data/processed/model_freeze_state.json")
        if freeze_path.exists():
            try:
                freeze = json.loads(freeze_path.read_text())
                report['system_status']['freeze_active'] = bool(freeze.get('freeze_active', False))
                report['system_status']['freeze_triggers'] = freeze.get('triggers', [])
            except Exception:
                report['system_status']['freeze_active'] = False
                report['system_status']['freeze_triggers'] = []
        else:
            report['system_status']['freeze_active'] = False
            report['system_status']['freeze_triggers'] = []
        
        # Save report
        report_dir = Path("reports/system")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"complete_system_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report, report_file
    
    def print_execution_summary(self, report, report_file):
        """Print execution summary"""
        
        print("\n" + "="*60)
        print("📊 EXECUTION SUMMARY")
        print("="*60)
        
        total_minutes = report['execution_summary']['total_duration_minutes']
        print(f"   Total execution time: {total_minutes:.1f} minutes")
        print(f"   Report saved to: {report_file}")
        
        print(f"\n📋 PHASE RESULTS:")
        for phase, details in self.phases.items():
            status_icon = "✅" if details['status'] == 'success' else "❌" if details['status'] == 'failed' else "⚠️"
            duration_str = f"({details['duration']:.1f}s)" if details['duration'] > 0 else ""
            print(f"   {status_icon} {phase.replace('_', ' ').title()}: {details['status']} {duration_str}")
        
        failed_phases = [name for name, details in self.phases.items() if details.get("status") == "failed"]
        warning_phases = [name for name, details in self.phases.items() if details.get("status") == "warning"]
        dashboard_status = self.phases.get("dashboard_launch", {}).get("status", "pending")
        core_required = ["data_ingestion", "system_update", "integration_alignment"]
        core_success = all(self.phases.get(p, {}).get("status") == "success" for p in core_required)
        dashboard_running = dashboard_status == "success"
        dashboard_required = not self.no_dashboard
        all_success = core_success and (dashboard_running if dashboard_required else True) and len(failed_phases) == 0

        if all_success:
            status_text = "✅ FULLY OPERATIONAL"
        elif core_success and len(failed_phases) == 0:
            status_text = "⚠️ CORE OPERATIONAL (HEADLESS/PARTIAL UI)"
        else:
            status_text = "⚠️ PARTIAL SUCCESS"

        print(f"\n🎯 SYSTEM STATUS: {status_text}")
        if failed_phases:
            print(f"   Failed phases: {', '.join(failed_phases)}")
        if dashboard_required and not dashboard_running:
            print(f"   Dashboard status: {dashboard_status}")

        if report.get("system_status", {}).get('dashboard_running'):
            print(f"\n🖥️ DASHBOARD ACCESS:")
            port = self.dashboard_port or 8517
            dtype = self.dashboard_type or "brain"
            print(f"   {dtype.title()} Dashboard: http://localhost:{port}")
            print(f"   Use Ctrl+C to stop the dashboard")

        if report.get("system_status", {}).get("freeze_active"):
            triggers = report.get("system_status", {}).get("freeze_triggers", [])
            print(f"\n🧊 MODEL FREEZE: ACTIVE ({', '.join(triggers) if triggers else 'risk guardrails'})")

        runtime_integrity_violations = []
        if failed_phases:
            runtime_integrity_violations.append(f"failed_phases={failed_phases}")

        allowed_warning_phases = set()
        if self.quick_mode:
            allowed_warning_phases.update({"backtesting", "shadow_trading", "performance_analysis"})
        if self.no_dashboard:
            allowed_warning_phases.add("dashboard_launch")
        if self.skip_integration_alignment:
            allowed_warning_phases.add("integration_alignment")

        unexpected_warning_phases = [p for p in warning_phases if p not in allowed_warning_phases]
        if self.strict_mode and unexpected_warning_phases:
            runtime_integrity_violations.append(f"warning_phases={unexpected_warning_phases}")

        for entry in self.execution_log:
            msg = str(entry.get("message", "")).lower()
            if self.strict_mode and any(
                token in msg
                for token in (
                    "fallback",
                    "ignored",
                    "continuing",
                    "skipping",
                    "skipped",
                    "defaulting",
                    "recovered",
                    "retrying",
                )
            ):
                runtime_integrity_violations.append(f"log_pattern_violation={entry.get('phase')}")

        if runtime_integrity_violations:
            print("\n❌ RUNTIME INTEGRITY VIOLATIONS DETECTED:")
            for item in runtime_integrity_violations:
                print(f"   - {item}")
            return False

        return all_success

def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(description="Complete Northstar V3 System Runner")
    parser.add_argument("--quick", action="store_true", help="Quick update mode")
    parser.add_argument("--data-only", action="store_true", help="Data ingestion only")
    parser.add_argument("--backtest-only", action="store_true", help="Backtesting only")
    parser.add_argument("--dashboard-only", action="store_true", help="Launch dashboard only")
    parser.add_argument("--dashboard", default="brain", choices=["brain", "unified", "professional"], help="Dashboard type")
    parser.add_argument("--port", type=int, default=8517, help="Streamlit server port")
    parser.add_argument("--force-data", action="store_true", help="Force data update even if fresh")
    parser.add_argument("--sentiment-cycles", type=int, default=1, help="Number of NS-USO sentiment cycles during system update (full mode)")
    parser.add_argument("--sentiment-interval-minutes", type=int, default=180, help="Minutes between NS-USO sentiment cycles (full mode)")
    parser.add_argument("--block-sentiment-cycles", action="store_true", help="Block and wait between sentiment cycles (default is non-blocking)")
    parser.add_argument("--skip-options-cycle", action="store_true", help="Skip integrated options paper-trading cycle in Phase 2")
    financials_group = parser.add_mutually_exclusive_group()
    financials_group.add_argument(
        "--update-quarterly-financials",
        action="store_true",
        help="Include quarterly financials/fundamentals refresh (default: skipped)",
    )
    financials_group.add_argument(
        "--skip-quarterly-financials",
        action="store_true",
        help="Explicitly skip quarterly financial refresh (default behavior)",
    )
    parser.add_argument(
        "--financials-tickers",
        type=str,
        default="",
        help="Optional comma-separated ticker override for quarterly financial refresh",
    )
    parser.add_argument(
        "--financials-max-tickers",
        type=int,
        default=0,
        help="Optional cap for quarterly financial refresh",
    )
    parser.add_argument("--macro-heavy", action="store_true", help="Run heavier macro impact/transmission profile in artifact refresh")
    parser.add_argument("--skip-macro-impact", action="store_true", help="Skip macro impact engine during artifact refresh")
    parser.add_argument("--skip-macro-transmission", action="store_true", help="Skip macro transmission engine during artifact refresh")
    parser.add_argument("--macro-impact-companies", type=int, default=120, help="Company cap for macro impact refresh")
    parser.add_argument("--macro-impact-top-macros", type=int, default=30, help="Macro-variable cap for macro impact refresh")
    parser.add_argument("--macro-transmission-companies", type=int, default=120, help="Company cap for macro transmission refresh")
    parser.add_argument("--macro-transmission-macros", type=int, default=20, help="Macro-variable cap for macro transmission refresh")
    parser.add_argument("--skip-integrity-audit", action="store_true", help="Skip final V3 integrity verification step")
    parser.add_argument("--no-dashboard", action="store_true", help="Do not launch Streamlit dashboard at the end (automation-safe)")
    parser.add_argument("--skip-integration-alignment", action="store_true", help="Skip Phase 5B integration alignment checks")
    parser.add_argument("--verbose", "-v", action="store_true", default=True, help="Verbose output")
    
    args = parser.parse_args()

    archive_ok, archive_reason = _archive_isolation_check()
    if not archive_ok:
        print(f"❌ Archive isolation violation: {archive_reason}")
        return 1
    
    # Initialize system runner
    runner = NorthstarV3SystemRunner(verbose=args.verbose)
    runner.quick_mode = bool(args.quick)
    runner.no_dashboard = bool(args.no_dashboard)
    runner.skip_integration_alignment = bool(args.skip_integration_alignment)
    
    print("🚀 NORTHSTAR V3 COMPLETE SYSTEM RUNNER")
    print("=" * 60)
    print("   Comprehensive orchestrator for all system facets")
    print(f"   Started: {runner.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    dashboard_process = None
    
    try:
        # Hard preflight: no mock/synthetic generators in production modules.
        ok = runner.run_command(
            [runner.python, "scripts/runners/enforce_real_data_only.py"],
            "real_data_policy",
            "Real-data-only policy enforcement",
            timeout=120,
        )
        if not ok:
            print("❌ Real-data-only policy failed. Aborting run.")
            return 1

        # Execute phases based on arguments
        if args.dashboard_only:
            if args.no_dashboard:
                runner.log_phase("dashboard_launch", "success", "Dashboard launch disabled by --no-dashboard")
            else:
                dashboard_process = runner.phase_6_dashboard_launch(args.dashboard, port=args.port)
        elif args.data_only:
            runner.phase_1_data_ingestion(force_update=args.force_data)
        elif args.backtest_only:
            runner.phase_3_backtesting()
        else:
            # Full pipeline
            runner.phase_1_data_ingestion(force_update=args.force_data)
            update_financials = bool(args.update_quarterly_financials and not args.skip_quarterly_financials)
            runner.phase_2_system_update(
                quick=args.quick,
                sentiment_cycles=args.sentiment_cycles,
                sentiment_interval_minutes=args.sentiment_interval_minutes,
                block_on_sentiment_cycles=args.block_sentiment_cycles,
                skip_options_cycle=args.skip_options_cycle,
                update_financials=update_financials,
                financials_tickers=args.financials_tickers,
                financials_max_tickers=args.financials_max_tickers,
                macro_heavy=args.macro_heavy,
                skip_macro_impact=args.skip_macro_impact,
                skip_macro_transmission=args.skip_macro_transmission,
                macro_impact_companies=args.macro_impact_companies,
                macro_impact_top_macros=args.macro_impact_top_macros,
                macro_transmission_companies=args.macro_transmission_companies,
                macro_transmission_macros=args.macro_transmission_macros,
                skip_integrity_audit=args.skip_integrity_audit,
            )
            runner.run_alpha_generation()
            
            if not args.quick:
                runner.phase_3_backtesting()
                runner.phase_4_shadow_trading()
                runner.phase_5_performance_analysis()
            else:
                runner.log_phase("backtesting", "success", "Backtesting disabled by --quick mode")
                runner.log_phase("shadow_trading", "success", "Shadow trading disabled by --quick mode")
                runner.log_phase("performance_analysis", "success", "Performance analysis disabled by --quick mode")

            if args.skip_integration_alignment:
                runner.log_phase(
                    "integration_alignment",
                    "success",
                    "Integration alignment disabled by --skip-integration-alignment",
                )
            else:
                runner.phase_5b_integration_alignment(quick=args.quick)
            
            if args.no_dashboard:
                runner.log_phase("dashboard_launch", "success", "Dashboard launch disabled by --no-dashboard")
            else:
                dashboard_process = runner.phase_6_dashboard_launch(args.dashboard, port=args.port)
        
        # Generate and display report
        report, report_file = runner.generate_execution_report()
        success = runner.print_execution_summary(report, report_file)
        
        # Keep dashboard running if launched
        if dashboard_process:
            print(f"\n🖥️ Dashboard is running (PID: {dashboard_process.pid})")
            print("   Press Ctrl+C to stop...")
            try:
                dashboard_process.wait()
            except KeyboardInterrupt:
                print(f"\n🛑 Stopping dashboard...")
                dashboard_process.terminate()
                dashboard_process.wait()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n🛑 Execution interrupted by user")
        if dashboard_process:
            dashboard_process.terminate()
        return 1
    except Exception as e:
        print(f"\n❌ Execution failed: {e}")
        if dashboard_process:
            dashboard_process.terminate()
        return 1

if __name__ == "__main__":
    sys.exit(main())
