#!/usr/bin/env python3
"""Train Transformer and TCN sequence models and report IC/Sharpe comparisons."""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.models.stock_tcn import DEFAULT_TCN_CONFIG, StockTCN
from src.models.stock_transformer import DEFAULT_TRANSFORMER_CONFIG, StockTransformer


@dataclass
class SplitConfig:
    train_end: str = "2019-12-31"
    valid_start: str = "2020-01-01"
    valid_end: str = "2020-12-31"
    test_start: str = "2021-01-01"
    test_end: str = "2024-12-31"


def _ensure_torch():
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:
        raise RuntimeError("train_sequence_models_requires_torch") from exc
    return torch, nn, DataLoader, TensorDataset


def _to_date_series(meta_df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(meta_df["date"], errors="coerce").dt.normalize()


def _mask_for_split(meta_df: pd.DataFrame, split_cfg: SplitConfig) -> dict[str, np.ndarray]:
    dt = _to_date_series(meta_df)
    train_end = pd.Timestamp(split_cfg.train_end)
    valid_start = pd.Timestamp(split_cfg.valid_start)
    valid_end = pd.Timestamp(split_cfg.valid_end)
    test_start = pd.Timestamp(split_cfg.test_start)
    test_end = pd.Timestamp(split_cfg.test_end)

    masks = {
        "train": (dt <= train_end).to_numpy(dtype=bool),
        "valid": ((dt >= valid_start) & (dt <= valid_end)).to_numpy(dtype=bool),
        "test": ((dt >= test_start) & (dt <= test_end)).to_numpy(dtype=bool),
    }
    return masks


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 8 or len(b) < 8:
        return 0.0
    s1 = pd.Series(np.asarray(a, dtype=float))
    s2 = pd.Series(np.asarray(b, dtype=float))
    val = s1.corr(s2, method="spearman")
    return float(val) if np.isfinite(val) else 0.0


def _monthly_ic(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["month"] = pd.to_datetime(work["date"], errors="coerce").dt.to_period("M").astype(str)
    out = (
        work.groupby("month", as_index=False)
        .apply(lambda g: pd.Series({"ic": _spearman(g["pred"].to_numpy(), g["target"].to_numpy())}))
        .reset_index(drop=True)
    )
    return out


def _equal_weight_top30_sharpe(df: pd.DataFrame) -> float:
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    daily = []
    for d, g in work.groupby("date", sort=True):
        gg = g.sort_values("pred", ascending=False)
        top = gg.head(30)
        if top.empty:
            continue
        daily.append({"date": d, "ret_5d": float(pd.to_numeric(top["target"], errors="coerce").mean())})
    if not daily:
        return 0.0
    dr = pd.DataFrame(daily)
    mu = float(dr["ret_5d"].mean())
    sd = float(dr["ret_5d"].std())
    if not np.isfinite(sd) or sd < 1e-12:
        return 0.0
    periods_per_year = 252.0 / 5.0
    return float((mu / sd) * math.sqrt(periods_per_year))


def _best_regime(df: pd.DataFrame) -> str:
    if "regime" not in df.columns:
        return "unknown"
    work = df.copy()
    work["regime"] = work["regime"].astype(str)
    rows = []
    for reg, g in work.groupby("regime", sort=False):
        if not reg:
            continue
        ic = _spearman(g["pred"].to_numpy(), g["target"].to_numpy())
        rows.append((str(reg), float(ic), int(len(g))))
    if not rows:
        return "unknown"
    rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return rows[0][0]


def _prepare_loader(torch_mod, TensorDataset, DataLoader, x, y, batch_size: int, shuffle: bool):
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, drop_last=False)


def _train_torch_model(
    model,
    *,
    train_loader,
    valid_loader,
    device,
    epochs: int,
    patience: int,
    lr: float,
):
    torch_mod, nn, _, _ = _ensure_torch()
    model = model.to(device)
    optimizer = torch_mod.optim.AdamW(model.parameters(), lr=float(lr), weight_decay=1e-4)
    loss_fn = nn.MSELoss()

    best_state = None
    best_loss = float("inf")
    bad_epochs = 0

    for _ in range(int(max(1, epochs))):
        model.train()
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            optimizer.step()

        model.eval()
        losses = []
        with torch_mod.no_grad():
            for xb, yb in valid_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                pred = model(xb)
                losses.append(float(loss_fn(pred, yb).detach().cpu().item()))
        val_loss = float(np.mean(losses)) if losses else float("inf")

        if val_loss + 1e-8 < best_loss:
            best_loss = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= int(max(1, patience)):
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model = model.to(device)
    model.eval()
    return model


def _predict_torch_model(model, x, device):
    torch_mod, _, _, _ = _ensure_torch()
    with torch_mod.no_grad():
        xb = x.to(device)
        pred = model(xb).detach().cpu().numpy().reshape(-1)
    return pred


def _evaluate_model(test_meta: pd.DataFrame, preds: np.ndarray, targets: np.ndarray) -> dict[str, Any]:
    eval_df = test_meta.copy()
    eval_df["pred"] = np.asarray(preds, dtype=float)
    eval_df["target"] = np.asarray(targets, dtype=float)

    monthly = _monthly_ic(eval_df)
    global_ic = _spearman(eval_df["pred"].to_numpy(), eval_df["target"].to_numpy())
    sharpe = _equal_weight_top30_sharpe(eval_df)
    best_regime = _best_regime(eval_df)

    return {
        "global_ic": float(global_ic),
        "sharpe": float(sharpe),
        "best_regime": str(best_regime),
        "monthly_ic": monthly.to_dict(orient="records"),
    }


def _load_dataset(path: Path):
    torch_mod, _, _, _ = _ensure_torch()
    payload = torch_mod.load(path, map_location="cpu", weights_only=False)
    X = payload["X"].float()
    y = payload["y"].float().view(-1, 1)
    meta = pd.DataFrame(payload.get("metadata", []))
    feature_names = list(payload.get("feature_names", []))
    seq_len = int(payload.get("seq_len", X.shape[1] if X.ndim == 3 else 252))

    if meta.empty:
        raise ValueError("sequence_dataset_missing_metadata")
    if "date" not in meta.columns or "ticker" not in meta.columns:
        raise ValueError("sequence_dataset_metadata_requires_date_ticker")

    return X, y, meta, feature_names, seq_len


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train sequence models (Transformer + TCN)")
    p.add_argument("--dataset", type=str, default="data/processed/sequence_dataset.pt")
    p.add_argument("--output", type=str, default="data/results/research/reports/sequence_models_results.json")
    p.add_argument("--models-root", type=str, default="models")
    p.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "mps", "cuda"])
    p.add_argument("--epochs", type=int, default=50)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    torch_mod, _, DataLoader, TensorDataset = _ensure_torch()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise FileNotFoundError(f"sequence_dataset_missing:{dataset_path}")

    X, y, meta, feature_names, seq_len = _load_dataset(dataset_path)

    split_cfg = SplitConfig()
    masks = _mask_for_split(meta, split_cfg)

    if not masks["train"].any() or not masks["valid"].any() or not masks["test"].any():
        raise ValueError("sequence_split_empty_partition")

    X_train = X[masks["train"]]
    y_train = y[masks["train"]]
    X_valid = X[masks["valid"]]
    y_valid = y[masks["valid"]]
    X_test = X[masks["test"]]
    y_test = y[masks["test"]]
    meta_test = meta.loc[masks["test"]].reset_index(drop=True)

    if args.device == "cpu":
        device = torch_mod.device("cpu")
    elif args.device == "mps":
        device = torch_mod.device("mps")
    elif args.device == "cuda":
        device = torch_mod.device("cuda")
    else:
        if torch_mod.backends.mps.is_available():
            device = torch_mod.device("mps")
        elif torch_mod.cuda.is_available():
            device = torch_mod.device("cuda")
        else:
            device = torch_mod.device("cpu")

    tr_cfg = DEFAULT_TRANSFORMER_CONFIG
    tr_cfg = tr_cfg.__class__(
        d_model=tr_cfg.d_model,
        n_heads=tr_cfg.n_heads,
        n_layers=tr_cfg.n_layers,
        d_ff=tr_cfg.d_ff,
        dropout=tr_cfg.dropout,
        seq_len=int(seq_len),
        n_features=int(X.shape[-1]),
        learning_rate=tr_cfg.learning_rate,
        batch_size=tr_cfg.batch_size,
        epochs=int(args.epochs),
        early_stopping_patience=tr_cfg.early_stopping_patience,
    )

    tcn_cfg = DEFAULT_TCN_CONFIG
    tcn_cfg = tcn_cfg.__class__(
        n_channels=tcn_cfg.n_channels,
        kernel_size=tcn_cfg.kernel_size,
        dilations=tcn_cfg.dilations,
        dropout=tcn_cfg.dropout,
        n_features=int(X.shape[-1]),
        learning_rate=tcn_cfg.learning_rate,
        batch_size=tcn_cfg.batch_size,
        epochs=int(args.epochs),
        early_stopping_patience=tcn_cfg.early_stopping_patience,
    )

    train_loader_tr = _prepare_loader(torch_mod, TensorDataset, DataLoader, X_train, y_train, tr_cfg.batch_size, True)
    valid_loader_tr = _prepare_loader(torch_mod, TensorDataset, DataLoader, X_valid, y_valid, tr_cfg.batch_size, False)

    model_tr = StockTransformer(tr_cfg)
    model_tr = _train_torch_model(
        model_tr,
        train_loader=train_loader_tr,
        valid_loader=valid_loader_tr,
        device=device,
        epochs=tr_cfg.epochs,
        patience=tr_cfg.early_stopping_patience,
        lr=tr_cfg.learning_rate,
    )
    pred_tr = _predict_torch_model(model_tr, X_test, device=device)
    metrics_tr = _evaluate_model(meta_test, pred_tr, y_test.numpy().reshape(-1))

    train_loader_tcn = _prepare_loader(
        torch_mod,
        TensorDataset,
        DataLoader,
        X_train.transpose(1, 2),
        y_train,
        tcn_cfg.batch_size,
        True,
    )
    valid_loader_tcn = _prepare_loader(
        torch_mod,
        TensorDataset,
        DataLoader,
        X_valid.transpose(1, 2),
        y_valid,
        tcn_cfg.batch_size,
        False,
    )

    model_tcn = StockTCN(tcn_cfg)
    model_tcn = _train_torch_model(
        model_tcn,
        train_loader=train_loader_tcn,
        valid_loader=valid_loader_tcn,
        device=device,
        epochs=tcn_cfg.epochs,
        patience=tcn_cfg.early_stopping_patience,
        lr=tcn_cfg.learning_rate,
    )
    pred_tcn = _predict_torch_model(model_tcn, X_test.transpose(1, 2), device=device)
    metrics_tcn = _evaluate_model(meta_test, pred_tcn, y_test.numpy().reshape(-1))

    models_root = Path(args.models_root)
    tr_dir = models_root / "transformer"
    tcn_dir = models_root / "tcn"
    tr_dir.mkdir(parents=True, exist_ok=True)
    tcn_dir.mkdir(parents=True, exist_ok=True)

    torch_mod.save(
        {
            "state_dict": model_tr.cpu().state_dict(),
            "config": tr_cfg.__dict__,
            "feature_names": feature_names,
            "seq_len": int(seq_len),
        },
        tr_dir / "transformer_latest.pt",
    )
    torch_mod.save(
        {
            "state_dict": model_tcn.cpu().state_dict(),
            "config": {
                **tcn_cfg.__dict__,
                "dilations": list(tcn_cfg.dilations),
            },
            "feature_names": feature_names,
            "seq_len": int(seq_len),
        },
        tcn_dir / "tcn_latest.pt",
    )

    results = {
        "dataset": {
            "path": str(dataset_path),
            "n_samples": int(X.shape[0]),
            "seq_len": int(seq_len),
            "n_features": int(X.shape[-1]),
            "feature_names": feature_names,
            "split": split_cfg.__dict__,
        },
        "baseline": {
            "xgboost": {
                "global_ic": 0.0323,
                "sharpe": -0.169,
                "best_regime": "high_vol|downtrend|expansion",
            }
        },
        "transformer": metrics_tr,
        "tcn": metrics_tcn,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("Model        | Global IC | Sharpe | Best Regime")
    print("XGBoost      | 0.0323    | -0.169 | high_vol|downtrend|expansion")
    print(
        f"Transformer  | {metrics_tr['global_ic']:.4f}    | {metrics_tr['sharpe']:.3f} | {metrics_tr['best_regime']}"
    )
    print(
        f"TCN          | {metrics_tcn['global_ic']:.4f}    | {metrics_tcn['sharpe']:.3f} | {metrics_tcn['best_regime']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
