#!/usr/bin/env python3
"""
🧠 NORTHSTAR API SERVER
FastAPI backend that serves Northstar data to the React terminal

This extracts the brain from Streamlit and makes it a proper data service.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List
import uvicorn

# Add src to path and get the project root
PROJECT_ROOT_PATH = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH))
PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent.parent)

app = FastAPI(
    title="Northstar API",
    description="Hedge fund intelligence API",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Northstar API",
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/snapshot")
async def get_snapshot() -> Dict[str, Any]:
    """
    Get the unified dashboard snapshot
    
    This is the single source of truth for all dashboard data
    """
    try:
        snapshot_path = os.path.join(PROJECT_ROOT, "data/processed/cache/dashboard_snapshot.parquet")
        
        if os.path.exists(snapshot_path):
            df = pd.read_parquet(snapshot_path)
            if len(df) > 0:
                # Get the first row as a dictionary
                snapshot_raw = df.iloc[0].to_dict()
                
                # Clean the data for JSON serialization
                snapshot = {}
                for key, value in snapshot_raw.items():
                    try:
                        snapshot[key] = clean_for_json(value)
                    except Exception as e:
                        print(f"Error cleaning key {key}: {e}")
                        snapshot[key] = str(value)  # Fallback to string
                
                return {
                    "success": True,
                    "data": snapshot,
                    "timestamp": datetime.now().isoformat(),
                    "source": "parquet"
                }
            raise HTTPException(
                status_code=503,
                detail=f"Snapshot file exists but contains no rows: {snapshot_path}",
            )
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_path}")
            
    except Exception as e:
        print(f"Snapshot error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading snapshot: {str(e)}")

@app.get("/timeseries/{name}")
async def get_timeseries(name: str, limit: int = 500) -> Dict[str, Any]:
    """
    Get time series data for charts
    
    Args:
        name: Name of the time series (e.g., 'pnl', 'market_state', 'volatility')
        limit: Number of recent records to return
    """
    try:
        # Map common names to actual file paths
        file_mapping = {
            'pnl': os.path.join(PROJECT_ROOT, 'data/portfolio/pnl_on_paper.parquet'),
            'market_state': os.path.join(PROJECT_ROOT, 'data/processed/market_state.parquet'),
            'volatility': os.path.join(PROJECT_ROOT, 'data/processed/volatility_state.parquet'),
            'portfolio_weights': os.path.join(PROJECT_ROOT, 'data/processed/portfolio_weights.parquet'),
            'strategy_beliefs': os.path.join(PROJECT_ROOT, 'data/processed/strategy_beliefs.parquet'),
            'strategy_performance': os.path.join(PROJECT_ROOT, 'data/processed/strategy_performance.parquet')
        }
        
        file_path = file_mapping.get(name, f"data/processed/{name}.parquet")
        
        if os.path.exists(file_path):
            df = pd.read_parquet(file_path)
            
            # Get the most recent records
            df_recent = df.tail(limit)
            
            # Convert to records format for JSON
            records = df_recent.to_dict("records")
            
            # Clean for JSON serialization
            records = [clean_for_json(record) for record in records]
            
            return {
                "success": True,
                "data": records,
                "count": len(records),
                "name": name,
                "timestamp": datetime.now().isoformat()
            }
        raise HTTPException(status_code=404, detail=f"Timeseries artifact not found: {file_path}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading timeseries {name}: {str(e)}")

@app.get("/strategies")
async def get_strategies() -> Dict[str, Any]:
    """Get strategy information including beliefs, regret, and allocations"""
    try:
        strategies_data = {}
        
        # Load strategy beliefs
        beliefs_path = os.path.join(PROJECT_ROOT, 'data/processed/strategy_beliefs.parquet')
        if os.path.exists(beliefs_path):
            beliefs_df = pd.read_parquet(beliefs_path)
            if not beliefs_df.empty:
                latest_beliefs = beliefs_df.iloc[-1].to_dict()
                strategies_data['beliefs'] = clean_for_json(latest_beliefs)
        
        # Load strategy regret
        regret_path = os.path.join(PROJECT_ROOT, 'data/processed/strategy_regret.parquet')
        if os.path.exists(regret_path):
            regret_df = pd.read_parquet(regret_path)
            if not regret_df.empty:
                latest_regret = regret_df.iloc[-1].to_dict()
                strategies_data['regret'] = clean_for_json(latest_regret)
        
        # Load capital allocations
        capital_path = os.path.join(PROJECT_ROOT, 'data/processed/capital_allocations.json')
        if os.path.exists(capital_path):
            with open(capital_path, 'r') as f:
                capital_data = json.load(f)
            strategies_data['capital'] = capital_data
        
        if not strategies_data:
            raise HTTPException(status_code=404, detail="No real strategy artifacts available")
        
        return {
            "success": True,
            "data": strategies_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading strategies: {str(e)}")

@app.get("/portfolio/holdings")
async def get_portfolio_holdings(limit: int = 50) -> Dict[str, Any]:
    """Get current portfolio holdings"""
    try:
        weights_path = os.path.join(PROJECT_ROOT, 'data/processed/portfolio_weights.parquet')
        
        if os.path.exists(weights_path):
            df = pd.read_parquet(weights_path)
            
            # Get weight column
            weight_col = 'final_weight' if 'final_weight' in df.columns else 'weight'
            
            # Sort by weight and get top holdings
            top_holdings = df.nlargest(limit, weight_col)
            
            # Convert to records
            holdings = top_holdings.to_dict('records')
            holdings = [clean_for_json(holding) for holding in holdings]
            
            return {
                "success": True,
                "data": holdings,
                "count": len(holdings),
                "timestamp": datetime.now().isoformat()
            }
        raise HTTPException(status_code=404, detail=f"Portfolio holdings artifact not found: {weights_path}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading holdings: {str(e)}")

@app.get("/chart/pnl")
async def get_pnl_chart_data() -> Dict[str, Any]:
    """Get P&L chart data optimized for visualization"""
    try:
        chart_data_path = os.path.join(PROJECT_ROOT, 'data/processed/cache/pnl_chart_data.json')
        
        if os.path.exists(chart_data_path):
            with open(chart_data_path, 'r') as f:
                chart_data = json.load(f)
            
            return {
                "success": True,
                "data": chart_data,
                "timestamp": datetime.now().isoformat(),
                "source": "cached"
            }
        else:
            # Generate chart data on the fly
            pnl_path = os.path.join(PROJECT_ROOT, 'data/portfolio/pnl_on_paper.parquet')
            if os.path.exists(pnl_path):
                df = pd.read_parquet(pnl_path)
                
                # Sample data for chart (every 5th day)
                chart_df = df.iloc[::5].copy()
                chart_df['Date'] = pd.to_datetime(chart_df['Date'])
                
                # Calculate metrics
                initial_equity = chart_df['Equity'].iloc[0]
                chart_df['cumulative_return'] = (chart_df['Equity'] / initial_equity - 1) * 100
                
                # Calculate drawdowns
                peak = chart_df['Equity'].expanding().max()
                chart_df['drawdown'] = (chart_df['Equity'] / peak - 1) * 100
                
                chart_data = {
                    'dates': chart_df['Date'].dt.strftime('%Y-%m-%d').tolist(),
                    'equity': chart_df['Equity'].round(0).tolist(),
                    'cumulative_return': chart_df['cumulative_return'].round(2).tolist(),
                    'drawdown': chart_df['drawdown'].round(2).tolist(),
                    'metadata': {
                        'start_date': chart_df['Date'].iloc[0].strftime('%Y-%m-%d'),
                        'end_date': chart_df['Date'].iloc[-1].strftime('%Y-%m-%d'),
                        'initial_equity': float(initial_equity),
                        'final_equity': float(chart_df['Equity'].iloc[-1]),
                        'total_return': float(chart_df['cumulative_return'].iloc[-1]),
                        'max_drawdown': float(chart_df['drawdown'].min()),
                        'data_points': len(chart_df)
                    }
                }
                
                return {
                    "success": True,
                    "data": chart_data,
                    "timestamp": datetime.now().isoformat(),
                    "source": "generated"
                }
            raise HTTPException(status_code=404, detail=f"P&L artifact not found: {pnl_path}")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading P&L chart data: {str(e)}")

@app.get("/health")
async def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health check"""
    try:
        health_data = {
            "api_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "data_sources": {},
            "overall_grade": "A"
        }
        
        # Check key data files
        key_files = {
            "snapshot": os.path.join(PROJECT_ROOT, "data/processed/cache/dashboard_snapshot.parquet"),
            "market_state": os.path.join(PROJECT_ROOT, "data/processed/market_state.parquet"),
            "portfolio_weights": os.path.join(PROJECT_ROOT, "data/processed/portfolio_weights.parquet"),
            "pnl": os.path.join(PROJECT_ROOT, "data/portfolio/pnl_on_paper.parquet"),
            "strategy_beliefs": os.path.join(PROJECT_ROOT, "data/processed/strategy_beliefs.parquet")
        }
        
        healthy_count = 0
        for name, path in key_files.items():
            if os.path.exists(path):
                try:
                    df = pd.read_parquet(path)
                    age_hours = 0  # Assume fresh for now
                    health_data["data_sources"][name] = {
                        "status": "healthy",
                        "records": len(df),
                        "age_hours": age_hours
                    }
                    healthy_count += 1
                except Exception as e:
                    health_data["data_sources"][name] = {
                        "status": "error",
                        "error": str(e)
                    }
            else:
                health_data["data_sources"][name] = {
                    "status": "missing"
                }
        
        # Calculate overall grade
        health_ratio = healthy_count / len(key_files)
        if health_ratio > 0.8:
            health_data["overall_grade"] = "A"
        elif health_ratio > 0.6:
            health_data["overall_grade"] = "B"
        elif health_ratio > 0.4:
            health_data["overall_grade"] = "C"
        else:
            health_data["overall_grade"] = "D"
        
        health_data["healthy_sources"] = healthy_count
        health_data["total_sources"] = len(key_files)
        
        return {
            "success": True,
            "data": health_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking health: {str(e)}")

# --------------------------
# UTILITY FUNCTIONS
# --------------------------

def clean_for_json(obj):
    """Clean object for JSON serialization"""
    import numpy as np
    
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return [clean_for_json(item) for item in obj.tolist()]
    elif pd.isna(obj):
        return None
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, (int, float)):
        # Handle NaN and infinity
        if pd.isna(obj) or obj == float('inf') or obj == float('-inf'):
            return None
        return obj
    elif isinstance(obj, (str, bool)):
        return obj
    elif hasattr(obj, 'item'):  # numpy scalars
        try:
            return obj.item()
        except:
            return str(obj)
    elif hasattr(obj, 'to_dict'):  # pandas objects
        try:
            return clean_for_json(obj.to_dict())
        except:
            return str(obj)
    elif hasattr(obj, '__dict__'):  # custom objects
        try:
            return clean_for_json(obj.__dict__)
        except:
            return str(obj)
    else:
        return str(obj)

if __name__ == "__main__":
    print("🚀 Starting Northstar API Server...")
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
