#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_CONFIG="${1:-/tmp/research_policy_full_stack_postfix.yaml}"
if [[ ! -f "${BASE_CONFIG}" ]]; then
  echo "Missing base config: ${BASE_CONFIG}" >&2
  exit 1
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="data/results/research/regime_ic_runs/robustness_${RUN_TS}"
RPTDIR="data/results/research/reports/regime_ic/robustness_${RUN_TS}"
mkdir -p "${OUTDIR}" "${RPTDIR}"

python3 -m py_compile \
  scripts/run_regime_ic_split.py \
  scripts/generate_regime_ic_experiment_report.py \
  src/research/training_pipeline.py \
  src/research/diagnostics/ic_diagnostics.py

COMMON=(
  --base-config "${BASE_CONFIG}"
  --model xgboost
  --max-cpu-cores 1
  --max-blas-threads 1
  --dataset-max-rows 2500000
  --dataset-max-tickers 500
  --dataset-lookback-days 5000
  --prune-features-by-ic
  --ic-min-abs 0.01
  --ic-min-sign-consistency 0.55
  --max-keep-features 60
  --transaction-cost-bps 25
  --sector-neutralize
)

WF_CORE=(
  --max-windows 12
  --train-periods 756
  --valid-periods 126
  --test-periods 126
  --step-periods 63
  --target-horizon-days 10
  --rebalance-frequency-days 10
  --label-embargo-periods 10
)

WF_FALLBACK=(
  --max-windows 10
  --train-periods 504
  --valid-periods 84
  --test-periods 84
  --step-periods 42
)

declare -a FAILED=()
run_exp () {
  local NAME="$1"; shift
  local RETRY_ON_ZERO_WINDOWS=1
  if [[ "${1:-}" == "--no-retry" ]]; then
    RETRY_ON_ZERO_WINDOWS=0
    shift
  fi
  local OUT_JSON="${OUTDIR}/${NAME}.json"
  local LOG_FILE="${OUTDIR}/${NAME}.log"
  if [[ -f "${OUT_JSON}" ]]; then
    echo "=== SKIP ${NAME} (exists) ==="
    return 0
  fi
  echo "=== RUN ${NAME} ==="
  if python3 scripts/run_regime_ic_split.py "${COMMON[@]}" "$@" --output-json "${OUT_JSON}" 2>&1 | tee "${LOG_FILE}"; then
    echo "=== DONE ${NAME} ==="
  else
    echo "=== FAIL ${NAME} ==="
    FAILED+=("${NAME}")
    return 0
  fi

  local WINDOWS
  WINDOWS="$(python3 - <<PY
import json
from pathlib import Path
p=Path("${OUT_JSON}")
if not p.exists():
    print(0)
else:
    d=json.load(open(p))
    a=d.get("aggregate_metrics",{}) or {}
    print(int(round(float(a.get("windows",0.0) or 0.0))))
PY
)"
  if [[ "${RETRY_ON_ZERO_WINDOWS}" -eq 1 && "${WINDOWS}" -eq 0 ]]; then
    echo "=== RETRY ${NAME} with fallback WF split (504/84/84/42) ==="
    if python3 scripts/run_regime_ic_split.py "${COMMON[@]}" "$@" "${WF_FALLBACK[@]}" --output-json "${OUT_JSON}" 2>&1 | tee -a "${LOG_FILE}"; then
      local WINDOWS2
      WINDOWS2="$(python3 - <<PY
import json
from pathlib import Path
p=Path("${OUT_JSON}")
if not p.exists():
    print(0)
else:
    d=json.load(open(p))
    a=d.get("aggregate_metrics",{}) or {}
    print(int(round(float(a.get("windows",0.0) or 0.0))))
PY
)"
      echo "=== RETRY DONE ${NAME} windows=${WINDOWS2} ==="
      if [[ "${WINDOWS2}" -eq 0 ]]; then
        FAILED+=("${NAME}_zero_windows")
      fi
    else
      echo "=== RETRY FAIL ${NAME} ==="
      FAILED+=("${NAME}_retry")
    fi
  fi
}

# -------------------------
# Experiment 1: Long walk-forward robustness
# -------------------------
run_exp ex01_long_wf "${WF_CORE[@]}"

# -------------------------
# Experiment 2: Universe scaling
# -------------------------
for T in 100 200 350 500; do
  run_exp "ex02_universe_${T}" "${WF_CORE[@]}" --dataset-max-tickers "${T}"
done

# -------------------------
# Experiment 3: Feature family ablation
# -------------------------
run_exp ex03_family_momentum "${WF_CORE[@]}" \
  --feature-include-patterns "mom_,ret_,rsi,roc,stoch,trend,ema,sma"

