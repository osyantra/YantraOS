#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# YantraOS — Master ISO Compilation Script
# Target: ~/archlive/compile_iso.sh
# Milestone 6, Tasks 6.2 & 6.3
#
# This script orchestrates the entire ArchISO build pipeline:
#   1. Pre-flight validation (root check, dependency check, ownership audit)
#   2. Archlive directory preparation (copy YantraOS core into airootfs)
#   3. Python venv embedding + hashbang correction (Task 6.2)
#   4. Pacman.conf multilib enablement (Task 6.3 pre-flight)
#   5. mkarchiso execution (Task 6.3)
#
# Usage:
#   sudo bash compile_iso.sh [--output /path/to/output] [--work /tmp/archiso-tmp]
#
# MUST be run as root. mkarchiso requires root to create the squashfs image
# and set file ownership/permissions as defined in profiledef.sh.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

# ── Configuration ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHLIVE_DIR="${SCRIPT_DIR}"
AIROOTFS="${ARCHLIVE_DIR}/airootfs"

# Defaults — overridable via flags
WORK_DIR="/tmp/archiso-tmp"
OUTPUT_DIR="${ARCHLIVE_DIR}/out"

# Source repository root (where the dev copies of YantraOS live)
YANTRA_SRC="$(dirname "${ARCHLIVE_DIR}")"

# Venv paths
VENV_BUILD="${AIROOTFS}/opt/yantra/venv"
VENV_DEPLOY="/opt/yantra/venv"

# Python dependencies for the daemon
PIP_REQUIREMENTS=(
    "fastapi>=0.111.0"
    "uvicorn[standard]>=0.29.0"
    "litellm>=1.35.0"
    "chromadb>=0.5.0"
    "docker>=7.0.0"
    "sdnotify>=0.3.0"
    "pynvml>=12.0.0"
    "psutil>=5.9.0"
    "httpx>=0.27.0"
)

# ── Color output ──────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Argument parsing ──────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --output|-o)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --work|-w)
            WORK_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: sudo bash $0 [--output /path] [--work /path]"
            exit 0
            ;;
        *)
            log_error "Unknown argument: $1"
            exit 2
            ;;
    esac
done

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1: Pre-flight Validation
# ══════════════════════════════════════════════════════════════════════════════

log_info "═══ PHASE 1: Pre-flight Validation ═══"

# ── Root check ────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root."
    log_error "Usage: sudo bash $0"
    exit 1
fi
log_ok "Running as root."

# ── Dependency check ──────────────────────────────────────────────────────────
REQUIRED_CMDS=("mkarchiso" "python3" "pip" "sed" "install" "chown")
for cmd in "${REQUIRED_CMDS[@]}"; do
    if ! command -v "$cmd" &>/dev/null; then
        log_error "Required command not found: $cmd"
        log_error "Install archiso: pacman -S archiso"
        exit 1
    fi
done
log_ok "All required commands available."

# ── Verify archlive structure ─────────────────────────────────────────────────
if [[ ! -f "${ARCHLIVE_DIR}/profiledef.sh" ]]; then
    log_error "profiledef.sh not found in ${ARCHLIVE_DIR}"
    exit 1
fi
if [[ ! -f "${ARCHLIVE_DIR}/pacman.conf" ]]; then
    log_warn "pacman.conf not found — copying from system default."
    cp /etc/pacman.conf "${ARCHLIVE_DIR}/pacman.conf"
fi
log_ok "Archlive profile structure verified."

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: Populate airootfs Overlay
# ══════════════════════════════════════════════════════════════════════════════

log_info "═══ PHASE 2: Populating airootfs overlay ═══"

# ── Copy YantraOS core modules ───────────────────────────────────────────────
log_info "Copying YantraOS core/ into airootfs..."
install -dm755 "${AIROOTFS}/opt/yantra/core"
for pyfile in "${YANTRA_SRC}/core/"*.py; do
    if [[ -f "$pyfile" ]]; then
        install -Dm644 "$pyfile" "${AIROOTFS}/opt/yantra/core/$(basename "$pyfile")"
    fi
done
# Mark entry points as executable
chmod 755 "${AIROOTFS}/opt/yantra/core/daemon.py" 2>/dev/null || true
chmod 755 "${AIROOTFS}/opt/yantra/core/cli.py" 2>/dev/null || true
log_ok "Core modules copied."

# ── Copy deploy configs ──────────────────────────────────────────────────────
log_info "Copying deploy/ configs into airootfs..."

# sysusers.d
install -Dm644 "${YANTRA_SRC}/deploy/sysusers.d/yantra.conf" \
    "${AIROOTFS}/usr/lib/sysusers.d/yantra.conf"

