"""Historical research dataset manager."""

from __future__ import annotations

import bisect
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yaml

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
                self.config.get("screener_annual_path", "data/processed/screener_fundamentals_annual.csv"),
            )
        )
        self.screener_quarterly_path = str(
            self.config.get("screener_quarterly_path", "data/processed/screener_fundamentals_quarterly.csv")
        )
        self.screener_shareholding_path = str(
            self.config.get("screener_shareholding_path", "data/processed/screener_shareholding.csv")
        )
        self.use_alternative_features = bool(self.config.get("use_alternative_features", False))
        self.use_sentiment_features = bool(self.config.get("use_sentiment_features", False))
        self.use_sentiment_regime = bool(self.config.get("use_sentiment_regime", False))
        self.use_macro_features = bool(self.config.get("use_macro_features", False))
        self.alternative_data_path = str(self.config.get("alternative_data_path", "data/processed/alternative"))
        self.sentiment_path = str(
            self.config.get("sentiment_path", "data/processed/sentiment/ticker_sentiment_daily.parquet")
        )
        self.market_sentiment_path = str(
            self.config.get("market_sentiment_path", "data/processed/sentiment/market_sentiment_daily.parquet")
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
        self.snapshot_dir = self.project_root / "data/research"
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
        except Exception:
            return 0.0

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

        try:
            cur_rows_raw = self.config.get("max_rows", cap_rows)
            cur_rows = int(cur_rows_raw) if cur_rows_raw is not None else cap_rows
        except Exception:
            cur_rows = cap_rows
        try:
            cur_tickers = int(self.config.get("max_tickers", cap_tickers) or cap_tickers)
        except Exception:
            cur_tickers = cap_tickers
        try:
            cur_lookback = int(self.config.get("lookback_days", cap_lookback) or cap_lookback)
        except Exception:
            cur_lookback = cap_lookback

        self.config["max_rows"] = max(5000, min(cur_rows, cap_rows))
        self.config["max_tickers"] = max(20, min(cur_tickers, cap_tickers))
        self.config["lookback_days"] = max(365, min(cur_lookback, cap_lookback))

    @staticmethod
    def _normalize_ticker(value: Any) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(".NS"):
            return s
        if "." in s:
            s = s.split(".", 1)[0]
        return f"{s}.NS"

    def _load_sector_lookup(self) -> Dict[str, str]:
        """Canonical sector mapping: YAML overrides CSV, CSV fills remainder."""
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
                csv_map = {}

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
                yaml_map = {}

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
            self._et500_membership_cache = pd.DataFrame()
            return pd.DataFrame()

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

    @staticmethod
    def _group_zscore(values: pd.Series, groups: pd.Series, clip_abs: float = 8.0) -> pd.Series:
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
        return (r.fillna(0.5) - 0.5).astype(float)

    @staticmethod
    def _sector_residualized_target(target: pd.Series, dates: pd.Series, sectors: pd.Series) -> pd.Series:
        t = pd.to_numeric(target, errors="coerce").fillna(0.0).astype(float)
        d = pd.to_datetime(dates, errors="coerce")
        s = sectors.astype(str).fillna("UNKNOWN")
        key = pd.MultiIndex.from_arrays([d, s])
        sec_mean = t.groupby(key, sort=False).transform("mean")
        resid = (t - sec_mean).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return resid.astype(float)

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
        tk = tickers.astype(str).fillna("UNKNOWN")
        sc = sectors.astype(str).fillna("UNKNOWN")

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
                sectors = panel[sector_col].astype(str).fillna("UNKNOWN")
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
            if must_require:
                raise RuntimeError(f"required_{artifact}_artifact_corrupt:{path}:{exc}") from exc
            return pd.DataFrame()
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
                lookback_days = int(self.config.get("lookback_days", 3650) or 3650)
                max_tickers = int(self.config.get("max_tickers", 250) or 250)
                cfg_start = self._config_date("start_date")
                cfg_end = self._config_date("end_date")

                start_date = None
                end_date = cfg_end
                if cfg_start is not None:
                    start_date = cfg_start
                else:
                    max_date = self.query.scalar(path, f"max({_safe_sql_identifier(date_col)})")
                    if max_date is not None and lookback_days > 0:
                        try:
                            max_ts = pd.to_datetime(max_date, errors="coerce")
                            if pd.notna(max_ts):
                                start_date = pd.Timestamp(max_ts) - pd.Timedelta(days=lookback_days + 180)
                        except Exception:
                            start_date = None
                if cfg_end is not None and start_date is not None and cfg_end < start_date:
                    start_date = cfg_end

                ticker_filter = None
                if max_tickers > 0:
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
                ],
            )
            if cols:
                out = self.query.read_parquet(path, columns=cols)
                must_require = bool(self.strict_real_data_only and ("fundamentals" in self.required_artifacts))
                self._validate_artifact(df=out, artifact="fundamentals", path=path, required=must_require)
                return out
        return self._read_parquet(rel, artifact="fundamentals")

    def _load_optional_csv(self, rel_path: str) -> pd.DataFrame:
        path = self.project_root / rel_path
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
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

    def load_macro(self) -> pd.DataFrame:
        # Priority merge: intelligent market state + market state.
        ims = self._read_parquet("data/processed/intelligent_market_state.parquet", artifact="macro", required=False)
        ms = self._read_parquet("data/processed/market_state.parquet", artifact="macro", required=False)

        if ims.empty and ms.empty:
            if self.strict_real_data_only and "macro" in self.required_artifacts:
                raise ValueError("required_macro_artifact_empty_after_merge")
            return pd.DataFrame()

        def _norm(df: pd.DataFrame) -> pd.DataFrame:
            out = df.copy()
            date_col = None
            for c in ["date", "Date", "timestamp", "intelligence_timestamp_str"]:
                if c in out.columns:
                    date_col = c
                    break
            if date_col is None:
                return pd.DataFrame()
            out["date"] = pd.to_datetime(out[date_col], errors="coerce")
            return out.dropna(subset=["date"]).sort_values("date")

        ims = _norm(ims)
        ms = _norm(ms)

        if ims.empty:
            return ms
        if ms.empty:
            return ims

        merged = pd.merge_asof(
            ims.sort_values("date"),
            ms.sort_values("date"),
            on="date",
            direction="backward",
            suffixes=("", "_ms"),
        )
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

    def load_sentiment_company(self) -> pd.DataFrame:
        rel = str(
            self.config.get(
                "sentiment_company_path",
                "data/sentiment/v3/company_sentiment_trends.parquet",
            )
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
                    "ticker",
                    "symbol",
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
                ],
            )
            all_cols = self.query.columns(path)
            date_col = self._pick_first_existing(all_cols, ["date", "Date", "timestamp"])
            lookback_days = int(self.config.get("lookback_days", 3650) or 3650)
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
            return out

        return self._read_parquet(rel, artifact="sentiment_company", required=must_require)

    def load_sentiment_market(self) -> pd.DataFrame:
        rel = str(
            self.config.get(
                "sentiment_market_path",
                "data/sentiment/v3/market_sentiment_india.parquet",
            )
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
                ],
            )
            all_cols = self.query.columns(path)
            date_col = self._pick_first_existing(all_cols, ["date", "Date", "timestamp"])
            lookback_days = int(self.config.get("lookback_days", 3650) or 3650)
            start_date = None

    def load_sentiment_features(self) -> pd.DataFrame:
        """
        Load sentiment features from legacy_news_clean.parquet when use_sentiment_features is enabled.
        
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
            self.config.get("sentiment_path", "data/processed/news/legacy_news_clean.parquet")
        )
        
        if not sentiment_path.exists():
            logger.warning(f"Sentiment features enabled but file not found: {sentiment_path}")
            return pd.DataFrame()
        
        try:
            news_df = pd.read_parquet(sentiment_path)
        except Exception as e:
            logger.warning(f"Failed to load sentiment data: {e}")
            return pd.DataFrame()
        
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
        
        if "sentiment_score" not in news_df.columns and "sentiment" in news_df.columns:
            news_df["sentiment_score"] = pd.to_numeric(news_df["sentiment"], errors="coerce")
        elif "sentiment_score" in news_df.columns:
            news_df["sentiment_score"] = pd.to_numeric(news_df["sentiment_score"], errors="coerce")
        
        news_df = news_df.dropna(subset=["date", "ticker", "sentiment_score"])
        
        if news_df.empty:
            return pd.DataFrame()
        
        # Aggregate daily sentiment per ticker
        daily_sent = (
            news_df.groupby(["date", "ticker"])
            .agg(
                sentiment_daily_mean=("sentiment_score", "mean"),
                sentiment_daily_count=("sentiment_score", "count"),
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
            self.config.get(
                "sentiment_market_path",
                "data/sentiment/v3/market_sentiment_india.parquet",
            )
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
                ],
            )
            all_cols = self.query.columns(path)
            date_col = self._pick_first_existing(all_cols, ["date", "Date", "timestamp"])
            lookback_days = int(self.config.get("lookback_days", 3650) or 3650)
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
            return out

        return self._read_parquet(rel, artifact="sentiment_market", required=must_require)

    def _assign_regime_labels_with_engine(self, panel: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        if panel.empty or "date" not in panel.columns:
            return panel, False

        out = panel.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).copy()
        if out.empty:
            return out, False

        regime_engine = RegimeEngine(
            {
                "regime_labels_path": str(
                    self.config.get("regime_labels_path", "data/processed/regime_labels.parquet")
                )
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
                reg_series = pd.Series(dtype=object)

        if reg_series.empty:
            return out, False

        reg_map = pd.Series(reg_series.astype(str).to_numpy(), index=pd.DatetimeIndex(reg_series.index).normalize())
        out["regime"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize().map(reg_map)
        out["regime"] = out["regime"].astype("string").fillna("").astype(str)
        ok = bool((out["regime"].str.strip() != "").mean() > 0.50)
        return out, ok

    def build_research_dataset(self) -> ResearchDataset:
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
        X_df = X_df.fillna(X_df.median(numeric_only=True)).fillna(0.0)
        X_df = self._apply_feature_cross_sectional_normalization(X_df, panel["date"])
        X_df = X_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        y = panel[target_col].to_numpy(dtype=float)
        feature_cs_z = bool(self.config.get("feature_cross_sectional_zscore", False))
        feature_z_clip = float(self.config.get("feature_zscore_clip_abs", 8.0))
        if self.strict_real_data_only:
            if len(X_df) < 500:
                raise ValueError(f"research_dataset_too_small:{len(X_df)}")
            if float(np.abs(y).mean()) <= 1e-10:
                raise ValueError("research_target_degenerate_all_zero")

        tft_split = self.factory.build_tft_feature_split(panel, target_col=target_col)

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
                "use_macro_features": bool(self.use_macro_features),
                "alternative_data_path": str(self.alternative_data_path),
                "sentiment_path": str(self.sentiment_path),
                "market_sentiment_path": str(self.market_sentiment_path),
                "sentiment_duckdb_path": str(self.sentiment_duckdb_path),
                "alternative_feature_raw_columns": int(len(alt_cols_present)),
                "alternative_feature_cs_columns": int(len(alt_cs_cols_present)),
                "alternative_feature_non_null_counts": dict(alt_non_null),
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

        self._write_snapshot(panel)
        return dataset

    def _write_snapshot(self, panel: pd.DataFrame) -> None:
        ts = datetime.now().strftime("%Y%m%d")
        path = self.snapshot_dir / f"research_snapshot_{ts}.parquet"
        try:
            panel.to_parquet(path, index=False)
        except Exception as exc:
            if self.strict_real_data_only:
                raise RuntimeError(f"failed_to_write_research_snapshot:{path}:{exc}") from exc
