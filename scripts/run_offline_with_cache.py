#!/usr/bin/env python3
"""
Run options engine using only cached/historical option chains (offline mode)

This script demonstrates the system working without live API calls,
using previously cached option chain data.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, date
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.config_loader import get_config
from src.options.options_regime_detector import RegimeDetector
from src.options.strategy_generator import StrategyGenerator
from src.options.trade_eligibility_validator import TradeEligibilityValidator


def load_cached_chains():
    """Load all available cached option chains"""
    cache_dir = Path("data/options/chains_cache")
    historical_dir = Path("data/options/historical")
    
    chains = {}
    
    # Load from cache (most recent)
    if cache_dir.exists():
        for underlying in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            pattern = f"{underlying}_*.parquet"
            files = sorted(cache_dir.glob(pattern), reverse=True)
            if files:
                try:
                    df = pd.read_parquet(files[0])
                    if "date" in df.columns:
                        d = pd.to_datetime(df["date"], errors="coerce")
                        if d.notna().any():
                            latest = d.max()
                            df = df.loc[d == latest].copy()
                    chains[underlying] = df
                    print(f"✅ Loaded {underlying}: {len(df)} contracts from {files[0].name}")
                except Exception as e:
                    print(f"❌ Failed to load {underlying}: {e}")
    
    # Load from historical
    if historical_dir.exists():
        for file in historical_dir.glob("*_option_chains.parquet"):
            underlying = file.stem.replace("_option_chains", "").upper()
            if underlying not in chains:
                try:
                    df = pd.read_parquet(file)
                    if "date" in df.columns:
                        d = pd.to_datetime(df["date"], errors="coerce")
                        if d.notna().any():
                            latest = d.max()
                            df = df.loc[d == latest].copy()
                    chains[underlying] = df
                    print(f"✅ Loaded {underlying}: {len(df)} contracts from historical")
                except Exception as e:
                    print(f"❌ Failed to load {underlying} from historical: {e}")
    
    return chains


def estimate_atm_iv(chain: pd.DataFrame) -> float:
    """Estimate ATM implied volatility"""
    if chain.empty or 'iv' not in chain.columns:
        return 0.15  # Default 15%
    
    # Get ATM options (closest to underlying price)
    if 'underlying_price' in chain.columns and 'strike' in chain.columns:
        spot = chain['underlying_price'].iloc[0]
        chain['distance'] = abs(chain['strike'] - spot)
        atm = chain.nsmallest(10, 'distance')
        iv = atm['iv'].median()
        return float(iv) if pd.notna(iv) else 0.15
    
    # Fallback: median IV
    iv = chain['iv'].median()
    return float(iv) if pd.notna(iv) else 0.15


def main():
    print("\n" + "="*70)
    print("📊 OFFLINE OPTIONS ENGINE - CACHED DATA MODE")
    print("="*70 + "\n")
    
    # Load config
    config = get_config()
    
    # Initialize components
    regime_detector = RegimeDetector(config)
    strategy_generator = StrategyGenerator(config)
    eligibility_validator = TradeEligibilityValidator(config)
    
    print("🔧 Components initialized\n")
    
    # Load cached chains
    print("📁 Loading cached option chains...")
    chains = load_cached_chains()
    
    if not chains:
        print("\n❌ No cached chains found!")
        print("   Run the system once during market hours to cache chains")
        return 1
    
    print(f"\n✅ Loaded {len(chains)} underlyings\n")
    
    # Process each underlying
    results = []
    
    for underlying, chain in chains.items():
        print("="*70)
        print(f"📈 Processing: {underlying}")
        print("="*70)
        
        # Estimate IV
        iv = estimate_atm_iv(chain)
        print(f"  IV: {iv:.2%}")
        
        # Create IV series (mock historical data)
        iv_series = pd.Series([iv * 0.95, iv * 0.98, iv], 
                             index=pd.date_range(end=datetime.now(), periods=3, freq='D'))
        
        # Detect regime
        regime_state = regime_detector.detect_regime(
            chain, 
            iv_series, 
            underlying_regime="NORMAL"
        )
        
        print(f"  Regime: {regime_state.regime.value}")
        print(f"  IV Rank: {regime_state.metrics.iv_rank:.2%}")
        print(f"  Confidence: {regime_state.confidence:.2%}")
        
        # Generate strategy
        strategy = strategy_generator.generate_strategy(
            regime_state.regime,
            chain,
            underlying=underlying
        )
        
        if strategy and strategy.is_valid:
            print(f"\n  ✅ Strategy Generated: {strategy.strategy_type.value}")
            print(f"     Max Loss: ₹{strategy.max_loss:,.0f}")
            print(f"     Max Profit: ₹{strategy.max_profit:,.0f}")
            print(f"     Net Credit/Debit: ₹{strategy.net_credit_debit:,.0f}")
            print(f"     Risk/Reward: {abs(strategy.max_profit / strategy.max_loss):.2f}")
            
            # Validate eligibility
            eligibility = eligibility_validator.validate_trade(
                strategy,
                regime_state,
                chain
            )
            
            if eligibility.is_eligible:
                print(f"     ✅ TRADE ELIGIBLE")
                results.append({
                    "underlying": underlying,
                    "strategy": strategy.strategy_type.value,
                    "regime": regime_state.regime.value,
                    "max_loss": strategy.max_loss,
                    "eligible": True
                })
            else:
                print(f"     ❌ TRADE REJECTED")
                print(f"        Violations: {', '.join(eligibility.violations)}")
                results.append({
                    "underlying": underlying,
                    "strategy": strategy.strategy_type.value,
                    "regime": regime_state.regime.value,
                    "max_loss": strategy.max_loss,
                    "eligible": False,
                    "violations": eligibility.violations
                })
        else:
            print(f"\n  ❌ No valid strategy generated")
            results.append({
                "underlying": underlying,
                "strategy": None,
                "regime": regime_state.regime.value,
                "eligible": False
            })
        
        print()
    
    # Summary
    print("="*70)
    print("📊 SUMMARY")
    print("="*70)
    print(f"  Total Underlyings: {len(results)}")
    print(f"  Strategies Generated: {sum(1 for r in results if r['strategy'])}")
    print(f"  Eligible Trades: {sum(1 for r in results if r.get('eligible'))}")
    print()
    
    # Save results
    output_file = Path("data/options/offline_data/results/analysis.json")
    output_file.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "results": results
    }, indent=2))
    
    print(f"💾 Results saved to: {output_file}")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
