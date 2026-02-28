#!/usr/bin/env python3
"""
Macro Overlay Engine - Step 5 of Northstar Macro Engine
Applies macro risk budget to stock engine weights
"""
import pandas as pd
import numpy as np
import os

# Input files
ENGINE_WEIGHT_SOURCES = [
    "data/processed/macro_transmission/macro_adjusted_scores.parquet",
    "data/processed/cohesive_alpha_feed.parquet",
    "data/processed/scores.parquet",
]
RISK_FILE = "data/macro/factors/risk_budget.parquet"
OUT_FILE = "data/portfolio/final_weights.parquet"
OUT_FILE_PROCESSED = "data/processed/portfolio_weights.parquet"

os.makedirs("data/portfolio", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

def _resolve_engine_weight_source():
    """Pick the best available alpha/score source for portfolio construction."""
    for path in ENGINE_WEIGHT_SOURCES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"No engine weight source found. Checked: {ENGINE_WEIGHT_SOURCES}"
    )


def load_engine_weights():
    """Load and convert Northstar scores to portfolio weights"""

    source_path = _resolve_engine_weight_source()
    print(f"📊 Loading engine weights from: {source_path}")

    if not os.path.exists(source_path):
        print(f"❌ Engine weights not found: {source_path}")
        print("   Run the complete pipeline first: python src/processing/pipeline.py")
        raise FileNotFoundError(f"Required file not found: {source_path}")

    # Load actual scores and convert to weights
    scores = pd.read_parquet(source_path)

    # Identify columns
    date_col = 'Date' if 'Date' in scores.columns else ('date' if 'date' in scores.columns else None)
    ticker_col = 'ticker' if 'ticker' in scores.columns else ('Ticker' if 'Ticker' in scores.columns else None)
    score_cols = [
        c
        for c in [
            'adjusted_alpha',
            'cohesive_alpha_score',
            'northstar_score',
            'final_score',
            'score',
            'ns_score',
            'raw_alpha',
        ]
        if c in scores.columns
    ]

    if not ticker_col:
        raise ValueError("No ticker column found in scores data. Expected 'ticker' or 'Ticker'")
    
    if not score_cols:
        raise ValueError(
            "No supported score column found in source data. "
            "Expected one of: adjusted_alpha, cohesive_alpha_score, northstar_score, final_score, score, ns_score, raw_alpha"
        )

    score_col = score_cols[0]

    if date_col:
        # Build weekly cadence: last-in-week snapshot before Top-20
        df_scores = scores[[date_col, ticker_col, score_col]].dropna().copy()
        df_scores[date_col] = pd.to_datetime(df_scores[date_col])
        df_scores['week'] = df_scores[date_col].dt.to_period('W-FRI').dt.to_timestamp()
        weights_list = []
        TOP_N = int(os.getenv('TOP_N', '20'))
        for w in sorted(df_scores['week'].unique()):
            week_df = df_scores[df_scores['week'] == w]
            # Take last score per ticker within the week
            week_df = week_df.sort_values(date_col).groupby(ticker_col, as_index=False).tail(1)
            week_df = week_df[[ticker_col, score_col]].dropna()
            if week_df.empty:
                continue
            top = week_df.nlargest(TOP_N, score_col)
            s = top[score_col].astype(float)
            # stable softmax
            s = (s - s.mean()) / (s.std() + 1e-8)
            s = s - s.max()
            raw = np.exp(s)
            wts = raw / (raw.sum() + 1e-12)
            weights_list.append({'date': pd.to_datetime(w), **dict(zip(top[ticker_col], wts))})
        if not weights_list:
            raise ValueError("No valid dated scores found in the data")
        weights_df = pd.DataFrame(weights_list).set_index('date').sort_index().fillna(0)
        # Normalize to weekly Friday, forward-fill within week
        weights_df = weights_df.resample('W-FRI').last().ffill().fillna(0)
        # Row-normalize to 1.0
        row_sums = weights_df.sum(axis=1).replace(0, 1)
        weights_df = weights_df.div(row_sums, axis=0).fillna(0)
        return weights_df
    else:
        # No explicit dates: treat as a current snapshot
        snap = scores[[ticker_col, score_col]].dropna().nlargest(20, score_col)
        s = snap[score_col].astype(float)
        s = (s - s.mean()) / (s.std() + 1e-8)
        s = s - s.max()
        raw = np.exp(s)
        w = raw / (raw.sum() + 1e-12)
        df = pd.DataFrame([{'date': pd.Timestamp.now(), **dict(zip(snap[ticker_col], w))}]).set_index('date')
        df = df.resample('W-FRI').last().ffill().fillna(0)
        row_sums = df.sum(axis=1).replace(0, 1)
        return df.div(row_sums, axis=0).fillna(0)

