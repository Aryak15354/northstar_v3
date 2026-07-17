#!/usr/bin/env bash
# Install (load) the Northstar data-collection launchd agents.
#
# This modifies your user's launchd configuration, so it is a manual, opt-in step
# — the automation does NOT run it for you. Review the two plists in this
# directory first, then run:  bash deploy/launchd/install_data_agents.sh
#
# Idempotent: re-running unloads then reloads. Uninstall with:
#   launchctl bootout gui/$(id -u)/com.northstar.data.daily
#   launchctl bootout gui/$(id -u)/com.northstar.data.weekly
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$DEST_DIR"

for label in com.northstar.data.daily com.northstar.data.weekly; do
  src="$SRC_DIR/${label}.plist"
  dest="$DEST_DIR/${label}.plist"
  cp "$src" "$dest"
  launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dest"
  echo "loaded ${label}"
done

echo
echo "Installed. Verify with: launchctl list | grep northstar.data"
echo "Trigger once now with:  launchctl kickstart -k gui/$(id -u)/com.northstar.data.daily"
