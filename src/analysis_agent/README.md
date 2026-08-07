# Analysis Agent

An intelligent security analysis agent for AI agents, powered by LLM-based multi-round analysis.

## Overview

The Analysis Agent automatically discovers, analyzes, and reports security vulnerabilities in target AI agent codebases. It uses a sophisticated multi-round LLM-based approach to understand tool implementations, data flows, and potential security risks with end-to-end attack scenarios.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Analysis Agent                          │
│                    (Google ADK Agent)                       │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────────────┐
        │            │            │                    │
        ▼            ▼            ▼                    ▼
┌──────────────┐ ┌────────┐ ┌──────────────┐ ┌──────────────┐
│ Code Reading │ │ Docker │ │ Tool         │ │ Report       │
│ Tools        │ │ Tools  │ │ Extraction   │ │ Writing      │
│              │ │        │ │ (Multi-Round)│ │              │
└──────────────┘ └────────┘ └──────────────┘ └──────────────┘
```

## Core Workflow

### 1. Discovery Phase
The agent explores the target codebase to:
- Identify agent framework (Google ADK, LangGraph, CrewAI, etc.)
- Locate tool definitions and implementations
- Map the agent's architecture

### 2. Analysis Phase (Automated Multi-Round)
When a tool is discovered, the **Tool Extractor** automatically performs 3 rounds of LLM-based analysis:

**ROUND 1: Tool Information Extraction**
- Extract tool description and functionality
- Identify parameters and return types
- Understand what the tool does

**ROUND 2: Data Flow Analysis**
- Map data sources (user_input, web_content, file_read, etc.)
- Map data destinations (llm_prompt, bash_command, file_write, etc.)
- Identify data transformations and sensitive flows
- Detect untrusted data paths

**ROUND 3: Vulnerability Analysis**
- Analyze security vulnerabilities using code + dataflow context
- Generate end-to-end attack scenarios
- Assess severity and exploitability
- Provide mitigation recommendations

### 3. Reporting Phase
- Incremental reports during analysis (optional)
- Final comprehensive security report (JSON)
- Structured vulnerability data with evidence

## Tools Reference

### Code Reading Tools (Local Filesystem)

#### `read_code(file_path, start_line=None, end_line=None)`
Read source code from target agent's codebase.
- **Use for**: Reading specific files identified during exploration
- **Returns**: File content with line numbers

#### `read_code_with_references(file_path, include_imports=True, max_depth=1)`
Read code with automatic cross-reference resolution.
- **Use for**: Understanding how a tool calls other functions
- **Returns**: Main file content + referenced code snippets

#### `extract_imports(file_path)`
Extract all imports from a Python file.
- **Use for**: Understanding dependencies
- **Returns**: List of import statements

#### `list_directory(directory_path, pattern="*", recursive=False)`
List files in a directory.
- **Use for**: Discovering tool files, config files
- **Returns**: List of file paths

#### `search_code(directory_path, search_pattern, file_pattern="*.py")`
Search for code patterns across the codebase.
- **Use for**: Finding tool definitions, security patterns
- **Returns**: List of matches with file paths and line numbers

### Docker Container Tools

#### `execute_docker_command(container_name, command, timeout=30)`
Execute commands inside Docker containers.
- **Use for**: Analyzing containerized agents
- **Examples**:
  - `execute_docker_command("my_agent", "find /app -name '*.py'")`
  - `execute_docker_command("my_agent", "cat /app/tools/search.py")`

### Analysis Tools

#### 🌟 `analyze_tool(tool_name, code_snippet, position, auto_write_report=False)` **[RECOMMENDED]**
**Automated 3-round LLM analysis** - Use this when you discover a new tool!

**What it does:**
1. Extracts tool information (description, parameters, functionality)
2. Analyzes data flow (sources → destinations, sensitive paths)
3. Identifies vulnerabilities (with attack scenarios and impacts)

**Parameters:**
- `tool_name`: Name of the tool
- `code_snippet`: The actual implementation code
- `position`: Location (e.g., "tools/search.py:search_web")
- `auto_write_report`: If True, automatically writes to incremental report

**Returns:**
```python
{
    "tool_name": str,
    "position": str,
    "tool_info": {
        "description": str,
        "functionality": str,
        "parameters": [...],
        "return_type": str
    },
    "dataflow": {
        "data_sources": [...],
        "data_destinations": [...],
        "sensitive_flows": [...]
    },
    "vulnerabilities": {
        "has_vulnerabilities": bool,
        "vulnerabilities": [...],
        "overall_risk": "critical|high|medium|low",
        "risk_summary": str
    },
    "analysis_complete": bool
}
```

**Example Usage:**
```python
result = analyze_tool(
    "search_web",
    code_snippet,
    "tools/search.py:search_web",
    auto_write_report=True
)
```

#### `extract_tool_info(tool_name, code_snippet, position)`
**ROUND 1 only** - Extract tool description and functionality.
- Use when you only need basic tool information
- Faster than full `analyze_tool()`

#### `extract_dataflow(tool_name, code_snippet, tool_description, position)`
**ROUND 2 only** - Extract data flow analysis.
- Requires tool_description from Round 1
- Use when you already have tool info and only need dataflow

#### `extract_vulnerabilities(tool_name, code_snippet, tool_description, dataflow, position)`
**ROUND 3 only** - Extract vulnerability analysis.
- Requires tool_description and dataflow from previous rounds
- Use for fine-grained control over analysis process

#### `analyze_vulnerability(...)` **[LEGACY]**
Single-round vulnerability analysis. Consider using `analyze_tool()` or `extract_vulnerabilities()` instead.

### Report Writing Tools

#### `write_report(agent_name, tools, dataflows, vulnerabilities, ...)`
Generate security analysis report.

**Two modes:**

**1. Incremental Mode** (during analysis):
```python
write_report(
    agent_name="TargetAgent",
    incremental=True,
    tool_data=analyze_tool_result  # Automatically normalized
)
```

**2. Complete Mode** (final report):
```python
write_report(
    agent_name="TargetAgent",
    agent_framework="Google ADK",
    agent_entry_point="main.py",
    tools=[...],
    dataflows=[...],
    vulnerabilities=[...]
)
```

**Auto-normalization:** `write_report()` automatically handles output from both:
- `analyze_tool()` (new format)
- Legacy tool analysis format

**Returns:**
```python
{
    "success": bool,
    "report_path": str,  # e.g., "reports/security_analysis_TargetAgent_20231110.json"
    "message": str
}
```

### Progress Tracking Tools

#### `todo_write(todos)`, `todo_read()`, `todo_update()`, `todo_add()`, `todo_complete()`
Track analysis progress with auto-tracking support.

## Vulnerability Detection Capabilities

### Path Traversal Detection
- **Smart Detection**: Recognizes secure patterns (`os.path.abspath`, `Path.resolve()`)
- **No False Positives**: Only reports actual vulnerabilities
- **Evidence-Based**: References specific code patterns

### Prompt Injection Analysis (End-to-End)
- **Untrusted Documents → LLM**: Detects malicious content injection
- **Task Misfollowing**: Agent doing wrong tasks due to injected prompts
- **Incorrect Outputs**: Biased or wrong research/reports
- **Data Exfiltration**: Sensitive data leakage via crafted prompts
- **Workflow Manipulation**: Subtle data poisoning

### Command Injection Detection
- **Direct Injection**: User input → command execution
- **Nuanced Analysis**: Recognizes `shlex.quote` but flags `shell=True`
- **Severity Assessment**: Context-aware risk rating

### Indirect Prompt Injection
- **Multi-Stage Attacks**: Early injection → LLM manipulation → code execution
- **Automated Chains**: Detects exploitation paths

## LLM Provider Support

The analysis uses separate LLM instances for tool extraction (not the main analysis agent):

**Supported Providers:**
- **OpenAI GPT-4o** (Primary, recommended)
- **Google Gemini 2.0 Flash** (Fallback)

**Configuration:**
Set in `.env`:
```bash
# Option 1: OpenAI (Recommended)
OPENAI_API_KEY=sk-...

