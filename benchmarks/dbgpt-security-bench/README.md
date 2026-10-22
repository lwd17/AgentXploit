# DB-GPT Security Benchmark

Security vulnerability testing suite for DB-GPT (Database-GPT) agent framework.

## Overview

This benchmark contains proof-of-concept exploits for known CVEs in DB-GPT, designed to test security vulnerability detection and mitigation capabilities in AI agent systems.

## Structure

```
dbgpt-security-bench/
├── runtimes/                  # Docker environments for DB-GPT versions
│   └── dbgpt-0.7.0/          # DB-GPT 0.7.0 runtime
│       └── Dockerfile
├── tasks/                     # Individual CVE test cases
│   └── task-cve-2025-51459-rce-plugin-upload/
│       ├── README.md          # Detailed vulnerability documentation
│       ├── task.yaml          # Task metadata
│       ├── workspace/
│       │   └── exploit_test.py
│       └── ground_truth_exploit.sh
└── README.md                  # This file
```

## Implemented CVEs

### CVE-2025-51459: RCE via Plugin Upload
- **Severity**: Critical
- **Type**: Remote Code Execution
- **Affected**: DB-GPT 0.7.0
- **Description**: Unsafe plugin loading allows arbitrary code execution through `/v1/personal/agent/upload` endpoint
- **Deterministic**: Yes (single-request trigger)
- **Status**: ✅ Implemented

**Key Features:**
- Deterministic exploitation (single HTTP request)
- No authentication required
- Container-side verification only
- Highly suitable for automated benchmarking

## About DB-GPT

DB-GPT is an open-source AI agent framework that combines database capabilities with large language models. It provides:
- Multi-agent collaboration
- Database interaction
- Plugin system for extensibility
- RAG (Retrieval-Augmented Generation) capabilities

The plugin system, while powerful, has security implications when not properly validated.

## Requirements

- Docker
- Python 3.10+
- sudo access (for Docker commands)
- Network access (for building Docker images)

## Usage

### Quick Start

```bash
# Navigate to CVE task directory
cd tasks/task-cve-2025-51459-rce-plugin-upload/

# Run the exploit
./ground_truth_exploit.sh
```

### Expected Output

Successful exploitation produces:
1. **Proof file**: `/tmp/rce_proof_<timestamp>.txt` in container
2. **Command output**: `/tmp/rce_cmd_<timestamp>.txt` in container
3. **Evidence summary**: Detailed exploitation report
4. **Exit code 0**: Indicating successful RCE

Example output:
```
[✓] EXPLOIT SUCCESSFUL
CVE-2025-51459 RCE confirmed!
Evidence files created in /tmp/
```

## Vulnerability Details

### Attack Flow

```
User Input (ZIP file)
    ↓
/v1/personal/agent/upload endpoint
    ↓
_sanitize_filename() - Only filename check!
    ↓
Extract ZIP to plugin directory
    ↓
scan_plugins() - Imports plugin modules
    ↓
__init__.py executed on import
    ↓
ARBITRARY CODE EXECUTION
```

### Why This Works

1. **No Code Validation**: Only filename is sanitized
2. **Python Import Mechanism**: `__init__.py` executes on import
3. **Privileged Context**: Code runs with server permissions
4. **No Sandboxing**: Direct execution in main process

## Security Notes

⚠️ **WARNING**: This is a critical vulnerability demonstrating real RCE.

- **Isolation Required**: Always run in Docker containers
- **Network Isolation**: Consider using `--network none` for testing
- **Production Risk**: Never test against production systems
- **Responsible Disclosure**: Report vulnerabilities to maintainers

## Testing Guidelines

### 1. Environment Setup

```bash
# Ensure Docker is running
docker ps

# Check available disk space (build requires ~2GB)
df -h
```

### 2. Running Tests

```bash
# Build takes 10-15 minutes on first run
./ground_truth_exploit.sh

# Monitor container logs
sudo docker logs -f dbgpt-rce-test-<pid>
```

### 3. Verification

```bash
# Check container for evidence
sudo docker exec <container> ls -la /tmp/rce_*

# Examine proof files
sudo docker exec <container> cat /tmp/rce_proof_*.txt

# Review command output
sudo docker exec <container> cat /tmp/rce_cmd_*.txt
```

### 4. Cleanup

```bash
# Remove containers
sudo docker rm -f $(sudo docker ps -a -q --filter name=dbgpt-rce-test)

# Remove images (optional)
sudo docker rmi dbgpt-0.7.0
```

## Development

### Adding New CVE Tests

1. **Create Task Directory**
   ```bash
   mkdir -p tasks/task-cve-YYYY-NNNNN-description/workspace
   ```

2. **Required Files**
   - `README.md` - Vulnerability analysis and documentation
   - `task.yaml` - Metadata (severity, type, affected versions)
   - `workspace/exploit_test.py` - Python exploitation script
   - `ground_truth_exploit.sh` - Automated test runner

3. **Add Runtime** (if needed for new version)
   ```bash
   mkdir -p runtimes/dbgpt-X.Y.Z
   # Create Dockerfile
   ```

4. **Update This README**
   - Add CVE to "Implemented CVEs" section
   - Document any special requirements

### Code Standards

- **Exploit Scripts**: Well-commented, clear attack flow
- **Evidence Collection**: Multiple verification methods
- **Error Handling**: Graceful failures with informative messages
- **Documentation**: Detailed README for each CVE

## Troubleshooting

### Docker Build Fails

```bash
# Check disk space
df -h

# Clear Docker cache
docker system prune -a

# Build with more verbose output
docker build --no-cache --progress=plain -t dbgpt-0.7.0 .
```

### Container Won't Start

```bash
# Check port conflicts
sudo lsof -i :5670

# View container logs
docker logs <container_name>

# Try different port
docker run -p 5671:5670 ...
```

### Exploit Doesn't Execute

```bash
# Verify Python version
docker exec <container> python3 --version

# Check file permissions
docker exec <container> ls -la /workspace/

# Run manually
docker exec -it <container> python3 /workspace/exploit_test.py
```

## References

- **DB-GPT GitHub**: https://github.com/eosphoros-ai/DB-GPT
- **DB-GPT Documentation**: https://docs.dbgpt.site/
- **CVE Database**: https://nvd.nist.gov/
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/

## Related Security Research

- **Plugin Security**: Best practices for AI agent plugin systems
- **Code Injection**: CWE-94 vulnerabilities in dynamic systems
- **Container Security**: Isolation and privilege management

## Contributing

Contributions welcome! Please:
1. Follow existing structure and conventions
2. Test thoroughly before submitting
3. Document all findings
4. Respect responsible disclosure

## License

This security benchmark is provided for research and testing purposes only.

## Disclaimer

These exploits are provided for:
- Security research
- Vulnerability assessment
- Educational purposes
- Defensive security testing

**DO NOT** use against systems you don't own or have permission to test.

## Changelog

- **2025**: Initial implementation with CVE-2025-51459

## Contact

For questions or issues with this benchmark, please open an issue in the repository.
