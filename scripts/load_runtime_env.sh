#!/bin/bash
# load_runtime_env.sh - source canonical runtime env for live Northstar jobs

_northstar_env_fail() {
  echo "$1" >&2
  return 1 2>/dev/null || exit 1
}

PROJECT_ROOT=""

# Prefer the current working directory when the caller already `cd`'d into the
# repo root (for example from cron), then fall back to shell-specific script
# discovery when the script is executed directly.
if [ -f "./.env.options" ] || [ -f "./.env" ] || [ -f "./scripts/load_runtime_env.sh" ]; then
  PROJECT_ROOT="$(pwd)"
elif [ -n "${BASH_SOURCE:-}" ] && [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
elif [ "$(basename -- "${0:-}")" = "load_runtime_env.sh" ] && [ -f "${0:-}" ]; then
  SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${0}")" && pwd)"
  PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
fi

if [ -z "$PROJECT_ROOT" ]; then
  _northstar_env_fail "Unable to determine project root for load_runtime_env.sh."
fi

ENV_FILE=""
if [ -f "${PROJECT_ROOT}/.env.options" ]; then
  ENV_FILE="${PROJECT_ROOT}/.env.options"
elif [ -f "${PROJECT_ROOT}/.env" ]; then
  ENV_FILE="${PROJECT_ROOT}/.env"
fi

if [ -z "$ENV_FILE" ]; then
  _northstar_env_fail "No .env.options or .env file found under ${PROJECT_ROOT}."
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export NORTHSTAR_ENV_FILE="$ENV_FILE"

if [ "${NORTHSTAR_REQUIRE_UPSTOX_TOKEN:-0}" = "1" ]; then
  if [ -z "${UPSTOX_ACCESS_TOKEN:-}" ] || [ "${UPSTOX_ACCESS_TOKEN:-}" = "your_token_here" ] || [ "${UPSTOX_ACCESS_TOKEN:-}" = "ROTATE_REQUIRED" ]; then
    _northstar_env_fail "UPSTOX_ACCESS_TOKEN is missing or still a placeholder in ${ENV_FILE}."
  fi
fi
