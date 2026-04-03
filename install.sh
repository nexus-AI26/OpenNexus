#!/usr/bin/env bash
# install.sh — OpenNexus installer
# Usage:
#   bash install.sh              — interactive install
#   bash install.sh --service    — also install and enable systemd service
# Or via curl:
#   curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash

set -euo pipefail

REPO_URL="https://github.com/nexus-AI26/OpenNexus.git"
SERVICE_FILE="/etc/systemd/system/opennexus.service"
SERVICE_USER="opennexus"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11
INSTALL_SERVICE=false

# ── If root, install to /opt — otherwise install to ~/opennexus ──────────────
if [[ $EUID -eq 0 ]]; then
    INSTALL_DIR="/opt/opennexus"
    CONFIG_DIR="/root/.opennexus"
else
    INSTALL_DIR="$HOME/opennexus"
    CONFIG_DIR="$HOME/.opennexus"
fi

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERR ]${RESET}  $*"; }
log_step()  { echo -e "\n${BOLD}══ $* ${RESET}"; }

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --service) INSTALL_SERVICE=true ;;
        --help|-h)
            echo "Usage: bash install.sh [--service]"
            echo "  --service   Install and enable systemd service (requires root)"
            exit 0
            ;;
    esac
done

# ── Banner ────────────────────────────────────────────────────────────────────
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

# ── Step 1: System dependencies ───────────────────────────────────────────────
log_step "Checking and installing system dependencies"

# Auto-install git if missing
if ! command -v git &>/dev/null; then
    log_warn "git not found — attempting to install..."
    if [[ $EUID -eq 0 ]]; then
        apt-get update -qq && apt-get install -y -qq git
    else
        sudo apt-get update -qq && sudo apt-get install -y -qq git
    fi
    log_ok "git installed."
fi
log_ok "Found $(git --version)"

# Auto-install python3-venv if missing
if ! python3 -c "import ensurepip" &>/dev/null; then
    log_warn "python3-venv not found — attempting to install..."
    if [[ $EUID -eq 0 ]]; then
        apt-get update -qq && apt-get install -y -qq python3-venv python3-pip
    else
        sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip
    fi
    log_ok "python3-venv installed."
fi

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
    echo "  sudo apt install python3.11"
    exit 1
fi

log_ok "Found $($PYTHON_BIN --version)"

# ── Step 2: Clone or update ───────────────────────────────────────────────────
log_step "Installing OpenNexus to $INSTALL_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    log_info "Existing installation found — updating..."
    git -C "$INSTALL_DIR" pull --ff-only
    log_ok "Updated to latest."
else
    if [[ -d "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
        log_warn "$INSTALL_DIR exists and is not empty — removing and reinstalling..."
        rm -rf "$INSTALL_DIR"
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
"$VENV_PIP" install --quiet -r "$INSTALL_DIR/requirements.txt"
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

if [[ $EUID -eq 0 ]]; then
    LAUNCHER="/usr/local/bin/opennexus"
    cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$INSTALL_DIR/main.py" "\$@"
EOF
    chmod +x "$LAUNCHER"
    log_ok "Installed launcher at $LAUNCHER"
else
    LAUNCHER="$HOME/.local/bin/opennexus"
    mkdir -p "$HOME/.local/bin"
    cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$INSTALL_DIR/main.py" "\$@"
EOF
    chmod +x "$LAUNCHER"
    log_ok "Installed launcher at $LAUNCHER"
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        export PATH="$HOME/.local/bin:$PATH"
        log_ok "Added ~/.local/bin to PATH in .bashrc"
    fi
fi

# ── Step 6: Systemd service (optional) ────────────────────────────────────────
if $INSTALL_SERVICE; then
    log_step "Installing systemd service"

    if [[ $EUID -ne 0 ]]; then
        log_error "--service requires root. Re-run with sudo."
        exit 1
    fi

    if ! id -u "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
        log_ok "Created system user: $SERVICE_USER"
    else
        log_info "System user '$SERVICE_USER' already exists."
    fi

    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR" 2>/dev/null || true

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=OpenNexus Telegram AI Assistant
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_PYTHON} ${INSTALL_DIR}/main.py
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

# ── Done ──────────────────────────────────────────────────────────────────────
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
    echo -e "     ${CYAN}opennexus${RESET}"
fi
echo ""
