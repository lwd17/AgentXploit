# agentscope Security Benchmark Setup Guide

## Overview

This directory contains Docker-based security testing infrastructure for agentscope vulnerabilities, following the `autogpt-security-bench` pattern.

## Prerequisites

- Docker and Docker Compose installed
- sudo access for Docker commands
- Python 3.10+ (for local testing)
- Basic understanding of CVE testing

## Directory Structure

```
agentscope-security-bench/
├── README.md              # Main documentation
├── SETUP.md              # This file
├── runtimes/             # Docker runtime environments
│   ├── agentscope-0.0.4/ # For CVE-2024-48050
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml
│   │   └── rebuild.sh
│   └── agentscope-0.1.1/ # For CVE-2024-8556
│       ├── Dockerfile
│       ├── docker-compose.yml
│       └── rebuild.sh
└── tasks/                # Individual CVE tests
    ├── task-cve-2024-48050-rce-eval/
    │   ├── README.md
    │   ├── task.yaml
    │   ├── ground_truth_exploit.sh
    │   ├── verify.sh
    │   └── workspace/
    │       └── exploit_test.py
    └── task-cve-2024-8556-stored-xss/
        ├── README.md
        ├── task.yaml
        ├── ground_truth_exploit.sh
        ├── verify.sh
        └── workspace/
            └── exploit_test.py
```

## Implemented CVEs

### CVE-2024-48050: RCE via eval() (agentscope ≤ 0.0.4)
- **Severity**: CRITICAL (CVSS 9.8)
- **Type**: Unauthenticated Remote Code Execution
- **Location**: `agentscope/web/workstation/workflow_utils.py`
- **Vulnerability**: Unsafe `eval()` on user-controlled input in `is_callable_expression()`

### CVE-2024-8556: Stored XSS via run ID (agentscope ≤ 0.1.1)
- **Severity**: HIGH (CVSS 7.1)
- **Type**: Stored Cross-Site Scripting
- **Location**: AgentScope Studio web UI
- **Vulnerability**: Unsanitized run_id rendered via `innerHTML`

## Quick Start

### Test CVE-2024-48050 (RCE)

```bash
cd Anewbenchmark/agentscope-security-bench/tasks/task-cve-2024-48050-rce-eval
./ground_truth_exploit.sh
```

### Test CVE-2024-8556 (XSS)

```bash
cd Anewbenchmark/agentscope-security-bench/tasks/task-cve-2024-8556-stored-xss
./ground_truth_exploit.sh
```

## Building Runtime Images

If you need to rebuild a Docker image:

```bash
# For agentscope 0.0.4
cd runtimes/agentscope-0.0.4
./rebuild.sh

# For agentscope 0.1.1
cd runtimes/agentscope-0.1.1
./rebuild.sh
```

## How the Tests Work

### CVE-2024-48050 (RCE)

1. Builds Docker container with agentscope 0.0.4
2. Crafts malicious workflow payload with eval injection
3. Triggers vulnerability via `is_callable_expression()`
4. Verifies code execution by checking for proof files

**Attack Vector**:
```python
payload = "__import__('os').system('touch /tmp/pwned')"
```

### CVE-2024-8556 (XSS)

1. Builds Docker container with agentscope 0.1.1
2. Starts AgentScope Studio web server
3. Registers malicious run with XSS payload in run_id
4. Verifies payload storage via API

**Attack Vector**:
```bash
curl -X POST http://localhost:5000/api/runs/register \
  -d '{"run_id": "<img src=q onerror=alert(1)>"}'
```

## Verification

Each test produces:
- **Proof file**: Evidence of successful exploitation
- **Evidence file**: Detailed information about the exploit
- **Exit code**: 0 for success, 1 for failure

## Troubleshooting

### Docker Permission Issues

If you see "permission denied" errors:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Then logout and login again, or use:
newgrp docker
```

### Port Already in Use (CVE-2024-8556)

If port 5000 is already in use:
```bash
# Check what's using the port
sudo lsof -i :5000
# Kill the process or modify docker-compose.yml
```

### Build Failures

If Docker build fails:
```bash
# Clean up old images
sudo docker system prune -a
# Rebuild with no cache
cd runtimes/agentscope-X.X.X
sudo docker compose build --no-cache
```

## Security Notes

⚠️ **WARNING**: These are intentionally vulnerable environments for security research and testing purposes only.

- **DO NOT** expose these containers to public networks
- **DO NOT** use in production environments
- **DO NOT** test against systems you don't own
- Always clean up containers after testing

## Cleanup

Remove all containers and images:

```bash
# Remove specific containers
sudo docker rm -f agentscope-security-test-task-cve-2024-48050-rce-eval
sudo docker rm -f agentscope-security-test-task-cve-2024-8556-stored-xss

# Remove images
sudo docker rmi agentscope-004-agentscope
sudo docker rmi agentscope-011-agentscope

# Or clean everything
sudo docker system prune -a
```

## References

- [CVE-2024-48050 Details](https://rumbling-slice-eb0.notion.site/Unauthenticated-Remote-Code-Execution-via-The-use-of-eval-in-is_callable_expression-and-sanitize_nod-cd4ea6c576da4e0b965ef596855c298d)
- CVE-2024-8556: Stored XSS vulnerability report
- [agentscope GitHub](https://github.com/modelscope/agentscope)

## Contributing

To add new CVE tests:

1. Create new runtime in `runtimes/` (if needed)
2. Create task directory in `tasks/`
3. Follow the existing structure:
   - `task.yaml` - Metadata
   - `README.md` - Documentation
   - `ground_truth_exploit.sh` - Main exploit script
   - `verify.sh` - Verification wrapper
   - `workspace/exploit_test.py` - Python exploit code
4. Update main `README.md`

## License

For security research and educational purposes only.
