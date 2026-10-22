import os
import re
import mimetypes
import chardet
import fnmatch
from typing import Dict, Any, List, Optional, Union, Pattern
from pathlib import Path


class EnhancedFileReader:
    """Enhanced file reader with better encoding support and error handling"""
    
    def __init__(self, repo_path: str, max_file_size: int = 10 * 1024 * 1024):  # 10MB default
        self.repo_path = Path(repo_path).resolve()
        self.max_file_size = max_file_size
        
        # Define file categories - expanded for better coverage
        self.text_extensions = {
            # Programming languages
            '.py', '.js', '.java', '.cpp', '.c', '.go', '.rs', '.php', '.rb',
            '.swift', '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', '.elm',
            # Web technologies
            '.html', '.css', '.xml', '.json', '.yaml', '.yml', '.toml',
            '.ts', '.jsx', '.tsx', '.vue', '.svelte', '.scss', '.less', '.sass',
            # Documentation
            '.txt', '.md', '.rst', '.adoc', '.tex', '.pdf', '.doc', '.docx',
            # Configuration
            '.cfg', '.ini', '.env', '.conf', '.properties', '.yml', '.yaml',
            '.dockerfile', '.gitignore', '.gitattributes', '.editorconfig',
            # Scripts
            '.sh', '.bat', '.ps1', '.cmd', '.awk', '.sed', '.lua', '.pl', '.tcl',
            # Data formats
            '.csv', '.tsv', '.xml', '.jsonl', '.parquet', '.avro',
            # Build tools
            '.gradle', '.maven', '.sbt', '.cargo', '.gemfile', '.pipfile',
            # Other
            '.sql', '.graphql', '.proto', '.thrift', '.dockerignore'
        }
        
        self.binary_extensions = {
            '.exe', '.dll', '.so', '.dylib', '.bin', '.obj',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
            '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z',
            '.mp4', '.mp3', '.wav', '.avi', '.mov',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
        }

    def read_file(self, file_path: str, start_line: Optional[int] = None,
                  end_line: Optional[int] = None, max_lines: int = 100,
                  force_encoding: Optional[str] = None) -> Dict[str, Any]:
        try:
            target_file = self.repo_path / file_path

            if not target_file.exists():
                # Try to provide more context about the file not found error
                parent_dir = target_file.parent
                if parent_dir.exists():
                    try:
                        # List contents of parent directory to help diagnose
                        import os
                        contents = os.listdir(parent_dir)
                        similar_files = [f for f in contents if file_path.split('/')[-1] in f][:5]
                        return {
                            "error": f"File not found: {file_path}",
                            "file_path": file_path,
                            "error_type": "FILE_NOT_FOUND",
                            "parent_directory_exists": True,
                            "parent_directory_contents": contents[:10],  # First 10 items
                            "similar_files": similar_files,
                            "suggestion": f"Check if the file exists in {parent_dir}"
                        }
                    except Exception:
                        pass

                return {
                    "error": f"File not found: {file_path}",
                    "file_path": file_path,
                    "error_type": "FILE_NOT_FOUND",
                    "parent_directory_exists": parent_dir.exists(),
                    "suggestion": "Check file path and ensure it exists"
                }
            
            # Check file size
            file_size = target_file.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "error": f"File too large ({self._format_size(file_size)}). Maximum allowed: {self._format_size(self.max_file_size)}",
                    "file_path": file_path,
                    "file_size": file_size,
                    "error_type": "FILE_TOO_LARGE"
                }
            
            # Check if file is likely binary
            file_type_info = self._analyze_file_type(target_file)
            
            if file_type_info["is_binary"]:
                return {
                    "error": f"Cannot read binary file (detected as {file_type_info['mime_type']})",
                    "file_path": file_path,
                    "file_type": file_type_info,
                    "error_type": "BINARY_FILE"
                }
            
            # Detect encoding
            encoding_info = self._detect_encoding(target_file, force_encoding)
            if not encoding_info["success"]:
                return {
                    "error": encoding_info["error"],
                    "file_path": file_path,
                    "encoding_info": encoding_info,
                    "error_type": "ENCODING_ERROR"
                }
            
            # Read file content
            try:
                with open(target_file, 'r', encoding=encoding_info["encoding"]) as f:
                    lines = f.readlines()
            except UnicodeDecodeError as e:
                # Try terminal fallback for encoding issues
                fallback_result = self._try_terminal_fallback(target_file, start_line, end_line, max_lines)
                if fallback_result:
                    return fallback_result

                return {
                    "error": f"Unicode decode error: {str(e)}",
                    "file_path": file_path,
                    "encoding_tried": encoding_info["encoding"],
                    "error_type": "UNICODE_ERROR"
                }
            
            total_lines = len(lines)
            
            # Handle line range
            start_idx = max(0, (start_line or 1) - 1)
            end_idx = min(total_lines, end_line or (start_idx + max_lines))
            
            selected_lines = lines[start_idx:end_idx]
            
            return {
                "file_path": file_path,
                "content": ''.join(selected_lines),
                "total_lines": total_lines,
                "lines_read": len(selected_lines),
                "start_line": start_idx + 1,
                "end_line": end_idx,
                "file_size": file_size,
                "file_size_str": self._format_size(file_size),
                "encoding": encoding_info["encoding"],
                "encoding_confidence": encoding_info.get("confidence"),
                "file_type": file_type_info,
                "truncated": len(selected_lines) < total_lines
            }
            
        except PermissionError:
            # Try terminal fallback for permission issues
            fallback_result = self._try_terminal_fallback(target_file, start_line, end_line, max_lines)
            if fallback_result:
                return fallback_result

            return {
                "error": "Permission denied",
                "file_path": file_path,
                "error_type": "PERMISSION_DENIED"
            }
        except Exception as e:
            # Try terminal fallback methods before giving up
            fallback_result = self._try_terminal_fallback(target_file, start_line, end_line, max_lines)
            if fallback_result:
                return fallback_result

            return {
                "error": f"Unexpected error: {str(e)}",
                "file_path": file_path,
                "error_type": "UNEXPECTED_ERROR"
            }

    def get_tree_structure(self, path: str = ".", max_depth: int = 3) -> Dict[str, Any]:
        """
        Get repository tree structure using tree command for efficiency

        Args:
            path: Relative path to get tree structure from
            max_depth: Maximum depth to traverse

        Returns:
            Dictionary containing tree structure information
        """
        import subprocess

        try:
            target_path = self.repo_path / path
            if not target_path.exists():
                return {
                    "error": f"Path not found: {path}",
                    "error_type": "PATH_NOT_FOUND"
                }

            # Use tree command for efficient directory traversal
            cmd = f"tree -L {max_depth} -a -I '.git|__pycache__|node_modules|.pytest_cache' '{target_path}' 2>/dev/null || find '{target_path}' -type f -name '*.py' -o -name '*.md' -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name '*.json' -o -name '*.sh' | head -50"

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                tree_output = result.stdout.strip()

                # Parse tree output to extract structure
                lines = tree_output.split('\n')
                directories = []
                files = []

                for line in lines:
                    if line.strip():
                        # Simple parsing - can be enhanced
                        if line.endswith('/'):
                            directories.append(line.strip().rstrip('/'))
                        elif '.' in line:
                            files.append(line.strip())

                return {
                    "tree_output": tree_output,
                    "directories": directories,
                    "files": files,
                    "total_directories": len(directories),
                    "total_files": len(files),
                    "method": "tree_command",
                    "max_depth": max_depth,
                    "path": path
                }
            else:
                # Fallback to basic find command
                fallback_cmd = f"find '{target_path}' -maxdepth {max_depth} -type f | head -50"
                fallback_result = subprocess.run(fallback_cmd, shell=True, capture_output=True, text=True, timeout=10)

                if fallback_result.returncode == 0:
                    files = [line.strip() for line in fallback_result.stdout.split('\n') if line.strip()]

                    return {
                        "tree_output": fallback_result.stdout.strip(),
                        "directories": [],  # Basic fallback doesn't separate dirs/files
                        "files": files,
                        "total_directories": 0,
                        "total_files": len(files),
                        "method": "find_fallback",
                        "max_depth": max_depth,
                        "path": path
                    }

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
            return {
                "error": f"Tree command failed: {str(e)}",
                "error_type": "TREE_COMMAND_ERROR"
            }

        return {
            "error": "Unable to get tree structure",
            "error_type": "UNKNOWN_ERROR"
        }

    def _try_terminal_fallback(self, target_file: Path, start_line: Optional[int] = None,
                              end_line: Optional[int] = None, max_lines: int = 100) -> Optional[Dict[str, Any]]:
        """
        Try terminal commands as fallback when Python file reading fails
        """
        import subprocess

        file_path_str = str(target_file)

        # Try different terminal commands in order of preference
        commands = []

        if start_line and end_line:
            # Try sed for line range
            commands.append(f"sed -n '{start_line},{end_line}p' '{file_path_str}'")
        elif start_line:
            # Try tail + head combination
            commands.append(f"tail -n +{start_line} '{file_path_str}' | head -n {max_lines}")
        else:
            # Try head for beginning of file
            commands.append(f"head -n {max_lines} '{file_path_str}'")

        # Try cat as basic fallback
        commands.append(f"cat '{file_path_str}'")

        for cmd in commands:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.split('\n')
                    total_lines = len(lines)

                    # Handle line range for cat command
                    if cmd.startswith('cat') and start_line:
                        start_idx = max(0, start_line - 1)
                        end_idx = min(total_lines, end_line or (start_idx + max_lines))
                        selected_lines = lines[start_idx:end_idx]
                    else:
                        selected_lines = lines[:max_lines]

                    return {
                        "content": '\n'.join(selected_lines),
                        "lines": len(selected_lines),
                        "total_lines": total_lines,
                        "file_path": str(target_file.relative_to(self.repo_path)),
                        "truncated": len(selected_lines) < total_lines,
                        "method": "terminal_fallback",
                        "command_used": cmd
                    }

            except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
                # Try next command if this one fails
                continue

        return None

    def get_directory_tree(self, path: str = ".", max_depth: int = 3,
                          show_files: bool = True, exclude_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get directory tree structure using tree command (efficient for large repos)

        Args:
            path: Directory path relative to repo
            max_depth: Maximum depth to traverse
            show_files: Whether to show files or just directories
            exclude_patterns: Patterns to exclude (e.g., ['node_modules', '.git'])

        Returns:
            Dictionary with tree structure and metadata
        """
        import subprocess

        try:
            target_path = self.repo_path / path
            if not target_path.exists():
                return {"error": f"Path not found: {path}"}

            if not target_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            # Build tree command
            cmd_parts = ["tree"]
            cmd_parts.extend(["-L", str(max_depth)])

            if not show_files:
                cmd_parts.append("-d")  # directories only

            if exclude_patterns:
                # tree command supports -I for exclude patterns
                exclude_str = "|".join(exclude_patterns)
                cmd_parts.extend(["-I", exclude_str])

            cmd_parts.append(str(target_path))

            # Execute tree command
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.repo_path
            )

            if result.returncode == 0:
                tree_output = result.stdout
                error_output = result.stderr

                # Parse tree output to extract structure
                structure = self._parse_tree_output(tree_output, str(target_path))

                return {
                    "tree_output": tree_output,
                    "structure": structure,
                    "command_used": " ".join(cmd_parts),
                    "max_depth": max_depth,
                    "show_files": show_files,
                    "exclude_patterns": exclude_patterns or [],
                    "error_output": error_output.strip() if error_output.strip() else None
                }
            else:
                # Fallback to recursive listing if tree fails
                return self._recursive_tree_fallback(target_path, max_depth, show_files, exclude_patterns)

        except subprocess.TimeoutExpired:
            return {"error": "Tree command timed out"}
        except Exception as e:
            return {"error": f"Tree command failed: {str(e)}"}

    def _parse_tree_output(self, tree_output: str, root_path: str) -> Dict[str, Any]:
        """Parse tree command output into structured format"""
        lines = tree_output.strip().split('\n')
        structure = {
            "root": root_path,
            "directories": [],
            "files": [],
            "total_dirs": 0,
            "total_files": 0
        }

        for line in lines:
            if not line.strip() or line.startswith('└') or line.startswith('├'):
                continue

            # Count directories and files from summary line
            if line.startswith('directories,'):
                parts = line.split()
                try:
                    structure["total_dirs"] = int(parts[0])
                    structure["total_files"] = int(parts[2])
                except (ValueError, IndexError):
                    pass

        return structure

    def _recursive_tree_fallback(self, target_path: Path, max_depth: int,
                                show_files: bool, exclude_patterns: Optional[List[str]]) -> Dict[str, Any]:
        """Fallback tree implementation using recursive directory listing"""
        def should_exclude(name: str) -> bool:
            if not exclude_patterns:
                return False
            return any(fnmatch.fnmatch(name, pattern) for pattern in exclude_patterns)

        def build_tree(current_path: Path, current_depth: int) -> Dict[str, Any]:
            if current_depth > max_depth:
                return {"name": current_path.name, "type": "directory", "truncated": True}

            try:
                items = []
                if current_path.is_dir():
                    for item in sorted(current_path.iterdir()):
                        if should_exclude(item.name):
                            continue

                        if item.is_dir():
                            subtree = build_tree(item, current_depth + 1)
                            items.append(subtree)
                        elif show_files and item.is_file():
                            items.append({
                                "name": item.name,
                                "type": "file",
                                "size": item.stat().st_size
                            })

                return {
                    "name": current_path.name,
                    "type": "directory",
                    "items": items,
                    "path": str(current_path.relative_to(self.repo_path))
                }
            except PermissionError:
                return {"name": current_path.name, "type": "directory", "error": "permission_denied"}

        tree_structure = build_tree(target_path, 0)

        return {
            "tree_output": "Generated by fallback method (tree command not available)",
            "structure": tree_structure,
            "command_used": "recursive_fallback",
            "method": "fallback"
        }

    def _analyze_file_type(self, file_path: Path) -> Dict[str, Any]:
        """Analyze file type to determine if it's binary or text"""
        extension = file_path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        # Quick check based on extension
        if extension in self.binary_extensions:
            return {
                "is_binary": True,
                "reason": "known_binary_extension",
                "extension": extension,
                "mime_type": mime_type
            }
        
        if extension in self.text_extensions:
            return {
                "is_binary": False,
                "reason": "known_text_extension",
                "extension": extension,
                "mime_type": mime_type
            }
        
        # Check mime type
        if mime_type:
            if mime_type.startswith(('text/', 'application/json', 'application/xml')):
                return {
                    "is_binary": False,
                    "reason": "text_mime_type",
                    "extension": extension,
                    "mime_type": mime_type
                }
            elif mime_type.startswith(('image/', 'video/', 'audio/', 'application/octet-stream')):
                return {
                    "is_binary": True,
                    "reason": "binary_mime_type",
                    "extension": extension,
                    "mime_type": mime_type
                }
        
        # Sample file content to check for binary data
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(1024)  # Read first 1KB
            
            # Check for null bytes (common in binary files)
            if b'\x00' in sample:
                return {
                    "is_binary": True,
                    "reason": "null_bytes_detected",
                    "extension": extension,
                    "mime_type": mime_type
                }
            
            # Check for high ratio of non-printable characters
            printable_chars = sum(1 for byte in sample if 32 <= byte <= 126 or byte in [9, 10, 13])
            if len(sample) > 0 and printable_chars / len(sample) < 0.7:
                return {
                    "is_binary": True,
                    "reason": "high_non_printable_ratio",
                    "extension": extension,
                    "mime_type": mime_type,
                    "printable_ratio": printable_chars / len(sample)
                }
            
        except Exception:
            pass
        
        # Default to text if uncertain
        return {
            "is_binary": False,
            "reason": "default_assumption",
            "extension": extension,
            "mime_type": mime_type
        }
    
    def _detect_encoding(self, file_path: Path, force_encoding: Optional[str] = None) -> Dict[str, Any]:
        """Detect file encoding"""
        if force_encoding:
            return {
                "success": True,
                "encoding": force_encoding,
                "method": "forced",
                "confidence": 1.0
            }
        
        try:
            # Try UTF-8 first (most common)
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            try:
                raw_data.decode('utf-8')
                return {
                    "success": True,
                    "encoding": "utf-8",
                    "method": "utf8_test",
                    "confidence": 1.0
                }
            except UnicodeDecodeError:
                pass
            
            # Use chardet for encoding detection
            detection = chardet.detect(raw_data)
            
            if detection['encoding'] and detection['confidence'] > 0.7:
                return {
                    "success": True,
                    "encoding": detection['encoding'],
                    "method": "chardet",
                    "confidence": detection['confidence']
                }
            
            # Try common encodings as fallback
            common_encodings = ['latin-1', 'cp1252', 'iso-8859-1']
            for encoding in common_encodings:
                try:
                    raw_data.decode(encoding)
                    return {
                        "success": True,
                        "encoding": encoding,
                        "method": "fallback_test",
                        "confidence": 0.5
                    }
                except UnicodeDecodeError:
                    continue
            
            return {
                "success": False,
                "error": "Could not detect file encoding",
                "detection_result": detection
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error detecting encoding: {str(e)}"
            }
    
    def _format_size(self, size: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive file information without reading content"""
        try:
            target_file = self.repo_path / file_path
            
            if not target_file.exists():
                return {
                    "error": "File not found",
                    "file_path": file_path
                }
            
            stat_info = target_file.stat()
            file_type_info = self._analyze_file_type(target_file)
            
            info = {
                "file_path": file_path,
                "size": stat_info.st_size,
                "size_str": self._format_size(stat_info.st_size),
                "modified_time": stat_info.st_mtime,
                "is_readable": not file_type_info["is_binary"],
                "file_type": file_type_info
            }
            
            if not file_type_info["is_binary"] and stat_info.st_size <= self.max_file_size:
                encoding_info = self._detect_encoding(target_file)
                info["encoding"] = encoding_info
                
                # Get line count for text files
                try:
                    if encoding_info["success"]:
                        with open(target_file, 'r', encoding=encoding_info["encoding"]) as f:
                            line_count = sum(1 for _ in f)
                        info["line_count"] = line_count
                except Exception:
                    pass
            
            return info
            
        except Exception as e:
            return {
                "error": str(e),
                "file_path": file_path
            }

    def list_directory(self, path: str = ".", max_items: int = 50, include_structure: bool = False) -> Dict[str, Any]:
        """
        List directory contents (compatibility method for existing code)

        Args:
            path: Directory path relative to repo_path
            max_items: Maximum number of items to return
            include_structure: Whether to include tree structure

        Returns:
            Dictionary with directory listing information
        """
        try:
            target_path = self.repo_path / path if path != "." else self.repo_path

            if not target_path.exists():
                return {"error": f"Directory not found: {path}"}

            if not target_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            items = []
            files = []
            directories = []

            for item in sorted(target_path.iterdir()):
                # Allow all files and directories, let LLM decide what's important
                item_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item.relative_to(self.repo_path))
                }

                if item.is_file():
                    item_info["size"] = item.stat().st_size
                    item_info["extension"] = item.suffix
                    files.append(item.name)
                else:
                    directories.append(item.name)

                items.append(item_info)

                if len(items) >= max_items:
                    break

            result = {
                "path": path,
                "items": items,
                "total": len(items),
                "files": files,
                "directories": directories
            }

            return result

        except Exception as e:
            return {"error": str(e), "path": path}

    def grep_search(self, pattern: str, path: str = ".", include_pattern: str = "*",
                    exclude_pattern: str = "", recursive: bool = True,
                    case_insensitive: bool = False, max_results: int = 100) -> Dict[str, Any]:
        """
        Search for pattern in files using grep-like functionality

        Args:
            pattern: Search pattern (supports regex)
            path: Starting directory path relative to repo_path
            include_pattern: Glob pattern for files to include (e.g., "*.py", "*.js")
            exclude_pattern: Glob pattern for files to exclude
            recursive: Whether to search recursively
            case_insensitive: Case insensitive search
            max_results: Maximum number of results to return

        Returns:
            Dictionary with search results
        """
        try:
            target_path = self.repo_path / path if path != "." else self.repo_path

            if not target_path.exists():
                return {"error": f"Path not found: {path}"}

            results = []
            files_searched = 0
            total_matches = 0

            # Compile regex pattern
            flags = re.IGNORECASE if case_insensitive else 0
            try:
                regex_pattern = re.compile(pattern, flags)
            except re.error as e:
                return {"error": f"Invalid regex pattern: {str(e)}"}

            # Get files to search
            search_files = self._get_search_files(target_path, include_pattern,
                                                exclude_pattern, recursive)

            for file_path in search_files:
                if files_searched >= max_results:
                    break

                file_matches = self._search_in_file(file_path, regex_pattern, max_results - files_searched)
                if file_matches:
                    results.extend(file_matches)
                    total_matches += len(file_matches)
                    files_searched += 1

                    if total_matches >= max_results:
                        break

            return {
                "pattern": pattern,
                "results": results[:max_results],
                "total_matches": len(results),
                "files_searched": files_searched,
                "truncated": len(results) >= max_results,
                "search_path": path,
                "include_pattern": include_pattern,
                "exclude_pattern": exclude_pattern
            }

        except Exception as e:
            return {"error": str(e), "pattern": pattern}

    def _get_search_files(self, start_path: Path, include_pattern: str,
                         exclude_pattern: str, recursive: bool) -> List[Path]:
        """Get list of files to search based on patterns"""
        search_files = []

        if recursive:
            for root, dirs, files in os.walk(start_path):
                # Allow all directories and files, let LLM decide what's important
                root_path = Path(root)
                for file in files:

                    file_path = root_path / file
                    relative_path = file_path.relative_to(self.repo_path)

                    # Check include pattern
                    if not fnmatch.fnmatch(str(relative_path), include_pattern):
                        continue

                    # Check exclude pattern
                    if exclude_pattern and fnmatch.fnmatch(str(relative_path), exclude_pattern):
                        continue

                    # Check if file is text/readable
                    file_type_info = self._analyze_file_type(file_path)
                    if not file_type_info["is_binary"]:
                        search_files.append(file_path)
        else:
            for item in start_path.iterdir():
                if item.is_file():  # Allow all files, let LLM decide
                    relative_path = item.relative_to(self.repo_path)

                    # Check include pattern
                    if not fnmatch.fnmatch(str(relative_path), include_pattern):
                        continue

                    # Check exclude pattern
                    if exclude_pattern and fnmatch.fnmatch(str(relative_path), exclude_pattern):
                        continue

                    # Check if file is text/readable
                    file_type_info = self._analyze_file_type(item)
                    if not file_type_info["is_binary"]:
                        search_files.append(item)

        return search_files

    def _search_in_file(self, file_path: Path, pattern: Pattern,
                       max_results: int) -> List[Dict[str, Any]]:
        """Search for pattern in a single file"""
        matches = []

        try:
            # Detect encoding
            encoding_info = self._detect_encoding(file_path)
            if not encoding_info["success"]:
                return []

            with open(file_path, 'r', encoding=encoding_info["encoding"]) as f:
                lines = f.readlines()

            relative_path = file_path.relative_to(self.repo_path)

            for line_num, line in enumerate(lines, 1):
                if len(matches) >= max_results:
                    break

                # Search for pattern in line
                for match in pattern.finditer(line):
                    matches.append({
                        "file": str(relative_path),
                        "line_number": line_num,
                        "line_content": line.rstrip(),
                        "match_start": match.start(),
                        "match_end": match.end(),
                        "matched_text": match.group(),
                        "context": self._get_context(lines, line_num - 1, 2)  # 2 lines context
                    })

        except Exception as e:
            # If we can't read the file, skip it
            pass

        return matches

    def _get_context(self, lines: List[str], line_idx: int, context_lines: int) -> str:
        """Get context lines around a match"""
        start = max(0, line_idx - context_lines)
        end = min(len(lines), line_idx + context_lines + 1)
        context = []

        for i in range(start, end):
            marker = ">>> " if i == line_idx else "    "
            context.append(f"{marker}{i + 1:4d}: {lines[i].rstrip()}")

        return "\n".join(context)

    def list_directory_recursive(self, path: str = ".", max_depth: int = 3,
                               include_files: bool = True, include_dirs: bool = True,
                               file_filter: str = "*", dir_filter: str = "*",
                               include_hidden: bool = False) -> Dict[str, Any]:
        """
        Recursively list directory contents with tree structure

        Args:
            path: Directory path relative to repo_path
            max_depth: Maximum depth to traverse
            include_files: Whether to include files in listing
            include_dirs: Whether to include directories in listing
            file_filter: Glob pattern to filter files
            dir_filter: Glob pattern to filter directories
            include_hidden: Whether to include hidden files/directories

        Returns:
            Dictionary with recursive directory structure
        """
        try:
            target_path = self.repo_path / path if path != "." else self.repo_path

            if not target_path.exists():
                return {"error": f"Directory not found: {path}"}

            if not target_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            def build_tree(current_path: Path, current_depth: int = 0) -> Dict[str, Any]:
                if current_depth > max_depth:
                    return {"type": "directory", "truncated": True}

                items = []
                total_files = 0
                total_dirs = 0

                try:
                    for item in sorted(current_path.iterdir()):
                        # Allow hidden files based on include_hidden parameter
                        if not include_hidden and item.name.startswith('.'):
                            continue

                        relative_path = str(item.relative_to(self.repo_path))

                        if item.is_dir():
                            if include_dirs and fnmatch.fnmatch(item.name, dir_filter):
                                subtree = build_tree(item, current_depth + 1)
                                items.append({
                                    "name": item.name,
                                    "type": "directory",
                                    "path": relative_path,
                                    "contents": subtree.get("items", []),
                                    "total_files": subtree.get("total_files", 0),
                                    "total_dirs": subtree.get("total_dirs", 0)
                                })
                                total_dirs += 1 + subtree.get("total_dirs", 0)
                                total_files += subtree.get("total_files", 0)
                        elif item.is_file() and include_files:
                            if fnmatch.fnmatch(item.name, file_filter):
                                file_info = {
                                    "name": item.name,
                                    "type": "file",
                                    "path": relative_path,
                                    "size": item.stat().st_size,
                                    "extension": item.suffix
                                }

                                # Add file type info
                                file_type_info = self._analyze_file_type(item)
                                file_info["is_binary"] = file_type_info["is_binary"]
                                file_info["mime_type"] = file_type_info.get("mime_type")

                                items.append(file_info)
                                total_files += 1

                except PermissionError:
                    return {"type": "directory", "error": "Permission denied"}

                return {
                    "type": "directory",
                    "items": items,
                    "total_files": total_files,
                    "total_dirs": total_dirs,
                    "depth": current_depth
                }

            tree = build_tree(target_path)

            return {
                "path": path,
                "absolute_path": str(target_path),
                "structure": tree,
                "max_depth": max_depth,
                "total_files": tree.get("total_files", 0),
                "total_dirs": tree.get("total_dirs", 0)
            }

        except Exception as e:
            return {"error": str(e), "path": path}

    def find_files(self, name_pattern: str = "*", path: str = ".",
                  recursive: bool = True, file_type: str = "all") -> Dict[str, Any]:
        """
        Find files by name pattern and type

        Args:
            name_pattern: Glob pattern for file names (e.g., "*.py", "test_*")
            path: Starting directory path
            recursive: Whether to search recursively
            file_type: Filter by file type ("all", "text", "binary")

        Returns:
            Dictionary with found files
        """
        try:
            target_path = self.repo_path / path if path != "." else self.repo_path

            if not target_path.exists():
                return {"error": f"Path not found: {path}"}

            found_files = []

            def search_directory(current_path: Path):
                try:
                    for item in current_path.iterdir():
                        # Allow hidden files if explicitly searched for
                        if item.name.startswith('.') and not name_pattern.startswith('.'):
                            continue

                        if item.is_file():
                            # Check name pattern
                            if fnmatch.fnmatch(item.name, name_pattern):
                                file_type_info = self._analyze_file_type(item)

                                # Check file type filter
                                if file_type == "text" and file_type_info["is_binary"]:
                                    continue
                                elif file_type == "binary" and not file_type_info["is_binary"]:
                                    continue

                                found_files.append({
                                    "name": item.name,
                                    "path": str(item.relative_to(self.repo_path)),
                                    "size": item.stat().st_size,
                                    "extension": item.suffix,
                                    "is_binary": file_type_info["is_binary"],
                                    "mime_type": file_type_info.get("mime_type")
                                })

                        elif item.is_dir() and recursive:
                            search_directory(item)

                except PermissionError:
                    pass

            search_directory(target_path)

            return {
                "pattern": name_pattern,
                "search_path": path,
                "files": found_files,
                "total_found": len(found_files),
                "recursive": recursive,
                "file_type_filter": file_type
            }

        except Exception as e:
            return {"error": str(e), "pattern": name_pattern}

    def read_multiple_files(self, file_paths: List[str],
                          max_lines_per_file: int = 50) -> Dict[str, Any]:
        """
        Read multiple files efficiently

        Args:
            file_paths: List of file paths to read
            max_lines_per_file: Maximum lines to read per file

        Returns:
            Dictionary with results for each file
        """
        results = {}
        successful_reads = 0
        failed_reads = 0

        for file_path in file_paths:
            result = self.read_file(file_path, max_lines=max_lines_per_file)
            results[file_path] = result

            if "error" in result:
                failed_reads += 1
            else:
                successful_reads += 1

        return {
            "results": results,
            "successful_reads": successful_reads,
            "failed_reads": failed_reads,
            "total_requested": len(file_paths)
        }