"""
Code reading tools for analyzing local agent codebases.
"""
import os
import logging
import subprocess
import fnmatch
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_LINES = 2000
MAX_LINE_LENGTH = 2000


def read(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> dict:
    """Reads a file from the local filesystem.

    You can access any file directly by using this tool. Assume this tool is able
    to read all files on the machine. If the User provides a path to a file assume
    that path is valid. It is okay to read a file that does not exist; an error
    will be returned.

    Usage:
    - The file_path parameter must be an absolute path, not a relative path
    - By default, it reads up to 2000 lines starting from the beginning of the file
    - You can optionally specify a line offset and limit (especially handy for
      long files), but it's recommended to read the whole file by not providing
      these parameters
    - Any lines longer than 2000 characters will be truncated
    - Results are returned using cat -n format, with line numbers starting at 1
    - If you read a file that exists but has empty contents you will receive a
      system reminder warning in place of file contents.

    Args:
        file_path: The absolute path to the file to read
        offset: The line number to start reading from. Only provide if the file
                is too large to read at once
        limit: The number of lines to read. Only provide if the file is too large
               to read at once

    Returns:
        dict: {
            "success": bool,
            "file_path": str,
            "content": str,
            "message": str
        }
    """
    try:
        abs_path = os.path.abspath(file_path)

        if not os.path.exists(abs_path):
            return {
                "success": False,
                "file_path": abs_path,
                "content": "",
                "message": f"File not found: {abs_path}"
            }

        if os.path.isdir(abs_path):
            return {
                "success": False,
                "file_path": abs_path,
                "content": "",
                "message": f"Path is a directory, not a file: {abs_path}"
            }

        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        # Handle empty file
        if total_lines == 0:
            return {
                "success": True,
                "file_path": abs_path,
                "content": "[File is empty]",
                "message": f"File exists but has no content: {abs_path}"
            }

        # Apply offset and limit
        start_line = offset if offset is not None else 0
        max_lines = limit if limit is not None else DEFAULT_MAX_LINES

        # Clamp start_line to valid range
        start_line = max(0, min(start_line, total_lines - 1))

        # Select lines
        end_line = min(start_line + max_lines, total_lines)
        selected_lines = all_lines[start_line:end_line]

        # Format as cat -n output (line numbers starting at 1)
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=start_line + 1):
            # Truncate long lines
            line = line.rstrip('\n\r')
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "... [truncated]"
            formatted_lines.append(f"{i:6}\t{line}")

        content = '\n'.join(formatted_lines)

        # Build message
        lines_read = len(selected_lines)
        if lines_read < total_lines:
            message = f"Read lines {start_line + 1}-{end_line} of {total_lines} from {abs_path}"
        else:
            message = f"Read {total_lines} lines from {abs_path}"

        return {
            "success": True,
            "file_path": abs_path,
            "content": content,
            "message": message
        }

    except Exception as e:
        logger.error(f"Read error: {e}", exc_info=True)
        return {
            "success": False,
            "file_path": os.path.abspath(file_path),
            "content": "",
            "message": f"Error: {str(e)}"
        }


