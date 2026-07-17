#!/usr/bin/env python3
"""Generate the PANEL-B build notebook with streamed logging + a freshness gate.

Regenerate with:  python3 scripts/kaggle/write_build_export_notebook.py
"""
from __future__ import annotations
import json
from pathlib import Path

import os
SMOKE = os.environ.get("SMOKE") == "1"
_slug = "kernel_build_smoke" if SMOKE else "kernel_build_export"
_name = "northstar_build_smoke.ipynb" if SMOKE else "northstar_build_feature_export.ipynb"
OUT = Path(__file__).resolve().parents[2] / "kaggle_architecture/upload" / _slug / _name

CELLS: list[tuple[str, str]] = []
def md(s): CELLS.append(("markdown", s.strip("\n")))
def code(s): CELLS.append(("code", s.strip("\n")))

md("""
# Northstar V3 - Build PANEL-B Feature Export (chunked, memory-safe, LIVE LOGS)

Rebuilt 2026-07-16. Two things were broken before:

1. **Logs died at ~490s.** Cell 4 used `subprocess.run()`; the child writes to raw OS
   fds, which Kaggle's ipykernel-level capture never sees. The build was invisible by
   construction. Now every child line is piped and re-emitted live via `klog`, with a
   60s heartbeat (rss / disk / quiet-time) so a silent child is distinguishable from a
   hung one.
2. **It ran on a stale bundle.** The raw-inputs dataset predated the announcements /
   credit-ratings backfill, so it was rebuilding the exact data defect the plan exists
   to prevent -- and we'd only have found out after 5h. PHASE 2 is now a hard freshness
   gate that fails in ~60s instead.

Attach: `northstar-v3-weekly-raw-inputs` (MUST be the post-backfill version) and
`northstar-v3-code`. CPU, Internet ON. Save Version -> Save & Run All.
""")

code("""
# PHASE 0 - deps + machine
import subprocess, sys, os, time
subprocess.run([sys.executable,'-m','pip','install','--quiet','--break-system-packages',
                'pyyaml','tenacity','duckdb'], check=True)
print('deps ok', flush=True)
print(open('/proc/meminfo').readline().strip(), flush=True)
print('cores:', os.cpu_count(), flush=True)
""")

code("""
# PHASE 1 - discover mounted datasets, then load the logger from the code dataset
# Anchor RAW on the prices parquet, not on 'data/canonical' alone: the CODE dataset
# also ships data/canonical/reference/, and a bare rglob once picked code as RAW_DIR.
from pathlib import Path
INPUT = Path('/kaggle/input')
raw_hits  = list(INPUT.rglob('data/canonical/prices/equity_prices_daily.parquet'))
code_hits = list(INPUT.rglob('scripts/kaggle/build_local_feature_chunks.py'))
assert raw_hits,  'raw-inputs dataset not mounted'
assert code_hits, 'code dataset not mounted'
RAW_DIR, CODE_DIR = raw_hits[0].parents[3], code_hits[0].parents[2]

sys.path.insert(0, str(CODE_DIR / 'scripts/kaggle/_lib'))
import klog
klog.set_logfile('/kaggle/working/build_log.txt')
SMOKE_RUN = __SMOKE__  # baked in by the generator
klog.banner('NORTHSTAR V3 - PANEL-B ' + ('SMOKE REHEARSAL (2 chunks)' if SMOKE_RUN else 'FEATURE EXPORT BUILD'))
klog.say(f'RAW_DIR  = {RAW_DIR}')
klog.say(f'CODE_DIR = {CODE_DIR}')
cache_hits = list(INPUT.rglob('valuation_scores.provenance.json'))
assert cache_hits, ('valuation cache kernel output not mounted - add kernel source '
                    'aryakghoshal/northstar-v3-valuation-cache (must have COMPLETED)')
CACHE_DIR = cache_hits[0].parent
klog.say(f'CACHE_DIR = {CACHE_DIR}')
assert (RAW_DIR / 'data/processed').exists(), f'RAW_DIR lacks data/processed: {RAW_DIR}'
klog.say('data/processed present: %d entries' % len(list((RAW_DIR/'data/processed').rglob('*'))))
""")

