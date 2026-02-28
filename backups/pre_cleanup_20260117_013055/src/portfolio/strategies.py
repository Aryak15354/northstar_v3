#!/usr/bin/env python3
"""
Strategy Lab: simple alternative portfolio constructors for cross-comparison

Strategies implemented (lightweight, snapshot- and price-based):
- northstar: rank by northstar_score (same selector as governor core, but simplified)
- equal_weight_top: top N by northstar_score, equal-weighted
- low_vol: lowest realized_vol among liquid names
- liquidity_weighted: weight by dollar_volume among top N northstar_score
- mom_6m: 6-month price momentum

# Temporal protection
from src.intelligence.temporal_signal_engine import TemporalSignalEngine
from src.intelligence.temporal_guard import TemporalGuard
- mom_12m: 12-month price momentum
- mom_vol_adj: momentum divided by realized volatility
- quality_tilt: overweight high quality_score when available
- value_tilt: overweight high value_score when available
- sector_neutral_eq: equal-weight within top sectors by northstar_score
- risk_parity_vol: inverse-vol weights across selected names
- regime_conditional: momentum in risk-on regimes, value in risk-off
- mom_3m_6m_12m: composite momentum across 3/6/12 months
- dual_momentum: absolute + relative momentum filter
- quality_value_combo: composite of quality and value
- sector_tilt_mom: momentum within top sectors by northstar_score
- vol_target_ovr: volatility targeting overlay on northstar weights

Outputs: DataFrame with [ticker, Industry, weight]

Notes:
- Requires data/processed/scores.parquet with at least [ticker, northstar_score]
- Optional columns used when present: [Industry, realized_vol, dollar_volume]
- This module saves strategies to data/processed/strategy_portfolios/ for persistence
"""
import os
import pandas as pd
import numpy as np

SCORES_FILE = "data/processed/scores.parquet"
UNIVERSE_FILE = "universe/nifty500.csv"
PRICES_FILE = "data/processed/prices.parquet"
STRATEGY_PORTFOLIOS_DIR = "data/processed/strategy_portfolios"

# Ensure strategy portfolios directory exists
os.makedirs(STRATEGY_PORTFOLIOS_DIR, exist_ok=True)

DEFAULT_CFG = {
    'max_names': 30,
    'min_weight': 0.005,
    'max_weight_per_name': 0.08,
}


def save_strategy(name: str, df: pd.DataFrame):
    """Save strategy portfolio to persistent storage"""
    path = os.path.join(STRATEGY_PORTFOLIOS_DIR, f"{name}.parquet")
    df.to_parquet(path, index=False)
    print(f"   💾 Saved {name} strategy: {len(df)} positions")


def load_strategy_weights(strategy_name: str):
    """Load strategy weights from persistent storage"""
    path = os.path.join(STRATEGY_PORTFOLIOS_DIR, f"{strategy_name}.parquet")
    if os.path.exists(path):
        df = pd.read_parquet(path)
        if 'ticker' in df.columns and 'weight' in df.columns:
            return df.set_index('ticker')['weight']
    return pd.Series(dtype=float)


def _load_scores() -> pd.DataFrame:
    if not os.path.exists(SCORES_FILE):
        raise FileNotFoundError(SCORES_FILE)
    df = pd.read_parquet(SCORES_FILE)
    if 'Industry' not in df.columns:
        df['Industry'] = 'Unknown'
    if 'Date' in df.columns:
        df = df.sort_values('Date').groupby('ticker').tail(1)
    keep = ['ticker','northstar_score','Industry']
    for c in ['realized_vol','dollar_volume','Close','Volume']:
        if c in df.columns:
            keep.append(c)
    df = df[keep].dropna(subset=['northstar_score'])
    # Build dollar_volume if missing
    if 'dollar_volume' not in df.columns and {'Close','Volume'}.issubset(df.columns):
        df['dollar_volume'] = df['Close'] * df['Volume']
    # Industry enrichment from universe with standardized column handling
    try:
        if (df['Industry'] == 'Unknown').mean() > 0.5 and os.path.exists(UNIVERSE_FILE):
            uni = pd.read_csv(UNIVERSE_FILE)
            uni['ticker'] = uni['Symbol'].astype(str) + '.NS'
            
            # Use standardized column name mapping
            industry_column_candidates = ['Industry', 'Industry Name', 'industry', 'industry_name']
            icol = None
            for candidate in industry_column_candidates:
                if candidate in uni.columns:
                    icol = candidate
                    break
            
            if icol:
                u = uni[['ticker', icol]].dropna().drop_duplicates('ticker')
                df = df.merge(u, on='ticker', how='left', suffixes=('', '_u'))
                
                # Standardize to 'Industry' column name
                if icol != 'Industry':
                    df['Industry'] = df['Industry'].where(df['Industry'] != 'Unknown', df[icol].fillna('Unknown'))
                else:
                    df['Industry'] = df['Industry'].where(df['Industry'] != 'Unknown', df[f'{icol}_u'].fillna('Unknown'))
                
                # Clean up temporary columns
                drop_cols = [c for c in df.columns if c.endswith('_u') or (c == icol and icol != 'Industry')]
                df = df.drop(columns=drop_cols, errors='ignore')
    except Exception:
        pass
    return df


