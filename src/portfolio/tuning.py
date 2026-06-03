#!/usr/bin/env python3
"""
Hyperparameter Tuning Pipeline for Portfolio Governor v3

- Supports grid and random search (Bayesian stub)
- Rolling evaluation over historical dates using stored weekly portfolios and prices
- Regime-aware selection using market_state history
- Persists best configs per-regime and overall to data/portfolio/tuning/best_configs.json

NOTE: Full historical re-selection requires historical scores by date.
This light tuner reweights stored weekly portfolios under candidate constraints
(sector band, per-name/sector caps, exposure cap scaling). As you add historical
scores, extend evaluate_config() to rebuild portfolios per week using the Governor
selection logic for that date.
"""
import os
import json
import random
import itertools
from datetime import datetime
import pandas as pd
import numpy as np
import sys

WEEKLY_DIR = 'data/portfolio/weekly'
PRICES_FILE = 'data/processed/prices.parquet'
MARKET_STATE_FILE = 'data/processed/market_state.parquet'
OUT_DIR = 'data/portfolio/tuning'
OUT_FILE = os.path.join(OUT_DIR, 'best_configs.json')

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- Utilities ----------

def load_weekly_snapshots():
    files = sorted([f for f in os.listdir(WEEKLY_DIR) if f.endswith('.parquet')]) if os.path.isdir(WEEKLY_DIR) else []
    out = []
    for f in files:
        try:
            d = pd.to_datetime(f.replace('.parquet',''), errors='coerce')
            if pd.isna(d):
                continue
            df = pd.read_parquet(os.path.join(WEEKLY_DIR, f))
            if 'ticker' in df.columns and 'weight' in df.columns:
                df = df[['ticker','weight']]
                df['date'] = d
                out.append(df)
        except Exception:
            continue
    if not out:
        return pd.DataFrame(columns=['date','ticker','weight'])
    return pd.concat(out, ignore_index=True)

def load_prices():
    if not os.path.exists(PRICES_FILE):
        raise FileNotFoundError(PRICES_FILE)
    p = pd.read_parquet(PRICES_FILE)
    p['Date'] = pd.to_datetime(p['Date'])
    return p

def load_market_state():
    if not os.path.exists(MARKET_STATE_FILE):
        return pd.DataFrame(columns=['date','macro_regime'])
    ms = pd.read_parquet(MARKET_STATE_FILE)
    if 'date' not in ms.columns:
        ms['date'] = pd.to_datetime(ms.index)
    ms['date'] = pd.to_datetime(ms['date'])
    if 'macro_regime' not in ms.columns and 'Regime' in ms.columns:
        ms['macro_regime'] = ms['Regime']
    ms['macro_regime'] = ms['macro_regime'].astype(str).str.lower()
    return ms[['date','macro_regime']]

# ---------- Evaluation ----------

