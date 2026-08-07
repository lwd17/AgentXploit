"""
Priority task queue for managing analysis tasks.
Implements a simple priority queue with task lifecycle management.
"""

import heapq
from typing import Dict, List, Optional
from pathlib import Path
from .task import Task, TaskStatus


class TaskQueue:
    """Priority queue for analysis tasks, ordered by priority (higher = first)"""

    def __init__(self, repo_path: str = None):
        self._heap: List[tuple] = []  # (negative_priority, counter, task)
        self._tasks: Dict[str, Task] = {}  # task_id -> Task
        self._target_tasks: Dict[str, Task] = {}  # normalized_target -> Task (for deduplication)
        self._counter = 0  # For stable sorting when priorities are equal
        self._repo_path = Path(repo_path).resolve() if repo_path else None
    
    def _normalize_target(self, target: str) -> str:
        """
        Normalize target path for deduplication using absolute paths.
        Ensures reliable deduplication across different working directories and symlinks.
        """
        try:
            # Clean up input path
            target = str(target).strip().replace('\\', '/')
            
            if self._repo_path:
                repo_abs = self._repo_path.resolve()
                
                if Path(target).is_absolute():
                    # Already absolute - just resolve symlinks and normalize
                    abs_path = Path(target).resolve()
                else:
                    # Relative path - resolve from repo root
                    abs_path = (repo_abs / target).resolve()
                
                # Ensure consistent path format
                normalized = str(abs_path).replace('\\', '/')
                
                # Additional verification - ensure path actually exists or is reasonable
                try:
                    # Check if it's within or related to the repo
                    try:
                        abs_path.relative_to(repo_abs)
                        # Path is within repo - this is good
                    except ValueError:
                        # Path is outside repo - still valid but log it
                        pass
                except:
                    pass
                    
                return normalized
            else:
                # No repo path - still try to normalize to absolute
                if Path(target).is_absolute():
                    return str(Path(target).resolve()).replace('\\', '/')
                else:
                    # Relative path without repo context - use current working dir
                    return str(Path(target).resolve()).replace('\\', '/')
                    
        except Exception as e:
            # Comprehensive fallback handling
            try:
                # Try basic path operations
                if self._repo_path and not Path(target).is_absolute():
                    fallback = str((self._repo_path / target).absolute())
                else:
                    fallback = str(Path(target).absolute())
                return fallback.replace('\\', '/')
            except:
                # Absolute last resort - return cleaned input
                return str(target).replace('\\', '/')

    def add_task(self, task: Task) -> None:
        """Add a task to the queue with absolute path-based deduplication"""
        if task.task_id in self._tasks:
            return  # Task already exists

        # Use absolute normalized target for accurate deduplication across different repos
        normalized_target = self._normalize_target(task.target)
        target_key = f"{task.type.value}:{normalized_target}"
        
        if target_key in self._target_tasks:
            existing_task = self._target_tasks[target_key]
            # More lenient deduplication - only skip if exactly same absolute path and type
            if (existing_task.priority >= task.priority and 
                existing_task.status.name == 'PENDING'):  # Only skip if existing task is still pending
                print(f"  [DEDUP] Skipping duplicate task: {task.target} -> {normalized_target[:60]}...")
                return
            elif existing_task.status.name in ['COMPLETED', 'FAILED']:
                # Allow re-analysis of completed/failed tasks with higher priority
                if task.priority > existing_task.priority:
                    print(f"  [REANALYZE] Re-adding higher priority task: {task.target} (priority {task.priority} vs {existing_task.priority})")
                    # Remove the old completed/failed task
                    self._remove_task(existing_task.task_id)
                else:
                    print(f"  [DEDUP] Skipping re-analysis of {task.target} - already analyzed")
                    return
            else:
                # Replace lower priority pending task
                print(f"  [PRIORITY] Replacing task: {existing_task.target} (priority {existing_task.priority}) with {task.target} (priority {task.priority})")
                self._remove_task(existing_task.task_id)

        self._tasks[task.task_id] = task
        self._target_tasks[target_key] = task
        # Use negative priority for max-heap behavior (higher priority first)
        heapq.heappush(self._heap, (-task.priority, self._counter, task))
        self._counter += 1
        
        # Debug logging for high-priority LLM tasks
        if task.priority >= 85:
            print(f"  [QUEUE] Added HIGH-PRIORITY task: {task.type.value.upper()} {task.target} (priority: {task.priority})")

    def _remove_task(self, task_id: str) -> None:
        """Remove a task from internal data structures"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            # Use normalized target for removal
            normalized_target = self._normalize_target(task.target)
            target_key = f"{task.type.value}:{normalized_target}"
            if target_key in self._target_tasks:
                del self._target_tasks[target_key]
            del self._tasks[task_id]

    def get_next(self) -> Optional[Task]:
        """Get the next highest priority pending task"""
        while self._heap:
            _, _, task = heapq.heappop(self._heap)
            
            # Check if task still exists and is pending
            if task.task_id in self._tasks and task.is_pending():
                return task
        
        return None
    
    def complete_task(self, task_id: str, result: Dict) -> bool:
        """Mark a task as completed with result"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.set_completed(result)
        return True

    def fail_task(self, task_id: str, error_message: str) -> bool:
        """Mark a task as failed with error message"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.set_failed(error_message)
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID"""
        return self._tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks sorted by priority"""
        pending = [task for task in self._tasks.values() if task.is_pending()]
        return sorted(pending, key=lambda t: -t.priority)  # Higher priority first
    
    def get_completed_tasks(self) -> List[Task]:
        """Get all completed tasks"""
        return [task for task in self._tasks.values() if task.is_completed()]
    
    def get_failed_tasks(self) -> List[Task]:
        """Get all failed tasks"""
        return [task for task in self._tasks.values() if task.is_failed()]
    
    def size(self) -> int:
        """Get total number of tasks in queue"""
        return len(self._tasks)
    
    def pending_count(self) -> int:
        """Get number of pending tasks"""
        return len([t for t in self._tasks.values() if t.is_pending()])
    
    def clear(self) -> None:
        """Remove all tasks from queue"""
        self._heap.clear()
        self._tasks.clear()
        self._counter = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        for task in self._tasks.values():
            if task.is_pending():
                stats["pending"] += 1
            elif task.is_running():
                stats["running"] += 1
            elif task.is_completed():
                stats["completed"] += 1
            elif task.is_failed():
                stats["failed"] += 1
        return stats
    
    def has_high_priority_tasks(self, threshold: int = 85) -> bool:
        """Check if there are high priority tasks that might trigger reassessment"""
        pending_tasks = self.get_pending_tasks()
        return any(task.priority >= threshold for task in pending_tasks)
    
    def get_highest_priority(self) -> int:
        """Get the priority of the highest priority pending task"""
        pending_tasks = self.get_pending_tasks()
        return max([task.priority for task in pending_tasks], default=0)
    
    def reassess_priorities(self, priority_updates: Dict[str, int]) -> int:
        """Update task priorities and rebuild heap. Returns number of tasks updated."""
        updated_count = 0
        
        # Update priorities in tasks
        for target, new_priority in priority_updates.items():
            # Find task by target pattern (type:target)
            matching_tasks = [task for task in self._tasks.values() 
                            if f"{task.type.value}:{task.target}" == target or task.target == target]
            
            for task in matching_tasks:
                if task.is_pending() and task.priority != new_priority:
                    task.priority = new_priority
                    updated_count += 1
        
        if updated_count > 0:
            # Rebuild heap with new priorities
            self._rebuild_heap()
        
        return updated_count
    
    def _rebuild_heap(self) -> None:
        """Rebuild the heap with current task priorities"""
        # Clear current heap
        self._heap.clear()
        
        # Re-add all pending tasks with current priorities
        for task in self._tasks.values():
            if task.is_pending():
                heapq.heappush(self._heap, (-task.priority, self._counter, task))
                self._counter += 1