code("""
# PHASE 2 - FRESHNESS GATE (fail in ~60s, not 5h)
# Plan anti-pattern #8: never trust a self-certified SUCCESS; every stage reports
# rows and a freshness check. The 2026-07-16 incident: a Jul-14 bundle (announcements
# 18.9k rows, 2025-only) silently rebuilt a panel that fails D-04 and invalidates
# F-05/F-09. These minimums encode the post-backfill truth.
import pandas as pd

EXPECT = {
    'data/canonical/alternative/announcements_all.parquet':      dict(min_rows=900_000, min_span_start='2019-06-30'),
    'data/canonical/alternative/credit_ratings_nse_all.parquet': dict(min_rows=5_000,   min_span_start='2019-06-30'),
    'data/canonical/alternative/bulk_deals_nse_all.parquet':     dict(min_rows=100_000, min_span_start='2019-06-30'),
    'data/canonical/prices/equity_prices_daily.parquet':         dict(min_rows=1_000_000, min_span_start=None),
    # absence of this one silently emptied the sent_* family before:
    'data/processed/sentiment/ticker_sentiment_daily.parquet':   dict(min_rows=10_000, min_span_start=None),
}

with klog.Phase(2, 6, 'Freshness gate on the raw bundle'):
    failures, rows = [], []
    for rel, exp in EXPECT.items():
        p = RAW_DIR / rel
        if not p.exists():
            failures.append(f'{rel}: MISSING'); continue
        df = pd.read_parquet(p)
        dcols = [c for c in df.columns if 'date' in c.lower()]
        dmin = dmax = None
        if dcols:
            s = pd.to_datetime(df[dcols[0]], errors='coerce')
            dmin, dmax = s.min(), s.max()
        rows.append((rel.split('/')[-1], len(df), str(dmin)[:10], str(dmax)[:10]))
        klog.say(f'{rel.split("/")[-1]:38s} {len(df):>10,} rows  {str(dmin)[:10]} -> {str(dmax)[:10]}')
        if len(df) < exp['min_rows']:
            failures.append(f'{rel}: {len(df):,} rows < required {exp["min_rows"]:,} -- STALE BUNDLE')
        if exp['min_span_start'] and dmin is not None and dmin > pd.Timestamp(exp['min_span_start']):
            failures.append(f'{rel}: history starts {str(dmin)[:10]}, need <= {exp["min_span_start"]} -- STALE BUNDLE')
        del df
    # the valuation cache (kernel-A output) must be marker-attested post-N1,
    # else the builder quarantines it and the in-build recompute blows the cap
    import json as _json
    mkd = _json.loads((CACHE_DIR / 'valuation_scores.provenance.json').read_text())
    vs = CACHE_DIR / 'valuation_scores.parquet'
    if not mkd.get('post_n1_fix'):
        failures.append('valuation cache marker: post_n1_fix is not true')
    elif not vs.exists() or mkd.get('n_rows', 0) < 150_000:
        failures.append(f"valuation cache too small: n_rows={mkd.get('n_rows')}")
    else:
        klog.say(f"valuation cache OK: {mkd['n_rows']:,} rows, {mkd['n_dates']} dates, "
                 f"{mkd['date_min']} -> {mkd['date_max']} (post_n1_fix attested)")
    # sentiment must be FinBERT across 2019+ (the finbert->lexicon degradation
    # this whole exercise fixed). Check provenance in the source table directly.
    _sp = RAW_DIR / 'data/processed/sentiment/ticker_sentiment_daily.parquet'
    if _sp.exists():
        _sd = pd.read_parquet(_sp, columns=['date','nlp_model_version'])
        _w = _sd[pd.to_datetime(_sd['date'], errors='coerce').dt.year >= 2019]
        _ff = _w['nlp_model_version'].astype(str).str.contains('finbert').mean() if len(_w) else 0.0
        if _ff < 0.99:
            failures.append(f'sentiment provenance {_ff:.0%} finbert (need >=99%) -- LEXICON REGRESSION')
        else:
            klog.say(f'sentiment provenance OK: {_ff:.0%} finbert across 2019+')
        del _sd, _w
    if failures:
        klog.emit('')
        for f in failures:
            klog.emit(f'  FAIL  {f}')
        raise SystemExit(
            'FRESHNESS GATE FAILED -- the attached raw-inputs dataset is stale.\\n'
            'Re-export and version it locally, then re-attach the NEW version:\\n'
            '  python3 scripts/kaggle/export_weekly_raw_inputs.py --output-dir /tmp/rawup\\n'
            '  python3 -m kaggle datasets version -p /tmp/rawup -m "post-backfill" -r zip'
        )
    klog.say('all freshness checks PASSED - bundle is post-backfill')
""")

