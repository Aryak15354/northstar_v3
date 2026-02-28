"""Historical feature factory for research mode."""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


class FeatureFactory:
    """Builds cross-sectional + time-series features from historical artifacts."""

    def __init__(self, target_horizon_days: int = 5):
        self.target_horizon_days = int(max(1, target_horizon_days))

    @staticmethod
    def _as_date(df: pd.DataFrame, preferred: Iterable[str]) -> pd.Series:
        for c in preferred:
            if c in df.columns:
                out = pd.to_datetime(df[c], errors="coerce")
                try:
                    if getattr(out.dt, "tz", None) is not None:
                        out = out.dt.tz_localize(None)
                except Exception:
                    pass
                try:
                    out = out.astype("datetime64[ns]")
                except Exception:
                    out = pd.to_datetime(out, errors="coerce")
                return out
        return pd.Series(pd.NaT, index=df.index)

    @staticmethod
    def _merge_asof_by_ticker(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
        if left.empty or right.empty or "ticker" not in left.columns or "ticker" not in right.columns:
            return left

        out = []
        for ticker, lgrp in left.groupby("ticker", sort=False):
            rgrp = right[right["ticker"].astype(str) == str(ticker)].copy()
            if rgrp.empty:
                out.append(lgrp)
                continue
            l = lgrp.sort_values("date")
            r = rgrp.sort_values("date").drop(columns=["ticker"], errors="ignore")
            l["date"] = pd.to_datetime(l["date"], errors="coerce").astype("datetime64[ns]")
            r["date"] = pd.to_datetime(r["date"], errors="coerce").astype("datetime64[ns]")
            merged = pd.merge_asof(l, r, on="date", direction="backward")
            out.append(merged)
        merged_all = pd.concat(out, ignore_index=True) if out else left
        if "ticker" not in merged_all.columns and "ticker_x" in merged_all.columns:
            merged_all = merged_all.rename(columns={"ticker_x": "ticker"})
        if "ticker_y" in merged_all.columns:
            merged_all = merged_all.drop(columns=["ticker_y"], errors="ignore")
        return merged_all

    @staticmethod
    def _group_zscore(values: pd.Series, groups: pd.Series, clip_abs: float = 6.0) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        mu = v.groupby(groups, sort=False).transform("mean")
        sigma = v.groupby(groups, sort=False).transform("std").replace(0.0, np.nan)
        z = (v - mu) / (sigma + 1e-12)
        z = z.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if float(clip_abs) > 0.0:
            z = z.clip(lower=-float(clip_abs), upper=float(clip_abs))
        return z.astype(float)

    @staticmethod
    def _group_rank_centered(values: pd.Series, groups: pd.Series) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        r = v.groupby(groups, sort=False).rank(method="average", pct=True)
        r = r.fillna(0.5) - 0.5
        return r.astype(float)

    def _add_structural_alpha_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        out = panel.copy()
        if out.empty or "date" not in out.columns:
            return out

        sector_col = next((c for c in ["Industry", "industry", "Sector", "sector"] if c in out.columns), None)
        if sector_col is None:
            sector = pd.Series("UNKNOWN", index=out.index, dtype="object")
        else:
            sector = out[sector_col].astype(str).fillna("UNKNOWN")
        out["sector_name"] = sector

        # Sector-relative factors: cross-sectional de-biasing from broad beta.
        sector_group = [out["date"], sector]
        sector_rel_cols = [
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "mom_20d",
            "mom_60d",
            "vol_20d",
            "vol_60d",
            "price_to_sma20",
        ]
        for col in sector_rel_cols:
            if col not in out.columns:
                continue
            v = pd.to_numeric(out[col], errors="coerce")
            sec_mean = v.groupby(sector_group, sort=False).transform("mean")
            out[f"{col}_sector_rel"] = v - sec_mean

        if {"mom_20d_sector_rel", "vol_20d"}.issubset(set(out.columns)):
            sec_vol = (
                pd.to_numeric(out["vol_20d"], errors="coerce")
                .abs()
                .groupby(sector_group, sort=False)
                .transform("mean")
            )
            out["mom_20d_sector_ir"] = pd.to_numeric(out["mom_20d_sector_rel"], errors="coerce") / (sec_vol + 1e-6)

        # Residual momentum engine: sector-neutral daily return accumulation.
        if "ret_1d" in out.columns and "ticker" in out.columns:
            ret_1d = pd.to_numeric(out["ret_1d"], errors="coerce")
            sec_ret_1d = ret_1d.groupby(sector_group, sort=False).transform("mean")
            out["ret_1d_sector_resid"] = ret_1d - sec_ret_1d
            g_ticker = out.groupby("ticker", sort=False)
            resid = pd.to_numeric(out["ret_1d_sector_resid"], errors="coerce").fillna(0.0)

            out["res_mom_5d"] = (
                g_ticker["ret_1d_sector_resid"].rolling(5, min_periods=3).sum().reset_index(level=0, drop=True)
            )
            out["res_mom_20d"] = (
                g_ticker["ret_1d_sector_resid"].rolling(20, min_periods=10).sum().reset_index(level=0, drop=True)
            )
            out["res_mom_60d"] = (
                g_ticker["ret_1d_sector_resid"].rolling(60, min_periods=30).sum().reset_index(level=0, drop=True)
            )
            out["res_mom_20d_slope_5d"] = g_ticker["res_mom_20d"].diff(5)
            out["res_mom_20d_accel_5d"] = g_ticker["res_mom_20d_slope_5d"].diff(5)

            if "vol_20d" in out.columns:
                vol_scale = pd.to_numeric(out["vol_20d"], errors="coerce").abs() * np.sqrt(20.0)
                out["res_mom_20d_ir"] = pd.to_numeric(out["res_mom_20d"], errors="coerce") / (vol_scale + 1e-6)
            if {"res_mom_20d", "vol_z20"}.issubset(set(out.columns)):
                out["res_mom20_x_liquidity"] = (
                    pd.to_numeric(out["res_mom_20d"], errors="coerce")
                    * pd.to_numeric(out["vol_z20"], errors="coerce")
                )

        # Structural interactions.
        if {"mom_20d", "vol_z20"}.issubset(set(out.columns)):
            out["mom20_x_liquidity"] = (
                pd.to_numeric(out["mom_20d"], errors="coerce") * pd.to_numeric(out["vol_z20"], errors="coerce")
            )
        if {"vol_20d", "regime_modifier"}.issubset(set(out.columns)):
            out["vol20_x_regime_modifier"] = (
                pd.to_numeric(out["vol_20d"], errors="coerce")
                * pd.to_numeric(out["regime_modifier"], errors="coerce")
            )
        if {"mkt_sent_uncertainty", "mkt_sent_narrative_conflict"}.issubset(set(out.columns)):
            out["sent_conflict_x_uncertainty"] = (
                pd.to_numeric(out["mkt_sent_uncertainty"], errors="coerce")
                * pd.to_numeric(out["mkt_sent_narrative_conflict"], errors="coerce")
            )
        if {"mom_20d", "macro_regime_score"}.issubset(set(out.columns)):
            out["mom20_x_macro_regime"] = (
                pd.to_numeric(out["mom_20d"], errors="coerce")
                * pd.to_numeric(out["macro_regime_score"], errors="coerce")
            )

        # Cross-sectional transforms per date: ranking and z-score variants.
        cs_seed_cols = [
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "mom_20d",
            "mom_60d",
            "vol_20d",
            "vol_60d",
            "price_to_sma20",
            "vol_z20",
            "posterior_gap",
            "posterior_variance",
            "agreement_score",
            "regime_modifier",
            "mom_20d_sector_rel",
            "mom_60d_sector_rel",
            "ret_20d_sector_rel",
            "mom_20d_sector_ir",
            "ret_1d_sector_resid",
            "res_mom_5d",
            "res_mom_20d",
            "res_mom_60d",
            "res_mom_20d_slope_5d",
            "res_mom_20d_accel_5d",
            "res_mom_20d_ir",
            "res_mom20_x_liquidity",
            "mom20_x_liquidity",
            "vol20_x_regime_modifier",
            "sent_conflict_x_uncertainty",
            "mom20_x_macro_regime",
        ]
        for col in cs_seed_cols:
            if col not in out.columns or not pd.api.types.is_numeric_dtype(out[col]):
                continue
            out[f"{col}_cs_z"] = self._group_zscore(out[col], out["date"], clip_abs=6.0)
            out[f"{col}_cs_rank"] = self._group_rank_centered(out[col], out["date"])

        return out

    def build_features(
        self,
        prices: pd.DataFrame,
        fundamentals: Optional[pd.DataFrame] = None,
        macro: Optional[pd.DataFrame] = None,
        valuation_posterior: Optional[pd.DataFrame] = None,
        sentiment_company: Optional[pd.DataFrame] = None,
        sentiment_market: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        if prices is None or prices.empty:
            return pd.DataFrame()

        p = prices.copy()
        p["date"] = self._as_date(p, ["date", "Date", "timestamp"])
        close_col = "Close" if "Close" in p.columns else ("close" if "close" in p.columns else None)
        if close_col is None or "ticker" not in p.columns:
            return pd.DataFrame()

        p["close"] = pd.to_numeric(p[close_col], errors="coerce")
        p["volume"] = pd.to_numeric(p.get("Volume", p.get("volume", np.nan)), errors="coerce")
        p = p.dropna(subset=["date", "ticker", "close"])
        p = p.loc[p["close"] > 0.0].sort_values(["ticker", "date"])
        if p.empty:
            return pd.DataFrame()

        g = p.groupby("ticker", sort=False)
        p["ret_1d"] = g["close"].pct_change(fill_method=None)
        p["ret_5d"] = g["close"].pct_change(5, fill_method=None)
        p["ret_20d"] = g["close"].pct_change(20, fill_method=None)
        p["vol_20d"] = g["ret_1d"].rolling(20).std().reset_index(level=0, drop=True)
        p["vol_60d"] = g["ret_1d"].rolling(60).std().reset_index(level=0, drop=True)
        p["mom_20d"] = g["close"].pct_change(20, fill_method=None)
        p["mom_60d"] = g["close"].pct_change(60, fill_method=None)
        p["price_to_sma20"] = p["close"] / g["close"].rolling(20).mean().reset_index(level=0, drop=True)

        if p["volume"].notna().any():
            vol_roll = g["volume"].rolling(20)
            p["vol_z20"] = (
                p["volume"] - vol_roll.mean().reset_index(level=0, drop=True)
            ) / (vol_roll.std().reset_index(level=0, drop=True) + 1e-12)
        else:
            p["vol_z20"] = 0.0

        p["forward_return_5d"] = g["close"].shift(-self.target_horizon_days) / p["close"] - 1.0

        panel = p[
            [
                "date",
                "ticker",
                "close",
                "ret_1d",
                "ret_5d",
                "ret_20d",
                "vol_20d",
                "vol_60d",
                "mom_20d",
                "mom_60d",
                "price_to_sma20",
                "vol_z20",
                "forward_return_5d",
            ]
        ].copy()

        if isinstance(fundamentals, pd.DataFrame) and not fundamentals.empty:
            f = fundamentals.copy()
            f["date"] = self._as_date(f, ["date", "Date", "timestamp"])
            needed = [
                "date",
                "ticker",
                "Industry",
                "industry",
                "Sector",
                "sector",
                "revenue",
                "ebitda",
                "operating_income",
                "net_income",
                "equity",
                "total_debt",
                "operating_cash_flow",
                "free_cash_flow",
                "shares_outstanding",
            ]
            keep = [c for c in needed if c in f.columns]
            f = f[keep].copy()
            for c in keep:
                if c not in {"date", "ticker"}:
                    f[c] = pd.to_numeric(f[c], errors="coerce")
            panel = self._merge_asof_by_ticker(panel, f)
            panel["ni_margin"] = panel["net_income"] / (panel["revenue"] + 1e-12)
            panel["debt_to_equity"] = panel["total_debt"] / (panel["equity"] + 1e-12)
            panel["fcf_to_ocf"] = panel["free_cash_flow"] / (panel["operating_cash_flow"] + 1e-12)

        if isinstance(macro, pd.DataFrame) and not macro.empty:
            m = macro.copy()
            m["date"] = self._as_date(m, ["date", "Date", "timestamp", "intelligence_timestamp_str"])
            m = m.dropna(subset=["date"]).sort_values("date")

            # Prefix numeric macro columns to prevent collisions.
            macro_numeric = [
                c
                for c in m.columns
                if c != "date" and pd.api.types.is_numeric_dtype(m[c])
            ]
            rename = {c: f"macro_{c}" for c in macro_numeric}
            m = m.rename(columns=rename)

            # Keep one daily record for asof merge.
            m = m.drop_duplicates(subset=["date"], keep="last")
            panel = pd.merge_asof(
                panel.sort_values("date"),
                m.sort_values("date"),
                on="date",
                direction="backward",
            )

            if "macro_regime" in macro.columns:
                regime = macro[["date", "macro_regime"]].copy()
                regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
                regime = regime.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
                panel = pd.merge_asof(panel.sort_values("date"), regime.sort_values("date"), on="date", direction="backward")
            elif "regime" in macro.columns:
                regime = macro[["date", "regime"]].copy()
                regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
                regime = regime.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
                panel = pd.merge_asof(panel.sort_values("date"), regime.sort_values("date"), on="date", direction="backward")

        if isinstance(valuation_posterior, pd.DataFrame) and not valuation_posterior.empty:
            v = valuation_posterior.copy()
            v["date"] = self._as_date(v, ["date", "Date", "timestamp"])
            keep = [
                c
                for c in [
                    "date",
                    "ticker",
                    "posterior_gap",
                    "posterior_variance",
                    "agreement_score",
                    "posterior_confidence",
                    "regime_modifier",
                    "macro_compression",
                ]
                if c in v.columns
            ]
            v = v[keep].copy()
            for c in keep:
                if c not in {"date", "ticker"}:
                    v[c] = pd.to_numeric(v[c], errors="coerce")
            panel = self._merge_asof_by_ticker(panel, v)

        if isinstance(sentiment_company, pd.DataFrame) and not sentiment_company.empty:
            s = sentiment_company.copy()
            s["date"] = self._as_date(s, ["date", "Date", "timestamp"])
            if "ticker" not in s.columns and "symbol" in s.columns:
                s["ticker"] = s["symbol"].astype(str)
            if "ticker" in s.columns:
                s["ticker"] = s["ticker"].astype(str)
            keep = [
                c
                for c in [
                    "date",
                    "ticker",
                    "sentiment_score",
                    "trend_score",
                    "event_shock_factor",
                    "headline_count",
                    "sentiment_intensity",
                    "signed_sentiment_intensity",
                    "northstar_score",
                    "momentum_score",
                    "mispricing",
                    "confirmation",
                    "cohesive_alpha_score",
                ]
                if c in s.columns
            ]
            if {"date", "ticker"}.issubset(set(keep)):
                s = s[keep].copy()
                for c in keep:
                    if c not in {"date", "ticker"}:
                        s[c] = pd.to_numeric(s[c], errors="coerce")
                rename = {c: f"sent_{c}" for c in s.columns if c not in {"date", "ticker"}}
                s = s.rename(columns=rename)
                panel = self._merge_asof_by_ticker(panel, s)

        if isinstance(sentiment_market, pd.DataFrame) and not sentiment_market.empty:
            ms = sentiment_market.copy()
            ms["date"] = self._as_date(ms, ["date", "Date", "timestamp"])
            keep = [
                c
                for c in [
                    "date",
                    "polarity",
                    "conviction",
                    "uncertainty",
                    "narrative_cohesion",
                    "policy_weight",
                    "narrative_conflict",
                    "delta_polarity",
                    "delta_uncertainty",
                    "delta_conviction",
                    "change_velocity",
                    "micro_shift_score",
                ]
                if c in ms.columns
            ]
            if "date" in keep:
                ms = ms[keep].copy()
                for c in keep:
                    if c != "date":
                        ms[c] = pd.to_numeric(ms[c], errors="coerce")
                rename = {c: f"mkt_sent_{c}" for c in ms.columns if c != "date"}
                ms = ms.rename(columns=rename)
                ms = ms.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
                panel_sorted = panel.sort_values("date").copy()
                panel_sorted["date"] = pd.to_datetime(panel_sorted["date"], errors="coerce").astype("datetime64[ns]")
                ms_sorted = ms.sort_values("date").copy()
                ms_sorted["date"] = pd.to_datetime(ms_sorted["date"], errors="coerce").astype("datetime64[ns]")
                panel = pd.merge_asof(
                    panel_sorted,
                    ms_sorted,
                    on="date",
                    direction="backward",
                )

        panel = self._add_structural_alpha_features(panel)

        # Replace non-finite values only on numeric columns; object columns may
        # legitimately contain array-like payloads from upstream artifacts.
        numeric_cols = list(panel.select_dtypes(include=[np.number]).columns)
        if numeric_cols:
            panel.loc[:, numeric_cols] = panel[numeric_cols].replace([np.inf, -np.inf], np.nan)
        panel = panel.sort_values(["date", "ticker"]).dropna(subset=["forward_return_5d"])
        return panel

    @staticmethod
    def build_tft_feature_split(
        panel: pd.DataFrame,
        *,
        target_col: str = "forward_return_5d",
    ) -> dict:
        """Create TFT-style static/known/observed feature groups.

        Returns a dict with:
        - static_features/static_feature_names
        - known_dynamic_features/known_dynamic_feature_names
        - observed_dynamic_features/observed_dynamic_feature_names
        - ticker_ids/sector_ids
        """
        if panel is None or panel.empty:
            return {
                "static_features": np.empty((0, 0), dtype=np.float32),
                "known_dynamic_features": np.empty((0, 0), dtype=np.float32),
                "observed_dynamic_features": np.empty((0, 0), dtype=np.float32),
                "static_feature_names": [],
                "known_dynamic_feature_names": [],
                "observed_dynamic_feature_names": [],
                "ticker_ids": np.empty((0,), dtype=np.int64),
                "sector_ids": np.empty((0,), dtype=np.int64),
            }

        df = panel.copy()
        if "date" not in df.columns:
            raise ValueError("panel must include date column for TFT split")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).copy()

        # ------------------------------------------------------------------
        # Known dynamic features: calendar/expiry-cycle terms known in advance.
        # ------------------------------------------------------------------
        dt = df["date"]
        dow = dt.dt.dayofweek.astype(float)
        month = dt.dt.month.astype(float)
        dom = dt.dt.day.astype(float)
        woy = dt.dt.isocalendar().week.astype(float)

        # India weekly index options mostly expire Thursday; create a deterministic
        # countdown feature [0..6] so model can learn expiry-cycle behavior.
        # weekday: Mon=0 ... Sun=6
        days_to_thu = ((3 - dt.dt.dayofweek) % 7).astype(float)

        known = pd.DataFrame(
            {
                "known_dow_sin": np.sin(2.0 * np.pi * dow / 7.0),
                "known_dow_cos": np.cos(2.0 * np.pi * dow / 7.0),
                "known_month_sin": np.sin(2.0 * np.pi * month / 12.0),
                "known_month_cos": np.cos(2.0 * np.pi * month / 12.0),
                "known_dom_sin": np.sin(2.0 * np.pi * dom / 31.0),
                "known_dom_cos": np.cos(2.0 * np.pi * dom / 31.0),
                "known_woy_sin": np.sin(2.0 * np.pi * woy / 52.0),
                "known_woy_cos": np.cos(2.0 * np.pi * woy / 52.0),
                "known_is_month_start": dt.dt.is_month_start.astype(float),
                "known_is_month_end": dt.dt.is_month_end.astype(float),
                "known_days_to_weekly_expiry": days_to_thu,
            },
            index=df.index,
        )

        # ------------------------------------------------------------------
        # Static features: slow-moving firm characteristics + valuation confidence.
        # ------------------------------------------------------------------
        static_candidates = [
            "ni_margin",
            "debt_to_equity",
            "fcf_to_ocf",
            "equity",
            "total_debt",
            "shares_outstanding",
            "posterior_confidence",
            "posterior_variance",
            "agreement_score",
            "macro_compression",
            "regime_modifier",
        ]
        static_cols = [c for c in static_candidates if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        static_df = df[static_cols].copy() if static_cols else pd.DataFrame(index=df.index)

        # ------------------------------------------------------------------
        # Observed dynamic features: market/macro/valuation terms only known at t.
        # ------------------------------------------------------------------
        base_observed = [
            "close",
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "vol_20d",
            "vol_60d",
            "mom_20d",
            "mom_60d",
            "price_to_sma20",
            "vol_z20",
            "posterior_gap",
            "posterior_variance",
            "agreement_score",
            "regime_code",
        ]
        macro_cols = [c for c in df.columns if c.startswith("macro_") and pd.api.types.is_numeric_dtype(df[c])]
        sentiment_cols = [
            c
            for c in df.columns
            if (c.startswith("sent_") or c.startswith("mkt_sent_")) and pd.api.types.is_numeric_dtype(df[c])
        ]
        observed_cols = [c for c in base_observed + macro_cols + sentiment_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        # Ensure no target leakage.
        observed_cols = [c for c in observed_cols if c != target_col and not c.startswith("forward_return")]
        observed_df = df[observed_cols].copy() if observed_cols else pd.DataFrame(index=df.index)

        # ------------------------------------------------------------------
        # Static categorical ids for embeddings.
        # ------------------------------------------------------------------
        ticker_codes = (
            df["ticker"].astype(str).fillna("UNKNOWN").astype("category").cat.codes.astype(np.int64)
            if "ticker" in df.columns
            else np.zeros(len(df), dtype=np.int64)
        )

        sector_col = None
        for c in ["Industry", "industry", "Sector", "sector"]:
            if c in df.columns:
                sector_col = c
                break
        if sector_col is None:
            sector_codes = np.zeros(len(df), dtype=np.int64)
        else:
            sector_codes = df[sector_col].astype(str).fillna("UNKNOWN").astype("category").cat.codes.astype(np.int64)

        def _to_numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
            if frame.empty:
                return frame
            out = frame.replace([np.inf, -np.inf], np.nan)
            out = out.apply(pd.to_numeric, errors="coerce")
            out = out.fillna(out.median(numeric_only=True)).fillna(0.0)
            return out

        static_df = _to_numeric_frame(static_df)
        known = _to_numeric_frame(known)
        observed_df = _to_numeric_frame(observed_df)

        return {
            "static_features": static_df.to_numpy(dtype=np.float32) if not static_df.empty else np.empty((len(df), 0), dtype=np.float32),
            "known_dynamic_features": known.to_numpy(dtype=np.float32) if not known.empty else np.empty((len(df), 0), dtype=np.float32),
            "observed_dynamic_features": observed_df.to_numpy(dtype=np.float32) if not observed_df.empty else np.empty((len(df), 0), dtype=np.float32),
            "static_feature_names": list(static_df.columns),
            "known_dynamic_feature_names": list(known.columns),
            "observed_dynamic_feature_names": list(observed_df.columns),
            "ticker_ids": np.asarray(ticker_codes, dtype=np.int64),
            "sector_ids": np.asarray(sector_codes, dtype=np.int64),
        }
