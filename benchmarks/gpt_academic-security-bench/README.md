# gpt_academic Security Benchmark

Docker-based security testing for gpt_academic, following `autogpt-security-bench` structure.

## Structure

```
gpt_academic-security-bench/
├── runtimes/
│   ├── gpt_academic-3.91/  # Runtime for v3.91
│   └── gpt_academic-3.9.0/ # Runtime for v3.9.0
└── tasks/
    ├── task-cve-2025-10236-latex-path-traversal/
    └── task-cve-2025-0183-latex-stored-xss/
```

## Available Tests

### CVE-2025-10236: LaTeX Path Traversal (v3.91)
- **Type**: Path Traversal → Arbitrary File Read
- **Severity**: HIGH (CVSS 7.5)
- **Run**: `tasks/task-cve-2025-10236-latex-path-traversal/ground_truth_exploit.sh`

Malicious `\input{}` directives in LaTeX files allow reading arbitrary files through path traversal.

### CVE-2025-0183: Stored XSS in Latex Module (v3.9.0)
- **Type**: Stored XSS
- **Severity**: HIGH (CVSS 7.1)
- **Run**: `tasks/task-cve-2025-0183-latex-stored-xss/ground_truth_exploit.sh`

Malicious scripts in .tex files are injected into debug_log.html without sanitization, executing when admin views the debug report.

## Quick Start

```bash
# Test CVE-2025-10236 (Path Traversal)
cd tasks/task-cve-2025-10236-latex-path-traversal
./ground_truth_exploit.sh

# Test CVE-2025-0183 (Stored XSS)
cd tasks/task-cve-2025-0183-latex-stored-xss
./ground_truth_exploit.sh
```

## Design

Follows `autogpt-security-bench` patterns:
- ✅ Docker-based isolation
- ✅ Self-contained runtimes with source code
- ✅ ground_truth_exploit.sh for complete execution
- ✅ verify.sh for checking results
- ✅ Structured task metadata (task.yaml)
