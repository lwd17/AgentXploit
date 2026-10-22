"""
Security analyzer using LLM for comprehensive security analysis.
Provides intelligent security assessment and vulnerability detection.
"""

from typing import Dict, Any, List
from dataclasses import dataclass
import os
import re

# Import LLMClient from core module
from ..core.llm_client import LLMClient


@dataclass
class SecurityFinding:
    """Represents a security finding with risk assessment"""
    finding_id: str
    finding_type: str  # "injection_risk", "authentication_issue", "data_exposure", "configuration_risk"
    severity: str  # "high", "medium", "low", "info"
    file_path: str
    line_number: int
    description: str
    details: Dict[str, Any]
    risk_score: int  # 0-100
    recommendation: str
    code_snippet: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert SecurityFinding to dictionary for JSON serialization"""
        from dataclasses import asdict
        return asdict(self)


class SecurityAnalyzer:
    """LLM-powered security analysis of code files"""
    
    def __init__(self):
        self.finding_counter = 0
        self._setup_llm()

    def _setup_llm(self):
        """Setup LLM for security analysis"""
        if not os.environ.get("OPENAI_API_KEY"):
            try:
                from ...config import settings
                api_key = settings.get_openai_api_key()
                os.environ["OPENAI_API_KEY"] = api_key
            except Exception:
                pass
    
    def analyze_file_security(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Perform LLM-powered comprehensive security analysis of a file.

        Args:
            file_path: Path to the file being analyzed
            content: File content to analyze

        Returns:
            Structured security analysis results
        """
        # Reset finding counter for this file
        self.finding_counter = 0

        # Perform LLM-based security analysis
        llm_analysis = self._analyze_with_llm(file_path, content)

        # Extract findings from LLM analysis - injection point focused only
        findings = self._extract_findings_from_llm(file_path, content, llm_analysis)

        # Calculate overall risk assessment
        risk_assessment = self._calculate_risk_assessment(findings)

        # IMPORTANT: Always extract tool and dataflow information regardless of security risk
        # Even LOW risk files may contain important tool implementations and dataflow patterns

        # Extract tool and dataflow information for ALL files (regardless of risk level)
        tool_analysis = llm_analysis.get("tool_analysis", {})
        agent_tools = self._extract_agent_tools_summary(tool_analysis)
        dataflow_analysis = self._extract_dataflow_summary(tool_analysis)
        
        # Log dataflow detection results for debugging
        if agent_tools or dataflow_analysis:
            print(f"  [DATAFLOW_DETECTED] {file_path}: {len(agent_tools)} tools, {len(dataflow_analysis)} flows")
        else:
            print(f"  [DATAFLOW_NONE] {file_path}: No tools or dataflow patterns detected")

        return {
            "file_path": file_path,
            "analysis_timestamp": self._get_timestamp(),
            "risk_assessment": risk_assessment,
            "agent_analysis": {
                "agent_tools": agent_tools,
                "dataflow_patterns": dataflow_analysis,
                "tool_summary": self._generate_tool_summary(agent_tools, dataflow_analysis)
            },
            "findings": findings,
            "llm_analysis": llm_analysis,
            "summary": self._generate_security_summary(findings, risk_assessment),
            "recommendations": self._generate_recommendations(findings)
        }
    
    def _analyze_with_llm(self, file_path: str, content: str) -> Dict[str, Any]:
        """Use LLM to perform comprehensive security analysis"""
        lines = content.split('\n')
        file_extension = file_path.split('.')[-1].lower() if '.' in file_path else 'unknown'

        # Let LLM analyze ALL files - no rule-based pre-filtering
        # Focused prompt specifically for dataflow detection
        prompt = f"""Analyze this file for AGENT TOOLS and DATA FLOWS:

File: {file_path}
Content:
{content[:1800]}{'...' if len(content) > 1800 else ''}

FIND THESE PATTERNS:

1. TOOLS - Any function that:
   - Reads/writes files
   - Makes API calls  
   - Executes commands
   - Processes user input
   - Calls LLM services
   - Transforms data

2. DATAFLOWS - How data moves:
   - Input -> Processing -> Output
   - External sources (files, APIs, users)
   - Data transformations
   - Output destinations

IMPORTANT: Look for ANY data processing, even in simple utility functions or configuration handlers.

Format response as JSON:
{{
    "overall_risk": "HIGH|MEDIUM|LOW",  
    "risk_score": 0-100,
    "tool_analysis": {{
        "identified_tools": [
            {{
                "tool_name": "function_name",
                "tool_type": "file_processor|api_client|command_executor|data_transformer|llm_interface",
                "description": "what it does"
            }}
        ],
        "dataflow_patterns": [
            {{
                "flow_id": "flow_1", 
                "description": "data flow description",
                "data_path": "input -> process -> output",
                "risk_level": "HIGH|MEDIUM|LOW"
            }}
        ]
    }},
    "injection_analysis": {{
        "potential_injection_points": [
            {{
                "location": "line_number_or_function_name",
                "injection_type": "prompt_injection|tool_parameter_injection|command_injection|data_poisoning",
                "severity": "HIGH|MEDIUM|LOW",
                "description": "specific vulnerability description", 
                "attack_scenario": "how attacker could exploit this",
                "affected_dataflow": "flow_id from above"
            }}
        ]
    }},
    "summary": "Brief summary of tool capabilities and dataflow risks"
}}"""

        # Use centralized LLM client with higher temperature for better detection
        result_text = LLMClient.call_llm(
            model=LLMClient.get_model(),
            messages=[
                {"role": "system", "content": "You are an expert security analyst specializing in agent tool implementations and dataflow analysis. ALWAYS return valid JSON with tool_analysis section, even if no patterns found. Be thorough in identifying ANY data processing patterns, tool functions, or external interactions, even in seemingly simple files."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.4,  # Increased for better pattern recognition
            timeout=35,
            max_retries=3
        )
        
        print(f"  [LLM_RESPONSE] Got response: {len(result_text) if result_text else 0} characters")

        if result_text and len(result_text.strip()) > 0:
            # Try to parse JSON response with enhanced error handling
            import json
            import re

            def try_parse_json(text_to_parse):
                """Try to parse JSON with validation"""
                try:
                    parsed = json.loads(text_to_parse)
                    # Validate required structure
                    if "tool_analysis" not in parsed:
                        print(f"  [WARNING] LLM response missing tool_analysis for {file_path}")
                        parsed["tool_analysis"] = {"identified_tools": [], "dataflow_patterns": []}

                    # Ensure required sub-structures exist
                    if "identified_tools" not in parsed["tool_analysis"]:
                        parsed["tool_analysis"]["identified_tools"] = []
                    if "dataflow_patterns" not in parsed["tool_analysis"]:
                        parsed["tool_analysis"]["dataflow_patterns"] = []

                    # Log successful dataflow/tool detection
                    tool_analysis = parsed.get("tool_analysis", {})
                    tools_count = len(tool_analysis.get("identified_tools", []))
                    flows_count = len(tool_analysis.get("dataflow_patterns", []))
                    if tools_count > 0 or flows_count > 0:
                        print(f"  [DATAFLOW_DETECTED] {file_path}: {tools_count} tools, {flows_count} flows")

                    return parsed
                except json.JSONDecodeError:
                    return None

            # Method 1: Try direct parsing
            parsed_result = try_parse_json(result_text.strip())
            if parsed_result:
                return parsed_result

            # Method 2: Try removing markdown code blocks
            markdown_pattern = r'```(?:json)?\s*(.*?)\s*```'
            markdown_match = re.search(markdown_pattern, result_text, re.DOTALL)
            if markdown_match:
                json_content = markdown_match.group(1).strip()
                parsed_result = try_parse_json(json_content)
                if parsed_result:
                    print(f"  [JSON_RECOVERY] Successfully extracted JSON from markdown for {file_path}")
                    return parsed_result

            # Method 3: Find JSON object boundaries
            start_idx = result_text.find('{')
            if start_idx != -1:
                # Try to find matching closing brace
                brace_count = 0
                end_idx = start_idx
                for i, char in enumerate(result_text[start_idx:], start_idx):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break

                if end_idx > start_idx:
                    json_str = result_text[start_idx:end_idx]
                    parsed_result = try_parse_json(json_str)
                    if parsed_result:
                        print(f"  [JSON_RECOVERY] Successfully extracted JSON from response for {file_path}")
                        return parsed_result

            # Method 4: Try array format
            array_start = result_text.find('[')
            array_end = result_text.rfind(']') + 1
            if array_start != -1 and array_end > array_start:
                try:
                    array_result = json.loads(result_text[array_start:array_end])
                    if isinstance(array_result, list) and len(array_result) > 0:
                        # Convert array to expected format
                        parsed_result = {
                            "tool_analysis": {"identified_tools": array_result, "dataflow_patterns": []},
                            "overall_risk": "MEDIUM",
                            "risk_score": 50
                        }
                        print(f"  [JSON_RECOVERY] Successfully parsed JSON array for {file_path}")
                        return parsed_result
                except:
                    pass

            # All parsing methods failed
            print(f"  [JSON_ERROR] All JSON parsing methods failed for {file_path}")
            print(f"  [JSON_ERROR] Response preview: {result_text[:300]}...")

            # If all parsing fails, return structured response with debug info
            return {
                "overall_risk": "MEDIUM",
                "risk_score": 50,
                "tool_analysis": {
                    "identified_tools": [],
                    "dataflow_patterns": []
                },
                "injection_analysis": {
                    "potential_injection_points": []
                },
                "summary": result_text[:500],
                "llm_raw_response": result_text,
                "parse_error": "JSON parsing failed after all recovery attempts"
            }
        else:
            return {
                "overall_risk": "UNKNOWN",
                "risk_score": 0,
                "tool_analysis": {
                    "identified_tools": [],
                    "dataflow_patterns": []
                },
                "injection_analysis": {
                    "potential_injection_points": []
                },
                "summary": "LLM analysis failed - no response received",
                "error": "LLM call failed"
            }

    def _extract_findings_from_llm(self, file_path: str, content: str, llm_analysis: Dict) -> List[SecurityFinding]:
        """Extract tool use and dataflow findings from LLM analysis"""
        findings = []
        
        # Handle new tool_analysis and injection_analysis format
        injection_analysis = llm_analysis.get("injection_analysis", {})
        injection_points = injection_analysis.get("potential_injection_points", [])
        
        # Also support legacy formats
        legacy_injection_points = llm_analysis.get("agent_injection_points", [])
        legacy_findings = llm_analysis.get("findings", [])
        
        all_findings = injection_points + legacy_injection_points + legacy_findings

        for finding_data in all_findings:
            # Use dataflow-focused classification
            finding_type = self._classify_dataflow_finding(finding_data, llm_analysis)

            # Extract severity and risk score
            severity = finding_data.get("severity", "MEDIUM").lower()
            risk_score = self._calculate_dataflow_risk_score(finding_data, severity, llm_analysis)

            # Extract location information
            location = finding_data.get("location", finding_data.get("line", 1))
            line_number = self._extract_line_number(location)

            finding = SecurityFinding(
                finding_id=self._next_finding_id(),
                finding_type=finding_type,
                severity=severity,
                file_path=file_path,
                line_number=line_number,
                description=finding_data.get("description", "Dataflow security issue detected"),
                details={
                    "llm_analysis": llm_analysis.get("summary", ""),
                    "detection_method": "tool_dataflow_analysis", 
                    "injection_type": finding_data.get("injection_type", "unknown"),
                    "attack_scenario": finding_data.get("attack_scenario", ""),
                    "affected_dataflow": finding_data.get("affected_dataflow", ""),
                    "tool_analysis": llm_analysis.get("tool_analysis", {}),
                    "dataflow_context": self._extract_dataflow_context(llm_analysis, finding_data),
                    "content_context": self._extract_content_context(content, line_number)
                },
                risk_score=risk_score,
                recommendation=finding_data.get("recommendation", "Review and mitigate dataflow vulnerability"),
                code_snippet=finding_data.get("code_snippet", "")
            )
            findings.append(finding)
        
        return findings

    def _classify_finding_with_llm(self, finding_data: Dict, content: str) -> str:
        """Use LLM to classify the finding type based on content context"""
        prompt = f"""Classify this security finding based on the code context:

Finding: {finding_data.get('description', '')}
Code snippet: {finding_data.get('code_snippet', '')}

Classify as one of: injection_risk, authentication_issue, data_exposure, configuration_risk, code_quality, other

Respond with just the classification:"""

        response_text = LLMClient.call_llm(
            model=LLMClient.get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1,
            timeout=15,
            max_retries=2
        )

        if response_text:
            classification = response_text.strip().lower()
            # Map to valid finding types including new agent injection types
            valid_types = [
                "data_flow_injection", "tool_output_injection", "context_injection", 
                "workflow_manipulation", "injection_risk", "authentication_issue", 
                "data_exposure", "configuration_risk", "code_quality"
            ]
            if classification in valid_types:
                return classification

        # Check for agent injection types in finding_data
        finding_type = finding_data.get("type", "")
        if finding_type in valid_types:
            return finding_type
            
        return "general_security_issue"

    def _assess_severity_with_llm(self, finding_data: Dict, content: str, file_path: str) -> str:
        """Use LLM to assess severity with full context"""
        prompt = f"""Assess the severity of this security finding considering:

File: {file_path}
Finding: {finding_data.get('description', '')}
Context: {content[:500]}...

Rate severity as: critical, high, medium, low, info

Consider:
- Potential impact on the system
- Ease of exploitation
- Data sensitivity
- System criticality

Respond with just the severity level:"""

        response_text = LLMClient.call_llm(
            model=LLMClient.get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.1,
            timeout=15,
            max_retries=2
        )

        if response_text:
            severity = response_text.strip().lower()
            # Normalize severity
            if severity in ["critical"]:
                return "high"
            elif severity in ["high", "medium", "low", "info"]:
                return severity

        return finding_data.get("severity", "medium")

    def _calculate_llm_driven_risk_score(self, finding_data: Dict, severity: str, content: str) -> int:
        """Use LLM to calculate risk score with context"""
        prompt = f"""Calculate a risk score (0-100) for this security finding:

Severity: {severity}
Description: {finding_data.get('description', '')}
Code context: {content[:300]}...

Consider:
- Technical complexity of exploitation
- Potential data exposure
- System impact
- Likelihood of occurrence
- Current mitigations in the code

Respond with just the numeric score:"""

        response_text = LLMClient.call_llm(
            model=LLMClient.get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1,
            timeout=15,
            max_retries=2
        )

        if response_text:
            # Extract numeric score
            import re
            numbers = re.findall(r'\d+', response_text)
            if numbers:
                score = int(numbers[0])
                return max(0, min(100, score))

        return self._calculate_risk_score_from_severity(severity)

    def _generate_llm_recommendation(self, finding_data: Dict, content: str) -> str:
        """Use LLM to generate specific recommendations"""
        prompt = f"""Generate a specific, actionable recommendation for this security finding:

Finding: {finding_data.get('description', '')}
Code context: {content[:300]}...

Provide a concrete, implementable solution.
Keep it brief but specific:"""

        response_text = LLMClient.call_llm(
            model=LLMClient.get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.2,
            timeout=15,
            max_retries=2
        )

        if response_text and len(response_text) > 10:
            return response_text

        return finding_data.get("recommendation", "Review and address this security concern")

    def _classify_dataflow_finding(self, finding_data: Dict, llm_analysis: Dict) -> str:
        """Classify finding type based on dataflow analysis"""
        injection_type = finding_data.get("injection_type", "").lower()
        
        # Map injection types to finding categories
        type_mapping = {
            "prompt_injection": "prompt_injection_risk",
            "tool_parameter_injection": "tool_parameter_injection",
            "command_injection": "command_execution_risk",
            "data_poisoning": "data_flow_injection"
        }
        
        return type_mapping.get(injection_type, "dataflow_security_issue")

    def _calculate_dataflow_risk_score(self, finding_data: Dict, severity: str, llm_analysis: Dict) -> int:
        """Calculate risk score based on dataflow analysis"""
        base_score = self._calculate_risk_score_from_severity(severity)
        
        # Adjust score based on dataflow factors
        injection_type = finding_data.get("injection_type", "").lower()
        if injection_type in ["prompt_injection", "command_injection"]:
            base_score += 20  # Higher risk for direct injection types
        
        # Check if external input is involved
        affected_flow = finding_data.get("affected_dataflow", "")
        tool_analysis = llm_analysis.get("tool_analysis", {})
        dataflows = tool_analysis.get("dataflow_patterns", [])
        
        for flow in dataflows:
            if flow.get("flow_id") == affected_flow:
                if flow.get("external_input") == "yes":
                    base_score += 15  # Higher risk for external input
                if flow.get("sanitization") == "no":
                    base_score += 10  # Higher risk for no sanitization
                break
        
        return max(0, min(100, base_score))

    def _extract_line_number(self, location) -> int:
        """Extract line number from location string"""
        if isinstance(location, int):
            return location
        elif isinstance(location, str):
            # Try to extract number from string
            import re
            numbers = re.findall(r'\d+', location)
            return int(numbers[0]) if numbers else 1
        return 1

    def _extract_dataflow_context(self, llm_analysis: Dict, finding_data: Dict) -> Dict:
        """Extract dataflow context for the finding"""
        tool_analysis = llm_analysis.get("tool_analysis", {})
        affected_flow = finding_data.get("affected_dataflow", "")
        
        context = {
            "tools_involved": [],
            "dataflow_details": {},
            "input_sources": [],
            "output_destinations": []
        }
        
        # Extract tool information
        for tool in tool_analysis.get("identified_tools", []):
            context["tools_involved"].append({
                "name": tool.get("tool_name", ""),
                "type": tool.get("tool_type", ""),
                "description": tool.get("description", "")
            })
            context["input_sources"].extend(tool.get("input_sources", []))
            context["output_destinations"].extend(tool.get("output_destinations", []))
        
        # Extract specific dataflow details
        for flow in tool_analysis.get("dataflow_patterns", []):
            if flow.get("flow_id") == affected_flow:
                context["dataflow_details"] = flow
                break
        
        return context

    def _extract_content_context(self, content: str, line_number: int) -> str:
        """Extract relevant content context around the finding"""
        lines = content.split('\n')
        start = max(0, line_number - 3)
        end = min(len(lines), line_number + 3)

        context_lines = []
        for i in range(start, end):
            marker = ">>> " if i + 1 == line_number else "    "
            context_lines.append(f"{marker}{i + 1:4d}: {lines[i]}")

        return "\n".join(context_lines)

    def _is_likely_low_risk(self, content: str, file_path: str) -> bool:
        """Determine if a file is likely to be LOW risk based on content analysis"""
        # Quick content analysis to determine if this is likely a low-risk file
        content_lower = content.lower()

        # Check for risky patterns
        risky_patterns = [
            'api[_-]?key', 'password', 'secret', 'token', 'auth',
            'eval', 'exec', 'system', 'subprocess', 'shell',
            'sql', 'query', 'database', 'inject',
            'config', 'settings', 'env', 'credential'
        ]

        risky_count = 0
        for pattern in risky_patterns:
            if re.search(pattern, content_lower):
                risky_count += 1

        # If file has very few risky patterns and is not a config file, likely low risk
        file_extension = file_path.split('.')[-1] if '.' in file_path else ''
        config_files = ['config', 'settings', 'env', 'toml', 'yaml', 'yml', 'json']

        if file_extension in config_files:
            return False  # Config files are potentially risky

        # Consider low risk if very few risky patterns found
        return risky_count <= 2




    def _calculate_risk_score_from_severity(self, severity: str) -> int:
        """Convert severity string to risk score"""
        severity_map = {
            "high": 80,
            "medium": 50,
            "low": 25,
            "info": 10
        }
        return severity_map.get(severity.lower(), 25)
    
    
    def _calculate_risk_assessment(self, findings: List[SecurityFinding]) -> Dict[str, Any]:
        """Calculate overall risk assessment for the file"""
        if not findings:
            return {
                "overall_risk": "LOW",
                "risk_score": 0,
                "critical_findings": 0,
                "high_findings": 0,
                "medium_findings": 0,
                "low_findings": 0
            }

        # Count findings by severity
        high_findings = sum(1 for f in findings if f.severity == "high")
        medium_findings = sum(1 for f in findings if f.severity == "medium")
        low_findings = sum(1 for f in findings if f.severity == "low")

        # Calculate overall risk with adjusted thresholds for cleaner output
        total_risk_score = sum(f.risk_score for f in findings) // len(findings) if findings else 0

        if high_findings > 0:
            overall_risk = "HIGH"
        elif medium_findings > 0:
            overall_risk = "MEDIUM"
        else:
            overall_risk = "LOW"  # Only low severity findings = LOW risk

        return {
            "overall_risk": overall_risk,
            "risk_score": total_risk_score if overall_risk != "LOW" else 0,  # Don't show score for LOW risk
            "critical_findings": 0,  # Reserved for future use
            "high_findings": high_findings,
            "medium_findings": medium_findings,
            "low_findings": low_findings,
            "total_findings": len(findings)
        }
    
    def _generate_security_summary(
        self,
        findings: List[SecurityFinding],
        risk_assessment: Dict[str, Any]
    ) -> str:
        """Generate a human-readable security summary"""
        risk_level = risk_assessment.get("overall_risk", "LOW")

        # For LOW risk files, provide minimal summary
        if risk_level == "LOW":
            total_findings = risk_assessment.get("total_findings", 0)
            if total_findings == 0:
                return "Security Risk: LOW - No security issues found"
            else:
                return f"Security Risk: LOW - {total_findings} minor finding(s), no immediate action required"

        # For MEDIUM and HIGH risk files, provide detailed summary
        risk_score = risk_assessment.get("risk_score", 0)
        summary = f"Security Risk: {risk_level} (Score: {risk_score}/100)"

        high_findings = risk_assessment.get("high_findings", 0)
        if high_findings > 0:
            summary += f"\n- {high_findings} high-risk finding(s)"

        medium_findings = risk_assessment.get("medium_findings", 0)
        if medium_findings > 0:
            summary += f"\n- {medium_findings} medium-risk finding(s)"

        # Highlight specific critical issues
        injection_findings = [f for f in findings if "injection" in f.finding_type.lower()]
        if injection_findings:
            summary += f"\n- WARNING: {len(injection_findings)} potential injection vulnerability(ies)"

        return summary
    
    def _generate_recommendations(self, findings: List[SecurityFinding]) -> List[str]:
        """Generate security recommendations based on findings"""
        recommendations = set()
        
        for finding in findings:
            if finding.severity in ["high", "medium"]:
                recommendations.add(finding.recommendation)
        
        # Add general recommendations based on injection finding types
        finding_types = {f.finding_type for f in findings}
        
        if "data_flow_injection" in finding_types:
            recommendations.add("Sanitize data before passing between tools and LLM")
        
        if "tool_output_injection" in finding_types:
            recommendations.add("Validate and sanitize tool outputs before LLM processing")
        
        if "context_injection" in finding_types:
            recommendations.add("Implement strict context validation and sanitization")
        
        if "workflow_manipulation" in finding_types:
            recommendations.add("Add integrity checks to agent workflow processes")
        
        return sorted(list(recommendations))

    def _extract_agent_tools_summary(self, tool_analysis: Dict) -> List[Dict]:
        """Extract agent tools summary from tool analysis"""
        tools_summary = []
        identified_tools = tool_analysis.get("identified_tools", [])
        
        for tool in identified_tools:
            tool_summary = {
                "tool_name": tool.get("tool_name", "unknown"),
                "tool_type": tool.get("tool_type", "unknown"),
                "description": tool.get("description", ""),
                "input_sources": tool.get("input_sources", []),
                "output_destinations": tool.get("output_destinations", []),
                "security_implications": self._assess_tool_security_implications(tool)
            }
            tools_summary.append(tool_summary)
        
        return tools_summary

    def _extract_dataflow_summary(self, tool_analysis: Dict) -> List[Dict]:
        """Extract dataflow patterns summary from tool analysis"""
        dataflow_summary = []
        dataflow_patterns = tool_analysis.get("dataflow_patterns", [])
        
        for flow in dataflow_patterns:
            flow_summary = {
                "flow_id": flow.get("flow_id", "unknown"),
                "description": flow.get("description", ""),
                "data_path": flow.get("data_path", "unknown"),
                "external_input": flow.get("external_input", "unknown"),
                "sanitization": flow.get("sanitization", "unknown"),
                "risk_level": flow.get("risk_level", "UNKNOWN"),
                "injection_potential": self._assess_injection_potential(flow)
            }
            dataflow_summary.append(flow_summary)
        
        return dataflow_summary

    def _generate_tool_summary(self, agent_tools: List[Dict], dataflow_patterns: List[Dict]) -> str:
        """Generate human-readable summary of agent tools and dataflow"""
        if not agent_tools and not dataflow_patterns:
            return "No obvious agent tool usage or dataflow patterns found in this file"
        
        summary_parts = []
        
        # Tool summary
        if agent_tools:
            tool_types = {}
            for tool in agent_tools:
                tool_type = tool.get("tool_type", "unknown")
                tool_types[tool_type] = tool_types.get(tool_type, 0) + 1
            
            tool_desc = ", ".join([f"{count} {type_name}" for type_name, count in tool_types.items()])
            summary_parts.append(f"Agent tool types found: {tool_desc}")
        
        # Dataflow summary
        if dataflow_patterns:
            high_risk_flows = [f for f in dataflow_patterns if f.get("risk_level") == "HIGH"]
            external_flows = [f for f in dataflow_patterns if f.get("external_input") == "yes"]
            
            if high_risk_flows:
                summary_parts.append(f"Found {len(high_risk_flows)} high-risk dataflows")
            if external_flows:
                summary_parts.append(f"Found {len(external_flows)} dataflows with external input")
            
            # Example dataflow description
            if dataflow_patterns:
                example_flow = dataflow_patterns[0]
                summary_parts.append(f"Main dataflow example: {example_flow.get('data_path', 'unknown')}")
        
        return "; ".join(summary_parts)

    def _assess_tool_security_implications(self, tool: Dict) -> str:
        """Assess security implications of a tool"""
        tool_type = tool.get("tool_type", "").lower()
        
        if "command" in tool_type or "executor" in tool_type:
            return "HIGH - Command execution tool, injection risk exists"
        elif "llm" in tool_type or "interface" in tool_type:
            return "MEDIUM - LLM interface, prompt injection risk exists"
        elif "file" in tool_type or "processor" in tool_type:
            return "MEDIUM - File processing tool, data injection risk exists"
        elif "api" in tool_type or "client" in tool_type:
            return "LOW - API client, relatively low risk"
        else:
            return "UNKNOWN - Unknown tool type, requires further analysis"

    def _assess_injection_potential(self, flow: Dict) -> str:
        """Assess injection potential of a dataflow"""
        external_input = flow.get("external_input", "").lower()
        sanitization = flow.get("sanitization", "").lower()
        risk_level = flow.get("risk_level", "").upper()
        
        if external_input == "yes" and sanitization == "no":
            return "HIGH - External input enters processing flow without validation"
        elif external_input == "yes" and sanitization == "partial":
            return "MEDIUM - External input partially validated, risks still exist"
        elif external_input == "yes" and sanitization == "yes":
            return "LOW - External input fully validated"
        elif risk_level == "HIGH":
            return "HIGH - Dataflow itself marked as high risk"
        else:
            return "LOW - Dataflow has relatively low risk"
    
    
    def _next_finding_id(self) -> str:
        """Generate next finding ID"""
        self.finding_counter += 1
        return f"SEC-{self.finding_counter:03d}"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        import datetime
        return datetime.datetime.now().isoformat()

    def _get_llm_helper(self):
        """Get LLM helper instance for code analysis"""
        from ..code_analysis.llm_decider import LLMHelper
        return LLMHelper()
    
    def batch_analyze_files(self, files: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze multiple files and provide aggregate results.
        
        Args:
            files: Dictionary mapping file paths to file contents
            
        Returns:
            Aggregate security analysis results
        """
        results = {}
        all_findings = []
        
        for file_path, content in files.items():
            file_result = self.analyze_file_security(file_path, content)
            results[file_path] = file_result
            all_findings.extend(file_result["findings"])
        
        # Generate aggregate statistics
        aggregate_stats = self._calculate_aggregate_stats(all_findings, results)
        
        return {
            "files_analyzed": len(files),
            "individual_results": results,
            "aggregate_findings": all_findings,
            "aggregate_stats": aggregate_stats,
            "summary": self._generate_aggregate_summary(aggregate_stats)
        }
    
    def _calculate_aggregate_stats(self, all_findings: List[SecurityFinding], results: Dict) -> Dict[str, Any]:
        """Calculate aggregate statistics across all analyzed files"""
        high_risk_files = sum(1 for r in results.values() if r["risk_assessment"]["overall_risk"] == "HIGH")
        medium_risk_files = sum(1 for r in results.values() if r["risk_assessment"]["overall_risk"] == "MEDIUM")
        low_risk_files = sum(1 for r in results.values() if r["risk_assessment"]["overall_risk"] == "LOW")
        
        return {
            "total_findings": len(all_findings),
            "high_risk_files": high_risk_files,
            "medium_risk_files": medium_risk_files,
            "low_risk_files": low_risk_files,
            "findings_by_severity": {
                "high": sum(1 for f in all_findings if f.severity == "high"),
                "medium": sum(1 for f in all_findings if f.severity == "medium"),
                "low": sum(1 for f in all_findings if f.severity == "low")
            }
        }
    
    def _generate_aggregate_summary(self, stats: Dict[str, Any]) -> str:
        """Generate summary for multiple file analysis"""
        high_risk = stats.get('high_risk_files', 0)
        medium_risk = stats.get('medium_risk_files', 0)
        low_risk = stats.get('low_risk_files', 0)

        summary = f"Analyzed {high_risk + medium_risk + low_risk} files"

        if high_risk > 0:
            summary += f", {high_risk} HIGH risk"
        if medium_risk > 0:
            summary += f", {medium_risk} MEDIUM risk"

        summary += f"\nTotal findings: {stats.get('total_findings', 0)}"

        return summary

    def analyze_injection_points_for_high_risk_files(self, file_reports: List[Dict[str, Any]], dataflow_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Dedicated LLM analysis for high/medium risk files to identify injection points
        Only processes files with HIGH or MEDIUM risk assessment
        """
        # Filter for high and medium risk files only
        high_medium_risk_files = []
        for report in file_reports:
            risk_level = report.get("risk_assessment", {}).get("overall_risk", "LOW")
            if risk_level in ["HIGH", "MEDIUM"]:
                high_medium_risk_files.append(report)
        
        if not high_medium_risk_files:
            return {
                "analysis_performed": False,
                "reason": "No high or medium risk files found",
                "injection_points": [],
                "summary": "No high/medium risk files found requiring deep analysis"
            }
        
        # Prepare comprehensive context for LLM
        context_data = self._prepare_injection_analysis_context(high_medium_risk_files, dataflow_analysis or {})
        
        # Call specialized LLM for injection point analysis
        injection_analysis = self._call_injection_point_llm(context_data)
        
        return {
            "analysis_performed": True,
            "files_analyzed": len(high_medium_risk_files),
            "injection_analysis": injection_analysis,
            "high_risk_files": [f["file_path"] for f in high_medium_risk_files if f.get("risk_assessment", {}).get("overall_risk") == "HIGH"],
            "medium_risk_files": [f["file_path"] for f in high_medium_risk_files if f.get("risk_assessment", {}).get("overall_risk") == "MEDIUM"],
            "summary": injection_analysis.get("summary", "Injection point analysis completed")
        }

    def _prepare_injection_analysis_context(self, high_risk_files: List[Dict], dataflow_analysis: Dict) -> Dict[str, Any]:
        """Prepare context for injection point analysis"""
        context = {
            "file_summaries": [],
            "aggregated_tools": [],
            "aggregated_dataflows": [],
            "risk_indicators": []
        }
        
        for file_report in high_risk_files:
            file_summary = {
                "file_path": file_report["file_path"],
                "risk_level": file_report.get("risk_assessment", {}).get("overall_risk", "UNKNOWN"),
                "agent_tools": file_report.get("agent_analysis", {}).get("agent_tools", []),
                "dataflow_patterns": file_report.get("agent_analysis", {}).get("dataflow_patterns", []),
                "findings_count": len(file_report.get("findings", [])),
                "tool_summary": file_report.get("agent_analysis", {}).get("tool_summary", "")
            }
            context["file_summaries"].append(file_summary)
            
            # Aggregate tools across all files
            for tool in file_summary["agent_tools"]:
                if tool not in context["aggregated_tools"]:
                    context["aggregated_tools"].append(tool)
            
            # Aggregate high-risk dataflows
            for flow in file_summary["dataflow_patterns"]:
                if flow.get("risk_level") == "HIGH" or flow.get("external_input") == "yes":
                    context["aggregated_dataflows"].append({
                        "file": file_summary["file_path"],
                        "flow": flow
                    })
        
        return context

    def _call_injection_point_llm(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call specialized LLM to analyze injection points in high/medium risk files"""
        
        # Build comprehensive prompt for injection analysis
        prompt = f"""Based on tool use and dataflow analysis of high/medium risk files, identify potential injection points:

**File Analysis Overview:**
{self._format_file_summaries_for_llm(context_data["file_summaries"])}

**Aggregated Tool Types:**
{self._format_tools_for_llm(context_data["aggregated_tools"])}

**High-Risk Dataflows:**
{self._format_dataflows_for_llm(context_data["aggregated_dataflows"])}

**Analysis Tasks:**
1. Identify cross-file injection attack vectors
2. Analyze vulnerable points in tool chains
3. Assess injection possibilities in dataflows
4. Provide specific exploit scenarios

**Focus Areas:**
- Paths where external input directly enters LLM prompts
- Tool outputs passed to other tools without validation
- User-controllable data affecting agent decisions
- External data sources like file uploads/API responses

Respond in JSON format:
{{
    "critical_injection_points": [
        {{
            "attack_vector": "Specific attack vector description",
            "affected_files": ["file1.py", "file2.py"],
            "injection_type": "prompt_injection|tool_chain_injection|data_poisoning",
            "severity": "CRITICAL|HIGH|MEDIUM",
            "exploit_scenario": "Specific exploitation scenario",
            "mitigation": "Mitigation recommendations"
        }}
    ],
    "cross_file_vulnerabilities": [
        {{
            "description": "Cross-file vulnerability description",
            "affected_dataflow": "Affected dataflow",
            "risk_assessment": "Risk assessment"
        }}
    ],
    "summary": "Overall injection risk assessment summary"
}}"""

        # Call LLM for injection analysis
        result_text = LLMClient.call_llm(
            model=LLMClient.get_model(),
            messages=[
                {"role": "system", "content": "You are an expert security analyst specializing in AI agent injection vulnerabilities. Analyze the provided context to identify critical injection points."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.1,
            timeout=45,
            max_retries=3
        )

        if result_text:
            try:
                import json
                # Try to parse JSON response
                start = result_text.find('{')
                end = result_text.rfind('}') + 1
                if start != -1 and end > start:
                    json_text = result_text[start:end]
                    return json.loads(json_text)
            except Exception as e:
                # Fallback to text response
                return {
                    "critical_injection_points": [],
                    "cross_file_vulnerabilities": [],
                    "summary": result_text[:500],
                    "parse_error": str(e)
                }
        
        return {
            "critical_injection_points": [],
            "cross_file_vulnerabilities": [],
            "summary": "LLM injection point analysis failed",
            "error": "LLM call failed"
        }

    def _format_file_summaries_for_llm(self, file_summaries: List[Dict]) -> str:
        """Format file summaries for LLM context"""
        formatted = []
        for summary in file_summaries:
            formatted.append(f"- {summary['file_path']} (risk level: {summary['risk_level']})")
            formatted.append(f"  tools: {len(summary['agent_tools'])}, dataflows: {len(summary['dataflow_patterns'])}")
            if summary['tool_summary']:
                formatted.append(f"  summary: {summary['tool_summary']}")
        return "\n".join(formatted)

    def _format_tools_for_llm(self, tools: List[Dict]) -> str:
        """Format tools for LLM context"""
        if not tools:
            return "No obvious tool usage patterns found"
        
        tool_types = {}
        for tool in tools:
            tool_type = tool.get("tool_type", "unknown")
            tool_types[tool_type] = tool_types.get(tool_type, 0) + 1
        
        formatted = []
        for tool_type, count in tool_types.items():
            formatted.append(f"- {tool_type}: {count} tools")
        
        return "\n".join(formatted)

    def _format_dataflows_for_llm(self, dataflows: List[Dict]) -> str:
        """Format dataflows for LLM context"""
        if not dataflows:
            return "No high-risk dataflows found"
        
        formatted = []
        for item in dataflows:
            flow = item["flow"]
            formatted.append(f"- {item['file']}: {flow.get('data_path', 'unknown path')}")
            formatted.append(f"  external input: {flow.get('external_input', 'unknown')}, validation: {flow.get('sanitization', 'unknown')}")
        
        return "\n".join(formatted)