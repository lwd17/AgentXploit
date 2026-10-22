"""
Context tools for agents to access analysis history, manage todos,
and make informed decisions about what to analyze next.
"""

import json
from typing import Optional, Dict, Any, List
from google.adk.tools import ToolContext

from .analysis_context_manager import AnalysisContextManager

# Global context manager instance (initialized per analysis session)
_context_manager = None


def initialize_analysis_context(repo_path: str, tool_context: Optional[ToolContext] = None) -> str:
    """Initialize analysis context for a repository"""
    global _context_manager
    _context_manager = AnalysisContextManager(repo_path)
    return f"Analysis context initialized for repository: {repo_path}"