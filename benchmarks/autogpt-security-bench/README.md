# AutoGPT Security Benchmark Suite

Automated security testing benchmark for AutoGPT, focusing on prompt injection, sandbox escape, and output manipulation vulnerabilities.

## Overview

This benchmark suite provides reproducible security tests for AutoGPT agents. Each task tests a specific vulnerability with automated verification of exploit success.

## Quick Start

```bash
# 1. Setup runtime environment
cd runtimes/autogpt-0.4.2
cp .env.template .env
# Edit .env with your OPENAI_API_KEY and AUTOGPT_SOURCE_PATH

# 2. Clone AutoGPT source
git clone -b v0.4.2 https://github.com/Significant-Gravitas/Auto-GPT /tmp/AutoGPT-0.4.2

# 3. Build Docker image
docker-compose build

# 4. Run a task
cd ../..
./scripts/run.sh task-prompt-injection-docker-write autogpt-0.4.2

# 5. Verify results
./scripts/run.sh task-prompt-injection-docker-write autogpt-0.4.2 --verify
```

## Structure

- `runtimes/` - AutoGPT runtime environments (version-specific Docker configurations)
- `tasks/` - Individual security test cases with exploit payloads
- `scripts/` - Utility scripts for running and managing tests
- `docs/` - Detailed documentation

## Available Tasks

| Task ID | Vulnerability | Severity |
|---------|--------------|----------|
| task-prompt-injection-docker-write | Prompt injection leading to container escape | CRITICAL |
| task-path-traversal-sandbox-escape | Path traversal for arbitrary code execution | HIGH |
| task-ansi-injection-output-manipulation | ANSI escape sequence injection | MEDIUM |

## Requirements

- Docker 20.10+
- docker-compose 1.29+
- Bash 4.0+
- OpenAI API key
- AutoGPT source code (cloned separately)

## Documentation

- [Usage Guide](docs/USAGE.md) - Detailed setup and usage instructions
- [Creating Tasks](docs/CREATING_TASKS.md) - How to add new security tests
- [Architecture](docs/ARCHITECTURE.md) - System design and structure
- [Vulnerabilities](docs/VULNERABILITIES.md) - CVE details and mitigation

## Running Tests

### Run Single Task

```bash
./scripts/run.sh <task-id> <runtime-version>
```

### Run with Cleanup

```bash
./scripts/run.sh <task-id> <runtime-version> --cleanup
```

### Verify Only

```bash
./scripts/run.sh <task-id> <runtime-version> --verify
```

### List Available Tasks

```bash
ls tasks/
```

## Verification Exit Codes

- **0**: Exploit successful (vulnerability confirmed)
- **1**: Exploit failed (system protected)
- **2**: Verification error

## Security Notice

This benchmark contains real exploit payloads for security testing purposes. All tests are designed to run in isolated Docker containers. Do not run these tests against production systems.

## License

See LICENSE file for details.

## Contributing

Contributions welcome! See docs/CREATING_TASKS.md for guidelines on adding new security tests.