def glob(pattern: str, path: Optional[str] = None) -> dict:
    """Fast file pattern matching tool that works with any codebase size.

    Supports glob patterns with wildcards for flexible file matching.
    Returns matching file paths (absolute) sorted by modification time.
    Use this tool when you need to find files by name patterns.

    RECOMMENDED: Use broad wildcard patterns to avoid missing files:
    - "**/*tool*" or "**/*Tool*" - find files containing 'tool' in the name
    - "**/*agent*/**/*.py" - find .py files under directories containing 'agent'
    - "**/*.{py,js,ts}" - find files with multiple extensions
    - "**/test*" or "**/*test*" - find test-related files
    - "**/*[Cc]onfig*" - case-insensitive pattern matching

    Pattern syntax:
    - * matches any characters within a single path segment
    - ** matches any characters across path segments (recursive)
    - ? matches a single character
    - [abc] matches any character in brackets
    - {a,b,c} matches any of the comma-separated patterns

    Examples:
    - glob("**/*OpenHands*/**") - find all files under OpenHands directories
    - glob("**/*openhands*/**") - also search lowercase variant
    - glob("**/src/**/*.py") - find Python files under any src directory
    - glob("**/*handler*") - find files with 'handler' in the name

    Args:
        pattern: The glob pattern to match files against. Use wildcards liberally
                 to avoid overly narrow searches.
        path: The directory to search in. If not specified, the current working
              directory will be used. Must be a valid directory path if provided.

    Returns:
        dict: {
            "success": bool,
            "pattern": str,
            "path": str,
            "files": list[str],
            "total_matches": int,
            "message": str
        }
    """
    try:
        search_path = Path(os.path.abspath(path)) if path else Path.cwd()

        if not search_path.exists():
            return {
                "success": False,
                "pattern": pattern,
                "path": str(search_path),
                "files": [],
                "total_matches": 0,
                "message": f"Directory not found: {search_path}"
            }

        if not search_path.is_dir():
            return {
                "success": False,
                "pattern": pattern,
                "path": str(search_path),
                "files": [],
                "total_matches": 0,
                "message": f"Not a directory: {search_path}"
            }

        # Find matching files
        matched_files = []
        for match in search_path.glob(pattern):
            if match.is_file():
                abs_match = match.resolve()
                matched_files.append((str(abs_match), abs_match.stat().st_mtime))

        # Sort by modification time (most recent first)
        matched_files.sort(key=lambda x: x[1], reverse=True)
        files = [f[0] for f in matched_files]

        return {
            "success": True,
            "pattern": pattern,
            "path": str(search_path),
            "files": files,
            "total_matches": len(files),
            "message": f"Found {len(files)} files matching '{pattern}'"
        }

    except Exception as e:
        logger.error(f"Glob error: {e}", exc_info=True)
        return {
            "success": False,
            "pattern": pattern,
            "path": os.path.abspath(path) if path else str(Path.cwd()),
            "files": [],
            "total_matches": 0,
            "message": f"Error: {str(e)}"
        }


def grep(pattern: str, path: Optional[str] = None, include: Optional[str] = None,
         case_insensitive: bool = False) -> dict:
    """Fast content search tool that works with any codebase size.

    Searches file contents using regular expressions (powered by ripgrep).
    Returns file paths (absolute) with at least one match sorted by modification time.
    Use this tool when you need to find files containing specific patterns.

    RECOMMENDED: Use regex patterns for flexible matching:
    - Use "tool|Tool|TOOL" for case variations
    - Use ".*" to match any characters: "def.*tool"
    - Use "\\s+" for whitespace: "class\\s+\\w+Agent"
    - Use word boundaries: "\\btool\\b" to match exact word
    - Use alternation: "(read|write|execute)_file"

    Examples:
    - grep("def\\s+\\w+tool", include="*.py") - find Python function definitions with 'tool'
    - grep("import.*requests", include="*.py") - find requests imports
    - grep("(execute|run|eval)\\s*\\(", include="*.py") - find dangerous function calls
    - grep("api[_-]?key|API[_-]?KEY", case_insensitive=True) - find API key references
    - grep("\\.(get|post|put|delete)\\s*\\(") - find HTTP method calls

    Pattern syntax (ripgrep regex):
    - . matches any character
    - * matches zero or more of previous
    - + matches one or more of previous
    - ? matches zero or one of previous
    - \\s matches whitespace, \\w matches word characters
    - [abc] character class, [^abc] negated class
    - (a|b) alternation
    - ^ start of line, $ end of line
    - \\b word boundary

    Args:
        pattern: The regular expression pattern to search for in file contents.
                 Use regex liberally for flexible matching.
        path: The directory to search in. Defaults to the current working directory.
        include: File glob pattern to filter (e.g. "*.py", "*.{ts,tsx}", "*test*")
        case_insensitive: If True, perform case-insensitive search (default: False)

    Returns:
        dict: {
            "success": bool,
            "pattern": str,
            "path": str,
            "include": str or None,
            "files": list[str],
            "total_matches": int,
            "message": str
        }
    """
    try:
        search_path = os.path.abspath(path) if path else os.getcwd()

        result = None
        use_grep_fallback = False

        # Try ripgrep first
        try:
            cmd = ["rg", "-l", pattern, search_path]
            if case_insensitive:
                cmd.insert(2, "-i")
            if include:
                cmd.extend(["--glob", include])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # rg returns 1 if no matches found, 0 if matches found, 2 for errors
            if result.returncode not in [0, 1]:
                use_grep_fallback = True
        except FileNotFoundError:
            # ripgrep not installed, fallback to grep
            use_grep_fallback = True

        # Fallback to grep if rg not available or failed
        if use_grep_fallback:
            try:
                cmd = ["grep", "-rlE", pattern, search_path]
                if case_insensitive:
                    cmd.insert(1, "-i")
                if include:
                    cmd.extend(["--include", include])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode not in [0, 1]:
                    return {
                        "success": False,
                        "pattern": pattern,
                        "path": search_path,
                        "include": include,
                        "files": [],
                        "total_matches": 0,
                        "message": f"Search failed: {result.stderr}"
                    }
            except FileNotFoundError:
                return {
                    "success": False,
                    "pattern": pattern,
                    "path": search_path,
                    "include": include,
                    "files": [],
                    "total_matches": 0,
                    "message": "Neither ripgrep (rg) nor grep is available on this system"
                }

        if result is None:
            return {
                "success": False,
                "pattern": pattern,
                "path": search_path,
                "include": include,
                "files": [],
                "total_matches": 0,
                "message": "Search failed: no result from search command"
            }

        # Parse file paths and convert to absolute paths
        raw_files = [f for f in result.stdout.strip().split('\n') if f]
        files_with_mtime = []
        for f in raw_files:
            abs_f = os.path.abspath(f)
            try:
                mtime = os.path.getmtime(abs_f)
                files_with_mtime.append((abs_f, mtime))
            except OSError:
                files_with_mtime.append((abs_f, 0))

        # Sort by modification time (most recent first)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        sorted_files = [f[0] for f in files_with_mtime]

        return {
            "success": True,
            "pattern": pattern,
            "path": search_path,
            "include": include,
            "files": sorted_files,
            "total_matches": len(sorted_files),
            "message": f"Found {len(sorted_files)} files containing pattern '{pattern}'"
        }

    except Exception as e:
        logger.error(f"Grep error: {e}", exc_info=True)
        return {
            "success": False,
            "pattern": pattern,
            "path": os.path.abspath(path) if path else os.getcwd(),
            "include": include,
            "files": [],
            "total_matches": 0,
            "message": f"Error: {str(e)}"
        }


