#!/usr/bin/env python3
"""
🔄 REFRESH V3 ARTIFACTS (REAL DATA ONLY)

This runner rebuilds/updates the core artifacts that power the V3 dashboard.
It is designed to be called by `run_complete_v3_system.py` so that "freshness"
panels and advanced analytics never go stale.

What it refreshes (in order):
  1) processed prices (data/processed/prices.parquet) from raw csvs
  2) technicals (data/processed/technicals.parquet)
  3) market regime (data/processed/market_regime.parquet)
  4) sector rotation + flows (data/processed/sector_rotation.parquet, sector_flows.parquet)
  5) macro factors (macro score/risk budget) if the scripts exist
  6) intelligent market state (data/processed/intelligent_market_state.parquet)
  7) portfolio snapshot (data/portfolio/weekly/YYYY-MM-DD.parquet) from current weights
  8) PnL-on-paper incremental update (data/portfolio/pnl_on_paper.parquet)
  9) daily narrative parquet (data/processed/daily_narrative.parquet)
 10) regime transitions + intelligence feed (data/processed/regime_transitions.parquet, regime_intelligence_feed.json)
 11) system execution log (data/processed/system_execution_log.json)

No mock/synthetic data is generated; everything is derived from existing real
artifacts or real market data already ingested (yfinance → csv/parquet).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.sentiment.context_loader import load_sentiment_context


@dataclass
class StepResult:
    name: str
    status: str  # success | failed | skipped
    message: str = ""
    duration_seconds: float = 0.0


def _now() -> datetime:
    return datetime.now()


def _as_fraction(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        x = float(v)
    except Exception:
        return None
    # Normalize percent-ish to 0..1 if needed.
    if x > 1.0:
        x = x / 100.0
    return float(x)


def _run_cmd(cmd: list[str], *, timeout: int = 3600) -> tuple[bool, str]:
    """Run a child command with live output + heartbeat.

    Users frequently run this directly; capturing output makes it look "hung".
    We stream stdout/stderr and still return a concise tail for dashboards/logs.
    """
    start = time.time()
    tail: list[str] = []
    max_tail = 200
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        last_heartbeat = time.time()
        last_output = time.time()

        while True:
            if proc.poll() is not None:
                break
            if proc.stdout is not None:
                line = proc.stdout.readline()
                if line:
                    last_output = time.time()
                    line = line.rstrip("\n")
                    if line.strip():
                        print(f"   {line}", flush=True)
                        tail.append(line)
                        if len(tail) > max_tail:
                            tail = tail[-max_tail:]
                    continue

            # Heartbeat if child is quiet (common during yfinance downloads / parquet reads).
            now = time.time()
            if now - last_heartbeat >= 15:
                elapsed = now - start
                quiet = now - last_output
                print(f"   ⏳ Still running... ({elapsed:.0f}s elapsed, {quiet:.0f}s quiet)", flush=True)
                last_heartbeat = now

            if now - start > timeout:
                proc.terminate()
                return False, f"Timed out after {timeout}s"

            time.sleep(0.05)

        rc = proc.wait(timeout=30)
        msg = " | ".join(tail[-12:]).strip()
        if rc == 0:
            return True, msg
        return False, msg or f"Command failed with code {rc}"
    except Exception as e:
        return False, str(e)


def _safe_read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(path)


def _atomic_write_parquet(df: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_parquet(tmp, index=index)
    tmp.replace(path)


def _sentiment_probe(project_root: Path) -> Dict[str, Any]:
    """
    Compact, canonical sentiment probe for execution logs.
    """
    try:
        ctx = load_sentiment_context(
            now=_now(),
            project_root=project_root,
            top_companies_limit=30,
        )
    except Exception:
        return {"available": False, "status": "error"}

    return {
        "available": bool(ctx.get("available", False)),
        "status": str(ctx.get("status", "missing") or "missing"),
        "fresh": bool(ctx.get("fresh", False)),
        "summary_age_minutes": ctx.get("summary_age_minutes"),
        "market_age_minutes": ctx.get("market_age_minutes"),
        "polarity": float(ctx.get("polarity", 0.0) or 0.0),
        "uncertainty": float(ctx.get("uncertainty", 0.0) or 0.0),
        "conviction": float(ctx.get("conviction", 1.0) or 1.0),
        "event_shock_score": float(ctx.get("event_shock_score", 0.0) or 0.0),
        "alert_level": str(ctx.get("alert_level", "normal") or "normal"),
        "dominant_theme": str(ctx.get("dominant_theme", "neutral") or "neutral"),
        "negative_company_count": int(len(ctx.get("negative_trending_companies", []) or [])),
        "event_impact_count": int(len(ctx.get("event_company_impacts", []) or [])),
    }


def _load_latest_intelligent_state(project_root: Path) -> Optional[dict]:
    """Load latest intelligent market-state row as a plain dict."""
    ims_path = project_root / "data/processed/intelligent_market_state.parquet"
    if not ims_path.exists():
        return None
    try:
        ims = pd.read_parquet(ims_path)
        if ims.empty:
            return None
        if "date" in ims.columns:
            ims["date"] = pd.to_datetime(ims["date"], errors="coerce")
            ims = ims.dropna(subset=["date"]).sort_values("date")
        row = ims.iloc[-1].to_dict()
        return row
    except Exception:
        return None


def _normalize_weights_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ticker" not in out.columns and "symbol" in out.columns:
        out["ticker"] = out["symbol"].astype(str).map(
            lambda s: s if str(s).endswith(".NS") else f"{s}.NS"
        )
    if "symbol" not in out.columns and "ticker" in out.columns:
        out["symbol"] = out["ticker"].astype(str).str.replace(".NS", "", regex=False)

    wcol = None
    for c in ["weight", "final_weight", "allocation", "w"]:
        if c in out.columns:
            wcol = c
            break
    if wcol:
        out["weight"] = pd.to_numeric(out[wcol], errors="coerce")
    return out


def _is_meaningful_weights(df: Optional[pd.DataFrame]) -> bool:
    if df is None or df.empty or "weight" not in df.columns:
        return False
    w = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
    n_pos = int((w > 0).sum())
    exposure = float(w.sum())
    return n_pos >= 5 and exposure > 0.01


def _load_best_portfolio_weights(project_root: Path) -> tuple[Optional[pd.DataFrame], str]:
    """
    Load the best available portfolio weights with fallback order:
    canonical -> latest backup -> weekly latest snapshot.
    """
    fallback_df: Optional[pd.DataFrame] = None
    fallback_src = "none"

    # Canonical
    canonical = project_root / "data/processed/portfolio_weights.parquet"
    if canonical.exists():
        try:
            cdf = _normalize_weights_frame(pd.read_parquet(canonical))
            if _is_meaningful_weights(cdf):
                return cdf, "canonical"
            if cdf is not None and not cdf.empty:
                fallback_df, fallback_src = cdf, "canonical_degenerate"
        except Exception:
            pass

    # Backup
    backup_dir = project_root / "data/processed/backups"
    if backup_dir.exists():
        backups = sorted(backup_dir.glob("portfolio_weights_*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
        for bp in backups:
            try:
                bdf = _normalize_weights_frame(pd.read_parquet(bp))
                if _is_meaningful_weights(bdf):
                    return bdf, f"backup:{bp.name}"
                if fallback_df is None and bdf is not None and not bdf.empty:
                    fallback_df, fallback_src = bdf, f"backup_degenerate:{bp.name}"
            except Exception:
                continue

    # Weekly latest pointer
    latest_json = _safe_read_json(project_root / "data/portfolio/weekly/latest.json") or {}
    snap_path = latest_json.get("path")
    if isinstance(snap_path, str) and snap_path:
        sp = Path(snap_path)
        if not sp.is_absolute():
            sp = project_root / sp
        if sp.exists():
            try:
                sdf = _normalize_weights_frame(pd.read_parquet(sp))
                if _is_meaningful_weights(sdf):
                    return sdf, f"weekly:{sp.name}"
                if fallback_df is None and sdf is not None and not sdf.empty:
                    fallback_df, fallback_src = sdf, f"weekly_degenerate:{sp.name}"
            except Exception:
                pass

    return fallback_df, fallback_src


def _latest_date_in_prices_raw(raw_dir: Path, sample: int = 25) -> Optional[pd.Timestamp]:
    if not raw_dir.exists():
        return None
    files = list(raw_dir.glob("*.csv"))
    if not files:
        return None
    # Sample a handful for speed.
    files = files[:sample]
    mx = None
    for f in files:
        try:
            df = pd.read_csv(f, usecols=["Date"])
            if df.empty:
                continue
            d = pd.to_datetime(df["Date"], errors="coerce").max()
            if pd.isna(d):
                continue
            mx = d if mx is None else max(mx, d)
        except Exception:
            continue
    return mx


def _write_daily_narrative(project_root: Path) -> tuple[bool, str]:
    out_path = project_root / "data/processed/daily_narrative.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mr_path = project_root / "data/processed/market_regime.parquet"
    ims_path = project_root / "data/processed/intelligent_market_state.parquet"
    flows_path = project_root / "data/processed/sector_flows.parquet"

    if not mr_path.exists():
        return False, "market_regime.parquet missing"

    mr = pd.read_parquet(mr_path)
    if mr.empty or "Date" not in mr.columns:
        return False, "market_regime.parquet empty or malformed"
    mr["Date"] = pd.to_datetime(mr["Date"], errors="coerce")
    mr = mr.dropna(subset=["Date"]).sort_values("Date")

    latest = mr.iloc[-1]
    market_regime = str(latest.get("market_regime") or "Neutral")
    risk_on = _as_fraction(latest.get("risk_on_score"))

    # Prefer canonical intelligent-state controls for regime/risk.
    ims_latest = _load_latest_intelligent_state(project_root) or {}
    ims_regime = (
        ims_latest.get("regime_ai")
        or ims_latest.get("regime")
        or ims_latest.get("macro_regime")
        or ims_latest.get("market_regime")
    )
    if isinstance(ims_regime, str) and ims_regime.strip():
        market_regime = ims_regime.strip()
    ims_risk_on = _as_fraction(
        ims_latest.get("risk_on_probability", ims_latest.get("risk_on"))
    )
    if ims_risk_on is not None:
        risk_on = ims_risk_on

    # Regime momentum: slope of risk_on_score over the last ~10 trading days.
    regime_momentum = "Stable"
    try:
        tail = mr.tail(15).copy()
        x = np.arange(len(tail))
        y = pd.to_numeric(tail.get("risk_on_score"), errors="coerce").values
        if np.isfinite(y).sum() >= 5:
            slope = np.polyfit(x[np.isfinite(y)], y[np.isfinite(y)], 1)[0]
            if slope > 0.002:
                regime_momentum = "Improving"
            elif slope < -0.002:
                regime_momentum = "Cracking"
    except Exception:
        pass

    allowed_exposure = _as_fraction(ims_latest.get("allowed_exposure"))

    if allowed_exposure is None:
        allowed_exposure = 0.6

    # Sector focus/avoid from sector_flows (if present)
    focus_sectors = ""
    avoid_sectors = ""
    opportunity_state = "Stabilizing"

    if flows_path.exists():
        try:
            flows = pd.read_parquet(flows_path)
            if not flows.empty and "Industry" in flows.columns:
                df = flows.copy()
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    df = df.dropna(subset=["Date"]).sort_values("Date")
                    df = df[df["Date"] == df["Date"].max()]
                score_col = None
                for cand in ["flow_strength", "capital_flow", "relative_performance"]:
                    if cand in df.columns:
                        score_col = cand
                        break
                if score_col:
                    s = pd.to_numeric(df[score_col], errors="coerce")
                    df = df.assign(_score=s).dropna(subset=["_score"])
                    top = df.sort_values("_score", ascending=False)["Industry"].head(3).astype(str).tolist()
                    bot = df.sort_values("_score", ascending=True)["Industry"].head(3).astype(str).tolist()
                    focus_sectors = ", ".join(top)
                    avoid_sectors = ", ".join(bot)
        except Exception:
            pass

    # Opportunity state (simple, transparent rules)
    try:
        if risk_on is not None and risk_on >= 0.6 and allowed_exposure >= 0.6:
            opportunity_state = "Expanding"
        elif risk_on is not None and risk_on <= 0.4:
            opportunity_state = "Contracting"
    except Exception:
        pass

    as_of = mr["Date"].max().normalize()
    ims_dt = pd.to_datetime(ims_latest.get("date", ims_latest.get("Date")), errors="coerce")
    if pd.notna(ims_dt):
        as_of = ims_dt.normalize()
    row = pd.DataFrame(
        [
            {
                "Date": as_of,
                "market_regime": market_regime,
                "regime_momentum": regime_momentum,
                "allowed_exposure": float(allowed_exposure),
                "opportunity_state": opportunity_state,
                "focus_sectors": focus_sectors,
                "avoid_sectors": avoid_sectors,
            }
        ]
    )

    if out_path.exists():
        try:
            existing = pd.read_parquet(out_path)
            if not existing.empty and "Date" in existing.columns:
                existing["Date"] = pd.to_datetime(existing["Date"], errors="coerce")
                combined = pd.concat([existing, row], ignore_index=True)
                combined = combined.dropna(subset=["Date"]).sort_values("Date")
                combined = combined.drop_duplicates(subset=["Date"], keep="last")
                _atomic_write_parquet(combined, out_path, index=False)
                return True, f"Updated ({len(combined)} rows, last={as_of.date()})"
        except Exception:
            pass

    _atomic_write_parquet(row, out_path, index=False)
    return True, f"Wrote ({len(row)} rows, as_of={as_of.date()})"


def _update_narrative_change_log(project_root: Path) -> tuple[bool, str]:
    """
    Build incremental narrative change records from daily_narrative.parquet.

    Produces:
    - data/processed/narrative_change_log.jsonl (append-only)
    - data/processed/latest_narrative_change.json (latest snapshot)
    """
    narrative_path = project_root / "data/processed/daily_narrative.parquet"
    log_path = project_root / "data/processed/narrative_change_log.jsonl"
    latest_path = project_root / "data/processed/latest_narrative_change.json"

    if not narrative_path.exists():
        return False, "daily_narrative.parquet missing"

    df = pd.read_parquet(narrative_path)
    if df.empty or "Date" not in df.columns:
        return False, "daily_narrative.parquet empty or malformed"

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    if df.empty:
        return False, "daily_narrative.parquet has no valid Date rows"

    current = df.iloc[-1].to_dict()
    previous = df.iloc[-2].to_dict() if len(df) >= 2 else None

    tracked_fields = [
        "market_regime",
        "regime_momentum",
        "allowed_exposure",
        "opportunity_state",
        "focus_sectors",
        "avoid_sectors",
    ]

    def _normalize(v: Any) -> Any:
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        if isinstance(v, np.floating):
            return float(v)
        if isinstance(v, np.integer):
            return int(v)
        return v

    changes: Dict[str, Dict[str, Any]] = {}
    for field in tracked_fields:
        cur = _normalize(current.get(field))
        prev = _normalize(previous.get(field) if previous else None)

        changed = cur != prev
        if isinstance(cur, float) and isinstance(prev, float):
            changed = abs(cur - prev) > 1e-9

        if changed:
            entry = {"from": prev, "to": cur}
            if field == "allowed_exposure" and isinstance(cur, float) and isinstance(prev, float):
                entry["delta"] = cur - prev
            changes[field] = entry

    if changes:
        summary = "Changed: " + ", ".join(changes.keys())
    else:
        summary = "No material narrative changes vs previous snapshot"

    payload = {
        "timestamp": _now().isoformat(),
        "narrative_as_of": _normalize(current.get("Date")),
        "previous_as_of": _normalize(previous.get("Date")) if previous else None,
        "change_count": len(changes),
        "changes": changes,
        "summary": summary,
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(payload, default=str) + "\n")

    _atomic_write_json(latest_path, payload)
    return True, summary


def _refresh_dashboard_narrative_feed(project_root: Path) -> tuple[bool, str]:
    """
    Refresh dashboard narrative feed from the latest narrative/market artifacts.

    This keeps `data/dashboard/narrative_feed.json` current even when the
    heavyweight narrative integration runner is skipped.
    """
    out_path = project_root / "data/dashboard/narrative_feed.json"
    state_path = project_root / "data/processed/narrative_state.parquet"
    change_path = project_root / "data/processed/latest_narrative_change.json"

    if not state_path.exists():
        return False, "narrative_state.parquet missing"

    try:
        ns = pd.read_parquet(state_path)
    except Exception as e:
        return False, f"failed to read narrative_state.parquet: {e}"

    if ns.empty or "date" not in ns.columns:
        return False, "narrative_state.parquet empty or malformed"

    ns = ns.copy()
    ns["date"] = pd.to_datetime(ns["date"], errors="coerce")
    ns = ns.dropna(subset=["date"]).sort_values("date")
    if ns.empty:
        return False, "narrative_state.parquet has no valid dated rows"

    row = ns.iloc[-1]
    as_of = pd.to_datetime(row.get("date"), errors="coerce")
    as_of_str = as_of.strftime("%Y-%m-%d") if pd.notna(as_of) else "unknown"

    regime_name = str(row.get("regime_name", "Unknown"))
    regime_stability = float(pd.to_numeric(row.get("regime_stability"), errors="coerce") or 0.0)
    risk_level = str(row.get("regime_risk_level", "medium"))
    pulse_intensity = float(pd.to_numeric(row.get("pulse_intensity"), errors="coerce") or 0.0)
    cash_allocation = float(pd.to_numeric(row.get("cash_allocation"), errors="coerce") or 0.0)
    returns = float(pd.to_numeric(row.get("returns"), errors="coerce") or 0.0)
    total_risk = float(pd.to_numeric(row.get("total_risk"), errors="coerce") or 0.0)
    max_drawdown = float(pd.to_numeric(row.get("drawdown"), errors="coerce") or 0.0)
    total_strategies = int(pd.to_numeric(row.get("total_strategies"), errors="coerce") or 0)

    latest_change = _safe_read_json(change_path) or {}
    change_summary = str(latest_change.get("summary", "No narrative delta summary available"))
    change_count = int(latest_change.get("change_count", 0) or 0)

    now = _now()
    feed = {
        "timestamp": now.isoformat(),
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S"),
        "market_pulse": (
            f"As of {as_of_str}: {regime_name} regime with {regime_stability:.1%} stability; "
            f"pulse intensity {pulse_intensity:.1%}."
        ),
        "regime_status": {
            "name": regime_name.replace("_", " "),
            "stability": f"{regime_stability:.1%}",
            "risk_level": risk_level,
            "confidence": "high" if regime_stability >= 0.7 else ("moderate" if regime_stability >= 0.4 else "low"),
            "as_of": as_of_str,
        },
        "portfolio_snapshot": {
            "cash_allocation": f"{cash_allocation:.1%}",
            "total_strategies": total_strategies,
            "risk_level": f"{total_risk:.1%}",
            "max_drawdown": f"{abs(max_drawdown):.1%}",
            "returns": f"{returns:+.2%}",
        },
        "key_insights": [
            f"Regime as of {as_of_str}: {regime_name.replace('_', ' ')} ({regime_stability:.1%} stability).",
            f"Pulse intensity at {pulse_intensity:.1%}; risk level assessed as {risk_level}.",
            f"Cash allocation {cash_allocation:.1%} across {total_strategies} active strategies.",
            f"Narrative delta: {change_summary}",
        ],
        "status_indicators": {
            "narrative_engine": "active",
            "regime_intelligence": "operational",
            "risk_management": "institutional_grade",
            "latest_change_count": change_count,
            "last_update": "current",
        },
    }

    _atomic_write_json(out_path, feed)
    return True, f"Refreshed narrative_feed.json (as_of={as_of_str}, changes={change_count})"


def _build_regime_transitions_and_feed(project_root: Path) -> tuple[bool, str]:
    """Build transitions + regime_intelligence_feed with intelligent-state authority."""
    mr_path = project_root / "data/processed/market_regime.parquet"
    ims_path = project_root / "data/processed/intelligent_market_state.parquet"
    nifty_path = project_root / "data/processed/nifty.parquet"
    out_transitions = project_root / "data/processed/regime_transitions.parquet"
    out_feed = project_root / "data/processed/regime_intelligence_feed.json"

    regime_df: Optional[pd.DataFrame] = None
    source_name = "market_regime"
    source_alignment = "fallback"
    latest_controls: Dict[str, Any] = {}

    if ims_path.exists():
        try:
            ims = pd.read_parquet(ims_path)
            if not ims.empty:
                date_col = "date" if "date" in ims.columns else ("Date" if "Date" in ims.columns else None)
                regime_cols = [c for c in ["regime_ai", "regime", "macro_regime", "market_regime"] if c in ims.columns]
                if date_col and regime_cols:
                    ims[date_col] = pd.to_datetime(ims[date_col], errors="coerce")
                    ims = ims.dropna(subset=[date_col]).sort_values(date_col)
                    best_reg_col = None
                    best_non_null = -1
                    for c in regime_cols:
                        s = ims[c].astype(str).str.strip()
                        nn = int(((s != "") & (s.str.lower() != "none") & (s.str.lower() != "nan")).sum())
                        if nn > best_non_null:
                            best_non_null = nn
                            best_reg_col = c
                    if best_reg_col and best_non_null >= 10:
                        d = ims[[date_col, best_reg_col]].copy()
                        d = d.rename(columns={date_col: "Date", best_reg_col: "market_regime"})
                        d["market_regime"] = d["market_regime"].astype(str).str.strip()
                        d = d[
                            (d["market_regime"] != "")
                            & (d["market_regime"].str.lower() != "none")
                            & (d["market_regime"].str.lower() != "nan")
                        ]
                        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
                        d = d.dropna(subset=["Date", "market_regime"]).sort_values("Date")
                        if len(d) >= 10:
                            regime_df = d
                            source_name = "intelligent_market_state"
                            source_alignment = "authoritative"
                            latest_ims = ims.iloc[-1]
                            latest_controls = {
                                "allowed_exposure": _as_fraction(latest_ims.get("allowed_exposure")),
                                "risk_on_probability": _as_fraction(latest_ims.get("risk_on_probability")),
                            }
        except Exception:
            regime_df = None

    if regime_df is None:
        if not mr_path.exists():
            return False, "Neither intelligent_market_state nor market_regime available"
        mr = pd.read_parquet(mr_path)
        if mr.empty or "Date" not in mr.columns or "market_regime" not in mr.columns:
            return False, "market_regime.parquet empty or malformed"
        mr["Date"] = pd.to_datetime(mr["Date"], errors="coerce")
        regime_df = mr.dropna(subset=["Date", "market_regime"]).sort_values("Date")

    labels = regime_df["market_regime"].astype(str).reset_index(drop=True)
    if len(labels) < 10:
        return False, "Not enough regime history to compute transitions"

    # Use a stable ordering for readability.
    preferred = ["Bull", "Neutral", "Bear", "Fragile", "Panic"]
    states = [s for s in preferred if s in set(labels.tolist())]
    # Include any unexpected states at the end (still real data).
    states.extend([s for s in sorted(set(labels.tolist())) if s not in set(states)])
    if not states:
        return False, "No regimes found"

    counts = pd.DataFrame(0.0, index=states, columns=states)
    for a, b in zip(labels.iloc[:-1].tolist(), labels.iloc[1:].tolist()):
        if a in counts.index and b in counts.columns:
            counts.loc[a, b] += 1.0

    # Dirichlet-style smoothing prevents degenerate 0/1 transitions on sparse rows.
    counts = counts + 1e-3

    # Normalize rows to probabilities
    row_sums = counts.sum(axis=1).replace(0, 1.0)
    transitions = counts.div(row_sums, axis=0)

    out_transitions.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_parquet(transitions, out_transitions)

    # Current regime + stability
    current_regime = str(labels.iloc[-1])
    # Duration in current regime (consecutive days)
    duration = 1
    for v in labels.iloc[::-1].tolist()[1:]:
        if v == current_regime:
            duration += 1
        else:
            break

    recent = labels.tail(min(30, len(labels))).reset_index(drop=True)
    changes = int((recent != recent.shift(1)).sum()) - 1  # ignore first NaN shift
    denom = max(len(recent) - 1, 1)
    # Smoothed estimator avoids pathological 0/1 certainty on small windows.
    stability_raw = 1.0 - (changes / denom)
    stability = float(np.clip((stability_raw * denom + 1.0) / (denom + 2.0), 0.02, 0.98))

    if current_regime in transitions.index:
        next_probs = transitions.loc[current_regime].to_dict()
    else:
        next_probs = {current_regime: 1.0}

    # Forward expectations from NIFTY (if available)
    forward_expectations: Dict[str, Any] = {}
    if nifty_path.exists():
        try:
            nifty = pd.read_parquet(nifty_path)
            close_col = "close" if "close" in nifty.columns else ("Close" if "Close" in nifty.columns else None)
            if close_col:
                closes = pd.to_numeric(nifty[close_col], errors="coerce").dropna()
                closes.index = pd.to_datetime(closes.index, errors="coerce")
                closes = closes.dropna().sort_index()

                # Align regimes to NIFTY dates
                reg_idx = regime_df.set_index("Date").sort_index()
                common = reg_idx.index.intersection(closes.index)
                reg_idx = reg_idx.loc[common]
                closes = closes.loc[common]

                horizons = {"5d": 5, "21d": 21, "63d": 63}
                for label_name, h in horizons.items():
                    # Dates where regime == current
                    mask = reg_idx["market_regime"].astype(str) == current_regime
                    idx = reg_idx.index[mask]
                    fwd = []
                    for dt in idx:
                        pos = closes.index.get_loc(dt)
                        if isinstance(pos, int) and pos + h < len(closes):
                            r = closes.iloc[pos + h] / closes.iloc[pos] - 1.0
                            if np.isfinite(r):
                                fwd.append(float(r))
                    if len(fwd) >= 5:
                        s = pd.Series(fwd, dtype="float64")
                        forward_expectations[label_name] = {
                            "mean": float(s.mean()),
                            "median": float(s.median()),
                            "win_rate": float((s > 0).mean()),
                            "p10": float(s.quantile(0.10)),
                            "p90": float(s.quantile(0.90)),
                            "samples": int(len(s)),
                        }
        except Exception:
            forward_expectations = {}

    # Confidence metrics (transparent + real-data-derived)
    probs = np.array([v for v in next_probs.values() if v is not None], dtype="float64")
    probs = probs[probs > 0]
    if probs.size > 0:
        entropy = float(-(probs * np.log(probs)).sum())
        max_entropy = float(np.log(len(states))) if len(states) > 1 else 1.0
        transition_conf = float(np.clip(1.0 - (entropy / max_entropy), 0.0, 1.0))
    else:
        transition_conf = 0.0

    # Sample-size confidence for forward expectations
    sample_n = 0
    try:
        if forward_expectations:
            sample_n = int(max(v.get("samples", 0) for v in forward_expectations.values()))
    except Exception:
        sample_n = 0
    forward_conf = float(np.clip(sample_n / 200.0, 0.0, 1.0)) if sample_n > 0 else 0.0

    confidence_metrics = {
        "regime_identification": stability,
        "transition_prediction": transition_conf,
        "forward_expectations": forward_conf,
        "overall": float(np.mean([stability, transition_conf, forward_conf])),
    }

    feed = {
        "timestamp": _now().isoformat(),
        "version": "3.0",
        "feed_type": "market_regime_markov_v1",
        "current_regime": {
            "cluster": states.index(current_regime) if current_regime in states else None,
            "name": current_regime,
            "stability": stability,
            "duration_in_regime": int(duration),
        },
        "regime_transitions": {
            "next_regime_probabilities": next_probs,
            "transition_confidence": transition_conf,
        },
        "forward_expectations": forward_expectations,
        "confidence_metrics": confidence_metrics,
        "integration_metadata": {
            "source": f"{source_name}.parquet" if source_name != "market_regime" else "market_regime.parquet",
            "regime_authority": source_name,
            "authority_alignment": source_alignment,
            "states": states,
            "as_of": str(pd.to_datetime(regime_df["Date"].max()).date()),
            "controls": latest_controls,
        },
    }

    _atomic_write_json(out_feed, feed)

    return True, (
        f"Transitions={len(states)}x{len(states)}; current={current_regime}; "
        f"stability={stability:.2f}; authority={source_name}"
    )


def _build_anticipatory_signals_from_feed(project_root: Path) -> tuple[bool, str]:
    """
    Build `anticipatory_signals.json` from the latest regime feed.
    This keeps narrative + legacy integrations fresh even when older upstream
    scripts are not run in the current cycle.
    """
    feed_path = project_root / "data/processed/regime_intelligence_feed.json"
    out_path = project_root / "data/processed/anticipatory_signals.json"

    feed = _safe_read_json(feed_path)
    if not feed:
        return False, "regime_intelligence_feed.json missing/unreadable"

    cur = feed.get("current_regime", {}) or {}
    trans = feed.get("regime_transitions", {}) or {}
    next_probs = trans.get("next_regime_probabilities", {}) or {}

    cur_name = str(cur.get("name", "Unknown"))
    stability = float(cur.get("stability", 0.5) or 0.5)
    duration = int(cur.get("duration_in_regime", 0) or 0)

    # Ex-transition probability excludes the current regime if present.
    ex_probs = {k: float(v) for k, v in next_probs.items() if str(k) != cur_name}
    if ex_probs:
        next_likely = max(ex_probs, key=ex_probs.get)
        transition_probability_raw = float(ex_probs[next_likely])
    elif next_probs:
        next_likely = max(next_probs, key=next_probs.get)
        transition_probability_raw = float(next_probs[next_likely])
    else:
        next_likely = "Unknown"
        transition_probability_raw = 0.0

    # Calibrate transition probability to avoid hard saturation and
    # include stability/duration context.
    duration_factor = float(np.clip(duration / 10.0, 0.0, 1.0))
    transition_probability = float(np.clip(
        (0.60 * transition_probability_raw + 0.40 * (1.0 - stability)) * (0.5 + 0.5 * duration_factor),
        0.0,
        0.85
    ))

    stability_risk = float(np.clip(1.0 - stability, 0.0, 1.0))
    transition_risk = float(np.clip(transition_probability, 0.0, 1.0))
    risk_score = float(np.clip(0.6 * transition_risk + 0.4 * stability_risk, 0.0, 1.0))
    if risk_score >= 0.66:
        risk_level = "high"
    elif risk_score >= 0.33:
        risk_level = "medium"
    else:
        risk_level = "low"

    signals = {
        "timestamp": _now().isoformat(),
        "available": True,
        "source": "regime_intelligence_feed",
        "current_regime": {
            "name": cur_name,
            "cluster": cur.get("cluster"),
            "stability": stability,
            "confidence": float((feed.get("confidence_metrics") or {}).get("overall", 0.0) or 0.0),
            "duration_in_regime": duration,
        },
        "regime_transitions": {
            "next_likely_regime": next_likely,
            "transition_probability": transition_probability,
            "transition_probability_raw": transition_probability_raw,
            "next_regime_probabilities": next_probs,
            "transition_confidence": float(trans.get("transition_confidence", 0.0) or 0.0),
        },
        "forward_expectations": feed.get("forward_expectations", {}),
        "strategy_recommendations": {},
        "risk_assessment": {
            "overall_risk": risk_level,
            "regime_risk_level": risk_level,
            "risk_score": risk_score,
            "transition_risk": transition_risk,
            "stability_risk": stability_risk,
        },
    }

    _atomic_write_json(out_path, signals)
    return True, f"Built anticipatory_signals.json (regime={cur_name}, risk={risk_level})"


def _snapshot_weekly_portfolio(project_root: Path) -> tuple[bool, str]:
    """Create a weekly snapshot from the latest portfolio weights artifact."""
    wdf, source = _load_best_portfolio_weights(project_root)
    if wdf is None or wdf.empty:
        return False, "No usable portfolio weights found (canonical/backup/weekly)"
    if "weight" not in wdf.columns:
        return False, f"No weight column in portfolio weights ({source})"

    # Normalize tickers + weight column
    if "ticker" not in wdf.columns and "symbol" not in wdf.columns:
        return False, "No ticker/symbol column in portfolio weights"

    tick = wdf["ticker"].astype(str) if "ticker" in wdf.columns else wdf["symbol"].astype(str)
    tick = tick.str.strip()
    tick = tick.where(tick.str.contains(r"\."), tick + ".NS")
    wdf["ticker"] = tick

    wdf["weight"] = pd.to_numeric(wdf["weight"], errors="coerce")
    wdf = wdf.dropna(subset=["ticker", "weight"])
    wdf = wdf[wdf["weight"] > 0].copy()
    if wdf.empty:
        return False, f"All portfolio weights are zero/non-positive ({source})"

    # If canonical weights are currently degenerate but we found a valid fallback,
    # repair canonical state so downstream engines stay aligned.
    canonical_path = project_root / "data/processed/portfolio_weights.parquet"
    if source != "canonical":
        try:
            canon_df = pd.read_parquet(canonical_path) if canonical_path.exists() else pd.DataFrame()
            if not _is_meaningful_weights(_normalize_weights_frame(canon_df)):
                repaired = pd.DataFrame(
                    {
                        "date": pd.to_datetime(_now().date()),
                        "symbol": wdf["ticker"].astype(str).str.replace(".NS", "", regex=False),
                        "weight": pd.to_numeric(wdf["weight"], errors="coerce").fillna(0.0),
                        "exposure": pd.to_numeric(wdf["weight"], errors="coerce").fillna(0.0),
                        "ticker": wdf["ticker"].astype(str),
                    }
                )
                _atomic_write_parquet(repaired, canonical_path, index=False)
                source = f"{source}→repaired_canonical"
        except Exception:
            pass

    # Enrich with Industry if available
    uni = project_root / "universe/nifty500.csv"
    if uni.exists():
        try:
            u = pd.read_csv(uni)
            u["ticker"] = u["Symbol"].astype(str).str.strip() + ".NS"
            if "Industry" in u.columns:
                wdf = wdf.merge(u[["ticker", "Industry"]], on="ticker", how="left")
        except Exception:
            pass

    snap_date = _now().date().isoformat()
    out_dir = project_root / "data/portfolio/weekly"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{snap_date}.parquet"
    _atomic_write_parquet(
        wdf[["ticker", "weight"] + (["Industry"] if "Industry" in wdf.columns else [])],
        out_path,
        index=False,
    )

    # Update "latest.json"
    latest_path = out_dir / "latest.json"
    _atomic_write_json(latest_path, {"date": snap_date, "path": str(out_path)})

    return True, f"Saved {out_path.relative_to(project_root)} ({len(wdf)} positions, source={source})"


def _build_weekly_trade_deltas(project_root: Path) -> tuple[bool, str]:
    """Build latest weekly trade delta artifact from the last two snapshots."""
    weekly_dir = project_root / "data/portfolio/weekly"
    trade_dir = project_root / "data/portfolio/trades"
    if not weekly_dir.exists():
        return False, "weekly snapshot directory missing"

    snaps = sorted([p for p in weekly_dir.glob("*.parquet") if p.name != "latest.json"])
    if len(snaps) < 2:
        return True, "Not enough weekly snapshots for trade delta (need >=2)"

    prev_path, cur_path = snaps[-2], snaps[-1]
    prev = _normalize_weights_frame(pd.read_parquet(prev_path))
    cur = _normalize_weights_frame(pd.read_parquet(cur_path))

    if "ticker" not in prev.columns or "ticker" not in cur.columns or "weight" not in prev.columns or "weight" not in cur.columns:
        return False, "Weekly snapshots missing ticker/weight columns"

    prev_df = prev[["ticker", "weight"]].copy()
    cur_df = cur[["ticker", "weight"]].copy()
    prev_df["ticker"] = prev_df["ticker"].astype(str).str.strip()
    cur_df["ticker"] = cur_df["ticker"].astype(str).str.strip()
    prev_df["weight"] = pd.to_numeric(prev_df["weight"], errors="coerce").fillna(0.0)
    cur_df["weight"] = pd.to_numeric(cur_df["weight"], errors="coerce").fillna(0.0)

    merged = prev_df.merge(cur_df, on="ticker", how="outer", suffixes=("_prev", "_cur")).fillna(0.0)
    merged["delta"] = merged["weight_cur"] - merged["weight_prev"]
    merged["action"] = np.where(
        merged["delta"] > 0,
        "BUY",
        np.where(merged["delta"] < 0, "SELL", "HOLD"),
    )
    merged["abs_delta"] = merged["delta"].abs()
    merged = merged.sort_values("abs_delta", ascending=False)

    trade_dir.mkdir(parents=True, exist_ok=True)
    trade_path = trade_dir / f"{cur_path.stem}.parquet"
    _atomic_write_parquet(merged, trade_path, index=False)

    nonzero = int((merged["abs_delta"] > 1e-8).sum())
    turnover = float(merged["abs_delta"].sum())
    return True, f"Saved {trade_path.relative_to(project_root)} (changes={nonzero}, turnover={turnover:.4f})"


def _update_pnl_on_paper(project_root: Path) -> tuple[bool, str]:
    """Rebuild pnl_on_paper.parquet from weekly snapshots + processed prices."""
    pnl_path = project_root / "data/portfolio/pnl_on_paper.parquet"
    prices_path = project_root / "data/processed/prices.parquet"
    weekly_dir = project_root / "data/portfolio/weekly"

    if not prices_path.exists():
        return False, "prices.parquet missing"
    if not weekly_dir.exists():
        return False, "weekly snapshots missing"

    prices = pd.read_parquet(prices_path, columns=["Date", "ticker", "Close"])
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices = prices.dropna(subset=["Date", "ticker", "Close"])
    prices["ticker"] = prices["ticker"].astype(str).str.strip()
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = prices.dropna(subset=["Close"])

    price_tbl = (
        prices.sort_values(["Date", "ticker"])
        .pivot(index="Date", columns="ticker", values="Close")
        .sort_index()
        .ffill()
    )
    if price_tbl.empty:
        return False, "No prices available after pivot"

    # Load weekly snapshots
    snaps = []
    for p in sorted(weekly_dir.glob("*.parquet")):
        if p.name == "latest.json":
            continue
        try:
            s = pd.read_parquet(p)
            if s.empty or "ticker" not in s.columns:
                continue
            dt = pd.to_datetime(p.stem, errors="coerce")
            if pd.isna(dt):
                continue
            if "weight" not in s.columns:
                # Some snapshots may store final_weight, etc.
                wcol = None
                for c in ["final_weight", "w", "allocation"]:
                    if c in s.columns:
                        wcol = c
                        break
                if wcol is None:
                    continue
                s["weight"] = pd.to_numeric(s[wcol], errors="coerce")
            else:
                s["weight"] = pd.to_numeric(s["weight"], errors="coerce")
            s = s.dropna(subset=["ticker", "weight"])
            s["ticker"] = s["ticker"].astype(str).str.strip()
            s["date"] = dt.normalize()
            snaps.append(s[["date", "ticker", "weight"]])
        except Exception:
            continue

    if not snaps:
        return False, "No weekly snapshots to compute PnL"

    weekly = pd.concat(snaps, ignore_index=True)
    weekly_pivot = weekly.pivot_table(index="date", columns="ticker", values="weight", fill_value=0.0)

    # Build daily weights schedule by forward-filling weekly weights.
    weight_daily = weekly_pivot.reindex(price_tbl.index, method="ffill").fillna(0.0)

    # Align
    common = weight_daily.columns.intersection(price_tbl.columns)
    if common.empty:
        return False, "No overlap between weekly tickers and prices"
    weight_daily = weight_daily[common]
    price_tbl = price_tbl[common]

    ret_tbl = price_tbl.pct_change().fillna(0.0)
    weight_prev = weight_daily.shift(1).fillna(0.0)
    port_ret = (weight_prev * ret_tbl).sum(axis=1)
    equity = (1.0 + port_ret).cumprod()
    combined = pd.DataFrame(
        {"Date": port_ret.index, "Equity": equity.values, "Return": port_ret.values}
    ).dropna(subset=["Date"]).sort_values("Date")
    combined = combined.drop_duplicates(subset=["Date"], keep="last")

    _atomic_write_parquet(combined, pnl_path, index=False)

    dmax = pd.to_datetime(combined["Date"], errors="coerce").max()
    return True, f"PnL rebuilt through {dmax.date()} ({len(combined)} rows)"


def _build_portfolio_analytics(project_root: Path) -> tuple[bool, str]:
    """Build a lightweight portfolio_analytics.json from current weights (real data)."""
    mapping = project_root / "data/processed/sector_mapping.csv"
    out_path = project_root / "data/processed/portfolio_analytics.json"
    wdf, source = _load_best_portfolio_weights(project_root)
    if wdf is None or wdf.empty:
        return False, "No usable portfolio weights found"
    if "weight" not in wdf.columns:
        return False, "No weight column in portfolio weights"

    wdf = wdf.copy()
    wdf["ticker"] = wdf["ticker"].astype(str).str.strip()
    wdf["weight"] = pd.to_numeric(wdf["weight"], errors="coerce")
    wdf = wdf.dropna(subset=["ticker", "weight"])

    sector_alloc: Dict[str, float] = {}
    if mapping.exists():
        try:
            smap = pd.read_csv(mapping)
            merged = wdf.merge(smap, on="ticker", how="left")
            if "sector" in merged.columns and merged["sector"].notna().any():
                s = merged.dropna(subset=["sector"]).groupby("sector")["weight"].sum().sort_values(ascending=False)
                sector_alloc = {str(k): float(v) for k, v in s.items()}
        except Exception:
            sector_alloc = {}

    exposure = float(wdf["weight"].sum())
    if exposure > 1.0 + 1e-6:
        # Normalize accidental overweight snapshots to portfolio space.
        wdf["weight"] = wdf["weight"] / max(exposure, 1e-12)
        exposure = float(wdf["weight"].sum())
    cash = float(max(0.0, 1.0 - exposure))

    sharpe_ratio = 0.0
    max_drawdown = 0.0
    volatility = 0.0
    try:
        pnl_path = project_root / "data/portfolio/pnl_on_paper.parquet"
        if pnl_path.exists():
            pnl = pd.read_parquet(pnl_path)
            if not pnl.empty and "Return" in pnl.columns:
                r = pd.to_numeric(pnl["Return"], errors="coerce").dropna()
                if len(r) >= 10:
                    volatility = float(r.std() * np.sqrt(252))
                    sharpe_ratio = float((r.mean() * 252) / (r.std() * np.sqrt(252) + 1e-9))
            if not pnl.empty and "Equity" in pnl.columns:
                eq = pd.to_numeric(pnl["Equity"], errors="coerce").dropna()
                if len(eq) >= 2:
                    peak = eq.cummax()
                    dd = eq / peak - 1.0
                    max_drawdown = float(dd.min())
    except Exception:
        pass

    ims_latest = _load_latest_intelligent_state(project_root) or {}
    feed = _safe_read_json(project_root / "data/processed/regime_intelligence_feed.json") or {}

    canonical_regime = (
        ims_latest.get("regime_ai")
        or ims_latest.get("regime")
        or ims_latest.get("macro_regime")
    )
    feed_regime = ((feed.get("current_regime") or {}).get("name") if isinstance(feed, dict) else None)
    allowed_exposure = _as_fraction(ims_latest.get("allowed_exposure"))
    risk_on_probability = _as_fraction(
        ims_latest.get("risk_on_probability", ims_latest.get("risk_on"))
    )

    authority = (
        (feed.get("integration_metadata") or {}).get("regime_authority")
        if isinstance(feed, dict)
        else None
    )
    if not authority:
        authority = "intelligent_market_state" if canonical_regime else "market_regime"

    def _norm_reg(v: Any) -> str:
        s = str(v or "").replace("_", " ").replace("-", " ").strip().lower()
        if any(k in s for k in ["late expansion", "neutral", "recovery"]):
            return "neutral"
        if any(k in s for k in ["panic", "hostile", "crisis"]):
            return "crisis"
        if any(k in s for k in ["boom", "supportive", "expansion"]):
            return "expansion"
        if any(k in s for k in ["slowdown", "tightening", "bear"]):
            return "slowdown"
        return s

    if canonical_regime and feed_regime:
        regime_alignment = "aligned" if _norm_reg(canonical_regime) == _norm_reg(feed_regime) else "mismatch"
    else:
        regime_alignment = "unknown"

    analytics = {
        "timestamp": _now().isoformat(),
        "source": source,
        "portfolio_summary": {
            "n_positions": int(len(wdf)),
            "total_exposure": exposure,
            "cash": cash,
        },
        "total_risk": volatility,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "volatility": volatility,
        "sector_allocation": sector_alloc,
        # Keep attribution empty unless a dedicated attribution engine is run.
        "attribution": {},
        "intelligence_integration": {
            "regime": canonical_regime,
            "allowed_exposure": allowed_exposure,
            "risk_on_probability": risk_on_probability,
            "regime_authority": authority,
            "regime_alignment": regime_alignment,
            "feed_regime": feed_regime,
        },
    }

    _atomic_write_json(out_path, analytics)
    return True, f"Saved ({len(sector_alloc)} sectors, exposure={exposure:.3f})"


def _build_shadow_snapshot(project_root: Path) -> tuple[bool, str]:
    """
    Build canonical shadow-trading artifacts used by dashboards:
    - data/processed/shadow_trading_snapshot.json
    - data/processed/shadow_pnl_series.parquet
    """
    shadow_root = project_root / "data/live/shadow_trading"
    pnl_dir = shadow_root / "pnl"
    state_path = shadow_root / "trading_state.json"

    out_json = project_root / "data/processed/shadow_trading_snapshot.json"
    out_pnl = project_root / "data/processed/shadow_pnl_series.parquet"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    snapshot: Dict[str, Any] = {
        "timestamp": _now().isoformat(),
        "status": "missing",
        "source_dir": str(shadow_root),
        "latest_date": None,
        "stale_days": None,
        "files_count": 0,
        "latest": {},
        "trading_state": {},
    }

    if not shadow_root.exists():
        _atomic_write_json(out_json, snapshot)
        return False, "shadow trading directory missing"

    rows: list[Dict[str, Any]] = []
    if pnl_dir.exists():
        files = sorted(pnl_dir.glob("pnl_*.json"))
        snapshot["files_count"] = len(files)
        for f in files[-365:]:
            try:
                obj = json.loads(f.read_text())
            except Exception:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(obj.get("date"), errors="coerce"),
                    "timestamp": pd.to_datetime(obj.get("timestamp"), errors="coerce"),
                    "daily_return": pd.to_numeric(obj.get("daily_return"), errors="coerce"),
                    "daily_pnl": pd.to_numeric(obj.get("daily_pnl"), errors="coerce"),
                    "portfolio_value": pd.to_numeric(obj.get("portfolio_value"), errors="coerce"),
                    "cash": pd.to_numeric(obj.get("cash"), errors="coerce"),
                }
            )

    if rows:
        sdf = pd.DataFrame(rows)
        sdf = sdf.dropna(subset=["date"]).sort_values("date")
        if not sdf.empty:
            # Keep one row per date, latest write wins.
            sdf = sdf.drop_duplicates(subset=["date"], keep="last")
            _atomic_write_parquet(sdf, out_pnl, index=False)

            latest = sdf.iloc[-1]
            latest_date = pd.to_datetime(latest.get("date"), errors="coerce")
            stale_days = None
            if pd.notna(latest_date):
                stale_days = float((_now().date() - latest_date.date()).days)
            snapshot.update(
                {
                    "status": "ok",
                    "latest_date": latest_date.date().isoformat() if pd.notna(latest_date) else None,
                    "stale_days": stale_days,
                    "latest": {
                        "daily_return": float(pd.to_numeric(latest.get("daily_return"), errors="coerce") or 0.0),
                        "daily_pnl": float(pd.to_numeric(latest.get("daily_pnl"), errors="coerce") or 0.0),
                        "portfolio_value": float(pd.to_numeric(latest.get("portfolio_value"), errors="coerce") or 0.0),
                        "cash": float(pd.to_numeric(latest.get("cash"), errors="coerce") or 0.0),
                    },
                }
            )
            if stale_days is not None and stale_days > 3:
                snapshot["status"] = "stale"
        else:
            # Retain previous parquet if present, but mark current snapshot as no_data.
            snapshot["status"] = "no_data"
    else:
        snapshot["status"] = "no_data"

    if state_path.exists():
        try:
            s = json.loads(state_path.read_text())
            snapshot["trading_state"] = {
                "system_active": bool(s.get("system_active", False)),
                "last_trading_date": s.get("last_trading_date"),
                "total_trading_days": int(s.get("total_trading_days", 0) or 0),
                "cumulative_return": float(pd.to_numeric(s.get("cumulative_return"), errors="coerce") or 0.0),
                "current_positions_count": int(len(s.get("current_positions") or {})),
            }
        except Exception:
            pass

    _atomic_write_json(out_json, snapshot)

    if snapshot["status"] == "ok":
        return True, (
            f"shadow snapshot updated (files={snapshot['files_count']}, "
            f"latest={snapshot.get('latest_date')})"
        )
    if snapshot["status"] == "stale":
        return True, (
            f"shadow snapshot is stale (latest={snapshot.get('latest_date')}, "
            f"stale_days={snapshot.get('stale_days')})"
        )
    return False, f"shadow snapshot incomplete (status={snapshot['status']})"


def main() -> int:
    os.chdir(PROJECT_ROOT)

    parser = argparse.ArgumentParser(description="Refresh core V3 artifacts (real data only)")
    parser.add_argument("--quick", action="store_true", help="Skip heavier rebuild steps")
    parser.add_argument("--skip-index", action="store_true", help="Skip index_data refresh")
    parser.add_argument(
        "--update-financials",
        action="store_true",
        help="Run yfinance quarterly financials -> fundamentals -> valuation refresh",
    )
    parser.add_argument(
        "--financials-tickers",
        type=str,
        default="",
        help="Optional comma-separated tickers for --update-financials",
    )
    parser.add_argument(
        "--financials-max-tickers",
        type=int,
        default=0,
        help="Optional cap for ad-hoc financials refresh",
    )
    parser.add_argument(
        "--skip-macro-impact",
        action="store_true",
        help="Skip Macro Impact Engine refresh",
    )
    parser.add_argument(
        "--skip-macro-transmission",
        action="store_true",
        help="Skip Macro Transmission Engine refresh",
    )
    parser.add_argument(
        "--macro-impact-companies",
        type=int,
        default=120,
        help="Company cap for macro impact refresh",
    )
    parser.add_argument(
        "--macro-impact-top-macros",
        type=int,
        default=30,
        help="Macro-variable cap for macro impact refresh",
    )
    parser.add_argument(
        "--macro-transmission-companies",
        type=int,
        default=120,
        help="Company cap for macro transmission refresh",
    )
    parser.add_argument(
        "--macro-transmission-macros",
        type=int,
        default=20,
        help="Macro-variable cap for macro transmission refresh",
    )
    parser.add_argument(
        "--macro-heavy",
        action="store_true",
        help="Disable macro light-mode caps (heavier run)",
    )
    parser.add_argument(
        "--skip-integrity-audit",
        action="store_true",
        help="Skip final V3 integrity verification step",
    )
    args = parser.parse_args()

    # Heavy profile should materially exceed light defaults even when callers only pass
    # `--macro-heavy` without explicit dimension flags.
    if args.macro_heavy:
        args.macro_impact_companies = max(int(args.macro_impact_companies), 300)
        args.macro_impact_top_macros = max(int(args.macro_impact_top_macros), 40)
        args.macro_transmission_companies = max(int(args.macro_transmission_companies), 250)
        args.macro_transmission_macros = max(int(args.macro_transmission_macros), 30)
        print(
            "ℹ️  Macro heavy profile active: "
            f"impact_companies={args.macro_impact_companies}, "
            f"impact_macros={args.macro_impact_top_macros}, "
            f"trans_companies={args.macro_transmission_companies}, "
            f"trans_macros={args.macro_transmission_macros}",
            flush=True,
        )

    start = time.time()
    steps: list[StepResult] = []

    def run_step(name: str, fn, *, optional: bool = False) -> None:
        # Always print step boundaries so callers (run_complete_v3_system) show progress,
        # even if inner scripts are quiet for long periods.
        kind = "optional" if optional else "required"
        print(f"\n▶️  Step: {name} ({kind})", flush=True)
        t0 = time.time()
        try:
            ok, msg = fn()
            dt = time.time() - t0
            steps.append(
                StepResult(
                    name=name,
                    status="success" if ok else ("skipped" if optional else "failed"),
                    message=msg,
                    duration_seconds=dt,
                )
            )
            icon = "✅" if ok else ("⚠️" if optional else "❌")
            print(f"{icon} {name} ({dt:.1f}s): {msg}", flush=True)
        except Exception as e:
            dt = time.time() - t0
            steps.append(
                StepResult(
                    name=name,
                    status="skipped" if optional else "failed",
                    message=str(e),
                    duration_seconds=dt,
                )
            )
            icon = "⚠️" if optional else "❌"
            print(f"{icon} {name} ({dt:.1f}s): {e}", flush=True)

    def _step_real_data_only_policy():
        ok, msg = _run_cmd([sys.executable, "-u", "scripts/runners/enforce_real_data_only.py"], timeout=120)
        return ok, msg or "real-data-only policy passed"

    run_step("real_data_only_policy", _step_real_data_only_policy)

    # ---- Index data refresh (benchmarks) ----
    def _step_index():
        if args.skip_index:
            return True, "Skipped by flag"
        ok, msg = _run_cmd([sys.executable, "-u", "scripts/update_index_data.py", "--period", "5y"], timeout=900)
        return ok, msg or "index_data updated"

    run_step("index_data", _step_index, optional=True)

    # ---- Prices + technicals + market regime ----
    def _step_price_processor():
        ok, msg = _run_cmd([sys.executable, "-u", "src/processing/price_processor.py"], timeout=1800)
        return ok, msg or "prices.parquet rebuilt"

    run_step("price_processor", _step_price_processor)

    def _step_financials_update():
        if not args.update_financials:
            return True, "Skipped by flag"
        cmd = [sys.executable, "-u", "scripts/update_financials_data.py"]
        if args.financials_tickers.strip():
            cmd += ["--tickers", args.financials_tickers]
        if args.financials_max_tickers and args.financials_max_tickers > 0:
            cmd += ["--max-tickers", str(args.financials_max_tickers)]
        ok, msg = _run_cmd(cmd, timeout=9000)
        return ok, msg or "financials/fundamentals/valuation refreshed"

    run_step("financials_refresh", _step_financials_update, optional=True)

    def _step_technicals():
        # technicals can be expensive; skip in quick mode if already present and newer than prices
        prices_p = PROJECT_ROOT / "data/processed/prices.parquet"
        tech_p = PROJECT_ROOT / "data/processed/technicals.parquet"
        if args.quick and tech_p.exists() and prices_p.exists() and tech_p.stat().st_mtime >= prices_p.stat().st_mtime:
            return True, "Quick mode: technicals already fresh"
        ok, msg = _run_cmd([sys.executable, "-u", "src/processing/technical_engine.py"], timeout=3600)
        return ok, msg or "technicals.parquet rebuilt"

    run_step("technical_engine", _step_technicals)

    def _step_northstar_scoring():
        ok, msg = _run_cmd([sys.executable, "-u", "-m", "src.scoring.northstar_model"], timeout=1800)
        return ok, msg or "scores.parquet rebuilt"

    run_step("northstar_scoring", _step_northstar_scoring, optional=True)

    def _step_market_regime():
        regime_script = PROJECT_ROOT / "src/processing/market_regime.py"
        regime_artifact = PROJECT_ROOT / "data/processed/market_regime.parquet"

        if not regime_script.exists():
            if regime_artifact.exists():
                return True, "market_regime.py missing; using existing market_regime.parquet"
            return False, "market_regime.py missing and market_regime.parquet unavailable"

        ok, msg = _run_cmd([sys.executable, "-u", "src/processing/market_regime.py"], timeout=1800)
        return ok, msg or "market_regime.parquet rebuilt"

    run_step("market_regime", _step_market_regime)

    # ---- Sector rotation + flows ----
    def _step_sector_rotation():
        ok, msg = _run_cmd([sys.executable, "-u", "src/processing/sector_rotation.py"], timeout=900)
        return ok, msg or "sector_rotation.parquet rebuilt"

    run_step("sector_rotation", _step_sector_rotation, optional=True)

    def _step_sector_flows():
        ok, msg = _run_cmd([sys.executable, "-u", "src/processing/flow_acceleration.py"], timeout=900)
        return ok, msg or "sector_flows.parquet rebuilt"

    run_step("sector_flows", _step_sector_flows, optional=True)

    # ---- Macro factors (optional; depends on RBI pipeline) ----
    def _step_macro_factors():
        cmds = [
            [sys.executable, "-u", "src/preprocessing/market_internals.py"],
            [sys.executable, "-u", "src/preprocessing/macro_blocks.py"],
            [sys.executable, "-u", "src/models/macro_regime.py"],
            [sys.executable, "-u", "src/portfolio/macro_risk_controller.py"],
        ]
        ok_all = True
        msgs = []
        for cmd in cmds:
            path = PROJECT_ROOT / cmd[2]
            if not path.exists():
                msgs.append(f"missing:{cmd[2]}")
                ok_all = False
                continue
            ok, msg = _run_cmd(cmd, timeout=1200)
            ok_all = ok_all and ok
            if msg:
                msgs.append(msg.splitlines()[0][:180])

        # Long-history macro v2 (global PCA de-correlation)
        macro_v2_script = PROJECT_ROOT / "src/preprocessing/macro_blocks_v2.py"
        macro_regime_script = PROJECT_ROOT / "src/models/macro_regime.py"
        if macro_v2_script.exists() and macro_regime_script.exists():
            v2_cmds = [
                [sys.executable, "-u", "src/preprocessing/macro_blocks_v2.py"],
                [
                    sys.executable,
                    "-u",
                    "src/models/macro_regime.py",
                    "--in-file",
                    "data/macro/factors/macro_factors_v2.parquet",
                    "--out-file",
                    "data/macro/factors/macro_score_v2.parquet",
                ],
            ]
            for cmd in v2_cmds:
                ok, msg = _run_cmd(cmd, timeout=1500)
                ok_all = ok_all and ok
                if msg:
                    msgs.append(f"v2:{msg.splitlines()[0][:170]}")
        else:
            msgs.append("v2_skipped:macro_blocks_v2_or_macro_regime_missing")

        # Dashboard expects this canonical path. Macro pipeline writes under
        # data/macro/factors/, so mirror the latest artifact into data/processed/.
        src = PROJECT_ROOT / "data/macro/factors/macro_factors.parquet"
        dst = PROJECT_ROOT / "data/processed/macro_factors.parquet"
        try:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                msgs.append(f"synced:{dst}")
            src_v2 = PROJECT_ROOT / "data/macro/factors/macro_factors_v2.parquet"
            dst_v2 = PROJECT_ROOT / "data/processed/macro_factors_v2.parquet"
            if src_v2.exists():
                dst_v2.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_v2, dst_v2)
                msgs.append(f"synced:{dst_v2}")
        except Exception as e:
            ok_all = False
            msgs.append(f"sync_failed:{e}")

        return ok_all, "; ".join(msgs) if msgs else "macro scripts executed"

    run_step("macro_pipeline", _step_macro_factors, optional=True)

    # ---- Macro-conditioned signal layer (daily market + RBI macro integration) ----
    def _step_macro_conditioned_alpha():
        out_dir = PROJECT_ROOT / "data/processed/macro_conditioned_alpha"
        latest_snapshot = out_dir / "latest_macro_conditioned_signal_snapshot.parquet"
        prices_p = PROJECT_ROOT / "data/processed/prices.parquet"
        macro_p = PROJECT_ROOT / "data/macro/factors/macro_factors.parquet"

        if (
            args.quick
            and latest_snapshot.exists()
            and prices_p.exists()
            and macro_p.exists()
            and latest_snapshot.stat().st_mtime >= prices_p.stat().st_mtime
            and latest_snapshot.stat().st_mtime >= macro_p.stat().st_mtime
        ):
            return True, "Quick mode: macro_conditioned_alpha already fresh"

        ok, msg = _run_cmd(
            [
                sys.executable,
                "-u",
                "scripts/macro_conditioned_signal_audit.py",
                "--horizon",
                "20",
                "--lookback-days",
                "504",
                "--min-obs",
                "20",
                "--output-dir",
                "data/processed/macro_conditioned_alpha",
            ],
            timeout=2400,
        )
        return ok, msg or "macro-conditioned alpha artifacts refreshed"

    run_step("macro_conditioned_alpha", _step_macro_conditioned_alpha, optional=True)

    # ---- Mandatory robustness suite for macro-conditioned alpha (full runs) ----
    def _step_macro_conditioned_mandatory():
        if args.quick:
            return True, "Quick mode: skipped macro-conditioned mandatory tests"
        ok, msg = _run_cmd(
            [
                sys.executable,
                "-u",
                "scripts/macro_conditioned_mandatory_tests.py",
                "--lookback-days",
                "504",
                "--min-obs",
                "20",
            ],
            timeout=3600,
        )
        return ok, msg or "macro-conditioned mandatory tests refreshed"

    run_step("macro_conditioned_mandatory", _step_macro_conditioned_mandatory, optional=True)

    # ---- Cohesive alpha feed (scores + macro-conditioned + optional institutional overlay) ----
    def _step_cohesive_alpha_feed():
        script = PROJECT_ROOT / "scripts/build_cohesive_alpha_feed.py"
        out_file = PROJECT_ROOT / "data/processed/cohesive_alpha_feed.parquet"
        deps = [
            PROJECT_ROOT / "data/processed/scores.parquet",
            PROJECT_ROOT / "data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet",
            PROJECT_ROOT / "data/alpha/latest_alpha_results.json",
        ]
        existing_deps = [p for p in deps if p.exists()]
        if (
            args.quick
            and out_file.exists()
            and existing_deps
            and out_file.stat().st_mtime >= max(p.stat().st_mtime for p in existing_deps)
        ):
            return True, "Quick mode: cohesive alpha feed already fresh"
        if not script.exists():
            return False, "scripts/build_cohesive_alpha_feed.py missing"
        ok, msg = _run_cmd(
            [
                sys.executable,
                "-u",
                "scripts/build_cohesive_alpha_feed.py",
                "--output",
                "data/processed/cohesive_alpha_feed.parquet",
            ],
            timeout=900,
        )
        return ok, msg or "cohesive alpha feed refreshed"

    run_step("cohesive_alpha_feed", _step_cohesive_alpha_feed, optional=True)

    # ---- Macro Impact Engine (institutional lagged transmission) ----
    def _step_macro_impact_engine():
        if args.skip_macro_impact:
            return True, "Skipped by flag"

        script = PROJECT_ROOT / "scripts/run_macro_impact_analysis.py"
        out_meta = PROJECT_ROOT / "data/processed/macro_impact/analysis_metadata.json"
        deps = [
            PROJECT_ROOT / "data/processed/prices.parquet",
            PROJECT_ROOT / "data/macro/comprehensive_rbi_data.parquet",
        ]
        if (
            args.quick
            and out_meta.exists()
            and all(p.exists() for p in deps)
            and out_meta.stat().st_mtime >= max(p.stat().st_mtime for p in deps)
        ):
            return True, "Quick mode: macro impact artifacts already fresh"

        if not script.exists():
            return False, "scripts/run_macro_impact_analysis.py missing"

        cmd = [
            sys.executable,
            "-u",
            "scripts/run_macro_impact_analysis.py",
            "--start-date",
            "2018-01-01",
            "--frequency",
            "W",
            "--companies",
            str(max(10, int(args.macro_impact_companies))),
            "--top-macros",
            str(max(5, int(args.macro_impact_top_macros))),
            "--output-dir",
            "reports/macro_impact",
            "--processed-output-dir",
            "data/processed/macro_impact",
        ]
        if not args.macro_heavy:
            cmd.append("--light-mode")

        ok, msg = _run_cmd(cmd, timeout=5400)
        return ok, msg or "macro impact artifacts refreshed"

    run_step("macro_impact_engine", _step_macro_impact_engine, optional=True)

    # ---- Macro Transmission Engine (TVP + forecasting + stress replay) ----
    def _step_macro_transmission_engine():
        if args.skip_macro_transmission:
            return True, "Skipped by flag"

        script = PROJECT_ROOT / "scripts/run_macro_transmission_analysis.py"
        out_meta = PROJECT_ROOT / "data/processed/macro_transmission/run_metadata.json"
        deps = [
            PROJECT_ROOT / "data/processed/cohesive_alpha_feed.parquet",
            PROJECT_ROOT / "data/processed/scores.parquet",
            PROJECT_ROOT / "data/processed/prices.parquet",
            PROJECT_ROOT / "data/macro/comprehensive_rbi_data.parquet",
        ]
        if (
            args.quick
            and out_meta.exists()
            and all(p.exists() for p in deps)
            and out_meta.stat().st_mtime >= max(p.stat().st_mtime for p in deps)
        ):
            return True, "Quick mode: macro transmission artifacts already fresh"

        if not script.exists():
            return False, "scripts/run_macro_transmission_analysis.py missing"

        cmd = [
            sys.executable,
            "-u",
            "scripts/run_macro_transmission_analysis.py",
            "--start-date",
            "2019-01-01",
            "--frequency",
            "W",
            "--max-companies",
            str(max(10, int(args.macro_transmission_companies))),
            "--max-macros",
            str(max(5, int(args.macro_transmission_macros))),
            "--output-dir",
            "data/processed/macro_transmission",
            "--score-source",
            "data/processed/cohesive_alpha_feed.parquet",
            "--score-column",
            "cohesive_alpha_score",
            "--run-optimizer",
        ]
        if args.macro_heavy:
            cmd.extend(["--run-jax-kalman", "--run-stochastic-vol"])
        if not args.macro_heavy:
            cmd.append("--light-mode")

        ok, msg = _run_cmd(cmd, timeout=5400)
        return ok, msg or "macro transmission artifacts refreshed"

    run_step("macro_transmission_engine", _step_macro_transmission_engine, optional=True)

    # ---- Intelligent market state (keeps the dashboard regime/exposure honest) ----
    def _step_intelligent_state():
        ok, msg = _run_cmd([sys.executable, "-u", "scripts/runners/run_intelligent_market_state.py"], timeout=600)
        return ok, msg or "intelligent_market_state updated"

    run_step("intelligent_market_state", _step_intelligent_state, optional=True)

    def _step_market_pulse():
        ok, msg = _run_cmd(
            [sys.executable, "-u", "-m", "src.intelligence.market_brain.market_pulse"],
            timeout=900,
        )
        return ok, msg or "pulse_state.json updated"

    run_step("market_pulse", _step_market_pulse, optional=True)

    # ---- High-conviction intelligence spine (beliefs -> tailwinds -> no-edge -> allocation) ----
    def _recent_enough(path: str, max_age_hours: float = 8.0) -> bool:
        p = PROJECT_ROOT / path
        if not p.exists():
            return False
        age_hours = (_now().timestamp() - p.stat().st_mtime) / 3600.0
        return age_hours <= max_age_hours

    def _step_strategy_beliefs():
        out_p = "data/processed/strategy_beliefs.parquet"
        if args.quick and _recent_enough(out_p):
            return True, "Quick mode: strategy beliefs already fresh"
        ok, msg = _run_cmd([sys.executable, "-u", "src/intelligence/strategy_beliefs.py"], timeout=1200)
        return ok, msg or "strategy beliefs refreshed"

    def _step_strategy_tailwinds():
        out_p = "data/intelligence/strategy_tailwinds.parquet"
        if args.quick and _recent_enough(out_p):
            return True, "Quick mode: strategy tailwinds already fresh"
        ok, msg = _run_cmd([sys.executable, "-u", "src/intelligence/simple_tailwind_engine.py"], timeout=900)
        return ok, msg or "strategy tailwinds refreshed"

    def _step_no_edge_detector():
        out_p = "data/intelligence/no_edge_state.parquet"
        if args.quick and _recent_enough(out_p):
            return True, "Quick mode: no-edge state already fresh"
        ok, msg = _run_cmd([sys.executable, "-u", "src/intelligence/no_edge_detector.py"], timeout=600)
        return ok, msg or "no-edge state refreshed"

    def _step_capital_allocator():
        out_p = "data/processed/capital_allocations.json"
        if args.quick and _recent_enough(out_p):
            return True, "Quick mode: capital allocations already fresh"
        ok, msg = _run_cmd([sys.executable, "-u", "src/intelligence/capital_allocator.py"], timeout=1200)
        return ok, msg or "capital allocations refreshed"

    run_step("strategy_beliefs", _step_strategy_beliefs, optional=True)
    run_step("strategy_tailwinds", _step_strategy_tailwinds, optional=True)
    run_step("no_edge_detector", _step_no_edge_detector, optional=True)
    run_step("capital_allocator", _step_capital_allocator, optional=True)

    def _step_portfolio_governor():
        ok, msg = _run_cmd([sys.executable, "-u", "-m", "src.portfolio.portfolio_governor"], timeout=1200)
        return ok, msg or "portfolio_weights.parquet refreshed via portfolio_governor"

    run_step("portfolio_governor", _step_portfolio_governor, optional=True)

    # ---- Portfolio snapshot + PnL ----
    run_step("weekly_snapshot", lambda: _snapshot_weekly_portfolio(PROJECT_ROOT), optional=True)
    run_step("weekly_trade_deltas", lambda: _build_weekly_trade_deltas(PROJECT_ROOT), optional=True)
    run_step("pnl_on_paper", lambda: _update_pnl_on_paper(PROJECT_ROOT), optional=True)

    # ---- Analytics + narrative + intelligence feed ----
    run_step("portfolio_analytics", lambda: _build_portfolio_analytics(PROJECT_ROOT), optional=True)
    run_step(
        "current_positions_snapshot",
        lambda: _run_cmd([sys.executable, "-u", "scripts/runners/sync_current_positions.py"], timeout=300),
        optional=True,
    )
    run_step("regime_feed", lambda: _build_regime_transitions_and_feed(PROJECT_ROOT), optional=True)
    run_step("anticipatory_signals", lambda: _build_anticipatory_signals_from_feed(PROJECT_ROOT), optional=True)
    run_step(
        "narrative_intelligence",
        lambda: _run_cmd([sys.executable, "-u", "-m", "src.intelligence.narrative_intelligence_engine"], timeout=900),
        optional=True,
    )
    run_step("daily_narrative", lambda: _write_daily_narrative(PROJECT_ROOT), optional=True)
    run_step("narrative_change_log", lambda: _update_narrative_change_log(PROJECT_ROOT), optional=True)
    run_step("dashboard_narrative_feed", lambda: _refresh_dashboard_narrative_feed(PROJECT_ROOT), optional=True)
    run_step(
        "edge_half_life",
        lambda: _run_cmd([sys.executable, "-u", "scripts/runners/run_edge_half_life.py"], timeout=600),
        optional=True,
    )
    run_step(
        "liquidity_risk",
        lambda: _run_cmd([sys.executable, "-u", "scripts/runners/run_liquidity_risk.py"], timeout=600),
        optional=True,
    )
    def _step_integrated_state_snapshot():
        out_p = "data/integrated/integrated_state_snapshot.parquet"
        if args.quick and _recent_enough(out_p):
            return True, "Quick mode: integrated state snapshot already fresh"
        ok, msg = _run_cmd(
            [sys.executable, "-u", "scripts/build_integrated_state_snapshot.py", "--lookback-days", "3650"],
            timeout=900,
        )
        return ok, msg or "integrated_state_snapshot refreshed"

    run_step("integrated_state_snapshot", _step_integrated_state_snapshot, optional=True)
    run_step(
        "shadow_trading_snapshot",
        lambda: _run_cmd(
            [
                sys.executable,
                "-u",
                "scripts/launch_comprehensive_shadow_trading.py",
                "--mode",
                "manual",
                "--days",
                "1",
            ],
            timeout=1200,
        ),
        optional=True,
    )
    run_step("shadow_snapshot_canonical", lambda: _build_shadow_snapshot(PROJECT_ROOT), optional=True)

    # ---- Valuation quality gates (strict schema + predictive diagnostics) ----
    def _step_valuation_schema_validation():
        cmd = [sys.executable, "-u", "scripts/runners/validate_valuation_artifacts.py", "--strict"]
        ok, msg = _run_cmd(cmd, timeout=900)
        return ok, msg or "valuation artifacts schema validated"

    run_step("valuation_schema_validation", _step_valuation_schema_validation)

    def _step_valuation_validation():
        cmd = [sys.executable, "-u", "scripts/runners/valuation_validation.py"]
        if args.quick:
            cmd.extend(["--horizons", "21", "--min-universe", "20"])
        ok, msg = _run_cmd(cmd, timeout=1200)
        return ok, msg or "valuation validation diagnostics refreshed"

    run_step("valuation_validation", _step_valuation_validation, optional=True)

    def _step_institutional_hardening():
        cmd = [sys.executable, "-u", "scripts/runners/run_institutional_hardening.py"]
        ok, msg = _run_cmd(cmd, timeout=900)
        return ok, msg or "institutional hardening checks refreshed"

    run_step("institutional_hardening", _step_institutional_hardening)

    def _step_integrity_audit():
        if args.skip_integrity_audit:
            return True, "Skipped by flag"
        cmd = [sys.executable, "-u", "scripts/runners/verify_v3_integrity.py"]
        if not args.quick:
            cmd.extend(["--sample-rows", "300000"])
        ok, msg = _run_cmd(cmd, timeout=1200)
        return ok, msg or "integrity verification completed"

    run_step("v3_integrity_audit", _step_integrity_audit)

    # ---- Execution log artifact (dashboard uses this) ----
    total = time.time() - start
    success = sum(1 for s in steps if s.status == "success")
    failed = sum(1 for s in steps if s.status == "failed")
    skipped = sum(1 for s in steps if s.status == "skipped")
    success_rate = success / max(len(steps), 1)

    log = {
        "timestamp": _now().isoformat(),
        "system_version": "v3",
        "component_status": {s.name: s.status for s in steps},
        "execution_log": [
            {
                "timestamp": _now().isoformat(),
                "component": s.name,
                "status": s.status,
                "message": s.message,
                "duration_seconds": s.duration_seconds,
            }
            for s in steps
        ],
        "total_duration": total,
        "success_rate": success_rate,
        "summary": {"success": success, "failed": failed, "skipped": skipped, "steps": len(steps)},
        "data_freshness_probe": {
            "raw_prices_max_date_sample": (
                str(_latest_date_in_prices_raw(PROJECT_ROOT / "data/raw/prices_daily").date())
                if _latest_date_in_prices_raw(PROJECT_ROOT / "data/raw/prices_daily") is not None
                else None
            ),
            "sentiment_summary": _safe_read_json(PROJECT_ROOT / "data/sentiment/v3/v3_sentiment_summary.json"),
            "sentiment_context": _sentiment_probe(PROJECT_ROOT),
        },
    }

    out_log = PROJECT_ROOT / "data/processed/system_execution_log.json"
    _atomic_write_json(out_log, log)

    # Print a concise summary (useful when called from run_complete_v3_system)
    print("\n📌 V3 ARTIFACT REFRESH SUMMARY")
    print("=" * 60)
    for s in steps:
        icon = "✅" if s.status == "success" else "⚠️" if s.status == "skipped" else "❌"
        print(f"{icon} {s.name}: {s.message}")
    print("-" * 60)
    print(f"Total: {total:.1f}s | Success: {success} | Failed: {failed} | Skipped: {skipped}")
    print(f"Execution log: {out_log.relative_to(PROJECT_ROOT)}")

    # Non-zero exit if required steps failed
    required_failed = any(
        s.status == "failed"
        and s.name in {
            "real_data_only_policy",
            "price_processor",
            "market_regime",
            "institutional_hardening",
            "v3_integrity_audit",
        }
        for s in steps
    )
    return 1 if required_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
