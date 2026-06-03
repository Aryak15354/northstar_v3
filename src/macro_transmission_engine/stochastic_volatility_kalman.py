#!/usr/bin/env python3
"""
🟣 STATE-SPACE WITH STOCHASTIC VOLATILITY
Extended Kalman filter with time-varying volatility

Extended State-Space Model:
    State:       [β_t, h_t]  where h_t = log(σ_t²)
    Observation: R_t = M_t^T β_t + ε_t,  ε_t ~ N(0, exp(h_t))
    Volatility:  h_t = μ + φ(h_{t-1} - μ) + ξ_t

Features:
- Time-varying macro sensitivities (β_t)
- Time-varying volatility (σ_t)
- Crisis detection (volatility spikes)
- Regime-dependent transmission
"""

import numpy as np
from typing import Tuple, Optional, Dict
import warnings
warnings.filterwarnings('ignore')

try:
    import jax
    import jax.numpy as jnp
    from jax import lax, jit
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False
    jax = None  # type: ignore
    jnp = np  # type: ignore

    def jit(fn=None, **_kwargs):  # type: ignore
        if fn is None:
            return lambda f: f
        return fn

    class _LaxPlaceholder:  # type: ignore
        @staticmethod
        def scan(*_args, **_kwargs):
            raise ImportError("JAX is required for lax.scan")

    lax = _LaxPlaceholder()  # type: ignore


