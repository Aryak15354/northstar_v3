import pandas as pd
import numpy as np

FUND_FILE = "data/processed/fundamentals.parquet"
PRICE_FILE = "data/processed/prices.parquet"
UNIVERSE_FILE = "universe/nifty500.csv"
OUTPUT_FILE = "data/processed/valuation.parquet"


def main():
    fundamentals = pd.read_parquet(FUND_FILE)
    prices = pd.read_parquet(PRICE_FILE)
    universe = pd.read_csv(UNIVERSE_FILE)

    universe["ticker"] = universe["Symbol"] + ".NS"

    # Latest financials
    fundamentals = fundamentals.sort_values("date").groupby("ticker").tail(1)

    # Latest prices
    latest_price = prices.sort_values("Date").groupby("ticker").tail(1)[["ticker", "Close"]]

    df = fundamentals.merge(latest_price, on="ticker", how="left")
    df = df.merge(universe[["ticker", "Industry"]], on="ticker", how="left")

    # Growth (YoY revenue) — use approximately 1 year back (5 quarters) if available
    hist_prev = (
        pd.read_parquet(FUND_FILE)
        .sort_values(["ticker", "date"]) 
        .groupby("ticker")
        .apply(lambda g: pd.Series({"revenue_prev": g["revenue"].iloc[-5] if len(g) >= 5 else np.nan}))
        .reset_index()
    )
    df = df.merge(hist_prev, on="ticker", how="left")
    df["revenue_growth"] = (df["revenue"] - df["revenue_prev"]) / df["revenue_prev"]

    # Market cap & Enterprise Value
    df["market_cap"] = (df["Close"].astype(float) * df["shares_outstanding"].astype(float))
    # Include cash in EV (EV = MC + Debt - Cash)
    if "cash_and_equivalents" not in df.columns:
        df["cash_and_equivalents"] = np.nan
    df["enterprise_value"] = df["market_cap"].astype(float) + df["total_debt"].astype(float) - df["cash_and_equivalents"].astype(float)

    # Core valuation ratios
    def safe_div(n, d):
        n = pd.to_numeric(n, errors="coerce")
        d = pd.to_numeric(d, errors="coerce")
        out = n / d
        out = out.replace([np.inf, -np.inf], np.nan)
        return out

    df["pe"] = safe_div(df["market_cap"], df["net_income"]).clip(lower=-100, upper=100)
    df["pb"] = safe_div(df["market_cap"], df["equity"]).clip(lower=-50, upper=50)
    df["fcf_yield"] = safe_div(df["free_cash_flow"], df["market_cap"]).clip(lower=-1, upper=1)
    df["cfo_yield"] = safe_div(df["operating_cash_flow"], df["market_cap"]).clip(lower=-1, upper=1)
    df["ev_ebitda"] = safe_div(df["enterprise_value"], df["ebitda"]).clip(lower=-100, upper=100)
    df["ev_sales"] = safe_div(df["enterprise_value"], df["revenue"]).clip(lower=-50, upper=50)

    # Growth adjusted
    # Avoid divide-by-zero by replacing near-zero growth with NaN
    growth_denom = df["revenue_growth"].where(df["revenue_growth"].abs() > 1e-6)
    df["peg"] = safe_div(df["pe"], (growth_denom * 100))

    # Financial safety
    df["roe"] = safe_div(df["net_income"], df["equity"]).clip(lower=-1, upper=1)
    df["debt_equity"] = safe_div(df["total_debt"], df["equity"]).clip(lower=0, upper=5)

    # Bucketed caps by sector and market cap to reduce outlier distortion
    try:
        # Market-cap buckets via tertiles
        df["mcap_bucket"] = pd.qcut(df["market_cap"], 3, labels=["Small", "Mid", "Large"])  
        # Sector-specific base caps (upper bounds)
        sector_pe_caps = {
            "Information Technology": 120,
            "Communication Services": 100,
            "Health Care": 100,
            "Consumer Discretionary": 90,
            "Financials": 25,
            "Utilities": 35,
            "Energy": 40,
            "Materials": 50,
            "Industrials": 60,
            "Consumer Staples": 55,
        }
        sector_ev_caps = {
            "Information Technology": 50,
            "Communication Services": 45,
            "Health Care": 45,
            "Consumer Discretionary": 40,
            "Financials": 20,
            "Utilities": 18,
            "Energy": 20,
            "Materials": 25,
            "Industrials": 30,
            "Consumer Staples": 28,
        }
        bucket_multipliers = {"Small": 1.4, "Mid": 1.2, "Large": 1.0}

        df["_pe_cap"] = df["Industry"].map(sector_pe_caps).fillna(60)
        df["_ev_cap"] = df["Industry"].map(sector_ev_caps).fillna(25)
        df["_mult"] = df["mcap_bucket"].map(bucket_multipliers).fillna(1.0)

        df["pe"] = df["pe"].clip(lower=-100, upper=(df["_pe_cap"] * df["_mult"]))
        df["ev_ebitda"] = df["ev_ebitda"].clip(lower=-100, upper=(df["_ev_cap"] * df["_mult"]))
        # Clean up helper columns
        df = df.drop(columns=[c for c in ["_pe_cap", "_ev_cap", "_mult"] if c in df.columns])
    except Exception:
        pass

    # Rank everything inside Industry
    def pct_rank(col):
        return df.groupby("Industry")[col].rank(pct=True)

    df["pe_pct"] = pct_rank("pe").fillna(0.5)
    df["pb_pct"] = pct_rank("pb").fillna(0.5)
    df["ev_ebitda_pct"] = pct_rank("ev_ebitda").fillna(0.5)
    df["ev_sales_pct"] = pct_rank("ev_sales").fillna(0.5)
    df["fcf_yield_pct"] = pct_rank("fcf_yield").fillna(0.5)
    df["cfo_yield_pct"] = pct_rank("cfo_yield").fillna(0.5)
    df["peg_pct"] = pct_rank("peg").fillna(0.5)
    df["roe_pct"] = pct_rank("roe").fillna(0.5)
    df["debt_equity_pct"] = pct_rank("debt_equity").fillna(0.5)

    # Build value components
    df["earnings_value"] = 1 - df["pe_pct"]
    df["asset_value"] = 1 - df["pb_pct"]
    df["cash_value"] = (df["fcf_yield_pct"] + df["cfo_yield_pct"]) / 2
    df["enterprise_value_score"] = (1 - df["ev_ebitda_pct"] + 1 - df["ev_sales_pct"]) / 2
    df["growth_value"] = 1 - df["peg_pct"]
    df["balance_sheet"] = (df["roe_pct"] + (1 - df["debt_equity_pct"])) / 2

    # Final true undervaluation score
    df["true_undervaluation"] = (
        0.25 * df["earnings_value"] +
        0.15 * df["asset_value"] +
        0.15 * df["cash_value"] +
        0.15 * df["enterprise_value_score"] +
        0.15 * df["growth_value"] +
        0.15 * df["balance_sheet"]
    ) * 100

    df.to_parquet(OUTPUT_FILE, index=False)
    print("✅ Institutional valuation model built")


if __name__ == "__main__":
    main()
