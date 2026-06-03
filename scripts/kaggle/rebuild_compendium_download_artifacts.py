#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import shutil
import zipfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_DOWNLOADS_ROOT = Path.home() / "Downloads"
DEFAULT_BUNDLE_NAME = "kaggle_compendium_upload_bundle_20260408"
DEFAULT_WRAPPER_DIR = "northstar_compendium_selfcontained_sections_20260408"
DEFAULT_BUNDLE_DIR = "northstar_compendium_kaggle_bundle_20260408"

SECTION_TARGETS = [
    "run_section_legacy_01_08.py",
    "run_section_ratio_09_12.py",
    "run_section_sector_13_16.py",
    "run_section_regime_17_19.py",
    "run_section_redemption_20_23.py",
    "run_section_signal_24_25.py",
    "run_section_verification_26_27.py",
]

SYNC_DIRS = [
    "scripts/kaggle/plan_2026_04_05",
    "scripts/kaggle/plan_2026_04_08",
    "scripts/kaggle/plan_2026_04_08_sections",
    "scripts/kaggle/week_2026_03_29",
    "notebooks/kaggle_sprint/shared",
    "configs/plan_2026_04_05",
    "data/canonical/reference/regimes",
]


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _bundle_launcher(import_path: str) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parent
if str(BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(BUNDLE_ROOT))

from {import_path} import main


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _selfcontained_wrapper(bundle_dirname: str, target_script: str, archive_sha256: str, archive_b64: str) -> str:
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import os
import runpy
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ARCHIVE_SHA256 = '{archive_sha256}'
ARCHIVE_B64 = \"\"\"
{archive_b64}
\"\"\"
TARGET_SCRIPT = '{target_script}'
BUNDLE_DIRNAME = '{bundle_dirname}'


def _preferred_runtime_root() -> Path:
    env_value = str(os.environ.get('NORTHSTAR_COMPENDIUM_RUNTIME_ROOT', '') or '').strip()
    suffix = f"{{Path(TARGET_SCRIPT).stem}}_{{ARCHIVE_SHA256[:12]}}"
    if env_value:
        return Path(env_value) / suffix
    kaggle_root = Path('/kaggle/working')
    if kaggle_root.exists() and os.access(kaggle_root, os.W_OK):
        return kaggle_root / 'northstar_compendium_runtime' / suffix
    cwd = Path.cwd()
    if cwd.exists() and os.access(cwd, os.W_OK):
        return cwd / 'tmp' / 'northstar_compendium_runtime' / suffix
    return Path(tempfile.gettempdir()) / 'northstar_compendium_runtime' / suffix


def _materialize_bundle() -> Path:
    preferred_root = _preferred_runtime_root()
    preferred_root.mkdir(parents=True, exist_ok=True)
    bundle_root = preferred_root / BUNDLE_DIRNAME
    marker = preferred_root / '.archive_sha256'
    if bundle_root.exists() and marker.exists() and marker.read_text(encoding='utf-8').strip() == ARCHIVE_SHA256:
        return bundle_root
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    archive_bytes = base64.b64decode(ARCHIVE_B64.encode('ascii'))
    digest = hashlib.sha256(archive_bytes).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise RuntimeError(f'embedded_archive_hash_mismatch:{{digest}}!={{ARCHIVE_SHA256}}')
    with zipfile.ZipFile(io.BytesIO(archive_bytes), 'r') as handle:
        handle.extractall(preferred_root)
    marker.write_text(ARCHIVE_SHA256 + '\\n', encoding='utf-8')
    return bundle_root


