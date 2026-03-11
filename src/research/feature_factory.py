"""Historical feature factory for research mode."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureFactory:
    """Builds cross-sectional + time-series features from historical artifacts."""

    def __init__(
        self,
        target_horizon_days: int = 5,
        *,
        enable_pit_fundamentals: bool = True,
        pit_fundamental_lag_days: int = 60,
        pit_announcement_plus_days: int = 1,
        use_announcement_dates: bool = True,
        use_et500_features: bool = False,
        use_screener_features: bool = False,
        screener_fundamentals_path: str = "data/processed/screener_fundamentals_annual.csv",
        screener_shareholding_path: str = "data/processed/screener_shareholding.csv",
        use_screener_extended_features: bool = False,  # backward-compat alias
        config: Optional[dict[str, Any]] = None,
    ):
        self.config = dict(config or {})
        self.target_horizon_days = int(max(1, target_horizon_days))
        self.enable_pit_fundamentals = bool(enable_pit_fundamentals)
        self.pit_fundamental_lag_days = int(max(0, pit_fundamental_lag_days))
        self.pit_announcement_plus_days = int(max(0, pit_announcement_plus_days))
        self.use_announcement_dates = bool(use_announcement_dates)
        self.use_et500_features = bool(use_et500_features)
        self.use_screener_features = bool(
            self.config.get("use_screener_features", use_screener_features)
            or self.config.get("use_screener_extended_features", use_screener_extended_features)
        )
        self.screener_fundamentals_path = str(
            self.config.get(
                "screener_fundamentals_path",
                self.config.get("screener_annual_path", screener_fundamentals_path),
            )
        )
        self.screener_shareholding_path = str(
            self.config.get(
                "screener_shareholding_path",
                screener_shareholding_path,
            )
        )
        self.use_alternative_features = bool(self.config.get("use_alternative_features", False))
        self.alternative_data_path = str(self.config.get("alternative_data_path", "data/processed/alternative"))
        self.alternative_features_available = self.config.get("alternative_features_available", {}) or {}
        self.use_sentiment_features = bool(self.config.get("use_sentiment_features", False))
        self.use_sentiment_regime = bool(self.config.get("use_sentiment_regime", False))
        self.sentiment_path = str(
            self.config.get("sentiment_path", "data/processed/sentiment/ticker_sentiment_daily.parquet")
        )
        self.market_sentiment_path = str(
            self.config.get("market_sentiment_path", "data/processed/sentiment/market_sentiment_daily.parquet")
        )
        self.use_macro_features = bool(self.config.get("use_macro_features", False))
        self.macro_features_path = str(
            self.config.get("macro_features_path", "data/processed/macro/macro_regime_features.parquet")
        )

        self._screener_annual: Optional[pd.DataFrame] = None
        self._screener_shareholding: Optional[pd.DataFrame] = None
        if bool(self.use_screener_features):
            self._screener_annual = self._load_screener_annual()
            self._screener_shareholding = self._load_screener_shareholding()

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
    def _merge_asof_by_ticker(
        left: pd.DataFrame,
        right: pd.DataFrame,
        *,
        left_on: str = "date",
        right_on: str = "date",
    ) -> pd.DataFrame:
        if left.empty or right.empty or "ticker" not in left.columns or "ticker" not in right.columns:
            return left

        ldf = left.copy()
        rdf = right.copy()
        ldf["ticker"] = ldf["ticker"].astype(str)
        rdf["ticker"] = rdf["ticker"].astype(str)
        ldf[left_on] = pd.to_datetime(ldf[left_on], errors="coerce")
        rdf[right_on] = pd.to_datetime(rdf[right_on], errors="coerce")
        ldf = ldf.dropna(subset=["ticker", left_on]).sort_values(["ticker", left_on], kind="mergesort")
        rdf = rdf.dropna(subset=["ticker", right_on]).sort_values(["ticker", right_on], kind="mergesort")

        out = []
        for ticker, lgrp in ldf.groupby("ticker", sort=True):
            rgrp = rdf[rdf["ticker"] == str(ticker)].copy()
            if rgrp.empty:
                out.append(lgrp)
                continue
            l = lgrp.sort_values(left_on, kind="mergesort")
            r = rgrp.sort_values(right_on, kind="mergesort").drop(columns=["ticker"], errors="ignore")
            l[left_on] = pd.to_datetime(l[left_on], errors="coerce").astype("datetime64[ns]")
            r[right_on] = pd.to_datetime(r[right_on], errors="coerce").astype("datetime64[ns]")
            merged = pd.merge_asof(
                l,
                r,
                left_on=left_on,
                right_on=right_on,
                direction="backward",
                allow_exact_matches=True,
            )
            out.append(merged)
        merged_all = pd.concat(out, ignore_index=True) if out else ldf
        if "ticker" not in merged_all.columns and "ticker_x" in merged_all.columns:
            merged_all = merged_all.rename(columns={"ticker_x": "ticker"})
        if "ticker_y" in merged_all.columns:
            merged_all = merged_all.drop(columns=["ticker_y"], errors="ignore")
        return merged_all.sort_values([left_on, "ticker"], kind="mergesort").reset_index(drop=True)

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

    @staticmethod
    def _concat_new_columns(frame: pd.DataFrame, new_cols: dict[str, pd.Series]) -> pd.DataFrame:
        """Append many columns at once to avoid DataFrame fragmentation."""
        if not new_cols:
            return frame
        add = pd.DataFrame(new_cols, index=frame.index)
        overlap = [c for c in add.columns if c in frame.columns]
        base = frame.drop(columns=overlap, errors="ignore") if overlap else frame
        return pd.concat([base, add], axis=1)

    def _append_cross_sectional_transforms(
        self,
        frame: pd.DataFrame,
        cols: Iterable[str],
        *,
        groups: Optional[pd.Series] = None,
        clip_abs: float = 6.0,
        coerce_source: bool = False,
    ) -> pd.DataFrame:
        if frame.empty:
            return frame
        out = frame
        grp = groups if groups is not None else out["date"]
        source_updates: dict[str, pd.Series] = {}
        derived: dict[str, pd.Series] = {}
        for col in cols:
            if col not in out.columns:
                continue
            series = pd.to_numeric(out[col], errors="coerce")
            if coerce_source:
                source_updates[str(col)] = series
            derived[f"{col}_cs_z"] = self._group_zscore(series, grp, clip_abs=clip_abs)
            derived[f"{col}_cs_rank"] = self._group_rank_centered(series, grp)
        if source_updates:
            out = out.copy()
            source_df = pd.DataFrame(source_updates, index=out.index)
            out.loc[:, list(source_df.columns)] = source_df
        return self._concat_new_columns(out, derived)

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(".NS"):
            return s
        if "." in s:
            s = s.split(".", 1)[0]
        return f"{s}.NS"

    @staticmethod
    def _resolve_column(columns: Iterable[str], aliases: Iterable[str]) -> Optional[str]:
        norm_cols = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): str(c) for c in columns}
        for alias in aliases:
            key = re.sub(r"[^a-z0-9]+", "", str(alias).lower())
            if key in norm_cols:
                return norm_cols[key]
        return None

    @staticmethod
    def _timeseries_zscore_by_date(values: pd.Series, dates: pd.Series, window: int = 252) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        d = pd.to_datetime(dates, errors="coerce")
        work = pd.DataFrame({"date": d, "value": v}).dropna(subset=["date"])
        if work.empty:
            return pd.Series(0.0, index=values.index, dtype=float)
        work = work.sort_values("date", kind="mergesort")
        by_date = work.groupby("date", as_index=False)["value"].last()
        roll_win = max(20, int(window))
        mu = by_date["value"].rolling(roll_win, min_periods=20).mean()
        sd = by_date["value"].rolling(roll_win, min_periods=20).std().replace(0.0, np.nan)
        z = ((by_date["value"] - mu) / (sd + 1e-12)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        by_date["z"] = z.clip(-6.0, 6.0)
        mapped = pd.DataFrame({"date": d}).merge(by_date[["date", "z"]], on="date", how="left")["z"]
        return pd.to_numeric(mapped, errors="coerce").fillna(0.0).astype(float)

    @staticmethod
    def _safe_load_table(path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            if path.suffix.lower() in {".parquet", ".pq"}:
                return pd.read_parquet(path)
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _is_alternative_family_enabled(self, family: str) -> bool:
        cfg = self.alternative_features_available
        if not isinstance(cfg, dict) or not cfg:
            return True
        aliases = {
            "bulk_deals": ("bulk_deals",),
            "pledge": ("pledge", "promoter_pledge"),
            "earnings": ("earnings", "earnings_dates"),
            "ratings": ("ratings", "credit_ratings"),
            "announcements": ("announcements", "order_announcements"),
        }
        for key in aliases.get(family, (family,)):
            if key in cfg:
                return bool(cfg.get(key))
        return True

    def _merge_sentiment_training_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        sent = self._safe_load_table(Path(self.sentiment_path))
        if sent.empty:
            return panel

        out = panel.copy()
        sent = sent.copy()
        sent["date"] = self._as_date(sent, ["date", "Date", "timestamp"])
        if "availability_date" in sent.columns:
            sent["availability_date"] = self._as_date(sent, ["availability_date"])
        else:
            # PIT safety fallback: sentiment dated D is only tradable from D+1 BDay.
            sent["availability_date"] = self._as_date(sent, ["date"]) + pd.offsets.BDay(1)
        if "ticker" not in sent.columns:
            return out
        sent["ticker"] = sent["ticker"].map(self._normalize_ticker)
        sent = sent.dropna(subset=["ticker", "availability_date"]).sort_values(["ticker", "availability_date"], kind="mergesort")
        if sent.empty:
            return out

        sent["sentiment_polarity"] = pd.to_numeric(sent.get("sentiment_polarity"), errors="coerce")
        sent["sentiment_conviction"] = pd.to_numeric(sent.get("sentiment_conviction"), errors="coerce")
        sent["sentiment_surprise"] = pd.to_numeric(sent.get("sentiment_surprise"), errors="coerce")
        sent["sentiment_uncertainty"] = pd.to_numeric(sent.get("sentiment_uncertainty"), errors="coerce")
        sent["news_volume"] = pd.to_numeric(sent.get("news_volume"), errors="coerce")
        sent = sent.sort_values(["ticker", "date"], kind="mergesort")
        g = sent.groupby("ticker", sort=False)
        sent["sentiment_polarity_5d_ma"] = g["sentiment_polarity"].transform(lambda x: x.rolling(5, min_periods=1).mean())
        sent["sentiment_polarity_momentum"] = g["sentiment_polarity"].transform(lambda x: x - x.shift(5))
        sent["sentiment_volume_20d_avg"] = g["news_volume"].transform(lambda x: x.rolling(20, min_periods=1).mean())
        sent["sentiment_volume_spike"] = sent["news_volume"] / sent["sentiment_volume_20d_avg"].replace(0, 1)
        sent["sentiment_conviction_x_polarity"] = sent["sentiment_polarity"] * sent["sentiment_conviction"]
        sent["sentiment_availability_date"] = sent["availability_date"]

        merge_cols = [
            "ticker",
            "sentiment_availability_date",
            "sentiment_polarity",
            "sentiment_conviction",
            "sentiment_surprise",
            "sentiment_uncertainty",
            "sentiment_polarity_5d_ma",
            "sentiment_polarity_momentum",
            "sentiment_volume_spike",
            "sentiment_conviction_x_polarity",
        ]
        out = self._merge_asof_by_ticker(out, sent[merge_cols], left_on="date", right_on="sentiment_availability_date")
        out = out.drop(columns=["sentiment_availability_date"], errors="ignore")
        feat_cols = [c for c in merge_cols if c not in {"ticker", "sentiment_availability_date"}]
        out = self._append_cross_sectional_transforms(
            out,
            feat_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _merge_macro_feature_pack(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        macro_path = Path(self.macro_features_path)
        macro_df = self._safe_load_table(macro_path)
        if macro_df.empty:
            return panel

        out = panel.copy()
        m = macro_df.copy()
        m["date"] = self._as_date(m, ["date", "Date", "timestamp"])
        m["availability_date"] = self._as_date(m, ["availability_date", "date", "Date", "timestamp"])
        if "ticker" in m.columns:
            m["ticker"] = m["ticker"].astype(str)
        else:
            m["ticker"] = ""
        m = m.dropna(subset=["availability_date"]).sort_values("availability_date", kind="mergesort")
        if m.empty:
            return out

        market = m[m["ticker"].astype(str).eq("MARKET")].copy()
        market_cols = [
            c
            for c in [
                "power_yoy_growth",
                "gst_yoy_growth",
                "macro_activity_composite",
                "macro_regime_label",
                "india_market_polarity",
                "india_market_uncertainty",
            ]
            if c in market.columns
        ]
        if not market.empty and market_cols:
            market = market.rename(columns={"availability_date": "macro_availability_date"})
            out = pd.merge_asof(
                out.sort_values("date"),
                market[["macro_availability_date"] + market_cols].sort_values("macro_availability_date", kind="mergesort"),
                left_on="date",
                right_on="macro_availability_date",
                direction="backward",
                allow_exact_matches=True,
            )
            out = out.drop(columns=["macro_availability_date"], errors="ignore")

            market_num_cols = [c for c in market_cols if c != "macro_regime_label"]
            if market_num_cols:
                numeric_updates = {c: pd.to_numeric(out[c], errors="coerce") for c in market_num_cols}
                out = out.copy()
                out.loc[:, market_num_cols] = pd.DataFrame(numeric_updates, index=out.index)
                ts_features = {
                    f"{c}_ts_z": self._timeseries_zscore_by_date(out[c], out["date"], window=252)
                    for c in market_num_cols
                }
                out = self._concat_new_columns(out, ts_features)

        sector_cols = [c for c in ["sector_gst_yoy", "sector_activity_zscore"] if c in m.columns]
        if sector_cols:
            sector_col = next((c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in out.columns), None)
            sec_rows = m[m["ticker"].astype(str).ne("MARKET")].copy()
            if sector_col and "sector" in sec_rows.columns and not sec_rows.empty:
                sec_rows["sector"] = sec_rows["sector"].astype(str)
                left = out.copy()
                left["_merge_sector"] = left[sector_col].astype(str)
                sec_merge = sec_rows.rename(columns={"availability_date": "macro_sector_availability_date"})[
                    ["macro_sector_availability_date", "sector"] + sector_cols
                ].sort_values("macro_sector_availability_date", kind="mergesort")
                merged_parts: list[pd.DataFrame] = []
                for sec, grp in left.groupby("_merge_sector", sort=False):
                    rhs = sec_merge[sec_merge["sector"] == str(sec)]
                    lg = grp.sort_values("date", kind="mergesort")
                    if rhs.empty:
                        for c in sector_cols:
                            lg[c] = np.nan
                        merged_parts.append(lg)
                        continue
                    mg = pd.merge_asof(
                        lg,
                        rhs.drop(columns=["sector"], errors="ignore"),
                        left_on="date",
                        right_on="macro_sector_availability_date",
                        direction="backward",
                        allow_exact_matches=True,
                    )
                    mg = mg.drop(columns=["macro_sector_availability_date"], errors="ignore")
                    merged_parts.append(mg)
                out = pd.concat(merged_parts, ignore_index=True) if merged_parts else left
                out = out.drop(columns=["_merge_sector"], errors="ignore")

            out = self._append_cross_sectional_transforms(
                out,
                sector_cols,
                groups=out["date"],
                clip_abs=6.0,
                coerce_source=True,
            )

        return out

    def _prepare_screener_annual_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        out = raw.copy()
        if "ticker" in out.columns:
            out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out["availability_date"] = self._as_date(out, ["availability_date", "date", "Date", "timestamp"])
        out = out.dropna(subset=["ticker", "availability_date"]).sort_values(
            ["ticker", "availability_date"], kind="mergesort"
        )

        alias_map = {
            "screener_raw_sales": ["sales", "revenue"],
            "screener_raw_operating_profit": ["operating_profit", "operating profit", "ebit", "ebitda"],
            "screener_raw_net_profit": ["net_profit", "net profit", "pat"],
            "screener_raw_roce": ["roce_pct", "roce %", "roce"],
            "screener_raw_debtor_days": ["debtor_days", "debtor days"],
            "screener_raw_cash_conversion_cycle": ["cash_conversion_cycle", "cash conversion cycle"],
            "screener_raw_cash_from_operating_activity": [
                "cash_from_operating_activity",
                "cash from operating activity",
                "cash_from_operating_activities",
                "cash from operating activities",
            ],
        }
        keep = ["ticker", "availability_date"]
        for target, aliases in alias_map.items():
            src = self._resolve_column(out.columns, aliases)
            if src is None:
                out[target] = np.nan
                keep.append(target)
                continue
            out[target] = pd.to_numeric(out[src], errors="coerce")
            keep.append(target)

        out = out[keep].copy()
        out["pat_prev_year"] = out.groupby("ticker", sort=False)["screener_raw_net_profit"].shift(1)
        out["sales_prev_year"] = out.groupby("ticker", sort=False)["screener_raw_sales"].shift(1)
        out["screener_pat_growth_1y"] = (
            (out["screener_raw_net_profit"] - out["pat_prev_year"])
            / out["pat_prev_year"].abs().replace(0.0, np.nan)
        ) * 100.0
        out["screener_revenue_growth_1y"] = (
            (out["screener_raw_sales"] - out["sales_prev_year"])
            / out["sales_prev_year"].abs().replace(0.0, np.nan)
        ) * 100.0
        out = out.drop(columns=["pat_prev_year", "sales_prev_year"], errors="ignore")
        out = out.sort_values(["ticker", "availability_date"], kind="mergesort")
        out = out.drop_duplicates(subset=["ticker", "availability_date"], keep="last")
        return out.reset_index(drop=True)

    def _prepare_screener_shareholding_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        out = raw.copy()
        if "ticker" in out.columns:
            out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out["availability_date"] = self._as_date(out, ["availability_date", "date", "Date", "timestamp"])
        out = out.dropna(subset=["ticker", "availability_date"]).sort_values(
            ["ticker", "availability_date"], kind="mergesort"
        )

        alias_map = {
            "screener_raw_promoter_pct": ["promoter_pct", "promoters_pct", "promoter"],
            "screener_raw_fii_pct": ["fii_pct", "fiis_pct", "fii"],
            "screener_raw_dii_pct": ["dii_pct", "diis_pct", "dii"],
        }
        keep = ["ticker", "availability_date"]
        for target, aliases in alias_map.items():
            src = self._resolve_column(out.columns, aliases)
            if src is None:
                out[target] = np.nan
                keep.append(target)
                continue
            out[target] = pd.to_numeric(out[src], errors="coerce")
            keep.append(target)

        out = out[keep].copy()
        out["screener_promoter_change_1q"] = out.groupby("ticker", sort=False)["screener_raw_promoter_pct"].diff(1)
        out["screener_promoter_change_4q"] = out.groupby("ticker", sort=False)["screener_raw_promoter_pct"].diff(4)
        out["screener_fii_change_1q"] = out.groupby("ticker", sort=False)["screener_raw_fii_pct"].diff(1)
        out["screener_institutional_pct"] = (
            pd.to_numeric(out["screener_raw_fii_pct"], errors="coerce")
            + pd.to_numeric(out["screener_raw_dii_pct"], errors="coerce")
        )
        out = out.sort_values(["ticker", "availability_date"], kind="mergesort")
        out = out.drop_duplicates(subset=["ticker", "availability_date"], keep="last")
        return out.reset_index(drop=True)

    def _load_screener_annual(self) -> Optional[pd.DataFrame]:
        path = Path(self.screener_fundamentals_path)
        if not path.exists():
            logger.warning("[screener] annual fundamentals not found at %s", path)
            return None
        try:
            raw = pd.read_csv(path, parse_dates=["availability_date"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[screener] failed to read annual fundamentals at %s: %s", path, exc)
            return None
        if raw.empty:
            return None
        return self._prepare_screener_annual_frame(raw)

    def _load_screener_shareholding(self) -> Optional[pd.DataFrame]:
        path = Path(self.screener_shareholding_path)
        if not path.exists():
            logger.warning("[screener] shareholding not found at %s", path)
            return None
        try:
            raw = pd.read_csv(path, parse_dates=["availability_date"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[screener] failed to read shareholding at %s: %s", path, exc)
            return None
        if raw.empty:
            return None
        return self._prepare_screener_shareholding_frame(raw)

    @staticmethod
    def _drop_screener_collision_columns(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        drops: list[str] = []
        for col in out.columns:
            if not str(col).endswith("_screener"):
                continue
            base = str(col)[: -len("_screener")]
            if base in out.columns:
                drops.append(col)
        if drops:
            out = out.drop(columns=drops, errors="ignore")
        return out

    @staticmethod
    def _series_or_nan(frame: pd.DataFrame, col: str) -> pd.Series:
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce")
        return pd.Series(np.nan, index=frame.index, dtype=float)

    def _merge_screener_annual(
        self,
        df: pd.DataFrame,
        screener_annual: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        source = screener_annual if isinstance(screener_annual, pd.DataFrame) else self._screener_annual
        if isinstance(source, pd.DataFrame) and not source.empty and "screener_raw_sales" not in source.columns:
            source = self._prepare_screener_annual_frame(source)
        if df.empty or not isinstance(source, pd.DataFrame) or source.empty:
            return df
        left = df.copy()
        left["ticker"] = left["ticker"].map(self._normalize_ticker)
        left["date"] = self._as_date(left, ["date"])

        right = source.copy()
        right["ticker"] = right["ticker"].map(self._normalize_ticker)
        right["availability_date"] = self._as_date(right, ["availability_date", "date", "Date", "timestamp"])
        right = right.rename(columns={"availability_date": "screener_availability_date"})
        right = right.dropna(subset=["ticker", "screener_availability_date"]).sort_values(
            ["ticker", "screener_availability_date"], kind="mergesort"
        )

        frames: list[pd.DataFrame] = []
        for ticker, group in left.groupby("ticker", sort=False):
            rt = right[right["ticker"] == ticker]
            if rt.empty:
                frames.append(group)
                continue
            merged = pd.merge_asof(
                group.sort_values("date", kind="mergesort"),
                rt.drop(columns=["ticker"], errors="ignore").sort_values("screener_availability_date", kind="mergesort"),
                left_on="date",
                right_on="screener_availability_date",
                direction="backward",
                suffixes=("", "_screener"),
            )
            frames.append(merged)
        out = pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"], kind="mergesort")
        out = self._drop_screener_collision_columns(out)

        op = self._series_or_nan(out, "screener_raw_operating_profit")
        sales = self._series_or_nan(out, "screener_raw_sales")
        net_profit = self._series_or_nan(out, "screener_raw_net_profit")
        cfo = self._series_or_nan(out, "screener_raw_cash_from_operating_activity")
        out["screener_opm_pct"] = (op / sales.replace(0.0, np.nan)) * 100.0
        out["screener_pat_growth_1y"] = self._series_or_nan(out, "screener_pat_growth_1y")
        out["screener_revenue_growth_1y"] = self._series_or_nan(out, "screener_revenue_growth_1y")
        out["screener_roce"] = self._series_or_nan(out, "screener_raw_roce")
        out["screener_debtor_days"] = self._series_or_nan(out, "screener_raw_debtor_days")
        out["screener_cash_conversion_cycle"] = self._series_or_nan(out, "screener_raw_cash_conversion_cycle")
        out["screener_cfo_to_pat"] = (cfo / net_profit.replace(0.0, np.nan)).clip(-5.0, 5.0)
        out["screener_availability_date"] = pd.to_datetime(
            out.get("screener_availability_date", pd.NaT), errors="coerce"
        )

        annual_cols = [
            "screener_opm_pct",
            "screener_pat_growth_1y",
            "screener_revenue_growth_1y",
            "screener_roce",
            "screener_debtor_days",
            "screener_cash_conversion_cycle",
            "screener_cfo_to_pat",
        ]
        out = self._append_cross_sectional_transforms(
            out,
            annual_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _merge_screener_shareholding(
        self,
        df: pd.DataFrame,
        screener_shareholding: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        source = (
            screener_shareholding if isinstance(screener_shareholding, pd.DataFrame) else self._screener_shareholding
        )
        if isinstance(source, pd.DataFrame) and not source.empty and "screener_raw_promoter_pct" not in source.columns:
            source = self._prepare_screener_shareholding_frame(source)
        if df.empty or not isinstance(source, pd.DataFrame) or source.empty:
            return df
        left = df.copy()
        left["ticker"] = left["ticker"].map(self._normalize_ticker)
        left["date"] = self._as_date(left, ["date"])

        right = source.copy()
        right["ticker"] = right["ticker"].map(self._normalize_ticker)
        right["availability_date"] = self._as_date(right, ["availability_date", "date", "Date", "timestamp"])
        right = right.rename(columns={"availability_date": "screener_shareholding_availability_date"})
        right = right.dropna(subset=["ticker", "screener_shareholding_availability_date"]).sort_values(
            ["ticker", "screener_shareholding_availability_date"], kind="mergesort"
        )

        frames: list[pd.DataFrame] = []
        for ticker, group in left.groupby("ticker", sort=False):
            rt = right[right["ticker"] == ticker]
            if rt.empty:
                frames.append(group)
                continue
            merged = pd.merge_asof(
                group.sort_values("date", kind="mergesort"),
                rt.drop(columns=["ticker"], errors="ignore").sort_values(
                    "screener_shareholding_availability_date", kind="mergesort"
                ),
                left_on="date",
                right_on="screener_shareholding_availability_date",
                direction="backward",
                suffixes=("", "_screener"),
            )
            frames.append(merged)
        out = pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"], kind="mergesort")
        out = self._drop_screener_collision_columns(out)

        out["screener_promoter_pct"] = self._series_or_nan(out, "screener_raw_promoter_pct")
        out["screener_promoter_change_1q"] = self._series_or_nan(out, "screener_promoter_change_1q")
        out["screener_promoter_change_4q"] = self._series_or_nan(out, "screener_promoter_change_4q")
        out["screener_fii_pct"] = self._series_or_nan(out, "screener_raw_fii_pct")
        out["screener_fii_change_1q"] = self._series_or_nan(out, "screener_fii_change_1q")
        out["screener_dii_pct"] = self._series_or_nan(out, "screener_raw_dii_pct")
        out["screener_institutional_pct"] = self._series_or_nan(out, "screener_institutional_pct")
        out["screener_shareholding_availability_date"] = pd.to_datetime(
            out.get("screener_shareholding_availability_date", pd.NaT), errors="coerce"
        )

        share_cols = [
            "screener_promoter_pct",
            "screener_promoter_change_1q",
            "screener_promoter_change_4q",
            "screener_fii_pct",
            "screener_fii_change_1q",
            "screener_dii_pct",
            "screener_institutional_pct",
        ]
        out = self._append_cross_sectional_transforms(
            out,
            share_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _apply_sector_lookup(self, panel: pd.DataFrame, sector_lookup: Optional[dict[str, str]]) -> pd.DataFrame:
        if panel.empty or "ticker" not in panel.columns or not sector_lookup:
            return panel
        out = panel.copy()
        tk_norm = out["ticker"].map(self._normalize_ticker)
        mapped = tk_norm.map(sector_lookup)
        sector_col = next((c for c in ["Industry", "industry", "Sector", "sector"] if c in out.columns), None)
        if sector_col is None:
            out["sector"] = mapped.astype("string")
        else:
            cur = out[sector_col].astype("string")
            out[sector_col] = cur.where(cur.notna() & cur.str.strip().ne(""), mapped).astype("string")
        return out

    def _add_fundamental_factor_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        out = panel.copy()
        eps = 1e-12
        def to_num(c: str) -> pd.Series:
            if c in out.columns:
                return pd.to_numeric(out[c], errors="coerce")
            return pd.Series(np.nan, index=out.index, dtype=float)

        net_income = to_num("net_income")
        equity = to_num("equity")
        revenue = to_num("revenue")
        op_inc = to_num("operating_income")
        ebitda = to_num("ebitda")
        op_cf = to_num("operating_cash_flow")
        total_assets = to_num("total_assets")
        debt = to_num("total_debt")
        interest = to_num("interest_expense")

        out["roe"] = net_income / (equity + eps)
        out["operating_margin"] = op_inc / (revenue + eps)
        out["ebitda_margin"] = ebitda / (revenue + eps)
        out["accruals_ratio"] = (net_income - op_cf) / (total_assets + eps)
        out["cash_conversion"] = op_cf / (net_income + eps)
        out["asset_turnover"] = revenue / (total_assets + eps)
        out["debt_to_equity"] = debt / (equity + eps)
        out["interest_coverage"] = op_inc / (interest.abs() + eps)

        if "ticker" in out.columns:
            g = out.groupby("ticker", sort=False)
            out["roe_qoq_change"] = g["roe"].diff(1)
            out["operating_margin_change"] = g["operating_margin"].diff(1)
        else:
            out["roe_qoq_change"] = np.nan
            out["operating_margin_change"] = np.nan
        return out

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
            "mom_5d",
            "mom_10d",
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

        fundamental_cols = [
            "roe",
            "roe_qoq_change",
            "operating_margin",
            "operating_margin_change",
            "ebitda_margin",
            "accruals_ratio",
            "cash_conversion",
            "asset_turnover",
            "debt_to_equity",
            "interest_coverage",
        ]
        sector_z_updates: dict[str, pd.Series] = {}
        for col in fundamental_cols:
            if col not in out.columns:
                continue
            sector_z_updates[f"{col}_sector_z"] = self._group_zscore(
                out[col],
                pd.MultiIndex.from_arrays([out["date"], sector]),
                clip_abs=6.0,
            )
        out = self._concat_new_columns(out, sector_z_updates)

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
            "mom_5d",
            "mom_10d",
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
            "roe",
            "roe_qoq_change",
            "operating_margin",
            "operating_margin_change",
            "ebitda_margin",
            "accruals_ratio",
            "cash_conversion",
            "asset_turnover",
            "debt_to_equity",
            "interest_coverage",
            "debtor_days",
            "inventory_days",
            "days_payable",
            "cash_conversion_cycle",
            "working_capital_days",
            "promoter_pct",
            "fii_pct",
            "dii_pct",
            "promoter_change_1q",
            "fii_change_1q",
            "institutional_total_pct",
            "et500_rank_change",
        ]
        cs_numeric_cols = [c for c in cs_seed_cols if c in out.columns and pd.api.types.is_numeric_dtype(out[c])]
        out = self._append_cross_sectional_transforms(
            out,
            cs_numeric_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=False,
        )

        return out

    def _add_et500_features(
        self,
        panel: pd.DataFrame,
        et500_membership: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        if panel.empty or not bool(self.use_et500_features):
            return panel
        if not isinstance(et500_membership, pd.DataFrame) or et500_membership.empty:
            return panel
        need = {"year", "nse_ticker", "rank", "prev_rank"}
        if not need.issubset(set(et500_membership.columns)):
            return panel

        ref = et500_membership.copy()
        ref["ticker"] = ref["nse_ticker"].map(self._normalize_ticker)
        ref["et500_year"] = pd.to_numeric(ref["year"], errors="coerce")
        ref["et500_rank"] = pd.to_numeric(ref["rank"], errors="coerce")
        ref["et500_prev_rank"] = pd.to_numeric(ref["prev_rank"], errors="coerce")
        ref["et500_rank_change"] = ref["et500_prev_rank"] - ref["et500_rank"]
        ref["et500_availability_date"] = pd.to_datetime(
            ref["et500_year"].astype("Int64").astype("string") + "-12-31",
            errors="coerce",
        )
        ref = ref.dropna(subset=["ticker", "et500_availability_date"]).copy()
        ref = ref.sort_values(["ticker", "et500_availability_date", "et500_rank"], kind="mergesort")
        ref = ref.drop_duplicates(subset=["ticker", "et500_availability_date"], keep="first")
        keep = [
            "ticker",
            "et500_availability_date",
            "et500_rank_change",
        ]
        return self._merge_asof_by_ticker(panel, ref[keep], left_on="date", right_on="et500_availability_date")

    def build_features(
        self,
        prices: pd.DataFrame,
        fundamentals: Optional[pd.DataFrame] = None,
        screener_annual: Optional[pd.DataFrame] = None,
        screener_quarterly: Optional[pd.DataFrame] = None,
        screener_shareholding: Optional[pd.DataFrame] = None,
        macro: Optional[pd.DataFrame] = None,
        valuation_posterior: Optional[pd.DataFrame] = None,
        sentiment_company: Optional[pd.DataFrame] = None,
        sentiment_market: Optional[pd.DataFrame] = None,
        sector_lookup: Optional[dict[str, str]] = None,
        et500_membership: Optional[pd.DataFrame] = None,
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
        # Skip-1 momentum convention avoids 1-day reversal contamination.
        p["mom_5d"] = g["close"].shift(1) / g["close"].shift(6) - 1.0
        p["mom_10d"] = g["close"].shift(1) / g["close"].shift(11) - 1.0
        p["mom_20d"] = g["close"].shift(1) / g["close"].shift(21) - 1.0
        p["mom_60d"] = g["close"].shift(1) / g["close"].shift(61) - 1.0
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
                "mom_5d",
                "mom_10d",
                "mom_20d",
                "mom_60d",
                "price_to_sma20",
                "vol_z20",
                "forward_return_5d",
            ]
        ].copy()

        if isinstance(fundamentals, pd.DataFrame) and not fundamentals.empty:
            f = fundamentals.copy()
            f["fundamental_date"] = self._as_date(f, ["date", "Date", "timestamp", "fiscal_quarter_end_date"])
            ann = self._as_date(
                f,
                [
                    "announcement_date",
                    "announcementDate",
                    "results_announcement_date",
                    "results_announced_at",
                    "report_announcement_date",
                ],
            )
            has_announcement = bool(self.use_announcement_dates and ann.notna().any())
            if bool(self.enable_pit_fundamentals):
                if has_announcement:
                    availability = ann + pd.Timedelta(days=int(self.pit_announcement_plus_days))
                else:
                    availability = f["fundamental_date"] + pd.Timedelta(days=int(self.pit_fundamental_lag_days))
            else:
                availability = f["fundamental_date"]
            f["availability_date"] = pd.to_datetime(availability, errors="coerce")
            needed = [
                "fundamental_date",
                "availability_date",
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
                "total_assets",
                "total_debt",
                "operating_cash_flow",
                "free_cash_flow",
                "interest_expense",
                "shares_outstanding",
            ]
            keep = [c for c in needed if c in f.columns]
            f = f[keep].copy()
            non_numeric_cols = {
                "fundamental_date",
                "availability_date",
                "ticker",
                "Industry",
                "industry",
                "Sector",
                "sector",
            }
            for c in keep:
                if c not in non_numeric_cols:
                    f[c] = pd.to_numeric(f[c], errors="coerce")
            panel = self._merge_asof_by_ticker(panel, f, left_on="date", right_on="availability_date")
            panel["ni_margin"] = panel["net_income"] / (panel["revenue"] + 1e-12)
            panel["debt_to_equity"] = panel["total_debt"] / (panel["equity"] + 1e-12)
            panel["fcf_to_ocf"] = panel["free_cash_flow"] / (panel["operating_cash_flow"] + 1e-12)
            panel = self._add_fundamental_factor_features(panel)

        _ = screener_quarterly  # reserved for future screener quarterly feature set
        if bool(self.use_screener_features):
            panel = self._merge_screener_annual(panel, screener_annual=screener_annual)
            panel = self._merge_screener_shareholding(panel, screener_shareholding=screener_shareholding)

        if bool(self.use_alternative_features):
            try:
                from src.signals.signal_loader import AlternativeDataLoader
                from src.signals.feature_builder import AlternativeFeatureBuilder

                alt_loader = AlternativeDataLoader(
                    {
                        **self.config,
                        "alternative_data_path": self.alternative_data_path,
                    }
                )
                alt_features = alt_loader.get_features_as_of_frame(panel)
                if isinstance(alt_features, pd.DataFrame) and not alt_features.empty:
                    # Debug coverage for alternative features.
                    bulk_cols = [c for c in alt_features.columns if str(c).startswith("bulk_")]
                    pledge_cols = [c for c in alt_features.columns if str(c).startswith("pledge_")]
                    rating_cols = [c for c in alt_features.columns if str(c).startswith("rating_")]
                    any_mask = alt_features.notna().any(axis=1)
                    bulk_rows = int(alt_features[bulk_cols].notna().any(axis=1).sum()) if bulk_cols else 0
                    pledge_rows = int(alt_features[pledge_cols].notna().any(axis=1).sum()) if pledge_cols else 0
                    rating_rows = int(alt_features[rating_cols].notna().any(axis=1).sum()) if rating_cols else 0
                    matched_tickers = int(panel.loc[any_mask, "ticker"].nunique()) if bool(any_mask.any()) else 0
                    logger.info(
                        "alt_features_joined bulk_deal_rows=%d pledge_rows=%d ratings_rows=%d matched_tickers=%d",
                        bulk_rows,
                        pledge_rows,
                        rating_rows,
                        matched_tickers,
                    )

                    col_to_family: dict[str, str] = {}
                    for fam, fam_cols in AlternativeFeatureBuilder.FEATURE_GROUPS.items():
                        for c in fam_cols:
                            col_to_family[str(c)] = str(fam)
                    raw_updates: dict[str, pd.Series] = {}
                    cs_updates: dict[str, pd.Series] = {}
                    family_counts: dict[str, int] = {}
                    for col in alt_features.columns:
                        fam = col_to_family.get(str(col))
                        if fam and not self._is_alternative_family_enabled(fam):
                            continue
                        series = pd.to_numeric(alt_features[col], errors="coerce")
                        if len(series) != len(panel):
                            continue
                        series = pd.Series(series.to_numpy(), index=panel.index, dtype=float)
                        # Skip empty columns so missing/disabled families do not
                        # silently become zeroed cross-sectional signals.
                        if not bool(series.notna().any()):
                            continue
                        raw_updates[str(col)] = series
                        if fam:
                            family_counts[str(fam)] = int(family_counts.get(str(fam), 0) + 1)
                        cs_updates[f"{col}_cs_z"] = self._group_zscore(series, panel["date"], clip_abs=6.0)
                        cs_updates[f"{col}_cs_rank"] = self._group_rank_centered(series, panel["date"])
                    if raw_updates:
                        panel = panel.copy()
                        panel.loc[:, list(raw_updates.keys())] = pd.DataFrame(raw_updates, index=panel.index)
                        panel = self._concat_new_columns(panel, cs_updates)
                        logger.info(
                            "[alternative] merged raw_cols=%d cs_cols=%d family_counts=%s",
                            int(len(raw_updates)),
                            int(len(cs_updates)),
                            dict(sorted(family_counts.items())),
                        )
                    else:
                        logger.info("[alternative] enabled but no usable alternative columns were merged")
            except Exception as exc:  # noqa: BLE001
                logger.warning("[alternative] feature merge skipped: %s", exc)

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

        if bool(self.use_sentiment_features):
            panel = self._merge_sentiment_training_features(panel)

        panel = self._apply_sector_lookup(panel, sector_lookup)
        if bool(self.use_macro_features):
            panel = self._merge_macro_feature_pack(panel)
        panel = self._add_et500_features(panel, et500_membership)
        panel["trade_date"] = panel["date"]
        panel = self._add_structural_alpha_features(panel)

        if {"availability_date", "trade_date"}.issubset(set(panel.columns)):
            av = pd.to_datetime(panel["availability_date"], errors="coerce")
            td = pd.to_datetime(panel["trade_date"], errors="coerce")
            mask = av.notna() & td.notna()
            if bool(mask.any()) and not bool((av[mask] <= td[mask]).all()):
                raise ValueError("pit_leak_detected:availability_date_after_trade_date")

        for av_col in ["screener_availability_date", "screener_shareholding_availability_date"]:
            if {av_col, "trade_date"}.issubset(set(panel.columns)):
                av = pd.to_datetime(panel[av_col], errors="coerce")
                td = pd.to_datetime(panel["trade_date"], errors="coerce")
                mask = av.notna() & td.notna()
                if bool(mask.any()) and not bool((av[mask] <= td[mask]).all()):
                    raise ValueError(f"pit_leak_detected:{av_col}_after_trade_date")

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
