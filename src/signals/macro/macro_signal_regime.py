"""Macro regime feature builder from GST and CEA datasets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


class MacroRegimeBuilder:
    """Construct market-wide and sector macro regime features."""

    def __init__(self, output_path: str = "data/processed/macro/macro_regime_features.parquet"):
        self.output_path = Path(output_path)

    @staticmethod
    def _prep_gst(gst_df: pd.DataFrame) -> pd.DataFrame:
        if gst_df is None or gst_df.empty:
            return pd.DataFrame()
        g = gst_df.copy()
        if "year_month" in g.columns:
            g["date"] = pd.to_datetime(g["year_month"].astype(str) + "-01", errors="coerce")
            g["date"] = g["date"] + pd.offsets.MonthEnd(0)
        elif "date" in g.columns:
            g["date"] = pd.to_datetime(g["date"], errors="coerce")
        else:
            return pd.DataFrame()

        if "eway_bills_generated" not in g.columns:
            g["eway_bills_generated"] = pd.to_numeric(g.get("bills", np.nan), errors="coerce")
        if "eway_bill_value_crore" not in g.columns:
            g["eway_bill_value_crore"] = pd.to_numeric(g.get("value_crore", np.nan), errors="coerce")

        g["availability_date"] = pd.to_datetime(g.get("availability_date"), errors="coerce")
        missing_av = g["availability_date"].isna()
        # PIT safety: conservative GST publication lag of +30 days.
        g.loc[missing_av, "availability_date"] = g.loc[missing_av, "date"] + pd.Timedelta(days=30)

        g["category"] = g.get("sector", g.get("category", "")).astype(str)
        g = g.dropna(subset=["date"])
        return g

    @staticmethod
    def _prep_power(power_df: pd.DataFrame) -> pd.DataFrame:
        if power_df is None or power_df.empty:
            return pd.DataFrame()
        p = power_df.copy()
        p["date"] = pd.to_datetime(p.get("date"), errors="coerce")
        p["energy_met_mu"] = pd.to_numeric(p.get("energy_met_mu"), errors="coerce")
        p["energy_requirement_mu"] = pd.to_numeric(p.get("energy_requirement_mu"), errors="coerce")
        p["peak_met_gw"] = pd.to_numeric(p.get("peak_met_gw"), errors="coerce")
        p["deficit_pct"] = pd.to_numeric(p.get("deficit_pct"), errors="coerce")
        if p["deficit_pct"].isna().all():
            p["deficit_pct"] = (
                (p["energy_requirement_mu"] - p["energy_met_mu"]) / p["energy_requirement_mu"].replace(0.0, np.nan)
            ) * 100.0
        p["availability_date"] = pd.to_datetime(p.get("availability_date"), errors="coerce")
        missing_av = p["availability_date"].isna()
        # PIT safety: CEA daily data lag of +1 day.
        p.loc[missing_av, "availability_date"] = p.loc[missing_av, "date"] + pd.Timedelta(days=1)
        p = p.dropna(subset=["date"])
        return p

    @staticmethod
    def _trend3(series: pd.Series) -> pd.Series:
        ma3 = series.rolling(3, min_periods=2).mean()
        delta = ma3.diff(1)
        return np.where(delta > 0, 1.0, np.where(delta < 0, -1.0, 0.0))

    @staticmethod
    def _zscore_rolling(series: pd.Series, window: int = 24) -> pd.Series:
        mu = series.rolling(window, min_periods=max(6, window // 4)).mean()
        sd = series.rolling(window, min_periods=max(6, window // 4)).std().replace(0.0, np.nan)
        z = (series - mu) / (sd + 1e-12)
        return z.replace([np.inf, -np.inf], np.nan)

    def build_market_features(self, gst_df: pd.DataFrame, power_df: pd.DataFrame) -> pd.DataFrame:
        """Build market-wide macro features (one row per date)."""
        gst = self._prep_gst(gst_df)
        power = self._prep_power(power_df)

        m_gst = pd.DataFrame()
        if not gst.empty:
            m_gst = (
                gst.groupby("date", as_index=False)
                .agg(
                    gst_total_bills=("eway_bills_generated", "sum"),
                    gst_total_value_crore=("eway_bill_value_crore", "sum"),
                    gst_availability_date=("availability_date", "max"),
                )
                .sort_values("date", kind="mergesort")
            )
            m_gst["gst_yoy_growth"] = m_gst["gst_total_bills"].pct_change(12) * 100.0
            m_gst["gst_mom_growth"] = m_gst["gst_total_bills"].pct_change(1) * 100.0
            m_gst["gst_3m_trend"] = self._trend3(m_gst["gst_total_bills"])
            m_gst["gst_value_growth"] = m_gst["gst_total_value_crore"].pct_change(12) * 100.0

        m_power = pd.DataFrame()
        if not power.empty:
            mp = power.copy()
            mp["month_end"] = mp["date"] + pd.offsets.MonthEnd(0)
            m_power = (
                mp.groupby("month_end", as_index=False)
                .agg(
                    power_energy_met_mu=("energy_met_mu", "sum"),
                    power_peak_met_gw=("peak_met_gw", "max"),
                    power_deficit_pct=("deficit_pct", "mean"),
                    power_availability_date=("availability_date", "max"),
                )
                .rename(columns={"month_end": "date"})
                .sort_values("date", kind="mergesort")
            )
            m_power["power_yoy_growth"] = m_power["power_energy_met_mu"].pct_change(12) * 100.0
            m_power["power_mom_growth"] = m_power["power_energy_met_mu"].pct_change(1) * 100.0
            m_power["power_3m_trend"] = self._trend3(m_power["power_energy_met_mu"])

        if m_gst.empty and m_power.empty:
            return pd.DataFrame()
        if m_gst.empty:
            out = m_power.copy()
            out["gst_yoy_growth"] = np.nan
            out["gst_mom_growth"] = np.nan
            out["gst_3m_trend"] = np.nan
            out["gst_value_growth"] = np.nan
            out["gst_availability_date"] = pd.NaT
        elif m_power.empty:
            out = m_gst.copy()
            out["power_yoy_growth"] = np.nan
            out["power_mom_growth"] = np.nan
            out["power_3m_trend"] = np.nan
            out["power_deficit_pct"] = np.nan
            out["power_availability_date"] = pd.NaT
        else:
            out = pd.merge(m_power, m_gst, on="date", how="outer").sort_values("date", kind="mergesort")

        out["macro_activity_composite"] = out[["power_yoy_growth", "gst_yoy_growth"]].mean(axis=1)
        out["macro_regime_label"] = np.where(
            out["macro_activity_composite"] > 5.0,
            "expansion",
            np.where(out["macro_activity_composite"] < -5.0, "contraction", "neutral"),
        )

        out["availability_date"] = out[["power_availability_date", "gst_availability_date"]].max(axis=1)
        out["availability_date"] = pd.to_datetime(out["availability_date"], errors="coerce")
        out["ticker"] = "MARKET"

        keep = [
            "date",
            "availability_date",
            "ticker",
            "power_yoy_growth",
            "power_mom_growth",
            "power_3m_trend",
            "power_deficit_pct",
            "gst_yoy_growth",
            "gst_mom_growth",
            "gst_3m_trend",
            "gst_value_growth",
            "macro_activity_composite",
            "macro_regime_label",
        ]
        for c in keep:
            if c not in out.columns:
                out[c] = np.nan
        return out[keep].reset_index(drop=True)

    def build_sector_features(
        self,
        gst_df: pd.DataFrame,
        sector_mapper,
        metadata_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build sector activity features and map to ticker rows."""
        gst = self._prep_gst(gst_df)
        if gst.empty:
            return pd.DataFrame()

        needed = gst.dropna(subset=["date", "category"]).copy()
        sec = (
            needed.groupby(["date", "category"], as_index=False)
            .agg(
                sector_bills=("eway_bills_generated", "sum"),
                availability_date=("availability_date", "max"),
            )
            .sort_values(["category", "date"], kind="mergesort")
        )
        sec["sector_gst_yoy"] = sec.groupby("category", sort=False)["sector_bills"].pct_change(12) * 100.0
        sec["sector_gst_mom"] = sec.groupby("category", sort=False)["sector_bills"].pct_change(1) * 100.0
        sec["sector_gst_3m_trend"] = sec.groupby("category", sort=False)["sector_bills"].transform(self._trend3)
        sec["sector_activity_zscore"] = sec.groupby("category", sort=False)["sector_bills"].transform(
            lambda x: self._zscore_rolling(x, window=24)
        )

        md = metadata_df.copy() if metadata_df is not None and not metadata_df.empty else pd.DataFrame()
        if "ticker" not in md.columns:
            return pd.DataFrame()
        md["ticker"] = md["ticker"].astype(str)

        rows: list[dict] = []
        for tk in sorted(md["ticker"].dropna().astype(str).unique()):
            cats = sector_mapper.get_relevant_gst_categories(tk, metadata_df=md)
            if not cats:
                continue
            sub = sec[sec["category"].isin(cats)].copy()
            if sub.empty:
                continue
            agg = (
                sub.groupby("date", as_index=False)
                .agg(
                    availability_date=("availability_date", "max"),
                    sector_gst_yoy=("sector_gst_yoy", "mean"),
                    sector_gst_mom=("sector_gst_mom", "mean"),
                    sector_gst_3m_trend=("sector_gst_3m_trend", "mean"),
                    sector_activity_zscore=("sector_activity_zscore", "mean"),
                )
                .sort_values("date", kind="mergesort")
            )
            meta_row = md[md["ticker"].astype(str) == tk].head(1)
            sec_name = ""
            if not meta_row.empty:
                sec_name = str(meta_row.iloc[0].get("sector", meta_row.iloc[0].get("industry", "")) or "").strip()
            agg["ticker"] = tk
            agg["sector"] = sec_name
            rows.extend(agg.to_dict("records"))

        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def build_combined_features(
        self,
        gst_df: pd.DataFrame,
        power_df: pd.DataFrame,
        sector_mapper,
        metadata_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build and persist combined macro features."""
        market = self.build_market_features(gst_df, power_df)
        sector = self.build_sector_features(gst_df, sector_mapper, metadata_df)

        if market.empty and sector.empty:
            out = pd.DataFrame(
                columns=[
                    "date",
                    "availability_date",
                    "ticker",
                    "sector",
                    "power_yoy_growth",
                    "power_mom_growth",
                    "power_3m_trend",
                    "power_deficit_pct",
                    "gst_yoy_growth",
                    "gst_mom_growth",
                    "gst_3m_trend",
                    "gst_value_growth",
                    "macro_activity_composite",
                    "macro_regime_label",
                    "sector_gst_yoy",
                    "sector_gst_mom",
                    "sector_gst_3m_trend",
                    "sector_activity_zscore",
                ]
            )
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            out.to_parquet(self.output_path, index=False)
            return out

        out = pd.concat([market, sector], ignore_index=True, sort=False)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(self.output_path, index=False)
        return out
