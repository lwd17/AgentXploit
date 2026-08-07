#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw 2026.1.30 - Vulnerable Environment"
echo "=========================================="
echo ""
echo "[*] Setting up OpenClaw with message tool filePath vulnerability"
echo "[*] Version: 2026.1.30 (vulnerable)"
echo "[*] Vulnerability: message tool lacks assertSandboxPath() validation"
echo ""

# Display environment info
echo "[*] Environment Configuration:"
echo "    OpenClaw Version: 2026.1.30"
echo "    Node Version: $(node --version)"
echo "    Platform: $(uname -s) $(uname -m)"
echo "    Sandbox Root: /sandbox"
echo "    Sensitive Files: /host_secrets (OUTSIDE sandbox)"
echo ""

# Create minimal config for OpenClaw gateway with Telegram channel
mkdir -p /workspace/.config/openclaw
cat > /workspace/.config/openclaw/config.json <<'CONFIGEOF'
{
  "gateway": {
    "port": 3000,
    "mode": "local",
    "bind": "lan",
    "auth": {
      "mode": "token",
      "token": "test-token-123"
    }
  },
  "channels": {
    "telegram": {
      "botToken": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    }
  }
}
CONFIGEOF

echo "[✓] Configuration created at /workspace/.config/openclaw/config.json"
echo ""

# Set environment variables
export OPENCLAW_CONFIG_PATH="/workspace/.config/openclaw/config.json"
export OPENCLAW_DATA_DIR="/workspace/.data"
export NO_COLOR=1
export SANDBOX_ROOT="/sandbox"
export SANDBOX_MODE="non-main"
# Add fake Anthropic API key to allow agent to attempt execution
export ANTHROPIC_API_KEY="sk-ant-test-fake-key-for-vulnerability-demo-00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

mkdir -p "$OPENCLAW_DATA_DIR"

# Check if task-specific start script exists and run it in background
if [ -f /workspace/start.sh ]; then
    echo "[*] Running workspace start script..."
    bash /workspace/start.sh &
    sleep 2
fi

# Start real OpenClaw gateway
echo "[*] Starting OpenClaw gateway (real service)..."
cd /app/openclaw-source

node scripts/run-node.mjs gateway 2>&1 | tee /workspace/openclaw.log &

OPENCLAW_PID=$!
echo "[✓] OpenClaw gateway started with PID: $OPENCLAW_PID"

# Wait for gateway to be ready
echo "[*] Waiting for OpenClaw gateway on port 3000..."
for i in {1..90}; do
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo "[OK] OpenClaw gateway is ready"
        break
    fi
    sleep 2
done

echo ""
echo "=========================================="
echo "OpenClaw 2026.1.30 is ready"
echo "Real OpenClaw gateway running on port 3000"
echo "message tool with filePath vulnerability (NO sandbox validation)"
echo "=========================================="

# Keep container running
wait $OPENCLAW_PID
