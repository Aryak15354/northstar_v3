"""
Finish V3 Cleanup - Move remaining files
"""
from pathlib import Path
import shutil

workspace = Path.cwd()

# Remaining completion/summary reports to move
remaining_reports = [
    "INSTITUTIONAL_SAFEGUARDS_FINAL_SUMMARY.md",
    "INSTITUTIONAL_SAFEGUARDS_SUMMARY.md",
    "SYSTEM_FULLY_OPERATIONAL.md",
    "SYSTEM_INTEGRITY_INTEGRATION_SUMMARY.md",
    "SYSTEM_INTEGRITY_REPAIR_SUMMARY.md",
]

# Move to docs/completion_reports
dest_dir = workspace / "docs/completion_reports"
dest_dir.mkdir(parents=True, exist_ok=True)

moved = []
for report in remaining_reports:
    source = workspace / report
    if source.exists():
        dest = dest_dir / report
        shutil.move(str(source), str(dest))
        moved.append(report)
        print(f"✓ Moved: {report}")

# Move sealed_results.json to backups
sealed = workspace / "sealed_results.json"
if sealed.exists():
    dest = workspace / "backups" / "sealed_results.json"
    shutil.move(str(sealed), str(dest))
    moved.append("sealed_results.json")
    print(f"✓ Moved: sealed_results.json → backups/")

print(f"\n✓ Cleanup complete! Moved {len(moved)} files.")
