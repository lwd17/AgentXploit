#!/bin/bash
# Run Codex baseline on a single task (runs INSIDE the attacker container)
#
# Usage:
#   bash run_codex.sh
#
# Required environment variables:
#   OPENAI_API_KEY    - Your OpenAI/LiteLLM API key
#   OPENAI_BASE_URL   - API base URL (optional, for proxy/custom endpoint)
#   TASK_INSTRUCTION  - Full natural-language instruction for Codex (see run_baseline_codex.sh)
#
# Output:
#   /workspace/codex_output.json   - Full Codex execution log (JSON)
#   Any files written by Codex     - In /workspace/ as instructed

set -euo pipefail

CODEX_HOME="${CODEX_HOME:-/root/.codex}"
OUTPUT_FILE="${OUTPUT_FILE:-/workspace/codex_output.json}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "[✗] OPENAI_API_KEY is not set"
    exit 1
fi

if [ -z "${TASK_INSTRUCTION:-}" ]; then
    echo "[✗] TASK_INSTRUCTION is not set"
    exit 1
fi

# Load nvm so codex is available
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if ! command -v codex &>/dev/null; then
    echo "[✗] Codex not found. Run install_codex.sh first."
    exit 1
fi

echo "[*] Setting up Codex auth..."
mkdir -p /tmp/codex-secrets
cat >/tmp/codex-secrets/auth.json <<AUTHEOF
{
  "OPENAI_API_KEY": "${OPENAI_API_KEY}"
}
AUTHEOF
mkdir -p "$CODEX_HOME"
ln -sf /tmp/codex-secrets/auth.json "$CODEX_HOME/auth.json"

trap 'rm -rf /tmp/codex-secrets "$CODEX_HOME/auth.json"' EXIT TERM INT

echo "[*] Running Codex..."
codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    --skip-git-repo-check \
    --json \
    --enable unified_exec \
    -- \
    "$TASK_INSTRUCTION" \
    2>&1 </dev/null | tee "$OUTPUT_FILE"

echo "[*] Codex execution completed. Output: $OUTPUT_FILE"
