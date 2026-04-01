from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.gap9_academic_factors import Gap9AcademicFactors


def _make_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=280)
    market_ret = pd.Series(0.0005 + 0.01 * np.sin(np.arange(len(dates)) / 8.0), index=dates)
    nifty_close = 1000.0 * (1.0 + market_ret).cumprod()

    tickers = {
        "LOWBETA.NS": {"beta": 0.35, "volume": 2_500_000, "spike": 0.00, "ocf_mult": 1.4, "ni_sign": 1.0},
        "HIGHBETA.NS": {"beta": 1.60, "volume": 2_500_000, "spike": 0.00, "ocf_mult": 0.8, "ni_sign": 1.0},
        "LIQUID.NS": {"beta": 0.90, "volume": 8_000_000, "spike": 0.00, "ocf_mult": 1.0, "ni_sign": 1.0},
        "ILLIQ.NS": {"beta": 0.90, "volume": 35_000, "spike": 0.00, "ocf_mult": 1.0, "ni_sign": 1.0},
        "LOTTERY.NS": {"beta": 1.10, "volume": 900_000, "spike": 0.22, "ocf_mult": 1.0, "ni_sign": 1.0},
        "CALM.NS": {"beta": 0.75, "volume": 900_000, "spike": 0.00, "ocf_mult": 1.0, "ni_sign": 1.0},
        "CASHRICH.NS": {"beta": 0.95, "volume": 1_400_000, "spike": 0.00, "ocf_mult": 1.8, "ni_sign": 1.0},
        "ACCRUAL.NS": {"beta": 0.95, "volume": 1_400_000, "spike": 0.00, "ocf_mult": 0.4, "ni_sign": 1.0},
        "GOOD.NS": {"beta": 0.80, "volume": 1_800_000, "spike": 0.00, "ocf_mult": 1.6, "ni_sign": 1.0},
        "BAD.NS": {"beta": 1.15, "volume": 1_100_000, "spike": 0.00, "ocf_mult": 0.5, "ni_sign": -1.0},
        "FILL1.NS": {"beta": 1.00, "volume": 1_250_000, "spike": 0.00, "ocf_mult": 1.0, "ni_sign": 1.0},
        "FILL2.NS": {"beta": 1.05, "volume": 1_350_000, "spike": 0.00, "ocf_mult": 1.1, "ni_sign": 1.0},
    }

    rows: list[dict[str, float | str | pd.Timestamp]] = []
    for idx, (ticker, spec) in enumerate(tickers.items()):
        noise = 0.0002 * np.cos(np.arange(len(dates)) / (idx + 3.0))
        stock_ret = spec["beta"] * market_ret.to_numpy() + noise
        if spec["spike"]:
            stock_ret[-12] += spec["spike"]
        close = 100.0 * np.cumprod(1.0 + stock_ret)

        base_assets = 900.0 + idx * 25.0
        good_name = ticker in {"GOOD.NS", "LOWBETA.NS", "CASHRICH.NS", "LIQUID.NS"}
        debt_trend = np.linspace(0.55, 0.30, len(dates)) if good_name else np.linspace(0.35, 0.75, len(dates))
        wc_trend = np.linspace(120.0, 220.0, len(dates)) if good_name else np.linspace(200.0, 80.0, len(dates))
        shares_trend = np.linspace(100.0, 100.0, len(dates)) if good_name else np.linspace(100.0, 125.0, len(dates))
        gross_margin = np.linspace(0.42, 0.55, len(dates)) if good_name else np.linspace(0.48, 0.32, len(dates))
        asset_turnover_z = np.linspace(0.2, 1.3, len(dates)) if good_name else np.linspace(0.8, -0.9, len(dates))
        roe_qoq_change = np.full(len(dates), 0.04 if good_name else -0.03)

        revenue = np.linspace(500.0 + idx * 10.0, 650.0 + idx * 12.0, len(dates))
        total_assets = np.full(len(dates), base_assets)
        net_income = spec["ni_sign"] * np.linspace(45.0, 75.0, len(dates))
        operating_cash_flow = net_income * spec["ocf_mult"]
        accruals_ratio = np.linspace(-0.12, -0.03, len(dates)) if spec["ocf_mult"] > 1.0 else np.linspace(0.03, 0.15, len(dates))
        volume = np.full(len(dates), float(spec["volume"]))

        for i, dt in enumerate(dates):
            rows.append(
                {
                    "date": dt,
                    "ticker": ticker,
                    "close": float(close[i]),
                    "volume": float(volume[i]),
                    "ret_1d": float(stock_ret[i]),
                    "nifty_close": float(nifty_close.loc[dt]),
                    "net_income": float(net_income[i]),
                    "total_assets": float(total_assets[i]),
                    "operating_cash_flow": float(operating_cash_flow[i]),
                    "roe_qoq_change": float(roe_qoq_change[i]),
                    "accruals_ratio": float(accruals_ratio[i]),
                    "debt_to_equity": float(debt_trend[i]),
                    "working_capital": float(wc_trend[i]),
                    "shares_outstanding": float(shares_trend[i]),
                    "gross_profit": float(revenue[i] * gross_margin[i]),
                    "revenue": float(revenue[i]),
                    "asset_turnover_sector_z": float(asset_turnover_z[i]),
                }
            )

    return pd.DataFrame(rows)