code("""
# PHASE 3 - stage a writable copy and patch known bundle quirks
import shutil
RAWFIX = Path('/kaggle/tmp/rawfix')
with klog.Phase(3, 6, 'Stage writable bundle copy (rawfix)'):
    if not RAWFIX.exists():
        klog.say('copying bundle (a few minutes; this is the old "silent 490s")...')
        shutil.copytree(RAW_DIR, RAWFIX)
    klog.say(f'rawfix staged: {sum(1 for _ in RAWFIX.rglob("*"))} entries')
    # macro: builder's stub policy resolves data/processed/macro/, bundle ships
    # canonical/macro/. Mirror UNCONDITIONALLY: any processed/ copy is the stale
    # 87-row monthly pack, and load_macro's min_rows=200 gate rejects it
    # (smoke kernel, 2026-07-17). Canonical is weekly, same schema, 383 rows.
    import pandas as _pd
    src = RAWFIX / 'data/canonical/macro/macro_regime_features.parquet'
    dst = RAWFIX / 'data/processed/macro/macro_regime_features.parquet'
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert src.exists(), f'canonical macro pack missing from bundle: {src}'
    shutil.copy2(src, dst)
    _n = len(_pd.read_parquet(dst))
    assert _n >= 200, f'macro pack has {_n} rows, load_macro requires >=200'
    klog.say(f'macro mirrored canonical -> processed ({_n} rows, weekly)')
    # install the kernel-A valuation cache (marker-attested post-N1) into rawfix;
    # the builder bootstrap trusts it because the marker ships alongside.
    dstv = RAWFIX / 'data/processed/valuation_scores.parquet'
    shutil.copy2(CACHE_DIR / 'valuation_scores.parquet', dstv)
    shutil.copy2(CACHE_DIR / 'valuation_scores.provenance.json', dstv.with_name('valuation_scores.provenance.json'))
    klog.say(f'installed kernel-A valuation cache ({dstv.stat().st_size/1e6:.1f} MB)')
""")

code("""
# PHASE 4 - build chunks. THE long one. Every builder line now streams live.
CHUNKS = Path('/kaggle/tmp/chunks')
with klog.Phase(4, 6, 'Build feature chunks (2019-01 -> now, 3-month chunks)'):
    klog.run_streamed([
        sys.executable, str(CODE_DIR / 'scripts/kaggle/build_local_feature_chunks.py'),
        '--data-dir', str(RAWFIX),
        '--output-dir', str(CHUNKS),
        '--start-date', '2019-01-01',
        '--chunk-months', '3',
        '--warmup-days', '420',
        '--forward-buffer-days', '10',
        '--threads', '2',
        '--duckdb-threads', '2',
        '--duckdb-memory-limit-mb', '2048',
        '--rebuild-screener', 'auto',
        '--allow-proxies', 'false',
        '--strict-plan-signals', 'false',
        '--min-exact-signal-coverage-pct', '0',
        '--skip-existing',
    ] + (['--end-date', '2019-07-01'] if SMOKE_RUN else []), tag='chunk-builder', heartbeat=60)
    built = sorted(CHUNKS.rglob('features/*.parquet'))
    klog.say(f'chunks on disk: {len(built)}')
""")

code("""
# PHASE 5 - merge chunks into the final export
OUTPUT_DIR = Path('/kaggle/working/00_export')
with klog.Phase(5, 6, 'Merge chunks -> northstar_features.parquet'):
    klog.run_streamed([
        sys.executable, str(CODE_DIR / 'scripts/kaggle/merge_chunked_feature_dataset.py'),
        '--chunk-root', str(CHUNKS),
        '--output-dir', str(OUTPUT_DIR),
    ] + (['--no-enforce-family-audit'] if SMOKE_RUN else []), tag='merger', heartbeat=60)
    # SMOKE ONLY: the family audit is a FULL-PANEL gate. The smoke builds
    # 2019-01..2019-07, where credit_quality is legitimately 0% (XBRL history
    # starts 2022) -- enforcing it here fails on correct data and tells us
    # nothing about the real build. The full build keeps the gate armed.
    if SMOKE_RUN:
        klog.say('NOTE: family audit NOT enforced (smoke window; full build enforces it)')
    # Persist the freshly-recomputed (post-N1-fix, clean) valuation cache as a
    # run artifact: shipping it in a future bundle makes later builds cheap.
    cache = CHUNKS / '_runtime_root/data/processed/valuation_scores.parquet'
    if cache.exists():
        shutil.copy2(cache, '/kaggle/working/valuation_scores_clean.parquet')
        klog.say(f'valuation cache saved as artifact ({cache.stat().st_size/1e6:.1f} MB)')
    else:
        klog.say('NOTE: no valuation cache found to persist')
""")