# Option 2: Gemini
GEMINI_API_KEY=...
```

## Usage Examples

### Basic Usage
```python
from analysis_agent import AnalysisAgent

# Analyze local codebase
agent = AnalysisAgent(target_path="/path/to/target/agent")
result = agent.run(max_turns=50)

# Analyze containerized agent
agent = AnalysisAgent(
    target_path="/app",
    container_name="my_agent_container"
)
result = agent.run()
```

### Example Analysis Flow

```python
# 1. The agent discovers a tool
tool_code = read_code("tools/researcher.py")

# 2. Automatically analyze it (3 rounds)
analysis = analyze_tool(
    tool_name="research_topic",
    code_snippet=tool_code,
    position="tools/researcher.py:research_topic",
    auto_write_report=True  # Automatically add to report
)

# 3. Check results
if analysis['vulnerabilities']['has_vulnerabilities']:
    print(f"Risk: {analysis['vulnerabilities']['overall_risk']}")
    for vuln in analysis['vulnerabilities']['vulnerabilities']:
        print(f"- {vuln['type']}: {vuln['severity']}")
```

### Manual Control (Advanced)

```python
# For fine-grained control, use individual rounds:

# Round 1: Get tool info
info = extract_tool_info(tool_name, code, position)

# Round 2: Analyze dataflow
dataflow = extract_dataflow(tool_name, code, info['description'], position)

