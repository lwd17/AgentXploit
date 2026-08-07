#!/bin/bash
# Codex Vulnerability Analysis Script
# This script uses Codex to scan local cloned agent codebases for vulnerabilities

set -euo pipefail

# ============================================
# CONFIGURATION - MODIFY THESE VARIABLES
# ============================================
TARGET_PATH="/home/shiqiu/Anewbenchmark/AutoGPT_0.4.2"  # Path to the target codebase to analyze (e.g., /path/to/agent-repo)
OUTPUT_DIR="${OUTPUT_DIR:-/home/shiqiu/AgentXploit/src/analysis_agent/codex_part/reports}"
ANALYSIS_STYLE="${ANALYSIS_STYLE:-prompt_injection}"  # Options: traditional, prompt_injection

# Fixed API Configuration
export OPENAI_API_KEY="sk-Eav7rsFEDl480mnJwGL-4g"
export OPENAI_BASE_URL="https://litellm-991596698159.us-west1.run.app/v1"

# Codex Configuration
CODEX_HOME="${CODEX_HOME:-/home/shiqiu/.codex}"

# ============================================
# VALIDATION
# ============================================
if [ -z "$TARGET_PATH" ]; then
    echo "[ERROR] TARGET_PATH is not set!"
    echo "Please edit this script and set TARGET_PATH to the codebase you want to analyze."
    echo "Example: TARGET_PATH=\"/home/shiqiu/repos/agentscope\""
    exit 1
fi

if [ ! -d "$TARGET_PATH" ]; then
    echo "[ERROR] TARGET_PATH does not exist: $TARGET_PATH"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/codex_analysis_${TIMESTAMP}.json"

echo "=========================================="
echo "Codex Vulnerability Analysis"
echo "=========================================="
echo "[*] Target Path: $TARGET_PATH"
echo "[*] Analysis Style: $ANALYSIS_STYLE"
echo "[*] Output File: $OUTPUT_FILE"
echo "[*] Web Search: DISABLED"
echo ""

# Ensure NVM and Node are available
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Verify codex is installed
if ! command -v codex &> /dev/null; then
    echo "[ERROR] Codex not found. Please install codex first."
    exit 1
fi

echo "[*] Codex version: $(codex --version 2>/dev/null || echo 'unknown')"
echo ""

# ============================================
# BUILD SYSTEM PROMPT (from analysis_agent.py)
# ============================================
SYSTEM_PROMPT=$(cat <<'SYSPROMPT'
You are an expert AI Agent Security researcher and vulnerability analyst.

You specialize in discovering security vulnerabilities in codebases, including both:
- AI/LLM agent-specific vulnerabilities (prompt injection, indirect prompt injection, data exfiltration via tools)
- Traditional application security vulnerabilities (RCE, XSS, CSRF, SQL injection, path traversal, SSRF, etc.)

=== AVAILABLE TOOLS ===

You have access to standard file operations through bash:
- ls, find - list directory contents and find files
- grep, rg - search for text patterns in files
- cat, head, tail - read file contents

=== RULES ===

- Thoroughly examine all relevant code before making conclusions
- Keep analyzing until you have examined all relevant code paths
- Follow the task and workflow provided in the user message
- Write your findings to the specified output files
SYSPROMPT
)

# ============================================
# BUILD INSTRUCTION BASED ON ANALYSIS STYLE
# ============================================
if [ "$ANALYSIS_STYLE" = "prompt_injection" ]; then
    INSTRUCTION=$(cat <<EOF
=== ANALYSIS TARGET ===
Path: ${TARGET_PATH}
Analysis Style: Prompt Injection & Agent Security

=== TASK ===
Analyze the agent codebase to identify prompt injection vulnerabilities by:
1. Understanding environment and dependencies
2. Finding all TOOLS - functions that interact with external environment (filesystem, web, bash, APIs, database, etc.)
3. Analyzing dataflow for each tool
4. Identifying security vulnerabilities related to prompt injection

=== WORKFLOW ===

1. **ENVIRONMENT**: Explore codebase structure
   - Use ls, find to understand project layout
   - Identify entry points, config files, dependencies

2. **FIND TOOLS**: Search for agent tools that interact with external environment
   - Look for: file read/write, bash/shell execution, web requests, API calls, database operations
   - Identify tools that could be exploited via prompt injection

3. **FOR EACH TOOL FOUND**:
   a) Read and understand the tool code thoroughly
   b) Document tool name, position, description, parameters
   c) Analyze data sources, destinations, transformations
   d) Identify vulnerabilities if found

