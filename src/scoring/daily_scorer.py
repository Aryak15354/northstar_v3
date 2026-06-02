"""Daily regime-aware stock scoring pipeline for Northstar v3."""

from __future__ import annotations

import pickle
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.research.dataset_manager import DatasetManager
from src.research.regime_conditional_trainer import RegimeConditionalTrainer
from src.research.regime_engine import RegimeEngine
from src.signals.sentiment_overlay import SentimentOverlay

logger = logging.getLogger(__name__)

# Turnover constraint cache file
_TURNOVER_CACHE_PATH = Path("data/paper_trading/.prev_portfolio.pkl")


def apply_turnover_constraint(
    new_ranks: pd.DataFrame,
    prev_portfolio: pd.DataFrame | None,
    max_turnover: float = 0.30,
    top_n: int = 20,
    keep_threshold: int = 35,
) -> pd.DataFrame:
    """
    Limit weekly rebalance to replacing maximum 30% of positions.
    
    Logic:
    - Keep any stock from last week's portfolio if it ranks in the top 35 this week
    - Only replace positions that have fallen below rank 35
    - Fill new slots from the top of this week's ranking
    - Cap total turnover at 30% of portfolio per week
    
    Args:
        new_ranks: DataFrame with ticker and final_score columns for current week
        prev_portfolio: DataFrame with ticker column from last week (or None)
        max_turnover: Maximum fraction of portfolio to turnover (default 0.30)
        top_n: Target number of positions (default 20)
        keep_threshold: Keep prev holdings if ranked in top N this week (default 35)
    
    Returns:
        DataFrame with turnover-constrained portfolio
    """
    if prev_portfolio is None or prev_portfolio.empty:
        # No previous portfolio, just take top N
        work = new_ranks.copy()
        work["rank"] = work["final_score"].rank(method="first", ascending=False).astype(int)
        work["keep_from_prev"] = False
        return work[work["rank"] <= top_n].copy()
    
    work = new_ranks.copy()
    work["rank"] = work["final_score"].rank(method="first", ascending=False).astype(int)
    
    # Get previous tickers
    prev_tickers = set(prev_portfolio["ticker"].astype(str).tolist())
    
    # Mark which stocks are from previous portfolio
    work["ticker_str"] = work["ticker"].astype(str)
    work["is_prev_holding"] = work["ticker_str"].isin(prev_tickers)
    
    # Keep prev holdings if they're still in top keep_threshold
    keep_mask = (work["is_prev_holding"]) & (work["rank"] <= keep_threshold)
    work["keep_from_prev"] = keep_mask
    
    # Calculate how many we're keeping
    n_keep = int(keep_mask.sum())
    n_new_slots = max(0, top_n - n_keep)
    
    # Get non-kept stocks ranked by current score
    non_kept = work[~work["keep_from_prev"]].copy()
    non_kept = non_kept.sort_values("final_score", ascending=False)
    
    # Take top n_new_slots from non-kept
    new_picks = non_kept.head(n_new_slots).copy()
    new_picks["keep_from_prev"] = False
    
    # Get kept stocks
    kept = work[work["keep_from_prev"]].copy()
    
    # Combine
    result = pd.concat([kept, new_picks], ignore_index=True)
    result = result.sort_values("final_score", ascending=False).reset_index(drop=True)
    
    # Verify turnover constraint
    n_prev_in_result = int(result["is_prev_holding"].sum())
    n_turnover = top_n - n_prev_in_result
    max_allowed_turnover = int(top_n * max_turnover)
    
    # If we exceeded turnover limit, force more holds
    if n_turnover > max_allowed_turnover:
        # Need to keep more from prev
        extra_holds_needed = n_turnover - max_allowed_turnover
        
        # Find prev holdings that we didn't keep but are in top keep_threshold + buffer
        prev_not_kept = work[(work["is_prev_holding"]) & (~work["keep_from_prev"])]
        prev_not_kept = prev_not_kept.sort_values("rank").head(extra_holds_needed)
        
        # Remove lowest ranked new picks
        result = result.drop(prev_not_kept.index[:0], errors="ignore")
        
        # Add the extra holds
        if len(prev_not_kept) > 0:
            result = pd.concat([result, prev_not_kept], ignore_index=True)
            result = result.sort_values("final_score", ascending=False).reset_index(drop=True)
            result = result.head(top_n)
    
    return result


