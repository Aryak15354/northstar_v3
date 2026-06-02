import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cohesion.state_file_manager import StateFileManager

SCORES_FILE = "data/processed/scores.parquet"
VALUATION_FILE = "data/processed/valuation.parquet"
OUTPUT_FILE = "data/processed/opportunity_surface.parquet"

def load_latest_market_state():
    """Load latest market state safely"""
    try:
        state_manager = StateFileManager()
        market_df = state_manager.read_market_state()
        if not market_df.empty:
            return market_df.iloc[-1].to_dict()
    except:
        pass
    
    return {
        'risk_on_probability': 0.5,
        'allowed_exposure': 60,
        'macro_regime': 'neutral'
    }

def load_latest_confidence():
    """Load latest confidence safely"""
    try:
        conf_df = pd.read_parquet('data/processed/data_confidence.parquet')
        if not conf_df.empty:
            return conf_df.iloc[-1]['confidence']
    except:
        pass
    
    return 0.7

def main():
    print("🎯 Building Opportunity Surface...")
    
    # PHASE 3: OBEY THE MARKET STATE SPINE
    print("🧠 Loading Market State Authority...")
    market_state = load_latest_market_state()
    data_confidence = load_latest_confidence()
    
    risk_on_prob = market_state['risk_on_probability']
    allowed_exposure = market_state['allowed_exposure']
    
    print(f"   Risk-On Probability: {risk_on_prob:.1%}")
    print(f"   Allowed Exposure: {allowed_exposure:.1f}%")
    print(f"   Data Confidence: {data_confidence:.1%}")
    
    # Load scores and valuation data
    scores = pd.read_parquet(SCORES_FILE)
    valuation = pd.read_parquet(VALUATION_FILE)
    
    # Get latest valuation data per ticker
    valuation_latest = valuation.sort_values('date').groupby('ticker').tail(1)
    
    # Merge scores with valuation to get true_undervaluation
    df = scores.merge(valuation_latest[['ticker', 'true_undervaluation']], on='ticker', how='left')
    
    # Fill missing values with neutral scores
    df['true_undervaluation'] = df['true_undervaluation'].fillna(50)
    
    # Normalize score schema across legacy and canonical daily scorer outputs.
    if 'market_score' not in df.columns:
        score_source = next(
            (c for c in ['momentum_score', 'final_score', 'score', 'northstar_score'] if c in df.columns),
            None,
        )
        if score_source is None:
            df['market_score'] = 0.0
        else:
            df['market_score'] = pd.to_numeric(df[score_source], errors='coerce').fillna(0.0)
    else:
        df['market_score'] = pd.to_numeric(df['market_score'], errors='coerce').fillna(0.0)

    # PHASE 3: APPLY MARKET STATE AUTHORITY
    print("🧠 Applying Market State Authority to scores...")
    
    # Apply risk-on probability to all scores
    # Risk-off environment penalizes all scores
    df['northstar_score'] = df['northstar_score'] * risk_on_prob
    df['market_score'] = df['market_score'] * risk_on_prob
    
    # Apply data confidence penalty
    df['northstar_score'] = df['northstar_score'] * data_confidence
    df['market_score'] = df['market_score'] * data_confidence
    
    print(f"   Applied {risk_on_prob:.1%} risk-on penalty")
    print(f"   Applied {data_confidence:.1%} confidence penalty")

    # FIXED: Opportunity surface with percentile-based classification
    # Mispricing: true_undervaluation (higher = more undervalued)
    # Confirmation: market_score (higher = stronger trend/momentum)

    # Normalize to 0-1 scale
    mis_min = df["true_undervaluation"].min()
    mis_max = df["true_undervaluation"].max()
    df["mispricing"] = (df["true_undervaluation"] - mis_min) / (mis_max - mis_min) if mis_max > mis_min else 0.5

    conf_min = df["market_score"].min()
    conf_max = df["market_score"].max()
    df["confirmation"] = (df["market_score"] - conf_min) / (conf_max - conf_min) if conf_max > conf_min else 0.5

    # FIXED: Use percentile-based thresholds instead of fixed values
    mispricing_75th = df["mispricing"].quantile(0.75)
    mispricing_50th = df["mispricing"].quantile(0.50)
    mispricing_25th = df["mispricing"].quantile(0.25)
    
    confirmation_75th = df["confirmation"].quantile(0.75)
    confirmation_50th = df["confirmation"].quantile(0.50)
    confirmation_25th = df["confirmation"].quantile(0.25)
    
    print(f"📊 Mispricing thresholds: 25th={mispricing_25th:.3f}, 50th={mispricing_50th:.3f}, 75th={mispricing_75th:.3f}")
    print(f"📊 Confirmation thresholds: 25th={confirmation_25th:.3f}, 50th={confirmation_50th:.3f}, 75th={confirmation_75th:.3f}")

    # FIXED: Intelligent classification with balanced distribution
    def classify_opportunity(row):
        mispricing = row["mispricing"]
        confirmation = row["confirmation"]
        
        # Alpha Core: Top quartile in both dimensions (high mispricing + high confirmation)
        if mispricing >= mispricing_75th and confirmation >= confirmation_75th:
            return "Alpha Core"
        
        # Momentum Breakouts: High confirmation, moderate+ mispricing
        elif confirmation >= confirmation_75th and mispricing >= mispricing_50th:
            return "Momentum Breakouts"
        
        # Value Traps: High mispricing but weak confirmation
        elif mispricing >= mispricing_75th and confirmation <= confirmation_25th:
            return "Value Traps"
        
        # Secondary Alpha: Good scores in both but not top quartile
        elif mispricing >= mispricing_50th and confirmation >= mispricing_50th:
            return "Alpha Core"  # Expand alpha core to include more opportunities
        
        # Secondary Momentum: Strong confirmation with any mispricing
        elif confirmation >= confirmation_50th:
            return "Momentum Breakouts"  # Expand momentum category
        
        # Everything else is deterioration
        else:
            return "Deteriorations"

    df["opportunity_type"] = df.apply(classify_opportunity, axis=1)
    
    # Verify distribution is more balanced
    type_counts = df["opportunity_type"].value_counts()
    deterioration_pct = type_counts.get("Deteriorations", 0) / len(df) * 100
    
    print(f"📊 Classification distribution:")
    for opp_type, count in type_counts.items():
        pct = count / len(df) * 100
        print(f"   {opp_type}: {count} ({pct:.1f}%)")
    
    # If still too many deteriorations, apply more aggressive reclassification
    if deterioration_pct > 60:
        print("⚠️ Still too many deteriorations, applying secondary classification...")
        
        def classify_aggressive(row):
            mispricing = row["mispricing"]
            confirmation = row["confirmation"]
            
            # Use 60th percentiles for more inclusive classification
            mispricing_60th = df["mispricing"].quantile(0.60)
            confirmation_60th = df["confirmation"].quantile(0.60)
            
            if mispricing >= mispricing_60th and confirmation >= confirmation_60th:
                return "Alpha Core"
            elif confirmation >= confirmation_60th:
                return "Momentum Breakouts"
            elif mispricing >= mispricing_60th and confirmation <= confirmation_25th:
                return "Value Traps"
            elif mispricing >= mispricing_25th and confirmation >= confirmation_25th:
                return "Alpha Core"  # Very inclusive
            else:
                return "Deteriorations"
        
        df["opportunity_type"] = df.apply(classify_aggressive, axis=1)
        
        # Report new distribution
        type_counts = df["opportunity_type"].value_counts()
        print(f"📊 Aggressive classification distribution:")
        for opp_type, count in type_counts.items():
            pct = count / len(df) * 100
            print(f"   {opp_type}: {count} ({pct:.1f}%)")

    # Prepare output columns
    output_columns = ["ticker", "mispricing", "confirmation", "northstar_score", "opportunity_type"]
    if "Company Name" in df.columns:
        output_columns.insert(1, "Company Name")
    
    # Save
    result_df = df[output_columns].copy()
    result_df.to_parquet(OUTPUT_FILE, index=False)
    
    final_counts = result_df["opportunity_type"].value_counts()
    print(f"✅ Opportunity surface mapped: {len(result_df)} stocks")
    for opp_type, count in final_counts.items():
        pct = count / len(result_df) * 100
        print(f"   {opp_type}: {count} ({pct:.1f}%)")

if __name__ == "__main__":
    main()