def main() -> int:
    bundle_root = _materialize_bundle()
    if str(bundle_root) not in sys.path:
        sys.path.insert(0, str(bundle_root))
    script_path = bundle_root / TARGET_SCRIPT
    sys.argv[0] = str(script_path)
    runpy.run_path(str(script_path), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
"""


def _readme_text() -> str:
    lines = [
        "# Northstar Compendium Self-Contained Section Scripts",
        "",
        "Upload one section script at a time to Kaggle, attach the feature export dataset, and run the script directly.",
        "",
        "Section files:",
    ]
    for name in SECTION_TARGETS:
        lines.append(f"- `{name}`")
    lines.extend(
        [
            "",
            "These files already embed the matching runtime bundle. You do not need to upload the older support tree beside them.",
        ]
    )
    return "\n".join(lines) + "\n"


def _zip_directory(source_dir: Path, zip_path: Path, root_name: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir() or path.name == ".DS_Store" or "__pycache__" in path.parts:
                continue
            arcname = Path(root_name) / path.relative_to(source_dir)
            handle.write(path, arcname.as_posix())
    data = buffer.getvalue()
    zip_path.write_bytes(data)
    return data


def rebuild(downloads_root: Path, bundle_dir_name: str, bundle_zip_name: str, wrapper_dir_name: str, wrapper_zip_name: str) -> dict[str, Path]:
    bundle_dir = downloads_root / bundle_dir_name
    bundle_zip = downloads_root / bundle_zip_name
    wrapper_dir = downloads_root / wrapper_dir_name
    wrapper_zip = downloads_root / wrapper_zip_name

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    for rel_dir in SYNC_DIRS:
        src = PROJECT_ROOT / rel_dir
        dst = bundle_dir / rel_dir
        _copy_tree(src, dst)

    top_level_entries: list[tuple[str, str]] = []
    for path in sorted((PROJECT_ROOT / "scripts/kaggle/plan_2026_04_08").glob("run_exp*.py")):
        top_level_entries.append((path.name, f"scripts.kaggle.plan_2026_04_08.{path.stem}"))
    for path in sorted((PROJECT_ROOT / "scripts/kaggle/plan_2026_04_08_sections").glob("run_section_*.py")):
        top_level_entries.append((path.name, f"scripts.kaggle.plan_2026_04_08_sections.{path.stem}"))

    for filename, import_path in top_level_entries:
        _write_text(bundle_dir / filename, _bundle_launcher(import_path))

    _write_text(
        bundle_dir / "README_UPLOAD_ORDER.md",
        "\n".join(
            [
                "# Kaggle Upload Order",
                "",
                "Run these section scripts one at a time after attaching the augmented feature export dataset:",
                "",
                *[f"- `{name}`" for name in SECTION_TARGETS],
                "",
            ]
        ),
    )

    if wrapper_dir.exists():
        shutil.rmtree(wrapper_dir)
    wrapper_dir.mkdir(parents=True, exist_ok=True)

    runtime_bundle_name = DEFAULT_BUNDLE_NAME
    archive_bytes = _zip_directory(bundle_dir, bundle_zip, runtime_bundle_name)
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    archive_b64 = base64.encodebytes(archive_bytes).decode("ascii")

    for target_script in SECTION_TARGETS:
        wrapper_text = _selfcontained_wrapper(
            bundle_dirname=runtime_bundle_name,
            target_script=target_script,
            archive_sha256=archive_sha256,
            archive_b64=archive_b64,
        )
        wrapper_path = wrapper_dir / target_script
        _write_text(wrapper_path, wrapper_text)
        wrapper_path.chmod(0o755)

    _write_text(wrapper_dir / "README_SELFCONTAINED.md", _readme_text())
    _zip_directory(wrapper_dir, wrapper_zip, wrapper_dir_name)

    return {
        "bundle_dir": bundle_dir,
        "bundle_zip": bundle_zip,
        "wrapper_dir": wrapper_dir,
        "wrapper_zip": wrapper_zip,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild Kaggle compendium bundle and self-contained section scripts in Downloads.")
    parser.add_argument("--downloads-root", type=Path, default=DEFAULT_DOWNLOADS_ROOT)
    parser.add_argument("--bundle-dir-name", default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--bundle-zip-name", default=f"{DEFAULT_BUNDLE_NAME}.zip")
    parser.add_argument("--wrapper-dir-name", default=DEFAULT_WRAPPER_DIR)
    parser.add_argument("--wrapper-zip-name", default=f"{DEFAULT_WRAPPER_DIR}.zip")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = rebuild(
        downloads_root=args.downloads_root,
        bundle_dir_name=args.bundle_dir_name,
        bundle_zip_name=args.bundle_zip_name,
        wrapper_dir_name=args.wrapper_dir_name,
        wrapper_zip_name=args.wrapper_zip_name,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
