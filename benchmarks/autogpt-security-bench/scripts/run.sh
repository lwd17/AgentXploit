#!/bin/bash
# Main runner script for AutoGPT security benchmark

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
VERIFY_ONLY=false
CLEANUP=false
VERBOSE=false

# Function to display usage
usage() {
    cat << EOF
AutoGPT Security Benchmark Runner

Usage: $0 <task-id> <runtime-version> [options]

Arguments:
    task-id          Task identifier (e.g., task-prompt-injection-docker-write)
    runtime-version  Runtime version (e.g., autogpt-0.4.2)

Options:
    --verify         Run verification only (don't execute task)
    --cleanup        Clean up containers and volumes after run
    --verbose        Enable verbose output
    -h, --help       Display this help message

Examples:
    $0 task-prompt-injection-docker-write autogpt-0.4.2
    $0 task-prompt-injection-docker-write autogpt-0.4.2 --verify
    $0 task-path-traversal-sandbox-escape autogpt-0.4.2 --cleanup

Available Tasks:
$(ls -1 "$(dirname "$0")/../tasks/" 2>/dev/null | grep "^task-" | sed 's/^/    /' || echo "    (none found)")

Available Runtimes:
$(ls -1 "$(dirname "$0")/../runtimes/" 2>/dev/null | sed 's/^/    /' || echo "    (none found)")

EOF
}

# Parse arguments
if [ $# -lt 2 ]; then
    usage
    exit 1
fi

TASK_ID="$1"
RUNTIME_VERSION="$2"
shift 2

# Parse options
while [ $# -gt 0 ]; do
    case "$1" in
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            set -x
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Get script directory and repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TASK_DIR="${REPO_ROOT}/tasks/${TASK_ID}"
RUNTIME_DIR="${REPO_ROOT}/runtimes/${RUNTIME_VERSION}"

# Validate task exists
if [ ! -d "$TASK_DIR" ]; then
    echo -e "${RED}Error: Task '${TASK_ID}' not found${NC}"
    echo "Available tasks:"
    ls -1 "${REPO_ROOT}/tasks/" 2>/dev/null | grep "^task-" | sed 's/^/  /' || echo "  (none found)"
    exit 1
fi

# Validate runtime exists
if [ ! -d "$RUNTIME_DIR" ]; then
    echo -e "${RED}Error: Runtime '${RUNTIME_VERSION}' not found${NC}"
    echo "Available runtimes:"
    ls -1 "${REPO_ROOT}/runtimes/" 2>/dev/null | sed 's/^/  /' || echo "  (none found)"
    exit 1
fi

# Load task configuration
TASK_YAML="${TASK_DIR}/task.yaml"
TASK_WORKSPACE="${TASK_DIR}/workspace"
VERIFY_SCRIPT="${TASK_DIR}/verify.sh"

if [ ! -f "$TASK_YAML" ]; then
    echo -e "${RED}Error: task.yaml not found in ${TASK_DIR}${NC}"
    exit 1
fi

# If verify only, run verification and exit
if [ "$VERIFY_ONLY" = true ]; then
    echo -e "${YELLOW}Running verification for ${TASK_ID}...${NC}"
    cd "$TASK_DIR"
    if [ -x "$VERIFY_SCRIPT" ]; then
        bash "$VERIFY_SCRIPT"
        exit $?
    else
        echo -e "${RED}Error: verify.sh not found or not executable${NC}"
        exit 1
    fi
fi

# Prepare runtime environment
echo -e "${GREEN}=== AutoGPT Security Benchmark ===${NC}"
echo "Task: ${TASK_ID}"
echo "Runtime: ${RUNTIME_VERSION}"
echo "Task Directory: ${TASK_DIR}"
echo "Runtime Directory: ${RUNTIME_DIR}"
echo ""

# Check if .env exists
if [ ! -f "${RUNTIME_DIR}/.env" ]; then
    echo -e "${RED}Error: .env file not found in ${RUNTIME_DIR}${NC}"
    echo "Please copy .env.template to .env and configure it:"
    echo "  cd ${RUNTIME_DIR}"
    echo "  cp .env.template .env"
    echo "  # Edit .env with your OPENAI_API_KEY and AUTOGPT_SOURCE_PATH"
    exit 1
fi

# Backup docker-compose.yml (for exploit verification)
if [ -f "${RUNTIME_DIR}/docker-compose.yml" ]; then
    cp "${RUNTIME_DIR}/docker-compose.yml" "${RUNTIME_DIR}/docker-compose.yml.backup"
fi

# Set environment variables for this run
export TASK_ID="${TASK_ID}"
export TASK_WORKSPACE_PATH="${TASK_WORKSPACE}"

# Load AUTOGPT_SOURCE_PATH from .env
set -a  # Automatically export all variables
source "${RUNTIME_DIR}/.env"
set +a

if [ -z "$AUTOGPT_SOURCE_PATH" ] || [ ! -d "$AUTOGPT_SOURCE_PATH" ]; then
    echo -e "${RED}Error: AUTOGPT_SOURCE_PATH not set or invalid${NC}"
    echo "Current value: ${AUTOGPT_SOURCE_PATH:-<not set>}"
    echo ""
    echo "Please set AUTOGPT_SOURCE_PATH in ${RUNTIME_DIR}/.env"
    echo "Example:"
    echo "  AUTOGPT_SOURCE_PATH=/tmp/AutoGPT-0.4.2"
    echo ""
    echo "To clone AutoGPT source:"
    echo "  git clone -b v0.4.2 https://github.com/Significant-Gravitas/Auto-GPT /tmp/AutoGPT-0.4.2"
    exit 1
fi

# Create logs directory
mkdir -p "${RUNTIME_DIR}/logs"

# Build Docker image if needed
echo -e "${YELLOW}Building Docker image...${NC}"
cd "$RUNTIME_DIR"
if ! docker compose build; then
    echo -e "${RED}Error: Docker build failed${NC}"
    exit 1
fi

# Copy task-specific ai_settings.yaml if exists
if [ -f "${TASK_WORKSPACE}/ai_settings.yaml" ]; then
    echo "Copying task-specific ai_settings.yaml..."
    cp "${TASK_WORKSPACE}/ai_settings.yaml" "${AUTOGPT_SOURCE_PATH}/ai_settings.yaml"
fi

# Run AutoGPT with task-specific configuration
echo -e "${YELLOW}Starting AutoGPT...${NC}"
echo "Container: autogpt-security-test-${TASK_ID}"
echo "Workspace: ${TASK_WORKSPACE}"
echo ""
echo "Press Ctrl+C to stop execution"
echo ""

# Read timeout from task.yaml (default 300 seconds)
TIMEOUT=$(grep "^timeout:" "$TASK_YAML" 2>/dev/null | awk '{print $2}' || echo "300")

# Run container with timeout
echo "Running with ${TIMEOUT}s timeout..."
timeout "${TIMEOUT}s" docker compose run --rm \
    --name "autogpt-security-test-${TASK_ID}" \
    -e TASK_ID="${TASK_ID}" \
    -e TASK_WORKSPACE_PATH="${TASK_WORKSPACE_PATH}" \
    autogpt \
    --continuous \
    --skip-reprompt \
    --ai-settings /app/autogpt-source/ai_settings.yaml \
    2>&1 | tee "${RUNTIME_DIR}/logs/${TASK_ID}.log" || true

echo ""
echo -e "${YELLOW}AutoGPT execution completed${NC}"
echo ""

# Run verification
echo -e "${YELLOW}Running verification...${NC}"
cd "$TASK_DIR"
VERIFY_EXIT=0
if [ -x "$VERIFY_SCRIPT" ]; then
    bash "$VERIFY_SCRIPT" || VERIFY_EXIT=$?
else
    echo -e "${RED}Warning: verify.sh not found or not executable${NC}"
    VERIFY_EXIT=2
fi

# Cleanup if requested
if [ "$CLEANUP" = true ]; then
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    cd "$RUNTIME_DIR"
    docker compose down -v 2>/dev/null || true

    # Restore docker-compose.yml backup
    if [ -f "${RUNTIME_DIR}/docker-compose.yml.backup" ]; then
        mv "${RUNTIME_DIR}/docker-compose.yml.backup" "${RUNTIME_DIR}/docker-compose.yml"
    fi

    echo "Cleanup complete"
fi

exit $VERIFY_EXIT
