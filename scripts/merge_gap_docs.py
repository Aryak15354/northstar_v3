#!/usr/bin/env python3
"""
Merge Gap Documentation Files

This script merges all update/fix documents for each gap into a single consolidated file.
"""

from pathlib import Path
from datetime import datetime

# Define merge plan
MERGE_PLAN = {
    'GAP1': {
        'output': 'GAP1_FINAL.md',
        'files': [
            'GAP1_INGESTION_LAYER_COMPLETE_CONSOLIDATED.md',
            'GAP1_CRITICAL_FIXES_COMPLETE.md'
        ]
    },
    'GAP2': {
        'output': 'GAP2_FINAL.md',
        'files': [
            'GAP2_SENTIMENT_COMPLETE_CONSOLIDATED.md',
            'GAP2_SENTIMENT_COMPLETE_FINAL.md',
            'GAP2_SENTIMENT_FIXES_ACTUAL.md',
            'GAP2_ACTUAL_STATUS.md',
            'GAP2_FINAL_STATUS.md'
        ]
    },
    'GAP3': {
        'output': 'GAP3_FINAL.md',
        'files': [
            'GAP3_COMPLETE.md',
            'GAP3_IMPLEMENTATION_SUMMARY.md',
            'GAP3_README.md',
            'GAP3_ROBUST_COMPLETE.md',
            'GAP3_FINAL_STATUS.md'
        ]
    },
    'GAP4': {
        'output': 'GAP4_FINAL.md',
        'files': [
            'GAP4_ALPHA_OS_COMPLETE.md',
            'GAP4_ROBUST_COMPLETE.md'
        ]
    },
    'GAP5': {
        'output': 'GAP5_FINAL.md',
        'files': [
            'GAP5_IMPLEMENTATION_SUMMARY.md',
            'GAP5_README.md',
            'GAP5_ROBUST_IMPLEMENTATION_PLAN.md',
            'GAP5_ROBUST_COMPLETE.md',
            'GAP5_ACTUAL_STATUS.md',
            'GAP5_FINAL_HONEST_STATUS.md'
        ]
    },
    'GAP6': {
        'output': 'GAP6_FINAL.md',
        'files': [
            'GAP6_PORTFOLIO_GOVERNOR_COMPLETE.md',
            'GAP6_IMPLEMENTATION_SUMMARY.md',
            'GAP6_CRITICAL_INTEGRATION_FIXES.md',
            'GAP6_INTEGRATION_VERIFIED.md'
        ]
    },
    'GAP7': {
        'output': 'GAP7_FINAL.md',
        'files': [
            'GAP7_STATE_CONSOLIDATION_COMPLETE.md',
            'GAP7_README.md',
            'GAP7_INTEGRATION_COMPLETE.md'
        ]
    },
    'GAP8': {
        'output': 'GAP8_FINAL.md',
        'files': [
            'GAP8_DASHBOARD_CONSOLIDATION_COMPLETE.md',
            'GAP8_IMPLEMENTATION_SUMMARY.md',
            'GAP8_NEXT_STEPS.md',
            'GAP8_PHASE2_VISUALIZATION_PLAN.md',
            'GAP8_COMPLETE_FINAL_SUMMARY.md',
            'GAP8_DASHBOARD_AUDIT_AND_FIX_PLAN.md',
            'GAP8_HONEST_FINAL_STATUS.md',
            'GAP8_FIXES_COMPLETED_TODAY.md'
        ]
    }
}


def merge_gap_docs(gap_name, config):
    """Merge all documents for a gap into a single file"""
    print(f"\n{'='*80}")
    print(f"Merging {gap_name} Documentation")
    print(f"{'='*80}")
    
    output_file = Path(config['output'])
    source_files = config['files']
    
    # Start building merged content
    merged_content = []
    
    # Add header
    merged_content.append(f"# {gap_name} - Complete Documentation")
    merged_content.append("")
    merged_content.append(f"**Consolidated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    merged_content.append("")
    merged_content.append("This document consolidates all implementation, updates, and fixes for this gap.")
    merged_content.append("")
    merged_content.append("## Document History")
    merged_content.append("")
    
    # List source documents
    for i, filename in enumerate(source_files, 1):
        merged_content.append(f"{i}. `{filename}`")
    merged_content.append("")
    merged_content.append("---")
    merged_content.append("")
    
    # Merge each source file
    for i, filename in enumerate(source_files, 1):
        filepath = Path(filename)
        
        if not filepath.exists():
            print(f"  ⚠️  Warning: {filename} not found, skipping...")
            continue
        
        print(f"  ✅ Merging: {filename}")
        
        # Read source file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add section header
        merged_content.append(f"## Section {i}: {filepath.stem}")
        merged_content.append("")
        merged_content.append(f"**Source:** `{filename}`")
        merged_content.append("")
        
        # Add content
        merged_content.append(content)
        merged_content.append("")
        merged_content.append("---")
        merged_content.append("")
    
    # Write merged file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(merged_content))
    
    print(f"  📝 Created: {output_file}")
    print(f"  📊 Merged {len([f for f in source_files if Path(f).exists()])} files")
    
    return output_file


def main():
    print("="*80)
    print("Gap Documentation Merger")
    print("="*80)
    print("\nThis script will merge all update/fix documents into single files per gap.")
    print()
    
    created_files = []
    
    for gap_name, config in MERGE_PLAN.items():
        try:
            output_file = merge_gap_docs(gap_name, config)
            created_files.append(output_file)
        except Exception as e:
            print(f"  ❌ Error merging {gap_name}: {e}")
    
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print(f"\n✅ Successfully created {len(created_files)} consolidated files:")
    for f in created_files:
        print(f"  - {f}")
    
    print("\n📋 Old files can now be archived or deleted.")
    print("\nTo archive old files:")
    print("  mkdir -p archive/gap_docs")
    print("  mv GAP*_*.md archive/gap_docs/  # (except GAP*_FINAL.md)")


if __name__ == '__main__':
    main()
