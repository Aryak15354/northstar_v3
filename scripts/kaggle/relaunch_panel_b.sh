#!/bin/bash
# Rebuild PANEL-B on Kaggle from CURRENT local data, with live logs.
#
# The 2026-07-16 incident this guards against: a kernel ran 5h against a raw-inputs
# dataset that predated the announcements backfill, while its logs were structurally
# invisible (subprocess output bypasses ipykernel capture). Fixed by klog streaming
# + the notebook's PHASE 2 freshness gate. This script makes the re-export the
# default path so the bundle can't silently drift again.
#
# Usage:  bash scripts/kaggle/relaunch_panel_b.sh [--data-only|--code-only|--kernel-only]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

KG="python3 -m kaggle"
USER="$(python3 -c 'import json;print(json.load(open("'"$HOME"'/.kaggle/kaggle.json"))["username"])')"
STAMP="$(date +%Y%m%d-%H%M)"
STEP="${1:-all}"

step() { echo ""; echo "=============================================================="; echo ">>> $1"; echo "=============================================================="; }

if [[ "$STEP" == "all" || "$STEP" == "--data-only" ]]; then
  step "1/3  Re-export raw inputs from current local data"
  rm -rf tmp/kaggle_uploads/raw_inputs
  python3 scripts/kaggle/export_weekly_raw_inputs.py \
      --output-dir tmp/kaggle_uploads/raw_inputs \
      --kaggle-username "$USER"
  echo "--- freshness preflight (same gate the notebook enforces) ---"
  python3 - <<'PY'
import pandas as pd, sys
from pathlib import Path
EXPECT = {
  'data/canonical/alternative/announcements_all.parquet': (900_000, '2019-06-30'),
  'data/canonical/alternative/credit_ratings_nse_all.parquet': (5_000, '2019-06-30'),
  'data/canonical/alternative/bulk_deals_nse_all.parquet': (100_000, '2019-06-30'),
  'data/processed/sentiment/ticker_sentiment_daily.parquet': (10_000, None),
}
# valuation cache is Kaggle-side now (kernel northstar-v3-valuation-cache output,
# mounted into the build kernels as a kernel source) - not part of this bundle
root = Path('tmp/kaggle_uploads/raw_inputs'); bad = []
for rel,(minrows,minstart) in EXPECT.items():
    p = root/rel
    if not p.exists(): bad.append(f'{rel}: MISSING'); continue
    df = pd.read_parquet(p)
    dc = [c for c in df.columns if 'date' in c.lower()]
    dmin = pd.to_datetime(df[dc[0]], errors='coerce').min() if dc else None
    print(f'  {rel.split("/")[-1]:40s} {len(df):>10,} rows  from {str(dmin)[:10]}')
    if len(df) < minrows: bad.append(f'{rel}: {len(df):,} < {minrows:,}')
    if minstart and dmin is not None and dmin > pd.Timestamp(minstart): bad.append(f'{rel}: starts {str(dmin)[:10]}')
if bad:
    print('\nPREFLIGHT FAILED - do not upload:'); [print('  ',b) for b in bad]; sys.exit(1)
print('  preflight PASSED')
PY
  step "2/3  Version the raw-inputs dataset"
  $KG datasets version -p tmp/kaggle_uploads/raw_inputs \
      -m "post-backfill $STAMP: announcements 2019+ (1.06M), ratings 5.4k, pledge B2 fix" -r zip
  # A kernel pushed while a version is still processing silently mounts the
  # PREVIOUS version (2026-07-17: cost a smoke cycle debugging an already-fixed
  # bug). Verify by CONTENT -- timestamp/grep waits are unreliable.
  python3 scripts/kaggle/wait_dataset_live.py "$USER/northstar-v3-weekly-raw-inputs" \
      --file data/canonical/alternative/announcements_all.parquet --contains "" || exit 1
fi

if [[ "$STEP" == "all" || "$STEP" == "--code-only" ]]; then
  step "Code dataset (ships scripts/kaggle/_lib/klog.py)"
  bash scripts/kaggle/prepare_code_dataset_upload.sh "$USER/northstar-v3-code"
  $KG datasets version -p tmp/kaggle_uploads/code_dataset -m "klog live logging + freshness gate $STAMP" -r zip
  python3 scripts/kaggle/wait_dataset_live.py "$USER/northstar-v3-code" \
      --file src/core/panel_math.py --contains "_coerce_groups" || exit 1
fi

if [[ "$STEP" == "all" || "$STEP" == "--kernel-only" ]]; then
  step "3/3  Push the build kernel"
  echo "NOTE: Kaggle runs one version at a time. Cancel any in-flight run first:"
  echo "  https://www.kaggle.com/code/$USER/northstar-v3-build-feature-export"
  python3 scripts/kaggle/write_build_export_notebook.py
  # `kernels push` exits 0 even when it REFUSES the push (title/id slug mismatch
  # prints only a warning) -- 2026-07-17: a "successful" push silently never ran
  # and we read the previous run's ERROR as current. Assert the success line.
  PUSH_OUT="$($KG kernels push -p kaggle_architecture/upload/kernel_build_export 2>&1)"
  echo "$PUSH_OUT"
  grep -q "successfully pushed" <<<"$PUSH_OUT" || { echo "PUSH REFUSED - aborting"; exit 1; }
  echo ""
  echo "Watch it with:   bash scripts/kaggle/watch_kernel.sh"
fi

echo ""; echo "DONE."
