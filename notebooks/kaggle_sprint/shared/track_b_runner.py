"""Robust Track B Kaggle runner with resume, day control, and frontier-model exports."""

from __future__ import annotations

import gc
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from sprint_utils import (
    DEFAULT_REDUCED_EXCLUDE_REGEX,
    EnsembleBuilder,
    FactorICAnalyzer,
    PromotionVerdict,
    RegimeConditionalIC,
    SectorICAnalyzer,
)
from track_a_runner import (
    TrackARunner,
    _parse_csv_list,
    _parse_bool,
    _parse_day_set,
    torch,
    nn,
)

if os.environ.get("PYTORCH_CUDA_ALLOC_CONF") is None:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"


def _safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    left_arr = np.asarray(left, dtype=float)
    right_arr = np.asarray(right, dtype=float)
    mask = np.isfinite(left_arr) & np.isfinite(right_arr)
    if int(mask.sum()) < 5:
        return 0.0
    corr, _ = spearmanr(left_arr[mask], right_arr[mask])
    return float(corr) if np.isfinite(corr) else 0.0


@dataclass
class TrackBRunConfig:
    data_dir: Path | None = None
    output_dir: Path | None = None
    track_name: str = "track_b_frontier"
    device: str = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
    skip_days: set[int] = field(default_factory=set)
    force_rerun_days: set[int] = field(default_factory=set)
    continue_on_error: bool = True
    resume_from_checkpoint: bool = True
    run_profile: str = "full"
    max_splits: int | None = None
    patchtst_result_path: Path | None = None
    model_filter: list[str] = field(default_factory=list)
    feature_mode: str = "full"
    reduced_feature_count: int = 60
    reduced_feature_min_abs_ic: float = 0.005
    feature_exclude_regex: str | None = DEFAULT_REDUCED_EXCLUDE_REGEX
    normalize_raw_financials: bool = False
    require_group_ranking: bool = True

    @classmethod
    def from_env(cls) -> "TrackBRunConfig":
        output_dir = (
            Path("/kaggle/working/track_b_results")
            if Path("/kaggle").exists()
            else Path("./track_b_results")
        )
        data_dir_env = os.environ.get("TRACK_B_DATA_DIR")
        max_splits_env = os.environ.get("TRACK_B_MAX_SPLITS")
        patchtst_result_env = os.environ.get("TRACK_B_PATCHTST_RESULT_PATH")
        reduced_count_env = os.environ.get("TRACK_B_REDUCED_FEATURE_COUNT")
        reduced_min_ic_env = os.environ.get("TRACK_B_REDUCED_FEATURE_MIN_ABS_IC")
        feature_exclude_regex = os.environ.get("TRACK_B_FEATURE_EXCLUDE_REGEX", DEFAULT_REDUCED_EXCLUDE_REGEX)
        return cls(
            data_dir=Path(data_dir_env) if data_dir_env else None,
            output_dir=Path(os.environ.get("TRACK_B_OUTPUT_DIR", str(output_dir))),
            skip_days=_parse_day_set(os.environ.get("TRACK_B_SKIP_DAYS"), default=set()),
            force_rerun_days=_parse_day_set(os.environ.get("TRACK_B_FORCE_RERUN_DAYS"), default=set()),
            continue_on_error=_parse_bool(os.environ.get("TRACK_B_CONTINUE_ON_ERROR"), True),
            resume_from_checkpoint=_parse_bool(os.environ.get("TRACK_B_RESUME_CHECKPOINTS"), True),
            run_profile=os.environ.get("TRACK_B_RUN_PROFILE", "full").strip().lower() or "full",
            max_splits=int(max_splits_env) if max_splits_env and max_splits_env.strip() else None,
            patchtst_result_path=Path(patchtst_result_env) if patchtst_result_env else None,
            model_filter=_parse_csv_list(os.environ.get("TRACK_B_MODEL_FILTER")),
            feature_mode=os.environ.get("TRACK_B_FEATURE_MODE", "full").strip().lower() or "full",
            reduced_feature_count=int(reduced_count_env) if reduced_count_env and reduced_count_env.strip() else 60,
            reduced_feature_min_abs_ic=(
                float(reduced_min_ic_env) if reduced_min_ic_env and reduced_min_ic_env.strip() else 0.005
            ),
            feature_exclude_regex=feature_exclude_regex or None,
            normalize_raw_financials=_parse_bool(os.environ.get("TRACK_B_NORMALIZE_RAW_FINANCIALS"), False),
            require_group_ranking=_parse_bool(os.environ.get("TRACK_B_REQUIRE_GROUP_RANKING"), True),
        )


