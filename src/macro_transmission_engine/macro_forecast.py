#!/usr/bin/env python3
"""
🟣 BAYESIAN VAR MACRO FORECASTER
Forecast macro variables using Bayesian Vector Autoregression

Model:
    M_t = A M_{t-1} + ε_t
    A ~ N(0, λ²I)  (Minnesota prior)

Output:
    - E[ΔM_{t+h}] for h=1,2,...,H
    - Var(ΔM) uncertainty
    - Regime-conditional forecasts
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

try:
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist
    from numpyro.infer import MCMC, NUTS
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False
    jnp = np  # type: ignore[assignment]


class BayesianVARForecaster:
    """
    Bayesian Vector Autoregression for macro forecasting
    
    Features:
    - Minnesota prior (shrinkage)
    - Multi-step ahead forecasts
    - Uncertainty quantification
    """
    
    def __init__(
        self,
        lags: int = 1,
        prior_scale: float = 0.1,
        num_samples: int = 500
    ):
        self.lags = lags
        self.prior_scale = prior_scale
        self.num_samples = num_samples
        
        self.A_posterior = None
        self.forecast_samples = None
        self.fit_diagnostics: Dict[str, Any] = {}
        
        print(f"🟣 Bayesian VAR Forecaster initialized (lags={lags})")

    def _sanitize_macro_input(self, macro_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        clean = macro_df.copy()
        clean = clean.apply(pd.to_numeric, errors="coerce")
        clean = clean.replace([np.inf, -np.inf], np.nan)

        diagnostics: Dict[str, Any] = {
            "input_rows": int(len(clean)),
            "input_cols": int(len(clean.columns)),
            "nan_cells_before": int(clean.isna().sum().sum()),
        }

        all_nan_cols = [str(c) for c in clean.columns if clean[c].isna().all()]
        if all_nan_cols:
            clean = clean.drop(columns=all_nan_cols, errors="ignore")
        diagnostics["dropped_all_nan_cols"] = all_nan_cols

        clean = clean.ffill().bfill().fillna(0.0)
        arr = clean.values.astype(float)
        if not np.isfinite(arr).all():
            arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
            clean = pd.DataFrame(arr, index=clean.index, columns=clean.columns)

        diagnostics["nan_cells_after"] = int(clean.isna().sum().sum())
        diagnostics["non_finite_after"] = int((~np.isfinite(clean.values)).sum())
        diagnostics["output_rows"] = int(len(clean))
        diagnostics["output_cols"] = int(len(clean.columns))

        if clean.empty or clean.shape[1] == 0:
            raise ValueError("Macro forecast input empty after sanitization")
        if len(clean) <= self.lags + 1:
            raise ValueError("Not enough observations for VAR after sanitization")

        return clean, diagnostics
    
    def _var_model(self, M: jnp.ndarray):
        """NumPyro VAR model"""
        T, K = M.shape
        
        # Prior on VAR coefficients (Minnesota prior)
        A = numpyro.sample(
            "A",
            dist.Normal(0.0, self.prior_scale).expand([K, K]).to_event(2)
        )
        
        # Observation noise
        sigma = numpyro.sample(
            "sigma",
            dist.HalfNormal(0.1).expand([K]).to_event(1)
        )
        
        # Likelihood
        for t in range(self.lags, T):
            mean = jnp.dot(A, M[t-1])
            numpyro.sample(
                f"M_{t}",
                dist.Normal(mean, sigma).to_event(1),
                obs=M[t]
            )
    
    def fit(self, macro_df: pd.DataFrame) -> Dict:
        """
        Fit Bayesian VAR
        
        Args:
            macro_df: Macro variables DataFrame (time × factors)
        
        Returns:
            Dict with posterior samples
        """
        clean_df, diagnostics = self._sanitize_macro_input(macro_df)
        self.fit_diagnostics = diagnostics

        if not JAX_AVAILABLE:
            return self._fit_ols_fallback(clean_df)
        
        print("\n🟣 Fitting Bayesian VAR...")

        try:
            M = jnp.array(clean_df.values.astype(float))

            # Run MCMC
            kernel = NUTS(self._var_model)
            mcmc = MCMC(kernel, num_warmup=200, num_samples=self.num_samples)

            import jax
            mcmc.run(jax.random.PRNGKey(0), M=M)

            samples = mcmc.get_samples().get("A")
            if samples is None:
                raise ValueError("Bayesian VAR returned no coefficient samples")

            self.A_posterior = np.asarray(samples)
            if not np.isfinite(self.A_posterior).all():
                raise ValueError("Bayesian VAR posterior contains non-finite coefficients")

            print(f"   ✓ VAR fitted ({self.num_samples} samples)")
            return {"A_posterior": self.A_posterior, "method": "bayesian", "diagnostics": diagnostics}
        except Exception as exc:
            print(f"   ⚠️ Bayesian VAR failed ({exc}); using OLS fallback")
            return self._fit_ols_fallback(clean_df, reason=str(exc), diagnostics=diagnostics)

    def _fit_ols_fallback(
        self,
        macro_df: pd.DataFrame,
        *,
        reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """OLS VAR as fallback"""
        msg = "\n🟣 Fitting OLS VAR (fallback)..."
        if reason:
            msg += f" reason={reason}"
        print(msg)
        
        clean_df = macro_df.copy()
        clean_df = clean_df.apply(pd.to_numeric, errors="coerce")
        clean_df = clean_df.replace([np.inf, -np.inf], np.nan)
        # Keep deterministic + robust behavior when early differencing introduces gaps.
        clean_df = clean_df.ffill().bfill().fillna(0.0)

        M = clean_df.values.astype(float)
        T, K = M.shape
        if T <= self.lags + 1:
            raise ValueError("Not enough observations for VAR fallback")
        
        # Construct lagged matrix
        Y = M[self.lags:]
        X = M[self.lags-1:-1]

        # OLS: A = (X'X)^{-1} X'Y with robust fallback.
        try:
            A = np.linalg.lstsq(X, Y, rcond=None)[0].T
        except np.linalg.LinAlgError:
            XtX = X.T @ X
            ridge = 1e-6 * (np.trace(XtX) / max(K, 1))
            A = (np.linalg.pinv(XtX + np.eye(K) * max(ridge, 1e-8)) @ X.T @ Y).T
        
        self.A_posterior = A[np.newaxis, :, :]  # Add sample dimension
        
        print(f"   ✓ OLS VAR fitted")
        
        return {'A_ols': A, "method": "ols_fallback", "diagnostics": diagnostics or self.fit_diagnostics}
    
    def forecast(
        self,
        macro_df: pd.DataFrame,
        horizon: int = 4
    ) -> Dict:
        """
        Generate multi-step ahead forecasts
        
        Args:
            macro_df: Historical macro data
            horizon: Forecast horizon (periods ahead)
        
        Returns:
            Dict with forecast mean and uncertainty
        """
        if self.A_posterior is None:
            raise ValueError("Model not fitted")

        clean_df, _diag = self._sanitize_macro_input(macro_df)
        M_last = clean_df.values[-1]
        K = len(M_last)
        n_samples = self.A_posterior.shape[0]
        
        # Storage for forecasts
        forecasts = np.zeros((n_samples, horizon, K))
        
        # Generate forecast samples
        for s in range(n_samples):
            A = self.A_posterior[s]
            M_t = M_last.copy()
            
            for h in range(horizon):
                M_t = A @ M_t
                forecasts[s, h] = M_t
        
        # Compute statistics
        forecast_mean = forecasts.mean(axis=0)
        forecast_std = forecasts.std(axis=0)
        
        # Create DataFrame
        forecast_df = pd.DataFrame(
            forecast_mean,
            columns=clean_df.columns
        )
        
        return {
            'forecast_mean': forecast_df,
            'forecast_std': forecast_std,
            'forecast_samples': forecasts
        }
    
    def get_expected_change(
        self,
        macro_df: pd.DataFrame,
        horizon: int = 1
    ) -> pd.Series:
        """
        Get expected macro change: E[ΔM_{t+h}]
        
        Args:
            macro_df: Historical macro data
            horizon: Forecast horizon
        
        Returns:
            Series with expected changes
        """
        forecast_result = self.forecast(macro_df, horizon)
        clean_df, _diag = self._sanitize_macro_input(macro_df)
        M_current = clean_df.iloc[-1]
        M_forecast = forecast_result['forecast_mean'].iloc[horizon-1]
        
        delta_M = M_forecast - M_current
        
        return delta_M
