"""Gap 9 academic factor block built from the research feature panel.

This module computes the five academically-motivated signals requested by the
feature composition audit directly from already-merged panel columns, then
adds cross-sectional z-score and rank variants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import pandas as pd

from src.core.panel_math import group_rank_centered, group_zscore


@dataclass
class Gap9AcademicFactors:
    """Append Gap 9 factor features to a research feature panel."""

    factor_lookback_days: int = 252
    beta_lookback_days: int = 252
    beta_min_observations: int = 120
    amihud_lookback_days: int = 20
    amihud_min_observations: int = 10
    max_lookback_days: int = 20
    max_min_observations: int = 10
    min_piotroski_signals: int = 6

    GROUP_NAME: ClassVar[str] = "gap9_academic_factors"
    RAW_COLUMNS: ClassVar[list[str]] = [
        "piotroski_fscore",
        "bab_signal",
        "amihud_illiquidity",
        "max_ret_20d",
        "earnings_quality_ratio",
    ]
    OUTPUT_COLUMNS: ClassVar[list[str]] = [
        "piotroski_fscore",
        "piotroski_fscore_cs_z",
        "piotroski_fscore_cs_rank",
        "bab_signal",
        "bab_signal_cs_z",
        "bab_signal_cs_rank",
        "amihud_illiquidity",
        "amihud_illiquidity_cs_z",
        "amihud_illiquidity_cs_rank",
        "max_ret_20d",
        "max_ret_20d_cs_z",
        "max_ret_20d_cs_rank",
        "earnings_quality_ratio",
        "earnings_quality_ratio_cs_z",
        "earnings_quality_ratio_cs_rank",
    ]
    FUNDAMENTAL_HOLD_COLUMNS: ClassVar[list[str]] = [
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "roe_qoq_change",
        "accruals_ratio",
        "accruals_ratio_sector_z",
        "accruals_ratio_cs_z",
        "debt_to_equity",
        "working_capital",
        "shares_outstanding",
        "gross_profit",
        "revenue",
        "asset_turnover_sector_z",
        "asset_turnover",
        "cash_conversion",
        "cash_conversion_sector_z",
        "cash_conversion_cs_z",
    ]

    _group_zscore = staticmethod(group_zscore)
    _group_rank_centered = staticmethod(group_rank_centered)

    @staticmethod
    def _binary_signal(condition: pd.Series, *inputs: pd.Series) -> pd.Series:
        mask = pd.Series(True, index=condition.index, dtype=bool)
        for source in inputs:
            mask &= pd.to_numeric(source, errors="coerce").notna()
        out = pd.Series(np.nan, index=condition.index, dtype=float)
        cond = pd.Series(condition, index=condition.index).fillna(False)
        out.loc[mask] = cond.loc[mask].astype(float)
        return out

    @staticmethod
    def _coalesce_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
        out = pd.Series(np.nan, index=frame.index, dtype=float)
        for column in columns:
            if column in frame.columns:
                values = pd.to_numeric(frame[column], errors="coerce")
                out = out.where(out.notna(), values)
        return out

    @staticmethod
    def _series_or_nan(frame: pd.DataFrame, column: str) -> pd.Series:
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce")
        return pd.Series(np.nan, index=frame.index, dtype=float)

    def _compute_piotroski_fscore(self, frame: pd.DataFrame) -> pd.Series:
        g = frame.groupby("ticker", sort=False)
        lag = int(max(21, self.factor_lookback_days))

        # I.5: sign/magnitude sub-signals must be built from raw values or true
        # ratios only. Coalescing a value with its OWN z-score as a fallback is a
        # scale error: a z-score's sign reflects distance from the cross-sectional
        # mean, not from zero, so "accruals_ratio < 0" and "ocf > 0" would flip
        # meaning whenever the cross-sectional mean is nonzero (the normal case).
        # We accept slightly reduced coverage for these sub-signals instead;
        # min_piotroski_signals gating absorbs it.
        net_income = self._series_or_nan(frame, "net_income")
        total_assets = self._series_or_nan(frame, "total_assets").replace(0.0, np.nan)
        operating_cash_flow = self._series_or_nan(frame, "operating_cash_flow")
        roe_qoq_change = self._series_or_nan(frame, "roe_qoq_change")
        accruals_ratio = self._series_or_nan(frame, "accruals_ratio")
        debt_to_equity = self._series_or_nan(frame, "debt_to_equity")
        working_capital = self._series_or_nan(frame, "working_capital")
        shares_outstanding = self._series_or_nan(frame, "shares_outstanding")
        gross_profit = self._series_or_nan(frame, "gross_profit")
        revenue = self._series_or_nan(frame, "revenue").replace(0.0, np.nan)
        asset_turnover_signal = self._coalesce_numeric(frame, ["asset_turnover_sector_z", "asset_turnover"])

        roa = net_income / total_assets
        debt_prev = debt_to_equity.groupby(frame["ticker"], sort=False).shift(lag)
        wc_prev = working_capital.groupby(frame["ticker"], sort=False).shift(lag)
        shares_prev = g["shares_outstanding"].shift(lag) if "shares_outstanding" in frame.columns else pd.Series(np.nan, index=frame.index)
        asset_turnover_prev = g["asset_turnover_sector_z"].shift(lag) if "asset_turnover_sector_z" in frame.columns else (
            g["asset_turnover"].shift(lag) if "asset_turnover" in frame.columns else pd.Series(np.nan, index=frame.index)
        )
        gross_margin = gross_profit / revenue
        gross_margin_prev = gross_margin.groupby(frame["ticker"], sort=False).shift(lag)

        signals = pd.DataFrame(
            {
                "roa_positive": self._binary_signal(roa > 0.0, roa),
                "ocf_positive": self._binary_signal(operating_cash_flow > 0.0, operating_cash_flow),
                "roa_increasing_proxy": self._binary_signal(roe_qoq_change > 0.0, roe_qoq_change),
                "accruals_negative": self._binary_signal(accruals_ratio < 0.0, accruals_ratio),
                "leverage_decreasing": self._binary_signal(debt_to_equity < debt_prev, debt_to_equity, debt_prev),
                "current_ratio_proxy_improving": self._binary_signal(working_capital > wc_prev, working_capital, wc_prev),
                "no_new_shares_issued": self._binary_signal(shares_outstanding <= shares_prev, shares_outstanding, shares_prev),
                "gross_margin_improving": self._binary_signal(gross_margin > gross_margin_prev, gross_margin, gross_margin_prev),
                "asset_turnover_improving": self._binary_signal(
                    asset_turnover_signal > asset_turnover_prev,
                    asset_turnover_signal,
                    asset_turnover_prev,
                ),
            },
            index=frame.index,
        )

        # I.6: normalize by the number of genuinely-available signals so a
        # company with sparse disclosure is not systematically depressed by
        # missing checks counting as "failed" (0). Only produce a score when at
        # least min_piotroski_signals of the 9 have real data, then scale back to
        # the 0-9 range.
        valid = signals.notna().sum(axis=1)
        score = signals.fillna(0.0).sum(axis=1)
        normalized = score.where(valid <= 0, (score / valid.replace(0, np.nan)) * 9.0)
        return normalized.where(valid >= int(self.min_piotroski_signals)).astype(float)

    def _compute_bab_signal(self, frame: pd.DataFrame) -> pd.Series:
        if "date" not in frame.columns:
            return pd.Series(np.nan, index=frame.index, dtype=float)

        if "nifty_ret_1d" in frame.columns:
            nifty = (
                frame[["date", "nifty_ret_1d"]]
                .copy()
                .dropna(subset=["date"])
                .sort_values("date", kind="mergesort")
                .drop_duplicates(subset=["date"], keep="last")
            )
            nifty["nifty_ret_1d"] = pd.to_numeric(nifty["nifty_ret_1d"], errors="coerce")
        elif "nifty_close" in frame.columns:
            nifty = (
                frame[["date", "nifty_close"]]
                .copy()
                .dropna(subset=["date"])
                .sort_values("date", kind="mergesort")
                .drop_duplicates(subset=["date"], keep="last")
            )
            nifty["nifty_ret_1d"] = pd.to_numeric(nifty["nifty_close"], errors="coerce").pct_change()
        else:
            return pd.Series(np.nan, index=frame.index, dtype=float)

        if nifty.empty:
            return pd.Series(np.nan, index=frame.index, dtype=float)

        out = frame[["ticker", "date"]].copy()
        if "ret_1d" in frame.columns:
            out["ret_1d"] = pd.to_numeric(frame["ret_1d"], errors="coerce")
        elif "close" in frame.columns:
            out["ret_1d"] = (
                pd.to_numeric(frame["close"], errors="coerce")
                .groupby(frame["ticker"], sort=False)
                .pct_change()
            )
        else:
            return pd.Series(np.nan, index=frame.index, dtype=float)
        out["nifty_ret_1d"] = pd.to_datetime(out["date"], errors="coerce").map(
            nifty.set_index("date")["nifty_ret_1d"]
        )
        pieces: list[pd.Series] = []
        for _, group in out.groupby("ticker", sort=False):
            stock = pd.to_numeric(group["ret_1d"], errors="coerce")
            market = pd.to_numeric(group["nifty_ret_1d"], errors="coerce")
            cov = stock.rolling(self.beta_lookback_days, min_periods=self.beta_min_observations).cov(market)
            var = market.rolling(self.beta_lookback_days, min_periods=self.beta_min_observations).var()
            beta = cov / (var + 1e-12)
            signal = (-beta).replace([np.inf, -np.inf], np.nan).astype(float)
            signal.index = group.index
            pieces.append(signal)

        if not pieces:
            return pd.Series(np.nan, index=frame.index, dtype=float)
        return pd.concat(pieces).reindex(frame.index).astype(float)

    def _compute_amihud_illiquidity(self, frame: pd.DataFrame) -> pd.Series:
        close = self._series_or_nan(frame, "close")
        volume = self._series_or_nan(frame, "volume")
        ret_1d = self._series_or_nan(frame, "ret_1d")
        rupee_volume = (close * volume).where((close > 0.0) & (volume > 0.0), np.nan)
        illiq_daily = ret_1d.abs() / rupee_volume
        return (
            illiq_daily.groupby(frame["ticker"], sort=False)
            .rolling(self.amihud_lookback_days, min_periods=self.amihud_min_observations)
            .mean()
            .reset_index(level=0, drop=True)
            .replace([np.inf, -np.inf], np.nan)
            .astype(float)
        )

    def _compute_max_ret_20d(self, frame: pd.DataFrame) -> pd.Series:
        ret_1d = self._series_or_nan(frame, "ret_1d")
        return (
            ret_1d.groupby(frame["ticker"], sort=False)
            .rolling(self.max_lookback_days, min_periods=self.max_min_observations)
            .max()
            .reset_index(level=0, drop=True)
            .replace([np.inf, -np.inf], np.nan)
            .astype(float)
        )

    @staticmethod
    def _compute_earnings_quality_ratio(frame: pd.DataFrame) -> pd.Series:
        # I.4: the numerator must be RAW operating cash flow only. Coalescing
        # ``cash_conversion`` (which is itself operating_cash_flow / net_income)
        # into the numerator and then dividing by net_income again produced
        # op_cf / net_income^2 — a different, blown-up quantity precisely in the
        # missing-data case the fallback was meant to handle. Compute the ratio
        # from the raw figure, and use the already-computed cash_conversion ratio
        # directly as the fallback (no second division).
        operating_cash_flow = Gap9AcademicFactors._series_or_nan(frame, "operating_cash_flow")
        net_income = Gap9AcademicFactors._series_or_nan(frame, "net_income").replace(0.0, np.nan)
        ratio = (operating_cash_flow / net_income).replace([np.inf, -np.inf], np.nan)
        proxy = Gap9AcademicFactors._coalesce_numeric(
            frame,
            [
                "cash_conversion",
                "cash_conversion_sector_z",
                "cash_conversion_cs_z",
            ],
        )
        ratio = ratio.where(ratio.notna(), proxy)
        return ratio.clip(lower=-10.0, upper=10.0).astype(float)

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``frame`` with Gap 9 factor columns appended."""
        if frame is None or frame.empty:
            return pd.DataFrame() if frame is None else frame
        if not {"date", "ticker"}.issubset(frame.columns):
            return frame

        out = frame.copy()
        out["_gap9_orig_order"] = np.arange(len(out), dtype=int)
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date", "ticker"]).sort_values(
            ["ticker", "date", "_gap9_orig_order"],
            kind="mergesort",
        )
        for column in self.FUNDAMENTAL_HOLD_COLUMNS:
            if column in out.columns:
                out[column] = (
                    pd.to_numeric(out[column], errors="coerce")
                    .groupby(out["ticker"], sort=False)
                    .ffill()
                )

        out["piotroski_fscore"] = self._compute_piotroski_fscore(out)
        out["bab_signal"] = self._compute_bab_signal(out)
        out["amihud_illiquidity"] = self._compute_amihud_illiquidity(out)
        out["max_ret_20d"] = self._compute_max_ret_20d(out)
        out["earnings_quality_ratio"] = self._compute_earnings_quality_ratio(out)

        for column in self.RAW_COLUMNS:
            out[column] = pd.to_numeric(out[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            out[f"{column}_cs_z"] = self._group_zscore(out[column], out["date"])
            out[f"{column}_cs_rank"] = self._group_rank_centered(out[column], out["date"])

        out = out.sort_values("_gap9_orig_order", kind="mergesort").drop(columns=["_gap9_orig_order"], errors="ignore")
        return out.reset_index(drop=True)