def apply_macro_throttle(weights_df, risk_df):
    """Apply macro risk budget to scale portfolio exposure"""
    
    print("🎚️  Applying macro risk throttle...")
    
    # Ensure weekly Friday frequency
    if not isinstance(weights_df.index, pd.DatetimeIndex):
        weights_df = weights_df.copy()
        weights_df.index = pd.to_datetime(weights_df.index)
    if not isinstance(risk_df.index, pd.DatetimeIndex):
        risk_df = risk_df.copy()
        risk_df.index = pd.to_datetime(risk_df.index)

    # Optional same-day alignment mode for intraday use
    if os.getenv('ALIGN_SAME_DAY', '0') != '0':
        print("   ALIGN_SAME_DAY active: daily alignment")
        weights_w = weights_df.asfreq('D').ffill()
        risk_w = risk_df.asfreq('D').ffill()
    else:
        weights_w = weights_df.resample('W-FRI').last().ffill()
        risk_w = risk_df.resample('W-FRI').last().ffill()

    # Align on union of dates so we don't drop latest-only weights or risk rows
    union_index = weights_w.index.union(risk_w.index).sort_values()
    weights_aligned = weights_w.reindex(union_index).ffill().bfill().fillna(0)
    risk_aligned = risk_w.reindex(union_index).ffill().bfill()

    # Optional shock-aware cap series
    shock_cap_series = None
    try:
        shock_path = "data/risk/shock_state.parquet"
        if os.path.exists(shock_path):
            shock = pd.read_parquet(shock_path)
            if not isinstance(shock.index, pd.DatetimeIndex) and 'Date' in shock.columns:
                shock['Date'] = pd.to_datetime(shock['Date'], errors='coerce')
                shock = shock.set_index('Date')
            # Expect column 'Shock_Max_Exposure'
            if 'Shock_Max_Exposure' in shock.columns:
                # Resample/align to union index
                if os.getenv('ALIGN_SAME_DAY', '0') != '0':
                    shock_w = shock.asfreq('D').ffill()
                else:
                    shock_w = shock.asfreq('W-FRI').ffill()
                shock_cap_series = shock_w.reindex(union_index).ffill().bfill()['Shock_Max_Exposure']
                print("   Shock-aware cap detected and aligned")
    except Exception as _:
        shock_cap_series = None
    common_dates = union_index
    
    print(f"   Aligned data: {len(common_dates)} dates")
    print(f"   Date range: {common_dates.min()} to {common_dates.max()}")
    if weights_w.index.min() > risk_w.index.min() or weights_w.index.max() < risk_w.index.max():
        print(f"   ⚠️  Weights coverage: {weights_w.index.min()} → {weights_w.index.max()} vs Risk {risk_w.index.min()} → {risk_w.index.max()}")
    
    # Get stock columns (exclude non-stock columns)
    stock_cols = [col for col in weights_aligned.columns 
                 if not col.lower().startswith(('max_', 'risk_', 'regime', 'macro'))]
    
    print(f"   Applying throttle to {len(stock_cols)} stocks")
    
    # Apply macro risk budget as a multiplier
    throttled_weights = weights_aligned.copy()
    
    # Optional caps from ENV or defaults
    MAX_NAME_CAP = float(os.getenv('MAX_NAME_CAP', '0.10'))  # 10% per-name
    MAX_SECTOR_CAP = float(os.getenv('MAX_SECTOR_CAP', '0.30'))  # 30% per-sector

    # Build sector map from canonical scores file if available
    sector_map = {}
    try:
        scores_ref = pd.read_parquet("data/processed/scores.parquet")
        tcol = 'ticker' if 'ticker' in scores_ref.columns else ('Ticker' if 'Ticker' in scores_ref.columns else None)
        icol = 'Industry' if 'Industry' in scores_ref.columns else None
        if tcol and icol:
            tmp = scores_ref[[tcol, icol]].dropna().drop_duplicates(subset=[tcol])
            sector_map = dict(zip(tmp[tcol], tmp[icol]))
    except Exception:
        pass

    constraint_rows = []
    effective_budget = pd.Series(index=common_dates, dtype=float)
    for date in common_dates:
        risk_budget = float(risk_aligned.loc[date, 'Max_Equity_Exposure'])
        if shock_cap_series is not None and date in shock_cap_series.index:
            risk_budget = float(min(risk_budget, float(shock_cap_series.loc[date])))
        effective_budget.loc[date] = risk_budget
        # Ensure we have numeric weights and normalize to 1 before applying budget
        row = throttled_weights.loc[date, stock_cols].astype(float).fillna(0)
        row_sum = float(row.sum())
        if row_sum > 0:
            row = row / row_sum
            # Track pre-cap stats
            pre_scaled = row * risk_budget
            pre_name_caps = int((pre_scaled > MAX_NAME_CAP + 1e-12).sum())
            pre_sector_caps = 0
            if sector_map:
                pre_sectors = pd.Series({tic: sector_map.get(tic, 'Unknown') for tic in pre_scaled.index})
                pre_sector_totals = pre_scaled.groupby(pre_sectors).sum()
                pre_sector_caps = int((pre_sector_totals > MAX_SECTOR_CAP * risk_budget + 1e-12).sum())

            # Apply per-name cap iteratively
            target = risk_budget
            w = row.copy()
            for _ in range(5):
                # Scale to target
                s = w.sum()
                if s > 0:
                    w = w * (target / s)
                # Clip by name cap
                over = w > MAX_NAME_CAP
                excess = float((w[over] - MAX_NAME_CAP).sum()) if over.any() else 0.0
                w[over] = MAX_NAME_CAP
                free = w.index[~over]
                if excess > 1e-9 and len(free) > 0:
                    # Distribute excess proportionally to free names
                    add_base = w[free]
                    add_sum = float(add_base.sum())
                    if add_sum > 0:
                        w[free] = add_base + add_base / add_sum * excess
                    else:
                        # spread evenly
                        w[free] = w[free] + excess / len(free)
                else:
                    break
            # Apply sector caps if sector map available
            final_sector_caps = 0
            if sector_map:
                for _ in range(5):
                    # Compute sector totals
                    sectors = pd.Series({tic: sector_map.get(tic, 'Unknown') for tic in w.index})
                    sector_totals = w.groupby(sectors).sum()
                    # Exclude 'Unknown' from sector cap checks
                    sector_totals_checked = sector_totals.drop(labels=['Unknown'], errors='ignore')
                    breached = sector_totals_checked[sector_totals_checked > MAX_SECTOR_CAP * target]
                    if breached.empty:
                        break
                    final_sector_caps = len(breached)
                    # Scale down breached sectors
                    for sec, tot in breached.items():
                        idx = w.index[sectors == sec]
                        if float(tot) > 0:
                            factor = (MAX_SECTOR_CAP * target) / float(tot)
                            w[idx] = w[idx] * factor
                    # Re-scale to target while keeping name caps enforced
                    s = w.sum()
                    if s > 0:
                        w = w * (target / s)
                    w = w.clip(upper=MAX_NAME_CAP)
            throttled_weights.loc[date, stock_cols] = w
            capped_names_after = int((w > MAX_NAME_CAP - 1e-12).sum())
            constraint_rows.append({
                'date': date,
                'risk_budget': target,
                'pre_name_caps': pre_name_caps,
                'pre_sector_caps': pre_sector_caps,
                'final_sector_caps': final_sector_caps,
                'capped_names_after': capped_names_after,
                'total_exposure': float(w.sum())
            })
        else:
            # keep zeros when no weights available for this date
            throttled_weights.loc[date, stock_cols] = 0.0
    
    # Add risk budget info for tracking (effective after shock cap)
    if effective_budget is not None and len(effective_budget) == len(throttled_weights):
        throttled_weights['Applied_Risk_Budget'] = effective_budget
    else:
        throttled_weights['Applied_Risk_Budget'] = risk_aligned['Max_Equity_Exposure']
    throttled_weights['Total_Exposure'] = throttled_weights[stock_cols].sum(axis=1)
    
    # Save alignment diagnostics
    try:
        diag = pd.DataFrame(index=union_index)
        diag['weights_row_sum_pre_budget'] = weights_aligned[stock_cols].sum(axis=1)
        diag['risk_budget'] = risk_aligned['Max_Equity_Exposure']
        diag['total_exposure_post'] = throttled_weights[stock_cols].sum(axis=1)
        diag_file = "data/portfolio/overlay_alignment.csv"
        os.makedirs("data/portfolio", exist_ok=True)
        diag.to_csv(diag_file)
        print(f"🧪 Alignment diagnostics: {diag_file}")
    except Exception as e:
        print(f"⚠️  Could not write alignment diagnostics: {e}")

    # Save constraint summary
    try:
        if constraint_rows:
            cons_df = pd.DataFrame(constraint_rows).set_index('date').sort_index()
            cons_file = "data/portfolio/constraint_summary.csv"
            cons_df.to_csv(cons_file)
            print(f"🧪 Constraint summary: {cons_file}")
    except Exception as e:
        print(f"⚠️  Could not write constraint summary: {e}")

    return throttled_weights

