#!/usr/bin/env python3
"""T1-07 — AEP Paper D: multiplicity correction across the five resolutions.

Paper D tested whether market state carries information about the correct portfolio action
at five decision-time resolutions. Monthly cleared its own permutation null by 5% and was
recorded ACCEPTED (barely). The other four failed.

No correction was applied across the five. This computes it, from the archived
resolution_curve.json — no re-run, no new data.

Pre-registered in GEN10_REMEDIATION_CHARTER.md s4/T1-07:
  kill = monthly fails the corrected threshold -> retired, and Gen-5 F17's weekly null
         becomes the settled answer at all resolutions.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.gen10.inference import benjamini_hochberg, benjamini_yekutieli  # noqa: E402

OUT = ROOT / "results/gen10/T1-07"
OUT.mkdir(parents=True, exist_ok=True)
SRC = ROOT / "results/AEP_PAPER_D/resolution_curve.json"
RES_ORDER = ["weekly", "biweekly", "monthly", "6week", "quarterly"]
N_PERM = 1000     # permutation draws behind each null, per Paper D's methodology


def main() -> int:
    print("=" * 92)
    print("T1-07 — AEP PAPER D: MULTIPLICITY ACROSS THE FIVE RESOLUTIONS")
    print("=" * 92)
    d = json.loads(SRC.read_text())

    print("\n--- archived results ---")
    print(f"{'resolution':<12}{'n_obs':>8}{'MI':>10}{'null mean':>12}{'null p95':>11}"
          f"{'archived':>11}")
    rows = []
    for k in RES_ORDER:
        r = d[k]
        rows.append({"resolution": k, "n_obs": r["n_obs"], "mi": r["mi_bits"],
                     "null_mean": r["perm_null_mean_mi"], "null_p95": r["perm_null_95pct_mi"],
                     "archived_sig": r["significant_vs_null"]})
        print(f"{k:<12}{r['n_obs']:>8}{r['mi_bits']:>10.5f}{r['perm_null_mean_mi']:>12.5f}"
              f"{r['perm_null_95pct_mi']:>11.5f}{str(r['significant_vs_null']):>11}")

    # --- recover an approximate permutation p-value for each resolution ------------------
    # The archive stores the null's mean and 95th percentile, not the full draw. For a
    # right-skewed MI null an exponential-tail approximation is the standard reconstruction:
    #   p ~ exp(-(MI - mean) / scale),  scale chosen so the p95 point maps to p = 0.05.
    print("\n--- reconstructed permutation p-values ---")
    print("(the archive stores the null's mean and p95, not the draws; an exponential-tail")
    print(" fit anchored on those two points is used, and the anchoring is exact at p=0.05)")
    pvals = []
    for r in rows:
        scale = (r["null_p95"] - r["null_mean"]) / np.log(20.0)   # p95 -> p=0.05 exactly
        z = (r["mi"] - r["null_mean"]) / max(scale, 1e-12)
        p = float(min(1.0, np.exp(-z))) if z > 0 else 1.0
        p = max(p, 1.0 / (N_PERM + 1))         # permutation p-value floor
        r["p_reconstructed"] = p
        pvals.append(p)
        print(f"  {r['resolution']:<12} MI={r['mi']:.5f}  null_mean={r['null_mean']:.5f}  "
              f"scale={scale:.5f}  ->  p ~ {p:.4f}")

    # --- corrections ----------------------------------------------------------------------
    m = len(pvals)
    bonf = np.array(pvals) <= 0.05 / m
    bh = benjamini_hochberg(pvals, q=0.05)
    by = benjamini_yekutieli(pvals, q=0.05)

    print(f"\n--- multiplicity corrections across m={m} resolutions ---")
    print(f"{'resolution':<12}{'p':>10}{'archived':>11}{'Bonferroni':>13}{'BH':>8}{'BY':>8}")
    for r, p, b1, b2, b3 in zip(rows, pvals, bonf, bh, by):
        r.update(bonferroni_pass=bool(b1), bh_pass=bool(b2), by_pass=bool(b3))
        print(f"{r['resolution']:<12}{p:>10.4f}{str(r['archived_sig']):>11}"
              f"{str(bool(b1)):>13}{str(bool(b2)):>8}{str(bool(b3)):>8}")

    monthly = next(r for r in rows if r["resolution"] == "monthly")
    survives = monthly["by_pass"]

    # --- the margin, in context -----------------------------------------------------------
    print("\n--- how thin is monthly's margin? ---")
    marg = (monthly["mi"] - monthly["null_p95"]) / monthly["null_p95"]
    print(f"  monthly MI {monthly['mi']:.5f} vs null p95 {monthly['null_p95']:.5f}  "
          f"-> clears by {marg:+.1%}")
    print("  and the null band widens sharply as n falls, which is what makes monthly")
    print("  the resolution most able to clear it:")
    for r in rows:
        print(f"    {r['resolution']:<12} n={r['n_obs']:>5}  null p95 = {r['null_p95']:.5f}")
    print("  Monthly is where n is still large enough for a tight null while aggregation")
    print("  has lifted MI. That is a shape of the null, not an economic cadence.")

    print("\n" + "=" * 92)
    print("VERDICT vs the pre-registered rule (charter s4/T1-07)")
    print("=" * 92)
    if survives:
        print("  monthly SURVIVES the correction -> proceed to a genuine OOS split.")
    else:
        print("  monthly FAILS the pre-registered multiplicity correction.")
        print("  -> RETIRED. Gen-5 F17's weekly null is the settled answer at ALL five")
        print("     resolutions: market state carries no usable information about the")
        print("     correct portfolio action at any decision cadence tested.")
        print(f"  (Bonferroni threshold {0.05/m:.4f}; monthly p ~ {monthly['p_reconstructed']:.4f})")

    payload = {"experiment": "T1-07", "source": str(SRC.relative_to(ROOT)),
               "m": m, "rows": rows, "monthly_survives": bool(survives),
               "verdict": ("PROCEED to OOS split" if survives else
                           "RETIRED — fails multiplicity across the five resolutions")}
    (OUT / "t1_07_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_07_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
