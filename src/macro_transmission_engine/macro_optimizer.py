#!/usr/bin/env python3
"""
🔴 MACRO-AWARE QUADRATIC PORTFOLIO OPTIMIZER
Portfolio optimization with macro exposure constraints

Objective:
    max_w  w^T μ - (γ/2) w^T Σ w - κ ||B^T w - β*||²

Where:
    μ = expected returns
    Σ = covariance matrix
    B = macro beta matrix (N × K)
    β* = target macro exposure (K,)
    γ = risk aversion
    κ = macro penalty

Constraints:
    Σ w_i = 1  (fully invested)
    w_i ≥ 0    (long-only)
    w_i ≤ w_max (position limits)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Try to import optimization libraries
try:
    import cvxpy as cp
    CVXPY_AVAILABLE = True
except ImportError:
    CVXPY_AVAILABLE = False
    print("⚠️  CVXPY not available. Install with: pip install cvxpy")

try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class MacroAwareOptimizer:
    """
    Portfolio optimizer with macro exposure management
    
    Features:
    - Macro exposure penalties
    - Target macro neutrality or tilts
    - Risk-adjusted optimization
    - Position limits
    - Turnover constraints
    """
    
    def __init__(
        self,
        gamma: float = 3.0,      # Risk aversion
        kappa: float = 5.0,      # Macro penalty
        max_position: float = 0.1,  # 10% max per stock
        max_turnover: Optional[float] = None  # Optional turnover limit
    ):
        self.gamma = gamma
        self.kappa = kappa
        self.max_position = max_position
        self.max_turnover = max_turnover
        
        print(f"🔴 Macro-Aware Optimizer initialized")
        print(f"   Risk aversion (γ): {gamma}")
        print(f"   Macro penalty (κ): {kappa}")
        print(f"   Max position: {max_position*100}%")
    
    def optimize_cvxpy(
        self,
        mu: np.ndarray,
        Sigma: np.ndarray,
        B: np.ndarray,
        beta_target: Optional[np.ndarray] = None,
        w_prev: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Optimize using CVXPY (convex optimization)
        
        Args:
            mu: Expected returns (N,)
            Sigma: Covariance matrix (N, N)
            B: Macro beta matrix (N, K)
            beta_target: Target macro exposure (K,) - default: zeros
            w_prev: Previous weights for turnover constraint (N,)
        
        Returns:
            Dict with optimal weights and diagnostics
        """
        if not CVXPY_AVAILABLE:
            raise ImportError("CVXPY required. Install with: pip install cvxpy")
        
        N = len(mu)
        K = B.shape[1]
        
        if beta_target is None:
            beta_target = np.zeros(K)
        
        # Decision variable
        w = cp.Variable(N)
        
        # Portfolio macro exposure
        beta_portfolio = B.T @ w
        
        # Objective components
        expected_return = mu @ w
        risk_penalty = 0.5 * self.gamma * cp.quad_form(w, Sigma)
        macro_penalty = self.kappa * cp.sum_squares(beta_portfolio - beta_target)
        
        # Full objective
        objective = cp.Maximize(
            expected_return - risk_penalty - macro_penalty
        )
        
        # Constraints
        constraints = [
            cp.sum(w) == 1,  # Fully invested
            w >= 0,  # Long-only
            w <= self.max_position  # Position limits
        ]
        
        # Turnover constraint
        if self.max_turnover is not None and w_prev is not None:
            turnover = cp.sum(cp.abs(w - w_prev))
            constraints.append(turnover <= self.max_turnover)
        
        # Solve
        problem = cp.Problem(objective, constraints)
        
        try:
            problem.solve(solver=cp.ECOS, verbose=False)
            
            if problem.status not in ['optimal', 'optimal_inaccurate']:
                print(f"   ⚠️ Solver status: {problem.status}")
                return {'success': False, 'status': problem.status}
            
            w_opt = w.value
            
            # Compute diagnostics
            portfolio_return = mu @ w_opt
            portfolio_risk = np.sqrt(w_opt @ Sigma @ w_opt)
            portfolio_beta = B.T @ w_opt
            macro_distance = np.linalg.norm(portfolio_beta - beta_target)
            
            return {
                'success': True,
                'weights': w_opt,
                'expected_return': portfolio_return,
                'risk': portfolio_risk,
                'sharpe': portfolio_return / portfolio_risk if portfolio_risk > 0 else 0,
                'portfolio_beta': portfolio_beta,
                'macro_distance': macro_distance,
                'objective_value': problem.value,
                'n_active': int(np.sum(w_opt > 1e-6))
            }
            
        except Exception as e:
            print(f"   ❌ Optimization failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def optimize_scipy(
        self,
        mu: np.ndarray,
        Sigma: np.ndarray,
        B: np.ndarray,
        beta_target: Optional[np.ndarray] = None,
        w_prev: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Optimize using scipy (fallback method)
        
        Uses SLSQP (Sequential Least Squares Programming)
        """
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required")
        
        N = len(mu)
        K = B.shape[1]
        
        if beta_target is None:
            beta_target = np.zeros(K)
        
        # Objective function (negative for minimization)
        def objective(w):
            expected_return = mu @ w
            risk_penalty = 0.5 * self.gamma * (w @ Sigma @ w)
            beta_portfolio = B.T @ w
            macro_penalty = self.kappa * np.sum((beta_portfolio - beta_target)**2)
            
            return -(expected_return - risk_penalty - macro_penalty)
        
        # Gradient
        def gradient(w):
            grad_return = mu
            grad_risk = self.gamma * (Sigma @ w)
            beta_portfolio = B.T @ w
            grad_macro = 2 * self.kappa * (B @ (beta_portfolio - beta_target))
            
            return -(grad_return - grad_risk - grad_macro)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Fully invested
        ]
        
        # Bounds
        bounds = [(0, self.max_position) for _ in range(N)]
        
        # Initial guess (equal weight)
        w0 = np.ones(N) / N
        
        # Optimize
        result = minimize(
            objective,
            w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        if not result.success:
            print(f"   ⚠️ Optimization warning: {result.message}")
        
        w_opt = result.x
        
        # Compute diagnostics
        portfolio_return = mu @ w_opt
        portfolio_risk = np.sqrt(w_opt @ Sigma @ w_opt)
        portfolio_beta = B.T @ w_opt
        macro_distance = np.linalg.norm(portfolio_beta - beta_target)
        
        return {
            'success': result.success,
            'weights': w_opt,
            'expected_return': portfolio_return,
            'risk': portfolio_risk,
            'sharpe': portfolio_return / portfolio_risk if portfolio_risk > 0 else 0,
            'portfolio_beta': portfolio_beta,
            'macro_distance': macro_distance,
            'objective_value': -result.fun,
            'n_active': int(np.sum(w_opt > 1e-6))
        }
    
    def optimize(
        self,
        mu: np.ndarray,
        Sigma: np.ndarray,
        B: np.ndarray,
        beta_target: Optional[np.ndarray] = None,
        w_prev: Optional[np.ndarray] = None,
        method: str = 'auto'
    ) -> Dict:
        """
        Optimize portfolio (auto-selects best method)
        
        Args:
            mu: Expected returns (N,)
            Sigma: Covariance matrix (N, N)
            B: Macro beta matrix (N, K)
            beta_target: Target macro exposure (K,)
            w_prev: Previous weights (N,)
            method: 'cvxpy', 'scipy', or 'auto'
        
        Returns:
            Dict with optimal weights and diagnostics
        """
        if method == 'auto':
            method = 'cvxpy' if CVXPY_AVAILABLE else 'scipy'
        
        if method == 'cvxpy':
            return self.optimize_cvxpy(mu, Sigma, B, beta_target, w_prev)
        elif method == 'scipy':
            return self.optimize_scipy(mu, Sigma, B, beta_target, w_prev)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def compute_efficient_frontier(
        self,
        mu: np.ndarray,
        Sigma: np.ndarray,
        B: np.ndarray,
        beta_target: Optional[np.ndarray] = None,
        n_points: int = 20
    ) -> Dict:
        """
        Compute efficient frontier with macro constraints
        
        Args:
            mu: Expected returns (N,)
            Sigma: Covariance matrix (N, N)
            B: Macro beta matrix (N, K)
            beta_target: Target macro exposure (K,)
            n_points: Number of frontier points
        
        Returns:
            Dict with frontier points
        """
        # Range of risk aversion parameters
        gamma_range = np.logspace(-1, 2, n_points)
        
        frontier_returns = []
        frontier_risks = []
        frontier_sharpes = []
        frontier_weights = []
        
        original_gamma = self.gamma
        
        for gamma in gamma_range:
            self.gamma = gamma
            
            result = self.optimize(mu, Sigma, B, beta_target)
            
            if result['success']:
                frontier_returns.append(result['expected_return'])
                frontier_risks.append(result['risk'])
                frontier_sharpes.append(result['sharpe'])
                frontier_weights.append(result['weights'])
        
        # Restore original gamma
        self.gamma = original_gamma
        
        return {
            'returns': np.array(frontier_returns),
            'risks': np.array(frontier_risks),
            'sharpes': np.array(frontier_sharpes),
            'weights': np.array(frontier_weights),
            'gamma_range': gamma_range[:len(frontier_returns)]
        }
    
    def backtest_rebalancing(
        self,
        mu_history: np.ndarray,
        Sigma_history: np.ndarray,
        B_history: np.ndarray,
        returns_realized: np.ndarray,
        rebalance_frequency: int = 20
    ) -> Dict:
        """
        Backtest portfolio with periodic rebalancing
        
        Args:
            mu_history: Expected returns over time (T, N)
            Sigma_history: Covariance matrices over time (T, N, N)
            B_history: Macro betas over time (T, N, K)
            returns_realized: Realized returns (T, N)
            rebalance_frequency: Rebalance every N periods
        
        Returns:
            Dict with backtest results
        """
        T, N = mu_history.shape
        
        portfolio_values = [1.0]
        weights_history = []
        turnover_history = []
        
        w_current = np.ones(N) / N  # Start equal-weighted
        
        for t in range(T):
            # Rebalance if needed
            if t % rebalance_frequency == 0:
                result = self.optimize(
                    mu_history[t],
                    Sigma_history[t],
                    B_history[t],
                    w_prev=w_current
                )
                
                if result['success']:
                    w_new = result['weights']
                    turnover = np.sum(np.abs(w_new - w_current))
                    
                    w_current = w_new
                    weights_history.append(w_current)
                    turnover_history.append(turnover)
            
            # Compute portfolio return
            portfolio_return = w_current @ returns_realized[t]
            portfolio_values.append(portfolio_values[-1] * (1 + portfolio_return))
        
        portfolio_values = np.array(portfolio_values)
        
        # Compute statistics
        total_return = portfolio_values[-1] - 1
        returns = np.diff(portfolio_values) / portfolio_values[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        max_dd = np.max(np.maximum.accumulate(portfolio_values) - portfolio_values) / np.maximum.accumulate(portfolio_values).max()
        
        return {
            'portfolio_values': portfolio_values,
            'total_return': total_return,
            'sharpe': sharpe,
            'max_drawdown': max_dd,
            'avg_turnover': np.mean(turnover_history) if turnover_history else 0,
            'weights_history': weights_history
        }
