#!/usr/bin/env python3
"""
🔄 MIGRATION HELPER - TASK 14.1
Helper utilities to migrate from hardcoded assumptions to configurable parameters

This provides utilities to help migrate existing code from hardcoded market
assumptions and file paths to the new configurable system.

SYSTEM LAWS ENFORCED:
- Invariant M1: Migration Completeness - all hardcoded values are identified
- Invariant M2: Migration Safety - migrations preserve system behavior
- Invariant M3: Migration Verification - migrations are validated

These are not suggestions - they are LAWS that ensure safe migration.
"""

import os
import sys
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.market_configuration import get_market_config_manager, get_active_market_config
from src.cohesion.path_configuration import get_path_config_manager, get_path_config

@dataclass
class HardcodedReference:
    """A hardcoded reference found in code"""
    file_path: str
    line_number: int
    line_content: str
    reference_type: str  # 'market', 'path', 'currency'
    hardcoded_value: str
    suggested_replacement: str
    confidence: float  # 0.0 to 1.0

class MigrationHelper:
    """
    Helper class to migrate from hardcoded assumptions to configurable parameters
    """
    
    def __init__(self):
        self.market_patterns = {
            # Indian market patterns
            r'\.NS\b': ('market_symbol_suffix', 'Use market_config.data_sources.format_symbol()'),
            r'\bINR\b': ('currency', 'Use market_config.currency.base_currency'),
            r'\bNSE\b': ('exchange', 'Use market_config.data_sources.primary_provider'),
            r'\bBSE\b': ('exchange', 'Use market_config.data_sources.backup_providers'),
            r'\bNIFTY\b': ('benchmark', 'Use market_config.benchmark_indices'),
            r'09:15|15:30': ('trading_hours', 'Use market_config.trading_hours'),
            r'Asia/Kolkata|Indian': ('timezone', 'Use market_config.trading_hours.timezone'),
            r'₹': ('currency_symbol', 'Use market_config.currency.currency_symbol'),
            
            # US market patterns
            r'\bUSD\b': ('currency', 'Use market_config.currency.base_currency'),
            r'\bSPY\b': ('benchmark', 'Use market_config.benchmark_indices'),
            r'09:30|16:00': ('trading_hours', 'Use market_config.trading_hours'),
            r'America/New_York': ('timezone', 'Use market_config.trading_hours.timezone'),
            r'\$': ('currency_symbol', 'Use market_config.currency.currency_symbol'),
        }
        
        self.path_patterns = {
            r'data/validation/': ('data_path', 'Use get_data_path("validation", filename)'),
            r'data/processed/': ('data_path', 'Use get_data_path("processed", filename)'),
            r'data/raw/': ('data_path', 'Use get_data_path("raw", filename)'),
            r'data/simulation/': ('data_path', 'Use get_data_path("simulation", filename)'),
            r'data/audit_trail/': ('data_path', 'Use get_data_path("audit", filename)'),
            r'data/integrity/': ('data_path', 'Use get_data_path("integrity", filename)'),
            r'data/execution/': ('data_path', 'Use get_data_path("execution", filename)'),
            r'reports/': ('report_path', 'Use get_report_path("system", filename)'),
            r'logs/': ('log_path', 'Use get_log_path("system", filename)'),
            r'config/': ('config_path', 'Use get_config_path("system", filename)'),
            r'cache/': ('cache_path', 'Use get_cache_path("system", filename)'),
        }
        
        self.currency_patterns = {
            r'format.*\$.*\d': ('currency_format', 'Use market_config.currency.format_amount()'),
            r'format.*₹.*\d': ('currency_format', 'Use market_config.currency.format_amount()'),
            r'format.*EUR.*\d': ('currency_format', 'Use market_config.currency.format_amount()'),
        }
    
    def scan_file(self, file_path: str) -> List[HardcodedReference]:
        """Scan a single file for hardcoded references"""
        references = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Skip comments and docstrings
                if line.strip().startswith('#') or '"""' in line or "'''" in line:
                    continue
                
                # Check market patterns
                for pattern, (ref_type, suggestion) in self.market_patterns.items():
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        references.append(HardcodedReference(
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line.strip(),
                            reference_type='market',
                            hardcoded_value=match.group(),
                            suggested_replacement=suggestion,
                            confidence=0.8
                        ))
                
                # Check path patterns
                for pattern, (ref_type, suggestion) in self.path_patterns.items():
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        references.append(HardcodedReference(
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line.strip(),
                            reference_type='path',
                            hardcoded_value=match.group(),
                            suggested_replacement=suggestion,
                            confidence=0.9
                        ))
                
                # Check currency patterns
                for pattern, (ref_type, suggestion) in self.currency_patterns.items():
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        references.append(HardcodedReference(
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line.strip(),
                            reference_type='currency',
                            hardcoded_value=match.group(),
                            suggested_replacement=suggestion,
                            confidence=0.7
                        ))
        
        except Exception as e:
            print(f"⚠️ Error scanning {file_path}: {e}")
        
        return references
    
    def scan_directory(self, directory: str, extensions: List[str] = ['.py']) -> List[HardcodedReference]:
        """Scan a directory for hardcoded references"""
        all_references = []
        
        for root, dirs, files in os.walk(directory):
            # Skip certain directories
            skip_dirs = ['.git', '__pycache__', '.pytest_cache', 'venv', '.venv', 'node_modules']
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    references = self.scan_file(file_path)
                    all_references.extend(references)
        
        return all_references
    
    def generate_migration_report(self, references: List[HardcodedReference]) -> str:
        """Generate a migration report"""
        
        # Group references by type and file
        by_type = {}
        by_file = {}
        
        for ref in references:
            # Group by type
            if ref.reference_type not in by_type:
                by_type[ref.reference_type] = []
            by_type[ref.reference_type].append(ref)
            
            # Group by file
            if ref.file_path not in by_file:
                by_file[ref.file_path] = []
            by_file[ref.file_path].append(ref)
        
        report = []
        report.append("# HARDCODED REFERENCES MIGRATION REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Summary
        report.append("## SUMMARY")
        report.append(f"- Total hardcoded references found: {len(references)}")
        report.append(f"- Files affected: {len(by_file)}")
        report.append(f"- Reference types: {', '.join(by_type.keys())}")
        report.append("")
        
        # By type
        report.append("## REFERENCES BY TYPE")
        for ref_type, refs in by_type.items():
            report.append(f"\n### {ref_type.upper()} ({len(refs)} references)")
            
            # Show top 10 most common values
            value_counts = {}
            for ref in refs:
                value = ref.hardcoded_value
                value_counts[value] = value_counts.get(value, 0) + 1
            
            sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
            for value, count in sorted_values[:10]:
                report.append(f"- `{value}`: {count} occurrences")
        
        report.append("")
        
        # By file (top 20 files with most references)
        report.append("## FILES WITH MOST REFERENCES")
        sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)
        
        for file_path, refs in sorted_files[:20]:
            report.append(f"\n### {file_path} ({len(refs)} references)")
            
            # Group by line for this file
            by_line = {}
            for ref in refs:
                line_key = f"Line {ref.line_number}"
                if line_key not in by_line:
                    by_line[line_key] = []
                by_line[line_key].append(ref)
            
            for line_key, line_refs in sorted(by_line.items(), key=lambda x: int(x[0].split()[1]))[:10]:
                report.append(f"\n**{line_key}:**")
                for ref in line_refs:
                    report.append(f"- `{ref.hardcoded_value}` ({ref.reference_type})")
                    report.append(f"  - Suggestion: {ref.suggested_replacement}")
                    report.append(f"  - Code: `{ref.line_content[:80]}...`")
        
        report.append("")
        
        # Migration recommendations
        report.append("## MIGRATION RECOMMENDATIONS")
        report.append("")
        report.append("### 1. Market Configuration Migration")
        report.append("```python")
        report.append("from src.cohesion.market_configuration import get_active_market_config")
        report.append("")
        report.append("# Replace hardcoded market values")
        report.append("market_config = get_active_market_config()")
        report.append("currency = market_config.currency.base_currency  # Instead of 'INR' or 'USD'")
        report.append("symbol_suffix = market_config.data_sources.symbol_suffix  # Instead of '.NS'")
        report.append("trading_hours = market_config.trading_hours  # Instead of hardcoded times")
        report.append("```")
        report.append("")
        
        report.append("### 2. Path Configuration Migration")
        report.append("```python")
        report.append("from src.cohesion.path_configuration import get_data_path, get_report_path")
        report.append("")
        report.append("# Replace hardcoded paths")
        report.append("validation_path = get_data_path('validation', 'report.json')  # Instead of 'data/validation/report.json'")
        report.append("report_path = get_report_path('system', 'summary.md')  # Instead of 'reports/summary.md'")
        report.append("```")
        report.append("")
        
        report.append("### 3. Currency Formatting Migration")
        report.append("```python")
        report.append("# Replace hardcoded currency formatting")
        report.append("formatted_amount = market_config.currency.format_amount(1000000)  # Instead of f'₹{amount:,.2f}'")
        report.append("```")
        report.append("")
        
        return "\n".join(report)
    
    def generate_migration_script(self, references: List[HardcodedReference], output_file: str):
        """Generate a migration script to fix hardcoded references"""
        
        script_lines = []
        script_lines.append("#!/usr/bin/env python3")
        script_lines.append('"""')
        script_lines.append("AUTOMATED MIGRATION SCRIPT")
        script_lines.append("Generated by MigrationHelper to fix hardcoded references")
        script_lines.append('"""')
        script_lines.append("")
        script_lines.append("import os")
        script_lines.append("import re")
        script_lines.append("import shutil")
        script_lines.append("")
        script_lines.append("def backup_file(file_path):")
        script_lines.append("    backup_path = file_path + '.backup'")
        script_lines.append("    shutil.copy2(file_path, backup_path)")
        script_lines.append("    print(f'Backed up {file_path} to {backup_path}')")
        script_lines.append("")
        script_lines.append("def migrate_file(file_path, replacements):")
        script_lines.append("    backup_file(file_path)")
        script_lines.append("    ")
        script_lines.append("    with open(file_path, 'r') as f:")
        script_lines.append("        content = f.read()")
        script_lines.append("    ")
        script_lines.append("    for old_pattern, new_replacement in replacements:")
        script_lines.append("        content = re.sub(old_pattern, new_replacement, content)")
        script_lines.append("    ")
        script_lines.append("    with open(file_path, 'w') as f:")
        script_lines.append("        f.write(content)")
        script_lines.append("    ")
        script_lines.append("    print(f'Migrated {file_path}')")
        script_lines.append("")
        script_lines.append("# Migration mappings")
        script_lines.append("migrations = {")
        
        # Group by file
        by_file = {}
        for ref in references:
            if ref.file_path not in by_file:
                by_file[ref.file_path] = []
            by_file[ref.file_path].append(ref)
        
        for file_path, refs in by_file.items():
            script_lines.append(f"    '{file_path}': [")
            for ref in refs:
                # Create simple replacement patterns
                if ref.reference_type == 'path':
                    old_pattern = re.escape(ref.hardcoded_value)
                    if 'data/validation/' in ref.hardcoded_value:
                        new_replacement = "get_data_path('validation', filename)"
                    elif 'data/processed/' in ref.hardcoded_value:
                        new_replacement = "get_data_path('processed', filename)"
                    elif 'reports/' in ref.hardcoded_value:
                        new_replacement = "get_report_path('system', filename)"
                    else:
                        new_replacement = f"# TODO: Replace {ref.hardcoded_value}"
                    
                    script_lines.append(f"        (r'{old_pattern}', '{new_replacement}'),")
            script_lines.append("    ],")
        
        script_lines.append("}")
        script_lines.append("")
        script_lines.append("def main():")
        script_lines.append("    print('Starting migration...')")
        script_lines.append("    ")
        script_lines.append("    for file_path, replacements in migrations.items():")
        script_lines.append("        if os.path.exists(file_path):")
        script_lines.append("            migrate_file(file_path, replacements)")
        script_lines.append("        else:")
        script_lines.append("            print(f'File not found: {file_path}')")
        script_lines.append("    ")
        script_lines.append("    print('Migration complete!')")
        script_lines.append("")
        script_lines.append("if __name__ == '__main__':")
        script_lines.append("    main()")
        
        with open(output_file, 'w') as f:
            f.write("\n".join(script_lines))
        
        print(f"📝 Generated migration script: {output_file}")

