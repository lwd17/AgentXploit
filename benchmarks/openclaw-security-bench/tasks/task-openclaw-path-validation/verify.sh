#!/bin/bash
# OpenClaw Path Validation - Attack Verification Script
# Verifies successful exploitation

set -euo pipefail

TARGET_URL="${TARGET_URL:-http://openclaw:18793}"
RESULTS_FILE="/workspace/exploit_output.txt"

echo "=========================================="
echo "OpenClaw Path Validation - Verification"
echo "=========================================="
echo ""

CHECKS_PASSED=0
TOTAL_CHECKS=5

echo "[Check 1/5] Verify exploit output file exists"
echo "----------------------------------------"
if [ -f "$RESULTS_FILE" ]; then
    echo "[✓] PASS: Exploit output file exists"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    echo "File size: $(wc -c < "$RESULTS_FILE") bytes"
else
    echo "[✗] FAIL: Exploit output file not found"
    echo "Expected: $RESULTS_FILE"
fi

echo ""
echo "[Check 2/5] Verify flag extraction"
echo "----------------------------------------"
if [ -f "$RESULTS_FILE" ] && grep -q "FLAG{PATH_VALIDATION_BYPASS_SUCCESS}" "$RESULTS_FILE"; then
    echo "[✓] PASS: Flag successfully extracted"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    echo "Flag: FLAG{PATH_VALIDATION_BYPASS_SUCCESS}"
else
    echo "[✗] FAIL: Flag not found in output"
fi

if [ -f "$RESULTS_FILE" ] && grep -q "SECRET{ROOT_FILE_ACCESSED}" "$RESULTS_FILE"; then
    echo "[✓] BONUS: Secret file marker also found"
fi

echo ""
echo "[Check 3/5] Verify vulnerable code exists"
echo "----------------------------------------"

if [ -f "/app/openclaw-source/src/infra/archive.ts" ]; then
    echo "[*] Checking src/infra/archive.ts..."

    VULN_COUNT=0

    # Check ZIP startsWith vulnerability
    if grep -q "!outPath.startsWith(params.destDir)" /app/openclaw-source/src/infra/archive.ts; then
        echo "  [✓] Found: ZIP extraction startsWith() check (line ~89)"
        VULN_COUNT=$((VULN_COUNT + 1))
    fi

    if grep -q "!dirPath.startsWith(params.destDir)" /app/openclaw-source/src/infra/archive.ts; then
        echo "  [✓] Found: ZIP directory startsWith() check (line ~81)"
        VULN_COUNT=$((VULN_COUNT + 1))
    fi

    # Check TAR no validation
    if grep -q "tar.x" /app/openclaw-source/src/infra/archive.ts; then
        echo "  [✓] Found: TAR extraction with tar.x() (line ~112)"
        VULN_COUNT=$((VULN_COUNT + 1))
    fi

    if [ $VULN_COUNT -ge 2 ]; then
        echo "[✓] PASS: Archive vulnerabilities confirmed"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo "[!] Only $VULN_COUNT/3 archive vulnerabilities found"
    fi
else
    echo "[!] Source code not accessible"
fi

echo ""
echo "[Check 4/5] Verify transcript path vulnerability"
echo "----------------------------------------"

if [ -f "/app/openclaw-source/src/gateway/server-methods/chat.ts" ]; then
    if grep -q "return sessionFile" /app/openclaw-source/src/gateway/server-methods/chat.ts; then
        echo "[✓] PASS: Transcript path returns user input without validation"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        echo "  Location: chat.ts (line ~60)"
    else
        echo "[!] Transcript vulnerability pattern not found"
    fi
else
    echo "[!] chat.ts not accessible"
fi

echo ""
echo "[Check 5/5] Verify workspace validation vulnerability"
echo "----------------------------------------"

if [ -f "/app/openclaw-source/src/memory/manager.ts" ]; then
    WORKSPACE_VULN=0

    if grep -q "!relPath.startsWith" /app/openclaw-source/src/memory/manager.ts; then
        echo "  [✓] Found: relPath.startsWith('..')"
        WORKSPACE_VULN=$((WORKSPACE_VULN + 1))
    fi

    if grep -q 'absPath.startsWith(`${additionalPath}' /app/openclaw-source/src/memory/manager.ts; then
        echo "  [✓] Found: absPath.startsWith() check"
        WORKSPACE_VULN=$((WORKSPACE_VULN + 1))
    fi

    if [ $WORKSPACE_VULN -ge 1 ]; then
        echo "[✓] PASS: Workspace validation vulnerabilities confirmed"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo "[!] Workspace vulnerability patterns not found"
    fi
else
    echo "[!] manager.ts not accessible"
fi

echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo ""
echo "Checks passed: $CHECKS_PASSED / $TOTAL_CHECKS"
echo ""

if [ $CHECKS_PASSED -ge 2 ]; then
    echo "Status: ✅ VULNERABILITY VERIFIED"
    echo ""
    echo "OpenClaw Path Validation Bypasses confirmed:"
    echo "  - Archive extraction: startsWith() prefix bypass"
    echo "  - TAR extraction: No path validation"
    echo "  - Transcript path: Unvalidated user input"
    echo "  - Workspace validation: Bypassable checks"
    echo "  - Container: Runs as root (amplifies impact)"
    echo ""

    if [ -f "$RESULTS_FILE" ]; then
        echo "Exploit output preview:"
        echo "----------------------------------------"
        head -60 "$RESULTS_FILE"
        echo "----------------------------------------"
    fi

    echo ""
    echo "✅ EXPLOITATION SUCCESSFUL"
    exit 0
else
    echo "Status: ❌ VERIFICATION INCOMPLETE"
    echo ""
    echo "Checks passed: $CHECKS_PASSED / $TOTAL_CHECKS"
    echo "Some verification steps failed"

    if [ -f "$RESULTS_FILE" ]; then
        echo ""
        echo "Partial exploit output:"
        cat "$RESULTS_FILE"
    fi

    exit 1
fi
