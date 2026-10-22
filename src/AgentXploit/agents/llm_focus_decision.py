#!/usr/bin/env python3
"""
LLM Focus Decision Maker
Fully autonomous focus generation and path selection driven by LLM
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from litellm import completion


def _serialize_findings(findings: List) -> List[Dict]:
    """Convert SecurityFinding objects to dicts for JSON serialization"""
    serialized = []
    for finding in findings:
        if hasattr(finding, "to_dict"):
            serialized.append(finding.to_dict())
        elif isinstance(finding, dict):
            serialized.append(finding)
        else:
            # Fallback: try to extract basic info
            serialized.append({"description": str(finding)})
    return serialized


def _is_valid_path(path: str) -> bool:
    """Validate path format - reject commands, URLs, paths with spaces"""
    if not path or not isinstance(path, str):
        return False

    # Reject paths with spaces (likely commands)
    if " " in path:
        return False

    # Reject command symbols
    if any(c in path for c in ["|", "&", ";", ">", "<", "$", "`", "\n", "\r"]):
        return False

    # Reject URLs
    if path.startswith(("http://", "https://", "ftp://", "file://")):
        return False

    # Reject command-line parameters
    if path.startswith(("--", "-")) or path.endswith(("--", "-")):
        return False

    # Reject absolute paths outside typical project structures
    # (allow relative paths and paths starting with common project dirs)
    if path.startswith("/") and not any(
        path.startswith(p) for p in ["/srv/", "/home/", "/app/", "/workspace/"]
    ):
        return False

    return True


class LLMFocusDecisionMaker:
    """LLM-driven focus generation and investigation path selection"""

    def __init__(self, model_name: str = None):
        """Initialize LLM decision maker"""
        self.model_name = model_name or os.getenv("LLM_HELPER_MODEL", "openai/gpt-4o")

    def generate_initial_focus(
        self,
        repo_structure: Dict[str, Any],
        initial_findings: List[Dict] = None,
        analysis_goal: str = "",
    ) -> Dict[str, Any]:
        """
        Generate initial investigation focus based on repository structure

        Returns:
            {
                'focus_description': str,  # Free-form focus description
                'priority': int,           # 1-100
                'reason': str,             # Why this focus was chosen
                'suggested_targets': List[str]  # Initial paths to investigate
            }
        """
        prompt = f"""You are an AGENT SECURITY expert analyzing vulnerabilities in AI agent systems.

**ANALYSIS SCOPE: Agent Tool Use & Dataflow Security**

This analysis focuses on:
1. **Agent Tool Implementations** - Functions that AI agents can call/execute
2. **Dataflow Analysis** - How external data flows through tools to LLMs
3. **Indirect Prompt Injection** - External input affecting agent prompts/behavior
4. **Tool Output Handling** - Unsanitized tool outputs feeding into LLM prompts

Repository Structure:
- Directories explored: {repo_structure.get("directories", [])}
- Files found: {repo_structure.get("files", [])}
- Total items: {len(repo_structure.get("directories", []))} dirs, {len(repo_structure.get("files", []))} files

Analysis Goal: {analysis_goal or "Agent security - tool use and dataflow vulnerabilities"}

Initial Findings: {json.dumps(_serialize_findings(initial_findings or []), indent=2)}

Generate an AGENT-SPECIFIC security focus. Return ONLY a JSON object with this structure:
{{
    "focus_description": "A clear, specific description of what to investigate (e.g., 'Authentication flow and session management vulnerabilities', 'Data validation in user input handlers')",
    "priority": <1-100 integer>,
    "reason": "Why this focus is important for finding vulnerabilities",
    "suggested_targets": ["list", "of", "specific", "paths", "to", "start", "investigating"]
}}

**FOCUS REQUIREMENTS - Must be AGENT-SPECIFIC:**
✓ "Dataflow from file tool outputs to LLM prompts - indirect injection risk"
✓ "Tool parameter validation in agent command executors"
✓ "External API responses feeding into prompt construction"
✓ "User input handling in agent tool implementations"
✗ "General code quality issues" (too broad, not agent-specific)
✗ "Configuration file vulnerabilities" (not focused on agent tools/dataflow)

