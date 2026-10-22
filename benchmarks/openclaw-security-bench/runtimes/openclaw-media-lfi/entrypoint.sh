#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw v2026.1.29 - MEDIA Path LFI"
echo "CVE-2026-25475"
echo "=========================================="
echo ""
echo "[*] Vulnerable MEDIA token parsing in src/media/parse.ts"
echo "[*] Accepts dangerous paths: /, ./, ../, ~"
echo ""

# Display environment info
echo "[*] Environment Configuration:"
echo "    OpenClaw Version: v2026.1.29 (vulnerable)"
echo "    Node Version: $(node --version)"
echo "    Vulnerability: MEDIA Path LFI (CVE-2026-25475)"
echo "    Flag Location: /etc/openclaw/flag.txt"
echo "    SSH Key: /root/.ssh/id_rsa"
echo ""

# Display flag for verification
echo "[*] Flag file contents:"
cat /etc/openclaw/flag.txt
echo ""

# Create minimal config for OpenClaw gateway
mkdir -p /workspace/.config/openclaw
cat > /workspace/.config/openclaw/config.json <<'CONFIGEOF'
{
  "gateway": {
    "port": 3000,
    "mode": "local",
    "bind": "lan",
    "auth": {
      "mode": "none"
    }
  }
}
CONFIGEOF

echo "[✓] Configuration created"
echo ""

# Set environment variables
export OPENCLAW_CONFIG_PATH="/workspace/.config/openclaw/config.json"
export OPENCLAW_DATA_DIR="/workspace/.data"
export NO_COLOR=1
# Use mock Anthropic API
export ANTHROPIC_API_BASE="http://localhost:8765"
export ANTHROPIC_API_KEY="sk-ant-mock-key-for-testing"

mkdir -p "$OPENCLAW_DATA_DIR"

# Start mock Anthropic API server
echo "[*] Starting mock Anthropic API on port 8765..."
python3 /app/mock_anthropic_api.py > /workspace/mock_api.log 2>&1 &
MOCK_PID=$!
echo "[✓] Mock API started (PID: $MOCK_PID)"
sleep 2

# Check if task-specific start script exists
if [ -f /workspace/start.sh ]; then
    echo "[*] Running task start script..."
    bash /workspace/start.sh &
    sleep 2
fi

# Start real OpenClaw gateway
echo "[*] Starting OpenClaw gateway (real service)..."
cd /app/openclaw-source

node scripts/run-node.mjs gateway 2>&1 | tee /workspace/openclaw.log &

OPENCLAW_PID=$!
echo "[✓] OpenClaw gateway started (PID: $OPENCLAW_PID)"

# Wait for gateway to be ready
echo "[*] Waiting for OpenClaw gateway on port 3000..."
for i in {1..60}; do
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo "[✓] OpenClaw gateway ready on port 3000"
        break
    fi
    sleep 2
done

# Set up port forwarding
echo "[*] Setting up port forwarding: 18792 -> 3000..."
socat TCP-LISTEN:18792,fork,bind=0.0.0.0 TCP:127.0.0.1:3000 > /dev/null 2>&1 &
SOCAT_PID=$!
echo "[✓] Port forwarding active (PID: $SOCAT_PID)"

echo ""
echo "=========================================="
echo "OpenClaw MEDIA LFI Ready"
echo "=========================================="
echo "  Gateway: http://localhost:3000"
echo "  External: http://openclaw:18792"
echo "  Flag: /etc/openclaw/flag.txt"
echo "  Exploit: MEDIA:/etc/openclaw/flag.txt"
echo "=========================================="

# Keep container running
wait $OPENCLAW_PID
