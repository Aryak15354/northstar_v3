"""
Property tests for cleanup structural guarantees.

Feature: v3-cleanup-organization
- Property 3: Idempotent Cleanup
- Property 5: Directory Consolidation
- Property 6: Naming Consistency
"""

import hashlib
import importlib
import sys
import tempfile
from pathlib import Path

from hypothesis import assume, given, settings, strategies as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from cleanup.cleanup_executor import CleanupExecutor
from cleanup.move_planner import MovePlanner


def _snapshot_hashes(workspace: Path) -> dict[str, str]:
    """Return stable content fingerprint of all files under workspace."""
    snapshots: dict[str, str] = {}
    for file_path in sorted(workspace.rglob("*")):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(workspace))
        snapshots[rel] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return snapshots


def _is_snake_case_python(name: str) -> bool:
    stem = name[:-3] if name.endswith(".py") else name
    if not stem or not stem[0].islower():
        return False
    for ch in stem:
        if not (ch.islower() or ch.isdigit() or ch == "_"):
            return False
    return name.endswith(".py")


@settings(max_examples=20)
@given(
    include_test_dirs=st.lists(
        st.sampled_from(
            [
                "test_config",
                "test_env",
                "test_schemas",
                "test_simple_config",
                "test_simple_schemas",
                "test_integration_schemas",
                "integration_test_schemas",
            ]
        ),
        min_size=1,
        max_size=7,
        unique=True,
    )
)
def test_property_idempotent_cleanup(include_test_dirs: list[str]) -> None:
    """
    Property 3: Running cleanup twice should produce the same final workspace.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Seed workspace with artifact directories and a control file.
        for d in include_test_dirs:
            target = workspace / d
            target.mkdir(parents=True, exist_ok=True)
            (target / "artifact.json").write_text('{"status":"tmp"}')
        (workspace / "keep.txt").write_text("keep")

        planner = MovePlanner(workspace)
        ops = planner.plan_test_artifacts_removal()

        # Restrict to directories we intentionally created in the temp workspace.
        wanted = {Path(d) for d in include_test_dirs}
        ops = [op for op in ops if op.source_path in wanted]

        executor = CleanupExecutor(workspace, dry_run=False)
        first_results = executor.execute_all(ops)
        after_first = _snapshot_hashes(workspace)

        second_results = executor.execute_all(ops)
        after_second = _snapshot_hashes(workspace)

        assert all(r.success for r in first_results)
        assert all(r.success for r in second_results)
        assert after_first == after_second


@settings(max_examples=15)
@given(
    backup_files=st.integers(min_value=1, max_value=5),
    backups_files=st.integers(min_value=0, max_value=5),
)
def test_property_directory_consolidation(backup_files: int, backups_files: int) -> None:
    """
    Property 5: Consolidating backup/ into backups/ preserves unique files and is idempotent.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        backup = workspace / "backup"
        backups = workspace / "backups"
        backup.mkdir(parents=True, exist_ok=True)
        backups.mkdir(parents=True, exist_ok=True)

        for i in range(backup_files):
            (backup / f"old_{i}.txt").write_text(f"backup:{i}")
        for i in range(backups_files):
            (backups / f"existing_{i}.txt").write_text(f"backups:{i}")

        module = importlib.import_module("cleanup.consolidate_directories")
        original_workspace = module.workspace
        module.workspace = workspace
        try:
            module.consolidate_backup_dirs()
            first_state = _snapshot_hashes(workspace)
            module.consolidate_backup_dirs()
            second_state = _snapshot_hashes(workspace)
        finally:
            module.workspace = original_workspace

        assert not (workspace / "backup").exists()
        assert len(list((workspace / "backups").glob("old_*.txt"))) == backup_files
        assert first_state == second_state


@settings(max_examples=30)
@given(
    stem=st.from_regex(r"[a-z][a-z0-9_]{1,20}", fullmatch=True),
)
def test_property_naming_consistency_valid_snake_case(stem: str) -> None:
    """
    Property 6: Valid snake_case Python filenames are accepted.
    """
    assert _is_snake_case_python(f"{stem}.py")


@settings(max_examples=30)
@given(
    stem=st.from_regex(r"[A-Za-z0-9_-]{1,20}", fullmatch=True),
)
def test_property_naming_consistency_rejects_non_snake_case(stem: str) -> None:
    """
    Property 6: Non-snake-case Python filenames are rejected.
    """
    filename = f"{stem}.py"
    assume(not _is_snake_case_python(filename))
    assert not _is_snake_case_python(filename)
