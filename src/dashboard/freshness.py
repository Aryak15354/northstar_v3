#!/usr/bin/env python3
"""Content-age freshness resolver for dashboard visuals.

The dashboard's failure mode (2026-07 audit) was that stale panels rendered
identically to live ones — a Market tab describing December sat next to a fresh
NAV chart with nothing to distinguish them. This module computes, for any
visual spec, the age of the OLDEST real artifact it depends on, measured by the
data's own content date (the latest in-file date), not just the file mtime — a
file can be rewritten daily while its content freezes (the macro chain did
exactly this).

Every consumer (the per-card badge in sections/shared.py, the Data Truth Panel,
and the check_dashboard_freshness CI invariant) resolves freshness through here
so there is one definition of "is this telling the truth".
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import pandas as pd

from src.dashboard.registry import DEPENDENCY_SOURCES

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Freshness tiers (calendar days of content age). Generous enough that a normal
# weekend/holiday does not trip green->amber.
FRESH_DAYS = 2
STALE_DAYS = 7

STATUS_FRESH = "fresh"     # green
STATUS_AGING = "aging"     # amber
STATUS_STALE = "stale"     # red
STATUS_MISSING = "missing"  # red (file absent)
STATUS_UNKNOWN = "unknown"  # could not determine a date

_BADGE = {
    STATUS_FRESH: "🟢",
    STATUS_AGING: "🟡",
    STATUS_STALE: "🔴",
    STATUS_MISSING: "⛔",
    STATUS_UNKNOWN: "⚪",
}

_DATE_COLS = (
    "date", "Date", "timestamp", "trade_date", "as_of", "quarter_end",
    "MonthEnd", "month_end", "snapshot_date", "updated_at", "created_at",
    "datetime", "time",
)
_JSON_TS_KEYS = (
    "timestamp", "updated_at", "as_of", "generated_at", "generated_utc",
    "date", "last_updated",
)

# Cache within a single process run (Streamlit reruns get a fresh import scope
# often enough; the cost is a couple of parquet header reads).
_AGE_CACHE: dict[str, tuple[float | None, str, str | None]] = {}


def _paths_in(source_str: str) -> list[Path]:
    """Extract concrete data/ file paths from a DEPENDENCY_SOURCES value.

    Values can be a bare path, a "a + b" join, or a "path → json.key" reference;
    we only need the real files.
    """
    rels = re.findall(r"data/[\w/.\-]+\.(?:parquet|json|csv|jsonl)", str(source_str))
    return [PROJECT_ROOT / rel for rel in dict.fromkeys(rels)]


def _content_date(path: Path) -> pd.Timestamp | None:
    """Latest in-file content date; falls back to file mtime when undated."""
    try:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
            for col in _DATE_COLS:
                if col in df.columns:
                    s = pd.to_datetime(df[col], errors="coerce", utc=True).dropna()
                    if len(s):
                        return pd.Timestamp(s.max()).tz_localize(None)
            if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
                idx = df.index
                return pd.Timestamp((idx.tz_localize(None) if idx.tz is not None else idx).max())
        elif path.suffix in (".json", ".jsonl"):
            if path.suffix == ".jsonl":
                # last non-empty line
                last = None
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip():
                        last = line
                d = json.loads(last) if last else {}
            else:
                d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(d, dict):
                for key in _JSON_TS_KEYS:
                    if d.get(key):
                        ts = pd.to_datetime(d[key], errors="coerce", utc=True)
                        if pd.notna(ts):
                            return pd.Timestamp(ts).tz_localize(None)
        elif path.suffix == ".csv":
            df = pd.read_csv(path, nrows=100_000)
            for col in _DATE_COLS:
                if col in df.columns:
                    s = pd.to_datetime(df[col], errors="coerce", utc=True).dropna()
                    if len(s):
                        return pd.Timestamp(s.max()).tz_localize(None)
    except Exception:
        pass
    # Fallback: file mtime (still meaningful for status/heartbeat files).
    try:
        return pd.Timestamp(_dt.datetime.fromtimestamp(path.stat().st_mtime))
    except Exception:
        return None


def _path_age(path: Path) -> tuple[float | None, str, str | None]:
    """(age_days, status, as_of_date_str) for one file."""
    key = str(path)
    if key in _AGE_CACHE:
        return _AGE_CACHE[key]
    if not path.exists():
        result = (None, STATUS_MISSING, None)
        _AGE_CACHE[key] = result
        return result
    cdate = _content_date(path)
    if cdate is None:
        result = (None, STATUS_UNKNOWN, None)
    else:
        age = float((pd.Timestamp.now() - cdate).days)
        if age <= FRESH_DAYS:
            status = STATUS_FRESH
        elif age <= STALE_DAYS:
            status = STATUS_AGING
        else:
            status = STATUS_STALE
        result = (age, status, str(cdate.date()))
    _AGE_CACHE[key] = result
    return result


_STATUS_RANK = {
    STATUS_FRESH: 0, STATUS_UNKNOWN: 1, STATUS_AGING: 2,
    STATUS_STALE: 3, STATUS_MISSING: 4,
}


def dependency_paths(dependency_keys) -> list[Path]:
    out: list[Path] = []
    for dep in dependency_keys:
        src = DEPENDENCY_SOURCES.get(dep, dep)
        out.extend(_paths_in(src))
    return list(dict.fromkeys(out))


def spec_freshness(spec) -> dict:
    """Freshness of a visual: driven by its WORST (oldest/most-broken) input.

    Returns dict(status, badge, age_days, as_of, detail) where status is the
    worst across all resolved dependency files. Visuals whose data_dependency is
    just the visual_id (cockpit generation) resolve via data_source instead.
    """
    paths = dependency_paths(spec.data_dependency)
    if not paths:
        # cockpit-style spec: dependency is the visual_id; use data_source string
        paths = _paths_in(getattr(spec, "data_source", ""))
    if not paths:
        return {"status": STATUS_UNKNOWN, "badge": _BADGE[STATUS_UNKNOWN],
                "age_days": None, "as_of": None, "detail": "no resolvable data source"}

    worst = None
    per = []
    for p in paths:
        age, status, as_of = _path_age(p)
        per.append((p, age, status, as_of))
        if worst is None or _STATUS_RANK[status] > _STATUS_RANK[worst[2]]:
            worst = (p, age, status, as_of)
    _, age, status, as_of = worst
    # Name the offending file for stale/missing so the operator knows what to fix.
    detail = ""
    if status in (STATUS_STALE, STATUS_MISSING):
        try:
            detail = str(worst[0].relative_to(PROJECT_ROOT))
        except Exception:
            detail = str(worst[0])
    return {
        "status": status,
        "badge": _BADGE.get(status, "⚪"),
        "age_days": age,
        "as_of": as_of,
        "detail": detail,
    }


def badge_html(fresh: dict) -> str:
    """Small inline badge for a visual card header."""
    status = fresh["status"]
    if status == STATUS_MISSING:
        label = f"{fresh['badge']} data missing"
    elif fresh["as_of"]:
        age = fresh["age_days"]
        agestr = "today" if (age is not None and age <= 0) else (
            f"{int(age)}d old" if age is not None else "unknown age")
        label = f"{fresh['badge']} data as of {fresh['as_of']} ({agestr})"
    else:
        label = f"{fresh['badge']} freshness unknown"
    if fresh.get("detail"):
        label += f" · stale source: {fresh['detail']}"
    color = {"fresh": "#3fb950", "aging": "#d29922", "stale": "#f85149",
             "missing": "#f85149", "unknown": "#8b949e"}.get(status, "#8b949e")
    return f'<span class="ns-freshness-badge" style="color:{color};font-size:11px;">{label}</span>'
