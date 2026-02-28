#!/bin/bash
# Northstar cron management helpers.

set -euo pipefail

PROJECT_ROOT="/Users/aryakghoshal/Downloads/northstar/northstar_v3"
PYTHON_BIN_DEFAULT="/Users/aryakghoshal/miniforge3/envs/northstar_v7_env_m1/bin/python3"
PYTHON_BIN="${PYTHON_BIN:-$PYTHON_BIN_DEFAULT}"
BACKUP_DEST_DEFAULT="/Volumes/NORTHSTAR_BACKUP/northstar_v3"
BACKUP_DEST="${BACKUP_DEST:-$BACKUP_DEST_DEFAULT}"

DAILY_EXECUTOR_CMD="0 6 * * 1-5 cd $PROJECT_ROOT && $PYTHON_BIN $PROJECT_ROOT/run_daily_v3.py --quick >> logs/cron.log 2>&1"
TRADING_ORCH_CMD="10 9 * * 1-5 cd $PROJECT_ROOT && $PYTHON_BIN $PROJECT_ROOT/scripts/run_trading_day_orchestrator.py --run-once-day --interval-minutes 5 --aggressive >> logs/trading_day_orchestrator.log 2>&1"
BACKUP_CMD="45 20 * * * cd $PROJECT_ROOT && $PYTHON_BIN $PROJECT_ROOT/scripts/backup_northstar_data.py --destination-root \"$BACKUP_DEST\" --verify >> logs/backup.log 2>&1"

_current_crontab() {
  crontab -l 2>/dev/null || true
}

_install_crontab() {
  local content="$1"
  printf "%s\n" "$content" | crontab -
}

add_daily_job() {
  echo "Adding Northstar daily V3 runner cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "daily_executor.py" | grep -v "run_daily_v3.py" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Daily Execution\n%s\n" "$current" "$DAILY_EXECUTOR_CMD")"
  _install_crontab "$updated"
  echo "Added: $DAILY_EXECUTOR_CMD"
}

remove_daily_job() {
  echo "Removing Northstar daily V3 runner cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "daily_executor.py" | grep -v "run_daily_v3.py" || true)"
  _install_crontab "$current"
  echo "Removed daily runner cron entry"
}

add_trading_job() {
  echo "Adding trading-day orchestrator cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "run_trading_day_orchestrator.py" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Trading-Day Orchestrator\n%s\n" "$current" "$TRADING_ORCH_CMD")"
  _install_crontab "$updated"
  echo "Added: $TRADING_ORCH_CMD"
}

remove_trading_job() {
  echo "Removing trading-day orchestrator cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "run_trading_day_orchestrator.py" || true)"
  _install_crontab "$current"
  echo "Removed trading-day orchestrator cron entry"
}

show_jobs() {
  echo "Current cron jobs:"
  _current_crontab
}

add_backup_job() {
  echo "Adding daily backup cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "backup_northstar_data.py" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Daily Backup\n%s\n" "$current" "$BACKUP_CMD")"
  _install_crontab "$updated"
  echo "Added: $BACKUP_CMD"
}

remove_backup_job() {
  echo "Removing daily backup cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "backup_northstar_data.py" || true)"
  _install_crontab "$current"
  echo "Removed backup cron entry"
}

case "${1:-}" in
  add)
    add_daily_job
    ;;
  remove)
    remove_daily_job
    ;;
  add-trading)
    add_trading_job
    ;;
  remove-trading)
    remove_trading_job
    ;;
  add-backup)
    add_backup_job
    ;;
  remove-backup)
    remove_backup_job
    ;;
  show)
    show_jobs
    ;;
  *)
    echo "Usage: $0 {add|remove|add-trading|remove-trading|add-backup|remove-backup|show}"
    echo "  add            -> add daily V3 runner"
    echo "  remove         -> remove daily V3 runner"
    echo "  add-trading    -> add trading-day orchestrator (intraday + EOD)"
    echo "  remove-trading -> remove trading-day orchestrator"
    echo "  add-backup     -> add daily local backup job"
    echo "  remove-backup  -> remove daily local backup job"
    echo "  show           -> show all crontab entries"
    exit 1
    ;;
esac