def _clip_and_floor(weights: pd.Series, cfg: dict) -> pd.Series:
    w = weights.clip(upper=cfg.get('max_weight_per_name', DEFAULT_CFG['max_weight_per_name']))
    w = w / max(1e-12, w.sum())
    w = w.clip(lower=cfg.get('min_weight', DEFAULT_CFG['min_weight']))
    return w / max(1e-12, w.sum())

def _load_prices_pivot() -> pd.DataFrame:
    if not os.path.exists(PRICES_FILE):
        return pd.DataFrame()
    px = pd.read_parquet(PRICES_FILE)
    if 'Date' in px.columns:
        px['Date'] = pd.to_datetime(px['Date'])
    pivot = px.pivot(index='Date', columns='ticker', values='Close').ffill()
    return pivot


def _momentum_weights(pivot: pd.DataFrame, window_days: int, universe: list[str], cfg: dict) -> pd.Series:
    if pivot.empty:
        return pd.Series(dtype=float)
    common = pivot.columns.intersection(universe)
    if len(common) == 0:
        return pd.Series(dtype=float)
    px = pivot[common].copy()
    tail = px.tail(window_days + 1)
    ret = tail.pct_change().dropna()
    mom = (1 + ret).prod() - 1
    mom = mom.sort_values(ascending=False).head(int(cfg.get('max_names', 30)))
    ranks = mom.rank(pct=True)
    return (ranks / ranks.sum()).astype(float)


def _volatility(pivot: pd.DataFrame, window_days: int, universe: list[str]) -> pd.Series:
    common = pivot.columns.intersection(universe)
    if len(common) == 0:
        return pd.Series(dtype=float)
    ret = pivot[common].pct_change().dropna()
    vol = ret.tail(window_days).std()
    return vol