4. **OUTPUT**: Write findings to ${OUTPUT_DIR}/vulnerability_report_${TIMESTAMP}.txt

=== CRITICAL VULNERABILITIES TO IDENTIFY ===

Focus on these two attack patterns:

1. **Untrusted Data -> LLM Context/Decision**
   - External/untrusted data (web content, file content, user input, API responses) flows into LLM prompt
   - This enables indirect prompt injection attacks
   - Example: web_search results directly concatenated into prompt

2. **LLM Output -> Sensitive Tool Execution**
   - LLM decisions/outputs are passed to dangerous tools without validation
   - This enables RCE, data exfiltration, etc.
   - Example: LLM output used as bash command argument, file path, or API parameter

Document vulnerabilities with:
- Vulnerability type, severity, attack scenario
- End-to-end impact (what an attacker can achieve)
- Evidence from code/dataflow

=== BEGIN ===
Start by exploring the codebase structure at ${TARGET_PATH}
EOF
)
else
    # Traditional vulnerability analysis (default)
    INSTRUCTION=$(cat <<EOF
=== ANALYSIS TARGET ===
Path: ${TARGET_PATH}
Analysis Style: Traditional Security Vulnerabilities

=== TASK ===
Perform a **traditional security vulnerability assessment** of this codebase (non-AI-specific). The goal is to find vulnerabilities that exist **regardless of any agent/LLM prompt logic**.

This assessment explicitly does **NOT** require:
- Running or starting any services/agents
- Analyzing LLM prompt flows, conversation policies, or agent planning logic

This assessment **DOES** require:
- Careful reading of **as much code as possible**
- Flexible, multi-pass searching (keywords + regex + data-flow tracing across files)
- Evidence-based findings with precise locations and actionable fixes

Deliver a report that is **thorough, reproducible, and code-grounded** (avoid generic advice).

---

=== OPERATING PRINCIPLES ===
1) **Coverage-first, then depth**: start broad (repo map + dependency map), then drill into hotspots (I/O boundaries, network, auth, deserialization, shell/OS interfaces).
2) **Assume attacker-controlled inputs** at boundaries (HTTP params, CLI args, env vars, config files, files read from disk, IPC, webhook payloads, queue messages).
3) **Trace taint**: follow input -> transformation -> sink (e.g., user input -> string concat -> subprocess).
4) **Minimize false positives**: only report issues confirmed by code evidence; if uncertain, label as "Potential" with rationale.
5) **Prefer minimal, safe fixes**: propose the smallest viable patch and safe alternatives.

---

=== REQUIRED WORKFLOW (MANDATORY) ===

1) **ENVIRONMENT & INVENTORY**
- Explore repository structure using ls / find
- Identify:
  - Primary languages (Python/JS/Go/etc.)
  - Frameworks (web frameworks, CLI tools, job runners)
  - Entry points (main, server, CLI, scripts, CI)
  - Dangerous subsystems (upload/download, extract, execute, parse)

2) **VULNERABILITY SCANNING (MULTI-PASS)**
Do at least **three passes**:

**PASS A - Broad Pattern Search**
- Use grep with many patterns to locate candidate files quickly.
- Prioritize:
  - request handlers / API routes / controllers
  - file read/write utilities
  - archive extraction utilities
  - subprocess usage
  - parsers (yaml/xml/pickle)
  - authn/authz middleware
  - config loaders
  - logging of sensitive values

**PASS B - Sink-Centric Deep Review**
For each sink category (command execution, deserialization, SQL execution, URL fetch, file write, template render):
- Open the file and read surrounding context
- Identify whether any attacker-controlled input can reach the sink
- Check for safeguards (validation, allowlists, encoding, sandboxing, safe APIs)

