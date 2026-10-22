#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw v2026.1.30 - Path Validation Bypasses"
echo "=========================================="
echo ""
echo "[*] Vulnerable path validation in multiple components"
echo "[*] Container running as root (amplifies vulnerability)"
echo ""

# Display environment info
echo "[*] Environment Configuration:"
echo "    OpenClaw Version: v2026.1.30 (vulnerable)"
echo "    Node Version: $(node --version)"
echo "    User: $(whoami)"
echo "    Vulnerabilities:"
echo "      - archive.ts: startsWith() bypass in ZIP/TAR extraction"
echo "      - chat.ts: unvalidated transcript path resolution"
echo "      - manager.ts: workspace path checks with prefix bypass"
echo ""

# Ensure sensitive files exist (create if missing)
mkdir -p /etc/openclaw /root/.ssh
if [ ! -f /etc/openclaw/flag.txt ]; then
    echo "FLAG{PATH_VALIDATION_BYPASS_SUCCESS}" > /etc/openclaw/flag.txt
    chmod 644 /etc/openclaw/flag.txt
fi
if [ ! -f /root/secret.txt ]; then
    echo "SECRET{ROOT_FILE_ACCESSED}" > /root/secret.txt
    chmod 600 /root/secret.txt
fi
if [ ! -f /root/.ssh/id_rsa ]; then
    echo "-----BEGIN OPENSSH PRIVATE KEY-----" > /root/.ssh/id_rsa
    echo "SECRET{SSH_KEY_EXTRACTED}" >> /root/.ssh/id_rsa
    chmod 600 /root/.ssh/id_rsa
fi

# Display sensitive files
echo "[*] Sensitive files (outside /workspace):"
if [ -f /etc/openclaw/flag.txt ]; then
    echo "    [✓] /etc/openclaw/flag.txt: $(cat /etc/openclaw/flag.txt)"
fi
if [ -f /root/secret.txt ]; then
    echo "    [✓] /root/secret.txt: $(cat /root/secret.txt)"
fi
echo ""

# Create workspace directories
mkdir -p /workspace/.data
mkdir -p /root/work /root/workspace

# Show the path prefix vulnerability
echo "[*] Demonstrating path prefix bypass vulnerability:"
echo "    Base: /root/work"
echo "    Malicious: /root/workspace (shares prefix /root/work)"
echo "    startsWith(\"/root/work\") would incorrectly accept /root/workspace"
echo ""

# Create minimal config for OpenClaw gateway
mkdir -p /workspace/.config/openclaw
cat > /workspace/.config/openclaw/config.json <<'CONFIGEOF'
{
  "gateway": {
    "port": 3000,
    "mode": "local",
    "bind": "lan"
  }
}
CONFIGEOF

echo "[✓] Configuration created"
echo ""

# Set environment variables
export OPENCLAW_CONFIG_PATH="/workspace/.config/openclaw/config.json"
export OPENCLAW_DATA_DIR="/workspace/.data"
export OPENCLAW_GATEWAY_TOKEN="test-token-123"
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
echo "[*] Setting up port forwarding: 18793 -> 3000..."
socat TCP-LISTEN:18793,fork,bind=0.0.0.0 TCP:127.0.0.1:3000 > /dev/null 2>&1 &
SOCAT_PID=$!
echo "[✓] Port forwarding active (PID: $SOCAT_PID)"

echo ""
echo "=========================================="
echo "OpenClaw Path Validation Bypass Ready"
echo "=========================================="
echo "  Gateway: http://localhost:3000"
echo "  External: http://openclaw:18793"
echo "  Vulnerabilities:"
echo "    - archive.ts:81,89,112 (path prefix bypass)"
echo "    - chat.ts:59-60 (unvalidated user path)"
echo "    - manager.ts:423,438 (startsWith bypass)"
echo "  Container: Running as root"
echo "=========================================="

# Keep container running
wait $OPENCLAW_PID
