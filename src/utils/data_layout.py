"""Canonical repository layout helpers for raw datasets and result artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional


RAW_ROOT = Path("data/raw")
RAW_EXCHANGES_ROOT = RAW_ROOT / "exchanges"
RAW_SHARED_ROOT = RAW_ROOT / "shared"
RAW_VENDORS_ROOT = RAW_ROOT / "vendors"

RUNTIME_ROOT = Path("data/runtime")
RUNTIME_AUTOMATION_ROOT = RUNTIME_ROOT / "automation"
RUNTIME_FAILURES_ROOT = RUNTIME_ROOT / "failures"
RUNTIME_QUARANTINE_ROOT = RUNTIME_ROOT / "quarantine"
RUNTIME_RUNS_ROOT = RUNTIME_ROOT / "runs"

TESTING_ROOT = Path("data/testing")

ARCHIVE_ROOT = Path("data/archive")
ARCHIVE_ANALYTICS_ROOT = ARCHIVE_ROOT / "analytics"
ARCHIVE_DEMOS_ROOT = ARCHIVE_ROOT / "demos"
ARCHIVE_NEWS_ROOT = ARCHIVE_ROOT / "news"

RESULTS_ROOT = Path("data/results")
RESEARCH_RESULTS_ROOT = RESULTS_ROOT / "research"
RESEARCH_STATE_ROOT = RESEARCH_RESULTS_ROOT / "state"
RESEARCH_CYCLES_ROOT = RESEARCH_RESULTS_ROOT / "cycles"
RESEARCH_SNAPSHOTS_ROOT = RESEARCH_RESULTS_ROOT / "snapshots"
RESEARCH_TRACKERS_ROOT = RESEARCH_RESULTS_ROOT / "trackers"
RESEARCH_REPORTS_ROOT = RESEARCH_RESULTS_ROOT / "reports"
RESEARCH_NIGHTLY_REPORTS_ROOT = RESEARCH_REPORTS_ROOT / "nightly"
RESEARCH_ALPHA_FACTORY_ROOT = RESEARCH_RESULTS_ROOT / "alpha_factory"
RESEARCH_EXPERIMENTS_ROOT = RESEARCH_RESULTS_ROOT / "experiments"
RESEARCH_FULL_STACK_RUNS_ROOT = RESEARCH_RESULTS_ROOT / "full_stack_runs"
RESEARCH_IC_DIAGNOSTICS_ROOT = RESEARCH_RESULTS_ROOT / "ic_diagnostics"
RESEARCH_REGIME_IC_RUNS_ROOT = RESEARCH_RESULTS_ROOT / "regime_ic_runs"
RESEARCH_WEEKLY_REVIEWS_ROOT = RESEARCH_RESULTS_ROOT / "weekly_reviews"
ANALYSIS_RESULTS_ROOT = RESULTS_ROOT / "analysis"
ANALYSIS_CLUSTERING_ROOT = ANALYSIS_RESULTS_ROOT / "clustering"

_TS_RE = re.compile(r"(?P<date>\d{8})(?:_(?P<time>\d{6}))?")


def exchange_raw_dir(exchange: str, *parts: str) -> Path:
    return RAW_EXCHANGES_ROOT / str(exchange).lower() / Path(*parts)


def shared_raw_dir(*parts: str) -> Path:
    return RAW_SHARED_ROOT / Path(*parts)


def vendor_raw_dir(vendor: str, *parts: str) -> Path:
    return RAW_VENDORS_ROOT / str(vendor).lower() / Path(*parts)


def runtime_dir(*parts: str) -> Path:
    return RUNTIME_ROOT / Path(*parts)


def testing_dir(*parts: str) -> Path:
    return TESTING_ROOT / Path(*parts)


def archive_dir(*parts: str) -> Path:
    return ARCHIVE_ROOT / Path(*parts)


def research_state_file(name: str) -> Path:
    return RESEARCH_STATE_ROOT / name


def research_cycle_dir(*parts: str) -> Path:
    return RESEARCH_CYCLES_ROOT / Path(*parts)


def research_snapshot_dir(*parts: str) -> Path:
    return RESEARCH_SNAPSHOTS_ROOT / Path(*parts)


def research_tracker_file(name: str) -> Path:
    return RESEARCH_TRACKERS_ROOT / name


def research_report_dir(*parts: str) -> Path:
    return RESEARCH_REPORTS_ROOT / Path(*parts)


def analysis_result_dir(*parts: str) -> Path:
    return ANALYSIS_RESULTS_ROOT / Path(*parts)


def timestamp_partition_from_name(name: str) -> Optional[Path]:
    match = _TS_RE.search(str(name))
    if not match:
        return None
    date_token = match.group("date")
    return Path(date_token[:4]) / date_token[4:6]


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