def build_strategy_portfolio(strategy: str, cfg: dict | None = None) -> pd.DataFrame:
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    scores = _load_scores().copy()
    N = int(cfg.get('max_names', DEFAULT_CFG['max_names']))
    prices_pivot = _load_prices_pivot()

    if strategy == 'northstar':
        sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
        ranks = sel['northstar_score'].rank(pct=True)
        sel['weight'] = _clip_and_floor(ranks / ranks.sum(), cfg)
    elif strategy == 'equal_weight_top':
        sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
        sel['weight'] = 1.0 / max(1, len(sel))
    elif strategy == 'low_vol':
        base = scores.dropna(subset=['realized_vol']) if 'realized_vol' in scores.columns else scores.copy()
        # prefer liquid names if available
        if 'dollar_volume' in base.columns:
            base = base.sort_values(['realized_vol','dollar_volume'], ascending=[True, False])
        else:
            base = base.sort_values('realized_vol', ascending=True)
        sel = base.head(N).copy()
        inv = 1.0 / (sel['realized_vol'].replace(0, np.nan)) if 'realized_vol' in sel.columns else pd.Series(1.0, index=sel.index)
        inv = inv.fillna(inv.median())
        sel['weight'] = _clip_and_floor(inv / inv.sum(), cfg)
    elif strategy == 'liquidity_weighted':
        sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
        if 'dollar_volume' in sel.columns:
            w = sel['dollar_volume'] / max(1e-12, sel['dollar_volume'].sum())
        else:
            w = pd.Series(1.0 / max(1, len(sel)), index=sel.index)
        sel['weight'] = _clip_and_floor(w, cfg)
    elif strategy in ('mom_6m','mom_12m','mom_vol_adj'):
        if not prices_pivot.empty:
            universe = scores['ticker'].tolist()
            window = 126 if strategy == 'mom_6m' else 252
            wraw = _momentum_weights(prices_pivot, window, universe, cfg)
            if strategy == 'mom_vol_adj':
                vol = _volatility(prices_pivot, 63, list(wraw.index))
                score = (wraw.reindex(vol.index).fillna(0.0) / (vol + 1e-6))
                w = _clip_and_floor(score / max(1e-12, score.sum()), cfg)
            else:
                w = _clip_and_floor(wraw, cfg)
            sel = scores.set_index('ticker').reindex(w.index).reset_index()
            sel['weight'] = w.values
        else:
            sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
            sel['weight'] = 1.0 / max(1, len(sel))
    elif strategy == 'mom_3m_6m_12m':
        if not prices_pivot.empty:
            universe = scores['ticker'].tolist()
            w3 = _momentum_weights(prices_pivot, 63, universe, cfg)
            w6 = _momentum_weights(prices_pivot, 126, universe, cfg)
            w12 = _momentum_weights(prices_pivot, 252, universe, cfg)
            # Align and average ranks
            union = w3.index.union(w6.index).union(w12.index)
            w3 = w3.reindex(union).fillna(0)
            w6 = w6.reindex(union).fillna(0)
            w12 = w12.reindex(union).fillna(0)
            comp = (w3 + w6 + w12) / 3.0
            comp = comp.sort_values(ascending=False).head(N)
            w = _clip_and_floor(comp / max(1e-12, comp.sum()), cfg)
            sel = scores.set_index('ticker').reindex(w.index).reset_index()
            sel['weight'] = w.values
        else:
            sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
            sel['weight'] = 1.0 / max(1, len(sel))
    elif strategy == 'dual_momentum':
        if not prices_pivot.empty:
            universe = scores['ticker'].tolist()
            # Absolute momentum filter: 12M > 0
            mom12 = _momentum_weights(prices_pivot, 252, universe, cfg)
            abs_pos = mom12[mom12 > 0]
            if abs_pos.empty:
                # fallback to value tilt if nothing passes
                return build_strategy_portfolio('value_tilt', cfg)
            # Relative momentum weights via 6M among filtered
            w6 = _momentum_weights(prices_pivot, 126, list(abs_pos.index), cfg)
            w = _clip_and_floor(w6, cfg)
            sel = scores.set_index('ticker').reindex(w.index).reset_index()
            sel['weight'] = w.values
        else:
            sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
            sel['weight'] = 1.0 / max(1, len(sel))
    elif strategy in ('quality_tilt','value_tilt'):
        col = 'quality_score' if strategy == 'quality_tilt' else 'value_score'
        if col in scores.columns:
            base = scores.sort_values(col, ascending=False).head(N).copy()
            ranks = base[col].rank(pct=True)
            base['weight'] = _clip_and_floor(ranks / ranks.sum(), cfg)
            sel = base
        else:
            sel = scores.sort_values('northstar_score', ascending=False).head(N).copy()
            sel['weight'] = 1.0 / max(1, len(sel))
    elif strategy == 'sector_neutral_eq':
        base = scores.sort_values('northstar_score', ascending=False).head(5*N).copy()
        sec_score = base.groupby('Industry')['northstar_score'].sum().sort_values(ascending=False)
        top_secs = set(sec_score.head(5).index.tolist())
        sel = base[base['Industry'].isin(top_secs)].copy().head(N)
        sel['weight'] = 1.0 / max(1, len(sel))
    elif strategy == 'risk_parity_vol':
        base = scores.dropna(subset=['realized_vol']) if 'realized_vol' in scores.columns else scores.copy()
        base = base.sort_values('realized_vol', ascending=True).head(N)
        vol = base['realized_vol'].replace(0, np.nan).fillna(base['realized_vol'].median())
        inv = 1.0 / (vol + 1e-6)
        sel = base.copy()
        sel['weight'] = _clip_and_floor(inv / inv.sum(), cfg)
    elif strategy == 'regime_conditional':
        regime = 'neutral'
        try:
            from src.cohesion.state_file_manager import StateFileManager
            state_manager = StateFileManager()
            ms = state_manager.read_market_state()
            if not ms.empty:
                regime = str(ms.iloc[-1].get('macro_regime','neutral')).lower()
        except Exception:
            pass
        if regime in ('boom','expansion','late-expansion'):
            return build_strategy_portfolio('mom_6m', cfg)
        else:
            return build_strategy_portfolio('value_tilt', cfg)
    elif strategy == 'quality_value_combo':
        have_cols = [c for c in ['quality_score','value_score'] if c in scores.columns]
        if len(have_cols) >= 1:
            base = scores.copy()
            if 'quality_score' in base.columns and 'value_score' in base.columns:
                zq = (base['quality_score'] - base['quality_score'].mean())/ (base['quality_score'].std()+1e-9)
                zv = (base['value_score'] - base['value_score'].mean())/ (base['value_score'].std()+1e-9)
                base['qv_combo'] = 0.5*zq + 0.5*zv
                sel = base.sort_values('qv_combo', ascending=False).head(N)
                ranks = sel['qv_combo'].rank(pct=True)
            else:
                col = have_cols[0]
                sel = base.sort_values(col, ascending=False).head(N)
                ranks = sel[col].rank(pct=True)
            sel['weight'] = _clip_and_floor(ranks / ranks.sum(), cfg)
        else:
            sel = scores.sort_values('northstar_score', ascending=False).head(N)
            sel['weight'] = 1.0/ max(1,len(sel))
    elif strategy == 'sector_tilt_mom':
        # pick top sectors by northstar score, then apply 6M momentum inside
        base = scores.sort_values('northstar_score', ascending=False).head(5*N).copy()
        top_secs = set(base.groupby('Industry')['northstar_score'].sum().sort_values(ascending=False).head(5).index.tolist())
        tickers = base[base['Industry'].isin(top_secs)]['ticker'].tolist()
        if not _load_prices_pivot().empty and tickers:
            wraw = _momentum_weights(_load_prices_pivot(), 126, tickers, cfg)
            w = _clip_and_floor(wraw, cfg)
            sel = scores.set_index('ticker').reindex(w.index).reset_index()
            sel['weight'] = w.values
        else:
            sel = base.head(N)
            sel['weight'] = 1.0/ max(1,len(sel))
    elif strategy == 'vol_target_ovr':
        # Start from northstar weights then scale daily returns to target vol (approximate via static scaling)
        target_vol = float(cfg.get('target_vol', 0.15))
        sel = build_strategy_portfolio('northstar', cfg).copy()
        # No dynamic daily scaling here; we just output weights; backtester can scale returns if extended.
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    out = sel[['ticker','Industry','weight']].copy()
    out['weight'] = out['weight'].astype(float)
    return out