def validate_final_weights(weights_df):
    """Validate the final portfolio weights"""
    
    print("\n📊 Portfolio Validation:")
    print("=" * 30)
    
    stock_cols = [col for col in weights_df.columns 
                 if not col.lower().startswith(('applied_', 'total_', 'max_', 'risk_'))]
    
    # Check weight constraints
    total_weights = weights_df[stock_cols].sum(axis=1)
    
    print(f"Total Exposure Statistics:")
    print(f"  Mean: {total_weights.mean():.3f}")
    print(f"  Min: {total_weights.min():.3f}")
    print(f"  Max: {total_weights.max():.3f}")
    print(f"  Std: {total_weights.std():.3f}")
    
    # Check for negative weights
    negative_weights = (weights_df[stock_cols] < 0).sum().sum()
    if negative_weights > 0:
        print(f"⚠️  Found {negative_weights} negative weights")
    
    # Top holdings
    print(f"\nTop Holdings (Latest Date):")
    latest_weights = weights_df[stock_cols].iloc[-1]
    top_holdings = latest_weights.nlargest(10)
    for ticker, weight in top_holdings.items():
        if weight > 0:
            print(f"  {ticker}: {weight:.3f} ({weight*100:.1f}%)")
    
    # Risk budget application
    if 'Applied_Risk_Budget' in weights_df.columns:
        latest_risk = weights_df['Applied_Risk_Budget'].iloc[-1]
        print(f"\nCurrent Risk Budget: {latest_risk:.3f} ({latest_risk*100:.0f}%)")

