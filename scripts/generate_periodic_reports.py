#!/usr/bin/env python3
"""
Generate detailed periodic Northstar reports (daily/weekly/monthly/quarterly).

Each run updates *_latest files and archives older versions automatically.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.report_versioning import write_json_with_archive, write_text_with_archive


@dataclass
class PeriodWindow:
    name: str
    start: datetime
    end: datetime


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def _truncate(text: Any, limit: int = 320) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3].rstrip() + "..."


def _period_windows(now: datetime) -> List[PeriodWindow]:
    today_start = datetime.combine(now.date(), dt_time(0, 0, 0), tzinfo=now.tzinfo)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    quarter_month = ((now.month - 1) // 3) * 3 + 1
    quarter_start = today_start.replace(month=quarter_month, day=1)
    return [
        PeriodWindow("daily", today_start, now),
        PeriodWindow("weekly", week_start, now),
        PeriodWindow("monthly", month_start, now),
        PeriodWindow("quarterly", quarter_start, now),
    ]


def _load_market_state(window_start: datetime) -> Dict[str, Any]:
    path = PROJECT_ROOT / "data/processed/market_state.parquet"
    if not path.exists():
        return {"available": False, "reason": f"missing:{path}"}
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return {"available": False, "reason": "empty_market_state"}
        if "date" not in df.columns:
            return {"available": False, "reason": "missing_date_column"}
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=False)
        df = df.dropna(subset=["date"]).sort_values("date")
        if df.empty:
            return {"available": False, "reason": "no_valid_dates"}
        period_df = df[df["date"] >= pd.Timestamp(window_start.replace(tzinfo=None))]
        if period_df.empty:
            period_df = df.tail(1)
        first = period_df.iloc[0]
        last = period_df.iloc[-1]

        return {
            "available": True,
            "records_total": int(len(df)),
            "records_in_period": int(len(period_df)),
            "date_range": {
                "start": period_df["date"].min().isoformat(),
                "end": period_df["date"].max().isoformat(),
            },
            "latest_snapshot": {
                "regime": str(last.get("regime", "unknown")),
                "macro_regime": str(last.get("macro_regime", "unknown")),
                "stress_level": _safe_float(last.get("stress_level")),
                "risk_on_probability": _safe_float(last.get("risk_on_probability")),
                "health_score": _safe_float(last.get("health_score")),
                "market_phase": str(last.get("market_phase", "unknown")),
                "pulse_risk_level": str(last.get("pulse_risk_level", "unknown")),
                "allowed_exposure": _safe_float(last.get("allowed_exposure")),
                "coherence_score": _safe_float(last.get("coherence_score")),
            },
            "period_averages": {
                "stress_level": _safe_float(period_df.get("stress_level", pd.Series(dtype=float)).mean(), 0.0),
                "risk_on_probability": _safe_float(period_df.get("risk_on_probability", pd.Series(dtype=float)).mean(), 0.0),
                "health_score": _safe_float(period_df.get("health_score", pd.Series(dtype=float)).mean(), 0.0),
                "allowed_exposure": _safe_float(period_df.get("allowed_exposure", pd.Series(dtype=float)).mean(), 0.0),
            },
            "period_change": {
                "stress_level": _safe_float(last.get("stress_level")) - _safe_float(first.get("stress_level")),
                "risk_on_probability": _safe_float(last.get("risk_on_probability")) - _safe_float(first.get("risk_on_probability")),
                "health_score": _safe_float(last.get("health_score")) - _safe_float(first.get("health_score")),
                "allowed_exposure": _safe_float(last.get("allowed_exposure")) - _safe_float(first.get("allowed_exposure")),
            },
        }
    except Exception as exc:
        return {"available": False, "reason": f"error:{exc}"}


def _load_macro_state(window_start: datetime) -> Dict[str, Any]:
    cleaned_path = PROJECT_ROOT / "data/macro/cleaned/macro_cleaned.parquet"
    changes_path = PROJECT_ROOT / "data/macro/changes/all_retrospective_changes.json"

    out: Dict[str, Any] = {
        "available": cleaned_path.exists(),
        "cleaned_path": str(cleaned_path),
        "retrospective_log_path": str(changes_path),
    }
    if not cleaned_path.exists():
        out["reason"] = "missing_cleaned_macro"
        return out

    try:
        df = pd.read_parquet(cleaned_path)
        if df.empty:
            out["reason"] = "empty_cleaned_macro"
            return out

        if isinstance(df.index, pd.DatetimeIndex):
            date_idx = pd.to_datetime(df.index, errors="coerce")
        elif "date" in df.columns:
            date_idx = pd.to_datetime(df["date"], errors="coerce")
        else:
            date_idx = pd.Series(pd.NaT, index=df.index)

        mask = date_idx.notna()
        valid_df = df.loc[mask].copy()
        valid_dates = pd.to_datetime(date_idx[mask])
        if valid_df.empty:
            out["reason"] = "no_valid_macro_dates"
            return out

        period_mask = valid_dates >= pd.Timestamp(window_start.replace(tzinfo=None))
        period_df = valid_df.loc[period_mask].copy()
        if period_df.empty:
            period_df = valid_df.tail(1)

        out.update(
            {
                "rows_total": int(len(valid_df)),
                "rows_in_period": int(len(period_df)),
                "columns": int(len(valid_df.columns)),
                "latest_data_date": pd.to_datetime(valid_dates.max()).isoformat(),
            }
        )

        # Build top moving macro features in the period.
        numeric = period_df.select_dtypes(include=["number"])
        top_moves: List[Dict[str, Any]] = []
        if len(numeric) >= 2 and not numeric.empty:
            first = numeric.iloc[0]
            last = numeric.iloc[-1]
            deltas = (last - first).abs().sort_values(ascending=False)
            for col in deltas.index[:10]:
                old_val = _safe_float(first.get(col))
                new_val = _safe_float(last.get(col))
                denom = abs(old_val) if abs(old_val) > 1e-9 else 1.0
                pct = ((new_val - old_val) / denom) * 100.0
                top_moves.append(
                    {
                        "metric": str(col),
                        "old_value": old_val,
                        "new_value": new_val,
                        "delta": new_val - old_val,
                        "delta_pct": pct,
                    }
                )
        out["top_macro_moves"] = top_moves

    except Exception as exc:
        out["available"] = False
        out["reason"] = f"macro_error:{exc}"
        return out

    # Retrospective revisions summary.
    revisions: List[Dict[str, Any]] = []
    if changes_path.exists():
        try:
            logs = json.loads(changes_path.read_text(encoding="utf-8"))
            if isinstance(logs, list):
                for entry in logs:
                    ts = pd.to_datetime(entry.get("timestamp"), errors="coerce")
                    if pd.isna(ts):
                        continue
                    if ts.to_pydatetime() < window_start.replace(tzinfo=None):
                        continue
                    analysis = entry.get("analysis", {}) if isinstance(entry.get("analysis"), dict) else {}
                    revisions.append(
                        {
                            "timestamp": ts.isoformat(),
                            "filename": entry.get("filename"),
                            "changes": int(analysis.get("changes", 0) or 0),
                            "overlap_periods": int(analysis.get("overlap_periods", 0) or 0),
                            "new_periods": int(analysis.get("new_periods", 0) or 0),
                        }
                    )
        except Exception:
            pass
    out["retrospective_changes"] = {
        "count": int(len(revisions)),
        "items": revisions[:20],
    }
    return out


def _load_options_state() -> Dict[str, Any]:
    hist_dir = PROJECT_ROOT / "data/options/historical"
    manifests = {
        "1d": hist_dir / "upstox_universe_manifest_latest.json",
        "1w": hist_dir / "1w/upstox_universe_manifest_latest.json",
        "5m": hist_dir / "5m/upstox_universe_manifest_latest.json",
    }
    out: Dict[str, Any] = {
        "historical_dir": str(hist_dir),
        "intervals": {},
        "parquet_counts": {},
    }

    for interval, path in manifests.items():
        payload = _read_json(path)
        if not payload:
            out["intervals"][interval] = {"available": False, "manifest": str(path)}
            continue
        results = payload.get("results", []) if isinstance(payload.get("results"), list) else []
        success_rows = sorted(
            [r for r in results if isinstance(r, dict) and str(r.get("status")) == "SUCCESS"],
            key=lambda x: int(x.get("rows", 0) or 0),
            reverse=True,
        )
        out["intervals"][interval] = {
            "available": True,
            "manifest": str(path),
            "provider": payload.get("provider"),
            "generated_at": payload.get("generated_at"),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "status_breakdown": payload.get("status_breakdown", {}),
            "top_underlyings_by_rows": [
                {
                    "symbol": row.get("symbol"),
                    "rows": int(row.get("rows", 0) or 0),
                    "contracts_selected": int(row.get("contracts_selected", 0) or 0),
                    "contracts_with_data": int(row.get("contracts_with_data", 0) or 0),
                }
                for row in success_rows[:10]
            ],
        }

    out["parquet_counts"] = {
        "1d": len(list(hist_dir.glob("*_option_chains.parquet"))) if hist_dir.exists() else 0,
        "1w": len(list((hist_dir / "1w").glob("*_option_chains.parquet"))) if (hist_dir / "1w").exists() else 0,
        "5m": len(list((hist_dir / "5m").glob("*_option_chains.parquet"))) if (hist_dir / "5m").exists() else 0,
    }
    return out


def _load_narrative_state() -> Dict[str, Any]:
    reports_dir = PROJECT_ROOT / "data/reports"
    daily = _read_json(reports_dir / "daily_narrative.json")
    weekly = _read_json(reports_dir / "weekly_pulse.json")
    monthly = _read_json(reports_dir / "monthly_report.json")
    master = _read_json(reports_dir / "northstar_v3_master_report.json")
    return {
        "daily_narrative": {
            "available": bool(daily),
            "date": daily.get("date") if daily else None,
            "headline": _truncate((daily or {}).get("narrative", "")),
            "regime": ((daily or {}).get("regime_status", {}) or {}).get("current_regime")
            if isinstance((daily or {}).get("regime_status"), dict)
            else None,
        },
        "weekly_pulse": {
            "available": bool(weekly),
            "period": (weekly or {}).get("period"),
            "headline": _truncate(((weekly or {}).get("regime_summary", {}) or {}).get("narrative", "")),
            "risk_level": ((weekly or {}).get("regime_summary", {}) or {}).get("risk_level"),
        },
        "monthly_report": {
            "available": bool(monthly),
            "period": (monthly or {}).get("period"),
            "executive_summary": _truncate((((monthly or {}).get("executive_summary", {}) or {}).get("narrative", ""))),
        },
        "master_report": {
            "available": bool(master),
            "status": (master or {}).get("status"),
            "reports_available": (master or {}).get("reports_available", []),
        },
    }


def _load_system_health() -> Dict[str, Any]:
    status = _read_json(PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json")
    eod_state = _read_json(PROJECT_ROOT / "data/options/live/trading_day_orchestrator_eod_state.json")
    runtime_state = _read_json(PROJECT_ROOT / "data/options/live/options_runtime_state.json")
    return {
        "trading_day_orchestrator": status or {"available": False},
        "eod_state": eod_state or {"available": False},
        "options_runtime_state": runtime_state or {"available": False},
    }


def _build_executive_summary(
    period_name: str,
    window: PeriodWindow,
    market: Dict[str, Any],
    options_state: Dict[str, Any],
    macro: Dict[str, Any],
    narratives: Dict[str, Any],
) -> List[str]:
    summary: List[str] = []
    summary.append(
        f"{period_name.title()} report window: {window.start.date().isoformat()} to {window.end.date().isoformat()}."
    )

    if market.get("available"):
        snap = market.get("latest_snapshot", {})
        summary.append(
            "Market regime is "
            f"{snap.get('regime', 'unknown')} with health {snap.get('health_score', 0):.3f}, "
            f"stress {snap.get('stress_level', 0):.3f}, and risk-on probability {snap.get('risk_on_probability', 0):.3f}."
        )
    else:
        summary.append("Market-state parquet was unavailable; report uses only narrative and options artifacts.")

    one_d = ((options_state.get("intervals", {}) or {}).get("1d", {}) or {})
    if one_d.get("available"):
        bd = one_d.get("status_breakdown", {}) or {}
        summary.append(
            "Options universe coverage (1d) reports "
            f"{bd.get('SUCCESS', 0)} successful underlyings, "
            f"{bd.get('SKIPPED_NO_OPTIONS', 0)} no-option symbols, and "
            f"{bd.get('FAILED', 0)} failures."
        )
    else:
        summary.append("Options universe manifest (1d) was unavailable in this run.")

    retro = ((macro.get("retrospective_changes", {}) or {}).get("count", 0) if macro else 0)
    summary.append(
        f"RBI retrospective revision logs detected in this window: {retro}."
    )

    daily_headline = (((narratives.get("daily_narrative", {}) or {}).get("headline")) or "").strip()
    if daily_headline:
        summary.append(f"Daily narrative context: {daily_headline}")
    return summary


def _build_action_items(market: Dict[str, Any], options_state: Dict[str, Any], macro: Dict[str, Any]) -> List[str]:
    actions: List[str] = []

    if market.get("available"):
        snap = market.get("latest_snapshot", {})
        stress = _safe_float(snap.get("stress_level"), 0.0)
        health = _safe_float(snap.get("health_score"), 0.0)
        if stress >= 0.5:
            actions.append("Raise hedge ratio on weekly portfolio to cap drawdown under elevated stress.")
        if health <= 0.35:
            actions.append("Bias new entries toward defined-risk structures and reduce naked directional exposure.")

    one_d = ((options_state.get("intervals", {}) or {}).get("1d", {}) or {})
    if one_d.get("available"):
        failed = int(((one_d.get("status_breakdown", {}) or {}).get("FAILED", 0) or 0))
        if failed > 0:
            actions.append("Re-run failed option-universe symbols and inspect provider permission/logging failures.")
    else:
        actions.append("Generate or refresh 1d option universe manifest before next trading session.")

    retro_count = int(((macro.get("retrospective_changes", {}) or {}).get("count", 0) or 0))
    if retro_count > 0:
        actions.append("Review RBI retrospective revisions and rerun macro-dependent attribution where changes are material.")

    if not actions:
        actions.append("No urgent integrity issues detected; keep 5-minute live loops and EOD chain on schedule.")
    return actions


def _render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Northstar {report['period'].title()} Report")
    lines.append("")
    lines.append(f"- Generated: {report['generated_at']}")
    lines.append(f"- Window Start: {report['window']['start']}")
    lines.append(f"- Window End: {report['window']['end']}")
    lines.append("")
    lines.append("## Executive Summary")
    for bullet in report.get("executive_summary", []):
        lines.append(f"- {bullet}")
    lines.append("")
    lines.append("## Market State")
    lines.append("```json")
    lines.append(json.dumps(report.get("market_state", {}), indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## Macro State")
    lines.append("```json")
    lines.append(json.dumps(report.get("macro_state", {}), indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## Options Universe")
    lines.append("```json")
    lines.append(json.dumps(report.get("options_universe", {}), indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## Narrative Intelligence")
    lines.append("```json")
    lines.append(json.dumps(report.get("narrative_intelligence", {}), indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## System Health")
    lines.append("```json")
    lines.append(json.dumps(report.get("system_health", {}), indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## Action Checklist")
    for item in report.get("action_checklist", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def _build_report(window: PeriodWindow, generated_at: datetime) -> Dict[str, Any]:
    market_state = _load_market_state(window.start)
    macro_state = _load_macro_state(window.start)
    options_state = _load_options_state()
    narratives = _load_narrative_state()
    system_health = _load_system_health()

    report: Dict[str, Any] = {
        "generated_at": generated_at.isoformat(),
        "period": window.name,
        "window": {
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
        },
        "market_state": market_state,
        "macro_state": macro_state,
        "options_universe": options_state,
        "narrative_intelligence": narratives,
        "system_health": system_health,
    }
    report["executive_summary"] = _build_executive_summary(
        period_name=window.name,
        window=window,
        market=market_state,
        options_state=options_state,
        macro=macro_state,
        narratives=narratives,
    )
    report["action_checklist"] = _build_action_items(
        market=market_state,
        options_state=options_state,
        macro=macro_state,
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate detailed periodic system reports.")
    parser.add_argument("--timezone", type=str, default="Asia/Kolkata")
    parser.add_argument("--output-dir", type=str, default="data/reports/periodic")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tz = ZoneInfo(args.timezone)
    now = datetime.now(tz)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    windows = _period_windows(now)
    for window in windows:
        report = _build_report(window, now)
        json_path = output_dir / f"{window.name}_report_latest.json"
        md_path = output_dir / f"{window.name}_report_latest.md"
        write_json_with_archive(json_path, report)
        write_text_with_archive(md_path, _render_markdown(report))
        print(f"generated {window.name}: {json_path}")
        print(f"generated {window.name}: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
