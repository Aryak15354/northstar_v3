# Design Document: Northstar V3 Cleanup & Organization

## Overview

This design outlines a systematic approach to cleaning and organizing the Northstar V3 workspace. The cleanup will be performed in phases to minimize disruption, with each phase validated before proceeding. The design prioritizes safety (no data loss) and maintainability (clear organization).

## Architecture

### Cleanup Strategy

The cleanup follows a phased approach:

1. **Analysis Phase**: Scan and categorize all files
2. **Planning Phase**: Generate move/delete operations
3. **Validation Phase**: Verify operations won't break imports
4. **Execution Phase**: Perform file operations with backups
5. **Verification Phase**: Run tests to ensure system still works

### Directory Structure (Target State)

```
northstar-v3/
├── .kiro/
│   └── specs/
│       ├── active/           # Currently active specs
│       └── archive/          # Completed specs
├── config/                   # Configuration files
├── data/                     # Data files
├── docs/
│   ├── architecture/         # Architecture documentation
│   ├── completion_reports/   # Historical completion reports
│   ├── guides/              # User guides
│   └── api/                 # API documentation
├── logs/                     # Log files
├── reports/                  # Generated reports (keep for now)
├── scripts/
│   ├── demos/               # Demo scripts
│   ├── deployment/          # Deployment scripts
│   ├── implementation/      # Implementation scripts
│   ├── maintenance/         # Maintenance scripts
│   ├── testing/             # Testing scripts
│   └── validation/          # Validation scripts
├── src/                      # Source code
├── tests/                    # Test files
│   └── schemas/             # Test schemas
├── backups/                  # Backup files
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
└── run.py
```


## Components and Interfaces

### 1. File Analyzer

**Purpose**: Scan workspace and categorize files

**Interface**:
```python
class FileAnalyzer:
    def scan_workspace() -> Dict[str, List[Path]]
    def categorize_file(path: Path) -> FileCategory
    def find_duplicates() -> List[Tuple[Path, Path]]
    def identify_test_artifacts() -> List[Path]
```

**Categories**:
- Completion reports
- Documentation
- Scripts (by type)
- Test artifacts
- Temporary files
- Source code
- Configuration

### 2. Move Planner

**Purpose**: Generate safe file move operations

**Interface**:
```python
class MovePlanner:
    def plan_moves(categorized_files: Dict) -> List[MoveOperation]
    def validate_plan(operations: List[MoveOperation]) -> ValidationResult
    def detect_conflicts(operations: List[MoveOperation]) -> List[Conflict]
```

**MoveOperation**:
- source_path: Path
- dest_path: Path
- operation_type: "move" | "delete" | "merge"
- affected_imports: List[str]

### 3. Import Updater

**Purpose**: Update import statements after file moves

**Interface**:
```python
class ImportUpdater:
    def find_imports(file: Path) -> List[ImportStatement]
    def update_import(file: Path, old_path: str, new_path: str)
    def validate_imports() -> List[ImportError]
```

### 4. Cleanup Executor

**Purpose**: Execute file operations safely

**Interface**:
```python
class CleanupExecutor:
    def create_backup() -> Path
    def execute_operation(op: MoveOperation) -> Result
    def rollback(backup_path: Path)
    def verify_operation(op: MoveOperation) -> bool
```


## Data Models

### FileCategory Enum
```python
class FileCategory(Enum):
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
    UNKNOWN = "unknown"
```

### CleanupPlan
```python
@dataclass
class CleanupPlan:
    operations: List[MoveOperation]
    estimated_time: timedelta
    affected_files: int
    import_updates_needed: int
    backup_size: int
    risks: List[str]
```

### ValidationResult
```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    affected_imports: List[str]
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system.*

### Property 1: No Data Loss
*For any* cleanup operation, all unique file content should be preserved either in the new location or in backups.

**Validates: Requirements 1.2, 4.4**

### Property 2: Import Integrity
*For any* file move operation, all import statements referencing that file should be updated to maintain functionality.

**Validates: Requirements 9.1, 9.2**

### Property 3: Idempotent Cleanup
*For any* cleanup script execution, running it multiple times should produce the same result as running it once.

**Validates: Requirements 2.5**

### Property 4: Backup Completeness
*For any* cleanup execution, the backup should contain all files that will be modified or deleted.

**Validates: Requirements 9.4**


### Property 5: Directory Consolidation
*For any* set of duplicate directories, consolidation should preserve all unique files and remove only true duplicates.

**Validates: Requirements 4.1, 4.4**

### Property 6: Naming Consistency
*For any* file in a category, the filename should follow the standard naming convention for that category.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

### Property 7: Root Directory Minimalism
*For any* file in the root directory, it should be one of the essential files (README, LICENSE, requirements.txt, run.py, .gitignore) or a configuration file.

**Validates: Requirements 6.1**

## Error Handling

### File Operation Errors
- **Missing Source**: Log error, skip operation, continue with others
- **Permission Denied**: Log error, add to manual review list
- **Destination Exists**: Check if identical, merge if different, skip if same

### Import Update Errors
- **Circular Import**: Log warning, add to manual review list
- **Missing Module**: Log error, attempt to locate, add to manual review list
- **Syntax Error**: Log error, skip file, add to manual review list

### Validation Errors
- **Test Failures**: Rollback changes, report which operations caused failures
- **Import Errors**: Rollback changes, report affected files
- **Missing Files**: Rollback changes, report inconsistency

## Testing Strategy

### Unit Tests
- Test file categorization logic with various file types
- Test move operation planning with edge cases
- Test import path updating with various import styles
- Test backup creation and restoration

### Property Tests
- Property 1: Verify no unique content is lost (compare file hashes before/after)
- Property 2: Verify all imports resolve after updates (run import checker)
- Property 3: Verify cleanup script is idempotent (run twice, compare results)
- Property 4: Verify backup contains all affected files (compare file lists)
- Property 5: Verify no unique files lost in consolidation (hash comparison)
- Property 6: Verify naming conventions (regex validation)
- Property 7: Verify root directory contents (whitelist check)

### Integration Tests
- Test full cleanup workflow on a test workspace
- Test rollback functionality after simulated failures
- Test import validation after file moves
- Test that system tests still pass after cleanup

