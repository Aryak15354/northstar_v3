"""
Move Planner for Northstar V3 Cleanup
Plans safe file move operations with validation.
"""
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass
from enum import Enum


class OperationType(Enum):
    """Types of file operations"""
    MOVE = "move"
    DELETE = "delete"
    MERGE = "merge"


@dataclass
class MoveOperation:
    """Represents a file move operation"""
    source_path: Path
    dest_path: Path
    operation_type: OperationType
    affected_imports: List[str]
    reason: str


@dataclass
class ValidationResult:
    """Result of plan validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    affected_imports: List[str]


@dataclass
class Conflict:
    """Represents a conflict in the plan"""
    operation: MoveOperation
    conflict_type: str
    description: str


class MovePlanner:
    """Plans file move operations"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.operations: List[MoveOperation] = []
        
    def plan_completion_reports_move(self) -> List[MoveOperation]:
        """Plan moving completion reports to docs/completion_reports/"""
        operations = []
        dest_dir = Path("docs/completion_reports")
        
        # Find completion reports in root
        for file in self.workspace_root.glob("*_COMPLETE.md"):
            if file.is_file():
                operations.append(MoveOperation(
                    source_path=file.relative_to(self.workspace_root),
                    dest_path=dest_dir / file.name,
                    operation_type=OperationType.MOVE,
                    affected_imports=[],
                    reason="Organize completion reports"
                ))
        
        # Also check for other completion patterns
        for file in self.workspace_root.glob("*COMPLETE*.md"):
            if file.is_file() and file.name not in [op.source_path.name for op in operations]:
                operations.append(MoveOperation(
                    source_path=file.relative_to(self.workspace_root),
                    dest_path=dest_dir / file.name,
                    operation_type=OperationType.MOVE,
                    affected_imports=[],
                    reason="Organize completion reports"
                ))
        
        return operations
    
    def plan_test_artifacts_removal(self) -> List[MoveOperation]:
        """Plan removal of test artifacts"""
        operations = []
        
        # Test directories to remove
        test_dirs = [
            "test_config", "test_env", "test_schemas",
            "test_simple_config", "test_simple_schemas",
            "test_integration_schemas", "integration_test_schemas"
        ]
        
        for test_dir in test_dirs:
            dir_path = self.workspace_root / test_dir
            if dir_path.exists():
                operations.append(MoveOperation(
                    source_path=Path(test_dir),
                    dest_path=Path(""),  # Delete
                    operation_type=OperationType.DELETE,
                    affected_imports=[],
                    reason="Remove test artifacts"
                ))
        
        # Temporary JSON files in root
        for file in self.workspace_root.glob("*.json"):
            if any(x in file.name for x in ['test', 'debug', 'variance', 'attribution']):
                operations.append(MoveOperation(
                    source_path=file.relative_to(self.workspace_root),
                    dest_path=Path(""),  # Delete
                    operation_type=OperationType.DELETE,
                    affected_imports=[],
                    reason="Remove temporary test files"
                ))
        
        return operations
    
    def plan_documentation_organization(self) -> List[MoveOperation]:
        """Plan documentation organization"""
        operations = []
        
        # Architecture docs
        arch_patterns = [
            "*ARCHITECTURE*.md", "*SYSTEM_DOCUMENTATION*.md",
            "*GUIDE*.md", "*REORGANIZATION*.md"
        ]
        dest_arch = Path("docs/architecture")
        
        for pattern in arch_patterns:
            for file in self.workspace_root.glob(pattern):
                if file.is_file():
                    operations.append(MoveOperation(
                        source_path=file.relative_to(self.workspace_root),
                        dest_path=dest_arch / file.name,
                        operation_type=OperationType.MOVE,
                        affected_imports=[],
                        reason="Organize architecture documentation"
                    ))
        
        return operations
    
    def plan_root_cleanup(self) -> List[MoveOperation]:
        """Plan root directory cleanup"""
        operations = []
        
        # Essential files that should stay in root
        essential = {
            'README.md', 'LICENSE', 'requirements.txt', 'run.py',
            '.gitignore', 'PROJECT_STRUCTURE.md'
        }
        
        # Move debug scripts
        for file in self.workspace_root.glob("*.py"):
            if file.name not in essential and any(x in file.name for x in ['debug', 'check', 'test_import']):
                operations.append(MoveOperation(
                    source_path=file.relative_to(self.workspace_root),
                    dest_path=Path("scripts/debug") / file.name,
                    operation_type=OperationType.MOVE,
                    affected_imports=[],
                    reason="Move debug scripts out of root"
                ))
        
        # Move log files
        for file in self.workspace_root.glob("*.log"):
            operations.append(MoveOperation(
                source_path=file.relative_to(self.workspace_root),
                dest_path=Path("logs") / file.name,
                operation_type=OperationType.MOVE,
                affected_imports=[],
                reason="Move log files to logs/"
            ))
        
        # Move system freeze/sealed files
        for file in self.workspace_root.glob("*.txt"):
            if 'freeze' in file.name or 'sealed' in file.name:
                operations.append(MoveOperation(
                    source_path=file.relative_to(self.workspace_root),
                    dest_path=Path("backups") / file.name,
                    operation_type=OperationType.MOVE,
                    affected_imports=[],
                    reason="Move system state files to backups/"
                ))
        
        return operations
    
    def plan_moves(self, categorized_files: Dict) -> List[MoveOperation]:
        """Generate complete move plan"""
        self.operations = []
        
        # Add all planned operations
        self.operations.extend(self.plan_completion_reports_move())
        self.operations.extend(self.plan_test_artifacts_removal())
        self.operations.extend(self.plan_documentation_organization())
        self.operations.extend(self.plan_root_cleanup())
        
        # Deduplicate operations - keep first occurrence
        seen_sources = set()
        deduplicated = []
        for op in self.operations:
            if op.source_path not in seen_sources:
                seen_sources.add(op.source_path)
                deduplicated.append(op)
        
        self.operations = deduplicated
        return self.operations
    
    def validate_plan(self, operations: List[MoveOperation]) -> ValidationResult:
        """Validate the move plan"""
        errors = []
        warnings = []
        affected_imports = []
        
        # Check for destination conflicts
        dest_paths = {}
        for op in operations:
            if op.operation_type != OperationType.DELETE:
                if op.dest_path in dest_paths:
                    errors.append(
                        f"Destination conflict: {op.dest_path} "
                        f"(from {op.source_path} and {dest_paths[op.dest_path]})"
                    )
                dest_paths[op.dest_path] = op.source_path
        
        # Check if source files exist
        for op in operations:
            source_full = self.workspace_root / op.source_path
            if not source_full.exists():
                warnings.append(f"Source does not exist: {op.source_path}")
        
        # Check for Python file moves (potential import issues)
        for op in operations:
            if op.source_path.suffix == '.py' and op.operation_type == OperationType.MOVE:
                warnings.append(
                    f"Python file move may affect imports: {op.source_path} → {op.dest_path}"
                )
                affected_imports.append(str(op.source_path))
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            affected_imports=affected_imports
        )
    
    def detect_conflicts(self, operations: List[MoveOperation]) -> List[Conflict]:
        """Detect conflicts in operations"""
        conflicts = []
        
        # Check for circular moves
        move_map = {}
        for op in operations:
            if op.operation_type == OperationType.MOVE:
                move_map[op.source_path] = op.dest_path
        
        for source, dest in move_map.items():
            if dest in move_map and move_map[dest] == source:
                conflicts.append(Conflict(
                    operation=op,
                    conflict_type="circular_move",
                    description=f"Circular move detected: {source} ↔ {dest}"
                ))
        
        return conflicts
    
    def generate_plan_report(self) -> str:
        """Generate a report of the planned operations"""
        report = ["# Cleanup Plan Report\n\n"]
        
        # Group by operation type
        by_type = {}
        for op in self.operations:
            if op.operation_type not in by_type:
                by_type[op.operation_type] = []
            by_type[op.operation_type].append(op)
        
        for op_type, ops in by_type.items():
            report.append(f"## {op_type.value.upper()} Operations: {len(ops)}\n\n")
            for op in ops[:20]:  # Show first 20
                if op.operation_type == OperationType.DELETE:
                    report.append(f"- DELETE: {op.source_path}\n")
                else:
                    report.append(f"- {op.source_path} → {op.dest_path}\n")
            if len(ops) > 20:
                report.append(f"  ... and {len(ops) - 20} more\n")
            report.append("\n")
        
        # Validation
        validation = self.validate_plan(self.operations)
        report.append(f"## Validation\n\n")
        report.append(f"- Valid: {validation.is_valid}\n")
        report.append(f"- Errors: {len(validation.errors)}\n")
        report.append(f"- Warnings: {len(validation.warnings)}\n")
        
        if validation.errors:
            report.append("\n### Errors\n\n")
            for error in validation.errors:
                report.append(f"- {error}\n")
        
        if validation.warnings:
            report.append("\n### Warnings\n\n")
            for warning in validation.warnings[:10]:
                report.append(f"- {warning}\n")
        
        return "".join(report)


if __name__ == "__main__":
    planner = MovePlanner(Path.cwd())
    operations = planner.plan_moves({})
    report = planner.generate_plan_report()
    
    # Save report
    report_path = Path("reports/cleanup_plan.md")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(report)
    print(f"Plan generated. Report saved to: {report_path}")