# tmpfiles.d
install -Dm644 "${YANTRA_SRC}/deploy/tmpfiles.d/yantra.conf" \
    "${AIROOTFS}/usr/lib/tmpfiles.d/yantra.conf"

# Polkit
install -Dm644 "${YANTRA_SRC}/deploy/polkit/50-yantra-btrfs.rules" \
    "${AIROOTFS}/etc/polkit-1/rules.d/50-yantra-btrfs.rules"

# Systemd unit
install -Dm644 "${YANTRA_SRC}/deploy/systemd/yantra.service" \
    "${AIROOTFS}/etc/systemd/system/yantra.service"

# Pacman hooks
install -dm755 "${AIROOTFS}/etc/pacman.d/hooks"
install -Dm644 "${YANTRA_SRC}/deploy/pacman/00-yantra-autosnap.hook.inactive" \
    "${AIROOTFS}/etc/pacman.d/hooks/00-yantra-autosnap.hook.inactive"
install -Dm644 "${YANTRA_SRC}/deploy/pacman/99-yantra-reload.hook" \
    "${AIROOTFS}/etc/pacman.d/hooks/99-yantra-reload.hook"

# Secrets placeholder (empty, root-only)
install -dm700 "${AIROOTFS}/etc/yantra"
touch "${AIROOTFS}/etc/yantra/secrets.env"
chmod 600 "${AIROOTFS}/etc/yantra/secrets.env"

log_ok "Deploy configs copied."

# ── Create runtime directories ───────────────────────────────────────────────
install -dm770 "${AIROOTFS}/run/yantra"
install -dm770 "${AIROOTFS}/var/lib/yantra"
install -dm770 "${AIROOTFS}/var/lib/yantra/chroma"
log_ok "Runtime directories created."

# ── Enable yantra.service on first boot ───────────────────────────────────────
install -dm755 "${AIROOTFS}/etc/systemd/system/multi-user.target.wants"
ln -sf /etc/systemd/system/yantra.service \
    "${AIROOTFS}/etc/systemd/system/multi-user.target.wants/yantra.service" 2>/dev/null || true
log_ok "yantra.service enabled for first boot."

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3: Python Virtual Environment Embedding (Task 6.2)
# ══════════════════════════════════════════════════════════════════════════════

log_info "═══ PHASE 3: Embedding Python virtual environment ═══"

# ── Create venv in airootfs ───────────────────────────────────────────────────
if [[ -d "${VENV_BUILD}" ]]; then
    log_warn "Existing venv found — removing for clean rebuild."
    rm -rf "${VENV_BUILD}"
fi

log_info "Creating venv at ${VENV_BUILD}..."
python3 -m venv "${VENV_BUILD}"
log_ok "Venv created."

# ── Install pip dependencies ─────────────────────────────────────────────────
log_info "Installing pip dependencies into venv..."
"${VENV_BUILD}/bin/pip" install --upgrade pip setuptools wheel --quiet
for pkg in "${PIP_REQUIREMENTS[@]}"; do
    log_info "  Installing: ${pkg}"
    "${VENV_BUILD}/bin/pip" install "${pkg}" --quiet
done
log_ok "All pip dependencies installed."

# ── CRITICAL FIX: Hashbang correction (Task 6.2) ─────────────────────────────
#
# pip embeds the BUILD MACHINE's absolute Python path into the hashbang (#!)
# of every script it generates in venv/bin/. For example:
#
#   #!/home/builder/archlive/airootfs/opt/yantra/venv/bin/python3
#
# This path will NOT EXIST inside the final ISO's filesystem. It must be
# rewritten to the DEPLOYMENT path:
#
#   #!/opt/yantra/venv/bin/python3
#
# The sed command below performs this replacement recursively on all files
# in venv/bin/ that contain a hashbang line.
# ──────────────────────────────────────────────────────────────────────────────

log_info "Fixing hashbangs in venv/bin/ scripts..."
HASHBANG_COUNT=0

# Escape the build path for sed (handle forward slashes)
BUILD_PATH_ESCAPED=$(echo "${VENV_BUILD}" | sed 's/[\/&]/\\&/g')
DEPLOY_PATH_ESCAPED=$(echo "${VENV_DEPLOY}" | sed 's/[\/&]/\\&/g')

