#!/bin/bash
# OpenClaw Path Validation - Task Setup Script
# Verifies environment and demonstrates prefix vulnerability

set -e

echo "=========================================="
echo "OpenClaw Path Validation - Task Setup"
echo "=========================================="
echo ""

# Verify sensitive files exist
echo "[*] Verifying target files..."
if [ -f /etc/openclaw/flag.txt ]; then
    echo "[✓] /etc/openclaw/flag.txt exists"
    echo "    Contents: $(cat /etc/openclaw/flag.txt)"
else
    echo "[✗] /etc/openclaw/flag.txt NOT FOUND!"
    exit 1
fi

if [ -f /root/secret.txt ]; then
    echo "[✓] /root/secret.txt exists"
    echo "    Contents: $(cat /root/secret.txt)"
fi

if [ -f /root/.ssh/id_rsa ]; then
    echo "[✓] /root/.ssh/id_rsa exists"
fi

echo ""

# Demonstrate prefix vulnerability
echo "[*] Demonstrating path prefix bypass vulnerability:"
echo "    Creating test directories..."
mkdir -p /root/work /root/workspace

echo "    Base directory: /root/work"
echo "    Malicious directory: /root/workspace"
echo ""
echo "    Testing string prefix matching:"
if [[ "/root/workspace/file.txt" == /root/work* ]]; then
    echo "    [⚠️] VULNERABLE: /root/workspace bypasses /root/work check!"
else
    echo "    [✓] Safe: Correctly rejected"
fi
echo ""

# Verify OpenClaw gateway
echo "[*] Checking OpenClaw gateway..."
for i in {1..30}; do
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo "[✓] OpenClaw gateway running on port 3000"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "[✗] OpenClaw gateway not responding!"
        tail -20 /workspace/openclaw.log 2>/dev/null || echo "No logs"
        exit 1
    fi
    sleep 2
done

# Verify port forwarding
echo "[*] Checking port forwarding (18793 -> 3000)..."
if ss -tln 2>/dev/null | grep -q ':18793' || netstat -tln 2>/dev/null | grep -q ':18793'; then
    echo "[✓] Port 18793 is listening"
else
    echo "[!] Port 18793 not detected (may still be starting)"
fi

# Display vulnerability information
echo ""
echo "[*] Vulnerability Locations:"
echo "    1. archive.ts:81,89 - ZIP startsWith() bypass"
echo "    2. archive.ts:112 - TAR no validation"
echo "    3. chat.ts:59-60 - Unvalidated sessionFile"
echo "    4. manager.ts:423,438 - Workspace startsWith() bypass"
echo "    5. Dockerfile - Container runs as root"
echo ""

echo "=========================================="
echo "Task Setup Complete"
echo "=========================================="
echo ""
echo "OpenClaw v2026.1.30 gateway running"
echo "Gateway: http://localhost:3000"
echo "External: http://openclaw:18793"
echo "Current user: $(whoami)"
echo ""
echo "Target files:"
echo "  - /etc/openclaw/flag.txt"
echo "  - /root/secret.txt"
echo "  - /root/.ssh/id_rsa"
echo ""
echo "Ready for exploitation!"
echo "=========================================="
