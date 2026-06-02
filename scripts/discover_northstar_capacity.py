#!/usr/bin/env python3
"""
Discover NorthStar deployable capacity and generate institutional report.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.validation.capacity_analysis_engine import CapacityAnalysisEngine
from src.validation.capacity_stress_tester import CapacityStressTester


def run_discovery() -> dict:
    engine = CapacityAnalysisEngine()
    base_report = engine.run_capacity_sweep()
    curve_exports = engine.export_capacity_curves(
        base_report,
        output_dir=PROJECT_ROOT / "reports/capacity",
        file_stem="northstar_capacity_curves",
    )

    stress_tester = CapacityStressTester(engine)
    stress_report = stress_tester.run_stress_tests()
    stress_path = stress_tester.export_report(
        stress_report,
        output_dir=PROJECT_ROOT / "reports/capacity",
        file_name="northstar_capacity_stress_report.json",
    )

    # Final recommendation prioritizes stress-adjusted estimate.
    recommended_aum = float(
        min(base_report.max_recommended_aum, stress_report.stress_adjusted_recommendation)
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_report": base_report.to_dict(),
        "stress_report_path": stress_path,
        "curve_exports": curve_exports,
        "final_recommendation": {
            "capacity_knee_aum": base_report.capacity_knee_aum,
            "max_recommended_aum": base_report.max_recommended_aum,
            "stress_adjusted_aum": stress_report.stress_adjusted_recommendation,
            "deployable_aum_recommendation": recommended_aum,
        },
    }

    out_dir = PROJECT_ROOT / "reports/capacity"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "northstar_capacity_report.json"
    out_file.write_text(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover NorthStar deployable capacity.")
    parser.parse_args()

    payload = run_discovery()
    rec = payload["final_recommendation"]
    print("✅ NorthStar capacity discovery complete")
    print(f"   Capacity knee: ${rec['capacity_knee_aum']:,.0f}")
    print(f"   Max recommended AUM: ${rec['max_recommended_aum']:,.0f}")
    print(f"   Stress-adjusted AUM: ${rec['stress_adjusted_aum']:,.0f}")
    print(f"   Deployable recommendation: ${rec['deployable_aum_recommendation']:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
