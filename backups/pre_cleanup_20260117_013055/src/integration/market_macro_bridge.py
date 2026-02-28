#!/usr/bin/env python3
"""
Market↔Macro Integration Bridge
Align daily market data (prices/technicals/financials) with weekly macro/risk/stress
and persist a unified, point-in-time safe daily table for downstream use.

Inputs (expected if present, all optional with graceful degradation):
- data/market/daily_prices.parquet  (index: Date, columns: tickers; or long with [Date,ticker,Close])
- data/market/technicals.parquet    (long: [Date,ticker,<tech cols>])
- data/market/financials.parquet    (long snapshot: [Date,ticker,<fin cols>])
- data/processed/market_regime.parquet (daily or weekly with breadth/participation/corr/vol)
- data/macro/factors/macro_score.parquet (weekly; includes Regime, MacroScore, MarketStress_z,...)
- data/macro/factors/risk_budget.parquet (weekly; Max_Equity_Exposure)
- data/risk/shock_state.parquet         (weekly; Shock_Level, Shock_Max_Exposure)

Outputs:
- data/processed/unified_daily.parquet
- data/processed/unified_daily_diagnostics.csv
"""
import os
import pandas as pd
import numpy as np

PRICES = "data/market/daily_prices.parquet"
TECH = "data/market/technicals.parquet"
FIN = "data/market/financials.parquet"
MREG = "data/processed/market_regime.parquet"
MACRO = "data/macro/factors/macro_score.parquet"
RISK = "data/macro/factors/risk_budget.parquet"
SHOCK = "data/risk/shock_state.parquet"
OUT = "data/processed/unified_daily.parquet"
DIAG = "data/processed/unified_daily_diagnostics.csv"

# Optional raw CSV fallbacks
RAW_PRICES = "data/raw/daily_prices.csv"
RAW_TECH = "data/raw/technicals.csv"
RAW_FIN = "data/raw/financials.csv"

os.makedirs("data/processed", exist_ok=True)

def safe_read(path):
    try:
        if os.path.exists(path):
            return pd.read_parquet(path)
    except Exception:
        return None
    return None

def safe_read_csv(path):
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        return None
    return None


def normalize_long(df, date_col="Date", symbol_col="ticker"):
    if df is None or df.empty:
        return None
    d = df.copy()
    # Try wide-to-long for prices if necessary
    if date_col not in d.columns and not isinstance(d.index, pd.DatetimeIndex):
        # Keep as is
        return d
    if isinstance(d.index, pd.DatetimeIndex):
        d = d.reset_index().rename(columns={d.index.name or 'index': date_col})
    d[date_col] = pd.to_datetime(d[date_col], errors='coerce')
    # If clearly wide, melt
    fixed_cols = [c for c in [date_col, symbol_col] if c in d.columns]
    if symbol_col not in d.columns:
        value_cols = [c for c in d.columns if c != date_col]
        d = d.melt(id_vars=[date_col], value_vars=value_cols, var_name=symbol_col, value_name='value')
    return d


