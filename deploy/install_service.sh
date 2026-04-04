#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (e.g. sudo ./install_service.sh)"
  exit 1
fi

echo "Installing OpenNexus Systemd Service..."

if [ "$SUDO_USER" ]; then
    USER_NAME=$SUDO_USER
else
    USER_NAME=$(whoami)
fi

APP_DIR=$(pwd)

echo "Setting up service for user: ${USER_NAME}"
echo "Application directory: ${APP_DIR}"

cat > /etc/systemd/system/opennexus.service << EOF
[Unit]
Description=OpenNexus AI Assistant
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/env python3 main.py
Environment=PATH=${APP_DIR}/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling OpenNexus to start on boot..."
systemctl enable opennexus.service

echo "Starting OpenNexus service..."
systemctl start opennexus.service

echo "Service installed! Use 'systemctl status opennexus' to check status."