class StochasticVolatilityKalman:
    """
    Extended Kalman filter with stochastic volatility
    
    State vector: x_t = [β_t, h_t]
    - β_t: Macro sensitivities (K-dimensional)
    - h_t: Log-volatility (scalar)
    
    Total state dimension: K + 1
    """
    
    def __init__(
        self,
        Q_beta_scale: float = 1e-4,  # Beta evolution noise
        Q_h_scale: float = 1e-3,     # Volatility evolution noise
        phi: float = 0.95,           # Volatility persistence
        mu_h: float = -2.0           # Mean log-volatility
    ):
        if not JAX_AVAILABLE:
            raise ImportError("JAX required. Install with: pip install jax jaxlib")
        
        self.Q_beta_scale = Q_beta_scale
        self.Q_h_scale = Q_h_scale
        self.phi = phi
        self.mu_h = mu_h
        
        print(f"🟣 Stochastic Volatility Kalman initialized")
        print(f"   Beta noise: {Q_beta_scale}")
        print(f"   Vol noise: {Q_h_scale}")
        print(f"   Vol persistence (φ): {phi}")
    
    @staticmethod
    @jit
    def _sv_kalman_step(carry: Tuple, t_data: Tuple) -> Tuple:
        """
        Single step of stochastic volatility Kalman filter
        
        Args:
            carry: (x_prev, P_prev, Q, phi, mu_h)
            t_data: (y_t, H_t)
        
        Returns:
            Updated carry and outputs
        """
        x_prev, P_prev, Q, phi, mu_h = carry
        y_t, H_t = t_data
        
        D = len(x_prev)  # State dimension (K + 1)
        K = D - 1  # Beta dimension
        
        # Extract beta and h from state
        beta_prev = x_prev[:K]
        h_prev = x_prev[K]
        
        # ========== PREDICTION STEP ==========
        # State transition
        # β_t = β_{t-1} + w_β
        # h_t = μ + φ(h_{t-1} - μ) + w_h
        
        beta_pred = beta_prev
        h_pred = mu_h + phi * (h_prev - mu_h)
        
        x_pred = jnp.concatenate([beta_pred, jnp.array([h_pred])])
        
        # Covariance prediction
        # F = [I_K, 0; 0, φ]
        F = jnp.eye(D)
        F = F.at[K, K].set(phi)
        
        P_pred = F @ P_prev @ F.T + Q
        
        # ========== UPDATE STEP ==========
        # Observation model: y_t = M_t^T β_t + ε_t
        # where ε_t ~ N(0, exp(h_t))
        
        # Observation matrix: H = [M_t^T, 0]
        H = jnp.concatenate([H_t[0], jnp.array([0.0])]).reshape(1, -1)
        
        # Observation noise (time-varying)
        R_t = jnp.exp(h_pred)
        
        # Innovation
        y_pred = (H @ x_pred)[0]
        innovation = y_t - y_pred
        
        # Innovation covariance
        S_t = (H @ P_pred @ H.T)[0, 0] + R_t
        
        # Kalman gain
        K_gain = (P_pred @ H.T / S_t).flatten()
        
        # State update
        x_new = x_pred + K_gain * innovation
        
        # Covariance update (Joseph form)
        I_KH = jnp.eye(D) - jnp.outer(K_gain, H[0])
        P_new = I_KH @ P_pred @ I_KH.T + jnp.outer(K_gain, K_gain) * R_t
        
        # Ensure symmetry
        P_new = (P_new + P_new.T) / 2
        
        new_carry = (x_new, P_new, Q, phi, mu_h)
        
        return new_carry, (x_new, P_new, innovation, S_t, R_t)
    
    def filter(
        self,
        returns: jnp.ndarray,
        macro: jnp.ndarray,
        x0: Optional[jnp.ndarray] = None,
        P0: Optional[jnp.ndarray] = None
    ) -> Dict:
        """
        Run stochastic volatility Kalman filter
        
        Args:
            returns: Company returns (T,)
            macro: Macro variables (T, K)
            x0: Initial state [β_0, h_0] (K+1,)
            P0: Initial covariance (K+1, K+1)
        
        Returns:
            Dict with filtered states and volatility
        """
        T, K = macro.shape
        D = K + 1  # State dimension
        
        # Initialize
        if x0 is None:
            x0 = jnp.concatenate([jnp.zeros(K), jnp.array([self.mu_h])])
        if P0 is None:
            P0 = jnp.eye(D)
        
        # System matrices
        Q = jnp.eye(D)
        Q = Q.at[:K, :K].set(self.Q_beta_scale * jnp.eye(K))
        Q = Q.at[K, K].set(self.Q_h_scale)
        
        # Prepare data
        H_sequence = macro.reshape(T, 1, K)
        y_sequence = returns.reshape(T, 1)
        
        # Run filter
        init_carry = (x0, P0, Q, self.phi, self.mu_h)
        _, outputs = lax.scan(
            self._sv_kalman_step,
            init_carry,
            (y_sequence, H_sequence)
        )
        
        x_filtered, P_filtered, innovations, S_sequence, R_sequence = outputs
        
        # Extract beta and volatility
        beta_filtered = x_filtered[:, :K]
        h_filtered = x_filtered[:, K]
        sigma_filtered = jnp.exp(h_filtered / 2)  # Convert log-vol to vol
        
        return {
            'beta_filtered': beta_filtered,  # (T, K)
            'h_filtered': h_filtered,  # (T,)
            'sigma_filtered': sigma_filtered,  # (T,)
            'x_filtered': x_filtered,  # (T, K+1)
            'P_filtered': P_filtered,  # (T, K+1, K+1)
            'innovations': innovations,  # (T,)
            'innovation_vars': S_sequence,  # (T,)
            'observation_vars': R_sequence,  # (T,)
            'log_likelihood': self._compute_log_likelihood(innovations, S_sequence)
        }
    
    @staticmethod
    @jit
    def _compute_log_likelihood(innovations: jnp.ndarray, S_sequence: jnp.ndarray) -> float:
        """Compute log-likelihood"""
        log_2pi = jnp.log(2 * jnp.pi)
        log_lik = -0.5 * jnp.sum(
            log_2pi + jnp.log(S_sequence) + innovations**2 / S_sequence
        )
        return log_lik
    
    def detect_volatility_regimes(
        self,
        filter_results: Dict,
        threshold: float = 2.0
    ) -> Dict:
        """
        Detect high/low volatility regimes
        
        Args:
            filter_results: Output from filter()
            threshold: Threshold in standard deviations
        
        Returns:
            Dict with regime classifications
        """
        sigma = filter_results['sigma_filtered']
        
        # Compute rolling statistics
        mean_sigma = jnp.mean(sigma)
        std_sigma = jnp.std(sigma)
        
        # Classify regimes
        z_score = (sigma - mean_sigma) / std_sigma
        
        high_vol = z_score > threshold
        low_vol = z_score < -threshold
        normal_vol = ~(high_vol | low_vol)
        
        return {
            'sigma': sigma,
            'mean_sigma': mean_sigma,
            'std_sigma': std_sigma,
            'z_score': z_score,
            'high_vol_periods': high_vol,
            'low_vol_periods': low_vol,
            'normal_vol_periods': normal_vol,
            'pct_high_vol': float(jnp.mean(high_vol)),
            'pct_low_vol': float(jnp.mean(low_vol))
        }
    
    def compare_crisis_vs_normal(
        self,
        filter_results: Dict,
        crisis_threshold: float = 1.5
    ) -> Dict:
        """
        Compare beta estimates during crisis vs normal periods
        
        Args:
            filter_results: Output from filter()
            crisis_threshold: Volatility threshold for crisis
        
        Returns:
            Dict with crisis vs normal comparison
        """
        beta = filter_results['beta_filtered']
        sigma = filter_results['sigma_filtered']
        
        # Identify crisis periods
        mean_sigma = jnp.mean(sigma)
        std_sigma = jnp.std(sigma)
        z_score = (sigma - mean_sigma) / std_sigma
        
        is_crisis = z_score > crisis_threshold
        is_normal = z_score < 0.5
        
        # Compute average betas
        beta_crisis = jnp.mean(beta[is_crisis], axis=0) if jnp.any(is_crisis) else jnp.zeros(beta.shape[1])
        beta_normal = jnp.mean(beta[is_normal], axis=0) if jnp.any(is_normal) else jnp.zeros(beta.shape[1])
        
        # Compute difference
        beta_diff = beta_crisis - beta_normal
        
        return {
            'beta_crisis': beta_crisis,
            'beta_normal': beta_normal,
            'beta_difference': beta_diff,
            'pct_crisis': float(jnp.mean(is_crisis)),
            'pct_normal': float(jnp.mean(is_normal))
        }


# ============================================================================
# NUMPY WRAPPER
# ============================================================================

class StochasticVolatilityKalmanNumPy:
    """NumPy-compatible wrapper"""
    
    def __init__(self, **kwargs):
        self.sv_filter = StochasticVolatilityKalman(**kwargs)
    
    def filter(
        self,
        returns: np.ndarray,
        macro: np.ndarray,
        **kwargs
    ) -> Dict:
        """Filter with NumPy arrays"""
        returns_jax = jnp.array(returns)
        macro_jax = jnp.array(macro)
        
        results = self.sv_filter.filter(returns_jax, macro_jax, **kwargs)
        
        return {k: np.array(v) if hasattr(v, 'shape') else v 
                for k, v in results.items()}
    
    def detect_volatility_regimes(self, filter_results: Dict) -> Dict:
        """Detect regimes with NumPy arrays"""
        # Convert to JAX
        filter_results_jax = {
            k: jnp.array(v) if isinstance(v, np.ndarray) else v
            for k, v in filter_results.items()
        }
        
        results = self.sv_filter.detect_volatility_regimes(filter_results_jax)
        
        return {k: np.array(v) if hasattr(v, 'shape') else v 
                for k, v in results.items()}