run_exp ex03_family_liquidity "${WF_CORE[@]}" \
  --feature-include-patterns "liquidity,turnover,volume,adv,dollar_volume,spread,amihud"

run_exp ex03_family_fundamental "${WF_CORE[@]}" \
  --feature-include-patterns "eps,pe,pb,ps,ev,ebitda,revenue,income,profit,margin,cashflow,debt,book,roe,roa"

run_exp ex03_family_macro "${WF_CORE[@]}" \
  --feature-include-patterns "macro_"

run_exp ex03_family_mom_liq "${WF_CORE[@]}" \
  --feature-include-patterns "mom_,ret_,rsi,roc,trend,liquidity,turnover,volume,adv,spread"

run_exp ex03_family_mom_fund "${WF_CORE[@]}" \
  --feature-include-patterns "mom_,ret_,rsi,roc,trend,eps,pe,pb,ev,revenue,income,margin,book,roe,roa"

# -------------------------
# Experiment 4: Liquidity-momentum isolation
# -------------------------
run_exp ex04_liq_mom_isolation "${WF_CORE[@]}" \
  --feature-include-patterns "mom5,mom10,mom20,mom30,mom_,ret_10d,ret_20d,vol_20d,liquidity,spread,turnover,volume,adv"

# -------------------------
# Experiment 5: Macro removal
# -------------------------
run_exp ex05_no_macro "${WF_CORE[@]}" \
  --feature-exclude-patterns "macro_"

# -------------------------
# Experiment 6: Liquidity bucket test
# -------------------------
for B in top mid bottom; do
  run_exp "ex06_liquidity_${B}" "${WF_CORE[@]}" --liquidity-bucket "${B}"
done

# -------------------------
# Experiment 7: Dispersion dependency
# -------------------------
for D in high low; do
  run_exp "ex07_dispersion_${D}" "${WF_CORE[@]}" --dispersion-bucket "${D}" --dispersion-col ret_1d
done

# -------------------------
# Experiment 8: Feature stability overlap (window-by-window)
# -------------------------
FEATURE_STAB_WINDOWS="$(python3 - <<PY
import json
from pathlib import Path
p=Path("${OUTDIR}/ex01_long_wf.json")
if not p.exists():
    print(1)
else:
    d=json.load(open(p))
    a=d.get("aggregate_metrics",{}) or {}
    w=int(round(float(a.get("windows",0.0) or 0.0)))
    print(max(1, min(8, w)))
PY
)"
echo "Feature-stability windows to run: ${FEATURE_STAB_WINDOWS}"
if [[ "${FEATURE_STAB_WINDOWS}" -lt 8 ]]; then
  echo "Note: limiting ex08 windows to ${FEATURE_STAB_WINDOWS} due available WF windows."
fi
for ((W=0; W<FEATURE_STAB_WINDOWS; W++)); do
  run_exp "ex08_featstab_w${W}" \
    --no-retry \
    --max-windows 1 --start-window "${W}" \
    --train-periods 756 --valid-periods 126 --test-periods 126 --step-periods 63 \
    --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10
done

# -------------------------
# Experiment 9: Hard chronological OOS
# Train: pre-2020, Test: 2020-2024
# -------------------------
run_exp ex09_hard_oos_2020_2024 \
  --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 \
  --holdout-train-end-date 2019-12-31 \
  --holdout-test-start-date 2020-01-01 \
  --holdout-test-end-date 2024-12-31 \
  --holdout-valid-periods 756 \
  --holdout-min-train-periods 2000

# -------------------------
# Experiment 10: Cross-sectional panel target
# -------------------------
run_exp ex10_panel_target_rank_z "${WF_CORE[@]}" \
  --target-mode rank \
  --target-cross-sectional-zscore \
  --feature-cross-sectional-zscore \
  --prediction-transform zscore

# Main detailed report
python3 scripts/generate_regime_ic_experiment_report.py \
  --glob "${OUTDIR}/*.json" \
  --output-md "${RPTDIR}/regime_ic_experiment_report.md" \
  --output-csv "${RPTDIR}/regime_ic_experiment_summary.csv" \
  --output-regime-csv "${RPTDIR}/regime_ic_experiment_regime_rows.csv"

# Extra diagnostics report: feature overlap + block leaderboards
python3 - <<PY
import csv
import glob
import itertools
import json
import os
from pathlib import Path

outdir = Path("${OUTDIR}")
rptdir = Path("${RPTDIR}")
rptdir.mkdir(parents=True, exist_ok=True)

