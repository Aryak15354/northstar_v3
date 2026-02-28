#!/usr/bin/env python3
"""
📊 INSTITUTIONAL REPORT GENERATOR - COMPLETE SPECIFICATION
Generates the exact institutional report format with:
- Per-window summary table
- Distribution plots (showing pain, not hiding it)
- Worst-case narrative (mandatory)
- System behavior validation
- Interpretation guidelines

Usage:
    python scripts/generate_institutional_report_complete.py
"""

import json
import os
import tempfile
import pandas as pd
import numpy as np

# Ensure matplotlib can write cache in restricted environments.
os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(tempfile.gettempdir(), "northstar_mpl_cache"),
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import warnings

warnings.filterwarnings('ignore')

class InstitutionalReportGenerator:
    """
    Generate institutional-grade reports following exact specification
    
    Report Structure:
    A. Per-Window Summary Table
    B. Distribution Plots (don't cherry-pick)
    C. Worst-Case Narrative (MANDATORY)
    D. System Behavior Validation
    E. Interpretation Guidelines
    """
    
    def __init__(self):
        self.name = "Institutional Report Generator"
        self.version = "1.0.0"
        
    def load_latest_validation_results(self) -> Dict[str, Any]:
        """Load the latest institutional validation results"""
        
        results_dir = Path("data/validation/institutional_complete")
        if not results_dir.exists():
            raise FileNotFoundError("No institutional validation results found")
        
        # Find latest report
        report_files = list(results_dir.glob("institutional_walk_forward_report_*.json"))
        if not report_files:
            raise FileNotFoundError("No validation report files found")
        
        latest_file = max(report_files, key=lambda x: x.stat().st_mtime)
        
        print(f"📊 Loading validation results: {latest_file.name}")
        
        with open(latest_file, 'r') as f:
            results = json.load(f)
        
        return results
    
    def generate_summary_table_markdown(self, results: Dict[str, Any]) -> str:
        """Generate A. Per-Window Summary Table in markdown format"""
        
        summary_table = results.get('summary_table', [])
        if not summary_table:
            return "No summary table data available"
        
        markdown = "## A. Per-Window Summary Table\n\n"
        markdown += "| Year | Return | Sharpe | Max DD | Avg Exposure | Risk-On % | Regime Flips | Shutdowns | Overrides |\n"
        markdown += "|------|--------|--------|--------|--------------|-----------|--------------|-----------|----------|\n"
        
        for row in summary_table:
            markdown += f"| {row['Year']} | {row['Return']} | {row['Sharpe']} | {row['Max_DD']} | {row['Avg_Exposure']} | {row['Risk_On_%']} | {row['Regime_Flips']} | {row['Shutdowns']} | {row['Overrides']} |\n"
        
        return markdown
    
    def generate_distribution_plots(self, results: Dict[str, Any]) -> str:
        """Generate B. Distribution Plots (showing pain, not hiding it)"""
        
        distributions = results.get('distributions', {})
        if not distributions:
            return "No distribution data available"
        
        # Create plots directory
        plots_dir = Path("data/validation/institutional_complete/plots")
        plots_dir.mkdir(exist_ok=True)
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Distribution Analysis - Showing Reality, Not Hiding Pain', fontsize=16, fontweight='bold')
        
        # Extract data from summary table for plotting
        summary_table = results.get('summary_table', [])
        if summary_table:
            returns = [float(row['Return'].replace('%', '').replace('+', '')) for row in summary_table]
            drawdowns = [float(row['Max_DD'].replace('%', '')) for row in summary_table]
            exposures = [float(row['Avg_Exposure'].replace('%', '')) for row in summary_table]
            years = [row['Year'] for row in summary_table]
        else:
            returns = drawdowns = exposures = years = []
        
        # 1. Returns Distribution
        if returns:
            axes[0, 0].hist(returns, bins=max(3, len(returns)//2), alpha=0.7, color='steelblue', edgecolor='black')
            axes[0, 0].axvline(np.mean(returns), color='red', linestyle='--', label=f'Mean: {np.mean(returns):.1f}%')
            axes[0, 0].axvline(np.min(returns), color='darkred', linestyle=':', label=f'Worst: {np.min(returns):.1f}%')
            axes[0, 0].set_title('Returns Distribution\n(Showing the full reality)')
            axes[0, 0].set_xlabel('Annual Return (%)')
            axes[0, 0].set_ylabel('Frequency')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Drawdown Distribution
        if drawdowns:
            axes[0, 1].hist(drawdowns, bins=max(3, len(drawdowns)//2), alpha=0.7, color='crimson', edgecolor='black')
            axes[0, 1].axvline(np.mean(drawdowns), color='darkred', linestyle='--', label=f'Mean: {np.mean(drawdowns):.1f}%')
            axes[0, 1].axvline(np.max(drawdowns), color='red', linestyle=':', label=f'Worst: {np.max(drawdowns):.1f}%')
            axes[0, 1].set_title('Drawdown Distribution\n(Pain is part of the story)')
            axes[0, 1].set_xlabel('Maximum Drawdown (%)')
            axes[0, 1].set_ylabel('Frequency')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Exposure Distribution
        if exposures:
            axes[1, 0].hist(exposures, bins=max(3, len(exposures)//2), alpha=0.7, color='forestgreen', edgecolor='black')
            axes[1, 0].axvline(np.mean(exposures), color='darkgreen', linestyle='--', label=f'Mean: {np.mean(exposures):.1f}%')
            axes[1, 0].set_title('Exposure Distribution\n(Conviction under pressure)')
            axes[1, 0].set_xlabel('Average Exposure (%)')
            axes[1, 0].set_ylabel('Frequency')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Time Series of Returns (showing lumpy nature)
        if returns and years:
            axes[1, 1].plot(years, returns, 'o-', color='steelblue', linewidth=2, markersize=8)
            axes[1, 1].axhline(0, color='black', linestyle='-', alpha=0.3)
            axes[1, 1].axhline(np.mean(returns), color='red', linestyle='--', alpha=0.7, label=f'Mean: {np.mean(returns):.1f}%')
            axes[1, 1].set_title('Returns Over Time\n(Lumpy, not smooth - signature of conviction)')
            axes[1, 1].set_xlabel('Year')
            axes[1, 1].set_ylabel('Annual Return (%)')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_file = plots_dir / f"distribution_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        markdown = f"## B. Distribution Plots\n\n"
        markdown += f"**Purpose**: Show the pain, don't hide it. Reality includes:\n"
        markdown += f"- Lumpy returns (not smooth equity)\n"
        markdown += f"- Meaningful drawdowns (pain that teaches)\n"
        markdown += f"- Variable exposure (conviction under pressure)\n"
        markdown += f"- Clustered performance (asymmetric payoffs)\n\n"
        markdown += f"![Distribution Analysis]({plot_file.name})\n\n"
        
        # Add statistical summary
        if returns:
            markdown += f"### Statistical Summary\n\n"
            markdown += f"**Returns**: Mean {np.mean(returns):.1f}%, Std {np.std(returns):.1f}%, Min {np.min(returns):.1f}%, Max {np.max(returns):.1f}%\n\n"
            markdown += f"**Drawdowns**: Mean {np.mean(drawdowns):.1f}%, Max {np.max(drawdowns):.1f}%\n\n"
            markdown += f"**Exposures**: Mean {np.mean(exposures):.1f}%, Std {np.std(exposures):.1f}%\n\n"
        
        return markdown
    
    def generate_worst_case_narrative(self, results: Dict[str, Any]) -> str:
        """Generate C. Worst-Case Narrative (MANDATORY)"""
        
        worst_case = results.get('worst_case_narrative', '')
        if not worst_case:
            return "No worst-case narrative available"
        
        markdown = "## C. Worst-Case Narrative (MANDATORY)\n\n"
        markdown += "### The Critical Question\n\n"
        markdown += worst_case + "\n\n"
        
        markdown += "### Decision Framework\n\n"
        markdown += "**If YES** → System passes institutional validation\n"
        markdown += "- Proceed with current configuration\n"
        markdown += "- Establish monitoring procedures\n"
        markdown += "- Document operational procedures\n\n"
        
        markdown += "**If NO** → Adjust exposure expectations, NOT system logic\n"
        markdown += "- Reduce initial capital allocation\n"
        markdown += "- Lower leverage if applicable\n"
        markdown += "- DO NOT modify system parameters\n\n"
        
        markdown += "### Remember\n"
        markdown += "This question separates institutional discipline from self-deception.\n"
        markdown += "The system's job is to deliver its truth. Your job is to decide if you can live with it.\n\n"
        
        return markdown
    
    def generate_behavior_validation(self, results: Dict[str, Any]) -> str:
        """Generate D. System Behavior Validation"""
        
        behavior = results.get('behavior_validation', {})
        if not behavior:
            return "No behavior validation data available"
        
        markdown = "## D. System Behavior Validation\n\n"
        markdown += "### The Five Critical Questions\n\n"
        
        questions = {
            'system_behaved_as_designed': "Did the system behave exactly as designed?",
            'stayed_exposed_when_uncomfortable': "Did it stay exposed when uncomfortable?",
            'exited_only_for_structural_reasons': "Did it exit only for structural reasons?",
            'drawdowns_within_covenant': "Did drawdowns stay within covenant?",
            'payoff_profile_shows_asymmetry': "Does the payoff profile show asymmetry?"
        }
        
        all_passed = True
        for key, question in questions.items():
            passed = behavior.get(key, False)
            status = "✅ YES" if passed else "❌ NO"
            markdown += f"**{question}**\n{status}\n\n"
            if not passed:
                all_passed = False
        
        markdown += "### Overall Assessment\n\n"
        if all_passed:
            markdown += "✅ **SYSTEM PASSES BEHAVIOR VALIDATION**\n\n"
            markdown += "The system demonstrated institutional discipline:\n"
            markdown += "- Followed rules exactly as designed\n"
            markdown += "- Maintained exposure during uncomfortable periods\n"
            markdown += "- Respected risk management covenants\n"
            markdown += "- Showed asymmetric payoff profile\n\n"
        else:
            markdown += "❌ **SYSTEM FAILS BEHAVIOR VALIDATION**\n\n"
            markdown += "The system violated institutional discipline. Address fundamental issues before proceeding.\n\n"
        
        return markdown
    
    def generate_interpretation_guidelines(self, results: Dict[str, Any]) -> str:
        """Generate E. Interpretation Guidelines"""
        
        markdown = "## E. Interpretation Guidelines\n\n"
        
        markdown += "### 🚫 Wrong Interpretation\n\n"
        markdown += "- \"Sharpe is lower than live → system is worse\"\n"
        markdown += "- \"This year underperformed → strategy is broken\"\n"
        markdown += "- \"If we tweak X, this improves\"\n\n"
        
        markdown += "### ✅ Correct Interpretation\n\n"
        markdown += "Ask ONLY these questions:\n"
        markdown += "1. Did the system behave exactly as designed?\n"
        markdown += "2. Did it stay exposed when uncomfortable?\n"
        markdown += "3. Did it exit only for structural reasons?\n"
        markdown += "4. Did drawdowns stay within covenant?\n"
        markdown += "5. Does the payoff profile show asymmetry?\n\n"
        
        markdown += "**If YES to all** → System passes, even if some years underperform\n\n"
        
        markdown += "### What Success Actually Looks Like\n\n"
        markdown += "A successful walk-forward does **NOT** look like:\n"
        markdown += "- Smooth equity curve\n"
        markdown += "- Constant Sharpe ratio\n"
        markdown += "- Always beating benchmark\n\n"
        
        markdown += "It **DOES** look like:\n"
        markdown += "- Lumpy returns\n"
        markdown += "- Long flat periods\n"
        markdown += "- Sharp recovery phases\n"
        markdown += "- Drawdowns that hurt but don't kill\n"
        markdown += "- Outsized gains clustered in specific years\n\n"
        
        markdown += "**That is the signature of conviction.**\n\n"
        
        markdown += "### After the Report - What to Do\n\n"
        
        markdown += "**If results are mixed but disciplined:**\n"
        markdown += "- ✅ Proceed live\n"
        markdown += "- ❌ Do NOT tweak parameters\n\n"
        
        markdown += "**If results violate drawdown covenant:**\n"
        markdown += "- ✅ Reduce initial capital or leverage\n"
        markdown += "- ❌ Do NOT soften exits\n\n"
        
        markdown += "**If results are too smooth:**\n"
        markdown += "- ⚠️ You are still under-expressed\n"
        markdown += "- ❌ Do NOT congratulate yourself\n\n"
        
        return markdown
    
    def generate_system_integrity_summary(self, results: Dict[str, Any]) -> str:
        """Generate system integrity and data quality summary"""
        
        integrity = results.get('system_integrity', {})
        if not integrity:
            return "No system integrity data available"
        
        markdown = "## System Integrity & Data Quality\n\n"
        
        # Data integrity status
        data_integrity_passed = integrity.get('data_integrity_passed', False)
        status = "✅ PASSED" if data_integrity_passed else "❌ FAILED"
        markdown += f"**Data Integrity Checklist**: {status}\n\n"
        
        if data_integrity_passed:
            markdown += "All 5 layers of data integrity checks passed:\n"
            markdown += "- Layer 1: Raw Data Integrity ✅\n"
            markdown += "- Layer 2: Signal Integrity ✅\n"
            markdown += "- Layer 3: Execution Realism ✅\n"
            markdown += "- Layer 4: Portfolio Accounting ✅\n"
            markdown += "- Layer 5: Interpretation & Reporting ✅\n\n"
        else:
            failed_checks = integrity.get('failed_checks', 0)
            total_checks = integrity.get('total_integrity_checks', 0)
            markdown += f"**{failed_checks} of {total_checks} integrity checks failed**\n\n"
            markdown += "🚨 **VALIDATION INVALID** - Results must be discarded entirely\n\n"
        
        # System discipline metrics
        override_attempts = integrity.get('override_attempts', 0)
        validation_violations = integrity.get('validation_violations', 0)
        
        markdown += f"**Override Attempts**: {override_attempts} (should be 0)\n"
        markdown += f"**Validation Violations**: {validation_violations}\n"
        markdown += f"**Rules Hash**: `{integrity.get('rules_hash', 'N/A')[:16]}...`\n\n"
        
        if override_attempts == 0 and validation_violations == 0:
            markdown += "✅ **Perfect Conviction Integrity** - No rule violations detected\n\n"
        else:
            markdown += "❌ **Conviction Integrity Compromised** - System violated frozen rules\n\n"
        
        return markdown
    
    def generate_complete_institutional_report(self) -> str:
        """Generate the complete institutional report"""
        
        print(f"📊 {self.name} v{self.version}")
        print("Generating institutional-grade report...")
        
        # Load validation results
        try:
            results = self.load_latest_validation_results()
        except Exception as e:
            return f"Error loading validation results: {e}"
        
        # Generate report sections
        report = []
        
        # Header
        report.append("# INSTITUTIONAL 12-MONTH WALK-FORWARD VALIDATION REPORT")
        report.append("## Historical Behavior Verification Under Frozen Rules")
        report.append("")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Validation Status**: {results.get('validation_status', 'UNKNOWN')}")
        report.append(f"**Windows Processed**: {results.get('windows_processed', 0)}")
        report.append(f"**Execution Time**: {results.get('execution_timestamp', 'N/A')}")
        report.append("")
        report.append("---")
        report.append("")
        
        # Executive Summary
        validation_status = results.get('validation_status', 'UNKNOWN')
        if validation_status == 'PASS':
            report.append("## 🎯 EXECUTIVE SUMMARY")
            report.append("")
            report.append("✅ **SYSTEM PASSES INSTITUTIONAL VALIDATION**")
            report.append("")
            report.append("The system has demonstrated institutional discipline under rigorous walk-forward testing.")
            report.append("All behavior validation criteria met. Ready for institutional consideration.")
            report.append("")
        else:
            report.append("## ⚠️ EXECUTIVE SUMMARY")
            report.append("")
            report.append("❌ **SYSTEM FAILS INSTITUTIONAL VALIDATION**")
            report.append("")
            report.append("The system violated institutional discipline criteria.")
            report.append("Address fundamental issues before proceeding to live deployment.")
            report.append("")
        
        report.append("---")
        report.append("")
        
        # A. Per-Window Summary Table
        report.append(self.generate_summary_table_markdown(results))
        report.append("")
        
        # B. Distribution Plots
        report.append(self.generate_distribution_plots(results))
        report.append("")
        
        # C. Worst-Case Narrative
        report.append(self.generate_worst_case_narrative(results))
        report.append("")
        
        # D. System Behavior Validation
        report.append(self.generate_behavior_validation(results))
        report.append("")
        
        # E. Interpretation Guidelines
        report.append(self.generate_interpretation_guidelines(results))
        report.append("")
        
        # System Integrity Summary
        report.append(self.generate_system_integrity_summary(results))
        report.append("")
        
        # Footer
        report.append("---")
        report.append("")
        report.append("## Final Reminder")
        report.append("")
        report.append("**This is a mirror, not a steering wheel.**")
        report.append("")
        report.append("You are checking: *\"Can I live with the truth of this system?\"*")
        report.append("")
        report.append("NOT: *\"How can I make it look better?\"*")
        report.append("")
        report.append("---")
        report.append("")
        report.append("*Generated by Institutional Walk-Forward Validator*")
        
        return "\n".join(report)
    
    def save_report(self, report_content: str):
        """Save the institutional report"""
        
        reports_dir = Path("data/validation/institutional_complete")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = reports_dir / f"INSTITUTIONAL_REPORT_{timestamp}.md"
        
        with open(report_file, 'w') as f:
            f.write(report_content)
        
        print(f"✅ Institutional report saved: {report_file}")
        return report_file

def main():
    """Generate institutional report"""
    
    print("📊 INSTITUTIONAL REPORT GENERATOR")
    print("=" * 60)
    print("Generating comprehensive institutional-grade report")
    print("Following exact specification requirements")
    print("=" * 60)
    
    generator = InstitutionalReportGenerator()
    
    try:
        # Generate complete report
        report_content = generator.generate_complete_institutional_report()
        
        # Save report
        report_file = generator.save_report(report_content)
        
        print("\n" + "=" * 60)
        print("REPORT GENERATION COMPLETE")
        print("=" * 60)
        print(f"Report saved: {report_file}")
        print("\nReport includes:")
        print("✅ Per-window summary table")
        print("✅ Distribution plots (showing pain)")
        print("✅ Worst-case narrative (mandatory)")
        print("✅ System behavior validation")
        print("✅ Interpretation guidelines")
        print("✅ System integrity summary")
        print("=" * 60)
        
        return report_file
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return None

if __name__ == "__main__":
    main()