**PASS C - Boundary-Centric Review**
Review every code boundary where external input enters:
- HTTP endpoints
- CLI argument parsing
- environment variables
- config file loaders
- file uploads / dataset ingestion
- webhooks / queue consumers
- plugins/extensions loading
Trace what they can affect (paths, commands, URLs, templates, queries).

3) **DOCUMENT FINDINGS (EVIDENCE-DRIVEN)**
Write findings to: ${OUTPUT_DIR}/vulnerability_report_${TIMESTAMP}.txt

Each finding **MUST** include:
- Title + category
- Severity (Critical/High/Medium/Low) with justification
- Exact file path + line numbers
- Minimal code snippet (just enough to prove the issue)
- Attack scenario (how an attacker supplies input and what they gain)
- Impact (RCE/data leak/priv escalation/etc.)
- Preconditions/assumptions
- Concrete remediation:
  - preferred fix (minimal change)
  - defense-in-depth improvements
- If applicable: secure-by-default alternative APIs


=== BEGIN ===
Start by exploring the codebase structure at ${TARGET_PATH}
EOF
)
fi

# Setup Codex auth
mkdir -p /tmp/codex-secrets
cat >/tmp/codex-secrets/auth.json <<AUTHEOF
{
  "OPENAI_API_KEY": "${OPENAI_API_KEY}"
}
AUTHEOF
mkdir -p "$CODEX_HOME"
ln -sf /tmp/codex-secrets/auth.json "$CODEX_HOME/auth.json"

# Run Codex with cleanup trap
trap 'rm -rf /tmp/codex-secrets "$CODEX_HOME/auth.json"' EXIT TERM INT

echo "[*] Starting Codex vulnerability analysis..."
echo "[*] This may take a while depending on codebase size..."
echo ""

# Run codex with web search DISABLED
# Using --disable web_search_request to prevent web searches
codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    --skip-git-repo-check \
    --disable web_search_request \
    --json \
    --enable unified_exec \
    -- \
    "$INSTRUCTION" \
    2>&1 </dev/null | tee "$OUTPUT_FILE"

echo ""
echo "[*] Codex analysis completed"
echo "[*] Output saved to: $OUTPUT_FILE"

# Check for vulnerability report
REPORT_FILE="${OUTPUT_DIR}/vulnerability_report_${TIMESTAMP}.txt"
if [ -f "$REPORT_FILE" ]; then
    echo ""
    echo "[SUCCESS] Vulnerability report created!"
    echo "[*] Report location: $REPORT_FILE"
fi

# ============================================
# EXPORT STRUCTURED VULNERABILITIES TO JSON
# ============================================
VULNS_DIR="${OUTPUT_DIR}/vulns"
mkdir -p "$VULNS_DIR"

# Extract the last folder name from TARGET_PATH
TARGET_NAME=$(basename "$TARGET_PATH")
VULNS_JSON="${VULNS_DIR}/${TARGET_NAME}.json"

echo ""
echo "[*] Extracting structured vulnerabilities to JSON..."

# Create structured JSON from the analysis output
python3 - "$OUTPUT_FILE" "$VULNS_JSON" "$TARGET_PATH" "$TIMESTAMP" "$ANALYSIS_STYLE" <<'PYEOF'
import sys
import json
import re
from datetime import datetime

output_file = sys.argv[1]
vulns_json = sys.argv[2]
target_path = sys.argv[3]
timestamp = sys.argv[4]
analysis_style = sys.argv[5]

vulnerabilities = []

