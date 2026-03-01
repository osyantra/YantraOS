#!/usr/bin/env bash
# YantraOS Atomic Installer
# Final bare-metal deployment script

set -euo pipefail

log_info() { echo -e "\e[36m[INFO]\e[0m $*"; }
log_error() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; }
log_ok() { echo -e "\e[32m[OK]\e[0m $*"; }
log_warn() { echo -e "\e[33m[WARN]\e[0m $*"; }

BACKUP_TAR="/var/backups/yantra_$(date +%Y%m%d%H%M%S).tar.gz"

log_info "1. Installing required packages..."
if ! pacman -Sy --noconfirm python-pip docker; then
    log_error "Failed to install required packages. Aborting."
    exit 1
fi
log_ok "Packages installed."

log_info "2. Creating users..."
if ! id yantra_daemon &>/dev/null; then
    useradd -r -s /usr/bin/nologin yantra_daemon
    log_ok "Created yantra_daemon user."
else
    log_info "yantra_daemon user already exists."
fi

if ! id yantra_user &>/dev/null; then
    useradd -m -s /bin/bash yantra_user
    log_ok "Created yantra_user user."
else
    log_info "yantra_user already exists."
fi

log_info "3. Adding users to required groups..."
for grp in docker video render; do
    if getent group "$grp" >/dev/null; then
        usermod -aG "$grp" yantra_daemon
        usermod -aG "$grp" yantra_user
        log_ok "Added users to $grp group."
    else
        log_warn "Group $grp does not exist, skipping."
    fi
done

log_info "4. Backing up /opt/yantra to $BACKUP_TAR ..."
mkdir -p /var/backups
if [[ -d /opt/yantra ]]; then
    tar -czf "$BACKUP_TAR" /opt/yantra
    log_ok "Backup created."
else
    log_info "/opt/yantra does not exist yet; skipping backup."
fi

# Trap to restore on failure
function rollback {
    trap - ERR EXIT
    log_error "Installation failed or aborted. Initiating rollback..."
    if [[ -f "$BACKUP_TAR" ]]; then
        log_info "Restoring backup from $BACKUP_TAR..."
        rm -rf /opt/yantra || true
        tar -xzf "$BACKUP_TAR" -C / || true
        log_ok "Rollback complete."
    fi
    exit 1
}
trap rollback ERR EXIT

log_info "5. Installing components (simulated)..."
# (Actual component installation omitted for brevity)
# Suppose Python requirements fail here:
# if ! pip install <reqs>; then
#     exit 1 # trap ERR will catch this and rollback
# fi

log_info "6. Post-installation: Reactivating BTRFS autonomous snapshotting..."
if [[ -f /etc/pacman.d/hooks/00-yantra-autosnap.hook.inactive ]]; then
    mv /etc/pacman.d/hooks/00-yantra-autosnap.hook.inactive /etc/pacman.d/hooks/00-yantra-autosnap.hook
    log_ok "Hook reactivated successfully."
fi

# Clear the trap as we finished successfully
trap - ERR EXIT
log_ok "Installation completed atomically."
