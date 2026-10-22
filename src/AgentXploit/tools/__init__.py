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

# Main analyzer - deferred import to avoid circular imports
def _get_analyzer():
    from ..agents.analysis_agent import AnalysisAgent
    return AnalysisAgent

# For backwards compatibility
class Analyzer:
    def __new__(cls, *args, **kwargs):
        AnalysisAgentClass = _get_analyzer()
        return AnalysisAgentClass(*args, **kwargs)

# Core components
from .core.core_tools import EnhancedFileReader
from .core.analysis_context import AnalysisContext
from .core.task import Task
from .core.task_queue import TaskQueue
from .core.execution_logger import ExecutionLogger
from .core.llm_client import LLMClient
from .core.history_compactor import HistoryCompactor

# Specialized components
from .analyzers.security_analyzer import SecurityAnalyzer
from .planning.analysis_context_manager import AnalysisContextManager
from .code_analysis.llm_decider import LLMHelper

# Injection-specific tools - import with error handling
try:
    from .injection_specific import (
        identify_injection_points,
        inject_malicious_prompt,
        process_log_file,
        scan_file,
        scan_directory,
        SWEReXTool
    )
except ImportError:
    identify_injection_points = None
    inject_malicious_prompt = None
    process_log_file = None
    scan_file = None
    scan_directory = None
    SWEReXTool = None

# Note: output and executors folders have been removed as redundant

# Main exports - always available
__all__ = [
    # Main analyzer
    'Analyzer',
    # Core components
    'EnhancedFileReader',
    'AnalysisContext',
    'Task',
    'TaskQueue',
    'ExecutionLogger',
    'LLMClient',
    'HistoryCompactor',
    # Specialized components
    'SecurityAnalyzer',
    'AnalysisContextManager',
    'LLMHelper',
]

# Add injection-specific tools that are available
_available_injection = []
if identify_injection_points is not None:
    _available_injection.append('identify_injection_points')
if inject_malicious_prompt is not None:
    _available_injection.append('inject_malicious_prompt')
if process_log_file is not None:
    _available_injection.append('process_log_file')
if scan_file is not None:
    _available_injection.extend(['scan_file', 'scan_directory'])
if SWEReXTool is not None:
    _available_injection.append('SWEReXTool')
# Removed references to deleted modules

__all__.extend(_available_injection)

# Backwards compatibility - provide smart_agent_analyze using new analyzer
def smart_agent_analyze(repo_path: str, max_steps: int = None, tool_context=None):
    """
    Backwards compatibility function for legacy smart_agent_analyze
    Now uses the new streamlined analyzer
    """
    # Get max_steps from settings if not provided
    if max_steps is None:
        try:
            from ..config import settings
            max_steps = getattr(settings, 'MAX_STEPS', 50)
        except:
            max_steps = 50

    AnalysisAgentClass = _get_analyzer()
    analyzer = AnalysisAgentClass(repo_path)
    return analyzer.analyze(max_steps=max_steps, save_results=True, focus=None)

# Add to exports
__all__.append('smart_agent_analyze') 