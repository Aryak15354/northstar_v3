"""Transformer window-artifact discovery and stability diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import json

import numpy as np
import pandas as pd

from .feature_stability import compute_feature_stability_report
from .transformer_model import TimeSeriesTransformerNet


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def safe_spearman(a: Sequence[float], b: Sequence[float]) -> float:
    x = np.asarray(a, dtype=float).reshape(-1)
    y = np.asarray(b, dtype=float).reshape(-1)
    if len(x) != len(y) or len(x) == 0:
        return 0.0
    x_const = bool(np.allclose(x, x[0], equal_nan=True))
    y_const = bool(np.allclose(y, y[0], equal_nan=True))
    if x_const and y_const:
        return 1.0 if np.allclose(x, y, equal_nan=True) else 0.0
    if x_const or y_const:
        return 0.0
    xr = pd.Series(x).rank(method="average")
    yr = pd.Series(y).rank(method="average")
    corr = xr.corr(yr)
    return 0.0 if corr is None or not np.isfinite(float(corr)) else float(corr)


def discover_transformer_artifacts(experiment_dir: str | Path) -> dict[str, Any]:
    exp_dir = Path(experiment_dir).expanduser().resolve()
    search_roots = [
        exp_dir / "transformer",
        exp_dir / "models" / "transformer",
        exp_dir / "window_artifacts" / "transformer",
        exp_dir / "window_artifacts",
        exp_dir / "seed_results",
    ]
    existing_roots = [path for path in search_roots if path.exists()]

    seed_files = sorted((exp_dir / "seed_results").glob("transformer_seed_*.json"))
    referenced_dirs: set[Path] = set()
    referenced_files: set[Path] = set()
    seed_payloads: list[dict[str, Any]] = []

    for seed_file in seed_files:
        try:
            payload = json.loads(seed_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        seed_payloads.append(payload)
        raw_dir = str(payload.get("window_artifact_dir", "") or "").strip()
        if raw_dir:
            referenced_dirs.add(Path(raw_dir).expanduser().resolve())
        full_result = dict(payload.get("full_result", {}) or {})
        for window in list(full_result.get("windows", []) or []):
            raw_path = str(window.get("artifact_path", "") or "").strip()
            if raw_path:
                referenced_files.add(Path(raw_path).expanduser().resolve())

    candidate_files: set[Path] = set()
    for root in existing_roots + sorted(referenced_dirs):
        if not root.exists():
            continue
        if root.is_file():
            candidate_files.add(root.resolve())
            continue
        for pattern in ("*.pt", "*.pth", "*.bin", "*.ckpt"):
            for path in root.rglob(pattern):
                name = path.name.lower()
                parent = str(path.parent).lower()
                if "transformer" in name or "transformer" in parent or "window_" in name:
                    candidate_files.add(path.resolve())
    for path in referenced_files:
        if path.exists():
            candidate_files.add(path.resolve())

    bundle_files = sorted(
        [
            path for path in candidate_files
            if "window_" in path.name.lower() or "window_artifacts" in str(path.parent).lower()
        ]
    )
    return {
        "experiment_dir": str(exp_dir),
        "search_roots": [str(path) for path in search_roots],
        "existing_search_roots": [str(path) for path in existing_roots],
        "seed_files": [str(path.resolve()) for path in seed_files],
        "referenced_artifact_dirs": [str(path) for path in sorted(referenced_dirs)],
        "referenced_artifact_files": [str(path) for path in sorted(referenced_files)],
        "candidate_artifact_files": [str(path) for path in sorted(candidate_files)],
        "window_bundle_files": [str(path) for path in bundle_files],
    }


def resolve_transformer_ratio(experiment_dir: str | Path) -> float | None:
    exp_dir = Path(experiment_dir).expanduser().resolve()
    model_summary = exp_dir / "model_summaries" / "transformer.json"
    if model_summary.exists():
        try:
            payload = json.loads(model_summary.read_text(encoding="utf-8"))
            return safe_float(payload.get("train_test_ratio", np.nan), np.nan)
        except Exception:
            pass

    summary_json = exp_dir / "summary.json"
    if summary_json.exists():
        try:
            payload = json.loads(summary_json.read_text(encoding="utf-8"))
            rows = list(payload.get("model_comparison", []) or payload.get("models", []) or [])
            for row in rows:
                if str(row.get("model", "")).strip().lower() == "transformer":
                    return safe_float(row.get("train_test_ratio", np.nan), np.nan)
        except Exception:
            pass

    seed_files = sorted((exp_dir / "seed_results").glob("transformer_seed_*.json"))
    ratios = []
    for seed_file in seed_files:
        try:
            payload = json.loads(seed_file.read_text(encoding="utf-8"))
            ratios.append(safe_float(dict(payload.get("seed_summary", {}) or {}).get("train_test_ratio", np.nan), np.nan))
        except Exception:
            continue
    ratios = [x for x in ratios if np.isfinite(x)]
    return float(np.mean(ratios)) if ratios else None


def load_window_bundle(path: str | Path) -> dict[str, Any]:
    import torch

    bundle_path = Path(path).expanduser().resolve()
    try:
        payload = torch.load(str(bundle_path), map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(str(bundle_path), map_location="cpu")
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_transformer_bundle:{bundle_path}")
    return payload


def bundle_feature_entries(bundle: Mapping[str, Any]) -> list[tuple[str, int, str]]:
    meta = dict(bundle.get("feature_meta", {}) or {})
    out: list[tuple[str, int, str]] = []
    for prefix, key in (
        ("obs", "observed_feature_names"),
        ("known", "known_feature_names"),
        ("static", "static_feature_names"),
    ):
        for idx, name in enumerate(list(meta.get(key, []) or [])):
            out.append((prefix, int(idx), f"{prefix}::{str(name)}"))
    return out


def restore_transformer_model(bundle: Mapping[str, Any]):
    import torch

    if str(bundle.get("mode", "")).strip().lower() != "torch":
        raise RuntimeError("transformer_bundle_is_not_native_torch")
    arch = dict(bundle.get("architecture", {}) or {})
    net = TimeSeriesTransformerNet(
        observed_dim=int(arch.get("observed_dim", 0)),
        known_dim=int(arch.get("known_dim", 0)),
        static_dim=int(arch.get("static_dim", 0)),
        d_model=int(arch.get("d_model", 64)),
        nhead=int(arch.get("nhead", 4)),
        num_layers=int(arch.get("num_layers", 2)),
        dim_feedforward=int(arch.get("dim_feedforward", 128)),
        dropout=float(arch.get("dropout", 0.1)),
        max_len=int(arch.get("max_len", 512)),
        n_tickers=int(arch.get("n_tickers", 0)),
        n_sectors=int(arch.get("n_sectors", 0)),
        embed_dim=int(arch.get("embed_dim", 16)),
    )
    state = dict(bundle.get("model_state", {}) or {})
    net.load_state_dict(state)
    net.eval()
    return net


def predict_from_bundle(
    bundle: Mapping[str, Any],
    *,
    obs: np.ndarray | None = None,
    known: np.ndarray | None = None,
    static: np.ndarray | None = None,
) -> np.ndarray:
    import torch

    net = restore_transformer_model(bundle)
    ctx = dict(bundle.get("context", {}) or {})
    obs_arr = np.asarray(obs if obs is not None else ctx.get("obs", np.empty((0, 0, 0), dtype=np.float32)), dtype=np.float32)
    known_arr = np.asarray(known if known is not None else ctx.get("known", np.empty((len(obs_arr), obs_arr.shape[1] if obs_arr.ndim == 3 else 0, 0), dtype=np.float32)), dtype=np.float32)
    static_arr = np.asarray(static if static is not None else ctx.get("static", np.empty((len(obs_arr), 0), dtype=np.float32)), dtype=np.float32)
    ticker_ids = np.asarray(ctx.get("ticker_ids", np.zeros(len(obs_arr), dtype=np.int64)), dtype=np.int64)
    sector_ids = np.asarray(ctx.get("sector_ids", np.zeros(len(obs_arr), dtype=np.int64)), dtype=np.int64)

    obs_t = torch.tensor(obs_arr, dtype=torch.float32)
    known_t = torch.tensor(known_arr, dtype=torch.float32) if known_arr.ndim == 3 and known_arr.shape[2] > 0 else None
    static_t = torch.tensor(static_arr, dtype=torch.float32) if static_arr.ndim == 2 and static_arr.shape[1] > 0 else None
    ticker_t = torch.tensor(ticker_ids, dtype=torch.long)
    sector_t = torch.tensor(sector_ids, dtype=torch.long)
    with torch.no_grad():
        pred = (
            net(
                observed=obs_t,
                known=known_t,
                static=static_t,
                ticker_id=ticker_t,
                sector_id=sector_t,
            )["return_pred"]
            .detach()
            .cpu()
            .numpy()
            .reshape(-1)
        )
    return np.asarray(pred, dtype=float).reshape(-1)


def gradient_importance(bundle: Mapping[str, Any]) -> dict[str, float]:
    import torch

    net = restore_transformer_model(bundle)
    ctx = dict(bundle.get("context", {}) or {})
    feature_entries = bundle_feature_entries(bundle)

    obs = torch.tensor(np.asarray(ctx.get("obs", np.empty((0, 0, 0), dtype=np.float32)), dtype=np.float32), dtype=torch.float32, requires_grad=True)
    known_arr = np.asarray(ctx.get("known", np.empty((len(obs), obs.shape[1] if obs.ndim == 3 else 0, 0), dtype=np.float32)), dtype=np.float32)
    static_arr = np.asarray(ctx.get("static", np.empty((len(obs), 0), dtype=np.float32)), dtype=np.float32)
    known = torch.tensor(known_arr, dtype=torch.float32, requires_grad=True) if known_arr.ndim == 3 and known_arr.shape[2] > 0 else None
    static = torch.tensor(static_arr, dtype=torch.float32, requires_grad=True) if static_arr.ndim == 2 and static_arr.shape[1] > 0 else None
    ticker_ids = torch.tensor(np.asarray(ctx.get("ticker_ids", np.zeros(len(obs), dtype=np.int64)), dtype=np.int64), dtype=torch.long)
    sector_ids = torch.tensor(np.asarray(ctx.get("sector_ids", np.zeros(len(obs), dtype=np.int64)), dtype=np.int64), dtype=torch.long)

    net.zero_grad(set_to_none=True)
    out = net(observed=obs, known=known, static=static, ticker_id=ticker_ids, sector_id=sector_ids)["return_pred"]
    out.sum().backward()

    importance: dict[str, float] = {}
    for group, idx, name in feature_entries:
        if group == "obs":
            grad = obs.grad[:, :, idx]
        elif group == "known" and known is not None and known.grad is not None:
            grad = known.grad[:, :, idx]
        elif group == "static" and static is not None and static.grad is not None:
            grad = static.grad[:, idx]
        else:
            importance[name] = 0.0
            continue
        importance[name] = float(grad.detach().abs().mean().cpu().item())
    return importance


def permutation_importance(
    bundle: Mapping[str, Any],
    *,
    random_state: int = 42,
) -> dict[str, Any]:
    ctx = dict(bundle.get("context", {}) or {})
    y = np.asarray(ctx.get("y", np.empty((0,), dtype=np.float32)), dtype=float).reshape(-1)
    obs = np.asarray(ctx.get("obs", np.empty((0, 0, 0), dtype=np.float32)), dtype=np.float32)
    known = np.asarray(ctx.get("known", np.empty((len(obs), obs.shape[1] if obs.ndim == 3 else 0, 0), dtype=np.float32)), dtype=np.float32)
    static = np.asarray(ctx.get("static", np.empty((len(obs), 0), dtype=np.float32)), dtype=np.float32)

    base_pred = np.asarray(bundle.get("baseline_predictions", np.empty((0,), dtype=np.float32)), dtype=float).reshape(-1)
    if len(base_pred) != len(y):
        base_pred = predict_from_bundle(bundle, obs=obs, known=known, static=static)
    base_ic = safe_spearman(y, base_pred)

    rng = np.random.default_rng(int(random_state))
    importance: dict[str, float] = {}
    for group, idx, name in bundle_feature_entries(bundle):
        order = rng.permutation(len(y))
        obs_perm = obs
        known_perm = known
        static_perm = static
        if group == "obs":
            obs_perm = np.array(obs, copy=True)
            obs_perm[:, :, idx] = obs_perm[order, :, idx]
        elif group == "known":
            known_perm = np.array(known, copy=True)
            known_perm[:, :, idx] = known_perm[order, :, idx]
        else:
            static_perm = np.array(static, copy=True)
            static_perm[:, idx] = static_perm[order, idx]
        perm_pred = predict_from_bundle(bundle, obs=obs_perm, known=known_perm, static=static_perm)
        perm_ic = safe_spearman(y, perm_pred)
        importance[name] = float(base_ic - perm_ic)
    return {
        "baseline_ic": float(base_ic),
        "importances": importance,
    }


def compute_window_importance(
    bundle: Mapping[str, Any],
    *,
    method: str = "auto",
    permutation_max_features: int = 64,
    random_state: int = 42,
) -> dict[str, Any]:
    feature_count = int(len(bundle_feature_entries(bundle)))
    chosen = str(method or "auto").strip().lower()
    if chosen not in {"auto", "permutation", "gradient"}:
        chosen = "auto"
    if chosen == "auto":
        chosen = "permutation" if feature_count <= max(1, int(permutation_max_features)) else "gradient"

    if chosen == "permutation":
        payload = permutation_importance(bundle, random_state=random_state)
        return {
            "method": "permutation",
            "baseline_ic": float(payload.get("baseline_ic", 0.0)),
            "feature_importance": dict(payload.get("importances", {}) or {}),
            "feature_count": feature_count,
        }

    importance = gradient_importance(bundle)
    y = np.asarray(dict(bundle.get("context", {}) or {}).get("y", np.empty((0,), dtype=np.float32)), dtype=float).reshape(-1)
    base_pred = np.asarray(bundle.get("baseline_predictions", np.empty((0,), dtype=np.float32)), dtype=float).reshape(-1)
    baseline_ic = safe_spearman(y, base_pred) if len(base_pred) == len(y) else 0.0
    return {
        "method": "gradient",
        "baseline_ic": float(baseline_ic),
        "feature_importance": importance,
        "feature_count": feature_count,
    }


def compute_seed_transformer_stability(
    bundle_paths: Sequence[str | Path],
    *,
    method: str = "auto",
    top_k: int = 15,
    permutation_max_features: int = 64,
    random_state: int = 42,
) -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    methods_used: list[str] = []
    for i, bundle_path in enumerate(sorted([Path(p).expanduser().resolve() for p in bundle_paths]), start=1):
        bundle = load_window_bundle(bundle_path)
        if str(bundle.get("artifact_type", "")).strip().lower() != "transformer_window_bundle":
            continue
        importance_payload = compute_window_importance(
            bundle,
            method=method,
            permutation_max_features=permutation_max_features,
            random_state=random_state + i,
        )
        methods_used.append(str(importance_payload.get("method", "unknown")))
        split = dict(bundle.get("split", {}) or {})
        windows.append(
            {
                "train_start": str(split.get("train_start", "") or ""),
                "train_end": str(split.get("train_end", "") or ""),
                "test_start": str(split.get("test_start", "") or ""),
                "test_end": str(split.get("test_end", "") or ""),
                "feature_importance": dict(importance_payload.get("feature_importance", {}) or {}),
                "artifact_path": str(bundle_path),
                "importance_method": str(importance_payload.get("method", "unknown")),
                "baseline_ic": float(importance_payload.get("baseline_ic", 0.0)),
            }
        )
    report = compute_feature_stability_report(windows, top_k=top_k)
    report["importance_methods_used"] = methods_used
    report["window_bundle_files"] = [str(Path(p).expanduser().resolve()) for p in bundle_paths]
    return report
