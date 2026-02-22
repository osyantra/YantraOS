#!/usr/bin/env bash
# =============================================================================
# YantraOS — BTRFS Snapshot Script
# =============================================================================
# Called by 50-yantra-snapshot.hook before pacman transactions.
# Creates a snapshot of /@ and prunes snapshots older than 7 days.
# =============================================================================

set -euo pipefail

readonly SNAPSHOT_DIR="/@snapshots"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
readonly SNAPSHOT_NAME="yantra_pre_exec_${TIMESTAMP}"
readonly MAX_AGE_DAYS=7

# Check if BTRFS is available
if ! command -v btrfs &>/dev/null; then
    echo "[YANTRA] btrfs command not found — skipping snapshot."
    exit 0
fi

# Check if root is a BTRFS filesystem
if ! btrfs filesystem show / &>/dev/null 2>&1; then
    echo "[YANTRA] Root filesystem is not BTRFS — skipping snapshot."
    exit 0
fi

# Ensure snapshot directory exists
mkdir -p "${SNAPSHOT_DIR}"

# Create snapshot
echo "[YANTRA] Creating snapshot: ${SNAPSHOT_DIR}/${SNAPSHOT_NAME}"
btrfs subvolume snapshot / "${SNAPSHOT_DIR}/${SNAPSHOT_NAME}" || {
    echo "[YANTRA] ERROR: Snapshot creation failed."
    exit 1
}

echo "[YANTRA] Snapshot created successfully."

# Prune old snapshots (older than 7 days)
echo "[YANTRA] Pruning snapshots older than ${MAX_AGE_DAYS} days..."
if [[ -d "${SNAPSHOT_DIR}" ]]; then
    find "${SNAPSHOT_DIR}" -maxdepth 1 -name "yantra_pre_exec_*" -type d | while read -r snap; do
        snap_name="$(basename "${snap}")"
        # Extract date from snapshot name: yantra_pre_exec_YYYYMMDD_HHMMSS
        snap_date="${snap_name#yantra_pre_exec_}"
        snap_date="${snap_date%%_*}"

        if [[ ${#snap_date} -eq 8 ]]; then
            snap_epoch=$(date -d "${snap_date:0:4}-${snap_date:4:2}-${snap_date:6:2}" +%s 2>/dev/null || echo 0)
            cutoff_epoch=$(date -d "-${MAX_AGE_DAYS} days" +%s)

            if [[ ${snap_epoch} -gt 0 && ${snap_epoch} -lt ${cutoff_epoch} ]]; then
                echo "[YANTRA] Pruning old snapshot: ${snap_name}"
                btrfs subvolume delete "${snap}" 2>/dev/null || true
            fi
        fi
    done
fi

echo "[YANTRA] Snapshot operation complete."
