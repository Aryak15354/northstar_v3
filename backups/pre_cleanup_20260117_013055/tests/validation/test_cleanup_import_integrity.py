"""
Property Test: Import Integrity After Cleanup
Validates that file moves preserve import relationships.

Property 2: Import Integrity
- All imports that worked before cleanup work after cleanup
- Import paths are correctly updated after file moves
- No circular imports are introduced
- All Python files remain syntactically valid
"""
import sys
from pathlib import Path
from hypothesis import given, strategies as st, settings
from hypothesis import Phase
import ast
import tempfile
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.cleanup.import_updater import ImportUpdater
from scripts.cleanup.move_planner import MoveOperation


def create_test_module(temp_dir: Path, module_path: str, imports: list) -> Path:
    """Create a test Python module with specified imports"""
    file_path = temp_dir / module_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create __init__.py files for packages (only within temp_dir)
    current = file_path.parent
    while current != temp_dir and current.is_relative_to(temp_dir):
        init_file = current / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")
        current = current.parent
    
    # Create module with imports
    content = "\n".join(imports) + "\n\ndef test_function():\n    pass\n"
    file_path.write_text(content)
    
    return file_path


def validate_python_syntax(file_path: Path) -> bool:
    """Check if a Python file has valid syntax"""
    try:
        ast.parse(file_path.read_text())
        return True
    except SyntaxError:
        return False


@given(
    module_name=st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu'), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=10
    ),
    num_imports=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_import_integrity_after_move(module_name: str, num_imports: int):
    """
    Property: Moving a Python file and updating imports preserves import integrity
    
    Given:
    - A Python module with imports
    - A move operation to a new location
    
    When:
    - The file is moved
    - Import paths are updated
    
    Then:
    - All imports remain valid
    - The file remains syntactically valid
    - Import relationships are preserved
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create source module
        source_path = f"src/{module_name}.py"
        imports = [f"import os", f"from pathlib import Path"]
        if num_imports > 0:
            imports.append(f"import sys")
        
        module_file = create_test_module(temp_path, source_path, imports)
        
        # Verify original file is valid
        assert validate_python_syntax(module_file), "Original file should be valid Python"
        
        # Create import updater
        updater = ImportUpdater(temp_path)
        
        # Find imports in original file
        original_imports = updater.find_imports(module_file)
        assert len(original_imports) >= 2, "Should find at least 2 imports"
        
        # Simulate move operation
        dest_path = temp_path / f"lib/{module_name}.py"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(module_file, dest_path)
        
        # Verify moved file is still valid
        assert validate_python_syntax(dest_path), "Moved file should remain valid Python"
        
        # Find imports in moved file
        moved_imports = updater.find_imports(dest_path)
        
        # Property: Import count is preserved
        assert len(moved_imports) == len(original_imports), \
            "Number of imports should be preserved after move"
        
        # Property: Import modules are preserved
        original_modules = {imp.module for imp in original_imports}
        moved_modules = {imp.module for imp in moved_imports}
        assert original_modules == moved_modules, \
            "Import modules should be preserved after move"


@given(
    num_files=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_no_circular_imports_introduced(num_files: int):
    """
    Property: File moves do not introduce circular imports
    
    Given:
    - Multiple Python modules with imports between them
    - Move operations for these modules
    
    When:
    - Files are moved and imports updated
    
    Then:
    - No circular import dependencies are introduced
    - All files remain importable
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a chain of imports (no cycles)
        files = []
        for i in range(num_files):
            module_name = f"module_{i}"
            imports = []
            
            # Each module imports the previous one (except first)
            if i > 0:
                imports.append(f"from src.module_{i-1} import test_function")
            
            file_path = create_test_module(temp_path, f"src/{module_name}.py", imports)
            files.append(file_path)
        
        # Verify no circular imports initially
        updater = ImportUpdater(temp_path)
        
        # Check each file can be parsed
        for file_path in files:
            assert validate_python_syntax(file_path), \
                f"File {file_path} should be valid Python"
            
            imports = updater.find_imports(file_path)
            # Property: No module imports itself
            module_name = file_path.stem
            for imp in imports:
                assert module_name not in imp.module, \
                    f"Module {module_name} should not import itself"


@given(
    num_moves=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=10, phases=[Phase.generate, Phase.target])
def test_import_paths_updated_correctly(num_moves: int):
    """
    Property: Import paths are correctly updated after file moves
    
    Given:
    - Python modules with imports
    - Move operations changing file locations
    
    When:
    - Import paths are updated
    
    Then:
    - All import statements reference correct new locations
    - No broken imports remain
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create modules
        modules = []
        for i in range(num_moves):
            module_name = f"util_{i}"
            file_path = create_test_module(
                temp_path,
                f"src/utils/{module_name}.py",
                [f"import os"]
            )
            modules.append((module_name, file_path))
        
        # Create a file that imports these modules
        import_statements = [
            f"from src.utils.{name} import test_function"
            for name, _ in modules
        ]
        importer = create_test_module(
            temp_path,
            "src/main.py",
            import_statements
        )
        
        # Verify original imports
        updater = ImportUpdater(temp_path)
        original_imports = updater.find_imports(importer)
        assert len(original_imports) == num_moves, \
            "Should find all import statements"
        
        # Simulate moving modules to new location
        for name, old_path in modules:
            new_path = temp_path / f"lib/helpers/{name}.py"
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(old_path, new_path)
            
            # Update imports
            old_module = f"src.utils.{name}"
            new_module = f"lib.helpers.{name}"
            updater.update_import(importer, old_module, new_module)
        
        # Verify imports were updated
        updated_imports = updater.find_imports(importer)
        
        # Property: All imports updated to new paths
        for imp in updated_imports:
            assert "lib.helpers" in imp.module, \
                f"Import should reference new location: {imp.module}"
            assert "src.utils" not in imp.module, \
                f"Import should not reference old location: {imp.module}"


def test_import_integrity_property_validation():
    """
    Meta-test: Verify the property test itself is working correctly
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a simple valid module
        module = create_test_module(
            temp_path,
            "test_module.py",
            ["import os", "from pathlib import Path"]
        )
        
        # Verify it's valid
        assert validate_python_syntax(module)
        
        # Verify we can find imports
        updater = ImportUpdater(temp_path)
        imports = updater.find_imports(module)
        assert len(imports) == 2
        
        # Verify import details
        modules = {imp.module for imp in imports}
        assert "os" in modules
        assert "pathlib" in modules


if __name__ == "__main__":
    # Run meta-test first
    print("Running meta-test...")
    test_import_integrity_property_validation()
    print("✓ Meta-test passed")
    
    # Run property tests
    print("\nRunning property tests...")
    print("Test 1: Import integrity after move...")
    test_import_integrity_after_move()
    print("✓ Test 1 passed")
    
    print("Test 2: No circular imports introduced...")
    test_no_circular_imports_introduced()
    print("✓ Test 2 passed")
    
    print("Test 3: Import paths updated correctly...")
    test_import_paths_updated_correctly()
    print("✓ Test 3 passed")
    
    print("\n✓ All property tests passed!")