# Process every file in venv/bin/
for script in "${VENV_BUILD}/bin/"*; do
    # Skip if not a regular file
    [[ -f "$script" ]] || continue

    # Only process text files with hashbangs
    if head -1 "$script" 2>/dev/null | grep -q "^#!"; then
        # Replace the build machine path with the deployment path
        sed -i "1s|#!.*${BUILD_PATH_ESCAPED}/bin/python[0-9.]*|#!${VENV_DEPLOY}/bin/python3|" "$script"
        HASHBANG_COUNT=$((HASHBANG_COUNT + 1))
    fi
done

log_ok "Fixed hashbangs in ${HASHBANG_COUNT} script(s)."

# Verify the fix
log_info "Verifying hashbang correction..."
SAMPLE_SCRIPT="${VENV_BUILD}/bin/pip"
if [[ -f "$SAMPLE_SCRIPT" ]]; then
    FIRST_LINE=$(head -1 "$SAMPLE_SCRIPT")
    if echo "$FIRST_LINE" | grep -q "${VENV_DEPLOY}"; then
        log_ok "Hashbang verified: ${FIRST_LINE}"
    else
        log_warn "Hashbang may not be correctly set: ${FIRST_LINE}"
        log_warn "Expected path containing: ${VENV_DEPLOY}"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4: Pacman.conf Multilib Enablement (Task 6.3 Pre-flight)
# ══════════════════════════════════════════════════════════════════════════════

log_info "═══ PHASE 4: Configuring pacman.conf ═══"

PACMAN_CONF="${ARCHLIVE_DIR}/pacman.conf"

# ── Enable [multilib] repository ──────────────────────────────────────────────
# Required for 32-bit compatibility libraries and pre-compiled LLM binaries.
# The default Arch pacman.conf has [multilib] commented out.
if grep -q "^#\[multilib\]" "${PACMAN_CONF}"; then
    log_info "Enabling [multilib] repository..."
    # Uncomment [multilib] and the Include line that follows it
    sed -i '/^#\[multilib\]/{
        s/^#//
        n
        s/^#//
    }' "${PACMAN_CONF}"
    log_ok "[multilib] enabled."
elif grep -q "^\[multilib\]" "${PACMAN_CONF}"; then
    log_ok "[multilib] already enabled."
else
    log_warn "[multilib] section not found — appending."
    echo -e "\n[multilib]\nInclude = /etc/pacman.d/mirrorlist" >> "${PACMAN_CONF}"
    log_ok "[multilib] appended."
fi

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5: Ownership Audit & ISO Build (Task 6.3)
# ══════════════════════════════════════════════════════════════════════════════

log_info "═══ PHASE 5: Ownership audit & ISO build ═══"

# ── Security invariant: root ownership of entire build tree ───────────────────
# mkarchiso maps UIDs from the build directory into the ISO. If any file is
# owned by a non-root user, that UID will cascade into the immutable ISO,
# potentially creating security holes or broken permissions.
log_info "Enforcing root ownership on build directory..."
chown -R root:root "${ARCHLIVE_DIR}"
log_ok "Build directory owned by root:root."

# ── Clean previous build artifacts ───────────────────────────────────────────
if [[ -d "${WORK_DIR}" ]]; then
    log_warn "Cleaning stale work directory: ${WORK_DIR}"
    rm -rf "${WORK_DIR}"
fi
mkdir -p "${WORK_DIR}"
mkdir -p "${OUTPUT_DIR}"

# ── Execute mkarchiso ─────────────────────────────────────────────────────────
log_info "Starting mkarchiso build..."
log_info "  Profile:  ${ARCHLIVE_DIR}"
log_info "  Work dir: ${WORK_DIR}"
log_info "  Output:   ${OUTPUT_DIR}"
echo ""

mkarchiso -v -w "${WORK_DIR}" -o "${OUTPUT_DIR}" "${ARCHLIVE_DIR}"

BUILD_EXIT=$?

if [[ $BUILD_EXIT -eq 0 ]]; then
    echo ""
    log_ok "═══════════════════════════════════════════════════════════"
    log_ok "  YantraOS ISO build SUCCESSFUL"
    log_ok "  Output: ${OUTPUT_DIR}/"
    ls -lh "${OUTPUT_DIR}/"*.iso 2>/dev/null || true
    log_ok "═══════════════════════════════════════════════════════════"
else
    echo ""
    log_error "═══════════════════════════════════════════════════════════"
    log_error "  mkarchiso FAILED with exit code ${BUILD_EXIT}"
    log_error "  Check the build log above for errors."
    log_error "═══════════════════════════════════════════════════════════"
    exit $BUILD_EXIT
fi

# ── Cleanup work directory ────────────────────────────────────────────────────
log_info "Cleaning work directory..."
rm -rf "${WORK_DIR}"
log_ok "Build complete. ISO ready for deployment."