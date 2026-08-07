"""
Task data structures for code analysis system.
Defines individual analysis tasks with type, target, priority, status and results.
"""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass


# Unified priority mapping for all components
PRIORITY_MAPPING = {
    "critical": 99,  # Critical/urgent tasks
    "high": 95,      # High priority LLM decisions
    "medium": 80,    # Medium priority LLM decisions  
    "low": 60,       # Low priority LLM decisions
    "default": 70    # Default when priority not specified
}


class TaskType(Enum):
    """Task type enumeration"""
    EXPLORE = "explore"  # Directory exploration
    READ = "read"        # File reading
    ANALYZE = "analyze"  # Code analysis
    TRACE = "trace"      # Call tracing


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"      # Awaiting execution
    RUNNING = "running"      # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"        # Execution failed


@dataclass
class Task:
    """
    Analysis task data structure
    
    Attributes:
        type: Task type (explore, read, analyze, trace)
        target: Target path or file
        priority: Priority level (0-100, higher = more priority)
        status: Current task status
        result: Task execution result
        task_id: Unique task identifier
        error_message: Error details (when status is FAILED)
        focus_id: Focus ID for focus-driven analysis
        focus_type: Focus type (vulnerability, dependency, etc.)
        focus_driven: Whether this task is focus-driven
    """
    type: TaskType
    target: str
    priority: int = 50
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None
    error_message: Optional[str] = None
    focus_id: Optional[str] = None
    focus_type: Optional[str] = None
    focus_driven: bool = False
    
    def __post_init__(self):
        if self.task_id is None:
            import uuid
            self.task_id = str(uuid.uuid4())[:8]
    
    def __str__(self) -> str:
        focus_info = f", focus={self.focus_type}:{self.focus_id}" if self.focus_driven else ""
        return f"Task[{self.task_id}]({self.type.value}: {self.target}, priority={self.priority}, status={self.status.value}{focus_info})"
    
    def __repr__(self) -> str:
        focus_info = f", focus_id='{self.focus_id}', focus_type='{self.focus_type}', focus_driven={self.focus_driven}" if self.focus_driven else ""
        return f"Task(id={self.task_id}, type={self.type.value}, target='{self.target}', priority={self.priority}, status={self.status.value}{focus_info})"
    
    def set_running(self) -> None:
        self.status = TaskStatus.RUNNING
    
    def set_completed(self, result: Dict[str, Any]) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.error_message = None
    
    def set_failed(self, error_message: str) -> None:
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.result = None
    
    def is_pending(self) -> bool:
        return self.status == TaskStatus.PENDING
    
    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING
    
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED
    
    def is_failed(self) -> bool:
        return self.status == TaskStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "type": self.type.value,
            "target": self.target,
            "priority": self.priority,
            "status": self.status.value,
            "result": self.result,
            "error_message": self.error_message
        }