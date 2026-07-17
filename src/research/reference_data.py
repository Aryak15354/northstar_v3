"""Helpers for canonical research reference data and provenance manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.panel_math import normalize_ticker as _normalize_ticker  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_ROOT = PROJECT_ROOT / "data" / "canonical" / "reference"
REFERENCE_RELATIVE_PATHS = {
    "research_inputs_manifest": "research_inputs_manifest.json",
    "major_regime_events": "regimes/nse_regime_events_major.parquet",
    "subtle_regime_periods": "regimes/nse_regime_periods_subtle.parquet",
    "regime_summary": "regimes/nse_regime_summary.parquet",
    "universe_enriched": "universe/nifty500_universe_enriched.parquet",
}




def _looks_like_reference_root(path: Path) -> bool:
    return path.exists() and any((path / rel).exists() for rel in REFERENCE_RELATIVE_PATHS.values())


def _candidate_reference_roots(base_dir: str | Path | None = None, cfg: dict[str, Any] | None = None) -> list[Path]:
    candidates: list[Path] = []
    if cfg is not None:
        reference_cfg = dict(cfg.get("reference") or {})
        for raw in [
            reference_cfg.get("canonical_root"),
            dict(cfg.get("_reference_bundle") or {}).get("reference_root"),
        ]:
            if not raw:
                continue
            path = Path(str(raw)).expanduser()
            if not path.is_absolute():
                path = (PROJECT_ROOT / path).resolve()
            candidates.append(path)
    if base_dir is not None:
        base = Path(base_dir).expanduser().resolve()
        candidates.extend([base, base / "data" / "canonical" / "reference"])
    candidates.append(DEFAULT_REFERENCE_ROOT)
    seen: set[str] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        token = str(resolved)
        if token in seen:
            continue
        seen.add(token)
        ordered.append(resolved)
    return ordered


def resolve_reference_root(
    base_dir: str | Path | None = None,
    *,
    cfg: dict[str, Any] | None = None,
    required: bool = False,
) -> Path | None:
    for candidate in _candidate_reference_roots(base_dir=base_dir, cfg=cfg):
        if _looks_like_reference_root(candidate):
            return candidate
    if required:
        raise FileNotFoundError("canonical_reference_root_not_found")
    return None


def reference_paths(reference_root: str | Path) -> dict[str, Path]:
    root = Path(reference_root).expanduser().resolve()
    return {name: (root / rel).resolve() for name, rel in REFERENCE_RELATIVE_PATHS.items()}


def load_reference_manifest(reference_root: str | Path) -> dict[str, Any]:
    manifest_path = reference_paths(reference_root)["research_inputs_manifest"]
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def summarize_reference_bundle(reference_root: str | Path | None) -> dict[str, Any]:
    if reference_root is None:
        return {
            "status": "missing",
            "reference_root": None,
            "manifest_path": None,
        }

    root = Path(reference_root).expanduser().resolve()
    paths = reference_paths(root)
    manifest = load_reference_manifest(root)
    summary: dict[str, Any] = {
        "status": "ok" if root.exists() else "missing",
        "reference_root": str(root),
        "manifest_path": str(paths["research_inputs_manifest"]) if paths["research_inputs_manifest"].exists() else None,
        "manifest_generated_at": manifest.get("generated_at"),
        "document_sources": sorted((manifest.get("sources") or {}).keys()),
        "documents": dict(manifest.get("documents") or {}),
        "paths": {name: str(path) for name, path in paths.items()},
    }
    for key in ["major_regime_events", "subtle_regime_periods", "regime_summary", "universe_enriched"]:
        path = paths[key]
        if not path.exists():
            summary[f"{key}_rows"] = 0
            continue
        try:
            frame = pd.read_parquet(path)
            summary[f"{key}_rows"] = int(len(frame))
        except Exception:
            summary[f"{key}_rows"] = None
    return summary


def validate_reference_bundle(
    reference_root: str | Path | None,
    *,
    features_df: pd.DataFrame | None = None,
    metadata_df: pd.DataFrame | None = None,
    strict: bool = False,
    expected_universe_size: int = 500,
) -> dict[str, Any]:
    summary = summarize_reference_bundle(reference_root)
    if reference_root is None:
        if strict:
            raise FileNotFoundError("canonical_reference_root_not_found")
        return summary

    root = Path(reference_root).expanduser().resolve()
    paths = reference_paths(root)
    universe_path = paths["universe_enriched"]
    if not universe_path.exists():
        if strict:
            raise FileNotFoundError(f"universe_reference_missing:{universe_path}")
        summary["universe_status"] = "missing"
        return summary

    universe = pd.read_parquet(universe_path)
    universe_ticker_col = "ticker" if "ticker" in universe.columns else "symbol"
    universe_tickers = {
        _normalize_ticker(value)
        for value in universe[universe_ticker_col].tolist()
        if _normalize_ticker(value)
    }
    summary["universe_status"] = "ok"
    summary["universe_ticker_count"] = int(len(universe_tickers))
    summary["universe_rows"] = int(len(universe))
    summary["expected_universe_size"] = int(expected_universe_size)

    if strict and len(universe_tickers) < int(expected_universe_size):
        raise ValueError(
            f"canonical_universe_too_small:{len(universe_tickers)}<{int(expected_universe_size)} at {universe_path}"
        )

    export_tickers: set[str] = set()
    for frame in [features_df, metadata_df]:
        if frame is None or frame.empty or "ticker" not in frame.columns:
            continue
        export_tickers.update(_normalize_ticker(value) for value in frame["ticker"].tolist() if _normalize_ticker(value))

    if export_tickers:
        missing = sorted(export_tickers - universe_tickers)
        summary["export_ticker_count"] = int(len(export_tickers))
        summary["export_missing_from_reference_count"] = int(len(missing))
        summary["export_missing_from_reference_sample"] = missing[:25]
        if strict and missing:
            raise ValueError(
                "export_contains_unknown_tickers:"
                + ",".join(missing[:10])
                + f" (total={len(missing)})"
            )

    return summary


__all__ = [
    "DEFAULT_REFERENCE_ROOT",
    "PROJECT_ROOT",
    "REFERENCE_RELATIVE_PATHS",
    "load_reference_manifest",
    "reference_paths",
    "resolve_reference_root",
    "summarize_reference_bundle",
    "validate_reference_bundle",
]
