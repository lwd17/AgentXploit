# AgentXploit Benchmark

A benchmark suite for evaluating AI agent security, covering real-world CVEs and design vulnerabilities across 9 popular AI agent frameworks. Each task includes a Dockerized target, a ground-truth exploit, automated verification, and support for both AI-agent-driven exploitation and Codex CLI baseline reproduction.

## Repository Structure

```
AgentXploit Benchmark/
├── benchmarks/                   # All benchmark tasks (9 agent frameworks, 72 tasks)
│   ├── agentscope-security-bench/
│   ├── autogpt-security-bench/
│   ├── dbgpt-security-bench/
│   ├── gpt_academic-security-bench/
│   ├── langchain-bench/
│   ├── llamaindex-bench/
│   ├── lobechat-bench/
│   ├── metagpt-security-bench/
│   └── openclaw-security-bench/
│
├── src/                          # Agent implementations
│   ├── analysis_agent/           # Static vulnerability analysis agent
│   ├── exploiter_agent/          # Dynamic vulnerability exploitation agent
│   └── AgentXploit/              # Core AgentXploit package (CLI: agentxploit)
│
├── codex_baseline/               # OpenAI Codex CLI baseline reproduction scripts
│   ├── install_codex.sh
│   ├── run_codex.sh
│   ├── run_baseline_codex.sh
│   └── README.md
│
├── pyproject.toml                # Python package (installs all 3 CLI entry points)
├── uv.lock                       # Locked dependencies
└── .env.example                  # Environment variable template
```

## Benchmark Coverage

| Framework | Tasks | Vulnerability Types |
|-----------|------:|---------------------|
| gpt_academic | 25 | LFI, RCE, XSS, CSRF, SSRF, path traversal, zip-bomb, ReDoS, pickle deserialization |
| openclaw | 11 | Arbitrary file write/read, browser API bypass, auth bypass, prompt injection, path validation |
| agentscope | 9 | RCE via eval, path traversal, LFI, CORS misconfiguration, stored XSS |
| langchain | 8 | SQL injection, PAL/CPAL injection, SSTI, graph Cypher injection, traversal RCE |
| lobechat | 8 | SSRF, JWT bypass, API key leak, XSS, open redirect, auth bypass |
| autogpt | 4 | Prompt injection, path traversal, ANSI injection |
| llamaindex | 4 | Command injection, RCE, Pandas eval injection |
| dbgpt | 3 | RCE via plugin upload, SQL injection, path traversal |
| metagpt | 1 | RCE via RunCode subprocess |
| **Total** | **72** | |

## Task Structure

Each benchmark has two subdirectories:

```
benchmarks/<agent>-bench/
├── tasks/
│   └── task-<name>/
│       ├── task_config.json   # Task definition (containers, setup, verify commands)
│       ├── start.sh           # Runs inside target container to initialize the scenario
│       ├── run_agent.sh       # Ground-truth exploit script (runs inside attacker container)
│       ├── verify.sh          # Automated verification (runs inside attacker container)
│       ├── README.md          # Vulnerability description and technical details
│       └── HOWTO.md           # Step-by-step manual testing guide
└── runtimes/
    └── <version>/
        ├── docker-compose.yml   # Defines target + attacker containers
        ├── Dockerfile           # Target container image
        └── Dockerfile.attacker  # Attacker container image
```

### task_config.json Schema

```json
{
  "task_id": "task-<name>",
  "task_name": "Human-readable name",
  "exploit_type": "network_api",
  "description": "What the vulnerability is",
  "vulnerability": { "cve": "...", "type": "...", "severity": "..." },
  "objective": {
    "goal": "What the exploit should achieve",
    "target_endpoint": "The vulnerable API endpoint",
    "vulnerability_detail": "Technical detail",
    "attack_requirements": {
      "execution_location": "Attacker container",
      "exploitation_method": "Step-by-step attack description",
      "success_condition": "What files/state prove success"
    }
  },
  "analysis_hints": { "hint_1": "...", "hint_2": "..." },
  "environment": {
    "attacker_container": "<framework>-attacker-<task>",
    "target_container": "<framework>-security-test-<task>",
    "source_code_path": "/app/<framework>-source"
  },
  "setup_container": { "runtime": "<version>", "command": "cd ../../runtimes/... && docker compose up -d" },
  "setup_server":    { "script": "start.sh", "command": "docker cp start.sh ... && docker exec ..." },
  "verify":          { "script": "verify.sh", "command": "docker cp verify.sh ... && docker exec ..." },
  "timeout": 300
}
```

## Setup

### Prerequisites

- Python ≥ 3.12
- Docker with Compose plugin
- An LLM API key (OpenAI-compatible endpoint)

