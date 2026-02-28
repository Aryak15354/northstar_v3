"""Bayesian hyperparameter optimization with safe fallback."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

import random


class BayesianOptimizer:
    """Optimize objective(params) -> float (lower is better)."""

    def __init__(self, n_calls: int = 20, random_state: int = 42, strict_gp_only: bool = False):
        self.n_calls = int(max(5, n_calls))
        self.random_state = int(random_state)
        self.strict_gp_only = bool(strict_gp_only)
        random.seed(self.random_state)

    @staticmethod
    def _sample(space: Dict[str, Tuple[float, float, str]]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for k, spec in space.items():
            lo, hi, kind = spec
            if kind == "int":
                params[k] = int(random.randint(int(lo), int(hi)))
            elif kind == "log_float":
                import math

                u = random.uniform(math.log(max(lo, 1e-12)), math.log(max(hi, 1e-12)))
                params[k] = float(math.exp(u))
            else:
                params[k] = float(random.uniform(float(lo), float(hi)))
        return params

    def optimize(
        self,
        objective: Callable[[Dict[str, Any]], float],
        space: Dict[str, Tuple[float, float, str]],
    ) -> Dict[str, Any]:
        try:
            from skopt import gp_minimize
            from skopt.space import Integer, Real

            keys = list(space.keys())
            dims: List[Any] = []
            for k in keys:
                lo, hi, kind = space[k]
                if kind == "int":
                    dims.append(Integer(int(lo), int(hi), name=k))
                elif kind == "log_float":
                    dims.append(Real(float(lo), float(hi), prior="log-uniform", name=k))
                else:
                    dims.append(Real(float(lo), float(hi), name=k))

            def _obj(x):
                params = {k: x[i] for i, k in enumerate(keys)}
                return float(objective(params))

            res = gp_minimize(_obj, dims, n_calls=self.n_calls, random_state=self.random_state)
            best = {k: res.x[i] for i, k in enumerate(keys)}
            return {
                "optimizer": "gp_minimize",
                "best_params": best,
                "best_objective": float(res.fun),
                "n_calls": int(self.n_calls),
            }
        except Exception as exc:
            if self.strict_gp_only:
                raise RuntimeError(f"bayesian_optimizer_gp_unavailable:{exc}") from exc
            best_params = None
            best_score = float("inf")
            history = []
            for _ in range(self.n_calls):
                params = self._sample(space)
                score = float(objective(params))
                history.append({"params": params, "objective": score})
                if score < best_score:
                    best_score = score
                    best_params = params

            return {
                "optimizer": "random_fallback",
                "best_params": best_params or {},
                "best_objective": float(best_score),
                "n_calls": int(self.n_calls),
                "history": history,
            }