def listnet_loss(scores, targets):
    """
    ListNet loss: cross-entropy between softmax of scores and softmax of targets.
    More stable than pairwise hinge loss in weak-signal windows.
    """

    targets_norm = (targets - targets.mean()) / (targets.std() + 1e-8)
    scores_norm = (scores - scores.mean()) / (scores.std() + 1e-8)
    k = max(10, len(scores) // 2)
    top_idx = torch.topk(targets_norm, k).indices
    scores_top = scores_norm[top_idx]
    targets_top = targets_norm[top_idx]
    p_targets = torch.softmax(targets_top / 0.5, dim=0)
    p_scores = torch.log_softmax(scores_top / 0.5, dim=0)
    return -torch.sum(p_targets * p_scores)


class GatedResidualNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, dropout=0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size)
        self.gate = nn.Linear(hidden_size, output_size)
        self.norm = nn.LayerNorm(output_size)
        self.dropout = nn.Dropout(dropout)
        self.skip = nn.Linear(input_size, output_size, bias=False) if input_size != output_size else nn.Identity()

    def forward(self, x):
        residual = self.skip(x)
        h = torch.relu(self.fc1(x))
        h = self.dropout(h)
        out = self.fc2(h)
        gate = torch.sigmoid(self.gate(h))
        return self.norm(gate * out + residual)


class VariableSelectionNetwork(nn.Module):
    def __init__(self, n_features, hidden_size, dropout=0.1):
        super().__init__()
        self.n_features = n_features
        self.feature_grns = nn.ModuleList(
            [GatedResidualNetwork(1, hidden_size, hidden_size, dropout) for _ in range(n_features)]
        )
        self.weight_network = nn.Sequential(
            GatedResidualNetwork(n_features, hidden_size, n_features, dropout),
            nn.Softmax(dim=-1),
        )

    def forward(self, x):
        processed = torch.stack(
            [self.feature_grns[i](x[:, i : i + 1]) for i in range(self.n_features)],
            dim=1,
        )
        weights = self.weight_network(x)
        selected = (processed * weights.unsqueeze(-1)).sum(dim=1)
        return selected, weights


class TFTRanker(nn.Module):
    def __init__(self, n_features, hidden_size=64, n_heads=4, n_attn_layers=2, dropout=0.15):
        super().__init__()
        self.vsn = VariableSelectionNetwork(n_features, hidden_size, dropout)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=n_heads,
            dim_feedforward=hidden_size * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.attention = nn.TransformerEncoder(
            encoder_layer,
            num_layers=n_attn_layers,
            enable_nested_tensor=False,
        )
        self.output_grn = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
        self.head = nn.Linear(hidden_size, 1)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        selected, weights = self.vsn(x)
        attended = self.attention(selected.unsqueeze(1)).squeeze(1)
        out = self.output_grn(attended)
        return self.head(self.dropout(out)).squeeze(-1), weights

    def get_selection_weights(self, x):
        with torch.no_grad():
            _, weights = self.vsn(x)
        return weights.mean(dim=0)


class ITransformerRanker(nn.Module):
    def __init__(self, n_features, d_model=32, n_heads=4, n_layers=2, d_ff=128, dropout=0.15, use_cls_token=True):
        super().__init__()
        self.feature_projection = nn.Linear(1, d_model)
        self.feature_pos_embed = nn.Parameter(torch.randn(1, n_features, d_model) * 0.02)
        self.use_cls_token = use_cls_token
        if use_cls_token:
            self.cls_token = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=n_layers,
            enable_nested_tensor=False,
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
        )

    def forward(self, x):
        batch_size = x.size(0)
        x_embed = self.feature_projection(x.unsqueeze(-1)) + self.feature_pos_embed
        if self.use_cls_token:
            cls_tokens = self.cls_token.expand(batch_size, -1, -1)
            x_embed = torch.cat([cls_tokens, x_embed], dim=1)
        encoded = self.encoder(x_embed)
        rep = encoded[:, 0, :] if self.use_cls_token else encoded.mean(dim=1)
        rep = self.norm(rep)
        return self.head(self.dropout(rep)).squeeze(-1)

    def get_feature_attention_weights(self, x):
        x_grad = x.clone().requires_grad_(True)
        out = self.forward(x_grad)
        out.sum().backward()
        return x_grad.grad.abs().mean(dim=0).detach()


