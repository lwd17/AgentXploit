#!/usr/bin/env python3
"""
mcp_language_server_agent.py
MCP Language Server Agent - Final Version
"""

import os
import re
import json
from typing import List
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters
import asyncio
from google.adk.runners import InMemoryRunner
from google.genai.types import Part, UserContent
from google.adk.models.lite_llm import LiteLlm

# Load environment variables
load_dotenv()


class LanguageServerRunner:
    """Runner for MCP Language Server Agent"""

    def __init__(self, workspace: str):
        """
        Initialize the Language Server Runner with .env configuration

        Args:
            workspace: REQUIRED - Path to the workspace directory for LSP analysis.
                       Must be explicitly provided to avoid using os.getcwd() incorrectly.
        """
        if not workspace:
            raise ValueError("workspace parameter is required - cannot use default os.getcwd()")

        # Read configuration from environment
        self.lsp_server = os.getenv("LSP_SERVER_TYPE", "pyright-langserver")
        self.model_name = os.getenv("MCP_AGENT_MODEL", "openai/gpt-4.1-2025-04-14")

        # Use provided workspace (no default fallback to avoid incorrect paths)
        self.default_workspace = workspace
        print(f"  [MCP_WORKSPACE] Using workspace: {self.default_workspace}")

        # Create the agent
        self.agent = self._create_agent()

        # Initialize runner and session immediately to avoid duplicate MCP processes
        self.runner = InMemoryRunner(agent=self.agent)
        self.session = None  # Will be created in first async call
        self._session_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

    def _create_agent(self) -> LlmAgent:
        """Create the MCP Language Server Agent"""
        return LlmAgent(
            model=LiteLlm(model=self.model_name),
            name="language_server_agent",
            instruction="""You are a code analysis assistant with access to Language Server Protocol tools.

IMPORTANT: You have access to MCP Language Server tools. Use them actively!

Available LSP tools you should use:
- lsp_textDocument_definition: Find where symbols are defined
- lsp_textDocument_references: Find all references to a symbol
- lsp_textDocument_documentSymbol: Get all symbols in a document
- lsp_workspace_symbol: Search for symbols across workspace

When analyzing file dependencies:
1. FIRST use lsp_textDocument_documentSymbol to get all imports/symbols in the file
2. THEN use lsp_textDocument_definition to resolve import paths
3. Extract and return the actual file paths

Always return results as a JSON array of file paths.""",
            tools=[
                MCPToolset(
                    connection_params=StdioServerParameters(
                        command="mcp-language-server",
                        args=[
                            "--workspace",
                            self.default_workspace,
                            "--lsp",
                            self.lsp_server,
                            "--",
                            "--stdio",
                        ],
                    ),
                )
            ],
        )

    def run(self, prompt: str) -> str:
        """Run the agent with a prompt using Google ADK runner"""
        try:
            # Run the agent asynchronously - handle existing event loop properly
            try:
                # Check if we're already in an event loop
                asyncio.get_running_loop()
                # We're in an event loop, use thread-based execution
                import concurrent.futures

                def run_in_thread():
                    # Create new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(self._run_async_helper(prompt))
                    finally:
                        # Cancel all pending tasks before closing
                        try:
                            pending = asyncio.all_tasks(new_loop)
                            for task in pending:
                                task.cancel()
                            # Wait for all tasks to complete cancellation
                            if pending:
                                new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception:
                            pass
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    result = future.result(timeout=60)  # 60 second timeout
                    return result

            except RuntimeError:
                # No running event loop, safe to use asyncio.run()
                result = asyncio.run(self._run_async_helper(prompt))
                return result

        except Exception:
            raise

    async def _run_async_helper(self, prompt: str) -> str:
        """Async helper to run the agent"""
        try:
            # Create session on first call only
            if self.session is None:
                self.session = await self.runner.session_service.create_session(
                    app_name=self.runner.app_name, user_id="mcp_user"
                )
                print("  [MCP_INIT] Created persistent session (runner already initialized)")

            # Create content
            content = UserContent(parts=[Part(text=prompt)])

            # Run agent and collect response
            response_text = ""
            async for event in self.runner.run_async(
                user_id=self.session.user_id,
                session_id=self.session.id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text

            return response_text or "[]"

        except Exception:
            raise

    def extract_file_list(self, response: str) -> List[str]:
        """Extract file list from agent response"""
        try:
            # Find JSON array in response
            json_match = re.search(r"\[.*?\]", response, re.DOTALL)
            if json_match:
                files = json.loads(json_match.group())
                # Filter to only return strings
                return [f for f in files if isinstance(f, str)]
        except Exception:
            raise

        # Extract file paths with common extensions
        patterns = r'["\']?([a-zA-Z0-9_\-/]+\.(?:py|js|ts|jsx|tsx|json|yaml|yml))["\']?'
        matches = re.findall(patterns, response)
        return list(set(matches))

    def get_file_diagnostics(self, file_uri: str, max_diagnostics: int = 10) -> List[dict]:
        """
        Get diagnostics for a specific file only (not all files in workspace).
        This prevents system hangs when processing large workspaces.
        
        NOTE: This method may not work as expected because LSP servers typically 
        push diagnostics for ALL files in the workspace after scanning completes.
        Consider disabling diagnostics entirely or using a very limited workspace.
        
        Args:
            file_uri: File URI (e.g., "file:///path/to/file.py")
            max_diagnostics: Maximum number of diagnostics to return
            
        Returns:
            List of diagnostic objects with useful information extracted
        """
        print(f"  [MCP_DIAGNOSTICS] WARNING: Diagnostics disabled to prevent workspace-wide scans")
        print(f"  [MCP_DIAGNOSTICS] LSP pushes diagnostics for ALL {self.default_workspace} files after scan")
        print(f"  [MCP_DIAGNOSTICS] This causes system hangs with large workspaces (2389+ files)")
        print(f"  [MCP_DIAGNOSTICS] Returning empty list to avoid hang")
        return []
        
        # DISABLED: The code below is commented out because LSP servers push 
        # diagnostics for ALL files in workspace, not just the requested file.
        # This causes system hangs when workspace contains 2389+ files.
        #
        # try:
        #     prompt = f"""Get diagnostics for this specific file only: {file_uri}
        # 
        # Use lsp_textDocument_diagnostic or similar LSP tools to get ONLY the diagnostics for this single file.
        # 
        # Return the diagnostics as a JSON array with this format:
        # [
        #   {{
        #     "severity": "error|warning|info",
        #     "message": "diagnostic message",
        #     "line": line_number,
        #     "code": "error_code"
        #   }}
        # ]
        # 
        # Return [] if no diagnostics found or if the tool is not available."""
        # 
        #     print(f"  [MCP_DIAGNOSTICS] Getting diagnostics for: {file_uri}")
        #     response = self.run(prompt)
        #     
        #     # Extract JSON array from response
        #     try:
        #         json_match = re.search(r"\[.*?\]", response, re.DOTALL)
        #         if json_match:
        #             diagnostics = json.loads(json_match.group())
        #             # Filter and limit diagnostics
        #             return self._filter_useful_diagnostics(diagnostics, max_diagnostics)
        #     except Exception as e:
        #         print(f"  [MCP_DIAGNOSTICS] Failed to parse diagnostics: {e}")
        #         return []
        #         
        #     return []
        #     
        # except Exception as e:
        #     print(f"  [MCP_DIAGNOSTICS] Error getting diagnostics: {e}")
        #     return []
    
    def _filter_useful_diagnostics(self, diagnostics: List[dict], max_count: int) -> List[dict]:
        """
        Filter diagnostics to extract only useful information.
        Prioritizes errors over warnings, and limits the count.
        
        Args:
            diagnostics: Raw diagnostics list
            max_count: Maximum number of diagnostics to return
            
        Returns:
            Filtered and sorted list of diagnostics
        """
        if not diagnostics:
            return []
        
        # Define severity priority (lower number = higher priority)
        severity_priority = {
            "error": 1,
            "warning": 2,
            "info": 3,
            "hint": 4
        }
        
        # Filter out noise and prioritize by severity
        useful_diagnostics = []
        for diag in diagnostics:
            if not isinstance(diag, dict):
                continue
                
            severity = diag.get("severity", "info").lower()
            message = diag.get("message", "")
            
            # Skip common noise patterns
            skip_patterns = [
                "could not import",  # Common false positives
                "unused import",     # Not critical for security analysis
                "line too long",     # Style issues
                "missing docstring"  # Documentation issues
            ]
            
            if any(pattern in message.lower() for pattern in skip_patterns):
                continue
            
            useful_diagnostics.append({
                "severity": severity,
                "message": message,
                "line": diag.get("line", 0),
                "code": diag.get("code", ""),
                "priority": severity_priority.get(severity, 5)
            })
        
        # Sort by priority (errors first) and limit count
        useful_diagnostics.sort(key=lambda x: x["priority"])
        return useful_diagnostics[:max_count]


# Global runner cache - maps workspace path to runner instance
_runner_cache = {}
_MAX_RUNNERS = 3  # Limit number of cached runners to prevent memory issues


def get_runner(workspace: str, force_new: bool = False) -> LanguageServerRunner:
    """
    Get or create a runner instance with specified workspace.
    
    CRITICAL FOR PERFORMANCE: To avoid LSP scanning 2389+ files and pushing diagnostics 
    for ALL files (which causes system hangs), we:
    1. Use the SMALLEST possible workspace (file's parent directory)
    2. Cache runners per workspace to avoid repeated scans
    3. Limit cache size to prevent memory issues

    Args:
        workspace: REQUIRED - Path to the workspace directory for LSP analysis.
                   Should be the file's parent directory (NOT the repo root!)
                   to minimize LSP indexing overhead and diagnostic pushes.
        force_new: If True, creates a new runner even if one exists for this workspace
                   (use with caution as it will trigger a new LSP workspace scan)

    Returns:
        LanguageServerRunner instance configured for the specified workspace
    """
    global _runner_cache

    if not workspace:
        raise ValueError("workspace parameter is required for get_runner()")

    # Check cache first (unless force_new is True)
    if not force_new and workspace in _runner_cache:
        print(f"  [MCP_RUNNER] Reusing cached runner for workspace: {workspace}")
        return _runner_cache[workspace]

    # Clean up old runners if cache is full
    if len(_runner_cache) >= _MAX_RUNNERS:
        print(f"  [MCP_RUNNER] Cache full ({_MAX_RUNNERS} runners), clearing oldest entry")
        # Remove the first (oldest) entry
        oldest_workspace = next(iter(_runner_cache))
        del _runner_cache[oldest_workspace]

    # Create new runner with MINIMAL workspace scope
    print(f"  [MCP_RUNNER] Creating NEW runner with LIMITED workspace: {workspace}")
    print(f"  [MCP_RUNNER] WARNING: LSP will scan this directory and push ALL file diagnostics")
    print(f"  [MCP_RUNNER] Keep workspace as SMALL as possible to avoid system hangs!")
    
    runner = LanguageServerRunner(workspace=workspace)
    _runner_cache[workspace] = runner

    return runner


def clear_runner_cache():
    """
    Clear all cached runners. Use this to force fresh LSP sessions.
    WARNING: This will cause LSP to rescan workspaces on next use.
    """
    global _runner_cache
    print(f"  [MCP_RUNNER] Clearing {len(_runner_cache)} cached runners")
    _runner_cache.clear()