def compare_strategies(strategies: list[str], cfg: dict | None = None) -> dict:
    """Compare strategies and save them to persistent storage"""
    out = {}
    for name in strategies:
        try:
            portfolio = build_strategy_portfolio(name, cfg)
            out[name] = portfolio
            # Save strategy to persistent storage
            save_strategy(name, portfolio)
        except Exception as e:
            out[name] = pd.DataFrame({'error': [str(e)]})
    return out


def generate_all_strategies():
    """Generate and save all available strategies"""
    print("🧪 GENERATING ALL STRATEGY PORTFOLIOS")
    print("=" * 50)
    
    strategies = [
        'northstar', 'mom_6m', 'mom_12m', 'value_tilt', 'quality_tilt',
        'low_vol', 'equal_weight_top', 'liquidity_weighted', 'mom_vol_adj',
        'sector_neutral_eq', 'risk_parity_vol', 'regime_conditional',
        'mom_3m_6m_12m', 'dual_momentum', 'quality_value_combo', 'sector_tilt_mom'
    ]
    
    results = compare_strategies(strategies)
    
    print(f"\n✅ Generated {len([k for k, v in results.items() if not v.empty])} strategies")
    print(f"📁 Saved to: {STRATEGY_PORTFOLIOS_DIR}")
    
    return results


if __name__ == '__main__':
    generate_all_strategies()

# =========================== TEMPORAL STRATEGY WRAPPER ===========================

class TemporalStrategyWrapper:
    """
    Wrapper that makes any strategy temporal-safe
    
    This ensures all strategies use temporal signals and respect point-in-time constraints.
    """
    
    def __init__(self, original_strategy):
        self.original_strategy = original_strategy
        self.signal_engine = TemporalSignalEngine()
        self.guard = TemporalGuard()
    
    def generate_signals(self, symbol, current_time):
        """Generate temporal-safe signals"""
        return self.signal_engine.generate_all_signals(symbol, current_time)
    
    def execute_strategy(self, symbol, current_time, *args, **kwargs):
        """Execute strategy with temporal protection"""
        
        # Get temporal-safe signals
        signals = self.generate_signals(symbol, current_time)
        
        # Pass to original strategy with temporal signals
        kwargs['temporal_signals'] = signals
        kwargs['current_time'] = current_time
        
        return self.original_strategy.execute(symbol, *args, **kwargs)

# =========================== TEMPORAL STRATEGY FACTORY ===========================

def make_temporal_safe(strategy_class):
    """Factory function to make any strategy temporal-safe"""
    
    class TemporalSafeStrategy(strategy_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.signal_engine = TemporalSignalEngine()
            self.guard = TemporalGuard()
        
        def get_signals(self, symbol, current_time):
            """Override to use temporal signals"""
            return self.signal_engine.generate_all_signals(symbol, current_time)
    
    return TemporalSafeStrategy