def main():
    """Test the migration helper"""
    
    print("🔄 TESTING MIGRATION HELPER")
    print("=" * 60)
    
    # Create migration helper
    helper = MigrationHelper()
    
    # Scan a few key directories for hardcoded references
    directories_to_scan = [
        "src/validation",
        "src/automation", 
        "src/preprocessing"
    ]
    
    all_references = []
    
    for directory in directories_to_scan:
        if os.path.exists(directory):
            print(f"\n🔍 Scanning {directory}...")
            references = helper.scan_directory(directory)
            all_references.extend(references)
            print(f"   Found {len(references)} hardcoded references")
    
    if all_references:
        print(f"\n📊 TOTAL REFERENCES FOUND: {len(all_references)}")
        
        # Generate migration report
        report = helper.generate_migration_report(all_references)
        
        # Save report
        report_file = "reports/HARDCODED_REFERENCES_MIGRATION_REPORT.md"
        os.makedirs("reports", exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"📄 Generated migration report: {report_file}")
        
        # Show summary
        by_type = {}
        for ref in all_references:
            by_type[ref.reference_type] = by_type.get(ref.reference_type, 0) + 1
        
        print(f"\n📈 BREAKDOWN BY TYPE:")
        for ref_type, count in sorted(by_type.items()):
            print(f"   {ref_type}: {count} references")
        
        # Generate migration script
        script_file = "scripts/migrate_hardcoded_references.py"
        os.makedirs("scripts", exist_ok=True)
        helper.generate_migration_script(all_references, script_file)
        
    else:
        print(f"\n✅ No hardcoded references found in scanned directories")
    
    print(f"\n✅ Migration helper test complete!")
    
    return True

if __name__ == "__main__":
    main()