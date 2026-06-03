#!/usr/bin/env python3
"""
🔵 BAYESIAN HIERARCHICAL MACRO TRANSMISSION MODEL
Probabilistic inference for macro-equity relationships

Mathematical Model:
    R_{i,t} ~ N(α_i + β_i^T M_t, σ_i²)
    β_i ~ N(μ_sector(i), Σ_β)
    μ_sector ~ N(μ_global, Σ_sector)
    μ_global ~ N(0, τ²I)

Key Advantages:
- Companies borrow strength from sector
- Sectors borrow strength from market
- Reduces overfitting
- Full posterior distribution
- Probabilistic conviction scores

Implementation:
- NumPyro for GPU acceleration
- Variational inference for speed
- MCMC for accuracy
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Try to import NumPyro/JAX (optional dependencies)
try:
    import jax
    import jax.numpy as jnp
    import numpyro
    import numpyro.distributions as dist
    from numpyro import plate
    from numpyro.infer import MCMC, NUTS, SVI, Trace_ELBO
    from numpyro.infer.autoguide import AutoNormal
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False
    jnp = np  # type: ignore[assignment]
    print("⚠️  NumPyro/JAX not available. Install with: pip install numpyro jax jaxlib")


class BayesianMacroTransmission:
    """
    Hierarchical Bayesian model for macro-equity transmission
    
    Hierarchy:
        Global → Sector → Company
    
    Output:
        - Posterior mean β
        - 95% credible intervals
        - P(β > 0) conviction scores
    """
    
    def __init__(
        self,
        use_gpu: bool = False,
        inference_method: str = 'svi',  # 'svi' or 'mcmc'
        num_samples: int = 1000,
        num_warmup: int = 500
    ):
        if not JAX_AVAILABLE:
            raise ImportError(
                "NumPyro/JAX required for Bayesian model. "
                "Install with: pip install numpyro jax jaxlib"
            )
        
        self.use_gpu = use_gpu
        self.inference_method = inference_method
        self.num_samples = num_samples
        self.num_warmup = num_warmup
        
        # Set JAX platform
        if not use_gpu:
            jax.config.update('jax_platform_name', 'cpu')
        
        # Results storage
        self.posterior_samples = None
        self.posterior_summary = None
        
        print(f"🔵 Bayesian Macro Transmission initialized")
        print(f"   Inference: {inference_method}")
        print(f"   Samples: {num_samples}")
        print(f"   Device: {'GPU' if use_gpu else 'CPU'}")
    
    def _hierarchical_model(
        self,
        R: jnp.ndarray,
        M: jnp.ndarray,
        sector_index: jnp.ndarray,
        n_sectors: int
    ):
        """
        NumPyro hierarchical model specification
        
        Args:
            R: Returns matrix (N, T)
            M: Macro matrix (T, K)
            sector_index: Sector assignment (N,)
            n_sectors: Number of sectors
        """
        N, T = R.shape
        K = M.shape[1]
        
        # ========== Global Prior ==========
        mu_global = numpyro.sample(
            "mu_global",
            dist.Normal(0.0, 1.0).expand([K]).to_event(1)
        )
        
        # ========== Sector Level ==========
        with plate("sectors", n_sectors):
            mu_sector = numpyro.sample(
                "mu_sector",
                dist.Normal(mu_global, 1.0).to_event(1)
            )
        
        # ========== Company Level ==========
        with plate("companies", N):
            # Macro betas (hierarchical)
            beta = numpyro.sample(
                "beta",
                dist.Normal(mu_sector[sector_index], 0.5).to_event(1)
            )
            
            # Intercepts
            alpha = numpyro.sample(
                "alpha",
                dist.Normal(0.0, 0.1)
            )
            
            # Volatility
            sigma = numpyro.sample(
                "sigma",
                dist.HalfNormal(0.1)
            )
            
            # Expected returns: α + β^T M
            # beta: (N, K), M: (T, K) → need (N, T)
            mu = alpha[:, None] + jnp.einsum('nk,tk->nt', beta, M)
            
            # Likelihood
            numpyro.sample(
                "obs",
                dist.Normal(mu, sigma[:, None]).to_event(1),
                obs=R
            )
    
    def fit_svi(
        self,
        returns_df: pd.DataFrame,
        macro_df: pd.DataFrame,
        sector_map: Dict[str, str],
        num_steps: int = 5000
    ) -> Dict:
        """
        Fit model using Stochastic Variational Inference (fast)
        
        Args:
            returns_df: Company returns (companies × time)
            macro_df: Macro variables (time × factors)
            sector_map: Dict mapping ticker → sector
            num_steps: Number of optimization steps
        
        Returns:
            Dict with posterior samples and summary
        """
        print("\n🔵 Running SVI (Stochastic Variational Inference)...")
        
        # Prepare data
        R, M, sector_index, n_sectors, tickers, macro_names = self._prepare_data(
            returns_df, macro_df, sector_map
        )
        
        # Convert to JAX arrays
        R_jax = jnp.array(R)
        M_jax = jnp.array(M)
        sector_index_jax = jnp.array(sector_index)
        
        # Setup SVI
        guide = AutoNormal(self._hierarchical_model)
        optimizer = numpyro.optim.Adam(step_size=0.01)
        svi = SVI(
            self._hierarchical_model,
            guide,
            optimizer,
            loss=Trace_ELBO()
        )
        
        # Run SVI
        rng_key = jax.random.PRNGKey(0)
        svi_result = svi.run(
            rng_key,
            num_steps,
            R=R_jax,
            M=M_jax,
            sector_index=sector_index_jax,
            n_sectors=n_sectors,
            progress_bar=True
        )
        
        # Get posterior samples
        params = svi_result.params
        posterior_samples = guide.sample_posterior(
            jax.random.PRNGKey(1),
            params,
            sample_shape=(self.num_samples,)
        )
        
        # Compute summary statistics
        summary = self._compute_posterior_summary(
            posterior_samples,
            tickers,
            macro_names
        )
        
        self.posterior_samples = posterior_samples
        self.posterior_summary = summary
        
        print(f"   ✓ SVI complete ({num_steps} steps)")
        
        return {
            'posterior_samples': posterior_samples,
            'summary': summary,
            'loss': svi_result.losses
        }
    
    def fit_mcmc(
        self,
        returns_df: pd.DataFrame,
        macro_df: pd.DataFrame,
        sector_map: Dict[str, str]
    ) -> Dict:
        """
        Fit model using MCMC (slower but more accurate)
        
        Args:
            returns_df: Company returns (companies × time)
            macro_df: Macro variables (time × factors)
            sector_map: Dict mapping ticker → sector
        
        Returns:
            Dict with posterior samples and summary
        """
        print("\n🔵 Running MCMC (Markov Chain Monte Carlo)...")
        
        # Prepare data
        R, M, sector_index, n_sectors, tickers, macro_names = self._prepare_data(
            returns_df, macro_df, sector_map
        )
        
        # Convert to JAX arrays
        R_jax = jnp.array(R)
        M_jax = jnp.array(M)
        sector_index_jax = jnp.array(sector_index)
        
        # Setup MCMC
        kernel = NUTS(self._hierarchical_model)
        mcmc = MCMC(
            kernel,
            num_warmup=self.num_warmup,
            num_samples=self.num_samples,
            num_chains=1
        )
        
        # Run MCMC
        rng_key = jax.random.PRNGKey(0)
        mcmc.run(
            rng_key,
            R=R_jax,
            M=M_jax,
            sector_index=sector_index_jax,
            n_sectors=n_sectors
        )
        
        # Get posterior samples
        posterior_samples = mcmc.get_samples()
        
        # Compute summary statistics
        summary = self._compute_posterior_summary(
            posterior_samples,
            tickers,
            macro_names
        )
        
        self.posterior_samples = posterior_samples
        self.posterior_summary = summary
        
        print(f"   ✓ MCMC complete ({self.num_samples} samples)")
        
        return {
            'posterior_samples': posterior_samples,
            'summary': summary,
            'diagnostics': mcmc.get_extra_fields()
        }
    
    def _prepare_data(
        self,
        returns_df: pd.DataFrame,
        macro_df: pd.DataFrame,
        sector_map: Dict[str, str]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int, List[str], List[str]]:
        """
        Prepare data for Bayesian model
        
        Returns:
            Tuple of (R, M, sector_index, n_sectors, tickers)
        """
        # Align + sanitize data
        common_idx = returns_df.index.intersection(macro_df.index)
        returns_aligned = returns_df.loc[common_idx].copy()
        macro_aligned = macro_df.loc[common_idx].copy()

        if returns_aligned.empty or macro_aligned.empty:
            raise ValueError("No overlapping observations between returns and macro inputs")

        returns_aligned = (
            returns_aligned.apply(pd.to_numeric, errors='coerce')
            .replace([np.inf, -np.inf], np.nan)
        )
        macro_aligned = (
            macro_aligned.apply(pd.to_numeric, errors='coerce')
            .replace([np.inf, -np.inf], np.nan)
        )

        n_obs = len(common_idx)
        min_obs = max(30, int(n_obs * 0.50))

        # Drop weak/degenerate company columns.
        ret_cov = returns_aligned.notna().sum()
        ret_std = returns_aligned.std(skipna=True)
        keep_returns = ret_cov[(ret_cov >= min_obs) & (ret_std > 1e-10)].index.tolist()
        returns_aligned = returns_aligned[keep_returns]

        # Drop weak/degenerate macro columns.
        macro_cov = macro_aligned.notna().sum()
        macro_std = macro_aligned.std(skipna=True)
        keep_macro = macro_cov[(macro_cov >= min_obs) & (macro_std > 1e-10)].index.tolist()
        macro_aligned = macro_aligned[keep_macro]

        if returns_aligned.empty:
            raise ValueError("No valid return columns after cleaning (coverage/std checks)")
        if macro_aligned.empty:
            raise ValueError("No valid macro columns after cleaning (coverage/std checks)")

        # Fill remaining gaps with robust medians and clip outliers.
        returns_aligned = returns_aligned.fillna(returns_aligned.median()).fillna(0.0)
        macro_aligned = macro_aligned.fillna(macro_aligned.median()).fillna(0.0)

        # Scale-safe clipping to avoid pathological likelihood loc/sigma behavior.
        returns_aligned = returns_aligned.clip(-0.50, 0.50)
        macro_aligned = macro_aligned.apply(
            lambda s: s.clip(
                lower=float(s.quantile(0.001)),
                upper=float(s.quantile(0.999))
            )
        )

        # Standardize macro features for numerical conditioning.
        macro_mu = macro_aligned.mean()
        macro_sigma = macro_aligned.std().replace(0.0, np.nan)
        macro_aligned = ((macro_aligned - macro_mu) / (macro_sigma + 1e-12)).fillna(0.0).clip(-8.0, 8.0)

        # Convert to numpy and validate finite tensors.
        R = returns_aligned.T.values.astype(np.float64)  # (N, T)
        M = macro_aligned.values.astype(np.float64)      # (T, K)
        if not np.isfinite(R).all():
            raise ValueError("Returns tensor contains NaN/inf after cleaning")
        if not np.isfinite(M).all():
            raise ValueError("Macro tensor contains NaN/inf after cleaning")

        if R.shape[1] < max(60, M.shape[1] * 3):
            raise ValueError(
                f"Insufficient time observations for Bayesian fit: T={R.shape[1]}, K={M.shape[1]}"
            )
        
        # Create sector index
        tickers = returns_aligned.columns.tolist()
        sectors = [sector_map.get(t, 'Unknown') for t in tickers]
        unique_sectors = sorted(set(sectors))
        sector_to_idx = {s: i for i, s in enumerate(unique_sectors)}
        sector_index = np.array([sector_to_idx[s] for s in sectors])
        n_sectors = len(unique_sectors)
        macro_names = macro_aligned.columns.tolist()
        
        print(f"   Data prepared:")
        print(f"      Companies: {R.shape[0]}")
        print(f"      Time periods: {R.shape[1]}")
        print(f"      Macro factors: {M.shape[1]}")
        print(f"      Sectors: {n_sectors}")

        return R, M, sector_index, n_sectors, tickers, macro_names
    
    def _compute_posterior_summary(
        self,
        posterior_samples: Dict,
        tickers: List[str],
        macro_names: List[str]
    ) -> pd.DataFrame:
        """
        Compute posterior summary statistics
        
        Returns:
            DataFrame with posterior mean, std, credible intervals, P(β>0)
        """
        beta_samples = np.array(posterior_samples['beta'])  # (n_samples, N, K)
        
        rows = []
        for i, ticker in enumerate(tickers):
            for k, macro_name in enumerate(macro_names):
                beta_posterior = beta_samples[:, i, k]
                
                rows.append({
                    'ticker': ticker,
                    'macro_variable': macro_name,
                    'posterior_mean': float(np.mean(beta_posterior)),
                    'posterior_std': float(np.std(beta_posterior)),
                    'ci_lower': float(np.percentile(beta_posterior, 2.5)),
                    'ci_upper': float(np.percentile(beta_posterior, 97.5)),
                    'prob_positive': float(np.mean(beta_posterior > 0)),
                    'prob_negative': float(np.mean(beta_posterior < 0)),
                    'conviction': float(np.max([
                        np.mean(beta_posterior > 0),
                        np.mean(beta_posterior < 0)
                    ]))
                })
        
        return pd.DataFrame(rows)
    
    def get_macro_conviction(
        self,
        ticker: str,
        macro_variable: str,
        threshold: float = 0.9
    ) -> Dict:
        """
        Get macro conviction score for a company-macro pair
        
        Args:
            ticker: Company ticker
            macro_variable: Macro variable name
            threshold: Conviction threshold (default: 0.9)
        
        Returns:
            Dict with conviction metrics
        """
        if self.posterior_summary is None:
            raise ValueError("Model not fitted yet")
        
        row = self.posterior_summary[
            (self.posterior_summary['ticker'] == ticker) &
            (self.posterior_summary['macro_variable'] == macro_variable)
        ]
        
        if row.empty:
            return {'error': 'not_found'}
        
        row = row.iloc[0]
        
        return {
            'ticker': ticker,
            'macro_variable': macro_variable,
            'posterior_mean': row['posterior_mean'],
            'credible_interval': (row['ci_lower'], row['ci_upper']),
            'conviction': row['conviction'],
            'high_conviction': row['conviction'] > threshold,
            'direction': 'positive' if row['prob_positive'] > 0.5 else 'negative'
        }
    
    def get_high_conviction_relationships(
        self,
        threshold: float = 0.9
    ) -> pd.DataFrame:
        """
        Get all high-conviction macro relationships
        
        Args:
            threshold: Conviction threshold
        
        Returns:
            DataFrame with high-conviction relationships
        """
        if self.posterior_summary is None:
            raise ValueError("Model not fitted yet")
        
        high_conviction = self.posterior_summary[
            self.posterior_summary['conviction'] > threshold
        ].copy()
        
        high_conviction = high_conviction.sort_values('conviction', ascending=False)
        
        return high_conviction
