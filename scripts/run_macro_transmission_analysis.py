#!/usr/bin/env python3
"""
🧠 RUN MACRO TRANSMISSION ANALYSIS (REAL DATA ONLY)

Production runner for Macro Transmission Engine outputs used by V3:
- current_kalman_betas.parquet
- macro_expected_change.parquet
- macro_adjusted_scores.parquet
- stress_replay_summary.json
- run_metadata.json

Optional:
- bayesian_posterior_summary.parquet (when --run-bayesian and NumPyro/JAX available)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.macro_impact_engine import MacroDataLoader, MacroPreprocessor
from src.macro_transmission_engine import (
    BayesianMacroTransmission,
    BayesianVARForecaster,
    MacroAwareOptimizer,
    MacroAlphaAdjuster,
    MacroStressReplay,
    TimeVaryingBetaKalman,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Macro Transmission Engine (real data only)")
    p.add_argument("--start-date", type=str, default="2019-01-01")
    p.add_argument("--frequency", type=str, default="W", choices=["D", "W", "M"])
    p.add_argument("--max-companies", type=int, default=120)
    p.add_argument("--max-macros", type=int, default=20)
    p.add_argument("--output-dir", type=str, default="data/processed/macro_transmission")
    p.add_argument("--horizon", type=int, default=1, help="Macro forecast horizon")
    p.add_argument("--adjustment-strength", type=float, default=0.35)
    p.add_argument("--score-source", type=str, default="data/processed/cohesive_alpha_feed.parquet")
    p.add_argument("--score-column", type=str, default="cohesive_alpha_score")
    p.add_argument("--run-bayesian", action="store_true", help="Run Bayesian hierarchical layer (heavier)")
    p.add_argument("--bayesian-steps", type=int, default=1200)
    p.add_argument("--bayesian-samples", type=int, default=250)
    p.add_argument("--bayesian-max-companies", type=int, default=40)
    p.add_argument("--bayesian-max-macros", type=int, default=10)
    p.add_argument("--run-jax-kalman", action="store_true", help="Run JAX Kalman summary layer (optional)")
    p.add_argument(
        "--run-stochastic-vol",
        action="store_true",
        help="Run stochastic-volatility Kalman summary layer (optional)",
    )
    p.add_argument(
        "--run-optimizer",
        action="store_true",
        help="Run macro-aware optimizer and emit optimized weights",
    )
    p.add_argument("--tvp-companies", type=int, default=40, help="Company cap for JAX/SV layers")
    p.add_argument("--tvp-macros", type=int, default=8, help="Macro cap for JAX/SV layers")
    p.add_argument(
        "--light-mode",
        action="store_true",
        help="M1-safe mode (caps dimensions, keeps compute bounded)",
    )
    return p.parse_args()


def _select_top_columns(df: pd.DataFrame, max_cols: int) -> pd.DataFrame:
    if df.empty or max_cols <= 0 or len(df.columns) <= max_cols:
        return df
    var_rank = df.var().sort_values(ascending=False)
    top_cols = var_rank.head(max_cols).index.tolist()
    return df[top_cols]


def _select_top_companies(returns_df: pd.DataFrame, max_companies: int) -> pd.DataFrame:
    if returns_df.empty or max_companies <= 0 or len(returns_df.columns) <= max_companies:
        return returns_df
    coverage = returns_df.notna().sum() / max(len(returns_df), 1)
    vol = returns_df.std(skipna=True).replace(0, np.nan)
    score = (coverage.fillna(0.0) * 0.7) + (vol.rank(pct=True).fillna(0.0) * 0.3)
    keep = score.sort_values(ascending=False).head(max_companies).index.tolist()
    return returns_df[keep]


def _load_raw_alpha(score_source: Path, score_col: str) -> tuple[pd.Series, Dict[str, str]]:
    candidate_paths: List[Path] = []
    if score_source:
        candidate_paths.append(score_source)
    candidate_paths.extend(
        [
            Path("data/processed/cohesive_alpha_feed.parquet"),
            Path("data/processed/macro_transmission/macro_adjusted_scores.parquet"),
            Path("data/processed/scores.parquet"),
        ]
    )

    # preserve order, remove duplicates
    deduped: List[Path] = []
    seen = set()
    for p in candidate_paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    preferred_cols = [
        score_col,
        "cohesive_alpha_score",
        "adjusted_alpha",
        "northstar_score",
        "score",
        "raw_alpha",
        "final_score",
    ]

    last_error = "No candidate score source checked"
    for path in deduped:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            if df.empty:
                last_error = f"Score source empty: {path}"
                continue
            if "ticker" not in df.columns:
                last_error = f"Score source missing ticker column: {path}"
                continue
            col = next((c for c in preferred_cols if c in df.columns), None)
            if col is None:
                last_error = f"No supported score column in: {path}"
                continue
            out = df[["ticker", col]].copy()
            out["ticker"] = out["ticker"].astype(str).str.strip()
            out[col] = pd.to_numeric(out[col], errors="coerce")
            out = out.dropna(subset=["ticker", col]).drop_duplicates("ticker", keep="last")
            if out.empty:
                last_error = f"No valid rows after cleaning: {path}"
                continue
            s = out.set_index("ticker")[col]
            s = (s - s.mean()) / (s.std() + 1e-12)
            return s, {"source_path": str(path), "score_column": str(col)}
        except Exception as e:
            last_error = f"Failed reading {path}: {e}"
            continue

    raise ValueError(f"Unable to load raw alpha from candidate sources. Last error: {last_error}")


def _load_portfolio_weights(path: Path = Path("data/processed/portfolio_weights.parquet")) -> Optional[Dict[str, float]]:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty:
        return None
    if "ticker" not in df.columns and "symbol" in df.columns:
        df["ticker"] = df["symbol"].astype(str).map(
            lambda s: s if str(s).endswith(".NS") else f"{s}.NS"
        )
    if "ticker" not in df.columns:
        return None
    wcol = None
    for c in ["weight", "final_weight", "allocation", "w"]:
        if c in df.columns:
            wcol = c
            break
    if wcol is None:
        return None
    out = df[["ticker", wcol]].copy()
    out["ticker"] = out["ticker"].astype(str).str.strip()
    out[wcol] = pd.to_numeric(out[wcol], errors="coerce")
    out = out.dropna(subset=["ticker", wcol])
    out = out[out[wcol] > 0]
    if out.empty:
        return None
    total = float(out[wcol].sum())
    if total <= 0:
        return None
    out[wcol] = out[wcol] / total
    return dict(zip(out["ticker"], out[wcol]))


def _serialize(obj):
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type not serializable: {type(obj)}")


def _select_macro_subset_by_expected(expected_df: pd.DataFrame, max_macros: int) -> List[str]:
    if expected_df is None or expected_df.empty or "macro_variable" not in expected_df.columns:
        return []
    df = expected_df.copy()
    if "expected_change" in df.columns:
        df["expected_change"] = pd.to_numeric(df["expected_change"], errors="coerce")
        df = df.dropna(subset=["expected_change"])
        if not df.empty:
            df = df.assign(_abs=df["expected_change"].abs()).sort_values("_abs", ascending=False)
    cols = df["macro_variable"].astype(str).head(max_macros).tolist()
    return [c for c in cols if c]


def main() -> int:
    args = parse_args()
    if args.light_mode:
        args.max_companies = min(int(args.max_companies), 120)
        args.max_macros = min(int(args.max_macros), 20)
        args.tvp_companies = min(int(args.tvp_companies), 30)
        args.tvp_macros = min(int(args.tvp_macros), 6)
        args.run_bayesian = bool(args.run_bayesian and args.bayesian_max_companies <= 40)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("🧠 MACRO TRANSMISSION ENGINE - PRODUCTION RUN (REAL DATA ONLY)")
    print("=" * 88)
    print(f"Start date: {args.start_date}")
    print(f"Frequency: {args.frequency}")
    print(f"Max companies: {args.max_companies}")
    print(f"Max macros: {args.max_macros}")
    print(f"Output dir: {out_dir}")
    print(f"Run Bayesian: {args.run_bayesian}")
    print(f"Run JAX Kalman: {args.run_jax_kalman}")
    print(f"Run Stochastic Volatility: {args.run_stochastic_vol}")
    print(f"Run Macro Optimizer: {args.run_optimizer}")
    print(f"Light mode: {args.light_mode}")

    # 1) Load + preprocess real data
    loader = MacroDataLoader(target_frequency=args.frequency)
    data = loader.load_all(start_date=args.start_date)
    macro_df_raw = data["macro"]
    returns_df_raw = data["returns"]
    sector_map = data.get("sector_map") or {}
    macro_unit_conversion_log = data.get("macro_unit_conversion_log") or {}
    macro_unit_profile = data.get("macro_unit_profile") or {}

    if macro_df_raw is None or macro_df_raw.empty:
        raise RuntimeError("Macro data unavailable for transmission run")
    if returns_df_raw is None or returns_df_raw.empty:
        raise RuntimeError("Returns data unavailable for transmission run")

    pre = MacroPreprocessor(lags=[0], winsorize_pct=0.01)
    macro_df, _meta = pre.preprocess_macro(
        macro_df_raw,
        make_stationary=True,
        standardize=True,
        winsorize=True,
        construct_lags=False,
    )
    returns_df = pre.preprocess_returns(returns_df_raw)

    common_idx = macro_df.index.intersection(returns_df.index)
    macro_df = macro_df.loc[common_idx].copy()
    returns_df = returns_df.loc[common_idx].copy()

    macro_df = _select_top_columns(macro_df, args.max_macros)
    returns_df = _select_top_companies(returns_df, args.max_companies)

    if macro_df.empty or returns_df.empty:
        raise RuntimeError("No aligned data after preprocessing and filtering")

    print(f"Aligned periods: {len(common_idx)}")
    print(f"Selected macro vars: {len(macro_df.columns)}")
    print(f"Selected companies: {len(returns_df.columns)}")

    # 2) Time-varying beta layer (Kalman)
    kalman = TimeVaryingBetaKalman(Q_scale=0.001, R_scale=0.01)
    kalman_results = kalman.fit_all_companies(
        returns_df,
        macro_df,
        max_companies=args.max_companies,
    )

    beta_rows = []
    for ticker, result in kalman_results.items():
        if not isinstance(result, dict) or "error" in result:
            continue
        try:
            cur = kalman.get_current_beta(ticker)
            traj = result.get("beta_trajectory")
            for macro_var, beta_val in cur.items():
                series = pd.to_numeric(traj[macro_var], errors="coerce") if isinstance(traj, pd.DataFrame) and macro_var in traj.columns else pd.Series(dtype=float)
                tail = series.dropna().tail(52)
                beta_rows.append(
                    {
                        "ticker": ticker,
                        "macro_variable": str(macro_var),
                        "beta": float(beta_val),
                        "beta_mean_52w": float(tail.mean()) if not tail.empty else np.nan,
                        "beta_std_52w": float(tail.std()) if not tail.empty else np.nan,
                        "beta_abs": float(abs(beta_val)),
                    }
                )
        except Exception:
            continue

    beta_df = pd.DataFrame(beta_rows)
    if not beta_df.empty:
        for c in ["beta", "beta_mean_52w", "beta_std_52w", "beta_abs"]:
            if c in beta_df.columns:
                beta_df[c] = pd.to_numeric(beta_df[c], errors="coerce")
        beta_df = beta_df.dropna(subset=["beta"])
    if beta_df.empty:
        raise RuntimeError(
            "Kalman beta output empty/invalid after cleaning; check returns-macro alignment and missing data."
        )
    beta_df.to_parquet(out_dir / "current_kalman_betas.parquet", index=False)
    beta_df.to_csv(out_dir / "current_kalman_betas.csv", index=False)
    print(f"Saved Kalman betas: {len(beta_df)} rows")

    # 3) Forecast layer
    forecaster = BayesianVARForecaster(lags=1, num_samples=250 if args.light_mode else 400)
    fit_result = forecaster.fit(macro_df)
    expected_change = forecaster.get_expected_change(macro_df, horizon=max(1, int(args.horizon)))
    expected_df = pd.DataFrame(
        {
            "macro_variable": expected_change.index.astype(str),
            "expected_change": pd.to_numeric(expected_change.values, errors="coerce"),
            "horizon": int(args.horizon),
            "as_of": pd.Timestamp.utcnow(),
        }
    ).dropna(subset=["expected_change"])
    expected_df.to_parquet(out_dir / "macro_expected_change.parquet", index=False)
    expected_df.to_csv(out_dir / "macro_expected_change.csv", index=False)
    print(f"Saved expected change: {len(expected_df)} macro vars")

    # 4) Macro-adjusted alpha layer
    raw_alpha, raw_alpha_meta = _load_raw_alpha(Path(args.score_source), args.score_column)
    beta_for_adjust = beta_df[["ticker", "macro_variable", "beta"]].copy()
    common_tickers = sorted(set(raw_alpha.index).intersection(set(beta_for_adjust["ticker"].astype(str))))
    if not common_tickers:
        raise RuntimeError("No ticker overlap between raw alpha and macro beta outputs")
    raw_alpha = raw_alpha.loc[common_tickers]
    beta_for_adjust = beta_for_adjust[beta_for_adjust["ticker"].isin(common_tickers)]

    adjuster = MacroAlphaAdjuster(adjustment_strength=float(args.adjustment_strength))
    adjusted = adjuster.adjust_alpha(
        raw_alpha=raw_alpha,
        beta_df=beta_for_adjust,
        expected_macro_change=expected_df.set_index("macro_variable")["expected_change"],
    )
    adjusted["macro_adjustment"] = (
        pd.to_numeric(adjusted["macro_adjustment"], errors="coerce")
        .fillna(0.0)
        .clip(lower=-3.0, upper=3.0)
    )
    adjusted["adjusted_alpha"] = pd.to_numeric(adjusted["raw_alpha"], errors="coerce") + adjusted["macro_adjustment"]
    if adjusted["adjusted_alpha"].isna().all():
        raise RuntimeError("Macro adjusted alpha is fully NaN after adjustment; transmission outputs are unusable.")
    adjusted["adjusted_rank"] = adjusted["adjusted_alpha"].rank(ascending=False, method="average")
    adjusted.to_parquet(out_dir / "macro_adjusted_scores.parquet", index=False)
    adjusted.to_csv(out_dir / "macro_adjusted_scores.csv", index=False)
    print(f"Saved macro-adjusted scores: {len(adjusted)} tickers")

    # 5) Stress replay layer
    stress = MacroStressReplay()
    portfolio_weights = _load_portfolio_weights()
    exp_map = expected_df.set_index("macro_variable")["expected_change"].to_dict()
    std_map = macro_df.std().replace(0, np.nan).fillna(macro_df.std().median() if np.isfinite(macro_df.std().median()) else 1.0).to_dict()

    # Broad adverse: shock opposite to expected direction, scaled by 1 sigma.
    broad_adverse = {}
    for mv in expected_df["macro_variable"].tolist():
        mu = float(exp_map.get(mv, 0.0))
        sd = float(std_map.get(mv, 1.0))
        sign = 1.0 if mu >= 0 else -1.0
        broad_adverse[mv] = -sign * sd
    stress.define_shock("broad_adverse_1sigma", broad_adverse)

    # Liquidity crunch: targeted names if present.
    liquidity_keys = []
    for mv in expected_df["macro_variable"].astype(str).tolist():
        low = mv.lower()
        if any(k in low for k in ["liquid", "money", "credit", "repo", "call", "reserve", "yield", "rate"]):
            liquidity_keys.append(mv)
    liquidity_crunch = {}
    if liquidity_keys:
        for mv in liquidity_keys[:15]:
            liquidity_crunch[mv] = -1.5 * float(std_map.get(mv, 1.0))
    else:
        for mv in expected_df.sort_values("expected_change", key=lambda s: s.abs(), ascending=False)["macro_variable"].head(8):
            liquidity_crunch[mv] = -1.0 * float(std_map.get(mv, 1.0))
    stress.define_shock("liquidity_crunch", liquidity_crunch)

    stress_payload = {"scenarios": {}, "as_of": pd.Timestamp.utcnow()}
    for scenario in ["broad_adverse_1sigma", "liquidity_crunch"]:
        res = stress.replay_shock(scenario, beta_for_adjust, portfolio_weights=portfolio_weights)
        stress_payload["scenarios"][scenario] = {
            "portfolio_impact": res.get("portfolio_impact"),
            "worst_stocks": res.get("worst_stocks", [])[:10],
            "best_stocks": res.get("best_stocks", [])[:10],
        }
    with open(out_dir / "stress_replay_summary.json", "w") as f:
        json.dump(stress_payload, f, indent=2, default=_serialize)
    print("Saved stress replay summary")

    # 6) Optional macro-aware optimizer layer
    optimizer_status: Dict[str, Any] = {"ran": False, "available": True, "error": None}
    if args.run_optimizer:
        try:
            common_opt = sorted(set(adjusted["ticker"].astype(str)).intersection(set(returns_df.columns.astype(str))))
            if len(common_opt) < 10:
                raise RuntimeError("insufficient overlap between adjusted scores and return history for optimization")

            opt_df = adjusted[adjusted["ticker"].isin(common_opt)].copy()
            opt_df["adjusted_alpha"] = pd.to_numeric(opt_df.get("adjusted_alpha"), errors="coerce")
            if opt_df["adjusted_alpha"].isna().all():
                # Fallback to raw alpha if adjusted alpha is entirely missing.
                opt_df["adjusted_alpha"] = pd.to_numeric(opt_df.get("raw_alpha"), errors="coerce")
            opt_df = opt_df.dropna(subset=["adjusted_alpha"]).sort_values("adjusted_alpha", ascending=False)
            common_opt = opt_df["ticker"].astype(str).tolist()

            if not common_opt:
                raise RuntimeError("no adjusted alpha rows available for optimization")

            ret_mat = returns_df[common_opt].apply(pd.to_numeric, errors="coerce")
            ret_mat = ret_mat.dropna(how="all")
            ret_mat = ret_mat.fillna(0.0)
            sigma = ret_mat.cov().values
            # Small diagonal ridge for numerical stability.
            sigma = sigma + np.eye(len(common_opt)) * 1e-6

            mu = (
                opt_df.set_index("ticker")
                .reindex(common_opt)["adjusted_alpha"]
                .astype(float)
                .fillna(0.0)
                .values
            )

            beta_wide = (
                beta_for_adjust.copy()
                .pivot_table(index="ticker", columns="macro_variable", values="beta", aggfunc="mean")
            )
            selected_macro = _select_macro_subset_by_expected(expected_df, max_macros=min(12, beta_wide.shape[1]))
            if not selected_macro:
                selected_macro = list(beta_wide.columns)[: min(12, beta_wide.shape[1])]
            beta_wide = beta_wide.reindex(index=common_opt, columns=selected_macro).fillna(0.0)
            B = beta_wide.values
            beta_target = np.zeros(B.shape[1], dtype=float)

            w_prev_map = _load_portfolio_weights() or {}
            w_prev = np.array([float(w_prev_map.get(t, 0.0)) for t in common_opt], dtype=float)
            if w_prev.sum() > 0:
                w_prev = w_prev / w_prev.sum()
            else:
                w_prev = None

            optimizer = MacroAwareOptimizer(
                gamma=3.0,
                kappa=5.0,
                max_position=0.08,
                max_turnover=0.30 if w_prev is not None else None,
            )
            opt_res = optimizer.optimize(mu=mu, Sigma=sigma, B=B, beta_target=beta_target, w_prev=w_prev, method="auto")
            if not opt_res.get("success", False):
                raise RuntimeError(opt_res.get("error") or opt_res.get("status") or "optimizer failed")

            w_opt = np.array(opt_res["weights"], dtype=float)
            weights_df = pd.DataFrame(
                {
                    "ticker": common_opt,
                    "optimized_weight": w_opt,
                    "previous_weight": (w_prev if w_prev is not None else np.zeros_like(w_opt)),
                }
            )
            weights_df["delta_weight"] = weights_df["optimized_weight"] - weights_df["previous_weight"]
            weights_df = weights_df.sort_values("optimized_weight", ascending=False)
            weights_df.to_parquet(out_dir / "macro_optimized_weights.parquet", index=False)
            weights_df.to_csv(out_dir / "macro_optimized_weights.csv", index=False)

            optimizer_diag = {
                "expected_return": float(opt_res.get("expected_return", 0.0)),
                "risk": float(opt_res.get("risk", 0.0)),
                "sharpe": float(opt_res.get("sharpe", 0.0)),
                "macro_distance": float(opt_res.get("macro_distance", 0.0)),
                "n_active": int(opt_res.get("n_active", 0)),
                "macro_variables_used": selected_macro,
            }
            with open(out_dir / "macro_optimizer_summary.json", "w") as f:
                json.dump(optimizer_diag, f, indent=2, default=_serialize)

            optimizer_status["ran"] = True
            print(f"Saved optimizer outputs: {len(weights_df)} rows")
        except ImportError as e:
            optimizer_status["available"] = False
            optimizer_status["error"] = str(e)
            print(f"Optimizer layer skipped (dependency missing): {e}")
        except Exception as e:
            optimizer_status["error"] = str(e)
            print(f"Optimizer layer failed: {e}")

    # 7) Optional JAX Kalman summary layer
    jax_kalman_status: Dict[str, Any] = {"ran": False, "available": True, "error": None}
    if args.run_jax_kalman:
        try:
            from src.macro_transmission_engine.jax_kalman import JAXKalmanFilterNumPy

            tvp_macros = _select_macro_subset_by_expected(expected_df, max_macros=max(2, int(args.tvp_macros)))
            if not tvp_macros:
                tvp_macros = list(macro_df.columns[: max(2, int(args.tvp_macros))])
            tvp_companies = list(returns_df.columns[: max(5, int(args.tvp_companies))])

            jax_filter = JAXKalmanFilterNumPy(Q_scale=1e-4, R_scale=1e-2)
            jax_rows: List[Dict[str, Any]] = []
            for ticker in tvp_companies:
                frame = pd.concat(
                    [pd.to_numeric(returns_df[ticker], errors="coerce"), macro_df[tvp_macros].apply(pd.to_numeric, errors="coerce")],
                    axis=1,
                ).dropna()
                if len(frame) < 80:
                    continue
                y = frame.iloc[:, 0].values.astype(float)
                X = frame.iloc[:, 1:].values.astype(float)
                res = jax_filter.filter(y, X)
                xf = np.array(res.get("x_filtered"))
                if xf.ndim != 2 or xf.shape[0] == 0:
                    continue
                beta_cur = xf[-1]
                for i, mv in enumerate(tvp_macros):
                    if i < len(beta_cur):
                        jax_rows.append(
                            {
                                "ticker": str(ticker),
                                "macro_variable": str(mv),
                                "beta_jax": float(beta_cur[i]),
                                "beta_jax_abs": float(abs(beta_cur[i])),
                                "obs_used": int(len(frame)),
                            }
                        )

            jax_df = pd.DataFrame(jax_rows)
            if not jax_df.empty:
                jax_df.to_parquet(out_dir / "jax_kalman_betas.parquet", index=False)
                jax_df.to_csv(out_dir / "jax_kalman_betas.csv", index=False)
            jax_kalman_status["ran"] = True
            print(f"Saved JAX Kalman outputs: {len(jax_df)} rows")
        except ImportError as e:
            jax_kalman_status["available"] = False
            jax_kalman_status["error"] = str(e)
            print(f"JAX Kalman layer skipped (dependency missing): {e}")
            # Deterministic fallback from standard Kalman betas so downstream artifacts exist.
            try:
                tvp_companies = list(returns_df.columns[: max(5, int(args.tvp_companies))])
                jax_df = beta_df[beta_df["ticker"].astype(str).isin([str(x) for x in tvp_companies])][
                    ["ticker", "macro_variable", "beta"]
                ].copy()
                if not jax_df.empty:
                    obs_map = {
                        str(tk): int(pd.to_numeric(returns_df[tk], errors="coerce").notna().sum())
                        for tk in tvp_companies
                    }
                    jax_df = jax_df.rename(columns={"beta": "beta_jax"})
                    jax_df["beta_jax_abs"] = jax_df["beta_jax"].abs()
                    jax_df["obs_used"] = jax_df["ticker"].astype(str).map(obs_map).fillna(int(len(common_idx))).astype(int)
                    jax_df.to_parquet(out_dir / "jax_kalman_betas.parquet", index=False)
                    jax_df.to_csv(out_dir / "jax_kalman_betas.csv", index=False)
                    jax_kalman_status["ran"] = True
                    jax_kalman_status["fallback_mode"] = "standard_kalman_projection"
                    print(f"Saved JAX Kalman fallback outputs: {len(jax_df)} rows")
            except Exception as fb_exc:
                jax_kalman_status["fallback_error"] = str(fb_exc)
        except Exception as e:
            jax_kalman_status["error"] = str(e)
            print(f"JAX Kalman layer failed: {e}")

    # 8) Optional stochastic-volatility Kalman summary layer
    sv_status: Dict[str, Any] = {"ran": False, "available": True, "error": None}
    if args.run_stochastic_vol:
        try:
            from src.macro_transmission_engine.stochastic_volatility_kalman import StochasticVolatilityKalmanNumPy

            sv_macros = _select_macro_subset_by_expected(expected_df, max_macros=max(2, int(args.tvp_macros)))
            if not sv_macros:
                sv_macros = list(macro_df.columns[: max(2, int(args.tvp_macros))])
            sv_companies = list(returns_df.columns[: max(5, int(args.tvp_companies))])

            sv_filter = StochasticVolatilityKalmanNumPy(Q_beta_scale=1e-4, Q_h_scale=1e-3, phi=0.95, mu_h=-2.0)
            sv_rows: List[Dict[str, Any]] = []
            sv_beta_rows: List[Dict[str, Any]] = []
            for ticker in sv_companies:
                frame = pd.concat(
                    [pd.to_numeric(returns_df[ticker], errors="coerce"), macro_df[sv_macros].apply(pd.to_numeric, errors="coerce")],
                    axis=1,
                ).dropna()
                if len(frame) < 100:
                    continue
                y = frame.iloc[:, 0].values.astype(float)
                X = frame.iloc[:, 1:].values.astype(float)

                filt = sv_filter.filter(y, X)
                sigma = np.asarray(filt.get("sigma_filtered", []), dtype=float)
                betas = np.asarray(filt.get("beta_filtered", []), dtype=float)
                if sigma.size == 0 or betas.ndim != 2:
                    continue
                sigma_std = float(np.nanstd(sigma)) if sigma.size else 0.0
                # Degeneracy fallback: if latent-vol filter collapses, derive a bounded
                # EWMA realized-vol path from returns so summary statistics remain informative.
                if (not np.isfinite(sigma_std)) or sigma_std < 1e-8:
                    y_series = pd.Series(y, index=frame.index)
                    span = int(max(12, min(52, max(12, len(y_series) // 4))))
                    sigma_fallback = (
                        y_series.ewm(span=span, adjust=False).std(bias=False)
                        .replace([np.inf, -np.inf], np.nan)
                        .fillna(float(y_series.std(ddof=1) or 0.0))
                    )
                    sigma = sigma_fallback.to_numpy(dtype=float)
                    sigma_std = float(np.nanstd(sigma)) if len(sigma) else 0.0
                reg = sv_filter.detect_volatility_regimes(filt)
                sv_rows.append(
                    {
                        "ticker": str(ticker),
                        "sigma_current": float(sigma[-1]),
                        "sigma_mean": float(np.nanmean(sigma)),
                        "sigma_std": float(sigma_std),
                        "pct_high_vol": float(reg.get("pct_high_vol", np.nan)),
                        "pct_low_vol": float(reg.get("pct_low_vol", np.nan)),
                        "obs_used": int(len(frame)),
                    }
                )
                beta_cur = betas[-1]
                for i, mv in enumerate(sv_macros):
                    if i < len(beta_cur):
                        sv_beta_rows.append(
                            {
                                "ticker": str(ticker),
                                "macro_variable": str(mv),
                                "beta_sv": float(beta_cur[i]),
                                "beta_sv_abs": float(abs(beta_cur[i])),
                            }
                        )

            sv_df = pd.DataFrame(sv_rows)
            sv_beta_df = pd.DataFrame(sv_beta_rows)
            if not sv_df.empty:
                sv_df.to_parquet(out_dir / "stochastic_volatility_summary.parquet", index=False)
                sv_df.to_csv(out_dir / "stochastic_volatility_summary.csv", index=False)
            if not sv_beta_df.empty:
                sv_beta_df.to_parquet(out_dir / "stochastic_volatility_betas.parquet", index=False)
                sv_beta_df.to_csv(out_dir / "stochastic_volatility_betas.csv", index=False)
            sv_status["ran"] = True
            print(f"Saved stochastic-volatility outputs: {len(sv_df)} summaries, {len(sv_beta_df)} betas")
        except ImportError as e:
            sv_status["available"] = False
            sv_status["error"] = str(e)
            print(f"Stochastic-vol layer skipped (dependency missing): {e}")
            # Deterministic fallback: EWMA realized volatility summaries + beta projection.
            try:
                sv_companies = list(returns_df.columns[: max(5, int(args.tvp_companies))])
                sv_rows: List[Dict[str, Any]] = []
                for ticker in sv_companies:
                    s = pd.to_numeric(returns_df[ticker], errors="coerce").dropna()
                    if len(s) < 30:
                        continue
                    sigma_series = (
                        s.ewm(span=20, adjust=False)
                        .std(bias=False)
                        .replace([np.inf, -np.inf], np.nan)
                        .dropna()
                    )
                    if sigma_series.empty:
                        continue
                    mu = float(sigma_series.mean())
                    sd = float(sigma_series.std(ddof=0))
                    z = (sigma_series - mu) / (sd + 1e-12)
                    sv_rows.append(
                        {
                            "ticker": str(ticker),
                            "sigma_current": float(sigma_series.iloc[-1]),
                            "sigma_mean": float(mu),
                            "sigma_std": float(sd),
                            "pct_high_vol": float((z > 1.5).mean()),
                            "pct_low_vol": float((z < -1.5).mean()),
                            "obs_used": int(len(s)),
                        }
                    )
                sv_df = pd.DataFrame(sv_rows)
                if not sv_df.empty:
                    sv_df.to_parquet(out_dir / "stochastic_volatility_summary.parquet", index=False)
                    sv_df.to_csv(out_dir / "stochastic_volatility_summary.csv", index=False)
                sv_beta_df = beta_df[beta_df["ticker"].astype(str).isin([str(x) for x in sv_companies])][
                    ["ticker", "macro_variable", "beta"]
                ].copy()
                if not sv_beta_df.empty:
                    sv_beta_df = sv_beta_df.rename(columns={"beta": "beta_sv"})
                    sv_beta_df["beta_sv_abs"] = sv_beta_df["beta_sv"].abs()
                    sv_beta_df.to_parquet(out_dir / "stochastic_volatility_betas.parquet", index=False)
                    sv_beta_df.to_csv(out_dir / "stochastic_volatility_betas.csv", index=False)
                sv_status["ran"] = bool((not sv_df.empty) or (not sv_beta_df.empty))
                sv_status["fallback_mode"] = "ewma_realized_volatility"
                if sv_status["ran"]:
                    print(
                        f"Saved stochastic-vol fallback outputs: {len(sv_df)} summaries, {len(sv_beta_df)} betas"
                    )
            except Exception as fb_exc:
                sv_status["fallback_error"] = str(fb_exc)
        except Exception as e:
            sv_status["error"] = str(e)
            print(f"Stochastic-vol layer failed: {e}")

    # 9) Optional Bayesian hierarchical layer (heavier)
    bayesian_status = {"ran": False, "available": True, "error": None}
    if args.run_bayesian:
        try:
            b_companies = min(int(args.bayesian_max_companies), len(returns_df.columns))
            b_macros = min(int(args.bayesian_max_macros), len(macro_df.columns))
            returns_b = returns_df.iloc[:, :b_companies].copy()
            macro_b = macro_df.iloc[:, :b_macros].copy()
            bayes = BayesianMacroTransmission(
                inference_method="svi",
                num_samples=int(args.bayesian_samples),
                use_gpu=False,
            )
            fit = bayes.fit_svi(
                returns_df=returns_b,
                macro_df=macro_b,
                sector_map=sector_map,
                num_steps=int(args.bayesian_steps),
            )
            summary = fit.get("summary")
            if isinstance(summary, pd.DataFrame) and not summary.empty:
                summary.to_parquet(out_dir / "bayesian_posterior_summary.parquet", index=False)
                summary.to_csv(out_dir / "bayesian_posterior_summary.csv", index=False)
            high = bayes.get_high_conviction_relationships(threshold=0.90)
            if isinstance(high, pd.DataFrame) and not high.empty:
                high.to_parquet(out_dir / "bayesian_high_conviction.parquet", index=False)
                high.to_csv(out_dir / "bayesian_high_conviction.csv", index=False)
            bayesian_status["ran"] = True
            print("Saved Bayesian artifacts")
        except ImportError as e:
            bayesian_status["available"] = False
            bayesian_status["error"] = str(e)
            print(f"Bayesian layer skipped (dependency missing): {e}")
        except Exception as e:
            bayesian_status["error"] = str(e)
            print(f"Bayesian layer failed: {e}")

    # 10) Metadata
    conversion_log_path = out_dir / "macro_unit_conversion_log.json"
    unit_profile_path = out_dir / "macro_unit_profile.json"
    with open(conversion_log_path, "w", encoding="utf-8") as f:
        json.dump(dict(macro_unit_conversion_log), f, indent=2, default=_serialize)
    with open(unit_profile_path, "w", encoding="utf-8") as f:
        json.dump(dict(macro_unit_profile), f, indent=2, default=_serialize)

    metadata = {
        "run_date": datetime.now().isoformat(),
        "config": vars(args),
        "data_coverage": {
            "start": str(common_idx.min()) if len(common_idx) else None,
            "end": str(common_idx.max()) if len(common_idx) else None,
            "observations": int(len(common_idx)),
            "companies_selected": int(len(returns_df.columns)),
            "macro_selected": int(len(macro_df.columns)),
        },
        "raw_alpha_input": raw_alpha_meta,
        "unit_handling": {
            "percent_conversions": int(len(macro_unit_conversion_log)),
            "conversion_log_sample": dict(list(macro_unit_conversion_log.items())[:25]),
            "conversion_log_path": str(conversion_log_path),
            "unit_profile_path": str(unit_profile_path),
            "unit_family_counts": (
                pd.Series(list(macro_unit_profile.values())).value_counts().to_dict()
                if isinstance(macro_unit_profile, dict) and macro_unit_profile
                else {}
            ),
        },
        "forecast_fit": {
            "method": fit_result.get("method") if isinstance(fit_result, dict) else None,
            "diagnostics": fit_result.get("diagnostics") if isinstance(fit_result, dict) else {},
        },
        "artifacts": {
            "current_kalman_betas": str(out_dir / "current_kalman_betas.parquet"),
            "macro_expected_change": str(out_dir / "macro_expected_change.parquet"),
            "macro_adjusted_scores": str(out_dir / "macro_adjusted_scores.parquet"),
            "stress_replay_summary": str(out_dir / "stress_replay_summary.json"),
            "macro_optimizer_weights": str(out_dir / "macro_optimized_weights.parquet"),
            "macro_optimizer_summary": str(out_dir / "macro_optimizer_summary.json"),
            "jax_kalman_betas": str(out_dir / "jax_kalman_betas.parquet"),
            "stochastic_volatility_summary": str(out_dir / "stochastic_volatility_summary.parquet"),
            "stochastic_volatility_betas": str(out_dir / "stochastic_volatility_betas.parquet"),
        },
        "optimizer": optimizer_status,
        "jax_kalman": jax_kalman_status,
        "stochastic_volatility": sv_status,
        "bayesian": bayesian_status,
        "real_data_only": True,
    }
    with open(out_dir / "run_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=_serialize)

    print("=" * 88)
    print("✅ MACRO TRANSMISSION RUN COMPLETE")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
