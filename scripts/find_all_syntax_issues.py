#!/usr/bin/env python3
"""
Find All Syntax Issues

Analyzes the dashboard file to find ALL syntax errors at once,
then provides a comprehensive fix plan.
"""

import ast
import re
from typing import List, Tuple

def find_all_syntax_issues(file_path: str) -> List[Tuple[int, str, str]]:
    """Find all syntax issues in the file"""
    
    issues = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Try to parse and get the first syntax error
    content = ''.join(lines)
    
    try:
        ast.parse(content)
        return []  # No syntax errors
    except SyntaxError as e:
        print(f"First syntax error at line {e.lineno}: {e.msg}")
        if e.text:
            print(f"  Text: {e.text.strip()}")
    
    # Analyze common patterns that cause issues
    for i, line in enumerate(lines, 1):
        line_num = i
        original_line = line.rstrip()
        
        # Pattern 1: Corrupted HTML color attributes
        if re.search(r'<span style="color[^>]*?is not None.*?\};">', line):
            issues.append((line_num, "corrupted_html_color", original_line))
        
        # Pattern 2: Broken if statements with "if True:"
        if re.search(r'if True:\s*$', line):
            issues.append((line_num, "broken_if_true", original_line))
        
        # Pattern 3: Corrupted variable assignments with "if True:"
        if re.search(r'= .+ if True:', line):
            issues.append((line_num, "corrupted_assignment", original_line))
        
        # Pattern 4: Broken try/except indentation
        if re.search(r'try:\s*st\.plotly_chart', line):
            issues.append((line_num, "broken_try_plotly", original_line))
        
        # Pattern 5: Corrupted max() calls
        if re.search(r'max\(max\([^,]+,, 0\.001\) 0\.001\)', line):
            issues.append((line_num, "corrupted_max_call", original_line))
        
        # Pattern 6: Corrupted "is not None and len(...)" patterns
        if re.search(r'is not None and len\([^)]+\) > 0', line):
            issues.append((line_num, "corrupted_none_check", original_line))
        
        # Pattern 7: Unmatched brackets/parentheses
        open_brackets = line.count('[') - line.count(']')
        open_parens = line.count('(') - line.count(')')
        open_braces = line.count('{') - line.count('}')
        
        if abs(open_brackets) > 2 or abs(open_parens) > 3 or abs(open_braces) > 2:
            issues.append((line_num, "unmatched_brackets", original_line))
        
        # Pattern 8: Incomplete string literals
        if line.count('"') % 2 != 0 or line.count("'") % 2 != 0:
            if not line.strip().startswith('#'):  # Ignore comments
                issues.append((line_num, "incomplete_string", original_line))
        
        # Pattern 9: Wrong indentation for try/except blocks
        if 'except Exception as e:' in line:
            # Check if the indentation matches the try block
            indent = len(line) - len(line.lstrip())
            if i > 1:
                prev_lines = lines[max(0, i-5):i-1]
                for j, prev_line in enumerate(reversed(prev_lines)):
                    if 'try:' in prev_line:
                        try_indent = len(prev_line) - len(prev_line.lstrip())
                        if indent != try_indent:
                            issues.append((line_num, "mismatched_try_except_indent", original_line))
                        break
    
    return issues

def main():
    """Find all syntax issues"""
    
    print("🔍 Finding ALL syntax issues in dashboard...")
    
    file_path = "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py"
    issues = find_all_syntax_issues(file_path)
    
    if not issues:
        print("✅ No syntax issues found!")
        return
    
    print(f"\n📋 Found {len(issues)} potential issues:")
    print("=" * 80)
    
    # Group issues by type
    issue_types = {}
    for line_num, issue_type, line_content in issues:
        if issue_type not in issue_types:
            issue_types[issue_type] = []
        issue_types[issue_type].append((line_num, line_content))
    
    for issue_type, occurrences in issue_types.items():
        print(f"\n🔧 {issue_type.upper().replace('_', ' ')} ({len(occurrences)} occurrences):")
        for line_num, line_content in occurrences[:5]:  # Show first 5
            print(f"  Line {line_num}: {line_content[:80]}...")
        if len(occurrences) > 5:
            print(f"  ... and {len(occurrences) - 5} more")
    
    print("\n" + "=" * 80)
    print("🛠️  RECOMMENDED FIX ORDER:")
    print("1. Fix corrupted HTML color attributes")
    print("2. Fix broken if True: statements")
    print("3. Fix corrupted variable assignments")
    print("4. Fix try/except indentation issues")
    print("5. Fix unmatched brackets/parentheses")
    print("6. Fix incomplete string literals")
    print("7. Fix corrupted None checks")
    print("8. Fix corrupted max() calls")

if __name__ == "__main__":
    main()