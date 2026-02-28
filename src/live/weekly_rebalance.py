#!/usr/bin/env python3
"""
Live Weekly Rebalance - Step 8 of Northstar Macro Engine
Production-ready weekly portfolio rebalancing system
"""
import pandas as pd
import numpy as np
import os
import json
import argparse
from datetime import datetime, timedelta

# Canonical input files
CANONICAL_WEIGHTS = "data/processed/portfolio_weights.parquet"
LEGACY_FINAL_WEIGHTS = "data/portfolio/final_weights.parquet"
CANONICAL_MARKET_STATE = "data/processed/market_state.parquet"
CANONICAL_RISK_STATE = "data/processed/risk_state.parquet"
LEGACY_EMERGENCY = "data/risk/emergency_signal.parquet"
LEGACY_MACRO_REGIME = "data/macro/factors/macro_score.parquet"
OUT_DIR = "data/live"

os.makedirs(OUT_DIR, exist_ok=True)

def _extract_weights_series(df: pd.DataFrame):
    """
    Extract a ticker->weight series from both canonical row-format and legacy wide-format
    portfolio files.
    """
    if df is None or df.empty:
        return None, "empty"

    work = df.copy()

    # Canonical row format: one row per symbol.
    ticker_col = None
    for c in ["ticker", "symbol"]:
        if c in work.columns:
            ticker_col = c
            break

    weight_col = None
    for c in ["weight", "final_weight", "allocation", "w"]:
        if c in work.columns:
            weight_col = c
            break

    if ticker_col and weight_col:
        tmp = work[[ticker_col, weight_col]].copy()
        tmp[ticker_col] = tmp[ticker_col].astype(str).str.strip()
        tmp[weight_col] = pd.to_numeric(tmp[weight_col], errors="coerce")
        tmp = tmp.dropna(subset=[ticker_col, weight_col])
        if not tmp.empty:
            series = tmp.groupby(ticker_col)[weight_col].sum()
            series = series[series != 0.0]
            return series.sort_values(ascending=False), "canonical_row"

    # Legacy wide format: last row has ticker columns.
    row = work.iloc[-1] if len(work) > 0 else None
    if row is None:
        return None, "empty"

    skip_prefixes = ("applied_", "total_", "max_", "risk_")
    wide = {}
    for col in work.columns:
        col_str = str(col)
        if col_str.lower().startswith(skip_prefixes):
            continue
        if col_str.lower() in {"date", "timestamp", "regime"}:
            continue
        val = pd.to_numeric(row[col], errors="coerce")
        if pd.isna(val) or abs(float(val)) <= 0.0:
            continue
        ticker = col_str if col_str.endswith(".NS") else f"{col_str}.NS"
        wide[ticker] = float(val)

    if not wide:
        return None, "legacy_wide_empty"

    series = pd.Series(wide).sort_values(ascending=False)
    return series, "legacy_wide"


def load_latest_data():
    """Load the most recent data for live trading"""
    
    print("📊 Loading latest trading data...")
    
    data = {}
    
    # Load portfolio weights (prefer canonical unified file).
    weights = None
    weight_source = None
    for path in [CANONICAL_WEIGHTS, LEGACY_FINAL_WEIGHTS]:
        if not os.path.exists(path):
            continue
        try:
            raw = pd.read_parquet(path)
            weights, weight_source = _extract_weights_series(raw)
            if weights is not None and len(weights) > 0:
                print(f"   ✅ Portfolio weights: {len(weights)} positions ({weight_source})")
                break
        except Exception as e:
            print(f"   ⚠️ Failed loading weights from {path}: {e}")
            continue

    if weights is None:
        print(f"   ❌ Portfolio weights not found in canonical or legacy paths")
    data["weights"] = weights
    data["weights_source"] = weight_source
    
    # Load risk / emergency signals
    risk_row = None
    if os.path.exists(CANONICAL_RISK_STATE):
        try:
            rdf = pd.read_parquet(CANONICAL_RISK_STATE)
            risk_row = rdf.iloc[-1] if len(rdf) > 0 else None
            if risk_row is not None:
                print(f"   ✅ Risk state: {len(rdf)} rows (canonical)")
        except Exception as e:
            print(f"   ⚠️ Could not read canonical risk state: {e}")

    emergency_row = None
    if os.path.exists(LEGACY_EMERGENCY):
        try:
            edf = pd.read_parquet(LEGACY_EMERGENCY)
            emergency_row = edf.iloc[-1] if len(edf) > 0 else None
            if emergency_row is not None:
                print(f"   ✅ Emergency signals: {len(edf)} rows (legacy)")
        except Exception as e:
            print(f"   ⚠️ Could not read legacy emergency signals: {e}")

    data["risk"] = risk_row
    data["emergency"] = emergency_row
    
    # Load market regime/context (prefer canonical market state).
    regime_row = None
    if os.path.exists(CANONICAL_MARKET_STATE):
        try:
            mdf = pd.read_parquet(CANONICAL_MARKET_STATE)
            regime_row = mdf.iloc[-1] if len(mdf) > 0 else None
            if regime_row is not None:
                print(f"   ✅ Market state: {len(mdf)} rows (canonical)")
        except Exception as e:
            print(f"   ⚠️ Could not read canonical market state: {e}")

    legacy_macro_row = None
    if os.path.exists(LEGACY_MACRO_REGIME):
        try:
            mdf = pd.read_parquet(LEGACY_MACRO_REGIME)
            legacy_macro_row = mdf.iloc[-1] if len(mdf) > 0 else None
            if legacy_macro_row is not None:
                print(f"   ✅ Macro regime: {len(mdf)} rows (legacy)")
        except Exception as e:
            print(f"   ⚠️ Could not read legacy macro regime: {e}")

    data["regime"] = regime_row
    data["macro_legacy"] = legacy_macro_row
    
    return data

