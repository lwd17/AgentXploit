"""
Task manager integrated with new AnalysisContextManager system.
Provides task management capabilities for agents using the context-aware approach.
"""

import logging
from typing import Optional, Dict, Any, List
from google.adk.tools import ToolContext

from .analysis_context_manager import AnalysisContextManager

logger = logging.getLogger(__name__)


def manage_analysis_tasks(
    repo_path: str,
    max_tasks: int = 50,
    priority_focus: str = "security",
    tool_context: Optional[ToolContext] = None
) -> str:
    """
    Manage and coordinate analysis tasks using the new context-driven approach.
    
    This tool integrates with AnalysisContextManager to provide task management
    capabilities for agents, allowing them to track progress, manage todos,
    and coordinate analysis workflow.
    
    Args:
        repo_path: Path to repository to analyze
        max_tasks: Maximum number of tasks to track
        priority_focus: Focus area for analysis ("security", "architecture")
        tool_context: ADK tool context (optional)
    
    Returns:
        Task management summary and current status
    """
    
    try:
        logger.info(f"Managing analysis tasks for: {repo_path}")
        
        # Initialize context manager
        context_manager = AnalysisContextManager(repo_path)
        
        # Get current project overview
        overview = context_manager.get_project_overview()
        
        # Get analysis history
        history = context_manager.get_analysis_history(limit=10)
        
        # Get current todos
        todos = context_manager.get_todos(status="pending")
        
        # Get security summary
        security = context_manager.get_security_summary()
        
        # Prepare comprehensive task summary
        summary = f"""ANALYSIS TASK MANAGEMENT - {repo_path}
        
=== PROJECT STATUS ===
Project Type: {overview['project_type']}
Total Files: {overview['total_files']} | Directories: {overview['total_directories']}
Analyzed Files: {overview['analysis_progress']['files_analyzed']}
Security Findings: {overview['analysis_progress']['security_findings']}

=== ACTIVE TODOS ({len(todos)}) ===
"""
        
        if todos:
            for todo in todos[:5]:  # Show top 5 todos
                summary += f"• [{todo['priority'].upper()}] {todo['description']}\n"
        else:
            summary += "No pending todos\n"
            
        summary += f"""
=== SECURITY STATUS ===
Total Findings: {security.get('total_findings', 0)}
High Risk Files: {security.get('high_risk_count', 0)} | Medium Risk Files: {security.get('medium_risk_count', 0)}

=== RECENT ACTIVITY ===
"""
        
        if history:
            for entry in history[:3]:  # Show last 3 activities
                timestamp = entry['timestamp'][:19]  # Remove microseconds
                if entry['type'] == 'structure_discovery':
                    summary += f"[{timestamp}] DISCOVERED: {entry['path']} - {entry['files_found']} files\n"
                elif entry['type'] == 'file_analysis':
                    summary += f"[{timestamp}] ANALYZED: {entry['file']} - Risk: {entry['risk_level']}\n"
        else:
            summary += "No recent activity\n"
            
        summary += f"""
=== NEXT RECOMMENDATIONS ===
Based on current analysis state and {priority_focus} focus, suggest prioritizing:
1. High-risk security files requiring analysis
2. Configuration files with potential vulnerabilities
3. Entry points and authentication mechanisms
"""
        
        return summary
        
    except Exception as e:
        error_msg = f"Failed to manage tasks: {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"