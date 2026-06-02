#!/bin/bash
# Northstar cron management helpers.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN_DEFAULT="python3"
PYTHON_BIN="${PYTHON_BIN:-$PYTHON_BIN_DEFAULT}"
BACKUP_DEST_DEFAULT="${HOME}/northstar_backups/northstar_v3"
BACKUP_DEST="${BACKUP_DEST:-$BACKUP_DEST_DEFAULT}"
ENV_LOADER="$PROJECT_ROOT/scripts/load_runtime_env.sh"

DAILY_EXECUTOR_CMD="0 6 * * 1-5 cd $PROJECT_ROOT && $PYTHON_BIN $PROJECT_ROOT/run_daily_v3.py --quick >> logs/cron.log 2>&1"
TRADING_ORCH_CMD="50 8 * * 1-5 cd $PROJECT_ROOT && export NORTHSTAR_REQUIRE_UPSTOX_TOKEN=1 && . $ENV_LOADER && $PYTHON_BIN $PROJECT_ROOT/scripts/run_trading_day_orchestrator.py --run-once-day --start-fresh-today --interval-minutes 5 --runtime-sync-minutes 15 --eod-v3-mode quick --skip-options-backtest >> logs/trading_day_orchestrator.log 2>&1"
WEEKEND_MAINTENANCE_CMD="30 10 * * 6 cd $PROJECT_ROOT && . $ENV_LOADER && $PYTHON_BIN $PROJECT_ROOT/scripts/run_weekend_maintenance.py --backup-destination-root \"$BACKUP_DEST\" >> logs/weekend_maintenance.log 2>&1"
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
  current="$(printf "%s\n" "$current" | grep -v "daily_executor.py" | grep -v "run_daily_v3.py" | grep -v "^# Northstar Daily Execution$" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Daily Execution\n%s\n" "$current" "$DAILY_EXECUTOR_CMD")"
  _install_crontab "$updated"
  echo "Added: $DAILY_EXECUTOR_CMD"
}

remove_daily_job() {
  echo "Removing Northstar daily V3 runner cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "daily_executor.py" | grep -v "run_daily_v3.py" | grep -v "^# Northstar Daily Execution$" || true)"
  _install_crontab "$current"
  echo "Removed daily runner cron entry"
}

add_trading_job() {
  echo "Adding trading-day orchestrator cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "run_trading_day_orchestrator.py" | grep -v "^# Northstar Trading-Day Orchestrator$" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Trading-Day Orchestrator\n%s\n" "$current" "$TRADING_ORCH_CMD")"
  _install_crontab "$updated"
  echo "Added: $TRADING_ORCH_CMD"
}

remove_trading_job() {
  echo "Removing trading-day orchestrator cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "run_trading_day_orchestrator.py" | grep -v "^# Northstar Trading-Day Orchestrator$" || true)"
  _install_crontab "$current"
  echo "Removed trading-day orchestrator cron entry"
}

show_jobs() {
  echo "Current cron jobs:"
  _current_crontab
}

install_live_schedule() {
  remove_daily_job
  add_trading_job
  add_weekend_job
  add_backup_job
}

remove_live_schedule() {
  remove_trading_job
  remove_weekend_job
  remove_backup_job
}

add_backup_job() {
  echo "Adding daily backup cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "backup_northstar_data.py" | grep -v "^# Northstar Daily Backup$" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Daily Backup\n%s\n" "$current" "$BACKUP_CMD")"
  _install_crontab "$updated"
  echo "Added: $BACKUP_CMD"
}

remove_backup_job() {
  echo "Removing daily backup cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "backup_northstar_data.py" | grep -v "^# Northstar Daily Backup$" || true)"
  _install_crontab "$current"
  echo "Removed backup cron entry"
}

add_weekend_job() {
  echo "Adding weekend maintenance cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "run_weekend_maintenance.py" | grep -v "^# Northstar Weekend Maintenance$" || true)"
  local updated
  updated="$(printf "%s\n# Northstar Weekend Maintenance\n%s\n" "$current" "$WEEKEND_MAINTENANCE_CMD")"
  _install_crontab "$updated"
  echo "Added: $WEEKEND_MAINTENANCE_CMD"
}

remove_weekend_job() {
  echo "Removing weekend maintenance cron job..."
  local current
  current="$(_current_crontab)"
  current="$(printf "%s\n" "$current" | grep -v "run_weekend_maintenance.py" | grep -v "^# Northstar Weekend Maintenance$" || true)"
  _install_crontab "$current"
  echo "Removed weekend maintenance cron entry"
}

case "${1:-}" in
  install)
    install_live_schedule
    ;;
  uninstall)
    remove_live_schedule
    ;;
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
  add-weekend)
    add_weekend_job
    ;;
  remove-weekend)
    remove_weekend_job
    ;;
  show)
    show_jobs
    ;;
  status)
    show_jobs
    ;;
  *)
    echo "Usage: $0 {install|uninstall|add|remove|add-trading|remove-trading|add-weekend|remove-weekend|add-backup|remove-backup|show|status}"
    echo "  install        -> add trading-day, weekend maintenance, and backup schedules"
    echo "  uninstall      -> remove trading-day, weekend maintenance, and backup schedules"
    echo "  add            -> add daily V3 runner"
    echo "  remove         -> remove daily V3 runner"
    echo "  add-trading    -> add trading-day orchestrator (intraday + EOD)"
    echo "  remove-trading -> remove trading-day orchestrator"
    echo "  add-weekend    -> add Saturday maintenance run"
    echo "  remove-weekend -> remove Saturday maintenance run"
    echo "  add-backup     -> add daily local backup job"
    echo "  remove-backup  -> remove daily local backup job"
    echo "  show/status    -> show all crontab entries"
    exit 1
    ;;
esac