def run():
    print("🔗 Building Market↔Macro unified daily table")

    prices = safe_read(PRICES)
    tech = safe_read(TECH)
    fin = safe_read(FIN)
    mreg = safe_read(MREG)
    macro = safe_read(MACRO)
    risk = safe_read(RISK)
    shock = safe_read(SHOCK)

    # If market parquets missing, try to build them from raw CSVs in data/raw
    wrote_any = False
    if (prices is None or prices.empty):
        rp = safe_read_csv(RAW_PRICES)
        if rp is not None and not rp.empty:
            df = rp.copy()
            # Normalize to long [Date,ticker,Close] if possible
            date_col = 'Date' if 'Date' in df.columns else ('date' if 'date' in df.columns else None)
            ticker_col = 'ticker' if 'ticker' in df.columns else ('Ticker' if 'Ticker' in df.columns else None)
            close_col = None
            for c in ['Close', 'close', 'Adj Close', 'adj_close']:
                if c in df.columns:
                    close_col = c
                    break
            if date_col and ticker_col and close_col:
                df = df[[date_col, ticker_col, close_col]].rename(columns={date_col: 'Date', ticker_col: 'ticker', close_col: 'Close'})
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
                os.makedirs(os.path.dirname(PRICES), exist_ok=True)
                df.to_parquet(PRICES)
                prices = df
                wrote_any = True
    if (tech is None or tech.empty):
        rt = safe_read_csv(RAW_TECH)
        if rt is not None and not rt.empty:
            df = rt.copy()
            if 'Date' not in df.columns and 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
            os.makedirs(os.path.dirname(TECH), exist_ok=True)
            df.to_parquet(TECH)
            tech = df
            wrote_any = True
    if (fin is None or fin.empty):
        rf = safe_read_csv(RAW_FIN)
        if rf is not None and not rf.empty:
            df = rf.copy()
            if 'Date' not in df.columns and 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
            os.makedirs(os.path.dirname(FIN), exist_ok=True)
            df.to_parquet(FIN)
            fin = df
            wrote_any = True
    if wrote_any:
        print("🗃️  Normalized CSVs from data/raw to data/market parquets")

    # Normalize prices to long [Date,ticker,Close]
    price_long = None
    if prices is not None and not prices.empty:
        if isinstance(prices.index, pd.DatetimeIndex) and (set(prices.columns.str.upper()) - {"DATE"}):
            # wide matrix of Close values
            pl = prices.copy().reset_index().rename(columns={prices.index.name or 'index': 'Date'})
            pl = pl.melt(id_vars=['Date'], var_name='ticker', value_name='Close')
            price_long = pl
        elif {"Date","ticker","Close"}.issubset(prices.columns):
            price_long = prices[["Date","ticker","Close"]].copy()
        else:
            # best effort: look for 'close' col
            cols = prices.columns
            close_col = 'close' if 'close' in cols else ('Close' if 'Close' in cols else None)
            if close_col and {"Date","ticker"}.issubset(cols):
                price_long = prices[["Date","ticker",close_col]].rename(columns={close_col:'Close'})
    if price_long is not None:
        price_long['Date'] = pd.to_datetime(price_long['Date'], errors='coerce')
        price_long = price_long.dropna(subset=['Date'])

    # Normalize tech to [Date,ticker,<tech...>]
    if tech is not None and not tech.empty:
        if 'Date' in tech.columns:
            tech['Date'] = pd.to_datetime(tech['Date'], errors='coerce')
        else:
            tech.index = pd.to_datetime(tech.index)
            tech = tech.reset_index().rename(columns={tech.index.name or 'index': 'Date'})

    # Normalize fin snapshot (forward-fill per ticker)
    if fin is not None and not fin.empty:
        if 'Date' in fin.columns:
            fin['Date'] = pd.to_datetime(fin['Date'], errors='coerce')
        else:
            fin.index = pd.to_datetime(fin.index)
            fin = fin.reset_index().rename(columns={fin.index.name or 'index': 'Date'})

    # Build daily calendar from prices if available, else from market_regime
    cal = None
    if price_long is not None:
        cal = price_long['Date'].dropna().drop_duplicates().sort_values()
    elif mreg is not None:
        if 'Date' in mreg.columns:
            cal = pd.to_datetime(mreg['Date'], errors='coerce').dropna().drop_duplicates().sort_values()
    if cal is None is None:
        print("❌ No calendar available (prices or market_regime missing)")
        return

    # Join macro weekly to daily with last-known (ffill)
    def to_weekly_index(df):
        x = df.copy()
        if not isinstance(x.index, pd.DatetimeIndex) and 'Date' in x.columns:
            x['Date'] = pd.to_datetime(x['Date'], errors='coerce')
            x = x.set_index('Date')
        return x

    macro_w = to_weekly_index(macro)
    risk_w = to_weekly_index(risk)
    shock_w = to_weekly_index(shock)

    # Create a daily frame for joins
    daily_index = pd.DatetimeIndex(cal)
    daily = pd.DataFrame(index=daily_index)

    if macro_w is not None and not macro_w.empty:
        daily = daily.join(macro_w.resample('D').ffill(), how='left')
    if risk_w is not None and not risk_w.empty:
        daily = daily.join(risk_w.resample('D').ffill(), how='left')
    if shock_w is not None and not shock_w.empty:
        daily = daily.join(shock_w.resample('D').ffill(), how='left')

    # Attach market_regime daily features if available
    if mreg is not None and not mreg.empty:
        mr = mreg.copy()
        if 'Date' in mr.columns:
            mr['Date'] = pd.to_datetime(mr['Date'], errors='coerce')
            mr = mr.set_index('Date')
        daily = daily.join(mr.resample('D').ffill(), how='left', rsuffix='_mr')

    # Build unified long by ticker if we have prices
    rows = []
    if price_long is not None and not price_long.empty:
        # Returns
        px = price_long.sort_values(['ticker','Date'])
        px['Return'] = px.groupby('ticker')['Close'].pct_change()
        # Merge tech and fin
        if tech is not None and not tech.empty:
            px = px.merge(tech, on=['Date','ticker'], how='left')
        if fin is not None and not fin.empty:
            # forward-fill financials by ticker
            fin_sorted = fin.sort_values(['ticker','Date']) if 'ticker' in fin.columns else fin
            px = px.merge(fin_sorted, on=['Date','ticker'], how='left')
            if 'ticker' in px.columns:
                px = px.sort_values(['ticker','Date'])
                fin_cols = [c for c in fin.columns if c not in ('Date','ticker')]
                px[fin_cols] = px.groupby('ticker')[fin_cols].ffill()
        # Attach daily macro/risk/shock by date
        px = px.merge(daily.reset_index().rename(columns={'index':'Date'}), on='Date', how='left')
        rows = px
    else:
        rows = daily.reset_index().rename(columns={'index':'Date'})

    # Diagnostics
    diag = {
        'prices_latest': str(price_long['Date'].max()) if price_long is not None and not price_long.empty else 'NA',
        'macro_latest': str(macro_w.index.max()) if macro_w is not None and not macro_w.empty else 'NA',
        'risk_latest': str(risk_w.index.max()) if risk_w is not None and not risk_w.empty else 'NA',
        'shock_latest': str(shock_w.index.max()) if shock_w is not None and not shock_w.empty else 'NA',
        'rows': len(rows) if isinstance(rows, pd.DataFrame) else 0,
        'cols': len(rows.columns) if isinstance(rows, pd.DataFrame) else 0,
    }

    # Persist
    if isinstance(rows, pd.DataFrame) and not rows.empty:
        # set index for downstream ease
        if 'Date' in rows.columns:
            rows['Date'] = pd.to_datetime(rows['Date'], errors='coerce')
            rows = rows.set_index('Date').sort_index()
        rows.to_parquet(OUT)
        print(f"✅ Unified daily saved → {OUT} ({rows.shape[0]} rows × {rows.shape[1]} cols)")
    else:
        print("⚠️ Unified daily empty — check inputs")

    pd.DataFrame([diag]).to_csv(DIAG, index=False)
    print(f"🧪 Diagnostics → {DIAG} :: {diag}")


if __name__ == "__main__":
    run()