# Round 3: Find vulnerabilities
vulns = extract_vulnerabilities(
    tool_name, code, info['description'], dataflow, position
)
```

## Report Structure

### Incremental Report (during analysis)
```json
{
  "agent_name": "TargetAgent",
  "framework": "Google ADK",
  "entry_point": "main.py",
  "analysis_start": "2023-11-10 14:30:00",
  "last_updated": "2023-11-10 15:45:00",
  "tools": [
    {
      "name": "search_web",
      "description": "...",
      "position": "tools/search.py:search_web",
      "parameters": [...],
      "dataflow": {
        "sources": ["user_input", "web_content"],
        "destinations": ["llm_prompt"],
        "sensitive_flows": [...]
      },
      "vulnerability_analysis": {
        "has_vulnerabilities": true,
        "vulnerabilities": [
          {
            "type": "prompt_injection_via_untrusted_content",
            "severity": "high",
            "description": "...",
            "attack_scenario": "...",
            "end_to_end_impact": [...],
            "evidence": "...",
            "mitigation": "..."
          }
        ],
        "overall_risk": "high"
      }
    }
  ],
  "vulnerabilities": [...],
  "environment": {...}
}
```

## Key Features

### ✅ Automated Multi-Round Analysis
- Discovers tool → Analyzes in 3 rounds → Reports automatically
- No manual orchestration needed

### ✅ Intelligent Vulnerability Detection
- LLM-based reasoning (not rigid rules)
- Code-aware pattern recognition
- End-to-end attack scenarios

### ✅ Flexible & Extensible
- Works with any AI agent framework
- Supports local and containerized agents
- Handles both legacy and modern tool formats

### ✅ Production-Ready
- Comprehensive logging
- Incremental + final reporting
- Error handling and fallbacks
- Multi-provider LLM support

## Logging

Logs are written to `analysis_agent.log`:
```
2023-11-10 14:30:15 - analysis_agent - INFO - Starting analysis for: TargetAgent
2023-11-10 14:30:20 - tool_extractor - INFO - [ROUND 1] Extracting tool info for: search_web
2023-11-10 14:30:25 - tool_extractor - INFO - [ROUND 2] Extracting dataflow for: search_web
2023-11-10 14:30:30 - tool_extractor - INFO - [ROUND 3] Extracting vulnerabilities for: search_web
2023-11-10 14:30:35 - tool_extractor - INFO - Complete analysis finished for: search_web
2023-11-10 14:30:35 - tool_extractor - INFO -   - Vulnerabilities found: 2
2023-11-10 14:30:35 - tool_extractor - INFO -   - Overall risk: high
```

## Configuration Files

### `config.yaml` (Optional)
```yaml
target:
  path: /path/to/target/agent
  container_name: my_agent  # Optional for Docker

analysis:
  max_turns: 50
  enable_incremental_reports: true

llm:
  model: gemini-2.0-flash-exp
  temperature: 0.7
```

## Development

### Running Tests
```bash
# Test tool extractor
python test_tool_extractor.py

# Test vulnerability analyzer (legacy)
python test_llm_vulnerability_analyzer.py

# Test specific functionality
python -m pytest tests/
```

### Adding New Analysis Capabilities

To add new vulnerability types, update the prompt in `tools/tool_extractor.py`:

```python
# In extract_vulnerabilities()
prompt = f"""
...
6. **New Vulnerability Type**: Description of what to look for
   - Detection criteria
   - Attack scenarios
   - Impacts
...
"""
```

## Troubleshooting

### "No LLM API key found"
Set `OPENAI_API_KEY` or `GEMINI_API_KEY` in `.env` file.

### "Analysis incomplete"
- Check logs in `analysis_agent.log`
- Increase `max_turns` if agent runs out of iterations
- Verify code snippets are being extracted correctly

### "Report not generated"
- Ensure all required fields are provided
- Check `reports/` directory permissions
- Review error messages in function returns

## Contributing

When adding new tools:
1. Add function to `tools/` directory
2. Import in `analysis_agent.py`
3. Wrap with `FunctionTool(func=your_function)`
4. Add to agent's tools list
5. Update this README

## License

[Your License Here]

---

**Analysis Agent v2.0** - Powered by LLM-based multi-round analysis
