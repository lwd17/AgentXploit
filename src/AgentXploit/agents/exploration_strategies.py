"""
Pure LLM-driven exploration strategies for Analysis Agent
All exploration decisions are made by LLM, no rule-based logic
"""

from typing import Dict, List, Any
from pathlib import Path


class ExplorationStrategies:
    """Helper class for LLM-driven exploration strategies in Analysis Agent"""
    
    def __init__(self, tools, context, context_manager, task_queue):
        self.tools = tools
        self.context = context
        self.context_manager = context_manager
        self.task_queue = task_queue
    
    def get_unexplored_areas(self) -> Dict[str, List[str]]:
        """Get raw unexplored directories for LLM decision making - no filtering"""
        explored_dirs = set(self.context.get_explored_directories())
        unexplored_root_dirs = []
        unexplored_subdirs = []
        
        try:
            # Get root directories - return ALL directories, let LLM decide
            root_list = self.tools.list_directory(".")
            if "error" not in root_list:
                root_dirs = root_list.get("directories", [])
                for dir_name in root_dirs:
                    if dir_name not in explored_dirs:
                        unexplored_root_dirs.append(dir_name)

            # Get unexplored subdirectories from analyzed directories
            for explored_dir in list(explored_dirs):
                try:
                    dir_result = self.tools.list_directory(explored_dir)
                    if "error" not in dir_result:
                        subdirs = dir_result.get("directories", [])
                        for subdir in subdirs:
                            subdir_path = str(Path(explored_dir) / subdir).replace('\\', '/')
                            if not self.context.is_directory_explored(subdir_path):
                                unexplored_subdirs.append(subdir_path)
                except:
                    continue
                    
        except Exception as e:
            print(f"  Error gathering unexplored areas: {e}")
            
        # Return ALL unexplored areas - no artificial limits
        return {
            'root_dirs': unexplored_root_dirs,
            'subdirs': unexplored_subdirs
        }

    # REMOVED: force_exploration_tasks - this was rule-based
    # REMOVED: create_deep_exploration_tasks - this was rule-based  
    # REMOVED: smart_fallback_strategy - this was rule-based
    
    # All task creation is now handled by LLM through DecisionEngine