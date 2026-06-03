"""Research certification evaluator for institutional hardening gates."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import resource
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .formula_lineage import (
    build_belief_layer_diagnostics,
    build_formula_lineage_report,
    build_gate_overfitting_shadow_audit,
    build_macro_unit_integrity,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _hash_jsonable(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sharpe_like(returns: np.ndarray, periods_per_year: int = 252) -> float:
    arr = np.asarray(returns, dtype=float).reshape(-1)
    if len(arr) < 2:
        return 0.0
    mu = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1))
    if sd <= 1e-12:
        return 0.0
    return float(mu * np.sqrt(float(max(1, periods_per_year))) / sd)


def _max_drawdown(returns: np.ndarray) -> float:
    arr = np.asarray(returns, dtype=float).reshape(-1)
    if len(arr) == 0:
        return 0.0
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    curve = np.cumprod(1.0 + np.clip(arr, -0.999, 1.0))
    peak = np.maximum.accumulate(curve)
    dd = curve / np.maximum(peak, 1e-12) - 1.0
    return float(abs(np.min(dd)))


def _normalize_entropy(weights: Sequence[float]) -> float:
    w = np.asarray(weights, dtype=float).reshape(-1)
    if len(w) == 0:
        return 0.0
    w = np.abs(np.nan_to_num(w, nan=0.0, posinf=0.0, neginf=0.0))
    s = float(np.sum(w))
    if s <= 1e-12:
        return 0.0
    p = w / s
    p = np.clip(p, 1e-12, 1.0)
    h = -float(np.sum(p * np.log(p)))
    hmax = float(np.log(len(p)))
    return float(h / max(hmax, 1e-12))


def _rolling_param_drift(history: Sequence[Mapping[str, Any]]) -> float:
    rows = [dict(x.get("params", {})) for x in history if isinstance(x, Mapping)]
    if len(rows) < 2:
        return 0.0
    drifts: List[float] = []
    for prev, cur in zip(rows[:-1], rows[1:]):
        keys = sorted(set(prev.keys()) | set(cur.keys()))
        if not keys:
            continue
        rels: List[float] = []
        for k in keys:
            a = _safe_float(prev.get(k, 0.0))
            b = _safe_float(cur.get(k, 0.0))
            denom = max(1e-8, abs(a), abs(b), 1.0)
            rels.append(abs(b - a) / denom)
        if rels:
            drifts.append(float(np.mean(rels)))
    return float(np.mean(drifts)) if drifts else 0.0


def _bootstrap_sharpe_bounds(
    returns: np.ndarray,
    *,
    n_boot: int = 300,
    periods_per_year: int = 252,
    random_state: int = 42,
) -> Tuple[float, float, float]:
    arr = np.asarray(returns, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 30:
        s = _sharpe_like(arr, periods_per_year=periods_per_year)
        return s, s, 0.0
    rs = np.random.RandomState(int(random_state))
    vals: List[float] = []
    for _ in range(int(max(50, n_boot))):
        idx = rs.randint(0, len(arr), size=len(arr))
        sample = arr[idx]
        vals.append(_sharpe_like(sample, periods_per_year=periods_per_year))
    p05 = float(np.percentile(vals, 5))
    p95 = float(np.percentile(vals, 95))
    return p05, p95, float(p95 - p05)


def _block_bootstrap_dd_p95(
    returns: np.ndarray,
    *,
    n_boot: int = 250,
    block: int = 5,
    random_state: int = 42,
) -> float:
    arr = np.asarray(returns, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 30:
        return _max_drawdown(arr)
    rs = np.random.RandomState(int(random_state))
    block = int(max(2, block))
    out: List[float] = []
    n = len(arr)
    starts = np.arange(0, max(1, n - block + 1))
    for _ in range(int(max(40, n_boot))):
        segs: List[np.ndarray] = []
        while sum(len(s) for s in segs) < n:
            st = int(rs.choice(starts))
            segs.append(arr[st : st + block])
        sample = np.concatenate(segs)[:n]
        out.append(_max_drawdown(sample))
    return float(np.percentile(out, 95))


def _weekly_monthly_returns(series: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
    if series.empty:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    if not isinstance(s.index, pd.DatetimeIndex):
        try:
            s.index = pd.to_datetime(s.index, errors="coerce")
        except Exception:
            return np.asarray([], dtype=float), np.asarray([], dtype=float)
    s = s.dropna()
    if s.empty:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    wk = (1.0 + s).resample("W-FRI").prod() - 1.0
    mo = (1.0 + s).resample("ME").prod() - 1.0
    return wk.to_numpy(dtype=float), mo.to_numpy(dtype=float)


@dataclass
class CertificationContext:
    outputs: List[Dict[str, Any]]
    model_results: Dict[str, Dict[str, Any]]
    best_model: str
    best_payload: Dict[str, Any]
    param_payload: Dict[str, Any]
    cap_metrics: Dict[str, Any]
    dataset_metadata: Dict[str, Any]
    dataset_frame: pd.DataFrame
    portfolio_cfg: Dict[str, Any]
    freeze_active: bool
    weekend_run: bool
    started_at: datetime
    completed_at: datetime
    system_state: Dict[str, Any]


class CertificationEvaluator:
    """Compute integrity blocks and enforce critical research governance gates."""

    def __init__(self, project_root: Path, config: Optional[Dict[str, Any]] = None):
        self.project_root = Path(project_root)
        self.config = dict(config or {})
        cert_cfg = dict(self.config.get("certification", {}))
        self.cert_cfg = cert_cfg
        mode = str(cert_cfg.get("mode", "enforce") or "enforce").strip().lower()
        self.mode = mode if mode in {"enforce", "shadow"} else "enforce"
        self.enabled = bool(cert_cfg.get("enabled", True))
        self.state_path = self.project_root / str(
            cert_cfg.get("state_path", "data/results/research/state/certification_state.json")
        )
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {
                "updated_at": None,
                "turnover_zero_streak": 0,
                "allocation_l1_high_streak": 0,
                "advisory_streaks": {},
                "best_param_history": {},
                "last_blend_weights": {},
                "last_dependency_hash": None,
                "last_runtime_hash": None,
                "replay_baselines": {},
                "burn_in": {
                    "consecutive_pass_cycles": 0,
                    "observed_volatility_regimes": [],
                    "certification_passed": False,
                },
            }
        try:
            payload = json.loads(self.state_path.read_text())
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return {}

    def _save_state(self) -> None:
        self.state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.state_path.write_text(json.dumps(self.state, indent=2, sort_keys=True, default=str))

    @staticmethod
    def _extract_output(outputs: Sequence[Dict[str, Any]], otype: str) -> List[Dict[str, Any]]:
        otype_l = str(otype).strip().lower()
        out: List[Dict[str, Any]] = []
        for row in outputs:
            if not isinstance(row, dict):
                continue
            if str(row.get("type", "")).strip().lower() == otype_l:
                data = row.get("data")
                if isinstance(data, dict):
                    out.append(data)
                else:
                    out.append({})
        return out

    def _model_return_series(self, model_results: Mapping[str, Mapping[str, Any]]) -> Dict[str, pd.Series]:
        out: Dict[str, pd.Series] = {}
        for model_name, payload in model_results.items():
            if not isinstance(payload, Mapping):
                continue
            rows = payload.get("portfolio_return_series", [])
            if not isinstance(rows, list) or not rows:
                continue
            df = pd.DataFrame(rows)
            if "date" not in df.columns or "return" not in df.columns:
                continue
            d = pd.to_datetime(df["date"], errors="coerce")
            r = pd.to_numeric(df["return"], errors="coerce")
            s = pd.Series(r.to_numpy(dtype=float), index=d)
            s = s[~s.index.isna()].dropna()
            if s.empty:
                continue
            s = s.groupby(level=0).mean().sort_index()
            out[str(model_name)] = s
        return out

    def _dependency_lock(self) -> Dict[str, Any]:
        req_path = self.project_root / "requirements.txt"
        lock_hash = ""
        if req_path.exists():
            lock_hash = hashlib.sha256(req_path.read_bytes()).hexdigest()

        runtime_parts: List[str] = []
        try:
            import importlib.metadata as md

            pkgs = ["numpy", "pandas", "scikit-learn", "xgboost", "lightgbm", "catboost", "hmmlearn", "torch"]
            for p in pkgs:
                try:
                    runtime_parts.append(f"{p}=={md.version(p)}")
                except Exception:
                    runtime_parts.append(f"{p}==missing")
        except Exception:
            runtime_parts.append("metadata_unavailable")

        runtime_hash = hashlib.sha256("|".join(runtime_parts).encode("utf-8")).hexdigest()
        prev_lock = str(self.state.get("last_dependency_hash", "") or "")
        prev_runtime = str(self.state.get("last_runtime_hash", "") or "")
        changed = bool((prev_lock and prev_lock != lock_hash) or (prev_runtime and prev_runtime != runtime_hash))
        approved_window = bool(self.cert_cfg.get("approved_dependency_change_window", False))
        passed = bool((not changed) or approved_window)

        self.state["last_dependency_hash"] = lock_hash
        self.state["last_runtime_hash"] = runtime_hash
        return {
            "lock_hash": lock_hash,
            "runtime_hash": runtime_hash,
            "changed": bool(changed),
            "approved_change_window": bool(approved_window),
            "passed": bool(passed),
        }

    def _resource_guard(self, started_at: datetime, completed_at: datetime) -> Dict[str, Any]:
        runtime_sec = float(max(0.0, (completed_at - started_at).total_seconds()))
        max_runtime = float(self.cert_cfg.get("max_cycle_runtime_sec", 2400.0))
        max_mem_mb = float(self.cert_cfg.get("max_peak_rss_mb", 4096.0))
        max_threads = int(self.cert_cfg.get("max_threads", 1))

        rss_raw = 0.0
        try:
            rss_raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except Exception:
            rss_raw = 0.0
        # macOS reports bytes; Linux reports KB. Detect by magnitude.
        peak_rss_mb = float(rss_raw / (1024.0 * 1024.0)) if rss_raw > 10_000_000 else float(rss_raw / 1024.0)

        env_threads = [
            _safe_int(os.getenv("OMP_NUM_THREADS", "1"), 1),
            _safe_int(os.getenv("OPENBLAS_NUM_THREADS", "1"), 1),
            _safe_int(os.getenv("MKL_NUM_THREADS", "1"), 1),
            _safe_int(os.getenv("NUMEXPR_NUM_THREADS", "1"), 1),
        ]
        thread_cap_respected = bool(max(env_threads) <= int(max(1, max_threads)))
        passed = bool((runtime_sec <= max_runtime) and (peak_rss_mb <= max_mem_mb) and thread_cap_respected)
        return {
            "cycle_runtime_sec": runtime_sec,
            "peak_rss_mb": peak_rss_mb,
            "thread_cap_respected": thread_cap_respected,
            "passed": passed,
        }

    def _data_provenance(self, dataset_metadata: Mapping[str, Any]) -> Dict[str, Any]:
        universe_hash = str(dataset_metadata.get("universe_hash", "") or "")
        price_hash = str(dataset_metadata.get("price_hash", "") or "")
        feature_hash = str(dataset_metadata.get("feature_hash", "") or "")
        label_hash = str(dataset_metadata.get("label_hash", "") or "")
        passed = all(bool(x) for x in [universe_hash, price_hash, feature_hash, label_hash])
        return {
            "universe_hash": universe_hash,
            "price_hash": price_hash,
            "feature_hash": feature_hash,
            "label_hash": label_hash,
            "passed": bool(passed),
        }

    def _replay_certification(
        self,
        cycle_id: str,
        outputs: Sequence[Dict[str, Any]],
        provenance: Mapping[str, Any],
        system_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        replay_seed = int(self.config.get("random_state", 42))
        output_hash = _hash_jsonable(outputs)
        prov_hash = _hash_jsonable(provenance)
        replay_baselines = self.state.get("replay_baselines", {})
        if not isinstance(replay_baselines, MutableMapping):
            replay_baselines = {}
        controlled_replay = bool(system_state.get("controlled_replay", False))
        replay_cycle_id = str(system_state.get("replay_cycle_id", cycle_id) or cycle_id)
        baseline = replay_baselines.get(replay_cycle_id, {})
        output_hash_match = True
        prov_hash_match = True
        if controlled_replay:
            output_hash_match = bool((baseline or {}).get("output_hash", "") == output_hash)
            prov_hash_match = bool((baseline or {}).get("provenance_hash", "") == prov_hash)
        else:
            replay_baselines[str(cycle_id)] = {
                "output_hash": str(output_hash),
                "provenance_hash": str(prov_hash),
                "seed": int(replay_seed),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            # Bound on-disk state growth.
            keep = int(max(10, int(self.cert_cfg.get("replay_baseline_keep", 80))))
            keys = sorted(replay_baselines.keys())
            if len(keys) > keep:
                for k in keys[: len(keys) - keep]:
                    replay_baselines.pop(k, None)
        self.state["replay_baselines"] = dict(replay_baselines)
        passed = bool(output_hash_match and prov_hash_match)
        return {
            "cycle_id": str(replay_cycle_id),
            "replay_seed": int(replay_seed),
            "output_hash_match": bool(output_hash_match),
            "provenance_hash_match": bool(prov_hash_match),
            "passed": bool(passed),
        }

    def _universe_integrity(
        self,
        frame: pd.DataFrame,
        dataset_metadata: Mapping[str, Any],
    ) -> Dict[str, Any]:
        membership_drift_rate = _safe_float(dataset_metadata.get("membership_drift_rate", 0.0), 0.0)
        delisted_assets_handled = _safe_float(dataset_metadata.get("delisted_assets_handled", 1.0), 1.0)
        forward_inclusion_check = bool(dataset_metadata.get("forward_inclusion_check", True))

        if (
            ("membership_drift_rate" not in dataset_metadata)
            or ("delisted_assets_handled" not in dataset_metadata)
            or ("forward_inclusion_check" not in dataset_metadata)
        ):
            if frame.empty or "date" not in frame.columns or "ticker" not in frame.columns:
                membership_drift_rate = 1.0
                delisted_assets_handled = 0.0
                forward_inclusion_check = False
            else:
                work = frame[["date", "ticker"]].copy()
                work["date"] = pd.to_datetime(work["date"], errors="coerce")
                work["ticker"] = work["ticker"].astype(str)
                work = work.dropna().sort_values("date")
                if work.empty:
                    membership_drift_rate = 1.0
                    delisted_assets_handled = 0.0
                    forward_inclusion_check = False
                else:
                    by_date = work.groupby("date")["ticker"].apply(lambda x: set(x.astype(str))).sort_index()
                    drifts: List[float] = []
                    prev: Optional[set[str]] = None
                    for cur in by_date:
                        if prev is not None:
                            union = len(prev.union(cur))
                            inter = len(prev.intersection(cur))
                            drifts.append(1.0 - (float(inter) / float(max(1, union))))
                        prev = cur
                    membership_drift_rate = float(np.mean(drifts)) if drifts else 0.0
                    span = work.groupby("ticker")["date"].agg(["min", "max"])
                    gmax = pd.to_datetime(work["date"]).max()
                    delisted_like = span["max"] < gmax
                    delisted_assets_handled = float(delisted_like.mean()) if len(delisted_like) else 1.0
                    if delisted_assets_handled < 0.01:
                        delisted_assets_handled = 1.0
                    first_dates = span["min"].sort_values()
                    if len(first_dates) > 5:
                        q90 = pd.to_datetime(first_dates).quantile(0.90)
                        late_ratio = float((pd.to_datetime(first_dates) >= q90).mean())
                        forward_inclusion_check = bool(late_ratio < 0.25)
                    else:
                        forward_inclusion_check = True

        passed = bool(
            bool(forward_inclusion_check)
            and (float(delisted_assets_handled) >= float(self.cert_cfg.get("delisted_assets_min", 0.99)))
        )
        return {
            "membership_drift_rate": float(membership_drift_rate),
            "delisted_assets_handled": float(delisted_assets_handled),
            "forward_inclusion_check": bool(forward_inclusion_check),
            "passed": bool(passed),
        }

    def _strategy_correlation_check(self, model_results: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
        series_map = self._model_return_series(model_results)
        names = sorted(series_map.keys())
        max_corr = 0.0
        duplicated: List[Dict[str, Any]] = []
        overlap_persistence_threshold = float(self.cert_cfg.get("overlap_persistence_threshold", 0.70))
        overlap_threshold = float(self.cert_cfg.get("max_holdings_overlap", 0.95))
        high_overlap_share_max = 0.0

        snapshots: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for model_name, payload in model_results.items():
            rows = payload.get("rebalance_snapshots", []) if isinstance(payload, Mapping) else []
            snap_map: Dict[str, Dict[str, Any]] = {}
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, Mapping):
                        continue
                    dt = str(row.get("date", "")).strip()
                    if not dt:
                        continue
                    tickers = row.get("tickers", [])
                    weights = row.get("weights", {})
                    if not isinstance(tickers, list):
                        tickers = []
                    if not isinstance(weights, Mapping):
                        weights = {}
                    snap_map[dt] = {
                        "tickers": {str(x) for x in tickers},
                        "weights": {str(k): _safe_float(v, 0.0) for k, v in dict(weights).items()},
                    }
            snapshots[str(model_name)] = snap_map

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = series_map[names[i]]
                b = series_map[names[j]]
                idx = a.index.intersection(b.index)
                if len(idx) < 30:
                    continue
                corr = float(a.loc[idx].corr(b.loc[idx]))
                if not np.isfinite(corr):
                    corr = 0.0
                max_corr = max(max_corr, corr)
                if corr > float(self.cert_cfg.get("max_pairwise_corr", 0.99)):
                    duplicated.append(
                        {
                            "strategy_a": names[i],
                            "strategy_b": names[j],
                            "return_corr": corr,
                        }
                    )

        max_holdings_overlap = 0.0
        max_weight_sim = 0.0
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a_map = snapshots.get(names[i], {})
                b_map = snapshots.get(names[j], {})
                if not a_map or not b_map:
                    continue
                dates = sorted(set(a_map.keys()).intersection(set(b_map.keys())))
                if not dates:
                    continue
                high_overlap_hits = 0
                pair_max_overlap = 0.0
                pair_max_sim = 0.0
                for dt in dates:
                    a_row = a_map.get(dt, {})
                    b_row = b_map.get(dt, {})
                    a_t = set(a_row.get("tickers", set()))
                    b_t = set(b_row.get("tickers", set()))
                    if not a_t or not b_t:
                        continue
                    overlap = float(len(a_t.intersection(b_t)) / float(max(1, min(len(a_t), len(b_t)))))
                    pair_max_overlap = max(pair_max_overlap, overlap)
                    if overlap > overlap_threshold:
                        high_overlap_hits += 1

                    keys = sorted(a_t.union(b_t))
                    a_w = np.asarray([_safe_float((a_row.get("weights", {}) or {}).get(k, 0.0), 0.0) for k in keys], dtype=float)
                    b_w = np.asarray([_safe_float((b_row.get("weights", {}) or {}).get(k, 0.0), 0.0) for k in keys], dtype=float)
                    na = float(np.linalg.norm(a_w))
                    nb = float(np.linalg.norm(b_w))
                    if na > 1e-12 and nb > 1e-12:
                        sim = float(np.dot(a_w / na, b_w / nb))
                        pair_max_sim = max(pair_max_sim, sim)
                if dates:
                    high_share = float(high_overlap_hits) / float(max(1, len(dates)))
                    high_overlap_share_max = max(high_overlap_share_max, high_share)
                    max_holdings_overlap = max(max_holdings_overlap, pair_max_overlap)
                    max_weight_sim = max(max_weight_sim, pair_max_sim)
                    if high_share >= overlap_persistence_threshold and pair_max_overlap > overlap_threshold:
                        duplicated.append(
                            {
                                "strategy_a": names[i],
                                "strategy_b": names[j],
                                "return_corr": float(
                                    series_map[names[i]].corr(series_map[names[j]])
                                    if len(series_map[names[i]].index.intersection(series_map[names[j]].index)) >= 3
                                    else 0.0
                                ),
                                "holdings_overlap_share": high_share,
                                "max_holdings_overlap": pair_max_overlap,
                            }
                        )

        passed = bool(
            (max_corr <= float(self.cert_cfg.get("max_pairwise_corr", 0.99)))
            and (max_holdings_overlap <= overlap_threshold or high_overlap_share_max < overlap_persistence_threshold)
        )
        return {
            "max_pairwise_corr": float(max_corr),
            "duplicated_strategies": duplicated,
            "max_holdings_overlap": float(max_holdings_overlap),
            "high_overlap_share_max": float(high_overlap_share_max),
            "max_weight_vector_similarity": float(max_weight_sim),
            "passed": bool(passed),
        }

    def _portfolio_integrity(
        self,
        best_payload: Mapping[str, Any],
        portfolio_cfg: Mapping[str, Any],
    ) -> Dict[str, Any]:
        agg = best_payload.get("aggregate_metrics", {}) if isinstance(best_payload, Mapping) else {}
        snapshots = best_payload.get("rebalance_snapshots", []) if isinstance(best_payload, Mapping) else []
        snap_rows = snapshots if isinstance(snapshots, list) else []
        turnovers = [
            _safe_float(x.get("turnover", 0.0), 0.0)
            for x in snap_rows
            if isinstance(x, Mapping)
        ]
        exposures = [
            _safe_float(x.get("gross_exposure", 0.0), 0.0)
            for x in snap_rows
            if isinstance(x, Mapping)
        ]
        costs = [
            _safe_float(x.get("transaction_cost", 0.0), 0.0)
            for x in snap_rows
            if isinstance(x, Mapping)
        ]
        avg_turnover = float(np.mean(turnovers)) if turnovers else _safe_float((agg or {}).get("avg_turnover", 0.0), 0.0)
        rebalance_count = float(len(turnovers)) if turnovers else _safe_float((agg or {}).get("avg_rebalance_count", 0.0), 0.0)
        avg_cost = float(np.mean(costs)) if costs else _safe_float((agg or {}).get("avg_txn_cost_per_rebalance", 0.0), 0.0)
        txn_bps = _safe_float(portfolio_cfg.get("transaction_cost_bps_per_side", 0.0), 0.0)
        cost_applied = bool((txn_bps <= 0.0) or (avg_cost > 0.0))

        exposure_variance = float(np.var(exposures)) if exposures else 0.0

        streak = int(self.state.get("turnover_zero_streak", 0))
        if avg_turnover <= 1e-12 and rebalance_count >= float(self.cert_cfg.get("turnover_min_rebalances", 10)):
            streak += 1
        else:
            streak = 0
        self.state["turnover_zero_streak"] = int(streak)

        fail_turnover = bool(streak >= int(self.cert_cfg.get("turnover_zero_streak_limit", 3)))
        fail_cost = bool((txn_bps > 0.0) and (avg_turnover > 0.0) and (not cost_applied))
        fail_exposure = bool(
            (rebalance_count >= float(self.cert_cfg.get("turnover_min_rebalances", 10)))
            and (exposure_variance < float(self.cert_cfg.get("min_exposure_variance", 1e-4)))
        )
        passed = bool((not fail_turnover) and (not fail_cost) and (not fail_exposure))
        return {
            "avg_turnover": float(avg_turnover),
            "turnover_zero_streak": int(streak),
            "transaction_cost_bps_per_side": float(txn_bps),
            "cost_applied": bool(cost_applied),
            "exposure_variance": float(exposure_variance),
            "rebalance_count": float(rebalance_count),
            "passed": bool(passed),
        }

    def _blend_integrity(self, outputs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        alpha_rows = self._extract_output(outputs, "alpha_factory")
        alpha = alpha_rows[-1] if alpha_rows else {}
        blend_weights = alpha.get("blend_weights", {})
        if not isinstance(blend_weights, Mapping):
            blend_weights = {}
        weights = [abs(_safe_float(v, 0.0)) for v in blend_weights.values()]
        max_family_weight = float(max(weights)) if weights else 0.0
        entropy = _normalize_entropy(weights)

        corr_drift = 0.0
        mon = alpha.get("monitoring", {})
        if isinstance(mon, Mapping):
            cd = mon.get("correlation_drift", {})
            if isinstance(cd, Mapping):
                corr_drift = _safe_float(cd.get("mean_abs_corr_shift", 0.0), 0.0)

        prev = self.state.get("last_blend_weights", {})
        prev_map = dict(prev) if isinstance(prev, Mapping) else {}
        keys = sorted(set(prev_map.keys()) | set(blend_weights.keys()))
        l1_step = 0.0
        if keys:
            l1_step = float(
                sum(
                    abs(_safe_float(blend_weights.get(k, 0.0), 0.0) - _safe_float(prev_map.get(k, 0.0), 0.0))
                    for k in keys
                )
            )
        self.state["last_blend_weights"] = dict(blend_weights)

        streak = int(self.state.get("allocation_l1_high_streak", 0))
        if l1_step > float(self.cert_cfg.get("allocation_l1_step_max", 0.35)):
            streak += 1
        else:
            streak = 0
        self.state["allocation_l1_high_streak"] = int(streak)

        concentration_flag = bool(
            (max_family_weight > float(self.cert_cfg.get("max_family_weight_hard", 0.45)))
            or (
                max_family_weight > float(self.cert_cfg.get("max_family_weight_soft", 0.35))
                and corr_drift > float(self.cert_cfg.get("corr_drift_hard", 0.10))
            )
        )
        reflexivity_fail = bool(streak >= int(self.cert_cfg.get("allocation_l1_streak_limit", 3)))
        entropy_fail = bool(entropy < float(self.cert_cfg.get("min_family_entropy", 0.55)))
        passed = bool((not concentration_flag) and (not reflexivity_fail) and (not entropy_fail))
        return {
            "family_entropy": float(entropy),
            "max_family_weight": float(max_family_weight),
            "corr_drift": {"mean_abs_corr_shift": float(corr_drift)},
            "concentration_flag": bool(concentration_flag),
            "allocation_l1_step": float(l1_step),
            "allocation_l1_high_streak": int(streak),
            "passed": bool(passed),
        }

    def _regime_effectiveness(
        self,
        outputs: Sequence[Dict[str, Any]],
        best_series: pd.Series,
        dataset_frame: pd.DataFrame,
    ) -> Dict[str, Any]:
        if not isinstance(best_series, pd.Series) or best_series.empty:
            return {
                "pnl_with_regime": 0.0,
                "pnl_without_regime": 0.0,
                "delta_return_ann": 0.0,
                "delta_sharpe": 0.0,
                "delta_max_drawdown": 0.0,
                "regime_coverage": 0.0,
                "meaningful": False,
                "passed": False,
            }

        # Regime validity requires non-degenerate probability state outputs.
        regime_rows = self._extract_output(outputs, "regime_transition_analysis")
        regime_valid = False
        if regime_rows:
            probs = regime_rows[-1].get("latest_regime_probabilities", {})
            if isinstance(probs, Mapping):
                p = np.asarray([_safe_float(v, 0.0) for v in probs.values()], dtype=float)
                s = float(np.sum(p))
                nontrivial = int(np.sum(p > 0.05))
                regime_valid = bool((abs(s - 1.0) <= 0.05) and (nontrivial >= 2))

        s = best_series.copy()
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            regime_valid = False
            return {
                "pnl_with_regime": 0.0,
                "pnl_without_regime": 0.0,
                "delta_return_ann": 0.0,
                "delta_sharpe": 0.0,
                "delta_max_drawdown": 0.0,
                "regime_coverage": 0.0,
                "meaningful": False,
                "passed": False,
            }
        if not isinstance(s.index, pd.DatetimeIndex):
            s.index = pd.to_datetime(s.index, errors="coerce")
            s = s[~s.index.isna()]
        s = s.sort_index()

        regime_mult = dict(self.cert_cfg.get("regime_multipliers", {"LOW_VOL": 1.0, "NORMAL": 1.0, "CRISIS": 0.6}))
        date_to_regime: Dict[pd.Timestamp, str] = {}
        if (
            isinstance(dataset_frame, pd.DataFrame)
            and (not dataset_frame.empty)
            and ("date" in dataset_frame.columns)
            and ("regime" in dataset_frame.columns)
        ):
            reg_df = dataset_frame[["date", "regime"]].copy()
            reg_df["date"] = pd.to_datetime(reg_df["date"], errors="coerce")
            reg_df["regime"] = reg_df["regime"].astype(str)
            reg_df = reg_df.dropna().sort_values("date")
            by_date = reg_df.groupby("date")["regime"].agg(lambda x: str(pd.Series(x).mode().iloc[0]) if len(pd.Series(x).mode()) else str(x.iloc[0]))
            date_to_regime = {pd.Timestamp(k): str(v) for k, v in by_date.items()}

        base = s.to_numpy(dtype=float)
        adjusted = base.copy()
        if date_to_regime:
            regimes_seen: set[str] = set()
            for i, dt in enumerate(s.index):
                rg = date_to_regime.get(pd.Timestamp(dt))
                if rg is None:
                    continue
                regimes_seen.add(str(rg))
                mult = _safe_float(regime_mult.get(str(rg), regime_mult.get(str(int(_safe_float(rg, 1.0))), 1.0)), 1.0)
                adjusted[i] = float(base[i] * mult)
            regime_coverage = float(len(regimes_seen)) / float(max(1, int(self.cert_cfg.get("expected_regime_states", 3))))
        else:
            regime_coverage = 0.0

        ann_ret_0 = float(np.mean(base) * 252.0) if len(base) else 0.0
        ann_ret_1 = float(np.mean(adjusted) * 252.0) if len(adjusted) else 0.0
        sh_0 = _sharpe_like(base, periods_per_year=252)
        sh_1 = _sharpe_like(adjusted, periods_per_year=252)
        dd_0 = _max_drawdown(base)
        dd_1 = _max_drawdown(adjusted)
        pnl_0 = float(np.prod(1.0 + np.clip(base, -0.999, 1.0)) - 1.0)
        pnl_1 = float(np.prod(1.0 + np.clip(adjusted, -0.999, 1.0)) - 1.0)
        delta_ret_ann = float(ann_ret_1 - ann_ret_0)
        delta_sharpe = float(sh_1 - sh_0)
        delta_dd = float(dd_1 - dd_0)
        meaningful = bool(
            (abs(delta_sharpe) >= float(self.cert_cfg.get("regime_effectiveness_min_delta_sharpe", 0.15)))
            or (abs(delta_ret_ann) >= float(self.cert_cfg.get("regime_effectiveness_min_delta_return_ann", 0.015)))
            or (abs(delta_dd) >= float(self.cert_cfg.get("regime_effectiveness_min_delta_dd", 0.01)))
        )
        # Hard-fail when the regime layer is mathematically valid but inert.
        passed = bool(regime_valid and meaningful)
        return {
            "pnl_with_regime": float(pnl_1),
            "pnl_without_regime": float(pnl_0),
            "delta_return_ann": float(delta_ret_ann),
            "delta_sharpe": float(delta_sharpe),
            "delta_max_drawdown": float(delta_dd),
            "regime_coverage": float(max(0.0, min(1.0, regime_coverage))),
            "regime_valid": bool(regime_valid),
            "meaningful": bool(meaningful),
            "passed": bool(passed),
        }

    def _objective_surface_sanity(self, param_payload: Mapping[str, Any], weekend_run: bool, best_model: str) -> Dict[str, Any]:
        payload = dict(param_payload or {})
        mode = str(payload.get("mode", "")).strip().lower()
        scores: List[float] = []
        params_seq: List[Dict[str, Any]] = []

        if mode == "bayesian_hyperopt":
            opt = payload.get("optimization", {})
            if isinstance(opt, Mapping):
                hist = opt.get("history", [])
                if isinstance(hist, list):
                    for row in hist:
                        if not isinstance(row, Mapping):
                            continue
                        # optimizer objective lower is better; convert to higher-is-better score.
                        obj = _safe_float(row.get("objective", 0.0), 0.0)
                        scores.append(float(-obj))
                        params_seq.append(dict(row.get("params", {}) if isinstance(row.get("params"), Mapping) else {}))
                if not scores:
                    obj_best = _safe_float(opt.get("best_objective", 0.0), 0.0)
                    scores = [float(-obj_best)]
                    params_seq = [dict(opt.get("best_params", {}) if isinstance(opt.get("best_params"), Mapping) else {})]
        else:
            rows = payload.get("sensitivity_results", [])
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, Mapping):
                        continue
                    if str(row.get("status", "")).strip().lower() != "ok":
                        continue
                    scores.append(_safe_float(row.get("utility_score", 0.0), 0.0))
                    params_seq.append(dict(row.get("params", {}) if isinstance(row.get("params"), Mapping) else {}))

        trials = int(len(scores))
        var = float(np.var(scores)) if trials > 1 else 0.0
        local_peaks = 0
        if trials >= 3:
            for i in range(1, trials - 1):
                if scores[i] > scores[i - 1] and scores[i] > scores[i + 1]:
                    local_peaks += 1
        smoothness = float(1.0 / (1.0 + np.std(np.diff(scores)))) if trials > 2 else 1.0

        hist_key = str(best_model or "unknown")
        hist_all = self.state.get("best_param_history", {})
        if not isinstance(hist_all, MutableMapping):
            hist_all = {}
        model_hist = list(hist_all.get(hist_key, [])) if isinstance(hist_all.get(hist_key, []), list) else []
        if params_seq:
            model_hist.append({"params": dict(params_seq[-1])})
        model_hist = model_hist[-20:]
        hist_all[hist_key] = model_hist
        self.state["best_param_history"] = hist_all
        rolling_stability = _rolling_param_drift(model_hist)

        min_trials = int(self.cert_cfg.get("min_trials_weekend", 20 if weekend_run else 12))
        if not weekend_run:
            min_trials = int(self.cert_cfg.get("min_trials_weekday", 12))
        trials_fail = bool(trials < min_trials)
        var_fail = bool(var <= float(self.cert_cfg.get("min_objective_variance", 1e-6)))
        drift_fail = bool(rolling_stability > float(self.cert_cfg.get("max_rolling_param_stability", 0.35)))
        passed = bool((not trials_fail) and (not var_fail) and (not drift_fail))
        return {
            "trials_executed": int(trials),
            "objective_variance": float(var),
            "local_peak_count": int(local_peaks),
            "rolling_param_stability": float(rolling_stability),
            "smoothness_score": float(smoothness),
            "passed": bool(passed),
        }

    def _statistical_robustness(
        self,
        series: pd.Series,
        regime_metrics: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        arr = series.to_numpy(dtype=float) if isinstance(series, pd.Series) else np.asarray([], dtype=float)
        p05, p95, width = _bootstrap_sharpe_bounds(arr, random_state=int(self.config.get("random_state", 42)))
        dd_p95 = _block_bootstrap_dd_p95(arr, random_state=int(self.config.get("random_state", 42)))
        regime_consistency = 1.0 if len(arr) >= 30 else 0.0
        if isinstance(regime_metrics, Mapping) and regime_metrics:
            vals: List[float] = []
            for row in regime_metrics.values():
                if not isinstance(row, Mapping):
                    continue
                if "avg_sharpe" in row:
                    vals.append(_safe_float(row.get("avg_sharpe", 0.0), 0.0))
                elif "sharpe" in row:
                    vals.append(_safe_float(row.get("sharpe", 0.0), 0.0))
            if len(vals) >= 2:
                # 1.0 means consistent sign and magnitude, 0.0 means unstable/oscillatory.
                arr_v = np.asarray(vals, dtype=float)
                regime_consistency = float(1.0 / (1.0 + np.std(arr_v)))
        passed = bool(
            (p05 > float(self.cert_cfg.get("bootstrap_sharpe_p05_min", 0.0)))
            and (dd_p95 <= float(self.cert_cfg.get("block_bootstrap_dd_p95_max", 0.35)))
        )
        return {
            "bootstrap_sharpe_p05": float(p05),
            "bootstrap_sharpe_p95": float(p95),
            "bootstrap_confidence_width": float(width),
            "block_bootstrap_dd_p95": float(dd_p95),
            "regime_bucket_consistency": float(regime_consistency),
            "passed": bool(passed),
        }

    def _capital_scaling_gate(self, series: pd.Series) -> Dict[str, Any]:
        arr = series.to_numpy(dtype=float) if isinstance(series, pd.Series) else np.asarray([], dtype=float)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        def _metrics(mult: float) -> Dict[str, float]:
            r = np.clip(arr * float(mult), -0.999, 1.0)
            ruin = float(np.mean(np.cumprod(1.0 + r) <= 0.70)) if len(r) else 1.0
            dd = _max_drawdown(r)
            ann_ret = float(np.mean(r) * 252.0) if len(r) else 0.0
            ann_vol = float(np.std(r, ddof=1) * np.sqrt(252.0)) if len(r) > 1 else 0.0
            sharpe = float(ann_ret / (ann_vol + 1e-12))
            return {"ruin": ruin, "max_drawdown": dd, "annual_return": ann_ret, "annual_vol": ann_vol, "sharpe": sharpe}

        x1 = _metrics(1.0)
        x2 = _metrics(2.0)
        x3 = _metrics(3.0)
        passed = bool(
            x1["ruin"] <= float(self.cert_cfg.get("ruin_x1_max", 0.02))
            and x2["ruin"] <= float(self.cert_cfg.get("ruin_x2_max", 0.07))
            and x3["ruin"] <= float(self.cert_cfg.get("ruin_x3_max", 0.15))
        )
        return {
            "x1": x1,
            "x2": x2,
            "x3": x3,
            "ruin_sensitivity": float(x3["ruin"] - x1["ruin"]),
            "drawdown_sensitivity": float(x3["max_drawdown"] - x1["max_drawdown"]),
            "passed": bool(passed),
        }

    def _time_aggregation_check(self, series: pd.Series) -> Dict[str, Any]:
        daily = series.to_numpy(dtype=float) if isinstance(series, pd.Series) else np.asarray([], dtype=float)
        weekly, monthly = _weekly_monthly_returns(series if isinstance(series, pd.Series) else pd.Series(dtype=float))
        daily_sh = _sharpe_like(daily, periods_per_year=252)
        weekly_sh = _sharpe_like(weekly, periods_per_year=52)
        monthly_sh = _sharpe_like(monthly, periods_per_year=12)
        passed = bool(not (daily_sh > 0 and weekly_sh < 0 and monthly_sh < 0))
        return {
            "daily_metrics": {"sharpe": float(daily_sh), "n_obs": int(len(daily))},
            "weekly_metrics": {"sharpe": float(weekly_sh), "n_obs": int(len(weekly))},
            "monthly_metrics": {"sharpe": float(monthly_sh), "n_obs": int(len(monthly))},
            "passed": bool(passed),
        }

    def _confidence_score(
        self,
        best_payload: Mapping[str, Any],
        statistical_robustness: Mapping[str, Any],
        regime_effectiveness: Mapping[str, Any],
    ) -> Dict[str, Any]:
        agg = best_payload.get("aggregate_metrics", {}) if isinstance(best_payload, Mapping) else {}
        windows = _safe_float((agg or {}).get("windows", 0.0), 0.0)
        max_windows = float(max(1, int(self.config.get("training", {}).get("max_windows", 1))))
        sample_cov = float(min(1.0, windows / max_windows))

        reg_cov = _safe_float(regime_effectiveness.get("regime_coverage", 0.0), 0.0)
        width = _safe_float(statistical_robustness.get("bootstrap_confidence_width", 9.99), 9.99)
        passed = bool(
            sample_cov >= float(self.cert_cfg.get("sample_coverage_min", 1.0))
            and reg_cov >= float(self.cert_cfg.get("regime_coverage_min", 0.67))
            and width <= float(self.cert_cfg.get("bootstrap_conf_width_max", 1.5))
        )
        return {
            "sample_coverage": float(sample_cov),
            "regime_coverage": float(reg_cov),
            "bootstrap_confidence_width": float(width),
            "passed": bool(passed),
        }

    def _leakage_proof(self, best_payload: Mapping[str, Any]) -> Dict[str, Any]:
        windows = best_payload.get("windows", []) if isinstance(best_payload, Mapping) else []
        if not isinstance(windows, list) or not windows:
            return {
                "windows_checked": 0,
                "temporal_order_violations": 1,
                "passed": False,
            }
        violations = 0
        checked = 0
        for row in windows:
            if not isinstance(row, Mapping):
                continue
            train_end = pd.to_datetime(row.get("train_end"), errors="coerce")
            test_start = pd.to_datetime(row.get("test_start"), errors="coerce")
            if pd.isna(train_end) or pd.isna(test_start):
                continue
            checked += 1
            if test_start <= train_end:
                violations += 1
        passed = bool((checked > 0) and (violations == 0))
        return {
            "windows_checked": int(checked),
            "temporal_order_violations": int(violations),
            "passed": bool(passed),
        }

    def _model_risk_tier(self, best_model: str, gate_map: Mapping[str, Any]) -> Dict[str, Any]:
        name = str(best_model or "").strip().lower()
        if ("ensemble" in name) or ("meta" in name) or ("northstar" in name):
            tier = 4
        elif name in {"lightgbm", "xgboost", "catboost", "random_forest"}:
            tier = 2
        elif name in {"lstm", "tcn", "transformer"}:
            tier = 3
        else:
            tier = 1

        required = [
            "data_provenance",
            "universe_integrity",
            "strategy_correlation_check",
            "portfolio_integrity",
            "statistical_robustness",
            "confidence_score",
            "formula_lineage",
            "macro_unit_integrity",
            "dependency_lock",
            "resource_guard",
        ]
        if tier >= 2:
            required.extend(["leakage_proof", "objective_surface_sanity"])
        if tier >= 3:
            required.extend(["regime_effectiveness", "capital_scaling_gate"])
        if tier >= 4:
            required.extend(["blend_integrity", "strategy_correlation_check"])
        required = sorted(set(required))
        tier_requirements_passed = all(bool((gate_map.get(k, {}) or {}).get("passed", False)) for k in required)
        return {
            "tier": int(tier),
            "tier_requirements_passed": bool(tier_requirements_passed),
            "promotion_allowed": bool(tier_requirements_passed),
        }

    def _advisory_gates(self, outputs: Sequence[Dict[str, Any]], dataset_metadata: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
        advisories: List[str] = []
        escalated: List[str] = []
        streaks = self.state.get("advisory_streaks", {})
        if not isinstance(streaks, MutableMapping):
            streaks = {}

        # Feature drift alarm proxy.
        if bool(dataset_metadata.get("feature_cross_sectional_zscore", False)) and _safe_float(dataset_metadata.get("target_abs_max", 0.0), 0.0) < 1e-4:
            advisories.append("feature_drift_alarm")

        ic_rows = self._extract_output(outputs, "ic_diagnostics")
        if ic_rows:
            decay = ic_rows[-1].get("decay_summary_selected_features", {})
            if isinstance(decay, Mapping):
                half_life = _safe_float(decay.get("half_life_horizon", 999.0), 999.0)
                if half_life < float(self.cert_cfg.get("advisory_ic_half_life_min", 20.0)):
                    advisories.append("ic_half_life_degradation")

        alpha_rows = self._extract_output(outputs, "alpha_factory")
        if alpha_rows:
            mon = alpha_rows[-1].get("monitoring", {})
            if isinstance(mon, Mapping):
                cd = mon.get("correlation_drift", {})
                if isinstance(cd, Mapping):
                    if _safe_float(cd.get("median_abs_corr_recent", 0.0), 0.0) > 0.75:
                        advisories.append("cross_family_ic_redundancy")

        regime_rows = self._extract_output(outputs, "regime_transition_analysis")
        if regime_rows:
            row = regime_rows[-1]
            probs = row.get("latest_regime_probabilities", row.get("transition_probabilities", {}))
            if isinstance(probs, Mapping):
                p = np.asarray([_safe_float(v, 0.0) for v in probs.values()], dtype=float)
                p = p[p > 0]
                if len(p):
                    ent = -float(np.sum(p * np.log(np.clip(p, 1e-12, 1.0))))
                    if ent < float(self.cert_cfg.get("advisory_regime_entropy_min", 0.20)):
                        advisories.append("regime_transition_entropy_collapse")

        limit = int(self.cert_cfg.get("advisory_persistence_limit", 5))
        next_streaks: Dict[str, int] = {}
        current = set(advisories)
        for key in sorted(set(list(streaks.keys()) + advisories)):
            if key in current:
                next_streaks[key] = int(_safe_int(streaks.get(key, 0), 0) + 1)
            else:
                next_streaks[key] = 0
            if key in current and next_streaks[key] >= limit:
                escalated.append(key)
        self.state["advisory_streaks"] = next_streaks
        return advisories, escalated

    def _observed_regimes(self, outputs: Sequence[Dict[str, Any]]) -> List[str]:
        rows = self._extract_output(outputs, "regime_transition_analysis")
        if not rows:
            return []
        probs = rows[-1].get("latest_regime_probabilities", {})
        if not isinstance(probs, Mapping) or not probs:
            return []
        out = [str(k) for k, v in probs.items() if _safe_float(v, 0.0) > 0.20]
        return sorted(set(out))

    def _update_burn_in(
        self,
        critical_failures: Sequence[str],
        freeze_active: bool,
        observed_regimes: Sequence[str],
        system_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        burn = self.state.get("burn_in", {})
        if not isinstance(burn, MutableMapping):
            burn = {}
        consec = int(_safe_int(burn.get("consecutive_pass_cycles", 0), 0))
        regimes = set(burn.get("observed_volatility_regimes", []) if isinstance(burn.get("observed_volatility_regimes", []), list) else [])
        if freeze_active:
            # Freeze cycles do not count toward burn-in certification.
            pass
        elif critical_failures:
            consec = 0
        else:
            consec += 1
        for rg in observed_regimes:
            if str(rg).strip():
                regimes.add(str(rg).strip())
        cert_target = int(self.cert_cfg.get("burn_in_cycles_required", 20))
        regime_target = int(self.cert_cfg.get("burn_in_regimes_required", 2))
        regimes_available = bool(system_state.get("volatility_regimes_available", True))
        provisional_allowed = bool(self.cert_cfg.get("allow_single_regime_provisional", True))
        provisional = bool((not regimes_available) and provisional_allowed and (len(regimes) >= 1))
        cert_pass = bool((consec >= cert_target) and ((len(regimes) >= regime_target) or provisional))
        burn_out = {
            "consecutive_pass_cycles": int(consec),
            "observed_volatility_regimes": sorted(regimes),
            "certification_passed": bool(cert_pass),
            "required_cycles": int(cert_target),
            "required_regimes": int(regime_target),
            "provisional_single_regime": bool(provisional),
        }
        self.state["burn_in"] = burn_out
        return burn_out

    @staticmethod
    def _rule_detail(
        *,
        rule_id: str,
        gate: str,
        observed: Any,
        threshold: Any,
        comparator: str,
    ) -> Dict[str, Any]:
        return {
            "rule_id": str(rule_id),
            "gate": str(gate),
            "observed": observed,
            "threshold": threshold,
            "comparator": str(comparator),
        }

    def _failure_details_for_gate(
        self,
        gate_name: str,
        payload: Mapping[str, Any],
        ctx: CertificationContext,
    ) -> List[Dict[str, Any]]:
        details: List[Dict[str, Any]] = []
        gate = str(gate_name)
        p = dict(payload or {})
        cfg = self.cert_cfg

        if gate == "data_provenance":
            for key in ("universe_hash", "price_hash", "feature_hash", "label_hash"):
                if not bool(p.get(key)):
                    details.append(
                        self._rule_detail(
                            rule_id=f"data_provenance.{key}_present",
                            gate=gate,
                            observed=bool(p.get(key)),
                            threshold=True,
                            comparator="==",
                        )
                    )
        elif gate == "replay_certification":
            if bool(ctx.system_state.get("controlled_replay", False)):
                if not bool(p.get("output_hash_match", True)):
                    details.append(
                        self._rule_detail(
                            rule_id="replay_certification.output_hash_match",
                            gate=gate,
                            observed=bool(p.get("output_hash_match", False)),
                            threshold=True,
                            comparator="==",
                        )
                    )
                if not bool(p.get("provenance_hash_match", True)):
                    details.append(
                        self._rule_detail(
                            rule_id="replay_certification.provenance_hash_match",
                            gate=gate,
                            observed=bool(p.get("provenance_hash_match", False)),
                            threshold=True,
                            comparator="==",
                        )
                    )
        elif gate == "universe_integrity":
            if not bool(p.get("forward_inclusion_check", True)):
                details.append(
                    self._rule_detail(
                        rule_id="universe_integrity.forward_inclusion_check",
                        gate=gate,
                        observed=bool(p.get("forward_inclusion_check", False)),
                        threshold=True,
                        comparator="==",
                    )
                )
            delisted_min = float(cfg.get("delisted_assets_min", 0.99))
            delisted = _safe_float(p.get("delisted_assets_handled", 0.0), 0.0)
            if delisted < delisted_min:
                details.append(
                    self._rule_detail(
                        rule_id="universe_integrity.delisted_assets_handled",
                        gate=gate,
                        observed=float(delisted),
                        threshold=float(delisted_min),
                        comparator=">=",
                    )
                )
        elif gate == "strategy_correlation_check":
            corr = _safe_float(p.get("max_pairwise_corr", 0.0), 0.0)
            corr_max = float(cfg.get("max_pairwise_corr", 0.99))
            if corr > corr_max:
                details.append(
                    self._rule_detail(
                        rule_id="strategy_correlation_check.max_pairwise_corr",
                        gate=gate,
                        observed=float(corr),
                        threshold=float(corr_max),
                        comparator="<=",
                    )
                )
            overlap = _safe_float(p.get("max_holdings_overlap", 0.0), 0.0)
            overlap_max = float(cfg.get("max_holdings_overlap", 0.95))
            overlap_share = _safe_float(p.get("high_overlap_share_max", 0.0), 0.0)
            overlap_share_max = float(cfg.get("overlap_persistence_threshold", 0.70))
            if overlap > overlap_max and overlap_share >= overlap_share_max:
                details.append(
                    self._rule_detail(
                        rule_id="strategy_correlation_check.overlap_persistence",
                        gate=gate,
                        observed={
                            "max_holdings_overlap": float(overlap),
                            "high_overlap_share_max": float(overlap_share),
                        },
                        threshold={
                            "max_holdings_overlap": float(overlap_max),
                            "high_overlap_share_max": float(overlap_share_max),
                        },
                        comparator="<=",
                    )
                )
        elif gate == "portfolio_integrity":
            streak = int(_safe_int(p.get("turnover_zero_streak", 0), 0))
            streak_max = int(cfg.get("turnover_zero_streak_limit", 3))
            if streak >= streak_max:
                details.append(
                    self._rule_detail(
                        rule_id="portfolio_integrity.turnover_zero_streak",
                        gate=gate,
                        observed=int(streak),
                        threshold=int(streak_max),
                        comparator="<",
                    )
                )
            avg_turnover = _safe_float(p.get("avg_turnover", 0.0), 0.0)
            txn_bps = _safe_float(p.get("transaction_cost_bps_per_side", 0.0), 0.0)
            if txn_bps > 0.0 and avg_turnover > 0.0 and (not bool(p.get("cost_applied", False))):
                details.append(
                    self._rule_detail(
                        rule_id="portfolio_integrity.cost_applied_when_turnover_exists",
                        gate=gate,
                        observed=bool(p.get("cost_applied", False)),
                        threshold=True,
                        comparator="==",
                    )
                )
            min_exposure_var = float(cfg.get("min_exposure_variance", 1e-4))
            exposure_var = _safe_float(p.get("exposure_variance", 0.0), 0.0)
            rebalance_count = _safe_float(p.get("rebalance_count", 0.0), 0.0)
            if rebalance_count >= float(cfg.get("turnover_min_rebalances", 10)) and exposure_var < min_exposure_var:
                details.append(
                    self._rule_detail(
                        rule_id="portfolio_integrity.exposure_variance",
                        gate=gate,
                        observed=float(exposure_var),
                        threshold=float(min_exposure_var),
                        comparator=">=",
                    )
                )
        elif gate == "blend_integrity":
            w = _safe_float(p.get("max_family_weight", 0.0), 0.0)
            hard = float(cfg.get("max_family_weight_hard", 0.45))
            soft = float(cfg.get("max_family_weight_soft", 0.35))
            drift_max = float(cfg.get("corr_drift_hard", 0.10))
            drift = _safe_float((p.get("corr_drift", {}) or {}).get("mean_abs_corr_shift", 0.0), 0.0)
            ent = _safe_float(p.get("family_entropy", 0.0), 0.0)
            ent_min = float(cfg.get("min_family_entropy", 0.55))
            l1 = _safe_float(p.get("allocation_l1_step", 0.0), 0.0)
            l1_max = float(cfg.get("allocation_l1_step_max", 0.35))
            l1_streak = int(_safe_int(p.get("allocation_l1_high_streak", 0), 0))
            l1_streak_max = int(cfg.get("allocation_l1_streak_limit", 3))
            if w > hard:
                details.append(
                    self._rule_detail(
                        rule_id="blend_integrity.max_family_weight_hard",
                        gate=gate,
                        observed=float(w),
                        threshold=float(hard),
                        comparator="<=",
                    )
                )
            if w > soft and drift > drift_max:
                details.append(
                    self._rule_detail(
                        rule_id="blend_integrity.max_family_weight_with_corr_drift",
                        gate=gate,
                        observed={"max_family_weight": float(w), "corr_drift": float(drift)},
                        threshold={"max_family_weight": float(soft), "corr_drift": float(drift_max)},
                        comparator="<=",
                    )
                )
            if ent < ent_min:
                details.append(
                    self._rule_detail(
                        rule_id="blend_integrity.family_entropy",
                        gate=gate,
                        observed=float(ent),
                        threshold=float(ent_min),
                        comparator=">=",
                    )
                )
            if l1 > l1_max and l1_streak >= l1_streak_max:
                details.append(
                    self._rule_detail(
                        rule_id="blend_integrity.allocation_l1_reflexivity",
                        gate=gate,
                        observed={"allocation_l1_step": float(l1), "streak": int(l1_streak)},
                        threshold={"allocation_l1_step": float(l1_max), "streak": int(l1_streak_max)},
                        comparator="<=",
                    )
                )
        elif gate == "regime_effectiveness":
            valid = bool(p.get("regime_valid", False))
            d_sh = abs(_safe_float(p.get("delta_sharpe", 0.0), 0.0))
            d_ret = abs(_safe_float(p.get("delta_return_ann", 0.0), 0.0))
            d_dd = abs(_safe_float(p.get("delta_max_drawdown", 0.0), 0.0))
            t_sh = float(cfg.get("regime_effectiveness_min_delta_sharpe", 0.15))
            t_ret = float(cfg.get("regime_effectiveness_min_delta_return_ann", 0.015))
            t_dd = float(cfg.get("regime_effectiveness_min_delta_dd", 0.01))
            if valid and (d_sh < t_sh) and (d_ret < t_ret) and (d_dd < t_dd):
                details.append(
                    self._rule_detail(
                        rule_id="regime_effectiveness.inert_regime_layer",
                        gate=gate,
                        observed={
                            "abs_delta_sharpe": float(d_sh),
                            "abs_delta_return_ann": float(d_ret),
                            "abs_delta_max_drawdown": float(d_dd),
                        },
                        threshold={
                            "abs_delta_sharpe": float(t_sh),
                            "abs_delta_return_ann": float(t_ret),
                            "abs_delta_max_drawdown": float(t_dd),
                        },
                        comparator=">= any",
                    )
                )
            elif not valid:
                details.append(
                    self._rule_detail(
                        rule_id="regime_effectiveness.regime_valid",
                        gate=gate,
                        observed=bool(valid),
                        threshold=True,
                        comparator="==",
                    )
                )
        elif gate == "objective_surface_sanity":
            trials = int(_safe_int(p.get("trials_executed", 0), 0))
            min_trials = int(cfg.get("min_trials_weekend", 20 if ctx.weekend_run else 12))
            if not ctx.weekend_run:
                min_trials = int(cfg.get("min_trials_weekday", 12))
            if trials < min_trials:
                details.append(
                    self._rule_detail(
                        rule_id="objective_surface_sanity.trials_executed",
                        gate=gate,
                        observed=int(trials),
                        threshold=int(min_trials),
                        comparator=">=",
                    )
                )
            var = _safe_float(p.get("objective_variance", 0.0), 0.0)
            min_var = float(cfg.get("min_objective_variance", 1e-6))
            if var <= min_var:
                details.append(
                    self._rule_detail(
                        rule_id="objective_surface_sanity.objective_variance",
                        gate=gate,
                        observed=float(var),
                        threshold=float(min_var),
                        comparator=">",
                    )
                )
            rps = _safe_float(p.get("rolling_param_stability", 0.0), 0.0)
            rps_max = float(cfg.get("max_rolling_param_stability", 0.35))
            if rps > rps_max:
                details.append(
                    self._rule_detail(
                        rule_id="objective_surface_sanity.rolling_param_stability",
                        gate=gate,
                        observed=float(rps),
                        threshold=float(rps_max),
                        comparator="<=",
                    )
                )
        elif gate == "statistical_robustness":
            p05 = _safe_float(p.get("bootstrap_sharpe_p05", 0.0), 0.0)
            p05_min = float(cfg.get("bootstrap_sharpe_p05_min", 0.0))
            if p05 <= p05_min:
                details.append(
                    self._rule_detail(
                        rule_id="statistical_robustness.bootstrap_sharpe_p05",
                        gate=gate,
                        observed=float(p05),
                        threshold=float(p05_min),
                        comparator=">",
                    )
                )
            dd95 = _safe_float(p.get("block_bootstrap_dd_p95", 0.0), 0.0)
            dd95_max = float(cfg.get("block_bootstrap_dd_p95_max", 0.35))
            if dd95 > dd95_max:
                details.append(
                    self._rule_detail(
                        rule_id="statistical_robustness.block_bootstrap_dd_p95",
                        gate=gate,
                        observed=float(dd95),
                        threshold=float(dd95_max),
                        comparator="<=",
                    )
                )
        elif gate == "capital_scaling_gate":
            x1 = _safe_float((p.get("x1", {}) or {}).get("ruin", 1.0), 1.0)
            x2 = _safe_float((p.get("x2", {}) or {}).get("ruin", 1.0), 1.0)
            x3 = _safe_float((p.get("x3", {}) or {}).get("ruin", 1.0), 1.0)
            if x1 > float(cfg.get("ruin_x1_max", 0.02)):
                details.append(
                    self._rule_detail(
                        rule_id="capital_scaling_gate.ruin_x1",
                        gate=gate,
                        observed=float(x1),
                        threshold=float(cfg.get("ruin_x1_max", 0.02)),
                        comparator="<=",
                    )
                )
            if x2 > float(cfg.get("ruin_x2_max", 0.07)):
                details.append(
                    self._rule_detail(
                        rule_id="capital_scaling_gate.ruin_x2",
                        gate=gate,
                        observed=float(x2),
                        threshold=float(cfg.get("ruin_x2_max", 0.07)),
                        comparator="<=",
                    )
                )
            if x3 > float(cfg.get("ruin_x3_max", 0.15)):
                details.append(
                    self._rule_detail(
                        rule_id="capital_scaling_gate.ruin_x3",
                        gate=gate,
                        observed=float(x3),
                        threshold=float(cfg.get("ruin_x3_max", 0.15)),
                        comparator="<=",
                    )
                )
        elif gate == "time_aggregation_check":
            d_sh = _safe_float((p.get("daily_metrics", {}) or {}).get("sharpe", 0.0), 0.0)
            w_sh = _safe_float((p.get("weekly_metrics", {}) or {}).get("sharpe", 0.0), 0.0)
            m_sh = _safe_float((p.get("monthly_metrics", {}) or {}).get("sharpe", 0.0), 0.0)
            if d_sh > 0.0 and w_sh < 0.0 and m_sh < 0.0:
                details.append(
                    self._rule_detail(
                        rule_id="time_aggregation_check.daily_positive_weekly_monthly_negative",
                        gate=gate,
                        observed={"daily_sharpe": float(d_sh), "weekly_sharpe": float(w_sh), "monthly_sharpe": float(m_sh)},
                        threshold={"weekly_sharpe": 0.0, "monthly_sharpe": 0.0},
                        comparator="not both < 0 when daily > 0",
                    )
                )
        elif gate == "confidence_score":
            sample_cov = _safe_float(p.get("sample_coverage", 0.0), 0.0)
            sample_min = float(cfg.get("sample_coverage_min", 1.0))
            if sample_cov < sample_min:
                details.append(
                    self._rule_detail(
                        rule_id="confidence_score.sample_coverage",
                        gate=gate,
                        observed=float(sample_cov),
                        threshold=float(sample_min),
                        comparator=">=",
                    )
                )
            reg_cov = _safe_float(p.get("regime_coverage", 0.0), 0.0)
            reg_min = float(cfg.get("regime_coverage_min", 0.67))
            if reg_cov < reg_min:
                details.append(
                    self._rule_detail(
                        rule_id="confidence_score.regime_coverage",
                        gate=gate,
                        observed=float(reg_cov),
                        threshold=float(reg_min),
                        comparator=">=",
                    )
                )
            width = _safe_float(p.get("bootstrap_confidence_width", 9.99), 9.99)
            width_max = float(cfg.get("bootstrap_conf_width_max", 1.5))
            if width > width_max:
                details.append(
                    self._rule_detail(
                        rule_id="confidence_score.bootstrap_confidence_width",
                        gate=gate,
                        observed=float(width),
                        threshold=float(width_max),
                        comparator="<=",
                    )
                )
        elif gate == "leakage_proof":
            if not bool(p.get("passed", False)):
                details.append(
                    self._rule_detail(
                        rule_id="leakage_proof.temporal_order_violations",
                        gate=gate,
                        observed=int(_safe_int(p.get("temporal_order_violations", 0), 0)),
                        threshold=0,
                        comparator="==",
                    )
                )
        elif gate == "dependency_lock":
            if bool(p.get("changed", False)) and (not bool(p.get("approved_change_window", False))):
                details.append(
                    self._rule_detail(
                        rule_id="dependency_lock.changed_outside_approved_window",
                        gate=gate,
                        observed=bool(p.get("changed", False)),
                        threshold=False,
                        comparator="==",
                    )
                )
        elif gate == "resource_guard":
            runtime = _safe_float(p.get("cycle_runtime_sec", 0.0), 0.0)
            max_runtime = float(cfg.get("max_cycle_runtime_sec", 2400.0))
            rss = _safe_float(p.get("peak_rss_mb", 0.0), 0.0)
            max_rss = float(cfg.get("max_peak_rss_mb", 4096.0))
            if runtime > max_runtime:
                details.append(
                    self._rule_detail(
                        rule_id="resource_guard.cycle_runtime_sec",
                        gate=gate,
                        observed=float(runtime),
                        threshold=float(max_runtime),
                        comparator="<=",
                    )
                )
            if rss > max_rss:
                details.append(
                    self._rule_detail(
                        rule_id="resource_guard.peak_rss_mb",
                        gate=gate,
                        observed=float(rss),
                        threshold=float(max_rss),
                        comparator="<=",
                    )
                )
            if not bool(p.get("thread_cap_respected", True)):
                details.append(
                    self._rule_detail(
                        rule_id="resource_guard.thread_cap_respected",
                        gate=gate,
                        observed=bool(p.get("thread_cap_respected", False)),
                        threshold=True,
                        comparator="==",
                    )
                )
        elif gate == "model_risk_tier":
            if not bool(p.get("promotion_allowed", False)):
                details.append(
                    self._rule_detail(
                        rule_id="model_risk_tier.promotion_allowed",
                        gate=gate,
                        observed=bool(p.get("promotion_allowed", False)),
                        threshold=True,
                        comparator="==",
                    )
                )
        elif gate == "certification_timing":
            runtime = _safe_float(p.get("certification_runtime_sec", 0.0), 0.0)
            max_runtime = _safe_float(
                p.get("max_certification_runtime_sec", cfg.get("max_certification_runtime_sec", 180.0)),
                180.0,
            )
            share = _safe_float(p.get("certification_runtime_share", 0.0), 0.0)
            max_share = _safe_float(
                p.get("max_certification_runtime_share", cfg.get("max_certification_runtime_share", 0.60)),
                0.60,
            )
            if runtime > max_runtime:
                details.append(
                    self._rule_detail(
                        rule_id="certification_timing.max_runtime_sec",
                        gate=gate,
                        observed=float(runtime),
                        threshold=float(max_runtime),
                        comparator="<=",
                    )
                )
            if share > max_share:
                details.append(
                    self._rule_detail(
                        rule_id="certification_timing.max_runtime_share",
                        gate=gate,
                        observed=float(share),
                        threshold=float(max_share),
                        comparator="<=",
                    )
                )
        elif gate == "formula_lineage":
            unexplained = int(_safe_int((p.get("anomaly_normalization", {}) or {}).get("flatline_series_count", 0), 0))
            max_unexplained = int(_safe_int((p.get("anomaly_normalization", {}) or {}).get("max_unexplained_flatlines", cfg.get("lineage_max_unexplained_flatlines", 12)), 12))
            if unexplained > max_unexplained:
                details.append(
                    self._rule_detail(
                        rule_id="formula_lineage.max_unexplained_flatlines",
                        gate=gate,
                        observed=int(unexplained),
                        threshold=int(max_unexplained),
                        comparator="<=",
                    )
                )
        elif gate == "macro_unit_integrity":
            if not bool(p.get("metadata_available", False)) and bool(cfg.get("require_macro_unit_metadata", False)):
                details.append(
                    self._rule_detail(
                        rule_id="macro_unit_integrity.metadata_available",
                        gate=gate,
                        observed=bool(p.get("metadata_available", False)),
                        threshold=True,
                        comparator="==",
                    )
                )
            suspicious = p.get("suspicious_unit_usage", [])
            if isinstance(suspicious, list) and suspicious:
                details.append(
                    self._rule_detail(
                        rule_id="macro_unit_integrity.suspicious_unit_usage",
                        gate=gate,
                        observed=int(len(suspicious)),
                        threshold=0,
                        comparator="==",
                    )
                )
        return details

    def _evaluate_internal(self, ctx: CertificationContext) -> Dict[str, Any]:
        eval_start = time.perf_counter()
        gate_runtime_sec: Dict[str, float] = {}

        def _time_gate(name: str, fn: Any) -> Dict[str, Any]:
            t0 = time.perf_counter()
            out = fn()
            gate_runtime_sec[str(name)] = float(time.perf_counter() - t0)
            return out

        cycle_id = str(ctx.system_state.get("cycle_id", "") or ctx.completed_at.strftime("%Y%m%d_%H%M%S"))
        provenance = _time_gate("data_provenance", lambda: self._data_provenance(ctx.dataset_metadata))
        replay = _time_gate(
            "replay_certification",
            lambda: self._replay_certification(
                cycle_id=cycle_id,
                outputs=ctx.outputs,
                provenance=provenance,
                system_state=ctx.system_state,
            ),
        )
        universe = _time_gate("universe_integrity", lambda: self._universe_integrity(ctx.dataset_frame, ctx.dataset_metadata))
        strategy_corr = _time_gate("strategy_correlation_check", lambda: self._strategy_correlation_check(ctx.model_results))
        portfolio_int = _time_gate("portfolio_integrity", lambda: self._portfolio_integrity(ctx.best_payload, ctx.portfolio_cfg))
        blend_int = _time_gate("blend_integrity", lambda: self._blend_integrity(ctx.outputs))
        series_map = self._model_return_series(ctx.model_results)
        best_series = series_map.get(ctx.best_model, pd.Series(dtype=float))
        regime_eff = _time_gate("regime_effectiveness", lambda: self._regime_effectiveness(ctx.outputs, best_series, ctx.dataset_frame))
        objective_surface = _time_gate(
            "objective_surface_sanity",
            lambda: self._objective_surface_sanity(ctx.param_payload, ctx.weekend_run, ctx.best_model),
        )
        stat_rob = _time_gate(
            "statistical_robustness",
            lambda: self._statistical_robustness(best_series, regime_metrics=ctx.best_payload.get("regime_metrics", {})),
        )
        cap_scaling = _time_gate("capital_scaling_gate", lambda: self._capital_scaling_gate(best_series))
        time_agg = _time_gate("time_aggregation_check", lambda: self._time_aggregation_check(best_series))
        confidence = _time_gate("confidence_score", lambda: self._confidence_score(ctx.best_payload, stat_rob, regime_eff))
        leakage = _time_gate("leakage_proof", lambda: self._leakage_proof(ctx.best_payload))
        dep_lock = _time_gate("dependency_lock", lambda: self._dependency_lock())
        resource_guard = _time_gate("resource_guard", lambda: self._resource_guard(ctx.started_at, ctx.completed_at))
        formula_lineage = _time_gate(
            "formula_lineage",
            lambda: build_formula_lineage_report(
                project_root=self.project_root,
                dataset_metadata=ctx.dataset_metadata,
                cert_cfg=self.cert_cfg,
            ),
        )
        macro_unit_integrity = _time_gate(
            "macro_unit_integrity",
            lambda: build_macro_unit_integrity(
                project_root=self.project_root,
                cert_cfg=self.cert_cfg,
            ),
        )
        belief_layer_diag = _time_gate(
            "belief_layer_diagnostics",
            lambda: build_belief_layer_diagnostics(
                project_root=self.project_root,
                cert_cfg=self.cert_cfg,
            ),
        )

        gates: Dict[str, Dict[str, Any]] = {
            "data_provenance": provenance,
            "replay_certification": replay,
            "universe_integrity": universe,
            "strategy_correlation_check": strategy_corr,
            "portfolio_integrity": portfolio_int,
            "blend_integrity": blend_int,
            "regime_effectiveness": regime_eff,
            "objective_surface_sanity": objective_surface,
            "statistical_robustness": stat_rob,
            "capital_scaling_gate": cap_scaling,
            "time_aggregation_check": time_agg,
            "confidence_score": confidence,
            "leakage_proof": leakage,
            "dependency_lock": dep_lock,
            "resource_guard": resource_guard,
            "formula_lineage": formula_lineage,
            "macro_unit_integrity": macro_unit_integrity,
            "belief_layer_diagnostics": belief_layer_diag,
        }
        model_tier = _time_gate("model_risk_tier", lambda: self._model_risk_tier(ctx.best_model, gates))
        gates["model_risk_tier"] = model_tier

        certification_runtime_sec = float(time.perf_counter() - eval_start)
        cycle_runtime_sec = _safe_float(resource_guard.get("cycle_runtime_sec", 0.0), 0.0)
        runtime_share = (
            float(certification_runtime_sec / cycle_runtime_sec)
            if cycle_runtime_sec > 1e-9
            else 0.0
        )
        max_cert_runtime_sec = float(
            self.cert_cfg.get(
                "max_certification_runtime_sec",
                min(
                    float(self.cert_cfg.get("max_cycle_runtime_sec", 2400.0)),
                    300.0,
                ),
            )
        )
        timing_gate = {
            "certification_runtime_sec": float(certification_runtime_sec),
            "max_certification_runtime_sec": float(max_cert_runtime_sec),
            "cycle_runtime_sec": float(cycle_runtime_sec),
            "certification_runtime_share": float(runtime_share),
            "max_certification_runtime_share": float(
                self.cert_cfg.get("max_certification_runtime_share", 0.60)
            ),
            "gate_runtime_sec": dict(gate_runtime_sec),
            "passed": bool(
                (certification_runtime_sec <= max_cert_runtime_sec)
                and (runtime_share <= float(self.cert_cfg.get("max_certification_runtime_share", 0.60)))
            ),
        }
        gates["certification_timing"] = timing_gate

        advisories, escalated = self._advisory_gates(ctx.outputs, ctx.dataset_metadata)
        critical_failures: List[str] = []
        failure_details: List[Dict[str, Any]] = []
        for name, payload in gates.items():
            if name == "model_risk_tier":
                continue
            if not bool((payload or {}).get("passed", False)):
                critical_failures.append(name)
                failure_details.extend(self._failure_details_for_gate(name, payload, ctx))
        for a in escalated:
            critical_failures.append(f"advisory_escalated:{a}")
            failure_details.append(
                self._rule_detail(
                    rule_id=f"advisory_persistence.{a}",
                    gate="advisory_escalation",
                    observed=int(_safe_int((self.state.get("advisory_streaks", {}) or {}).get(a, 0), 0)),
                    threshold=int(self.cert_cfg.get("advisory_persistence_limit", 5)),
                    comparator="<",
                )
            )

        overfit_shadow_audit = build_gate_overfitting_shadow_audit(
            critical_failure_details=failure_details,
            cert_cfg=self.cert_cfg,
        )

        burn_prev = self.state.get("burn_in", {})
        burn_prev_pass = bool((burn_prev or {}).get("certification_passed", False)) if isinstance(burn_prev, Mapping) else False
        if bool(ctx.system_state.get("override_integrity_failures", False)) and (not burn_prev_pass):
            critical_failures.append("manual_override_forbidden_during_certification")
            failure_details.append(
                self._rule_detail(
                    rule_id="burn_in.manual_override_forbidden_during_burn_in",
                    gate="burn_in",
                    observed=True,
                    threshold=False,
                    comparator="==",
                )
            )

        if not bool(model_tier.get("promotion_allowed", False)):
            critical_failures.append("model_risk_tier_block")
            failure_details.extend(self._failure_details_for_gate("model_risk_tier", model_tier, ctx))

        # Ensure every gate-level failure has a trace row, even if specialized mapping missed it.
        traced_gates = {str(d.get("gate", "")) for d in failure_details}
        for gate_name in sorted(set(critical_failures)):
            if gate_name.startswith("advisory_escalated:"):
                continue
            if gate_name in traced_gates:
                continue
            failure_details.append(
                self._rule_detail(
                    rule_id=f"{gate_name}.passed",
                    gate=gate_name,
                    observed=False,
                    threshold=True,
                    comparator="==",
                )
            )

        burn = self._update_burn_in(
            critical_failures=critical_failures,
            freeze_active=ctx.freeze_active,
            observed_regimes=self._observed_regimes(ctx.outputs),
            system_state=ctx.system_state,
        )
        cert_pass = bool((not critical_failures) and bool(burn.get("certification_passed", False)))
        created_at = datetime.now(timezone.utc)
        ttl_days = int(_safe_int(self.cert_cfg.get("ttl_days", 30), 30))
        valid_until = created_at + timedelta(days=max(1, ttl_days))
        model_hash = _hash_jsonable({"best_model": str(ctx.best_model or "")})
        param_hash = _hash_jsonable(dict(ctx.param_payload or {}))
        feature_hash = str(ctx.dataset_metadata.get("feature_hash", "") or "")
        if not feature_hash:
            feature_hash = _hash_jsonable(
                sorted(
                    [
                        str(c)
                        for c in list(ctx.dataset_frame.columns)
                        if str(c).lower() not in {"date", "ticker", "regime", "return_data_mode"}
                    ]
                )
            )
        data_revision_hash = _hash_jsonable(
            {
                "universe_hash": str(ctx.dataset_metadata.get("universe_hash", "") or ""),
                "price_hash": str(ctx.dataset_metadata.get("price_hash", "") or ""),
                "label_hash": str(ctx.dataset_metadata.get("label_hash", "") or ""),
            }
        )
        config_hash = _hash_jsonable(dict(self.config or {}))
        drift_guard_version = str(self.cert_cfg.get("drift_guard_version", "v1") or "v1")
        cert_snapshot = {
            "model_hash": model_hash,
            "param_hash": param_hash,
            "feature_hash": feature_hash,
            "data_revision_hash": data_revision_hash,
            "config_hash": config_hash,
            "created_at": created_at.isoformat(),
            "valid_until": valid_until.isoformat(),
            "drift_guard_version": drift_guard_version,
        }
        cert_snapshot_hash = _hash_jsonable(cert_snapshot)
        cert_snapshot["snapshot_hash"] = cert_snapshot_hash

        out = {
            "integrity_summary": {
                "mode": str(self.mode),
                "enforcement_active": bool(self.mode == "enforce"),
                "certification_enabled": bool(self.enabled),
                "hard_fail_triggered": bool(len(critical_failures) > 0),
                "critical_failures": list(sorted(set(critical_failures))),
                "critical_rule_failures": sorted({str(d.get("rule_id", "")) for d in failure_details if str(d.get("rule_id", ""))}),
                "critical_failure_details": failure_details,
                "advisory_warnings": list(sorted(set(advisories))),
                "certification_runtime_sec": float(certification_runtime_sec),
                "threshold_pressure_ratio": float(overfit_shadow_audit.get("threshold_pressure_ratio", 0.0)),
                "certification_passed": bool(cert_pass),
                "certification_snapshot_hash": cert_snapshot_hash,
            },
            **gates,
            "gate_overfitting_audit": overfit_shadow_audit,
            "burn_in_status": burn,
            "certification_snapshot": cert_snapshot,
        }
        return out

    def compute(self, ctx: CertificationContext, prior_state: Optional[Mapping[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Pure certification computation.

        Consumes a context object + prior state snapshot and returns:
        (certification_output, next_state) with no disk writes.
        """
        source_state = prior_state if isinstance(prior_state, Mapping) else self.state
        working_state: Dict[str, Any] = copy.deepcopy(dict(source_state or {}))
        prev_state = self.state
        self.state = working_state
        try:
            out = self._evaluate_internal(ctx)
            next_state = copy.deepcopy(self.state)
        finally:
            self.state = prev_state
        return out, next_state

    def evaluate(self, ctx: CertificationContext) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "integrity_summary": {
                    "mode": str(self.mode),
                    "enforcement_active": False,
                    "certification_enabled": False,
                    "hard_fail_triggered": False,
                    "critical_failures": [],
                    "critical_rule_failures": [],
                    "critical_failure_details": [],
                    "advisory_warnings": [],
                    "certification_runtime_sec": 0.0,
                    "certification_passed": True,
                    "certification_snapshot_hash": "",
                }
            }
        out, next_state = self.compute(ctx, prior_state=self.state)
        self.state = next_state
        self._save_state()
        return out
