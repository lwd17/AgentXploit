"""
Fallback Analysis Strategies
Extracted from analysis_agent.py for better organization
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json

class FallbackAnalysisStrategies:
    """Consolidated fallback strategies for analysis continuation"""
    
    def __init__(self, context_manager, task_queue, context, tools):
        self.context_manager = context_manager
        self.task_queue = task_queue
        self.context = context
        self.tools = tools
    
    def simple_fallback_exploration(self, explored_path: str, files: List[str], dirs: List[str], focus: str = "security") -> None:
        """Add fallback tasks when LLM decisions fail - simplified without rule-based logic"""
        from ..tools.core.task import Task, TaskType
        from ..tools.core.path_validator import PathValidator
        
        path_validator = PathValidator()
        
        print("  [FALLBACK] LLM decisions incomplete - adding basic fallback tasks...")
        
        # Simple fallback: take first few files and directories
        added_count = 0
        for file_name in files[:5]:  # Take up to 5 files
            file_path = f"{explored_path.rstrip('/')}/{file_name}" if explored_path != "." else file_name
            
            # Basic existence check only
            path_info = path_validator.get_path_info(file_path)
            if path_info['exists'] and path_info['is_file']:
                # Use medium priority for fallback tasks
                task = Task(
                    type=TaskType.READ, 
                    target=file_path, 
                    priority=60,  # Medium priority fallback
                    focus_driven=False
                )
                self.task_queue.add_task(task)
                added_count += 1
                print(f"    [+] FALLBACK-FILE: {file_name}")
                
                if added_count >= 3:  # Limit fallback tasks
                    break
        
        # Add directories if we didn't find enough files
        if added_count < 2:
            for dir_name in dirs[:2]:  # Take up to 2 directories
                dir_path = f"{explored_path.rstrip('/')}/{dir_name}" if explored_path != "." else dir_name
                
                path_info = path_validator.get_path_info(dir_path)
                if path_info['exists'] and path_info['is_directory']:
                    task = Task(
                        type=TaskType.EXPLORE, 
                        target=dir_path, 
                        priority=55,  # Slightly lower priority for directories
                        focus_driven=False
                    )
                    self.task_queue.add_task(task)
                    added_count += 1
                    print(f"    [+] FALLBACK-DIR: {dir_name}")
                    
                    if added_count >= 3:
                        break
        
        if added_count > 0:
            print(f"  [FALLBACK] Added {added_count} strategic fallback tasks")
        else:
            print("  [FALLBACK] No suitable fallback targets found")
    
    def minimal_fallback_exploration(self, unexplored_root_dirs: List[str]) -> None:
        """Minimal exploration when other strategies fail"""
        from ..tools.core.task import Task, TaskType
        
        print("  [MINIMAL_FALLBACK] Adding essential exploration tasks...")
        
        added_count = 0
        # Simply take first available directories
        for dir_name in unexplored_root_dirs[:2]:  # Take up to 2 directories
            task = Task(
                type=TaskType.EXPLORE, 
                target=dir_name, 
                priority=50,  # Low priority for minimal fallback
                focus_driven=False
            )
            self.task_queue.add_task(task)
            added_count += 1
            print(f"    [+] MINIMAL: {dir_name}")
        
        print(f"  [MINIMAL_FALLBACK] Added {added_count} essential tasks")
    
    def intelligent_queue_reassessment(self, focus_tracker) -> None:
        """Intelligent task queue reassessment based on discoveries and focus"""
        print("  Performing intelligent task queue reassessment...")
        
        if not focus_tracker:
            print("    [ERROR] Focus tracker is required for consistent focus-driven architecture")
            return self._fallback_queue_reassessment([])
        
        try:
            # Get current analysis state
            analyzed_files = list(self.context.get_analyzed_files())
            security_summary = self.context_manager.get_security_summary()
            
            # Get high-risk files for priority boost
            high_risk_files = []
            for finding in security_summary.get('findings', []):
                if finding.get('risk_level') == 'high':
                    high_risk_files.append(finding['file'])
            
            print(f"    Found {len(high_risk_files)} high-risk files for priority analysis")
            
            if high_risk_files:
                # Create or update focuses based on high-risk findings
                for high_risk_file in high_risk_files[:2]:  # Limit to top 2
                    findings_for_file = [f for f in security_summary.get('findings', []) 
                                       if f.get('file') == high_risk_file and f.get('risk_level') == 'high']
                    
                    if findings_for_file:
                        focus_id = focus_tracker.create_focus(
                            'vulnerability',
                            high_risk_file,
                            f"High-risk findings: {len(findings_for_file)} issues",
                            findings_for_file
                        )
                        
                        # Add related files as leads
                        related_paths = self._get_related_file_paths(high_risk_file)
                        for related_path in related_paths[:3]:
                            focus_tracker.update_focus(focus_id, lead={
                                'path': related_path,
                                'reason': f"Related to high-risk file {Path(high_risk_file).name}"
                            })
            
            # Perform traditional priority reassessment as backup
            self._fallback_queue_reassessment(high_risk_files)
            
        except Exception as e:
            print(f"    [ERROR] Reassessment failed: {e}")
            # Emergency fallback
            if self.task_queue.pending_count() == 0:
                self.minimal_fallback_exploration(['src', 'app', 'main'])
    
    def _get_related_file_paths(self, target_file: str) -> List[str]:
        """Get file paths that might be related to the target"""
        base_path = Path(target_file)
        base_dir = str(base_path.parent)
        base_name = base_path.stem
        
        related_patterns = [
            f"{base_dir}/{base_name}_test.py",
            f"{base_dir}/{base_name}_config.py", 
            f"{base_dir}/{base_name}_utils.py",
            f"{base_dir}/test_{base_name}.py",
            f"{base_dir}/__init__.py",
            f"{base_dir}/models.py",
            f"{base_dir}/views.py",
            f"{base_dir}/handlers.py"
        ]
        
        return related_patterns
    
    def _fallback_queue_reassessment(self, high_risk_files: List[str]) -> None:
        """Conservative fallback priority reassessment"""
        print("    Applying conservative priority adjustments...")
        
        priority_updates = {}
        pending_tasks = self.task_queue.get_pending_tasks()
        
        for task in pending_tasks:
            priority_boost = 0
            
            # Boost for files in same directory as high-risk files
            for high_risk_file in high_risk_files:
                risk_dir = str(Path(high_risk_file).parent)
                task_dir = str(Path(task.target).parent) if '/' in task.target else '.'
                
                if risk_dir == task_dir:
                    priority_boost = max(priority_boost, 15)
                    
            # Boost for security-related files
            security_patterns = ['auth', 'login', 'password', 'token', 'key', 'secret', 'security']
            if any(pattern in task.target.lower() for pattern in security_patterns):
                priority_boost = max(priority_boost, 12)
            
            # Apply boost
            if priority_boost > 0:
                new_priority = min(85, task.priority + priority_boost)
                if new_priority != task.priority:
                    priority_updates[task.target] = new_priority
        
        if priority_updates:
            updated_count = self.task_queue.reassess_priorities(priority_updates)
            print(f"    Updated {updated_count} task priorities based on risk analysis")
        else:
            print("    No priority adjustments needed")

    def fallback_file_priority_selection(self, files: List[str], explored_path: str) -> None:
        """Minimal fallback for file selection when LLM completely fails"""
        from ..tools.core.task import Task, TaskType
        if not files:
            return
        added_count = 0
        # Simply take the first few files without any priority logic
        # This ensures the system can continue but doesn't make intelligent decisions
        for file in files[:2]:  # Only take 2 files to be conservative
            file_path = f"{explored_path.rstrip('/')}/{file}"
            if not self.context.is_file_analyzed(file_path):
                read_task = Task(
                    type=TaskType.READ, 
                    target=file_path, 
                    priority=50,
                    focus_driven=False  # Fallback task, not focus-driven
                )
                self.task_queue.add_task(read_task)
                print(f"  [MINIMAL-FALLBACK] Added file: {file} (LLM unavailable)")
                added_count += 1
        print(f"  [MINIMAL-FALLBACK] Added {added_count} files using basic fallback")

    def simple_fallback_exploration_basic(self, explored_path: str, files: List[str], dirs: List[str]) -> None:
        """Simple fallback exploration when LLM fails"""
        from ..tools.core.task import Task, TaskType
        print("  Using simple fallback exploration strategy")
        # Add a few files to analyze
        added_count = 0
        for file_name in files[:3]:  # Take first 3 files
            file_path = f"{explored_path.rstrip('/')}/{file_name}"
            if not self.context.is_file_analyzed(file_path):
                task = Task(
                    type=TaskType.READ, 
                    target=file_path, 
                    priority=45,
                    focus_driven=False  # Fallback task, not focus-driven
                )
                self.task_queue.add_task(task)
                added_count += 1
                print(f"  [SIMPLE-FALLBACK] Added file: {file_name}")
        
        # Add one directory if available
        if dirs and added_count < 2:
            target_dir = dirs[0]
            dir_path = f"{explored_path.rstrip('/')}/{target_dir}" if explored_path != "." else target_dir
            task = Task(
                type=TaskType.EXPLORE, 
                target=dir_path, 
                priority=40,
                focus_driven=False  # Fallback task, not focus-driven
            )
            self.task_queue.add_task(task)
            print(f"  [SIMPLE-FALLBACK] Added directory: {target_dir}")
            added_count += 1
        
        print(f"  [SIMPLE-FALLBACK] Added {added_count} items via simple fallback")

    def simple_security_followup(self, file_path: str, content: str) -> None:
        """Simple fallback for high-risk files"""
        from ..tools.core.task import Task, TaskType
        print("  Using simple security follow-up strategy")
        
        base_dir = str(Path(file_path).parent)
        
        # Look for related security files
        security_patterns = ['auth', 'config', 'security', 'middleware']
        for pattern in security_patterns:
            related_file = f"{base_dir}/{pattern}.py"
            if not self.context.is_file_analyzed(related_file):
                task = Task(
                    type=TaskType.READ, 
                    target=related_file, 
                    priority=65,
                    focus_driven=False  # Fallback task, not focus-driven
                )
                self.task_queue.add_task(task)
                print(f"  [SEC-FOLLOWUP] Added related file: {pattern}.py")

    def discovery_based_queue_reassessment(self) -> None:
        """Discovery-based fallback reassessment when LLM fails"""
        print("  [REASSESS] Using discovery-based fallback reassessment")
        
        # Get actual security findings
        security_summary = self.context_manager.get_security_summary() if hasattr(self.context_manager, 'get_security_summary') else {}
        high_risk_files = []
        medium_risk_files = []
        
        for finding in security_summary.get('findings', []):
            if finding.get('risk_level') == 'high':
                high_risk_files.append(finding['file'])
            elif finding.get('risk_level') == 'medium':
                medium_risk_files.append(finding['file'])
        
        high_risk_count = len(set(high_risk_files))  # Unique files
        if high_risk_count == 0:
            print("  [REASSESS] No high-risk files found - no fallback changes needed")
            return
        
        print(f"  [REASSESS] Found {high_risk_count} high-risk files, applying discovery-based priority boost")
        
        # Increase priority for files in same directories as high-risk files
        priority_updates = {}
        pending_tasks = self.task_queue.get_pending_tasks()
        
        for task in pending_tasks:
            priority_boost = 0
            
            # Check if task is in same directory as any high-risk file
            for high_risk_file in set(high_risk_files):  # Remove duplicates
                risk_dir = str(Path(high_risk_file).parent)
                task_dir = str(Path(task.target).parent) if '/' in task.target else '.'
                
                if risk_dir == task_dir:
                    priority_boost = max(priority_boost, 20)  # Significant boost
                    break
            
            # Also boost medium-risk related files
            for medium_risk_file in set(medium_risk_files):
                risk_dir = str(Path(medium_risk_file).parent)
                task_dir = str(Path(task.target).parent) if '/' in task.target else '.'
                
                if risk_dir == task_dir:
                    priority_boost = max(priority_boost, 10)  # Moderate boost
                    break
            
            if priority_boost > 0:
                new_priority = min(85, task.priority + priority_boost)  # Cap at 85 for fallback
                if new_priority != task.priority:
                    priority_updates[task.target] = new_priority
        
        if priority_updates:
            updated_count = self.task_queue.reassess_priorities(priority_updates)
            print(f"  [REASSESS] Applied {updated_count} discovery-based priority updates")
        else:
            print("  [REASSESS] No fallback updates applied - no clear connections found")