**PATH FORMAT REQUIREMENTS for suggested_targets:**
- ONLY valid paths: "src/tools/file_reader.py", "agents/executor.py"
- NO commands: ✗ "docker run", NO parameters: ✗ "--flag"
- Prioritize: tool implementations, dataflow handlers, prompt construction code

**SELECT PATHS WHERE:**
- Agent tools are implemented (functions agents can call)
- External input flows to LLMs (files, APIs, user input → prompts)
- Tool outputs are used in prompts without sanitization

Focus on AGENT TOOL USE and DATAFLOW to identify indirect prompt injection vulnerabilities."""

        try:
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            # Validate structure and normalize field names
            required_keys = ["focus_description", "priority", "suggested_targets"]
            if not all(k in result for k in required_keys):
                raise ValueError(
                    f"Missing required keys in LLM response. Got: {result.keys()}"
                )

            # Normalize 'reasoning' to 'reason' for consistency
            if "reasoning" in result and "reason" not in result:
                result["reason"] = result.pop("reasoning")
            elif "reason" not in result:
                result["reason"] = "LLM-generated focus"

            return result

        except Exception as e:
            print(f"  [LLM_FOCUS_ERROR] Failed to generate initial focus: {e}")
            # Fallback to basic focus
            return {
                "focus_description": analysis_goal
                or "General security vulnerability analysis",
                "priority": 50,
                "reason": "Default focus due to LLM error",
                "suggested_targets": repo_structure.get("files", [])[:3],
            }

    def update_focus_from_context(
        self,
        current_focus: Dict[str, Any],
        recent_findings: List[Dict],
        explored_paths: List[str],
        analyzed_files: List[str],
    ) -> Dict[str, Any]:
        """
        Update or shift focus based on recent discoveries

        Returns:
            {
                'action': 'keep' | 'update' | 'shift',
                'focus_description': str,  # Updated focus (if action != 'keep')
                'priority': int,
                'reason': str
            }
        """
        prompt = f"""You are guiding a security vulnerability analysis. Based on recent findings and progress, decide whether to keep, update, or shift the investigation focus.

Current Focus:
- Description: {current_focus.get("focus_description", "Unknown")}
- Priority: {current_focus.get("priority", 50)}

Recent Findings ({len(recent_findings)} total):
{json.dumps(_serialize_findings(recent_findings[:5]), indent=2)}

Progress:
- Explored paths: {len(explored_paths)} directories
- Analyzed files: {len(analyzed_files)} files
- Recent paths: {explored_paths[-5:] if explored_paths else []}

