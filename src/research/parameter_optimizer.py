"""Governed parameter proposal engine (Bayesian search, no auto deployment)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from .dataset_manager import DatasetManager
from .hyperopt import BayesianOptimizer
from .model_adapters import LightGBMModel
from .training_pipeline import TrainingPipeline


class ParameterOptimizer:
    """Produces candidate parameter sets for manual review only."""

    def __init__(self) -> None:
        self.search_space = {
            "n_estimators": (120, 420, "int"),
            "learning_rate": (0.005, 0.12, "log_float"),
            "max_depth": (3, 12, "int"),
        }

    def run_analysis(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()

        try:
            dm = DatasetManager(
                config={
                    "target_col": "forward_return_5d",
                    "lookback_days": int(system_state.get("optimizer_lookback_days", 1460) or 1460),
                    "max_tickers": int(system_state.get("optimizer_max_tickers", 120) or 120),
                    "target_horizon_days": 5,
                    "strict_real_data_only": True,
                }
            )
            ds = dm.build_research_dataset()
            pipe = TrainingPipeline(
                train_periods=504,
                valid_periods=63,
                test_periods=63,
                step_periods=42,
                max_windows=4,
            )

            def objective(params: Dict[str, Any]) -> float:
                model = LightGBMModel(params=params)
                out = pipe.run(model=model, dataset=ds)
                agg = out.get("aggregate_metrics", {})
                sharpe = float(agg.get("avg_sharpe", 0.0))
                ic = float(agg.get("ic_mean", 0.0))
                dd = float(agg.get("avg_max_drawdown", 1.0))
                monotonic = float(agg.get("monotonic_pass_rate", 0.0))
                # minimize negative utility
                return float(-(0.9 * sharpe + 0.4 * ic + 0.2 * monotonic - 0.7 * dd))

            opt = BayesianOptimizer(n_calls=int(system_state.get("optimizer_calls", 10) or 10))
            best = opt.optimize(objective=objective, space=self.search_space)

            data = {
                "status": "completed",
                "optimizer": best.get("optimizer"),
                "candidate_count": int(best.get("n_calls", 0)),
                "best_candidate": {
                    "params": best.get("best_params", {}),
                    "objective_score": float(best.get("best_objective", 0.0)),
                },
                "top_candidates": [],
                "requires_manual_approval": True,
            }
        except Exception as exc:
            data = {
                "status": "failed",
                "error": str(exc),
                "candidate_count": 0,
                "best_candidate": None,
                "top_candidates": [],
                "requires_manual_approval": True,
                "actionable": False,
            }

        return {
            "module": "parameter_optimizer",
            "timestamp": now,
            "outputs": [
                {
                    "type": "parameter_search",
                    "actionable": bool(data.get("status") == "completed"),
                    "generated_at": datetime.now().isoformat(),
                    "data": data,
                }
            ],
        }
