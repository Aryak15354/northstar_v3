#!/usr/bin/env python3
"""
Institutional hardening utilities for Northstar V3.

This module centralizes allocator-grade governance checks:
- dataset lineage + reproducibility fingerprints
- parameter/version locking metadata
- calendar/time alignment audits
- drift monitoring
- independent NAV reconciliation
- snapshot hash integrity checks
- automatic freeze-state decisions
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        if isinstance(v, str) and not v.strip():
            return default
        x = float(v)
        if np.isfinite(x):
            return float(x)
        return default
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        obj = json.loads(path.read_text())
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(payload)
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, default=str))


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _hash_many(paths: Iterable[Path], project_root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted({str(x) for x in paths}):
        fp = Path(p)
        if not fp.exists() or not fp.is_file():
            continue
        rel = fp.resolve().relative_to(project_root.resolve()) if fp.is_absolute() else fp
        digest = sha256_file(fp)
        h.update(str(rel).encode("utf-8"))
        h.update(digest.encode("utf-8"))
    return h.hexdigest()


def _scope_universe_manager_to_project(um: Any, project_root: Path) -> Any:
    try:
        for k, v in list(getattr(um, "paths", {}).items()):
            p = Path(str(v))
            if not p.is_absolute():
                um.paths[k] = str((project_root / p).resolve())
    except Exception:
        pass
    return um


def _git_commit(project_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out
    except Exception:
        return "unknown"


def _file_meta(path: Path, project_root: Path) -> Dict[str, Any]:
    exists = path.exists()
    rel = str(path.resolve().relative_to(project_root.resolve())) if path.is_absolute() else str(path)
    out: Dict[str, Any] = {
        "path": rel,
        "exists": bool(exists),
        "sha256": "",
        "size_bytes": 0,
        "modified_at": None,
    }
    if not exists or not path.is_file():
        return out
    try:
        stat = path.stat()
        out["sha256"] = sha256_file(path)
        out["size_bytes"] = int(stat.st_size)
        out["modified_at"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    except Exception:
        pass
    return out


def build_parameter_version(project_root: Path) -> Dict[str, Any]:
    config_dir = project_root / "config"
    config_files: List[Path] = []
    if config_dir.exists():
        config_files.extend(config_dir.rglob("*.yaml"))
        config_files.extend(config_dir.rglob("*.yml"))
        config_files.extend(config_dir.rglob("*.json"))

    key_code_files = [
        project_root / "run.py",
        project_root / "src/intelligence/capital_allocator.py",
        project_root / "src/portfolio/portfolio_governor.py",
        project_root / "scripts/runners/refresh_v3_artifacts.py",
        project_root / "scripts/run_complete_v3_system.py",
    ]

    config_hash = _hash_many(config_files, project_root=project_root)
    code_hash = _hash_many([p for p in key_code_files if p.exists()], project_root=project_root)
    version_id = hashlib.sha256(f"{config_hash}:{code_hash}".encode("utf-8")).hexdigest()[:16]

    return {
        "timestamp": _utc_now_iso(),
        "version_id": version_id,
        "git_commit": _git_commit(project_root),
        "config_hash": config_hash,
        "code_hash": code_hash,
        "config_file_count": len([p for p in config_files if p.exists()]),
        "key_code_files": [str(p.relative_to(project_root)) for p in key_code_files if p.exists()],
        "python_version": platform.python_version(),
    }


def build_dataset_lineage(project_root: Path) -> Dict[str, Any]:
    key_inputs = [
        project_root / "data/processed/prices.parquet",
        project_root / "data/processed/technicals.parquet",
        project_root / "data/processed/market_state.parquet",
        project_root / "data/processed/intelligent_market_state.parquet",
        project_root / "data/processed/cohesive_alpha_feed.parquet",
        project_root / "data/processed/regime_intelligence_feed.json",
        project_root / "data/processed/capital_allocations.json",
        project_root / "data/processed/portfolio_weights.parquet",
        project_root / "data/portfolio/pnl_on_paper.parquet",
        project_root / "data/processed/shadow_pnl_series.parquet",
        project_root / "data/processed/portfolio_analytics.json",
        project_root / "data/processed/market_tensor.parquet",
    ]
    files = [_file_meta(p, project_root) for p in key_inputs]
    combined_hash = hashlib.sha256(
        "|".join(f"{f['path']}:{f['sha256']}" for f in files if f.get("sha256")).encode("utf-8")
    ).hexdigest()
    return {
        "timestamp": _utc_now_iso(),
        "git_commit": _git_commit(project_root),
        "files": files,
        "combined_hash": combined_hash,
    }


def build_feature_lineage_map() -> Dict[str, Any]:
    lineage = {
        "cohesive_alpha_score": {
            "sources": [
                "data/processed/scores.parquet:northstar_score/final_score",
                "data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet:signal_composite_*",
            ],
            "transform": "Cross-sectional blend with macro-conditioned overlay",
            "lookback": "Daily market snapshot + macro state",
        },
        "allowed_exposure": {
            "sources": [
                "data/processed/intelligent_market_state.parquet:allowed_exposure",
                "data/processed/market_state.parquet:allowed_exposure (fallback)",
            ],
            "transform": "Canonical intelligent-state authority with bounded [0,1] normalization",
            "lookback": "Latest state row",
        },
        "regime_transition_probability": {
            "sources": [
                "data/processed/regime_transitions.parquet",
                "data/processed/regime_intelligence_feed.json",
            ],
            "transform": "Smoothed Markov transition + stability/duration calibration with saturation cap",
            "lookback": "Rolling regime history",
        },
        "market_pulse_intensity": {
            "sources": [
                "data/processed/market_tensor.parquet",
                "data/processed/pulse_state.json",
            ],
            "transform": "Robust scaled force aggregation with bounded normalization",
            "lookback": "Recent daily market-state windows",
        },
        "portfolio_nav": {
            "sources": [
                "data/portfolio/weekly/*.parquet",
                "data/processed/prices.parquet",
                "data/portfolio/pnl_on_paper.parquet",
                "data/processed/shadow_pnl_series.parquet",
            ],
            "transform": "Daily compounding from prior-day weights and realized returns",
            "lookback": "Full available portfolio history",
        },
    }
    return {"timestamp": _utc_now_iso(), "features": lineage}


def _latest_weekly_summary(project_root: Path) -> Optional[Path]:
    base = project_root / "data/weekly_insights"
    if not base.exists():
        return None
    best_path: Optional[Path] = None
    best_date: Optional[pd.Timestamp] = None

    for p in base.glob("*/summary.parquet"):
        candidate_date: Optional[pd.Timestamp] = None
        try:
            sdf = pd.read_parquet(p, columns=["date"])
            s = pd.to_datetime(sdf["date"], errors="coerce").dropna()
            if not s.empty:
                candidate_date = pd.Timestamp(s.max())
        except Exception:
            candidate_date = None

        if candidate_date is None:
            try:
                candidate_date = pd.Timestamp(datetime.fromtimestamp(p.stat().st_mtime, timezone.utc))
            except Exception:
                continue

        if best_date is None or candidate_date > best_date:
            best_date = candidate_date
            best_path = p

    return best_path


def _series_from_frame(df: pd.DataFrame, date_col: str) -> pd.Series:
    s = pd.to_datetime(df[date_col], errors="coerce")
    return s.dropna().sort_values().reset_index(drop=True)


def audit_calendar_consistency(project_root: Path) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def _add_check(name: str, status: str, details: Dict[str, Any]) -> None:
        checks.append({"name": name, "status": status, "details": details})

    today_utc = datetime.now(timezone.utc).date()

    # Prices cadence check
    prices_path = project_root / "data/processed/prices.parquet"
    if prices_path.exists():
        try:
            pdf = pd.read_parquet(prices_path, columns=["Date"])
            ds = _series_from_frame(pdf, "Date")
            monotonic = bool(ds.is_monotonic_increasing)
            dupes = int(ds.duplicated().sum())
            latest = ds.max().date() if not ds.empty else None
            future = bool(latest is not None and latest > today_utc)
            status = "pass" if monotonic and not future else "warn"
            _add_check(
                "prices_calendar",
                status,
                {
                    "rows": int(len(ds)),
                    "duplicates": dupes,
                    "latest_date": str(latest) if latest else None,
                    "future_date_detected": future,
                },
            )
        except Exception as e:
            _add_check("prices_calendar", "fail", {"error": str(e)})
    else:
        _add_check("prices_calendar", "warn", {"missing": str(prices_path.relative_to(project_root))})

    # Market-state cadence check
    market_state_path = project_root / "data/processed/market_state.parquet"
    if market_state_path.exists():
        try:
            mdf = pd.read_parquet(market_state_path)
            dcol = "date" if "date" in mdf.columns else ("Date" if "Date" in mdf.columns else None)
            if dcol is None:
                _add_check("market_state_calendar", "fail", {"error": "missing date column"})
            else:
                ds = _series_from_frame(mdf, dcol)
                monotonic = bool(ds.is_monotonic_increasing)
                latest = ds.max().date() if not ds.empty else None
                _add_check(
                    "market_state_calendar",
                    "pass" if monotonic else "warn",
                    {"rows": int(len(ds)), "latest_date": str(latest) if latest else None},
                )
        except Exception as e:
            _add_check("market_state_calendar", "fail", {"error": str(e)})
    else:
        _add_check("market_state_calendar", "warn", {"missing": str(market_state_path.relative_to(project_root))})

    # Weekly relationships vs tensor lag check
    tensor_path = project_root / "data/processed/market_tensor.parquet"
    weekly_summary_path = _latest_weekly_summary(project_root)
    if tensor_path.exists() and weekly_summary_path and weekly_summary_path.exists():
        try:
            tdf = pd.read_parquet(tensor_path)
            tcol = "date" if "date" in tdf.columns else ("Date" if "Date" in tdf.columns else None)
            wdf = pd.read_parquet(weekly_summary_path, columns=["date"])
            if tcol is None:
                _add_check(
                    "tensor_weekly_alignment",
                    "warn",
                    {"warning": "market_tensor missing date column", "columns": list(tdf.columns[:25])},
                )
            else:
                t_latest = pd.to_datetime(tdf[tcol], errors="coerce").dropna().max()
                w_latest = pd.to_datetime(wdf["date"], errors="coerce").dropna().max()
                lag_days = int((t_latest.normalize() - w_latest.normalize()).days) if pd.notna(t_latest) and pd.notna(w_latest) else None
                status = "pass"
                if lag_days is None:
                    status = "warn"
                elif lag_days < 0 or lag_days > 10:
                    status = "warn"
                _add_check(
                    "tensor_weekly_alignment",
                    status,
                    {
                        "tensor_latest_date": str(t_latest.date()) if pd.notna(t_latest) else None,
                        "weekly_latest_date": str(w_latest.date()) if pd.notna(w_latest) else None,
                        "lag_days": lag_days,
                        "weekly_summary_file": str(weekly_summary_path.relative_to(project_root)),
                    },
                )
        except Exception as e:
            _add_check("tensor_weekly_alignment", "fail", {"error": str(e)})
    else:
        _add_check(
            "tensor_weekly_alignment",
            "warn",
            {
                "tensor_exists": tensor_path.exists(),
                "weekly_summary_exists": bool(weekly_summary_path and weekly_summary_path.exists()),
            },
        )

    severities = {"pass": 0, "warn": 1, "fail": 2}
    worst = max((severities.get(c["status"], 2) for c in checks), default=0)
    overall = {0: "pass", 1: "warn", 2: "fail"}.get(worst, "fail")
    return {"timestamp": _utc_now_iso(), "overall_status": overall, "checks": checks}


def _relationship_density_stats(project_root: Path) -> Dict[str, Any]:
    summary_path = _latest_weekly_summary(project_root)
    if not summary_path or not summary_path.exists():
        return {"available": False}
    try:
        df = pd.read_parquet(summary_path, columns=["date"])
        if df.empty:
            return {"available": False}
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        cnt = df.groupby(df["date"].dt.normalize()).size().sort_index()
        if len(cnt) < 8:
            return {"available": True, "samples": int(len(cnt)), "status": "insufficient"}
        last = cnt.tail(8)
        base = cnt.iloc[:-8] if len(cnt) > 8 else cnt.tail(16)
        base_mean = float(base.mean()) if len(base) > 0 else float(last.mean())
        last_mean = float(last.mean())
        ratio = float(last_mean / max(base_mean, 1e-9))
        return {
            "available": True,
            "samples": int(len(cnt)),
            "weekly_relationships_recent_mean": last_mean,
            "weekly_relationships_baseline_mean": base_mean,
            "density_ratio": ratio,
        }
    except Exception:
        return {"available": False}


def compute_drift_monitor(project_root: Path) -> Dict[str, Any]:
    drift_flags: List[str] = []
    metrics: Dict[str, Any] = {}

    # Market return drift from NIFTY
    nifty_path = project_root / "data/processed/nifty.parquet"
    if nifty_path.exists():
        try:
            ndf = pd.read_parquet(nifty_path)
            close_col = "close" if "close" in ndf.columns else ("Close" if "Close" in ndf.columns else None)
            if close_col is not None:
                close = pd.to_numeric(ndf[close_col], errors="coerce").dropna()
                ret = close.pct_change().dropna()
                if len(ret) >= 320:
                    recent = ret.tail(60)
                    base = ret.iloc[-312:-60]
                    mean_shift = float(recent.mean() - base.mean())
                    vol_ratio = float(recent.std() / max(base.std(), 1e-9))
                    metrics["nifty_mean_shift"] = mean_shift
                    metrics["nifty_vol_ratio"] = vol_ratio
                    if abs(mean_shift) > 0.003:
                        drift_flags.append("price_mean_shift")
                    if vol_ratio > 1.8 or vol_ratio < 0.55:
                        drift_flags.append("price_vol_shift")
        except Exception:
            pass

    # Regime drift monitor carry-through
    regime_drift = _read_json(project_root / "data/processed/regime_drift_monitor.json")
    last_payload = regime_drift.get("last_payload", {}) if isinstance(regime_drift, dict) else {}
    if isinstance(last_payload, dict):
        severity = str(last_payload.get("severity", "normal")).lower()
        metrics["regime_drift_severity"] = severity
        if severity in {"elevated", "high", "watch"}:
            drift_flags.append(f"regime_drift_{severity}")
        flags = last_payload.get("flags", {})
        if isinstance(flags, dict):
            active = [k for k, v in flags.items() if bool(v)]
            if active:
                metrics["regime_drift_flags"] = active

    # Weekly relationship-density drift
    rel = _relationship_density_stats(project_root)
    metrics["relationship_density"] = rel
    ratio = _safe_float(rel.get("density_ratio"), default=1.0)
    if rel.get("available") and (ratio > 2.5 or ratio < 0.4):
        drift_flags.append("relationship_density_shift")

    severity = "normal"
    if len(drift_flags) >= 3:
        severity = "high"
    elif len(drift_flags) == 2:
        severity = "elevated"
    elif len(drift_flags) == 1:
        severity = "watch"

    return {
        "timestamp": _utc_now_iso(),
        "severity": severity,
        "flags": drift_flags,
        "metrics": metrics,
    }


def _normalize_nav(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="float64")
    date_col = "Date" if "Date" in df.columns else ("date" if "date" in df.columns else None)
    if date_col is None:
        return pd.Series(dtype="float64")
    nav_col = None
    for c in ["Equity", "equity", "portfolio_value", "nav", "NAV"]:
        if c in df.columns:
            nav_col = c
            break
    if nav_col is None:
        return pd.Series(dtype="float64")
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "nav": pd.to_numeric(df[nav_col], errors="coerce"),
        }
    ).dropna()
    if out.empty:
        return pd.Series(dtype="float64")
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    base = float(out["nav"].iloc[0])
    if abs(base) < 1e-12:
        return pd.Series(dtype="float64")
    out["norm_nav"] = out["nav"] / base
    return out.set_index("date")["norm_nav"]


def _recompute_independent_nav(project_root: Path) -> pd.Series:
    prices_path = project_root / "data/processed/prices.parquet"
    weekly_dir = project_root / "data/portfolio/weekly"
    if not prices_path.exists() or not weekly_dir.exists():
        return pd.Series(dtype="float64")

    prices = pd.read_parquet(prices_path, columns=["Date", "ticker", "Close"])
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = prices.dropna(subset=["Date", "ticker", "Close"])
    if prices.empty:
        return pd.Series(dtype="float64")

    price_tbl = (
        prices.sort_values(["Date", "ticker"])
        .pivot(index="Date", columns="ticker", values="Close")
        .sort_index()
        .ffill()
    )
    if price_tbl.empty:
        return pd.Series(dtype="float64")

    snaps = []
    for p in sorted(weekly_dir.glob("*.parquet")):
        try:
            sdf = pd.read_parquet(p)
            if sdf.empty or "ticker" not in sdf.columns:
                continue
            wcol = "weight" if "weight" in sdf.columns else ("final_weight" if "final_weight" in sdf.columns else None)
            if wcol is None:
                continue
            dt = pd.to_datetime(p.stem, errors="coerce")
            if pd.isna(dt):
                continue
            part = pd.DataFrame(
                {
                    "date": dt.normalize(),
                    "ticker": sdf["ticker"].astype(str).values,
                    "weight": pd.to_numeric(sdf[wcol], errors="coerce").fillna(0.0).values,
                }
            )
            part = part.dropna(subset=["ticker", "weight"])
            snaps.append(part)
        except Exception:
            continue
    if not snaps:
        return pd.Series(dtype="float64")

    weekly = pd.concat(snaps, ignore_index=True)
    weekly_pivot = weekly.pivot_table(index="date", columns="ticker", values="weight", fill_value=0.0)
    weight_daily = weekly_pivot.reindex(price_tbl.index, method="ffill").fillna(0.0)

    common = weight_daily.columns.intersection(price_tbl.columns)
    if len(common) == 0:
        return pd.Series(dtype="float64")
    ret_tbl = price_tbl[common].pct_change().fillna(0.0)
    w_prev = weight_daily[common].shift(1).fillna(0.0)
    port_ret = (w_prev * ret_tbl).sum(axis=1)
    nav = (1.0 + port_ret).cumprod()
    nav.name = "norm_nav"
    return nav


def reconcile_nav_ledgers(project_root: Path) -> Dict[str, Any]:
    paper_path = project_root / "data/portfolio/pnl_on_paper.parquet"
    if not paper_path.exists():
        return {
            "timestamp": _utc_now_iso(),
            "status": "no_data",
            "paper_exists": paper_path.exists(),
        }

    try:
        paper = pd.read_parquet(paper_path)
        s_paper = _normalize_nav(paper)
        s_independent = _recompute_independent_nav(project_root)
        if s_paper.empty or s_independent.empty:
            return {"timestamp": _utc_now_iso(), "status": "insufficient_data"}
        common = s_paper.index.intersection(s_independent.index)
        if len(common) == 0:
            return {
                "timestamp": _utc_now_iso(),
                "status": "no_overlap",
                "paper_latest": str(s_paper.index.max().date()),
                "independent_latest": str(s_independent.index.max().date()),
            }
        aligned = pd.DataFrame(
            {"paper": s_paper.loc[common], "independent": s_independent.loc[common]}
        ).dropna()
        if aligned.empty:
            return {"timestamp": _utc_now_iso(), "status": "no_overlap"}
        aligned = aligned.sort_index()
        # Use a recent window so legacy-history rebasing differences do not
        # mask current accounting divergences.
        aligned = aligned.tail(90)
        base_paper = float(aligned["paper"].iloc[0])
        base_independent = float(aligned["independent"].iloc[0])
        if abs(base_paper) < 1e-12 or abs(base_independent) < 1e-12:
            return {"timestamp": _utc_now_iso(), "status": "insufficient_data"}
        aligned["paper_rebased"] = aligned["paper"] / base_paper
        aligned["independent_rebased"] = aligned["independent"] / base_independent
        latest_dt = aligned.index.max()
        paper_nav = float(aligned.loc[latest_dt, "paper_rebased"])
        independent_nav = float(aligned.loc[latest_dt, "independent_rebased"])
        denom = max(1e-12, 0.5 * (abs(paper_nav) + abs(independent_nav)))
        mismatch_bps = float(abs(paper_nav - independent_nav) / denom * 10000.0)
        status = "pass" if mismatch_bps <= 5.0 else ("warn" if mismatch_bps <= 15.0 else "fail")

        # Optional shadow comparison is informational only (different strategy scope in many runs).
        shadow_info: Dict[str, Any] = {}
        shadow_path = project_root / "data/processed/shadow_pnl_series.parquet"
        if shadow_path.exists():
            try:
                shadow = pd.read_parquet(shadow_path)
                s_shadow = _normalize_nav(shadow)
                c2 = s_paper.index.intersection(s_shadow.index)
                if len(c2) > 0:
                    a2 = pd.DataFrame({"paper": s_paper.loc[c2], "shadow": s_shadow.loc[c2]}).dropna()
                    if not a2.empty:
                        dt2 = a2.index.max()
                        p2 = float(a2.loc[dt2, "paper"])
                        s2 = float(a2.loc[dt2, "shadow"])
                        d2 = max(1e-12, 0.5 * (abs(p2) + abs(s2)))
                        shadow_info = {
                            "latest_common_date": str(dt2.date()),
                            "mismatch_bps": float(abs(p2 - s2) / d2 * 10000.0),
                            "common_points": int(len(a2)),
                        }
            except Exception:
                shadow_info = {}

        return {
            "timestamp": _utc_now_iso(),
            "status": status,
            "comparison_basis": "paper_vs_recomputed_weekly_nav",
            "latest_common_date": str(latest_dt.date()),
            "paper_norm_nav": paper_nav,
            "independent_norm_nav": independent_nav,
            "mismatch_bps": mismatch_bps,
            "common_points": int(len(aligned)),
            "shadow_comparison": shadow_info,
        }
    except Exception as e:
        return {"timestamp": _utc_now_iso(), "status": "error", "error": str(e)}


def validate_exposure_cash_contract(project_root: Path) -> Dict[str, Any]:
    analytics = _read_json(project_root / "data/processed/portfolio_analytics.json")
    if not analytics:
        return {"timestamp": _utc_now_iso(), "status": "no_data"}

    summary = analytics.get("portfolio_summary") if isinstance(analytics.get("portfolio_summary"), dict) else {}

    exposure_raw = None
    for key in ["total_exposure", "final_exposure", "allowed_exposure"]:
        if key in summary:
            exposure_raw = summary.get(key)
            break
        if key in analytics:
            exposure_raw = analytics.get(key)
            break

    cash_raw = None
    for key in ["cash", "cash_allocation", "cash_weight"]:
        if key in summary:
            cash_raw = summary.get(key)
            break
        if key in analytics:
            cash_raw = analytics.get(key)
            break

    if exposure_raw is None or cash_raw is None:
        return {
            "timestamp": _utc_now_iso(),
            "status": "insufficient_data",
            "details": {
                "has_exposure": exposure_raw is not None,
                "has_cash": cash_raw is not None,
            },
        }

    exposure = _safe_float(exposure_raw, default=np.nan)
    cash = _safe_float(cash_raw, default=np.nan)
    if not np.isfinite(exposure) or not np.isfinite(cash):
        return {
            "timestamp": _utc_now_iso(),
            "status": "fail",
            "details": {"error": "non_finite_exposure_or_cash", "exposure": exposure_raw, "cash": cash_raw},
        }

    exposure = float(exposure)
    cash = float(cash)
    residual = float(abs((1.0 - exposure) - cash))
    residual_bps = float(residual * 10000.0)
    within_bounds = bool(0.0 <= exposure <= 1.0 and 0.0 <= cash <= 1.0)
    if not within_bounds:
        status = "fail"
    elif residual_bps <= 5.0:
        status = "pass"
    elif residual_bps <= 25.0:
        status = "warn"
    else:
        status = "fail"

    return {
        "timestamp": _utc_now_iso(),
        "status": status,
        "exposure": exposure,
        "cash": cash,
        "implied_cash_from_exposure": float(1.0 - exposure),
        "residual_bps": residual_bps,
        "within_bounds": within_bounds,
    }


def audit_survivorship_bias(project_root: Path) -> Dict[str, Any]:
    prices_path = project_root / "data/processed/prices.parquet"
    if not prices_path.exists():
        return {"timestamp": _utc_now_iso(), "status": "no_data", "missing": str(prices_path.relative_to(project_root))}

    try:
        px = pd.read_parquet(prices_path, columns=["Date", "ticker"])
        px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
        px["ticker"] = px["ticker"].astype(str)
        px = px.dropna(subset=["Date", "ticker"])
        if px.empty:
            return {"timestamp": _utc_now_iso(), "status": "no_data"}

        px = px.sort_values("Date")
        start_dt = pd.Timestamp(px["Date"].min())
        end_dt = pd.Timestamp(px["Date"].max())
        span_years = float((end_dt - start_dt).days / 365.25)
        required_snapshot_start = max(start_dt.normalize(), end_dt.normalize() - pd.Timedelta(days=365 * 5))

        life = px.groupby("ticker").agg(first_date=("Date", "min"), last_date=("Date", "max"), rows=("Date", "size")).reset_index()
        universe_size = int(len(life))

        recent_cutoff = end_dt - pd.Timedelta(days=90)
        active_now = life[life["last_date"] >= recent_cutoff]
        inactive = life[life["last_date"] < recent_cutoff]

        births = life["first_date"].dt.year.value_counts().sort_index()
        deaths_from_prices = life["last_date"].dt.year.value_counts().sort_index()
        yearly_universe = px.groupby(px["Date"].dt.year)["ticker"].nunique().sort_index()
        universe_constant = bool(len(yearly_universe) >= 3 and yearly_universe.nunique() == 1)

        # Integrate official delisting universe governance if available.
        delist_rows = 0
        delist_unique_symbols = 0
        mapping_coverage = None
        snapshot_rows = 0
        snapshot_date_start = None
        snapshot_date_end = None
        try:
            from src.validation.universe_manager import UniverseManager

            um = _scope_universe_manager_to_project(
                UniverseManager(project_root=project_root), project_root=project_root
            )
            del_df = um.create_delisting_database(force_refresh=False)
            if isinstance(del_df, pd.DataFrame) and not del_df.empty:
                delist_rows = int(len(del_df))
                delist_unique_symbols = int(del_df["symbol"].astype(str).nunique()) if "symbol" in del_df.columns else 0
                if "mapped_has_price_history" in del_df.columns:
                    mapping_coverage = float(pd.to_numeric(del_df["mapped_has_price_history"], errors="coerce").fillna(0.0).mean())

            snap_path = project_root / "data/universe/universe_snapshots.parquet"
            snapshot_ok = False
            if snap_path.exists():
                try:
                    sdf = pd.read_parquet(snap_path, columns=["date", "ticker"])
                    if not sdf.empty:
                        sdf["date"] = pd.to_datetime(sdf["date"], errors="coerce")
                        sdf = sdf.dropna(subset=["date", "ticker"])
                        if not sdf.empty:
                            snap_start = pd.Timestamp(sdf["date"].min()).normalize()
                            snap_end = pd.Timestamp(sdf["date"].max()).normalize()
                            snapshot_rows = int(len(sdf))
                            snapshot_date_start = str(snap_start.date())
                            snapshot_date_end = str(snap_end.date())
                            snapshot_ok = bool(
                                snap_start <= required_snapshot_start and snap_end >= end_dt.normalize()
                            )
                except Exception:
                    snapshot_ok = False

            if not snapshot_ok:
                built = um.build_historical_universe_snapshots(
                    start_date=required_snapshot_start.to_pydatetime(),
                    end_date=end_dt.to_pydatetime(),
                    apply_liquidity_filter=False,
                    apply_survivorship_filter=True,
                )
                if isinstance(built, pd.DataFrame) and not built.empty:
                    b = built.copy()
                    b["date"] = pd.to_datetime(b["date"], errors="coerce")
                    b = b.dropna(subset=["date", "ticker"])
                    snapshot_rows = int(len(b))
                    if snapshot_rows > 0:
                        snapshot_date_start = str(pd.Timestamp(b["date"].min()).date())
                        snapshot_date_end = str(pd.Timestamp(b["date"].max()).date())
        except Exception:
            pass

        issues: List[str] = []
        if span_years >= 5.0 and int(len(inactive)) == 0 and delist_rows == 0:
            issues.append("no_inactive_tickers_detected")
        if span_years >= 5.0 and delist_rows == 0:
            issues.append("no_historical_delistings_detected")
        if span_years >= 5.0 and universe_constant:
            issues.append("yearly_universe_size_constant")
        if delist_rows > 0 and mapping_coverage is not None and mapping_coverage < 0.25:
            issues.append("low_delisting_price_mapping_coverage")
        if delist_rows > 0 and snapshot_rows == 0:
            issues.append("missing_historical_universe_snapshots")

        status = "pass"
        if issues:
            status = "warn"
        if len([x for x in issues if x not in {"low_delisting_price_mapping_coverage", "missing_historical_universe_snapshots"}]) >= 2 and span_years >= 8.0:
            status = "fail"
        if delist_rows == 0 and span_years >= 8.0:
            status = "fail"

        return {
            "timestamp": _utc_now_iso(),
            "status": status,
            "coverage": {
                "start_date": str(start_dt.date()),
                "end_date": str(end_dt.date()),
                "span_years": span_years,
                "universe_size": universe_size,
                "active_now_count": int(len(active_now)),
                "inactive_count": int(len(inactive)),
            },
            "official_delistings": {
                "rows": delist_rows,
                "unique_symbols": delist_unique_symbols,
                "mapping_price_history_coverage": mapping_coverage,
            },
            "historical_snapshots": {
                "rows": snapshot_rows,
                "start_date": snapshot_date_start,
                "end_date": snapshot_date_end,
                "required_start_date": str(required_snapshot_start.date()),
            },
            "yearly_universe_count": {str(int(k)): int(v) for k, v in yearly_universe.items()},
            "births_by_year": {str(int(k)): int(v) for k, v in births.items()},
            "deaths_from_prices_by_year": {str(int(k)): int(v) for k, v in deaths_from_prices.items()},
            "issues": issues,
        }
    except Exception as e:
        return {"timestamp": _utc_now_iso(), "status": "error", "error": str(e)}


def evaluate_regime_misclassification_tolerance(project_root: Path, allocator_cls: Any = None) -> Dict[str, Any]:
    """
    Force alternative regime labels and measure allocation sensitivity.
    Lower sensitivity implies better wrong-regime tolerance.
    """
    cwd = os.getcwd()
    try:
        os.chdir(project_root)
    except Exception:
        pass
    try:
        if allocator_cls is None:
            from src.intelligence.capital_allocator import CapitalAllocator

            allocator_cls = CapitalAllocator
        allocator = allocator_cls()

        strategy_data = allocator.load_strategy_performance()
        if not strategy_data:
            return {"timestamp": _utc_now_iso(), "status": "no_data"}

        beliefs = allocator.load_strategy_beliefs()
        regret = allocator.load_strategy_regret()
        tailwinds = allocator.load_strategy_tailwinds()
        fabric_insights = allocator.load_weekly_fabric_insights()
        no_edge_state = allocator.load_no_edge_state()
        edge_health = allocator.load_edge_half_life()
        freeze_state = allocator.load_model_freeze_state()
        base_regime = allocator.load_market_regime()

        if not isinstance(no_edge_state, dict) or not no_edge_state:
            no_edge_state = {"state": "NORMAL", "exposure_cap": 0.8, "reasons": []}
        if not isinstance(base_regime, dict) or not base_regime:
            base_regime = {"macro_regime": "neutral", "risk_on_prob": 0.5}

        def _alloc_for(regime_name: str) -> Dict[str, Any]:
            scenario = dict(base_regime)
            scenario["macro_regime"] = str(regime_name)
            if regime_name == "crisis":
                scenario["risk_on_prob"] = 0.10
            elif regime_name in {"boom", "expansion", "late-expansion"}:
                scenario["risk_on_prob"] = 0.80
            else:
                scenario["risk_on_prob"] = 0.50

            health = allocator.calculate_health_scores(strategy_data, beliefs, regret, scenario, tailwinds)
            health = allocator.apply_weekly_fabric_conditioning(health, fabric_insights)
            alloc = allocator.allocate_capital(
                health,
                dict(no_edge_state),
                edge_health,
                strategy_data=strategy_data,
                freeze_state=freeze_state,
            )
            exposure = float(sum(float(v) for v in alloc.values()))
            return {"regime": regime_name, "allocations": alloc, "exposure": exposure}

        base_name = str(base_regime.get("macro_regime", "neutral")).lower()
        base_case = _alloc_for(base_name)
        base_alloc = base_case["allocations"]
        base_exposure = float(base_case["exposure"])
        if not base_alloc:
            return {"timestamp": _utc_now_iso(), "status": "insufficient_data"}

        forced_regimes = ["crisis", "slowdown", "tightening", "neutral", "late-expansion", "boom"]
        forced_regimes = [r for r in forced_regimes if r != base_name]
        if not forced_regimes:
            forced_regimes = ["crisis", "boom"]

        scenario_results = []
        max_l1 = 0.0
        max_exposure_shift = 0.0
        for regime_name in forced_regimes:
            alt = _alloc_for(regime_name)
            alt_alloc = alt["allocations"]
            alt_exp = float(alt["exposure"])
            keys = sorted(set(base_alloc.keys()) | set(alt_alloc.keys()))
            l1_turnover = 0.5 * sum(abs(float(base_alloc.get(k, 0.0)) - float(alt_alloc.get(k, 0.0))) for k in keys)
            exposure_shift = abs(alt_exp - base_exposure)
            max_l1 = max(max_l1, float(l1_turnover))
            max_exposure_shift = max(max_exposure_shift, float(exposure_shift))
            scenario_results.append(
                {
                    "forced_regime": regime_name,
                    "exposure": alt_exp,
                    "exposure_shift_bps": float(exposure_shift * 10000.0),
                    "allocation_l1_turnover": float(l1_turnover),
                }
            )

        if max_l1 <= 0.25 and max_exposure_shift <= 0.20:
            status = "pass"
        elif max_l1 <= 0.45 and max_exposure_shift <= 0.35:
            status = "warn"
        else:
            status = "fail"

        return {
            "timestamp": _utc_now_iso(),
            "status": status,
            "base_regime": base_name,
            "base_exposure": base_exposure,
            "max_allocation_l1_turnover": float(max_l1),
            "max_exposure_shift_bps": float(max_exposure_shift * 10000.0),
            "scenario_results": scenario_results,
            "freeze_active": bool((freeze_state or {}).get("freeze_active", False)),
        }
    except Exception as e:
        return {"timestamp": _utc_now_iso(), "status": "error", "error": str(e)}
    finally:
        try:
            os.chdir(cwd)
        except Exception:
            pass


def validate_allocator_universe_alignment(project_root: Path) -> Dict[str, Any]:
    """
    Verify current allocator/portfolio outputs only contain symbols valid for the latest universe date.
    """
    try:
        from src.validation.universe_manager import UniverseManager
    except Exception as e:
        return {"timestamp": _utc_now_iso(), "status": "error", "error": f"universe_manager_import_failed: {e}"}

    weights_path = project_root / "data/processed/portfolio_weights.parquet"
    if not weights_path.exists():
        return {"timestamp": _utc_now_iso(), "status": "no_data", "missing": str(weights_path.relative_to(project_root))}

    try:
        wdf = pd.read_parquet(weights_path)
        if wdf.empty:
            return {"timestamp": _utc_now_iso(), "status": "no_data"}

        ticker_col = "ticker" if "ticker" in wdf.columns else ("symbol" if "symbol" in wdf.columns else None)
        if ticker_col is None:
            return {"timestamp": _utc_now_iso(), "status": "fail", "error": "ticker_column_missing"}
        tickers = sorted(set(wdf[ticker_col].astype(str).str.strip().tolist()))

        date_col = "date" if "date" in wdf.columns else ("Date" if "Date" in wdf.columns else None)
        if date_col is not None:
            latest_dt = pd.to_datetime(wdf[date_col], errors="coerce").dropna().max()
        else:
            latest_dt = None
        if pd.isna(latest_dt) or latest_dt is None:
            prices_path = project_root / "data/processed/prices.parquet"
            if prices_path.exists():
                p = pd.read_parquet(prices_path, columns=["Date"])
                latest_dt = pd.to_datetime(p["Date"], errors="coerce").dropna().max()
        if pd.isna(latest_dt) or latest_dt is None:
            latest_dt = pd.Timestamp.utcnow().normalize()

        um = _scope_universe_manager_to_project(
            UniverseManager(project_root=project_root), project_root=project_root
        )
        uni = um.get_universe_at_date(pd.Timestamp(latest_dt).to_pydatetime(), apply_liquidity_filter=False, apply_survivorship_filter=True, verbose=False)
        valid_symbols = set(uni.keys())
        tradeable_symbols = {k for k, v in uni.items() if bool(v.get("tradeable", False))}

        off_universe = sorted([t for t in tickers if t not in valid_symbols])
        non_tradeable = sorted([t for t in tickers if t in valid_symbols and t not in tradeable_symbols])

        if len(off_universe) == 0 and len(non_tradeable) == 0:
            status = "pass"
        elif len(off_universe) <= 1 and len(non_tradeable) <= 2:
            status = "warn"
        else:
            status = "fail"

        return {
            "timestamp": _utc_now_iso(),
            "status": status,
            "latest_date": str(pd.Timestamp(latest_dt).date()),
            "portfolio_symbol_count": int(len(tickers)),
            "universe_symbol_count": int(len(valid_symbols)),
            "off_universe_count": int(len(off_universe)),
            "non_tradeable_count": int(len(non_tradeable)),
            "off_universe_symbols": off_universe[:50],
            "non_tradeable_symbols": non_tradeable[:50],
        }
    except Exception as e:
        return {"timestamp": _utc_now_iso(), "status": "error", "error": str(e)}


def snapshot_integrity(project_root: Path) -> Dict[str, Any]:
    keys = {
        "portfolio_weights": project_root / "data/processed/portfolio_weights.parquet",
        "portfolio_analytics": project_root / "data/processed/portfolio_analytics.json",
        "capital_allocations": project_root / "data/processed/capital_allocations.json",
        "regime_feed": project_root / "data/processed/regime_intelligence_feed.json",
        "narrative_feed": project_root / "data/dashboard/narrative_feed.json",
        "integrated_state_snapshot": project_root / "data/integrated/integrated_state_snapshot.parquet",
    }
    snapshots: Dict[str, Any] = {}
    mtimes: List[float] = []
    missing: List[str] = []
    for key, path in keys.items():
        meta = _file_meta(path, project_root=project_root)
        snapshots[key] = meta
        if meta.get("exists"):
            mt = path.stat().st_mtime
            mtimes.append(mt)
        else:
            missing.append(key)

    staleness_seconds = None
    if mtimes:
        staleness_seconds = float(max(mtimes) - min(mtimes))
    status = "pass"
    if missing:
        status = "warn"
    if staleness_seconds is not None and staleness_seconds > 6 * 3600:
        status = "warn"

    # Cross-check hash anchors for dashboard vs core snapshot.
    anchor = {
        "portfolio_hash": snapshots["portfolio_weights"].get("sha256", ""),
        "analytics_hash": snapshots["portfolio_analytics"].get("sha256", ""),
    }
    anchor["combined_anchor_hash"] = hashlib.sha256(
        f"{anchor['portfolio_hash']}:{anchor['analytics_hash']}".encode("utf-8")
    ).hexdigest()

    return {
        "timestamp": _utc_now_iso(),
        "status": status,
        "staleness_seconds": staleness_seconds,
        "missing": missing,
        "snapshot_hashes": snapshots,
        "hash_anchor": anchor,
    }


def audit_real_data_only_policy(project_root: Path) -> Dict[str, Any]:
    scanner = project_root / "scripts/runners/enforce_real_data_only.py"
    if not scanner.exists():
        return {
            "timestamp": _utc_now_iso(),
            "status": "no_scanner",
            "missing": str(scanner.relative_to(project_root)),
        }
    try:
        proc = subprocess.run(
            ["python3", str(scanner)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        return {
            "timestamp": _utc_now_iso(),
            "status": "pass" if proc.returncode == 0 else "fail",
            "returncode": int(proc.returncode),
            "stdout_tail": out.splitlines()[-30:],
            "stderr_tail": err.splitlines()[-30:],
        }
    except Exception as e:
        return {"timestamp": _utc_now_iso(), "status": "error", "error": str(e)}


def _rolling_ic_from_signals(project_root: Path) -> Dict[str, Any]:
    # Lightweight IC proxy: cross-sectional rank corr between score(t) and return(t+1)
    score_path = project_root / "data/processed/cohesive_alpha_feed.parquet"
    prices_path = project_root / "data/processed/prices.parquet"
    if not score_path.exists() or not prices_path.exists():
        return {"available": False}
    try:
        sdf = pd.read_parquet(score_path)
        if "ticker" not in sdf.columns:
            return {"available": False}
        scol = "cohesive_alpha_score" if "cohesive_alpha_score" in sdf.columns else None
        if scol is None:
            for c in ["adjusted_alpha", "northstar_score", "score", "final_score"]:
                if c in sdf.columns:
                    scol = c
                    break
        if scol is None:
            return {"available": False}

        sdf = sdf[["ticker", scol]].copy()
        sdf["ticker"] = sdf["ticker"].astype(str)
        sdf[scol] = pd.to_numeric(sdf[scol], errors="coerce")
        sdf = sdf.dropna(subset=["ticker", scol]).drop_duplicates(subset=["ticker"], keep="last")
        if len(sdf) < 25:
            return {"available": False}

        pdf = pd.read_parquet(prices_path, columns=["Date", "ticker", "Close"])
        pdf["Date"] = pd.to_datetime(pdf["Date"], errors="coerce")
        pdf["Close"] = pd.to_numeric(pdf["Close"], errors="coerce")
        pdf = pdf.dropna(subset=["Date", "ticker", "Close"])
        pdf = pdf.sort_values(["ticker", "Date"])
        pdf["fwd_ret_1d"] = pdf.groupby("ticker")["Close"].shift(-1) / pdf["Close"] - 1.0
        latest_date = pdf["Date"].max()
        x = pdf[pdf["Date"] == latest_date][["ticker", "fwd_ret_1d"]].dropna()
        x["ticker"] = x["ticker"].astype(str)
        merged = sdf.merge(x, on="ticker", how="inner")
        if len(merged) < 25:
            return {"available": False}
        ic = merged[scol].rank(pct=True).corr(merged["fwd_ret_1d"].rank(pct=True), method="spearman")
        if ic is None or not np.isfinite(ic):
            return {"available": False}
        return {"available": True, "ic_proxy_1d": float(ic), "sample_size": int(len(merged))}
    except Exception:
        return {"available": False}


def evaluate_freeze_state(
    project_root: Path,
    drift: Dict[str, Any],
    nav_recon: Dict[str, Any],
) -> Dict[str, Any]:
    triggers: List[str] = []
    actions: Dict[str, Any] = {
        "target_max_exposure": 0.80,
        "risk_aversion_multiplier": 1.00,
        "lock_new_risk": False,
        "require_human_override": False,
    }

    analytics = _read_json(project_root / "data/processed/portfolio_analytics.json")
    max_dd = abs(_safe_float(analytics.get("max_drawdown"), 0.0))
    sharpe = _safe_float(analytics.get("sharpe_ratio"), 0.0)
    if max_dd >= 0.25:
        triggers.append("drawdown_gt_25pct")
    if sharpe < 0.0:
        triggers.append("negative_sharpe")

    drift_sev = str(drift.get("severity", "normal")).lower()
    if drift_sev in {"elevated", "high"}:
        triggers.append(f"drift_{drift_sev}")

    nav_status = str(nav_recon.get("status", "no_data")).lower()
    nav_mismatch = _safe_float(nav_recon.get("mismatch_bps"), 0.0)
    nav_alert = bool(nav_status in {"warn", "fail"} and nav_mismatch > 5.0)
    if nav_status in {"warn", "fail"} and nav_mismatch > 100.0:
        triggers.append("nav_mismatch_gt_100bps")

    ic_proxy = _rolling_ic_from_signals(project_root)
    if ic_proxy.get("available") and _safe_float(ic_proxy.get("ic_proxy_1d"), 0.0) < 0:
        triggers.append("ic_proxy_negative")

    freeze_active = len(triggers) >= 2 or "drawdown_gt_25pct" in triggers or "nav_mismatch_gt_100bps" in triggers
    if freeze_active:
        actions.update(
            {
                "target_max_exposure": 0.15,
                "risk_aversion_multiplier": 1.75,
                "lock_new_risk": True,
                "require_human_override": True,
            }
        )

    return {
        "timestamp": _utc_now_iso(),
        "freeze_active": bool(freeze_active),
        "triggers": triggers,
        "context": {
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "drift_severity": drift_sev,
            "nav_mismatch_bps": nav_mismatch,
            "nav_alert_gt_5bps": nav_alert,
            "ic_proxy": ic_proxy,
        },
        "actions": actions,
    }


@dataclass
class HardeningResult:
    parameter_version: Dict[str, Any]
    dataset_lineage: Dict[str, Any]
    feature_lineage: Dict[str, Any]
    calendar_audit: Dict[str, Any]
    drift_monitor: Dict[str, Any]
    nav_reconciliation: Dict[str, Any]
    exposure_cash_contract: Dict[str, Any]
    survivorship_bias_audit: Dict[str, Any]
    regime_misclassification_tolerance: Dict[str, Any]
    allocator_universe_alignment: Dict[str, Any]
    snapshot_integrity: Dict[str, Any]
    real_data_only_policy: Dict[str, Any]
    freeze_state: Dict[str, Any]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "timestamp": _utc_now_iso(),
            "freeze_active": bool(self.freeze_state.get("freeze_active", False)),
            "drift_severity": self.drift_monitor.get("severity", "unknown"),
            "calendar_status": self.calendar_audit.get("overall_status", "unknown"),
            "nav_reconciliation_status": self.nav_reconciliation.get("status", "unknown"),
            "exposure_cash_contract_status": self.exposure_cash_contract.get("status", "unknown"),
            "survivorship_bias_status": self.survivorship_bias_audit.get("status", "unknown"),
            "regime_tolerance_status": self.regime_misclassification_tolerance.get("status", "unknown"),
            "allocator_universe_alignment_status": self.allocator_universe_alignment.get("status", "unknown"),
            "snapshot_integrity_status": self.snapshot_integrity.get("status", "unknown"),
            "real_data_only_policy_status": self.real_data_only_policy.get("status", "unknown"),
            "parameter_version_id": self.parameter_version.get("version_id", "unknown"),
            "lineage_combined_hash": self.dataset_lineage.get("combined_hash", ""),
        }


def run_institutional_hardening(project_root: Path) -> HardeningResult:
    project_root = project_root.resolve()

    parameter_version = build_parameter_version(project_root)
    dataset_lineage = build_dataset_lineage(project_root)
    feature_lineage = build_feature_lineage_map()
    calendar_audit = audit_calendar_consistency(project_root)
    drift_monitor = compute_drift_monitor(project_root)
    nav_reconciliation = reconcile_nav_ledgers(project_root)
    exposure_cash_contract = validate_exposure_cash_contract(project_root)
    survivorship_bias_audit = audit_survivorship_bias(project_root)
    regime_misclassification_tolerance = evaluate_regime_misclassification_tolerance(project_root)
    allocator_universe_alignment = validate_allocator_universe_alignment(project_root)
    snapshot_integrity_payload = snapshot_integrity(project_root)
    real_data_only_policy = audit_real_data_only_policy(project_root)
    freeze_state = evaluate_freeze_state(project_root, drift=drift_monitor, nav_recon=nav_reconciliation)

    out_dir = project_root / "data/processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "parameter_version.json", parameter_version)
    atomic_write_json(out_dir / "dataset_lineage.json", dataset_lineage)
    atomic_write_json(out_dir / "feature_lineage_map.json", feature_lineage)
    atomic_write_json(out_dir / "calendar_alignment_audit.json", calendar_audit)
    atomic_write_json(out_dir / "drift_monitor.json", drift_monitor)
    atomic_write_json(out_dir / "nav_reconciliation.json", nav_reconciliation)
    atomic_write_json(out_dir / "exposure_cash_contract.json", exposure_cash_contract)
    atomic_write_json(out_dir / "survivorship_bias_audit.json", survivorship_bias_audit)
    atomic_write_json(
        out_dir / "regime_misclassification_tolerance.json",
        regime_misclassification_tolerance,
    )
    atomic_write_json(out_dir / "allocator_universe_alignment.json", allocator_universe_alignment)
    atomic_write_json(out_dir / "snapshot_integrity.json", snapshot_integrity_payload)
    atomic_write_json(out_dir / "real_data_only_policy.json", real_data_only_policy)
    atomic_write_json(out_dir / "model_freeze_state.json", freeze_state)

    return HardeningResult(
        parameter_version=parameter_version,
        dataset_lineage=dataset_lineage,
        feature_lineage=feature_lineage,
        calendar_audit=calendar_audit,
        drift_monitor=drift_monitor,
        nav_reconciliation=nav_reconciliation,
        exposure_cash_contract=exposure_cash_contract,
        survivorship_bias_audit=survivorship_bias_audit,
        regime_misclassification_tolerance=regime_misclassification_tolerance,
        allocator_universe_alignment=allocator_universe_alignment,
        snapshot_integrity=snapshot_integrity_payload,
        real_data_only_policy=real_data_only_policy,
        freeze_state=freeze_state,
    )
