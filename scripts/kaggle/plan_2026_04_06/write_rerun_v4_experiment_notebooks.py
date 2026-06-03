#!/usr/bin/env python3
"""Write brand-new rerun-v4 Kaggle notebooks for EXP-09 through EXP-18."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOWNLOADS_DIR = Path.home() / "Downloads"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint"


def _md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip() + "\n")


def _code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip() + "\n")


def _write_notebook(path: Path, cells: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python", "version": "3.12"}
    path.write_text(nbf.writes(nb), encoding="utf-8")


def _common_runtime(log_prefix: str) -> str:
    return dedent(
        """
        import json
        import math
        import time
        import warnings
        from datetime import datetime
        from pathlib import Path

        import numpy as np
        import pandas as pd
        from IPython.display import Markdown, display

        warnings.filterwarnings("ignore")

        try:
            from catboost import CatBoostRegressor
        except Exception as exc:
            raise RuntimeError("catboost is required for these rerun notebooks.") from exc

        try:
            import shap
        except Exception:
            shap = None

        try:
            from scipy import stats
        except Exception:
            stats = None

        LOG_PREFIX = "__LOG_PREFIX__"
        RUN_STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
        LEAK_WINDOW_IDS = {13, 17, 19}
        TARGET_COL = "target_weekly_return"
        EXPECTED_ROWS = 168431
        EXPECTED_COLS = 463
        EXPECTED_DATE_MIN = pd.Timestamp("2019-01-04")
        EXPECTED_SPLIT_GAP_DAYS = 7
        LEAKAGE_ABS_CORR_THRESHOLD = 0.15
        SUSPICIOUS_MIN_ROWS = 1000
        SPARSE_DATE_THRESHOLD = 10
        SPARSE_ROW_FRACTION_THRESHOLD = 0.05
        LOW_CARDINALITY_THRESHOLD = 10
        ACTIVE_CS_SHARE_MIN = 0.25
        ACTIVE_CS_DATES_MIN = 26
        DROP_REDUNDANT_CS_RANK = True
        FEATURE_AUDIT_STATE = {"kept": [], "quarantined": [], "report": []}

        FEATURE_EXCLUDE = {
            "date",
            "ticker",
            "sector",
            "broad_sector",
            "subsector",
            "plan_regime_id",
            "plan_regime_label",
            "major_event_id",
            "subtle_period_id",
            "regime_code",
            "regime_modifier",
            "oil_sensitivity_score",
            "fx_sensitivity_score",
            "rate_sensitivity_score",
            "steel_sensitivity_score",
            "pledge_pct_available",
            "rating_numeric_available",
            "days_since_earnings_available",
        }

        INTERACTION_SOURCE_COLS = [
            "fx_sensitivity_score",
            "rate_sensitivity_score",
            "oil_sensitivity_score",
            "steel_sensitivity_score",
            "copper_sensitivity_score",
            "gold_sensitivity_score",
            "international_revenue_proxy",
            "inrusd_4w_return",
            "dxy_4w_return",
            "rbi_rate_chg",
            "yield_curve_slope_ts_z",
            "crude_4w_return",
            "steel_4w_return",
            "copper_4w_return",
            "gold_4w_return",
            "india_vix_z",
            "india_vix_norm",
            "bab_signal",
        ]


        def log(message):
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"{LOG_PREFIX} {stamp} | {message}", flush=True)


        def log_kv(label, **kwargs):
            parts = ", ".join(f"{key}={value}" for key, value in kwargs.items())
            log(f"{label}: {parts}" if parts else label)


        def json_ready(value):
            if isinstance(value, dict):
                return {str(k): json_ready(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [json_ready(v) for v in value]
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, pd.Timestamp):
                return value.isoformat()
            if isinstance(value, np.generic):
                return value.item()
            if isinstance(value, float) and not np.isfinite(value):
                return None
            return value


        def write_json(path, payload):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
            log(f"Wrote JSON: {path}")
            return path


        def write_text(path, text):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(text).strip() + "\\n", encoding="utf-8")
            log(f"Wrote text: {path}")
            return path


        def write_table(path, frame):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".parquet":
                frame.to_parquet(path, index=False)
            else:
                frame.to_csv(path, index=False)
            log_kv("Wrote table", path=path, rows=len(frame), cols=frame.shape[1])
            return path


        def log_frame(name, frame):
            details = {"rows": len(frame), "cols": frame.shape[1]}
            if "date" in frame.columns and len(frame):
                details["date_min"] = str(pd.to_datetime(frame["date"], errors="coerce").min())
                details["date_max"] = str(pd.to_datetime(frame["date"], errors="coerce").max())
            if "ticker" in frame.columns:
                details["tickers"] = int(frame["ticker"].nunique())
            log_kv(name, **details)


        def dedupe(items):
            seen = set()
            output = []
            for item in items:
                if item in seen:
                    continue
                seen.add(item)
                output.append(item)
            return output


        def slugify(value):
            clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
            while "__" in clean:
                clean = clean.replace("__", "_")
            return clean or "unknown"


        def resolve_output_base(preferred):
            candidates = [
                Path(preferred),
                Path("/kaggle/working"),
                Path.cwd(),
                Path("/tmp"),
            ]
            seen = set()
            for candidate in candidates:
                key = str(candidate.expanduser())
                if key in seen:
                    continue
                seen.add(key)
                try:
                    candidate = candidate.expanduser()
                    candidate.mkdir(parents=True, exist_ok=True)
                    log(f"Resolved output base at: {candidate}")
                    return candidate
                except Exception as exc:
                    log(f"Output base candidate failed: {candidate} ({exc})")
            raise RuntimeError(f"Unable to create output base from preferred path: {preferred}")


        def experiment_dir(exp_slug):
            root = OUTPUT_BASE / f"northstar_{exp_slug}_{RUN_STAMP}"
            root.mkdir(parents=True, exist_ok=True)
            return root


        def resolve_export_dir():
            required = [
                "northstar_features.parquet",
                "northstar_metadata.parquet",
                "northstar_regime_labels.parquet",
                "northstar_walk_forward_splits.json",
            ]

            def _candidate_dirs(root):
                if not root.exists() or not root.is_dir():
                    return []
                results = []
                if all((root / name).exists() for name in required):
                    results.append(root)
                try:
                    for match in root.rglob(required[0]):
                        parent = match.parent
                        if all((parent / name).exists() for name in required):
                            results.append(parent)
                except Exception:
                    pass
                deduped = []
                seen = set()
                for item in sorted(results, key=lambda p: (len(p.parts), str(p))):
                    key = str(item)
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(item)
                return deduped

            probes = []
            if EXPORT_DIR_OVERRIDE:
                probes.append(Path(EXPORT_DIR_OVERRIDE).expanduser())
            probes.extend(Path(item) for item in EXPORT_CANDIDATES)
            kaggle_root = Path("/kaggle/input")
            if kaggle_root.exists():
                probes.append(kaggle_root)
                probes.extend(sorted(path for path in kaggle_root.iterdir() if path.is_dir()))

            checked = []
            log("Resolving export dataset directory")
            for probe in probes:
                log(f"Checking probe: {probe}")
                if not probe.exists():
                    checked.append(str(probe))
                    log(f"Probe missing: {probe}")
                    continue
                for candidate in _candidate_dirs(probe):
                    log(f"Resolved export dataset at: {candidate}")
                    return candidate
                checked.append(str(probe))
                log(f"No complete export bundle found under: {probe}")

            raise FileNotFoundError(
                "Unable to resolve the export dataset recursively. Checked:\\n- "
                + "\\n- ".join(checked[:40])
            )


        def load_bundle(export_dir):
            root = Path(export_dir).expanduser().resolve()
            log(f"Loading export bundle from {root}")
            started = time.time()
            features = pd.read_parquet(root / "northstar_features.parquet")
            metadata = pd.read_parquet(root / "northstar_metadata.parquet")
            regimes = pd.read_parquet(root / "northstar_regime_labels.parquet")
            splits = json.loads((root / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))

            for frame in (features, metadata, regimes):
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

            log_frame("features", features)
            log_frame("metadata", metadata)
            log_frame("regimes", regimes)
            log_kv("Loaded splits", count=len(splits))

            meta_cols = ["date", "ticker", "sector", "broad_sector", "subsector"]
            meta_available = [c for c in meta_cols if c in metadata.columns]
            merged = features.merge(metadata[meta_available], on=["date", "ticker"], how="left", sort=False)

            regime_cols = [c for c in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id", "subtle_period_id"] if c in regimes.columns]
            if regime_cols:
                log_kv("Merging regime columns", columns=regime_cols)
                merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)

            for col in ["sector", "broad_sector", "subsector", "plan_regime_label", "major_event_id"]:
                if col in merged.columns:
                    merged[col] = merged[col].fillna("Unknown").astype(str)

            log_frame("merged", merged)
            log_kv("Bundle load complete", seconds=round(time.time() - started, 2))
            return {
                "root": root,
                "features": features,
                "metadata": metadata,
                "regimes": regimes,
                "splits": list(splits),
                "merged": merged,
            }


        def validate_bundle(bundle):
            features = bundle["features"]
            required = ["date", "ticker", TARGET_COL]
            missing = [c for c in required if c not in features.columns]
            if missing:
                raise RuntimeError(f"Missing required columns: {missing}")
            dead_cols = [c for c in features.columns if "earnings_quality_ratio" in c]
            if dead_cols:
                raise RuntimeError(f"Dead earnings_quality_ratio columns came back: {dead_cols}")
            if features.columns[-1] != TARGET_COL:
                raise RuntimeError(f"Target column must be last. Found last={features.columns[-1]}")
            log_kv(
                "Validation passed",
                features_rows=len(features),
                feature_columns=features.shape[1],
                tickers=int(features["ticker"].nunique()),
                weekly_dates=int(features["date"].nunique()),
                windows=len(bundle["splits"]),
            )


        def audit_splits(bundle):
            rows = []
            for split in bundle["splits"]:
                train_end = pd.Timestamp(split["train_end"]).normalize()
                test_start = pd.Timestamp(split["test_start"]).normalize()
                gap_days = int((test_start - train_end).days)
                rows.append(
                    {
                        "window_id": int(split.get("window_id", 0)),
                        "train_end": str(train_end.date()),
                        "test_start": str(test_start.date()),
                        "gap_days": gap_days,
                        "is_expected_gap": bool(gap_days == EXPECTED_SPLIT_GAP_DAYS),
                    }
                )
            audit_df = pd.DataFrame(rows)
            bad = audit_df[~audit_df["is_expected_gap"]]
            log_kv("Split gap audit", windows=len(audit_df), bad_windows=len(bad))
            if not bad.empty:
                log_kv("Split gap anomalies", rows=bad.to_dict(orient="records")[:10])
            return audit_df


        def feature_family(col):
            if col.endswith("_cs_z"):
                return "cs_z"
            if col.endswith("_cs_rank"):
                return "cs_rank"
            if "_sector_resid" in col:
                return "sector_resid"
            if "_sector_rel" in col:
                return "sector_rel"
            if "_sector_z" in col:
                return "sector_z"
            if col.startswith("val_"):
                return "value_zscore"
            if col.startswith("stock_x_") or col.endswith("_x_sens") or col.endswith("_x_export"):
                return "interaction"
            if col.startswith("sector_dummy_"):
                return "sector_dummy"
            if col.startswith("macro_"):
                return "macro_raw"
            if col.startswith("mkt_sent_") or col.startswith("sent_"):
                return "sentiment"
            if col.endswith("_ts_z"):
                return "ts_z"
            if col.endswith("_available"):
                return "availability_flag"
            if col.endswith("_sensitivity_score"):
                return "sensitivity"
            return "raw"


        def is_prestandardized_feature(col):
            return feature_family(col) in {
                "cs_z",
                "cs_rank",
                "sector_resid",
                "sector_rel",
                "sector_z",
                "value_zscore",
                "interaction",
                "ts_z",
            }


        def build_feature_columns(bundle, extra_exclude=None):
            exclude = set(FEATURE_EXCLUDE)
            if extra_exclude:
                exclude.update(extra_exclude)
            features = bundle["features"]
            candidate_cols = [
                col for col in features.columns
                if col not in exclude
                and col != TARGET_COL
                and pd.api.types.is_numeric_dtype(features[col])
            ]
            target = pd.to_numeric(features[TARGET_COL], errors="coerce")
            total_rows = max(len(features), 1)
            report_rows = []
            kept = []
            quarantined = []
            for col in candidate_cols:
                family = feature_family(col)
                series = pd.to_numeric(features[col], errors="coerce")
                non_null = series.notna()
                non_null_rows = int(non_null.sum())
                non_null_dates = int(features.loc[non_null, "date"].nunique())
                unique_count = int(series[non_null].nunique()) if non_null_rows else 0
                by_date = features.groupby("date")[col].agg(["count", "std"])
                valid_dates = int((by_date["count"] >= 10).sum())
                active_cs_dates = int(((by_date["count"] >= 10) & (by_date["std"].fillna(0.0) > 1e-10)).sum())
                active_cs_share = float(active_cs_dates / valid_dates) if valid_dates else 0.0
                corr_abs = 0.0
                corr_raw = 0.0
                leakage_flag = False
                reason_bits = []
                if non_null_rows >= SUSPICIOUS_MIN_ROWS:
                    mask = non_null & target.notna()
                    if int(mask.sum()) >= SUSPICIOUS_MIN_ROWS and series[mask].nunique() >= 2 and target[mask].nunique() >= 2:
                        corr = series[mask].corr(target[mask], method="spearman")
                        if corr is not None and np.isfinite(corr):
                            corr_raw = float(corr)
                            corr_abs = abs(float(corr))
                is_sparse = (non_null_dates <= SPARSE_DATE_THRESHOLD) or ((non_null_rows / total_rows) <= SPARSE_ROW_FRACTION_THRESHOLD and unique_count <= LOW_CARDINALITY_THRESHOLD)
                if corr_abs >= LEAKAGE_ABS_CORR_THRESHOLD and is_sparse:
                    leakage_flag = True
                    reason_bits.append("sparse_high_target_corr")
                if col.startswith("macro_") and is_sparse:
                    leakage_flag = True
                    reason_bits.append("sparse_macro_feature")
                if family == "availability_flag":
                    leakage_flag = True
                    reason_bits.append("availability_flag")
                if active_cs_share < ACTIVE_CS_SHARE_MIN or active_cs_dates < ACTIVE_CS_DATES_MIN:
                    leakage_flag = True
                    reason_bits.append("low_cross_sectional_variation")
                if DROP_REDUNDANT_CS_RANK and family == "cs_rank" and col.replace("_cs_rank", "_cs_z") in candidate_cols:
                    leakage_flag = True
                    reason_bits.append("redundant_rank_with_cs_z")
                report_rows.append(
                    {
                        "feature": col,
                        "family": family,
                        "non_null_rows": non_null_rows,
                        "non_null_dates": non_null_dates,
                        "unique_count": unique_count,
                        "row_fraction": float(non_null_rows / total_rows),
                        "active_cs_dates": active_cs_dates,
                        "active_cs_share": active_cs_share,
                        "abs_spearman_target_corr": corr_abs,
                        "spearman_target_corr": corr_raw,
                        "quarantined": leakage_flag,
                        "reason": "|".join(reason_bits) if reason_bits else "",
                    }
                )
                if leakage_flag:
                    quarantined.append(col)
                else:
                    kept.append(col)
            FEATURE_AUDIT_STATE = {
                "kept": kept,
                "quarantined": quarantined,
                "report": report_rows,
            }
            globals()["FEATURE_AUDIT_STATE"] = FEATURE_AUDIT_STATE
            log_kv("Built feature column list", candidate_count=len(candidate_cols), kept_count=len(kept), quarantined_count=len(quarantined))
            if quarantined:
                log_kv("Quarantined features", features=quarantined[:20], total=len(quarantined))
            return kept


        def feature_audit_tables():
            report = pd.DataFrame(FEATURE_AUDIT_STATE.get("report", []))
            if report.empty:
                return report, report
            top_corr = (
                report.sort_values("abs_spearman_target_corr", ascending=False, kind="mergesort")
                .head(20)
                .reset_index(drop=True)
            )
            return report, top_corr


        def log_feature_audit():
            report, top_corr = feature_audit_tables()
            if report.empty:
                log("Feature audit unavailable.")
                return
            log_kv(
                "Feature audit summary",
                kept=len(FEATURE_AUDIT_STATE.get("kept", [])),
                quarantined=len(FEATURE_AUDIT_STATE.get("quarantined", [])),
                suspicious_top20=top_corr["feature"].tolist()[:10],
            )
            suspect_rows = top_corr[
                (top_corr["abs_spearman_target_corr"] >= LEAKAGE_ABS_CORR_THRESHOLD)
                | (top_corr["quarantined"])
            ]
            if not suspect_rows.empty:
                log_kv("Top target-correlation suspects", rows=suspect_rows.to_dict(orient="records")[:10])


        def add_cross_sectional_interactions(frame):
            working = frame.copy()
            added = []
            specs = [
                ("fx_x_sens", "inrusd_4w_return", "fx_sensitivity_score"),
                ("fx_x_export", "inrusd_4w_return", "international_revenue_proxy"),
                ("rate_x_sens", "rbi_rate_chg", "rate_sensitivity_score"),
                ("yc_x_sens", "yield_curve_slope_ts_z", "rate_sensitivity_score"),
                ("crude_x_sens", "crude_4w_return", "oil_sensitivity_score"),
                ("steel_x_sens", "steel_4w_return", "steel_sensitivity_score"),
                ("copper_x_sens", "copper_4w_return", "copper_sensitivity_score"),
                ("gold_x_sens", "gold_4w_return", "gold_sensitivity_score"),
                ("dxy_x_export", "dxy_4w_return", "international_revenue_proxy"),
                ("vix_x_beta", "india_vix_z", "bab_signal"),
            ]
            for name, left, right in specs:
                if name in working.columns or left not in working.columns or right not in working.columns:
                    continue
                working[name] = (
                    pd.to_numeric(working[left], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
                    * pd.to_numeric(working[right], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
                )
                added.append(name)
            log_kv("Added cross-sectional interactions", count=len(added), features=added)
            return working, added


        def build_model_frame(bundle, feature_cols, extra_cols=None):
            cols = ["date", "ticker", TARGET_COL, "sector", "broad_sector", "subsector", "plan_regime_id", "plan_regime_label", "major_event_id", "subtle_period_id"]
            cols.extend([c for c in (extra_cols or []) if c in bundle["merged"].columns])
            cols.extend([c for c in feature_cols if c in bundle["merged"].columns])
            cols = dedupe([c for c in cols if c in bundle["merged"].columns])
            frame = bundle["merged"][cols].copy()
            for col in feature_cols:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce")
            frame[TARGET_COL] = pd.to_numeric(frame[TARGET_COL], errors="coerce")
            frame = frame.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
            log_frame("model_frame", frame)
            return frame


        def run_preflight_checks(bundle, feature_cols):
            features = bundle["features"]
            assert features.shape == (EXPECTED_ROWS, EXPECTED_COLS), f"Wrong shape: {features.shape}"
            assert pd.Timestamp(features["date"].min()).normalize() == EXPECTED_DATE_MIN
            assert features.columns[-1] == TARGET_COL
            dead_cols = [c for c in features.columns if "earnings_quality_ratio" in c]
            assert len(dead_cols) == 0, f"Dead columns still present: {dead_cols}"
            assert "date" not in feature_cols
            assert "ticker" not in feature_cols
            assert TARGET_COL not in feature_cols
            test_ic = compute_ic(np.ones(100), np.random.randn(100))
            assert test_ic == 0.0, "compute_ic must return 0.0 for constant predictions"
            mock_windows = [
                {"test_ic": 0.05, "nan_flag": False},
                {"test_ic": 0.0, "nan_flag": True},
                {"test_ic": 0.03, "nan_flag": False},
            ]
            mock_mean = np.mean([row["test_ic"] for row in mock_windows])
            assert abs(mock_mean - 0.02667) < 0.001
            split_audit = audit_splits(bundle)
            assert bool(split_audit["is_expected_gap"].all()), "Unexpected split gap detected"
            log("All pre-flight checks passed. Proceeding with experiments.")


        def coerce_split_dates(split):
            return {
                "window_id": int(split.get("window_id", 0)),
                "train_start": pd.Timestamp(split["train_start"]).normalize(),
                "train_end": pd.Timestamp(split["train_end"]).normalize(),
                "test_start": pd.Timestamp(split["test_start"]).normalize(),
                "test_end": pd.Timestamp(split["test_end"]).normalize(),
            }


        def normalize_cs(df, feature_cols, skip_cols=None):
            df = df.copy()
            skip_cols = set(skip_cols or [])
            for col in feature_cols:
                if col in skip_cols or col not in df.columns:
                    continue
                if is_prestandardized_feature(col):
                    df[col] = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
                    continue
                df[col] = df.groupby("date")[col].transform(
                    lambda x: ((x - x.mean()) / (x.std() + 1e-8)).clip(-3, 3)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            return df


        def compute_ic_with_flag(preds, actuals):
            preds = np.asarray(preds, dtype=float)
            actuals = np.asarray(actuals, dtype=float)
            if len(preds) < 10:
                return 0.0, False
            if np.std(preds) < 1e-10 or np.std(actuals) < 1e-10:
                return 0.0, True
            if stats is None:
                corr = pd.Series(preds).corr(pd.Series(actuals), method="spearman")
                if corr is None or not np.isfinite(corr):
                    return 0.0, True
                return float(corr), False
            corr, _ = stats.spearmanr(preds, actuals)
            if corr is None or not np.isfinite(corr):
                return 0.0, True
            return float(corr), False


        def compute_ic(preds, actuals):
            value, _ = compute_ic_with_flag(preds, actuals)
            return value


        def compute_window_ic(scored_df, pred_col="pred", target_col=TARGET_COL):
            rows = []
            nan_count = 0
            if scored_df.empty:
                return {"mean_ic": 0.0, "date_ics": [], "nan_flag": True, "nan_dates": 0, "evaluated_dates": 0, "constant_date_share": 1.0}
            for date_value, group in scored_df.groupby("date", sort=True):
                ic_value, had_nan = compute_ic_with_flag(group[pred_col].to_numpy(), group[target_col].to_numpy())
                rows.append({"date": pd.Timestamp(date_value).normalize(), "ic": float(ic_value)})
                nan_count += int(had_nan)
            mean_ic = float(np.mean([row["ic"] for row in rows])) if rows else 0.0
            overall_nan_flag = False
            if rows:
                overall_nan_flag = bool(pd.to_numeric(scored_df[pred_col], errors="coerce").std() < 1e-10)
            return {
                "mean_ic": mean_ic,
                "date_ics": rows,
                "nan_flag": overall_nan_flag,
                "nan_dates": int(nan_count),
                "evaluated_dates": int(len(rows)),
                "constant_date_share": float(nan_count / max(len(rows), 1)),
            }


        def center_preds(frame, pred_col="pred"):
            frame = frame.copy()
            frame[pred_col] = frame.groupby("date")[pred_col].transform(
                lambda x: (x - x.mean()) / (x.std() + 1e-8)
            )
            frame[pred_col] = pd.to_numeric(frame[pred_col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            return frame


        def compute_hit_rate(test_df, pred_col="pred", target_col=TARGET_COL):
            hit_rates = []
            for _, group in test_df.groupby("date", sort=True):
                if len(group) < 10:
                    continue
                q80 = group[pred_col].quantile(0.8)
                q20 = group[pred_col].quantile(0.2)
                top = group.loc[group[pred_col] >= q80, target_col].mean()
                bot = group.loc[group[pred_col] <= q20, target_col].mean()
                if pd.isna(top) or pd.isna(bot):
                    continue
                hit_rates.append(1.0 if top > bot else 0.0)
            return float(np.mean(hit_rates)) if hit_rates else 0.0


        def make_chronological_val_split(frame, val_fraction=0.10):
            dates = sorted(pd.to_datetime(frame["date"]).dropna().unique())
            if len(dates) < 12:
                return frame.copy(), None
            cutoff = pd.Timestamp(dates[int(len(dates) * (1 - val_fraction))]).normalize()
            train_mask = frame["date"] < cutoff
            valid_mask = frame["date"] >= cutoff
            fit_frame = frame.loc[train_mask].copy()
            valid_frame = frame.loc[valid_mask].copy()
            if fit_frame.empty or valid_frame.empty:
                return frame.copy(), None
            return fit_frame, valid_frame


        def resolve_cat_feature_indices(feature_cols, cat_feature_names=None):
            cat_feature_names = [name for name in (cat_feature_names or []) if name in feature_cols]
            indices = [feature_cols.index(name) for name in cat_feature_names]
            return cat_feature_names, indices


        def fit_catboost(train_frame, feature_cols, params, use_early_stopping=True, cat_feature_names=None):
            cat_feature_names, cat_indices = resolve_cat_feature_indices(feature_cols, cat_feature_names)
            config = {
                "loss_function": "RMSE",
                "eval_metric": "RMSE",
                "random_seed": int(params.get("random_seed", 42)),
                "verbose": False,
                "allow_writing_files": False,
                "depth": int(params.get("depth", 4)),
                "l2_leaf_reg": float(params.get("l2_leaf_reg", 3)),
                "min_data_in_leaf": int(params.get("min_data_in_leaf", 1)),
                "od_type": "Iter",
                "od_wait": int(params.get("od_wait", 30)),
                "boosting_type": str(params.get("boosting_type", "Ordered")),
                "learning_rate": float(params.get("learning_rate", 0.05)),
                "iterations": int(params.get("iterations", 400)),
            }
            if "grow_policy" in params:
                config["grow_policy"] = str(params["grow_policy"])
            model = CatBoostRegressor(**config)
            fit_frame, valid_frame = make_chronological_val_split(train_frame)
            x_fit = fit_frame[feature_cols].fillna(0.0)
            y_fit = fit_frame[TARGET_COL].fillna(0.0)
            if use_early_stopping and valid_frame is not None and not valid_frame.empty:
                model.fit(
                    x_fit,
                    y_fit,
                    cat_features=cat_indices if cat_indices else None,
                    eval_set=(valid_frame[feature_cols].fillna(0.0), valid_frame[TARGET_COL].fillna(0.0)),
                    use_best_model=True,
                )
            else:
                model.fit(x_fit, y_fit, cat_features=cat_indices if cat_indices else None)
            return model


        def score_train_test(model, train_score, test_score, feature_cols):
            train_scored = train_score[["date", "ticker", TARGET_COL, "plan_regime_label", "sector", "subsector"]].copy()
            test_scored = test_score[["date", "ticker", TARGET_COL, "plan_regime_label", "sector", "subsector"]].copy()
            if "rbi_rate_chg" in train_score.columns:
                train_scored["rbi_rate_chg"] = train_score["rbi_rate_chg"].to_numpy()
            if "rbi_rate_chg" in test_score.columns:
                test_scored["rbi_rate_chg"] = test_score["rbi_rate_chg"].to_numpy()
            train_scored["pred"] = model.predict(train_score[feature_cols].fillna(0.0))
            test_scored["pred"] = model.predict(test_score[feature_cols].fillna(0.0))
            return center_preds(train_scored), center_preds(test_scored)


        def aggregate_results(window_results):
            all_test_ics = [row["test_ic"] for row in window_results]
            all_train_ics = [row["train_ic"] for row in window_results]
            all_ratios = [row["ratio"] for row in window_results if row["ratio"] < 500]
            all_hit_rates = [row["hit_rate"] for row in window_results]
            nan_count = sum(1 for row in window_results if row["nan_flag"])
            leak_ratios = [row["ratio"] for row in window_results if row["is_leak_window"] and row["ratio"] < 500]
            mean_test_ic = float(np.mean(all_test_ics)) if all_test_ics else 0.0
            mean_train_ic = float(np.mean(all_train_ics)) if all_train_ics else 0.0
            mean_ratio = float(np.mean(all_ratios)) if all_ratios else 999.0
            ic_std = float(np.std(all_test_ics)) if all_test_ics else 0.0
            return {
                "mean_test_ic": mean_test_ic,
                "mean_train_ic": mean_train_ic,
                "mean_ratio": mean_ratio,
                "ic_ir": float(mean_test_ic / (ic_std + 1e-8)),
                "ic_tstat": float(mean_test_ic / ((ic_std / max(math.sqrt(len(all_test_ics)), 1.0)) + 1e-8)) if all_test_ics else 0.0,
                "sign_stability": float(np.mean([1 if ic > 0 else 0 for ic in all_test_ics])) if all_test_ics else 0.0,
                "mean_hit_rate": float(np.mean(all_hit_rates)) if all_hit_rates else 0.0,
                "leak_window_ratio": float(np.mean(leak_ratios)) if leak_ratios else None,
                "nan_window_count": int(nan_count),
                "n_windows": int(len(window_results)),
                "gate_ic": bool(mean_test_ic >= 0.020),
                "gate_ratio": bool(mean_ratio < 2.5),
                "verdict_a": bool(mean_test_ic >= 0.020 and mean_ratio < 2.5),
            }


        def run_single_config(
            frame,
            feature_cols,
            splits,
            params,
            config_label,
            exp_root,
            max_splits=None,
            override_window_years=None,
            use_early_stopping=True,
            fit_frame=None,
            score_tickers=None,
            train_eval_tickers=None,
            test_eval_tickers=None,
            cat_feature_names=None,
        ):
            selected_splits = list(splits[:max_splits] if max_splits else splits)
            reference_frame = fit_frame if fit_frame is not None else frame
            score_ticker_set = set(score_tickers or [])
            train_eval_ticker_set = set(train_eval_tickers or score_ticker_set or [])
            test_eval_ticker_set = set(test_eval_tickers or score_ticker_set or [])
            window_results = []
            scored_tests = []
            candidate_dir = exp_root / "artifacts" / slugify(config_label)
            candidate_dir.mkdir(parents=True, exist_ok=True)
            log_kv("Candidate start", config=config_label, windows=len(selected_splits), feature_count=len(feature_cols))
            for split in selected_splits:
                split_dates = coerce_split_dates(split)
                window_id = split_dates["window_id"]
                train_start = split_dates["train_start"]
                if override_window_years is not None:
                    train_start = (split_dates["train_end"] - pd.DateOffset(years=int(override_window_years))).normalize()
                    train_start = max(train_start, pd.Timestamp(reference_frame["date"].min()).normalize())
                train_fit = reference_frame[
                    reference_frame["date"].between(train_start, split_dates["train_end"])
                ].copy()
                test_fit = reference_frame[
                    reference_frame["date"].between(split_dates["test_start"], split_dates["test_end"])
                ].copy()
                train_fit = normalize_cs(train_fit, feature_cols, skip_cols=cat_feature_names)
                test_fit = normalize_cs(test_fit, feature_cols, skip_cols=cat_feature_names)
                if train_eval_ticker_set:
                    train_score = train_fit[train_fit["ticker"].isin(train_eval_ticker_set)].copy()
                else:
                    train_score = train_fit.copy()
                if test_eval_ticker_set:
                    test_score = test_fit[test_fit["ticker"].isin(test_eval_ticker_set)].copy()
                else:
                    test_score = test_fit.copy()
                if len(train_fit) < 1000 or len(test_score) < 200:
                    result = {
                        "window": window_id,
                        "train_start": str(train_start.date()),
                        "train_end": str(split_dates["train_end"].date()),
                        "test_start": str(split_dates["test_start"].date()),
                        "test_end": str(split_dates["test_end"].date()),
                        "train_ic": 0.0,
                        "test_ic": 0.0,
                        "ratio": 999.0,
                        "hit_rate": 0.0,
                        "n_train": int(len(train_fit)),
                        "n_test": int(len(test_score)),
                        "regime": str(test_score["plan_regime_label"].mode(dropna=True).iloc[0]) if not test_score.empty and "plan_regime_label" in test_score.columns else "Unknown",
                        "nan_flag": True,
                        "nan_date_count": 0,
                        "constant_date_share": 1.0,
                        "is_leak_window": bool(window_id in LEAK_WINDOW_IDS),
                    }
                    window_results.append(result)
                    log_kv("Window skipped", config=config_label, window=window_id, n_train=len(train_fit), n_test=len(test_score))
                    continue
                log_kv(
                    "Window start",
                    config=config_label,
                    window=window_id,
                    train_start=train_start.date(),
                    train_end=split_dates["train_end"].date(),
                    test_start=split_dates["test_start"].date(),
                    test_end=split_dates["test_end"].date(),
                    n_train=len(train_fit),
                    n_test=len(test_score),
                )
                model = fit_catboost(train_fit, feature_cols, params, use_early_stopping=use_early_stopping, cat_feature_names=cat_feature_names)
                train_scored, test_scored = score_train_test(model, train_score, test_score, feature_cols)
                train_metrics = compute_window_ic(train_scored)
                test_metrics = compute_window_ic(test_scored)
                hit_rate = compute_hit_rate(test_scored)
                test_ic = float(test_metrics["mean_ic"])
                train_ic = float(train_metrics["mean_ic"])
                ratio = float(abs(train_ic / test_ic)) if abs(test_ic) > 1e-6 else 999.0
                regime = str(test_scored["plan_regime_label"].mode(dropna=True).iloc[0]) if not test_scored.empty else "Unknown"
                result = {
                    "window": window_id,
                    "train_start": str(train_start.date()),
                    "train_end": str(split_dates["train_end"].date()),
                    "test_start": str(split_dates["test_start"].date()),
                    "test_end": str(split_dates["test_end"].date()),
                    "train_ic": train_ic,
                    "test_ic": test_ic,
                    "ratio": ratio,
                    "hit_rate": float(hit_rate),
                    "n_train": int(len(train_fit)),
                    "n_test": int(len(test_score)),
                    "regime": regime,
                    "nan_flag": bool(test_metrics["nan_flag"]),
                    "nan_date_count": int(test_metrics["nan_dates"]),
                    "constant_date_share": float(test_metrics["constant_date_share"]),
                    "is_leak_window": bool(window_id in LEAK_WINDOW_IDS),
                }
                window_results.append(result)
                log_kv(
                    "Window complete",
                    config=config_label,
                    window=window_id,
                    train_ic=round(train_ic, 6),
                    test_ic=round(test_ic, 6),
                    ratio=round(ratio, 6) if ratio < 900 else 999.0,
                    hit_rate=round(float(hit_rate), 6),
                    nan_flag=result["nan_flag"],
                    nan_date_count=result["nan_date_count"],
                    regime=regime,
                )
                test_scored = test_scored.copy()
                test_scored["window"] = window_id
                scored_tests.append(test_scored)
            aggregate = aggregate_results(window_results)
            payload = {
                "config_label": config_label,
                "params": dict(params),
                "window_results": window_results,
                "aggregate": aggregate,
            }
            write_table(candidate_dir / "window_results.csv", pd.DataFrame(window_results))
            write_json(candidate_dir / "results.json", payload)
            if scored_tests:
                write_table(candidate_dir / "scored_test_predictions.csv", pd.concat(scored_tests, ignore_index=True))
            log_kv(
                "Candidate complete",
                config=config_label,
                mean_test_ic=aggregate["mean_test_ic"],
                mean_ratio=aggregate["mean_ratio"],
                nan_windows=aggregate["nan_window_count"],
            )
            return {
                "payload": payload,
                "aggregate": aggregate,
                "window_results": window_results,
                "scored_tests": pd.concat(scored_tests, ignore_index=True) if scored_tests else pd.DataFrame(),
            }


        def pick_best_result(rows):
            if not rows:
                return None
            verdict_rows = [row for row in rows if row["verdict_a"]]
            if verdict_rows:
                verdict_rows.sort(key=lambda row: (row["mean_ratio"], -row["mean_test_ic"], -row["ic_ir"]))
                return verdict_rows[0]
            qualified = [row for row in rows if row["gate_ic"]]
            if qualified:
                qualified.sort(key=lambda row: (row["mean_ratio"], -row["mean_test_ic"], -row["ic_ir"]))
                return qualified[0]
            fallback = sorted(rows, key=lambda row: (-row["mean_test_ic"], row["mean_ratio"], -row["ic_ir"]))
            return fallback[0]


        def sort_candidate_rows(rows):
            return sorted(
                rows,
                key=lambda row: (
                    0 if row["gate_ic"] else 1,
                    row["mean_ratio"],
                    -row["mean_test_ic"],
                    -row["ic_ir"],
                ),
            )


        def run_seed_validation(frame, feature_cols, splits, params, exp_root, label_prefix, seeds=(11, 23, 37, 47, 59), max_splits=None, score_tickers=None, cat_feature_names=None):
            rows = []
            for seed in seeds:
                seeded = dict(params)
                seeded["random_seed"] = int(seed)
                state = run_single_config(
                    frame=frame,
                    feature_cols=feature_cols,
                    splits=splits,
                    params=seeded,
                    config_label=f"{label_prefix}_seed_{seed}",
                    exp_root=exp_root,
                    max_splits=max_splits,
                    score_tickers=score_tickers,
                    cat_feature_names=cat_feature_names,
                )
                row = {
                    "seed": int(seed),
                    "mean_test_ic": state["aggregate"]["mean_test_ic"],
                    "mean_ratio": state["aggregate"]["mean_ratio"],
                    "ic_ir": state["aggregate"]["ic_ir"],
                    "nan_window_count": state["aggregate"]["nan_window_count"],
                }
                rows.append(row)
            table = pd.DataFrame(rows)
            write_table(exp_root / f"{label_prefix}_five_seed_validation.csv", table)
            write_json(exp_root / f"{label_prefix}_five_seed_validation.json", rows)
            return rows


        export_dir = resolve_export_dir()
        bundle = load_bundle(export_dir)
        validate_bundle(bundle)
        OUTPUT_BASE = resolve_output_base(OUTPUT_BASE)
        log_kv("Notebook bootstrap complete", export_dir=export_dir, output_base=OUTPUT_BASE)
        """
    ).replace("__LOG_PREFIX__", log_prefix)


RATIO_V2_NOTEBOOK = [
    _md(
        """
        # NORTHSTAR V3 Rerun V4: EXP-09 through EXP-12

        This notebook is the rerun-v4 campaign for the ratio experiments.

        It is built directly from the merged export and encodes the lessons from the first run:
        - NaN IC windows are treated as `0.0`, never dropped
        - the baseline sanity check is run first
        - `min_data_in_leaf=1` and `l2_leaf_reg=3` are restored for EXP-09 v4
        - train and test are normalized separately within each split
        - sparse target-correlated features are quarantined before modeling
        - all outputs are written incrementally after every candidate
        - logs are detailed enough to trace every window in Kaggle

        Attach only:
        - `northstar-v3-feature-export`
        """
    ),
    _md("## Config"),
    _code(
        """
        from pathlib import Path

        SELECTED_EXP = "EXP-09"  # EXP-09 | EXP-10 | EXP-11 | EXP-12
        RUN_FULL_CHAIN = True
        MAX_SPLITS = None
        OUTPUT_BASE = Path("/kaggle/working")
        EXPORT_DIR_OVERRIDE = None
        EXPORT_CANDIDATES = [
            "/kaggle/input/northstar-v3-feature-export",
            "/kaggle/input/northstar-v3-feature-export-1",
            "/kaggle/input/northstar-v3-feature-export-2",
        ]

        FORCE_STOP_ON_SANITY_FAIL = True
        RUN_FIVE_SEED_VALIDATION = True
        TREE_PARAM_OVERRIDES = {}

        EXP09_V2_GRID = [
            (3, 20), (3, 30), (3, 50),
            (4, 20), (4, 30), (4, 50),
            (5, 20), (5, 30), (5, 50),
            (6, 20), (6, 30), (6, 50),
        ]
        EXP10_L2_GRID = [3, 4, 5, 6, 7, 8, 10, 12, 15, 20]
        EXP11_CONFIGS = [
            {"boosting_type": "Ordered", "grow_policy": "SymmetricTree"},
            {"boosting_type": "Plain", "grow_policy": "SymmetricTree"},
            {"boosting_type": "Plain", "grow_policy": "Lossguide"},
        ]
        EXP12_WINDOW_YEARS = [1, 2, 3, 4]
        DEFAULT_TREE_PARAMS = {
            "depth": 4,
            "od_wait": 30,
            "l2_leaf_reg": 3,
            "min_data_in_leaf": 1,
            "learning_rate": 0.05,
            "iterations": 400,
            "boosting_type": "Ordered",
            "loss_function": "RMSE",
            "eval_metric": "RMSE",
            "random_seed": 42,
        }

        print(f"Notebook configured for {SELECTED_EXP}")
        """
    ),
    _md("## Runtime"),
    _code(_common_runtime("[ratio-rerun-v4]")),
    _md("## EXP-09 through EXP-12"),
    _code(
        """
        FEATURE_COLS = build_feature_columns(bundle)
        FRAME = build_model_frame(bundle, FEATURE_COLS, extra_cols=INTERACTION_SOURCE_COLS)
        FRAME, INTERACTION_FEATURES = add_cross_sectional_interactions(FRAME)
        FEATURE_COLS = dedupe([col for col in FEATURE_COLS if col in FRAME.columns] + INTERACTION_FEATURES)
        if FEATURE_AUDIT_STATE.get("report"):
            write_table(OUTPUT_BASE / "northstar_ratio_rerun_v4_feature_audit.csv", pd.DataFrame(FEATURE_AUDIT_STATE["report"]))
            write_json(OUTPUT_BASE / "northstar_ratio_rerun_v4_feature_audit.json", FEATURE_AUDIT_STATE)
            log_feature_audit()
        run_preflight_checks(bundle, FEATURE_COLS)

        RESULT_CACHE = {}


        def candidate_row(config_label, payload):
            aggregate = dict(payload["aggregate"])
            return {
                "config_label": config_label,
                "mean_test_ic": aggregate["mean_test_ic"],
                "mean_train_ic": aggregate["mean_train_ic"],
                "mean_ratio": aggregate["mean_ratio"],
                "ic_ir": aggregate["ic_ir"],
                "ic_tstat": aggregate["ic_tstat"],
                "sign_stability": aggregate["sign_stability"],
                "mean_hit_rate": aggregate["mean_hit_rate"],
                "leak_window_ratio": aggregate["leak_window_ratio"],
                "nan_window_count": aggregate["nan_window_count"],
                "n_windows": aggregate["n_windows"],
                "gate_ic": aggregate["gate_ic"],
                "gate_ratio": aggregate["gate_ratio"],
                "verdict_a": aggregate["verdict_a"],
                "params": payload["params"],
            }


        def summary_path_for(exp_slug):
            matches = sorted(OUTPUT_BASE.glob(f"northstar_{exp_slug}_*/{exp_slug}_summary.json"))
            return matches[-1] if matches else None


        def load_previous_best(exp_slug):
            if exp_slug in RESULT_CACHE:
                return RESULT_CACHE[exp_slug].get("best_candidate")
            path = summary_path_for(exp_slug)
            if not path or not path.exists():
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("best_candidate")


        def resolve_best_params():
            params = dict(DEFAULT_TREE_PARAMS)
            params.update(dict(TREE_PARAM_OVERRIDES or {}))
            for exp_slug in ["exp11_v4", "exp10_v4", "exp09_v4"]:
                best = load_previous_best(exp_slug)
                if best:
                    params.update(dict(best.get("params") or {}))
                    break
            return params


        def write_experiment_summary(exp_root, exp_slug, title, rows, best_candidate, extras=None):
            table = pd.DataFrame(sort_candidate_rows(rows))
            write_table(exp_root / "candidate_table.csv", table)
            payload = {
                "exp_slug": exp_slug,
                "title": title,
                "feature_count": len(FEATURE_COLS),
                "candidate_count": len(rows),
                "best_candidate": best_candidate,
                "candidates": rows,
            }
            if extras:
                payload.update(extras)
            write_json(exp_root / f"{exp_slug}_summary.json", payload)
            verdict_lines = [
                f"{title}",
                "",
                f"Best config: {(best_candidate or {}).get('config_label', 'none')}",
                f"Mean test IC: {(best_candidate or {}).get('mean_test_ic', 'nan')}",
                f"Mean ratio: {(best_candidate or {}).get('mean_ratio', 'nan')}",
                f"Verdict A: {(best_candidate or {}).get('verdict_a', False)}",
            ]
            write_text(exp_root / f"{exp_slug}_verdict.txt", "\\n".join(verdict_lines))
            return payload


        def run_exp09_v4():
            exp_slug = "exp09_v4"
            exp_root = experiment_dir(exp_slug)
            title = "EXP-09 v4: CatBoost Depth x Early Stopping"
            sanity_params = {
                "depth": 6,
                "od_wait": 30,
                "l2_leaf_reg": 3,
                "min_data_in_leaf": 1,
                "learning_rate": 0.05,
                "iterations": 400,
                "boosting_type": "Ordered",
                "loss_function": "RMSE",
                "eval_metric": "RMSE",
                "random_seed": 42,
            }
            sanity_state = run_single_config(
                frame=FRAME,
                feature_cols=FEATURE_COLS,
                splits=bundle["splits"],
                params=sanity_params,
                config_label="sanity_check",
                exp_root=exp_root,
                max_splits=MAX_SPLITS,
                use_early_stopping=False,
            )
            sanity_payload = {
                "config_label": "sanity_check",
                "params": sanity_params,
                "aggregate": sanity_state["aggregate"],
                "window_results": sanity_state["window_results"],
            }
            write_json(exp_root / "sanity_check_results.json", sanity_payload)
            log_kv(
                "Sanity check result",
                mean_test_ic=sanity_state["aggregate"]["mean_test_ic"],
                mean_ratio=sanity_state["aggregate"]["mean_ratio"],
            )
            if FORCE_STOP_ON_SANITY_FAIL and sanity_state["aggregate"]["mean_test_ic"] < 0.020:
                write_text(
                    exp_root / f"{exp_slug}_verdict.txt",
                    "Sanity check failed: mean_test_ic below 0.020. Stopping EXP-09 v4 before the grid.",
                )
                raise RuntimeError("Sanity IC < 0.020. Dataset or feature pipeline issue must be resolved before EXP-09 v4.")

            rows = []
            for depth, od_wait in EXP09_V2_GRID:
                params = dict(DEFAULT_TREE_PARAMS)
                params.update(dict(TREE_PARAM_OVERRIDES or {}))
                params.update({"depth": int(depth), "od_wait": int(od_wait), "l2_leaf_reg": 3, "min_data_in_leaf": 1})
                label = f"depth_{depth}_odwait_{od_wait}"
                state = run_single_config(
                    frame=FRAME,
                    feature_cols=FEATURE_COLS,
                    splits=bundle["splits"],
                    params=params,
                    config_label=label,
                    exp_root=exp_root,
                    max_splits=MAX_SPLITS,
                    use_early_stopping=True,
                )
                row = candidate_row(label, {"aggregate": state["aggregate"], "params": params})
                write_json(exp_root / f"{label}_results.json", {**row, "window_results": state["window_results"]})
                rows.append(row)
                if row["verdict_a"]:
                    log(f"Verdict A achieved at {label}. Stopping EXP-09 v4 grid early.")
                    if RUN_FIVE_SEED_VALIDATION:
                        run_seed_validation(FRAME, FEATURE_COLS, bundle["splits"], params, exp_root, label, max_splits=MAX_SPLITS)
                    break
            best = pick_best_result(rows)
            payload = write_experiment_summary(
                exp_root,
                exp_slug,
                title,
                rows,
                best,
                extras={"sanity_check": sanity_payload},
            )
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp10_v4():
            exp_slug = "exp10_v4"
            exp_root = experiment_dir(exp_slug)
            title = "EXP-10 v4: L2 Regularization Sweep"
            best_exp09 = load_previous_best("exp09_v4")
            if not best_exp09 or not best_exp09.get("gate_ic"):
                raise RuntimeError("EXP-10 v4 requires a qualified EXP-09 v4 result first.")
            rows = []
            for l2_value in EXP10_L2_GRID:
                params = dict(DEFAULT_TREE_PARAMS)
                params.update(dict(best_exp09["params"]))
                params.update({"l2_leaf_reg": float(l2_value), "min_data_in_leaf": 1})
                label = f"l2_{str(l2_value).replace('.', '_')}"
                state = run_single_config(
                    frame=FRAME,
                    feature_cols=FEATURE_COLS,
                    splits=bundle["splits"],
                    params=params,
                    config_label=label,
                    exp_root=exp_root,
                    max_splits=MAX_SPLITS,
                    use_early_stopping=True,
                )
                row = candidate_row(label, {"aggregate": state["aggregate"], "params": params})
                row["l2_leaf_reg"] = float(l2_value)
                write_json(exp_root / f"{label}_results.json", {**row, "window_results": state["window_results"]})
                rows.append(row)
                if row["verdict_a"]:
                    log(f"Verdict A achieved at {label}. Stopping EXP-10 v4 sweep early.")
                    if RUN_FIVE_SEED_VALIDATION:
                        run_seed_validation(FRAME, FEATURE_COLS, bundle["splits"], params, exp_root, label, max_splits=MAX_SPLITS)
                    break
            qualified = [row for row in rows if row["gate_ic"]]
            pareto = sorted(qualified, key=lambda row: row["mean_ratio"])
            write_json(exp_root / "pareto_frontier.json", pareto)
            best = pick_best_result(rows)
            payload = write_experiment_summary(
                exp_root,
                exp_slug,
                title,
                rows,
                best,
                extras={"pareto_frontier": pareto},
            )
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp11_v4():
            exp_slug = "exp11_v4"
            exp_root = experiment_dir(exp_slug)
            title = "EXP-11 v4: Ordered vs Plain Boosting"
            best_exp10 = load_previous_best("exp10_v4")
            if not best_exp10:
                raise RuntimeError("EXP-11 v4 requires EXP-10 v4 results.")
            rows = []
            for config in EXP11_CONFIGS:
                params = dict(DEFAULT_TREE_PARAMS)
                params.update(dict(best_exp10["params"]))
                params.update(dict(config))
                label = f"{config['boosting_type'].lower()}_{config['grow_policy'].lower()}"
                state = run_single_config(
                    frame=FRAME,
                    feature_cols=FEATURE_COLS,
                    splits=bundle["splits"],
                    params=params,
                    config_label=label,
                    exp_root=exp_root,
                    max_splits=MAX_SPLITS,
                    use_early_stopping=True,
                )
                row = candidate_row(label, {"aggregate": state["aggregate"], "params": params})
                row["boosting_type"] = config["boosting_type"]
                row["grow_policy"] = config["grow_policy"]
                write_json(exp_root / f"{label}_results.json", {**row, "window_results": state["window_results"]})
                rows.append(row)
            ordered = next((row for row in rows if row["config_label"] == "ordered_symmetrictree"), None)
            comparisons = []
            for row in rows:
                if row["config_label"] == "ordered_symmetrictree" or ordered is None:
                    continue
                comparisons.append(
                    {
                        "config_label": row["config_label"],
                        "ic_ok": bool(row["mean_test_ic"] >= ordered["mean_test_ic"] - 0.005),
                        "ratio_ok": bool(row["mean_ratio"] <= ordered["mean_ratio"]),
                    }
                )
            best = pick_best_result(rows)
            payload = write_experiment_summary(
                exp_root,
                exp_slug,
                title,
                rows,
                best,
                extras={"comparisons": comparisons},
            )
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp12_v4():
            exp_slug = "exp12_v4"
            exp_root = experiment_dir(exp_slug)
            title = "EXP-12 v4: Training Window Length Extension"
            best_exp11 = load_previous_best("exp11_v4")
            if not best_exp11:
                raise RuntimeError("EXP-12 v4 requires EXP-11 v4 results.")
            rows = []
            regime_breakdowns = {}
            for years in EXP12_WINDOW_YEARS:
                params = dict(DEFAULT_TREE_PARAMS)
                params.update(dict(best_exp11["params"]))
                label = f"train_window_{years}yr"
                state = run_single_config(
                    frame=FRAME,
                    feature_cols=FEATURE_COLS,
                    splits=bundle["splits"],
                    params=params,
                    config_label=label,
                    exp_root=exp_root,
                    max_splits=MAX_SPLITS,
                    override_window_years=int(years),
                    use_early_stopping=True,
                )
                row = candidate_row(label, {"aggregate": state["aggregate"], "params": params})
                row["window_years"] = int(years)
                write_json(exp_root / f"{label}_results.json", {**row, "window_results": state["window_results"]})
                rows.append(row)
                regime_table = (
                    pd.DataFrame(state["window_results"])
                    .groupby("regime", as_index=False)["test_ic"]
                    .mean()
                    .rename(columns={"test_ic": "mean_test_ic"})
                )
                regime_breakdowns[label] = regime_table.to_dict(orient="records")
            best = pick_best_result(rows)
            payload = write_experiment_summary(
                exp_root,
                exp_slug,
                title,
                rows,
                best,
                extras={"regime_breakdowns": regime_breakdowns},
            )
            RESULT_CACHE[exp_slug] = payload
            return payload


        RUNNERS = {
            "EXP-09": run_exp09_v4,
            "EXP-10": run_exp10_v4,
            "EXP-11": run_exp11_v4,
            "EXP-12": run_exp12_v4,
        }

        run_order = ["EXP-09", "EXP-10", "EXP-11", "EXP-12"]
        if RUN_FULL_CHAIN:
            selected_order = run_order[: run_order.index(SELECTED_EXP) + 1]
        else:
            selected_order = [SELECTED_EXP]

        EXECUTION_RESULTS = {}
        for exp_id in selected_order:
            log_kv("Dispatching experiment", exp_id=exp_id, run_full_chain=RUN_FULL_CHAIN)
            EXECUTION_RESULTS[exp_id] = RUNNERS[exp_id]()
            display(Markdown(f"### {exp_id} complete"))

        EXECUTION_RESULTS[SELECTED_EXP]
        """
    ),
    _md("## Output Files"),
    _code(
        """
        existing = sorted(str(path) for path in OUTPUT_BASE.glob("northstar_exp*_v4_*"))
        log_kv("Output inventory", count=len(existing))
        pd.DataFrame({"experiment_dirs": existing})
        """
    ),
]


SECTOR_V2_NOTEBOOK = [
    _md(
        """
        # NORTHSTAR V3 Rerun V4: EXP-13 through EXP-18

        This notebook is the rerun-v4 campaign for the sector, event, and collapse experiments.

        It uses the built dataset exactly as it exists today and adapts to the real schema:
        - Financial Services expands beyond the narrow first-run label match
        - missing compendium columns are aliased or skipped honestly
        - event windows come from the regime parquet first, then fall back only when needed
        - train and test are normalized separately within each split
        - sparse target-correlated features are quarantined before modeling
        - all outputs are written incrementally and all major loops are logged

        Attach only:
        - `northstar-v3-feature-export`
        """
    ),
    _md("## Config"),
    _code(
        """
        from pathlib import Path

        SELECTED_EXP = "EXP-13"  # EXP-13 | EXP-14 | EXP-15 | EXP-16 | EXP-17 | EXP-18
        RUN_FULL_CHAIN = False
        MAX_SPLITS = None
        OUTPUT_BASE = Path("/kaggle/working")
        EXPORT_DIR_OVERRIDE = None
        EXPORT_CANDIDATES = [
            "/kaggle/input/northstar-v3-feature-export",
            "/kaggle/input/northstar-v3-feature-export-1",
            "/kaggle/input/northstar-v3-feature-export-2",
        ]

        TREE_BASE_PARAMS = {
            "depth": 4,
            "od_wait": 30,
            "l2_leaf_reg": 3,
            "min_data_in_leaf": 1,
            "learning_rate": 0.05,
            "iterations": 400,
            "boosting_type": "Ordered",
            "loss_function": "RMSE",
            "eval_metric": "RMSE",
            "random_seed": 42,
        }
        TREE_PARAM_OVERRIDES = {}
        EXP07_BASELINE_IC = 0.0461

        OFFSHORE_IT = ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTIM.NS", "COFORGE.NS", "PERSISTENT.NS"]
        DOMESTIC_IT = ["MPHASIS.NS", "CYIENT.NS", "KPITTECH.NS", "TATAELXSI.NS"]

        EXP17_FACTORS = [
            "eps_sue_decay",
            "eps_revision_accel",
            "rev_sue_decay",
            "agreement_score",
            "accruals_ratio",
        ]
        EXP17_ALIASES = {
            "eps_revision_accel": ["eps_revision_accel_cs_z", "eps_accel", "rev_accel"],
            "agreement_score": ["agreement_score_cs_z", "analyst_agreement"],
            "accruals_ratio": ["accruals_ratio_cs_z", "accruals_cs_z"],
        }
        EXP18_FALLBACK_EVENTS = {
            "E004_GFC": ("2008-09-01", "2009-03-31"),
            "E007_TaperTantrum": ("2013-05-01", "2013-08-31"),
            "E011_Demonetization": ("2016-11-01", "2017-01-31"),
            "E012_ILFS": ("2018-09-01", "2019-01-31"),
            "E014_COVID": ("2020-02-01", "2020-05-31"),
        }

        print(f"Notebook configured for {SELECTED_EXP}")
        """
    ),
    _md("## Runtime"),
    _code(_common_runtime("[sector-regime-rerun-v4]")),
    _md("## EXP-13 through EXP-18"),
    _code(
        """
        BASE_FEATURE_COLS = build_feature_columns(bundle)
        FULL_FRAME = build_model_frame(bundle, BASE_FEATURE_COLS, extra_cols=INTERACTION_SOURCE_COLS)
        FULL_FRAME, INTERACTION_FEATURES = add_cross_sectional_interactions(FULL_FRAME)
        BASE_FEATURE_COLS = dedupe([col for col in BASE_FEATURE_COLS if col in FULL_FRAME.columns] + INTERACTION_FEATURES)
        if FEATURE_AUDIT_STATE.get("report"):
            write_table(OUTPUT_BASE / "northstar_sector_rerun_v4_feature_audit.csv", pd.DataFrame(FEATURE_AUDIT_STATE["report"]))
            write_json(OUTPUT_BASE / "northstar_sector_rerun_v4_feature_audit.json", FEATURE_AUDIT_STATE)
            log_feature_audit()
        run_preflight_checks(bundle, BASE_FEATURE_COLS)
        BASE_PARAMS = dict(TREE_BASE_PARAMS)
        BASE_PARAMS.update(dict(TREE_PARAM_OVERRIDES or {}))
        META_LOOKUP = bundle["metadata"][["ticker", "sector", "subsector"]].drop_duplicates().copy()
        META_LOOKUP["sector"] = META_LOOKUP["sector"].fillna("Unknown").astype(str)
        META_LOOKUP["subsector"] = META_LOOKUP["subsector"].fillna("Unknown").astype(str)
        RESULT_CACHE = {}


        def tickers_for_mask(mask):
            return sorted(META_LOOKUP.loc[mask, "ticker"].dropna().astype(str).unique().tolist())


        def finance_universes():
            sector_lower = META_LOOKUP["sector"].str.lower()
            subsector_lower = META_LOOKUP["subsector"].str.lower()
            include_mask = (
                sector_lower.str.contains("financial services", na=False)
                | subsector_lower.str.contains(r"\\bbank|insurance|finance|housing finance|gold loan|broking|wealth|payments|exchange|asset management|lending", regex=True, na=False)
            )
            exclude_mask = subsector_lower.str.contains("banking software|bfsi it|it services|insurance & travel focus", na=False)
            full_fs = tickers_for_mask(include_mask & ~exclude_mask)
            banks = tickers_for_mask((include_mask & ~exclude_mask) & subsector_lower.str.contains(r"\\bbank|small finance bank|private sector bank|public sector bank", regex=True, na=False))
            nbfcs = tickers_for_mask((include_mask & ~exclude_mask) & subsector_lower.str.contains(r"nbfc|housing finance|consumer finance|gold loan|commercial vehicle.*finance|diversified financial", regex=True, na=False))
            lenders = tickers_for_mask((include_mask & ~exclude_mask) & subsector_lower.str.contains(r"\\bbank|nbfc|finance|housing finance|gold loan|vehicle finance|lending", regex=True, na=False))
            insurance = tickers_for_mask((include_mask & ~exclude_mask) & subsector_lower.str.contains("insurance", na=False))
            other_financials = sorted(set(full_fs) - set(lenders) - set(insurance))
            log_kv("Financial Services universe", full_fs=len(full_fs), lenders=len(lenders), banks=len(banks), nbfcs=len(nbfcs), insurance=len(insurance), other_financials=len(other_financials))
            return {"full_fs": full_fs, "lenders": lenders, "banks": banks, "nbfcs": nbfcs, "insurance": insurance, "other_financials": other_financials}


        def it_universe():
            sector_lower = META_LOOKUP["sector"].str.lower()
            subsector_lower = META_LOOKUP["subsector"].str.lower()
            mask = sector_lower.str.contains("information technology", na=False) | subsector_lower.str.contains("it services|software|kpo|bpo|technology", na=False)
            tickers = tickers_for_mask(mask)
            log_kv("IT universe", tickers=len(tickers))
            return tickers


        def capital_goods_universe():
            sector_lower = META_LOOKUP["sector"].str.lower()
            subsector_lower = META_LOOKUP["subsector"].str.lower()
            mask = (
                sector_lower.str.contains("capital goods", na=False)
                | subsector_lower.str.contains("capital goods|industrial|engineering|automation|defence|construction equipment|electrical equipment|cables|bearings|castings|conductors|aerospace", na=False)
            )
            tickers = tickers_for_mask(mask)
            log_kv("Capital Goods universe", tickers=len(tickers))
            return tickers


        def subset_frame(frame, tickers):
            return frame[frame["ticker"].isin(set(tickers))].copy()


        def candidate_summary(label, state, params, extra=None):
            row = {
                "config_label": label,
                "mean_test_ic": state["aggregate"]["mean_test_ic"],
                "mean_train_ic": state["aggregate"]["mean_train_ic"],
                "mean_ratio": state["aggregate"]["mean_ratio"],
                "ic_ir": state["aggregate"]["ic_ir"],
                "ic_tstat": state["aggregate"]["ic_tstat"],
                "sign_stability": state["aggregate"]["sign_stability"],
                "mean_hit_rate": state["aggregate"]["mean_hit_rate"],
                "leak_window_ratio": state["aggregate"]["leak_window_ratio"],
                "nan_window_count": state["aggregate"]["nan_window_count"],
                "n_windows": state["aggregate"]["n_windows"],
                "gate_ic": state["aggregate"]["gate_ic"],
                "gate_ratio": state["aggregate"]["gate_ratio"],
                "verdict_a": state["aggregate"]["verdict_a"],
                "params": params,
            }
            if extra:
                row.update(extra)
            return row


        def standalone_feature_ic(frame, feature_col):
            rows = []
            for _, group in frame.groupby("date", sort=True):
                if feature_col not in group.columns:
                    continue
                rows.append(compute_ic(group[feature_col].to_numpy(), group[TARGET_COL].to_numpy()))
            return float(np.mean(rows)) if rows else 0.0


        def scored_group_ic(scored_df, tickers):
            subset = scored_df[scored_df["ticker"].isin(set(tickers))].copy()
            metrics = compute_window_ic(subset)
            return float(metrics["mean_ic"]), int(subset["date"].nunique()) if not subset.empty else 0


        def rate_regime_breakdown(scored_df):
            if scored_df.empty or "rbi_rate_chg" not in scored_df.columns:
                return []
            rows = []
            for label, mask in [
                ("rate_hiking", scored_df["rbi_rate_chg"] > 0),
                ("rate_cutting", scored_df["rbi_rate_chg"] < 0),
                ("rate_hold", scored_df["rbi_rate_chg"] == 0),
            ]:
                subset = scored_df.loc[mask].copy()
                if subset.empty:
                    rows.append({"rate_env": label, "mean_test_ic": 0.0, "n_dates": 0})
                    continue
                metrics = compute_window_ic(subset)
                rows.append({"rate_env": label, "mean_test_ic": metrics["mean_ic"], "n_dates": int(subset["date"].nunique())})
            return rows


        def resolve_it_anchor_feature(frame):
            for candidate in ["fx_x_export", "fx_x_sens", "stock_x_inrusd", "inrusd_4w_return"]:
                if candidate in frame.columns:
                    return candidate
            return None


        def explain_it_feature_importance(it_frame, feature_cols, params, windows=(5, 10, 15)):
            rows = []
            anchor_feature = resolve_it_anchor_feature(it_frame)
            for window_id in windows:
                split = next((item for item in bundle["splits"] if int(item["window_id"]) == int(window_id)), None)
                if split is None:
                    continue
                split_dates = coerce_split_dates(split)
                train_window = it_frame[it_frame["date"].between(split_dates["train_start"], split_dates["train_end"])].copy()
                test_window = it_frame[it_frame["date"].between(split_dates["test_start"], split_dates["test_end"])].copy()
                if train_window.empty or test_window.empty:
                    continue
                train_window = normalize_cs(train_window, feature_cols)
                test_window = normalize_cs(test_window, feature_cols)
                model = fit_catboost(train_window, feature_cols, params, use_early_stopping=True)
                method = "gain"
                if shap is not None:
                    try:
                        sample = test_window[feature_cols].fillna(0.0).sample(min(300, len(test_window)), random_state=42)
                        explainer = shap.TreeExplainer(model)
                        shap_values = explainer.shap_values(sample)
                        importance = np.abs(shap_values).mean(axis=0)
                        method = "shap"
                    except Exception:
                        importance = np.asarray(model.get_feature_importance(type="FeatureImportance"), dtype=float)
                else:
                    importance = np.asarray(model.get_feature_importance(type="FeatureImportance"), dtype=float)
                ranking = (
                    pd.DataFrame({"feature": feature_cols, "importance": importance})
                    .sort_values("importance", ascending=False, kind="mergesort")
                    .reset_index(drop=True)
                )
                anchor_rows = ranking[ranking["feature"] == anchor_feature]
                anchor_rank = int(anchor_rows.index[0] + 1) if not anchor_rows.empty else None
                anchor_importance = float(anchor_rows["importance"].iloc[0]) if not anchor_rows.empty else None
                rows.append(
                    {
                        "window": int(window_id),
                        "method": method,
                        "anchor_feature": anchor_feature,
                        "anchor_rank": anchor_rank,
                        "anchor_importance": anchor_importance,
                    }
                )
            return rows


        def add_capital_goods_interaction(frame):
            working = frame.copy()
            extra_features = []
            if "order_backlog_growth" in working.columns and "steel_4w_return" in working.columns:
                working["cg_order_x_steel"] = pd.to_numeric(working["order_backlog_growth"], errors="coerce").fillna(0.0) * pd.to_numeric(working["steel_4w_return"], errors="coerce").fillna(0.0)
                extra_features = ["cg_order_x_steel", "steel_4w_return", "copper_4w_return"]
            else:
                working["cg_momentum_x_steel"] = pd.to_numeric(working["eps_sue_decay"], errors="coerce").fillna(0.0) * pd.to_numeric(working["steel_4w_return"], errors="coerce").fillna(0.0)
                extra_features = ["cg_momentum_x_steel", "steel_4w_return", "copper_4w_return"]
            extra_features = [col for col in extra_features if col in working.columns]
            log_kv("Capital Goods interactions", extra_features=extra_features)
            return working, extra_features


        def regime_event_windows():
            reg = bundle["regimes"].copy()
            reg["date"] = pd.to_datetime(reg["date"], errors="coerce").dt.normalize()
            windows = {}
            if "major_event_id" not in reg.columns:
                return windows
            for event_id, group in reg.dropna(subset=["major_event_id"]).groupby(reg["major_event_id"].astype(str), sort=True):
                windows[str(event_id)] = (pd.Timestamp(group["date"].min()).normalize(), pd.Timestamp(group["date"].max()).normalize())
            log_kv("Resolved regime event windows", count=len(windows), ids=sorted(windows))
            return windows


        def resolve_exp17_factors():
            resolved = {}
            for factor in EXP17_FACTORS:
                if factor in FULL_FRAME.columns:
                    resolved[factor] = factor
                    continue
                for alias in EXP17_ALIASES.get(factor, []):
                    if alias in FULL_FRAME.columns:
                        resolved[factor] = alias
                        break
            for candidate in ["fx_x_export", "fx_x_sens", "stock_x_inrusd", "inrusd_4w_return"]:
                if candidate in FULL_FRAME.columns:
                    resolved["fx_anchor"] = candidate
                    break
            log_kv("Resolved EXP-17 factors", count=len(resolved), factors=resolved)
            return resolved


        def build_factor_heatmap(frame, factor_map, event_windows):
            long_rows = []
            event_dates = set()
            for event_id, (start_date, end_date) in event_windows.items():
                subset = frame[frame["date"].between(start_date, end_date)].copy()
                event_dates.update(pd.to_datetime(subset["date"]).dropna().unique().tolist())
                for factor_label, factor_col in factor_map.items():
                    scored = subset[["date", TARGET_COL, factor_col]].rename(columns={factor_col: "pred"})
                    metrics = compute_window_ic(scored)
                    long_rows.append({"factor": factor_label, "column": factor_col, "event_id": event_id, "mean_ic": metrics["mean_ic"]})
            non_crisis = frame[~frame["date"].isin(event_dates)].copy()
            for factor_label, factor_col in factor_map.items():
                scored = non_crisis[["date", TARGET_COL, factor_col]].rename(columns={factor_col: "pred"})
                metrics = compute_window_ic(scored)
                long_rows.append({"factor": factor_label, "column": factor_col, "event_id": "non_crisis", "mean_ic": metrics["mean_ic"]})
            long_df = pd.DataFrame(long_rows)
            wide_df = long_df.pivot(index="factor", columns="event_id", values="mean_ic").reset_index()
            return long_df, wide_df


        def exp17_hypotheses(long_df):
            results = []
            eps_df = long_df[long_df["factor"] == "eps_sue_decay"]
            positive_count = int((eps_df[eps_df["event_id"] != "non_crisis"]["mean_ic"] > 0).sum())
            n_events = int((eps_df["event_id"] != "non_crisis").sum())
            threshold = min(18, n_events) if n_events else 0
            results.append({"hypothesis": "H1", "status": "CONFIRMED" if positive_count >= threshold and threshold > 0 else "INCONCLUSIVE" if n_events == 0 else "REFUTED", "details": f"eps_sue_decay positive in {positive_count}/{n_events} event windows"})
            for hypothesis, factor, event_id, threshold_value in [
                ("H2_E014", "accruals_ratio", "E014", 0.0),
                ("H3_E020", "fx_anchor", "E020", 0.030),
            ]:
                if factor not in long_df["factor"].values or event_id not in long_df["event_id"].values:
                    results.append({"hypothesis": hypothesis, "status": "INCONCLUSIVE", "details": f"{factor} or {event_id} unavailable in dataset"})
                    continue
                value = float(long_df[(long_df["factor"] == factor) & (long_df["event_id"] == event_id)]["mean_ic"].iloc[0])
                if hypothesis == "H2_E014":
                    status = "CONFIRMED" if value < threshold_value else "REFUTED"
                else:
                    status = "CONFIRMED" if value > threshold_value else "REFUTED"
                results.append({"hypothesis": hypothesis, "status": status, "details": f"{factor} @ {event_id} = {value:.4f}"})
            results.append({"hypothesis": "H2_E004", "status": "INCONCLUSIVE", "details": "E004 predates the dataset"})
            results.append({"hypothesis": "H3_E007", "status": "INCONCLUSIVE", "details": "E007 predates the dataset"})
            return results


        def compute_collapse_score(ic_event, ic_normal):
            if abs(ic_normal) < 1e-6:
                return 0.0
            score = 1.0 - (ic_event / ic_normal)
            return float(np.clip(score, 0.0, 1.5))


        def evaluate_custom_window(frame, feature_cols, params, train_start, train_end, test_start, test_end, config_label, exp_root):
            custom_splits = [{
                "window_id": 1,
                "train_start": str(pd.Timestamp(train_start).date()),
                "train_end": str(pd.Timestamp(train_end).date()),
                "test_start": str(pd.Timestamp(test_start).date()),
                "test_end": str(pd.Timestamp(test_end).date()),
            }]
            return run_single_config(
                frame=frame,
                feature_cols=feature_cols,
                splits=custom_splits,
                params=params,
                config_label=config_label,
                exp_root=exp_root,
                max_splits=1,
                use_early_stopping=True,
            )


        def run_exp13_v4():
            exp_slug = "exp13_v4"
            exp_root = experiment_dir(exp_slug)
            universes = finance_universes()
            fs_tickers = universes["full_fs"]
            if "rbi_rate_chg" not in FULL_FRAME.columns:
                raise RuntimeError("rbi_rate_chg must be present for EXP-13 v4.")
            sector_frame = subset_frame(FULL_FRAME, fs_tickers)
            sector_state = run_single_config(sector_frame, BASE_FEATURE_COLS, bundle["splits"], BASE_PARAMS, "fs_sector_only", exp_root, max_splits=MAX_SPLITS)
            universal_state = run_single_config(
                FULL_FRAME,
                BASE_FEATURE_COLS,
                bundle["splits"],
                BASE_PARAMS,
                "universal_on_fs",
                exp_root,
                max_splits=MAX_SPLITS,
                fit_frame=FULL_FRAME,
                train_eval_tickers=fs_tickers,
                test_eval_tickers=fs_tickers,
            )
            subuniverse_rows = []
            for label in ["lenders", "banks", "nbfcs", "insurance", "other_financials"]:
                tickers = universes[label]
                if len(tickers) < 20:
                    subuniverse_rows.append({"sub_universe": label, "status": "SKIPPED", "ticker_count": len(tickers)})
                    continue
                sub_frame = subset_frame(FULL_FRAME, tickers)
                state = run_single_config(sub_frame, BASE_FEATURE_COLS, bundle["splits"], BASE_PARAMS, f"{label}_sector_only", exp_root, max_splits=MAX_SPLITS)
                subuniverse_rows.append({"sub_universe": label, "status": "RUN", "ticker_count": len(tickers), "mean_test_ic": state["aggregate"]["mean_test_ic"], "mean_ratio": state["aggregate"]["mean_ratio"]})
            rate_breakdown = rate_regime_breakdown(sector_state["scored_tests"])
            payload = {
                "exp_slug": exp_slug,
                "sector_ticker_count": len(fs_tickers),
                "sector_only": candidate_summary("fs_sector_only", sector_state, BASE_PARAMS, {"model_type": "sector_only"}),
                "universal_on_fs": candidate_summary("universal_on_fs", universal_state, BASE_PARAMS, {"model_type": "full_universe_fit_fs_subset_eval_aligned"}),
                "rate_regime_breakdown": rate_breakdown,
                "sub_universes": subuniverse_rows,
                "pass_sector_ic": bool(sector_state["aggregate"]["mean_test_ic"] > 0.025),
                "pass_vs_universal": bool(sector_state["aggregate"]["mean_test_ic"] > universal_state["aggregate"]["mean_test_ic"]),
            }
            write_json(exp_root / "exp13_v4_summary.json", payload)
            write_table(exp_root / "exp13_v4_subuniverses.csv", pd.DataFrame(subuniverse_rows))
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp14_v4():
            exp_slug = "exp14_v4"
            exp_root = experiment_dir(exp_slug)
            tickers = it_universe()
            anchor_feature = resolve_it_anchor_feature(FULL_FRAME)
            if anchor_feature is None:
                raise RuntimeError("An FX anchor feature must be present for EXP-14 v4.")
            it_frame = subset_frame(FULL_FRAME, tickers)
            sector_state = run_single_config(it_frame, BASE_FEATURE_COLS, bundle["splits"], BASE_PARAMS, "it_sector_only", exp_root, max_splits=MAX_SPLITS)
            standalone_ic = standalone_feature_ic(it_frame, anchor_feature)
            offshore = [ticker for ticker in OFFSHORE_IT if ticker in tickers]
            domestic = [ticker for ticker in DOMESTIC_IT if ticker in tickers]
            offshore_ic, offshore_dates = scored_group_ic(sector_state["scored_tests"], offshore)
            domestic_ic, domestic_dates = scored_group_ic(sector_state["scored_tests"], domestic)
            importance_rows = explain_it_feature_importance(it_frame, BASE_FEATURE_COLS, BASE_PARAMS)
            payload = {
                "exp_slug": exp_slug,
                "ticker_count": len(tickers),
                "fx_anchor_feature": anchor_feature,
                "standalone_inr_ic": standalone_ic,
                "sector_only": candidate_summary("it_sector_only", sector_state, BASE_PARAMS),
                "offshore_group": {"tickers": offshore, "mean_test_ic": offshore_ic, "n_dates": offshore_dates},
                "domestic_group": {"tickers": domestic, "mean_test_ic": domestic_ic, "n_dates": domestic_dates},
                "importance_checks": importance_rows,
                "pass_ic": bool(sector_state["aggregate"]["mean_test_ic"] > 0.030),
                "pass_directional_offshore": bool(offshore_ic > domestic_ic),
                "pass_inr_top5": bool(any((row.get("anchor_rank") or 999) <= 5 for row in importance_rows)),
            }
            write_json(exp_root / "exp14_v4_summary.json", payload)
            write_table(exp_root / "exp14_v4_importance_checks.csv", pd.DataFrame(importance_rows))
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp15_v4():
            exp_slug = "exp15_v4"
            exp_root = experiment_dir(exp_slug)
            tickers = capital_goods_universe()
            cg_frame = subset_frame(FULL_FRAME, tickers)
            base_state = run_single_config(cg_frame, BASE_FEATURE_COLS, bundle["splits"], BASE_PARAMS, "capital_goods_base", exp_root, max_splits=MAX_SPLITS)
            augmented_frame, extra_features = add_capital_goods_interaction(cg_frame)
            augmented_features = dedupe(BASE_FEATURE_COLS + [col for col in extra_features if col not in BASE_FEATURE_COLS])
            interaction_state = run_single_config(augmented_frame, augmented_features, bundle["splits"], BASE_PARAMS, "capital_goods_interaction", exp_root, max_splits=MAX_SPLITS)
            universal_state = run_single_config(
                FULL_FRAME,
                BASE_FEATURE_COLS,
                bundle["splits"],
                BASE_PARAMS,
                "universal_on_cg",
                exp_root,
                max_splits=MAX_SPLITS,
                fit_frame=FULL_FRAME,
                train_eval_tickers=tickers,
                test_eval_tickers=tickers,
            )
            payload = {
                "exp_slug": exp_slug,
                "ticker_count": len(tickers),
                "base_model": candidate_summary("capital_goods_base", base_state, BASE_PARAMS),
                "interaction_model": candidate_summary("capital_goods_interaction", interaction_state, BASE_PARAMS, {"extra_features": extra_features}),
                "universal_on_cg": candidate_summary("universal_on_cg", universal_state, BASE_PARAMS),
                "pass_interaction": bool(interaction_state["aggregate"]["mean_test_ic"] > base_state["aggregate"]["mean_test_ic"] and interaction_state["aggregate"]["mean_test_ic"] > 0.025),
            }
            write_json(exp_root / "exp15_v4_summary.json", payload)
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp16_v4():
            exp_slug = "exp16_v4"
            exp_root = experiment_dir(exp_slug)
            blend_tickers = sorted(set(finance_universes()["full_fs"]) | set(it_universe()) | set(capital_goods_universe()))
            blend_frame = subset_frame(FULL_FRAME, blend_tickers)
            blend_frame = blend_frame.copy()
            blend_frame["sector_id"] = blend_frame["sector"].astype("category").cat.codes.astype(int)
            blend_features = dedupe(BASE_FEATURE_COLS + ["sector_id"])
            selected_splits = [split for split in bundle["splits"] if 8 <= int(split["window_id"]) <= 15]
            base_state = run_single_config(blend_frame, BASE_FEATURE_COLS, selected_splits, BASE_PARAMS, "blend_without_sector_id", exp_root, max_splits=MAX_SPLITS)
            blend_state = run_single_config(blend_frame, blend_features, selected_splits, BASE_PARAMS, "blend_with_sector_id", exp_root, max_splits=MAX_SPLITS, cat_feature_names=["sector_id"])
            payload = {
                "exp_slug": exp_slug,
                "ticker_count": len(blend_tickers),
                "windows_tested": [int(split["window_id"]) for split in selected_splits],
                "baseline_without_sector_id": candidate_summary("blend_without_sector_id", base_state, BASE_PARAMS),
                "blend_with_sector_id": candidate_summary("blend_with_sector_id", blend_state, BASE_PARAMS),
                "exp07_baseline_ic": EXP07_BASELINE_IC,
                "improvement_vs_exp07": float(blend_state["aggregate"]["mean_test_ic"] - EXP07_BASELINE_IC),
            }
            write_json(exp_root / "exp16_v4_summary.json", payload)
            RESULT_CACHE[exp_slug] = payload
            return payload


        def run_exp17_v4():
            exp_slug = "exp17_v4"
            exp_root = experiment_dir(exp_slug)
            factor_map = resolve_exp17_factors()
            event_windows = regime_event_windows()
            long_df, wide_df = build_factor_heatmap(FULL_FRAME, factor_map, event_windows)
            hypotheses = exp17_hypotheses(long_df)
            write_table(exp_root / "exp17_factor_regime_ic_heatmap.csv", wide_df)
            write_json(exp_root / "exp17_factor_regime_ic_heatmap.json", long_df.to_dict(orient="records"))
            write_json(exp_root / "exp17_hypotheses.json", hypotheses)
            payload = {
                "exp_slug": exp_slug,
                "resolved_factors": factor_map,
                "event_windows": {key: [str(value[0].date()), str(value[1].date())] for key, value in event_windows.items()},
                "hypotheses": hypotheses,
            }
            write_json(exp_root / "exp17_v4_summary.json", payload)
            RESULT_CACHE[exp_slug] = {
                **payload,
                "long_df": long_df,
                "wide_df": wide_df,
            }
            return RESULT_CACHE[exp_slug]


        def run_exp18_v4():
            exp_slug = "exp18_v4"
            exp_root = experiment_dir(exp_slug)
            exp17_state = RESULT_CACHE.get("exp17_v4")
            if exp17_state is None:
                exp17_state = run_exp17_v4()
            event_windows = regime_event_windows()
            collapse_events = dict(EXP18_FALLBACK_EVENTS)
            for event_id, window in event_windows.items():
                collapse_events[event_id] = (str(window[0].date()), str(window[1].date()))
            long_df = exp17_state["long_df"]
            rows = []
            for event_name, (start_text, end_text) in collapse_events.items():
                start = pd.Timestamp(start_text).normalize()
                end = pd.Timestamp(end_text).normalize()
                event_df = FULL_FRAME[FULL_FRAME["date"].between(start, end)].copy()
                if len(event_df) < 50:
                    rows.append({"event_name": event_name, "status": "UNTESTABLE", "reason": "predates dataset or too few rows"})
                    continue
                event_duration = max(int(event_df["date"].nunique()), 1)
                normal_end = start - pd.Timedelta(days=7)
                normal_start = normal_end - pd.Timedelta(weeks=event_duration - 1)
                train_end = normal_start - pd.Timedelta(days=7)
                train_start = train_end - pd.DateOffset(years=1)
                if len(FULL_FRAME[FULL_FRAME["date"].between(train_start, train_end)]) < 500:
                    rows.append({"event_name": event_name, "status": "UNTESTABLE", "reason": "insufficient pre-event training data"})
                    continue
                event_factor_rows = long_df[(long_df["event_id"] == event_name) & (long_df["mean_ic"] > 0.010)]
                regime_features = [exp17_state["resolved_factors"].get(factor, factor) for factor in event_factor_rows["factor"].tolist()]
                regime_features = [feature for feature in dedupe(regime_features) if feature in BASE_FEATURE_COLS]
                if not regime_features:
                    regime_features = [col for col in BASE_FEATURE_COLS if col in ["eps_sue_decay", "rev_sue_decay", "agreement_score", "agreement_score_cs_z", "accruals_ratio", "accruals_ratio_cs_z"]]
                universal_normal = evaluate_custom_window(FULL_FRAME, BASE_FEATURE_COLS, BASE_PARAMS, train_start, train_end, normal_start, normal_end, f"{event_name}_universal_normal", exp_root)
                universal_event = evaluate_custom_window(FULL_FRAME, BASE_FEATURE_COLS, BASE_PARAMS, train_start, train_end, start, end, f"{event_name}_universal_event", exp_root)
                regime_normal = evaluate_custom_window(FULL_FRAME, regime_features, BASE_PARAMS, train_start, train_end, normal_start, normal_end, f"{event_name}_regime_normal", exp_root)
                regime_event = evaluate_custom_window(FULL_FRAME, regime_features, BASE_PARAMS, train_start, train_end, start, end, f"{event_name}_regime_event", exp_root)
                row = {
                    "event_name": event_name,
                    "status": "RUN",
                    "universal_event_ic": universal_event["aggregate"]["mean_test_ic"],
                    "universal_normal_ic": universal_normal["aggregate"]["mean_test_ic"],
                    "regime_event_ic": regime_event["aggregate"]["mean_test_ic"],
                    "regime_normal_ic": regime_normal["aggregate"]["mean_test_ic"],
                    "collapse_score_universal": compute_collapse_score(universal_event["aggregate"]["mean_test_ic"], universal_normal["aggregate"]["mean_test_ic"]),
                    "collapse_score_regime": compute_collapse_score(regime_event["aggregate"]["mean_test_ic"], regime_normal["aggregate"]["mean_test_ic"]),
                    "regime_features": regime_features,
                }
                row["collapse_score"] = max(row["collapse_score_universal"], row["collapse_score_regime"])
                rows.append(row)
            table = pd.DataFrame(rows)
            valid = table[table["status"] == "RUN"].copy()
            mean_collapse = float(valid["collapse_score"].mean()) if not valid.empty else 0.0
            payload = {
                "exp_slug": exp_slug,
                "mean_collapse_score": mean_collapse,
                "gate_pass": bool(mean_collapse > 0.40),
                "tested_events": int(len(valid)),
                "skipped_events": int(len(table) - len(valid)),
            }
            write_table(exp_root / "exp18_event_collapse_table.csv", table)
            write_json(exp_root / "exp18_v4_summary.json", payload)
            RESULT_CACHE[exp_slug] = payload
            return payload


        RUNNERS = {
            "EXP-13": run_exp13_v4,
            "EXP-14": run_exp14_v4,
            "EXP-15": run_exp15_v4,
            "EXP-16": run_exp16_v4,
            "EXP-17": run_exp17_v4,
            "EXP-18": run_exp18_v4,
        }

        run_order = ["EXP-13", "EXP-14", "EXP-15", "EXP-16", "EXP-17", "EXP-18"]
        if RUN_FULL_CHAIN:
            selected_order = run_order[: run_order.index(SELECTED_EXP) + 1]
        else:
            selected_order = [SELECTED_EXP]

        EXECUTION_RESULTS = {}
        for exp_id in selected_order:
            log_kv("Dispatching experiment", exp_id=exp_id, run_full_chain=RUN_FULL_CHAIN)
            EXECUTION_RESULTS[exp_id] = RUNNERS[exp_id]()
            display(Markdown(f"### {exp_id} complete"))

        EXECUTION_RESULTS[SELECTED_EXP]
        """
    ),
    _md("## Output Files"),
    _code(
        """
        existing = sorted(str(path) for path in OUTPUT_BASE.glob("northstar_exp*_v4_*"))
        log_kv("Output inventory", count=len(existing))
        pd.DataFrame({"experiment_dirs": existing})
        """
    ),
]


def main() -> None:
    ratio_repo = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign_rerun_v4_20260406.ipynb"
    ratio_downloads = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign_rerun_v4_20260406.ipynb"
    sector_repo = NOTEBOOK_DIR / "northstar_exp13_18_sector_regime_rerun_v4_20260406.ipynb"
    sector_downloads = DOWNLOADS_DIR / "northstar_exp13_18_sector_regime_rerun_v4_20260406.ipynb"

    _write_notebook(ratio_repo, RATIO_V2_NOTEBOOK)
    _write_notebook(ratio_downloads, RATIO_V2_NOTEBOOK)
    _write_notebook(sector_repo, SECTOR_V2_NOTEBOOK)
    _write_notebook(sector_downloads, SECTOR_V2_NOTEBOOK)

    print("Created:")
    print(ratio_repo)
    print(ratio_downloads)
    print(sector_repo)
    print(sector_downloads)


if __name__ == "__main__":
    main()
