"""Regime Lab for Northstar: model-based regime diagnostics."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

from .model_adapters import DynamicFactorModel, HMMRegimeModel


class RegimeLab:
    def __init__(self):
        self.transition_thresholds = {
            "volatility_spike": 1.5,
            "correlation_breakdown": 0.3,
            "momentum_reversal": 0.05,
        }

    @staticmethod
    def _read_parquet_safe(path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_parquet(path)
            if isinstance(df, pd.DataFrame):
                return df
        except Exception:
            return pd.DataFrame()
        return pd.DataFrame()

    @staticmethod
    def _coalesce_numeric(df: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
        out = pd.Series(np.nan, index=df.index, dtype=float)
        for col in columns:
            if col in df.columns:
                s = pd.to_numeric(df[col], errors="coerce")
                out = out.where(out.notna(), s)
        return out

    @classmethod
    def _canonicalize_market_frame(cls, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()
        out = df.copy()
        date_col = next(
            (c for c in ["date", "Date", "timestamp", "intelligence_timestamp_str"] if c in out.columns),
            None,
        )
        if date_col is None:
            return pd.DataFrame()

        out["date"] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date")
        if out.empty:
            return pd.DataFrame()

        out["macro_score"] = cls._coalesce_numeric(
            out,
            [
                "macro_score",
                "MacroScore",
                "macro_sentiment_z",
                "belief_strength",
                "regime_confidence",
            ],
        )
        out["stress_score"] = cls._coalesce_numeric(
            out,
            [
                "stress_score",
                "MarketStress_z",
                "risk_pressure_index",
                "liquidity_stress_index",
                "volatility_z",
            ],
        )
        out["breadth_pct"] = cls._coalesce_numeric(
            out,
            [
                "breadth_pct",
                "MarketBreadth",
                "regime_confidence",
            ],
        )
        breadth = pd.to_numeric(out["breadth_pct"], errors="coerce")
        if breadth.notna().any() and float(breadth.dropna().max()) <= 1.0:
            out["breadth_pct"] = breadth * 100.0
        out["participation_score"] = cls._coalesce_numeric(
            out,
            [
                "participation_score",
                "MarketParticipation",
                "edge_health_mean",
                "rolling_sharpe_21d",
            ],
        )
        out["correlation"] = cls._coalesce_numeric(out, ["correlation", "correlation_z"])

        risk_on = cls._coalesce_numeric(out, ["risk_on_probability"])
        if not risk_on.notna().any():
            crisis = cls._coalesce_numeric(out, ["crisis_probability", "drawdown_probability_30d"])
            risk_on = 1.0 - crisis
        out["risk_on_probability"] = risk_on

        allowed = cls._coalesce_numeric(out, ["allowed_exposure"])
        gross = cls._coalesce_numeric(out, ["gross_exposure", "net_exposure"])
        if gross.notna().any() and float(gross.dropna().max()) <= 1.0:
            gross = gross * 100.0
        allowed = allowed.where(allowed.notna(), gross)
        cash = cls._coalesce_numeric(out, ["cash_weight"])
        if cash.notna().any():
            if float(cash.dropna().max()) <= 1.0:
                cash = cash * 100.0
            allowed = allowed.where(allowed.notna(), 100.0 - cash)
        out["allowed_exposure"] = allowed

        keep = [
            "date",
            "macro_score",
            "stress_score",
            "breadth_pct",
            "participation_score",
            "correlation",
            "risk_on_probability",
            "allowed_exposure",
        ]
        out = out[keep].replace([np.inf, -np.inf], np.nan)
        out = out.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        return out

    @classmethod
    def _load_market_history(cls) -> pd.DataFrame:
        # Prefer long integrated history, then override overlapping recent dates
        # with canonical market state artifacts.
        candidates = [
            Path("data/integrated/integrated_state_snapshot.parquet"),
            Path("data/processed/market_state.parquet"),
            Path("data/processed/intelligent_market_state.parquet"),
        ]
        frames: List[pd.DataFrame] = []
        for priority, path in enumerate(candidates):
            raw = cls._read_parquet_safe(path)
            if raw.empty:
                continue
            canon = cls._canonicalize_market_frame(raw)
            if canon.empty:
                continue
            canon["_priority"] = int(priority)
            frames.append(canon)
        if not frames:
            return pd.DataFrame()

        merged = pd.concat(frames, axis=0, ignore_index=True, sort=False)
        merged = merged.dropna(subset=["date"]).sort_values(["date", "_priority"])
        merged = merged.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        return merged.drop(columns=["_priority"], errors="ignore").reset_index(drop=True)

    @staticmethod
    def _normalize_market(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        date_col = next((c for c in ["date", "Date", "timestamp", "intelligence_timestamp_str"] if c in out.columns), None)
        if date_col is None:
            out["date"] = pd.NaT
        else:
            out["date"] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.replace([np.inf, -np.inf], np.nan)
        out = out.dropna(subset=["date"]).sort_values("date")
        return out

    def _feature_matrix(self, market_hist: pd.DataFrame) -> np.ndarray:
        cols = [
            c
            for c in [
                "macro_score",
                "stress_score",
                "breadth_pct",
                "participation_score",
                "correlation",
                "risk_on_probability",
                "allowed_exposure",
                "MacroScore",
                "MarketStress_z",
                "MarketBreadth",
                "MarketParticipation",
            ]
            if c in market_hist.columns
        ]
        if not cols:
            return np.empty((0, 0), dtype=float)
        X = market_hist[cols].apply(pd.to_numeric, errors="coerce").ffill().fillna(0.0)
        return X.to_numpy(dtype=float)

    @staticmethod
    def _change_point_alert(market_hist: pd.DataFrame) -> Dict[str, Any]:
        # Simple online change-point proxy from stress-score z-jump.
        col = "stress_score" if "stress_score" in market_hist.columns else ("MarketStress_z" if "MarketStress_z" in market_hist.columns else None)
        if col is None:
            return {"detected": False, "z_jump": 0.0}
        s = pd.to_numeric(market_hist[col], errors="coerce").dropna()
        if len(s) < 30:
            return {"detected": False, "z_jump": 0.0}
        z = (s - s.rolling(20).mean()) / (s.rolling(20).std() + 1e-12)
        jump = float(abs(z.iloc[-1] - z.iloc[-2])) if len(z.dropna()) >= 2 else 0.0
        return {
            "detected": bool(jump > 1.5),
            "z_jump": jump,
            "threshold": 1.5,
        }

    def run_analysis(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        market_hist = self._normalize_market(self._load_market_history())

        if market_hist.empty:
            return {
                "module": "regime_lab",
                "timestamp": now,
                "outputs": [
                    {
                        "type": "regime_assessment",
                        "actionable": False,
                        "generated_at": now,
                        "data": {"status": "insufficient_history"},
                    }
                ],
            }

        X = self._feature_matrix(market_hist)
        if X.size == 0:
            return {
                "module": "regime_lab",
                "timestamp": now,
                "outputs": [
                    {
                        "type": "regime_assessment",
                        "actionable": False,
                        "generated_at": now,
                        "data": {"status": "missing_regime_features"},
                    }
                ],
            }

        # Dynamic factors + HMM probabilities.
        dfm = DynamicFactorModel(n_factors=3)
        factors = dfm.fit_transform(X)

        hmm = HMMRegimeModel(
            n_states=3,
            max_iter=400,
            tol=1e-4,
            n_init=8,
            min_samples_per_state=30,
            allow_kmeans_fallback=False,
        )
        hmm.fit(factors)
        probs = hmm.predict_proba(factors)
        last = probs[-1] if len(probs) else np.array([1 / 3, 1 / 3, 1 / 3], dtype=float)

        # Map latent states by relative stress to LOW/NORMAL/CRISIS.
        stress = pd.to_numeric(market_hist.get("stress_score", market_hist.get("MarketStress_z", 0.0)), errors="coerce").fillna(0.0).to_numpy()
        state_idx = np.argmax(probs, axis=1) if len(probs) else np.zeros(len(stress), dtype=int)
        state_stress = {i: float(np.mean(stress[state_idx == i])) if np.any(state_idx == i) else 0.0 for i in range(3)}
        ordered = sorted(state_stress.items(), key=lambda kv: kv[1])
        low_state = ordered[0][0]
        high_state = ordered[-1][0]
        normal_state = [i for i in range(3) if i not in {low_state, high_state}][0]

        transition_probs = {
            "to_low_vol": float(last[low_state]),
            "to_normal": float(last[normal_state]),
            "to_crisis": float(last[high_state]),
        }

        change_alert = self._change_point_alert(market_hist)

        primary = "transition"
        if transition_probs["to_crisis"] >= 0.55:
            primary = "crisis"
        elif transition_probs["to_low_vol"] >= 0.55:
            primary = "calm"
        elif transition_probs["to_normal"] >= 0.55:
            primary = "normal"

        regime_assessment = {
            "timestamp": now,
            "primary_regime": primary,
            "regime_confidence": float(max(transition_probs.values())),
            "transition_probabilities": transition_probs,
            "change_point": change_alert,
            "state_stress_profile": state_stress,
        }

        recommendations: List[Dict[str, Any]] = []
        if transition_probs["to_crisis"] > 0.35:
            recommendations.append(
                {
                    "strategy": "increase_defensives",
                    "rationale": f"Crisis transition probability {transition_probs['to_crisis']:.1%}",
                    "confidence": "medium",
                }
            )
        if transition_probs["to_low_vol"] > 0.40:
            recommendations.append(
                {
                    "strategy": "carry_short_vol_selective",
                    "rationale": f"Low-vol transition probability {transition_probs['to_low_vol']:.1%}",
                    "confidence": "medium",
                }
            )
        if change_alert.get("detected"):
            recommendations.append(
                {
                    "strategy": "reduce_regime_confident_bets",
                    "rationale": "Detected potential structural break via change-point proxy",
                    "confidence": "high",
                }
            )

        return {
            "module": "regime_lab",
            "timestamp": now,
            "outputs": [
                {
                    "type": "regime_assessment",
                    "data": regime_assessment,
                    "actionable": False,
                    "generated_at": now,
                },
                {
                    "type": "regime_transition_analysis",
                    "data": {
                        "transition_probabilities": transition_probs,
                        "change_point": change_alert,
                    },
                    "actionable": True,
                    "generated_at": now,
                },
                {
                    "type": "regime_strategy_recommendations",
                    "data": {
                        "current_regime": primary,
                        "recommendations": recommendations,
                    },
                    "actionable": True,
                    "generated_at": now,
                },
            ],
            "alerts": [
                {
                    "signal": "change_point_detected",
                    "severity": "warning",
                    "details": change_alert,
                }
            ]
            if change_alert.get("detected")
            else [],
        }
