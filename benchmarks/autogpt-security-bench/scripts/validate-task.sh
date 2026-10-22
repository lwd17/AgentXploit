#!/bin/bash
# Validate task structure

TASK_DIR="$1"

if [ -z "$TASK_DIR" ]; then
    echo "Usage: $0 <task-directory>"
    echo ""
    echo "Example:"
    echo "  $0 ../tasks/task-prompt-injection-docker-write"
    exit 1
fi

if [ ! -d "$TASK_DIR" ]; then
    echo "Error: Directory not found: $TASK_DIR"
    exit 1
fi

ERRORS=0
WARNINGS=0

echo "=========================================="
echo "Validating task: $(basename "$TASK_DIR")"
echo "=========================================="
echo ""

# Check required files
echo "Checking required files..."

if [ ! -f "${TASK_DIR}/task.yaml" ]; then
    echo "[✗] Missing task.yaml"
    ERRORS=$((ERRORS + 1))
else
    echo "[✓] task.yaml exists"
fi

if [ ! -d "${TASK_DIR}/workspace" ]; then
    echo "[✗] Missing workspace directory"
    ERRORS=$((ERRORS + 1))
else
    echo "[✓] workspace directory exists"

    # Check if workspace has any files
    FILE_COUNT=$(find "${TASK_DIR}/workspace" -type f | wc -l)
    if [ "$FILE_COUNT" -eq 0 ]; then
        echo "[!] Warning: workspace directory is empty"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    - Contains ${FILE_COUNT} file(s)"
    fi
fi

if [ ! -f "${TASK_DIR}/verify.sh" ]; then
    echo "[✗] Missing verify.sh"
    ERRORS=$((ERRORS + 1))
else
    echo "[✓] verify.sh exists"

    if [ ! -x "${TASK_DIR}/verify.sh" ]; then
        echo "[!] Warning: verify.sh is not executable"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    - Is executable"
    fi
fi

if [ ! -f "${TASK_DIR}/README.md" ]; then
    echo "[!] Warning: Missing README.md"
    WARNINGS=$((WARNINGS + 1))
else
    echo "[✓] README.md exists"
fi

echo ""

# Validate task.yaml structure
if [ -f "${TASK_DIR}/task.yaml" ]; then
    echo "Validating task.yaml structure..."

    if ! grep -q "^id:" "${TASK_DIR}/task.yaml"; then
        echo "[✗] task.yaml missing 'id' field"
        ERRORS=$((ERRORS + 1))
    else
        TASK_ID=$(grep "^id:" "${TASK_DIR}/task.yaml" | awk '{print $2}')
        echo "[✓] id: ${TASK_ID}"
    fi

    if ! grep -q "^name:" "${TASK_DIR}/task.yaml"; then
        echo "[✗] task.yaml missing 'name' field"
        ERRORS=$((ERRORS + 1))
    else
        TASK_NAME=$(grep "^name:" "${TASK_DIR}/task.yaml" | cut -d':' -f2- | xargs)
        echo "[✓] name: ${TASK_NAME}"
    fi

    if ! grep -q "^runtime:" "${TASK_DIR}/task.yaml"; then
        echo "[✗] task.yaml missing 'runtime' field"
        ERRORS=$((ERRORS + 1))
    else
        echo "[✓] runtime field present"
    fi

    if ! grep -q "^vulnerability:" "${TASK_DIR}/task.yaml"; then
        echo "[✗] task.yaml missing 'vulnerability' field"
        ERRORS=$((ERRORS + 1))
    else
        echo "[✓] vulnerability field present"
    fi

    if ! grep -q "^verification:" "${TASK_DIR}/task.yaml"; then
        echo "[✗] task.yaml missing 'verification' field"
        ERRORS=$((ERRORS + 1))
    else
        echo "[✓] verification field present"
    fi

    if ! grep -q "^timeout:" "${TASK_DIR}/task.yaml"; then
        echo "[!] Warning: task.yaml missing 'timeout' field (will use default)"
        WARNINGS=$((WARNINGS + 1))
    else
        TIMEOUT=$(grep "^timeout:" "${TASK_DIR}/task.yaml" | awk '{print $2}')
        echo "[✓] timeout: ${TIMEOUT}s"
    fi
fi

echo ""

# Check for ai_settings.yaml in workspace
if [ -f "${TASK_DIR}/workspace/ai_settings.yaml" ]; then
    echo "[✓] workspace/ai_settings.yaml present"

    # Validate ai_settings.yaml structure
    if ! grep -q "^ai_name:" "${TASK_DIR}/workspace/ai_settings.yaml"; then
        echo "    [!] Warning: ai_settings.yaml missing 'ai_name' field"
        WARNINGS=$((WARNINGS + 1))
    fi

    if ! grep -q "^ai_role:" "${TASK_DIR}/workspace/ai_settings.yaml"; then
        echo "    [!] Warning: ai_settings.yaml missing 'ai_role' field"
        WARNINGS=$((WARNINGS + 1))
    fi

    if ! grep -q "^ai_goals:" "${TASK_DIR}/workspace/ai_settings.yaml"; then
        echo "    [!] Warning: ai_settings.yaml missing 'ai_goals' field"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "[!] Warning: workspace/ai_settings.yaml not found"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "=========================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "Task validation successful! ✓"
    echo "=========================================="
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "Task validation passed with ${WARNINGS} warning(s)"
    echo "=========================================="
    exit 0
else
    echo "Task validation failed:"
    echo "  Errors: ${ERRORS}"
    echo "  Warnings: ${WARNINGS}"
    echo "=========================================="
    exit 1
fi
