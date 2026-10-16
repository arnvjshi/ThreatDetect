#!/usr/bin/env bash
# ==============================================================================
# ThreatDetect — Auto-Start ESP32-CAM Pipeline
# ==============================================================================
# Call this after the backend is healthy to automatically start the camera
# pipeline so the demo is truly hands-free.
#
# Usage:
#   ./pi-autostart-camera.sh [esp32-base-url] [owner-email]
#
# Examples:
#   ./pi-autostart-camera.sh http://192.168.1.50 user@example.com
#   ./pi-autostart-camera.sh http://esp32cam.local user@example.com
# ==============================================================================

set -euo pipefail

ESP32_BASE="${1:-http://threatdetect-cam.local}"
OWNER_EMAIL="${2:-demo@threatdetect.local}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}[→]${NC} Waiting for backend to be healthy..."

for i in $(seq 1 60); do
  if curl -sf --max-time 3 "${BACKEND_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}[✓]${NC} Backend is healthy"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo -e "${RED}[✗]${NC} Backend not healthy after 60 attempts. Aborting."
    exit 1
  fi
  sleep 2
done

# Register a demo user if needed
echo -e "${CYAN}[→]${NC} Ensuring demo user is registered..."
curl -sf -X POST "${BACKEND_URL}/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"${OWNER_EMAIL}\", \"name\": \"Demo User\", \"camera_name\": \"ESP32-CAM\"}" \
  > /dev/null 2>&1 || true

# Start the camera pipeline with retries in case ESP32 is still booting/connecting
STREAM_URL="${ESP32_BASE}/stream"
FLASH_URL="${ESP32_BASE}/flash"

echo -e "${CYAN}[→]${NC} Connecting to ESP32-CAM pipeline..."
echo "    Source:   ${STREAM_URL}"
echo "    Flash:    ${FLASH_URL}"
echo "    Owner:    ${OWNER_EMAIL}"

STARTED=false
RESPONSE=""
for attempt in $(seq 1 15); do
  RESPONSE=$(curl -sf -X POST "${BACKEND_URL}/start" \
    -H "Content-Type: application/json" \
    -d "{
      \"source\": \"${STREAM_URL}\",
      \"owner_email\": \"${OWNER_EMAIL}\",
      \"camera_mode\": \"esp32\",
      \"flash_url\": \"${FLASH_URL}\"
    }" 2>&1) || true

  if echo "$RESPONSE" | grep -q '"running":true'; then
    STARTED=true
    break
  fi
  echo -e "${YELLOW}[→]${NC} Camera not ready yet (attempt $attempt/15). Retrying in 3s..."
  sleep 3
done

if [[ "$STARTED" == "true" ]]; then
  echo -e "${GREEN}[✓]${NC} Camera pipeline started successfully!"
  echo -e "${GREEN}[✓]${NC} Demo is live at ${CYAN}http://$(hostname -I | awk '{print $1}'):3000${NC}"
else
  echo -e "${YELLOW}[!]${NC} Camera start response: $RESPONSE"
  echo -e "${YELLOW}[!]${NC} The ESP32-CAM could not be connected automatically after 15 attempts."
  echo -e "${YELLOW}[!]${NC} Verify ESP32 is powered on and connected to the same WiFi, or start it from the dashboard."
fi
