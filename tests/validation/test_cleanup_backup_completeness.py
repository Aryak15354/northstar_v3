"""
Property Test: Backup Completeness
Validates that backups capture all necessary data for rollback.

Property 4: Backup Completeness
- All files in workspace are included in backup
- Backup preserves file contents exactly
- Backup preserves directory structure
- Backup can be used to restore workspace
"""
import sys
from pathlib import Path
from hypothesis import given, strategies as st, settings
from hypothesis import Phase
import tempfile
import shutil
import hashlib

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_workspace_structure(base_dir: Path, num_files: int, num_dirs: int):
    """Create a test workspace with files and directories"""
    files_created = []
    
    # Create directories
    dirs = []
    for i in range(num_dirs):
        dir_path = base_dir / f"dir_{i}"
        dir_path.mkdir(exist_ok=True)
        dirs.append(dir_path)
    
    # Create files in base and subdirectories
    for i in range(num_files):
        if dirs and i % 2 == 0:
            # Put some files in subdirectories
            parent = dirs[i % len(dirs)]
        else:
            parent = base_dir
        
        file_path = parent / f"file_{i}.txt"
        content = f"Content of file {i}\n" * (i + 1)
        file_path.write_text(content)
        files_created.append(file_path)
    
    return files_created


def backup_workspace(source: Path, backup: Path):
    """Create a backup of the workspace"""
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(source, backup, dirs_exist_ok=True)


def restore_workspace(backup: Path, target: Path):
    """Restore workspace from backup"""
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(backup, target, dirs_exist_ok=True)


