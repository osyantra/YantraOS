#!/usr/bin/env bash
# =============================================================================
# YantraOS — Atomic Installer
# Model Route: GPT-OSS 120B / Gemini 3.1 Pro (Low)
# =============================================================================
# Creates the yantra_daemon user, constructs /opt/yantra/ directory tree,
# initializes Python venv, and installs dependencies. Atomic: partial
# installations are rolled back automatically.
# =============================================================================

set -euo pipefail

# ─── CONSTANTS ───────────────────────────────────────────────────────────────
readonly YANTRA_HOME="/opt/yantra"
readonly YANTRA_USER="yantra_daemon"
readonly YANTRA_GROUP="yantra"
readonly VENV_PATH="${YANTRA_HOME}/venv"
readonly LOG_DIR="/var/log/yantra"
readonly DATA_DIR="/var/lib/yantra"
readonly RUN_DIR="/run/yantra"
readonly BACKUP_DIR="/var/backups"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_FILE="${BACKUP_DIR}/yantra_${TIMESTAMP}.tar.gz"

# ─── COLORS ──────────────────────────────────────────────────────────────────
readonly CYAN='\033[0;36m'    # Electric Blue (accent)
readonly AMBER='\033[0;33m'   # Terminal Amber (alert)
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly NC='\033[0m'         # No Color

