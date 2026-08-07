import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import asdict

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from ..config import settings

# Core analysis components
from ..tools.core.analysis_context import AnalysisContext
from ..tools.core.task import Task, TaskType
from ..tools.core.task_queue import TaskQueue
from ..tools.core.execution_logger import ExecutionLogger
from ..tools.prompt_manager import PromptManager

# Planning and context tools
from ..tools.planning.analysis_context_manager import AnalysisContextManager
from ..tools.planning.context_tools import initialize_analysis_context
from ..tools.planning.decision_engine import DecisionEngine
from .exploration_strategies import ExplorationStrategies
from .focus_tracker import FocusTracker, AnalysisFocus
from .dynamic_focus_manager import DynamicFocusManager
from .llm_focus_decision import LLMFocusDecisionMaker
# from .fallback_strategies import FallbackAnalysisStrategies  # DISABLED: Using only LLM-driven decisions


# Import LLM client from core module
from ..tools.core.llm_client import LLMClient
from ..tools.core.history_compactor import HistoryCompactor
from .mcp_agent import get_runner


def serialize_for_json(obj):
    """Convert dataclass objects and other non-serializable objects to dict"""
    if hasattr(obj, '__dataclass_fields__'):  # Check if it's a dataclass
        return asdict(obj)
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    else:
        return obj


