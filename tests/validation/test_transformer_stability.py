from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from src.research.transformer_model import TimeSeriesTransformerNet
from src.research.transformer_stability import compute_seed_transformer_stability, discover_transformer_artifacts


def _make_bundle(path: Path, *, offset: float) -> None:
    torch.manual_seed(7)
    net = TimeSeriesTransformerNet(
        observed_dim=2,
        known_dim=0,
        static_dim=1,
        d_model=4,
        nhead=2,
        num_layers=1,
        dim_feedforward=8,
        dropout=0.0,
        max_len=16,
        n_tickers=2,
        n_sectors=2,
        embed_dim=4,
    )
    net.eval()

    obs = np.asarray(
        [
            [[0.1 + offset, 0.2], [0.2 + offset, 0.1], [0.3 + offset, 0.0]],
            [[0.2 + offset, 0.1], [0.3 + offset, 0.0], [0.4 + offset, -0.1]],
            [[0.3 + offset, 0.0], [0.4 + offset, -0.1], [0.5 + offset, -0.2]],
            [[0.4 + offset, -0.1], [0.5 + offset, -0.2], [0.6 + offset, -0.3]],
            [[0.5 + offset, -0.2], [0.6 + offset, -0.3], [0.7 + offset, -0.4]],
            [[0.6 + offset, -0.3], [0.7 + offset, -0.4], [0.8 + offset, -0.5]],
        ],
        dtype=np.float32,
    )
    static = np.asarray([[0.1], [0.0], [-0.1], [-0.2], [-0.3], [-0.4]], dtype=np.float32)
    ticker_ids = np.zeros(len(obs), dtype=np.int64)
    sector_ids = np.zeros(len(obs), dtype=np.int64)

    with torch.no_grad():
        pred = (
            net(
                observed=torch.tensor(obs, dtype=torch.float32),
                static=torch.tensor(static, dtype=torch.float32),
                ticker_id=torch.tensor(ticker_ids, dtype=torch.long),
                sector_id=torch.tensor(sector_ids, dtype=torch.long),
            )["return_pred"]
            .detach()
            .cpu()
            .numpy()
            .reshape(-1)
        )
    y = (0.9 * pred + np.linspace(-0.01, 0.01, len(pred))).astype(np.float32)

    payload = {
        "artifact_type": "transformer_window_bundle",
        "model_name": "transformer",
        "mode": "torch",
        "window_index": 1,
        "split": {
            "train_start": "2025-01-01",
            "train_end": "2025-03-01",
            "test_start": f"2025-04-{1 + int(offset * 10):02d}",
            "test_end": f"2025-05-{1 + int(offset * 10):02d}",
        },
        "lookback": 3,
        "params": {"d_model": 4},
        "architecture": {
            "observed_dim": 2,
            "known_dim": 0,
            "static_dim": 1,
            "d_model": 4,
            "nhead": 2,
            "num_layers": 1,
            "dim_feedforward": 8,
            "dropout": 0.0,
            "max_len": 16,
            "n_tickers": 2,
            "n_sectors": 2,
            "embed_dim": 4,
        },
        "feature_meta": {
            "observed_feature_names": ["mom_20d", "rsi_14"],
            "known_feature_names": [],
            "static_feature_names": ["sector_score"],
        },
        "context": {
            "obs": obs,
            "known": np.empty((len(obs), 3, 0), dtype=np.float32),
            "static": static,
            "ticker_ids": ticker_ids,
            "sector_ids": sector_ids,
            "indices": np.arange(len(obs), dtype=np.int64),
            "y": y,
        },
        "baseline_predictions": pred.astype(np.float32),
        "model_state": {k: v.detach().cpu() for k, v in net.state_dict().items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)


def test_discover_transformer_artifacts_reads_seed_references(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp"
    bundle_dir = exp_dir / "window_artifacts" / "transformer" / "seed_42"
    bundle_path = bundle_dir / "window_01_20250401_20250501.pt"
    _make_bundle(bundle_path, offset=0.0)

    seed_dir = exp_dir / "seed_results"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "transformer_seed_42.json").write_text(
        json.dumps(
            {
                "seed_summary": {"model": "transformer", "seed": 42, "train_test_ratio": 4.31},
                "window_artifact_dir": str(bundle_dir),
                "full_result": {"windows": [{"artifact_path": str(bundle_path)}]},
            }
        ),
        encoding="utf-8",
    )

    discovery = discover_transformer_artifacts(exp_dir)

    assert discovery["seed_files"]
    assert discovery["window_bundle_files"] == [str(bundle_path.resolve())]


def test_compute_seed_transformer_stability_returns_ok_report(tmp_path: Path) -> None:
    bundle_a = tmp_path / "window_01_20250401_20250501.pt"
    bundle_b = tmp_path / "window_02_20250501_20250601.pt"
    _make_bundle(bundle_a, offset=0.0)
    _make_bundle(bundle_b, offset=0.1)

    report = compute_seed_transformer_stability(
        [bundle_a, bundle_b],
        method="permutation",
        top_k=3,
        permutation_max_features=8,
        random_state=42,
    )

    assert report["status"] == "ok"
    assert report["windows_with_feature_importance"] == 2
    assert report["importance_methods_used"] == ["permutation", "permutation"]
    assert report["mean_pairwise_rank_correlation"] >= 0.5
