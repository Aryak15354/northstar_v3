#!/usr/bin/env python3
"""
🎯 CREATE SAMPLE DASHBOARD DATA
Creates sample data for testing the integrated dashboard

This script generates realistic sample data for:
- Shadow trading logs
- Market intelligence
- System health metrics
- Portfolio analytics
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

def create_sample_shadow_trading_data():
    """Create sample shadow trading data"""
    base_path = Path("data/live/shadow_trading")
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Create trading state
    trading_state = {
        "current_capital": 10500000,  # 1.05 Crore (5% gain)
        "initial_capital": 10000000,
        "positions": {
            "RELIANCE": {
                "weight": 0.15,
                "shares": 500,
                "avg_price": 2850.0,
                "last_updated": datetime.now().isoformat()
            },
            "TCS": {
                "weight": 0.12,
                "shares": 300,
                "avg_price": 4200.0,
                "last_updated": datetime.now().isoformat()
            },
            "HDFCBANK": {
                "weight": 0.10,
                "shares": 650,
                "avg_price": 1620.0,
                "last_updated": datetime.now().isoformat()
            },
            "INFY": {
                "weight": 0.08,
                "shares": 550,
                "avg_price": 1850.0,
                "last_updated": datetime.now().isoformat()
            },
            "ITC": {
                "weight": 0.07,
                "shares": 2000,
                "avg_price": 450.0,
                "last_updated": datetime.now().isoformat()
            }
        },
        "last_updated": datetime.now().isoformat()
    }
    
    with open(base_path / "trading_state.json", 'w') as f:
        json.dump(trading_state, f, indent=2)
    
    # Create daily logs for the past 30 days
    daily_logs = []
    current_date = datetime.now() - timedelta(days=30)
    cumulative_return = 1.0
    nifty_cumulative = 1.0
    
    for i in range(30):
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
            
        # Generate realistic returns
        northstar_return = np.random.normal(0.08, 1.2)  # Slightly positive bias
        nifty_return = np.random.normal(0.05, 1.0)
        
        cumulative_return *= (1 + northstar_return/100)
        nifty_cumulative *= (1 + nifty_return/100)
        
        daily_log = {
            "date": current_date.strftime('%Y-%m-%d'),
            "timestamp": current_date.isoformat(),
            "decisions": {
                "market_regime": np.random.choice(["risk_on", "risk_off", "neutral"]),
                "confidence": np.random.uniform(0.6, 0.9),
                "target_exposure": np.random.uniform(0.4, 0.8)
            },
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "action": "BUY",
                    "shares": 50,
                    "price": 2850 + np.random.normal(0, 50),
                    "value": 142500
                }
            ] if np.random.random() > 0.7 else [],
            "pnl": {
                "total_pnl": northstar_return * 100000,
                "total_pnl_pct": northstar_return,
                "portfolio_value": 10000000 * cumulative_return,
                "position_pnl": {
                    "RELIANCE": {"daily_pnl": np.random.normal(0, 5000)},
                    "TCS": {"daily_pnl": np.random.normal(0, 3000)},
                    "HDFCBANK": {"daily_pnl": np.random.normal(0, 4000)}
                }
            },
            "nifty_performance": {
                "daily_return": nifty_return,
                "price_change": nifty_return * 220,  # Assuming NIFTY ~22000
                "current_level": 22000 * nifty_cumulative
            }
        }
        
        daily_logs.append(daily_log)
        current_date += timedelta(days=1)
    
    # Save monthly log
    current_month = datetime.now().strftime('%Y%m')
    with open(base_path / f"daily_log_{current_month}.json", 'w') as f:
        json.dump(daily_logs, f, indent=2, default=str)
    
    print("✅ Sample shadow trading data created")

def create_sample_intelligence_data():
    """Create sample market intelligence data"""
    data_path = Path("data/processed")
    data_path.mkdir(parents=True, exist_ok=True)
    
    # Unified intelligence
    unified_intelligence = {
        "stance": "BULLISH",
        "conviction": 75.5,
        "target_exposure": 68.2,
        "risk_level": "MODERATE",
        "regime": "risk_on",
        "overall_confidence": 0.78,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(data_path / "unified_intelligence_state.json", 'w') as f:
        json.dump(unified_intelligence, f, indent=2)
    
    # Market state
    market_state_data = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "regime": "risk_on",
        "risk_on_probability": 0.72,
        "volatility": 0.18,
        "momentum": 0.65,
        "sentiment": 0.58
    }
    
    market_df = pd.DataFrame([market_state_data])
    market_df.to_parquet(data_path / "market_state.parquet")
    
    # Capital allocations
    allocations = {
        "allocations": {
            "Momentum": 0.18,
            "Mean Reversion": 0.15,
            "Quality Growth": 0.12,
            "Value": 0.10,
            "Low Vol": 0.08,
            "Sector Rotation": 0.07,
            "Macro Overlay": 0.05
        },
        "total_exposure": 0.75,
        "cash": 0.25,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(data_path / "capital_allocations.json", 'w') as f:
        json.dump(allocations, f, indent=2)
    
    # Portfolio analytics
    portfolio_analytics = {
        "total_positions": 45,
        "total_exposure": 0.681,
        "sector_count": 8,
        "risk_score": 0.24,
        "sharpe_ratio": 1.85,
        "max_drawdown": -0.08,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(data_path / "portfolio_analytics.json", 'w') as f:
        json.dump(portfolio_analytics, f, indent=2)
    
    print("✅ Sample intelligence data created")

def create_sample_health_data():
    """Create sample system health data"""
    data_path = Path("data/processed")
    intelligence_path = Path("data/intelligence")
    intelligence_path.mkdir(parents=True, exist_ok=True)
    
    # Pulse state
    pulse_state = {
        "pulse_intensity": 2.8,
        "market_stress": 0.25,
        "volatility_regime": "normal",
        "timestamp": datetime.now().isoformat()
    }
    
    with open(data_path / "pulse_state.json", 'w') as f:
        json.dump(pulse_state, f, indent=2)
    
    # System stress
    system_stress = {
        "system_stress": 0.35,
        "memory_usage": 0.68,
        "cpu_usage": 0.45,
        "data_quality": 0.92,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(data_path / "system_stress.json", 'w') as f:
        json.dump(system_stress, f, indent=2)
    
    # NO_EDGE state
    no_edge_data = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "state": "NORMAL",
        "edge_strength": 0.68,
        "confidence": 0.82,
        "last_trigger": None
    }
    
    no_edge_df = pd.DataFrame([no_edge_data])
    no_edge_df.to_parquet(intelligence_path / "no_edge_state.parquet")
    
    print("✅ Sample health data created")

def main():
    """Create all sample data"""
    print("🎯 CREATING SAMPLE DASHBOARD DATA")
    print("=" * 50)
    
    create_sample_shadow_trading_data()
    create_sample_intelligence_data()
    create_sample_health_data()
    
    print("\n✅ All sample data created successfully!")
    print("\nYou can now launch the dashboard with:")
    print("python scripts/launch_integrated_dashboard.py")

if __name__ == "__main__":
    main()