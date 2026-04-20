#!/bin/bash
# JCAMP FxScalper ML — Linux VPS Deployment Script
# Tested on Ubuntu 22.04 (Hetzner CX23)
# Run as root: bash deploy_linux.sh

set -e

YOUR_HOME_IP="${1:-}"  # Pass your home IP as first argument: bash deploy_linux.sh 1.2.3.4

echo "========================================"
echo "JCAMP FxScalper ML — VPS Setup"
echo "========================================"

# --- 1. System update ---
echo "[1/7] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq

# --- 2. Install Python 3.11 ---
echo "[2/7] Installing Python 3.11..."
apt-get install -y -qq python3.11 python3.11-venv python3.11-dev build-essential

# --- 3. Create service user and directories ---
echo "[3/7] Creating user and directories..."
useradd --system --no-create-home --shell /bin/false jcamp 2>/dev/null || true
mkdir -p /opt/jcamp/predict_service/models
mkdir -p /var/log/jcamp

# --- 4. Copy files (run from local machine or upload manually) ---
echo "[4/7] NOTE: Copy your files to /opt/jcamp/predict_service/"
echo "      From your Windows PC, run:"
echo "      scp -r predict_service/* root@<VPS_IP>:/opt/jcamp/predict_service/"
echo "      scp models/eurusd_long_v05.joblib root@<VPS_IP>:/opt/jcamp/predict_service/models/"
echo ""
read -p "Press ENTER once files are uploaded..."

# --- 5. Python virtual environment + dependencies ---
echo "[5/7] Creating Python venv and installing dependencies..."
python3.11 -m venv /opt/jcamp/venv
/opt/jcamp/venv/bin/pip install --quiet --upgrade pip
/opt/jcamp/venv/bin/pip install --quiet -r /opt/jcamp/predict_service/requirements.txt

# Set permissions
chown -R jcamp:jcamp /opt/jcamp
chown -R jcamp:jcamp /var/log/jcamp

# --- 6. Install and start systemd service ---
echo "[6/7] Installing systemd service..."
cp /opt/jcamp/predict_service/jcamp-predict.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable jcamp-predict
systemctl start jcamp-predict

sleep 3
systemctl status jcamp-predict --no-pager

# --- 7. Firewall (UFW) ---
echo "[7/7] Configuring firewall..."
apt-get install -y -qq ufw
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"

if [ -n "$YOUR_HOME_IP" ]; then
    ufw allow from "$YOUR_HOME_IP" to any port 8000 comment "cTrader PC"
    echo "Port 8000 allowed for: $YOUR_HOME_IP"
else
    echo "WARNING: No IP provided. Port 8000 is NOT open yet."
    echo "Run this when you know your home IP:"
    echo "  ufw allow from <YOUR_IP> to any port 8000"
fi

ufw --force enable
ufw status verbose

echo ""
echo "========================================"
echo "DONE. Service running on port 8000."
echo ""
echo "Test from your PC:"
echo "  curl http://<VPS_IP>:8000/health"
echo ""
echo "In cTrader, set API URL to:"
echo "  http://<VPS_IP>:8000/predict"
echo "========================================"
