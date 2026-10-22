"""
LLM helper for code snippet analysis only - agents handle their own decisions
"""

import os
from typing import Dict, Any
from litellm import completion


class LLMHelper:
    """LLM helper for code snippet analysis only - agents make their own task decisions"""
    
    def __init__(self):
        self._setup_api_key()
    
    def _setup_api_key(self):
        """Setup OpenAI API key from environment or config"""
        if not os.environ.get("OPENAI_API_KEY"):
            try:
                from ...config import settings
                api_key = settings.get_openai_api_key()
                os.environ["OPENAI_API_KEY"] = api_key
            except Exception:
                pass
    
    def analyze_code_snippet(self, code: str, file_path: str, max_retries: int = 2) -> Dict[str, Any]:
        """Analyze code snippet for insights - used only for supplemental analysis"""

        if not code or not code.strip():
            return {"error": "Empty code snippet", "file": file_path}

        # Truncate very long code snippets to avoid token limits
        truncated_code = code[:1500] if len(code) > 1500 else code

        prompt = f"""Analyze this code snippet from {file_path}:

```
{truncated_code}
```

Provide a structured security analysis in the following format:
File Purpose: [One sentence describing what this file does]
Security Issue Location: [One sentence identifying where the security issue is located, such as a specific line of code or function name]
Issue Description:
[First sentence explaining the security problem]
[Second sentence elaborating on the severity and impact of the issue]
Security Risk Level: [HIGH/MEDIUM/LOW]
Recommended Fix: [Brief description of how to address the issue]

If there are no significant security issues, respond with:
File Purpose: [One sentence describing what this file does]
Security Assessment: No significant security vulnerabilities identified in this code.

Instructions for Analysis:

Focus on actual security vulnerabilities, not general code quality issues
Consider common security risks: injection attacks, authentication bypass, data exposure, privilege escalation, etc.
Prioritize issues that could lead to real security compromises
Be specific about the location and nature of any identified issues

Keep the entire response under 300 words and be specific about any security concerns found."""

        for attempt in range(max_retries + 1):
            try:
                from ...config import settings
                response = completion(
                    model=settings.LLM_HELPER_MODEL,  # Use configured model for snippet analysis
                    messages=[
                        {"role": "system", "content": "You are a code analysis assistant. Provide concise, accurate analysis."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,  # Slightly higher for more varied analysis
                    max_tokens=250,  # Reasonable limit for brief analysis
                    timeout=30  # 30 second timeout
                )

                content = response.choices[0].message.content

                if content and len(content.strip()) > 10:  # Ensure meaningful response
                    return {
                        "analysis": content.strip(),
                        "file": file_path,
                        "model_used": settings.LLM_HELPER_MODEL,
                        "attempt": attempt + 1,
                        "truncated": len(code) > 1500
                    }
                else:
                    if attempt < max_retries:
                        continue  # Try again for empty responses

            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries:
                    continue  # Try again for errors
                else:
                    return {
                        "error": f"LLM analysis failed after {max_retries + 1} attempts: {error_msg}",
                        "file": file_path,
                        "last_attempt_error": error_msg
                    }

        return {"error": "LLM analysis returned empty response", "file": file_path}