class AnalysisAgent:
    """Main analysis coordinator - streamlined and efficient"""
    
    def __init__(self, repo_path: str):
        """Initialize analyzer with streamlined setup"""
        self.repo_path = Path(repo_path).resolve()

        # Initialize core components
        from ..tools.core.core_tools import EnhancedFileReader
        self.tools = EnhancedFileReader(repo_path)
        self.context = AnalysisContext(str(self.repo_path))  # Pass repo path for normalization
        self.task_queue = TaskQueue(str(self.repo_path))  # Pass repo path for target normalization

        # Initialize context management (late import to avoid circular dependencies)
        from ..tools.planning.analysis_context_manager import AnalysisContextManager
        from ..tools.planning.context_tools import initialize_analysis_context
        self.context_manager = AnalysisContextManager(str(repo_path))
        initialize_analysis_context(str(repo_path))

        # Initialize supporting components
        self.execution_logger = ExecutionLogger()
        self.history_compactor = HistoryCompactor(max_context_length=4000)
        self.decision_engine = DecisionEngine(str(repo_path))
        
        # Initialize exploration strategies (after context_manager is ready)
        self.exploration_strategies = None  # Will be initialized after context_manager

        # Initialize LLM decision maker for autonomous focus and path selection
        self.llm_decision_maker = LLMFocusDecisionMaker()

        # Initialize focus tracker with LLM decision maker for LLM-driven path selection
        self.focus_tracker = FocusTracker(
            repo_path=self.repo_path,
            llm_decision_maker=self.llm_decision_maker
        )

        # Initialize dynamic focus manager with LLM decision maker
        self.dynamic_focus = DynamicFocusManager(llm_decision_maker=self.llm_decision_maker)
        
        # Initialize fallback strategies for comprehensive analysis
        # DISABLED: Using only LLM-driven decisions for true autonomous exploration
        # self.fallback_strategies = FallbackAnalysisStrategies(
        #     self.context_manager, self.task_queue, self.context, self.tools
        # )
        self.fallback_strategies = None

        # Initialize security analyzer (late import to avoid circular dependency)
        from ..tools.analyzers.security_analyzer import SecurityAnalyzer
        self.security_analyzer = SecurityAnalyzer()

        # Initialize LLM helper for code analysis
        from ..tools.code_analysis.llm_decider import LLMHelper
        self.llm = LLMHelper()

        # Initialize MCP analysis cache to avoid redundant calls
        self._mcp_cache = {
            'related_files': {},  # file_path -> List[str]
            'config_files': {}    # file_path -> List[str]
        }
    
    def _build_file_path(self, directory: str, filename: str) -> str:
        """Build normalized file path to prevent duplicates"""
        try:
            # Use pathlib for proper path joining
            if directory == ".":
                return filename
            else:
                # Normalize the path construction
                dir_path = Path(directory)
                full_path = dir_path / filename
                return str(full_path).replace('\\', '/')
        except Exception:
            # Fallback to string concatenation if pathlib fails
            return f"{directory.rstrip('/')}/{filename}"
    def analyze(self, max_steps: Optional[int] = None, save_results: bool = True, focus: str = None) -> Dict[str, Any]:
        """
        Autonomous agent-driven analysis using discoveries and context for intelligent decision making
        """
        # Initialize analysis parameters and components
        max_steps = self._initialize_analysis_parameters(max_steps)
        self._initialize_analysis_components()
        
        # Initialize analysis state
        analysis_state = self._initialize_analysis_state()
        
        # Generate initial dynamic focus if not provided (LLM-driven)
        if focus is None:
            # Get initial repository structure for LLM context
            initial_files = []
            initial_dirs = []
            try:
                root_result = self.tools.list_directory(".")
                initial_files = root_result.get("files", [])
                initial_dirs = root_result.get("directories", [])
            except:
                pass

            # Generate LLM-driven focus with full autonomy
            focus_result = self.dynamic_focus.generate_initial_focus(
                repo_name=self.repo_path.name,
                initial_files=initial_files,
                analysis_goal=f"Comprehensive security vulnerability analysis of {self.repo_path.name}",
                repo_structure={'directories': initial_dirs, 'files': initial_files}
            )
            focus = focus_result.get('focus_description', 'General security analysis')

            # Create initial focus in tracker using LLM-generated focus
            initial_focus_id = self.focus_tracker.create_focus(
                focus_description=focus,
                reason=focus_result.get('reason', focus_result.get('reasoning', 'Initial LLM-generated focus')),
                priority=focus_result.get('priority', 50)
            )

            # Add suggested targets from LLM
            suggested_targets = focus_result.get('suggested_targets', [])
            for target in suggested_targets[:3]:
                if target in initial_files or target in initial_dirs:
                    self.focus_tracker.update_focus(
                        initial_focus_id,
                        lead={'path': target, 'reason': 'LLM-suggested initial target'}
                    )

            print(f"[LLM_FOCUS_INIT] {focus}")
        else:
            # Legacy: create focus from provided string
            self.dynamic_focus.current_focus = focus
            self.focus_tracker.create_focus(
                focus_description=focus,
                reason="User-provided focus"
            )

        print("Starting LLM-driven autonomous security analysis...")
        print(f"Initial focus: '{focus}' - LLM will autonomously adapt and select paths")
        
        # Main analysis loop
        return self._run_analysis_loop(analysis_state, max_steps, save_results, focus)

    def _initialize_analysis_parameters(self, max_steps: Optional[int] = None) -> int:
        """Initialize analysis parameters from settings"""
        if max_steps is None:
            try:
                from ..config import settings
                max_steps = getattr(settings, 'MAX_STEPS', 50)
            except ImportError:
                max_steps = 100
        return max_steps

    def _initialize_analysis_components(self) -> None:
        """Initialize exploration and fallback strategies"""
        if self.exploration_strategies is None:
            self.exploration_strategies = ExplorationStrategies(
                self.tools, self.context, self.context_manager, self.task_queue
            )
            
        # DISABLED: Using only LLM-driven decisions
        self.fallback_strategies = None

    def _initialize_analysis_state(self) -> Dict:
        """Initialize analysis state variables"""
        # Initialize with minimal starting point - just explore the root
        initial_explore = Task(type=TaskType.EXPLORE, target=".", priority=100)
        self.task_queue.add_task(initial_explore)
        
        return {
            'step': 0,
            'findings': [],
            'detailed_findings': [],
            'security_findings': [],
            'last_reassessment_step': 0
        }

    def _run_analysis_loop(self, analysis_state: Dict, max_steps: int, save_results: bool, focus: str) -> Dict[str, Any]:
        """Main analysis loop with CORE INNOVATION: LLM-driven autonomous decision making and reassessment"""
        consecutive_empty_queue_count = 0  # Track consecutive empty queue attempts
        current_focus = focus  # Track current dynamic focus
        
        while analysis_state['step'] < max_steps:
            # LLM-driven focus update based on discoveries (every 10 steps)
            if analysis_state['step'] > 0 and analysis_state['step'] % 10 == 0:
                discoveries = self.dynamic_focus.extract_discoveries_from_context(
                    self.context_manager,
                    analysis_state.get('security_findings', [])
                )

                # LLM decides whether to update/shift focus
                focus_update = self.dynamic_focus.update_focus_from_discoveries(
                    discoveries,
                    explored_paths=self.context.get_explored_directories(),
                    analyzed_files=self.context.get_analyzed_files()
                )

                action = focus_update.get('action', 'keep')
                if action in ['update', 'shift']:
                    new_focus = focus_update.get('focus_description', current_focus)
                    current_focus = new_focus

                    # Update focus tracker with new LLM-generated focus
                    if self.focus_tracker.active_focuses:
                        # Update primary focus
                        primary_focus = self.focus_tracker.get_primary_focus()
                        if primary_focus:
                            # Create new focus to replace old one
                            self.focus_tracker.create_focus(
                                focus_description=new_focus,
                                reason=focus_update.get('reason', focus_update.get('reasoning', 'LLM focus shift')),
                                priority=focus_update.get('priority', 50)
                            )

                    print(f"\n[LLM_FOCUS_{action.upper()}] {current_focus}")
            
            # CORE INNOVATION: LLM-driven intelligent reassessment decision
            should_reassess, reassess_reason = self._llm_should_reassess_decision(
                analysis_state['step'], analysis_state['last_reassessment_step']
            )
            
            # Perform intelligent reassessment if LLM recommends it
            if should_reassess:
                print(f"\n[STEP {analysis_state['step'] + 1}/{max_steps}] LLM Queue Reassessment")
                self._intelligent_queue_reassessment()
                analysis_state['last_reassessment_step'] = analysis_state['step']
            
            # 1. Try to get a task from queue (focus-driven first)
            task = self._get_focus_driven_task() or self.task_queue.get_next()
            
            # 2. If no task available, perform comprehensive task generation
            if not task:
                print(f"\n[STEP {analysis_state['step'] + 1}/{max_steps}] No tasks - performing comprehensive reassessment...")
                
                # First try autonomous context reassessment (core innovation)
                self._autonomous_context_reassessment()
                task = self.task_queue.get_next()
                
                # If still no task, use LLM to generate new targets
                if not task:
                    new_tasks_added = self._llm_generate_new_tasks()
                    if new_tasks_added > 0:
                        print(f"  Generated {new_tasks_added} new tasks")
                        consecutive_empty_queue_count = 0  # Reset counter
                        task = self.task_queue.get_next()
                    else:
                        consecutive_empty_queue_count += 1
                        print(f"  No new tasks generated (attempt {consecutive_empty_queue_count})")
                
                # Only terminate if we've tried multiple times and have done minimum work
                if not task and consecutive_empty_queue_count >= 3 and analysis_state['step'] >= 10:
                    print(f"  Analysis complete - no more discoverable targets after {analysis_state['step']} steps")
                    break
                elif not task:
                    # Skip this step but continue trying
                    analysis_state['step'] += 1
                    continue
            
            # 3. Execute the task
            print(f"\n[STEP {analysis_state['step'] + 1}/{max_steps}] Executing Task:")
            print(f"  Task: {task.type.value.upper()} → {task.target}")
            print(f"  Current Repository: {self.repo_path}")
            
            # Determine current working directory for this task
            if task.type.value == "EXPLORE" and task.target != ".":
                # For EXPLORE tasks, the target becomes the new current directory
                current_dir = task.target
            else:
                # For READ tasks, use parent directory of the file
                current_dir = str(Path(task.target).parent) if "/" in task.target else "."
            
            print(f"  Current Working Directory: {current_dir}")
            print(f"  Available Files in Current Directory: {len(self.tools.list_directory('.').get('files', []))}")
                
            result = self._execute_task(task)

            # 4. Process results and update state
            success = result.get("success", False)
            print(f"  Status: {'Success' if success else 'Failed'}")
            
            if success and result.get("result", {}).get("lines_read"):
                print(f"  Content: {result['result']['lines_read']} lines")

            # Update task status and context
            if success:
                self.task_queue.complete_task(task.task_id, result)
                self._process_successful_task(task, result, analysis_state, focus)
            else:
                error_msg = result.get("error", "Unknown error")
                self.task_queue.fail_task(task.task_id, error_msg)
                print(f"  Error: {error_msg}")

                # Mark failed path in focus tracker to avoid retrying
                if hasattr(task, 'focus_id') and task.focus_id:
                    self.focus_tracker.mark_path_failed(task.focus_id, task.target)
                    print(f"  [FOCUS] Marked path as failed in focus {task.focus_id}")

            # Log execution for tracing
            self.execution_logger.log_execution(task, result, analysis_state['step'] + 1)
            analysis_state['step'] += 1

        # Final autonomous summary with dataflow focus
        dataflow_summary = self.execution_logger.get_dataflow_summary()
        print("\nAnalysis Complete - Tool & Dataflow Summary:")
        print(f"  Steps completed: {analysis_state['step']}")
        print(f"  Directories explored: {len(self.context.get_explored_directories())}")
        print(f"  Files analyzed: {len(self.context.get_analyzed_files())}")
        print(f"  Files with dataflow patterns: {dataflow_summary.get('files_with_dataflows', 0)}")
        print(f"  Total dataflow patterns found: {dataflow_summary.get('total_dataflow_patterns', 0)}")
        print(f"  High-risk dataflows: {dataflow_summary.get('high_risk_flows_count', 0)}")
        print(f"  Unique tools discovered: {dataflow_summary.get('tools_count', 0)}")
        
        # Get execution statistics and trace logs
        execution_stats = self.execution_logger.get_summary()
        trace_logs = self.execution_logger.get_trace_logs()
        task_stats = self.task_queue.get_stats()
        
        # Create a unique set of security findings (no duplicates) - simplified using dict comprehension
        unique_security_findings = {
            result["file_path"]: result for result in analysis_state['security_findings']
        }

        # Calculate risk statistics from unique findings
        risk_stats = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        high_risk_files = []
        medium_risk_files = []

        for sec_result in unique_security_findings.values():
            risk_level = sec_result["risk_assessment"]["overall_risk"]
            risk_stats[risk_level] = risk_stats.get(risk_level, 0) + 1

            if risk_level == "HIGH":
                high_risk_files.append(sec_result["file_path"])
            elif risk_level == "MEDIUM":
                medium_risk_files.append(sec_result["file_path"])

        # Compile final results with simplified structure (no duplicates)
        final_result = {
            "analysis_info": {
                "repository_path": str(self.repo_path),
                "analysis_timestamp": datetime.now().isoformat(),
                "analyzer_version": "4.0.0-autonomous",
                "initial_focus": focus,
                "final_focus": self.dynamic_focus.current_focus,
                "focus_history": self.dynamic_focus.focus_history,
                "analysis_mode": "autonomous_agent_driven"
            },

            "execution_summary": {
                "steps_completed": analysis_state['step'],
                "max_steps": max_steps,
                "status": "completed" if analysis_state['step'] < max_steps else "max_steps_reached",
                "execution_stats": execution_stats,
                "task_stats": task_stats,
                "trace_logs": trace_logs,
                "llm_decisions_made": len([log for log in trace_logs if log.get("extra_actions")])
            },

            "discovered_structure": {
                "explored_directories": list(self.context.get_explored_directories()),
                "analyzed_files": list(self.context.get_analyzed_files()),
                "total_directories": len(self.context.get_explored_directories()),
                "total_files": len(self.context.get_analyzed_files())
            },

            "tool_dataflow_analysis": {
                "llm_driven_dataflow_analysis": self._perform_llm_driven_dataflow_analysis(list(unique_security_findings.values())),
                "summary": dataflow_summary,
                "high_risk_dataflow_files": [log.target for log in self.execution_logger.get_high_risk_dataflow_logs()],
                "tool_chain_completeness": self._assess_tool_chain_completeness(dataflow_summary),
                "dataflow_coverage": self._assess_dataflow_coverage(dataflow_summary, len(self.context.get_analyzed_files()))
            },

            "security_analysis": {
                "summary": {
                    "total_files_analyzed": len(unique_security_findings),
                    "risk_distribution": risk_stats,
                    "high_risk_files": high_risk_files,
                    "medium_risk_files": medium_risk_files,
                    "total_findings": sum(len(result.get("findings", [])) for result in unique_security_findings.values())
                },
                "detailed_results": list(unique_security_findings.values()),
                # Add injection point analysis for high/medium risk files
                "injection_point_analysis": self._perform_injection_point_analysis(list(unique_security_findings.values()), dataflow_summary)
            }
        }
        
        # Save and return results
        if save_results:
            self._save_analysis_results(final_result)

        return final_result

    def _llm_generate_new_tasks(self) -> int:
        """Simplified LLM-driven task generation when queue is empty"""
        try:
            # Build current analysis context
            analyzed_files = list(self.context.get_analyzed_files())
            explored_dirs = list(self.context.get_explored_directories())
            
            # Get current repository state
            all_files = []
            all_dirs = []
            
            # Collect all discovered but unanalyzed files and unexplored directories
            try:
                for explored_dir in explored_dirs + ["."]:
                    dir_result = self.tools.list_directory(explored_dir)
                    if "error" not in dir_result:
                        dir_files = dir_result.get("files", [])
                        dir_subdirs = dir_result.get("directories", [])
                        
                        for file in dir_files:
                            file_path = self._build_file_path(explored_dir, file)
                            if file_path not in analyzed_files and not file.startswith('.'):
                                all_files.append(file_path)
                        
                        for subdir in dir_subdirs:
                            subdir_path = self._build_file_path(explored_dir, subdir)
                            if (subdir_path not in explored_dirs and 
                                not subdir.startswith('.') and 
                                subdir not in ['node_modules', '__pycache__', '.git', 'build', 'dist']):
                                all_dirs.append(subdir_path)
            except Exception as e:
                print(f"  Error collecting repository state: {e}")
                return 0
            
            # If we have discoverable targets, ask LLM to prioritize them
            if all_files or all_dirs:
                return self._llm_prioritize_targets(all_files, all_dirs)
            else:
                print("  No more discoverable targets in repository")
                return 0
                
        except Exception as e:
            print(f"  Error in LLM task generation: {e}")
            return 0

    def _llm_prioritize_targets(self, available_files: list, available_dirs: list) -> int:
        """Use LLM to prioritize and select targets from available options"""
        try:
            from ..tools.core.llm_client import LLMClient
            
            # Build context for LLM
            analyzed_files = list(self.context.get_analyzed_files())
            security_summary = self.context_manager.get_security_summary()
            
            context = f"""
ANALYSIS PROGRESS:
- Files analyzed: {len(analyzed_files)}
- Security findings: {security_summary.get('total_findings', 0)} 
- High risk files: {security_summary.get('high_risk_count', 0)}

RECENTLY ANALYZED FILES:
{chr(10).join([f"- {f}" for f in analyzed_files[-10:]])}

AVAILABLE TARGETS:
Files to analyze: {available_files}
Directories to explore: {available_dirs}
"""

            prompt = f"""You are continuing a security analysis. Select the MOST VALUABLE targets to analyze next.

{context}

SELECTION CRITERIA:
1. Prioritize files that could contain security vulnerabilities
2. Focus on core application logic, configuration, and entry points  
3. Explore directories likely to contain important components
4. Avoid redundant analysis of similar file types
5. **BE HIGHLY EFFICIENT**: Focus on targets for tool/dataflow analysis, avoid broad exploration

Select up to 3 targets that would provide the most tool/dataflow insight.

Respond in JSON format:
{{
    "selected_targets": [
        {{"type": "file", "path": "exact_path_from_available_list", "priority": "high", "reason": "why important"}},
        {{"type": "directory", "path": "exact_path_from_available_list", "priority": "medium", "reason": "why important"}}
    ],
    "strategy": "brief explanation of selection strategy"
}}"""

            model = LLMClient.get_model("analysis")
            messages = [
                {"role": "system", "content": "You are a security analyst selecting the most valuable analysis targets."},
                {"role": "user", "content": prompt}
            ]
            
            decision_text = LLMClient.call_llm(
                model=model, messages=messages, max_tokens=800,
                temperature=0.5, timeout=30, max_retries=2
            )
            
            if decision_text:
                # Parse LLM response
                import json
                start_idx = decision_text.find('{')
                end_idx = decision_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = decision_text[start_idx:end_idx]
                    decisions = json.loads(json_str)
                    
                    # Add selected targets to task queue
                    from ..tools.core.task import Task, TaskType
                    tasks_added = 0
                    
                    for target_info in decisions.get("selected_targets", []):
                        target_path = target_info.get("path", "")
                        target_type = target_info.get("type", "file")
                        priority_str = target_info.get("priority", "medium")
                        reason = target_info.get("reason", "LLM selection")
                        
                        # Convert priority to numeric value
                        from ..tools.core.task import PRIORITY_MAPPING
                        if isinstance(priority_str, str):
                            priority = PRIORITY_MAPPING.get(priority_str, PRIORITY_MAPPING["default"])
                        else:
                            priority = int(priority_str) if isinstance(priority_str, (int, float)) else PRIORITY_MAPPING["default"]
                        
                        # Validate target exists in available lists
                        if target_type == "file" and target_path in available_files:
                            task = Task(TaskType.READ, target_path, priority=priority)
                            self.task_queue.add_task(task)
                            tasks_added += 1
                            print(f"    [+] READ {target_path} (priority: {priority}) - {reason}")
                        elif target_type == "directory" and target_path in available_dirs:
                            task = Task(TaskType.EXPLORE, target_path, priority=priority)
                            self.task_queue.add_task(task)
                            tasks_added += 1
                            print(f"    [+] EXPLORE {target_path} (priority: {priority}) - {reason}")
                    
                    if tasks_added > 0:
                        strategy = decisions.get("strategy", "LLM-driven selection")
                        print(f"  Strategy: {strategy}")
                    
                    return tasks_added
            
            return 0
            
        except Exception as e:
            print(f"  Error in LLM prioritization: {e}")
            return 0

    def _process_successful_task(self, task, result, analysis_state, focus):
        """Process successful task execution and generate follow-up tasks"""
        from ..tools.core.task import TaskType
        
        if task.type == TaskType.EXPLORE:
            # Update context and generate follow-up tasks for exploration
            self.context.add_explored_directory(task.target)
            
            result_data = result.get("result", {})
            files = result_data.get("files", [])
            dirs = result_data.get("directories", [])
            
            # Record discovery in context manager
            self.context_manager.update_project_structure(task.target, {
                "files": files, "directories": dirs
            })
            
            # Use decision engine to generate follow-up tasks
            if files or dirs:
                # Pass current directory context for proper path construction
                current_explored_path = task.target
                print(f"  [PATH_DEBUG] Current explored_path: {current_explored_path}")
                print(f"  [PATH_DEBUG] Available files (total: {len(files)}): {files}")
                print(f"  [PATH_DEBUG] Available dirs (total: {len(dirs)}): {dirs}")
                print(f"  [PATH_DEBUG] Full dirs list: {dirs}")
                
                self.decision_engine.make_autonomous_decision(
                    "exploration", self.context_manager, self.task_queue, 
                    self.context.get_analyzed_files(), self.context.get_explored_directories(),
                    explored_path=current_explored_path, files=files, dirs=dirs, focus=self.dynamic_focus.current_focus
                )
                        
        elif task.type == TaskType.READ:
            # Update context and analyze file content
            self.context.add_analyzed_file(task.target)
            file_content = result.get("result", {}).get("content", "")
            
            if file_content:
                # Perform security analysis
                security_result = self.security_analyzer.analyze_file_security(task.target, file_content)
                analysis_state['security_findings'].append(security_result)
                
                # Get file diagnostics (optimized - single file only, won't cause hangs)
                try:
                    file_diagnostics = self.get_file_diagnostics_optimized(task.target, max_diagnostics=5)
                    if file_diagnostics:
                        # Add diagnostics to security result for additional context
                        security_result['diagnostics'] = file_diagnostics
                        print(f"  [DIAGNOSTICS_INTEGRATED] Added {len(file_diagnostics)} diagnostics to analysis")
                except Exception as e:
                    print(f"  [DIAGNOSTICS_SKIP] Could not get diagnostics: {e}")
                
                # Add security_result to the task result for ExecutionLogger
                result['security_result'] = security_result
                
                # Record analysis results
                risk_level = security_result["risk_assessment"]["overall_risk"]
                if risk_level in ["HIGH", "MEDIUM"]:
                    self.context.set_data(f"security_concern_{task.target}", True)
                    print(f"  Security Risk: {risk_level}")
                
                # Debug: Print detailed dataflow information
                agent_analysis = security_result.get("agent_analysis", {})
                print(f"  [DEBUG] Agent analysis present: {bool(agent_analysis)}")
                if agent_analysis:
                    dataflow_patterns = agent_analysis.get("dataflow_patterns", [])
                    agent_tools = agent_analysis.get("agent_tools", [])
                    print(f"  [DEBUG] Raw dataflow_patterns: {dataflow_patterns}")
                    print(f"  [DEBUG] Raw agent_tools: {agent_tools}")
                    
                    if dataflow_patterns:
                        print(f"  ✓ Dataflow Patterns: {len(dataflow_patterns)} found")
                        high_risk_flows = [f for f in dataflow_patterns if f.get("risk_level") == "HIGH"]
                        if high_risk_flows:
                            print(f"  ✓ High-Risk Flows: {len(high_risk_flows)}")
                    else:
                        print(f"  ✗ No dataflow patterns detected")
                        
                    if agent_tools:
                        print(f"  ✓ Agent Tools: {len(agent_tools)} identified")
                    else:
                        print(f"  ✗ No agent tools detected")
                else:
                    print(f"  ✗ No agent_analysis in security result")
                    # Debug: Print what we got instead
                    print(f"  [DEBUG] Security result keys: {list(security_result.keys())}")
                    if "llm_analysis" in security_result:
                        llm_analysis = security_result["llm_analysis"]
                        print(f"  [DEBUG] LLM analysis keys: {list(llm_analysis.keys()) if isinstance(llm_analysis, dict) else 'not dict'}")
                        if isinstance(llm_analysis, dict) and "tool_analysis" in llm_analysis:
                            tool_analysis = llm_analysis["tool_analysis"]
                            print(f"  [DEBUG] Tool analysis: {tool_analysis}")
                
                # Convert SecurityFinding objects to dicts for JSON serialization
                findings = security_result.get("findings", [])
                serialized_findings = [
                    f.to_dict() if hasattr(f, 'to_dict') else f
                    for f in findings
                ]

                analysis_data = {
                    "security_risk": risk_level.lower(),
                    "key_findings": serialized_findings,
                    "lines_of_code": result.get("result", {}).get("lines_read", 0),
                }
                self.context_manager.add_analysis_result(task.target, analysis_data)
                
                # Store for reporting
                analysis_state['detailed_findings'].append({
                    "file": task.target,
                    "content_preview": file_content[:500] + "..." if len(file_content) > 500 else file_content,
                    "lines": result.get("result", {}).get("lines_read", 0),
                    "security_summary": security_result.get("summary", ""),
                })
                
                # Update focus tracker with findings and related files (MCP agent integration)
                self._update_focus_tracker_with_findings(task.target, security_result, file_content)
                
                # Extract MCP analysis results for decision engine
                print(f"  [MCP_INTEGRATION] Extracting MCP analysis results for decision engine...")
                mcp_related_files = self._find_related_files_from_content(file_content, task.target)
                mcp_config_files = []
                if task.target.endswith(('.json', '.toml', '.yaml', '.yml', '.ini')):
                    mcp_config_files = self._find_referenced_files_from_config(file_content, task.target)
                
                print(f"  [MCP_INTEGRATION] MCP found {len(mcp_related_files)} related files, {len(mcp_config_files)} config files")
                
                # Generate follow-up tasks based on content analysis (including MCP results)
                self.decision_engine.make_autonomous_decision(
                    "content", self.context_manager, self.task_queue,
                    self.context.get_analyzed_files(), self.context.get_explored_directories(),
                    file_path=task.target, content=file_content, security_result=security_result, 
                    focus=self.dynamic_focus.current_focus,
                    mcp_related_files=mcp_related_files,  # Pass MCP analysis results
                    mcp_config_files=mcp_config_files     # Pass MCP config analysis results
                )

    def _assess_file_priorities_with_llm(self, files: List[str], explored_path: str) -> None:
        """Use LLM to assess file priorities and add high-value files to task queue"""
        if not files or len(files) == 0:
            return

        # Build comprehensive context including existing discoveries
        context = self._build_comprehensive_priority_context(explored_path, files)
        
        # Get comprehensive analysis context for intelligent prioritization
        comprehensive_context = self.context_manager.get_comprehensive_analysis_context()
        security_findings = comprehensive_context.get('security_findings', [])
        workflow_analysis = comprehensive_context.get('workflow_analysis', {})

        priority_prompt = PromptManager.get_file_priority_prompt(
            context=context, 
            files=files,
            security_findings=security_findings,
            workflow_analysis=workflow_analysis,
            focus=self.dynamic_focus.current_focus
        )

        # Use LLM to get priority assessment
        model = LLMClient.get_model("analysis")
        messages = [
            {"role": "system", "content": "You are an expert code analyst focused on tracing COMPLETE DATAFLOW CHAINS from external data sources to final LLM processing. Make autonomous decisions about file priorities based on the current analysis context and focus. Your goal is to identify files that form the complete dataflow: External Data Sources → Internal Processing → LLM Integration. Include external data interaction tools AND the internal processing functions that are part of the dataflow chain to LLM decision making."},
            {"role": "user", "content": priority_prompt}
        ]

        priority_text = LLMClient.call_llm(
            model=model,
            messages=messages,
            max_tokens=800,
            temperature=0.5,
            timeout=20,
            max_retries=2
        )

        if priority_text:
            try:
                import json
                start = priority_text.find('{')
                end = priority_text.rfind('}') + 1
                if start != -1 and end > start:
                    json_text = priority_text[start:end]
                    priorities = json.loads(json_text)

                    # Check if all files are low priority
                    priority_files = priorities.get("priority_files", [])  # No limit - get all files
                    high_medium_files = [f for f in priority_files if f.get("priority", "low") in ["high", "medium"]]
                    
                    if not high_medium_files:
                        # All files are low priority - suggest exploring subdirectories instead
                        print(f"  [SKIP] All {len(priority_files)} files are low priority")
                        print(f"  [RECOMMENDATION] Consider exploring subdirectories for more valuable content")
                        # Don't add any files, let the system explore deeper
                        return

                    # Add high and medium priority files to task queue
                    from ..tools.core.task import Task, TaskType
                    added_count = 0

                    for file_info in high_medium_files:
                        filename = file_info.get("filename", "")
                        priority = file_info.get("priority", "low")
                        reason = file_info.get("reason", "")

                        if filename in files:
                            # Construct full path using normalized method
                            file_path = self._build_file_path(explored_path, filename)

                            # Skip if already analyzed
                            if self.context.is_file_analyzed(file_path):
                                continue

                            # Set priority level based on LLM assessment using unified mapping
                            from ..tools.core.task import PRIORITY_MAPPING
                            task_priority = PRIORITY_MAPPING.get(priority, PRIORITY_MAPPING["default"])
                            
                            print(f"    [PRIORITY_ASSIGN] {filename}: {priority} → priority {task_priority}")

                            # Create read task
                            read_task = Task(type=TaskType.READ, target=file_path, priority=task_priority)
                            self.task_queue.add_task(read_task)

                            print(f"  [PRIORITY] Added {priority} priority file: {filename} ({reason})")
                            added_count += 1

                    print(f"  [SUCCESS] Added {added_count} priority files for analysis")

            except Exception as e:
                print(f"  [ERROR] Failed to parse LLM priority assessment: {e}")
                # # Fallback to simple priority selection (COMMENTED OUT FOR TESTING)
                # self.fallback_strategies.fallback_file_priority_selection(files, explored_path)
                print("  LLM priority assessment failed")
        else:
            print("  LLM priority assessment failed")
            # self.fallback_strategies.fallback_file_priority_selection(files, explored_path)

    def _generate_architectural_insights(self, findings: List[Dict]) -> Dict[str, Any]:
        """Generate architectural insights from analysis"""
        insights = {
            "file_types_analyzed": {},
            "key_components": [],
            "potential_entry_points": []
        }
        
        for finding in findings:
            file_ext = Path(finding["file"]).suffix
            insights["file_types_analyzed"][file_ext] = insights["file_types_analyzed"].get(file_ext, 0) + 1
            
            # Identify key components
            if "main" in finding["file"].lower() or "agent" in finding["file"].lower():
                insights["key_components"].append(finding["file"])
            
            # Look for entry points in analysis
            if "entry" in finding.get("analysis", "").lower() or "main" in finding.get("analysis", "").lower():
                insights["potential_entry_points"].append(finding["file"])
        
        return insights
    
    def _save_analysis_results(self, results: Dict[str, Any]) -> None:
        """Save analysis results to the configured analysis directory"""
        print("Attempting to save analysis results...")

        try:
            from ..config import settings

            # Save to configured analysis directory
            repo_name = self.repo_path.name or "unknown_repo"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Use the configured analysis directory from settings
            analysis_dir = Path(settings.ANALYSIS_DIR)
            print(f"Analysis directory: {analysis_dir.absolute()}")

            analysis_dir.mkdir(exist_ok=True, parents=True)

            filename = f"{repo_name}_static_analysis_{timestamp}.json"
            output_path = analysis_dir / filename

            print(f"Output path: {output_path.absolute()}")

            # Serialize dataclass objects before saving
            serialized_results = serialize_for_json(results)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serialized_results, f, indent=2, ensure_ascii=False)

            print(f"Analysis results saved to: {output_path}")

        except Exception as e:
            print(f"Warning: Could not save to central directory: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")

            # Fallback to current directory
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                repo_name = self.repo_path.name or "unknown_repo"
                fallback_path = Path(f"{repo_name}_analysis_results_{timestamp}.json")
                print(f"Trying fallback location: {fallback_path.absolute()}")

                serialized_results = serialize_for_json(results)
                with open(fallback_path, 'w', encoding='utf-8') as f:
                    json.dump(serialized_results, f, indent=2, ensure_ascii=False)
                print(f"Analysis results saved to fallback location: {fallback_path}")
            except Exception as e2:
                print(f"Failed to save analysis results: {e2}")
                print(f"   Error type: {type(e2).__name__}")
                import traceback
                print(f"   Traceback: {traceback.format_exc()}")

    def _run_targeted_security_analysis(self) -> List[Dict[str, Any]]:
        """Run LLM-driven targeted security analysis on high-priority files"""
        targeted_findings = []

        try:
            # Get analyzed files for security analysis
            analyzed_files = self.context.get_analyzed_files()

            # Focus on high-risk files first (limit to prevent token overflow)
            high_risk_files = []
            for file_path in analyzed_files:
                if file_path.endswith(('.py', '.js', '.ts', '.java', '.php')):
                    # Check if this was marked as high risk during initial analysis
                    if self.context.get_data(f"security_concern_{file_path}", False):
                        high_risk_files.append(file_path)

            # If no high-risk files, analyze a sample of recent files
            if not high_risk_files:
                high_risk_files = analyzed_files[-10:]  # Last 10 analyzed files

            # Limit to 5 files for LLM analysis
            analysis_files = high_risk_files  # Analyze all high risk files

            print(f"  [SECURITY] Analyzing {len(analysis_files)} files for targeted security issues")

            for file_path in analysis_files:
                try:
                    file_result = self.tools.read_file(file_path)
                    if "error" not in file_result and "content" in file_result:
                        content = file_result["content"]
                        findings = self._analyze_file_security_with_llm(file_path, content)
                        targeted_findings.extend(findings)
                except Exception as e:
                    print(f"  [ERROR] Failed to analyze {file_path}: {e}")
                    continue

        except Exception as e:
            print(f"Targeted security analysis failed: {e}")

        return targeted_findings

    def _analyze_file_security_with_llm(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Use LLM to analyze file content for security vulnerabilities"""
        findings = []

        # Prepare content sample (limit to avoid token limits)
        content_sample = content[:2000] + "..." if len(content) > 2000 else content

        # Build security analysis context
        language = file_path.split('.')[-1] if '.' in file_path else 'unknown'
        security_context = PromptManager.get_security_analysis_prompt(file_path, content_sample, language)

        # Use LLM for security analysis
        model = LLMClient.get_model("analysis")
        messages = [
            {"role": "system", "content": "You are an expert security auditor analyzing code for vulnerabilities. Focus on real security issues, not false positives."},
            {"role": "user", "content": security_context}
        ]

        analysis_text = LLMClient.call_llm(
            model=model,
            messages=messages,
            max_tokens=1200,
            temperature=0.5,
            timeout=30,
            max_retries=2
        )

        if analysis_text:
            try:
                import json
                # Extract JSON from response
                start = analysis_text.find('{')
                end = analysis_text.rfind('}') + 1
                if start != -1 and end > start:
                    json_text = analysis_text[start:end]
                    analysis_result = json.loads(json_text)

                    # Process findings
                    for finding in analysis_result.get("findings", []):
                        finding_dict = {
                            "file_path": file_path,
                            "vulnerability_type": finding.get("vulnerability_type", "Unknown"),
                            "severity": finding.get("severity", "MEDIUM"),
                            "line_number": finding.get("line_number", 0),
                            "description": finding.get("description", "Security issue detected"),
                            "code_snippet": finding.get("code_snippet", ""),
                            "injection_vector": finding.get("injection_vector", "Unknown"),
                            "data_flow": finding.get("data_flow", "Unknown"),
                            "attack_scenario": finding.get("attack_scenario", "Unknown"),
                            "remediation": finding.get("remediation", "Review and fix security issue"),
                            "exploitability": finding.get("exploitability", "Unknown"),
                            "analysis_method": "llm_driven"
                        }
                        findings.append(finding_dict)

                    print(f"  [SECURITY] Found {len(findings)} issues in {file_path.split('/')[-1]}")

            except Exception as e:
                print(f"  [ERROR] Failed to parse LLM security analysis for {file_path}: {e}")
        else:
            print(f"  [ERROR] LLM security analysis failed for {file_path}, no fallback available")

        return findings


    def _make_autonomous_decision(self, decision_type: str, **kwargs) -> None:
        """CORE INNOVATION: Unified LLM-driven autonomous decision making for exploration and content analysis"""
        
        try:
            print(f"  [AUTONOMOUS_DECISION] Making {decision_type} decision...")
            
            # Get comprehensive analysis history for LLM context
            history_context = self._build_history_context()

            # Use decision engine for autonomous decision making (core innovation)
            decision_result = self.decision_engine.make_autonomous_decision(
                decision_type, self.context_manager, self.task_queue, 
                self.context.get_analyzed_files(), self.context.get_explored_directories(),
                focus=self.dynamic_focus.current_focus, **kwargs
            )
            
            # Track decision results (core innovation tracking)
            if decision_result and decision_result.get("decisions_made", 0) > 0:
                tasks_added = decision_result.get("tasks_added", 0)
                decision_details = decision_result.get("decision_details", [])
                
                print(f"  [AUTONOMOUS_SUCCESS] Made {decision_result['decisions_made']} decisions, added {tasks_added} tasks")
                
                # Store for trace logging (core innovation)
                current_count = self.context.get_data("autonomous_decisions", 0)
                self.context.set_data("autonomous_decisions", current_count + decision_result["decisions_made"])
                self.context.set_data("last_llm_decisions", decision_details)
                
                # Log decision details
                for detail in decision_details[:3]:  # Show first 3
                    print(f"    → {detail.get('type', 'unknown').upper()}: {detail.get('path', 'unknown')} ({detail.get('reason', 'no reason')})")
            else:
                print(f"  [AUTONOMOUS_INFO] No decisions made for {decision_type}")
                
        except Exception as e:
            print(f"  [AUTONOMOUS_ERROR] Decision making failed: {e}")
            # Continue without autonomous decisions

    # DEPRECATED: Decision context building functions moved to legacy_decision_functions.py

    # DEPRECATED: Build decision prompt functions moved to DecisionEngine

    # REMOVED: _generate_related_files_recommendations - was rule-based
    # All file recommendations are now generated by LLM through DecisionEngine

    def _assess_tool_chain_completeness(self, dataflow_summary: Dict) -> str:
        """Assess how complete the tool chain analysis is"""
        total_tools = dataflow_summary.get('tools_count', 0)
        total_flows = dataflow_summary.get('total_dataflow_patterns', 0)
        
        if total_tools == 0 and total_flows == 0:
            return "No tool chains or dataflow patterns identified"
        elif total_tools > 0 and total_flows == 0:
            return f"Tools identified ({total_tools}) but dataflow patterns incomplete"
        elif total_tools == 0 and total_flows > 0:
            return f"Dataflow patterns found ({total_flows}) but tool definitions missing"
        else:
            completeness_ratio = min(total_flows / max(total_tools, 1), 1.0)
            if completeness_ratio > 0.8:
                return f"Tool chain analysis appears complete - {total_tools} tools, {total_flows} flows"
            elif completeness_ratio > 0.5:
                return f"Tool chain analysis partially complete - {total_tools} tools, {total_flows} flows"
            else:
                return f"Tool chain analysis incomplete - missing flow analysis for many tools"

    def _assess_dataflow_coverage(self, dataflow_summary: Dict, total_files: int) -> str:
        """Assess dataflow analysis coverage across analyzed files"""
        files_with_flows = dataflow_summary.get('files_with_dataflows', 0)
        if total_files == 0:
            return "No files analyzed"
        
        coverage_ratio = files_with_flows / total_files
        if coverage_ratio > 0.3:
            return f"Good dataflow coverage - {files_with_flows}/{total_files} files contain dataflow patterns"
        elif coverage_ratio > 0.1:
            return f"Moderate dataflow coverage - {files_with_flows}/{total_files} files contain dataflow patterns"
        else:
            return f"Limited dataflow coverage - only {files_with_flows}/{total_files} files contain dataflow patterns"

    def _perform_llm_driven_dataflow_analysis(self, security_results: List[Dict]) -> Dict[str, Any]:
        """Use LLM to analyze and categorize complete dataflow chains from external sources to LLM decisions"""
        try:
            # Prepare data for LLM analysis
            dataflow_data = self._prepare_dataflow_data_for_llm(security_results)
            
            if not dataflow_data["has_dataflows"]:
                return {
                    "analysis_performed": False,
                    "reason": "No dataflow patterns found to analyze"
                }
            
            # Create LLM prompt for dataflow analysis
            dataflow_prompt = PromptManager.get_llm_dataflow_analysis_prompt(dataflow_data)
            
            # Get LLM analysis
            model = LLMClient.get_model("analysis")
            messages = [
                {"role": "system", "content": "You are an expert dataflow analyst specializing in tracing complete data paths from external sources through internal processing to final LLM decision points. Analyze the provided dataflow patterns and categorize them intelligently."},
                {"role": "user", "content": dataflow_prompt}
            ]
            
            analysis_text = LLMClient.call_llm(
                model=model, messages=messages, max_tokens=2000,
                temperature=0.3, timeout=45, max_retries=2
            )
            
            if analysis_text:
                return self._parse_llm_dataflow_analysis(analysis_text)
            else:
                return {
                    "analysis_performed": False,
                    "reason": "LLM analysis failed"
                }
                
        except Exception as e:
            return {
                "analysis_performed": False,
                "error": f"Dataflow analysis failed: {str(e)}"
            }

    def _prepare_dataflow_data_for_llm(self, security_results: List[Dict]) -> Dict[str, Any]:
        """Prepare dataflow data for LLM analysis"""
        all_dataflows = []
        all_tools = []
        
        for result in security_results:
            file_path = result["file_path"]
            agent_analysis = result.get("agent_analysis", {})
            
            # Collect dataflow patterns
            dataflow_patterns = agent_analysis.get("dataflow_patterns", [])
            for flow in dataflow_patterns:
                flow_data = {
                    "file": file_path,
                    "flow_id": flow.get("flow_id", "unknown"),
                    "description": flow.get("description", ""),
                    "data_path": flow.get("data_path", ""),
                    "risk_level": flow.get("risk_level", "UNKNOWN"),
                    "sanitization": flow.get("sanitization", "unknown"),
                    "external_data_source": flow.get("external_data_source", ""),
                    "internal_processing_steps": flow.get("internal_processing_steps", []),
                    "llm_integration_point": flow.get("llm_integration_point", ""),
                    "llm_integration_details": flow.get("llm_integration_details", "")
                }
                all_dataflows.append(flow_data)
            
            # Collect tools
            agent_tools = agent_analysis.get("agent_tools", [])
            for tool in agent_tools:
                tool_data = {
                    "file": file_path,
                    "tool_name": tool.get("tool_name", "unknown"),
                    "tool_type": tool.get("tool_type", "unknown"),
                    "description": tool.get("description", ""),
                    "external_data_sources": tool.get("external_data_sources", []),
                    "external_data_destinations": tool.get("external_data_destinations", [])
                }
                all_tools.append(tool_data)
        
        return {
            "has_dataflows": len(all_dataflows) > 0,
            "has_tools": len(all_tools) > 0,
            "total_dataflows": len(all_dataflows),
            "total_tools": len(all_tools),
            "dataflows": all_dataflows,
            "tools": all_tools
        }


    def _parse_llm_dataflow_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse LLM dataflow analysis response"""
        try:
            import json
            start = analysis_text.find('{')
            end = analysis_text.rfind('}') + 1
            if start != -1 and end > start:
                json_text = analysis_text[start:end]
                parsed_analysis = json.loads(json_text)
                
                # Add metadata
                parsed_analysis["analysis_performed"] = True
                parsed_analysis["analysis_method"] = "llm_driven"
                
                return parsed_analysis
            else:
                return {
                    "analysis_performed": False,
                    "error": "Could not parse LLM response as JSON"
                }
        except Exception as e:
            return {
                "analysis_performed": False,
                "error": f"Failed to parse LLM analysis: {str(e)}"
            }

    def _perform_injection_point_analysis(self, security_results: List[Dict], dataflow_summary: Dict) -> Dict:
        """Perform specialized injection point analysis for high/medium risk files"""
        try:
            # Use the security analyzer's new injection point analysis
            injection_analysis = self.security_analyzer.analyze_injection_points_for_high_risk_files(
                security_results, dataflow_summary
            )
            return injection_analysis
        except Exception as e:
            return {
                "analysis_performed": False,
                "error": f"Injection point analysis failed: {str(e)}",
                "summary": "Failed to perform specialized injection point analysis"
            }

    def _build_history_context(self) -> str:
        """Build comprehensive analysis history context for LLM to prevent duplicates and invalid paths"""
        try:
            overview = self.context_manager.get_project_overview()
            security_summary = self.context_manager.get_security_summary()
            analyzed_files = list(self.context.get_analyzed_files())
            explored_dirs = list(self.context.get_explored_directories())

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

            # List all explored directories to prevent duplicates
            for dir_path in sorted(explored_dirs):
                history += f"- {dir_path}\n"

            history += f"\nANALYZED FILES (DO NOT RE-ANALYZE):\n"

            # List all analyzed files to prevent duplicates
            for file_path in sorted(analyzed_files):
                file_info = self.context_manager.get_analysis_result(file_path)
                risk = file_info.get('security_risk', 'unknown') if file_info else 'unknown'
                history += f"- {file_path}: {risk} risk\n"

            # Add current working directory context
            history += f"\nCURRENT ANALYSIS STATE:\n"
            history += f"- Repository root: {self.repo_path}\n"

            # Add unanalyzed files in recently explored directories
            if explored_dirs:
                history += f"\nFILES AVAILABLE FOR ANALYSIS (in explored directories):\n"
                for explored_dir in explored_dirs[-3:]:  # Last 3 explored dirs
                    try:
                        dir_path = self.repo_path / explored_dir
                        if dir_path.exists():
                            for item in dir_path.iterdir():
                                if item.is_file() and str(item.relative_to(self.repo_path)) not in analyzed_files:
                                    history += f"- {item.relative_to(self.repo_path)}\n"
                    except:
                        continue

            # Add repository structure overview
            try:
                tree_result = self.tools.get_tree_structure(".", max_depth=2)
                if "tree_output" in tree_result and not tree_result.get("error"):
                    tree_lines = tree_result["tree_output"].split('\n')[:15]  # First 15 lines
                    history += f"\nREPOSITORY STRUCTURE OVERVIEW:\n" + "\n".join(tree_lines)
            except Exception:
                pass  # Tree command might not be available

            # Apply auto-compaction if context is too long
            compacted_history = self.history_compactor.compact_if_needed(history)
            return compacted_history

        except Exception as e:
            return f"Analysis History: Limited context available (error: {e})"

    def _build_exploration_context(self, explored_path: str, files: List[str], dirs: List[str]) -> str:
        """Build current exploration context for LLM"""
        context = f"""
CURRENT EXPLORATION CONTEXT:
- Exploring: {explored_path}
- New files discovered: {len(files)}
- New directories discovered: {len(dirs)}

DISCOVERED FILES:
"""

        for file in files:  # Show all files for context
            file_path = f"{explored_path.rstrip('/')}/{file}"
            context += f"- {file_path}\n"

        context += "\nDISCOVERED DIRECTORIES:\n"
        for dir in dirs:  # Show all directories for context
            dir_path = f"{explored_path.rstrip('/')}/{dir}"
            context += f"- {dir_path}\n"

        return context



    # DEPRECATED FUNCTIONS MOVED TO legacy_decision_functions.py

    # DEPRECATED: _execute_decisions and related functions moved to legacy_decision_functions.py

    def _log_llm_decisions(self, task, result: Dict, success: bool) -> List[Dict]:
        """Helper method to log LLM decisions and generate extra_actions"""
        extra_actions = []
        autonomous_decisions = self.context.get_data("autonomous_decisions", 0)
        
        if task.type == TaskType.EXPLORE and success:
            # Add file priority assessment actions
            files = result.get("result", {}).get("files", [])
            if files:
                extra_actions.append({
                    "action": "PRIORITY_ASSESSMENT",
                    "target": f"{len(files)} files",
                    "result": "LLM analysis completed"
                })
            
            # Add autonomous decision actions
            if autonomous_decisions > 0:
                extra_actions.extend(self._create_decision_actions("AUTONOMOUS_DECISIONS", autonomous_decisions, 5))

        elif task.type == TaskType.READ and result.get("success", False):
            # Add content analysis actions
            extra_actions.append({
                "action": "CONTENT_ANALYSIS",
                "target": task.target,
                "result": "Security analysis completed"
            })
            
            # Add follow-up decision actions
            if autonomous_decisions > 0:
                extra_actions.extend(self._create_decision_actions("CONTENT_FOLLOW_UP", autonomous_decisions, 3))
        
        return extra_actions

    def _create_decision_actions(self, action_type: str, decision_count: int, limit: int) -> List[Dict]:
        """Helper method to create decision action entries"""
        last_decisions = self.context.get_data("last_llm_decisions", [])
        actions = []
        
        if last_decisions:
            decision_details = []
            for decision in last_decisions[:limit]:
                if isinstance(decision, dict):
                    target = decision.get("path", "unknown")
                    decision_action_type = decision.get("type", "unknown")
                    reason = decision.get("reason", "")
                    decision_details.append(f"{decision_action_type}: {target} ({reason})")
            
            if decision_details:
                result_text = f"Decisions: {'; '.join(decision_details)}" if action_type == "AUTONOMOUS_DECISIONS" else f"Follow-ups: {'; '.join(decision_details)}"
                actions.append({
                    "action": action_type,
                    "target": f"{len(last_decisions)} LLM decisions made" if action_type == "AUTONOMOUS_DECISIONS" else f"{len(last_decisions)} follow-up decisions",
                    "result": result_text
                })
            else:
                result_text = "Tasks added to queue" if action_type == "AUTONOMOUS_DECISIONS" else "Follow-up tasks added"
                actions.append({
                    "action": action_type,
                    "target": f"{decision_count} LLM decisions",
                    "result": result_text
                })
        else:
            result_text = "Tasks added to queue" if action_type == "AUTONOMOUS_DECISIONS" else "Follow-up tasks added"
            actions.append({
                "action": action_type,
                "target": f"{decision_count} LLM decisions",
                "result": result_text
            })
        
        return actions

    def _update_decision_context(self, analysis_state: Dict) -> None:
        """Helper method to update context with decision results"""
        decision_result = analysis_state.get('decision_result')
        if decision_result and decision_result.get("decisions_made", 0) > 0:
            # Handle exploration decisions (replace previous)
            if analysis_state.get('decision_type') == 'exploration':
                self.context.set_data("autonomous_decisions", decision_result["decisions_made"])
                self.context.set_data("last_llm_decisions", decision_result.get("decision_details", []))
            # Handle content decisions (append to existing)
            else:
                current_decisions = self.context.get_data("autonomous_decisions", 0)
                self.context.set_data("autonomous_decisions", current_decisions + decision_result["decisions_made"])
                
                current_details = self.context.get_data("last_llm_decisions", [])
                current_details.extend(decision_result.get("decision_details", []))
                self.context.set_data("last_llm_decisions", current_details)
        
        # Clean up temporary data
        analysis_state.pop('decision_result', None)
        analysis_state.pop('decision_type', None)

    def _autonomous_context_reassessment(self) -> None:
        """CORE INNOVATION: LLM-driven strategic context reassessment"""
        try:
            print("  [AUTONOMOUS_REASSESSMENT] Starting strategic context reassessment...")

            # Use decision engine for autonomous context reassessment (core innovation)
            self.decision_engine.autonomous_context_reassessment(
                self.context_manager, self.task_queue, self.context, self.tools, self.dynamic_focus.current_focus
            )
            
            print("  [AUTONOMOUS_REASSESSMENT] Context reassessment completed")

        except Exception as e:
            print(f"  [AUTONOMOUS_REASSESSMENT] Context reassessment failed: {e}")
            # Continue analysis without reassessment

    def _execute_reassessment_decisions(self, decisions: Dict, unexplored_root_dirs: List[str],
                                      unexplored_subdirs: List[str]) -> None:
        """Execute strategic decisions from LLM reassessment"""
        from ..tools.core.task import Task, TaskType

        next_actions = decisions.get("next_actions", [])
        executed_count = 0

        print(f"  [STRATEGY] {decisions.get('strategy_explanation', 'Strategic planning completed')}")

        for action in next_actions:
            action_type = action.get("action", "")
            target = action.get("target", "")
            priority = action.get("priority", "medium")
            reason = action.get("reason", "")

            # Improved target validation with better path resolution
            valid_target = False
            normalized_target = target.strip('/')

            if action_type == "explore_directory":
                # Check against unexplored directories with better path matching
                for unexplored in unexplored_root_dirs + unexplored_subdirs:
                    unexplored_normalized = unexplored.strip('/')
                    if (normalized_target == unexplored_normalized or
                        normalized_target.endswith(unexplored_normalized) or
                        unexplored_normalized.endswith(normalized_target)):
                        valid_target = True
                        target = unexplored  # Use the original path from unexplored list
                        break

                # Additional check: verify directory actually exists and is not explored
                if valid_target:
                    full_path = self.repo_path / target
                    if not full_path.exists() or not full_path.is_dir():
                        valid_target = False
                        print(f"  [SKIP] Directory does not exist: {target}")
                    elif self.context.is_directory_explored(target):
                        valid_target = False
                        print(f"  [SKIP] Directory already explored: {target}")

            elif action_type == "analyze_file":
                # For file analysis, validate that the file exists and hasn't been analyzed
                full_path = self.repo_path / normalized_target
                if full_path.exists() and full_path.is_file():
                    if not self.context.is_file_analyzed(normalized_target):
                        valid_target = True
                        target = normalized_target
                    else:
                        print(f"  [SKIP] File already analyzed: {normalized_target}")
                else:
                    print(f"  [SKIP] File does not exist: {normalized_target}")

            if not valid_target:
                print(f"  [SKIP] Target not valid for execution: {target}")
                continue

            # Create appropriate task with improved error handling
            try:
                # Unified priority mapping
                from ..tools.core.task import PRIORITY_MAPPING
                task_priority = PRIORITY_MAPPING.get(priority, PRIORITY_MAPPING["default"])
                
                if action_type == "explore_directory":
                    task = Task(type=TaskType.EXPLORE, target=target, priority=task_priority)
                    print(f"  [EXPLORE] {target} (priority: {task_priority}) - {reason}")
                elif action_type == "analyze_file":
                    task = Task(type=TaskType.READ, target=target, priority=task_priority)
                    print(f"  [ANALYZE] {target} (priority: {task_priority}) - {reason}")

                self.task_queue.add_task(task)
                executed_count += 1

            except Exception as e:
                print(f"  [ERROR] Failed to create task for {target}: {e}")
                continue

            if executed_count >= 3:  # Respect LLM's limit
                break

        print(f"  [SUCCESS] Added {executed_count} strategic tasks")

    # def _find_related_files_from_content(self, content: str) -> List[str]:
    #     """Find files that are imported or referenced in the content"""
    #     related_files = []

    #     # Python import patterns
    #     if 'import ' in content or 'from ' in content:
    #         import_matches = re.findall(r'(?:import|from)\s+([a-zA-Z0-9_.]+)', content)
    #         for match in import_matches:
    #             # Convert module name to potential file path
    #             file_candidate = match.replace('.', '/') + '.py'
    #             if '/' in file_candidate:
    #                 related_files.append(file_candidate)

    #     # JavaScript/TypeScript import patterns
    #     js_import_patterns = [
    #         r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
    #         r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
    #     ]

    #     for pattern in js_import_patterns:
    #         matches = re.findall(pattern, content)
    #         for match in matches:
    #             if match.endswith(('.js', '.ts', '.json')):
    #                 related_files.append(match)

    #     return related_files  # Return all related files

    # def _find_referenced_files_from_config(self, content: str) -> List[str]:
    #     """Find files referenced in configuration files"""
    #     referenced_files = []

    #     try:
    #         # Try to parse as JSON first
    #         if content.strip().startswith('{'):
    #             config_data = json.loads(content)
    #             self._extract_file_paths_from_dict(config_data, referenced_files)
    #         else:
    #             # For non-JSON files, use more restrictive pattern matching
    #             # Only match strings that look like actual file paths
    #             file_matches = re.findall(r'[\'"]([^\'"]*\.[a-zA-Z]{2,4})[\'"]', content)
    #             valid_files = []
    #             for match in file_matches:
    #                 # Skip version numbers (must contain at least one letter)
    #                 if not re.search(r'[a-zA-Z]', match):
    #                     continue
    #                 # Skip if too short (less than 3 characters before extension)
    #                 name_part = match.rsplit('.', 1)[0] if '.' in match else match
    #                 if len(name_part) < 3:
    #                     continue
    #                 # Must contain path indicators or be a reasonable filename
    #                 if ('/' in match or '\\' in match or
    #                     match.startswith('./') or match.startswith('../') or
    #                     len(match) >= 5):  # Reasonable minimum length for a filename
    #                     valid_files.append(match)

    #             referenced_files.extend(valid_files)
    #     except:
    #         # Fallback with even more restrictive pattern
    #         file_matches = re.findall(r'[\'"]([a-zA-Z0-9_\-]+\.[a-zA-Z]{2,4})[\'"]', content)
    #         valid_files = []
    #         for match in file_matches:
    #             # Additional validation
    #             if len(match) >= 5 and not match.replace('.', '').replace('_', '').replace('-', '').isdigit():
    #                 valid_files.append(match)

    #         referenced_files.extend(valid_files)

    #     return referenced_files
    def _find_related_files_from_content(self, content: str, file_path: str = None) -> List[str]:
        """
        Find files that are imported or referenced in the content.
        Direct replacement for the original function using MCP Language Server.

        Args:
            content: File content to analyze
            file_path: Optional path to the current file being analyzed (for relative path resolution)

        Returns:
            List of related file paths
        """
        # Check cache first
        if file_path and file_path in self._mcp_cache['related_files']:
            print(f"  [MCP_CACHE_HIT] Using cached related files for: {file_path}")
            return self._mcp_cache['related_files'][file_path]

        print(f"  [MCP_ANALYSIS] Starting MCP-powered related files analysis...")
        if file_path:
            print(f"  [MCP_ANALYSIS] Analyzing file: {file_path}")

        try:
            # CRITICAL: Use MINIMAL workspace (file's direct parent directory ONLY)
            # to prevent LSP from scanning 2389+ files and pushing diagnostics for ALL files
            if file_path:
                file_abs_path = self.repo_path / file_path
                # Use ONLY the file's parent directory (NOT parent's parent!)
                # This minimizes LSP scan scope and diagnostic pushes
                workspace_dir = file_abs_path.parent

                # Ensure workspace stays within repo bounds
                if str(workspace_dir).startswith(str(self.repo_path)):
                    workspace = str(workspace_dir)
                else:
                    workspace = str(self.repo_path)  # Fallback (rarely needed)
            else:
                # If no file_path provided, use repo root as last resort
                workspace = str(self.repo_path)
                print(f"  [MCP_WORKSPACE] WARNING: No file_path provided, using repo root (may be slow!)")

            print(f"  [MCP_WORKSPACE] Using MINIMAL workspace (file's parent dir only): {workspace}")
            print(f"  [MCP_WORKSPACE] This limits LSP scan scope to avoid processing 2389+ files")
            runner = get_runner(workspace=workspace)

            # Detect the file type from content
            file_type = "unknown"
            if 'import ' in content and 'from ' in content and ':' in content:
                file_type = "python"
            elif 'import ' in content or 'require(' in content:
                file_type = "javascript"

            print(f"  [MCP_ANALYSIS] Detected file type: {file_type}")

            # Construct file URI for LSP
            file_uri = f"file://{self.repo_path}/{file_path}" if not file_path.startswith('/') else f"file://{file_path}"

            # Create a more specific prompt that instructs the agent to use LSP tools
            prompt = f"""Analyze file dependencies using LSP tools.

FILE URI: {file_uri}
FILE PATH: {file_path}

TASK:
1. Use lsp_textDocument_documentSymbol on the file URI to get all symbols/imports
2. For each import symbol, use lsp_textDocument_definition to resolve the actual file path
3. Return a JSON array of the resolved file paths

The file contains:
```
{content[:500]}
```

IMPORTANT: Use the MCP LSP tools! Return ONLY a JSON array of local file paths.
Example: ["src/utils/helper.py", "lib/models/user.py"]

Return [] if no dependencies found."""

            print(f"  [MCP_ANALYSIS] Running MCP agent analysis...")
            response = runner.run(prompt)
            print(f"  [MCP_ANALYSIS] MCP raw response: {response[:200]}...")

            files = runner.extract_file_list(response)
            print(f"  [MCP_ANALYSIS] Extracted files: {files}")

            # Post-process to match original function behavior and handle relative paths
            processed_files = []
            base_dir = str(Path(file_path).parent) if file_path else ""

            for file in files:
                processed_file = file

                # Handle relative paths
                if file.startswith('./') or file.startswith('../'):
                    if file_path:
                        # Resolve relative path relative to the current file's directory
                        try:
                            resolved_path = Path(base_dir) / file
                            processed_file = str(resolved_path.resolve().relative_to(self.repo_path))
                            print(f"  [MCP_ANALYSIS] Resolved relative path: {file} -> {processed_file}")
                        except Exception as e:
                            print(f"  [MCP_ANALYSIS] Failed to resolve relative path {file}: {e}")
                            processed_file = file

                # Ensure we only include files with paths (containing /) or files with extensions
                if '/' in processed_file or processed_file.endswith(('.py', '.js', '.ts', '.json', '.tsx', '.jsx')):
                    processed_files.append(processed_file)
                    print(f"  [MCP_ANALYSIS] Added processed file: {processed_file}")

            print(f"  [MCP_ANALYSIS] Final processed files: {processed_files}")

            # Cache the result
            if file_path:
                self._mcp_cache['related_files'][file_path] = processed_files
                print(f"  [MCP_CACHE_SAVE] Cached related files for: {file_path}")

            return processed_files

        except Exception:
            raise
    
    def _find_referenced_files_from_config(self, content: str, file_path: str = None) -> List[str]:
        """
        Find files referenced in configuration files.
        Direct replacement for the original function using MCP Language Server.

        Args:
            content: Configuration file content
            file_path: Optional path to the current file being analyzed

        Returns:
            List of referenced file paths
        """
        # Check cache first
        if file_path and file_path in self._mcp_cache['config_files']:
            print(f"  [MCP_CACHE_HIT] Using cached config files for: {file_path}")
            return self._mcp_cache['config_files'][file_path]

        print(f"  [MCP_CONFIG] Starting MCP-powered config file analysis...")
        if file_path:
            print(f"  [MCP_CONFIG] Analyzing config file: {file_path}")

        try:
            # CRITICAL: Use MINIMAL workspace (file's direct parent directory ONLY)
            # For config files, using parent dir limits LSP scope and prevents
            # scanning 2389+ files with diagnostics pushes that cause system hangs
            if file_path:
                file_abs_path = self.repo_path / file_path
                # Use ONLY the file's parent directory (NOT grandparent!)
                workspace_dir = file_abs_path.parent

                # Ensure workspace stays within repo bounds
                if str(workspace_dir).startswith(str(self.repo_path)):
                    workspace = str(workspace_dir)
                else:
                    workspace = str(self.repo_path)  # Fallback (rarely needed)
            else:
                # If no file_path, use repo root as last resort
                workspace = str(self.repo_path)
                print(f"  [MCP_WORKSPACE] WARNING: No file_path for config, using repo root (may be slow!)")

            print(f"  [MCP_WORKSPACE] Using MINIMAL config workspace (parent dir only): {workspace}")
            print(f"  [MCP_WORKSPACE] This avoids LSP scanning entire repo (2389+ files)")
            runner = get_runner(workspace=workspace)

            # Detect config type from content
            config_type = "generic configuration"
            if '"scripts"' in content and '"dependencies"' in content:
                config_type = "package.json"
            elif '[tool.poetry]' in content or '[build-system]' in content:
                config_type = "pyproject.toml"
            elif content.strip().startswith('{'):
                config_type = "JSON configuration"

            print(f"  [MCP_CONFIG] Detected config type: {config_type}")
        
            prompt = f"""
            Analyze this {config_type} file content and find all local files it references.

            Configuration content:
            ```
            {content[:5000]}  # Limit to first 5000 chars
            ```

            Look for:
            - Entry points and main files
            - Script file paths
            - Build input/output files
            - Asset files
            - Test files
            - Any file paths in strings

            Return ONLY a JSON array of file paths that look like actual project files.
            Example: ["src/index.js", "dist/bundle.js", "config/settings.json"]

            Rules:
            - Only include paths with file extensions
            - Must be at least 5 characters long (like original function)
            - Skip version numbers (must contain letters)
            - Use forward slashes
            - Return empty array [] if no files found
            """

            print(f"  [MCP_CONFIG] Running MCP config analysis...")
            response = runner.run(prompt)
            print(f"  [MCP_CONFIG] MCP raw response: {response[:200]}...")

            files = runner.extract_file_list(response)
            print(f"  [MCP_CONFIG] Extracted files: {files}")

            # Filter to match original function validation rules
            valid_files = []
            base_dir = str(Path(file_path).parent) if file_path else ""

            for file in files:
                processed_file = file

                # Handle relative paths
                if file.startswith('./') or file.startswith('../'):
                    if file_path:
                        try:
                            resolved_path = Path(base_dir) / file
                            processed_file = str(resolved_path.resolve().relative_to(self.repo_path))
                            print(f"  [MCP_CONFIG] Resolved relative path: {file} -> {processed_file}")
                        except Exception as e:
                            print(f"  [MCP_CONFIG] Failed to resolve relative path {file}: {e}")
                            processed_file = file

                # Skip if too short
                if len(processed_file) < 5:
                    continue

                # Must have an extension
                if '.' not in processed_file:
                    continue

                # Get the name part before extension
                name_part = processed_file.rsplit('.', 1)[0]
                if len(name_part) < 3:
                    continue

                # Must contain at least one letter (skip pure numbers/versions)
                if not re.search(r'[a-zA-Z]', processed_file):
                    continue

                valid_files.append(processed_file)
                print(f"  [MCP_CONFIG] Added valid config file: {processed_file}")

            print(f"  [MCP_CONFIG] Final valid files: {valid_files}")

            # Cache the result
            if file_path:
                self._mcp_cache['config_files'][file_path] = valid_files
                print(f"  [MCP_CACHE_SAVE] Cached config files for: {file_path}")

            return valid_files

        except Exception as e:
            print(f"  [MCP_CONFIG] MCP language server not available: {e}")
            print(f"  [MCP_CONFIG] Falling back to simple config file analysis...")
            # Fallback to basic pattern matching when MCP is not available
            return self._fallback_find_config_files(content, file_path)

    def _fallback_find_config_files(self, content: str, file_path: str = None) -> List[str]:
        """Fallback method for finding config files when MCP is not available"""
        referenced_files = []
        
        try:
            import json
            import re
            # Try to parse as JSON first
            if content.strip().startswith('{'):
                config_data = json.loads(content)
                self._extract_file_paths_from_dict(config_data, referenced_files)
            else:
                # For non-JSON files, use pattern matching
                file_matches = re.findall(r'[\'"]([^\'"]*\.[a-zA-Z]{2,4})[\'"]', content)
                valid_files = []
                for match in file_matches:
                    # Skip version numbers (must contain at least one letter)
                    if not re.search(r'[a-zA-Z]', match):
                        continue
                    # Skip if too short (less than 3 characters before extension)
                    name_part = match.rsplit('.', 1)[0] if '.' in match else match
                    if len(name_part) < 3:
                        continue
                    # Must contain path indicators or be a reasonable filename
                    if ('/' in match or '\\' in match or
                        match.startswith('./') or match.startswith('../') or
                        len(match) >= 5):  # Reasonable minimum length for a filename
                        valid_files.append(match)
                
                referenced_files.extend(valid_files)
        except:
            # Fallback with even more restrictive pattern
            file_matches = re.findall(r'[\'"]([a-zA-Z0-9_\-]+\.[a-zA-Z]{2,4})[\'"]', content)
            valid_files = []
            for match in file_matches:
                # Additional validation
                if len(match) >= 5 and not match.replace('.', '').replace('_', '').replace('-', '').isdigit():
                    valid_files.append(match)
            
            referenced_files.extend(valid_files)
        
        print(f"  [FALLBACK] Found {len(referenced_files)} config references using pattern matching")
        return referenced_files[:10]  # Limit to top 10

    def _extract_file_paths_from_dict(self, data: Dict, file_list: List[str]) -> None:
        """Recursively extract file paths from nested dictionary"""
        for key, value in data.items():
            if isinstance(value, str) and '.' in value:
                extension = value.split('.')[-1]
                # Only consider it a file path if extension is reasonable and value looks like a filename
                if (len(extension) >= 2 and len(extension) <= 4 and extension.isalnum() and
                    len(value) >= 4 and not value.replace('.', '').replace('/', '').replace('\\', '').isdigit()):
                    # Additional validation: must contain letters or be a reasonable file path
                    if (re.search(r'[a-zA-Z]', value) or '/' in value or '\\' in value or
                        value.startswith('./') or value.startswith('../')):
                        file_list.append(value)
            elif isinstance(value, dict):
                self._extract_file_paths_from_dict(value, file_list)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._extract_file_paths_from_dict(item, file_list)

    # REMOVED: _investigate_related_files - was rule-based, now handled by LLM decisions
    
    def get_file_diagnostics_optimized(self, file_path: str, max_diagnostics: int = 10) -> List[dict]:
        """
        Get diagnostics for a single file only (optimized to avoid workspace-wide scans).
        This method prevents system hangs when processing large workspaces by:
        1. Only requesting diagnostics for the specific file being analyzed
        2. Using a limited workspace scope (file's parent directory)
        3. Filtering and extracting only useful diagnostic information
        
        Args:
            file_path: Path to the file to analyze (relative to repo_path)
            max_diagnostics: Maximum number of diagnostics to return (default: 10)
            
        Returns:
            List of filtered diagnostic objects with useful information
        """
        try:
            # Check cache first
            cache_key = f"diagnostics_{file_path}"
            if cache_key in self._mcp_cache.get('diagnostics', {}):
                print(f"  [DIAGNOSTICS_CACHE_HIT] Using cached diagnostics for: {file_path}")
                return self._mcp_cache['diagnostics'][cache_key]
            
            # Initialize diagnostics cache if not exists
            if 'diagnostics' not in self._mcp_cache:
                self._mcp_cache['diagnostics'] = {}
            
            # CRITICAL: Use MINIMAL workspace scope (file's parent directory ONLY)
            # Even with single-file diagnostic requests, LSP scans the entire workspace
            # and pushes diagnostics for ALL files, causing hangs with 2389+ files
            file_abs_path = self.repo_path / file_path
            if not file_abs_path.exists():
                print(f"  [DIAGNOSTICS] File not found: {file_path}")
                return []
            
            # Use ONLY the file's direct parent directory
            workspace_dir = file_abs_path.parent
            
            # Ensure workspace stays within repo bounds
            if not str(workspace_dir).startswith(str(self.repo_path)):
                workspace_dir = self.repo_path
                print(f"  [DIAGNOSTICS] WARNING: Workspace outside repo, using repo root")
            
            print(f"  [DIAGNOSTICS] Using MINIMAL workspace (parent dir only): {workspace_dir}")
            print(f"  [DIAGNOSTICS] NOTE: Diagnostics are currently DISABLED to prevent system hangs")
            print(f"  [DIAGNOSTICS] Reason: LSP pushes ALL workspace file diagnostics after scan")
            
            # Get the MCP runner with limited workspace scope
            runner = get_runner(workspace=str(workspace_dir))
            
            # Construct file URI
            file_uri = f"file://{file_abs_path}"
            
            # Use the new optimized method from mcp_agent
            diagnostics = runner.get_file_diagnostics(file_uri, max_diagnostics)
            
            # Cache the result
            self._mcp_cache['diagnostics'][cache_key] = diagnostics
            
            if diagnostics:
                print(f"  [DIAGNOSTICS] Found {len(diagnostics)} useful diagnostics for {file_path}")
                # Print summary of diagnostics by severity
                severity_counts = {}
                for diag in diagnostics:
                    severity = diag.get("severity", "unknown")
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                print(f"  [DIAGNOSTICS] Severity breakdown: {severity_counts}")
            else:
                print(f"  [DIAGNOSTICS] No diagnostics found for {file_path}")
            
            return diagnostics
            
        except Exception as e:
            print(f"  [DIAGNOSTICS_ERROR] Failed to get diagnostics for {file_path}: {e}")
            return []
    
    def _execute_task(self, task) -> Dict[str, Any]:
        """Execute a single task and return standardized result format with improved path resolution"""
        import time
        start_time = time.time()

        result_template = {
            "success": False,
            "task_id": task.task_id,
            "task_type": task.type.value,
            "target": task.target,
            "duration": 0.0,
            "result": None,
            "error": None
        }

        try:
            # Final deduplication check before execution
            if task.type == TaskType.READ and self.context.is_file_analyzed(task.target):
                duration = time.time() - start_time
                result_template.update({
                    "success": False,
                    "duration": duration,
                    "error": f"File already analyzed: {task.target} (duplicate detected at execution time)"
                })
                print(f"    [DUPLICATE_SKIP] File already analyzed: {task.target}")
                return result_template
            elif task.type == TaskType.EXPLORE and self.context.is_directory_explored(task.target):
                duration = time.time() - start_time
                result_template.update({
                    "success": False,
                    "duration": duration,
                    "error": f"Directory already explored: {task.target} (duplicate detected at execution time)"
                })
                print(f"    [DUPLICATE_SKIP] Directory already explored: {task.target}")
                return result_template

            # Improved path resolution and validation
            target_path = task.target.strip()
            # Handle relative paths correctly
            if target_path.startswith('./'):
                # Remove ./ prefix and resolve relative to repo_path
                clean_path = target_path[2:]
                full_path = self.repo_path / clean_path
            elif target_path.startswith('/'):
                # Absolute path - use as is
                from pathlib import Path
                full_path = Path(target_path)
            else:
                # Relative path - resolve relative to repo_path
                full_path = self.repo_path / target_path

            # Skip execution if target path is obviously invalid (like hardcoded example paths)
            if self._is_invalid_target_path(target_path):
                duration = time.time() - start_time
                result_template.update({
                    "success": False,
                    "duration": duration,
                    "error": f"Invalid target path: {target_path} (appears to be example/placeholder path)"
                })
                return result_template

            if task.type == TaskType.EXPLORE:
                print(f"    Executing EXPLORE on: {target_path}")
                print(f"    Repo path: {self.repo_path}")
                print(f"    Full target path: {full_path}")
                print(f"    Target path exists: {full_path.exists()}")
                print(f"    Target path is dir: {full_path.is_dir() if full_path.exists() else 'N/A'}")

                # Additional validation for exploration
                if not full_path.exists():
                    duration = time.time() - start_time
                    result_template.update({
                        "success": False,
                        "duration": duration,
                        "error": f"Directory not found: {target_path}"
                    })
                    return result_template

                if not full_path.is_dir():
                    duration = time.time() - start_time
                    result_template.update({
                        "success": False,
                        "duration": duration,
                        "error": f"Path is not a directory: {target_path}"
                    })
                    return result_template

                result_data = self.tools.list_directory(target_path)
                print(f"    List directory result: {result_data}")

            elif task.type == TaskType.READ:
                print(f"    Executing READ on: {target_path}")
                print(f"    Full path: {full_path}")

                # Additional validation for file reading
                if not full_path.exists():
                    duration = time.time() - start_time
                    result_template.update({
                        "success": False,
                        "duration": duration,
                        "error": f"File not found: {target_path}"
                    })
                    return result_template

                if not full_path.is_file():
                    duration = time.time() - start_time
                    result_template.update({
                        "success": False,
                        "duration": duration,
                        "error": f"Path is not a file: {target_path}"
                    })
                    return result_template

                # Check file size to avoid reading very large files
                file_size = full_path.stat().st_size
                if file_size > 50 * 1024 * 1024:  # 50MB limit
                    duration = time.time() - start_time
                    result_template.update({
                        "success": False,
                        "duration": duration,
                        "error": f"File too large to read: {target_path} ({file_size} bytes)"
                    })
                    return result_template

                result_data = self.tools.read_file(target_path)

            elif task.type == TaskType.ANALYZE:
                print(f"    Executing ANALYZE on: {target_path}")

                # First check if file exists and is readable
                if not full_path.exists() or not full_path.is_file():
                    duration = time.time() - start_time
                    result_template.update({
                        "success": False,
                        "duration": duration,
                        "error": f"File not found or not readable: {target_path}"
                    })
                    return result_template

                file_result = self.tools.read_file(target_path)
                if "error" not in file_result:
                    try:
                        # Use LLM for code snippet analysis
                        llm_analysis = self.llm.analyze_code_snippet(
                            file_result["content"],
                            target_path
                        )
                        result_data = {
                            "file_info": file_result,
                            "llm_analysis": llm_analysis
                        }
                    except Exception as e:
                        # Fallback to file content if LLM analysis fails
                        result_data = {
                            "file_info": file_result,
                            "llm_error": str(e)
                        }
                else:
                    result_data = file_result
            else:
                raise ValueError(f"Unknown task type: {task.type}")

            duration = time.time() - start_time
            result_template.update({
                "success": "error" not in result_data,
                "duration": duration,
                "result": result_data
            })

            if "error" in result_data:
                result_template["error"] = result_data["error"]

        except Exception as e:
            duration = time.time() - start_time
            result_template.update({
                "success": False,
                "duration": duration,
                "error": str(e)
            })

        return result_template

    def _is_invalid_target_path(self, target_path: str) -> bool:
        """Check if a target path is obviously invalid (like example/placeholder paths)"""
        invalid_patterns = [
            "path/to/",  # Generic example paths
            "example/",  # Example directories
            "placeholder",  # Placeholder text
            "dummy",  # Dummy files
            "sample",  # Sample files
            "template/file",  # Template paths
            "your/file",  # Generic placeholders
            "some/file",  # Generic placeholders
            "any/file",  # Generic placeholders
        ]

        target_lower = target_path.lower()
        return any(pattern in target_lower for pattern in invalid_patterns)
    
    def _build_comprehensive_priority_context(self, explored_path: str, files: List[str]) -> str:
        """Build comprehensive context including existing discoveries for intelligent priority assessment"""
        
        # Basic repository info
        context = f"""REPOSITORY ANALYSIS CONTEXT:
- Currently exploring: {explored_path}
- Repository root: {self.repo_path.name}
- Total files discovered: {len(files)}

**EXISTING ANALYSIS DISCOVERIES:**
"""
        
        # Add security findings summary
        security_summary = self.context_manager.get_security_summary()
        analyzed_files = list(self.context.get_analyzed_files())
        context += f"""
SECURITY ANALYSIS STATE:
- Files analyzed so far: {len(analyzed_files)}
- Security findings: {security_summary.get('total_findings', 0)} total
  - HIGH risk: {security_summary.get('high_risk_count', 0)} files
  - MEDIUM risk: {security_summary.get('medium_risk_count', 0)} files  
  - LOW risk: {security_summary.get('low_risk_count', 0)} files
"""
        
        # Add high-risk file details if any
        high_risk_details = []
        for file_path in analyzed_files[-10:]:  # Last 10 analyzed files
            analysis_result = self.context_manager.get_analysis_result(file_path)
            if analysis_result and analysis_result.get('security_risk') == 'high':
                findings_count = len(analysis_result.get('key_findings', []))
                high_risk_details.append(f"  - {file_path}: {findings_count} security findings")
        
        if high_risk_details:
            context += f"\nHIGH-RISK FILES DISCOVERED:\n" + "\n".join(high_risk_details)
            context += f"\n→ Consider prioritizing files RELATED to these high-risk findings"
        else:
            context += f"\nNo high-risk files found yet - focus on identifying injection points"
        
        # Add file type patterns discovered
        file_types = {}
        for file_path in analyzed_files:
            ext = file_path.split('.')[-1] if '.' in file_path else 'no_ext'
            file_types[ext] = file_types.get(ext, 0) + 1
        
        if file_types:
            context += f"\n\nFILE TYPES ANALYZED:\n"
            sorted_types = sorted(file_types.items(), key=lambda x: -x[1])
            for ext, count in sorted_types[:5]:
                context += f"  - .{ext}: {count} files analyzed\n"
            context += f"→ Consider similar file types in current directory for consistency"
        
        # Add workflow insights from context
        workflow_insights = self.context.get_data("workflow_insights", [])
        if workflow_insights:
            context += f"\nWORKFLOW PATTERNS DISCOVERED:\n"
            for insight in workflow_insights[-3:]:
                context += f"  - {insight}\n"
            context += f"→ Prioritize files that complete these workflow patterns"
        
        # Add current directory context
        context += f"\n\n**CURRENT DIRECTORY FILES (choose ONLY from this list):**\n"
        for i, file in enumerate(files, 1):
            context += f"{i}. {file}\n"
            
        # Add strategic guidance based on discoveries
        context += f"\n**INTELLIGENT PRIORITIZATION STRATEGY:**\n"
        
        if high_risk_details:
            context += f"- PRIORITIZE files that are likely RELATED to the high-risk files found\n"
            context += f"- Look for configuration, dependency, or import relationships\n"
        
        if len(analyzed_files) < 5:
            context += f"- EARLY STAGE: Focus on core system files (main, config, setup)\n"
        else:
            context += f"- FOLLOW-UP STAGE: Build on existing discoveries and fill knowledge gaps\n"
            
        context += f"- Consider file naming patterns and directory structure\n"
        context += f"- Focus on agent/LLM interaction points based on filename analysis\n"
        
        return context
    
    def _llm_should_reassess_decision(self, current_step: int, last_reassess_step: int) -> tuple[bool, str]:
        """DISCOVERY-DRIVEN LLM reassessment decision - triggers on significant findings"""
        
        try:
            # CRITICAL: Check for new significant findings since last reassessment
            recent_findings = self._get_new_findings_since_step(last_reassess_step)
            
            # IMMEDIATE triggers - don't wait for periodic check
            if self.focus_tracker.should_trigger_reassessment(recent_findings):
                return True, f"DISCOVERY-DRIVEN: Found {len(recent_findings)} significant findings requiring immediate focus"
            
            # Check if current focus needs attention
            primary_focus = self.focus_tracker.get_primary_focus()
            if primary_focus and len(primary_focus.leads_to_follow) > 0:
                return True, f"FOCUS-DRIVEN: Active focus '{primary_focus.target}' has {len(primary_focus.leads_to_follow)} leads to pursue"
            
            # Check if we're stuck analyzing low-value files repeatedly
            recent_files = list(self.context.get_analyzed_files())[-5:] if self.context.get_analyzed_files() else []
            config_file_count = sum(1 for f in recent_files if any(pattern in f.lower() for pattern in ['config', 'toml', 'yml', 'ini']))
            if config_file_count >= 3:
                return True, "ANTI-STAGNATION: Too many config files analyzed - need to diversify focus"
            
            # Get comprehensive analysis context
            comprehensive_context = self.context_manager.get_comprehensive_analysis_context()
            
            # Build current state info
            current_state = {
                'step': current_step,
                'analyzed_files': len(self.context.get_analyzed_files()),
                'steps_since_last': current_step - last_reassess_step,
                'recent_findings': len(recent_findings),
                'active_focuses': len(self.focus_tracker.active_focuses),
                'stagnation_risk': config_file_count >= 2
            }
            
            # Build task queue info
            task_queue_info = {
                'pending_count': self.task_queue.pending_count(),
                'highest_priority': self.task_queue.get_highest_priority(),
                'focus_targets_pending': len(self.focus_tracker.get_next_investigation_targets(
                    analyzed_files=self.context.get_analyzed_files(),
                    explored_directories=self.context.get_explored_directories()
                ))
            }
            
            # Get comprehensive data
            security_findings = comprehensive_context.get('security_findings', [])
            workflow_analysis = comprehensive_context.get('workflow_analysis', {})
            
            # Enhanced prompt with focus context
            decision_prompt = PromptManager.get_focus_aware_reassessment_prompt(
                current_state=current_state,
                security_findings=security_findings,
                workflow_patterns=workflow_analysis,
                task_queue_info=task_queue_info,
                focus_summary=self.focus_tracker.get_focus_summary(),
                primary_focus=self.focus_tracker.get_primary_focus()
            )
            
            # Ask LLM for intelligent decision
            model = LLMClient.get_model("analysis")
            messages = [
                {"role": "system", "content": "You are an intelligent agent injection analysis strategist making strategic reassessment decisions based on comprehensive security discoveries and workflow patterns."},
                {"role": "user", "content": decision_prompt}
            ]
            
            decision_text = LLMClient.call_llm(
                model=model,
                messages=messages,
                max_tokens=500,
                temperature=0.4,
                timeout=25,
                max_retries=2
            )
            
            if decision_text:
                import json
                start = decision_text.find('{')
                end = decision_text.rfind('}') + 1
                if start != -1 and end > start:
                    decision_data = json.loads(decision_text[start:end])
                    
                    should_reassess = decision_data.get("should_reassess", False)
                    reasoning = decision_data.get("reasoning", "LLM discovery-driven decision")
                    confidence = decision_data.get("confidence", "medium")
                    priority_focus = decision_data.get("priority_focus", "")
                    discovery_impact = decision_data.get("discovery_impact", "")
                    
                    # Simplified LLM decision output
                    if should_reassess:
                        print(f"  [LLM] Queue reassessment needed: {reasoning[:100]}...")
                    
                    return should_reassess, reasoning
        
        except Exception as e:
            # LLM decision failed, return minimal defaults
            print(f"  [WARNING] LLM reassessment decision failed: {e}")
            return False, "LLM decision failed - continuing with current strategy"
    
    def _has_meaningful_discoveries(self) -> bool:
        """Check if we have meaningful discoveries that warrant reassessment"""
        # Must have analyzed at least a few files
        analyzed_count = len(self.context.get_analyzed_files())
        security_summary = self.context_manager.get_security_summary()
        total_findings = security_summary.get('total_findings', 0)
        high_risk_count = security_summary.get('high_risk_count', 0)
        medium_risk_count = security_summary.get('medium_risk_count', 0)
        
        print(f"  [MEANINGFUL_CHECK] Files analyzed: {analyzed_count}, Findings: {total_findings} (H:{high_risk_count}, M:{medium_risk_count})")
        
        # More lenient criteria - either enough files OR security findings
        has_enough_files = analyzed_count >= 2  # Reduced from 3 to 2
        has_security_findings = total_findings > 0 or high_risk_count > 0 or medium_risk_count > 0
        
        # Allow reassessment if we have either condition OR if we've done some analysis
        meaningful = has_enough_files or has_security_findings or analyzed_count >= 1
        
        print(f"  [MEANINGFUL_CHECK] Result: {meaningful} (files≥2: {has_enough_files}, findings: {has_security_findings}, analyzed≥1: {analyzed_count >= 1})")
        return meaningful
    
    def _intelligent_queue_reassessment(self) -> None:
        """CORE INNOVATION: Focus-driven intelligent task queue reassessment with deep investigation capability"""
        try:
            print("  [INTELLIGENT_REASSESS] Starting priority reassessment...")
            
            pending_tasks = self.task_queue.get_pending_tasks()
            if not pending_tasks:
                print("  [INTELLIGENT_REASSESS] No pending tasks to reassess")
                return
            
            # Build comprehensive context for LLM reassessment
            analyzed_files = list(self.context.get_analyzed_files())
            explored_dirs = list(self.context.get_explored_directories())
            current_discoveries = self._build_discoveries_context(analyzed_files, explored_dirs)
            pending_tasks_context = self._build_pending_tasks_context(pending_tasks)
            
            # Create LLM prompt for intelligent reassessment
            reassessment_prompt = PromptManager.get_queue_reassessment_prompt(
                current_discoveries, pending_tasks_context
            )
            
            # Get LLM decision on task prioritization
            model = LLMClient.get_model("analysis")
            messages = [
                {"role": "system", "content": "You are an intelligent agent security analyst making strategic task prioritization decisions based on discoveries."},
                {"role": "user", "content": reassessment_prompt}
            ]

            decision_text = LLMClient.call_llm(
                model=model, messages=messages, max_tokens=1000,
                temperature=0.4, timeout=25, max_retries=2
            )

            if decision_text:
                # Parse and apply priority updates (core innovation)
                priority_updates = self._parse_priority_reassessment(decision_text)
                if priority_updates:
                    updated_count = self.task_queue.reassess_priorities(priority_updates)
                    print(f"  [INTELLIGENT_REASSESS] Updated priorities for {updated_count} tasks")
                    
                    # Log the changes
                    for target, new_priority in list(priority_updates.items())[:3]:  # Show first 3
                        print(f"    → {target}: priority → {new_priority}")
                else:
                    print("  [INTELLIGENT_REASSESS] No priority changes recommended")
            else:
                print("  [INTELLIGENT_REASSESS] LLM reassessment failed")
                
        except Exception as e:
            print(f"  [INTELLIGENT_REASSESS] Error during reassessment: {e}")
            # Continue without reassessment
    
    def _build_discoveries_context(self, analyzed_files: List[str], explored_dirs: List[str]) -> str:
        """Build detailed context about actual discoveries for reassessment"""
        discoveries = f"""ACTUAL ANALYSIS DISCOVERIES:

FILES ANALYZED: {len(analyzed_files)} total
DIRECTORIES EXPLORED: {len(explored_dirs)} total

**CONCRETE SECURITY FINDINGS:**
"""
        
        # Get actual security findings from context manager
        security_summary = self.context_manager.get_security_summary()
        high_risk_count = security_summary.get('high_risk_count', 0)
        medium_risk_count = security_summary.get('medium_risk_count', 0)
        
        discoveries += f"""
- HIGH RISK files found: {high_risk_count}
- MEDIUM RISK files found: {medium_risk_count}
- Total security findings: {security_summary.get('total_findings', 0)}

**SPECIFIC HIGH-RISK DISCOVERIES:**
"""
        
        # Get detailed information about high-risk files with actual findings
        high_risk_details = []
        for file_path in analyzed_files[-15:]:  # Check last 15 analyzed files
            if self.context.get_data(f"security_concern_{file_path}", False):
                # Get actual analysis result
                analysis_result = self.context_manager.get_analysis_result(file_path)
                if analysis_result:
                    risk_level = analysis_result.get('security_risk', 'unknown')
                    findings_count = len(analysis_result.get('key_findings', []))
                    high_risk_details.append({
                        'file': file_path,
                        'risk': risk_level,
                        'findings_count': findings_count,
                        'file_type': file_path.split('.')[-1] if '.' in file_path else 'unknown'
                    })
        
        if high_risk_details:
            for detail in high_risk_details[-5:]:  # Show last 5 high-risk files
                discoveries += f"- {detail['file']} ({detail['risk']} risk, {detail['findings_count']} findings, {detail['file_type']} file)\n"
        else:
            discoveries += "- No high-risk files found in recent analysis\n"

        # Add file type distribution for workflow understanding
        file_types = {}
        for file_path in analyzed_files:
            ext = file_path.split('.')[-1] if '.' in file_path else 'no_ext'
            file_types[ext] = file_types.get(ext, 0) + 1
        
        if file_types:
            discoveries += f"\n**FILE TYPES ANALYZED:**\n"
            # Sort by count to show most common file types
            sorted_types = sorted(file_types.items(), key=lambda x: -x[1])
            for ext, count in sorted_types[:8]:  # Show top 8 file types
                discoveries += f"- .{ext}: {count} files\n"

        # Add directory structure insights
        discoveries += f"\n**EXPLORED DIRECTORY STRUCTURE:**\n"
        root_dirs = [d for d in explored_dirs if '/' not in d.strip('./')]
        sub_dirs = [d for d in explored_dirs if '/' in d.strip('./')]
        
        discoveries += f"- Root-level directories: {len(root_dirs)}\n"
        discoveries += f"- Sub-directories explored: {len(sub_dirs)}\n"
        
        if root_dirs:
            discoveries += f"- Root dirs: {', '.join(root_dirs[:5])}\n"
        
        return discoveries
    
    def _build_pending_tasks_context(self, pending_tasks: List) -> str:
        """Build context about pending tasks for reassessment"""
        context = f"""CURRENT TASK QUEUE ({len(pending_tasks)} pending tasks):
"""
        
        # Group by type and priority
        by_type = {}
        for task in pending_tasks:
            task_type = task.type.value
            if task_type not in by_type:
                by_type[task_type] = []
            by_type[task_type].append(task)
        
        for task_type, tasks in by_type.items():
            context += f"\n{task_type.upper()} tasks ({len(tasks)}):\n"
            # Show top 5 highest priority tasks of each type
            sorted_tasks = sorted(tasks, key=lambda t: -t.priority)
            for task in sorted_tasks[:5]:
                context += f"  - {task.target} (priority: {task.priority})\n"
            if len(tasks) > 5:
                context += f"  - ... and {len(tasks) - 5} more tasks\n"
        
        return context
    
    def _parse_priority_reassessment(self, decision_text: str) -> Dict[str, int]:
        """Parse and validate LLM decision for discovery-based priority updates"""
        try:
            import json
            start = decision_text.find('{')
            end = decision_text.rfind('}') + 1
            if start != -1 and end > start:
                json_text = decision_text[start:end]
                decision_data = json.loads(json_text)
                
                # Check if LLM found relevant discoveries
                has_discoveries = decision_data.get("has_relevant_discoveries", False)
                priority_updates = decision_data.get("priority_updates", {})
                reasoning = decision_data.get("discovery_based_reasoning", "")
                
                print(f"  [REASSESS] Has relevant discoveries: {has_discoveries}")
                if reasoning:
                    print(f"  [REASSESS] Reasoning: {reasoning}")
                
                # If no relevant discoveries, don't update anything
                if not has_discoveries:
                    print("  [REASSESS] No relevant discoveries found - no priority changes")
                    return {}
                
                # Validate priority updates are discovery-based
                validated_updates = {}
                pending_tasks = self.task_queue.get_pending_tasks()
                existing_targets = {task.target for task in pending_tasks}
                
                for target, priority in priority_updates.items():
                    # Validate priority range
                    if not isinstance(priority, int) or not (30 <= priority <= 100):
                        print(f"  [REASSESS] Invalid priority {priority} for {target}, skipping")
                        continue
                    
                    # Validate target exists in queue
                    if target not in existing_targets:
                        print(f"  [REASSESS] Target '{target}' not in queue, skipping")
                        continue
                    
                    # Additional validation: ensure priority change is reasonable
                    current_task = next((t for t in pending_tasks if t.target == target), None)
                    if current_task:
                        priority_change = abs(priority - current_task.priority)
                        # Prevent extreme priority changes without strong justification
                        if priority_change > 30:
                            print(f"  [REASSESS] Large priority change ({current_task.priority} -> {priority}) for {target}")
                            # Allow it but log it for monitoring
                    
                    validated_updates[target] = priority
                
                print(f"  [REASSESS] Validated {len(validated_updates)}/{len(priority_updates)} priority updates")
                return validated_updates
                
        except Exception as e:
            print(f"  [REASSESS] Failed to parse LLM reassessment: {e}")
        
        return {}
    
    def _get_new_findings_since_step(self, last_step: int) -> List[Dict]:
        """Get significant findings discovered since the last step"""
        try:
            all_findings = self.context_manager.get_security_summary().get('findings', [])
            
            # Filter for findings from recent steps (rough approximation)
            recent_findings = []
            for finding in all_findings[-10:]:  # Last 10 findings
                if finding.get('risk_level') in ['high', 'medium']:
                    recent_findings.append(finding)
            
            return recent_findings
        except:
            return []
    
    def _get_focus_driven_task(self) -> Optional:
        """Get next task driven by current investigation focus (LLM-driven path selection)"""

        # Get recent findings for LLM context from context_manager
        try:
            security_summary = self.context_manager.get_security_summary()
            recent_findings = security_summary.get('findings', [])[-10:]  # Last 10 findings
        except:
            recent_findings = []

        # LLM-driven focus targets (pass full context including recent findings)
        focus_targets = self.focus_tracker.get_next_investigation_targets(
            limit=1,
            analyzed_files=self.context.get_analyzed_files(),
            explored_directories=self.context.get_explored_directories(),
            recent_findings=recent_findings
        )
        if focus_targets:
            target = focus_targets[0]
            from ..tools.core.task import Task, TaskType
            
            task_type = TaskType.READ if target['action'] == 'analyze_file' else TaskType.EXPLORE
            task = Task(
                type=task_type, 
                target=target['path'], 
                priority=target['priority'],
                focus_id=target.get('focus_id'),
                focus_type=target.get('focus_type'),
                focus_driven=True
            )
            
            print(f"  [FOCUS_TASK] {target['action'].upper()} {target['path']} - {target.get('reason', target.get('reasoning', 'LLM selected'))} (focus: {task.focus_type})")
            return task
        
        return None

    def _update_focus_tracker_with_findings(self, file_path: str, security_result: Dict, file_content: str) -> None:
        """Update focus tracker with new security findings and investigation leads"""
        try:
            findings = security_result.get("findings", [])
            risk_level = security_result["risk_assessment"]["overall_risk"].lower()
            
            # Create or update LLM-driven focus for high and medium risk findings
            if risk_level in ["high", "medium"] and findings:
                # Look for existing focus on this file or create new one
                focus_id = None
                for fid, focus in self.focus_tracker.active_focuses.items():
                    if focus.target == file_path:
                        focus_id = fid
                        break

                if focus_id is None:
                    # Create new LLM-driven focus for this file
                    # Generate focus description based on actual findings
                    finding_types = set(f.get('finding_type', 'unknown') for f in findings[:3])
                    focus_description = f"{risk_level.upper()} risk: {', '.join(finding_types)} in {Path(file_path).name}"

                    focus_id = self.focus_tracker.create_focus(
                        focus_description=focus_description,
                        target=file_path,
                        reason=f"{risk_level.upper()} risk findings: {len(findings)} issues",
                        findings=findings,
                        focus_type="vulnerability"  # Legacy compatibility
                    )
                
                # Add findings to existing or new focus
                for finding in findings:
                    self.focus_tracker.update_focus(focus_id, finding=finding)
                
                # Extract potential investigation leads from findings and content
                leads = self._extract_investigation_leads(file_path, findings, file_content)
                for lead in leads:
                    self.focus_tracker.update_focus(focus_id, lead=lead)
                    
                print(f"  [FOCUS_UPDATED] {focus_id}: Added {len(findings)} findings, {len(leads)} leads")
            
            # ALWAYS check for cross-file references using MCP (regardless of risk level)
            print(f"  [MCP_INTEGRATION] Analyzing file dependencies for: {file_path}")
            related_files = self._find_related_files_from_content(file_content, file_path)
            
            if related_files:
                print(f"  [MCP_INTEGRATION] Found {len(related_files)} related files via MCP analysis")
                for rf in related_files[:5]:  # Show first 5
                    print(f"    → {rf}")
                
                # Only create focuses for high/medium risk files
                if risk_level in ["high", "medium"]:
                    dependency_focus_description = f"Dependencies of {risk_level} risk file {Path(file_path).name}"
                    dependency_focus_id = self.focus_tracker.create_focus(
                        focus_description=dependency_focus_description,
                        target=file_path,
                        reason=f"Tracking dependencies of {risk_level} risk file",
                        focus_type="dependency"  # Legacy
                    )

                    for related_file in related_files[:3]:  # Limit to top 3
                        lead = {
                            'path': related_file,
                            'reason': f'Referenced by {risk_level} risk file {Path(file_path).name}'
                        }
                        self.focus_tracker.update_focus(dependency_focus_id, lead=lead)

            # ALWAYS check for configuration file references using MCP (regardless of risk level)
            if file_path.endswith(('.json', '.toml', '.yaml', '.yml', '.ini')):
                print(f"  [MCP_INTEGRATION] Analyzing config file references for: {file_path}")
                config_files = self._find_referenced_files_from_config(file_content, file_path)
                
                if config_files:
                    print(f"  [MCP_INTEGRATION] Found {len(config_files)} referenced files via MCP config analysis")
                    for cf in config_files[:5]:  # Show first 5
                        print(f"    → {cf}")
                    
                    # Only create focuses for high/medium risk files
                    if risk_level in ["high", "medium"]:
                        config_focus_description = f"Config references from {risk_level} risk file {Path(file_path).name}"
                        config_focus_id = self.focus_tracker.create_focus(
                            focus_description=config_focus_description,
                            target=file_path,
                            reason=f"Files referenced in {risk_level} risk config file",
                            focus_type="config_dependency"  # Legacy
                        )

                        for config_file in config_files[:3]:  # Limit to top 3
                            lead = {
                                'path': config_file,
                                'reason': f'Referenced in {risk_level} risk config file {Path(file_path).name}'
                            }
                            self.focus_tracker.update_focus(config_focus_id, lead=lead)
        
        except Exception as e:
            print(f"  [ERROR] Failed to update focus tracker: {e}")

    def _extract_investigation_leads(self, file_path: str, findings: List[Dict], content: str) -> List[Dict]:
        """Extract investigation leads from security findings and content"""
        leads = []
        
        try:
            base_dir = str(Path(file_path).parent)
            file_name = Path(file_path).stem
            
            # From findings - look for specific patterns
            for finding in findings:
                # Handle both SecurityFinding objects and dict formats
                if hasattr(finding, 'description'):
                    description = finding.description.lower()
                elif isinstance(finding, dict):
                    description = finding.get('description', '').lower()
                else:
                    description = ''

                # SQL injection patterns suggest database-related files
                if 'sql' in description or 'database' in description:
                    leads.append({
                        'path': f"{base_dir}/models.py",
                        'reason': f'SQL-related finding in {Path(file_path).name}'
                    })
                    leads.append({
                        'path': f"{base_dir}/db",
                        'reason': f'Database configuration check'
                    })

                # Authentication issues suggest auth-related files
                if 'auth' in description or 'login' in description or 'password' in description:
                    leads.append({
                        'path': f"{base_dir}/auth.py",
                        'reason': f'Authentication finding in {Path(file_path).name}'
                    })
                    leads.append({
                        'path': f"{base_dir}/security.py",
                        'reason': f'Security configuration check'
                    })

                # Configuration issues suggest config files
                if 'config' in description or 'setting' in description:
                    leads.append({
                        'path': f"{base_dir}/config.py",
                        'reason': f'Configuration issue in {Path(file_path).name}'
                    })
            
            # From content - look for imports and references
            if 'import ' in content or 'from ' in content:
                # Look for test files
                leads.append({
                    'path': f"{base_dir}/test_{file_name}.py",
                    'reason': f'Test coverage for {Path(file_path).name}'
                })
                leads.append({
                    'path': f"{base_dir}/{file_name}_test.py",
                    'reason': f'Test coverage for {Path(file_path).name}'
                })
            
        except Exception as e:
            print(f"  [ERROR] Failed to extract leads: {e}")
        
        # Remove duplicates and non-existent paths
        unique_leads = []
        seen_paths = set()
        
        for lead in leads:
            if lead['path'] not in seen_paths:
                seen_paths.add(lead['path'])
                # Basic existence check for files (directories handled later)
                if lead['path'].endswith('.py'):
                    full_path = self.repo_path / lead['path']
                    if full_path.exists():
                        unique_leads.append(lead)
                else:
                    # For directories, add without existence check
                    unique_leads.append(lead)
        
        return unique_leads[:5]  # Limit to top 5 leads





def perform_repository_analysis(repo_path: str, max_steps: Optional[int] = None, save_results: bool = True, focus: str = None) -> Dict[str, Any]:
    """
    Function tool for performing comprehensive repository analysis
    
    Args:
        repo_path: Path to repository to analyze
        max_steps: Maximum analysis steps (default from settings)
        save_results: Whether to save results to file
        focus: Analysis focus (None for dynamic LLM-generated focus)
    
    Returns:
        Comprehensive analysis results with dynamic focus adaptation
    """
    analyzer = AnalysisAgent(repo_path)
    return analyzer.analyze(max_steps=max_steps, save_results=save_results, focus=focus)


def get_analysis_queue_status(analyzer_instance=None) -> str:
    """
    Function tool to get current task queue status and pending priorities
    """
    if not analyzer_instance:
        return "No active analyzer instance"
    
    stats = analyzer_instance.task_queue.get_stats()
    pending_tasks = analyzer_instance.task_queue.get_pending_tasks()
    
    status = f"""TASK QUEUE STATUS:
- Pending tasks: {stats['pending']}
- Completed tasks: {stats['completed']}
- Failed tasks: {stats['failed']}

TOP PENDING TASKS:"""
    
    for i, task in enumerate(pending_tasks[:5]):
        status += f"\n{i+1}. [{task.priority}] {task.type.value} → {task.target}"
    
    return status


def compact_history_context(history_context: str, max_length: int = 4000) -> str:
    """
    Function tool to compact long history contexts using LLM
    """
    compactor = HistoryCompactor(max_context_length=max_length)
    return compactor.compact_if_needed(history_context)


def make_autonomous_decision(analyzer_instance, decision_type: str, context_data: Dict) -> str:
    """
    Function tool to trigger autonomous decision making
    """
    if not analyzer_instance:
        return "No active analyzer instance"
    
    try:
        if decision_type == "exploration":
            analyzer_instance._make_autonomous_decision(
                "exploration", 
                explored_path=context_data.get('explored_path', '.'),
                files=context_data.get('files', []),
                dirs=context_data.get('dirs', [])
            )
        elif decision_type == "content":
            analyzer_instance._make_autonomous_decision(
                "content",
                file_path=context_data.get('file_path', ''),
                content=context_data.get('content', ''),
                security_result=context_data.get('security_result', {})
            )
        return f"Autonomous decision making triggered for {decision_type}"
    except Exception as e:
        return f"Decision making failed: {e}"


def get_project_overview_direct(repo_path: str) -> str:
    """
    Function tool to get project overview directly from context manager
    """
    try:
        from ..tools.planning.analysis_context_manager import AnalysisContextManager
        manager = AnalysisContextManager(repo_path)
        overview = manager.get_project_overview()
        
        return f"""PROJECT OVERVIEW - {overview['repo_path']}

REPOSITORY STRUCTURE:
- Total files: {overview.get('total_files', 0)}
- Total directories: {overview.get('total_directories', 0)}
- Analysis progress: {overview.get('analysis_progress', '0%')}

SECURITY SUMMARY:
- High risk files: {overview.get('high_risk_count', 0)}
- Medium risk files: {overview.get('medium_risk_count', 0)}
- Total security findings: {overview.get('total_findings', 0)}

RECENT ACTIVITY:
{overview.get('recent_activity', 'No recent activity')}"""
    except Exception as e:
        return f"Failed to get project overview: {e}"


def build_analysis_agent() -> Agent:
    """
    Build the Analysis Agent with repository analysis capabilities.
    
    This agent focuses on static analysis, security scanning, and
    architectural understanding of target repositories.
    """
    
    analysis_agent = Agent(
        model=LiteLlm(model=settings.ANALYSIS_AGENT_MODEL),
        name="analysis_agent",
        instruction="""
You are an expert AI security analysis agent specialized in repository static analysis.
Your role is to perform comprehensive analysis of code repositories to understand
their architecture, identify security patterns, and map potential vulnerabilities.

Your capabilities include:

1. **Autonomous Repository Analysis**:
   - Perform intelligent analysis using context and discoveries
   - Make autonomous decisions about exploration and file analysis
   - Use security findings to drive investigation priorities
   - Generate comprehensive analysis reports

2. **Security Analysis**:
   - Analyze files for security vulnerabilities and injection points
   - Assess risk levels and provide detailed findings
   - Identify high-risk files requiring immediate attention
   - Generate security assessment summaries

3. **Context Management**:
   - Track analysis progress and project understanding
   - Maintain analysis history for intelligent decision making
   - Provide project overview and status information
   - Support adaptive planning based on discoveries

4. **Task Management**:
   - Create and manage analysis tasks with intelligent planning
   - Update analysis progress and track completion
   - Generate comprehensive analysis plans
   - Coordinate analysis workflow with adaptive strategies

CORE ARCHITECTURE & INTELLIGENT DECISION MAKING:
You are built on a sophisticated autonomous analysis architecture with these key innovations:

**Core Architecture Components:**
1. **Priority Task Queue** - Manages analysis tasks by priority with autonomous decision making
2. **History Context Management** - Maintains comprehensive analysis context with auto-compaction
3. **Autonomous Decision Making** - Uses LLM-driven decisions for exploration and content analysis
4. **Context-Aware Planning** - Prevents duplicate work and focuses on high-value targets

**Available Tools:**
1. **perform_repository_analysis()** - Execute comprehensive autonomous repository analysis
2. **get_project_overview_direct()** - Get real-time project structure and security status
3. **compact_history_context()** - Auto-compact long analysis contexts using LLM
4. **initialize_analysis_context()** - Set up analysis context for new repositories
5. **get_security_summary()** - Review current security findings and risk assessment

AUTONOMOUS ANALYSIS WORKFLOW:

1. **Initialization**: The system automatically initializes with a priority queue and context management
2. **Autonomous Exploration**: Uses LLM-driven decisions to explore repositories intelligently
3. **Context-Aware Analysis**: Maintains history to prevent duplicate work and focus on gaps
4. **Priority-Based Task Management**: High-risk findings automatically increase analysis priority
5. **Auto-Compaction**: Long contexts are automatically compacted to maintain LLM effectiveness

CONTEXT-AWARE DECISION MAKING:
- Always check current analysis status before making decisions
- Use project overview and history to avoid redundant analysis
- Prioritize based on security findings and architectural importance
- Create todos for follow-up analysis of interesting discoveries
- Update progress regularly to maintain accurate context

Focus on security vulnerabilities, injection points, and architectural risks.
Be proactive - when you discover something interesting, investigate it thoroughly and create follow-up tasks.
Use the full context and planning toolkit to manage comprehensive, intelligent analysis workflows.
""",
        tools=[
            # Core repository analysis tool  
            FunctionTool(perform_repository_analysis),
            
            # Core architecture tools - direct access to main functionality
            FunctionTool(get_project_overview_direct),
            FunctionTool(compact_history_context),
            
            # Essential context tools (simplified)
            FunctionTool(initialize_analysis_context),
            # Note: Other tools now integrated into agent architecture directly
        ],
    )

    return analysis_agent