paths = sorted(glob.glob(str(outdir / "*.json")))
rows = []
for p in paths:
    d = json.load(open(p))
    agg = d.get("aggregate_metrics", {}) or {}
    rows.append({
        "file": os.path.basename(p),
        "global_ic": float(agg.get("ic_mean", 0.0) or 0.0),
        "ic_std": float(agg.get("ic_std", 0.0) or 0.0),
        "global_sharpe": float(agg.get("avg_sharpe", 0.0) or 0.0),
        "windows": int(round(float(agg.get("windows", 0.0) or 0.0))),
        "avg_n_obs": float(agg.get("avg_n_obs", 0.0) or 0.0),
        "avg_turnover": float(agg.get("avg_turnover", 0.0) or 0.0),
    })

rows_sorted = sorted(rows, key=lambda r: r["global_ic"], reverse=True)
with open(rptdir / "block_leaderboard.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_sorted[0].keys()) if rows_sorted else ["file"])
    w.writeheader()
    for r in rows_sorted:
        w.writerow(r)

feat_paths = sorted(glob.glob(str(outdir / "ex08_featstab_w*.json")))
feat_sets = {}
for p in feat_paths:
    d = json.load(open(p))
    diag = d.get("ic_diagnostics", {}) or {}
    top = diag.get("top_features", []) or []
    names = [str(x.get("feature")) for x in top if isinstance(x, dict) and x.get("feature")]
    if not names:
        names = [str(x) for x in (d.get("selected_features", []) or []) if str(x)]
    feat_sets[os.path.basename(p)] = set(names[:30])

overlap_rows = []
for a, b in itertools.combinations(sorted(feat_sets), 2):
    sa, sb = feat_sets[a], feat_sets[b]
    if not sa and not sb:
        jac = 0.0
    else:
        jac = len(sa & sb) / float(max(1, len(sa | sb)))
    overlap_rows.append({"window_a": a, "window_b": b, "jaccard_top30": round(jac, 6)})

with open(rptdir / "feature_stability_overlap.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["window_a", "window_b", "jaccard_top30"])
    w.writeheader()
    for r in overlap_rows:
        w.writerow(r)

mean_overlap = sum(r["jaccard_top30"] for r in overlap_rows) / max(1, len(overlap_rows))
best = rows_sorted[0] if rows_sorted else {}

md = []
md.append("# Robustness Block Addendum")
md.append("")
md.append(f"- Experiments loaded: `{len(rows)}`")
if best:
    md.append(f"- Best global IC: `{best['file']}` ic={best['global_ic']:.4f}, sharpe={best['global_sharpe']:.4f}, windows={best['windows']}")
md.append(f"- Feature stability mean Jaccard (top30, ex08 windows): `{mean_overlap:.4f}`")
md.append("")
md.append("## Block Leaderboard (Top 10 by IC)")
md.append("")
md.append("| file | global_ic | sharpe | windows | avg_n_obs | avg_turnover |")
md.append("|---|---:|---:|---:|---:|---:|")
for r in rows_sorted[:10]:
    md.append(f"| {r['file']} | {r['global_ic']:.4f} | {r['global_sharpe']:.4f} | {r['windows']} | {r['avg_n_obs']:.1f} | {r['avg_turnover']:.4f} |")
md.append("")
md.append("## Notes")
md.append("")
md.append("- Use `feature_stability_overlap.csv` to verify structural feature persistence across windows.")
md.append("- Treat results with `windows < 6` as provisional even if IC is high.")
md.append("")
Path(rptdir / "robustness_addendum.md").write_text("\\n".join(md))
PY

echo "RUN_TS=${RUN_TS}"
echo "OUTDIR=${OUTDIR}"
echo "REPORT_MD=${RPTDIR}/regime_ic_experiment_report.md"
echo "REPORT_ADDENDUM_MD=${RPTDIR}/robustness_addendum.md"
echo "REPORT_CSV=${RPTDIR}/regime_ic_experiment_summary.csv"
echo "REPORT_REGIME_CSV=${RPTDIR}/regime_ic_experiment_regime_rows.csv"
echo "FEATURE_OVERLAP_CSV=${RPTDIR}/feature_stability_overlap.csv"
echo "BLOCK_LEADERBOARD_CSV=${RPTDIR}/block_leaderboard.csv"
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "FAILED_EXPERIMENTS=${FAILED[*]}"
fi
sed -n '1,140p' "${RPTDIR}/regime_ic_experiment_report.md"
echo ""
sed -n '1,140p' "${RPTDIR}/robustness_addendum.md"
