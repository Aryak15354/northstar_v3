#!/usr/bin/env python3
"""Run Northstar V3 temporal sequence experiments on the tensor export.

This runner reopens EXP-20..EXP-23 after the sequence dataset exists. It reads
the validated shard format produced by ``sequence_export/build_sequence_export.py``:

  sample_index.parquet
  static_features.parquet
  sequence_walk_forward_splits.json
  sequence_shards/seq_shard_*.npz

Outputs are written per experiment as window metrics, aggregate summary JSON,
and optional prediction CSVs.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
    from torch.amp import GradScaler, autocast
except Exception as exc:  # pragma: no cover - friendly runtime error in Kaggle.
    raise SystemExit(
        "PyTorch is required for EXP-20..EXP-23 sequence experiments. "
        "In Kaggle run: !pip install -q torch"
    ) from exc


EVENT_WINDOWS = [
    {
        "name": "budget_2024_ltcg_stt_buyback_tax_shock",
        "test_start": "2024-06-28",
        "test_end": "2024-09-20",
    },
    {
        "name": "post_budget_2024_microstructure_repricing",
        "test_start": "2024-09-27",
        "test_end": "2024-12-20",
    },
    {
        "name": "post_nifty_peak_correction",
        "test_start": "2024-12-27",
        "test_end": "2025-06-20",
    },
]

RATIO_EPS = 0.002
RATIO_CAP = 10.0

EXPERIMENTS = {
    "EXP-20": {
        "name": "lstm_temporal_ranker",
        "description": "Two-layer LSTM over 60-day OHLCV, macro, sentiment, and alternative-data tensors.",
        "model": "lstm",
        "uses_static": False,
    },
    "EXP-21": {
        "name": "gru_temporal_ranker",
        "description": "Two-layer GRU temporal model for sequence-signal baseline.",
        "model": "gru",
        "uses_static": False,
    },
    "EXP-22": {
        "name": "transformer_temporal_ranker",
        "description": "Compact Transformer encoder over daily lookback tensors.",
        "model": "transformer",
        "uses_static": False,
    },
    "EXP-23": {
        "name": "hybrid_lstm_static_ranker",
        "description": "LSTM temporal encoder blended with weekly static feature MLP.",
        "model": "hybrid_lstm_static",
        "uses_static": True,
    },
}


def log(msg: str) -> None:
    print(msg, flush=True)


def json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    return obj


def resolve_sequence_dir(user_path: str | None) -> Path:
    candidates = []
    if user_path:
        candidates.append(user_path)
    candidates.extend(
        [
            "/kaggle/input/datasets/aryakghoshal/northstar-v3-sequence-export",
            "/kaggle/input/northstar-v3-sequence-export",
            "/kaggle/working/northstar_v3_sequence_export",
            "tmp/kaggle_sequence_export",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if (path / "sequence_walk_forward_splits.json").exists() and (path / "sequence_shards").exists():
            return path
    raise FileNotFoundError(
        "Could not find sequence export. Attach/create northstar-v3-sequence-export or pass --sequence-dir."
    )


def is_event_window(test_start: str, test_end: str) -> tuple[bool, str | None]:
    start = datetime.strptime(test_start, "%Y-%m-%d")
    end = datetime.strptime(test_end, "%Y-%m-%d")
    for event in EVENT_WINDOWS:
        ev_start = datetime.strptime(event["test_start"], "%Y-%m-%d")
        ev_end = datetime.strptime(event["test_end"], "%Y-%m-%d")
        if start <= ev_end and end >= ev_start:
            return True, event["name"]
    return False, None


def spearman_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if int(mask.sum()) < 10:
        return float("nan")
    value, _ = stats.spearmanr(y_pred[mask], y_true[mask])
    return float(value) if np.isfinite(value) else float("nan")


def cross_sectional_ic(frame: pd.DataFrame) -> dict[str, Any]:
    ics = []
    rows = []
    for date, group in frame.groupby("date", sort=True):
        ic = spearman_ic(group["y"].to_numpy(float), group["pred"].to_numpy(float))
        rows.append({"date": str(pd.Timestamp(date).date()), "ic": ic, "n": int(len(group))})
        if np.isfinite(ic):
            ics.append(ic)
    arr = np.asarray(ics, dtype=float)
    return {
        "mean_ic": float(arr.mean()) if arr.size else None,
        "median_ic": float(np.median(arr)) if arr.size else None,
        "ic_ir": float(arr.mean() / (arr.std(ddof=1) + 1e-12)) if arr.size > 1 else None,
        "hit_rate": float((arr > 0).mean()) if arr.size else None,
        "n_dates": int(arr.size),
        "daily_rows": rows,
    }


def train_test_ratio(train_ic: float | None, test_ic: float | None) -> tuple[float | None, float | None, bool]:
    if train_ic is None or test_ic is None or not np.isfinite(train_ic) or not np.isfinite(test_ic):
        return None, None, False
    raw = abs(float(train_ic)) / (abs(float(test_ic)) + 1e-12)
    robust = abs(float(train_ic)) / max(abs(float(test_ic)), RATIO_EPS)
    capped = min(robust, RATIO_CAP)
    return raw, capped, bool(robust > RATIO_CAP)


@dataclass
class SequenceStore:
    seq_dir: Path
    sample_index: pd.DataFrame
    static: pd.DataFrame
    splits: list[dict[str, Any]]
    shard_map: dict[int, tuple[Path, int]]
    static_cols: list[str]

    @classmethod
    def open(cls, seq_dir: Path) -> "SequenceStore":
        sample_index = pd.read_parquet(seq_dir / "sample_index.parquet")
        sample_index["date"] = pd.to_datetime(sample_index["date"]).dt.normalize()
        static = pd.read_parquet(seq_dir / "static_features.parquet")
        static["date"] = pd.to_datetime(static["date"]).dt.normalize()
        splits = json.loads((seq_dir / "sequence_walk_forward_splits.json").read_text()).get("windows", [])
        shard_map: dict[int, tuple[Path, int]] = {}
        for shard in sorted((seq_dir / "sequence_shards").glob("seq_shard_*.npz")):
            payload = np.load(shard)
            ids = payload["sample_id"].astype(int)
            for pos, sample_id in enumerate(ids.tolist()):
                shard_map[int(sample_id)] = (shard, int(pos))
        static_cols = [
            c
            for c in static.columns
            if c not in {"sample_id", "date", "ticker"} and pd.api.types.is_numeric_dtype(static[c])
        ]
        return cls(seq_dir, sample_index, static, splits, shard_map, static_cols)

    def _ordered_ids(self, ids: list[int], cap: int | None, seed: int) -> list[int]:
        ids = [int(x) for x in ids if int(x) in self.shard_map]
        if cap and len(ids) > cap:
            rng = np.random.default_rng(seed)
            ids = sorted(rng.choice(np.asarray(ids, dtype=np.int64), size=cap, replace=False).astype(int).tolist())
        return ids

    def load_arrays(
        self,
        ids: list[int],
        *,
        max_samples: int | None,
        seed: int,
        include_mask: bool,
        include_static: bool,
    ) -> dict[str, Any]:
        ids = self._ordered_ids(ids, max_samples, seed)
        if not ids:
            raise ValueError("No sample ids available after filtering/capping.")
        requested = set(ids)
        by_shard: dict[Path, list[tuple[int, int]]] = {}
        for out_pos, sample_id in enumerate(ids):
            shard, shard_pos = self.shard_map[sample_id]
            by_shard.setdefault(shard, []).append((out_pos, shard_pos))

        first_payload = np.load(next(iter(by_shard)))
        x_shape = first_payload["X_temporal"].shape[1:]
        channels = x_shape[1] * (2 if include_mask else 1)
        X = np.empty((len(ids), x_shape[0], channels), dtype=np.float32)
        y = np.empty((len(ids),), dtype=np.float32)
        for shard, positions in by_shard.items():
            payload = np.load(shard)
            shard_positions = np.asarray([p[1] for p in positions], dtype=np.int64)
            out_positions = np.asarray([p[0] for p in positions], dtype=np.int64)
            x_part = payload["X_temporal"][shard_positions].astype(np.float32, copy=False)
            if include_mask:
                mask_part = payload["X_mask"][shard_positions].astype(np.float32, copy=False)
                x_part = np.concatenate([x_part, mask_part], axis=2)
            X[out_positions] = x_part
            y[out_positions] = payload["y"][shard_positions].astype(np.float32, copy=False)

        meta = self.sample_index[self.sample_index["sample_id"].isin(requested)].copy()
        meta["_order"] = pd.Categorical(meta["sample_id"].astype(int), categories=ids, ordered=True)
        meta = meta.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
        out: dict[str, Any] = {"ids": ids, "X": X, "y": y, "meta": meta}

        if include_static:
            static = self.static[self.static["sample_id"].isin(requested)].copy()
            static["_order"] = pd.Categorical(static["sample_id"].astype(int), categories=ids, ordered=True)
            static = static.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
            S = static[self.static_cols].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32)
            out["S"] = S
        return out


class LSTMRegressor(nn.Module):
    def __init__(self, input_dim: int, hidden: int, layers: int, dropout: float) -> None:
        super().__init__()
        self.rnn = nn.LSTM(input_dim, hidden, num_layers=layers, batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, hidden // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden // 2, 1))

    def forward(self, x: torch.Tensor, s: torch.Tensor | None = None) -> torch.Tensor:
        out, _ = self.rnn(x)
        return self.head(out[:, -1, :]).squeeze(-1)


class GRURegressor(nn.Module):
    def __init__(self, input_dim: int, hidden: int, layers: int, dropout: float) -> None:
        super().__init__()
        self.rnn = nn.GRU(input_dim, hidden, num_layers=layers, batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, hidden // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden // 2, 1))

    def forward(self, x: torch.Tensor, s: torch.Tensor | None = None) -> torch.Tensor:
        out, _ = self.rnn(x)
        return self.head(out[:, -1, :]).squeeze(-1)


class TransformerRegressor(nn.Module):
    def __init__(self, input_dim: int, hidden: int, layers: int, dropout: float, seq_len: int) -> None:
        super().__init__()
        d_model = max(64, hidden)
        self.proj = nn.Linear(input_dim, d_model)
        self.pos = nn.Parameter(torch.zeros(1, seq_len, d_model))
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=4,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=layers)
        self.head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, d_model // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(d_model // 2, 1))

    def forward(self, x: torch.Tensor, s: torch.Tensor | None = None) -> torch.Tensor:
        z = self.proj(x) + self.pos[:, : x.shape[1], :]
        z = self.encoder(z)
        return self.head(z.mean(dim=1)).squeeze(-1)


class HybridLSTMStaticRegressor(nn.Module):
    def __init__(self, input_dim: int, static_dim: int, hidden: int, layers: int, dropout: float) -> None:
        super().__init__()
        self.rnn = nn.LSTM(input_dim, hidden, num_layers=layers, batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.static_net = nn.Sequential(nn.Linear(static_dim, hidden), nn.LayerNorm(hidden), nn.GELU(), nn.Dropout(dropout))
        self.head = nn.Sequential(nn.LayerNorm(hidden * 2), nn.Linear(hidden * 2, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, 1))

    def forward(self, x: torch.Tensor, s: torch.Tensor | None = None) -> torch.Tensor:
        if s is None:
            raise ValueError("Hybrid model requires static features.")
        out, _ = self.rnn(x)
        return self.head(torch.cat([out[:, -1, :], self.static_net(s)], dim=1)).squeeze(-1)


def make_model(exp: dict[str, Any], input_dim: int, seq_len: int, static_dim: int, args: argparse.Namespace) -> nn.Module:
    if exp["model"] == "lstm":
        return LSTMRegressor(input_dim, args.hidden_dim, args.layers, args.dropout)
    if exp["model"] == "gru":
        return GRURegressor(input_dim, args.hidden_dim, args.layers, args.dropout)
    if exp["model"] == "transformer":
        return TransformerRegressor(input_dim, args.hidden_dim, args.layers, args.dropout, seq_len)
    if exp["model"] == "hybrid_lstm_static":
        return HybridLSTMStaticRegressor(input_dim, static_dim, args.hidden_dim, args.layers, args.dropout)
    raise ValueError(f"Unknown model type: {exp['model']}")


def sequence_capacity_args(args: argparse.Namespace, train_samples: int) -> argparse.Namespace:
    """Scale temporal model capacity for early chronological windows."""
    local = argparse.Namespace(**vars(args))
    local.warmup_window = False
    local.capacity_tier = "production"
    if train_samples < 25_000:
        local.warmup_window = True
        if train_samples < 8_000:
            local.capacity_tier = "warmup_tiny"
            local.hidden_dim = min(local.hidden_dim, 48)
            local.layers = 1
            local.dropout = max(local.dropout, 0.25)
            local.epochs = min(local.epochs, 5)
            local.patience = min(local.patience, 2)
        elif train_samples < 15_000:
            local.capacity_tier = "warmup_small"
            local.hidden_dim = min(local.hidden_dim, 64)
            local.layers = 1
            local.dropout = max(local.dropout, 0.25)
            local.epochs = min(local.epochs, 6)
        else:
            local.capacity_tier = "warmup_medium"
            local.hidden_dim = min(local.hidden_dim, 80)
            local.layers = min(local.layers, 2)
            local.epochs = min(local.epochs, 7)
    return local


def normalize_temporal(train_x: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    mean = train_x.mean(axis=(0, 1), keepdims=True)
    std = train_x.std(axis=(0, 1), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return tuple(((x - mean) / std).astype(np.float32) for x in (train_x, *others))


def normalize_static(train_s: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    train_s = np.nan_to_num(train_s, nan=0.0, posinf=0.0, neginf=0.0)
    mean = np.nanmean(train_s, axis=0, keepdims=True)
    std = np.nanstd(train_s, axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    outputs = [((train_s - mean) / std).astype(np.float32)]
    for arr in others:
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        outputs.append(((arr - mean) / std).astype(np.float32))
    return tuple(outputs)


def split_fit_val(meta: pd.DataFrame, val_fraction: float) -> tuple[np.ndarray, np.ndarray]:
    dates = sorted(pd.to_datetime(meta["date"]).unique())
    if len(dates) < 10:
        cutoff = max(1, int(len(meta) * (1.0 - val_fraction)))
        fit_idx = np.arange(cutoff)
        val_idx = np.arange(cutoff, len(meta))
        return fit_idx, val_idx
    val_dates = max(1, int(len(dates) * val_fraction))
    cutoff_date = dates[-val_dates]
    is_val = pd.to_datetime(meta["date"]).to_numpy() >= np.datetime64(cutoff_date)
    val_idx = np.where(is_val)[0]
    fit_idx = np.where(~is_val)[0]
    if len(fit_idx) < 100 or len(val_idx) < 100:
        cutoff = max(1, int(len(meta) * (1.0 - val_fraction)))
        fit_idx = np.arange(cutoff)
        val_idx = np.arange(cutoff, len(meta))
    return fit_idx, val_idx


def make_loader(X: np.ndarray, y: np.ndarray, S: np.ndarray | None, batch_size: int, shuffle: bool, num_workers: int) -> DataLoader:
    tensors = [torch.tensor(X, dtype=torch.float32)]
    if S is not None:
        tensors.append(torch.tensor(S, dtype=torch.float32))
    tensors.append(torch.tensor(y, dtype=torch.float32))
    return DataLoader(
        TensorDataset(*tensors),
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=max(0, int(num_workers)),
        pin_memory=torch.cuda.is_available(),
        persistent_workers=bool(num_workers and num_workers > 0),
    )


def unpack_batch(batch: tuple[torch.Tensor, ...], uses_static: bool, device: torch.device) -> tuple[torch.Tensor, torch.Tensor | None, torch.Tensor]:
    if uses_static:
        x, s, y = batch
        return x.to(device, non_blocking=True), s.to(device, non_blocking=True), y.to(device, non_blocking=True)
    x, y = batch
    return x.to(device, non_blocking=True), None, y.to(device, non_blocking=True)


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    uses_static: bool,
    args: argparse.Namespace,
    device: torch.device,
) -> dict[str, Any]:
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    loss_fn = nn.MSELoss()
    amp_enabled = bool(args.amp and device.type == "cuda")
    scaler = GradScaler("cuda", enabled=amp_enabled)
    best_state = None
    best_val = float("inf")
    stale = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_losses = []
        for batch in train_loader:
            x, s, y = unpack_batch(batch, uses_static, device)
            optimizer.zero_grad(set_to_none=True)
            with autocast("cuda", enabled=amp_enabled):
                pred = model(x, s)
                loss = loss_fn(pred, y)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            scaler.step(optimizer)
            scaler.update()
            train_losses.append(float(loss.detach().cpu()))

        model.eval()
        val_losses = []
        with torch.no_grad():
            for batch in val_loader:
                x, s, y = unpack_batch(batch, uses_static, device)
                with autocast("cuda", enabled=amp_enabled):
                    val_losses.append(float(loss_fn(model(x, s), y).detach().cpu()))
        train_loss = float(np.mean(train_losses)) if train_losses else float("nan")
        val_loss = float(np.mean(val_losses)) if val_losses else float("nan")
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        if val_loss + 1e-7 < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= args.patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"best_val_loss": best_val, "epochs_run": len(history), "history": history}


def predict(model: nn.Module, loader: DataLoader, uses_static: bool, device: torch.device) -> np.ndarray:
    model.eval()
    preds = []
    with torch.no_grad():
        for batch in loader:
            x, s, _ = unpack_batch(batch, uses_static, device)
            preds.append(model(x, s).detach().float().cpu().numpy())
    return np.concatenate(preds).astype(float)


def maybe_wrap_multi_gpu(model: nn.Module, args: argparse.Namespace, device: torch.device) -> tuple[nn.Module, bool, int]:
    gpu_count = torch.cuda.device_count() if device.type == "cuda" else 0
    use_multi = bool(device.type == "cuda" and gpu_count > 1 and not args.single_gpu)
    if use_multi:
        model = nn.DataParallel(model, device_ids=list(range(gpu_count)))
    return model, use_multi, int(gpu_count)


def run_window(store: SequenceStore, split: dict[str, Any], exp: dict[str, Any], args: argparse.Namespace, device: torch.device) -> dict[str, Any]:
    window_id = int(split["window_id"])
    train_ids = split["train_sample_ids"]
    test_ids = split["test_sample_ids"]
    event_flag, event_name = is_event_window(split["test_start"], split["test_end"])

    if len(train_ids) < args.min_train_samples:
        log(f"W{window_id}: SKIP train_samples={len(train_ids)} < {args.min_train_samples}")
        return {
            "window": window_id,
            "skipped": True,
            "skip_reason": f"train_samples_{len(train_ids)}_below_{args.min_train_samples}",
            "train_samples": int(len(train_ids)),
            "test_samples": int(len(test_ids)),
            "event_window": bool(event_flag),
            "event_name": event_name,
        }
    local_args = sequence_capacity_args(args, len(train_ids))
    if getattr(local_args, "warmup_window", False):
        log(
            f"W{window_id}: WARMUP train_samples={len(train_ids)}; "
            f"{local_args.capacity_tier} hidden={local_args.hidden_dim} "
            f"layers={local_args.layers} epochs={local_args.epochs}"
        )

    train = store.load_arrays(
        train_ids,
        max_samples=local_args.max_train_samples,
        seed=args.seed + window_id,
        include_mask=local_args.include_mask,
        include_static=bool(exp["uses_static"]),
    )
    test = store.load_arrays(
        test_ids,
        max_samples=local_args.max_test_samples,
        seed=args.seed + 10_000 + window_id,
        include_mask=local_args.include_mask,
        include_static=bool(exp["uses_static"]),
    )
    X_train, X_test = normalize_temporal(train["X"], test["X"])
    S_train = S_test = None
    if exp["uses_static"]:
        S_train, S_test = normalize_static(train["S"], test["S"])

    fit_idx, val_idx = split_fit_val(train["meta"], local_args.val_fraction)
    X_fit, y_fit = X_train[fit_idx], train["y"][fit_idx]
    X_val, y_val = X_train[val_idx], train["y"][val_idx]
    S_fit = S_train[fit_idx] if S_train is not None else None
    S_val = S_train[val_idx] if S_train is not None else None

    model = make_model(exp, input_dim=X_train.shape[2], seq_len=X_train.shape[1], static_dim=0 if S_train is None else S_train.shape[1], args=local_args)
    model, multi_gpu_used, gpu_count = maybe_wrap_multi_gpu(model, local_args, device)
    if multi_gpu_used:
        log(f"W{window_id}: using DataParallel across {gpu_count} CUDA devices")
    train_loader = make_loader(X_fit, y_fit, S_fit, local_args.batch_size, shuffle=True, num_workers=local_args.num_workers)
    val_loader = make_loader(X_val, y_val, S_val, local_args.batch_size, shuffle=False, num_workers=local_args.num_workers)
    full_train_loader = make_loader(X_train, train["y"], S_train, local_args.batch_size, shuffle=False, num_workers=local_args.num_workers)
    test_loader = make_loader(X_test, test["y"], S_test, local_args.batch_size, shuffle=False, num_workers=local_args.num_workers)

    fit_report = train_model(model, train_loader, val_loader, bool(exp["uses_static"]), local_args, device)
    train_pred = predict(model, full_train_loader, bool(exp["uses_static"]), device)
    test_pred = predict(model, test_loader, bool(exp["uses_static"]), device)

    train_frame = train["meta"][["sample_id", "date", "ticker"]].copy()
    train_frame["y"] = train["y"]
    train_frame["pred"] = train_pred
    test_frame = test["meta"][["sample_id", "date", "ticker"]].copy()
    test_frame["y"] = test["y"]
    test_frame["pred"] = test_pred

    train_ic = cross_sectional_ic(train_frame)
    test_ic = cross_sectional_ic(test_frame)
    raw_ratio, ratio, ratio_capped = train_test_ratio(train_ic["mean_ic"], test_ic["mean_ic"])

    out = {
        "window": window_id,
        "skipped": False,
        "train_samples": int(len(train_ids)),
        "fit_samples_used": int(len(fit_idx)),
        "val_samples_used": int(len(val_idx)),
        "test_samples": int(len(test_ids)),
        "train_samples_used": int(len(train["ids"])),
        "test_samples_used": int(len(test["ids"])),
        "test_start": split["test_start"],
        "test_end": split["test_end"],
        "event_window": bool(event_flag),
        "event_name": event_name,
        "excluded_from_aggregate": bool(event_flag),
        "warmup_window": bool(getattr(local_args, "warmup_window", False)),
        "capacity_tier": str(getattr(local_args, "capacity_tier", "production")),
        "hidden_dim_used": int(local_args.hidden_dim),
        "layers_used": int(local_args.layers),
        "epochs_configured": int(local_args.epochs),
        "multi_gpu_used": bool(multi_gpu_used),
        "gpu_count": int(gpu_count),
        "amp_used": bool(local_args.amp and device.type == "cuda"),
        "num_workers": int(local_args.num_workers),
        "train_ic": train_ic["mean_ic"],
        "test_ic": test_ic["mean_ic"],
        "test_ic_ir": test_ic["ic_ir"],
        "test_hit_rate": test_ic["hit_rate"],
        "ratio": ratio,
        "raw_ratio": raw_ratio,
        "ratio_capped": bool(ratio_capped),
        "best_val_loss": fit_report["best_val_loss"],
        "epochs_run": fit_report["epochs_run"],
    }
    log(
        f"W{window_id}: train_IC={out['train_ic']:+.4f} test_IC={out['test_ic']:+.4f} "
        f"ratio={(out['ratio'] if out['ratio'] is not None else float('nan')):.2f}x "
        f"raw={(out['raw_ratio'] if out['raw_ratio'] is not None else float('nan')):.2f}x "
        f"epochs={out['epochs_run']} event={event_name or 'none'}"
    )

    if args.save_predictions:
        return out | {"_train_predictions": train_frame, "_test_predictions": test_frame}
    return out


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eval_rows = [r for r in rows if not r.get("skipped") and not r.get("excluded_from_aggregate")]
    test_ics = np.asarray([r["test_ic"] for r in eval_rows if r.get("test_ic") is not None and np.isfinite(r["test_ic"])], dtype=float)
    train_ics = np.asarray([r["train_ic"] for r in eval_rows if r.get("train_ic") is not None and np.isfinite(r["train_ic"])], dtype=float)
    ratios = np.asarray([r["ratio"] for r in eval_rows if r.get("ratio") is not None and np.isfinite(r["ratio"])], dtype=float)
    raw_ratios = np.asarray([r["raw_ratio"] for r in eval_rows if r.get("raw_ratio") is not None and np.isfinite(r["raw_ratio"])], dtype=float)
    hit = np.asarray([r["test_hit_rate"] for r in eval_rows if r.get("test_hit_rate") is not None and np.isfinite(r["test_hit_rate"])], dtype=float)
    return {
        "effective_eval_windows": int(len(eval_rows)),
        "mean_train_ic": float(train_ics.mean()) if train_ics.size else None,
        "mean_test_ic": float(test_ics.mean()) if test_ics.size else None,
        "median_test_ic": float(np.median(test_ics)) if test_ics.size else None,
        "ic_ir": float(test_ics.mean() / (test_ics.std(ddof=1) + 1e-12)) if test_ics.size > 1 else None,
        "median_ratio": float(np.median(ratios)) if ratios.size else None,
        "mean_ratio": float(ratios.mean()) if ratios.size else None,
        "raw_mean_ratio": float(raw_ratios.mean()) if raw_ratios.size else None,
        "hit_rate": float(hit.mean()) if hit.size else None,
        "skipped_windows": [{"window": r["window"], "reason": r.get("skip_reason")} for r in rows if r.get("skipped")],
        "event_excluded_windows": [{"window": r["window"], "event": r.get("event_name")} for r in rows if r.get("excluded_from_aggregate")],
        "ratio_capped_windows": [int(r["window"]) for r in eval_rows if r.get("ratio_capped")],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exp_id", choices=sorted(EXPERIMENTS))
    parser.add_argument("--sequence-dir", default=None)
    parser.add_argument("--output-dir", default="/kaggle/working/northstar_sequence_results")
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--min-train-samples", type=int, default=5_000)
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-test-samples", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.20)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--include-mask", action="store_true")
    parser.add_argument("--amp", action="store_true", help="Use CUDA automatic mixed precision for sequence models.")
    parser.add_argument("--single-gpu", action="store_true", help="Disable DataParallel even when multiple CUDA devices are available.")
    parser.add_argument("--num-workers", type=int, default=2, help="DataLoader workers for sequence models.")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--save-predictions", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.backends.cudnn.benchmark = bool(torch.cuda.is_available())
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda" and not args.allow_cpu:
        raise SystemExit(
            "CUDA GPU is required for EXP-20..EXP-23 in the full Run 4 suite. "
            "Enable Kaggle P100/T4 or pass --allow-cpu for a deliberately slow/debug CPU run."
        )

    seq_dir = resolve_sequence_dir(args.sequence_dir)
    exp = EXPERIMENTS[args.exp_id]
    out_dir = Path(args.output_dir) / args.exp_id.lower()
    out_dir.mkdir(parents=True, exist_ok=True)

    log("\nNORTHSTAR V3 SEQUENCE EXPERIMENT")
    log(f"  Experiment : {args.exp_id} - {exp['name']}")
    log(f"  Description: {exp['description']}")
    log(f"  Sequence dir: {seq_dir}")
    log(f"  Output dir  : {out_dir}")
    log(f"  Device      : {device}")
    if device.type == "cuda":
        log(f"  CUDA devices: {torch.cuda.device_count()} - {[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}")
    log(f"  AMP         : {args.amp}")
    log(f"  Multi-GPU   : {'disabled' if args.single_gpu else 'auto'}")
    log(f"  Mask input  : {args.include_mask}")

    store = SequenceStore.open(seq_dir)
    splits = store.splits[: args.max_windows] if args.max_windows else store.splits
    log(f"  Windows     : {len(splits)}")
    log(f"  Static cols : {len(store.static_cols)}")

    rows: list[dict[str, Any]] = []
    prediction_frames = []
    for split in splits:
        try:
            result = run_window(store, split, exp, args, device)
            if "_test_predictions" in result:
                pred = result.pop("_test_predictions")
                pred["window"] = int(result["window"])
                prediction_frames.append(pred)
                result.pop("_train_predictions", None)
            rows.append(result)
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower() and torch.cuda.is_available():
                torch.cuda.empty_cache()
            log(f"W{split.get('window_id')}: ERROR {exc}")
            rows.append(
                {
                    "window": int(split.get("window_id", -1)),
                    "skipped": True,
                    "skip_reason": f"runtime_error:{exc}",
                    "train_samples": int(split.get("train_samples", 0)),
                    "test_samples": int(split.get("test_samples", 0)),
                }
            )

    public_rows = [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]
    metrics = aggregate(public_rows)
    summary = {
        "experiment": args.exp_id,
        "experiment_name": exp["name"],
        "description": exp["description"],
        "sequence_dir": str(seq_dir),
        "device": str(device),
        "args": vars(args),
        "aggregate": metrics,
        "windows": public_rows,
    }
    pd.DataFrame(public_rows).to_csv(out_dir / f"{args.exp_id.lower()}_windows.csv", index=False)
    (out_dir / f"{args.exp_id.lower()}_summary.json").write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    if prediction_frames:
        pd.concat(prediction_frames, ignore_index=True).to_csv(out_dir / f"{args.exp_id.lower()}_test_predictions.csv", index=False)

    log("\nAGGREGATE")
    log(json.dumps(json_safe(metrics), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
