"""Daily regime-aware stock scoring pipeline for Northstar v3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.research.dataset_manager import DatasetManager
from src.research.regime_conditional_trainer import RegimeConditionalTrainer
from src.research.regime_engine import RegimeEngine
from src.signals.sentiment_overlay import SentimentOverlay


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
        self.project_root = Path(str(self.config.get("project_root", ".")))

        regime_cfg = dict(self.config.get("regime", {}) or {})
        trainer_cfg = dict(self.config.get("trainer", {}) or {})
        overlay_cfg = dict(self.config.get("sentiment_overlay", {}) or {})

        self.regime_engine = RegimeEngine(regime_cfg)
        self.trainer = RegimeConditionalTrainer(config=trainer_cfg)
        self.overlay = SentimentOverlay(overlay_cfg)

        self._last_info: dict[str, Any] = {}

    @staticmethod
    def _normalize_date(value: object) -> pd.Timestamp:
        if str(value).strip().lower() == "today":
            return pd.Timestamp.today().normalize()
        return pd.to_datetime(value, errors="coerce").normalize()

    def _load_latest_universe_frame(self, as_of_date: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
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

        dm = DatasetManager(project_root=self.project_root, config=dataset_cfg)
        ds = dm.build_research_dataset()
        frame = ds.frame.copy()
        if frame.empty:
            return frame, []

        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame[frame["date"] <= as_of_date].copy()
        if frame.empty:
            return frame, list(ds.feature_names)

        latest_date = pd.to_datetime(frame["date"], errors="coerce").max()
        frame = frame[frame["date"] == latest_date].copy()

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

    def _build_weights(
        self,
        frame: pd.DataFrame,
        *,
        exposure_scale: float,
        mandate: str,
    ) -> pd.Series:
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

        frame, feature_cols = self._load_latest_universe_frame(dt)
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

        regime = self.regime_engine.get_regime_as_of(dt)
        exposure_scale = float(self.regime_engine.get_exposure_scale(regime))

        use_feats = [c for c in feature_cols if c in frame.columns]
        if not use_feats:
            use_feats = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
        preds = self.trainer.predict(frame[use_feats], regime=regime)
        if len(preds) != len(frame):
            preds = np.resize(preds, len(frame)) if len(preds) > 0 else np.zeros(len(frame), dtype=float)

        out = pd.DataFrame(
            {
                "ticker": frame["ticker"].astype(str).to_numpy(),
                "model_score": pd.to_numeric(pd.Series(preds), errors="coerce").fillna(0.0).to_numpy(),
                "regime": str(regime),
            }
        )

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

        self._last_info = {
            "as_of_date": str(dt.date()),
            "regime": str(regime),
            "exposure_scale": float(exposure_scale),
            "mandate": str(mandate),
            "model_meta": self.trainer.get_last_prediction_meta(),
        }

        cols = [
            "ticker",
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
        out = out[cols + extra].copy()
        out = out.sort_values("final_score", ascending=False, kind="mergesort").reset_index(drop=True)
        return out

    def get_last_info(self) -> dict[str, Any]:
        return dict(self._last_info)
