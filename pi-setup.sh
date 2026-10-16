#!/usr/bin/env bash
# ==============================================================================
# ThreatDetect — Raspberry Pi 5 One-Shot Setup Script
# ==============================================================================
# Run this ONCE after cloning the repo on the Pi:
#
#   chmod +x pi-setup.sh
#   sudo ./pi-setup.sh
#
# What it does:
#   1. Installs Docker + Docker Compose (if not already installed)
#   2. Detects the Pi's LAN IP and writes it to .env.pi
#   3. Builds and starts all containers
#   4. Creates a systemd service for auto-start on boot
#   5. Verifies everything is running
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*"; }
info()  { echo -e "${CYAN}[→]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# ── Ensure root ──────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  err "This script must be run as root (sudo ./pi-setup.sh)"
  exit 1
fi

ACTUAL_USER="${SUDO_USER:-$(whoami)}"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       ThreatDetect — Raspberry Pi 5 Setup              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Install Docker ───────────────────────────────────────────────────
if command -v docker &> /dev/null; then
  log "Docker already installed: $(docker --version)"
else
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "$ACTUAL_USER"
  systemctl enable docker
  systemctl start docker
  log "Docker installed and enabled"
fi

# Ensure Docker Compose plugin is available
if docker compose version &> /dev/null; then
  log "Docker Compose plugin available: $(docker compose version --short)"
else
  info "Installing Docker Compose plugin..."
  apt-get update
  apt-get install -y docker-compose-plugin
  log "Docker Compose plugin installed"
fi

# ── Step 2: Detect Pi's LAN IP ──────────────────────────────────────────────
PI_IP=$(hostname -I | awk '{print $1}')
PI_HOSTNAME=$(hostname)

if [[ -z "$PI_IP" ]]; then
  err "Could not detect LAN IP. Ensure WiFi or Ethernet is connected."
  exit 1
fi

log "Detected Pi IP: ${CYAN}$PI_IP${NC}"
log "Detected hostname: ${CYAN}$PI_HOSTNAME${NC}"

# ── Step 3: Update .env.pi with detected IP ─────────────────────────────────
ENV_FILE="$PROJECT_DIR/.env.pi"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$PROJECT_DIR/.env.pi.example" ]]; then
    warn ".env.pi not found. Initializing from .env.pi.example..."
    cp "$PROJECT_DIR/.env.pi.example" "$ENV_FILE"
  else
    err ".env.pi not found at $ENV_FILE"
    err "Please create it from .env.pi.example first"
    exit 1
  fi
fi

# Update the PI_IP line in the env file
sed -i "s/^PI_IP=.*/PI_IP=$PI_IP/" "$ENV_FILE"
sed -i "s/^PI_HOSTNAME=.*/PI_HOSTNAME=$PI_HOSTNAME/" "$ENV_FILE"
log "Updated .env.pi with PI_IP=$PI_IP, PI_HOSTNAME=$PI_HOSTNAME"

# ── Step 4: Build and start all containers ──────────────────────────────────
info "Building and starting all containers (this takes 5-15 minutes on first run)..."
cd "$PROJECT_DIR"

# Build with the Pi's IP baked into the frontend
export PI_IP PI_HOSTNAME
docker compose -f docker-compose.pi.yml --env-file .env.pi up -d --build

log "All containers started"

# ── Step 5: Create systemd service for auto-start ───────────────────────────
SERVICE_FILE="/etc/systemd/system/threatdetect.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=ThreatDetect - AI Threat Detection System
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose -f docker-compose.pi.yml --env-file .env.pi up -d
ExecStop=/usr/bin/docker compose -f docker-compose.pi.yml --env-file .env.pi down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable threatdetect.service
log "Systemd service created and enabled (auto-starts on boot)"

# ── Step 6: Set up mDNS so the Pi is reachable as <hostname>.local ──────────
if ! dpkg -l avahi-daemon &> /dev/null; then
  info "Installing Avahi (mDNS) for hostname.local resolution..."
  apt-get update
  apt-get install -y avahi-daemon
  systemctl enable avahi-daemon
  systemctl start avahi-daemon
  log "Avahi installed — Pi reachable at ${CYAN}${PI_HOSTNAME}.local${NC}"
else
  log "Avahi already installed — Pi reachable at ${CYAN}${PI_HOSTNAME}.local${NC}"
fi

# ── Step 7: Wait for services and verify ────────────────────────────────────
echo ""
info "Waiting for services to become healthy..."
sleep 10

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Service Health Check                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"

check_service() {
  local name="$1"
  local url="$2"
  if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
    log "$name — ${GREEN}OK${NC} ($url)"
  else
    warn "$name — ${YELLOW}not ready yet${NC} ($url) — may still be starting"
  fi
}

check_service "Backend API" "http://localhost:8000/health"
check_service "Frontend"    "http://localhost:3000"
check_service "Mailer"      "http://localhost:5001/health"
check_service "Mongo Express" "http://localhost:8081"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              🎉 Setup Complete!                        ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  Demo URL:  ${CYAN}http://$PI_IP:3000${GREEN}                      ║${NC}"
echo -e "${GREEN}║  Also:      ${CYAN}http://$PI_HOSTNAME.local:3000${GREEN}          ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  Backend:   ${CYAN}http://$PI_IP:8000/health${GREEN}               ║${NC}"
echo -e "${GREEN}║  MongoDB:   ${CYAN}http://$PI_IP:8081${GREEN}                      ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  The demo auto-starts on boot.                         ║${NC}"
echo -e "${GREEN}║  Just power on the Pi + ESP32-CAM on same WiFi.        ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Quick start:${NC}"
echo "  1. Open ${CYAN}http://$PI_IP:3000/register${NC} — register your email"
echo "  2. Go to ${CYAN}http://$PI_IP:3000${NC} — the dashboard"
echo "  3. Select 'ESP32-CAM' → enter ESP32 base URL → Start"
echo "  4. The system auto-detects threats and sends email alerts"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo "  View logs:        docker compose -f docker-compose.pi.yml logs -f"
echo "  Restart:          sudo systemctl restart threatdetect"
echo "  Stop:             sudo systemctl stop threatdetect"
echo "  Check status:     docker compose -f docker-compose.pi.yml ps"
echo ""
