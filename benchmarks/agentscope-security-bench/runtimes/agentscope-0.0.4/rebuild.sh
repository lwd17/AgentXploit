#!/bin/bash
# Rebuild Docker image for agentscope 0.0.4

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Rebuilding agentscope 0.0.4 Docker image..."
sudo docker compose build --no-cache

echo "✓ Build complete"