def apply_live_adjustments(weights, emergency_data, regime_data):
    """Apply live risk adjustments to portfolio weights"""
    
    print("⚙️  Applying live risk adjustments...")
    
    if weights is None:
        print("   ❌ No weights available")
        return None
    
    # Get stock columns (exclude metadata)
    stock_cols = [col for col in weights.index 
                 if not col.lower().startswith(('applied_', 'total_', 'max_', 'risk_'))]
    
    adjusted_weights = weights[stock_cols].copy()
    adjustments_applied = []
    
    # 1. Emergency brake adjustment
    if emergency_data is not None:
        emergency_flag = bool(emergency_data.get('Emergency', False))
        if emergency_flag:
            emergency_multiplier = 0.2  # Reduce to 20% during emergency
            adjusted_weights *= emergency_multiplier
            adjustments_applied.append(f"Emergency brake: {emergency_multiplier:.0%}")
            print(f"   🚨 EMERGENCY MODE: Reducing positions to 20%")
        
        elif 'Position_Multiplier' in emergency_data:
            pos_multiplier = float(emergency_data['Position_Multiplier'])
            adjusted_weights *= pos_multiplier
            adjustments_applied.append(f"Risk adjustment: {pos_multiplier:.0%}")
            print(f"   ⚙️  Risk adjustment: {pos_multiplier:.0%}")
    
    # 2. Macro regime adjustment
    if regime_data is not None:
        regime = regime_data.get('Regime', regime_data.get('regime', 'Unknown'))
        
        # Additional conservative adjustments for extreme regimes
        if regime == 'Crisis':
            crisis_multiplier = 0.5
            adjusted_weights *= crisis_multiplier
            adjustments_applied.append(f"Crisis mode: {crisis_multiplier:.0%}")
            print(f"   💥 CRISIS MODE: Further reducing positions to 50%")
        
        elif regime == 'Boom':
            # Could increase leverage in boom, but keeping conservative
            print(f"   📈 Boom regime detected - maintaining full allocation")
    
    # 3. Normalize weights to sum to target exposure
    total_weight = adjusted_weights.sum()
    if total_weight > 0:
        # Renormalize but maintain the risk-adjusted total exposure
        target_exposure = total_weight  # Keep the risk-adjusted exposure
        adjusted_weights = adjusted_weights / adjusted_weights.sum() * target_exposure
    
    return adjusted_weights, adjustments_applied

def generate_trade_list(current_weights, previous_weights=None, min_trade_size=0.01):
    """Generate actionable trade list"""
    
    print("📋 Generating trade list...")
    
    if previous_weights is None:
        # First time - all positions are new
        trades = current_weights[current_weights > min_trade_size].copy()
        trade_type = 'BUY'
    else:
        # Calculate position changes
        all_tickers = set(current_weights.index) | set(previous_weights.index)
        
        trades = []
        for ticker in all_tickers:
            current = current_weights.get(ticker, 0)
            previous = previous_weights.get(ticker, 0)
            change = current - previous
            
            if abs(change) > min_trade_size:
                trades.append({
                    'Ticker': ticker,
                    'Current_Weight': current,
                    'Previous_Weight': previous,
                    'Change': change,
                    'Action': 'BUY' if change > 0 else 'SELL',
                    'Trade_Size': abs(change)
                })
        
        trades = pd.DataFrame(trades)
    
    return trades

