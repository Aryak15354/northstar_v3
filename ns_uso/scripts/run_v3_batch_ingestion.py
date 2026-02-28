#!/usr/bin/env python3
"""
🧠 NS-USO V3 BATCH INGESTION (REAL-DATA ONLY)

This script is a strict bridge between the standalone NS-USO sentiment system
and Northstar V3. It DOES NOT fabricate or simulate sentiment.

Behavior:
- If real NS-USO export artifacts exist, they are copied into V3's
  `data/sentiment/v3/` directory.
- If no real artifacts are found, the script writes a small summary marker
  indicating "no data" and exits successfully (so the pipeline can continue).

Expected artifacts (from the NS-USO system):
- market_sentiment_india.parquet
- sector_narratives.parquet
- policy_context.json
- v3_sentiment_summary.json (optional)
- company_sentiment_trends.parquet (optional)
- event_company_impact.parquet (optional)
- weekend_top100_trending_companies.json (optional)
- weekend_top30_trending_companies.json (optional)

You can explicitly point to the NS-USO export directory with:
  NS_USO_EXPORT_DIR=/path/to/ns_uso/exports/v3
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from datetime import datetime


REQUIRED_FILES = [
    "market_sentiment_india.parquet",
    "sector_narratives.parquet",
    "policy_context.json",
]
OPTIONAL_FILES = [
    "v3_sentiment_summary.json",
    "company_sentiment_trends.parquet",
    "event_company_impact.parquet",
    "weekend_top100_trending_companies.json",
    "weekend_top30_trending_companies.json",
]


def _candidate_export_dirs() -> list[Path]:
    env_dir = os.environ.get("NS_USO_EXPORT_DIR") or os.environ.get("NS_USO_V3_EXPORT_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            Path("ns_uso/exports/v3"),
            Path("ns_uso/data/exports/v3"),
            Path("ns_uso/data/processed/v3"),
            Path("ns_uso/output/v3"),
            Path("ns_uso/data/v3"),
        ]
    )
    return candidates


def _find_export_dir() -> Path | None:
    for cand in _candidate_export_dirs():
        if not cand.exists():
            continue
        if all((cand / f).exists() for f in REQUIRED_FILES):
            return cand
    return None


def _write_summary(target_dir: Path, status: str, message: str) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    summary_path = target_dir / "v3_sentiment_summary.json"
    payload = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "status": status,
        "message": message,
        "data_available": status == "success",
    }
    with open(summary_path, "w") as f:
        json.dump(payload, f, indent=2)


def main() -> int:
    target_dir = Path("data/sentiment/v3")
    target_dir.mkdir(parents=True, exist_ok=True)

    export_dir = _find_export_dir()
    if export_dir is None:
        msg = (
            "No NS-USO export artifacts found. "
            "Set NS_USO_EXPORT_DIR or place files under ns_uso/exports/v3."
        )
        print(f"⚠️ {msg}")
        _write_summary(target_dir, "no_data", msg)
        return 0

    print(f"✅ NS-USO export directory: {export_dir}")

    # Copy required files
    copied_files = []
    for fname in REQUIRED_FILES + OPTIONAL_FILES:
        src = export_dir / fname
        if src.exists():
            shutil.copy2(src, target_dir / fname)
            copied_files.append(fname)
            print(f"   -> synced {fname}")

    summary_path = target_dir / "v3_sentiment_summary.json"
    if summary_path.exists():
        try:
            payload = json.loads(summary_path.read_text())
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        payload["status"] = "success"
        payload["data_available"] = True
        payload["message"] = f"Synced sentiment artifacts from {export_dir}"
        payload["timestamp"] = datetime.now().astimezone().isoformat()
        payload["ingestion_source_dir"] = str(export_dir)
        payload["ingested_files"] = copied_files
        with open(summary_path, "w") as f:
            json.dump(payload, f, indent=2)
    else:
        _write_summary(target_dir, "success", f"Synced sentiment artifacts from {export_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
