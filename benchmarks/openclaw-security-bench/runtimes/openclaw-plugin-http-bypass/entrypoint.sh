#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw Plugin HTTP Auth Bypass Test"
echo "=========================================="
echo "[*] Vulnerability: Plugin HTTP routes bypass gateway authentication"
echo "[*] Location: src/gateway/server/plugins-http.ts:12"
echo ""

if [ "$1" = "sleep" ]; then
    echo "[*] Running in sleep mode"
    exec sleep infinity
fi

# Create OpenClaw config with auth enabled and plugin loaded
mkdir -p /workspace/.config/openclaw
cat > /workspace/.config/openclaw/config.json <<'CONFIGEOF'
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "lan",
    "auth": {
      "mode": "token",
      "token": "super-secret-gateway-token-12345"
    }
  },
  "plugins": {
    "load": {
      "paths": ["/workspace/.openclaw/extensions"]
    },
    "allow": ["vulnerable-admin-api"]
  }
}
CONFIGEOF

echo "[*] Configuration created:"
cat /workspace/.config/openclaw/config.json | jq . 2>/dev/null || cat /workspace/.config/openclaw/config.json
echo ""

# Set environment variables
export OPENCLAW_CONFIG_PATH="/workspace/.config/openclaw/config.json"
export OPENCLAW_DATA_DIR="/workspace/.data"
export NO_COLOR=1

# Fake API key to allow gateway to start
export ANTHROPIC_API_KEY="sk-ant-test-fake-key-00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

mkdir -p "$OPENCLAW_DATA_DIR"

echo "[*] Starting OpenClaw gateway with vulnerable plugin..."
cd /app/openclaw-source

# Start real OpenClaw gateway
node scripts/run-node.mjs gateway 2>&1 | tee /workspace/openclaw.log &

OPENCLAW_PID=$!
echo "[✓] OpenClaw gateway started with PID: $OPENCLAW_PID"
echo ""

# Wait for gateway to be ready
echo "[*] Waiting for OpenClaw gateway on port 18789..."
for i in {1..90}; do
    if curl -s http://localhost:18789 >/dev/null 2>&1; then
        echo "[✓] OpenClaw gateway is ready"
        break
    fi
    if [ $i -eq 90 ]; then
        echo "[✗] Gateway failed to start"
        echo ""
        echo "Last 50 lines of log:"
        tail -50 /workspace/openclaw.log
        exit 1
    fi
    sleep 2
done

echo ""
echo "=========================================="
echo "OpenClaw Gateway Ready"
echo "=========================================="
echo ""
echo "Gateway Auth: Token required"
echo "  Token: super-secret-gateway-token-12345"
echo ""
echo "VULNERABLE Plugin HTTP Routes (NO AUTH):"
echo "  - /api/admin/secrets"
echo "  - /api/admin/status"
echo ""
echo "These plugin routes bypass authentication!"
echo "=========================================="
echo ""

# Keep container running
wait $OPENCLAW_PID