def create_trading_report(weights, emergency_data, regime_data, adjustments, trades):
    """Create comprehensive trading report"""
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("🧭 NORTHSTAR WEEKLY TRADING REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    # Market regime
    if regime_data is not None:
        report_lines.append("📊 MACRO REGIME STATUS")
        report_lines.append("-" * 30)
        current_regime = regime_data.get('Regime', regime_data.get('regime', 'Unknown'))
        macro_score = regime_data.get('MacroScore', regime_data.get('macro_score'))
        momentum = regime_data.get('Regime_Momentum', regime_data.get('macro_momentum'))
        report_lines.append(f"Current Regime: {current_regime}")
        if macro_score is not None and pd.notna(macro_score):
            report_lines.append(f"MacroScore: {float(macro_score):.3f}")
        else:
            report_lines.append("MacroScore: N/A")
        if momentum is not None and str(momentum) != "nan":
            report_lines.append(f"Momentum: {momentum}")
        report_lines.append("")
    
    # Risk status
    if emergency_data is not None and len(emergency_data) > 0:
        report_lines.append("🚨 RISK STATUS")
        report_lines.append("-" * 30)
        emergency_status = "ACTIVE" if emergency_data.get('Emergency', False) else "NORMAL"
        report_lines.append(f"Emergency Status: {emergency_status}")
        risk_level = emergency_data.get('Risk_Level', np.nan)
        drawdown = emergency_data.get('Drawdown', np.nan)
        if pd.notna(risk_level):
            report_lines.append(f"Risk Level: {float(risk_level):.1f}")
        else:
            report_lines.append("Risk Level: N/A")
        if pd.notna(drawdown):
            report_lines.append(f"Current Drawdown: {float(drawdown):.2%}")
        else:
            report_lines.append("Current Drawdown: N/A")
        report_lines.append("")
    
    # Adjustments applied
    if adjustments:
        report_lines.append("⚙️  ADJUSTMENTS APPLIED")
        report_lines.append("-" * 30)
        for adj in adjustments:
            report_lines.append(f"• {adj}")
        report_lines.append("")
    
    # Portfolio summary
    report_lines.append("💼 PORTFOLIO SUMMARY")
    report_lines.append("-" * 30)
    total_exposure = weights.sum()
    report_lines.append(f"Total Exposure: {total_exposure:.1%}")
    report_lines.append(f"Number of Positions: {(weights > 0.001).sum()}")
    report_lines.append(f"Largest Position: {weights.max():.2%}")
    report_lines.append("")
    
    # Top positions
    report_lines.append("📈 TOP 10 POSITIONS")
    report_lines.append("-" * 30)
    top_positions = weights.nlargest(10)
    for ticker, weight in top_positions.items():
        if weight > 0:
            report_lines.append(f"{ticker:15} {weight:8.2%}")
    report_lines.append("")
    
    # Trading activity
    if isinstance(trades, pd.DataFrame) and len(trades) > 0:
        report_lines.append("📋 TRADING ACTIVITY")
        report_lines.append("-" * 30)
        buys = trades[trades['Action'] == 'BUY']
        sells = trades[trades['Action'] == 'SELL']
        
        report_lines.append(f"Total Trades: {len(trades)}")
        report_lines.append(f"Buys: {len(buys)}, Sells: {len(sells)}")
        report_lines.append("")
        
        if len(trades) <= 20:  # Show all trades if not too many
            for _, trade in trades.iterrows():
                report_lines.append(f"{trade['Action']:4} {trade['Ticker']:15} {trade['Trade_Size']:8.2%}")
    else:
        report_lines.append("📋 NO TRADING ACTIVITY")
        report_lines.append("-" * 30)
        report_lines.append("No significant position changes required")
    
    report_lines.append("")
    report_lines.append("=" * 60)
    
    return "\n".join(report_lines)

def run(force_weekday: bool = False):
    """Main live trading function"""
    print("🔴 Live Weekly Rebalance - Step 8")
    print("=" * 50)
    
    now = datetime.now()
    if now.weekday() < 5 and not force_weekday:  # Monday-Friday
        print("⏭️ Weekly rebalance skipped (weekend-only policy active).")
        print(f"   Current day: {now.strftime('%A')} ({now.date()})")
        return
    
    # Load latest data
    data = load_latest_data()
    
    if data['weights'] is None:
        print("❌ Cannot proceed without portfolio weights")
        return
    
    # Apply live adjustments
    regime_context = data['regime'] if data.get('regime') is not None else data.get('macro_legacy')
    emergency_context = data['emergency']
    adjusted_weights, adjustments = apply_live_adjustments(
        data['weights'], emergency_context, regime_context
    )
    
    if adjusted_weights is None:
        print("❌ Failed to generate adjusted weights")
        return
    
    # Load previous weights for comparison (if available)
    previous_file = os.path.join(OUT_DIR, "previous_weights.parquet")
    previous_weights = None
    if os.path.exists(previous_file):
        try:
            previous_df = pd.read_parquet(previous_file)
            previous_weights, _ = _extract_weights_series(previous_df)
        except:
            pass
    
    # Generate trade list
    trades = generate_trade_list(adjusted_weights, previous_weights)
    
    # Create trading report
    report = create_trading_report(
        adjusted_weights, emergency_context, regime_context, adjustments, trades
    )
    
    # Print report to console
    print("\n" + report)
    
    # Save files for execution
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save current weights
    current_file = os.path.join(OUT_DIR, f"weights_{timestamp}.parquet")
    weights_df = pd.DataFrame([adjusted_weights])
    weights_df.to_parquet(current_file)
    
    # Update previous weights for next run
    weights_df.to_parquet(previous_file)
    
    # Save trade list
    if isinstance(trades, pd.DataFrame) and len(trades) > 0:
        trades_file = os.path.join(OUT_DIR, f"trades_{timestamp}.csv")
        trades.to_csv(trades_file, index=False)
        print(f"\n📋 Trade list saved: {trades_file}")
    
    # Save trading report
    report_file = os.path.join(OUT_DIR, f"report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"📊 Trading report saved: {report_file}")

    # Also publish standardized weekly snapshot + trade deltas for dashboard/reports.
    try:
        weekly_dir = "data/portfolio/weekly"
        trade_dir = "data/portfolio/trades"
        os.makedirs(weekly_dir, exist_ok=True)
        os.makedirs(trade_dir, exist_ok=True)

        snap_date = datetime.now().date().isoformat()
        snap_path = os.path.join(weekly_dir, f"{snap_date}.parquet")

        snap_df = pd.DataFrame(
            {
                "ticker": [t if str(t).endswith(".NS") else f"{t}.NS" for t in adjusted_weights.index.astype(str)],
                "weight": pd.to_numeric(adjusted_weights.values, errors="coerce"),
            }
        )
        snap_df = snap_df.dropna(subset=["ticker", "weight"])
        snap_df = snap_df[snap_df["weight"] > 0].copy()

        if not snap_df.empty:
            snap_df.to_parquet(snap_path, index=False)
            with open(os.path.join(weekly_dir, "latest.json"), "w") as f:
                json.dump({"date": snap_date, "path": os.path.abspath(snap_path)}, f, indent=2)
            print(f"📌 Weekly snapshot updated: {snap_path}")

            # Build delta vs previous snapshot (if available)
            snaps = sorted([p for p in os.listdir(weekly_dir) if p.endswith(".parquet")])
            if len(snaps) >= 2:
                prev_path = os.path.join(weekly_dir, snaps[-2])
                prev_df = pd.read_parquet(prev_path)
                prev_df = prev_df.rename(columns={"weight": "weight_prev"})[["ticker", "weight_prev"]]
                cur_df = snap_df.rename(columns={"weight": "weight_cur"})[["ticker", "weight_cur"]]

                delta = prev_df.merge(cur_df, on="ticker", how="outer").fillna(0.0)
                delta["delta"] = delta["weight_cur"] - delta["weight_prev"]
                delta["action"] = np.where(delta["delta"] > 0, "BUY", np.where(delta["delta"] < 0, "SELL", "HOLD"))
                delta["abs_delta"] = delta["delta"].abs()
                delta = delta.sort_values("abs_delta", ascending=False)

                trade_path = os.path.join(trade_dir, f"{snap_date}.parquet")
                delta.to_parquet(trade_path, index=False)
                print(f"📋 Weekly trade delta saved: {trade_path}")
    except Exception as e:
        print(f"⚠️ Could not publish standardized weekly artifacts: {e}")
    
    print(f"\n🎯 LIVE TRADING READY!")
    print(f"   Total Exposure: {adjusted_weights.sum():.1%}")
    print(f"   Execute trades and monitor positions")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run weekly rebalance (weekend-only by default)")
    parser.add_argument(
        "--force-weekday",
        action="store_true",
        help="Allow explicit weekday execution (manual override).",
    )
    args = parser.parse_args()
    run(force_weekday=bool(args.force_weekday))
