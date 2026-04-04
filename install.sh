#!/usr/bin/env bash

set -euo pipefail

REPO_URL="https://github.com/nexus-AI26/OpenNexus.git"
INSTALL_SERVICE=false

if [[ $EUID -eq 0 ]]; then
    INSTALL_DIR="/opt/opennexus"
    CONFIG_DIR="/root/.opennexus"
    INSTALL_SERVICE=true
else
    INSTALL_DIR="$HOME/opennexus"
    CONFIG_DIR="$HOME/.opennexus"
fi

SERVICE_FILE="/etc/systemd/system/opennexus.service"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

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

for arg in "$@"; do
    case "$arg" in
        --no-service) INSTALL_SERVICE=false ;;
        --help|-h)
            echo "Usage: bash install.sh [--no-service]"
            echo "  --no-service   Skip systemd service installation"
            exit 0 ;;
    esac
done

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

log_step "Checking and installing system dependencies"

if ! command -v git &>/dev/null; then
    log_warn "git not found — installing..."
    apt-get update -qq && apt-get install -y -qq git
    log_ok "git installed."
fi
log_ok "Found $(git --version)"

if ! python3 -c "import ensurepip" &>/dev/null 2>&1; then
    log_warn "python3-venv not found — installing..."
    apt-get update -qq && apt-get install -y -qq python3-venv python3-pip
    log_ok "python3-venv installed."
fi

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
    log_error "Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ not found."
    echo "  sudo apt install python3.11"
    exit 1
fi
log_ok "Found $($PYTHON_BIN --version)"

log_step "Installing OpenNexus to $INSTALL_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    log_info "Existing installation found — updating..."
    git -C "$INSTALL_DIR" pull --ff-only
    log_ok "Updated to latest."
else
    if [[ -d "$INSTALL_DIR" ]]; then
        log_warn "$INSTALL_DIR exists but is not a git repo — removing..."
        rm -rf "$INSTALL_DIR"
    fi
    log_info "Cloning from $REPO_URL ..."
    git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
    log_ok "Cloned successfully."
fi

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

log_info "Upgrading pip..."
"$VENV_PIP" install --quiet --upgrade pip

log_info "Installing dependencies..."
"$VENV_PIP" install --quiet -r "$INSTALL_DIR/requirements.txt"
log_info "Installing package (editable, optional CLI: opennexus)..."
"$VENV_PIP" install --quiet -e "$INSTALL_DIR"
log_ok "Dependencies installed."

log_step "Setting up config directory"

mkdir -p "$CONFIG_DIR/skills" "$CONFIG_DIR/logs"

if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "$INSTALL_DIR/config.toml.example" "$CONFIG_DIR/config.toml"
    log_ok "Created $CONFIG_DIR/config.toml from example."
    log_warn "Edit $CONFIG_DIR/config.toml and fill in:"
    log_warn "  - access.owner_id (Telegram ID; also used by Web UI)"
    log_warn "  - access.allowed_users"
    log_warn "  - At least one provider API key (or Ollama)"
    log_warn "  - bot_token       (from @BotFather; omit for Web-only)"
else
    log_info "Config already exists — skipping."
fi

log_step "Installing launcher"

if [[ $EUID -eq 0 ]]; then
    LAUNCHER="/usr/local/bin/opennexus"
else
    LAUNCHER="$HOME/.local/bin/opennexus"
    mkdir -p "$HOME/.local/bin"
fi

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$INSTALL_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"
log_ok "Installed launcher at $LAUNCHER"

if [[ $EUID -ne 0 ]] && [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    export PATH="$HOME/.local/bin:$PATH"
    log_ok "Added ~/.local/bin to PATH"
fi

if $INSTALL_SERVICE; then
    log_step "Installing systemd service"

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=OpenNexus AI (Telegram + Web UI)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_PYTHON} ${INSTALL_DIR}/main.py all
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
fi

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
echo -e "  2. Fill in owner_id, allowed_users, provider keys;"
echo -e "     add bot_token if you use Telegram (optional for Web-only)."
echo ""
if $INSTALL_SERVICE; then
    echo -e "  3. Start OpenNexus (Telegram + Web on port 8000):"
    echo -e "     ${CYAN}systemctl start opennexus${RESET}"
    echo ""
    echo -e "  4. Web UI: ${CYAN}http://<host>:8000${RESET} (runs in background with the bot)"
    echo ""
    echo -e "  5. Logs:"
    echo -e "     ${CYAN}journalctl -u opennexus -f${RESET}"
else
    echo -e "  3. From any directory, run (launcher uses repo venv):"
    echo -e "     ${CYAN}opennexus${RESET}   ${BOLD}# default: Telegram + Web on :8000${RESET}"
    echo -e "     ${CYAN}opennexus web${RESET}  ${BOLD}# Web UI only${RESET}"
    echo -e "     ${CYAN}opennexus bot${RESET}  ${BOLD}# Telegram only${RESET}"
    echo ""
    echo -e "     Or: ${CYAN}cd $INSTALL_DIR && ./venv/bin/python main.py all${RESET}"
fi
echo ""
