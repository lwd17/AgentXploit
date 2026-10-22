# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Decision engine for autonomous analysis decisions
Moved from analysis_agent.py to planning module for better organization
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import os
import json

from ..core.llm_client import LLMClient
from ..core.history_compactor import HistoryCompactor
from ..core.path_manager import PathManager
from ..prompt_manager import PromptManager


class DecisionEngine:
    """Handles autonomous decision making for analysis agent"""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.history_compactor = HistoryCompactor()
        self.path_manager = PathManager(repo_path)
    
    def make_autonomous_decision(self, decision_type: str, context_manager, task_queue, 
                                analyzed_files: set, explored_dirs: set, focus: str = "security", **kwargs) -> Dict[str, Any]:
        """
        Make autonomous decisions based on analysis context
        Returns decision results for trace logging
        """
        decision_result = {
            "decisions_made": 0,
            "tasks_added": 0,
            "decision_details": []
        }
        
        try:
            # Build comprehensive history context
            history_context = self.build_history_context(context_manager, analyzed_files, explored_dirs)
            
            # Decision logic based on type
            if decision_type == "exploration":
                result = self._handle_exploration_decision(
                    history_context, task_queue, kwargs.get('explored_path'), 
                    kwargs.get('files', []), kwargs.get('dirs', []), focus
                )
                decision_result.update(result)
            elif decision_type == "content":
                result = self._handle_content_decision(
                    history_context, task_queue, kwargs.get('file_path'), 
                    kwargs.get('content'), kwargs.get('security_result', {}), focus, **kwargs
                )
                decision_result.update(result)
                
        except Exception as e:
            print(f"  Decision making failed: {e}")
            
        return decision_result

    def build_history_context(self, context_manager, analyzed_files: set, explored_dirs: set) -> str:
        """
        Build comprehensive analysis history context
        Moved from AnalysisAgent._build_history_context
        """
        try:
            overview = context_manager.get_project_overview()
            security_summary = context_manager.get_security_summary()
            
            history = f"""
ANALYSIS HISTORY SUMMARY:
- Total analyzed files: {len(analyzed_files)}
- Total explored directories: {len(explored_dirs)}
- Security findings: {security_summary.get('total_findings', 0)}
  - High risk: {security_summary.get('high_risk_count', 0)}
  - Medium risk: {security_summary.get('medium_risk_count', 0)}
  - Low risk: {security_summary.get('low_risk_count', 0)}

EXPLORED DIRECTORIES (DO NOT RE-EXPLORE):
"""
            
            # List explored directories
            for dir_path in sorted(explored_dirs):
                history += f"- {dir_path}\n"
                
            history += f"\nANALYZED FILES (DO NOT RE-ANALYZE):\n"
            
            # List analyzed files with risk levels
            for file_path in sorted(analyzed_files):
                file_info = context_manager.get_analysis_result(file_path)
                risk = file_info.get('security_risk', 'unknown') if file_info else 'unknown'
                history += f"- {file_path}: {risk} risk\n"
                
            history += f"\nCURRENT ANALYSIS STATE:\n"
            history += f"- Repository root: {self.repo_path}\n"
            
            # Add repository structure overview
            try:
                from ..core.core_tools import EnhancedFileReader
                tools = EnhancedFileReader(str(self.repo_path))
                tree_result = tools.get_tree_structure(".", max_depth=2)
                if "tree_output" in tree_result and not tree_result.get("error"):
                    tree_lines = tree_result["tree_output"].split('\n')[:15]
                    history += f"\nREPOSITORY STRUCTURE OVERVIEW:\n" + "\n".join(tree_lines)
            except Exception:
                pass
                
            # Apply auto-compaction if needed
            compacted_history = self.history_compactor.compact_if_needed(history)
            return compacted_history
            
        except Exception as e:
            return f"Analysis History: Limited context available (error: {e})"
    
    def _handle_exploration_decision(self, history_context: str, task_queue, explored_path: str, 
                                   files: List[str], dirs: List[str], focus: str = "security") -> Dict[str, Any]:
        """Handle exploration-based autonomous decisions with enhanced prompts"""
        result = {"decisions_made": 0, "tasks_added": 0, "decision_details": []}
        
        from ..prompt_manager import PromptManager
        
        # Build exploration context with repository information
        # Validate that explored_path is within the current repository
        repo_abs_path = str(Path(self.repo_path).resolve())
        if explored_path and explored_path != "." and not os.path.isabs(explored_path):
            explored_abs_path = str(Path(self.repo_path, explored_path).resolve())
            if not explored_abs_path.startswith(repo_abs_path):
                # Reset to repository root if path is stale
                explored_path = "."
                print(f"  [PATH_FIX] Reset stale explored_path to repository root")
        
        exploration_context = f"Repository: {Path(self.repo_path).name}, Currently exploring: {explored_path}"
        prompt = PromptManager.get_exploration_decision_prompt(
            history_context=history_context,
            exploration_context=exploration_context,
            unexplored_areas=[],  # 暂时为空，可以后续扩展
            root_unexplored=[],   # 暂时为空，可以后续扩展
            files=files,
            dirs=dirs
        )
        
        model = LLMClient.get_model()
        messages = [
            {"role": "system", "content": "You are an expert code analyzer focused on finding agent tool implementations and dataflow patterns. Make autonomous decisions about what files and directories to analyze based on the current context and focus. Select targets that are most likely to contain relevant tool implementations or data processing logic."},
            {"role": "user", "content": prompt}
        ]
        
        decision_text = LLMClient.call_llm(
            model=model, messages=messages, max_tokens=800, 
            temperature=0.6, timeout=30, max_retries=2
        )
        
        if decision_text:
            decisions = self._parse_llm_decision(decision_text)
            validated_decisions = self._validate_decisions(decisions, files, dirs)
            execution_result = self._execute_llm_decisions(validated_decisions, explored_path, task_queue)
            result.update(execution_result)
        
        return result
    
    def _handle_content_decision(self, history_context: str, task_queue, file_path: str, 
                               content: str, security_result: Dict, focus: str = "security", **kwargs) -> Dict[str, Any]:
        """Handle content-based autonomous decisions with enhanced prompts"""
        result = {"decisions_made": 0, "tasks_added": 0, "decision_details": []}
        
        from ..prompt_manager import PromptManager
        
        # Extract MCP recommendations from kwargs
        mcp_related_files = kwargs.get('mcp_related_files', [])
        mcp_config_files = kwargs.get('mcp_config_files', [])
        
        print(f"  [DECISION_ENGINE] Processing MCP recommendations: {len(mcp_related_files)} related, {len(mcp_config_files)} config")
        
        # Immediately add MCP recommended files with HIGH priority
        mcp_tasks_added = self._add_mcp_recommended_files(task_queue, mcp_related_files, mcp_config_files, file_path)
        if mcp_tasks_added > 0:
            result["tasks_added"] += mcp_tasks_added
            result["decisions_made"] += 1
            result["decision_details"].append({
                "type": "MCP_RECOMMENDATIONS",
                "path": f"{len(mcp_related_files + mcp_config_files)} files",
                "reason": f"MCP Language Server analysis from {Path(file_path).name}",
                "priority": "highest"
            })
            print(f"  [MCP_PRIORITY] Added {mcp_tasks_added} MCP recommended files with HIGHEST priority")
        
        # Build context with available files from current directory  
        context = self._build_content_decision_context(file_path, content, security_result)
        
        # Add MCP recommendations to context
        context['mcp_related_files'] = mcp_related_files
        context['mcp_config_files'] = mcp_config_files
        
        # Get available files from multiple relevant directories for content follow-up
        current_dir = str(Path(file_path).parent) if "/" in file_path else "."
        
        try:
            from ..core.core_tools import EnhancedFileReader
            tools = EnhancedFileReader(self.repo_path)
            
            # Get files from current directory
            current_dir_result = tools.list_directory(current_dir)
            available_files = current_dir_result.get("files", [])
            available_dirs = current_dir_result.get("directories", [])
            
            # For content follow-up, also include related directories at the same level
            parent_dir = str(Path(current_dir).parent) if current_dir != "." else "."
            if parent_dir != current_dir:  # Only if we have a parent
                try:
                    parent_result = tools.list_directory(parent_dir)
                    parent_dirs = parent_result.get("directories", [])
                    
                    # Add sibling directories as potential targets
                    for sibling_dir in parent_dirs:
                        if sibling_dir != Path(current_dir).name:  # Don't include current dir
                            full_sibling_path = f"{parent_dir}/{sibling_dir}" if parent_dir != "." else sibling_dir
                            available_dirs.append(full_sibling_path)
                            
                            # Also check for common related files in sibling directories
                            try:
                                sibling_result = tools.list_directory(full_sibling_path)
                                for file_name in sibling_result.get("files", []):
                                    full_file_path = str(Path(full_sibling_path) / file_name).replace('\\', '/')
                                    available_files.append(full_file_path)
                            except:
                                pass  # Ignore errors accessing sibling directories
                except:
                    pass  # Ignore errors accessing parent directory
            
            context["available_files"] = available_files
            context["available_dirs"] = available_dirs
            
            # Debug logging for content follow-up scope - show ALL files and dirs
            print(f"  [CONTENT_SCOPE] Current dir: {current_dir}")
            print(f"  [CONTENT_SCOPE] Available files count: {len(available_files)}")
            print(f"  [CONTENT_SCOPE] Available dirs count: {len(available_dirs)}")
            if available_files:
                print(f"  [CONTENT_SCOPE] All files: {available_files}")
            if available_dirs:
                print(f"  [CONTENT_SCOPE] All dirs: {available_dirs}")
            
        except:
            context["available_files"] = []
            context["available_dirs"] = []
            
        prompt = PromptManager.get_content_decision_prompt(history_context, context, focus)
        
        model = LLMClient.get_model()
        messages = [
            {"role": "system", "content": "You are an expert code analyzer focused on tool implementations and dataflow tracking. Make autonomous decisions about follow-up analysis based on the current file content and context. Select files and directories that are most likely to contain related tool implementations or continue the dataflow analysis."},
            {"role": "user", "content": prompt}
        ]
        
        decision_text = LLMClient.call_llm(
            model=model, messages=messages, max_tokens=600,
            temperature=0.7, timeout=30, max_retries=2  # Increase temperature for more diverse decisions
        )
        
        if decision_text:
            decisions = self._parse_llm_decision(decision_text)
            # Filter out already analyzed files before execution
            decisions = self._filter_already_analyzed_targets(decisions, history_context)
            # Validate against available files like in exploration
            validated_decisions = self._validate_content_decisions(decisions, context["available_files"], context["available_dirs"])
            execution_result = self._execute_content_follow_up(validated_decisions, file_path, task_queue)
            result.update(execution_result)
        
        return result

    def _add_mcp_recommended_files(self, task_queue, related_files: List[str], config_files: List[str], source_file: str) -> int:
        """Add MCP recommended files to task queue with highest priority"""
        from ..core.task import Task, TaskType, PRIORITY_MAPPING
        
        tasks_added = 0
        all_recommended = related_files + config_files
        
        # Use HIGHEST priority for MCP recommendations (they are LSP-verified dependencies)
        mcp_priority = 98  # Very high priority, just below initial exploration
        
        for recommended_file in all_recommended:
            # Validate file exists and hasn't been analyzed
            full_path = Path(self.repo_path) / recommended_file
            
            try:
                if full_path.exists() and full_path.is_file():
                    # Check if already analyzed or in queue
                    existing_targets = {task.target for task in task_queue.get_pending_tasks()}
                    if recommended_file not in existing_targets:
                        task = Task(type=TaskType.READ, target=recommended_file, priority=mcp_priority)
                        task_queue.add_task(task)
                        tasks_added += 1
                        
                        # Determine recommendation type
                        rec_type = "config reference" if recommended_file in config_files else "code dependency"
                        print(f"    [MCP_PRIORITY] {recommended_file} (priority: {mcp_priority}) - {rec_type} from {Path(source_file).name}")
                    else:
                        print(f"    [MCP_SKIP] {recommended_file} already in queue")
                else:
                    print(f"    [MCP_SKIP] {recommended_file} does not exist")
                    
            except Exception as e:
                print(f"    [MCP_ERROR] Failed to validate {recommended_file}: {e}")
                continue
        
        return tasks_added

    def _build_exploration_decision_context(self, explored_path: str, files: List[str], dirs: List[str]) -> Dict:
        """Build context for exploration decisions"""
        return {
            "explored_path": explored_path,
            "files_count": len(files),
            "dirs_count": len(dirs),
            "files": files[:10],  # First 10 files
            "dirs": dirs[:5]      # First 5 directories
        }
    
    def _build_content_decision_context(self, file_path: str, content: str, security_result: Dict) -> Dict:
        """Build context for content decisions"""
        return {
            "file_path": file_path,
            "content": content,
            "security_result": security_result,
            "content_length": len(content),
            "security_risk": security_result.get('risk_level', 'unknown'),
            "key_findings": security_result.get('findings', [])[:3]  # First 3 findings
        }
    
    def _build_exploration_decision_prompt(self, history_context: str, context: Dict) -> str:
        """Build prompt for exploration decisions"""
        return f"""Based on the analysis history and current exploration context, make autonomous decisions about what to analyze next.

{history_context}

CURRENT EXPLORATION CONTEXT:
- Explored Path: {context['explored_path']}
- Files Found: {context['files_count']}
- Directories Found: {context['dirs_count']}

**AVAILABLE FILES (you MUST only choose from this list):**
{chr(10).join([f"- {file}" for file in context['files']])}

**AVAILABLE DIRECTORIES (you MUST only choose from this list):**
{chr(10).join([f"- {dir_name}" for dir_name in context['dirs']])}

DECISION INSTRUCTIONS:
1. **CRITICAL**: You can ONLY select files and directories from the lists above - NO OTHER FILES
2. Choose up to 3 high-priority files for agent workflow and data flow analysis
3. Choose up to 2 directories to explore if they contain agent components
4. Focus on: tool definitions, agent configurations, data processing pipelines, LLM interfaces
5. Prioritize files that handle external input or tool outputs
6. Avoid files/directories already analyzed (see history above)

Respond ONLY in JSON format using EXACT names from the available lists:
{{"read_files": ["exact_filename1", "exact_filename2"], "explore_dirs": ["exact_dirname1", "exact_dirname2"]}}"""

    def _build_content_decision_prompt(self, history_context: str, context: Dict) -> str:
        """Build prompt for content decisions"""
        return f"""Based on the analysis history and current file analysis, make decisions about follow-up analysis.

{history_context}

CURRENT FILE ANALYSIS CONTEXT:
- File: {context['file_path']}
- Security Risk: {context['security_risk']}
- Key Findings: {', '.join(context.get('key_findings', []))}

DECISION INSTRUCTIONS:
1. **IMPORTANT**: Do NOT suggest specific file names - we will explore directories to find related files
2. Instead, suggest directories to explore for related components
3. Focus on agent workflow analysis: data flow, tool chains, LLM interfaces
4. Look for injection points where external data enters the agent pipeline

Respond ONLY in JSON format:
{{"explore_dirs": ["directory_to_explore"], "analysis_focus": ["data_flow", "tool_interfaces", "llm_input_handling"]}}"""

    def _parse_llm_decision(self, decision_text: str) -> Dict:
        """Parse LLM decision from text response"""
        try:
            # Extract JSON from response
            start_idx = decision_text.find('{')
            end_idx = decision_text.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = decision_text[start_idx:end_idx]
                return json.loads(json_str)
            return {}
        except:
            return {}
    
    def _filter_already_analyzed_targets(self, decisions: Dict, history_context: str) -> Dict:
        """Filter out targets that have already been analyzed according to history context"""
        if not history_context:
            return decisions
            
        # Extract already analyzed files from history context
        analyzed_files = set()
        analyzed_dirs = set()
        
        lines = history_context.split('\n')
        in_analyzed_section = False
        in_explored_section = False
        
        for line in lines:
            line = line.strip()
            if 'ANALYZED FILES' in line:
                in_analyzed_section = True
                in_explored_section = False
                continue
            elif 'EXPLORED DIRECTORIES' in line:
                in_explored_section = True
                in_analyzed_section = False
                continue
            elif line.startswith('-') and (in_analyzed_section or in_explored_section):
                # Extract file/directory path
                path_part = line[1:].strip()
                if ':' in path_part:
                    path_part = path_part.split(':')[0].strip()
                if in_analyzed_section:
                    analyzed_files.add(path_part)
                else:
                    analyzed_dirs.add(path_part)
            elif line and not line.startswith('-') and (in_analyzed_section or in_explored_section):
                in_analyzed_section = False
                in_explored_section = False
        
        # Filter follow_up_targets
        filtered_decisions = decisions.copy()
        if 'follow_up_targets' in decisions:
            filtered_targets = []
            for target in decisions['follow_up_targets']:
                if isinstance(target, dict):
                    target_path = target.get('path', '')
                    target_type = target.get('type', 'file')
                    
                    if target_type == 'file' and target_path not in analyzed_files:
                        filtered_targets.append(target)
                    elif target_type == 'directory' and target_path not in analyzed_dirs:
                        filtered_targets.append(target)
                    # Skip if already analyzed
                else:
                    filtered_targets.append(target)  # Keep non-dict targets as-is
            filtered_decisions['follow_up_targets'] = filtered_targets
        
        # Filter explore_dirs (legacy support)
        if 'explore_dirs' in decisions:
            filtered_dirs = [d for d in decisions['explore_dirs'] if d not in analyzed_dirs]
            filtered_decisions['explore_dirs'] = filtered_dirs
            
        return filtered_decisions
    
    def _validate_decisions(self, decisions: Dict, available_files: List[str] = None, 
                          available_dirs: List[str] = None) -> Dict:
        """Validate LLM decisions with improved path matching"""
        validated = {"analysis_targets": [], "strategy_explanation": ""}
        
        # Extract strategy explanation
        validated["strategy_explanation"] = decisions.get("strategy_explanation", "No strategy provided")
        
        # Validate and convert analysis targets
        analysis_targets = decisions.get("analysis_targets", [])
        if isinstance(analysis_targets, list):
            for target in analysis_targets[:6]:  # Limit to 6 targets
                if isinstance(target, dict) and "path" in target:
                    target_path = target["path"].strip()  # Clean up any whitespace
                    target_type = target.get("type", "file")
                    
                    # No hallucination check - trust LLM to use exact names from lists
                    
                    print(f"  [VALIDATION_DEBUG] Checking {target_type}: '{target_path}'")
                    
                    # Smart type correction: if LLM type is wrong, auto-correct based on available lists
                    corrected_type = target_type
                    is_valid = False
                    
                    # Enhanced path matching - check for exact matches and relative path matches
                    file_match = False
                    dir_match = False
                    
                    if available_files:
                        # Direct match
                        file_match = target_path in available_files
                        # Also check for basename match (for cases where paths might be relative)
                        if not file_match:
                            target_basename = target_path.split('/')[-1]
                            file_match = any(f.endswith('/' + target_basename) or f == target_basename for f in available_files)
                    
                    if available_dirs:
                        # Direct match
                        dir_match = target_path in available_dirs
                        # Also check for basename match
                        if not dir_match:
                            target_basename = target_path.split('/')[-1]
                            dir_match = any(d.endswith('/' + target_basename) or d == target_basename for d in available_dirs)
                    
                    print(f"    File match: {file_match}, Dir match: {dir_match}")
                    print(f"    Target path: '{target_path}'")
                    
                    # Auto-correct type based on actual availability
                    if file_match and not dir_match:
                        corrected_type = "file"
                        is_valid = True
                        if target_type != "file":
                            print(f"    [AUTO_CORRECT] Type corrected from '{target_type}' to 'file'")
                    elif dir_match and not file_match:
                        corrected_type = "directory"
                        is_valid = True
                        if target_type != "directory":
                            print(f"    [AUTO_CORRECT] Type corrected from '{target_type}' to 'directory'")
                    elif file_match and dir_match:
                        # If both match (rare case), prefer the original LLM type
                        is_valid = True
                        print(f"    [AMBIGUOUS] Path exists in both lists, keeping original type: {target_type}")
                    else:
                        print(f"  [VALIDATION] Path '{target_path}' not found in available files or dirs")
                        if available_files and len(available_files) <= 10:
                            print(f"    Available files: {available_files}")
                        elif available_files:
                            print(f"    Available files (first 10): {available_files[:10]}")
                        if available_dirs and len(available_dirs) <= 10:
                            print(f"    Available dirs: {available_dirs}")
                        elif available_dirs:
                            print(f"    Available dirs (first 10): {available_dirs[:10]}")
                    
                    # Update the target with corrected type
                    if is_valid:
                        target["type"] = corrected_type
                    
                    if is_valid:
                        validated["analysis_targets"].append(target)
                        print(f"  [VALIDATION] Accepted {corrected_type}: {target_path}")
                    else:
                        print(f"  [VALIDATION] Rejected {target_type}: {target_path} (not in available lists)")
        
        print(f"  [VALIDATION] {len(validated['analysis_targets'])}/{len(analysis_targets)} targets validated")
        return validated

    def _validate_content_decisions(self, decisions: Dict, available_files: List[str] = None, 
                                   available_dirs: List[str] = None) -> Dict:
        """Validate content follow-up decisions against available files"""
        validated = {"follow_up_targets": []}
        
        follow_up_targets = decisions.get("follow_up_targets", [])
        if isinstance(follow_up_targets, list):
            for target in follow_up_targets:
                if isinstance(target, dict) and "path" in target:
                    target_path = target["path"].strip()  # Clean up any whitespace
                    target_type = target.get("type", "file")
                    
                    # No hallucination check - trust LLM to use exact names from lists
                    
                    print(f"  [CONTENT_VALIDATION] Checking {target_type}: '{target_path}'")
                    
                    # Smart type correction for content follow-up
                    corrected_type = target_type
                    is_valid = False
                    
                    # Enhanced path matching - check for exact matches and relative path matches
                    file_match = False
                    dir_match = False
                    
                    if available_files:
                        # Direct match
                        file_match = target_path in available_files
                        # Also check for basename match (for cases where paths might be relative)
                        if not file_match:
                            target_basename = target_path.split('/')[-1]
                            file_match = any(f.endswith('/' + target_basename) or f == target_basename for f in available_files)
                    
                    if available_dirs:
                        # Direct match
                        dir_match = target_path in available_dirs
                        # Also check for basename match
                        if not dir_match:
                            target_basename = target_path.split('/')[-1]
                            dir_match = any(d.endswith('/' + target_basename) or d == target_basename for d in available_dirs)
                    
                    print(f"    File match: {file_match}, Dir match: {dir_match}")
                    print(f"    Target path: '{target_path}'")
                    if available_files and len(available_files) <= 10:
                        print(f"    Available files: {available_files}")
                    if available_dirs and len(available_dirs) <= 10:
                        print(f"    Available dirs: {available_dirs}")
                    
                    # Auto-correct type based on actual availability
                    if file_match and not dir_match:
                        corrected_type = "file"
                        is_valid = True
                        if target_type != "file":
                            print(f"    [CONTENT_AUTO_CORRECT] Type corrected from '{target_type}' to 'file'")
                    elif dir_match and not file_match:
                        corrected_type = "directory"
                        is_valid = True
                        if target_type != "directory":
                            print(f"    [CONTENT_AUTO_CORRECT] Type corrected from '{target_type}' to 'directory'")
                    elif file_match and dir_match:
                        # If both match, prefer the original LLM type
                        is_valid = True
                        print(f"    [CONTENT_AMBIGUOUS] Path exists in both lists, keeping original type: {target_type}")
                    else:
                        print(f"  [CONTENT_VALIDATION] Path '{target_path}' not found in available files or dirs")
                        if available_files:
                            print(f"    Available files: {available_files}")
                        if available_dirs:
                            print(f"    Available dirs: {available_dirs}")
                    
                    # Update the target with corrected type
                    if is_valid:
                        target["type"] = corrected_type
                    
                    if is_valid:
                        validated["follow_up_targets"].append(target)
                        print(f"  [CONTENT_VALIDATION] Accepted {corrected_type}: {target_path}")
                    else:
                        print(f"  [CONTENT_VALIDATION] Rejected {target_type}: {target_path} (not available)")
        
        print(f"  [CONTENT_VALIDATION] {len(validated['follow_up_targets'])}/{len(follow_up_targets)} targets validated")
        return validated
    
    def _execute_llm_decisions(self, decisions: Dict, explored_path: str, task_queue) -> Dict[str, Any]:
        """Execute validated LLM decisions using unified path manager"""
        from ..core.task import Task, TaskType
        
        result = {
            "decisions_made": 0,
            "tasks_added": 0,
            "decision_details": []
        }
        
        # Process analysis targets from validated decisions using path manager
        analysis_targets = decisions.get("analysis_targets", [])
        if analysis_targets:
            # Resolve all paths using the unified path manager
            resolved_targets = self.path_manager.resolve_exploration_paths(analysis_targets, explored_path)
            
            for target in resolved_targets:
                target_path = target.get("path", "")
                original_path = target.get("original_path", target_path)
                target_type = target.get("type", "file")
                priority_level = target.get("priority", "medium")
                reason = target.get("reason", "LLM autonomous decision")
                
                print(f"  [PATH_MANAGER] Resolved {target_type}: '{original_path}' -> '{target_path}'")
                
                # Assign priority directly based on LLM selection - unified mapping
                from ..core.task import PRIORITY_MAPPING
                priority = PRIORITY_MAPPING.get(priority_level, PRIORITY_MAPPING["default"])
                
                # Create appropriate task
                if target_type == "file":
                    task = Task(
                        type=TaskType.READ, 
                        target=target_path, 
                        priority=priority,
                        focus_driven=True
                    )
                else:  # directory
                    task = Task(
                        type=TaskType.EXPLORE, 
                        target=target_path, 
                        priority=priority,
                        focus_driven=True
                    )
                
                task_queue.add_task(task)
                result["tasks_added"] += 1
                result["decision_details"].append({
                    "type": target_type,
                    "path": target_path,
                    "original_path": original_path,
                    "priority": priority,
                    "reason": reason
                })
        
        result["decisions_made"] = len(analysis_targets)
        return result
    
    def _execute_content_follow_up(self, decisions: Dict, current_file_path: str, task_queue) -> Dict[str, Any]:
        """Execute content-based follow-up decisions with unified path manager"""
        from ..core.task import Task, TaskType
        
        result = {
            "decisions_made": 0,
            "tasks_added": 0,
            "decision_details": []
        }
        
        # Use path manager to handle content follow-up paths correctly
        follow_up_files = decisions.get("follow_up_targets", [])
        if follow_up_files:
            # Resolve all paths using the unified path manager with current file context
            resolved_targets = self.path_manager.resolve_content_follow_up_paths(follow_up_files, current_file_path)
            
            for target_info in resolved_targets:
                target_path = target_info.get("path", "")
                original_path = target_info.get("original_path", target_path)
                target_type = target_info.get("type", "file")
                priority_str = target_info.get("priority", "medium")  # Get LLM-generated priority
                reason = target_info.get("reason", "content-based follow-up")
                
                # Convert LLM priority to numeric value
                from ..core.task import PRIORITY_MAPPING
                if isinstance(priority_str, str):
                    priority = PRIORITY_MAPPING.get(priority_str, PRIORITY_MAPPING["default"])
                else:
                    priority = int(priority_str) if isinstance(priority_str, (int, float)) else PRIORITY_MAPPING["default"]
                
                print(f"  [CONTENT_FOLLOW_UP] Resolved {target_type}: '{original_path}' -> '{target_path}' (LLM priority: {priority_str} -> {priority})")
                
                # Create task with LLM-determined priority
                if target_type == "file":
                    task = Task(TaskType.READ, target_path, priority=priority)
                    task_queue.add_task(task)
                    print(f"  [CONTENT_FOLLOW_UP] Added READ task: {target_path} (priority: {priority})")
                    result["tasks_added"] += 1
                    result["decision_details"].append({
                        "type": "file",
                        "path": target_path,
                        "original_path": original_path,
                        "reason": reason,
                        "llm_priority": priority_str
                    })
                elif target_type == "directory":
                    task = Task(TaskType.EXPLORE, target_path, priority=priority)
                    task_queue.add_task(task)
                    print(f"  [CONTENT_FOLLOW_UP] Added EXPLORE task: {target_path} (priority: {priority})")
                    result["tasks_added"] += 1
                    result["decision_details"].append({
                        "type": "directory",
                        "path": target_path,
                        "original_path": original_path,
                        "reason": reason
                    })
        
        # Note: Legacy explore_dirs format removed - all decisions now use follow_up_targets with LLM-generated priorities
        
        result["decisions_made"] = len(follow_up_files)
        
        if result["decisions_made"] > 0:
            print(f"  [CONTENT-AUTONOMOUS] Added {result['tasks_added']} content follow-up tasks")
        
        return result
    
    def autonomous_context_reassessment(self, context_manager, task_queue, context, tools, focus: str) -> None:
        """LLM-driven strategic context reassessment - moved from AnalysisAgent"""
        try:
            print("LLM-Driven Context Reassessment...")

            # Get comprehensive analysis history for LLM context
            analyzed_files = set(context.get_analyzed_files())
            explored_dirs = set(context.get_explored_directories())
            history_context = self.build_history_context(context_manager, analyzed_files, explored_dirs)

            # Gather current state information
            overview = context_manager.get_project_overview()
            analyzed_files_list = list(analyzed_files)
            explored_dirs_list = list(explored_dirs)
            security_summary = context_manager.get_security_summary()

            # Calculate coverage
            total_files = overview.get('total_files', 0)
            coverage = len(analyzed_files_list) / max(total_files, 1)

            current_state = {
                'analyzed_files': len(analyzed_files_list),
                'explored_dirs': len(explored_dirs_list),
                'high_risk_count': security_summary.get('high_risk_count', 0),
                'total_files': total_files,
                'coverage': coverage
            }

            # Find unexplored areas
            unexplored_root_dirs = []
            unexplored_subdirs = []

            try:
                # Get root directories
                root_list = tools.list_directory(".")
                if "error" not in root_list:
                    root_dirs = root_list.get("directories", [])
                    for dir_name in root_dirs:
                        if (not dir_name.startswith('.') and
                            dir_name not in explored_dirs and
                            dir_name not in ['node_modules', '__pycache__', '.git', 'build', 'dist']):
                            unexplored_root_dirs.append(dir_name)

                # Get unexplored subdirectories
                for explored_dir in explored_dirs_list:
                    try:
                        dir_result = tools.list_directory(explored_dir)
                        if "error" not in dir_result:
                            subdirs = dir_result.get("directories", [])
                            for subdir in subdirs:
                                if (not subdir.startswith('.') and
                                        subdir not in ['node_modules', '__pycache__', '.git', 'build', 'dist']):
                                    subdir_path = str(Path(explored_dir) / subdir).replace('\\', '/')
                                    if not context.is_directory_explored(subdir_path):
                                        unexplored_subdirs.append(subdir_path)
                    except:
                        continue
            except Exception as e:
                print(f"  Error gathering unexplored areas: {e}")

            # Use LLM for strategic decision making
            model = LLMClient.get_model()
            reassessment_prompt = PromptManager.get_context_reassessment_prompt(
                history_context=history_context,
                current_state=current_state,
                unexplored_root_dirs=unexplored_root_dirs,
                unexplored_subdirs=unexplored_subdirs,
                task_queue_size=task_queue.size(),
                focus=focus  # Use dynamic focus passed from caller
            )

            messages = [
                {"role": "system", "content": "You are a senior security strategist making intelligent analysis decisions based on current context and strategic goals."},
                {"role": "user", "content": reassessment_prompt}
            ]

            decision_text = LLMClient.call_llm(
                model=model,
                messages=messages,
                max_tokens=1000,
                temperature=0.4,
                timeout=30,
                max_retries=2
            )

            if decision_text:
                try:
                    start = decision_text.find('{')
                    end = decision_text.rfind('}') + 1
                    if start != -1 and end > start:
                        json_text = decision_text[start:end]
                        decisions = json.loads(json_text)

                        # Execute LLM-driven strategic decisions
                        self._execute_reassessment_decisions(decisions, unexplored_root_dirs, unexplored_subdirs, task_queue)
                        print("  [SUCCESS] LLM-driven context reassessment completed")

                except Exception as e:
                    print(f"  [ERROR] Failed to parse LLM reassessment: {e}")
                    # # Fallback to minimal exploration if needed (COMMENTED OUT FOR TESTING)
                    # if task_queue.size() == 0 and unexplored_root_dirs:
                    #     from ..core.task import Task, TaskType
                    #     task = Task(TaskType.EXPLORE, unexplored_root_dirs[0], priority=5)
                    #     task_queue.add_task(task)
                    print("  LLM reassessment failed")

        except Exception as e:
            print(f"  Context reassessment failed: {e}")

    def _execute_reassessment_decisions(self, decisions: Dict, unexplored_root_dirs: List[str], 
                                      unexplored_subdirs: List[str], task_queue) -> None:
        """Execute strategic reassessment decisions with proper next_actions format support"""
        from ..core.task import Task, TaskType
        
        tasks_added = 0
        
        # Parse new next_actions format with unified validation
        next_actions = decisions.get("next_actions", [])
        if next_actions:
            print(f"  [LLM-DECISION] Processing {len(next_actions)} strategic actions...")
            
            for action_info in next_actions[:4]:  # Limit to 4 actions for sustained analysis
                if not isinstance(action_info, dict):
                    print(f"    [SKIP] Invalid action format: {action_info}")
                    continue
                    
                action = action_info.get("action", "").strip()
                target = action_info.get("target", "").strip()
                priority_str = action_info.get("priority", "medium").strip().lower()
                reason = action_info.get("reason", "LLM strategic decision")
                expected_value = action_info.get("expected_value", "general")
                
                if not target or not action:
                    print(f"    [SKIP] Missing action or target: action='{action}', target='{target}'")
                    continue
                
                # Use unified path validation and resolution
                normalized_target, is_valid, validation_reason = self.path_manager.validate_and_resolve_target(target, action)
                if not is_valid:
                    print(f"    [SKIP] {validation_reason}: {target}")
                    continue
                
                # Unified priority mapping across all components
                from ..core.task import PRIORITY_MAPPING
                priority = PRIORITY_MAPPING.get(priority_str, PRIORITY_MAPPING["default"])
                
                # Additional context validation for exploration
                if action == "explore_directory":
                    # Check if target is in unexplored areas or reasonably accessible
                    context_valid = (
                        any(target in area_list for area_list in [unexplored_root_dirs, unexplored_subdirs]) or
                        len(normalized_target.split("/")) <= 4  # Allow reasonable depth
                    )
                    if not context_valid:
                        print(f"    [SKIP] Path not in exploration context: {target}")
                        continue
                
                # Create and add task
                if action == "explore_directory":
                    task = Task(TaskType.EXPLORE, normalized_target, priority=priority)
                    action_display = "EXPLORE"
                elif action == "analyze_file":
                    task = Task(TaskType.READ, normalized_target, priority=priority)
                    action_display = "READ"
                else:
                    print(f"    [SKIP] Unknown action: {action}")
                    continue
                
                task_queue.add_task(task)
                tasks_added += 1
                print(f"    [+] {action_display} {normalized_target} (priority: {priority}) - {reason}")
        
        if tasks_added > 0:
            print(f"  [SUCCESS] Added {tasks_added} strategic LLM-driven tasks to queue")
        else:
            print("  [WARNING] No valid tasks extracted from LLM decisions - relying on LLM autonomy")