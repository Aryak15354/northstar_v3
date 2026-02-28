"""
File Analyzer for Northstar V3 Cleanup
Scans workspace and categorizes files for organization.
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import hashlib


class FileCategory(Enum):
    """Categories for file classification"""
    COMPLETION_REPORT = "completion_report"
    ARCHITECTURE_DOC = "architecture_doc"
    USER_GUIDE = "user_guide"
    SCRIPT_DEMO = "script_demo"
    SCRIPT_IMPLEMENTATION = "script_implementation"
    SCRIPT_VALIDATION = "script_validation"
    SCRIPT_MAINTENANCE = "script_maintenance"
    TEST_ARTIFACT = "test_artifact"
    TEMPORARY_FILE = "temporary_file"
    SOURCE_CODE = "source_code"
    TEST_FILE = "test_file"
    CONFIGURATION = "configuration"
    LOG_FILE = "log_file"
    SPEC_FILE = "spec_file"
    UNKNOWN = "unknown"


@dataclass
class FileInfo:
    """Information about a file"""
    path: Path
    category: FileCategory
    size: int
    hash: str
    modified: datetime


class FileAnalyzer:
    """Analyzes workspace files and categorizes them"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.categorized_files: Dict[FileCategory, List[FileInfo]] = {}
        
    def scan_workspace(self) -> Dict[FileCategory, List[FileInfo]]:
        """Scan entire workspace and categorize all files"""
        print(f"Scanning workspace: {self.workspace_root}")
        
        # Initialize categories
        for category in FileCategory:
            self.categorized_files[category] = []
        
        # Walk through workspace
        for root, dirs, files in os.walk(self.workspace_root):
            # Skip certain directories
            root_path = Path(root)
            if self._should_skip_directory(root_path):
                dirs.clear()  # Don't recurse into this directory
                continue
            
            # Process files
            for file in files:
                file_path = root_path / file
                try:
                    file_info = self._analyze_file(file_path)
                    self.categorized_files[file_info.category].append(file_info)
                except Exception as e:
                    print(f"Error analyzing {file_path}: {e}")
        
        return self.categorized_files
    
    def _should_skip_directory(self, path: Path) -> bool:
        """Check if directory should be skipped"""
        skip_dirs = {
            '__pycache__', '.hypothesis', 'venv', 'node_modules',
            '.git', '.vscode', 'cache', '.DS_Store'
        }
        return path.name in skip_dirs or path.name.startswith('.')
    
    def _analyze_file(self, path: Path) -> FileInfo:
        """Analyze a single file and categorize it"""
        category = self.categorize_file(path)
        size = path.stat().st_size
        file_hash = self._compute_hash(path)
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        
        return FileInfo(
            path=path.relative_to(self.workspace_root),
            category=category,
            size=size,
            hash=file_hash,
            modified=modified
        )
    
    def categorize_file(self, path: Path) -> FileCategory:
        """Categorize a file based on its name and location"""
        name = path.name.lower()
        parent = path.parent.name.lower()
        
        # Completion reports
        if name.endswith('_complete.md') or 'completion' in name:
            return FileCategory.COMPLETION_REPORT
        
        # Architecture docs
        if any(x in name for x in ['architecture', 'system_documentation', 'guide']):
            return FileCategory.ARCHITECTURE_DOC
        
        # Scripts
        if path.suffix == '.py' and 'scripts' in str(path):
            if 'demo' in name or 'launch' in name:
                return FileCategory.SCRIPT_DEMO
            elif 'implement' in name or 'build' in name:
                return FileCategory.SCRIPT_IMPLEMENTATION
            elif 'test' in name or 'validate' in name or 'verify' in name:
                return FileCategory.SCRIPT_VALIDATION
            elif 'fix' in name or 'check' in name or 'inspect' in name:
                return FileCategory.SCRIPT_MAINTENANCE
            return FileCategory.SCRIPT_MAINTENANCE
        
        # Test artifacts
        if 'test_' in parent or name.startswith('test_'):
            if path.suffix in ['.json', '.yaml', '.yml']:
                return FileCategory.TEST_ARTIFACT
            elif path.suffix == '.py':
                return FileCategory.TEST_FILE
        
        # Temporary files
        if name.endswith('.json') and any(x in name for x in ['test', 'debug', 'temp']):
            return FileCategory.TEMPORARY_FILE
        
        # Log files
        if path.suffix == '.log' or name.endswith('.txt') and 'log' in name:
            return FileCategory.LOG_FILE
        
        # Source code
        if path.suffix == '.py' and 'src' in str(path):
            return FileCategory.SOURCE_CODE
        
        # Configuration
        if path.suffix in ['.yaml', '.yml', '.json', '.toml', '.ini', '.cfg']:
            return FileCategory.CONFIGURATION
        
        # Spec files
        if '.kiro/specs' in str(path):
            return FileCategory.SPEC_FILE
        
        return FileCategory.UNKNOWN
    
    def find_duplicates(self) -> List[Tuple[FileInfo, FileInfo]]:
        """Find duplicate files based on content hash"""
        duplicates = []
        hash_map: Dict[str, List[FileInfo]] = {}
        
        # Build hash map
        for category, files in self.categorized_files.items():
            for file_info in files:
                if file_info.hash not in hash_map:
                    hash_map[file_info.hash] = []
                hash_map[file_info.hash].append(file_info)
        
        # Find duplicates
        for file_hash, files in hash_map.items():
            if len(files) > 1:
                for i in range(len(files)):
                    for j in range(i + 1, len(files)):
                        duplicates.append((files[i], files[j]))
        
        return duplicates
    
    def identify_test_artifacts(self) -> List[Path]:
        """Identify test artifact directories and files"""
        artifacts = []
        
        # Test artifact directories
        test_dirs = [
            'test_config', 'test_env', 'test_schemas',
            'test_simple_config', 'test_simple_schemas',
            'test_integration_schemas', 'integration_test_schemas'
        ]
        
        for test_dir in test_dirs:
            dir_path = self.workspace_root / test_dir
            if dir_path.exists():
                artifacts.append(dir_path)
        
        # Temporary JSON files in root
        for file_info in self.categorized_files[FileCategory.TEMPORARY_FILE]:
            if file_info.path.parent == Path('.'):
                artifacts.append(self.workspace_root / file_info.path)
        
        return artifacts
    
    def _compute_hash(self, path: Path) -> str:
        """Compute SHA256 hash of file content"""
        try:
            sha256 = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return ""
    
    def generate_report(self) -> str:
        """Generate analysis report"""
        report = ["# Workspace Analysis Report\n"]
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"Workspace: {self.workspace_root}\n\n")
        
        # Summary by category
        report.append("## Files by Category\n\n")
        for category in FileCategory:
            files = self.categorized_files[category]
            if files:
                total_size = sum(f.size for f in files)
                report.append(f"- **{category.value}**: {len(files)} files ({total_size / 1024:.1f} KB)\n")
        
        # Duplicates
        duplicates = self.find_duplicates()
        if duplicates:
            report.append(f"\n## Duplicate Files: {len(duplicates)}\n\n")
            for dup1, dup2 in duplicates[:10]:  # Show first 10
                report.append(f"- {dup1.path} ↔ {dup2.path}\n")
        
        # Test artifacts
        artifacts = self.identify_test_artifacts()
        if artifacts:
            report.append(f"\n## Test Artifacts: {len(artifacts)}\n\n")
            for artifact in artifacts:
                report.append(f"- {artifact.relative_to(self.workspace_root)}\n")
        
        return "".join(report)


if __name__ == "__main__":
    analyzer = FileAnalyzer(Path.cwd())
    analyzer.scan_workspace()
    report = analyzer.generate_report()
    
    # Save report
    report_path = Path("reports/workspace_analysis.md")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(report)
    print(f"Analysis complete. Report saved to: {report_path}")
