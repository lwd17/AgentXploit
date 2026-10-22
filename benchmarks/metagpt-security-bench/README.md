# MetaGPT Security Benchmark

Security vulnerability testing suite for MetaGPT agent framework.

## Overview

This benchmark contains proof-of-concept exploits for known CVEs in MetaGPT, designed to test security vulnerability detection and mitigation capabilities.

## Structure

```
metagpt-security-bench/
├── runtimes/               # Docker environments for different MetaGPT versions
│   └── metagpt-0.6.4/     # MetaGPT 0.6.4 runtime
│       └── Dockerfile
├── tasks/                  # Individual CVE test cases
│   └── task-cve-2024-23750-rce-runcode/
│       ├── README.md       # Detailed vulnerability documentation
│       ├── task.yaml       # Task metadata
│       ├── workspace/
│       │   └── exploit_test.py
│       └── ground_truth_exploit.sh
└── README.md              # This file
```

## Implemented CVEs

### CVE-2024-23750: Arbitrary Code Execution in RunCode
- **Severity**: Critical
- **Type**: Remote Code Execution / Command Injection
- **Affected**: MetaGPT ≤ 0.6.4
- **Description**: Shell metacharacter injection in `RunCode.run_script()` via `QaEngineer` role
- **Status**: ✅ Implemented

## Requirements

- Docker
- Python 3.9+
- Valid OpenAI API key (for full exploitation)
- sudo access (for Docker commands)

## Usage

### Running Individual Tests

```bash
# Navigate to specific CVE task
cd tasks/task-cve-2024-23750-rce-runcode/

# Run the exploit
./ground_truth_exploit.sh
```

### With API Key

For full exploitation requiring LLM interaction:

```bash
export OPENAI_API_KEY="sk-your-key-here"
./ground_truth_exploit.sh
```

### Expected Output

Successful exploitation will:
1. Execute arbitrary shell commands
2. Create proof files (e.g., `/tmp/pwned`)
3. Generate evidence documents
4. Return exit code 0

## Security Notes

⚠️ **WARNING**: These exploits demonstrate real vulnerabilities.

- Only use in isolated testing environments
- Do not run against production systems
- Ensure proper containment (Docker isolation)
- Some exploits may require API keys (costs may apply)

## Testing Guidelines

1. **Isolation**: Always run in Docker containers
2. **API Keys**: Use test/development API keys only
3. **Costs**: Be aware of API call costs for LLM-based exploits
4. **Cleanup**: Scripts include automatic cleanup on exit
5. **Logs**: Review logs for detailed exploitation evidence

## Development

### Adding New CVE Tests

1. Create task directory:
   ```bash
   mkdir -p tasks/task-cve-YYYY-NNNNN-description/workspace
   ```

2. Create required files:
   - `README.md` - Vulnerability documentation
   - `task.yaml` - Task metadata
   - `workspace/exploit_test.py` - Python exploit
   - `ground_truth_exploit.sh` - Bash test runner

3. Add runtime if needed:
   ```bash
   mkdir -p runtimes/metagpt-X.Y.Z
   # Add Dockerfile
   ```

4. Update this README with new CVE entry

### File Templates

See existing tasks for templates and conventions.

## References

- **MetaGPT**: https://github.com/geekan/MetaGPT
- **CVE Database**: https://nvd.nist.gov/
- **Security Issues**: https://github.com/geekan/MetaGPT/issues

## License

This security benchmark is provided for research and testing purposes only.

## Contributors

Created for security research and vulnerability testing.

## Changelog

- **2024-01**: Initial implementation with CVE-2024-23750
