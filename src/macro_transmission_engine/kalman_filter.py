#!/usr/bin/env python3
"""
🟢 TIME-VARYING PARAMETER REGRESSION (KALMAN FILTER)
Track evolving macro sensitivities over time

State-Space Model:
    Observation: R_t = M_t^T β_t + ε_t
    State:       β_t = β_{t-1} + η_t

Kalman Recursion:
    Predict:  β̂_{t|t-1} = F β̂_{t-1|t-1}
              P_{t|t-1} = F P_{t-1|t-1} F^T + Q
    
    Update:   K_t = P_{t|t-1} H_t^T (H_t P_{t|t-1} H_t^T + R)^{-1}
              β̂_{t|t} = β̂_{t|t-1} + K_t (y_t - H_t β̂_{t|t-1})
              P_{t|t} = (I - K_t H_t) P_{t|t-1}

Output:
    - Time-varying β_t trajectories
    - Regime transition detection
    - Structural break identification
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class TimeVaryingBetaKalman:
    """
    Kalman filter for time-varying macro sensitivities
    
    Tracks how company macro betas evolve over time.
    Useful for:
    - Regime transition detection
    - Structural break identification
    - Adaptive macro exposure
    
    GAP 3 INTEGRATION: Now supports alternative data observations (GST, power)
    """
    
    def __init__(
        self,
        Q_scale: float = 0.001,  # State noise (how fast betas change)
        R_scale: float = 0.01,   # Observation noise
        initial_P_scale: float = 1.0,  # Initial uncertainty
        use_alternative_data: bool = True,  # GAP 3: Enable alternative data
        registry=None,  # GAP 3: IngestionRegistry for alternative data
        config: dict = None  # GAP 3: Configuration dict
    ):
        self.Q_scale = Q_scale
        self.R_scale = R_scale
        self.initial_P_scale = initial_P_scale
        self.use_alternative_data = use_alternative_data
        
        # Results storage
        self.beta_trajectories = {}
        self.P_trajectories = {}
        
        # GAP 3: Initialize alternative data bridge
        self.macro_bridge = None
        if use_alternative_data and registry is not None:
            try:
                from src.alternative_data import MacroAlternativeBridge
                self.macro_bridge = MacroAlternativeBridge(registry, config or {})
                print(f"🟢 Alternative data bridge initialized for Kalman filter")
            except Exception as e:
                print(f"⚠️ Could not initialize alternative data bridge: {e}")
                self.use_alternative_data = False
        
        print(f"🟢 Time-Varying Beta Kalman Filter initialized")
        print(f"   State noise (Q): {Q_scale}")
        print(f"   Observation noise (R): {R_scale}")
        print(f"   Alternative data: {'ENABLED' if self.use_alternative_data else 'DISABLED'}")
    
    def fit_single_company(
        self,
        returns: pd.Series,
        macro_df: pd.DataFrame,
        ticker: str = ""
    ) -> Dict:
        """
        Fit Kalman filter for one company
        
        Args:
            returns: Company return series
            macro_df: Macro variables DataFrame
            ticker: Company ticker for logging
        
        Returns:
            Dict with beta trajectories and diagnostics
        
        GAP 3 INTEGRATION: Now augments macro_df with alternative data observations
        """
        # GAP 3: Augment macro_df with alternative data if available
        if self.use_alternative_data and self.macro_bridge is not None:
            try:
                macro_df = self._augment_with_alternative_data(macro_df)
            except Exception as e:
                print(f"⚠️ Could not augment with alternative data: {e}")
        
        # Align + clean data (missing rows can otherwise poison the full recursion).
        frame = pd.concat(
            [
                pd.to_numeric(returns, errors="coerce").rename("returns"),
                macro_df.apply(pd.to_numeric, errors="coerce"),
            ],
            axis=1,
        ).dropna(how="any")
        if frame.empty:
            raise ValueError("no valid aligned rows after NaN filtering")

        y = frame["returns"].to_numpy(dtype=float)
        M = frame.drop(columns=["returns"]).to_numpy(dtype=float)
        common_idx = frame.index

        T, K = M.shape
        if T < max(30, K * 5):
            raise ValueError(f"insufficient observations after cleaning (T={T}, K={K})")
        
        # Initialize
        beta_t = np.zeros(K)  # Initial state
        P_t = self.initial_P_scale * np.eye(K)  # Initial covariance
        
        # Storage
        beta_history = np.zeros((T, K))
        P_history = np.zeros((T, K, K))
        innovations = np.zeros(T)
        innovation_vars = np.zeros(T)
        
        # Kalman filter recursion
        for t in range(T):
            # Current observation
            y_t = y[t]
            H_t = M[t].reshape(1, -1)  # (1, K)
            
            # ========== PREDICTION STEP ==========
            # State prediction: β̂_{t|t-1} = F β̂_{t-1|t-1}
            # (F = I for random walk)
            beta_pred = beta_t
            
            # Covariance prediction: P_{t|t-1} = F P_{t-1|t-1} F^T + Q
            P_pred = P_t + self.Q_scale * np.eye(K)
            
            # ========== UPDATE STEP ==========
            # Innovation: v_t = y_t - H_t β̂_{t|t-1}
            innovation = float(y_t - H_t @ beta_pred)
            
            # Innovation variance: S_t = H_t P_{t|t-1} H_t^T + R
            S_t = float(H_t @ P_pred @ H_t.T + self.R_scale)
            if not np.isfinite(S_t) or S_t <= 1e-12:
                S_t = 1e-12
            
            # Kalman gain: K_t = P_{t|t-1} H_t^T S_t^{-1}
            K_t = P_pred @ H_t.T / S_t
            
            # State update: β̂_{t|t} = β̂_{t|t-1} + K_t v_t
            beta_t = beta_pred + (K_t.flatten() * innovation)
            
            # Covariance update: P_{t|t} = (I - K_t H_t) P_{t|t-1}
            P_t = (np.eye(K) - K_t @ H_t) @ P_pred
            
            # Store
            beta_history[t] = beta_t
            P_history[t] = P_t
            innovations[t] = float(innovation)
            innovation_vars[t] = S_t
        
        # Create DataFrame
        beta_df = pd.DataFrame(
            beta_history,
            index=common_idx,
            columns=macro_df.columns
        )
        
        # Compute diagnostics
        diagnostics = self._compute_diagnostics(
            innovations,
            innovation_vars,
            beta_history
        )
        
        result = {
            'ticker': ticker,
            'beta_trajectory': beta_df,
            'P_trajectory': P_history,
            'innovations': innovations,
            'diagnostics': diagnostics
        }
        
        # Store
        if ticker:
            self.beta_trajectories[ticker] = beta_df
            self.P_trajectories[ticker] = P_history
        
        return result
    
    def fit_all_companies(
        self,
        returns_df: pd.DataFrame,
        macro_df: pd.DataFrame,
        max_companies: Optional[int] = None
    ) -> Dict[str, Dict]:
        """
        Fit Kalman filter for all companies
        
        Args:
            returns_df: Company returns DataFrame
            macro_df: Macro variables DataFrame
            max_companies: Limit number of companies (for testing)
        
        Returns:
            Dict mapping ticker → results
        """
        print("\n🟢 Fitting Kalman filters for all companies...")
        
        tickers = returns_df.columns.tolist()
        if max_companies:
            tickers = tickers[:max_companies]
        
        results = {}
        
        for i, ticker in enumerate(tickers):
            if (i + 1) % 50 == 0:
                print(f"   Progress: {i+1}/{len(tickers)}")
            
            try:
                result = self.fit_single_company(
                    returns_df[ticker],
                    macro_df,
                    ticker
                )
                results[ticker] = result
            except Exception as e:
                print(f"   ⚠️ Error for {ticker}: {e}")
                results[ticker] = {'error': str(e)}
        
        print(f"   ✓ Completed {len(results)} companies")
        
        return results
    
    def _compute_diagnostics(
        self,
        innovations: np.ndarray,
        innovation_vars: np.ndarray,
        beta_history: np.ndarray
    ) -> Dict:
        """
        Compute filter diagnostics
        
        Returns:
            Dict with diagnostic statistics
        """
        # Standardized innovations
        std_innovations = innovations / np.sqrt(innovation_vars)
        
        # Beta volatility (how much betas change)
        beta_changes = np.diff(beta_history, axis=0)
        beta_volatility = np.std(beta_changes, axis=0)
        
        return {
            'innovation_mean': float(np.mean(innovations)),
            'innovation_std': float(np.std(innovations)),
            'std_innovation_mean': float(np.mean(std_innovations)),
            'std_innovation_std': float(np.std(std_innovations)),
            'beta_volatility': beta_volatility.tolist(),
            'mean_beta_volatility': float(np.mean(beta_volatility))
        }
    
    def detect_regime_transitions(
        self,
        ticker: str,
        macro_variable: str,
        threshold: float = 2.0
    ) -> pd.DataFrame:
        """
        Detect regime transitions in macro sensitivity
        
        Args:
            ticker: Company ticker
            macro_variable: Macro variable name
            threshold: Threshold for significant change (in std devs)
        
        Returns:
            DataFrame with detected transitions
        """
        if ticker not in self.beta_trajectories:
            raise ValueError(f"No results for {ticker}")
        
        beta_df = self.beta_trajectories[ticker]
        
        if macro_variable not in beta_df.columns:
            raise ValueError(f"Macro variable {macro_variable} not found")
        
        beta_series = beta_df[macro_variable]
        
        # Compute rolling mean and std
        window = 52  # 1 year for weekly data
        rolling_mean = beta_series.rolling(window, min_periods=20).mean()
        rolling_std = beta_series.rolling(window, min_periods=20).std()
        
        # Detect significant deviations
        z_score = (beta_series - rolling_mean) / rolling_std
        transitions = z_score.abs() > threshold
        
        # Create transition DataFrame
        transition_dates = beta_series.index[transitions]
        
        if len(transition_dates) == 0:
            return pd.DataFrame()
        
        transition_df = pd.DataFrame({
            'date': transition_dates,
            'beta': beta_series.loc[transition_dates].values,
            'rolling_mean': rolling_mean.loc[transition_dates].values,
            'z_score': z_score.loc[transition_dates].values
        })
        
        return transition_df
    
    def plot_beta_trajectory(
        self,
        ticker: str,
        macro_variable: str,
        show_uncertainty: bool = True
    ):
        """
        Plot beta trajectory with uncertainty bands
        
        Requires matplotlib (optional dependency)
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed. Install with: pip install matplotlib")
            return None
        
        if ticker not in self.beta_trajectories:
            raise ValueError(f"No results for {ticker}")
        
        beta_df = self.beta_trajectories[ticker]
        P_history = self.P_trajectories[ticker]
        
        if macro_variable not in beta_df.columns:
            raise ValueError(f"Macro variable {macro_variable} not found")
        
        # Get beta trajectory
        beta_series = beta_df[macro_variable]
        
        # Get uncertainty (std dev)
        macro_idx = beta_df.columns.tolist().index(macro_variable)
        std_series = np.sqrt(P_history[:, macro_idx, macro_idx])
        
        # Plot
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(beta_series.index, beta_series.values, 'b-', linewidth=2, label='β_t')
        
        if show_uncertainty:
            ax.fill_between(
                beta_series.index,
                beta_series.values - 2*std_series,
                beta_series.values + 2*std_series,
                alpha=0.3,
                label='95% CI'
            )
        
        ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
        ax.set_xlabel('Date')
        ax.set_ylabel('Beta')
        ax.set_title(f'{ticker} - {macro_variable} Sensitivity (Time-Varying)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def get_current_beta(
        self,
        ticker: str,
        as_of_date: Optional[pd.Timestamp] = None
    ) -> pd.Series:
        """
        Get current (or as-of-date) beta estimates
        
        Args:
            ticker: Company ticker
            as_of_date: Date to get betas (default: latest)
        
        Returns:
            Series with current beta estimates
        """
        if ticker not in self.beta_trajectories:
            raise ValueError(f"No results for {ticker}")
        
        beta_df = self.beta_trajectories[ticker]
        beta_df = beta_df.dropna(how='all')
        if beta_df.empty:
            raise ValueError(f"No valid beta trajectory rows for {ticker}")
        
        if as_of_date is None:
            return beta_df.iloc[-1]
        else:
            # Find closest date
            idx = beta_df.index.get_indexer([as_of_date], method='nearest')[0]
            return beta_df.iloc[idx]
    
    def compare_static_vs_dynamic(
        self,
        ticker: str,
        macro_variable: str,
        static_beta: float
    ) -> Dict:
        """
        Compare static OLS beta vs time-varying Kalman beta
        
        Args:
            ticker: Company ticker
            macro_variable: Macro variable name
            static_beta: Static OLS beta estimate
        
        Returns:
            Dict with comparison metrics
        """
        if ticker not in self.beta_trajectories:
            raise ValueError(f"No results for {ticker}")
        
        beta_df = self.beta_trajectories[ticker]
        beta_series = beta_df[macro_variable]
        
        # Compute statistics
        mean_dynamic = beta_series.mean()
        std_dynamic = beta_series.std()
        min_dynamic = beta_series.min()
        max_dynamic = beta_series.max()
        
        # How often does dynamic beta differ significantly from static?
        significant_diff = np.abs(beta_series - static_beta) > 2 * std_dynamic
        pct_different = significant_diff.mean() * 100
        
        return {
            'ticker': ticker,
            'macro_variable': macro_variable,
            'static_beta': static_beta,
            'dynamic_mean': mean_dynamic,
            'dynamic_std': std_dynamic,
            'dynamic_range': (min_dynamic, max_dynamic),
            'pct_time_significantly_different': pct_different,
            'current_beta': beta_series.iloc[-1]
        }
    
    def _augment_with_alternative_data(self, macro_df: pd.DataFrame) -> pd.DataFrame:
        """
        GAP 3: Augment macro DataFrame with alternative data observations.
        
        Adds GST and power consumption signals as additional macro variables
        that the Kalman filter can track.
        
        Args:
            macro_df: Original macro DataFrame with index as dates
            
        Returns:
            Augmented DataFrame with alternative data columns
        """
        if self.macro_bridge is None:
            return macro_df
        
        augmented_df = macro_df.copy()
        
        # Add alternative data for each date in macro_df
        alt_data_rows = []
        for date in macro_df.index:
            try:
                # Get Kalman observation vector for this date
                obs = self.macro_bridge.get_kalman_observation_vector(date)
                alt_data_rows.append({
                    'date': date,
                    'gst_activity': obs.get('composite_activity_score', 0.0),
                    'power_industrial': obs.get('power_industrial_proxy', 0.0)
                })
            except Exception as e:
                # Graceful degradation: use zeros if data unavailable
                alt_data_rows.append({
                    'date': date,
                    'gst_activity': 0.0,
                    'power_industrial': 0.0
                })
        
        # Create alternative data DataFrame
        alt_df = pd.DataFrame(alt_data_rows).set_index('date')
        
        # Merge with original macro_df
        augmented_df = pd.concat([macro_df, alt_df], axis=1)
        
        return augmented_df
