#!/usr/bin/env python3
"""Normalize the repository data layout into canonical raw, results, runtime, testing, and archive roots."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.data_layout import (
    ANALYSIS_CLUSTERING_ROOT,
    ANALYSIS_RESULTS_ROOT,
    ARCHIVE_ANALYTICS_ROOT,
    ARCHIVE_DEMOS_ROOT,
    ARCHIVE_NEWS_ROOT,
    RAW_EXCHANGES_ROOT,
    RAW_SHARED_ROOT,
    RAW_VENDORS_ROOT,
    RESEARCH_ALPHA_FACTORY_ROOT,
    RESEARCH_CYCLES_ROOT,
    RESEARCH_EXPERIMENTS_ROOT,
    RESEARCH_FULL_STACK_RUNS_ROOT,
    RESEARCH_IC_DIAGNOSTICS_ROOT,
    RESEARCH_NIGHTLY_REPORTS_ROOT,
    RESEARCH_REGIME_IC_RUNS_ROOT,
    RESEARCH_REPORTS_ROOT,
    RESEARCH_RESULTS_ROOT,
    RESEARCH_SNAPSHOTS_ROOT,
    RESEARCH_STATE_ROOT,
    RESEARCH_TRACKERS_ROOT,
    RESEARCH_WEEKLY_REVIEWS_ROOT,
    RESULTS_ROOT,
    RUNTIME_AUTOMATION_ROOT,
    RUNTIME_FAILURES_ROOT,
    RUNTIME_QUARANTINE_ROOT,
    RUNTIME_RUNS_ROOT,
    TESTING_ROOT,
    ensure_directories,
    timestamp_partition_from_name,
)


RAW_MOVES = (
    ("data/raw/alternative/announcements_nse", "data/raw/exchanges/nse/alternative/announcements"),
    ("data/raw/alternative/bulk_deals_nse", "data/raw/exchanges/nse/alternative/bulk_deals"),
    ("data/raw/alternative/credit_ratings_nse", "data/raw/exchanges/nse/alternative/credit_ratings"),
    ("data/raw/alternative/promoter_pledge_nse", "data/raw/exchanges/nse/alternative/promoter_pledge"),
    ("data/raw/news_sentiment/nse", "data/raw/exchanges/nse/news_sentiment"),
    ("data/raw/alternative/bulk_deals", "data/raw/exchanges/bse/alternative/bulk_deals"),
    ("data/raw/alternative/order_announcements", "data/raw/exchanges/bse/alternative/order_announcements"),
    ("data/raw/alternative/promoter_pledge", "data/raw/exchanges/bse/alternative/promoter_pledge"),
    ("data/raw/news_sentiment/bse", "data/raw/exchanges/bse/news_sentiment"),
    ("data/raw/alternative/credit_ratings", "data/raw/shared/alternative/credit_ratings"),
    ("data/raw/alternative/earnings_dates", "data/raw/shared/alternative/earnings_dates"),
    ("data/raw/alternative/power_consumption", "data/raw/shared/alternative/power_consumption"),
    ("data/raw/alternative/power_yearly", "data/raw/shared/alternative/power_yearly"),
    ("data/raw/screener", "data/raw/vendors/screener"),
    ("data/raw/screener_delisted", "data/raw/vendors/screener_delisted"),
    ("data/raw/screener_delisted_smoke", "data/raw/vendors/screener_delisted_smoke"),
    ("data/raw/screener_smoke_test", "data/raw/vendors/screener_smoke_test"),
    ("data/raw/screener_smoke_test2", "data/raw/vendors/screener_smoke_test2"),
)


RESEARCH_ROOT_DIRS = {
    "alpha_factory": RESEARCH_ALPHA_FACTORY_ROOT,
    "experiments": RESEARCH_EXPERIMENTS_ROOT,
    "full_stack_runs": RESEARCH_FULL_STACK_RUNS_ROOT,
    "ic_diagnostics": RESEARCH_IC_DIAGNOSTICS_ROOT,
    "regime_ic_runs": RESEARCH_REGIME_IC_RUNS_ROOT,
    "weekly_reviews": RESEARCH_WEEKLY_REVIEWS_ROOT,
}

RESEARCH_TRACKER_NAMES = {
    "alpha_experience_memory.db",
    "experiments.ndjson",
    "strategy_signals.parquet",
}

RESEARCH_REPORT_PREFIX_MAP = {
    "formula_lineage": ("formula_lineage_and_unit_integrity_", "formula_lineage_and_unit_integrity"),
    "nightly": ("northstar_report_",),
    "regime_ic": ("regime_ic_", "regime_ic"),
}

RESEARCH_REPORT_RUN_PREFIXES = ("block", "next_alpha_", "robustness_", "run_", "signal_eng_")

STATE_FILE_PREFIX_MAP = {
    "research_cycle_": RESEARCH_CYCLES_ROOT,
    "research_snapshot_": RESEARCH_SNAPSHOTS_ROOT,
}

AUXILIARY_DIR_MOVES = (
    ("data/automation", RUNTIME_AUTOMATION_ROOT),
    ("data/clustering", ANALYSIS_CLUSTERING_ROOT),
    ("data/demo_shadow_fund_3m", ARCHIVE_DEMOS_ROOT / "shadow_fund_3m"),
    ("data/failures", RUNTIME_FAILURES_ROOT),
    ("data/greeks_history", ARCHIVE_ANALYTICS_ROOT / "greeks_history"),
    ("data/news_backup", ARCHIVE_NEWS_ROOT / "legacy_backup"),
    ("data/quarantine", RUNTIME_QUARANTINE_ROOT),
    ("data/regime_history", ARCHIVE_ANALYTICS_ROOT / "regime_history"),
    ("data/runs", RUNTIME_RUNS_ROOT),
)

AUXILIARY_FILE_MOVES = (
    ("data/regime_history.parquet", ARCHIVE_ANALYTICS_ROOT / "regime_history.parquet"),
)

TESTING_DIR_MOVES = (
    ("data/test_audit", TESTING_ROOT / "audit"),
    ("data/test_benchmark", TESTING_ROOT / "benchmark"),
    ("data/test_causality", TESTING_ROOT / "causality"),
    ("data/test_diagnostics", TESTING_ROOT / "diagnostics"),
    ("data/test_enhanced_validation", TESTING_ROOT / "enhanced_validation"),
    ("data/test_execution", TESTING_ROOT / "execution"),
    ("data/test_governance", TESTING_ROOT / "governance"),
    ("data/test_institutional_reports", TESTING_ROOT / "institutional_reports"),
    ("data/test_latency", TESTING_ROOT / "latency"),
    ("data/test_metadata", TESTING_ROOT / "metadata"),
    ("data/test_output", TESTING_ROOT / "output"),
    ("data/test_profile", TESTING_ROOT / "profile"),
    ("data/test_profile_quick", TESTING_ROOT / "profile_quick"),
    ("data/test_reports", TESTING_ROOT / "reports"),
    ("data/test_state", TESTING_ROOT / "state"),
)

EMPTY_TOP_LEVEL_DIRS = (
    "data/dcf_valuations",
    "data/positions",
)

TRASH_FILES = (
    "data/Users: 2.fileloc",
    "data/Users:.fileloc",
)


def _rel(path: str | Path) -> Path:
    return PROJECT_ROOT / Path(path)


def _is_symlink_to(path: Path, target: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        return path.resolve() == target.resolve()
    except FileNotFoundError:
        return False


def _merge_move(src: Path, dst: Path) -> None:
    if not src.exists() and not src.is_symlink():
        return
    if src.is_symlink():
        src.unlink()
        return
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if dst.is_dir():
                raise IsADirectoryError(f"cannot move file {src} into existing dir {dst}")
            if _files_identical(src, dst):
                src.unlink()
                return
            dst = _dedupe_destination(dst)
        shutil.move(str(src), str(dst))
        return

    dst.mkdir(parents=True, exist_ok=True)
    for child in list(src.iterdir()):
        _merge_move(child, dst / child.name)
    try:
        src.rmdir()
    except OSError:
        pass


def _files_identical(src: Path, dst: Path) -> bool:
    try:
        if src.stat().st_size != dst.stat().st_size:
            return False
        with src.open("rb") as src_handle, dst.open("rb") as dst_handle:
            while True:
                src_chunk = src_handle.read(8192)
                dst_chunk = dst_handle.read(8192)
                if src_chunk != dst_chunk:
                    return False
                if not src_chunk:
                    return True
    except Exception:
        return False


def _dedupe_destination(dst: Path) -> Path:
    counter = 1
    while True:
        candidate = dst.with_name(f"{dst.stem}__legacy{counter}{dst.suffix}")
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        counter += 1


def _ensure_symlink(link_path: Path, target_path: Path) -> None:
    if _is_symlink_to(link_path, target_path):
        return
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_file() or link_path.is_symlink():
            link_path.unlink()
        elif link_path.is_dir():
            try:
                next(link_path.iterdir())
                return
            except StopIteration:
                link_path.rmdir()
    link_path.parent.mkdir(parents=True, exist_ok=True)
    relative_target = Path(os.path.relpath(target_path, start=link_path.parent))
    link_path.symlink_to(relative_target)


def _move_with_compat(src: Path, dst: Path) -> None:
    if not src.exists() and not src.is_symlink():
        return
    _merge_move(src, dst)
    _ensure_symlink(src, dst)


def _partitioned_target(root: Path, name: str) -> Path:
    partition = timestamp_partition_from_name(name)
    return (root / partition / name) if partition is not None else (root / name)


def _research_target_for_child(child: Path) -> Path:
    if child.name in RESEARCH_ROOT_DIRS:
        return RESEARCH_ROOT_DIRS[child.name]
    if child.name in RESEARCH_TRACKER_NAMES:
        return RESEARCH_TRACKERS_ROOT / child.name
    for prefix, root in STATE_FILE_PREFIX_MAP.items():
        if child.name.startswith(prefix):
            return _partitioned_target(root, child.name)
    return RESEARCH_STATE_ROOT / child.name


def _report_target_for_child(child: Path) -> Path:
    name = child.name
    if child.is_dir():
        if any(name.startswith(prefix) for prefix in RESEARCH_REPORT_RUN_PREFIXES):
            return RESEARCH_REPORTS_ROOT / "regime_ic" / name
        return RESEARCH_REPORTS_ROOT / name
    for subdir, prefixes in RESEARCH_REPORT_PREFIX_MAP.items():
        if any(name.startswith(prefix) for prefix in prefixes):
            return RESEARCH_REPORTS_ROOT / subdir / name
    return RESEARCH_REPORTS_ROOT / "misc" / name


def _migrate_report_tree(legacy_root: Path) -> None:
    if not legacy_root.exists() or legacy_root.is_symlink():
        return
    for child in list(legacy_root.iterdir()):
        _move_with_compat(child, _report_target_for_child(child))
    _remove_if_empty(legacy_root)


def _migrate_research_tree(legacy_root: Path) -> None:
    if not legacy_root.exists() or legacy_root.is_symlink():
        return
    for child in list(legacy_root.iterdir()):
        if child.name == "reports":
            _migrate_report_tree(child)
            continue
        _move_with_compat(child, _research_target_for_child(child))
    _remove_if_empty(legacy_root)


def _migrate_nightly_reports(legacy_root: Path) -> None:
    if not legacy_root.exists() or legacy_root.is_symlink():
        return
    for child in list(legacy_root.iterdir()):
        _merge_move(child, RESEARCH_NIGHTLY_REPORTS_ROOT / child.name)
    _remove_if_empty(legacy_root)


def _migrate_analysis_root(legacy_root: Path) -> None:
    if not legacy_root.exists() or legacy_root.is_symlink():
        return
    for child in list(legacy_root.iterdir()):
        _move_with_compat(child, ANALYSIS_RESULTS_ROOT / child.name)
    _remove_if_empty(legacy_root)


def _repartition_timestamped_files(root: Path, stem_prefix: str) -> None:
    if not root.exists():
        return
    for path in list(root.glob(f"{stem_prefix}*")):
        if not path.is_file():
            continue
        dst = _partitioned_target(root, path.name)
        if dst == path:
            continue
        _merge_move(path, dst)


def _remove_if_empty(path: Path) -> None:
    if not path.exists() or path.is_symlink():
        return
    if not path.is_dir():
        return
    try:
        path.rmdir()
    except OSError:
        pass


def _delete_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def migrate_raw_layout() -> None:
    ensure_directories((RAW_EXCHANGES_ROOT, RAW_SHARED_ROOT, RAW_VENDORS_ROOT))
    for src_rel, dst_rel in RAW_MOVES:
        src = _rel(src_rel)
        dst = _rel(dst_rel)
        if src.exists() or src.is_symlink():
            _move_with_compat(src, dst)


def migrate_research_layout() -> None:
    ensure_directories(
        (
            RESULTS_ROOT,
            RESEARCH_RESULTS_ROOT,
            RESEARCH_ALPHA_FACTORY_ROOT,
            RESEARCH_CYCLES_ROOT,
            RESEARCH_EXPERIMENTS_ROOT,
            RESEARCH_FULL_STACK_RUNS_ROOT,
            RESEARCH_IC_DIAGNOSTICS_ROOT,
            RESEARCH_REGIME_IC_RUNS_ROOT,
            RESEARCH_REPORTS_ROOT,
            RESEARCH_SNAPSHOTS_ROOT,
            RESEARCH_STATE_ROOT,
            RESEARCH_TRACKERS_ROOT,
            RESEARCH_WEEKLY_REVIEWS_ROOT,
            ANALYSIS_RESULTS_ROOT,
        )
    )

    _migrate_research_tree(_rel("data/research"))
    _migrate_report_tree(_rel("reports/research"))
    _migrate_nightly_reports(_rel("data/research_reports"))

    _repartition_timestamped_files(RESEARCH_ALPHA_FACTORY_ROOT, "alpha_factory_report_")
    _repartition_timestamped_files(RESEARCH_CYCLES_ROOT, "research_cycle_")
    _repartition_timestamped_files(RESEARCH_FULL_STACK_RUNS_ROOT, "full_stack_run_")
    _repartition_timestamped_files(RESEARCH_IC_DIAGNOSTICS_ROOT, "ic_report_")
    _repartition_timestamped_files(RESEARCH_SNAPSHOTS_ROOT, "research_snapshot_")
    _repartition_timestamped_files(RESEARCH_WEEKLY_REVIEWS_ROOT, "weekly_review_")


def migrate_analysis_layout() -> None:
    ensure_directories((ANALYSIS_RESULTS_ROOT,))
    _migrate_analysis_root(_rel("analysis_results"))


def migrate_auxiliary_layout() -> None:
    ensure_directories(
        (
            ANALYSIS_CLUSTERING_ROOT,
            ARCHIVE_ANALYTICS_ROOT,
            ARCHIVE_DEMOS_ROOT,
            ARCHIVE_NEWS_ROOT,
            RESEARCH_NIGHTLY_REPORTS_ROOT,
            RUNTIME_AUTOMATION_ROOT,
            RUNTIME_FAILURES_ROOT,
            RUNTIME_QUARANTINE_ROOT,
            RUNTIME_RUNS_ROOT,
            TESTING_ROOT,
        )
    )

    for src_rel, dst in AUXILIARY_DIR_MOVES:
        src = _rel(src_rel)
        if src.exists() or src.is_symlink():
            _merge_move(src, dst)

    for src_rel, dst in AUXILIARY_FILE_MOVES:
        src = _rel(src_rel)
        if src.exists() or src.is_symlink():
            _merge_move(src, dst)

    for src_rel, dst in TESTING_DIR_MOVES:
        src = _rel(src_rel)
        if src.exists() or src.is_symlink():
            _merge_move(src, dst)

    for path_rel in EMPTY_TOP_LEVEL_DIRS:
        _remove_if_empty(_rel(path_rel))

    for path_rel in TRASH_FILES:
        _delete_path(_rel(path_rel))


def run() -> None:
    migrate_raw_layout()
    migrate_research_layout()
    migrate_analysis_layout()
    migrate_auxiliary_layout()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