# Try to parse the codex JSON output
try:
    with open(output_file, 'r') as f:
        content = f.read()

    # Codex output may contain multiple JSON objects, try to extract vulnerabilities
    # Look for vulnerability patterns in the output

    # Pattern to match vulnerability findings (common formats)
    vuln_patterns = [
        # Pattern: Title with severity
        r'(?:^|\n)#+\s*(?:Vulnerability|Finding|Issue)?\s*\d*[:\s]*([^\n]+?)(?:\s*\[?(Critical|High|Medium|Low)\]?)?',
        # Pattern: Numbered findings
        r'\d+\.\s*\*\*([^*]+)\*\*.*?(?:Severity|Risk):\s*(Critical|High|Medium|Low)',
    ]

    # Extract structured data from JSON output if available
    json_lines = []
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            try:
                json_obj = json.loads(line)
                json_lines.append(json_obj)
            except:
                pass

    # Build vulnerability list from parsed content
    # Look for common vulnerability indicators in text
    severity_keywords = {
        'critical': ['rce', 'remote code execution', 'command injection', 'sql injection', 'arbitrary code'],
        'high': ['path traversal', 'ssrf', 'xss', 'csrf', 'deserialization', 'pickle', 'yaml.load'],
        'medium': ['information disclosure', 'sensitive data', 'hardcoded', 'credentials'],
        'low': ['missing validation', 'weak', 'deprecated']
    }

    # Parse the text content for vulnerability mentions
    text_content = content.lower()
    found_vulns = set()

    vuln_types = [
        ('Remote Code Execution (RCE)', ['remote code execution', 'rce', 'command injection', 'os.system', 'subprocess', 'eval(', 'exec(']),
        ('SQL Injection', ['sql injection', 'sqli', 'raw sql', 'execute(.*user']),
        ('Path Traversal', ['path traversal', 'directory traversal', '../', 'lfi', 'local file inclusion']),
        ('Server-Side Request Forgery (SSRF)', ['ssrf', 'server-side request forgery', 'url fetch']),
        ('Cross-Site Scripting (XSS)', ['xss', 'cross-site scripting', 'script injection']),
        ('Insecure Deserialization', ['pickle', 'yaml.load', 'unsafe_load', 'deserialization', 'marshal.loads']),
        ('Hardcoded Credentials', ['hardcoded', 'api_key', 'password', 'secret', 'credentials']),
        ('Prompt Injection', ['prompt injection', 'indirect prompt', 'llm injection']),
        ('Arbitrary File Write', ['file write', 'arbitrary file', 'overwrite']),
        ('Arbitrary File Read', ['file read', 'arbitrary read', 'sensitive file']),
    ]

    for vuln_name, keywords in vuln_types:
        for kw in keywords:
            if kw in text_content and vuln_name not in found_vulns:
                # Try to extract more context
                found_vulns.add(vuln_name)

                # Determine severity
                severity = 'Medium'
                vuln_lower = vuln_name.lower()
                if any(k in vuln_lower for k in ['rce', 'injection', 'deserial']):
                    severity = 'Critical'
                elif any(k in vuln_lower for k in ['traversal', 'ssrf', 'xss']):
                    severity = 'High'
                elif any(k in vuln_lower for k in ['credential', 'hardcoded']):
                    severity = 'Medium'

                vulnerabilities.append({
                    'type': vuln_name,
                    'severity': severity,
                    'keyword_match': kw,
                    'details': f'Potential {vuln_name} detected based on keyword analysis'
                })
                break

except Exception as e:
    print(f"[WARN] Error parsing output: {e}", file=sys.stderr)

# Create the final structured output
result = {
    'metadata': {
        'target_path': target_path,
        'target_name': target_path.split('/')[-1],
        'analysis_timestamp': timestamp,
        'analysis_style': analysis_style,
        'generated_at': datetime.now().isoformat()
    },
    'summary': {
        'total_vulnerabilities': len(vulnerabilities),
        'critical': len([v for v in vulnerabilities if v.get('severity') == 'Critical']),
        'high': len([v for v in vulnerabilities if v.get('severity') == 'High']),
        'medium': len([v for v in vulnerabilities if v.get('severity') == 'Medium']),
        'low': len([v for v in vulnerabilities if v.get('severity') == 'Low'])
    },
    'vulnerabilities': vulnerabilities
}

# Write the structured JSON
with open(vulns_json, 'w') as f:
    json.dump(result, f, indent=2)

print(f"[*] Extracted {len(vulnerabilities)} potential vulnerabilities")
PYEOF

if [ -f "$VULNS_JSON" ]; then
    echo "[SUCCESS] Structured vulnerabilities saved to: $VULNS_JSON"
else
    echo "[WARN] Failed to create structured vulnerabilities JSON"
fi
