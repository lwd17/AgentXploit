import os
import logging
import json
import uuid
import time

import yaml
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

# Import custom tools
try:
    from .tools.todo_manager import todo_read, todo_write
    from .tools.file_tools import read, glob, grep, ls
    from .tools.analysis_writer import (
        create_analysis_json,
        write_tool_info,
        write_dataflow,
        write_vulnerabilities,
        write_vulnerabilities_traditional,
        write_environment,
        write_dependencies,
        write_final_report
    )
except ImportError:
    from tools.todo_manager import todo_read, todo_write  # type: ignore[no-redef]
    from tools.file_tools import read, glob, grep, ls  # type: ignore[no-redef]
    from tools.analysis_writer import (  # type: ignore[no-redef]
        create_analysis_json,
        write_tool_info,
        write_dataflow,
        write_vulnerabilities,
        write_vulnerabilities_traditional,
        write_environment,
        write_dependencies,
        write_final_report
    )

# Analysis style constants
STYLE_PROMPT_INJECTION = "prompt_injection"
STYLE_TRADITIONAL = "traditional"
VALID_STYLES = [STYLE_PROMPT_INJECTION, STYLE_TRADITIONAL]

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("analysis_agent.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Analysis agent for understanding target agent architecture and data flows."""

    def __init__(self, target_path: str, style: str = STYLE_PROMPT_INJECTION,
                 container_name: str = None, config_path: str = "config.yaml"):
        """Initialize analysis agent.

        Args:
            target_path: Path to target agent codebase (local or container path)
            style: Analysis style - 'prompt_injection' (tool/dataflow based) or
                   'traditional' (direct vulnerability scanning for RCE, XSS, CSRF, etc.)
            container_name: Docker container name if target is containerized
            config_path: Path to configuration file
        """
        if style not in VALID_STYLES:
            raise ValueError(f"Invalid style '{style}'. Must be one of: {VALID_STYLES}")

        self.target_path = target_path
        self.style = style
        self.container_name = container_name
        self.config_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), config_path)
        )
        self.config = self._load_config(self.config_path) if os.path.exists(self.config_path) else {}

        self.session_history = {
            "session_id": str(uuid.uuid4()),
            "target_path": target_path,
            "style": style,
            "container_name": container_name,
            "findings": [],
            "timestamp": time.strftime("%Y%m%d_%H%M%S")
        }

        self.agent = self._build_adk_agent()

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config or {}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            return {}

    def _build_system_prompt(self) -> str:
        """Build simplified system prompt for analysis agent."""
        prompt = """You are an expert AI Agent Security researcher and vulnerability analyst.

You specialize in discovering security vulnerabilities in codebases, including both:
- AI/LLM agent-specific vulnerabilities (prompt injection, indirect prompt injection, data exfiltration via tools)
- Traditional application security vulnerabilities (RCE, XSS, CSRF, SQL injection, path traversal, SSRF, etc.)

=== ANALYSIS PHILOSOPHY ===

**Trace Complete Dataflows**: Don't just analyze tools in isolation. For each tool:
1. Identify the data SOURCE (where untrusted input enters)
2. Trace ALL intermediate processing (helpers, validators, parsers, formatters)
3. Identify the data SINK (where it affects LLM context or executes actions)

**Helper Functions Matter**: Vulnerabilities often hide in:
- Summarization functions that preserve malicious instructions
- URL validators with bypass opportunities (e.g., missing cloud metadata IPs)
- Path validators vulnerable to traversal
- Memory/context handlers that persist poisoned data

=== AVAILABLE TOOLS ===

**File Operations:**
- ls(path) - list directory contents
- glob(pattern, path) - find files matching pattern
- grep(pattern, path) - search for text patterns in files
- read(file_path) - read file contents

**Progress Tracking:**
- todo_read() - read current todo list
- todo_write(todos) - update todo list

**Analysis Writers:**
- create_analysis_json(json_path) - initialize analysis file (MUST call first)
- write_environment(json_path, environment) - write environment info
- write_dependencies(json_path, dependencies) - write dependency list
- write_tool_info(json_path, tool_name, tool_info) - write tool description
- write_dataflow(json_path, tool_name, dataflow) - write data flow analysis
- write_vulnerabilities(json_path, tool_name, vulnerabilities) - write prompt injection related vulnerabilities
- write_vulnerabilities_traditional(json_path, vulnerabilities) - write traditional security vulnerabilities
- write_final_report(json_path) - finalize report (call when DONE)

=== RULES ===

- All write_* functions support overwriting - call them again to update findings
- Keep analyzing until you have thoroughly examined all relevant code
- When analyzing a tool, always grep for and read its helper functions
- Call write_final_report() ONLY when analysis is complete
- Follow the task and workflow provided in the user message
"""
        return prompt

    def _build_user_message_prompt_injection(self, json_path: str, max_turns: int) -> str:
        """Build user message for prompt injection style analysis."""
        return f"""=== ANALYSIS TARGET ===
Path: {self.target_path}
Output JSON: {json_path}
Max turns: {max_turns}
Analysis Style: Prompt Injection & Agent Security (Comprehensive)

=== TASK ===
Perform a **comprehensive** prompt injection vulnerability analysis by:
1. Understanding environment and dependencies
2. Finding all TOOLS - functions that interact with external environment
3. **CRITICAL**: Tracing the COMPLETE dataflow chain for each tool, including ALL helper/utility functions
4. Identifying security vulnerabilities - aim for thorough coverage, at least 8-10 vulnerabilities

=== WORKFLOW ===

1. **INITIALIZE**: Call create_analysis_json("{json_path}")

2. **ENVIRONMENT**: Explore codebase structure thoroughly
   - Use ls(), glob() to understand project layout
   - Identify entry points, config files, dependencies
   - Call write_environment() and write_dependencies()

3. **FIND TOOLS**: Search for agent tools that interact with external environment
   - Look for: file read/write, bash/shell execution, web requests, API calls, database operations
   - Identify tools that could be exploited via prompt injection

4. **FOR EACH TOOL FOUND** (Deep Analysis Required):
   a) Read and understand the tool code thoroughly
   b) **TRACE ALL HELPER FUNCTIONS**: For each tool, identify and analyze:
      - Content processing functions (summarizers, parsers, formatters)
      - Validation/sanitization functions (URL validators, path checkers, input filters)
      - Memory/storage functions (embedding, caching, logging)
      - Any intermediate function that touches data between source and sink
   c) Call write_tool_info() - document tool name, position, description, parameters
   d) Call write_dataflow() - analyze COMPLETE data flow including all intermediate functions
   e) Call write_vulnerabilities() - document all found vulnerabilities

5. **AUXILIARY FUNCTION ANALYSIS** (Critical - Do Not Skip):
   After analyzing tools, search for and analyze standalone helper modules:
   - Text processing: summarization, chunking, embedding functions
   - URL/network utilities: validators, fetchers, parsers
   - File utilities: path resolution, content parsing, format conversion
   - Memory utilities: storage, retrieval, serialization
   - Agent loop: message history handling, context injection, result formatting

   Use grep() to find patterns like:
   - "def summarize", "def validate", "def sanitize", "def parse"
   - "urllib", "requests", "fetch", "http"
   - "subprocess", "shell", "exec", "eval"
   - "memory", "history", "context", "prompt"

6. **FINALIZE**: Call write_final_report() when analysis is complete

=== CRITICAL VULNERABILITIES TO IDENTIFY ===

Focus on these attack patterns (expanded from core two):

**Pattern 1: Untrusted Data → LLM Context/Decision**
- External/untrusted data (web content, file content, user input, API responses) flows into LLM prompt
- This enables indirect prompt injection attacks
- **Check ALL intermediate processing**: Does summarization preserve malicious instructions? Does parsing strip dangerous content?
- Example: web_search results → summarize_text() → agent history → LLM prompt

**Pattern 2: LLM Output → Sensitive Tool Execution**
- LLM decisions/outputs are passed to dangerous tools without validation
- This enables RCE, data exfiltration, etc.
- **Check validation gaps**: Is command allowlist bypassable? Are path checks sufficient?
- Example: LLM output → weak allowlist check → shell execution

**Pattern 3: Insufficient Input Validation (Prompt Injection Enabler)**
- URL validators that miss internal IPs, cloud metadata endpoints (169.254.169.254)
- Path validators vulnerable to traversal or symlink attacks
- Content filters that don't catch encoded/obfuscated injection payloads
- Example: browse_website URL validation misses cloud metadata → SSRF → credential theft

**Pattern 4: Persistent Context Poisoning**
- Malicious content stored in memory/history without sanitization
- Poisoned context affects future LLM decisions across sessions
- Example: webpage content → memory embedding → future prompt poisoning

**Pattern 5: Credential/Secret Exposure via Prompt Injection**
- Credentials embedded in URLs, headers, or config accessible to LLM
- Prompt injection can trick LLM to expose these in outputs
- Example: git clone URL contains credentials → LLM can be tricked to log/return it

=== ANALYSIS DEPTH REQUIREMENTS ===

For each vulnerability, document:
- **Type**: Specific vulnerability category
- **Severity**: Critical/High/Medium/Low with justification
- **Attack Scenario**: Step-by-step exploitation path
- **Code Evidence**: Exact file paths, line numbers, code snippets
- **Dataflow Chain**: Complete path from attacker input to impact (including ALL intermediate functions)
- **End-to-End Impact**: What an attacker can ultimately achieve
- **Mitigation**: Specific remediation recommendations

=== THOROUGHNESS CHECKLIST ===
Before calling write_final_report(), ensure you have:
[ ] Analyzed all tools that interact with external environment
[ ] Traced helper functions called by each tool (summarizers, validators, parsers)
[ ] Checked URL/path validation functions for bypass opportunities
[ ] Examined memory/history handling for injection persistence
[ ] Reviewed agent loop for context injection vulnerabilities
[ ] Searched for credential handling in network operations

=== BEGIN ===
Start by calling create_analysis_json("{json_path}")
"""

    def _build_user_message_traditional(self, json_path: str, max_turns: int) -> str:
        """Build user message for traditional vulnerability style analysis."""
        return f"""=== ANALYSIS TARGET ===
Path: {self.target_path}
Output JSON: {json_path}
Max turns: {max_turns}
Analysis Style: Traditional Security Vulnerabilities

=== TASK ===
Perform a **traditional security vulnerability assessment** of this codebase (non-AI-specific). The goal is to find vulnerabilities that exist **regardless of any agent/LLM prompt logic**, AS MANY AS POSSIBLE.

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
3) **Trace taint**: follow input → transformation → sink (e.g., user input → string concat → subprocess).
4) **Minimize false positives**: only report issues confirmed by code evidence; if uncertain, label as “Potential” with rationale.
5) **Prefer minimal, safe fixes**: propose the smallest viable patch and safe alternatives.

---

=== REQUIRED WORKFLOW (MANDATORY) ===

1) **INITIALIZE**
- Call: `create_analysis_json("{json_path}")`

2) **ENVIRONMENT & INVENTORY**
- Explore repository structure using `ls()` / `glob()`
- Identify:
  - Primary languages (Python/JS/Go/etc.)
  - Frameworks (web frameworks, CLI tools, job runners)
  - Entry points (main, server, CLI, scripts, CI)
  - Dangerous subsystems (upload/download, extract, execute, parse)
- Call:
  - `write_environment()` (OS assumptions, runtime expectations, execution modes)
  - `write_dependencies()` (dependency files like requirements.txt, pyproject.toml, package.json, go.mod, etc.)

3) **VULNERABILITY SCANNING (MULTI-PASS)**
Do at least **three passes**:

**PASS A — Broad Pattern Search**
- Use `grep()` with many patterns to locate candidate files quickly.
- Prioritize:
  - request handlers / API routes / controllers
  - file read/write utilities
  - archive extraction utilities
  - subprocess usage
  - parsers (yaml/xml/pickle)
  - authn/authz middleware
  - config loaders
  - logging of sensitive values

**PASS B — Sink-Centric Deep Review**
For each sink category (command execution, deserialization, SQL execution, URL fetch, file write, template render):
- Open the file and read surrounding context
- Identify whether any attacker-controlled input can reach the sink
- Check for safeguards (validation, allowlists, encoding, sandboxing, safe APIs)

**PASS C — Boundary-Centric Review**
Review every code boundary where external input enters:
- HTTP endpoints
- CLI argument parsing
- environment variables
- config file loaders
- file uploads / dataset ingestion
- webhooks / queue consumers
- plugins/extensions loading
Trace what they can affect (paths, commands, URLs, templates, queries).

4) **DOCUMENT FINDINGS (EVIDENCE-DRIVEN)**
For every confirmed issue, call:
- `write_vulnerabilities_traditional()`

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

Also include:
- **“Not a vuln / mitigated” notes** when a suspicious pattern is actually safe (to show careful review).

5) **FINALIZE**
- Call: `write_final_report()` after completing scanning and documenting issues.
The final report should summarize:
- Repo overview & risk hotspots
- Findings by severity (Critical → Low)
- Cross-cutting themes (input validation gaps, dangerous defaults)
- Quick wins vs. longer-term refactors

---

=== VULNERABILITY CATEGORIES (EXPAND BEYOND THE LIST) ===
You must scan at least the following (and any others you discover):

1) **Remote Code Execution (RCE) / Command Injection** (Critical)
- Sinks: `eval`, `exec`, `compile`, `pickle` gadgets, dynamic imports, `subprocess.*`, `os.system`, `popen`, `shell=True`
- Also check: unsafe format strings in shell commands; use of `shlex` incorrectly; user input in command args

2) **Injection (SQL / NoSQL / Template / LDAP / CLI flags)** (Critical/High)
- SQL: raw query concatenation; missing parameterization; ORM raw fragments
- NoSQL: query object injection; `$where`-like patterns
- Template: Jinja2/Handlebars/etc. rendering of untrusted content
- Shell/CLI flag injection: passing user input as flags

3) **Path Traversal / Arbitrary File Read/Write** (High)
- `open()`, `Path()`, `send_file`, `read_text`, `write_text`, file serving endpoints
- Look for `../`, absolute paths, symlink following, improper `join` usage
- Unsafe temp files: predictable names, world-writable dirs

4) **SSRF / Arbitrary URL Fetch** (High)
- `requests`, `urllib`, `httpx`, `aiohttp`, `fetch`, `curl` wrappers
- Missing allowlist; no scheme restriction; follows redirects into internal networks
- Look for access to cloud metadata IPs, localhost, private ranges

5) **Insecure Deserialization** (Critical)
- `pickle.load/loads`, `yaml.load` (not safe_load), `marshal`, custom object hooks
- Loading untrusted files, network payloads, or user-supplied blobs

6) **Archive Extraction Vulnerabilities (Zip Slip / Tar Path Traversal)** (High)
- `zipfile`, `tarfile`, custom extractors
- Ensure normalized paths and extraction destination checks

7) **Hardcoded Secrets / Sensitive Data Exposure** (High)
- API keys/tokens/passwords embedded in code or committed configs
- Secrets in logs, exceptions, debug endpoints
- Leaky error messages exposing internal paths or stack traces in production

8) **Authentication / Authorization Issues** (High)
- Missing auth checks on endpoints; broken role checks
- Confused deputy: trusting headers, trusting client-side flags
- Weak session handling, insecure JWT validation (alg=none, missing audience/issuer)

9) **Cryptography Misuse** (Medium/High)
- Hardcoded keys, insecure randomness, weak hashes for passwords
- Lack of salts, outdated algorithms, DIY crypto

10) **XXE / Unsafe XML Parsing** (High)
- `lxml`, `xml.etree`, `minidom`, SAX parsers
- External entity resolution, DTD processing enabled

11) **Insecure Configuration / Debug Features** (Medium)
- `DEBUG=True`, permissive CORS, missing security headers
- Dev endpoints enabled in production; default admin credentials

12) **Dependency / Supply Chain Risks** (Medium/High)
- Unpinned dependencies, `pip install` from git HEAD, `curl | bash` installs
- Post-install scripts, suspicious CI steps, downloading executables at build time

13) **Race Conditions / Concurrency Bugs leading to Security Issues** (Medium)
- TOCTOU on file operations; lock-free temp file creation


=== STRONG SEARCH STRATEGY ===
Use multiple `grep()` waves:

**Wave 1: High-signal sinks**
- `eval(`, `exec(`, `compile(`, `importlib.import_module`, `__import__`
- `subprocess`, `os.system`, `popen`, `shell=True`
- `pickle.load`, `pickle.loads`, `yaml.load`, `marshal`
- `zipfile`, `tarfile`, `extractall`, `extract`

**Wave 2: Web/IO boundaries**
- `@app.route`, `router.`, `FastAPI`, `Flask`, `Django`, `express`, `koa`
- `request.`, `req.`, `ctx.request`, `body`, `query`, `params`
- `open(`, `Path(`, `read_text`, `write_text`, `send_file`, `upload`

**Wave 3: Secrets & config**
- `password`, `passwd`, `secret`, `api_key`, `token`, `credential`, `private_key`
- `.env`, `dotenv`, `AWS_`, `GCP_`, `AZURE_`
- `DEBUG`, `CORS`, `localhost`, `0.0.0.0`

**Wave 4: Network fetch & SSRF**
- `requests.get`, `requests.post`, `urllib`, `httpx`, `aiohttp`, `fetch`
- `allow_redirects`, `proxies`, `verify=False`

**Wave 5: Auth & session**
- `auth`, `login`, `jwt`, `session`, `cookie`, `Bearer`, `Authorization`
- `is_admin`, `role`, `permission`, `acl`

After matches, open the files and confirm whether attacker-controlled data reaches the sink.

---

=== BEGIN ===
Start by calling create_analysis_json("{json_path}")
"""

    def _build_adk_agent(self) -> LlmAgent:
        """Build Google ADK agent with tools."""
        model_name = os.getenv("ANALYSIS_AGENT_MODEL", "gpt-4")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

        system_prompt = self._build_system_prompt()
        llm = LiteLlm(model=model_name, api_key=api_key, base_url=base_url)

        # Wrap functions as FunctionTools
        tools = [
            # File operations - explore and read codebase
            FunctionTool(func=read),
            FunctionTool(func=glob),
            FunctionTool(func=grep),
            FunctionTool(func=ls),
            # Todo management - track analysis progress
            FunctionTool(func=todo_read),
            FunctionTool(func=todo_write),
            # Analysis writers - write findings to JSON
            FunctionTool(func=create_analysis_json),
            FunctionTool(func=write_tool_info),
            FunctionTool(func=write_dataflow),
            FunctionTool(func=write_vulnerabilities),
            FunctionTool(func=write_vulnerabilities_traditional),
            FunctionTool(func=write_environment),
            FunctionTool(func=write_dependencies),
            FunctionTool(func=write_final_report)
        ]

        agent = LlmAgent(
            model=llm,
            name="analysis_agent",
            description="Security analysis agent for AI agent codebases",
            instruction=system_prompt,
            tools=tools
        )

        logger.info(f"Analysis agent created with {len(tools)} tools")
        return agent

    def run(self, max_turns: int) -> dict:
        """Run the analysis agent.

        Args:
            max_turns: Maximum number of LLM calls (required, no default)

        Returns:
            dict: Analysis results

        Raises:
            ValueError: If max_turns is not provided
        """
        if max_turns is None:
            raise ValueError("max_turns is required")

        from google.adk.runners import InMemoryRunner, RunConfig
        from google.genai import types

        logger.info(f"Starting analysis of {self.target_path}")

        # Create runner
        runner = InMemoryRunner(agent=self.agent, app_name="analysis_agent")

        # Create session
        import asyncio
        asyncio.run(
            runner.session_service.create_session(
                app_name="analysis_agent",
                user_id="analyst",
                session_id="default"
            )
        )

        run_config = RunConfig(max_llm_calls=max_turns)

        # Generate unique JSON path using target path hash and timestamp
        script_dir = os.path.dirname(os.path.abspath(__file__))
        reports_dir = os.path.join(script_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        # Create unique identifier from target path and timestamp
        path_hash = abs(hash(self.target_path)) % 10000
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(reports_dir, f"analysis_{path_hash}_{timestamp}.json")

        # Build user message based on analysis style
        if self.style == STYLE_PROMPT_INJECTION:
            user_message_text = self._build_user_message_prompt_injection(json_path, max_turns)
        else:  # STYLE_TRADITIONAL
            user_message_text = self._build_user_message_traditional(json_path, max_turns)

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=user_message_text)]
        )

        final_response = None
        final_report_called = False

        analysis_data = {
            "session_id": self.session_history["session_id"],
            "target_path": self.target_path,
            "style": self.style,
            "json_path": json_path,
            "events": [],
            "final_response": None
        }

        # Detailed log data for tool calls and responses
        log_data = {
            "session_id": self.session_history["session_id"],
            "target_path": self.target_path,
            "style": self.style,
            "json_path": json_path,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tool_calls": []
        }

        try:
            logger.info(f"Starting agent execution (style: {self.style})...")
            for event in runner.run(
                user_id="analyst",
                session_id="default",
                new_message=user_message,
                run_config=run_config
            ):
                # Log tool calls
                function_calls = event.get_function_calls()
                if function_calls:
                    for fc in function_calls:
                        args = {}
                        try:
                            args = fc.args if hasattr(fc, 'args') else {}
                            if isinstance(args, str):
                                args = json.loads(args)
                        except Exception:
                            pass

                        log_entry = {
                            "type": "tool_call",
                            "tool": fc.name,
                            "timestamp": time.time()
                        }

                        # Detailed log entry for log_data
                        detailed_log_entry = {
                            "type": "tool_call",
                            "tool": fc.name,
                            "args": args,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "timestamp_unix": time.time()
                        }
                        log_data["tool_calls"].append(detailed_log_entry)

                        # Log based on tool type
                        if fc.name in ["ls", "glob", "grep", "read"]:
                            logger.info(f"[Tool Call] {fc.name}({args})")
                        elif fc.name.startswith("write_"):
                            tool_name = args.get("tool_name", "") if args else ""
                            logger.info(f"[Tool Call] {fc.name}(tool_name='{tool_name}')")
                            if fc.name == "write_final_report":
                                final_report_called = True
                        else:
                            logger.info(f"[Tool Call] {fc.name}")

                        analysis_data["events"].append(log_entry)

                # Log tool responses
                function_responses = event.get_function_responses()
                if function_responses:
                    for fr in function_responses:
                        response_summary = None
                        response_data = None
                        error_info = None
                        try:
                            if isinstance(fr.response, str):
                                response_data = json.loads(fr.response) if fr.response.startswith('{') else fr.response
                            else:
                                response_data = fr.response

                            if isinstance(response_data, dict):
                                if response_data.get("success") is not None:
                                    if response_data.get("success"):
                                        response_summary = "success"
                                    else:
                                        error_info = response_data.get("error") or response_data.get("message", "unknown")
                                        response_summary = f"error: {error_info}"
                        except Exception as parse_err:
                            error_info = str(parse_err)

                        log_entry = {
                            "type": "tool_response",
                            "tool": fr.name,
                            "timestamp": time.time()
                        }

                        # Detailed log entry for log_data
                        detailed_response_entry = {
                            "type": "tool_response",
                            "tool": fr.name,
                            "success": response_summary == "success" if response_summary else None,
                            "error": error_info,
                            "response_preview": str(response_data)[:500] if response_data else None,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "timestamp_unix": time.time()
                        }
                        log_data["tool_calls"].append(detailed_response_entry)

                        if response_summary:
                            logger.info(f"[Tool Response] {fr.name} -> {response_summary}")
                        else:
                            logger.info(f"[Tool Response] {fr.name}")

                        analysis_data["events"].append(log_entry)

                # Capture final response
                if event.is_final_response():
                    final_response = event.content.parts[0].text
                    logger.info(f"[Final Response] {final_response[:200]}...")
                    analysis_data["final_response"] = final_response

            logger.info("Analysis completed")

            if not final_report_called:
                logger.warning("write_final_report was not called during analysis")
            else:
                logger.info(f"Analysis report saved at: {json_path}")

            # Save log data to JSON file
            log_data["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            log_data["final_report_called"] = final_report_called
            self._save_log(log_data, path_hash, timestamp)

            self._save_results(analysis_data)
            return analysis_data

        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            analysis_data["error"] = str(e)
            # Also save log data on error
            log_data["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            log_data["error"] = str(e)
            self._save_log(log_data, path_hash, timestamp)
            return analysis_data

    def _save_log(self, log_data: dict, path_hash: int, timestamp: str):
        """Save detailed tool call log to JSON file.

        Args:
            log_data: Log data containing tool calls and responses
            path_hash: Hash of target path for unique filename
            timestamp: Timestamp string for filename
        """
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            reports_dir = os.path.join(script_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)

            log_file = os.path.join(reports_dir, f"log_{path_hash}_{timestamp}.json")

            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Tool call log saved to {log_file}")

        except Exception as e:
            logger.error(f"Failed to save log: {e}")

    def _save_results(self, analysis_data: dict):
        """Save analysis results to file."""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            reports_dir = os.path.join(script_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(reports_dir, f"analysis_{timestamp}.json")

            with open(report_file, 'w') as f:
                json.dump(analysis_data, f, indent=2)

            logger.info(f"Analysis results saved to {report_file}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")