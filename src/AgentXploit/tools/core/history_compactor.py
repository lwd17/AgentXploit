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
History context auto-compactor for managing long analysis contexts
"""

from typing import Dict, Any, List
from .llm_client import LLMClient


class HistoryCompactor:
    """Auto-compacts long history contexts while preserving key information"""
    
    def __init__(self, max_context_length: int = 4000):
        """
        Initialize compactor with max context length
        
        Args:
            max_context_length: Maximum length of context before compaction
        """
        self.max_context_length = max_context_length
        
    def compact_if_needed(self, history_context: str) -> str:
        """
        Compact history context if it exceeds max length
        
        Args:
            history_context: Full history context string
            
        Returns:
            Compacted context if needed, otherwise original context
        """
        if len(history_context) <= self.max_context_length:
            return history_context
            
        print(f"  [COMPACT] History context too long ({len(history_context)} chars), compacting...")
        return self._perform_compaction(history_context)
        
    def _perform_compaction(self, history_context: str) -> str:
        """
        Use LLM to intelligently compact the history context
        
        Args:
            history_context: Full context to compact
            
        Returns:
            Compacted context preserving key information
        """
        compaction_prompt = f"""
You are tasked with compacting an analysis history context while preserving the most critical information.

ORIGINAL CONTEXT (too long):
{history_context}

Please create a COMPACT version that preserves:
1. Summary statistics (file counts, security findings)  
2. High-risk files and directories
3. Key architectural insights
4. Recent analysis patterns
5. Security vulnerabilities found

IMPORTANT: Keep the compacted version under 2000 characters while maintaining all critical information for autonomous decision making.

Return ONLY the compacted context, no explanations:
"""

        model = LLMClient.get_model()
        messages = [
            {"role": "system", "content": "You are an expert at summarizing analysis contexts while preserving critical information for security analysis."},
            {"role": "user", "content": compaction_prompt}
        ]
        
        compacted = LLMClient.call_llm(
            model=model,
            messages=messages,
            max_tokens=1000,
            temperature=0.1,
            timeout=30,
            max_retries=2
        )
        
        if compacted and len(compacted) > 0:
            print(f"  [SUCCESS] Context compacted from {len(history_context)} to {len(compacted)} chars")
            return compacted
        else:
            print(f"  [FALLBACK] LLM compaction failed, using simple truncation")
            return self._simple_truncation(history_context)
            
    def _simple_truncation(self, history_context: str) -> str:
        """
        Simple fallback truncation keeping the most important parts
        
        Args:
            history_context: Context to truncate
            
        Returns:
            Truncated context
        """
        lines = history_context.split('\n')
        
        # Keep header and summary statistics
        important_lines = []
        for line in lines[:20]:  # First 20 lines usually contain summary
            important_lines.append(line)
            
        # Add separator
        important_lines.append("\n[... context truncated for length ...]")
        
        # Keep last few lines which might contain current state
        important_lines.extend(lines[-10:])
        
        truncated = '\n'.join(important_lines)
        return truncated[:self.max_context_length]