### Install

```bash
# Clone and install
git clone <repo>
cd AgentXploit-Benchmark

# Install Python package (creates 3 CLI entry points)
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, OPENAI_BASE_URL, EXPLOIT_AGENT_MODEL, ANALYSIS_AGENT_MODEL
```

## Running a Task Manually (Ground Truth)

Every task can be run manually following its `HOWTO.md`. The general flow from the task directory:

```bash
cd benchmarks/<agent>-bench/tasks/<task-name>/

# 1. Start containers (from task dir — ../../ navigates to the bench runtime)
cd ../../runtimes/<version>
export TASK_ID=<task-suffix>
docker compose up -d
cd ../../tasks/<task-name>

# 2. Start target server
docker cp start.sh <target-container>:/workspace/
docker exec -d <target-container> bash /workspace/start.sh

# 3. Run ground-truth exploit
docker cp run_agent.sh <attacker-container>:/workspace/
docker exec <attacker-container> bash /workspace/run_agent.sh

# 4. Verify
docker cp verify.sh <attacker-container>:/workspace/
docker exec <attacker-container> bash /workspace/verify.sh

# 5. Cleanup
cd ../../runtimes/<version>
docker compose down -v
```

All commands are also embedded in `task_config.json` under `setup_container.command`, `setup_server.command`, and `verify.command`.

## Running with the Exploiter Agent

The `exploiter-agent` uses an LLM (via Google ADK + LiteLLM) to autonomously find and execute exploits.

### Network Mode (for all benchmark tasks)

```bash
# Ensure containers are running first (see manual flow above, steps 1-2)

exploiter-agent benchmarks/<agent>-bench/tasks/<task-name>/ \
  --mode network \
  --max-turns 20
```

The agent will:
1. Read `task_config.json` to understand the target
2. Use `bash` (docker exec) to interact with the attacker container
3. Discover the vulnerability, write and execute an exploit
4. Automatically run `verify.sh` at the end and report success/failure

### File Mode (for document/prompt-injection tasks)

```bash
exploiter-agent benchmarks/<agent>-bench/tasks/<task-name>/ \
  --mode file \
  --max-turns 15
```

### Configuration

The agent reads `src/exploiter_agent/config.yaml` by default. Override with `--config /path/to/config.yaml`.

Key environment variables (set in `.env`):

| Variable | Description |
|----------|-------------|
| `EXPLOIT_AGENT_MODEL` | LiteLLM model string, e.g. `claude-sonnet-4-6` or `gpt-4o` |
| `OPENAI_API_KEY` | API key for the model |
| `OPENAI_BASE_URL` | Base URL (for proxy/custom endpoints) |

## Running with the Analysis Agent

The `analysis-agent` analyzes agent source code to discover vulnerabilities without executing exploits.

```bash
# Analyze for prompt injection vulnerabilities
analysis-agent \
  --target-path /absolute/path/to/agent-source \
  --style prompt_injection \
  --max-turns 20

# Analyze for traditional security vulnerabilities (RCE, XSS, SSRF, etc.)
analysis-agent \
  --target-path /absolute/path/to/agent-source \
  --style traditional \
  --max-turns 30

# Analyze containerized target (agent reads source from inside container)
analysis-agent \
  --target-path /app/agent-source \
  --container-name <target-container-name> \
  --style traditional
```

Output is saved to `src/analysis_agent/reports/analysis_<timestamp>.json`.

Key environment variable: `ANALYSIS_AGENT_MODEL`.

## Codex CLI Baseline

Reproduce results using OpenAI Codex CLI as a baseline agent.

```bash
export OPENAI_API_KEY=your-key
export OPENAI_BASE_URL=https://your-endpoint/v1  # optional

# Run Codex on any task (fully automated)
bash codex_baseline/run_baseline_codex.sh \
  benchmarks/openclaw-security-bench/tasks/task-openclaw-browser-trace-stop-arbitrary-file-write
```

The script reads all parameters from `task_config.json`, builds a structured instruction, and runs `codex exec --dangerously-bypass-approvals-and-sandbox` in the attacker container. See [codex_baseline/README.md](codex_baseline/README.md) for details.

## Adding a New Task

1. Choose the appropriate `benchmarks/<agent>-bench/`
2. Create `tasks/task-<name>/` with the required files: `task_config.json`, `start.sh`, `run_agent.sh`, `verify.sh`, `README.md`, `HOWTO.md`
3. Create or reuse a runtime in `runtimes/<version>/` with `docker-compose.yml`, `Dockerfile`, `Dockerfile.attacker`
4. Test the full flow manually with `HOWTO.md`
5. The task is automatically available to `exploiter-agent` and the Codex baseline

## License

Apache-2.0
