#!/usr/bin/env python3
"""Daily local backup tool for Northstar critical state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import fcntl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [
    PROJECT_ROOT / "data/options",
    PROJECT_ROOT / "data/model_registry",
    PROJECT_ROOT / "data/research",
]


@dataclass
class BackupStats:
    files: int = 0
    bytes: int = 0


def _estimate_tree_size(src: Path) -> BackupStats:
    stats = BackupStats()
    if not src.exists():
        return stats
    for root, _dirs, files in os.walk(src):
        root_path = Path(root)
        for name in files:
            src_file = root_path / name
            stats.files += 1
            try:
                stats.bytes += int(src_file.stat().st_size)
            except Exception:
                continue
    return stats


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _copy_tree(src: Path, dst: Path) -> BackupStats:
    stats = BackupStats()
    if not src.exists():
        return stats
    dst.mkdir(parents=True, exist_ok=True)
    for root, _dirs, files in os.walk(src):
        root_path = Path(root)
        rel_root = root_path.relative_to(src)
        target_root = dst / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        for name in files:
            src_file = root_path / name
            dst_file = target_root / name
            shutil.copy2(src_file, dst_file)
            stats.files += 1
            try:
                stats.bytes += int(src_file.stat().st_size)
            except Exception:
                pass
    return stats


def _critical_file_checksums(base: Path) -> Dict[str, str]:
    paths = [
        base / "data/options/live/options_runtime_state.json",
        base / "data/options/live/options_runtime_state.json.sha256",
        base / "data/options/trade_ledger.parquet",
        base / "data/options/live/write_journal.log",
        base / "data/options/live/governance_events.parquet",
        base / "data/model_registry/registry.json",
        base / "data/model_registry/production.json",
    ]
    out: Dict[str, str] = {}
    for path in paths:
        if path.exists() and path.is_file():
            try:
                out[str(path.relative_to(base))] = _sha256(path)
            except Exception:
                continue
    return out


def _prune_old_snapshots(snapshots_dir: Path, retention_days: int) -> List[str]:
    removed: List[str] = []
    cutoff = datetime.now() - timedelta(days=max(1, int(retention_days)))
    for child in sorted(snapshots_dir.iterdir()):
        if not child.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(child.stat().st_mtime)
            if mtime < cutoff:
                shutil.rmtree(child)
                removed.append(child.name)
        except Exception:
            continue
    return removed


def run_backup(destination_root: Path, retention_days: int, verify: bool) -> Dict[str, object]:
    destination_root.mkdir(parents=True, exist_ok=True)
    external_target = str(destination_root).startswith("/Volumes/")
    lock_path = destination_root / ".backup.lock"
    lock_fh = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fh.close()
        raise RuntimeError(f"Backup lock held: {lock_path}")

    try:
        source_estimate = BackupStats()
        for src in SOURCE_DIRS:
            stats = _estimate_tree_size(src)
            source_estimate.files += stats.files
            source_estimate.bytes += stats.bytes
        usage = shutil.disk_usage(destination_root)
        required_bytes = int(source_estimate.bytes * 1.10) + (200 * 1024 * 1024)
        if usage.free < required_bytes:
            raise RuntimeError(
                "Insufficient backup disk space: "
                f"free={usage.free} required~={required_bytes}"
            )

        snapshot_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshots_dir = destination_root / "snapshots"
        snapshot_dir = snapshots_dir / snapshot_name
        staging_dir = destination_root / f".staging_{snapshot_name}"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        totals = BackupStats()
        copied = {}
        for src in SOURCE_DIRS:
            dst = staging_dir / str(src.relative_to(PROJECT_ROOT))
            stats = _copy_tree(src, dst)
            copied[str(src.relative_to(PROJECT_ROOT))] = {"files": stats.files, "bytes": stats.bytes}
            totals.files += stats.files
            totals.bytes += stats.bytes

        manifest = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(PROJECT_ROOT),
            "snapshot_name": snapshot_name,
            "copied": copied,
            "totals": {"files": totals.files, "bytes": totals.bytes},
            "source_estimate": {"files": source_estimate.files, "bytes": source_estimate.bytes},
            "destination_disk": {"free_bytes": usage.free, "total_bytes": usage.total},
            "external_target": external_target,
            "source_checksums": _critical_file_checksums(PROJECT_ROOT),
        }
        manifest_path = staging_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

        staging_dir.replace(snapshot_dir)

        verify_status = {"enabled": verify, "ok": True, "errors": []}
        if verify:
            for rel, checksum in manifest["source_checksums"].items():
                backup_file = snapshot_dir / rel
                if not backup_file.exists():
                    verify_status["ok"] = False
                    verify_status["errors"].append(f"missing:{rel}")
                    continue
                backup_checksum = _sha256(backup_file)
                if backup_checksum != checksum:
                    verify_status["ok"] = False
                    verify_status["errors"].append(f"checksum_mismatch:{rel}")

        removed = _prune_old_snapshots(snapshots_dir, retention_days=retention_days)

        latest_ptr = destination_root / "latest.json"
        latest_payload = {
            "timestamp": datetime.now().isoformat(),
            "snapshot": str(snapshot_dir),
            "manifest": str(snapshot_dir / "manifest.json"),
            "verify": verify_status,
        }
        tmp_latest = latest_ptr.with_suffix(".tmp")
        with open(tmp_latest, "w", encoding="utf-8") as handle:
            json.dump(latest_payload, handle, indent=2)
        tmp_latest.replace(latest_ptr)

        warnings: List[str] = []
        if not external_target:
            warnings.append(
                "Backup destination is not on /Volumes; use external SSD for single-machine resilience."
            )

        return {
            "status": "ok" if verify_status["ok"] else "verify_failed",
            "destination": str(snapshot_dir),
            "manifest": str(snapshot_dir / "manifest.json"),
            "files_copied": totals.files,
            "bytes_copied": totals.bytes,
            "verify": verify_status,
            "pruned_snapshots": removed,
            "warnings": warnings,
        }
    finally:
        try:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        lock_fh.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup Northstar critical local data")
    parser.add_argument(
        "--destination-root",
        type=Path,
        default=Path("/Volumes/NORTHSTAR_BACKUP/northstar_v3"),
        help="Backup root folder (external SSD recommended)",
    )
    parser.add_argument("--retention-days", type=int, default=21)
    parser.add_argument("--verify", action="store_true", help="Verify critical file checksums post-copy")
    args = parser.parse_args()

    try:
        result = run_backup(
            destination_root=args.destination_root,
            retention_days=args.retention_days,
            verify=bool(args.verify),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "ok" else 2
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
