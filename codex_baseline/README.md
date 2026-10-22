# Codex Baseline

This folder contains scripts for reproducing the **OpenAI Codex CLI** baseline on benchmark tasks.

## Files

| File | Description |
|------|-------------|
| `install_codex.sh` | Installs Codex CLI inside an attacker container via nvm + npm |
| `run_codex.sh` | Runs Codex inside the attacker container; reads `TASK_INSTRUCTION` env var |
| `run_baseline_codex.sh` | One-click orchestrator: starts containers, installs Codex, runs it, verifies, teardown |
| `codex_reports/` | Output directory for `<task_id>_codex_output.json` (auto-created) |

## Quick Start

```bash
# From Anewbenchmark/ root:
export OPENAI_API_KEY=your-key-here
export OPENAI_BASE_URL=https://your-endpoint/v1  # optional

bash codex_baseline/run_baseline_codex.sh \
  benchmarks/openclaw-security-bench/tasks/task-openclaw-browser-trace-stop-arbitrary-file-write
```

## How It Works

`run_baseline_codex.sh` reads all task parameters from `task_config.json` automatically:

1. **Parses** `task_config.json` to extract container names, setup commands, objective, hints
2. **Starts** containers via `setup_container.command`
3. **Starts** the target server via `setup_server.command`
4. **Installs** Codex CLI in the attacker container (`install_codex.sh`)
5. **Builds** the instruction prompt from `task_config.json` fields (description, objective, hints)
6. **Runs** `codex exec --dangerously-bypass-approvals-and-sandbox` in the attacker container
7. **Verifies** results via `verify.command`
8. **Saves** `codex_output.json` to `codex_reports/<task_id>_codex_output.json`
9. **Tears down** containers

## task_config.json Fields Used for Instruction

The Codex instruction is assembled from:

| Field | Used as |
|-------|---------|
| `task_name` | Task title |
| `description` | Overview paragraph |
| `objective.goal` | Primary goal |
| `objective.vulnerability_detail` | Technical detail of the bug |
| `objective.attack_requirements.exploitation_method` | Step-by-step attack method |
| `objective.attack_requirements.success_condition` | What "success" means |
| `analysis_hints.*` | All hint key-value pairs |
| `output_requirements` | Where to save output files |

## Manual Per-Task Usage

If you want to run Codex manually on a task, use these steps:

```bash
# 1. Start containers (from task directory)
cd benchmarks/<bench>/tasks/<task>/
eval "$(python3 -c "import json; print(json.load(open('task_config.json'))['setup_container']['command'])")"

# 2. Setup server
eval "$(python3 -c "import json; print(json.load(open('task_config.json'))['setup_server']['command'])")"

# 3. Install Codex in attacker container
ATTACKER=$(python3 -c "import json; print(json.load(open('task_config.json'))['environment']['attacker_container'])")
docker cp ../../../../codex_baseline/install_codex.sh $ATTACKER:/workspace/
docker exec $ATTACKER bash /workspace/install_codex.sh

# 4. Write your instruction and run Codex
docker cp ../../../../codex_baseline/run_codex.sh $ATTACKER:/workspace/
docker exec $ATTACKER bash -c "
  export OPENAI_API_KEY=your-key
  export TASK_INSTRUCTION='Your instruction here...'
  source ~/.nvm/nvm.sh && bash /workspace/run_codex.sh
"

# 5. Verify
eval "$(python3 -c "import json; print(json.load(open('task_config.json'))['verify']['command'])")"
```

## Notes

- Codex runs with `--dangerously-bypass-approvals-and-sandbox` — only use in isolated Docker environments
- Output JSON from Codex is verbose; use `jq '.[-1]'` to see the final message
- If a task's `run_codex.sh` exists inside the task directory itself, that task-specific version takes precedence and contains a hand-crafted instruction
