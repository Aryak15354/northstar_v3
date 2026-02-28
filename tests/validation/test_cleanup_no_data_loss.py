"""
Property test for cleanup operations: No Data Loss
Validates that cleanup operations preserve all unique file content.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from hypothesis import given, strategies as st, settings
import hashlib

# Import cleanup infrastructure
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from cleanup.file_analyzer import FileAnalyzer
from cleanup.move_planner import MovePlanner, OperationType
from cleanup.cleanup_executor import CleanupExecutor


def compute_workspace_hashes(workspace: Path) -> set:
    """Compute hashes of all files in workspace"""
    hashes = set()
    for file_path in workspace.rglob("*"):
        if file_path.is_file():
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    hashes.add(file_hash)
            except Exception:
                pass
    return hashes


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create some test files
        (workspace / "test1.txt").write_text("content1")
        (workspace / "test2.txt").write_text("content2")
        (workspace / "subdir").mkdir()
        (workspace / "subdir" / "test3.txt").write_text("content3")
        
        yield workspace


def test_no_data_loss_on_move(temp_workspace):
    """
    Property 1: No Data Loss
    For any cleanup operation, all unique file content should be preserved.
    """
    # Get initial hashes
    initial_hashes = compute_workspace_hashes(temp_workspace)
    
    # Create executor and perform moves
    executor = CleanupExecutor(temp_workspace, dry_run=False)
    
    # Create a simple move operation
    from cleanup.move_planner import MoveOperation
    operations = [
        MoveOperation(
            source_path=Path("test1.txt"),
            dest_path=Path("moved/test1.txt"),
            operation_type=OperationType.MOVE,
            affected_imports=[],
            reason="Test move"
        )
    ]
    
    # Execute
    results = executor.execute_all(operations)
    
    # Get final hashes
    final_hashes = compute_workspace_hashes(temp_workspace)
    
    # Verify: all initial hashes should still exist
    assert initial_hashes.issubset(final_hashes), \
        "Data loss detected: some file content disappeared after move"


def test_no_data_loss_with_backup(temp_workspace):
    """
    Property 1: No Data Loss (with backup)
    Backup should contain all files that will be modified.
    """
    # Get initial hashes
    initial_hashes = compute_workspace_hashes(temp_workspace)
    
    # Create executor
    executor = CleanupExecutor(temp_workspace, dry_run=False)
    
    # Create backup
    backup_path = executor.create_backup()
    
    # Verify backup contains all content
    backup_hashes = compute_workspace_hashes(backup_path)
    
    # All initial content should be in backup
    assert initial_hashes.issubset(backup_hashes), \
        "Backup incomplete: missing some file content"


def test_no_data_loss_on_delete_with_backup(temp_workspace):
    """
    Property 1: No Data Loss (delete with backup)
    Even delete operations preserve data in backup.
    """
    # Create executor and backup
    executor = CleanupExecutor(temp_workspace, dry_run=False)
    backup_path = executor.create_backup()
    
    # Get initial hashes
    initial_hashes = compute_workspace_hashes(temp_workspace)
    
    # Delete a file
    from cleanup.move_planner import MoveOperation
    operations = [
        MoveOperation(
            source_path=Path("test1.txt"),
            dest_path=Path(""),
            operation_type=OperationType.DELETE,
            affected_imports=[],
            reason="Test delete"
        )
    ]
    
    executor.execute_all(operations)
    
    # Verify content still exists in backup
    backup_hashes = compute_workspace_hashes(backup_path)
    assert initial_hashes.issubset(backup_hashes), \
        "Data loss: deleted content not preserved in backup"


@settings(max_examples=10)  # Run 10 iterations
@given(
    num_files=st.integers(min_value=1, max_value=5),
    num_moves=st.integers(min_value=1, max_value=3)
)
def test_property_no_data_loss_random(num_files, num_moves):
    """
    Property 1: No Data Loss (randomized)
    For any set of move operations, content hashes are preserved.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create random files
        initial_hashes = set()
        for i in range(num_files):
            file_path = workspace / f"file_{i}.txt"
            content = f"content_{i}"
            file_path.write_text(content)
            initial_hashes.add(hashlib.sha256(content.encode()).hexdigest())
        
        # Create random move operations
        executor = CleanupExecutor(workspace, dry_run=False)
        from cleanup.move_planner import MoveOperation
        
        operations = []
        for i in range(min(num_moves, num_files)):
            operations.append(MoveOperation(
                source_path=Path(f"file_{i}.txt"),
                dest_path=Path(f"moved/file_{i}.txt"),
                operation_type=OperationType.MOVE,
                affected_imports=[],
                reason="Random test"
            ))
        
        # Execute
        executor.execute_all(operations)
        
        # Verify hashes preserved
        final_hashes = compute_workspace_hashes(workspace)
        assert initial_hashes.issubset(final_hashes), \
            f"Data loss in random test: {initial_hashes - final_hashes}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