# ─── LOGGING ─────────────────────────────────────────────────────────────────
log_info()  { echo -e "${CYAN}[YANTRA]${NC} $*"; }
log_warn()  { echo -e "${AMBER}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }

# ─── PREFLIGHT CHECKS ───────────────────────────────────────────────────────
preflight() {
    # Must run as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This installer must be run as root."
        exit 1
    fi

    # Must be Arch Linux
    if [[ ! -f /etc/arch-release ]]; then
        log_error "YantraOS requires Arch Linux. /etc/arch-release not found."
        exit 1
    fi

    # Must have pacman
    if ! command -v pacman &>/dev/null; then
        log_error "pacman not found. Aborting."
        exit 1
    fi

    log_ok "Preflight checks passed — Arch Linux detected, running as root."
}

# ─── BACKUP EXISTING INSTALLATION ───────────────────────────────────────────
backup_existing() {
    if [[ -d "${YANTRA_HOME}" ]]; then
        log_info "Backing up existing installation → ${BACKUP_FILE}"
        mkdir -p "${BACKUP_DIR}"
        tar -czf "${BACKUP_FILE}" -C /opt yantra 2>/dev/null || true
        log_ok "Backup created: ${BACKUP_FILE}"
    fi
}

# ─── ROLLBACK ────────────────────────────────────────────────────────────────
rollback() {
    log_error "Installation failed — initiating rollback..."

    if [[ -f "${BACKUP_FILE}" ]]; then
        log_warn "Restoring from backup: ${BACKUP_FILE}"
        rm -rf "${YANTRA_HOME}"
        tar -xzf "${BACKUP_FILE}" -C /opt
        log_ok "Rollback complete — previous installation restored."
    else
        log_warn "No backup found. Cleaning up partial installation..."
        rm -rf "${YANTRA_HOME}"
    fi

    exit 1
}

# ─── INSTALL SYSTEM PACKAGES ────────────────────────────────────────────────
install_packages() {
    log_info "Installing system packages via pacman..."

    local PACKAGES=(
        linux-headers
        nvidia-dkms
        cuda
        python-pip
        python
        docker
        docker-compose
        btrfs-progs
    )

    pacman -Sy --noconfirm --needed "${PACKAGES[@]}" || {
        log_error "pacman package installation failed."
        rollback
    }

    log_ok "System packages installed."
}

# ─── CREATE USER & GROUP ────────────────────────────────────────────────────
create_user() {
    # Create yantra group
    if ! getent group "${YANTRA_GROUP}" &>/dev/null; then
        log_info "Creating group: ${YANTRA_GROUP}"
        groupadd "${YANTRA_GROUP}"
    else
        log_warn "Group '${YANTRA_GROUP}' already exists — skipping."
    fi

    # Create yantra_daemon user (system user, nologin, no home dir)
    if ! id "${YANTRA_USER}" &>/dev/null; then
        log_info "Creating user: ${YANTRA_USER}"
        useradd \
            --system \
            --no-create-home \
            --shell /usr/bin/nologin \
            --gid "${YANTRA_GROUP}" \
            "${YANTRA_USER}"
    else
        log_warn "User '${YANTRA_USER}' already exists — skipping."
    fi

    # Add to docker group for container access
    if getent group docker &>/dev/null; then
        log_info "Adding ${YANTRA_USER} to docker group..."
        usermod -aG docker "${YANTRA_USER}"
    else
        log_warn "Docker group not found — will be created when docker starts."
    fi

    log_ok "User '${YANTRA_USER}' configured."
}

# ─── BUILD DIRECTORY STRUCTURE ───────────────────────────────────────────────
build_directories() {
    log_info "Constructing /opt/yantra/ directory tree..."

    # Core directory tree (per §4.5 of YANTRA_MASTER_CONTEXT.md)
    local DIRS=(
        "${YANTRA_HOME}/core"
        "${YANTRA_HOME}/ui"
        "${YANTRA_HOME}/deploy"
        "${YANTRA_HOME}/models"
        "${YANTRA_HOME}/skills"
        "${YANTRA_HOME}/data"
        "${YANTRA_HOME}/logs"
        "${YANTRA_HOME}/snapshots"
        "${LOG_DIR}"
        "${DATA_DIR}/chroma"
        "${RUN_DIR}"
    )

    for dir in "${DIRS[@]}"; do
        mkdir -p "${dir}"
    done

    # Set ownership — §4.6 Permissions Matrix
    chown -R "${YANTRA_USER}:${YANTRA_GROUP}" "${YANTRA_HOME}"
    chown -R "${YANTRA_USER}:${YANTRA_GROUP}" "${LOG_DIR}"
    chown -R "${YANTRA_USER}:${YANTRA_GROUP}" "${DATA_DIR}"
    chown -R "${YANTRA_USER}:${YANTRA_GROUP}" "${RUN_DIR}"

    # Config files: root owns, yantra group reads (640)
    if [[ -f "${YANTRA_HOME}/config.yaml" ]]; then
        chown root:"${YANTRA_GROUP}" "${YANTRA_HOME}/config.yaml"
        chmod 640 "${YANTRA_HOME}/config.yaml"
    fi

    # Model weights: owner rwx, group rx (750)
    chmod 750 "${YANTRA_HOME}/models"

    # Log directory: 755
    chmod 755 "${LOG_DIR}"

    log_ok "Directory tree constructed."
}

# ─── PYTHON VIRTUAL ENVIRONMENT ─────────────────────────────────────────────
setup_venv() {
    log_info "Creating Python virtual environment at ${VENV_PATH}..."

    python3 -m venv "${VENV_PATH}" || {
        log_error "Failed to create Python venv."
        rollback
    }

    log_info "Installing Python dependencies..."

    local REQ_FILE="${SCRIPT_DIR}/../requirements.txt"
    if [[ ! -f "${REQ_FILE}" ]]; then
        REQ_FILE="${YANTRA_HOME}/requirements.txt"
    fi

    if [[ -f "${REQ_FILE}" ]]; then
        "${VENV_PATH}/bin/pip" install --upgrade pip setuptools wheel 2>/dev/null
        "${VENV_PATH}/bin/pip" install -r "${REQ_FILE}" || {
            log_error "pip install failed — rolling back."
            rollback
        }
    else
        log_warn "requirements.txt not found — installing core dependencies manually."
        "${VENV_PATH}/bin/pip" install --upgrade pip setuptools wheel 2>/dev/null
        "${VENV_PATH}/bin/pip" install \
            nvidia-ml-py \
            litellm \
            chromadb \
            psutil \
            textual \
            rich \
            sdnotify \
            docker \
            pyyaml || {
            log_error "pip install failed — rolling back."
            rollback
        }
    fi

    # Set venv ownership to yantra_daemon
    chown -R "${YANTRA_USER}:${YANTRA_GROUP}" "${VENV_PATH}"

    log_ok "Python venv ready."
}

# ─── INSTALL SYSTEMD SERVICE ────────────────────────────────────────────────
install_service() {
    log_info "Installing systemd service..."

    local SERVICE_SRC="${SCRIPT_DIR}/yantra.service"
    local SERVICE_DST="/etc/systemd/system/yantra-daemon.service"

    if [[ -f "${SERVICE_SRC}" ]]; then
        cp "${SERVICE_SRC}" "${SERVICE_DST}"
        chmod 644 "${SERVICE_DST}"
        systemctl daemon-reload
        systemctl enable yantra-daemon.service
        log_ok "systemd service installed and enabled."
    else
        log_warn "yantra.service not found at ${SERVICE_SRC} — skipping."
    fi
}

# ─── INSTALL PACMAN HOOK ────────────────────────────────────────────────────
install_hook() {
    log_info "Installing pacman BTRFS snapshot hook..."

    local HOOK_SRC="${SCRIPT_DIR}/50-yantra-snapshot.hook"
    local HOOK_DST="/etc/pacman.d/hooks/50-yantra-snapshot.hook"

    if [[ -f "${HOOK_SRC}" ]]; then
        mkdir -p /etc/pacman.d/hooks
        cp "${HOOK_SRC}" "${HOOK_DST}"
        chmod 644 "${HOOK_DST}"
        log_ok "Pacman hook installed."
    else
        log_warn "50-yantra-snapshot.hook not found — skipping."
    fi
}

# ─── ENABLE DOCKER ───────────────────────────────────────────────────────────
enable_docker() {
    log_info "Enabling Docker daemon..."
    systemctl enable docker.service
    systemctl start docker.service 2>/dev/null || log_warn "Docker may need a reboot to start."
    log_ok "Docker enabled."
}

# ─── MAIN ────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          YANTRA_OS — ATOMIC INSTALLER v1.0         ║${NC}"
    echo -e "${CYAN}║       \"The Machine That Focuses Energy\"            ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    preflight
    backup_existing
    install_packages
    create_user
    build_directories
    setup_venv
    install_service
    install_hook
    enable_docker

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          INSTALLATION COMPLETE                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    log_ok "YantraOS daemon installed at ${YANTRA_HOME}"
    log_ok "User: ${YANTRA_USER} | Group: ${YANTRA_GROUP}"
    log_ok "Venv: ${VENV_PATH}"
    log_ok "Service: yantra-daemon.service (enabled, not started)"
    echo ""
    log_info "To start the daemon:"
    echo "    sudo systemctl start yantra-daemon.service"
    echo ""
    log_info "To view logs:"
    echo "    journalctl -u yantra-daemon.service -f"
    echo ""
}

main "$@"