@given(
    num_files=st.integers(min_value=1, max_value=10),
    num_dirs=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_backup_includes_all_files(num_files: int, num_dirs: int):
    """
    Property: Backup includes all files from workspace
    
    Given:
    - A workspace with files and directories
    
    When:
    - A backup is created
    
    Then:
    - All files are present in backup
    - File count matches exactly
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        backup_dir = temp_path / "backup"
        
        workspace.mkdir()
        
        # Create workspace structure
        files = create_workspace_structure(workspace, num_files, num_dirs)
        
        # Create backup
        backup_workspace(workspace, backup_dir)
        
        # Count files in original
        original_files = list(workspace.rglob("*"))
        original_file_count = len([f for f in original_files if f.is_file()])
        
        # Count files in backup
        backup_files = list(backup_dir.rglob("*"))
        backup_file_count = len([f for f in backup_files if f.is_file()])
        
        # Property: File counts match
        assert original_file_count == backup_file_count, \
            f"Backup should contain all files: {original_file_count} != {backup_file_count}"
        
        # Property: All original files exist in backup
        for orig_file in original_files:
            if orig_file.is_file():
                rel_path = orig_file.relative_to(workspace)
                backup_file = backup_dir / rel_path
                assert backup_file.exists(), \
                    f"File {rel_path} should exist in backup"


@given(
    num_files=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_backup_preserves_content(num_files: int):
    """
    Property: Backup preserves file contents exactly
    
    Given:
    - A workspace with files containing data
    
    When:
    - A backup is created
    
    Then:
    - All file contents match exactly (byte-for-byte)
    - File hashes are identical
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        backup_dir = temp_path / "backup"
        
        workspace.mkdir()
        
        # Create files with content
        files = create_workspace_structure(workspace, num_files, 2)
        
        # Calculate hashes before backup
        original_hashes = {}
        for file_path in files:
            if file_path.is_file():
                rel_path = file_path.relative_to(workspace)
                original_hashes[str(rel_path)] = calculate_file_hash(file_path)
        
        # Create backup
        backup_workspace(workspace, backup_dir)
        
        # Calculate hashes after backup
        for rel_path_str, original_hash in original_hashes.items():
            backup_file = backup_dir / rel_path_str
            backup_hash = calculate_file_hash(backup_file)
            
            # Property: Content hashes match
            assert original_hash == backup_hash, \
                f"File {rel_path_str} content should be preserved exactly"


@given(
    num_files=st.integers(min_value=2, max_value=8),
    num_dirs=st.integers(min_value=1, max_value=4)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_backup_preserves_structure(num_files: int, num_dirs: int):
    """
    Property: Backup preserves directory structure
    
    Given:
    - A workspace with nested directories
    
    When:
    - A backup is created
    
    Then:
    - Directory structure is preserved
    - Relative paths are maintained
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        backup_dir = temp_path / "backup"
        
        workspace.mkdir()
        
        # Create workspace with structure
        create_workspace_structure(workspace, num_files, num_dirs)
        
        # Get original structure
        original_dirs = [d.relative_to(workspace) for d in workspace.rglob("*") if d.is_dir()]
        
        # Create backup
        backup_workspace(workspace, backup_dir)
        
        # Get backup structure
        backup_dirs = [d.relative_to(backup_dir) for d in backup_dir.rglob("*") if d.is_dir()]
        
        # Property: Directory structure matches
        assert set(original_dirs) == set(backup_dirs), \
            "Backup should preserve directory structure"


@given(
    num_files=st.integers(min_value=2, max_value=8)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_backup_enables_restoration(num_files: int):
    """
    Property: Backup can be used to restore workspace
    
    Given:
    - A workspace with files
    - A backup of that workspace
    
    When:
    - Workspace is modified
    - Workspace is restored from backup
    
    Then:
    - Restored workspace matches original exactly
    - All modifications are reverted
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        backup_dir = temp_path / "backup"
        
        workspace.mkdir()
        
        # Create original workspace
        files = create_workspace_structure(workspace, num_files, 2)
        
        # Calculate original hashes
        original_hashes = {}
        for file_path in workspace.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(workspace)
                original_hashes[str(rel_path)] = calculate_file_hash(file_path)
        
        # Create backup
        backup_workspace(workspace, backup_dir)
        
        # Modify workspace (simulate cleanup operations)
        for file_path in list(workspace.rglob("*.txt"))[:num_files // 2]:
            file_path.write_text("MODIFIED CONTENT")
        
        # Add a new file
        (workspace / "new_file.txt").write_text("New content")
        
        # Verify workspace was modified
        modified_count = len(list(workspace.rglob("*.txt")))
        assert modified_count != len(original_hashes), \
            "Workspace should be modified"
        
        # Restore from backup
        restore_workspace(backup_dir, workspace)
        
        # Verify restoration
        restored_hashes = {}
        for file_path in workspace.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(workspace)
                restored_hashes[str(rel_path)] = calculate_file_hash(file_path)
        
        # Property: Restored workspace matches original
        assert original_hashes == restored_hashes, \
            "Restored workspace should match original exactly"
        
        # Property: New file is removed
        assert not (workspace / "new_file.txt").exists(), \
            "Restoration should remove files added after backup"


def test_backup_completeness_property_validation():
    """
    Meta-test: Verify the property test itself is working correctly
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        backup_dir = temp_path / "backup"
        
        workspace.mkdir()
        
        # Create a simple file
        test_file = workspace / "test.txt"
        test_file.write_text("test content")
        
        # Create backup
        backup_workspace(workspace, backup_dir)
        
        # Verify backup exists
        assert (backup_dir / "test.txt").exists()
        
        # Verify content matches
        assert (backup_dir / "test.txt").read_text() == "test content"
        
        # Verify hash calculation works
        hash1 = calculate_file_hash(test_file)
        hash2 = calculate_file_hash(backup_dir / "test.txt")
        assert hash1 == hash2


if __name__ == "__main__":
    # Run meta-test first
    print("Running meta-test...")
    test_backup_completeness_property_validation()
    print("✓ Meta-test passed")
    
    # Run property tests
    print("\nRunning property tests...")
    print("Test 1: Backup includes all files...")
    test_backup_includes_all_files()
    print("✓ Test 1 passed")
    
    print("Test 2: Backup preserves content...")
    test_backup_preserves_content()
    print("✓ Test 2 passed")
    
    print("Test 3: Backup preserves structure...")
    test_backup_preserves_structure()
    print("✓ Test 3 passed")
    
    print("Test 4: Backup enables restoration...")
    test_backup_enables_restoration()
    print("✓ Test 4 passed")
    
    print("\n✓ All property tests passed!")
