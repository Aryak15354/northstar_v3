#!/usr/bin/env python3
"""
📊 NORTHSTAR V3 CODE ANALYSIS
Comprehensive line count and codebase analysis for Northstar V3
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
import json

def count_lines_in_file(file_path):
    """Count lines in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            total_lines = len(lines)
            code_lines = 0
            comment_lines = 0
            blank_lines = 0
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    blank_lines += 1
                elif stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                    comment_lines += 1
                else:
                    code_lines += 1
            
            return {
                'total': total_lines,
                'code': code_lines,
                'comments': comment_lines,
                'blank': blank_lines
            }
    except Exception as e:
        return {'total': 0, 'code': 0, 'comments': 0, 'blank': 0, 'error': str(e)}

def analyze_codebase():
    """Analyze the entire Northstar V3 codebase"""
    
    print("📊 NORTHSTAR V3 CODEBASE ANALYSIS")
    print("=" * 70)
    
    # Define file extensions to analyze
    code_extensions = {
        '.py': 'Python',
        '.js': 'JavaScript', 
        '.jsx': 'React JSX',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript JSX',
        '.md': 'Markdown',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.json': 'JSON',
        '.toml': 'TOML',
        '.txt': 'Text',
        '.csv': 'CSV',
        '.sql': 'SQL'
    }
    
    # Directories to exclude
    exclude_dirs = {
        '__pycache__', 
        '.git', 
        'node_modules', 
        '.vscode', 
        '.kiro',
        'venv',
        '.pytest_cache',
        'logs',
        'backups'
    }
    
    # Initialize counters
    stats_by_extension = defaultdict(lambda: {'files': 0, 'total': 0, 'code': 0, 'comments': 0, 'blank': 0})
    stats_by_directory = defaultdict(lambda: {'files': 0, 'total': 0, 'code': 0, 'comments': 0, 'blank': 0})
    all_files = []
    
    # Walk through the codebase
    root_path = Path('.')
    
    for file_path in root_path.rglob('*'):
        if file_path.is_file():
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
            
            # Get file extension
            extension = file_path.suffix.lower()
            
            # Only analyze known code file types
            if extension in code_extensions:
                # Count lines
                line_stats = count_lines_in_file(file_path)
                
                if 'error' not in line_stats:
                    # Update extension stats
                    ext_stats = stats_by_extension[extension]
                    ext_stats['files'] += 1
                    ext_stats['total'] += line_stats['total']
                    ext_stats['code'] += line_stats['code']
                    ext_stats['comments'] += line_stats['comments']
                    ext_stats['blank'] += line_stats['blank']
                    
                    # Update directory stats
                    dir_name = str(file_path.parent)
                    if dir_name == '.':
                        dir_name = 'root'
                    
                    dir_stats = stats_by_directory[dir_name]
                    dir_stats['files'] += 1
                    dir_stats['total'] += line_stats['total']
                    dir_stats['code'] += line_stats['code']
                    dir_stats['comments'] += line_stats['comments']
                    dir_stats['blank'] += line_stats['blank']
                    
                    # Store file info
                    all_files.append({
                        'path': str(file_path),
                        'extension': extension,
                        'language': code_extensions[extension],
                        'directory': dir_name,
                        'stats': line_stats
                    })
    
    # Calculate totals
    total_files = sum(stats['files'] for stats in stats_by_extension.values())
    total_lines = sum(stats['total'] for stats in stats_by_extension.values())
    total_code = sum(stats['code'] for stats in stats_by_extension.values())
    total_comments = sum(stats['comments'] for stats in stats_by_extension.values())
    total_blank = sum(stats['blank'] for stats in stats_by_extension.values())
    
    # Display results
    print(f"\n🎯 OVERALL STATISTICS")
    print("-" * 50)
    print(f"Total Files: {total_files:,}")
    print(f"Total Lines: {total_lines:,}")
    print(f"Code Lines: {total_code:,}")
    print(f"Comment Lines: {total_comments:,}")
    print(f"Blank Lines: {total_blank:,}")
    
    # Display by language
    print(f"\n📝 BY LANGUAGE")
    print("-" * 70)
    print(f"{'Language':<15} {'Files':<8} {'Total':<10} {'Code':<10} {'Comments':<10} {'Blank':<8}")
    print("-" * 70)
    
    for ext in sorted(stats_by_extension.keys()):
        stats = stats_by_extension[ext]
        language = code_extensions[ext]
        print(f"{language:<15} {stats['files']:<8} {stats['total']:<10,} {stats['code']:<10,} {stats['comments']:<10,} {stats['blank']:<8,}")
    
    # Display top directories
    print(f"\n📁 TOP DIRECTORIES BY CODE LINES")
    print("-" * 70)
    print(f"{'Directory':<30} {'Files':<8} {'Total':<10} {'Code':<10}")
    print("-" * 70)
    
    sorted_dirs = sorted(stats_by_directory.items(), key=lambda x: x[1]['code'], reverse=True)
    for dir_name, stats in sorted_dirs[:15]:  # Top 15 directories
        short_name = dir_name if len(dir_name) <= 29 else dir_name[:26] + "..."
        print(f"{short_name:<30} {stats['files']:<8} {stats['total']:<10,} {stats['code']:<10,}")
    
    # Display largest files
    print(f"\n📄 LARGEST FILES BY CODE LINES")
    print("-" * 70)
    print(f"{'File':<40} {'Language':<12} {'Code':<8} {'Total':<8}")
    print("-" * 70)
    
    sorted_files = sorted(all_files, key=lambda x: x['stats']['code'], reverse=True)
    for file_info in sorted_files[:15]:  # Top 15 files
        file_name = file_info['path']
        if len(file_name) > 39:
            file_name = "..." + file_name[-36:]
        
        print(f"{file_name:<40} {file_info['language']:<12} {file_info['stats']['code']:<8,} {file_info['stats']['total']:<8,}")
    
    # Institutional Alpha Engine specific analysis
    print(f"\n🏛️ INSTITUTIONAL ALPHA ENGINE ANALYSIS")
    print("-" * 70)
    
    alpha_engine_files = [f for f in all_files if 'intelligence' in f['path'] and f['extension'] == '.py']
    alpha_engine_code = sum(f['stats']['code'] for f in alpha_engine_files)
    alpha_engine_total = sum(f['stats']['total'] for f in alpha_engine_files)
    
    print(f"Alpha Engine Files: {len(alpha_engine_files)}")
    print(f"Alpha Engine Code Lines: {alpha_engine_code:,}")
    print(f"Alpha Engine Total Lines: {alpha_engine_total:,}")
    
    # Key system files
    key_files = [
        'src/intelligence/institutional_alpha_engine.py',
        'src/intelligence/regime_aware_specialists.py',
        'src/intelligence/bayesian_capital_tribunal.py',
        'src/intelligence/portfolio_governor.py',
        'src/intelligence/signal_health_monitor.py',
        'src/intelligence/real_time_health_monitor.py',
        'src/intelligence/economic_causality_validator.py',
        'src/intelligence/stress_testing_system.py',
        'src/reporting/institutional_reporting_system.py'
    ]
    
    print(f"\n🎯 KEY INSTITUTIONAL ALPHA ENGINE FILES")
    print("-" * 50)
    for key_file in key_files:
        file_info = next((f for f in all_files if f['path'] == key_file), None)
        if file_info:
            print(f"{key_file.split('/')[-1]:<35} {file_info['stats']['code']:>6} lines")
        else:
            print(f"{key_file.split('/')[-1]:<35} {'N/A':>6}")
    
    # Save detailed report
    report = {
        'summary': {
            'total_files': total_files,
            'total_lines': total_lines,
            'code_lines': total_code,
            'comment_lines': total_comments,
            'blank_lines': total_blank
        },
        'by_language': dict(stats_by_extension),
        'by_directory': dict(stats_by_directory),
        'alpha_engine': {
            'files': len(alpha_engine_files),
            'code_lines': alpha_engine_code,
            'total_lines': alpha_engine_total
        },
        'timestamp': '2026-01-04'
    }
    
    os.makedirs('reports', exist_ok=True)
    with open('reports/northstar_v3_code_analysis.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Detailed report saved to: reports/northstar_v3_code_analysis.json")
    
    return report

if __name__ == "__main__":
    analyze_codebase()