Based on the findings and progress, decide:
- 'keep': Continue with current focus (it's still productive)
- 'update': Refine/narrow the current focus based on discoveries
- 'shift': Change to a completely new focus area

Return ONLY a JSON object:
{{
    "action": "keep" | "update" | "shift",
    "focus_description": "Updated focus description (only if action != 'keep')",
    "priority": <1-100 integer>,
    "reason": "Why this decision was made"
}}"""

        try:
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            # If keeping focus, preserve current description
            if result.get("action") == "keep":
                result["focus_description"] = current_focus.get("focus_description", "")

            # Normalize 'reasoning' to 'reason' for consistency
            if "reasoning" in result and "reason" not in result:
                result["reason"] = result.pop("reasoning")
            elif "reason" not in result:
                result["reason"] = "LLM decision"

            return result

        except Exception as e:
            print(f"  [LLM_FOCUS_ERROR] Failed to update focus: {e}")
            return {
                "action": "keep",
                "focus_description": current_focus.get("focus_description", ""),
                "priority": current_focus.get("priority", 50),
                "reason": "Keeping focus due to LLM error",
            }

    def select_investigation_paths(
        self,
        current_focus: Dict[str, Any],
        available_paths: Dict[str, List[str]],
        recent_findings: List[Dict],
        failed_paths: List[str] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Select next investigation targets based on current focus

        Args:
            current_focus: Current investigation focus
            available_paths: {'directories': [...], 'files': [...]}
            recent_findings: Recent security findings
            failed_paths: Paths that previously failed
            limit: Maximum number of targets to return

        Returns:
            [
                {
                    'path': str,
                    'action': 'analyze_file' | 'explore_directory',
                    'priority': int,
                    'reason': str
                },
                ...
            ]
        """
        failed_paths = failed_paths or []

        # Filter out failed paths from available paths
        available_dirs = [
            d for d in available_paths.get("directories", []) if d not in failed_paths
        ]
        available_files = [
            f for f in available_paths.get("files", []) if f not in failed_paths
        ]

        prompt = f"""You are selecting targets for AGENT SECURITY analysis focusing on tool use and dataflow.

**Current Analysis Focus:** {current_focus.get("focus_description", "Unknown")}

**Available Paths:**
Directories ({len(available_dirs)}): {available_dirs}
Files ({len(available_files)}): {available_files}

**Recent Findings:** {json.dumps(_serialize_findings(recent_findings), indent=2)}

**Failed Paths (avoid):** {failed_paths}

**SELECT {limit} PATHS WITH HIGHEST AGENT SECURITY VALUE:**

**Priority 1 - Agent Tool Implementations:**
- Files containing tool/function definitions agents can call
- Command executors, file processors, API clients
- Look for: "tool", "executor", "handler", "processor", "client"

**Priority 2 - Dataflow & Prompt Construction:**
- Code that merges external data into LLM prompts
- Files reading user input/files/APIs and passing to agents
- Look for: "prompt", "template", "message", "context", "format"

**Priority 3 - Indirect Injection Vectors:**
- External input sources (file readers, API clients, parsers)
- Tool output handlers that feed data to prompts
- Look for: "read", "fetch", "parse", "response", "output"

**Avoid:**
- Generic utilities without agent interaction
- Pure data models/schemas
- Static configuration files (unless they control tool behavior)

Return ONLY a JSON array of targets:
[
    {{
        "path": "exact/path/from/available/paths",
        "action": "analyze_file" OR "explore_directory",
        "priority": <1-100 integer>,
        "reason": "Why this path is relevant to current focus"
    }}
]

**PATH REQUIREMENTS:**
- Choose ONLY from available paths above

**SELECTION CRITERIA:**
Focus on paths where EXTERNAL INPUT could affect AGENT BEHAVIOR or LLM PROMPTS.
Prioritize: tool implementations > dataflow handlers > prompt construction.

Return empty [] if no agent-security-relevant paths available."""

        try:
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON array
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            targets = json.loads(result_text)

            if not isinstance(targets, list):
                raise ValueError(f"Expected array, got: {type(targets)}")

            # Validate and filter targets
            valid_targets = []
            for target in targets[:limit]:
                if not isinstance(target, dict):
                    continue

                path = target.get("path", "")
                if not path or path in failed_paths:
                    continue

                # CRITICAL: Validate path format (reject commands, URLs, invalid paths)
                if not _is_valid_path(path):
                    print(f"  [PATH_VALIDATION_FAILED] Rejected invalid path: {path}")
                    continue

                # Verify path exists in available paths
                if path not in available_dirs and path not in available_files:
                    continue

                # Auto-determine action if not specified
                if "action" not in target:
                    target["action"] = (
                        "analyze_file"
                        if path in available_files
                        else "explore_directory"
                    )

                # Normalize 'reasoning' to 'reason' for consistency
                if "reasoning" in target and "reason" not in target:
                    target["reason"] = target.pop("reasoning")
                elif "reason" not in target:
                    target["reason"] = "LLM selected path"

                valid_targets.append(target)

            return valid_targets

        except Exception as e:
            print(f"  [LLM_PATH_SELECT_ERROR] Failed to select paths: {e}")
            # Fallback: return first available paths
            fallback = []
            for file_path in available_files[:limit]:
                fallback.append(
                    {
                        "path": file_path,
                        "action": "analyze_file",
                        "priority": 50,
                        "reason": "Fallback selection due to LLM error",
                    }
                )
            return fallback
