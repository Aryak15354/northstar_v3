#!/bin/bash
# Compatibility wrapper for the canonical dashboard launcher.

echo "launch_old_dashboard.sh is deprecated. Forwarding to the canonical dashboard..."
exec ./launch_dashboard.sh --port 8501
