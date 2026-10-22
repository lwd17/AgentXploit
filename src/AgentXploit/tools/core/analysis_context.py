"""
Unified analysis context manager

Provides a simple context management class to replace the existing knowledge_base dictionary.
Manages analysis state including explored directories and analyzed files.
"""

from typing import List, Set, Dict, Any
from pathlib import Path


class AnalysisContext:
    """Analysis context manager for tracking global analysis state"""
    
    def __init__(self, repo_path: str = None):
        self._explored_directories: Set[str] = set()
        self._analyzed_files: Set[str] = set()
        self._additional_data: Dict[str, Any] = {}
        # Repository root for path normalization
        self._repo_path = Path(repo_path).resolve() if repo_path else None
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path to prevent duplicate tracking of same file/directory"""
        try:
            if self._repo_path:
                # Convert to absolute path and resolve to handle . and .. and symlinks
                abs_path = (self._repo_path / path).resolve()
                # Convert back to relative path from repo root
                try:
                    rel_path = abs_path.relative_to(self._repo_path)
                    return str(rel_path).replace('\\', '/')  # Normalize separators
                except ValueError:
                    # Path is outside repo, return as-is but normalized
                    return str(abs_path).replace('\\', '/')
            else:
                # No repo path set, just resolve the path
                return str(Path(path).resolve()).replace('\\', '/')
        except Exception:
            # Fallback to original path if normalization fails
            return path.replace('\\', '/')
    
    def add_explored_directory(self, directory_path: str) -> None:
        normalized_path = self._normalize_path(directory_path)
        self._explored_directories.add(normalized_path)
    
    def add_analyzed_file(self, file_path: str) -> None:
        normalized_path = self._normalize_path(file_path)
        self._analyzed_files.add(normalized_path)
    
    def get_explored_directories(self) -> List[str]:
        return sorted(list(self._explored_directories))
    
    def get_analyzed_files(self) -> List[str]:
        return sorted(list(self._analyzed_files))
    
    def is_directory_explored(self, directory_path: str) -> bool:
        normalized_path = self._normalize_path(directory_path)
        return normalized_path in self._explored_directories
    
    def is_file_analyzed(self, file_path: str) -> bool:
        normalized_path = self._normalize_path(file_path)
        return normalized_path in self._analyzed_files
    
    def set_data(self, key: str, value: Any) -> None:
        self._additional_data[key] = value
    
    def get_data(self, key: str, default: Any = None) -> Any:
        return self._additional_data.get(key, default)
    
    def clear(self) -> None:
        """Reset all analysis state"""
        self._explored_directories.clear()
        self._analyzed_files.clear()
        self._additional_data.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get context summary with counts and lists of explored/analyzed items"""
        return {
            "explored_directories_count": len(self._explored_directories),
            "analyzed_files_count": len(self._analyzed_files),
            "explored_directories": self.get_explored_directories(),
            "analyzed_files": self.get_analyzed_files(),
            "additional_data_keys": list(self._additional_data.keys())
        }
