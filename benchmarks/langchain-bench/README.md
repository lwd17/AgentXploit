# LangChain Security Benchmark

Security testing framework for LangChain vulnerabilities. This benchmark provides containerized environments for testing and exploiting known CVEs in LangChain.

## Overview

This benchmark includes:
- **Runtimes**: Vulnerable LangChain versions in Docker containers
- **Tasks**: Specific CVE exploitation scenarios
- **Attack Scripts**: Attacker containers with tools for exploitation

## Structure

```
langchain-bench/
├── runtimes/           # Vulnerable LangChain runtime environments
│   └── langchain-0.0.141/
│       ├── Dockerfile
│       ├── entrypoint.sh
│       └── docker-compose.yml
├── tasks/              # Specific vulnerability exploitation tasks
│   └── task-cve-2023-29374-llmmath-rce/
│       ├── task_config.json
│       ├── start.sh
│       ├── run_agent.sh
│       ├── verify.sh
│       ├── README.md
│       └── HOWTO.md
└── README.md
```

## Vulnerabilities Covered

### CVE-2023-29374 - LLMMathChain Arbitrary Code Execution

- **Severity**: CRITICAL
- **Affected Versions**: langchain < 0.0.142
- **Type**: Arbitrary Code Execution
- **Description**: LLMMathChain uses numexpr.evaluate() which can execute arbitrary Python code
- **Task**: `task-cve-2023-29374-llmmath-rce`

## Quick Start

### Running a Task

1. **Navigate to runtime directory:**
   ```bash
   cd runtimes/langchain-0.0.141
   ```

2. **Set task ID and start containers:**
   ```bash
   export TASK_ID=cve-2023-29374-llmmath-rce
   docker compose up -d
   ```

3. **Setup target service:**
   ```bash
   cd ../../tasks/task-cve-2023-29374-llmmath-rce
   docker cp start.sh langchain-security-test-${TASK_ID}:/workspace/
   docker exec -d langchain-security-test-${TASK_ID} bash /workspace/start.sh
   ```

4. **Run exploit:**
   ```bash
   docker cp run_agent.sh langchain-attacker-${TASK_ID}:/workspace/
   docker exec langchain-attacker-${TASK_ID} bash /workspace/run_agent.sh
   ```

5. **Verify results:**
   ```bash
   docker cp verify.sh langchain-attacker-${TASK_ID}:/workspace/
   docker exec langchain-attacker-${TASK_ID} bash /workspace/verify.sh
   ```

## Task Configuration Format

Each task includes:
- `task_config.json` - Task metadata and configuration
- `start.sh` - Target service initialization
- `run_agent.sh` - Ground truth exploit implementation
- `verify.sh` - Verification script to confirm exploitation
- `README.md` - Vulnerability details and documentation
- `HOWTO.md` - Step-by-step exploitation guide

## Environment Architecture

Each task creates two containers:

1. **Target Container** (`langchain-security-test-*`)
   - Runs vulnerable LangChain application
   - Exposes HTTP API for exploitation
   - Contains source code at `/app/langchain-source`

2. **Attacker Container** (`langchain-attacker-*`)
   - Tools for exploitation (curl, jq, Python)
   - Read-only access to target source code
   - Workspace at `/workspace` for scripts and results

## Network Configuration

Containers communicate via Docker Compose network `exploit_net`:
- Target accessible from attacker via hostname (e.g., `langchain-security-test-cve-2023-29374-llmmath-rce`)
- Default target port: 8080

## Development Guide

### Adding a New CVE

1. **Create runtime directory:**
   ```bash
   mkdir -p runtimes/langchain-X.X.X
   ```

2. **Create Dockerfile, entrypoint.sh, docker-compose.yml**

3. **Create attacker image:**
   ```bash
   mkdir -p ../../attack-scripts/langchain-X.X.X
   ```

4. **Create task directory:**
   ```bash
   mkdir -p tasks/task-cve-YYYY-XXXXX-description
   ```

5. **Implement required files:**
   - task_config.json
   - start.sh
   - run_agent.sh
   - verify.sh
   - README.md
   - HOWTO.md

### Testing Your CVE

```bash
# Build and start containers
cd runtimes/langchain-X.X.X
export TASK_ID=your-task-id
docker compose up -d --build

# Check containers
docker ps | grep your-task-id

# Test the exploit
cd ../../tasks/task-your-cve
bash run_agent.sh

# Verify
bash verify.sh

# Cleanup
cd ../../runtimes/langchain-X.X.X
docker compose down -v
```

## Cleanup

Stop and remove all containers:
```bash
cd runtimes/langchain-0.0.141
docker compose down -v
```

Remove all images:
```bash
docker images | grep langchain | awk '{print $3}' | xargs docker rmi -f
```

## Security Notice

⚠️ **WARNING**: This benchmark contains real vulnerabilities and exploits. Only use in isolated, controlled environments for security research and testing purposes.

- Run in isolated networks (Docker networks)
- Never expose containers to public networks
- Clean up containers after testing
- Do not use against production systems

## Contributing

When adding new CVEs:
1. Follow the existing structure and naming conventions
2. Include comprehensive documentation
3. Test thoroughly in isolated environment
4. Ensure verification script is reliable

## References

- LangChain Repository: https://github.com/langchain-ai/langchain
- LangChain Security Advisories: https://github.com/langchain-ai/langchain/security/advisories
- CVE Database: https://nvd.nist.gov/

## License

This benchmark is for security research and educational purposes only.
