"""
Legacy decision functions moved from AnalysisAgent

These functions were originally part of the AnalysisAgent class but have been
replaced by the DecisionEngine implementation. They are kept here for reference
and potential future use, but are no longer actively used in the main analysis loop.

All functionality has been moved to:
- DecisionEngine (src/injection_agent/tools/planning/decision_engine.py)
- PromptManager (src/injection_agent/tools/prompt_manager.py)
"""

import json
import re
import os
from typing import Dict, List, Any
from pathlib import Path


class LegacyDecisionFunctions:
    """Container for legacy decision functions from AnalysisAgent"""
    
    def __init__(self, repo_path: str, context, context_manager):
        self.repo_path = Path(repo_path)
        self.context = context
        self.context_manager = context_manager
    
    def parse_llm_decision(self, decision_text: str) -> Dict:
        """Parse LLM decision response - LEGACY VERSION"""
        try:
            import json
            # Extract JSON from response (LLM might add extra text)
            start = decision_text.find('{')
            end = decision_text.rfind('}') + 1
            if start != -1 and end > start:
                json_text = decision_text[start:end]
                return json.loads(json_text)
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            print(f"Failed to parse LLM decision: {e}")
            return {"analysis_targets": [], "strategy_explanation": "parsing_failed"}

    def validate_decisions(self, decisions: Dict, available_files: List[str] = None,
                          available_dirs: List[str] = None, unexplored_subdirs: List[str] = None,
                          decision_type: str = "exploration") -> Dict:
        """Unified validation for LLM decisions - LEGACY VERSION"""
        available_files = available_files or []
        available_dirs = available_dirs or []
        unexplored_subdirs = unexplored_subdirs or []

        # Determine target key based on decision type
        target_key = "analysis_targets" if decision_type == "exploration" else "follow_up_targets"

        if not decisions or target_key not in decisions:
            return {target_key: [], "strategy_explanation": "no_valid_targets"}

        valid_targets = []
        original_count = len(decisions[target_key])

        for target in decisions[target_key]:
            target_path = target.get("path", "")
            target_type = target.get("type", "")

            # Normalize path for better matching
            normalized_path = target_path.strip('/')
            path_parts = normalized_path.split('/')
            item_name = path_parts[-1] if path_parts else ""

            # Validate based on type with improved path matching
            is_valid = False

            if target_type == "file":
                # Check if file exists in available files or can be found in unexplored subdirs
                if item_name in available_files:
                    is_valid = True
                    print(f"  [VALID] {decision_type.title()} file target accepted: {item_name}")
                else:
                    # Check if file might be in an unexplored subdirectory
                    for subdir in unexplored_subdirs:
                        if normalized_path.startswith(subdir) or subdir in normalized_path:
                            is_valid = True
                            print(f"  [VALID] {decision_type.title()} file target in unexplored area: {item_name}")
                            break

                if not is_valid:
                    # Final check: verify file actually exists
                    full_path = self.repo_path / normalized_path
                    if full_path.exists() and full_path.is_file() and not self.context.is_file_analyzed(normalized_path):
                        is_valid = True
                        print(f"  [VALID] {decision_type.title()} file exists and not analyzed: {item_name}")

                if not is_valid:
                    print(f"  [REJECT] {decision_type.title()} file not found or already analyzed: {item_name}")

            elif target_type == "directory":
                # Check if directory exists in available directories or unexplored subdirs
                if item_name in available_dirs:
                    is_valid = True
                    print(f"  [VALID] {decision_type.title()} directory target accepted: {item_name}")
                else:
                    # Check if directory is in unexplored subdirs
                    for subdir in unexplored_subdirs:
                        subdir_normalized = subdir.strip('/')
                        if (item_name == subdir_normalized or
                            normalized_path == subdir_normalized or
                            normalized_path.endswith(subdir_normalized) or
                            subdir_normalized.endswith(normalized_path)):
                            is_valid = True
                            # Use the original path from unexplored list
                            target["path"] = subdir
                            print(f"  [VALID] {decision_type.title()} directory in unexplored areas: {item_name}")
                            break

                if not is_valid:
                    # Final check: verify directory actually exists and is not explored
                    full_path = self.repo_path / normalized_path
                    if full_path.exists() and full_path.is_dir() and not self.context.is_directory_explored(normalized_path):
                        is_valid = True
                        print(f"  [VALID] {decision_type.title()} directory exists and not explored: {item_name}")

                if not is_valid:
                    print(f"  [REJECT] {decision_type.title()} directory not found or already explored: {item_name}")
            else:
                print(f"  [REJECT] Invalid target type: {target_type}")

            if is_valid:
                valid_targets.append(target)

        validated_decisions = decisions.copy()
        validated_decisions[target_key] = valid_targets

        validation_type = "CONTENT" if decision_type == "content" else "EXPLORATION"
        print(f"  [{validation_type} VALIDATION] {len(valid_targets)}/{original_count} targets validated")

        return validated_decisions

    def build_exploration_decision_context(self, explored_path: str, files: List[str], dirs: List[str]) -> Dict:
        """Build exploration decision context - LEGACY VERSION"""
        # Get repository structure for better exploration decisions
        unexplored_areas = []
        root_unexplored = []

        try:
            explored_dirs = list(self.context.get_explored_directories())

            # Get subdirectories of explored directories
            for explored_dir in explored_dirs:
                try:
                    dir_path = self.repo_path / explored_dir
                    if dir_path.exists():
                        for subitem in dir_path.iterdir():
                            if subitem.is_dir() and not subitem.name.startswith('.') and not subitem.name.startswith('__'):
                                subdir_path = f"{explored_dir}/{subitem.name}"
                                if subdir_path not in explored_dirs:
                                    unexplored_areas.append(subdir_path)
                except:
                    continue

            # Also look for important top-level directories that haven't been explored
            for item in (self.repo_path / ".").iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    dir_name = item.name
                    if dir_name not in explored_dirs and dir_name not in ['node_modules', '__pycache__', '.git', 'build', 'dist']:
                        root_unexplored.append(dir_name)

        except Exception:
            pass

        return {
            "explored_path": explored_path,
            "files": files,
            "dirs": dirs,
            "unexplored_areas": unexplored_areas,
            "root_unexplored": root_unexplored
        }

    def execute_decisions(self, decisions: Dict, base_path: str, decision_type: str = "exploration") -> int:
        """通用方法，用于执行LLM的决策并创建任务 - LEGACY VERSION"""
        from ..tools.core.task import Task, TaskType

        # 根据决策类型选择不同的配置
        if decision_type == "exploration":
            target_key = "analysis_targets"
            strategy_key = "strategy_explanation"
            log_message = "Executing LLM decisions"
        else:  # content
            target_key = "follow_up_targets"
            strategy_key = "exploration_strategy"
            log_message = "Executing content follow-up"

        targets = decisions.get(target_key, [])
        executed_count = 0
        strategy_explanation = decisions.get(strategy_key, "No explanation provided")

        print(f"  {log_message}: {strategy_explanation}")

        for target in targets[:6]:  # 限制数量避免过载
            target_path = target.get("path", "")
            target_type = target.get("type", "")
            priority = target.get("priority", "medium")
            reason = target.get("reason", "")

            # 根据决策类型处理路径
            if decision_type == "exploration":
                # Convert relative paths to absolute
                if not target_path.startswith('/'):
                    target_path = f"{base_path.rstrip('/')}/{target_path}"
            else:  # content decision type
                # Convert relative paths to absolute if needed
                if not target_path.startswith('/') and not target_path.startswith('./'):
                    # Assume it's relative to current file's directory
                    current_dir = str(Path(base_path).parent)
                    target_path = f"{current_dir}/{target_path}"

            # Skip already analyzed items
            if target_type == "file" and self.context.is_file_analyzed(target_path):
                continue
            elif target_type == "directory" and self.context.is_directory_explored(target_path):
                continue

            # Validate and normalize target path before creating task
            # Handle malformed paths from LLM (e.g., "././openhands/./openhands/core")
            if target_path.startswith('././'):
                target_path = target_path[4:]  # Remove "././" prefix

            # Remove redundant path segments like "/openhands/./openhands/"
            import re
            target_path = re.sub(r'/\./(?=[^/])', '/', target_path)

            # Basic path validation
            if not target_path or target_path == base_path:
                continue

            # Create appropriate task based on type
            task_priority = {"high": 80, "medium": 60, "low": 40}.get(priority.lower(), 60)
            
            # Note: Task creation would need to be handled by the calling code
            # since we don't have access to task_queue here
            executed_count += 1
            print(f"    [+] {target_type.upper()}: {target_path} ({reason})")

        print(f"  [SUCCESS] Would add {executed_count} tasks based on LLM {decision_type} decisions")
        return executed_count
