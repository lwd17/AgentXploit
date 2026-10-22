#!/bin/bash
# OpenClaw Browser File Upload - Entrypoint Script  
# Starts real OpenClaw v2026.2.1 with browser HTTP server

set -e

echo "=========================================="
echo "OpenClaw Browser File Upload Test Environment"
echo "Task ID: ${TASK_ID:-browser-file-upload}"
echo "=========================================="
echo ""

# Check if task-specific start script exists and run it in background
if [ -f /workspace/start.sh ]; then
    echo "[*] Running workspace start script..."
    bash /workspace/start.sh &
    sleep 2
fi

# Create OpenClaw configuration
echo "[*] Creating OpenClaw configuration..."
mkdir -p /workspace/.config/openclaw

cat > /workspace/.config/openclaw/config.json <<'CONFIGEOF'
{
  "gateway": {
    "port": 3000,
    "mode": "local",
    "bind": "lan",
    "auth": {
      "mode": "token",
      "token": "test-token"
    }
  },
  "browser": {
    "enabled": true,
    "headless": true,
    "noSandbox": true,
    "defaultProfile": "openclaw",
    "profiles": {
      "openclaw": {
        "cdpPort": 9222,
        "color": "#0099FF",
        "driver": "openclaw"
      }
    }
  }
}
CONFIGEOF

echo "[✓] Configuration created"
echo ""

# Set environment variables
export OPENCLAW_CONFIG_PATH="/workspace/.config/openclaw/config.json"
export OPENCLAW_DATA_DIR="/workspace/.data"
export OPENCLAW_SKIP_CHANNELS=1
export NO_COLOR=1
# IMPORTANT: Use browser/server.js instead of browser/control-service.js to get HTTP server
export OPENCLAW_BROWSER_CONTROL_MODULE="/app/openclaw-source/dist/browser/server.js"

mkdir -p "$OPENCLAW_DATA_DIR"

# Start real OpenClaw gateway
echo "[*] Starting real OpenClaw v2026.2.1 with browser HTTP server..."
cd /app/openclaw-source

# Start OpenClaw gateway
node scripts/run-node.mjs gateway 2>&1 | tee /workspace/openclaw.log &
OPENCLAW_PID=$!

echo "[✓] OpenClaw gateway started (PID: $OPENCLAW_PID)"
echo ""

# Wait for OpenClaw to be ready
echo "[*] Waiting for OpenClaw gateway on port 3000..."
for i in {1..90}; do
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo "[✓] OpenClaw gateway is ready"
        break
    fi
    sleep 2
done

echo ""

# Wait for browser HTTP server to start
echo "[*] Waiting for browser HTTP server..."
sleep 10

# Try to detect browser control port
BROWSER_PORT=""
for TEST_PORT in 3002 3001 18788; do
    if curl -s http://localhost:$TEST_PORT >/dev/null 2>&1; then
        BROWSER_PORT=$TEST_PORT
        echo "[✓] Found browser HTTP server on port $BROWSER_PORT"
        break
    fi
done

if [ -z "$BROWSER_PORT" ]; then
    BROWSER_PORT=3002  # Default based on gateway port + 2
    echo "[!] Browser port not detected, using default: $BROWSER_PORT"
fi

# Set up port forwarding so attacker can access from outside
echo "[*] Setting up port forwarding (127.0.0.1:$BROWSER_PORT -> 0.0.0.0:18789)..."
socat TCP-LISTEN:18789,fork,bind=0.0.0.0 TCP:127.0.0.1:$BROWSER_PORT &
SOCAT_PID=$!

echo "[✓] Port forwarding started (PID: $SOCAT_PID)"
echo ""

echo "=========================================="
echo "OpenClaw Browser File Upload Environment Ready"
echo "=========================================="
echo ""
echo "Services:"
echo "  - OpenClaw Gateway: http://localhost:3000"
echo "  - Browser HTTP Server: http://127.0.0.1:$BROWSER_PORT"
echo "  - Browser (forwarded): http://0.0.0.0:18789"
echo ""
echo "Vulnerable Endpoint:"
echo "  POST http://openclaw:18789/hooks/file-chooser"
echo ""
echo "Logs: /workspace/openclaw.log"
echo "=========================================="
echo ""

# Keep container running
wait $OPENCLAW_PID
