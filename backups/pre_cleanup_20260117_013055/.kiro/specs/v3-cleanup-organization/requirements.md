# Requirements Document: Northstar V3 Cleanup & Organization

## Introduction

Northstar V3 has accumulated significant technical debt through rapid development. The workspace contains duplicate files, scattered completion reports, test artifacts, and unclear organization. This project will systematically clean and organize the codebase to improve maintainability and developer experience.

## Glossary

- **System**: Northstar V3 trading system
- **Workspace**: The root directory containing all project files
- **Completion_Reports**: Markdown files documenting completed features
- **Test_Artifacts**: Temporary files created during testing
- **Archive**: Historical storage for completed work
- **Documentation**: User-facing and developer-facing guides

## Requirements

### Requirement 1: Consolidate Completion Reports

**User Story:** As a developer, I want all completion reports organized in one place, so that I can easily find project history without clutter in the root directory.

#### Acceptance Criteria

1. WHEN completion reports exist in the root directory, THE System SHALL move them to `docs/completion_reports/`
2. WHEN moving reports, THE System SHALL preserve file timestamps and content
3. WHEN reports are moved, THE System SHALL create an index file listing all reports by date
4. WHEN duplicate reports exist, THE System SHALL consolidate them into a single canonical version
5. THE System SHALL maintain a `docs/completion_reports/INDEX.md` file with categorized links

### Requirement 2: Remove Test Artifacts and Temporary Files

**User Story:** As a developer, I want test artifacts removed from the workspace, so that the repository stays clean and focused on production code.

#### Acceptance Criteria

1. WHEN test configuration directories exist (test_config, test_env, test_schemas), THE System SHALL remove them
2. WHEN temporary JSON files exist in root, THE System SHALL move them to appropriate locations or delete them
3. WHEN cache directories exist, THE System SHALL ensure they are in .gitignore
4. WHEN __pycache__ directories exist, THE System SHALL remove them
5. THE System SHALL create a cleanup script that can be run periodically

### Requirement 3: Organize Documentation

**User Story:** As a developer, I want documentation organized by purpose, so that I can quickly find relevant information.

#### Acceptance Criteria

1. WHEN architecture documents exist, THE System SHALL consolidate them into `docs/architecture/`
2. WHEN user guides exist, THE System SHALL place them in `docs/guides/`
3. WHEN API documentation exists, THE System SHALL place it in `docs/api/`
4. WHEN duplicate documentation exists, THE System SHALL merge into canonical versions
5. THE System SHALL create a master `docs/README.md` with navigation to all documentation

### Requirement 4: Consolidate Duplicate Directories

**User Story:** As a developer, I want duplicate directories removed, so that there is one clear location for each type of file.

#### Acceptance Criteria

1. WHEN multiple backup directories exist (backup, backups), THE System SHALL consolidate into `backups/`
2. WHEN multiple test schema directories exist, THE System SHALL consolidate into `tests/schemas/`
3. WHEN duplicate ingestion/preprocessing directories exist in root, THE System SHALL ensure all code is in `src/`
4. WHEN consolidating, THE System SHALL preserve all unique files
5. THE System SHALL log all consolidation actions for review

### Requirement 5: Organize Scripts Directory

**User Story:** As a developer, I want scripts organized by purpose, so that I can find the right script quickly.

#### Acceptance Criteria

1. WHEN scripts exist, THE System SHALL categorize them into subdirectories (setup, testing, deployment, maintenance)
2. WHEN demo scripts exist, THE System SHALL place them in `scripts/demos/`
3. WHEN implementation scripts exist, THE System SHALL place them in `scripts/implementation/`
4. WHEN validation scripts exist, THE System SHALL place them in `scripts/validation/`
5. THE System SHALL create a `scripts/README.md` documenting all script categories

### Requirement 6: Clean Root Directory

**User Story:** As a developer, I want a clean root directory, so that I can see essential files at a glance.

#### Acceptance Criteria

1. THE root directory SHALL contain only: README.md, LICENSE, requirements.txt, run.py, .gitignore, and essential config files
2. WHEN debug scripts exist in root, THE System SHALL move them to `scripts/debug/`
3. WHEN status check scripts exist in root, THE System SHALL move them to `scripts/maintenance/`
4. WHEN log files exist in root, THE System SHALL move them to `logs/`
5. THE System SHALL update all import paths affected by file moves

### Requirement 7: Archive Completed Specs

**User Story:** As a developer, I want completed specs archived, so that active specs are easy to find.

#### Acceptance Criteria

1. WHEN a spec is marked 100% complete, THE System SHALL move it to `.kiro/specs/archive/`
2. WHEN archiving specs, THE System SHALL preserve the complete directory structure
3. WHEN specs are archived, THE System SHALL update `.kiro/specs/README.md` with active vs archived lists
4. THE System SHALL maintain metadata about completion dates
5. THE System SHALL keep system-integrity-repair active (recently completed, may need updates)

### Requirement 8: Standardize Naming Conventions

**User Story:** As a developer, I want consistent file naming, so that I can predict file locations.

#### Acceptance Criteria

1. WHEN files use inconsistent naming (camelCase, snake_case, kebab-case), THE System SHALL standardize to snake_case for Python, kebab-case for configs
2. WHEN completion reports use inconsistent naming, THE System SHALL standardize to `YYYY-MM-DD-feature-name-complete.md`
3. WHEN test files exist, THE System SHALL ensure they follow `test_*.py` convention
4. WHEN script files exist, THE System SHALL ensure they use descriptive snake_case names
5. THE System SHALL document naming conventions in `docs/CONTRIBUTING.md`

### Requirement 9: Update Import Paths

**User Story:** As a developer, I want all imports working after reorganization, so that the system remains functional.

#### Acceptance Criteria

1. WHEN files are moved, THE System SHALL update all import statements referencing those files
2. WHEN imports are updated, THE System SHALL run tests to verify functionality
3. WHEN circular imports are detected, THE System SHALL log them for manual review
4. THE System SHALL create a mapping file documenting all file moves
5. THE System SHALL validate that all Python files can be imported without errors

### Requirement 10: Create Maintenance Documentation

**User Story:** As a developer, I want documentation on keeping the workspace clean, so that it doesn't become messy again.

#### Acceptance Criteria

1. THE System SHALL create `docs/MAINTENANCE.md` with cleanup procedures
2. THE documentation SHALL include pre-commit hooks for preventing clutter
3. THE documentation SHALL include periodic cleanup scripts
4. THE documentation SHALL define what belongs in each directory
5. THE documentation SHALL include a checklist for code reviews
