#!/usr/bin/env bash
# YantraOS First-Boot Autopilot
# This script runs once on first TTY login via .zlogin

echo "YantraOS First-Boot Autopilot"
echo ""

# Start NetworkManager
echo "[YANTRA] Starting NetworkManager..."
systemctl start NetworkManager 2>/dev/null || true
sleep 2

# Wait for network
echo "[YANTRA] OK - Contacting Yantra HUD health endpoint..."
curl -sf --max-time 5 https://www.yantraos.com/api/telemetry/ingest >/dev/null 2>&1 || true

# Show daemon status
systemctl status yantra.service --no-pager 2>/dev/null || true
echo ""

# Hand over to the TUI kiosk shell
if command -v cage &>/dev/null && id yantra_user &>/dev/null; then
    echo "[YANTRA] Launching Cage kiosk shell..."
    mkdir -p /run/user/1000
    chown 1000:1000 /run/user/1000
    su - yantra_user -c "XDG_RUNTIME_DIR=/run/user/1000 cage -- /opt/yantra/venv/bin/python3 /opt/yantra/core/cli.py" 2>/dev/null || true
fi