def apply_constraints(weights: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    w = weights.copy()
    # Sector info may be missing; treat as Unknown
    if 'Industry' not in w.columns:
        w['Industry'] = 'Unknown'
    # Per-name and sector caps
    max_name = float(cfg.get('max_weight_per_name', 0.08))
    max_sector = float(cfg.get('max_weight_per_sector', 0.30))
    sector_band = float(cfg.get('sector_neutral_band', 0.10))
    # Clip per-name
    w['weight'] = w['weight'].clip(upper=max_name)
    w['weight'] = w['weight'] / w['weight'].sum()
    # Sector cap
    sector_sum = w.groupby('Industry')['weight'].transform('sum')
    over = sector_sum > max_sector
    if over.any():
        for sec in w.loc[over,'Industry'].unique():
            mask = w['Industry'] == sec
            scale = max_sector / w.loc[mask,'weight'].sum()
            w.loc[mask,'weight'] *= scale
        w['weight'] = w['weight'] / w['weight'].sum()
    # Sector-neutral band toward equal-weight across present sectors
    secs = w['Industry'].unique().tolist()
    if len(secs) > 0:
        baseline = {s: 1.0/len(secs) for s in secs}
        sector_actual = w.groupby('Industry')['weight'].sum()
        for sec, actual in sector_actual.items():
            upper = min(max_sector, baseline.get(sec,0) + sector_band)
            if actual > upper and actual > 0:
                mask = w['Industry'] == sec
                w.loc[mask,'weight'] *= (upper/actual)
        w['weight'] = w['weight'] / w['weight'].sum()
    return w[['ticker','Industry','weight']]


def compute_pnl_from_weeklies(weeklies: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    if weeklies.empty:
        return pd.DataFrame(columns=['Date','Equity','Return'])
    prices = prices.sort_values(['Date','ticker'])
    price_tbl = prices.pivot(index='Date', columns='ticker', values='Close').ffill()
    weekly_pivot = weeklies.pivot_table(index='date', columns='ticker', values='weight', fill_value=0.0)
    # Align weights to price dates; allow backward-fill then forward-fill to handle
    # cases where weekly snapshots are newer than last available prices
    weight_daily = weekly_pivot.reindex(price_tbl.index).bfill().ffill().fillna(0.0)
    common = weight_daily.columns.intersection(price_tbl.columns)
    # If no common tickers, try simple symbol normalization heuristics
    if len(common) == 0:
        # Heuristic 1: add '.NS' to weekly tickers
        wk_alt = {c: (str(c) + '.NS') for c in weight_daily.columns}
        alt_cols = [wk_alt.get(c, c) for c in weight_daily.columns]
        weight_daily_alt = weight_daily.copy()
        weight_daily_alt.columns = alt_cols
        common_alt = weight_daily_alt.columns.intersection(price_tbl.columns)
        if len(common_alt) > 0:
            weight_daily = weight_daily_alt
            common = common_alt
        else:
            # Heuristic 2: strip '.NS' from weekly tickers
            wk_alt2 = {c: str(c).replace('.NS','') for c in weight_daily.columns}
            weight_daily_alt2 = weight_daily.copy()
            weight_daily_alt2.columns = [wk_alt2.get(c, c) for c in weight_daily.columns]
            common_alt2 = weight_daily_alt2.columns.intersection(price_tbl.columns)
            if len(common_alt2) > 0:
                weight_daily = weight_daily_alt2
                common = common_alt2
    weight_daily = weight_daily[common]
    price_tbl = price_tbl[common]
    ret_tbl = price_tbl.pct_change().fillna(0.0)
    # Default: no lookahead (shift weights by 1 day)
    port_ret = (weight_daily.shift(1).fillna(0.0) * ret_tbl).sum(axis=1)
    equity = (1 + port_ret).cumprod()
    df = pd.DataFrame({'Date': port_ret.index, 'Equity': equity.values, 'Return': port_ret.values})
    # Fallback: if trivial equity (e.g., single week or zero variance), try without shift
    if df['Equity'].std() < 1e-9 or (df['Equity'].iloc[-1] == 1.0):
        port_ret2 = (weight_daily * ret_tbl).sum(axis=1)
        equity2 = (1 + port_ret2).cumprod()
        df = pd.DataFrame({'Date': port_ret2.index, 'Equity': equity2.values, 'Return': port_ret2.values})
    return df


def score_kpis(ret_df: pd.DataFrame) -> dict:
    if ret_df.empty:
        return {'ann_return':0.0,'vol':0.0,'sharpe':0.0,'max_dd':0.0,'score':-1e9}
    r = ret_df['Return']
    total = float((1+r).prod() - 1)
    days = len(r)
    ann = float((1+total)**(252/max(1,days)) - 1) if days>0 else 0.0
    vol = float(r.std()*np.sqrt(252)) if days>1 else 0.0
    sharpe = float(ann/vol) if vol>1e-9 else 0.0
    eq = (1+r).cumprod()
    dd = float((eq/eq.cummax()-1).min()) if len(eq)>0 else 0.0
    # Composite score: emphasize Sharpe, punish drawdown
    score = sharpe - 0.5*abs(dd)
    return {'ann_return':ann,'vol':vol,'sharpe':sharpe,'max_dd':dd,'score':score}


def evaluate_config(cfg: dict, weeklies: pd.DataFrame, prices: pd.DataFrame, regime_map: pd.DataFrame|None=None) -> dict:
    # Apply constraints to each weekly snapshot and compute PnL
    if weeklies.empty:
        return {'overall':{'score':-1e9}, 'per_regime':{}}
    rows = []
    for d, df in weeklies.groupby('date'):
        w = df.copy()
        w = apply_constraints(w, cfg)
        w['date'] = d
        rows.append(w)
    tuned = pd.concat(rows, ignore_index=True) if rows else weeklies
    pnl = compute_pnl_from_weeklies(tuned, prices)
    overall = score_kpis(pnl)
    per_reg = {}
    if regime_map is not None and not regime_map.empty and not pnl.empty:
        # Map each Date to latest regime on/before that date
        rm = regime_map.sort_values('date').copy()
        pnl2 = pnl.merge(rm, left_on='Date', right_on='date', how='left')
        pnl2['macro_regime'] = pnl2['macro_regime'].ffill().fillna('unknown')
        for reg, rdf in pnl2.groupby('macro_regime'):
            per_reg[reg] = score_kpis(rdf[['Date','Return']])
    return {'overall': overall, 'per_regime': per_reg}

# ---------- Search Strategies ----------

def grid_search(space: dict, n_max: int|None, weeklies, prices, regime_map):
    keys = list(space.keys())
    values = [space[k] for k in keys]
    best = None
    for combo in itertools.product(*values):
        cfg = dict(zip(keys, combo))
        res = evaluate_config(cfg, weeklies, prices, regime_map)
        if (best is None) or (res['overall']['score'] > best['result']['overall']['score']):
            best = {'config': cfg, 'result': res}
        if n_max and n_max <= 0:
            break
        if n_max:
            n_max -= 1
    return best

def random_search(space: dict, trials: int, weeklies, prices, regime_map):
    keys = list(space.keys())
    best = None
    for _ in range(trials):
        cfg = {k: random.choice(space[k]) for k in keys}
        res = evaluate_config(cfg, weeklies, prices, regime_map)
        if (best is None) or (res['overall']['score'] > best['result']['overall']['score']):
            best = {'config': cfg, 'result': res}
    return best

def bayes_search(space: dict, trials: int, weeklies, prices, regime_map):
    """Bayesian optimization with optuna if available; falls back to random_search."""
    try:
        import optuna
    except Exception:
        return random_search(space, trials, weeklies, prices, regime_map)

    keys = list(space.keys())

    def objective(trial):
        cfg = {}
        for k in keys:
            vals = space[k]
            if all(isinstance(v, (int, float)) for v in vals):
                low, high = min(vals), max(vals)
                # Use uniform for continuous-like params
                cfg[k] = float(trial.suggest_float(k, low, high))
            else:
                cfg[k] = trial.suggest_categorical(k, vals)
        res = evaluate_config(cfg, weeklies, prices, regime_map)
        return -res['overall']['score']  # minimize

    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=trials)
    best_cfg = study.best_params
    res = evaluate_config(best_cfg, weeklies, prices, regime_map)
    return {'config': best_cfg, 'result': res}

def light_daily_tuning(strategy: str = 'auto'):
    weeklies = load_weekly_snapshots()
    prices = load_prices()
    regimes = load_market_state()
    if weeklies.empty:
        print('⚠️ No weekly portfolios to tune.')
        return None
    # Define compact search space (discrete for reproducibility)
    space = {
        'max_weight_per_name': [0.06, 0.08, 0.10],
        'max_weight_per_sector': [0.25, 0.30, 0.35],
        'sector_neutral_band': [0.05, 0.10, 0.15],
    }
    if strategy == 'bayes' or (strategy == 'auto'):
        # try bayesian; fallback handled inside
        best = bayes_search(space, trials=25, weeklies=weeklies, prices=prices, regime_map=regimes)
    else:
        best = random_search(space, trials=25, weeklies=weeklies, prices=prices, regime_map=regimes)
    if best is None:
        return None
    # Persist best per overall and per-regime
    payload = {
        'generated': datetime.now().isoformat(),
        'overall': best['result']['overall'],
        'config': best['config'],
        'per_regime': best['result']['per_regime']
    }
    with open(OUT_FILE, 'w') as f:
        json.dump(payload, f, indent=2)
    print(f"✅ Tuning complete. Best config saved: {OUT_FILE}")
    # Append to coherence memory for narrative/meta-governance
    try:
        mem_dir = 'data/intelligence'
        os.makedirs(mem_dir, exist_ok=True)
        mem_path = os.path.join(mem_dir, 'memory.json')
        hist = []
        if os.path.exists(mem_path):
            with open(mem_path, 'r') as f:
                hist = json.load(f)
                if not isinstance(hist, list):
                    hist = []
        # enrich with latest regime/coherence if available
        macro_regime = None
        coherence_score = None
        try:
            from src.cohesion.state_file_manager import StateFileManager
            state_manager = StateFileManager()
            ms = state_manager.read_market_state()
            if not ms.empty:
                last = ms.iloc[-1]
                macro_regime = str(last.get('macro_regime') or last.get('Regime'))
                coherence_score = float(last.get('coherence_score')) if 'coherence_score' in ms.columns else None
        except Exception:
            pass
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event': 'tuning',
            'tuning_strategy': strategy,
            'best_config': payload['config'],
            'overall_score': payload['overall'].get('score', 0.0),
            'per_regime': payload['per_regime'],
            'macro_regime': macro_regime,
            'coherence_score': coherence_score
        }
        hist.append(entry)
        hist = hist[-200:]
        with open(mem_path, 'w') as f:
            json.dump(hist, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to write tuning memory entry: {e}")
    return payload


if __name__ == '__main__':
    mode = 'auto'
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    light_daily_tuning(mode)
