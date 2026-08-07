#!/bin/bash
# Cleanup script for AutoGPT security benchmark

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "AutoGPT Security Benchmark - Cleanup"
echo "=========================================="
echo ""

# Stop and remove all benchmark containers
echo "Stopping containers..."
CONTAINERS=$(docker ps -a | grep "autogpt-security-test" | awk '{print $1}' || true)
if [ -n "$CONTAINERS" ]; then
    echo "$CONTAINERS" | xargs docker rm -f
    echo "Removed $(echo "$CONTAINERS" | wc -l) containers"
else
    echo "No benchmark containers found"
fi
echo ""

# Remove volumes
echo "Removing volumes..."
VOLUMES=$(docker volume ls | grep "autogpt-security" | awk '{print $2}' || true)
if [ -n "$VOLUMES" ]; then
    echo "$VOLUMES" | xargs docker volume rm
    echo "Removed $(echo "$VOLUMES" | wc -l) volumes"
else
    echo "No benchmark volumes found"
fi
echo ""

# Clean logs
echo "Cleaning logs..."
LOG_COUNT=0
for runtime_dir in "${REPO_ROOT}"/runtimes/*/; do
    if [ -d "${runtime_dir}logs" ]; then
        LOG_FILES=$(find "${runtime_dir}logs" -name "*.log" -type f 2>/dev/null || true)
        if [ -n "$LOG_FILES" ]; then
            echo "$LOG_FILES" | xargs rm -f
            LOG_COUNT=$((LOG_COUNT + $(echo "$LOG_FILES" | wc -l)))
        fi
    fi
done
echo "Removed ${LOG_COUNT} log files"
echo ""

# Restore backup files
echo "Restoring backup files..."
BACKUP_COUNT=0
find "${REPO_ROOT}/runtimes" -name "*.backup" -type f 2>/dev/null | while read backup; do
    original="${backup%.backup}"
    if [ -f "$backup" ]; then
        mv "$backup" "$original"
        echo "Restored: $(basename "$original")"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
done
echo "Restored ${BACKUP_COUNT} backup files"
echo ""

# Clean exploit proof files
echo "Cleaning exploit proof files..."
PROOF_COUNT=0
for task_dir in "${REPO_ROOT}"/tasks/*/workspace/; do
    if [ -f "${task_dir}EXPLOIT_PROOF.txt" ]; then
        rm -f "${task_dir}EXPLOIT_PROOF.txt"
        PROOF_COUNT=$((PROOF_COUNT + 1))
    fi
done

# Clean /tmp/pwned.txt if exists
if [ -f "/tmp/pwned.txt" ]; then
    rm -f "/tmp/pwned.txt"
    PROOF_COUNT=$((PROOF_COUNT + 1))
fi

echo "Removed ${PROOF_COUNT} exploit proof files"
echo ""

echo "=========================================="
echo "Cleanup complete!"
echo "=========================================="
