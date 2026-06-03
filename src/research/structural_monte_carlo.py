"""Structural Monte Carlo with macro-to-sector-to-company propagation."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


class StructuralMonteCarlo:
    """Simulates fat-tailed paths with macro/sector structure."""

    def __init__(self, random_state: int = 42):
        self.random_state = int(random_state)
        self.rng = np.random.default_rng(self.random_state)
        self.macro_cols: List[str] = []
        self.sector_betas: Dict[str, np.ndarray] = {}
        self.idio_scale: Dict[str, float] = {}
        self.base_mu = 0.0
        self.base_sigma = 0.01

    def fit(self, panel: pd.DataFrame, return_col: str = "forward_return_5d") -> "StructuralMonteCarlo":
        if panel.empty or return_col not in panel.columns:
            return self

        df = panel.copy()
        df[return_col] = pd.to_numeric(df[return_col], errors="coerce")
        df = df.dropna(subset=[return_col])
        if df.empty:
            return self

        self.base_mu = float(df[return_col].mean())
        self.base_sigma = float(df[return_col].std()) if np.isfinite(df[return_col].std()) else 0.01
        self.base_sigma = max(self.base_sigma, 1e-4)

        self.macro_cols = [c for c in df.columns if c.startswith("macro_") and pd.api.types.is_numeric_dtype(df[c])]
        if not self.macro_cols:
            return self

        industry_col = "Industry" if "Industry" in df.columns else None
        if industry_col is None:
            df["Industry"] = "UNKNOWN"
            industry_col = "Industry"

        for sector, g in df.groupby(industry_col, sort=False):
            sub = g.dropna(subset=self.macro_cols + [return_col])
            if len(sub) < 20:
                continue
            X = sub[self.macro_cols].to_numpy(dtype=float)
            y = sub[return_col].to_numpy(dtype=float)
            try:
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
            except Exception:
                beta = np.zeros(len(self.macro_cols), dtype=float)
            self.sector_betas[str(sector)] = np.asarray(beta, dtype=float)

        # ticker-specific idiosyncratic vol scale
        for ticker, g in df.groupby("ticker", sort=False):
            s = pd.to_numeric(g[return_col], errors="coerce").dropna()
            if len(s) < 8:
                continue
            self.idio_scale[str(ticker)] = float(max(s.std(), 1e-4))

        return self

    def _sample_macro_shocks(self, n_paths: int, horizon: int, df_t: float = 5.0) -> np.ndarray:
        n_macro = max(1, len(self.macro_cols))
        # Student-t shocks for heavy tails.
        z = self.rng.standard_t(df=df_t, size=(n_paths, horizon, n_macro))
        return z / np.sqrt(df_t / max(df_t - 2.0, 1.0))

    def simulate_paths(
        self,
        panel: pd.DataFrame,
        n_paths: int = 5000,
        horizon: int = 20,
        stress_multiplier: float = 1.0,
    ) -> Dict[str, np.ndarray]:
        if panel.empty:
            return {"paths": np.empty((0, 0), dtype=float), "tickers": np.array([], dtype=str)}

        tickers = np.array(sorted(set(panel.get("ticker", pd.Series(dtype=str)).astype(str))), dtype=str)
        if len(tickers) == 0:
            return {"paths": np.empty((0, 0), dtype=float), "tickers": tickers}

        shocks = self._sample_macro_shocks(n_paths=n_paths, horizon=horizon)
        n = len(tickers)
        paths = np.zeros((n_paths, horizon, n), dtype=float)

        ticker_sector = {}
        if "Industry" in panel.columns:
            latest_sector = panel.sort_values("date").groupby("ticker").tail(1)
            ticker_sector = {str(r["ticker"]): str(r.get("Industry", "UNKNOWN")) for _, r in latest_sector.iterrows()}

        for j, ticker in enumerate(tickers):
            sector = ticker_sector.get(str(ticker), "UNKNOWN")
            beta = self.sector_betas.get(sector)
            if beta is None or len(beta) != max(1, len(self.macro_cols)):
                beta = np.zeros(max(1, len(self.macro_cols)), dtype=float)

            idio = float(self.idio_scale.get(str(ticker), self.base_sigma))
            idio_noise = self.rng.standard_t(df=5.0, size=(n_paths, horizon)) * idio * stress_multiplier

            macro_component = np.tensordot(shocks, beta, axes=([2], [0]))
            paths[:, :, j] = self.base_mu + macro_component + idio_noise

        return {"paths": paths, "tickers": tickers}

    @staticmethod
    def evaluate(paths: np.ndarray) -> Dict[str, float]:
        if paths.size == 0:
            return {
                "survival_probability": 0.0,
                "avg_max_drawdown": 0.0,
                "p95_max_drawdown": 0.0,
                "tail_loss_p01": 0.0,
                "recovery_half_life": 0.0,
            }

        # Aggregate ticker returns equally.
        port = paths.mean(axis=2)
        curve = np.cumprod(1.0 + port, axis=1)
        peaks = np.maximum.accumulate(curve, axis=1)
        dd = curve / np.maximum(peaks, 1e-12) - 1.0
        max_dd = np.abs(np.min(dd, axis=1))

        end_ret = curve[:, -1] - 1.0
        surv = float(np.mean(max_dd < 0.20))

        # Approximate recovery half-life: first index where curve recovers to 95% of peak after trough.
        rec = []
        for i in range(len(curve)):
            c = curve[i]
            p = peaks[i]
            trough_idx = int(np.argmin(c / np.maximum(p, 1e-12) - 1.0))
            target = p[trough_idx] * 0.95
            post = np.where(c[trough_idx:] >= target)[0]
            rec.append(float(post[0]) if len(post) else float(len(c) - trough_idx))

        return {
            "survival_probability": surv,
            "avg_max_drawdown": float(np.mean(max_dd)),
            "p95_max_drawdown": float(np.percentile(max_dd, 95)),
            "tail_loss_p01": float(np.percentile(end_ret, 1)),
            "recovery_half_life": float(np.mean(rec)),
        }
