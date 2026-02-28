# Northstar V3 Cleanup + Automation Changes (2026-02-14)

## Goal
This change set cleaned system clutter, removed obsolete provider artifacts, enforced report version archiving, improved RBI file version handling, and wired detailed periodic reporting into the daily autonomous run.

## What Was Implemented

### 1) Report version archiving (no silent overwrite)
A shared versioning utility now archives existing `*_latest`/fixed-name report files before writing new output.

- Added utility:
  - `src/reporting/report_versioning.py`
- Integrated into core report writers:
  - `src/intelligence/narrative_intelligence_engine.py`
  - `src/intelligence/robust_narrative_engine.py`
  - `src/intelligence/narrative_integration.py`
  - `src/intelligence/enhanced_narrative_engine.py`
  - `scripts/run_complete_northstar_system.py`

Behavior now:
- Old file is moved to a timestamped archive path like:
  - `data/reports/archive/<report_name>/<report_name>_YYYYMMDD_HHMMSS.ext`
- New latest file is written at the original path.

### 2) RBI XLSX replacement archiving + retrospective-ready pipeline
RBI scraper copy logic now archives an existing raw XLSX before replacing it.

- Updated:
  - `src/ingestion/rbi_scraper.py`

Behavior now:
- If `data/macro/raw/<file>.xlsx` exists and a new one arrives, old version is moved to:
  - `data/macro/archive/<file>.xlsx_YYYYMMDD_HHMMSS`
- Then the new file is copied into `data/macro/raw`.

Note:
- RBI processor retrospective-change logic is already in place in:
  - `src/ingestion/rbi_processor.py`
- It now has stable series-key merging and retrospective diff logging hooks.

### 3) Detailed periodic reports (daily/weekly/monthly/quarterly)
Added a detailed report generator that composes market state, macro health, options universe coverage, narrative outputs, and system status into explanatory reports.

- Added:
  - `scripts/generate_periodic_reports.py`

Outputs:
- `data/reports/periodic/daily_report_latest.json`
- `data/reports/periodic/daily_report_latest.md`
- `data/reports/periodic/weekly_report_latest.json`
- `data/reports/periodic/weekly_report_latest.md`
- `data/reports/periodic/monthly_report_latest.json`
- `data/reports/periodic/monthly_report_latest.md`
- `data/reports/periodic/quarterly_report_latest.json`
- `data/reports/periodic/quarterly_report_latest.md`

Version archive behavior (same as above):
- Prior `*_latest` periodic files are archived under:
  - `data/reports/periodic/archive/...`

### 4) Wired periodic reports into autonomous trading-day EOD run
The trading-day orchestrator now runs periodic report generation after the full V3 system run.

- Updated:
  - `scripts/run_trading_day_orchestrator.py`

EOD sequence now:
1. Market update (yfinance forced)
2. RBI forced updater
3. Integrated market state recompute
4. Complete V3 run
5. Periodic reports generation

New CLI toggle:
- `--skip-periodic-reports` (optional override)

### 5) `data/options` cleanup (Groww leftovers removed)
Removed stale/partial Groww historical artifacts now that Upstox is the active source.

Removed:
- Groww manifests and instrument-master files under:
  - `data/options/historical/`
  - `data/options/historical/1w/`
- Entire partial Groww 5m directory:
  - `data/options/historical/5m/`
- Resume checkpoint clutter:
  - `data/options/historical/_resume/`
  - `data/options/historical/_resume_test/`

Result:
- `data/options/historical` shrank significantly and now keeps Upstox-centric artifacts.

### 6) Root folder cleanup
Moved obsolete root status/summary files to an archive folder instead of deleting permanently.

Moved to:
- `docs/archive/root_cleanup_20260214/`

Includes old integration/status/checklist summaries and stray zero-byte artifacts.

## Validation Performed

- Syntax checks (`py_compile`) passed for all modified Python modules/scripts.
- Executed periodic report generator successfully.
- Confirmed periodic archives are created on re-run.
- Confirmed Groww files/resume clutter removed from `data/options/historical`.

## Operational Notes

- If any background historical builder process is still launched manually, it can recreate `_resume` artifacts. Keep the build process stopped unless actively ingesting.
- Periodic reports are now part of EOD orchestration and will refresh daily with archived history.
- RBI raw XLSX version lineage is now preserved in `data/macro/archive`.

## Key Files Touched

- `src/reporting/report_versioning.py`
- `src/intelligence/narrative_intelligence_engine.py`
- `src/intelligence/robust_narrative_engine.py`
- `src/intelligence/narrative_integration.py`
- `src/intelligence/enhanced_narrative_engine.py`
- `scripts/run_complete_northstar_system.py`
- `src/ingestion/rbi_scraper.py`
- `scripts/generate_periodic_reports.py`
- `scripts/run_trading_day_orchestrator.py`

