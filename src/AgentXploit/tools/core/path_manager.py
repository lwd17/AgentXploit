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
Unified Path Manager for AgentXploit
Combines path validation and resolution into a single, consistent interface
Uses absolute workspace path + relative path approach for clear path management
"""

import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class PathManager:
    """
    Unified path management for validation, resolution and context tracking
    
    Design principles:
    1. Workspace is the absolute path to the repository root (e.g., /srv/home/shiqiu/OpenHands)
    2. All file/directory operations use workspace + relative_path
    3. Context tracks current working directory within workspace
    4. Prevents path state loss during content follow-up operations
    """
    
    def __init__(self, workspace_path: str):
        """
        Initialize path manager with absolute workspace path
        
        Args:
            workspace_path: Absolute path to the repository/workspace root
        """
        self.workspace_path = Path(workspace_path).resolve()
        if not self.workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace_path}")
        if not self.workspace_path.is_dir():
            raise ValueError(f"Workspace path is not a directory: {workspace_path}")
            
        self.current_working_dir = "."  # Relative to workspace_path
        logger.info(f"[PATH_MANAGER] Initialized with workspace: {self.workspace_path}")
    
    def set_working_directory(self, relative_path: str) -> bool:
        """
        Set current working directory within workspace
        
        Args:
            relative_path: Path relative to workspace (e.g., "openhands/llm" or ".")
            
        Returns:
            bool: True if successful, False if directory doesn't exist
        """
        try:
            # Normalize the path
            normalized = self._normalize_relative_path(relative_path)
            full_path = self.workspace_path / normalized
            
            if full_path.exists() and full_path.is_dir():
                self.current_working_dir = normalized
                logger.debug(f"[PATH_MANAGER] Working directory set to: {self.current_working_dir}")
                return True
            else:
                logger.warning(f"[PATH_MANAGER] Directory does not exist: {normalized}")
                return False
        except Exception as e:
            logger.error(f"[PATH_MANAGER] Error setting working directory: {e}")
            return False
    
    def get_working_directory(self) -> str:
        """Get current working directory relative to workspace"""
        return self.current_working_dir
    
    def get_absolute_path(self, relative_path: str = None) -> Path:
        """
        Get absolute path for a relative path within workspace
        
        Args:
            relative_path: Path relative to workspace, if None returns workspace path
            
        Returns:
            Path: Absolute path
        """
        if relative_path is None:
            return self.workspace_path
        
        normalized = self._normalize_relative_path(relative_path)
        return self.workspace_path / normalized
    
    def _normalize_relative_path(self, path: str) -> str:
        """
        Normalize a relative path to be consistent and safe
        
        Args:
            path: Input path (may be relative or have './' prefix)
            
        Returns:
            str: Normalized relative path
        """
        if not path:
            return "."
        
        # Clean the path
        path = str(path).strip().replace('\\', '/')
        
        # Remove leading './' if present
        if path.startswith('./'):
            path = path[2:]
        
        # Ensure it's not absolute
        if os.path.isabs(path):
            # Convert to relative if it's within workspace
            abs_path = Path(path).resolve()
            try:
                relative = abs_path.relative_to(self.workspace_path)
                path = str(relative).replace('\\', '/')
            except ValueError:
                # Path is outside workspace, invalid
                raise ValueError(f"Path outside workspace: {path}")
        
        # Handle "." case
        if path in ("", "."):
            return "."
        
        # Ensure no parent directory escapes
        if '..' in Path(path).parts:
            raise ValueError(f"Parent directory references not allowed: {path}")
        
        return path.replace('\\', '/')
    
    def resolve_target_path(self, target_path: str, target_type: str = "file", 
                           context_path: Optional[str] = None) -> Tuple[str, bool, str]:
        """
        Resolve target path with proper context handling
        
        Args:
            target_path: Target path (relative or from workspace root)
            target_type: Type of target ("file" or "directory")  
            context_path: Optional context path (file path or explored directory)
            
        Returns:
            Tuple of (resolved_relative_path, is_valid, reason)
        """
        try:
            # Check if target_path looks like a workspace-relative path
            # (contains multiple path components and starts with a known directory)
            target_parts = Path(target_path).parts
            
            if len(target_parts) > 1 and not target_path.startswith(('.', '..')):
                # This looks like a workspace-relative path (e.g., "openhands/cli/utils.py")
                # Try resolving directly from workspace root first
                resolved_relative = self._normalize_relative_path(target_path)
                absolute_path = self.get_absolute_path(resolved_relative)
                
                if absolute_path.exists():
                    # Direct workspace resolution worked
                    logger.debug(f"[PATH_MANAGER] Workspace-relative path resolved: '{target_path}' -> '{resolved_relative}'")
                else:
                    # Fall back to context-relative resolution
                    context_dir = self._determine_context_directory(context_path)
                    if context_dir != ".":
                        combined = f"{context_dir}/{target_path}"
                        resolved_relative = self._normalize_relative_path(combined)
                        logger.debug(f"[PATH_MANAGER] Context-relative fallback: '{target_path}' in '{context_dir}' -> '{resolved_relative}'")
            else:
                # This is a simple relative path (e.g., "utils.py", "../config.py")
                # Use context-based resolution
                context_dir = self._determine_context_directory(context_path)
                
                if context_dir == ".":
                    # At workspace root
                    resolved_relative = self._normalize_relative_path(target_path)
                else:
                    # In a subdirectory, combine paths
                    combined = f"{context_dir}/{target_path}"
                    resolved_relative = self._normalize_relative_path(combined)
            
            logger.debug(f"[PATH_MANAGER] Final resolution: '{target_path}' -> '{resolved_relative}'")
            
            # Validate the resolved path
            absolute_path = self.get_absolute_path(resolved_relative)
            
            if not absolute_path.exists():
                return resolved_relative, False, f"Path does not exist: {resolved_relative}"
            
            if target_type == "file" and not absolute_path.is_file():
                return resolved_relative, False, f"Path is not a file: {resolved_relative}"
            
            if target_type == "directory" and not absolute_path.is_dir():
                return resolved_relative, False, f"Path is not a directory: {resolved_relative}"
            
            # Additional validation for security
            if self._is_excluded_path(resolved_relative):
                return resolved_relative, False, f"Excluded path type: {resolved_relative}"
            
            logger.debug(f"[PATH_MANAGER] Successfully resolved: '{target_path}' -> '{resolved_relative}'")
            return resolved_relative, True, "Valid path"
            
        except Exception as e:
            logger.error(f"[PATH_MANAGER] Resolution error: {e}")
            return target_path, False, str(e)
    
    def _determine_context_directory(self, context_path: Optional[str]) -> str:
        """
        Determine the context directory for path resolution
        
        Args:
            context_path: Optional context (file path or directory path)
            
        Returns:
            str: Context directory relative to workspace
        """
        if not context_path:
            return self.current_working_dir
        
        try:
            normalized_context = self._normalize_relative_path(context_path)
            absolute_context = self.get_absolute_path(normalized_context)
            
            if absolute_context.is_file():
                # Context is a file, use its parent directory
                parent_relative = str(Path(normalized_context).parent)
                return "." if parent_relative in ("", ".") else parent_relative.replace('\\', '/')
            elif absolute_context.is_dir():
                # Context is a directory, use it directly
                return normalized_context
            else:
                # Context doesn't exist, fall back to current working dir
                return self.current_working_dir
                
        except Exception:
            return self.current_working_dir
    
    def _is_excluded_path(self, relative_path: str) -> bool:
        """Check if path should be excluded from processing"""
        excluded_patterns = {
            'node_modules', '__pycache__', '.git', 'build', 'dist', 
            '.pytest_cache', '.mypy_cache', '.tox', 'venv', 'env'
        }
        
        path_parts = set(Path(relative_path).parts)
        return bool(path_parts & excluded_patterns)
    
    def resolve_content_follow_up_paths(self, targets: List[Dict], current_file_path: str) -> List[Dict]:
        """
        Resolve paths for content follow-up targets with proper file context
        
        Args:
            targets: List of target dictionaries with 'path' and 'type'
            current_file_path: Path of the file that triggered the follow-up (relative to workspace)
            
        Returns:
            List of resolved target dictionaries with updated paths
        """
        resolved_targets = []
        
        for target in targets:
            if not isinstance(target, dict) or "path" not in target:
                continue
                
            original_path = target["path"]
            target_type = target.get("type", "file")
            
            # Use the current file as context for resolution
            resolved_path, is_valid, reason = self.resolve_target_path(
                original_path, target_type, current_file_path
            )
            
            if is_valid:
                resolved_target = target.copy()
                resolved_target["path"] = resolved_path
                resolved_target["original_path"] = original_path
                resolved_targets.append(resolved_target)
                logger.info(f"[PATH_MANAGER] Content follow-up: '{original_path}' -> '{resolved_path}'")
            else:
                logger.warning(f"[PATH_MANAGER] Invalid content follow-up: '{original_path}' ({reason})")
        
        return resolved_targets
    
    def resolve_exploration_paths(self, targets: List[Dict], explored_path: str) -> List[Dict]:
        """
        Resolve paths for exploration targets with proper directory context
        
        Args:
            targets: List of target dictionaries with 'path' and 'type'
            explored_path: Current directory being explored (relative to workspace)
            
        Returns:
            List of resolved target dictionaries with updated paths
        """
        resolved_targets = []
        
        # Update working directory to the explored path for context
        original_working_dir = self.current_working_dir
        self.set_working_directory(explored_path)
        
        try:
            for target in targets:
                if not isinstance(target, dict) or "path" not in target:
                    continue
                    
                original_path = target["path"]
                target_type = target.get("type", "file")
                
                # Use the explored directory as context for resolution
                resolved_path, is_valid, reason = self.resolve_target_path(
                    original_path, target_type, explored_path
                )
                
                if is_valid:
                    resolved_target = target.copy()
                    resolved_target["path"] = resolved_path
                    resolved_target["original_path"] = original_path
                    resolved_targets.append(resolved_target)
                    logger.info(f"[PATH_MANAGER] Exploration: '{original_path}' -> '{resolved_path}'")
                else:
                    logger.warning(f"[PATH_MANAGER] Invalid exploration: '{original_path}' ({reason})")
        
        finally:
            # Restore original working directory
            self.current_working_dir = original_working_dir
        
        return resolved_targets
    
    def get_path_info(self, relative_path: str) -> Dict[str, Any]:
        """
        Get comprehensive information about a path
        
        Args:
            relative_path: Path relative to workspace
            
        Returns:
            Dict with path information
        """
        try:
            normalized = self._normalize_relative_path(relative_path)
            absolute_path = self.get_absolute_path(normalized)
            
            return {
                'relative_path': normalized,
                'absolute_path': str(absolute_path),
                'exists': absolute_path.exists(),
                'is_file': absolute_path.is_file() if absolute_path.exists() else False,
                'is_directory': absolute_path.is_dir() if absolute_path.exists() else False,
                'size': absolute_path.stat().st_size if absolute_path.is_file() else 0,
                'depth': len(Path(normalized).parts) if normalized != "." else 0,
                'excluded': self._is_excluded_path(normalized),
                'category': self._get_path_category(normalized, absolute_path)
            }
        except Exception as e:
            return {
                'relative_path': relative_path,
                'absolute_path': str(self.workspace_path / relative_path),
                'exists': False,
                'error': str(e)
            }
    
    def _get_path_category(self, relative_path: str, absolute_path: Path) -> str:
        """Categorize path for analysis context"""
        if not absolute_path.exists():
            return "nonexistent"
        
        if absolute_path.is_file():
            suffix = absolute_path.suffix.lower()
            if suffix == '.py':
                return "python_source"
            elif suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                return "javascript_source"
            elif suffix in {'.json', '.yaml', '.yml', '.toml'}:
                return "config_file"
            elif suffix in {'.md', '.rst', '.txt'}:
                return "documentation"
            elif suffix in {'.sh', '.bash'}:
                return "shell_script"
            else:
                return "general_file"
        
        elif absolute_path.is_dir():
            path_lower = relative_path.lower()
            if 'test' in path_lower:
                return "test_directory"
            elif any(pattern in path_lower for pattern in ['src', 'source', 'lib']):
                return "source_directory"
            elif any(pattern in path_lower for pattern in ['config', 'conf', 'settings']):
                return "config_directory"
            elif any(pattern in path_lower for pattern in ['doc', 'docs']):
                return "documentation_directory"
            else:
                return "general_directory"
        
        return "unknown"
    
    def validate_and_resolve_target(self, target_path: str, action_type: str, 
                                   context_path: Optional[str] = None) -> Tuple[str, bool, str]:
        """
        Combined validation and resolution for targets
        
        Args:
            target_path: Target path to resolve
            action_type: Action type ("read_file", "explore_directory", etc.)
            context_path: Optional context path
            
        Returns:
            Tuple of (resolved_path, is_valid, reason)
        """
        # Map action types to target types
        target_type_map = {
            'read_file': 'file',
            'analyze_file': 'file', 
            'explore_directory': 'directory',
            'explore': 'directory'
        }
        
        target_type = target_type_map.get(action_type, 'file')
        return self.resolve_target_path(target_path, target_type, context_path)
    
    def get_context_info(self) -> Dict[str, Any]:
        """Get current context information for debugging"""
        return {
            'workspace_path': str(self.workspace_path),
            'current_working_dir': self.current_working_dir,
            'absolute_working_path': str(self.get_absolute_path(self.current_working_dir))
        }