def test_gap9_academic_factors_append_expected_columns_and_signal_direction() -> None:
    panel = _make_panel()
    transformed = Gap9AcademicFactors().transform(panel)

    for column in Gap9AcademicFactors.OUTPUT_COLUMNS:
        assert column in transformed.columns

    latest = (
        transformed.sort_values(["ticker", "date"], kind="mergesort")
        .groupby("ticker", sort=False)
        .tail(1)
        .set_index("ticker")
    )

    assert latest.loc["GOOD.NS", "piotroski_fscore"] > latest.loc["BAD.NS", "piotroski_fscore"]
    assert latest.loc["LOWBETA.NS", "bab_signal"] > latest.loc["HIGHBETA.NS", "bab_signal"]
    assert latest.loc["ILLIQ.NS", "amihud_illiquidity"] > latest.loc["LIQUID.NS", "amihud_illiquidity"]
    assert latest.loc["LOTTERY.NS", "max_ret_20d"] > latest.loc["CALM.NS", "max_ret_20d"]
    assert latest.loc["CASHRICH.NS", "earnings_quality_ratio"] > latest.loc["ACCRUAL.NS", "earnings_quality_ratio"]
    assert latest["piotroski_fscore_cs_z"].notna().all()


def test_gap9_academic_factors_forward_fill_sparse_accounting_inputs() -> None:
    panel = _make_panel().sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    sparse_cols = [
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "roe_qoq_change",
        "accruals_ratio",
        "debt_to_equity",
        "working_capital",
        "shares_outstanding",
        "gross_profit",
        "revenue",
        "asset_turnover_sector_z",
    ]
    keep_mask = panel.groupby("ticker", sort=False).cumcount() % 63 == 0
    panel.loc[~keep_mask, sparse_cols] = np.nan

    transformed = Gap9AcademicFactors().transform(panel)
    latest = (
        transformed.sort_values(["ticker", "date"], kind="mergesort")
        .groupby("ticker", sort=False)
        .tail(1)
        .set_index("ticker")
    )

    assert latest["piotroski_fscore"].notna().all()
    assert latest["earnings_quality_ratio"].notna().all()


def test_gap9_bab_signal_does_not_crash_when_nifty_close_is_missing() -> None:
    panel = _make_panel().drop(columns=["nifty_close"])

    transformed = Gap9AcademicFactors().transform(panel)

    assert "bab_signal" in transformed.columns
    assert transformed["bab_signal"].isna().all()
