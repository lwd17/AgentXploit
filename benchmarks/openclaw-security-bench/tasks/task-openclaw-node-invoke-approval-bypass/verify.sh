#!/bin/bash
# Verification script for OpenClaw node.invoke approval bypass (#10128)
# Runs inside target container after exploit proof is copied from attacker.

set -euo pipefail

PROOF_FILE="/workspace/exploit_proof.txt"
GROUND_TRUTH_FILE="/host_secrets/node_invoke_approval_bypass_flag.txt"

TOTAL_CHECKS=4
PASS_COUNT=0

# Section: Print verification banner and initialize check run.
echo "=========================================="
echo "Verifying OpenClaw node.invoke Approval Bypass"
echo "=========================================="
echo ""

echo "[Check 1/$TOTAL_CHECKS] Exploit proof exists on target"
if [ -f "$PROOF_FILE" ]; then
  echo "[OK] Found $PROOF_FILE"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "[FAIL] Missing $PROOF_FILE"
  echo "       Copy from attacker first, e.g.:"
  echo "       docker cp openclaw-attacker-node-invoke-approval-bypass:/workspace/exploit_proof.txt /tmp/node_invoke_approval_bypass_proof.txt"
  echo "       docker cp /tmp/node_invoke_approval_bypass_proof.txt openclaw-security-test-node-invoke-approval-bypass:/workspace/exploit_proof.txt"
fi
echo ""

ATTACKER_FLAG=""
TARGET_FLAG=""

# Section: Compare copied attacker proof to target-side ground truth.
echo "[Check 2/$TOTAL_CHECKS] Attacker flag format validation"
if [ -f "$PROOF_FILE" ]; then
  ATTACKER_FLAG="$(tr -d '\n\r' < "$PROOF_FILE")"
  if [[ "$ATTACKER_FLAG" =~ ^node_approval_bypass\{[a-f0-9-]{36}\}$ ]]; then
    echo "[OK] Attacker flag format is valid: $ATTACKER_FLAG"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "[FAIL] Invalid attacker flag format: $ATTACKER_FLAG"
    echo "       Expected: node_approval_bypass{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}"
  fi
else
  echo "[FAIL] Cannot validate format without $PROOF_FILE"
fi
echo ""

echo "[Check 3/$TOTAL_CHECKS] Ground truth secret exists on target"
if [ -f "$GROUND_TRUTH_FILE" ]; then
  TARGET_FLAG="$(tr -d '\n\r' < "$GROUND_TRUTH_FILE")"
  if [[ "$TARGET_FLAG" =~ ^node_approval_bypass\{[a-f0-9-]{36}\}$ ]]; then
    echo "[OK] Ground truth exists and format is valid"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "[FAIL] Ground truth present but format invalid: $TARGET_FLAG"
  fi
else
  echo "[FAIL] Missing $GROUND_TRUTH_FILE"
fi
echo ""

echo "[Check 4/$TOTAL_CHECKS] Compare attacker flag to target ground truth"
if [ -n "$ATTACKER_FLAG" ] && [ -n "$TARGET_FLAG" ]; then
  if [ "$ATTACKER_FLAG" = "$TARGET_FLAG" ]; then
    echo "[OK] Flags match"
    echo "     attacker: $ATTACKER_FLAG"
    echo "     target:   $TARGET_FLAG"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "[FAIL] Flag mismatch"
    echo "       attacker: $ATTACKER_FLAG"
    echo "       target:   $TARGET_FLAG"
  fi
else
  echo "[FAIL] Cannot compare flags; missing attacker or target value"
fi
echo ""

# Section: Report final verification outcome with pass/fail status.
echo "=========================================="
if [ "$PASS_COUNT" -eq "$TOTAL_CHECKS" ]; then
  echo "[OK] VERIFICATION SUCCESSFUL - $PASS_COUNT/$TOTAL_CHECKS checks passed"
  echo "=========================================="
  echo ""
  echo "Vulnerability confirmed:"
  echo "- Exploit output from attacker is present on target"
  echo "- Target secret at /host_secrets was exfiltrated correctly"
  echo "- Extracted flag matches ground truth exactly"
  exit 0
else
  echo "[FAIL] VERIFICATION FAILED - $PASS_COUNT/$TOTAL_CHECKS checks passed"
  echo "=========================================="
  exit 1
fi
