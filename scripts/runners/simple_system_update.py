#!/usr/bin/env python3
"""
🔄 SIMPLE SYSTEM UPDATE - NORTHSTAR V3
Simplified system update that bypasses complex living system integration

This script runs the essential system update components:
1. Data ingestion (RBI + Market data)
2. Market state computation
3. Portfolio construction
4. Basic system state updates

Usage:
    python simple_system_update.py
    python simple_system_update.py --quick
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import argparse
import traceback
warnings.filterwarnings('ignore')

# Ensure project root is importable when running as a script path.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def log_pipeline_failure(stage: str, message: str) -> None:
    """Append pipeline failure details to logs/pipeline_failures.log."""
    try:
        os.makedirs("logs", exist_ok=True)
        stamp = datetime.now().isoformat()
        with open("logs/pipeline_failures.log", "a", encoding="utf-8") as f:
            f.write(f"{stamp} | stage={stage} | {message}\\n")
    except Exception:
        pass

def run_daily_scoring():
    """Build canonical scores.parquet from DailyScorer."""

    print("\n📈 STEP 2.5: DAILYSCORER SCORING")
    print("-" * 40)

    score_builder = os.path.join("scripts", "runners", "generate_daily_scorer_scores.py")
    if not os.path.exists(score_builder):
        msg = f"missing scorer bridge script: {score_builder}"
        print(f"❌ {msg}")
        log_pipeline_failure("daily_scoring", msg)
        raise RuntimeError(msg)

    try:
        result = subprocess.run(
            [
                sys.executable,
                score_builder,
                "--date",
                "today",
                "--config",
                "config/research_policy.yaml",
                "--output",
                "data/processed/scores.parquet",
            ],
            capture_output=True,
            text=True,
            timeout=1200,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            print(f"❌ DailyScorer scoring failed: {err[:300]}")
            log_pipeline_failure("daily_scoring", err[:1000] or "unknown error")
            raise RuntimeError("daily scoring failed")
        print("✅ DailyScorer scoring completed")
        return True
    except Exception as e:
        print(f"❌ DailyScorer scoring error: {e}")
        tb = traceback.format_exc()
        log_pipeline_failure("daily_scoring", f"{e}\n{tb}")
        raise

def run_data_ingestion():
    """Run data ingestion pipeline"""
    
    print("📊 STEP 1: DATA INGESTION")
    print("-" * 40)
    
    success = True
    
    # Run integrated data pipeline
    try:
        print("🔄 Running integrated data pipeline...")
        result = subprocess.run([
            sys.executable, "src/ingestion/integrated_data_pipeline.py"
        ], capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            print("✅ Data ingestion completed")
        else:
            print(f"❌ Data ingestion failed: {result.stderr[:200]}")
            success = False
            
    except Exception as e:
        print(f"❌ Data ingestion error: {e}")
        success = False
    
    return success

def run_market_state_computation():
    """Run market state computation"""
    
    print("\n🧠 STEP 2: MARKET STATE COMPUTATION")
    print("-" * 40)
    
    try:
        print("📈 Computing canonical market state spine...")

        # Use the canonical engine so all downstream dashboards/panels get
        # full macro/market/regime/risk features instead of placeholder fields.
        from src.state.market_state import MarketStateEngine

        engine = MarketStateEngine()
        state = engine.compute_market_state()
        output_path = engine.save_market_state(state)

        # Basic sanity check for expected rich schema.
        market_state_df = pd.read_parquet(output_path)
        expected_cols = {"date", "macro_score", "macro_regime", "risk_on", "allowed_exposure", "stress_score"}
        missing = expected_cols - set(market_state_df.columns)
        if missing:
            print(f"⚠️ Market state saved but missing expected columns: {sorted(missing)}")
            return False

        print(f"✅ Market state computation completed ({len(market_state_df.columns)} columns)")
        return True
        
    except Exception as e:
        print(f"❌ Market state computation error: {e}")
        return False

def run_portfolio_construction():
    """Run basic portfolio construction"""
    
    print("\n💼 STEP 3: PORTFOLIO CONSTRUCTION")
    print("-" * 40)
    
    try:
        print("🎯 Generating basic portfolio weights...")

        run_daily_scoring()
        
        # Prefer real, score-weighted portfolios if scores exist.
        scores_path = "data/processed/scores.parquet"
        governor_cfg = "data/portfolio/governor_config.json"

        max_weight = 0.07

        # IMPORTANT: target exposure should come from the latest real market state artifacts.
        # Defaulting to a fixed 0.60 caused "exposure utilization" to exceed 100% when the
        # intelligent state capped exposure lower (e.g., 0.15 in bear regimes).
        target_exposure = 0.60
        try:
            ims_path = "data/processed/intelligent_market_state.parquet"
            if os.path.exists(ims_path):
                ims = pd.read_parquet(ims_path)
                if not ims.empty and "allowed_exposure" in ims.columns:
                    # Take the latest value; normalize percent-like values to [0,1].
                    v = pd.to_numeric(ims["allowed_exposure"], errors="coerce").dropna()
                    if not v.empty:
                        x = float(v.iloc[-1])
                        if x > 1.0:
                            x = x / 100.0
                        if 0.0 <= x <= 1.0:
                            target_exposure = x
        except Exception:
            pass

        # Keep within reasonable bounds.
        target_exposure = float(max(0.0, min(0.95, target_exposure)))
        if os.path.exists(governor_cfg):
            try:
                import json
                cfg = json.loads(open(governor_cfg, "r").read())
                max_weight = float(cfg.get("max_weight_per_name", max_weight))
            except Exception:
                pass

        if not os.path.exists(scores_path):
            raise RuntimeError(f"missing score artifact: {scores_path}")

        scores_df = pd.read_parquet(scores_path)
        if not {"ticker", "score"}.issubset(scores_df.columns):
            raise RuntimeError("scores.parquet missing required columns: ticker, score")

        scores_df = scores_df.copy()
        scores_df["score"] = pd.to_numeric(scores_df["score"], errors="coerce")
        scores_df = scores_df.dropna(subset=["ticker", "score"])
        scores_df = scores_df.sort_values("score", ascending=False)

        top = scores_df.head(50)
        if top.empty or float(top["score"].sum()) <= 0.0:
            raise RuntimeError("scores.parquet has no positive score mass for portfolio construction")

        w = top["score"] / float(top["score"].sum())
        w = (w * target_exposure).clip(upper=max_weight)
        # Renormalize to target exposure after capping.
        total = float(w.sum())
        if total <= 0.0:
            raise RuntimeError("score-weight normalization collapsed to zero")
        w = w / total * target_exposure

        portfolio_weights = pd.DataFrame(
            {
                "symbol": top["ticker"].astype(str).str.replace(".NS", "", regex=False),
                "weight": w.values,
                "timestamp": [datetime.now().isoformat()] * len(top),
            }
        )
        print(f"✅ Built score-weighted portfolio from {scores_path} ({len(portfolio_weights)} names)")
        
        # Save portfolio weights
        portfolio_weights.to_parquet("data/processed/portfolio_weights.parquet", index=False)
        
        # Create strategy beliefs (simple version)
        strategy_beliefs = pd.DataFrame({
            'strategy': ['equal_weight', 'momentum', 'value'],
            'belief_strength': [0.33, 0.33, 0.34],
            'timestamp': [datetime.now().isoformat()] * 3
        })
        
        strategy_beliefs.to_parquet("data/processed/strategy_beliefs.parquet", index=False)
        
        print("✅ Portfolio construction completed")
        return True
        
    except Exception as e:
        print(f"❌ Portfolio construction error: {e}")
        tb = traceback.format_exc()
        log_pipeline_failure("portfolio_construction", f"{e}\n{tb}")
        raise

def run_system_state_update():
    """Update system state files"""
    
    print("\n🔧 STEP 4: SYSTEM STATE UPDATE")
    print("-" * 40)
    
    try:
        print("📝 Updating system state files...")
        
        # Create system status
        system_status = {
            'last_update': datetime.now().isoformat(),
            'data_fresh': True,
            'portfolio_updated': True,
            'system_operational': True,
            'components': {
                'data_ingestion': True,
                'market_state': True,
                'portfolio_construction': True
            }
        }
        
        # Save system status
        os.makedirs("data/processed", exist_ok=True)
        with open("data/processed/system_status.json", 'w') as f:
            import json
            json.dump(system_status, f, indent=2)
        
        print("✅ System state update completed")
        return True
        
    except Exception as e:
        print(f"❌ System state update error: {e}")
        return False

def main():
    """Main system update function"""
    
    parser = argparse.ArgumentParser(description="Simple Northstar V3 System Update")
    parser.add_argument("--quick", action="store_true", help="Quick update mode")
    args = parser.parse_args()
    
    print("🔄 NORTHSTAR V3 SIMPLE SYSTEM UPDATE")
    print("=" * 50)
    print(f"Mode: {'Quick' if args.quick else 'Full'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success_count = 0
    total_steps = 4 if not args.quick else 2

    if not args.quick:
        # Step 1: Data Ingestion
        if run_data_ingestion():
            success_count += 1
        
        # Step 2: Market State Computation
        if run_market_state_computation():
            success_count += 1

    # Step 3: Portfolio Construction
    try:
        if run_portfolio_construction():
            success_count += 1
    except Exception as e:
        print(f"❌ HARD STOP: portfolio pipeline halted due to scoring/construction failure: {e}")
        return 1
    
    # Step 4: System State Update
    if run_system_state_update():
        success_count += 1
    
    # Summary
    print(f"\n📊 UPDATE SUMMARY")
    print("=" * 30)
    print(f"Steps completed: {success_count}/{total_steps}")
    print(f"Success rate: {success_count/total_steps:.1%}")
    
    if success_count == total_steps:
        print("✅ System update completed successfully!")
        
        # Show key files created
        key_files = [
            "data/processed/market_state.parquet",
            "data/processed/portfolio_weights.parquet", 
            "data/processed/strategy_beliefs.parquet",
            "data/processed/system_status.json"
        ]
        
        print(f"\n📁 Key files updated:")
        for file_path in key_files:
            if os.path.exists(file_path):
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"   ✅ {file_path} ({size_mb:.2f} MB)")
            else:
                print(f"   ❌ {file_path} (missing)")
        
        return 0
    else:
        print("⚠️ System update completed with issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
