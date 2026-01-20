#!/bin/bash
#
# Installation script for Multi-Retailer Store Scraper
# Run as root or with sudo
#

set -e

# Configuration
INSTALL_DIR="/opt/retail-store-scraper"
SERVICE_USER="scraper"
SERVICE_GROUP="scraper"
PYTHON_VERSION="python3.11"

echo "=========================================="
echo "Multi-Retailer Store Scraper Installation"
echo "=========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (use sudo)"
   exit 1
fi

# Check Python version
if ! command -v $PYTHON_VERSION &> /dev/null; then
    echo "Error: $PYTHON_VERSION not found. Please install Python 3.11+"
    exit 1
fi

echo "1. Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
    echo "   Created user: $SERVICE_USER"
else
    echo "   User $SERVICE_USER already exists"
fi

echo "2. Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"

echo "3. Copying application files..."
# Copy from current directory (assumes script is run from repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cp -r "$REPO_DIR"/* "$INSTALL_DIR/"
rm -rf "$INSTALL_DIR/deploy"  # Don't need deploy scripts in install dir

echo "4. Creating virtual environment..."
$PYTHON_VERSION -m venv "$INSTALL_DIR/venv"

echo "5. Installing dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "6. Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

echo "7. Installing systemd service..."
cp "$SCRIPT_DIR/scraper.service" /etc/systemd/system/retail-scraper.service
systemctl daemon-reload

echo "8. Enabling service..."
systemctl enable retail-scraper.service

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start retail-scraper"
echo "  Stop:    sudo systemctl stop retail-scraper"
echo "  Status:  sudo systemctl status retail-scraper"
echo "  Logs:    sudo journalctl -u retail-scraper -f"
echo ""
echo "Manual run:"
echo "  cd $INSTALL_DIR"
echo "  sudo -u $SERVICE_USER ./venv/bin/python run.py --status"
echo ""
echo "Dashboard (optional):"
echo "  sudo -u $SERVICE_USER ./venv/bin/python dashboard/app.py"
echo "  Then access: http://localhost:5001"
echo ""
echo "Environment configuration:"
echo "  Edit $INSTALL_DIR/.env for proxy credentials"
echo ""
