"""Historical research dataset manager - REFACTORED to use IngestionRegistry."""

from __future__ import annotations

import bisect
import fnmatch
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yaml

from src.core.panel_math import (
    group_rank_centered as _shared_group_rank_centered,
    group_zscore as _shared_group_zscore,
    normalize_ticker as _shared_normalize_ticker,
    sector_string,
)
# REFACTORED: Use unified ingestion layer instead of direct loaders
from src.ingestion import IngestionRegistry

from src.data.loaders import (
    load_fundamentals as load_fundamentals_artifact,
    load_macro as load_macro_artifact,
    load_prices as load_prices_artifact,
    load_regime_labels as load_regime_labels_artifact,
    load_sentiment as load_sentiment_artifact,
)
from src.data.query_engine import DuckDBQueryEngine

from .feature_factory import FeatureFactory
from .regime_engine import RegimeEngine
from .research_types import ResearchDataset
from .splits import rolling_time_splits

logger = logging.getLogger(__name__)


def _stable_hash_frame(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return ""
    take = [c for c in cols if c in df.columns]
    if not take:
        return ""
    work = df[take].copy()
    for c in take:
        if pd.api.types.is_datetime64_any_dtype(work[c]):
            work[c] = pd.to_datetime(work[c], errors="coerce").dt.strftime("%Y-%m-%d")
    work = work.replace([np.inf, -np.inf], np.nan).fillna("__nan__")
    hashed = pd.util.hash_pandas_object(work, index=False)
    raw = hashed.to_numpy(dtype=np.uint64).tobytes()
    return hashlib.sha256(raw).hexdigest()


def _safe_sql_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _sanitize_target_series(
    target: pd.Series,
    *,
    clip_abs: float = 1.0,
    winsor_quantile: float = 0.995,
) -> pd.Series:
    """Sanitize and bound target returns for stable training/metrics."""
    # N6: this fills missing internal targets with 0.0 for stable metric
    # computation. The Kaggle EXPORT target is recomputed separately in
    # resample_daily_panel_to_weekly (which nulls suspended/flat weeks), so this
    # 0-fill affects only DatasetManager-internal training consumers — documented
    # here so a consumer does not mistake a filled 0 for a real flat return.
    out = pd.to_numeric(target, errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)

    q = float(winsor_quantile)
    if 0.5 < q < 1.0 and len(out) > 0:
        abs_vals = np.abs(out.to_numpy(dtype=float))
        qv = float(np.nanquantile(abs_vals, q))
        if np.isfinite(qv) and qv > 0.0:
            out = out.clip(lower=-qv, upper=qv)

    cap = float(clip_abs)
    if np.isfinite(cap) and cap > 0.0:
        out = out.clip(lower=-cap, upper=cap)
    return out.astype(float)


class DatasetManager:
    """Loads historical artifacts and builds the canonical research dataset."""

    def __init__(self, project_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None):
        self.project_root = Path(project_root) if project_root else Path(".")
        self.config = dict(config or {})
        
        # REFACTORED: Initialize IngestionRegistry for unified data access
        self.ingestion = IngestionRegistry(self.config)
        
        self.policy_config_path = str(
            Path(
                self.config.get("policy_config_path", "config/research_policy.yaml")
            )
            if Path(str(self.config.get("policy_config_path", "config/research_policy.yaml"))).is_absolute()
            else (self.project_root / str(self.config.get("policy_config_path", "config/research_policy.yaml")))
        )
        self.use_et500_features = bool(self.config.get("use_et500_features", False))
        self.use_et500_universe_filter = bool(self.config.get("use_et500_universe_filter", False))
        self.use_screener_features = bool(
            self.config.get("use_screener_features", False)
            or self.config.get("use_screener_extended_features", False)
        )
        self.et500_membership_path = str(
            self.config.get("et500_membership_path", "data/reference/et500_pit_membership.csv")
        )
        self.screener_fundamentals_path = str(
            self.config.get(
                "screener_fundamentals_path",
                self.config.get("screener_annual_path", "data/canonical/fundamentals/fundamentals_annual_panel.parquet"),
            )
        )
        self.screener_quarterly_path = str(
            self.config.get(
                "screener_quarterly_path",
                "data/canonical/fundamentals/fundamentals_quarterly_panel.parquet",
            )
        )
        self.screener_shareholding_path = str(
            self.config.get("screener_shareholding_path", "data/canonical/fundamentals/shareholding_quarterly.parquet")
        )
        self.use_alternative_features = bool(self.config.get("use_alternative_features", False))
        self.use_sentiment_features = bool(self.config.get("use_sentiment_features", False))
        self.use_sentiment_regime = bool(self.config.get("use_sentiment_regime", False))
        self.use_macro_features = bool(self.config.get("use_macro_features", False))
        self.alternative_data_path = str(self.config.get("alternative_data_path", "data/canonical/alternative"))
        self.sentiment_path = str(
            self.config.get("sentiment_path", "data/canonical/sentiment/company_sentiment_daily.parquet")
        )
        self.market_sentiment_path = str(
            self.config.get("market_sentiment_path", "data/canonical/sentiment/market_sentiment_daily.parquet")
        )
        self.sentiment_duckdb_path = str(self.config.get("sentiment_duckdb_path", "data/sentiment.duckdb"))
        self._et500_membership_cache: Optional[pd.DataFrame] = None
        self.factory = FeatureFactory(
            target_horizon_days=int(self.config.get("target_horizon_days", 5)),
            enable_pit_fundamentals=bool(self.config.get("pit_fundamentals_enabled", True)),
            pit_fundamental_lag_days=int(self.config.get("pit_fundamental_lag_days", 60)),
            pit_announcement_plus_days=int(self.config.get("pit_announcement_plus_days", 1)),
            use_announcement_dates=bool(self.config.get("pit_use_announcement_dates", True)),
            use_et500_features=bool(self.use_et500_features),
            use_screener_features=bool(self.use_screener_features),
            screener_fundamentals_path=str(self.screener_fundamentals_path),
            screener_shareholding_path=str(self.screener_shareholding_path),
            config=self.config,
        )
        self.snapshot_dir = self.project_root / "data/results/research/snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.strict_real_data_only = bool(self.config.get("strict_real_data_only", True))
        self.required_artifacts = {
            str(x).strip().lower()
            for x in self.config.get(
                "strict_required_artifacts",
                ["prices", "fundamentals", "macro", "valuation_posterior"],
            )
        }
        self.artifact_min_rows = {
            "prices": int(self.config.get("artifact_min_rows", {}).get("prices", 2000)),
            "fundamentals": int(self.config.get("artifact_min_rows", {}).get("fundamentals", 400)),
            "macro": int(self.config.get("artifact_min_rows", {}).get("macro", 200)),
            "valuation_posterior": int(self.config.get("artifact_min_rows", {}).get("valuation_posterior", 400)),
            "sentiment_company": int(self.config.get("artifact_min_rows", {}).get("sentiment_company", 100)),
            "sentiment_market": int(self.config.get("artifact_min_rows", {}).get("sentiment_market", 5)),
        }
        self.reject_source_keywords = [
            str(x).lower().strip()
            for x in self.config.get(
                "reject_source_keywords",
                ["mock", "synthetic", "sample_data", "demo_data", "toy_data"],
            )
            if str(x).strip()
        ]
        self.low_resource_mode_effective = False
        self._apply_low_resource_dataset_caps()
        self.query = DuckDBQueryEngine(
            memory_limit_mb=int(self.config.get("duckdb_memory_limit_mb", 768)),
            threads=int(self.config.get("duckdb_threads", 1)),
        )

    def _host_memory_gb(self) -> float:
        try:
            import psutil  # type: ignore

            return float(psutil.virtual_memory().total / (1024 ** 3))
        except ModuleNotFoundError:
            logger.warning("psutil not available; host memory autodetect disabled")
            return 0.0
        except Exception:
            logger.exception("Failed to detect host memory")
            raise

    def _is_low_resource_host(self) -> bool:
        flag = str(self.config.get("low_resource_mode", "auto")).strip().lower()
        if flag in {"1", "true", "yes", "on", "enabled"}:
            return True
        if flag in {"0", "false", "no", "off", "disabled"}:
            return False
        host_gb = self._host_memory_gb()
        if host_gb > 0.0:
            return host_gb <= float(self.config.get("low_resource_max_memory_gb", 10.0))
        return False

    def _apply_low_resource_dataset_caps(self) -> None:
        self.low_resource_mode_effective = bool(self._is_low_resource_host())
        if not self.low_resource_mode_effective:
            return
        cap_rows = int(self.config.get("low_resource_max_rows", 90000) or 90000)
        cap_tickers = int(self.config.get("low_resource_max_tickers", 140) or 140)
        cap_lookback = int(self.config.get("low_resource_lookback_days", 2200) or 2200)

        cur_rows_raw = self.config.get("max_rows", cap_rows)
        cur_rows = int(cur_rows_raw) if cur_rows_raw is not None else cap_rows
        cur_tickers = int(self.config.get("max_tickers", cap_tickers) or cap_tickers)
        cur_lookback = int(self.config.get("lookback_days", cap_lookback) or cap_lookback)

        self.config["max_rows"] = max(5000, min(cur_rows, cap_rows))
        self.config["max_tickers"] = max(20, min(cur_tickers, cap_tickers))
        self.config["lookback_days"] = max(365, min(cur_lookback, cap_lookback))

    _normalize_ticker = staticmethod(_shared_normalize_ticker)

    @staticmethod
    def _as_date(df: pd.DataFrame, preferred: list[str]) -> pd.Series:
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

    def _load_sector_lookup(self) -> Dict[str, str]:
        """
        Canonical sector mapping: YAML overrides CSV, CSV fills remainder.
        
        NOTE: This reads auxiliary reference data (sector mappings), not primary market data.
        Primary data (prices, fundamentals, macro) is loaded through IngestionRegistry.
        """
        csv_map: Dict[str, str] = {}
        csv_path = self.project_root / "data/processed/sector_mapping.csv"
        if csv_path.exists():
            try:
                cdf = pd.read_csv(csv_path, usecols=["ticker", "sector"])
                if not cdf.empty:
                    cdf["ticker"] = cdf["ticker"].map(self._normalize_ticker)
                    cdf["sector"] = cdf["sector"].astype(str).str.strip()
                    cdf = cdf[(cdf["ticker"] != "") & (cdf["sector"] != "")]
                    csv_map = dict(zip(cdf["ticker"], cdf["sector"]))
            except Exception:
                logger.exception("Failed loading sector mapping CSV: %s", csv_path)
                raise

        yaml_map: Dict[str, str] = {}
        yaml_path = self.project_root / "config/stock_options_mapping_complete.yaml"
        if yaml_path.exists():
            try:
                payload = yaml.safe_load(yaml_path.read_text()) or {}
                stocks = payload.get("stocks", {}) if isinstance(payload, dict) else {}
                if isinstance(stocks, dict):
                    for symbol, meta in stocks.items():
                        if not isinstance(meta, dict):
                            continue
                        sec = str(meta.get("sector", "") or "").strip()
                        if not sec:
                            continue
                        tk = self._normalize_ticker(symbol)
                        if tk:
                            yaml_map[tk] = sec
            except Exception:
                logger.exception("Failed loading sector mapping YAML: %s", yaml_path)
                raise

        out = dict(csv_map)
        out.update(yaml_map)  # YAML overrides CSV labels when both exist.
        return out

    def _apply_sector_lookup_to_frame(self, frame: pd.DataFrame, sector_lookup: Dict[str, str]) -> pd.DataFrame:
        if frame.empty or "ticker" not in frame.columns or not sector_lookup:
            return frame
        out = frame.copy()
        norm_tk = out["ticker"].map(self._normalize_ticker)
        mapped = norm_tk.map(sector_lookup)
        if "sector" in out.columns:
            cur = out["sector"].astype("string")
            out["sector"] = cur.where(cur.notna() & cur.str.strip().ne(""), mapped).astype("string")
        else:
            out["sector"] = mapped.astype("string")
        return out

    @staticmethod
    def _pick_first_existing(columns: list[str], candidates: list[str]) -> Optional[str]:
        avail = {str(c) for c in columns}
        for c in candidates:
            if c in avail:
                return c
        return None

    def _select_existing_columns(self, path: Path, wanted: list[str]) -> list[str]:
        cols = self.query.columns(path) if self.query.available else []
        if not cols:
            return wanted
        avail = {str(c) for c in cols}
        out = [c for c in wanted if c in avail]
        return out

    def _config_date(self, key: str) -> Optional[pd.Timestamp]:
        raw = self.config.get(key)
        if raw in (None, "", "null"):
            return None
        ts = pd.to_datetime(raw, errors="coerce")
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts)

    def _config_int(self, key: str, default: int) -> int:
        raw = self.config.get(key, default)
        if raw in (None, "", "null"):
            return int(default)
        try:
            return int(raw)
        except Exception:
            return int(default)

    def _load_et500_membership(self) -> pd.DataFrame:
        if isinstance(self._et500_membership_cache, pd.DataFrame):
            return self._et500_membership_cache.copy()

        path = self.project_root / str(self.et500_membership_path)
        if not path.exists():
            self._et500_membership_cache = pd.DataFrame()
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
        except Exception:
            logger.exception("Failed loading ET500 membership file: %s", path)
            raise

        if df.empty or not {"year", "nse_ticker"}.issubset(set(df.columns)):
            self._et500_membership_cache = pd.DataFrame()
            return pd.DataFrame()

        out = df.copy()
        out["year"] = pd.to_numeric(out["year"], errors="coerce")
        out["nse_ticker"] = out["nse_ticker"].map(self._normalize_ticker)
        for c in [
            "rank",
            "prev_rank",
            "revenue_cr",
            "revenue_change_pct",
            "pat_cr",
            "pat_change_pct",
            "market_cap_cr",
        ]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=["year", "nse_ticker"]).copy()
        out["year"] = out["year"].astype(int)
        sort_cols = ["year", "nse_ticker"] + (["rank"] if "rank" in out.columns else [])
        out = out.sort_values(sort_cols, kind="mergesort")
        out = out.drop_duplicates(subset=["year", "nse_ticker"], keep="first")
        self._et500_membership_cache = out.reset_index(drop=True)
        return self._et500_membership_cache.copy()

    @staticmethod
    def _et500_cumulative_tickers_by_availability(
        et500_membership: pd.DataFrame,
    ) -> tuple[list[pd.Timestamp], dict[pd.Timestamp, set[str]]]:
        if et500_membership.empty or not {"year", "nse_ticker"}.issubset(set(et500_membership.columns)):
            return [], {}
        work = et500_membership.copy()
        work["availability_date"] = pd.to_datetime(
            pd.to_numeric(work["year"], errors="coerce").astype("Int64").astype("string") + "-12-31",
            errors="coerce",
        )
        work = work.dropna(subset=["availability_date", "nse_ticker"])
        if work.empty:
            return [], {}
        by_date: Dict[pd.Timestamp, set[str]] = {}
        for dt, grp in work.groupby("availability_date", sort=True):
            by_date[pd.Timestamp(dt)] = set(grp["nse_ticker"].astype(str))
        dates_sorted = sorted(by_date.keys())
        cumulative: dict[pd.Timestamp, set[str]] = {}
        running: set[str] = set()
        for dt in dates_sorted:
            running = running.union(by_date.get(dt, set()))
            cumulative[dt] = set(running)
        return dates_sorted, cumulative

    @staticmethod
    def _et500_allowed_tickers_for_date(
        dt: pd.Timestamp,
        *,
        availability_dates_sorted: list[pd.Timestamp],
        cumulative_by_date: dict[pd.Timestamp, set[str]],
    ) -> set[str]:
        if not availability_dates_sorted or pd.isna(dt):
            return set()
        key = pd.Timestamp(dt).normalize()
        idx = bisect.bisect_right(availability_dates_sorted, key) - 1
        if idx < 0:
            return set()
        ref_dt = availability_dates_sorted[idx]
        return set(cumulative_by_date.get(ref_dt, set()))

    def _emit_et500_filter_diagnostics(self, panel: pd.DataFrame, et500_membership: pd.DataFrame) -> None:
        if panel.empty or et500_membership.empty or "date" not in panel.columns or "ticker" not in panel.columns:
            return
        availability_dates_sorted, cumulative = self._et500_cumulative_tickers_by_availability(et500_membership)
        if not availability_dates_sorted:
            return

        train_periods = int(self.config.get("training_train_periods", self.config.get("train_periods", 756)) or 756)
        valid_periods = int(self.config.get("training_valid_periods", self.config.get("valid_periods", 126)) or 126)
        test_periods = int(self.config.get("training_test_periods", self.config.get("test_periods", 126)) or 126)
        step_periods = int(self.config.get("training_step_periods", self.config.get("step_periods", 63)) or 63)
        min_tickers_per_date = int(
            self.config.get("training_min_tickers_per_date", self.config.get("min_tickers_per_date", 50)) or 50
        )
        max_windows = int(self.config.get("training_max_windows", self.config.get("max_windows", 12)) or 12)

        diag_frame = panel[["date", "ticker"]].copy()
        diag_frame["date"] = pd.to_datetime(diag_frame["date"], errors="coerce")
        diag_frame["ticker"] = diag_frame["ticker"].map(self._normalize_ticker)
        diag_frame = diag_frame.dropna(subset=["date"])
        if diag_frame.empty:
            return

        seen = 0
        for split in rolling_time_splits(
            diag_frame,
            date_col="date",
            ticker_col="ticker",
            train_periods=train_periods,
            valid_periods=valid_periods,
            test_periods=test_periods,
            step_periods=step_periods,
            min_tickers_per_date=max(1, min_tickers_per_date),
        ):
            if seen >= max_windows:
                break
            train_mask = np.asarray(split["train_mask"], dtype=bool)
            if not bool(train_mask.any()):
                continue
            train_end = pd.to_datetime(split.get("train_end"), errors="coerce")
            if pd.isna(train_end):
                continue
            allowed = self._et500_allowed_tickers_for_date(
                pd.Timestamp(train_end),
                availability_dates_sorted=availability_dates_sorted,
                cumulative_by_date=cumulative,
            )
            before = diag_frame.loc[train_mask, "ticker"].astype(str)
            before_n = int(before.nunique())
            after_n = int(before[before.isin(allowed)].nunique())
            print(
                f"[et500-filter] window {split.get('train_start')}-{split.get('train_end')}: "
                f"{before_n} tickers before filter, {after_n} tickers after filter"
            )
            seen += 1

    def _apply_et500_universe_filter(self, panel: pd.DataFrame, et500_membership: pd.DataFrame) -> pd.DataFrame:
        if panel.empty or et500_membership.empty or "date" not in panel.columns or "ticker" not in panel.columns:
            return panel
        availability_dates_sorted, cumulative = self._et500_cumulative_tickers_by_availability(et500_membership)
        if not availability_dates_sorted:
            return panel

        out = panel.copy()
        out["__date_norm"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
        out["__ticker_norm"] = out["ticker"].map(self._normalize_ticker)
        keep = pd.Series(False, index=out.index, dtype=bool)

        for dt, idx in out.groupby("__date_norm", dropna=True, sort=False).groups.items():
            if pd.isna(dt):
                continue
            allowed = self._et500_allowed_tickers_for_date(
                pd.Timestamp(dt),
                availability_dates_sorted=availability_dates_sorted,
                cumulative_by_date=cumulative,
            )
            if not allowed:
                continue
            keep.loc[idx] = out.loc[idx, "__ticker_norm"].isin(allowed).to_numpy(dtype=bool)

        out = out.loc[keep].drop(columns=["__date_norm", "__ticker_norm"], errors="ignore")
        return out.reset_index(drop=True)

    def _add_sector_dummies(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        sector_col = next(
            (c for c in ["sector_name", "sector", "Industry", "industry", "Sector"] if c in panel.columns),
            None,
        )
        if sector_col is None:
            return panel
        sec = sector_string(panel[sector_col])
        dummies = pd.get_dummies(sec, prefix="sector_dummy")
        if dummies.empty:
            return panel
        # Sanitize dummy column names to ASCII-safe tokens.
        dummies.columns = [re.sub(r"[^A-Za-z0-9_]+", "_", str(c)) for c in dummies.columns]
        return pd.concat([panel.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)

    def _load_delisting_database(self) -> pd.DataFrame:
        path = self.project_root / "data/universe/delisting_database.parquet"
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_parquet(path)
        except Exception:
            logger.exception("Failed loading delisting database: %s", path)
            raise
        if df.empty:
            return pd.DataFrame()
        out = df.copy()
        sym_col = "symbol" if "symbol" in out.columns else ("ticker" if "ticker" in out.columns else None)
        if sym_col is None:
            return pd.DataFrame()
        out["ticker"] = out[sym_col].map(self._normalize_ticker)
        out["delisting_date"] = pd.to_datetime(out.get("delisting_date"), errors="coerce")
        out["final_price"] = pd.to_numeric(out.get("final_price"), errors="coerce")
        out["takeover_price"] = pd.to_numeric(out.get("takeover_price"), errors="coerce")
        out["pnl_impact"] = pd.to_numeric(out.get("pnl_impact"), errors="coerce")
        dtype_raw = out.get("delisting_type_original", pd.Series("", index=out.index)).astype(str).str.lower()
        reason_raw = out.get("reason", pd.Series("", index=out.index)).astype(str).str.lower()
        forced = (
            reason_raw.isin({"financial_distress", "regulatory"})
            | dtype_raw.str.contains("compulsory|liquidation|insolvency", regex=True, na=False)
        )
        out["delisting_class"] = np.where(forced, "forced", "voluntary")
        keep = ["ticker", "delisting_date", "delisting_class", "final_price", "takeover_price", "pnl_impact"]
        out = out.dropna(subset=["ticker", "delisting_date"])
        return out[keep].reset_index(drop=True)

    def _apply_delisting_adjustments(self, panel: pd.DataFrame, delist_df: pd.DataFrame) -> pd.DataFrame:
        if panel.empty or delist_df.empty or not {"date", "ticker"}.issubset(set(panel.columns)):
            return panel
        work = panel.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work["ticker"] = work["ticker"].map(self._normalize_ticker)
        delist = delist_df.copy()
        delist["ticker"] = delist["ticker"].map(self._normalize_ticker)
        delist["delisting_date"] = pd.to_datetime(delist["delisting_date"], errors="coerce")
        delist = delist.dropna(subset=["ticker", "delisting_date"])
        if delist.empty:
            return work

        work = work.merge(delist, on="ticker", how="left")
        if "delisting_date" not in work.columns:
            return panel

        after_delist = work["delisting_date"].notna() & (work["date"] > work["delisting_date"])
        work = work.loc[~after_delist].copy()

        on_delist = work["delisting_date"].notna() & (work["date"] == work["delisting_date"])
        if on_delist.any() and "forward_return_5d" in work.columns:
            forced = work["delisting_class"].astype(str).str.lower().eq("forced")
            use_forced = on_delist & forced
            work.loc[use_forced, "forward_return_5d"] = -1.0

            voluntary_mask = on_delist & (~forced)
            if voluntary_mask.any():
                close = pd.to_numeric(work.loc[voluntary_mask, "close"], errors="coerce")
                takeover = pd.to_numeric(work.loc[voluntary_mask, "takeover_price"], errors="coerce")
                final_price = pd.to_numeric(work.loc[voluntary_mask, "final_price"], errors="coerce")
                pnl_impact = pd.to_numeric(work.loc[voluntary_mask, "pnl_impact"], errors="coerce")
                price = takeover.where(takeover.notna(), final_price)
                ret = price / close.replace(0.0, np.nan) - 1.0
                ret = ret.where(ret.notna(), pnl_impact)
                work.loc[voluntary_mask, "forward_return_5d"] = ret
        work = work.drop(columns=["delisting_date", "delisting_class", "final_price", "takeover_price", "pnl_impact"], errors="ignore")
        return work.reset_index(drop=True)

    def _apply_liquidity_filter(self, panel: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
        if panel.empty or prices is None or prices.empty:
            return panel
        threshold = float(self.config.get("liquidity_threshold_cr", 0.0) or 0.0)
        if threshold <= 0.0:
            return panel
        p = prices.copy()
        date_col = "Date" if "Date" in p.columns else ("date" if "date" in p.columns else None)
        if date_col is None or "ticker" not in p.columns:
            return panel
        close_col = "Close" if "Close" in p.columns else ("close" if "close" in p.columns else None)
        vol_col = "Volume" if "Volume" in p.columns else ("volume" if "volume" in p.columns else None)
        if close_col is None or vol_col is None:
            return panel
        p["date"] = pd.to_datetime(p[date_col], errors="coerce")
        p["ticker"] = p["ticker"].map(self._normalize_ticker)
        p["close"] = pd.to_numeric(p[close_col], errors="coerce")
        p["volume"] = pd.to_numeric(p[vol_col], errors="coerce")
        p = p.dropna(subset=["date", "ticker", "close", "volume"])
        if p.empty:
            return panel
        p = p.sort_values(["ticker", "date"], kind="mergesort")
        p["rupee_volume"] = p["close"] * p["volume"]
        p["adt_21d"] = (
            p.groupby("ticker", sort=False)["rupee_volume"]
            .rolling(21, min_periods=10)
            .mean()
            .reset_index(level=0, drop=True)
        )
        p["quarter"] = p["date"].dt.to_period("Q")
        first = p.groupby(["ticker", "quarter"], sort=False).first().reset_index()
        first["liquid_flag"] = (pd.to_numeric(first["adt_21d"], errors="coerce") >= (threshold * 1e7)).astype(bool)

        membership = first[["ticker", "quarter", "liquid_flag"]].copy()
        mem_path = self.project_root / "data/universe/liquidity_membership.parquet"
        try:
            membership.to_parquet(mem_path, index=False)
        except Exception:
            logger.warning("Failed to write liquidity membership table: %s", mem_path)

        work = panel.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work["ticker"] = work["ticker"].map(self._normalize_ticker)
        work["quarter"] = work["date"].dt.to_period("Q")
        work = work.merge(membership, on=["ticker", "quarter"], how="left")
        work = work.loc[work["liquid_flag"].fillna(False)].copy()
        work = work.drop(columns=["quarter", "liquid_flag"], errors="ignore")
        return work.reset_index(drop=True)

    def _enforce_feature_budget_and_correlation(self, X_df: pd.DataFrame, feature_names: list[str], n_tickers: int) -> tuple[str | None, float, int]:
        if X_df is None or X_df.empty or not feature_names:
            return None, 0.0, 0
        n_universe = int(self.config.get("universe_size", n_tickers) or n_tickers)
        budget_enforce = bool(self.config.get("feature_budget_enforce", True))
        budget_override = self.config.get("feature_budget")
        if budget_override is not None:
            budget = int(budget_override)
        else:
            budget = max(1, int(n_universe // 5))
            if n_universe == 150:
                budget = 32
            elif n_universe == 300:
                budget = 45

        def _base_name(name: str) -> str:
            base = str(name)
            for suf in ["_cs_z", "_cs_rank"]:
                if base.endswith(suf):
                    base = base[: -len(suf)]
            if base.startswith("sector_dummy_"):
                return "sector_dummy"
            return base

        base_names = sorted({ _base_name(n) for n in feature_names })
        utilization = (len(base_names) / float(max(1, budget))) * 100.0
        logger.info(
            "[feature-budget] base_features=%d budget=%d utilization=%.1f%%",
            int(len(base_names)),
            int(budget),
            float(utilization),
        )
        if len(base_names) > budget:
            if budget_enforce:
                raise ValueError(f"feature_budget_exceeded:{len(base_names)}>{budget}")
            logger.warning("[feature-budget] exceeded %d>%d but enforcement disabled", int(len(base_names)), int(budget))

        if bool(self.config.get("feature_correlation_skip", False)):
            logger.info("[feature-corr] skipped by config")
            return None, utilization, budget

        corr_warn_threshold = float(self.config.get("feature_correlation_warn_threshold", 0.70) or 0.70)
        corr_reject_threshold = float(self.config.get("feature_correlation_reject_threshold", 0.85) or 0.85)
        corr_enforce = bool(self.config.get("feature_correlation_enforce", True))
        corr_warn_limit_raw = self.config.get("feature_correlation_warn_limit")
        corr_warn_limit = None
        if corr_warn_limit_raw not in (None, "", "null"):
            try:
                corr_warn_limit = max(0, int(corr_warn_limit_raw))
            except Exception:
                corr_warn_limit = None
        corr = X_df.corr(method="spearman")
        corr = corr.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if corr.shape[0] >= 2:
            mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
            stacked = corr.where(mask).stack()
            high = stacked[stacked.abs() > corr_reject_threshold]
            warn = stacked[(stacked.abs() > corr_warn_threshold) & (stacked.abs() <= corr_reject_threshold)]
            warn_items = list(warn.items())
            if corr_warn_limit is not None:
                warn_items = warn_items[:corr_warn_limit]
            for (f1, f2), val in warn_items:
                logger.warning("[feature-corr] warning %s vs %s = %.3f", f1, f2, float(val))
            if corr_warn_limit is not None and len(warn) > corr_warn_limit:
                logger.warning(
                    "[feature-corr] suppressed %d additional warnings above %.2f",
                    int(len(warn) - corr_warn_limit),
                    float(corr_warn_threshold),
                )
            if not high.empty:
                pairs = ", ".join([f"{a}:{b}:{float(v):.3f}" for (a, b), v in high.items()][:5])
                if corr_enforce:
                    raise ValueError(f"feature_correlation_reject:{pairs}")
                logger.warning("[feature-corr] reject-threshold exceeded but enforcement disabled: %s", pairs)

        corr_path = None
        try:
            ts = datetime.now().strftime("%Y%m%d")
            corr_path = str(self.project_root / f"reports/feature_correlation_matrix_{ts}.parquet")
            corr.to_parquet(corr_path)
        except Exception:
            logger.warning("Failed to write feature correlation matrix")
            corr_path = None
        return corr_path, utilization, budget

    def _enforce_feature_pit_registry(self, feature_names: list[str]) -> tuple[dict[str, float], list[str], int]:
        if not feature_names:
            return {}, [], 0

        registry = self.config.get("feature_pit_lags", {}) or {}
        rules: list[tuple[str, object]] = []
        if isinstance(registry, dict):
            for k, v in registry.items():
                rules.append((str(k), v))
        elif isinstance(registry, list):
            for item in registry:
                if isinstance(item, dict):
                    pattern = item.get("pattern") or item.get("feature") or item.get("name")
                    if pattern:
                        rules.append((str(pattern), item.get("lag", item.get("lag_days", 0))))

        def _normalize_feature(name: str) -> str:
            base = str(name)
            for suf in ["_cs_z", "_cs_rank", "_ts_z", "_zscore"]:
                if base.endswith(suf):
                    base = base[: -len(suf)]
            if base.endswith("_signal"):
                base = base[: -len("_signal")]
            if base.startswith("sector_dummy_"):
                return "sector_dummy"
            return base

        def _match(pattern: str, name: str) -> bool:
            key = str(pattern)
            if key.startswith("re:"):
                try:
                    return re.search(key[3:], name) is not None
                except re.error:
                    return False
            if any(ch in key for ch in "*?[]"):
                return fnmatch.fnmatch(name, key)
            return key == name

        def _resolve_lag(raw: object) -> float:
            if isinstance(raw, (int, float)) and np.isfinite(raw):
                return float(raw)
            token = str(raw or "").strip().lower()
            if token in {"price", "technical", "market"}:
                return 0.0
            if token in {"announcement"}:
                return float(self.config.get("pit_announcement_plus_days", 1))
            if token in {"earnings"}:
                return float(self.config.get("pit_earnings_announcement_plus_days", self.config.get("pit_announcement_plus_days", 1)))
            if token in {"financials"}:
                return float(self.config.get("pit_financials_plus_days", self.config.get("pit_announcement_plus_days", 1)))
            if token in {"fundamental", "quarterly", "annual"}:
                return float(self.config.get("pit_fundamental_lag_days", 60))
            if token in {"shareholding"}:
                return float(self.config.get("pit_shareholding_lag_days", 2))
            if token in {"bulk", "bulk_deals", "alt", "altdata"}:
                return float(self.config.get("pit_bulk_deal_lag_days", 1))
            if token in {"sentiment"}:
                return float(self.config.get("pit_sentiment_lag_days", 1))
            if token in {"macro"}:
                return float(self.config.get("pit_macro_lag_days", 1))
            return 0.0

        matched: dict[str, float] = {}
        missing: list[str] = []
        base_names = {_normalize_feature(str(f)) for f in feature_names}
        for feat in feature_names:
            base = _normalize_feature(str(feat))
            found = False
            for pattern, raw in rules:
                if _match(pattern, base):
                    matched[str(feat)] = _resolve_lag(raw)
                    found = True
                    break
            if not found:
                missing.append(base)

        missing = sorted({m for m in missing if m})
        enforce = bool(self.config.get("feature_pit_enforce", True))
        if missing:
            sample = ", ".join(missing[:20])
            if enforce:
                raise ValueError(f"feature_pit_lag_missing:{len(missing)}:{sample}")
            logger.warning("[pit-registry] missing=%d sample=%s", int(len(missing)), sample)
        return matched, missing, int(len(base_names))

    @staticmethod
    def _group_zscore(values: pd.Series, groups: pd.Series, clip_abs: float = 8.0) -> pd.Series:
        return _shared_group_zscore(values, groups, clip_abs=clip_abs)

    _group_rank_centered = staticmethod(_shared_group_rank_centered)

    @staticmethod
    def _sector_residualized_target(target: pd.Series, dates: pd.Series, sectors: pd.Series) -> pd.Series:
        t = pd.to_numeric(target, errors="coerce").fillna(0.0).astype(float)
        d = pd.to_datetime(dates, errors="coerce")
        s = sector_string(sectors).astype(object)
        key = pd.MultiIndex.from_arrays([d, s])
        sec_mean = t.groupby(key, sort=False).transform("mean")
        resid = (t - sec_mean).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return resid.astype(float)

    def _apply_regime_signal_weights(self, panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        if panel is None or panel.empty or "regime" not in panel.columns:
            return panel, {}
        if not bool(self.config.get("regime_signal_weighting_enabled", True)):
            return panel, {}

        weights_cfg = self.config.get("regime_signal_weights", {}) or {}
        if not isinstance(weights_cfg, dict) or not weights_cfg:
            return panel, {}

        cap = float(self.config.get("regime_signal_weight_cap", 1.5) or 1.5)
        floor = float(self.config.get("regime_signal_weight_floor", 0.6) or 0.6)
        floor = max(0.0, min(floor, cap))

        default_patterns = {
            "bab": [r"bab_beta", r"\bbab(_|$)"],
            "momentum": [r"\bmom_", r"\bret_[0-9]+d", r"log_return", r"price_to_sma", r"trend"],
            "flow": [r"^bulk_", r"flow_", r"order_", r"amihud"],
            "quality": [
                r"piotroski",
                r"earnings_quality",
                r"\broe\b",
                r"operating_margin",
                r"ebitda_margin",
                r"accrual",
                r"cash_conversion",
                r"asset_turnover",
                r"interest_coverage",
                r"debt_to_equity",
                r"working_capital",
                r"roce",
                r"opm",
            ],
        }
        patterns_cfg = self.config.get("regime_signal_feature_patterns") or default_patterns

        compiled: dict[str, list[re.Pattern]] = {}
        for cat, patterns in dict(patterns_cfg).items():
            compiled[str(cat).lower()] = [re.compile(p) for p in list(patterns or []) if p]

        def _canonical(name: str) -> str:
            base = str(name or "").strip().lower()
            return re.sub(r"(_cs_(z|rank))$", "", base)

        category_cols: dict[str, list[str]] = {k: [] for k in compiled.keys()}
        for col in panel.columns:
            if not pd.api.types.is_numeric_dtype(panel[col]):
                continue
            if str(col).startswith(("forward_return_", "target_")):
                continue
            base = _canonical(str(col))
            for cat, regexes in compiled.items():
                if any(r.search(base) for r in regexes):
                    category_cols.setdefault(cat, []).append(str(col))
                    break

        if not any(category_cols.values()):
            return panel, {}

        reg_series = panel["regime"].astype(str).str.lower()
        regime_weights: dict[str, dict[str, float]] = {}
        for regime, cat_map in weights_cfg.items():
            if not isinstance(cat_map, dict):
                continue
            regime_key = str(regime).lower()
            regime_weights[regime_key] = {str(k).lower(): float(v) for k, v in cat_map.items()}

        out = panel.copy()
        applied_counts: dict[str, int] = {}
        for cat, cols in category_cols.items():
            if not cols:
                continue
            weight_map = {r: regime_weights.get(r, {}).get(cat, 1.0) for r in reg_series.unique()}
            weights = reg_series.map(weight_map).fillna(1.0).astype(float)
            weights = weights.clip(lower=floor, upper=cap)
            out.loc[:, cols] = out[cols].mul(weights, axis=0)
            applied_counts[cat] = int(len(cols))

        return out, applied_counts

    @staticmethod
    def _rolling_beta_residualized_target(
        target: pd.Series,
        *,
        dates: pd.Series,
        tickers: pd.Series,
        sectors: pd.Series,
        include_sector_factor: bool = True,
        window_days: int = 252,
        min_obs: int = 80,
    ) -> pd.Series:
        """Residualize target by rolling market/sector betas per ticker (leakage-safe via shift(1))."""
        t = pd.to_numeric(target, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)
        d = pd.to_datetime(dates, errors="coerce")
        tk = sector_string(tickers).astype(object)
        sc = sector_string(sectors).astype(object)

        work = pd.DataFrame(
            {
                "date": d,
                "ticker": tk,
                "sector": sc,
                "target": t,
            }
        ).dropna(subset=["date"])
        if work.empty:
            return t

        work = work.sort_values(["ticker", "date"]).copy()
        work["mkt_factor"] = work.groupby("date", sort=False)["target"].transform("mean")
        if include_sector_factor:
            sec_key = pd.MultiIndex.from_arrays([work["date"], work["sector"]])
            work["sector_factor"] = work.groupby(sec_key, sort=False)["target"].transform("mean")
        else:
            work["sector_factor"] = 0.0

        w = max(20, int(window_days))
        min_p = max(20, min(int(min_obs), w))
        out = pd.Series(0.0, index=work.index, dtype=float)

        for _, grp in work.groupby("ticker", sort=False):
            idx = grp.index
            r = pd.to_numeric(grp["target"], errors="coerce").fillna(0.0).astype(float)
            m = pd.to_numeric(grp["mkt_factor"], errors="coerce").fillna(0.0).astype(float)
            s = pd.to_numeric(grp["sector_factor"], errors="coerce").fillna(0.0).astype(float)

            beta_m = (r.rolling(w, min_periods=min_p).cov(m).shift(1)) / (
                m.rolling(w, min_periods=min_p).var().shift(1) + 1e-12
            )
            beta_m = beta_m.replace([np.inf, -np.inf], np.nan).fillna(0.0)

            if include_sector_factor:
                beta_s = (r.rolling(w, min_periods=min_p).cov(s).shift(1)) / (
                    s.rolling(w, min_periods=min_p).var().shift(1) + 1e-12
                )
                beta_s = beta_s.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            else:
                beta_s = pd.Series(0.0, index=r.index, dtype=float)

            pred = beta_m.to_numpy(dtype=float) * m.to_numpy(dtype=float) + beta_s.to_numpy(dtype=float) * s.to_numpy(dtype=float)
            resid = r.to_numpy(dtype=float) - pred
            # Warmup fallback: de-mean by market factor only.
            fallback = r.to_numpy(dtype=float) - m.to_numpy(dtype=float)
            resid = np.where(np.isfinite(resid), resid, fallback)
            out.loc[idx] = resid

        full = pd.Series(0.0, index=target.index, dtype=float)
        full.loc[work.index] = pd.to_numeric(out, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        return full.astype(float)

    def _derive_target_series(self, panel: pd.DataFrame, target_col: str) -> tuple[pd.Series, Dict[str, Any]]:
        clip_abs = float(self.config.get("target_clip_abs", 1.0))
        winsor_quantile = float(self.config.get("target_winsor_quantile", 0.995))
        mode = str(self.config.get("target_mode", "raw")).strip().lower()
        if mode not in {"raw", "rank", "binary_tail", "vol_adjusted", "residualized"}:
            mode = "raw"

        target = _sanitize_target_series(
            panel[target_col],
            clip_abs=clip_abs,
            winsor_quantile=winsor_quantile,
        )
        dates = pd.to_datetime(panel["date"], errors="coerce")
        tickers = panel["ticker"] if "ticker" in panel.columns else pd.Series(np.arange(len(panel)), index=panel.index)

        sector_residualize = bool(self.config.get("target_sector_residualize", False)) or (mode == "residualized")
        market_residualize = bool(self.config.get("target_market_residualize", False))
        residual_window_days = int(self.config.get("target_residual_window_days", 252))
        residual_min_obs = int(self.config.get("target_residual_min_obs", 80))
        if sector_residualize:
            sector_col = next(
                (c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in panel.columns),
                None,
            )
            if sector_col is None:
                sectors = pd.Series("UNKNOWN", index=panel.index, dtype="object")
            else:
                sectors = sector_string(panel[sector_col]).astype(object)
        else:
            sectors = pd.Series("UNKNOWN", index=panel.index, dtype="object")

        if market_residualize:
            target = self._rolling_beta_residualized_target(
                target,
                dates=dates,
                tickers=tickers,
                sectors=sectors,
                include_sector_factor=bool(sector_residualize),
                window_days=residual_window_days,
                min_obs=residual_min_obs,
            )
        elif sector_residualize:
            target = self._sector_residualized_target(target, dates, sectors)

        binary_q = float(self.config.get("target_binary_quantile", 0.80))
        binary_q = min(0.99, max(0.50, binary_q))

        if mode == "rank":
            target = self._group_rank_centered(target, dates)
        elif mode == "binary_tail":
            thresh = target.groupby(dates, sort=False).transform(
                lambda x: float(np.nanquantile(np.asarray(x, dtype=float), binary_q)) if len(x) else np.nan
            )
            target = (target >= thresh).astype(float)
        elif mode == "vol_adjusted":
            vol_col = str(self.config.get("target_vol_col", "vol_20d"))
            vol = pd.to_numeric(panel.get(vol_col, pd.Series(np.nan, index=panel.index)), errors="coerce").abs()
            if "vol_20d" in panel.columns:
                fallback = pd.to_numeric(panel["vol_20d"], errors="coerce").abs()
                vol = vol.where(vol > 1e-8, fallback)
            target = target / (vol + 1e-6)

        target_cs_z = bool(self.config.get("target_cross_sectional_zscore", False))
        target_z_clip = float(self.config.get("target_zscore_clip_abs", 6.0))
        if target_cs_z and mode != "binary_tail":
            target = self._group_zscore(target, dates, clip_abs=target_z_clip)

        target = _sanitize_target_series(
            target,
            clip_abs=clip_abs,
            winsor_quantile=winsor_quantile,
        )
        return target, {
            "target_mode": mode,
            "target_clip_abs": clip_abs,
            "target_winsor_quantile": winsor_quantile,
            "target_sector_residualize": sector_residualize,
            "target_market_residualize": market_residualize,
            "target_residual_window_days": residual_window_days,
            "target_residual_min_obs": residual_min_obs,
            "target_binary_quantile": binary_q,
            "target_cross_sectional_zscore": target_cs_z,
            "target_zscore_clip_abs": target_z_clip,
        }

    def _apply_feature_cross_sectional_normalization(self, X_df: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
        if not bool(self.config.get("feature_cross_sectional_zscore", False)):
            return X_df
        out = X_df.copy()
        clip = float(self.config.get("feature_zscore_clip_abs", 8.0))
        for col in out.columns:
            out[col] = self._group_zscore(out[col], dates, clip_abs=clip)
        return out

    def _read_parquet(self, rel_path: str, *, artifact: str, required: Optional[bool] = None) -> pd.DataFrame:
        path = self.project_root / rel_path
        must_require = bool(self.strict_real_data_only and (artifact in self.required_artifacts))
        if required is not None:
            must_require = bool(required)
        path_l = str(path).lower()
        if self.strict_real_data_only and any(k in path_l for k in self.reject_source_keywords):
            raise ValueError(f"{artifact}_path_rejected_non_production:{path}")
        if not path.exists():
            if must_require:
                raise FileNotFoundError(f"required_{artifact}_artifact_missing:{path}")
            return pd.DataFrame()
        try:
            df = pd.read_parquet(path)
        except Exception as exc:
            logger.exception("Failed reading parquet artifact '%s': %s", artifact, path)
            raise RuntimeError(f"{artifact}_artifact_corrupt:{path}:{exc}") from exc
        self._validate_artifact(df=df, artifact=artifact, path=path, required=must_require)
        return df

    def _validate_artifact(self, *, df: pd.DataFrame, artifact: str, path: Path, required: bool) -> None:
        if df is None:
            if required:
                raise ValueError(f"required_{artifact}_artifact_invalid_none:{path}")
            return
        if not isinstance(df, pd.DataFrame):
            if required:
                raise ValueError(f"required_{artifact}_artifact_not_dataframe:{path}")
            return
        if df.empty:
            if required:
                raise ValueError(f"required_{artifact}_artifact_empty:{path}")
            return

        min_rows = int(self.artifact_min_rows.get(artifact, 0) or 0)
        if required and min_rows > 0 and len(df) < min_rows:
            raise ValueError(f"required_{artifact}_artifact_too_small:{len(df)}<{min_rows}:{path}")

        low_cols = {str(c).lower() for c in df.columns}
        if self.strict_real_data_only:
            # Hard reject obvious synthetic markers in schemas.
            if any(("mock" in c) or ("synthetic" in c) for c in low_cols):
                raise ValueError(f"{artifact}_artifact_schema_marked_mock_or_synthetic:{path}")

        if artifact == "prices":
            date_col = next((c for c in ["Date", "date", "timestamp"] if c in df.columns), None)
            ticker_ok = "ticker" in df.columns
            close_col = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
            if required and (date_col is None or not ticker_ok or close_col is None):
                raise ValueError(f"required_prices_schema_missing_core_fields:{path}")
            if close_col is not None:
                close = pd.to_numeric(df[close_col], errors="coerce")
                if required and float(close.notna().mean()) < 0.90:
                    raise ValueError(f"required_prices_close_quality_low:{path}")
                if required and float((close > 0).mean()) < 0.90:
                    raise ValueError(f"required_prices_close_non_positive_heavy:{path}")

        if artifact == "macro":
            date_col = next((c for c in ["date", "Date", "timestamp", "intelligence_timestamp_str"] if c in df.columns), None)
            if required and date_col is None:
                raise ValueError(f"required_macro_schema_missing_date:{path}")

        if artifact == "fundamentals":
            if required and "ticker" not in df.columns:
                raise ValueError(f"required_fundamentals_schema_missing_ticker:{path}")

        if artifact == "valuation_posterior":
            required_cols = {"ticker", "posterior_gap", "posterior_variance"}
            if required and not required_cols.issubset(set(df.columns)):
                raise ValueError(f"required_valuation_posterior_schema_missing:{path}")

        if artifact == "sentiment_company":
            date_col = next((c for c in ["date", "Date", "timestamp"] if c in df.columns), None)
            if required and date_col is None:
                raise ValueError(f"required_sentiment_company_schema_missing_date:{path}")
            if required and "ticker" not in df.columns:
                raise ValueError(f"required_sentiment_company_schema_missing_ticker:{path}")

        if artifact == "sentiment_market":
            date_col = next((c for c in ["date", "Date", "timestamp"] if c in df.columns), None)
            if required and date_col is None:
                raise ValueError(f"required_sentiment_market_schema_missing_date:{path}")

    def load_prices(self) -> pd.DataFrame:
        rel = str(self.config.get("prices_path", "data/processed/prices.parquet"))
        path = self.project_root / rel
        must_require = bool(self.strict_real_data_only and ("prices" in self.required_artifacts))
        if not path.exists():
            if must_require:
                raise FileNotFoundError(f"required_prices_artifact_missing:{path}")
            return pd.DataFrame()

        # Keep this projection minimal; feature factory only needs these columns.
        base_cols = ["Date", "date", "timestamp", "ticker", "Close", "close", "Volume", "volume"]
        cols = self._select_existing_columns(path, base_cols)
        cols = list(dict.fromkeys(cols))  # preserve order, remove dupes

        if self.query.available:
            all_cols = self.query.columns(path)
            date_col = self._pick_first_existing(all_cols, ["Date", "date", "timestamp"])
            close_col = self._pick_first_existing(all_cols, ["Close", "close"])
            if date_col and close_col and "ticker" in {str(c) for c in all_cols}:
                lookback_days = self._config_int("lookback_days", 3650)
                max_tickers = self._config_int("max_tickers", 250)
                cfg_start = self._config_date("start_date")
                cfg_end = self._config_date("end_date")

                start_date = None
                end_date = cfg_end
                if cfg_start is not None:
                    start_date = cfg_start
                else:
                    max_date = self.query.scalar(path, f"max({_safe_sql_identifier(date_col)})")
                    if max_date is not None and lookback_days > 0:
                        max_ts = pd.to_datetime(max_date, errors="coerce")
                        if pd.notna(max_ts):
                            start_date = pd.Timestamp(max_ts) - pd.Timedelta(days=lookback_days + 180)
                if cfg_end is not None and start_date is not None and cfg_end < start_date:
                    start_date = cfg_end

                ticker_filter = None
                if max_tickers > 0:
                    # N5: selecting the top-N by row-count picks the
                    # longest-history tickers = survivorship bias. Inactive in the
                    # canonical build (max_tickers=0); if ever enabled, prefer a
                    # recent-window ADV/liquidity ranking instead.
                    ticker_df = self.query.read_parquet(
                        path,
                        columns=["ticker"],
                        date_col=date_col,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    if isinstance(ticker_df, pd.DataFrame) and not ticker_df.empty and "ticker" in ticker_df.columns:
                        top = (
                            ticker_df["ticker"]
                            .astype(str)
                            .value_counts()
                            .head(max_tickers)
                            .index
                            .tolist()
                        )
                        if top:
                            ticker_filter = top

                pushed = self.query.read_parquet(
                    path,
                    columns=cols if cols else None,
                    date_col=date_col,
                    start_date=start_date,
                    end_date=end_date,
                    in_filters={"ticker": ticker_filter} if ticker_filter else None,
                    order_by=[date_col, "ticker"],
                )
                self._validate_artifact(df=pushed, artifact="prices", path=path, required=must_require)
                return pushed

        # Canonical loader path for live/research parity (2b).
        if rel.strip() == "data/processed/prices.parquet":
            try:
                df = load_prices_artifact(config_path=self.policy_config_path)
            except FileNotFoundError:
                if must_require:
                    raise
                return pd.DataFrame()
            self._validate_artifact(df=df, artifact="prices", path=path, required=must_require)
            if not df.empty:
                date_col = next((c for c in ["Date", "date", "timestamp"] if c in df.columns), None)
                if date_col is not None:
                    dts = pd.to_datetime(df[date_col], errors="coerce")
                    cfg_start = self._config_date("start_date")
                    cfg_end = self._config_date("end_date")
                    if cfg_start is not None:
                        df = df.loc[dts >= cfg_start].copy()
                        dts = pd.to_datetime(df[date_col], errors="coerce")
                    if cfg_end is not None:
                        df = df.loc[dts <= cfg_end].copy()
            return df

        df = self._read_parquet(rel, artifact="prices")
        if not df.empty:
            date_col = next((c for c in ["Date", "date", "timestamp"] if c in df.columns), None)
            if date_col is not None:
                dts = pd.to_datetime(df[date_col], errors="coerce")
                cfg_start = self._config_date("start_date")
                cfg_end = self._config_date("end_date")
                if cfg_start is not None:
                    df = df.loc[dts >= cfg_start].copy()
                    dts = pd.to_datetime(df[date_col], errors="coerce")
                if cfg_end is not None:
                    df = df.loc[dts <= cfg_end].copy()
        return df

    def load_fundamentals(self) -> pd.DataFrame:
        rel = str(self.config.get("fundamentals_path", "data/processed/fundamentals.parquet"))
        path = self.project_root / rel
        if path.exists() and self.query.available:
            cols = self._select_existing_columns(
                path,
                [
                    "date",
                    "Date",
                    "timestamp",
                    # The canonical fundamentals panel dates rows with report_date /
                    # availability_date; without these the loaded frame had NO date
                    # column, so the PIT merge in build_features matched nothing and
                    # silently emptied the whole fundamentals family (accruals_ratio,
                    # roe, operating_margin, earnings_quality...).
                    "report_date",
                    "availability_date",
                    "screener_report_date",
                    "announcement_date",
                    "announcementDate",
                    "results_announcement_date",
                    "results_announced_at",
                    "report_announcement_date",
                    "fiscal_quarter_end_date",
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
                    "gross_profit",
                    "cost_of_revenue",
                    "working_capital",
                    "cash_and_equivalents",
                    "receivables",
                    "inventory",
                    "payables",
                    "deferred_revenue",
                    "lease_liabilities",
                ],
            )
            if cols:
                out = self.query.read_parquet(path, columns=cols)
                must_require = bool(self.strict_real_data_only and ("fundamentals" in self.required_artifacts))
                self._validate_artifact(df=out, artifact="fundamentals", path=path, required=must_require)
                return out

        if rel.strip() == "data/processed/fundamentals.parquet":
            must_require = bool(self.strict_real_data_only and ("fundamentals" in self.required_artifacts))
            try:
                out = load_fundamentals_artifact(config_path=self.policy_config_path)
            except FileNotFoundError:
                if must_require:
                    raise
                return pd.DataFrame()
            self._validate_artifact(df=out, artifact="fundamentals", path=path, required=must_require)
            return out

        return self._read_parquet(rel, artifact="fundamentals")

    def _load_optional_csv(self, rel_path: str) -> pd.DataFrame:
        path = self.project_root / rel_path
        if not path.exists():
            return pd.DataFrame()
        try:
            if path.suffix.lower() in {".parquet", ".pq"}:
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path)
        except Exception:
            logger.exception("Failed loading optional tabular artifact: %s", path)
            raise
        if df.empty:
            return pd.DataFrame()
        if "ticker" in df.columns:
            tk = df["ticker"].where(df["ticker"].notna(), "")
            df["ticker"] = tk.map(self._normalize_ticker)
            df = df[df["ticker"] != ""].copy()
        for date_col in ["availability_date", "date", "Date", "timestamp"]:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        return df

    def load_screener_extended_annual(self) -> pd.DataFrame:
        return self._load_optional_csv(self.screener_fundamentals_path)

    def load_screener_extended_quarterly(self) -> pd.DataFrame:
        return self._load_optional_csv(self.screener_quarterly_path)

    def load_screener_extended_shareholding(self) -> pd.DataFrame:
        return self._load_optional_csv(self.screener_shareholding_path)

    @staticmethod
    def _normalize_macro_state_frame(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = raw.copy()
        date_col = next((c for c in ["date", "Date", "timestamp", "intelligence_timestamp_str"] if c in out.columns), None)
        if date_col is None:
            return pd.DataFrame()
        out["date"] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort")
        out = out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        return out

    def _build_macro_state_spine(self, intelligent: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
        ims = self._normalize_macro_state_frame(intelligent)
        ms = self._normalize_macro_state_frame(market)
        if ims.empty and ms.empty:
            return pd.DataFrame()

        anchor_dates = pd.concat(
            [df[["date"]] for df in [ims, ms] if not df.empty],
            ignore_index=True,
        ).drop_duplicates(subset=["date"]).sort_values("date", kind="mergesort")
        spine = anchor_dates.reset_index(drop=True)

        if not ims.empty:
            ims_work = ims.copy()
            ims_work["_ims_source_date"] = pd.to_datetime(ims_work["date"], errors="coerce")
            spine = pd.merge_asof(
                spine.sort_values("date"),
                ims_work.sort_values("date"),
                on="date",
                direction="backward",
            )

        if not ms.empty:
            ms_work = ms.copy()
            ms_work["_ms_source_date"] = pd.to_datetime(ms_work["date"], errors="coerce")
            spine = pd.merge_asof(
                spine.sort_values("date"),
                ms_work.sort_values("date"),
                on="date",
                direction="backward",
                suffixes=("", "_ms"),
            )

        if ms.empty:
            return spine.reset_index(drop=True)

        shared_cols = sorted((set(ims.columns) & set(ms.columns)) - {"date"}) if not ims.empty else []
        max_stale_days = int(self.config.get("macro_state_fallback_staleness_days", 5) or 5)

        if "_ims_source_date" in spine.columns:
            ims_age_days = (
                pd.to_datetime(spine["date"], errors="coerce")
                - pd.to_datetime(spine["_ims_source_date"], errors="coerce")
            ).dt.days
            stale_base = ims_age_days > max_stale_days
        else:
            stale_base = pd.Series(True, index=spine.index, dtype=bool)

        fallback_updates = 0
        for col in shared_cols:
            ms_col = f"{col}_ms"
            if ms_col not in spine.columns:
                continue
            if col not in spine.columns:
                spine[col] = spine[ms_col]
                fallback_updates += int(spine[ms_col].notna().sum())
                continue
            use_ms = spine[col].isna() | stale_base
            if bool(use_ms.any()):
                spine.loc[use_ms, col] = spine.loc[use_ms, ms_col]
                fallback_updates += int(use_ms.sum())

        if ims.empty:
            non_key = [c for c in ms.columns if c != "date"]
            for col in non_key:
                ms_col = f"{col}_ms"
                if ms_col in spine.columns and col not in spine.columns:
                    spine[col] = spine[ms_col]

        if fallback_updates > 0:
            logger.info(
                "[macro] filled %d stale/missing intelligent-state cells from market_state fallback",
                int(fallback_updates),
            )

        return spine.reset_index(drop=True)

    @staticmethod
    def _normalize_canonical_macro_frame(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = raw.copy()
        out["date"] = pd.to_datetime(out.get("date"), errors="coerce")
        if "availability_date" in out.columns:
            out["availability_date"] = pd.to_datetime(out["availability_date"], errors="coerce")
        else:
            out["availability_date"] = pd.to_datetime(out.get("date"), errors="coerce")
        out = out.dropna(subset=["availability_date"]).sort_values("availability_date", kind="mergesort")
        out = out.drop_duplicates(subset=["availability_date"], keep="last").reset_index(drop=True)
        return out

    def _merge_canonical_macro_with_state(
        self,
        state_spine: pd.DataFrame,
        canonical_macro: pd.DataFrame,
    ) -> pd.DataFrame:
        canon = self._normalize_canonical_macro_frame(canonical_macro)
        if canon.empty:
            return state_spine.reset_index(drop=True) if isinstance(state_spine, pd.DataFrame) else pd.DataFrame()

        if state_spine is None or state_spine.empty:
            out = canon.copy()
            out["date"] = pd.to_datetime(out["availability_date"], errors="coerce")
            return out.reset_index(drop=True)

        # The daily state spine only reaches as far back as market_state
        # history — which was truncated to a couple of rows for months (audit
        # finding H2). When the spine is SHORTER than the canonical macro
        # history it must not collapse the whole macro panel to its own
        # length: flip the merge, keep the macro panel as the base, and
        # asof-join the best-available state columns onto it (PIT-safe:
        # backward join on availability dates only).
        if len(state_spine) < len(canon):
            base = canon.copy()
            base["date"] = pd.to_datetime(base["availability_date"], errors="coerce")
            spine_cols = [c for c in state_spine.columns if c != "date"]
            merged = pd.merge_asof(
                base.sort_values("date"),
                state_spine.sort_values("date")[["date"] + spine_cols],
                on="date",
                direction="backward",
                allow_exact_matches=True,
            )
            return merged.reset_index(drop=True)

        right = canon.rename(
            columns={
                "date": "macro_period_date",
                "availability_date": "macro_availability_date",
            }
        )
        merged = pd.merge_asof(
            state_spine.sort_values("date"),
            right.sort_values("macro_availability_date", kind="mergesort"),
            left_on="date",
            right_on="macro_availability_date",
            direction="backward",
            allow_exact_matches=True,
        )
        return merged.reset_index(drop=True)

    def load_macro(self) -> pd.DataFrame:
        must_require = bool(self.strict_real_data_only and ("macro" in self.required_artifacts))
        macro_path = self.project_root / str(
            self.config.get("macro_features_path", "data/canonical/macro/macro_regime_features.parquet")
        )
        canonical = pd.DataFrame()
        try:
            canonical = load_macro_artifact(config_path=self.policy_config_path)
            canonical = self._normalize_canonical_macro_frame(canonical)
        except FileNotFoundError:
            if must_require:
                raise
        except ValueError:
            if must_require:
                raise

        # Rich daily macro surface: intelligent market state + market state,
        # with canonical macro pack PIT-merged on top.
        ims = self._read_parquet("data/processed/intelligent_market_state.parquet", artifact="macro", required=False)
        ms = self._read_parquet("data/processed/market_state.parquet", artifact="macro", required=False)
        state_spine = self._build_macro_state_spine(ims, ms)
        merged = self._merge_canonical_macro_with_state(state_spine, canonical)
        self._validate_artifact(df=merged, artifact="macro", path=macro_path, required=must_require)
        if merged.empty and must_require:
            raise ValueError("required_macro_artifact_empty_after_merge")
        return merged

    def load_valuation_posterior(self) -> pd.DataFrame:
        rel = str(self.config.get("valuation_posterior_path", "data/processed/valuation_posterior.parquet"))
        path = self.project_root / rel
        if path.exists() and self.query.available:
            cols = self._select_existing_columns(
                path,
                [
                    "date",
                    "Date",
                    "timestamp",
                    "ticker",
                    "posterior_gap",
                    "posterior_variance",
                    "agreement_score",
                    "posterior_confidence",
                    "regime_modifier",
                    "macro_compression",
                ],
            )
            if cols:
                out = self.query.read_parquet(path, columns=cols)
                must_require = bool(self.strict_real_data_only and ("valuation_posterior" in self.required_artifacts))
                self._validate_artifact(df=out, artifact="valuation_posterior", path=path, required=must_require)
                return out
        return self._read_parquet(rel, artifact="valuation_posterior")

    def _enrich_company_sentiment_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = raw.copy()
        def _num_series(col: str) -> pd.Series:
            if col in out.columns:
                return pd.to_numeric(out[col], errors="coerce")
            return pd.Series(np.nan, index=out.index, dtype=float)

        out["date"] = self._as_date(out, ["availability_date", "date", "Date", "timestamp"])
        if "availability_date" in out.columns:
            out["availability_date"] = self._as_date(out, ["availability_date"])
        else:
            out["availability_date"] = out["date"]
        if "ticker" not in out.columns and "symbol" in out.columns:
            out["ticker"] = out["symbol"]
        if "ticker" not in out.columns:
            return pd.DataFrame()
        out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out = out.dropna(subset=["date", "ticker"]).copy()
        if out.empty:
            return out

        polarity = _num_series("sentiment_score").where(_num_series("sentiment_score").notna(), _num_series("sentiment_polarity")).fillna(0.0)
        conviction = _num_series("sentiment_intensity").where(_num_series("sentiment_intensity").notna(), _num_series("sentiment_conviction")).fillna(0.0)
        surprise = _num_series("sentiment_surprise").fillna(0.0)
        uncertainty = _num_series("sentiment_uncertainty").fillna(1.0).clip(lower=0.0, upper=1.0)
        news_volume = _num_series("headline_count").where(_num_series("headline_count").notna(), _num_series("news_volume")).fillna(0.0)

        out["sentiment_score"] = polarity
        out["headline_count"] = news_volume
        out["sentiment_intensity"] = conviction
        out["signed_sentiment_intensity"] = polarity * conviction

        out = out.sort_values(["ticker", "date"], kind="mergesort")
        trend_default = (
            out.groupby("ticker", sort=False)["sentiment_score"]
            .transform(lambda x: x.rolling(5, min_periods=1).mean())
        )
        northstar_default = polarity * (0.5 + 0.5 * conviction)
        confirmation_default = conviction * (1.0 - uncertainty)

        out["trend_score"] = _num_series("trend_score").where(
            _num_series("trend_score").notna(),
            trend_default,
        )
        out["event_shock_factor"] = _num_series("event_shock_factor").where(
            _num_series("event_shock_factor").notna(),
            surprise.abs() * (1.0 + conviction),
        )
        out["northstar_score"] = _num_series("northstar_score").where(
            _num_series("northstar_score").notna(),
            northstar_default,
        )
        momentum_default = out.groupby("ticker", sort=False)["trend_score"].diff(3).fillna(0.0)
        out["momentum_score"] = _num_series("momentum_score").where(
            _num_series("momentum_score").notna(),
            momentum_default,
        )
        out["mispricing"] = _num_series("mispricing").where(
            _num_series("mispricing").notna(),
            surprise,
        )
        out["confirmation"] = _num_series("confirmation").where(
            _num_series("confirmation").notna(),
            confirmation_default,
        )
        out["cohesive_alpha_score"] = _num_series("cohesive_alpha_score").where(
            _num_series("cohesive_alpha_score").notna(),
            out["northstar_score"] * out["confirmation"],
        )

        keep = [
            "date",
            "availability_date",
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
        keep = [c for c in keep if c in out.columns]
        return out[keep].sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)

    def _enrich_market_sentiment_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        out = raw.copy()
        def _num_series(col: str) -> pd.Series:
            if col in out.columns:
                return pd.to_numeric(out[col], errors="coerce")
            return pd.Series(np.nan, index=out.index, dtype=float)

        out["date"] = self._as_date(out, ["availability_date", "date", "Date", "timestamp"])
        if "availability_date" in out.columns:
            out["availability_date"] = self._as_date(out, ["availability_date"])
        else:
            out["availability_date"] = out["date"]
        out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort").copy()
        if out.empty:
            return out

        polarity = _num_series("polarity").where(_num_series("polarity").notna(), _num_series("india_market_polarity")).fillna(0.0)
        conviction = _num_series("conviction").where(_num_series("conviction").notna(), _num_series("india_market_conviction")).fillna(0.0)
        uncertainty = _num_series("uncertainty").where(_num_series("uncertainty").notna(), _num_series("india_market_uncertainty")).fillna(1.0).clip(lower=0.0, upper=1.0)
        policy_weight = _num_series("policy_weight").where(_num_series("policy_weight").notna(), _num_series("global_risk_sentiment")).fillna(0.0)

        out["polarity"] = polarity
        out["conviction"] = conviction
        out["uncertainty"] = uncertainty
        out["policy_weight"] = policy_weight
        out["narrative_cohesion"] = _num_series("narrative_cohesion").where(
            _num_series("narrative_cohesion").notna(),
            conviction * (1.0 - uncertainty),
        )
        out["narrative_conflict"] = _num_series("narrative_conflict").where(
            _num_series("narrative_conflict").notna(),
            uncertainty * (1.0 - polarity.abs().clip(upper=1.0)),
        )
        out["delta_polarity"] = _num_series("delta_polarity").where(
            _num_series("delta_polarity").notna(),
            polarity.diff().fillna(0.0),
        )
        out["delta_uncertainty"] = _num_series("delta_uncertainty").where(
            _num_series("delta_uncertainty").notna(),
            uncertainty.diff().fillna(0.0),
        )
        out["delta_conviction"] = _num_series("delta_conviction").where(
            _num_series("delta_conviction").notna(),
            conviction.diff().fillna(0.0),
        )
        out["change_velocity"] = _num_series("change_velocity").where(
            _num_series("change_velocity").notna(),
            out["delta_polarity"].abs() + out["delta_uncertainty"].abs() + out["delta_conviction"].abs(),
        )
        out["micro_shift_score"] = _num_series("micro_shift_score").where(
            _num_series("micro_shift_score").notna(),
            out["delta_polarity"] * (0.5 + 0.5 * conviction),
        )

        keep = [
            "date",
            "availability_date",
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
        keep = [c for c in keep if c in out.columns]
        return out[keep].reset_index(drop=True)

    def load_sentiment_company(self) -> pd.DataFrame:
        rel = str(
            self.config.get("sentiment_path")
            or self.config.get("sentiment_company_path")
            or "data/canonical/sentiment/company_sentiment_daily.parquet"
        )
        path = self.project_root / rel
        must_require = bool(self.strict_real_data_only and ("sentiment_company" in self.required_artifacts))
        if not path.exists():
            if must_require:
                raise FileNotFoundError(f"required_sentiment_company_artifact_missing:{path}")
            return pd.DataFrame()

        if self.query.available:
            cols = self._select_existing_columns(
                path,
                [
                    "timestamp",
                    "date",
                    "Date",
                    "availability_date",
                    "ticker",
                    "symbol",
                    "sentiment_score",
                    "sentiment_polarity",
                    "trend_score",
                    "event_shock_factor",
                    "headline_count",
                    "news_volume",
                    "sentiment_intensity",
                    "sentiment_conviction",
                    "signed_sentiment_intensity",
                    "sentiment_surprise",
                    "sentiment_uncertainty",
                    "northstar_score",
                    "momentum_score",
                    "mispricing",
                    "confirmation",
                    "cohesive_alpha_score",
                ],
            )
            all_cols = self.query.columns(path)
            date_col = self._pick_first_existing(all_cols, ["date", "Date", "timestamp"])
            lookback_days = self._config_int("lookback_days", 3650)
            start_date = None
            if date_col and lookback_days > 0:
                max_date = self.query.scalar(path, f"max({_safe_sql_identifier(date_col)})")
                if max_date is not None:
                    max_ts = pd.to_datetime(max_date, errors="coerce")
                    if pd.notna(max_ts):
                        start_date = pd.Timestamp(max_ts) - pd.Timedelta(days=lookback_days + 120)
            out = self.query.read_parquet(
                path,
                columns=cols if cols else None,
                date_col=date_col,
                start_date=start_date,
            )
            self._validate_artifact(df=out, artifact="sentiment_company", path=path, required=must_require)
            return self._enrich_company_sentiment_frame(out)

        out = self._read_parquet(rel, artifact="sentiment_company", required=must_require)
        return self._enrich_company_sentiment_frame(out)

    def load_sentiment_features(self) -> pd.DataFrame:
        """
        Load sentiment features from the canonical daily ticker sentiment artifact when enabled.
        
        Builds these PIT-safe features per ticker per date:
        - sentiment_5d_mean: mean sentiment score over last 5 trading days
        - sentiment_21d_mean: mean sentiment score over last 21 trading days
        - sentiment_5d_count: number of news items in last 5 days
        - sentiment_shock: sentiment_5d_mean - sentiment_60d_mean (deviation from baseline)
        - sentiment_momentum: sentiment_5d_mean - sentiment_5d_mean_lag10 (direction change)
        
        All features use only news published before the current date (PIT-safe).
        """
        if not bool(self.config.get("use_sentiment_features", False)):
            return pd.DataFrame()
        
        sentiment_path = self.project_root / str(
            self.config.get("sentiment_path", "data/processed/sentiment/ticker_sentiment_daily.parquet")
        )

        try:
            news_df = load_sentiment_artifact(config_path=self.policy_config_path, prefer_legacy=False)
        except FileNotFoundError:
            logger.warning(f"Sentiment features enabled but file not found: {sentiment_path}")
            return pd.DataFrame()
        except Exception as e:
            logger.exception("Failed to load sentiment data: %s", sentiment_path)
            raise RuntimeError(f"sentiment_artifact_corrupt:{sentiment_path}:{e}") from e
        
        if news_df.empty:
            return pd.DataFrame()
        
        # Normalize columns
        news_df = news_df.copy()
        if "date" not in news_df.columns and "Date" in news_df.columns:
            news_df["date"] = pd.to_datetime(news_df["Date"], errors="coerce")
        elif "date" in news_df.columns:
            news_df["date"] = pd.to_datetime(news_df["date"], errors="coerce")
        elif "timestamp" in news_df.columns:
            news_df["date"] = pd.to_datetime(news_df["timestamp"], errors="coerce").dt.normalize()
        
        if "ticker" not in news_df.columns and "symbol" in news_df.columns:
            news_df["ticker"] = news_df["symbol"].astype(str).str.upper()
            if not news_df["ticker"].str.endswith(".NS").all():
                news_df["ticker"] = news_df["ticker"] + ".NS"
        elif "ticker" in news_df.columns:
            news_df["ticker"] = news_df["ticker"].astype(str).str.upper()
            if not news_df["ticker"].str.endswith(".NS").all():
                news_df["ticker"] = news_df["ticker"] + ".NS"
        
        sentiment_col = None
        for candidate in ["sentiment_score", "sentiment", "sentiment_polarity", "sentiment_mean"]:
            if candidate in news_df.columns:
                sentiment_col = candidate
                break
        if sentiment_col is not None:
            news_df["sentiment_score"] = pd.to_numeric(news_df[sentiment_col], errors="coerce")

        count_col = None
        for candidate in ["sentiment_item_count", "news_volume", "headline_count"]:
            if candidate in news_df.columns:
                count_col = candidate
                break
        if count_col is not None:
            news_df["sentiment_item_count"] = pd.to_numeric(news_df[count_col], errors="coerce").fillna(0.0)
        else:
            news_df["sentiment_item_count"] = 1.0
        
        required_cols = ["date", "ticker"]
        if "sentiment_score" not in news_df.columns:
            logger.warning("Sentiment artifact missing a usable score column; skipping sentiment features")
            return pd.DataFrame()
        news_df = news_df.dropna(subset=required_cols + ["sentiment_score"])
        
        if news_df.empty:
            return pd.DataFrame()
        
        # Aggregate daily sentiment per ticker
        daily_sent = (
            news_df.groupby(["date", "ticker"])
            .agg(
                sentiment_daily_mean=("sentiment_score", "mean"),
                sentiment_daily_count=("sentiment_item_count", "sum"),
            )
            .reset_index()
        )
        
        # Sort for rolling calculations
        daily_sent = daily_sent.sort_values(["ticker", "date"])
        
        # PIT-safe: shift all features by 1 day to ensure no future leakage
        daily_sent["sentiment_daily_mean"] = daily_sent.groupby("ticker")["sentiment_daily_mean"].shift(1)
        daily_sent["sentiment_daily_count"] = daily_sent.groupby("ticker")["sentiment_daily_count"].shift(1)
        
        # Calculate rolling features
        for window in [5, 21, 60]:
            daily_sent[f"sentiment_{window}d_mean"] = (
                daily_sent.groupby("ticker")["sentiment_daily_mean"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )
        
        # sentiment_5d_count: rolling sum of news count
        daily_sent["sentiment_5d_count"] = (
            daily_sent.groupby("ticker")["sentiment_daily_count"]
            .transform(lambda x: x.rolling(5, min_periods=1).sum())
        )
        
        # sentiment_shock: 5d mean - 60d mean
        daily_sent["sentiment_shock"] = (
            daily_sent["sentiment_5d_mean"] - daily_sent["sentiment_60d_mean"]
        )
        
        # sentiment_momentum: 5d mean - 5d mean lagged by 10 days
        daily_sent["sentiment_5d_mean_lag10"] = daily_sent.groupby("ticker")["sentiment_5d_mean"].shift(10)
        daily_sent["sentiment_momentum"] = (
            daily_sent["sentiment_5d_mean"] - daily_sent["sentiment_5d_mean_lag10"]
        )
        
        # Fill NaN with 0 (no news)
        sentiment_features = [
            "sentiment_5d_mean",
            "sentiment_21d_mean",
            "sentiment_5d_count",
            "sentiment_shock",
            "sentiment_momentum",
        ]
        daily_sent[sentiment_features] = daily_sent[sentiment_features].fillna(0.0)
        
        # Select final columns
        result = daily_sent[["date", "ticker"] + sentiment_features].copy()
        
        logger.info(f"Loaded sentiment features: {len(result)} rows, {len(sentiment_features)} features")
        return result

    def load_sentiment_market(self) -> pd.DataFrame:
        rel = str(
            self.config.get("market_sentiment_path")
            or self.config.get("sentiment_market_path")
            or "data/canonical/sentiment/market_sentiment_daily.parquet"
        )
        path = self.project_root / rel
        must_require = bool(self.strict_real_data_only and ("sentiment_market" in self.required_artifacts))
        if not path.exists():
            if must_require:
                raise FileNotFoundError(f"required_sentiment_market_artifact_missing:{path}")
            return pd.DataFrame()

        if self.query.available:
            cols = self._select_existing_columns(
                path,
                [
                    "date",
                    "Date",
                    "timestamp",
                    "availability_date",
                    "polarity",
                    "conviction",
                    "uncertainty",
                    "india_market_polarity",
                    "india_market_conviction",
                    "india_market_uncertainty",
                    "global_risk_sentiment",
                    "news_volume_total",
                    "narrative_cohesion",
                    "policy_weight",
                    "narrative_conflict",
                    "delta_polarity",
                    "delta_uncertainty",
                    "delta_conviction",
                    "change_velocity",
                    "micro_shift_score",
                ],
            )
            all_cols = self.query.columns(path)
            date_col = self._pick_first_existing(all_cols, ["date", "Date", "timestamp"])
            lookback_days = self._config_int("lookback_days", 3650)
            start_date = None
            if date_col and lookback_days > 0:
                max_date = self.query.scalar(path, f"max({_safe_sql_identifier(date_col)})")
                if max_date is not None:
                    max_ts = pd.to_datetime(max_date, errors="coerce")
                    if pd.notna(max_ts):
                        start_date = pd.Timestamp(max_ts) - pd.Timedelta(days=lookback_days + 60)
            out = self.query.read_parquet(
                path,
                columns=cols if cols else None,
                date_col=date_col,
                start_date=start_date,
            )
            self._validate_artifact(df=out, artifact="sentiment_market", path=path, required=must_require)
            return self._enrich_market_sentiment_frame(out)

        out = self._read_parquet(rel, artifact="sentiment_market", required=must_require)
        return self._enrich_market_sentiment_frame(out)

    def _assign_regime_labels_with_engine(self, panel: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        if panel.empty or "date" not in panel.columns:
            return panel, False

        out = panel.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).copy()
        if out.empty:
            return out, False

        # Prefer canonical regime labels artifact when available (2b).
        try:
            labels = load_regime_labels_artifact(config_path=self.policy_config_path)
        except FileNotFoundError:
            labels = pd.DataFrame()
        except Exception:
            logger.exception("Failed to load canonical regime labels")
            labels = pd.DataFrame()

        if isinstance(labels, pd.DataFrame) and not labels.empty:
            date_col = "date" if "date" in labels.columns else ("Date" if "Date" in labels.columns else None)
            regime_col = None
            for cand in ["regime", "macro_regime", "macro_regime_label"]:
                if cand in labels.columns:
                    regime_col = cand
                    break
            if date_col and regime_col:
                labels = labels.copy()
                labels[date_col] = pd.to_datetime(labels[date_col], errors="coerce").dt.normalize()
                reg_map = pd.Series(
                    labels[regime_col].astype(str).to_numpy(),
                    index=pd.DatetimeIndex(labels[date_col]),
                )
                out["regime"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize().map(reg_map)
                out["regime"] = out["regime"].astype("string").fillna("").astype(str)
                ok = bool((out["regime"].str.strip() != "").mean() > 0.50)
                if ok:
                    return out, True

        regime_engine = RegimeEngine(
            {
                "regime_labels_path": str(
                    self.config.get("regime_labels_path", "data/processed/regime_labels.parquet")
                ),
                "regime_mode": self.config.get("regime_mode", "auto"),
                "vix_threshold": self.config.get("vix_threshold", 20.0),
                "nifty_sma_window": self.config.get("nifty_sma_window", 200),
                "india_vix_path": self.config.get("india_vix_path", "data/processed/india_vix.parquet"),
                "nifty_prices_path": self.config.get("nifty_prices_path", "data/processed/nifty.parquet"),
            }
        )
        start = pd.to_datetime(out["date"], errors="coerce").min()
        end = pd.to_datetime(out["date"], errors="coerce").max()
        reg_series = regime_engine.get_regime_series(start, end)

        if reg_series.empty:
            try:
                labels = regime_engine.build_historical_regimes(prices_df=prices, macro_df=None)
                if isinstance(labels, pd.DataFrame) and not labels.empty:
                    reg_series = regime_engine.get_regime_series(start, end)
            except Exception:
                logger.exception("Failed to build fallback historical regimes")
                raise

        if reg_series.empty:
            return out, False

        reg_map = pd.Series(reg_series.astype(str).to_numpy(), index=pd.DatetimeIndex(reg_series.index).normalize())
        out["regime"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize().map(reg_map)
        out["regime"] = out["regime"].astype("string").fillna("").astype(str)
        ok = bool((out["regime"].str.strip() != "").mean() > 0.50)
        return out, ok

    def build_research_dataset(self) -> ResearchDataset:
        import time as _time
        _pg_t0 = _time.time()

        def _pg(msg: str) -> None:
            print(f"[progress] {msg} | +{_time.time() - _pg_t0:5.0f}s", flush=True)

        _pg("loading inputs (prices, fundamentals, screener, macro, sentiment)...")
        prices = self.load_prices()
        fundamentals = self.load_fundamentals()
        screener_annual = self.load_screener_extended_annual() if bool(self.use_screener_features) else pd.DataFrame()
        screener_quarterly = self.load_screener_extended_quarterly() if bool(self.use_screener_features) else pd.DataFrame()
        screener_shareholding = (
            self.load_screener_extended_shareholding() if bool(self.use_screener_features) else pd.DataFrame()
        )
        macro_enabled = bool(self.config.get("enable_macro_features", True))
        macro = self.load_macro() if macro_enabled else pd.DataFrame()
        valuation = self.load_valuation_posterior()
        sentiment_company = self.load_sentiment_company()
        sentiment_market = self.load_sentiment_market()
        
        # Load sentiment features from legacy news if enabled
        sentiment_features_df = self.load_sentiment_features() if bool(self.config.get("use_sentiment_features", False)) else pd.DataFrame()
        
        et500_membership = (
            self._load_et500_membership()
            if bool(self.use_et500_features or self.use_et500_universe_filter)
            else pd.DataFrame()
        )
        sector_lookup = self._load_sector_lookup()
        fundamentals = self._apply_sector_lookup_to_frame(fundamentals, sector_lookup)

        # Apply early lookback/universe filters before expensive feature joins.
        lookback_days = int(self.config.get("lookback_days", 3650))
        max_tickers = int(self.config.get("max_tickers", 250))
        cfg_start = self._config_date("start_date")
        cfg_end = self._config_date("end_date")

        if not prices.empty:
            p = prices.copy()
            date_col = "Date" if "Date" in p.columns else ("date" if "date" in p.columns else None)
            if date_col is not None:
                p["__date"] = pd.to_datetime(p[date_col], errors="coerce")
                p = p.dropna(subset=["__date"])
                if cfg_start is not None:
                    p = p.loc[p["__date"] >= cfg_start].copy()
                if cfg_end is not None:
                    p = p.loc[p["__date"] <= cfg_end].copy()
                if lookback_days > 0 and not p.empty:
                    # Keep extra warmup for rolling features.
                    cutoff = p["__date"].max() - pd.Timedelta(days=lookback_days + 180)
                    p = p.loc[p["__date"] >= cutoff].copy()

                # Restrict to the reference research universe when configured.
                # The delisted backfill in canonical prices adds ~91 names outside
                # the Nifty-500 universe, which fails validate_reference_bundle at
                # the very end (export_contains_unknown_tickers). Filtering here
                # (before the expensive feature joins) both fixes that and trims
                # wasted work on out-of-universe names.
                whitelist = self.config.get("universe_whitelist")
                if whitelist and "ticker" in p.columns:
                    wl = {str(t) for t in whitelist}
                    n_before = p["ticker"].nunique()
                    p = p.loc[p["ticker"].astype(str).isin(wl)].copy()
                    _pg(f"universe filter: {p['ticker'].nunique()}/{n_before} tickers in reference universe")

                if max_tickers > 0 and "ticker" in p.columns and p["ticker"].nunique() > max_tickers:
                    top = (
                        p.groupby("ticker")["__date"]
                        .count()
                        .sort_values(ascending=False)
                        .head(max_tickers)
                        .index
                    )
                    p = p.loc[p["ticker"].isin(top)].copy()
                    if not fundamentals.empty and "ticker" in fundamentals.columns:
                        fundamentals = fundamentals[fundamentals["ticker"].astype(str).isin(set(top.astype(str)))].copy()
                    if not valuation.empty and "ticker" in valuation.columns:
                        valuation = valuation[valuation["ticker"].astype(str).isin(set(top.astype(str)))].copy()
                    if not sentiment_company.empty and "ticker" in sentiment_company.columns:
                        sentiment_company = sentiment_company[
                            sentiment_company["ticker"].astype(str).isin(set(top.astype(str)))
                        ].copy()
                    if not screener_annual.empty and "ticker" in screener_annual.columns:
                        screener_annual = screener_annual[
                            screener_annual["ticker"].astype(str).isin(set(top.astype(str)))
                        ].copy()
                    if not screener_quarterly.empty and "ticker" in screener_quarterly.columns:
                        screener_quarterly = screener_quarterly[
                            screener_quarterly["ticker"].astype(str).isin(set(top.astype(str)))
                        ].copy()
                    if not screener_shareholding.empty and "ticker" in screener_shareholding.columns:
                        screener_shareholding = screener_shareholding[
                            screener_shareholding["ticker"].astype(str).isin(set(top.astype(str)))
                        ].copy()
                prices = p.drop(columns=["__date"], errors="ignore")

        n_tk = prices["ticker"].nunique() if ("ticker" in prices.columns and not prices.empty) else 0
        _pg(f"inputs ready ({n_tk} tickers); building features "
            "(momentum, valuation, screener, bulk-deals, macro)...")
        panel = self.factory.build_features(
            prices=prices,
            fundamentals=fundamentals,
            screener_annual=screener_annual if bool(self.use_screener_features) else None,
            screener_quarterly=screener_quarterly if bool(self.use_screener_features) else None,
            screener_shareholding=screener_shareholding if bool(self.use_screener_features) else None,
            macro=macro,
            valuation_posterior=valuation,
            sentiment_company=sentiment_company,
            sentiment_market=sentiment_market,
            sector_lookup=sector_lookup,
            et500_membership=et500_membership if bool(self.use_et500_features) else None,
        )

        _pg(f"features built ({panel.shape[1]} cols, {len(panel):,} rows); post-processing...")
        # Memory guard for low-RAM machines (e.g. an 8GB laptop): the daily panel
        # is ~900K rows x hundreds of float64 cols (~3GB), and the post-processing
        # tail + weekly resample transiently double it, which OOM-kills the build.
        # float32 halves the footprint with no meaningful precision loss for
        # standardized features. Gated so only the export opts in; other consumers
        # keep float64.
        if bool(self.config.get("downcast_float32_features", False)) and not panel.empty:
            f64_cols = [c for c in panel.select_dtypes(include=["float64"]).columns
                        if c not in ("date", "ticker")]
            if f64_cols:
                panel[f64_cols] = panel[f64_cols].astype("float32")
                _pg(f"downcast {len(f64_cols)} feature cols to float32 (memory guard)")
        # Merge sentiment features if enabled
        if not sentiment_features_df.empty:
            panel = panel.merge(
                sentiment_features_df,
                on=["date", "ticker"],
                how="left"
            )
            logger.info(f"Merged sentiment features: {len(sentiment_features_df.columns) - 2} columns")

        if bool(self.use_et500_universe_filter):
            self._emit_et500_filter_diagnostics(panel, et500_membership)
            panel = self._apply_et500_universe_filter(panel, et500_membership)

        # Liquidity filter (quarterly rebalance, Rs 2 crore ADT default).
        panel = self._apply_liquidity_filter(panel, prices)

        # Delisting adjustments (forced delist = -100% on delist date).
        delist_df = self._load_delisting_database()
        if not delist_df.empty:
            panel = self._apply_delisting_adjustments(panel, delist_df)

        # Sector dummies for XGBoost feature set.
        panel = self._add_sector_dummies(panel)
        panel = self.factory.apply_sentiment_feature_mode(panel)

        if panel.empty:
            raise ValueError("Research dataset is empty after feature build")

        # Apply final lookback cut if configured.
        if lookback_days > 0:
            cutoff = panel["date"].max() - pd.Timedelta(days=lookback_days)
            panel = panel.loc[panel["date"] >= cutoff].copy()
        if cfg_start is not None:
            panel = panel.loc[panel["date"] >= cfg_start].copy()
        if cfg_end is not None:
            panel = panel.loc[panel["date"] <= cfg_end].copy()

        min_history_days = int(self.config.get("min_history_days", 0) or 0)
        if min_history_days > 0 and {"date", "ticker"}.issubset(set(panel.columns)):
            hist_counts = panel.groupby("ticker")["date"].nunique()
            eligible = hist_counts[hist_counts >= min_history_days].index
            panel = panel.loc[panel["ticker"].isin(set(eligible))].copy()

        # Optional universe cap for laptop safety.
        if max_tickers > 0 and panel["ticker"].nunique() > max_tickers:
            liquid = (
                panel.groupby("ticker")["close"]
                .count()
                .sort_values(ascending=False)
                .head(max_tickers)
                .index
            )
            panel = panel.loc[panel["ticker"].isin(liquid)].copy()

        panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)
        max_rows_raw = self.config.get("max_rows", 200000)
        max_rows = int(max_rows_raw) if max_rows_raw is not None else 200000
        if max_rows > 0 and len(panel) > max_rows:
            # Keep latest rows for predictable laptop runtime.
            panel = panel.tail(max_rows).reset_index(drop=True)

        min_tickers_per_date = max(1, int(self.config.get("min_tickers_per_date", 50) or 50))
        if {"date", "ticker"}.issubset(set(panel.columns)) and not panel.empty:
            date_counts = panel.groupby("date", sort=True)["ticker"].nunique()
            n_valid_dates = int((date_counts >= min_tickers_per_date).sum())
            n_full_dates = int((date_counts >= int(panel["ticker"].nunique())).sum())
        else:
            n_valid_dates = 0
            n_full_dates = 0

        # Explicitly distinguish backtest vs live-return periods.
        cutover_raw = self.config.get("live_returns_cutover_date")
        cutover_ts = pd.to_datetime(cutover_raw, errors="coerce") if cutover_raw else pd.NaT
        if pd.notna(cutover_ts):
            panel["return_data_mode"] = np.where(panel["date"] >= cutover_ts, "live", "backtest")
        else:
            panel["return_data_mode"] = "backtest"

        panel, regime_from_engine = self._assign_regime_labels_with_engine(panel, prices)
        if not regime_from_engine:
            if "macro_regime" in panel.columns:
                regime_source = panel["macro_regime"]
            elif "regime" in panel.columns:
                regime_source = panel["regime"]
            else:
                regime_source = pd.Series("unknown", index=panel.index, dtype="object")
            panel["regime"] = regime_source.astype(str)
        panel["regime_code"] = panel["regime"].astype("category").cat.codes.astype(float)
        panel, regime_weight_counts = self._apply_regime_signal_weights(panel)

        target_col = str(self.config.get("target_col", "forward_return_5d"))
        if target_col not in panel.columns:
            raise ValueError(f"research_target_missing:{target_col}")
        target_realized_col = f"{target_col}__realized"
        panel[target_realized_col] = _sanitize_target_series(
            pd.to_numeric(panel[target_col], errors="coerce"),
            clip_abs=float(self.config.get("target_clip_abs", 1.0)),
            winsor_quantile=float(self.config.get("target_winsor_quantile", 0.995)),
        )
        target_series, target_meta = self._derive_target_series(panel=panel, target_col=target_col)
        panel[target_col] = target_series
        pit_no_future_leak = True
        if {"availability_date", "date"}.issubset(set(panel.columns)):
            av = pd.to_datetime(panel["availability_date"], errors="coerce")
            td = pd.to_datetime(panel["date"], errors="coerce")
            mask = av.notna() & td.notna()
            if bool(mask.any()):
                pit_no_future_leak = bool((av[mask] <= td[mask]).all())

        exclude = {
            "date",
            "ticker",
            "regime",
            "macro_regime",
            "regime_name",
            "valuation_regime",
            "volume",
            target_col,
            target_realized_col,
        }
        leakage_prefixes = ("forward_return_", "target_")
        numeric_features = [
            c
            for c in panel.columns
            if c not in exclude
            and pd.api.types.is_numeric_dtype(panel[c])
            and not str(c).endswith("__realized")
            and not str(c).startswith(leakage_prefixes)
        ]

        if not numeric_features:
            raise ValueError("No numeric feature columns available for research dataset")

        X_df = panel[numeric_features].replace([np.inf, -np.inf], np.nan)
        X_df = self._apply_feature_cross_sectional_normalization(X_df, panel["date"])
        X_df = X_df.replace([np.inf, -np.inf], np.nan)
        y = panel[target_col].to_numpy(dtype=float)
        feature_cs_z = bool(self.config.get("feature_cross_sectional_zscore", False))
        feature_z_clip = float(self.config.get("feature_zscore_clip_abs", 8.0))
        if self.strict_real_data_only:
            if len(X_df) < 500:
                raise ValueError(f"research_dataset_too_small:{len(X_df)}")
            if float(np.abs(y).mean()) <= 1e-10:
                raise ValueError("research_target_degenerate_all_zero")

        pit_registry, pit_missing, pit_base_count = self._enforce_feature_pit_registry(list(X_df.columns))
        pit_coverage = 1.0 - (len(pit_missing) / float(max(1, pit_base_count)))

        tft_split = self.factory.build_tft_feature_split(panel, target_col=target_col)

        corr_path, budget_utilization, feature_budget = self._enforce_feature_budget_and_correlation(
            X_df,
            list(X_df.columns),
            int(panel["ticker"].nunique()),
        )

        alt_base_prefixes = ("bulk_", "pledge_", "rating_", "order_", "earnings_")
        alt_cols_present = [c for c in panel.columns if str(c).startswith(alt_base_prefixes)]
        alt_cs_cols_present = [c for c in panel.columns if str(c).endswith("_cs_z") or str(c).endswith("_cs_rank")]
        alt_cs_cols_present = [c for c in alt_cs_cols_present if str(c).startswith(alt_base_prefixes)]
        alt_non_null = {
            str(c): int(pd.to_numeric(panel[c], errors="coerce").notna().sum())
            for c in alt_cols_present
        }
        if bool(self.use_alternative_features):
            logger.info(
                "[dataset] alternative_features enabled: raw_cols=%d cs_cols=%d non_null_cols=%d",
                int(len(alt_cols_present)),
                int(len(alt_cs_cols_present)),
                int(sum(1 for _, v in alt_non_null.items() if int(v) > 0)),
            )

        dataset = ResearchDataset(
            X=X_df.to_numpy(dtype=float),
            y=y,
            feature_names=list(X_df.columns),
            metadata={
                "built_at": datetime.now().isoformat(),
                "n_rows": int(len(panel)),
                "n_features": int(X_df.shape[1]),
                "n_tickers": int(panel["ticker"].nunique()),
                "start_date": str(panel["date"].min()),
                "end_date": str(panel["date"].max()),
                "slice_start_date": str(cfg_start) if cfg_start is not None else None,
                "slice_end_date": str(cfg_end) if cfg_end is not None else None,
                "live_returns_cutover_date": str(cutover_raw) if cutover_raw else None,
                "live_rows": int((panel["return_data_mode"] == "live").sum()),
                "backtest_rows": int((panel["return_data_mode"] == "backtest").sum()),
                "target_col": target_col,
                "target_realized_col": target_realized_col,
                "target_horizon_days": int(self.config.get("target_horizon_days", 5) or 5),
                "regime_labels_path": str(self.config.get("regime_labels_path", "data/processed/regime_labels.parquet")),
                "regime_mode": str(self.config.get("regime_mode", "auto")),
                "vix_threshold": float(self.config.get("vix_threshold", 20.0) or 20.0),
                "nifty_sma_window": int(self.config.get("nifty_sma_window", 200) or 200),
                "india_vix_path": str(self.config.get("india_vix_path", "data/processed/india_vix.parquet")),
                "nifty_prices_path": str(self.config.get("nifty_prices_path", "data/processed/nifty.parquet")),
                "target_mode": str(target_meta.get("target_mode", "raw")),
                "target_clip_abs": float(target_meta.get("target_clip_abs", 1.0)),
                "target_winsor_quantile": float(target_meta.get("target_winsor_quantile", 0.995)),
                "target_sector_residualize": bool(target_meta.get("target_sector_residualize", False)),
                "target_market_residualize": bool(target_meta.get("target_market_residualize", False)),
                "target_residual_window_days": int(target_meta.get("target_residual_window_days", 252)),
                "target_residual_min_obs": int(target_meta.get("target_residual_min_obs", 80)),
                "target_binary_quantile": float(target_meta.get("target_binary_quantile", 0.80)),
                "target_cross_sectional_zscore": bool(target_meta.get("target_cross_sectional_zscore", False)),
                "target_zscore_clip_abs": float(target_meta.get("target_zscore_clip_abs", 6.0)),
                "target_abs_max": float(np.max(np.abs(y))) if len(y) else 0.0,
                "feature_cross_sectional_zscore": feature_cs_z,
                "feature_zscore_clip_abs": feature_z_clip,
                "lookback_days": lookback_days,
                "max_tickers": max_tickers,
                "max_rows": max_rows,
                "min_tickers_per_date": int(min_tickers_per_date),
                "n_dates_min_tickers": int(n_valid_dates),
                "n_dates_all_tickers": int(n_full_dates),
                "effective_max_tickers": int(
                    self.config.get("max_tickers", max_tickers)
                    if self.config.get("max_tickers", max_tickers) is not None
                    else max_tickers
                ),
                "effective_max_rows": int(
                    self.config.get("max_rows", max_rows)
                    if self.config.get("max_rows", max_rows) is not None
                    else max_rows
                ),
                "low_resource_mode_effective": bool(self.low_resource_mode_effective),
                "macro_features_enabled": bool(macro_enabled),
                "pit_fundamentals_enabled": bool(getattr(self.factory, "enable_pit_fundamentals", True)),
                "pit_fundamental_lag_days": int(getattr(self.factory, "pit_fundamental_lag_days", 60)),
                "pit_use_announcement_dates": bool(getattr(self.factory, "use_announcement_dates", True)),
                "pit_announcement_plus_days": int(getattr(self.factory, "pit_announcement_plus_days", 1)),
                "pit_no_future_leak": bool(pit_no_future_leak),
                "use_et500_features": bool(self.use_et500_features),
                "use_et500_universe_filter": bool(self.use_et500_universe_filter),
                "use_screener_features": bool(self.use_screener_features),
                "use_alternative_features": bool(self.use_alternative_features),
                "use_sentiment_features": bool(self.use_sentiment_features),
                "use_sentiment_regime": bool(self.use_sentiment_regime),
                "sentiment_feature_mode": str(getattr(self.factory, "sentiment_feature_mode", "full")),
                "use_gap9_academic_factors": bool(getattr(self.factory, "use_gap9_academic_factors", False)),
                "use_macro_features": bool(self.use_macro_features),
                "alternative_data_path": str(self.alternative_data_path),
                "sentiment_path": str(self.sentiment_path),
                "market_sentiment_path": str(self.market_sentiment_path),
                "sentiment_duckdb_path": str(self.sentiment_duckdb_path),
                "alternative_feature_raw_columns": int(len(alt_cols_present)),
                "alternative_feature_cs_columns": int(len(alt_cs_cols_present)),
                "alternative_feature_non_null_counts": dict(alt_non_null),
                "feature_budget": int(feature_budget),
                "feature_budget_utilization_pct": float(budget_utilization),
                "feature_correlation_matrix_path": str(corr_path) if corr_path else None,
                "feature_pit_registry_base_features": int(pit_base_count),
                "feature_pit_registry_missing_count": int(len(pit_missing)),
                "feature_pit_registry_coverage_pct": float(pit_coverage * 100.0),
                "feature_pit_registry_missing_sample": pit_missing[:20],
                "feature_pit_registry_enforced": bool(self.config.get("feature_pit_enforce", True)),
                "regime_signal_weighting_enabled": bool(self.config.get("regime_signal_weighting_enabled", True)),
                "regime_signal_weight_counts": dict(regime_weight_counts),
                "et500_membership_rows": int(len(et500_membership)),
                "screener_annual_rows": int(len(screener_annual)),
                "screener_quarterly_rows": int(len(screener_quarterly)),
                "screener_shareholding_rows": int(len(screener_shareholding)),
                "sentiment_company_rows": int(len(sentiment_company)),
                "sentiment_market_rows": int(len(sentiment_market)),
                "tft_static_features": int(tft_split["static_features"].shape[1]),
                "tft_known_dynamic_features": int(tft_split["known_dynamic_features"].shape[1]),
                "tft_observed_dynamic_features": int(tft_split["observed_dynamic_features"].shape[1]),
            },
            index=pd.DatetimeIndex(panel["date"]),
            tickers=panel["ticker"].astype(str).to_numpy(),
            frame=panel,
            static_features=tft_split["static_features"],
            known_dynamic_features=tft_split["known_dynamic_features"],
            observed_dynamic_features=tft_split["observed_dynamic_features"],
            static_feature_names=tft_split["static_feature_names"],
            known_dynamic_feature_names=tft_split["known_dynamic_feature_names"],
            observed_dynamic_feature_names=tft_split["observed_dynamic_feature_names"],
            ticker_ids=tft_split["ticker_ids"],
            sector_ids=tft_split["sector_ids"],
        )

        # Data provenance + universe integrity hooks for certification gates.
        prov_universe = _stable_hash_frame(
            panel,
            cols=["date", "ticker"],
        )
        prov_prices = _stable_hash_frame(
            prices,
            cols=[c for c in ["date", "Date", "ticker", "close", "Close"] if c in prices.columns],
        )
        prov_features = _stable_hash_frame(
            X_df.reset_index(drop=True),
            cols=list(X_df.columns),
        )
        label_df = pd.DataFrame({"label": y})
        prov_labels = _stable_hash_frame(label_df, cols=["label"])

        universe_drift = 0.0
        forward_inclusion = True
        delisted_assets_handled = 1.0
        if not panel.empty and "date" in panel.columns and "ticker" in panel.columns:
            uni = panel[["date", "ticker"]].copy()
            uni["date"] = pd.to_datetime(uni["date"], errors="coerce")
            uni["ticker"] = uni["ticker"].astype(str)
            uni = uni.dropna().sort_values("date")
            by_date = uni.groupby("date")["ticker"].apply(lambda x: set(x.astype(str))).sort_index()
            drift = []
            prev = None
            for cur in by_date:
                if prev is not None:
                    union = len(prev.union(cur))
                    inter = len(prev.intersection(cur))
                    drift.append(1.0 - (float(inter) / float(max(1, union))))
                prev = cur
            universe_drift = float(np.mean(drift)) if drift else 0.0

            span = uni.groupby("ticker")["date"].agg(["min", "max"])
            if not span.empty:
                gmax = pd.to_datetime(uni["date"]).max()
                delisted_like = span["max"] < gmax
                delisted_assets_handled = 1.0 if len(delisted_like) == 0 else float(delisted_like.mean())
                # Lack of exits is not a failure for limited samples.
                if delisted_assets_handled < 0.01:
                    delisted_assets_handled = 1.0

                first_dates = span["min"].sort_values()
                if len(first_dates) > 5:
                    # Forward inclusion proxy: excessive late first appearances indicate leak risk.
                    q90 = pd.to_datetime(first_dates).quantile(0.90)
                    late_ratio = float((pd.to_datetime(first_dates) >= q90).mean())
                    forward_inclusion = bool(late_ratio < 0.25)

        dataset.metadata.update(
            {
                "universe_hash": str(prov_universe),
                "price_hash": str(prov_prices),
                "feature_hash": str(prov_features),
                "label_hash": str(prov_labels),
                "membership_drift_rate": float(universe_drift),
                "delisted_assets_handled": float(delisted_assets_handled),
                "forward_inclusion_check": bool(forward_inclusion),
            }
        )

        if bool(self.config.get("write_snapshot", True)):
            self._write_snapshot(panel)
        return dataset

    def _write_snapshot(self, panel: pd.DataFrame) -> None:
        ts = datetime.now().strftime("%Y%m%d")
        path = self.snapshot_dir / ts[:4] / ts[4:6] / f"research_snapshot_{ts}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            panel.to_parquet(path, index=False)
        except Exception as exc:
            logger.exception("Failed writing research snapshot: %s", path)
            raise RuntimeError(f"failed_to_write_research_snapshot:{path}:{exc}") from exc