def ls(path: str, ignore: Optional[List[str]] = None) -> dict:
    """Lists files and directories in a given path.

    The path parameter must be an absolute path, not a relative path.
    You can optionally provide an array of glob patterns to ignore.
    You should generally prefer the glob and grep tools if you know which
    directories to search.

    Args:
        path: The absolute path to the directory to list (must be absolute, not relative)
        ignore: List of glob patterns to ignore

    Returns:
        dict: {
            "success": bool,
            "path": str,
            "files": list[str],
            "directories": list[str],
            "total_items": int,
            "message": str
        }
    """
    try:
        abs_path = os.path.abspath(path)
        dir_path = Path(abs_path)

        if not dir_path.exists():
            return {
                "success": False,
                "path": abs_path,
                "files": [],
                "directories": [],
                "total_items": 0,
                "message": f"Directory not found: {abs_path}"
            }

        if not dir_path.is_dir():
            return {
                "success": False,
                "path": abs_path,
                "files": [],
                "directories": [],
                "total_items": 0,
                "message": f"Not a directory: {abs_path}"
            }

        ignore_patterns = ignore or []
        files = []
        directories = []

        for item in dir_path.iterdir():
            # Check if item matches any ignore pattern
            should_ignore = any(fnmatch.fnmatch(item.name, p) for p in ignore_patterns)
            if should_ignore:
                continue

            abs_item_path = str(item.resolve())
            if item.is_file():
                files.append(abs_item_path)
            elif item.is_dir():
                directories.append(abs_item_path)

        return {
            "success": True,
            "path": abs_path,
            "files": sorted(files),
            "directories": sorted(directories),
            "total_items": len(files) + len(directories),
            "message": f"Found {len(files)} files and {len(directories)} directories"
        }

    except Exception as e:
        logger.error(f"LS error: {e}", exc_info=True)
        return {
            "success": False,
            "path": os.path.abspath(path),
            "files": [],
            "directories": [],
            "total_items": 0,
            "message": f"Error: {str(e)}"
        }


__all__ = ["read", "glob", "grep", "ls"]