def run():
    """Main function to apply macro overlay"""
    print("🎚️  Macro Overlay Engine - Step 5")
    print("=" * 50)
    
    # Load engine weights
    weights_df = load_engine_weights()
    print(f"   Loaded weights: {len(weights_df)} dates × {len(weights_df.columns)} assets")
    
    # Load macro risk budget
    print("📊 Loading macro risk budget...")
    
    if not os.path.exists(RISK_FILE):
        print(f"❌ Risk budget not found: {RISK_FILE}")
        print("   Run macro_risk_controller.py first!")
        return
    
    risk_df = pd.read_parquet(RISK_FILE)
    print(f"   Loaded risk budget: {len(risk_df)} dates")
    
    # Apply macro throttle
    final_weights = apply_macro_throttle(weights_df, risk_df)
    
    # Validate results
    validate_final_weights(final_weights)
    
    # Save final weights to both portfolio and processed paths
    final_weights.to_parquet(OUT_FILE)
    print(f"\n✅ Final portfolio weights saved: {OUT_FILE}")
    try:
        final_weights.to_parquet(OUT_FILE_PROCESSED)
        print(f"✅ Final portfolio weights (dashboard) saved: {OUT_FILE_PROCESSED}")
    except Exception as e:
        print(f"⚠️  Could not save dashboard weights: {e}")

    # Save summary
    summary_file = OUT_FILE.replace('.parquet', '_summary.csv')
    summary = final_weights.describe()
    summary.to_csv(summary_file)
    print(f"📋 Portfolio summary: {summary_file}")

    # Debug export: last 5 rows with exposure and risk budget
    try:
        stock_cols = [c for c in final_weights.columns if not c.lower().startswith(('applied_','total_','max_','risk_'))]
        debug_df = final_weights.copy()
        debug_df['NonZero_Stocks'] = (debug_df[stock_cols].abs() > 0).sum(axis=1)
        debug_tail = debug_df.tail(5)
        debug_file = OUT_FILE.replace('.parquet', '_debug_tail.csv')
        debug_tail.to_csv(debug_file)
        nz_total = (final_weights[stock_cols].abs() > 0).sum().sum()
        print(f"🧪 Debug: non-zero weight entries total = {nz_total}, debug tail: {debug_file}")
    except Exception as e:
        print(f"⚠️  Debug export failed: {e}")

if __name__ == "__main__":
    run()
