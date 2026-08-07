"""
Todo list management tools for tracking task progress.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path for persisting todo list
_TODO_FILE = Path(__file__).parent.parent / ".todos.json"


def _load_todos() -> list[dict]:
    """Load todos from persistent storage."""
    if _TODO_FILE.exists():
        try:
            with open(_TODO_FILE, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_todos(todos: list[dict]) -> None:
    """Save todos to persistent storage."""
    with open(_TODO_FILE, 'w', encoding='utf-8') as f:
        json.dump(todos, f, indent=2)


def todo_read() -> list[dict]:
    """Read the current to-do list for the session.

    Use this tool proactively and frequently to ensure that you are aware of
    the status of the current task list. You should make use of this tool as
    often as possible, especially in the following situations:

    - At the beginning of conversations to see what's pending
    - Before starting new tasks to prioritize work
    - When the user asks about previous tasks or plans
    - Whenever you're uncertain about what to do next
    - After completing tasks to update your understanding of remaining work
    - After every few messages to ensure you're on track

    Usage:
    - This tool takes in no parameters. Leave the input blank or empty.
      DO NOT include a dummy object, placeholder string or a key like "input"
      or "empty". LEAVE IT BLANK.
    - Returns a list of todo items with their status, priority, and content
    - Use this information to track progress and plan next steps
    - If no todos exist yet, an empty list will be returned

    Returns:
        list[dict]: List of todos, each containing:
            - id (str): Unique identifier
            - content (str): Task description
            - status (str): "pending" | "in_progress" | "completed"
            - priority (str): "high" | "medium" | "low"
    """
    return _load_todos()


def todo_write(todos: list[dict]) -> dict:
    """Create and manage a structured task list for your current coding session.

    This helps you track progress, organize complex tasks, and demonstrate
    thoroughness to the user. It also helps the user understand the progress
    of the task and overall progress of their requests.

    When to Use This Tool:
    - Complex multi-step tasks: When a task requires 3 or more distinct steps
    - Non-trivial and complex tasks: Tasks requiring careful planning
    - User explicitly requests todo list
    - User provides multiple tasks (numbered or comma-separated)
    - After receiving new instructions: Immediately capture user requirements
    - When starting a task: Mark it as in_progress BEFORE beginning work
    - After completing a task: Mark it as completed

    When NOT to Use This Tool:
    - Single, straightforward task
    - Trivial task with no organizational benefit
    - Task can be completed in less than 3 trivial steps
    - Purely conversational or informational task

    Task States:
    - pending: Task not yet started
    - in_progress: Currently working on (limit to ONE task at a time)
    - completed: Task finished successfully

    Task Management Rules:
    - Update task status in real-time as you work
    - Mark tasks complete IMMEDIATELY after finishing
    - Only have ONE task in_progress at any time
    - Complete current tasks before starting new ones
    - Remove tasks that are no longer relevant

    Task Completion Requirements:
    - ONLY mark completed when FULLY accomplished
    - Keep as in_progress if errors or blockers occur
    - Never mark completed if tests fail or implementation is partial

    Args:
        todos: The updated todo list. Each todo must have:
            - id (str): Unique identifier for the todo
            - content (str): Task description
            - status (str): One of "pending", "in_progress", "completed"
            - priority (str): One of "high", "medium", "low"

    Returns:
        dict: {"success": bool, "error": str or None}
              If you need to see the current list after writing, call todo_read().
    """
    try:
        if not isinstance(todos, list):
            return {"success": False, "error": "todos must be a list"}

        valid_statuses = {"pending", "in_progress", "completed"}
        valid_priorities = {"high", "medium", "low"}
        validated_todos = []

        for i, todo in enumerate(todos):
            if not isinstance(todo, dict):
                continue

            content = todo.get("content", "").strip()
            if not content:
                return {"success": False, "error": f"Todo at index {i} missing content"}

            status = todo.get("status", "pending")
            if status not in valid_statuses:
                return {"success": False, "error": f"Invalid status '{status}' at index {i}"}

            priority = todo.get("priority", "medium")
            if priority not in valid_priorities:
                return {"success": False, "error": f"Invalid priority '{priority}' at index {i}"}

            todo_id = todo.get("id", f"todo_{i+1}")

            validated_todos.append({
                "id": todo_id,
                "content": content,
                "status": status,
                "priority": priority
            })

        _save_todos(validated_todos)
        return {"success": True, "error": None}

    except Exception as e:
        logger.error(f"Todo write error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


__all__ = ["todo_read", "todo_write"]