code("""
# PHASE 6 - verify + acceptance summary (D-04 style coverage read-out)
import pandas as pd
with klog.Phase(6, 6, 'Verify export'):
    for p in sorted(OUTPUT_DIR.glob('*')):
        klog.say(f'{p.name:45s} {p.stat().st_size/1e6:8.2f} MB')
    df = pd.read_parquet(OUTPUT_DIR / 'northstar_features.parquet')
    klog.say(f'shape: {df.shape[0]:,} rows x {df.shape[1]} cols')
    klog.say(f'dates: {df["date"].min()} -> {df["date"].max()}')
    klog.say(f'tickers: {df["ticker"].nunique()}')
    wk = df.groupby('date')['ticker'].nunique()
    klog.say(f'names/week: min={wk.min()} median={int(wk.median())} max={wk.max()}')

    klog.banner('FAMILY COVERAGE (first non-null year per prefix)')
    fams = {'sent_':'sentiment','ann_':'events','eps_sue':'anchors','val_':'value',
            'shp_':'shareholding','pledge_':'pledge','bulk_':'bulk-deals',
            'credit_rating':'ratings','gst_':'gst','ret_':'momentum','vol_':'volatility'}
    for pref, name in fams.items():
        cols = [c for c in df.columns if c.startswith(pref)]
        if not cols:
            klog.say(f'{name:14s} {pref:16s} NO COLUMNS'); continue
        sub = df[['date'] + cols]
        nn = sub.set_index('date')[cols].notna().any(axis=1)
        first = nn[nn].index.min()
        cov = 100.0 * nn.mean()
        klog.say(f'{name:14s} {pref:16s} {len(cols):>3d} cols  first={str(first)[:10]}  rowcov={cov:5.1f}%')
    klog.banner('BUILD COMPLETE - full log at /kaggle/working/build_log.txt')
""")

code("""
# SMOKE VERDICT - parse the mirrored log for step timings + warnings, project x31
import re
if not SMOKE_RUN:
    klog.say('full build - no smoke verdict')
else:
    log = Path('/kaggle/working/build_log.txt').read_text().splitlines()
    warn = sorted({l.strip() for l in log if re.search(r'not found|missing|failed|degrad|empty|skipped', l, re.I)
                   and 'quarantined stale' not in l})
    chunk_done = [l for l in log if re.search(r'\\[Chunk \\d+/\\d+\\] 8/8 DONE', l)]
    ph4 = [l for l in log if 'PHASE 4' in l and '<<<' in l]
    m = re.search(r'OK   \\((\\d+):(\\d+):(\\d+)\\)', ph4[0]) if ph4 else None
    total_s = (int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))) if m else 0
    n = max(len(chunk_done), 1)
    proj_h = (total_s / n) * 31 / 3600
    klog.banner('SMOKE VERDICT')
    klog.say(f'chunks completed: {len(chunk_done)}  phase4 total: {total_s/60:.1f}m  per-chunk: {total_s/n/60:.1f}m')
    klog.say(f'PROJECTED full build: {proj_h:.1f}h for 31 chunks (+ ~0.3h merge)')
    klog.say(f'input warnings: {len(warn)}')
    for w in warn: klog.emit('  !! ' + w)
    verdict = 'GO' if (proj_h < 8.0 and len(chunk_done) >= 2) else 'NO-GO'
    klog.banner(f'VERDICT: {verdict}' + (' - push the full build' if verdict=='GO' else ' - investigate before full build'))
""")

nb = {
    "cells": [
        {"cell_type": t, "metadata": {}, "source": s.splitlines(keepends=True)}
        | ({"outputs": [], "execution_count": None} if t == "code" else {})
        for t, s in CELLS
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    },
    "nbformat": 4, "nbformat_minor": 5,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1).replace("__SMOKE__", "True" if SMOKE else "False"))
print(f'wrote {OUT}  ({len(CELLS)} cells)')
