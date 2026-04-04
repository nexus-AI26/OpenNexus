#!/usr/bin/env bash
# install.sh — OpenNexus installer
# Installs OpenNexus from GitHub (nexus-AI26/OpenNexus) into /opt/opennexus
# Usage:
#   bash install.sh              — interactive install
#   bash install.sh --service    — also install and enable systemd service
# Or via curl:
#   curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash

set -euo pipefail

REPO_URL="https://github.com/nexus-AI26/OpenNexus.git"
INSTALL_DIR="/opt/opennexus"
CONFIG_DIR="$INSTALL_DIR/.opennexus"
SERVICE_FILE="/etc/systemd/system/opennexus.service"
SERVICE_USER="opennexus"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11
INSTALL_SERVICE=true

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()      { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERR ]${RESET}  $*"; }
log_step()    { echo -e "\n${BOLD}══ $* ${RESET}"; }

# ── Parse args ───────────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --no-service) 
            INSTALL_SERVICE=false 
            CONFIG_DIR="$HOME/.opennexus"
            ;;
        --help|-h)
            echo "Usage: bash install.sh [--no-service]"
            echo "  --no-service   Skip installing the systemd service and run locally"
            exit 0
            ;;
    esac
done

# ── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ██████╗ ██████╗ ███████╗███╗   ██╗███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
echo " ██╔═══██╗██╔══██╗██╔════╝████╗  ██║████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
echo " ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
echo " ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
echo " ╚██████╔╝██║     ███████╗██║ ╚████║██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║"
echo "  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo -e "${RESET}"
echo -e "  ${BOLD}AI assistant for developers and ethical hackers${RESET}"
echo -e "  github.com/nexus-AI26/OpenNexus"
echo ""

# ── Root check (for service) ───────────────────────────────────────────────
if $INSTALL_SERVICE && [[ $EUID -ne 0 ]]; then
    log_error "Installing the service requires root. Run: sudo bash install.sh"
    log_warn "Or run locally without a service: bash install.sh --no-service"
    exit 1
fi

# ── Step 1: System dependencies ──────────────────────────────────────────────
log_step "Checking system dependencies"

# Python version check
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(sys.version_info.major, sys.version_info.minor)")
        major=$(echo "$version" | awk '{print $1}')
        minor=$(echo "$version" | awk '{print $2}')
        if [[ $major -ge $PYTHON_MIN_MAJOR && $minor -ge $PYTHON_MIN_MINOR ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    log_error "Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ is required but not found."
    echo "Install it with:"
    echo "  sudo apt install python3.11  # Debian/Ubuntu"
    echo "  sudo dnf install python3.11  # Fedora/RHEL"
    echo "  sudo pacman -S python         # Arch"
    exit 1
fi

log_ok "Found $($PYTHON_BIN --version)"

# git check
if ! command -v git &>/dev/null; then
    log_error "git is required but not found."
    echo "Install it with: sudo apt install git"
    exit 1
fi
log_ok "Found $(git --version)"

# ── Step 2: Clone or update ───────────────────────────────────────────────────
log_step "Installing OpenNexus to $INSTALL_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    log_info "Existing installation found — updating..."
    git -C "$INSTALL_DIR" pull --ff-only
    log_ok "Updated to latest."
else
    if [[ -d "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
        log_error "$INSTALL_DIR exists and is not empty. Remove it first or update manually."
        exit 1
    fi
    log_info "Cloning from $REPO_URL ..."
    git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
    log_ok "Cloned successfully."
fi

# ── Step 3: Python virtual environment ───────────────────────────────────────
log_step "Setting up Python virtual environment"

VENV_DIR="$INSTALL_DIR/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    log_ok "Created venv at $VENV_DIR"
else
    log_info "Venv already exists — skipping creation."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

log_info "Installing dependencies..."
"$VENV_PIP" install --quiet --upgrade pip
"$VENV_PIP" install --quiet -e "$INSTALL_DIR"
log_ok "Dependencies installed."

# ── Step 4: Config ────────────────────────────────────────────────────────────
log_step "Setting up config directory"

mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/skills"
mkdir -p "$CONFIG_DIR/logs"

if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "$INSTALL_DIR/config.toml.example" "$CONFIG_DIR/config.toml"
    log_ok "Created $CONFIG_DIR/config.toml from example."
    log_warn "Edit $CONFIG_DIR/config.toml and fill in:"
    log_warn "  - bot_token (from @BotFather)"
    log_warn "  - access.owner_id (your Telegram user ID)"
    log_warn "  - access.allowed_users"
    log_warn "  - At least one provider API key"
else
    log_info "Config already exists at $CONFIG_DIR/config.toml — skipping."
fi

# ── Step 5: Launcher script ───────────────────────────────────────────────────
log_step "Installing launcher"

LAUNCHER="/usr/local/bin/opennexus"
if [[ $EUID -eq 0 ]]; then
    cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$INSTALL_DIR/main.py" "\$@"
EOF
    chmod +x "$LAUNCHER"
    log_ok "Installed launcher at $LAUNCHER"
else
    LOCAL_LAUNCHER="$HOME/.local/bin/opennexus"
    mkdir -p "$HOME/.local/bin"
    cat > "$LOCAL_LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$INSTALL_DIR/main.py" "\$@"
EOF
    chmod +x "$LOCAL_LAUNCHER"
    log_ok "Installed launcher at $LOCAL_LAUNCHER"
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        log_warn "Add ~/.local/bin to your PATH:"
        log_warn '  echo '"'"'export PATH="$HOME/.local/bin:$PATH"'"'"' >> ~/.bashrc && source ~/.bashrc'
    fi
fi

# ── Step 6: Systemd service (optional) ────────────────────────────────────────
if $INSTALL_SERVICE; then
    log_step "Installing systemd service"

    # Create system user if needed
    if ! id -u "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
        log_ok "Created system user: $SERVICE_USER"
    else
        log_info "System user '$SERVICE_USER' already exists."
    fi

    # Fix ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR" 2>/dev/null || true

    # Write service file
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=OpenNexus Telegram AI Assistant
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_PYTHON} ${INSTALL_DIR}/main.py bot
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable opennexus
    log_ok "Service installed and enabled."
    log_info "Start with: sudo systemctl start opennexus"
    log_info "Logs:       sudo journalctl -u opennexus -f"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${GREEN}  OpenNexus installed successfully!${RESET}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${BOLD}Next steps:${RESET}"
echo ""
echo -e "  1. Edit your config:"
echo -e "     ${CYAN}nano $CONFIG_DIR/config.toml${RESET}"
echo ""
echo -e "  2. Fill in bot_token, owner_id, allowed_users,"
echo -e "     and at least one provider API key."
echo ""
if $INSTALL_SERVICE; then
    echo -e "  3. Start the service:"
    echo -e "     ${CYAN}sudo systemctl start opennexus${RESET}"
    echo ""
    echo -e "  4. Follow logs:"
    echo -e "     ${CYAN}sudo journalctl -u opennexus -f${RESET}"
else
    echo -e "  3. Run OpenNexus:"
    echo -e "     ${CYAN}cd $INSTALL_DIR && $VENV_PYTHON main.py bot${RESET}"
    echo -e "     or just: ${CYAN}opennexus bot${RESET}"
fi
echo ""
