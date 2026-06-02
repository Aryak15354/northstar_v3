#!/usr/bin/env python3
"""
Clean and normalize data/options layout without touching active core artifacts.

Actions:
1) Prune `data/options/chains_cache` to keep latest N files per underlying.
2) Archive old Groww manifest snapshots under `data/options/historical/_manifests/*`.
3) Remove `.empty` resume markers (checkpoint noise only).

Dry-run by default.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
OPTIONS_DIR = ROOT / "data" / "options"
HIST_DIR = OPTIONS_DIR / "historical"
CHAINS_CACHE = OPTIONS_DIR / "chains_cache"


_CACHE_RE = re.compile(r"^(?P<symbol>[A-Za-z0-9_-]+)_(?P<d>\d{8})_(?P<t>\d{6})\.parquet$")


@dataclass
class Stats:
    pruned_cache_files: int = 0
    archived_manifests: int = 0
    removed_empty_markers: int = 0


def _iter_cache_groups(cache_dir: Path) -> Dict[str, List[Tuple[str, Path]]]:
    out: Dict[str, List[Tuple[str, Path]]] = {}
    if not cache_dir.exists():
        return out
    for p in cache_dir.glob("*.parquet"):
        m = _CACHE_RE.match(p.name)
        if not m:
            continue
        symbol = m.group("symbol").upper()
        stamp = f"{m.group('d')}_{m.group('t')}"
        out.setdefault(symbol, []).append((stamp, p))
    for symbol, rows in out.items():
        rows.sort(key=lambda x: x[0], reverse=True)
        out[symbol] = rows
    return out


def _prune_chains_cache(cache_dir: Path, keep_per_underlying: int, apply: bool, stats: Stats) -> None:
    groups = _iter_cache_groups(cache_dir)
    for symbol, rows in groups.items():
        stale = rows[max(0, int(keep_per_underlying)) :]
        for _, p in stale:
            if apply:
                try:
                    p.unlink(missing_ok=True)
                    stats.pruned_cache_files += 1
                except Exception:
                    continue
            else:
                stats.pruned_cache_files += 1


def _archive_manifests(hist_dir: Path, keep_recent: int, apply: bool, stats: Stats) -> None:
    roots = [
        (hist_dir, "1d"),
        (hist_dir / "1w", "1w"),
        (hist_dir / "5m", "5m"),
    ]
    for base, tag in roots:
        if not base.exists():
            continue
        files = sorted(base.glob("groww_universe_manifest_*.json"), reverse=True)
        if not files:
            continue
        # Keep latest + requested retention.
        keep_set = {f.name for f in files[: max(1, int(keep_recent))]}
        latest = base / "groww_universe_manifest_latest.json"
        if latest.exists():
            keep_set.add(latest.name)

        archive_dir = hist_dir / "_manifests" / tag
        if apply:
            archive_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            if f.name in keep_set:
                continue
            if apply:
                target = archive_dir / f.name
                try:
                    f.replace(target)
                    stats.archived_manifests += 1
                except Exception:
                    continue
            else:
                stats.archived_manifests += 1


def _remove_empty_markers(hist_dir: Path, apply: bool, stats: Stats) -> None:
    if not hist_dir.exists():
        return
    for p in hist_dir.rglob("*.empty"):
        if apply:
            try:
                p.unlink(missing_ok=True)
                stats.removed_empty_markers += 1
            except Exception:
                continue
        else:
            stats.removed_empty_markers += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean data/options clutter safely")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--chains-keep-per-underlying", type=int, default=4)
    parser.add_argument("--keep-manifests", type=int, default=12, help="Keep this many most recent manifest snapshots per interval")
    parser.add_argument("--skip-empty-marker-cleanup", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stats = Stats()

    _prune_chains_cache(
        cache_dir=CHAINS_CACHE,
        keep_per_underlying=max(1, int(args.chains_keep_per_underlying)),
        apply=bool(args.apply),
        stats=stats,
    )
    _archive_manifests(
        hist_dir=HIST_DIR,
        keep_recent=max(1, int(args.keep_manifests)),
        apply=bool(args.apply),
        stats=stats,
    )
    if not args.skip_empty_marker_cleanup:
        _remove_empty_markers(HIST_DIR, apply=bool(args.apply), stats=stats)

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"[{mode}] chains_cache_pruned={stats.pruned_cache_files}")
    print(f"[{mode}] manifests_archived={stats.archived_manifests}")
    print(f"[{mode}] empty_markers_removed={stats.removed_empty_markers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

