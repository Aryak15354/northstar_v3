#!/usr/bin/env python3
"""
Fix SystemHealthStatus enum references to use SystemHealthLevel instead.
"""

import re
from pathlib import Path

def fix_file(file_path):
    """Fix SystemHealthStatus enum references in a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace enum references
    replacements = [
        (r'SystemHealthStatus\.HEALTHY', 'SystemHealthLevel.HEALTHY'),
        (r'SystemHealthStatus\.WARNING', 'SystemHealthLevel.WARNING'),
        (r'SystemHealthStatus\.DEGRADED', 'SystemHealthLevel.DEGRADED'),
        (r'SystemHealthStatus\.CRITICAL', 'SystemHealthLevel.CRITICAL'),
        (r'SystemHealthStatus\.UNKNOWN', 'SystemHealthLevel.UNKNOWN'),
    ]
    
    original_content = content
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed {file_path}")
        return True
    return False

def main():
    """Fix all files with SystemHealthStatus enum references."""
    files_to_fix = [
        "src/operation/master_operation_controller.py",
        "src/operation/system_validation_suite.py",
        "src/operation/integration_testing_framework.py",
        "src/operation/system_integration_wiring.py"
    ]
    
    fixed_count = 0
    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            if fix_file(path):
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")
    
    print(f"Fixed {fixed_count} files")

if __name__ == "__main__":
    main()