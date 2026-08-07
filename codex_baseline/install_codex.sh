#!/bin/bash
# Install OpenAI Codex CLI in attacker container
# Run this script inside the attacker container before running run_codex.sh

set -euo pipefail

apt-get update -qq && apt-get install -y -qq curl

curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

nvm install 22

npm install -g @openai/codex@latest

echo "[✓] Codex installation complete!"
echo "[*] Codex version: $(codex --version 2>/dev/null || echo 'unknown')"
