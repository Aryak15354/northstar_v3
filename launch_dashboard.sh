#!/bin/bash
# launch_dashboard.sh — Northstar V3 Unified Production Dashboard
# Usage: ./launch_dashboard.sh [--port PORT] [--dev]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables if available, but don't let a messy env file kill the launcher.
load_env_file() {
    local env_file="$1"
    if [[ -f "$env_file" ]]; then
        set +e
        set +u
        # shellcheck disable=SC1090
        source "$env_file" >/dev/null 2>&1
        set -u
        set -e
    fi
}

load_env_file ".env.options"
load_env_file ".env"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

usage() {
    echo "Usage: ./launch_dashboard.sh [--port PORT] [--dev|--prod]"
}

PORT="8501"
DEV_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port|-p)
            if [[ $# -lt 2 ]]; then
                echo "Error: --port requires a value"
                usage
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --prod)
            DEV_MODE=false
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                PORT="$1"
                shift
            else
                echo "Error: unknown argument '$1'"
                usage
                exit 1
            fi
            ;;
    esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: invalid port '$PORT'"
    exit 1
fi

if command -v streamlit >/dev/null 2>&1; then
    STREAMLIT_CMD=(streamlit)
else
    STREAMLIT_CMD=(python3 -m streamlit)
fi

echo "=============================================="
echo "🚀 Northstar V3 Production Dashboard"
echo "=============================================="
echo ""
echo "Starting dashboard on port $PORT..."
echo "Access at: http://localhost:$PORT"
echo ""

if [[ "$DEV_MODE" == "true" ]]; then
    echo "Mode: Development (auto-reload on save)"
    "${STREAMLIT_CMD[@]}" run src/dashboard/app.py \
        --server.port "$PORT" \
        --server.address localhost \
        --server.runOnSave true \
        --theme.base dark
else
    echo "Mode: Production (headless)"
    "${STREAMLIT_CMD[@]}" run src/dashboard/app.py \
        --server.port "$PORT" \
        --server.address localhost \
        --server.headless true \
        --theme.base dark
fi
