#!/usr/bin/env python3
"""
Shared report versioning helpers.

Before writing a "latest" report, move any existing file to an archive folder
so we keep full history and avoid silent overwrites.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union


PathLike = Union[str, Path]


def _as_path(path: PathLike) -> Path:
    return path if isinstance(path, Path) else Path(path)


def archive_existing_file(path: PathLike, archive_root: Optional[PathLike] = None) -> Optional[Path]:
    """
    Archive an existing file to timestamped history.

    Returns the archive file path if a move happened, else None.
    """
    src = _as_path(path)
    if not src.exists() or not src.is_file():
        return None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "".join(src.suffixes)
    stem = src.name[: -len(ext)] if ext else src.name

    if archive_root is None:
        base_archive = src.parent / "archive" / stem
    else:
        base_archive = _as_path(archive_root)

    base_archive.mkdir(parents=True, exist_ok=True)

    target = base_archive / f"{stem}_{stamp}{ext}"
    counter = 1
    while target.exists():
        target = base_archive / f"{stem}_{stamp}_{counter}{ext}"
        counter += 1

    shutil.move(str(src), str(target))
    return target


def write_json_with_archive(path: PathLike, payload: Any, archive_root: Optional[PathLike] = None) -> Path:
    """Archive existing file (if any), then write JSON payload."""
    target = _as_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    archive_existing_file(target, archive_root=archive_root)
    with target.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return target


def write_text_with_archive(path: PathLike, text: str, archive_root: Optional[PathLike] = None) -> Path:
    """Archive existing file (if any), then write text payload."""
    target = _as_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    archive_existing_file(target, archive_root=archive_root)
    target.write_text(text, encoding="utf-8")
    return target

