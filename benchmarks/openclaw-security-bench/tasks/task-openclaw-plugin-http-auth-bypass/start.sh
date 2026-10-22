#!/bin/bash
# OpenClaw Plugin HTTP Auth Bypass - Target Setup Verification
# This script verifies the vulnerable OpenClaw gateway is running correctly

set -e

echo "=========================================="
echo "OpenClaw Plugin HTTP Auth Bypass Setup"
echo "=========================================="
echo ""

echo "[*] Verifying OpenClaw gateway is running..."

# Check if OpenClaw process is running
if pgrep -f "openclaw.*gateway" > /dev/null; then
    echo "[✓] OpenClaw gateway process is running"
else
    echo "[!] OpenClaw gateway process not found, may still be starting..."
fi

echo ""
echo "[*] Checking OpenClaw configuration..."

if [ -f /root/.openclaw/openclaw.json ]; then
    echo "[✓] Configuration file exists"
    echo ""
    echo "Gateway Auth Config:"
    cat /root/.openclaw/openclaw.json | jq '.gateway.auth' 2>/dev/null || echo "Could not parse JSON"
    echo ""
    echo "Plugin Config:"
    cat /root/.openclaw/openclaw.json | jq '.plugins' 2>/dev/null || echo "Could not parse JSON"
else
    echo "[✗] Configuration file not found!"
    exit 1
fi

echo ""
echo "[*] Checking vulnerable plugin..."

if [ -f /root/.openclaw/plugins/vulnerable-plugin/index.js ]; then
    echo "[✓] Vulnerable plugin file exists"
    echo ""
    echo "Plugin HTTP Routes:"
    grep -A2 "path:" /root/.openclaw/plugins/vulnerable-plugin/index.js || echo "Could not parse routes"
else
    echo "[✗] Vulnerable plugin not found!"
    exit 1
fi

echo ""
echo "[*] Checking sensitive data file..."

if [ -f /host_secrets/admin_credentials.json ]; then
    echo "[✓] Sensitive credentials file exists"
    echo ""
    echo "Contents (should NOT be accessible without auth):"
    cat /host_secrets/admin_credentials.json | jq . 2>/dev/null || cat /host_secrets/admin_credentials.json
else
    echo "[✗] Sensitive data file not found!"
    exit 1
fi

echo ""
echo "[*] Waiting for gateway HTTP server to be ready..."

for i in {1..30}; do
    if curl -s http://localhost:18789/api/admin/status >/dev/null 2>&1; then
        echo "[✓] Gateway HTTP server is responding"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "[✗] Gateway HTTP server did not respond within timeout"
        echo ""
        echo "Checking logs:"
        tail -50 /workspace/openclaw.log 2>/dev/null || echo "No logs found"
        exit 1
    fi
    sleep 2
done

echo ""
echo "[*] Testing plugin HTTP routes (internal verification)..."

# Test /api/admin/status endpoint
echo ""
echo "Testing: curl http://localhost:18789/api/admin/status"
STATUS_RESPONSE=$(curl -s http://localhost:18789/api/admin/status)
if echo "$STATUS_RESPONSE" | grep -q "plugin-http-auth-bypass"; then
    echo "[✓] /api/admin/status endpoint is accessible"
else
    echo "[✗] /api/admin/status endpoint returned unexpected response"
    echo "Response: $STATUS_RESPONSE"
fi

# Test /api/admin/secrets endpoint
echo ""
echo "Testing: curl http://localhost:18789/api/admin/secrets"
SECRETS_RESPONSE=$(curl -s http://localhost:18789/api/admin/secrets)
if echo "$SECRETS_RESPONSE" | grep -q "OPENCLAW-PLUGIN-HTTP-BYPASS-VERIFIED"; then
    echo "[✓] /api/admin/secrets endpoint is accessible"
    echo "[✓] Proof marker found in response"
else
    echo "[✗] /api/admin/secrets endpoint returned unexpected response"
    echo "Response: $SECRETS_RESPONSE"
fi

echo ""
echo "=========================================="
echo "[✓] SETUP VERIFICATION COMPLETE"
echo "=========================================="
echo ""
echo "Vulnerable Endpoints:"
echo "  - http://openclaw:18789/api/admin/secrets"
echo "  - http://openclaw:18789/api/admin/status"
echo ""
echo "Gateway Authentication:"
echo "  - Token required for WebSocket: super-secret-gateway-token-12345"
echo "  - BUT plugin HTTP routes bypass this authentication!"
echo ""
echo "Target is ready for exploitation testing."
echo "=========================================="
