"""Historical research dataset manager."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.data.query_engine import DuckDBQueryEngine

from .feature_factory import FeatureFactory
from .research_types import ResearchDataset


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
        self.factory = FeatureFactory(target_horizon_days=int(self.config.get("target_horizon_days", 5)))
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
        if not self._is_low_resource_host():
            return
        cap_rows = int(self.config.get("low_resource_max_rows", 90000) or 90000)
        cap_tickers = int(self.config.get("low_resource_max_tickers", 140) or 140)
        cap_lookback = int(self.config.get("low_resource_lookback_days", 2200) or 2200)

        try:
            cur_rows = int(self.config.get("max_rows", cap_rows) or cap_rows)
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
                ],
            )
            if cols:
                out = self.query.read_parquet(path, columns=cols)
                must_require = bool(self.strict_real_data_only and ("fundamentals" in self.required_artifacts))
                self._validate_artifact(df=out, artifact="fundamentals", path=path, required=must_require)
                return out
        return self._read_parquet(rel, artifact="fundamentals")

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

    def build_research_dataset(self) -> ResearchDataset:
        prices = self.load_prices()
        fundamentals = self.load_fundamentals()
        macro = self.load_macro()
        valuation = self.load_valuation_posterior()
        sentiment_company = self.load_sentiment_company()
        sentiment_market = self.load_sentiment_market()

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
                prices = p.drop(columns=["__date"], errors="ignore")

        panel = self.factory.build_features(
            prices=prices,
            fundamentals=fundamentals,
            macro=macro,
            valuation_posterior=valuation,
            sentiment_company=sentiment_company,
            sentiment_market=sentiment_market,
        )

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
        max_rows = int(self.config.get("max_rows", 200000) or 200000)
        if max_rows > 0 and len(panel) > max_rows:
            # Keep latest rows for predictable laptop runtime.
            panel = panel.tail(max_rows).reset_index(drop=True)

        # Explicitly distinguish backtest vs live-return periods.
        cutover_raw = self.config.get("live_returns_cutover_date")
        cutover_ts = pd.to_datetime(cutover_raw, errors="coerce") if cutover_raw else pd.NaT
        if pd.notna(cutover_ts):
            panel["return_data_mode"] = np.where(panel["date"] >= cutover_ts, "live", "backtest")
        else:
            panel["return_data_mode"] = "backtest"

        panel["regime"] = panel.get("macro_regime", panel.get("regime", "unknown")).astype(str)
        panel["regime_code"] = panel["regime"].astype("category").cat.codes.astype(float)

        target_col = str(self.config.get("target_col", "forward_return_5d"))
        if target_col not in panel.columns:
            raise ValueError(f"research_target_missing:{target_col}")
        target_series, target_meta = self._derive_target_series(panel=panel, target_col=target_col)
        panel[target_col] = target_series
        exclude = {
            "date",
            "ticker",
            "regime",
            "macro_regime",
            "regime_name",
            "valuation_regime",
            target_col,
        }
        numeric_features = [
            c for c in panel.columns if c not in exclude and pd.api.types.is_numeric_dtype(panel[c])
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