class DailyScorer:
    """
    Morning scoring pipeline. Run once per day before market open.

    Steps:
    1. Load latest data for all stocks
    2. Get today's regime from RegimeEngine
    3. Load appropriate regime model from RegimeConditionalTrainer
    4. Score all stocks
    5. Apply sentiment overlay
    6. Apply macro sector tilts
    7. Output ranked list with position sizes
    """

    def __init__(self, config: dict | None = None):
        self.config = dict(config or {})
        self.project_root = Path(str(self.config.get("project_root", "."))).resolve()

        regime_cfg = dict(self.config.get("regime", {}) or {})
        trainer_cfg = dict(self.config.get("trainer", {}) or {})
        overlay_cfg = dict(self.config.get("sentiment_overlay", {}) or {})

        self.regime_engine = RegimeEngine(regime_cfg)
        self.trainer = RegimeConditionalTrainer(config=trainer_cfg)
        self.overlay = SentimentOverlay(overlay_cfg)

        self._last_info: dict[str, Any] = {}
        self._reference_universe_cache: pd.DataFrame | None = None

    @staticmethod
    def _normalize_date(value: object) -> pd.Timestamp:
        if str(value).strip().lower() == "today":
            return pd.Timestamp.today().normalize()
        return pd.to_datetime(value, errors="coerce").normalize()

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        text = str(value or "").strip().upper()
        if not text or text in {"NAN", "NONE"}:
            return ""
        if "." not in text:
            return f"{text}.NS"
        return text

    @staticmethod
    def _apply_cross_sectional_prediction_transform(
        scores: pd.Series | np.ndarray | list[float],
        *,
        mode: str = "zscore",
        rank_power: float = 1.5,
        tanh_scale: float = 3.0,
    ) -> pd.Series:
        """
        Normalize one inference cross-section before overlays/allocator.

        Regime-specific models are trained for cross-sectional ranking, so their
        raw output distribution can drift by regime and make an absolute zero
        threshold meaningless at inference time.
        """
        s = pd.to_numeric(pd.Series(scores), errors="coerce").fillna(0.0)
        if s.empty:
            return pd.Series(dtype=float)

        m = str(mode or "raw").strip().lower()
        if m in {"", "raw", "none"}:
            return s.astype(float)

        if len(s) <= 1:
            return pd.Series(0.0, index=s.index, dtype=float)

        def _zscore(series: pd.Series) -> pd.Series:
            mu = float(series.mean())
            sigma = float(series.std(ddof=0))
            if not np.isfinite(sigma) or sigma < 1e-12:
                return pd.Series(0.0, index=series.index, dtype=float)
            return ((series - mu) / sigma).astype(float)

        if m == "zscore":
            return _zscore(s)

        if m == "rank":
            ranks = s.rank(method="average", pct=True)
            return (ranks.fillna(0.5) - 0.5).astype(float)

        if m == "rank_power":
            ranks = s.rank(method="average", pct=True)
            centered = (ranks.fillna(0.5) - 0.5).astype(float)
            power = float(max(1.0, rank_power))
            return (np.sign(centered) * np.power(np.abs(centered), power)).astype(float)

        if m == "tanh":
            z = _zscore(s)
            scale = float(max(0.1, tanh_scale))
            return pd.Series(np.tanh(scale * z.to_numpy(dtype=float)), index=s.index, dtype=float)

        raise ValueError(f"daily_scorer_unknown_prediction_transform:{m}")

    def _prediction_transform_settings(self) -> tuple[str, float, float]:
        mode = str(
            self.config.get("prediction_transform")
            or self.config.get("inference_prediction_transform")
            or ""
        ).strip().lower()
        if not mode:
            target_type = str(
                self.config.get("target_type")
                or self.config.get("training_target_type")
                or "cross_sectional_rank"
            ).strip().lower()
            mode = "zscore" if target_type in {"cross_sectional_rank", "rank", "cross_sectional"} else "zscore"
        rank_power = float(self.config.get("prediction_rank_power", 1.5) or 1.5)
        tanh_scale = float(self.config.get("prediction_tanh_scale", 3.0) or 3.0)
        return mode, rank_power, tanh_scale

    def transform_model_scores(
        self,
        scores: pd.Series | np.ndarray | list[float],
    ) -> pd.Series:
        mode, rank_power, tanh_scale = self._prediction_transform_settings()
        return self._apply_cross_sectional_prediction_transform(
            scores,
            mode=mode,
            rank_power=rank_power,
            tanh_scale=tanh_scale,
        )

    def _load_reference_universe(self) -> pd.DataFrame:
        cached = self._reference_universe_cache
        if isinstance(cached, pd.DataFrame):
            return cached.copy()

        candidates = [
            self.project_root / "universe" / "nifty500.csv",
            self.project_root / "data" / "processed" / "universe" / "nifty500.csv",
            self.project_root / "data" / "universe" / "nifty500.csv",
        ]
        out = pd.DataFrame(columns=["ticker", "Company Name", "Industry"])
        for path in candidates:
            if not path.exists():
                continue
            try:
                uni = pd.read_csv(path)
            except Exception:
                logger.exception("Failed loading reference universe: %s", path)
                continue

            ticker_col = next((c for c in ["Symbol", "ticker", "Ticker", "symbol"] if c in uni.columns), None)
            if ticker_col is None:
                continue

            name_col = next(
                (c for c in ["Company Name", "company_name", "Security Name", "name"] if c in uni.columns),
                None,
            )
            industry_col = next(
                (c for c in ["Industry", "industry", "Sector", "sector", "Industry Name"] if c in uni.columns),
                None,
            )

            ref = pd.DataFrame({"ticker": uni[ticker_col].map(self._normalize_ticker)})
            ref["Company Name"] = (
                uni[name_col].fillna("").astype(str)
                if name_col is not None
                else ref["ticker"].astype(str)
            )
            ref["Industry"] = (
                uni[industry_col].fillna("Unknown").astype(str)
                if industry_col is not None
                else "Unknown"
            )
            ref = ref[ref["ticker"].ne("")].drop_duplicates("ticker", keep="last").reset_index(drop=True)
            out = ref
            break

        self._reference_universe_cache = out.copy()
        return out

    def _enrich_reference_metadata(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or "ticker" not in frame.columns:
            return frame

        work = frame.copy()
        work["ticker"] = work["ticker"].map(self._normalize_ticker)
        ref = self._load_reference_universe()
        if ref.empty:
            return work

        work = work.merge(ref, on="ticker", how="left", suffixes=("", "_ref"))
        if "Company Name" not in work.columns:
            work["Company Name"] = ""
        if "Company Name_ref" in work.columns:
            base_name = work["Company Name"].fillna("").astype(str).str.strip()
            ref_name = work["Company Name_ref"].fillna("").astype(str).str.strip()
            work["Company Name"] = base_name.where(base_name.ne(""), ref_name)

        if "Industry" not in work.columns:
            work["Industry"] = "Unknown"
        if "Industry_ref" in work.columns:
            base_industry = work["Industry"].fillna("").astype(str).str.strip()
            ref_industry = work["Industry_ref"].fillna("Unknown").astype(str).str.strip()
            missing_industry = base_industry.eq("") | base_industry.eq("Unknown") | base_industry.eq("nan")
            work["Industry"] = base_industry.where(~missing_industry, ref_industry)

        if "sector" not in work.columns and "Industry" in work.columns:
            work["sector"] = work["Industry"].fillna("Unknown").astype(str)
        elif "sector" in work.columns:
            sector = work["sector"].fillna("").astype(str).str.strip()
            industry = work["Industry"].fillna("Unknown").astype(str).str.strip()
            work["sector"] = sector.where(sector.ne(""), industry)

        return work.drop(columns=["Company Name_ref", "Industry_ref"], errors="ignore")

    def _select_latest_snapshot(self, frame: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
        if frame.empty:
            return frame

        work = frame.copy()
        work["ticker"] = work["ticker"].map(self._normalize_ticker)
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
        work = work.dropna(subset=["ticker", "date"])
        work = work[work["ticker"].ne("")]
        work = work[work["date"] <= as_of_date].copy()
        if work.empty:
            return work

        work = work.sort_values(["ticker", "date"], kind="mergesort")
        snapshot = work.groupby("ticker", sort=False).tail(1).copy()

        max_staleness_days = int(self.config.get("max_snapshot_staleness_days", 14) or 14)
        staleness = (pd.Timestamp(as_of_date).normalize() - snapshot["date"]).dt.days
        valid_mask = staleness.between(0, max_staleness_days)
        dropped = int((~valid_mask).sum())
        if dropped > 0:
            logger.warning(
                "[daily-scorer] dropping %d stale tickers from live snapshot (max_staleness_days=%d)",
                dropped,
                max_staleness_days,
            )
        kept = snapshot.loc[valid_mask].copy()
        logger.info(
            "[daily-scorer] live snapshot tickers=%d as_of=%s max_source_date=%s median_staleness_days=%.1f",
            int(kept["ticker"].nunique()),
            pd.Timestamp(as_of_date).date(),
            kept["date"].max().date() if not kept.empty else None,
            float(staleness.loc[valid_mask].median()) if bool(valid_mask.any()) else float("nan"),
        )
        return kept.reset_index(drop=True)

    @staticmethod
    def _live_feature_columns(frame: pd.DataFrame) -> list[str]:
        exclude = {
            "date",
            "ticker",
            "regime",
            "macro_regime",
            "regime_name",
            "valuation_regime",
            "volume",
        }
        leakage_prefixes = ("forward_return_", "target_")
        return [
            str(c)
            for c in frame.columns
            if c not in exclude
            and pd.api.types.is_numeric_dtype(frame[c])
            and not str(c).endswith("__realized")
            and not str(c).startswith(leakage_prefixes)
        ]

    def _normalize_live_features(
        self,
        frame: pd.DataFrame,
        dm: DatasetManager,
    ) -> tuple[pd.DataFrame, list[str]]:
        if frame.empty:
            return frame, []
        feature_cols = self._live_feature_columns(frame)
        if not feature_cols:
            return frame, []
        X_df = frame[feature_cols].replace([np.inf, -np.inf], np.nan)
        X_df = dm._apply_feature_cross_sectional_normalization(X_df, frame["date"])
        X_df = X_df.replace([np.inf, -np.inf], np.nan)
        out = frame.copy()
        for col in feature_cols:
            out[col] = pd.to_numeric(X_df[col], errors="coerce").astype(float)
        return out, feature_cols

    @staticmethod
    def _feature_family(feature_name: str) -> str | None:
        name = str(feature_name or "")
        if not name:
            return None
        if name.startswith("screener_"):
            return "screener"
        if name.startswith(("bulk_", "pledge_", "rating_", "order_")) or name in {
            "recent_upgrade_flag",
            "recent_downgrade_flag",
            "watch_negative_flag",
            "investment_grade_flag",
        }:
            return "alternative"
        if name.startswith(("sent_", "mkt_sent_", "sentiment_")):
            return "sentiment"
        if name.startswith("macro_") or name in {
            "power_yoy_growth",
            "gst_yoy_growth",
            "india_market_polarity",
            "india_market_uncertainty",
            "sector_gst_yoy",
            "sector_activity_zscore",
        }:
            return "macro"
        return None

    def _live_feature_family_usage(self, regime: str | None) -> dict[str, bool]:
        families = {
            "screener": False,
            "alternative": False,
            "sentiment": False,
            "macro": False,
        }
        regime_key = str(regime or "").strip()
        records: list[dict[str, Any]] = []

        if regime_key:
            rec = self.trainer._resolve_model_record(regime_key)
            if isinstance(rec, dict) and rec:
                records.append(rec)

        if not records:
            registry = self.trainer._load_registry()
            models = registry.get("models", {}) if isinstance(registry, dict) else {}
            if isinstance(models, dict):
                records.extend(v for v in models.values() if isinstance(v, dict))

        for rec in records:
            for feat in list(rec.get("feature_cols", []) or []):
                family = self._feature_family(str(feat))
                if family is not None:
                    families[family] = True

        return families

    def _live_expensive_feature_usage(self, regime: str | None) -> dict[str, bool]:
        usage = {
            "valuation": False,
            "academic_factors": False,
        }
        regime_key = str(regime or "").strip()
        records: list[dict[str, Any]] = []

        if regime_key:
            rec = self.trainer._resolve_model_record(regime_key)
            if isinstance(rec, dict) and rec:
                records.append(rec)

        if not records:
            registry = self.trainer._load_registry()
            models = registry.get("models", {}) if isinstance(registry, dict) else {}
            if isinstance(models, dict):
                records.extend(v for v in models.values() if isinstance(v, dict))

        academic_prefixes = (
            "bab_",
            "amihud",
            "max_lottery",
            "piotroski",
            "earnings_quality",
        )
        for rec in records:
            for feat in list(rec.get("feature_cols", []) or []):
                name = str(feat or "")
                if not name:
                    continue
                if name.startswith("val_"):
                    usage["valuation"] = True
                if name.startswith(academic_prefixes):
                    usage["academic_factors"] = True
        return usage

    def _optimize_live_dataset_config(
        self,
        dataset_cfg: dict[str, Any],
        *,
        regime: str | None,
    ) -> dict[str, Any]:
        cfg = dict(dataset_cfg or {})
        if not bool(cfg.get("live_snapshot_only_model_families", True)):
            return cfg

        family_usage = self._live_feature_family_usage(regime)
        if not family_usage.get("screener", False):
            cfg["use_screener_features"] = False
        if not family_usage.get("alternative", False):
            cfg["use_alternative_features"] = False
        if not family_usage.get("sentiment", True):
            cfg["use_sentiment_features"] = False
        if not family_usage.get("macro", True):
            cfg["use_macro_features"] = False
        return cfg

    def _build_live_feature_panel(
        self,
        dm: DatasetManager,
        *,
        as_of_date: pd.Timestamp,
    ) -> pd.DataFrame:
        prices = dm.load_prices()
        fundamentals = dm.load_fundamentals()
        screener_annual = dm.load_screener_extended_annual() if bool(dm.use_screener_features) else pd.DataFrame()
        screener_quarterly = dm.load_screener_extended_quarterly() if bool(dm.use_screener_features) else pd.DataFrame()
        screener_shareholding = (
            dm.load_screener_extended_shareholding() if bool(dm.use_screener_features) else pd.DataFrame()
        )
        macro_enabled = bool(dm.config.get("enable_macro_features", True))
        macro = dm.load_macro() if macro_enabled else pd.DataFrame()
        valuation = dm.load_valuation_posterior()
        sentiment_company = dm.load_sentiment_company()
        sentiment_market = dm.load_sentiment_market()
        sentiment_features_df = dm.load_sentiment_features() if bool(dm.config.get("use_sentiment_features", False)) else pd.DataFrame()
        et500_membership = (
            dm._load_et500_membership()
            if bool(dm.use_et500_features or dm.use_et500_universe_filter)
            else pd.DataFrame()
        )
        sector_lookup = dm._load_sector_lookup()
        fundamentals = dm._apply_sector_lookup_to_frame(fundamentals, sector_lookup)

        lookback_days = int(dm.config.get("lookback_days", 420) or 420)
        cfg_start = dm._config_date("start_date")
        cfg_end = dm._config_date("end_date")

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
                    cutoff = p["__date"].max() - pd.Timedelta(days=lookback_days + 180)
                    p = p.loc[p["__date"] >= cutoff].copy()
                prices = p.drop(columns=["__date"], errors="ignore")

        factory = dm.factory
        original_use_valuation = bool(getattr(factory, "use_valuation_features", False))
        original_use_academic_factors = bool(getattr(factory, "use_academic_factors", False))
        if original_use_valuation or original_use_academic_factors:
            logger.info(
                "[daily-scorer] live snapshot optimization enabled "
                "(historical valuation=%s academic_factors=%s computed latest-only)",
                original_use_valuation,
                original_use_academic_factors,
            )
        factory.use_valuation_features = False
        factory.use_academic_factors = False
        try:
            panel = factory.build_features(
                prices=prices,
                fundamentals=fundamentals,
                screener_annual=screener_annual if bool(dm.use_screener_features) else None,
                screener_quarterly=screener_quarterly if bool(dm.use_screener_features) else None,
                screener_shareholding=screener_shareholding if bool(dm.use_screener_features) else None,
                macro=macro,
                valuation_posterior=valuation,
                sentiment_company=sentiment_company,
                sentiment_market=sentiment_market,
                sector_lookup=sector_lookup,
                et500_membership=et500_membership if bool(dm.use_et500_features) else None,
            )
        finally:
            factory.use_valuation_features = original_use_valuation
            factory.use_academic_factors = original_use_academic_factors

        if not sentiment_features_df.empty:
            panel = panel.merge(sentiment_features_df, on=["date", "ticker"], how="left")

        if bool(dm.use_et500_universe_filter):
            panel = dm._apply_et500_universe_filter(panel, et500_membership)

        panel = dm._apply_liquidity_filter(panel, prices)
        delist_df = dm._load_delisting_database()
        if not delist_df.empty:
            panel = dm._apply_delisting_adjustments(panel, delist_df)
        panel = dm._add_sector_dummies(panel)

        if panel.empty:
            return panel

        if lookback_days > 0:
            cutoff = panel["date"].max() - pd.Timedelta(days=lookback_days)
            panel = panel.loc[panel["date"] >= cutoff].copy()
        if cfg_start is not None:
            panel = panel.loc[panel["date"] >= cfg_start].copy()
        if cfg_end is not None:
            panel = panel.loc[panel["date"] <= cfg_end].copy()

        panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)
        panel, regime_from_engine = dm._assign_regime_labels_with_engine(panel, prices)
        if not regime_from_engine:
            if "macro_regime" in panel.columns:
                regime_source = panel["macro_regime"]
            elif "regime" in panel.columns:
                regime_source = panel["regime"]
            else:
                regime_source = pd.Series("unknown", index=panel.index, dtype="object")
            panel["regime"] = regime_source.astype(str)
        panel["regime_code"] = panel["regime"].astype("category").cat.codes.astype(float)
        panel, _ = dm._apply_regime_signal_weights(panel)
        return panel

    def _add_latest_only_live_features(
        self,
        frame: pd.DataFrame,
        dm: DatasetManager,
        *,
        as_of_date: pd.Timestamp,
        include_valuation: bool = True,
        include_academic_factors: bool = True,
    ) -> pd.DataFrame:
        """
        Add expensive feature families only to the final live snapshot.

        Live scoring needs one latest cross-section, not a full historical panel
        with valuation/factor recomputation for every date in the lookback window.
        """
        if frame.empty:
            return frame

        out = frame.copy()
        factory = dm.factory
        latest_dt = pd.Timestamp(as_of_date).to_pydatetime()

        try:
            if include_academic_factors and bool(getattr(factory, "use_academic_factors", False)):
                out = factory._add_academic_factor_features(out, latest_dt)
            if include_valuation and bool(getattr(factory, "use_valuation_features", False)):
                out = factory._add_valuation_features(out, latest_dt)
        except Exception:
            logger.exception("[daily-scorer] failed adding latest-only valuation/factor features")
            return frame

        return factory._ensure_primary_ticker_column(out)

    def _load_latest_universe_frame(
        self,
        as_of_date: pd.Timestamp,
        *,
        regime: str | None = None,
    ) -> tuple[pd.DataFrame, list[str]]:
        # Testing / synthetic hook.
        custom_loader = self.config.get("data_loader")
        if callable(custom_loader):
            out = custom_loader(as_of_date)
            if isinstance(out, tuple) and len(out) == 2:
                frame = out[0].copy() if isinstance(out[0], pd.DataFrame) else pd.DataFrame()
                feats = [str(c) for c in list(out[1] or [])]
                return frame, feats
            if isinstance(out, pd.DataFrame):
                frame = out.copy()
                feats = [
                    c
                    for c in frame.columns
                    if c
                    not in {
                        "ticker",
                        "date",
                        "regime",
                        "sector",
                        "model_score",
                        "sentiment_multiplier",
                        "final_score",
                        "suggested_weight",
                        "quintile",
                    }
                    and pd.api.types.is_numeric_dtype(frame[c])
                ]
                return frame, [str(c) for c in feats]

        dataset_cfg = dict(self.config.get("dataset", {}) or {})
        dataset_cfg.setdefault("strict_real_data_only", False)
        dataset_cfg.setdefault("end_date", str(as_of_date.date()))
        dataset_cfg.setdefault("enable_macro_features", True)
        dataset_cfg.setdefault("use_screener_features", True)
        dataset_cfg.setdefault("use_alternative_features", True)
        dataset_cfg.setdefault("use_sentiment_features", True)
        # Live scoring should build the widest current snapshot we can support,
        # not inherit training-time truncation and liquidity gates.
        live_snapshot_mode = bool(dataset_cfg.get("live_snapshot_mode", True))
        if live_snapshot_mode:
            dataset_cfg["strict_real_data_only"] = False
            dataset_cfg["low_resource_mode"] = "off"
            dataset_cfg["lookback_days"] = int(dataset_cfg.get("live_snapshot_lookback_days", 120) or 120)
            dataset_cfg["max_tickers"] = int(dataset_cfg.get("live_snapshot_max_tickers", 0) or 0)
            dataset_cfg["max_rows"] = int(dataset_cfg.get("live_snapshot_max_rows", 0) or 0)
            dataset_cfg["min_history_days"] = int(dataset_cfg.get("live_snapshot_min_history_days", 0) or 0)
            dataset_cfg["liquidity_threshold_cr"] = float(
                dataset_cfg.get("live_snapshot_liquidity_threshold_cr", 0.0) or 0.0
            )
            dataset_cfg["min_tickers_per_date"] = int(dataset_cfg.get("live_snapshot_min_tickers_per_date", 1) or 1)
            dataset_cfg["drop_unlabeled_target_rows"] = bool(
                dataset_cfg.get("live_snapshot_drop_unlabeled_target_rows", False)
            )
            dataset_cfg["write_snapshot"] = bool(dataset_cfg.get("live_snapshot_write_snapshot", False))
            dataset_cfg = self._optimize_live_dataset_config(dataset_cfg, regime=regime)

        dm = DatasetManager(project_root=self.project_root, config=dataset_cfg)

        if live_snapshot_mode:
            frame = self._build_live_feature_panel(dm, as_of_date=as_of_date)
            if frame.empty:
                return frame, []
            frame = self._select_latest_snapshot(frame, as_of_date)
            if frame.empty:
                return frame, []
            expensive_usage = self._live_expensive_feature_usage(regime)
            if expensive_usage["valuation"] or expensive_usage["academic_factors"]:
                frame = self._add_latest_only_live_features(
                    frame,
                    dm,
                    as_of_date=as_of_date,
                    include_valuation=expensive_usage["valuation"],
                    include_academic_factors=expensive_usage["academic_factors"],
                )
            frame, feature_cols = self._normalize_live_features(frame, dm)
            frame = self._enrich_reference_metadata(frame)
            return frame.reset_index(drop=True), feature_cols

        ds = dm.build_research_dataset()
        frame = ds.frame.copy()
        if frame.empty:
            return frame, []

        frame = self._select_latest_snapshot(frame, as_of_date)
        if frame.empty:
            return frame, list(ds.feature_names)
        frame, feature_cols = self._normalize_live_features(frame, dm)
        frame = self._enrich_reference_metadata(frame)

        feature_cols = [str(c) for c in list(feature_cols or []) if str(c) in frame.columns]
        if not feature_cols:
            feature_cols = [str(c) for c in list(ds.feature_names or []) if str(c) in frame.columns]
        return frame.reset_index(drop=True), feature_cols

    @staticmethod
    def _assign_quintiles(scores: pd.Series) -> pd.Series:
        s = pd.to_numeric(scores, errors="coerce").fillna(0.0)
        if len(s) < 5:
            return pd.Series(np.ones(len(s), dtype=int), index=s.index)
        rank = s.rank(method="first", pct=True)
        q = np.ceil(rank * 5.0).clip(1, 5)
        return q.astype(int)

    def _load_prev_portfolio(self) -> pd.DataFrame | None:
        """Load previous week's portfolio from cache."""
        if not _TURNOVER_CACHE_PATH.exists():
            return None
        try:
            with _TURNOVER_CACHE_PATH.open("rb") as f:
                return pickle.load(f)
        except Exception:
            logger.exception("Failed to load previous portfolio cache: %s", _TURNOVER_CACHE_PATH)
            raise
    
    def _save_prev_portfolio(self, portfolio: pd.DataFrame) -> None:
        """Save current portfolio for next week's turnover constraint."""
        _TURNOVER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _TURNOVER_CACHE_PATH.open("wb") as f:
            pickle.dump(portfolio, f)

    def _warn_if_unified_state_stale(self) -> None:
        state_cfg = dict(self.config.get("state", {}) or {})
        snapshot_path = Path(
            state_cfg.get(
                "snapshot_path",
                self.project_root / "data" / "state" / "unified_state.json",
            )
        )
        if not snapshot_path.exists():
            return

        try:
            from src.core.state import MAX_STATE_AGE_HOURS, UnifiedState

            max_age_hours = float(state_cfg.get("max_age_hours", MAX_STATE_AGE_HOURS) or MAX_STATE_AGE_HOURS)
            unified_state = UnifiedState.load_snapshot_file(snapshot_path, max_age_hours=max_age_hours)
        except Exception:
            logger.exception("[daily-scorer] failed to inspect unified state freshness: %s", snapshot_path)
            return

        if getattr(unified_state, "_state_is_stale", False):
            age_hours = getattr(unified_state, "_state_age_hours", None)
            logger.warning(
                "[daily-scorer] unified state is stale (age_hours=%s threshold=%.1f). "
                "Continuing, but intraday context may be outdated.",
                f"{float(age_hours):.1f}" if isinstance(age_hours, (int, float)) else "unknown",
                max_age_hours,
            )

    def _model_registry_dir(self) -> Path:
        configured = self.config.get("alpha_os_registry_path") or self.config.get("model_registry_path")
        if configured:
            return Path(str(configured))
        return self.project_root / "data" / "model_registry"

    def _load_production_model_path(self) -> str | None:
        production_path = self._model_registry_dir() / "production.json"
        if not production_path.exists():
            return None
        try:
            payload = json.loads(production_path.read_text())
        except Exception:
            logger.exception("[daily-scorer] failed reading production model pointer: %s", production_path)
            return None
        model_path = payload.get("model_path") if isinstance(payload, dict) else None
        return str(model_path) if model_path else None

    def _resolve_alpha_os_model_path(self) -> str | None:
        try:
            from src.alpha_os.strategy_registry import StrategyRegistry

            registry = StrategyRegistry({"alpha_os_registry_path": str(self._model_registry_dir())})
            alpha_os_model_path = registry.get_active_model_path()
        except Exception:
            logger.exception("[daily-scorer] failed loading Alpha OS strategy registry")
            alpha_os_model_path = None

        if alpha_os_model_path and Path(alpha_os_model_path).exists():
            logger.info("[daily-scorer] using Alpha OS ACTIVE model: %s", alpha_os_model_path)
            return alpha_os_model_path

        fallback_model_path = self._load_production_model_path()
        if fallback_model_path:
            logger.warning(
                "[daily-scorer] Alpha OS model path not available (%s). Falling back to production.json: %s",
                alpha_os_model_path,
                fallback_model_path,
            )
            return fallback_model_path
        return None

    def _predict_with_model_path(
        self,
        frame: pd.DataFrame,
        *,
        regime: str,
        model_path: str,
    ) -> np.ndarray:
        payload = pickle.loads(Path(model_path).read_bytes())
        model = payload.get("model")
        feature_cols = [str(col) for col in list(payload.get("feature_cols", []))]
        if model is None or not feature_cols:
            raise ValueError(f"daily_scorer_invalid_model_payload:{model_path}")

        X = frame.reindex(columns=feature_cols, fill_value=0.0).replace([np.inf, -np.inf], np.nan)
        X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
        preds = np.asarray(model.predict(X.to_numpy(dtype=float)), dtype=float).reshape(-1)
        self.trainer._last_prediction_meta = {
            "requested_regime": str(regime),
            "resolved_regime": str(payload.get("regime", regime)),
            "trained_on_regime": str(payload.get("regime", regime)),
            "model_path": str(model_path),
            "train_ic": None,
            "oos_ic": None,
            "backend": str(payload.get("backend", "alpha_os_override")),
            "source": "alpha_os_active_model",
        }
        return preds

    def _build_weights(
        self,
        frame: pd.DataFrame,
        *,
        exposure_scale: float,
        mandate: str,
        apply_turnover: bool = True,
    ) -> pd.Series:
        # Get max_weekly_turnover from config
        max_turnover = float(self.config.get("max_weekly_turnover", 0.30) or 0.30)
        top_n = 20  # Target portfolio size
        
        # Apply turnover constraint if enabled and we have previous portfolio
        if apply_turnover:
            prev_portfolio = self._load_prev_portfolio()
            constrained = apply_turnover_constraint(
                new_ranks=frame,
                prev_portfolio=prev_portfolio,
                max_turnover=max_turnover,
                top_n=top_n,
                keep_threshold=35,
            )
            # Mark which positions are kept from prev
            frame = frame.copy()
            frame["keep_from_prev"] = False
            if "keep_from_prev" in constrained.columns:
                for idx in constrained.index:
                    if idx in frame.index:
                        frame.loc[idx, "keep_from_prev"] = constrained.loc[idx, "keep_from_prev"]
        
        q = frame["quintile"].astype(int)
        w = pd.Series(0.0, index=frame.index, dtype=float)

        mode = str(mandate or "long_only").strip().lower()
        if mode not in {"long_only", "long_short"}:
            mode = "long_only"

        top = q.eq(5)
        bottom = q.eq(1)

        if mode == "long_only":
            n_top = int(top.sum())
            if n_top > 0:
                w.loc[top] = float(exposure_scale) / float(n_top)
            return w

        n_top = int(top.sum())
        n_bot = int(bottom.sum())
        if n_top > 0:
            w.loc[top] = 0.5 * float(exposure_scale) / float(n_top)
        if n_bot > 0:
            w.loc[bottom] = -0.5 * float(exposure_scale) / float(n_bot)
        return w

    def score(self, as_of_date):
        """
        Returns DataFrame:
        ticker | model_score | regime | sentiment_multiplier |
        final_score | suggested_weight | quintile
        """
        dt = self._normalize_date(as_of_date)
        if pd.isna(dt):
            raise ValueError("daily_scorer_invalid_date")

        self._warn_if_unified_state_stale()

        regime = self.regime_engine.get_regime_as_of(dt)
        exposure_scale = float(self.regime_engine.get_exposure_scale(regime))
        frame, feature_cols = self._load_latest_universe_frame(dt, regime=regime)
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "ticker",
                    "model_score",
                    "regime",
                    "sentiment_multiplier",
                    "final_score",
                    "suggested_weight",
                    "quintile",
                ]
            )

        if "ticker" not in frame.columns:
            frame["ticker"] = [f"asset_{i}" for i in range(len(frame))]

        use_feats = [c for c in feature_cols if c in frame.columns]
        if not use_feats:
            use_feats = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
        preds = np.asarray([], dtype=float)
        alpha_os_model_path = self._resolve_alpha_os_model_path()
        if alpha_os_model_path:
            try:
                preds = self._predict_with_model_path(frame[use_feats], regime=str(regime), model_path=alpha_os_model_path)
            except Exception as exc:
                logger.warning(
                    "[daily-scorer] failed using Alpha OS ACTIVE model (%s): %s. Falling back to regime trainer.",
                    alpha_os_model_path,
                    exc,
                )
                preds = np.asarray([], dtype=float)
        if len(preds) == 0:
            preds = self.trainer.predict(frame[use_feats], regime=regime)
        if len(preds) != len(frame):
            preds = np.resize(preds, len(frame)) if len(preds) > 0 else np.zeros(len(frame), dtype=float)

        raw_scores = pd.to_numeric(pd.Series(preds), errors="coerce").fillna(0.0)
        model_scores = self.transform_model_scores(raw_scores)
        mode, _, _ = self._prediction_transform_settings()

        out = pd.DataFrame(
            {
                "ticker": frame["ticker"].astype(str).to_numpy(),
                "raw_model_score": raw_scores.to_numpy(dtype=float),
                "model_score": model_scores.to_numpy(dtype=float),
                "regime": str(regime),
            }
        )

        if "Company Name" in frame.columns:
            out["Company Name"] = frame["Company Name"].fillna("").astype(str).to_numpy()
        if "Industry" in frame.columns:
            out["Industry"] = frame["Industry"].fillna("Unknown").astype(str).to_numpy()

        if "sector" in frame.columns:
            out["sector"] = frame["sector"].astype(str).to_numpy()
        else:
            sec_col = next((c for c in ["sector_name", "Industry", "industry", "Sector"] if c in frame.columns), None)
            if sec_col is not None:
                out["sector"] = frame[sec_col].astype(str).to_numpy()

        sent = self.overlay.apply(out[["ticker", "model_score"]], as_of_date=dt)
        out = out.merge(
            sent[
                [
                    "ticker",
                    "sentiment_multiplier",
                    "sentiment_override",
                    "override_reason",
                    "sentiment_polarity",
                    "sentiment_conviction",
                    "news_volume",
                ]
            ],
            on="ticker",
            how="left",
        )
        out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce").fillna(1.0)
        out["base_sentiment_multiplier"] = pd.to_numeric(
            out.get("base_sentiment_multiplier", out["sentiment_multiplier"]),
            errors="coerce",
        ).fillna(1.0)
        if "macro_multiplier" in out.columns:
            out["macro_multiplier"] = pd.to_numeric(out["macro_multiplier"], errors="coerce").fillna(1.0)
        else:
            out["macro_multiplier"] = 1.0
        out["sentiment_override"] = out.get("sentiment_override", False).fillna(False).astype(bool)
        out["sentiment_polarity"] = pd.to_numeric(out.get("sentiment_polarity"), errors="coerce")
        out["sentiment_conviction"] = pd.to_numeric(out.get("sentiment_conviction"), errors="coerce")
        out["news_volume"] = pd.to_numeric(out.get("news_volume"), errors="coerce").fillna(0.0)

        if "sector" in out.columns:
            out = self.overlay.apply_macro_overlay(out, as_of_date=dt)
            out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce").fillna(1.0)

        out["final_score"] = (
            pd.to_numeric(out["model_score"], errors="coerce").fillna(0.0)
            * pd.to_numeric(out["sentiment_multiplier"], errors="coerce").fillna(1.0)
            * float(exposure_scale)
        )

        out["quintile"] = self._assign_quintiles(out["final_score"])
        mandate = str(self.config.get("portfolio_mandate", "long_only") or "long_only").strip().lower()
        out["suggested_weight"] = self._build_weights(out, exposure_scale=exposure_scale, mandate=mandate)

        # Save current portfolio for next week's turnover constraint
        top_portfolio = out[out["suggested_weight"] > 0][["ticker", "final_score", "suggested_weight"]].copy()
        if not top_portfolio.empty:
            self._save_prev_portfolio(top_portfolio)

        self._last_info = {
            "as_of_date": str(dt.date()),
            "regime": str(regime),
            "exposure_scale": float(exposure_scale),
            "mandate": str(mandate),
            "prediction_transform": mode,
            "model_meta": self.trainer.get_last_prediction_meta(),
        }

        cols = [
            "ticker",
            "raw_model_score",
            "model_score",
            "regime",
            "sentiment_multiplier",
            "base_sentiment_multiplier",
            "macro_multiplier",
            "sentiment_polarity",
            "sentiment_conviction",
            "news_volume",
            "final_score",
            "suggested_weight",
            "quintile",
        ]
        extra = [c for c in ["sector", "sentiment_override", "override_reason"] if c in out.columns]
        extra += [c for c in ["Company Name", "Industry"] if c in out.columns]
        out = out[cols + extra].copy()
        out = out.sort_values("final_score", ascending=False, kind="mergesort").reset_index(drop=True)
        return out

    def get_last_info(self) -> dict[str, Any]:
        return dict(self._last_info)