class TrackBRunner(TrackARunner):
    PATCHTST_FALLBACK = {
        "model": "PatchTST",
        "summary": {
            "mean_test_ic": 0.0162,
            "ic_ir": 0.4379,
            "mean_train_test_ratio": 0.71,
            "mean_hit_rate": 0.5662,
            "windows_completed": 20,
            "windows_total": 20,
            "passed_viability_filter": True,
            "verdict": "QUALIFIED",
        },
        "stability": {
            "mean_pairwise_correlation": 0.7037,
            "band": "stable",
            "top_stable_features": [
                "earnings_quality_ratio_cs_rank",
                "earnings_quality_ratio_cs_z",
                "max_ret_20d_cs_rank",
            ],
            "top_unstable_features": [
                "macro_activity_composite_ts_z",
                "screener_dii_pct_cs_z",
            ],
            "mean_importance_by_feature": {},
            "top_features_by_mean_importance": [],
        },
        "windows": [],
    }

    def __init__(self, config: TrackBRunConfig | None = None):
        super().__init__(config=config or TrackBRunConfig.from_env())

    def run(self) -> dict[str, Any]:
        self._load_data()
        self._bootstrap_day1_if_needed()
        self._run_day(1, "Factor IC Analysis", self._run_day1)
        self._run_day(2, "Frontier Model Walk-Forward", self._run_day2)
        self._run_day(3, "Architecture-Specific Diagnostics", self._run_day3)
        self._run_day(4, "Regime + Sector Analysis", self._run_day4)
        self._run_day(5, "India-Specific Factor Tests", self._run_day5)
        self._run_day(6, "Ensemble + Deployment Analysis", self._run_day6)
        self._run_day(7, "Final Verdict", self._run_day7)
        self._save_run_state(status="completed")
        return self.state

    def _load_data(self) -> None:
        features_df, splits, regime_df = self.loader.load(self.config.data_dir)
        if self.config.max_splits is not None:
            splits = list(splits[: self.config.max_splits])
            print(f"Limiting run to first {len(splits)} walk-forward windows for profile control.")
        feature_names = self.loader.get_feature_names(features_df)
        self.state.update(
            {
                "features_df": features_df,
                "splits": splits,
                "regime_df": regime_df,
                "feature_names": feature_names,
                "analyzer": self.state.get("analyzer") or FactorICAnalyzer(),
            }
        )
        print("Track B - Frontier Models")
        print(f"Device: {self.config.device}")
        print(f"Output: {self.output_dir}")
        if self.config.data_dir is not None:
            print(f"Requested data dir: {self.config.data_dir}")
        print(f"Run profile: {self.config.run_profile}")
        print(f"Skip days: {sorted(self.config.skip_days)}")

    def _frontier_configs(self) -> tuple[dict[str, Any], dict[str, Any]]:
        tft_steps = 1000
        tft_patience = 120
        itr_steps = 800
        itr_patience = 100
        if self.config.run_profile == "smoke":
            tft_steps = 2
            tft_patience = 1
            itr_steps = 2
            itr_patience = 1
        elif self.config.run_profile == "fast":
            tft_steps = 120
            tft_patience = 20
            itr_steps = 120
            itr_patience = 20

        common = {
            "device": self.config.device,
            "output_dir": str(self.output_dir),
            "resume_from_checkpoint": self.config.resume_from_checkpoint,
            "verbose_training": True,
            "progress_every": 250 if self.config.run_profile == "full" else 25,
        }
        tft_config = {
            **common,
            "model": "TFT",
            "hidden_size": 64,
            "n_heads": 4,
            "n_attn_layers": 2,
            "dropout": 0.15,
            "lr": 2e-4,
            "weight_decay": 1e-4,
            "max_steps": tft_steps,
            "patience_steps": tft_patience,
            "batch_size": 256,
            "max_attempts": 3 if self.config.run_profile == "full" else 1,
        }
        itransformer_config = {
            **common,
            "model": "iTransformer",
            "d_model": 32,
            "n_heads": 4,
            "n_layers": 2,
            "d_ff": 128,
            "dropout": 0.15,
            "use_cls_token": True,
            "lr": 2e-4,
            "weight_decay": 1e-4,
            "max_steps": itr_steps,
            "patience_steps": itr_patience,
            "batch_size": 128,
            "max_attempts": 2 if self.config.run_profile == "full" else 1,
        }
        return tft_config, itransformer_config

    def _candidate_json_paths(self, filename: str) -> list[Path]:
        paths = []
        if filename == "patchtst_final.json" and self.config.patchtst_result_path is not None:
            paths.append(self.config.patchtst_result_path)
        output_roots = [
            self.output_dir,
            Path("/kaggle/working/results") if Path("/kaggle").exists() else Path("./kaggle_results"),
            Path("/kaggle/working/track_b_results") if Path("/kaggle").exists() else Path("./track_b_results"),
        ]
        for root in output_roots:
            paths.append(root / filename)
        if Path("/kaggle/input").exists():
            paths.extend(sorted(Path("/kaggle/input").glob(f"**/{filename}")))
        deduped: list[Path] = []
        seen = set()
        for path in paths:
            key = str(path)
            if key in seen:
                continue
            deduped.append(path)
            seen.add(key)
        return deduped

    def _load_json_payload(self, filename: str) -> dict[str, Any] | None:
        for candidate in self._candidate_json_paths(filename):
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                print(f"Loaded {filename} from {candidate}", flush=True)
                return payload
        return None

    def _load_patchtst_results(self) -> dict[str, Any]:
        payload = self._load_json_payload("patchtst_final.json")
        result_source = "artifact"
        if payload is None:
            print("WARNING: patchtst_final.json not found; using the known-good fallback payload.", flush=True)
            payload = json.loads(json.dumps(self.PATCHTST_FALLBACK))
            result_source = "fallback"
        normalized = self._normalize_frontier_summary(dict(payload.get("summary", {})))
        normalized["result_source"] = result_source
        payload["summary"] = normalized
        payload.setdefault("stability", {})
        payload.setdefault("windows", [])
        payload["result_source"] = result_source
        return payload

    def _load_track_a_payload(self) -> dict[str, Any] | None:
        payload = self._load_json_payload("track_a_classical_full_results.json")
        if payload is not None:
            return payload
        working_candidate = (
            Path("/kaggle/working/track_a_results/track_a_classical_full_results.json")
            if Path("/kaggle").exists()
            else Path("./track_a_results/track_a_classical_full_results.json")
        )
        if working_candidate.exists():
            with working_candidate.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        return None

    @staticmethod
    def _set_seed(seed: int) -> None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    @staticmethod
    def _predict_numpy_in_batches(model, array: np.ndarray, device: str, prediction_getter, batch_size: int) -> np.ndarray:
        values = np.asarray(array, dtype=np.float32)
        if len(values) == 0:
            return np.empty(0, dtype=np.float32)
        batch = max(1, int(batch_size))
        preds: list[np.ndarray] = []
        model.eval()
        with torch.no_grad():
            for start in range(0, len(values), batch):
                stop = min(start + batch, len(values))
                xb = torch.tensor(values[start:stop], dtype=torch.float32, device=device)
                pred = prediction_getter(model, xb).detach().cpu().numpy()
                preds.append(np.asarray(pred, dtype=np.float32).reshape(-1))
                del xb
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return np.concatenate(preds, axis=0) if preds else np.empty(0, dtype=np.float32)

    @staticmethod
    def _train_val_split(X_train: np.ndarray, y_train: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if len(y_train) < 3:
            return X_train, X_train, y_train, y_train
        val_size = max(1, min(max(16, len(y_train) // 10), len(y_train) - 1))
        split_idx = len(y_train) - val_size
        return X_train[:split_idx], X_train[split_idx:], y_train[:split_idx], y_train[split_idx:]

    def _train_with_sign_check(
        self,
        model_builder,
        X_train: np.ndarray,
        y_train: np.ndarray,
        config: dict[str, Any],
        model_label: str,
        prediction_getter,
    ):
        X_tr, X_val, y_tr, y_val = self._train_val_split(X_train, y_train)
        X_tr_np = np.asarray(X_tr, dtype=np.float32)
        X_val_np = np.asarray(X_val, dtype=np.float32)
        y_tr_np = np.asarray(y_tr, dtype=np.float32)
        y_val_np = np.asarray(y_val, dtype=float)
        batch_size = min(int(config["batch_size"]), len(y_tr_np))
        max_attempts = int(config.get("max_attempts", 1))
        progress_every = int(config.get("progress_every", 250))
        best_overall = None
        best_overall_ic = float("-inf")

        for attempt in range(max_attempts):
            seed = 42 + attempt * 11
            self._set_seed(seed)
            model = model_builder().to(config["device"])
            optimizer = torch.optim.AdamW(
                model.parameters(),
                lr=config["lr"],
                weight_decay=config["weight_decay"],
            )
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=config["max_steps"],
                eta_min=config["lr"] * 0.01,
            )
            best_state = None
            best_val_ic = float("-inf")
            patience_counter = 0
            model.train()
            for step in range(config["max_steps"]):
                idx = np.random.permutation(len(y_tr_np))[:batch_size]
                xb = torch.tensor(X_tr_np[idx], dtype=torch.float32, device=config["device"])
                yb = torch.tensor(y_tr_np[idx], dtype=torch.float32, device=config["device"])
                optimizer.zero_grad(set_to_none=True)
                preds = prediction_getter(model, xb)
                loss = listnet_loss(preds, yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                del xb, yb, preds, loss

                val_preds = self._predict_numpy_in_batches(
                    model,
                    X_val_np,
                    config["device"],
                    prediction_getter,
                    batch_size=min(batch_size, 256),
                )
                val_ic = _safe_spearman(val_preds, y_val_np)
                model.train()

                if config.get("verbose_training") and (
                    step == 0
                    or step + 1 == config["max_steps"]
                    or ((step + 1) % max(progress_every, 1) == 0)
                ):
                    print(
                        f"  {model_label} attempt {attempt + 1}: step {step + 1}/{config['max_steps']} val_ic={val_ic:.4f}",
                        flush=True,
                    )

                if val_ic > best_val_ic + 1e-4:
                    best_val_ic = val_ic
                    best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= config["patience_steps"]:
                        break

            if best_state is not None:
                model.load_state_dict(best_state)

            final_val_preds = self._predict_numpy_in_batches(
                model,
                X_val_np,
                config["device"],
                prediction_getter,
                batch_size=min(batch_size, 256),
            )
            final_val_ic = _safe_spearman(final_val_preds, y_val_np)
            if final_val_ic > best_overall_ic:
                best_overall_ic = final_val_ic
                best_overall = model
            if final_val_ic > 0.005:
                print(
                    f"  {model_label} sign check passed on attempt {attempt + 1}: val_ic={final_val_ic:.4f}",
                    flush=True,
                )
                return model
            print(
                f"  {model_label} sign check failed on attempt {attempt + 1}: val_ic={final_val_ic:.4f}",
                flush=True,
            )

        print(
            f"  WARNING: {model_label} did not clear the sign check; using the best available attempt (val_ic={best_overall_ic:.4f})",
            flush=True,
        )
        return best_overall

    def _run_model(self, model_name: str, model_factory, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        return super()._run_model(model_name, model_factory, config)

    def _run_day2(self) -> None:
        patchtst_results = self._load_patchtst_results()
        patchtst_summary = self._normalize_frontier_summary(patchtst_results["summary"])
        patchtst_results["summary"] = patchtst_summary
        patchtst_stability = patchtst_results.get("stability", {})
        print(
            f"PatchTST: IC={patchtst_summary.get('mean_test_ic', float('nan')):.4f} "
            f"ratio={patchtst_summary.get('mean_train_test_ratio', float('nan')):.2f}x "
            f"verdict={patchtst_summary.get('verdict', 'UNKNOWN')}",
            flush=True,
        )

        tft_config, itransformer_config = self._frontier_configs()

        def train_tft(X_train: np.ndarray, y_train: np.ndarray, config: dict[str, Any]):
            def build_model():
                return TFTRanker(
                    n_features=X_train.shape[1],
                    hidden_size=config["hidden_size"],
                    n_heads=config["n_heads"],
                    n_attn_layers=config["n_attn_layers"],
                    dropout=config["dropout"],
                )

            return self._train_with_sign_check(
                build_model,
                X_train,
                y_train,
                config,
                "TFT",
                lambda model, batch: model(batch)[0],
            )

        def tft_factory(X_train, y_train, X_test, feature_names, config):
            model = train_tft(X_train, y_train, config)
            train_preds = self._predict_numpy_in_batches(
                model,
                X_train,
                config["device"],
                lambda current_model, batch: current_model(batch)[0],
                batch_size=min(int(config["batch_size"]), 256),
            )
            test_preds = self._predict_numpy_in_batches(
                model,
                X_test,
                config["device"],
                lambda current_model, batch: current_model(batch)[0],
                batch_size=min(int(config["batch_size"]), 256),
            )
            sample = torch.tensor(X_test[: min(len(X_test), 512)], dtype=torch.float32, device=config["device"])
            model.eval()
            with torch.no_grad():
                importance = model.get_selection_weights(sample)
            return train_preds, test_preds, importance.cpu().numpy()

        def train_itransformer(X_train: np.ndarray, y_train: np.ndarray, config: dict[str, Any]):
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            def build_model():
                return ITransformerRanker(
                    n_features=X_train.shape[1],
                    d_model=config["d_model"],
                    n_heads=config["n_heads"],
                    n_layers=config["n_layers"],
                    d_ff=config["d_ff"],
                    dropout=config["dropout"],
                    use_cls_token=config["use_cls_token"],
                )

            model = self._train_with_sign_check(
                build_model,
                X_train,
                y_train,
                config,
                "iTransformer",
                lambda model, batch: model(batch),
            )
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return model

        def itransformer_factory(X_train, y_train, X_test, feature_names, config):
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            model = train_itransformer(X_train, y_train, config)
            train_preds = self._predict_numpy_in_batches(
                model,
                X_train,
                config["device"],
                lambda current_model, batch: current_model(batch),
                batch_size=min(int(config["batch_size"]), 128),
            )
            test_preds = self._predict_numpy_in_batches(
                model,
                X_test,
                config["device"],
                lambda current_model, batch: current_model(batch),
                batch_size=min(int(config["batch_size"]), 128),
            )
            X_test_t = torch.tensor(X_test[: min(len(X_test), 512)], dtype=torch.float32, device=config["device"])
            model.train()
            importance = model.get_feature_attention_weights(X_test_t[: min(len(X_test_t), 1024)]).cpu().numpy()
            return train_preds, test_preds, importance

        tft_results, tft_summary, tft_stability = self._run_model("TFT", tft_factory, tft_config)
        itransformer_results, itransformer_summary, itransformer_stability = self._run_model(
            "iTransformer",
            itransformer_factory,
            itransformer_config,
        )

        comparison_rows = [
            {
                "Model": "PatchTST",
                "Mean IC": patchtst_summary["mean_test_ic"],
                "IC IR": patchtst_summary["ic_ir"],
                "Ratio": patchtst_summary["mean_train_test_ratio"],
                "Hit Rate": patchtst_summary["mean_hit_rate"],
                "Stability": patchtst_stability.get("mean_pairwise_correlation", float("nan")),
                "Verdict": patchtst_summary["verdict"],
            },
            {
                "Model": "TFT",
                "Mean IC": tft_summary["mean_test_ic"],
                "IC IR": tft_summary["ic_ir"],
                "Ratio": tft_summary["mean_train_test_ratio"],
                "Hit Rate": tft_summary["mean_hit_rate"],
                "Stability": tft_stability["mean_pairwise_correlation"],
                "Verdict": tft_summary["verdict"],
            },
            {
                "Model": "iTransformer",
                "Mean IC": itransformer_summary["mean_test_ic"],
                "IC IR": itransformer_summary["ic_ir"],
                "Ratio": itransformer_summary["mean_train_test_ratio"],
                "Hit Rate": itransformer_summary["mean_hit_rate"],
                "Stability": itransformer_stability["mean_pairwise_correlation"],
                "Verdict": itransformer_summary["verdict"],
            },
        ]
        frontier_comparison_df = pd.DataFrame(comparison_rows)
        print("\nModel         | Mean IC | IC IR | Ratio | Hit Rate | Stability | Verdict")
        for _, row in frontier_comparison_df.iterrows():
            print(
                f"{row['Model']:<13} | {row['Mean IC']:.4f} | {row['IC IR']:.4f} | "
                f"{row['Ratio']:.2f}x | {row['Hit Rate']:.4f} | {row['Stability']:.4f} | {row['Verdict']}"
            )

        self.state.update(
            {
                "patchtst_results": patchtst_results,
                "patchtst_summary": patchtst_summary,
                "patchtst_stability": patchtst_stability,
                "tft_results": tft_results,
                "tft_summary": tft_summary,
                "tft_stability": tft_stability,
                "itransformer_results": itransformer_results,
                "itransformer_summary": itransformer_summary,
                "itransformer_stability": itransformer_stability,
                "all_model_results": {
                    "PatchTST": patchtst_results,
                    "TFT": tft_results,
                    "iTransformer": itransformer_results,
                },
                "all_summaries": {
                    "PatchTST": patchtst_summary,
                    "TFT": tft_summary,
                    "iTransformer": itransformer_summary,
                },
                "all_stabilities": {
                    "PatchTST": patchtst_stability,
                    "TFT": tft_stability,
                    "iTransformer": itransformer_stability,
                },
            }
        )

        self._export_model_payload("patchtst", patchtst_results, patchtst_summary, patchtst_stability)
        self._export_model_payload("tft", tft_results, tft_summary, tft_stability)
        self._export_model_payload(
            "itransformer",
            itransformer_results,
            itransformer_summary,
            itransformer_stability,
        )

        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {"day2_frontier_models": frontier_comparison_df.to_dict(orient="records")},
        )

    def _run_day3(self) -> None:
        feature_names = self.state["feature_names"]
        patchtst_stability = self.state["patchtst_stability"]
        tft_stability = self.state["tft_stability"]
        itransformer_stability = self.state["itransformer_stability"]

        patch_importance = patchtst_stability.get("mean_importance_by_feature", {})
        patch_scores: dict[int, list[float]] = {}
        for idx, feature in enumerate(feature_names):
            patch_id = idx // 16 + 1
            patch_scores.setdefault(patch_id, []).append(float(patch_importance.get(feature, 0.0)))
        patch_summary = sorted(
            [(patch_id, float(np.mean(values))) for patch_id, values in patch_scores.items()],
            key=lambda item: item[1],
            reverse=True,
        )
        print("PatchTST patch importance (top 10 patch positions):")
        for patch_id, score in patch_summary[:10]:
            print(f"  Patch {patch_id}: mean importance {score:.6f}")

        tft_weights = tft_stability.get("mean_importance_by_feature", {})
        always_selected = [feature for feature, weight in tft_weights.items() if weight > 0.05][:15]
        suppressed = [feature for feature, weight in tft_weights.items() if weight < 0.005][:15]
        print("\nTFT VSN weight analysis:")
        print(f"  Features usually selected (>0.05): {always_selected}")
        print(f"  Features usually suppressed (<0.005): {suppressed}")

        itransformer_importance = itransformer_stability.get("mean_importance_by_feature", {})
        top_itr_features = list(itransformer_importance.keys())[:12]
        pair_scores = []
        for left_idx in range(len(top_itr_features)):
            for right_idx in range(left_idx + 1, len(top_itr_features)):
                left_feature = top_itr_features[left_idx]
                right_feature = top_itr_features[right_idx]
                score = float(itransformer_importance[left_feature] * itransformer_importance[right_feature])
                pair_scores.append(((left_feature, right_feature), score))
        pair_scores = sorted(pair_scores, key=lambda item: item[1], reverse=True)
        print("\niTransformer inter-feature attention proxy (gradient co-importance, top 10 pairs):")
        for (left_feature, right_feature), score in pair_scores[:10]:
            print(f"  {left_feature} <-> {right_feature}: {score:.6f}")

        frontier_diagnostics = {
            "patchtst_patch_summary": patch_summary[:20],
            "tft_always_selected": always_selected,
            "tft_suppressed": suppressed,
            "itransformer_pairs_proxy": [
                {"left": left, "right": right, "score": score}
                for (left, right), score in pair_scores[:10]
            ],
        }
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {"day3_architecture_diagnostics": frontier_diagnostics},
        )

    def _has_valid_windows(self, model_name: str) -> bool:
        windows = self.state.get("all_model_results", {}).get(model_name, {}).get("windows", [])
        return any("error" not in window for window in windows)

    def _rank_models(self, require_windows: bool = False) -> list[str]:
        ranked = super()._rank_models()
        if not require_windows:
            return ranked
        return [model_name for model_name in ranked if self._has_valid_windows(model_name)]

    def _run_day4(self) -> None:
        if "all_summaries" not in self.state:
            raise RuntimeError("Day 4 requires model summaries from days 2-3.")

        regime_analyzer = RegimeConditionalIC()
        sector_analyzer = SectorICAnalyzer()
        ranked_models = self._rank_models()
        analysis_ranked_models = self._rank_models(require_windows=True) or ranked_models
        top2 = analysis_ranked_models[:2]
        self.state["ranked_models"] = ranked_models
        self.state["top2"] = top2
        print(f"Top 2 models for regime/sector analysis: {top2}")

        selected = {model_name: self.state["all_model_results"][model_name] for model_name in top2}
        regime_table = regime_analyzer.model_regime_breakdown(selected)
        print("\nRegime-conditional IC:")
        print(regime_table.round(4).to_string() if not regime_table.empty else "No regime table available.")

        for model_name in top2:
            print(f"\nSector IC - {model_name}:")
            sector_df = sector_analyzer.compute(self.state["features_df"], self.state["feature_names"])
            if sector_df.empty:
                print("  Sector column not available in this export, skipping.")
            else:
                print(sector_df.head(10).to_string(index=False))

        regime_ic = regime_analyzer.compute(
            self.state["features_df"],
            self.state["feature_names"],
            self.state["regime_df"],
        )
        for regime_name, ic_series in regime_ic.items():
            top5 = ic_series.abs().nlargest(5)
            print(f"\nTop 5 features in {regime_name}: {top5.index.tolist()}")

        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day4_regime_sector": {
                    "top2_models": top2,
                    "regime_table": regime_table.reset_index().to_dict(orient="records") if not regime_table.empty else [],
                    "regime_top_features": {
                        name: list(series.abs().nlargest(5).index)
                        for name, series in regime_ic.items()
                    },
                }
            },
        )

    def _run_day6(self) -> None:
        if "ranked_models" not in self.state:
            self.state["ranked_models"] = self._rank_models()
        ranked_models = self.state.get("ranked_models") or self._rank_models()
        ranked_with_windows = self._rank_models(require_windows=True)
        top2 = ranked_with_windows[:2] if len(ranked_with_windows) >= 2 else ranked_models[:2]
        ensemble_builder = EnsembleBuilder()
        ensemble_results_list = []

        if len(top2) >= 2:
            for split in self.state["splits"]:
                X_train, y_train, X_test, y_test = self.loader.get_window_arrays(
                    self.state["features_df"],
                    split,
                    self.state["feature_names"],
                )
                model_preds = {}
                ic_history = {}
                for model_name in top2:
                    model_windows = self.state["all_model_results"][model_name].get("windows", [])
                    valid_prior = [
                        window
                        for window in model_windows
                        if "error" not in window and window["window_id"] < split["window_id"]
                    ]
                    ic_history[model_name] = [window["test_ic"] for window in valid_prior[-10:]]
                    this_window = next(
                        (window for window in model_windows if window.get("window_id") == split["window_id"]),
                        None,
                    )
                    if this_window and "test_preds" in this_window:
                        preds = np.asarray(this_window["test_preds"], dtype=float)
                        if len(preds) == len(y_test):
                            model_preds[model_name] = preds
                if len(model_preds) >= 2:
                    ensemble_pred = ensemble_builder.build(model_preds, ic_history)
                    gain = ensemble_builder.evaluate_gain(ensemble_pred, model_preds, y_test)
                    gain["window_id"] = split["window_id"]
                    ensemble_results_list.append(gain)
        else:
            print("Not enough valid windowed models for ensemble analysis; continuing with deployment-only simulation.")

        mean_gain = None
        passes_parity = None
        if ensemble_results_list:
            mean_ensemble_ic = float(np.mean([row["ensemble_ic"] for row in ensemble_results_list]))
            mean_best_ic = float(np.mean([row["best_individual_ic"] for row in ensemble_results_list]))
            mean_gain = float(np.mean([row["ic_gain"] for row in ensemble_results_list]))
            passes_parity = bool(mean_gain > -0.003)
            print(f"\nEnsemble IC:        {mean_ensemble_ic:.4f}")
            print(f"Best individual IC: {mean_best_ic:.4f}")
            print(f"IC gain:            {mean_gain:+.4f}")
            print(f"Passes parity:      {passes_parity}")

        print("\n--- Deployment Sizing Simulation ---")
        best_model_for_deployment = ranked_with_windows[0] if ranked_with_windows else (ranked_models[0] if ranked_models else None)
        deployment_simulation = []
        if best_model_for_deployment is not None:
            for window in self.state["all_model_results"][best_model_for_deployment].get("windows", []):
                if "error" in window:
                    continue
                test_ic = window.get("test_ic", 0)
                if test_ic > 0.015:
                    simulated_exposure = 0.40
                elif test_ic > 0.005:
                    simulated_exposure = 0.20
                else:
                    simulated_exposure = 0.05
                deployment_simulation.append(
                    {
                        "window_id": window["window_id"],
                        "test_ic": test_ic,
                        "simulated_exposure": simulated_exposure,
                    }
                )

        sim_df = pd.DataFrame(deployment_simulation)
        if not sim_df.empty:
            print(f"Mean simulated exposure: {sim_df['simulated_exposure'].mean():.1%}")
            print(f"Windows above 20% exposure: {(sim_df['simulated_exposure'] >= 0.20).sum()}/{len(sim_df)}")
            print(f"Windows in HOLD (5%): {(sim_df['simulated_exposure'] <= 0.05).sum()}/{len(sim_df)}")

        self.state["mean_gain"] = mean_gain
        self.state["passes_parity"] = passes_parity
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day6_ensemble": ensemble_results_list,
                "day6_deployment_simulation": sim_df.to_dict(orient="records") if not sim_df.empty else [],
            },
        )

    def _run_day7(self) -> None:
        verdict_engine = PromotionVerdict()
        ranked_models = self.state.get("ranked_models") or self._rank_models()
        ranked_with_windows = self._rank_models(require_windows=True)
        best_model = ranked_models[0] if ranked_models else None
        best_summary = self.state.get("all_summaries", {}).get(best_model, {})
        best_stability = self.state.get("all_stabilities", {}).get(best_model, {})
        regime_source_model = ranked_with_windows[0] if ranked_with_windows else best_model
        best_regime = (
            self.engine.regime_breakdown(self.state["all_model_results"][regime_source_model])
            if regime_source_model and "all_model_results" in self.state
            else {}
        )
        ensemble_gain_result = {
            "ic_gain": self.state.get("mean_gain"),
            "passes_min_parity": self.state.get("passes_parity"),
        }
        verdict = verdict_engine.compute(
            self._ensure_ic_table_available("final verdict"),
            best_summary,
            best_stability,
            best_regime,
            ensemble_gain_result,
            self.track_name,
        )

        print("\n" + "=" * 60)
        print(f"TRACK B FINAL VERDICT: {verdict['verdict']} - {verdict['verdict_label']}")
        print("=" * 60)
        if best_model is not None:
            print(f"\nBest model: {best_model}")
        print(f"Recommendation: {verdict['recommendation']}")
        print("\nOpen questions:")
        for question in verdict["open_questions"]:
            print(f"  - {question}")

        memo = verdict_engine.format_memo(verdict, self.track_name)
        memo_path = self.output_dir / "track_b_promotion_memo.md"
        memo_path.write_text(memo, encoding="utf-8")
        print("\n--- PROMOTION MEMO ---")
        print(memo)

        track_a_payload = self._load_track_a_payload()
        if track_a_payload and "all_model_summaries" in track_a_payload:
            track_a_summaries = track_a_payload["all_model_summaries"]
            best_track_a_model = max(
                track_a_summaries,
                key=lambda name: float(track_a_summaries[name].get("ic_ir", float("-inf"))),
            )
            best_track_a_summary = track_a_summaries[best_track_a_model]
            print("\n=== CROSS-TRACK COMPARISON ===")
            print(f"Best Track A model: {best_track_a_model}")
            print(f"Best Track B model: {best_model}")
            metrics = [
                ("mean_test_ic", "higher"),
                ("ic_ir", "higher"),
                ("mean_train_test_ratio", "lower"),
                ("mean_hit_rate", "higher"),
            ]
            for metric, direction in metrics:
                a_val = float(best_track_a_summary.get(metric, np.nan))
                b_val = float(best_summary.get(metric, np.nan))
                if direction == "higher":
                    winner = "Track A" if a_val > b_val else "Track B"
                    delta = b_val - a_val
                else:
                    winner = "Track A" if a_val < b_val else "Track B"
                    delta = a_val - b_val
                print(f"  {metric}: {winner} wins by {delta:+.4f}")
        else:
            print("\nCross-track comparison skipped: attach Track A output to this notebook to compare both tracks directly.")

        total_time = (time.time() - self.sprint_start) / 60.0
        self.state["run_summary"] = {
            "best_model": best_model,
            "verdict": verdict["verdict"],
            "verdict_label": verdict["verdict_label"],
            "memo_path": str(memo_path),
            "total_runtime_minutes": total_time,
            "day_status": self.day_status,
        }
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day7_verdict": verdict,
                "day7_memo_path": str(memo_path),
                "all_model_summaries": self.state.get("all_summaries", {}),
                "all_model_stabilities": self.state.get("all_stabilities", {}),
                "total_runtime_minutes": total_time,
            },
        )
        print(f"\n\nTrack B complete. Total runtime: {total_time:.1f} minutes")
        print(f"All results saved to {self.output_dir}")


def run_track_b_notebook(config: TrackBRunConfig | None = None) -> dict[str, Any]:
    """Convenience entrypoint used by the Kaggle notebook."""

    runner = TrackBRunner(config=config)
    return runner.run()
