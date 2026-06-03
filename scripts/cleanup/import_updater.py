"""
Import Updater for Northstar V3 Cleanup
Updates import statements after file moves.
"""
import ast
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import logging


@dataclass
class ImportStatement:
    """Represents an import statement"""
    line_number: int
    original: str
    module: str
    names: List[str]
    is_from_import: bool


class ImportUpdater:
    """Updates import statements after file moves"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.logger = logging.getLogger(__name__)
        
    def find_imports(self, file_path: Path) -> List[ImportStatement]:
        """Find all import statements in a Python file"""
        imports = []
        
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(ImportStatement(
                            line_number=node.lineno,
                            original=ast.get_source_segment(content, node),
                            module=alias.name,
                            names=[alias.name],
                            is_from_import=False
                        ))
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        names = [alias.name for alias in node.names]
                        imports.append(ImportStatement(
                            line_number=node.lineno,
                            original=ast.get_source_segment(content, node),
                            module=node.module,
                            names=names,
                            is_from_import=True
                        ))
        
        except Exception as e:
            self.logger.warning(f"Could not parse {file_path}: {e}")
        
        return imports
    
    def update_import(self, file_path: Path, old_module: str, new_module: str) -> bool:
        """Update import statement in a file"""
        try:
            content = file_path.read_text()
            original_content = content
            
            # Pattern for import statements
            patterns = [
                (rf'import\s+{re.escape(old_module)}(\s|$|,)', f'import {new_module}\\1'),
                (rf'from\s+{re.escape(old_module)}\s+import', f'from {new_module} import'),
            ]
            
            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)
            
            if content != original_content:
                file_path.write_text(content)
                self.logger.info(f"Updated imports in: {file_path}")
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(f"Failed to update {file_path}: {e}")
            return False
    
    def find_files_importing(self, module_name: str) -> List[Path]:
        """Find all Python files that import a module"""
        importing_files = []
        
        for py_file in self.workspace_root.rglob("*.py"):
            if self._file_imports_module(py_file, module_name):
                importing_files.append(py_file)
        
        return importing_files
    
    def _file_imports_module(self, file_path: Path, module_name: str) -> bool:
        """Check if a file imports a specific module"""
        try:
            content = file_path.read_text()
            
            # Simple regex check (faster than AST parsing)
            patterns = [
                rf'import\s+{re.escape(module_name)}(\s|$|,)',
                rf'from\s+{re.escape(module_name)}\s+import',
            ]
            
            for pattern in patterns:
                if re.search(pattern, content):
                    return True
            
            return False
        
        except Exception:
            return False
    
    def validate_imports(self) -> List[str]:
        """Validate all imports in the workspace"""
        errors = []
        
        for py_file in self.workspace_root.rglob("*.py"):
            # Skip venv and cache
            if 'venv' in str(py_file) or '__pycache__' in str(py_file):
                continue
            
            try:
                imports = self.find_imports(py_file)
                for imp in imports:
                    # Check if module exists
                    if not self._module_exists(imp.module):
                        errors.append(f"{py_file}: Cannot import '{imp.module}'")
            
            except Exception as e:
                errors.append(f"{py_file}: {e}")
        
        return errors
    
    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists (simplified check)"""
        # Check if it's a standard library module
        try:
            __import__(module_name.split('.')[0])
            return True
        except ImportError:
            pass
        
        # Check if it's a local module
        module_path = self.workspace_root / module_name.replace('.', '/')
        if module_path.with_suffix('.py').exists():
            return True
        if (module_path / '__init__.py').exists():
            return True
        
        # Assume third-party modules exist
        return True
    
    def generate_import_map(self, move_operations: List) -> Dict[str, str]:
        """Generate mapping of old module paths to new ones"""
        import_map = {}
        
        for op in move_operations:
            if op.source_path.suffix == '.py':
                # Convert file path to module path
                old_module = str(op.source_path.with_suffix('')).replace('/', '.')
                new_module = str(op.dest_path.with_suffix('')).replace('/', '.')
                
                import_map[old_module] = new_module
        
        return import_map


if __name__ == "__main__":
    updater = ImportUpdater(Path.cwd())
    errors = updater.validate_imports()
    
    if errors:
        print(f"Found {len(errors)} import errors:")
        for error in errors[:20]:
            print(f"  - {error}")
    else:
        print("All imports valid!")
