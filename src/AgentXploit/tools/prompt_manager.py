"""
Improved prompt management for LLM interactions
Focuses on agent injection analysis with intelligent file selection
"""

from typing import Dict, Any, List


class PromptManager:
    """Strict prompt manager for agent injection analysis"""

    @staticmethod
    def get_exploration_decision_prompt(history_context: str,
                                        exploration_context: str = None,
                                        unexplored_areas: List[str] = None,
                                        root_unexplored: List[str] = None,
                                        files: List[str] = None,
                                        dirs: List[str] = None,
                                        context: Dict = None,
                                        focus: str = "security") -> str:
        """Unified exploration decision prompt with strict selection rules"""

        # Handle both calling patterns
        if context is not None:
            files = context.get('files', [])
            dirs = context.get('directories', [])
            explored_path = context.get('explored_path', '.')
            exploration_context = f"Currently exploring: {explored_path}"
            unexplored_areas = unexplored_areas or []
            root_unexplored = root_unexplored or []
        else:
            files = files or []
            dirs = dirs or []
            unexplored_areas = unexplored_areas or []
            root_unexplored = root_unexplored or []
            exploration_context = exploration_context or "Exploration in progress"

        return f"""FOCUS: {focus.upper()} - Analyze AGENT TOOLS and EXTERNAL DATAFLOW patterns
STRICT RULE: You MUST ONLY select from the AVAILABLE FILES and SUBDIRECTORIES lists below.

CRITICAL TOOL DEFINITION:
**TOOLS** are components that interact with EXTERNAL DATA SOURCES or USER DIRECT INPUT, such as:
- Web browsing/scraping tools (like browse_web in gpt-researcher)
- File system access tools (like fetch_local_reference_file)
- Database/API clients that fetch external data
- User input handlers and data processors
- External service integrators (not internal functions)

AGENT TOOL KEYWORDS TO PRIORITIZE:
- browse, fetch, scrape, crawl, download, upload
- client, api, request, http, web, url, endpoint
- database, db, query, search, retrieve
- file, read, write, load, save, import, export
- user_input, prompt, interactive, interface

EXTERNAL DATAFLOW KEYWORDS TO PRIORITIZE:
- external, remote, fetch, retrieve, download
- user_input, stdin, prompt, interactive
- api_call, http_request, web_request, url_fetch
- file_read, file_write, database_query
- source, sink, input_stream, output_stream

AVOID THESE (unless they implement tools):
- README.md, docs/, documentation/, examples/
- tests/, test_, _test.py (unless testing tool implementations)
- config files (unless they define tool configurations)

AVAILABLE FILES IN CURRENT DIRECTORY (SELECT EXACT NAMES ONLY):
{chr(10).join([f"- {f}" for f in files])}

AVAILABLE SUBDIRECTORIES (SELECT EXACT NAMES ONLY):
{chr(10).join([f"- {d}" for d in dirs])}

UNEXPLORED ROOT DIRECTORIES:
{chr(10).join([f"- {d}" for d in root_unexplored])}

{exploration_context}

HISTORY CONTEXT(only for reference):
{history_context}

CRITICAL RULES:
1. Copy-paste EXACT names from the lists above
2. NEVER add '.py' to directory names
3. If it's in SUBDIRECTORIES list, it's a directory, NOT a file
4. Focus on EXTERNAL INTERACTION TOOLS and DATAFLOW for {focus} analysis
5.**BE HIGHLY SELECTIVE**: Only choose files likely to contain actual TOOL IMPLEMENTATIONS that interact with external data sources - avoid internal utility functions

RESPONSE FORMAT (JSON only, using EXACT names from lists):
{{
  "analysis_targets": [
    {{
      "type": "file|directory",
      "path": "EXACT_NAME_FROM_LISTS",
      "priority": "high|medium|low",
      "reason": "contains EXTERNAL DATA INTERACTION tool|external dataflow processing|user input handling"
    }}
  ],
  "strategy_explanation": "focusing on EXTERNAL DATA INTERACTION tool implementations and external dataflow patterns for {focus} analysis"
}}"""


    @staticmethod
    def get_content_decision_prompt(history_context: str, context: Dict, focus: str = "security") -> str:
        """Strict content decision prompt with available-file filtering and MCP recommendations"""
    
        file_path = context.get('file_path', '')
        content = context.get('content', '')
        security_result = context.get('security_result', {})
        available_files = context.get('available_files', [])
        available_dirs = context.get('available_dirs', [])
        
        # Extract MCP recommendations (highest priority)
        mcp_related_files = context.get('mcp_related_files', [])
        mcp_config_files = context.get('mcp_config_files', [])
    
        # Extract imports and references (only used as hints, not direct selection)
        imports_found = []
        if content:
            import re
            python_imports = re.findall(r'from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.]+)', content)
            for match in python_imports:
                module = match[0] or match[1]
                if module and '.' in module:
                    file_candidate = module.replace('.', '/') + '.py'
                    imports_found.append(file_candidate)
    
            file_refs = re.findall(r'[\'"]([^\'\"]*\.(?:py|js|ts|json|toml|yaml|yml))[\'"]', content)
            imports_found.extend(file_refs)
    
        # Build analyzed files list from history
        analyzed_files_list = []
        if history_context and "ANALYZED FILES" in history_context:
            lines = history_context.split('\n')
            in_section = False
            for line in lines:
                if 'ANALYZED FILES' in line:
                    in_section = True
                    continue
                elif line.strip().startswith('-') and in_section:
                    file_name = line.strip()[1:].split(':')[0].strip()
                    analyzed_files_list.append(file_name)
                elif line.strip() and not line.startswith('-') and in_section:
                    break
    
        return f"""FOCUS: {focus.upper()} - Analyzing file content for EXTERNAL DATA INTERACTION TOOLS and DATAFLOW vulnerabilities
Make follow-up decisions using STRICT selection rules based on the history context.

CURRENT FILE: {file_path}
SECURITY RISK: {security_result.get('risk_assessment', {}).get('overall_risk', 'UNKNOWN')}

HISTORY CONTEXT:
{history_context}

ALREADY ANALYZED FILES (DO NOT suggest these):
{chr(10).join([f"- {f}" for f in analyzed_files_list])}

IMPORT/REFERENCE HINTS (for prioritization only, do not invent new paths):
{chr(10).join([f"- {imp}" for imp in imports_found])}

MCP LANGUAGE SERVER RECOMMENDATIONS (HIGHEST PRIORITY - these are LSP-verified dependencies):
{chr(10).join([f"- {mcp_file} (MCP verified dependency)" for mcp_file in mcp_related_files])}
{chr(10).join([f"- {mcp_file} (MCP verified config reference)" for mcp_file in mcp_config_files])}
{"No MCP recommendations available" if not (mcp_related_files or mcp_config_files) else ""}

AVAILABLE FILES (YOU MUST SELECT FROM THIS LIST ONLY):
{chr(10).join([f"- {f}" for f in available_files])}

AVAILABLE DIRECTORIES (YOU MUST SELECT FROM THIS LIST ONLY):
{chr(10).join([f"- {d}" for d in available_dirs])}

CRITICAL WARNING: DO NOT CREATE FILE NAMES! DO NOT ADD '.py' TO DIRECTORY NAMES!
If you see "serialization" in directories, it's a DIRECTORY, not "serialization.py"!

COMPLETE DATAFLOW TRACING FOCUS FOR {focus.upper()} ANALYSIS:
1. **PRIMARY**: Files/dirs with EXTERNAL DATA INTERACTION TOOLS (web, file, API, database access)
2. **SECONDARY**: Internal processing functions that are PART OF THE DATAFLOW from external sources to LLM decisions
3. **DATAFLOW CHAIN**: Trace complete path: External Data Source → Internal Processing → LLM Decision Making
4. AVOID documentation unless they define external tool interfaces
5. **COMPLETE CHAIN FOCUS**: Analyze files that form the COMPLETE DATAFLOW from external data sources to final LLM processing - include necessary internal functions

FOLLOW-UP STRATEGY FOR {focus.upper()} (in order of priority):
1. **FIRST PRIORITY**: MCP Language Server recommendations (if available) - these are verified dependencies
2. If current file contains EXTERNAL DATA INTERACTION tools -> find files that USE these tools (internal processing)
3. If current file has EXTERNAL DATAFLOW patterns -> trace COMPLETE dataflow path to LLM decision making
4. If current file processes EXTERNAL INPUT -> find downstream processing and LLM integration logic
5. **COMPLETE CHAIN**: Follow dataflow from external source through internal processing to final LLM decision
6. Maximum 2 follow-up targets - prioritize MCP recommendations first, then COMPLETING THE DATAFLOW CHAIN

ABSOLUTE RULES:
- You MUST copy-paste EXACT names from AVAILABLE FILES or AVAILABLE DIRECTORIES
- NEVER invent file names or add extensions to directory names
- If something appears only in AVAILABLE DIRECTORIES, it's a directory, NOT a file

Respond in JSON format:
{{
    "follow_up_targets": [
        {{"path": "EXACT_NAME_FROM_AVAILABLE_LISTS", "type": "file|directory", "priority": "highest", "reason": "🔥 MCP Language Server verified dependency - PRIORITY"}},
        {{"path": "EXACT_NAME_FROM_AVAILABLE_LISTS", "type": "file|directory", "priority": "high", "reason": "EXTERNAL DATA INTERACTION tool or part of COMPLETE DATAFLOW chain to LLM"}},
        {{"path": "EXACT_NAME_FROM_AVAILABLE_LISTS", "type": "file|directory", "priority": "medium", "reason": "Internal processing component in DATAFLOW chain from external source to LLM"}}
    ],
    "exploration_strategy": "focus on COMPLETE DATAFLOW CHAINS from external data sources through internal processing to final LLM decisions for {focus} analysis"
}}"""


    @staticmethod
    def get_context_reassessment_prompt(history_context: str, current_state: Dict,
                                      unexplored_root_dirs: List[str], unexplored_subdirs: List[str],
                                      task_queue_size: int, focus: str = "security") -> str:
        """Improved context reassessment prompt"""
        return f"""FOCUS: {focus.upper()} - Making strategic decisions about repository analysis continuation.

HISTORY CONTEXT:
{history_context}

CURRENT STATE:
- Files analyzed: {current_state.get('analyzed_files', 0)}
- Directories explored: {current_state.get('explored_dirs', 0)}
- High-risk findings: {current_state.get('high_risk_count', 0)}
- Task queue: {task_queue_size} tasks

UNEXPLORED AREAS:
Root directories: {unexplored_root_dirs}
Subdirectories: {unexplored_subdirs}

STRATEGIC PRIORITIES FOR {focus.upper()} ANALYSIS:
1. If files with EXTERNAL DATA INTERACTION tool definitions found -> explore directories containing external tool implementations or consumers
2. If EXTERNAL dataflow patterns identified -> prioritize directories that likely contain related external data processing logic
3. Focus on directories suggesting external data interaction
4. Prioritize directories that are likely to contain EXTERNAL DATA INTERACTION tool chains and external dataflow patterns
5. Avoid: documentation directories unless they contain tool configurations or data samples
6. **STRATEGIC FOCUS**: Select areas for tool/dataflow discovery - avoid broad exploration

Select the MOST PROMISING unexplored area for tool chain and dataflow analysis focused on {focus}.

Respond in JSON format:
{{
    "next_actions": [
        {{
            "action": "explore_directory",
            "target": "exact_directory_from_unexplored_lists",
            "priority": "high",
            "reason": "likely contains EXTERNAL DATA INTERACTION tool implementations or external data processing logic for {focus}",
            "expected_value": "tool_dataflow_analysis"
        }}
    ],
    "strategy_explanation": "focus on EXTERNAL DATA INTERACTION tool and external data processing directories for {focus} analysis",
    "reasoning": "prioritize areas most likely to contain EXTERNAL DATA INTERACTION tool chains and external dataflow patterns relevant to {focus}"
}}"""

    @staticmethod
    def get_queue_reassessment_prompt(discoveries_context: str, tasks_context: str) -> str:
        """Improved queue reassessment prompt with realistic expectations"""
        return f"""You are reassessing task priorities based on analysis discoveries.

{discoveries_context}

{tasks_context}

REASSESSMENT STRATEGY:
1. If EXTERNAL DATA INTERACTION tool definitions found → increase priority of files that implement or consume these external tools
2. If EXTERNAL dataflow patterns identified → prioritize external upstream sources and external downstream processors in the same flow
3. If external data sources discovered → prioritize validation, parsing, and processing files
4. If tool chains partially mapped → prioritize completing the chain analysis
5. Otherwise → minimal priority changes needed

REALISTIC EXPECTATIONS:
- Early in analysis: few discoveries, minimal priority changes
- Later in analysis: more discoveries, more targeted priority changes
- Only change priorities when there's clear logical connection

Respond in JSON format:
{{
    "has_relevant_discoveries": true/false,
    "priority_updates": {{
        "exact_task_target": new_priority_number
    }},
    "discovery_based_reasoning": "explain connection to EXTERNAL DATA INTERACTION tool/external dataflow discoveries"
}}

If no clear connections exist, respond:
{{
    "has_relevant_discoveries": false,
    "priority_updates": {{}},
    "discovery_based_reasoning": "No discoveries warrant priority changes"
}}"""

    @staticmethod
    def get_file_priority_prompt(context: str, files: List[str], 
                               security_findings: List[Dict] = None,
                               workflow_analysis: Dict = None,
                               focus: str = "security") -> str:
        """Improved file priority prompt focused on agent injection"""
        
        # Present ALL files to LLM for intelligent selection - no pre-filtering
        
        return f"""FOCUS: {focus.upper()} - Selecting files for EXTERNAL DATA INTERACTION TOOL IMPLEMENTATION and DATAFLOW analysis.
Your goal is to find actual code that implements EXTERNAL DATA INTERACTION tools, processes external data, or manages agent workflows that interact with external data sources for {focus} analysis.

REPOSITORY CONTEXT:
{context}

ALL AVAILABLE FILES (make intelligent selections):
{chr(10).join([f"{i+1}. {f}" for i, f in enumerate(files)])}

CRITICAL SELECTION PRIORITIES FOR {focus.upper()}:
1. **HIGHEST PRIORITY**: Source code files (.py, .js, .ts) that contain:
   - EXTERNAL DATA INTERACTION tools (web scraping, file access, API clients, database access)
   - User input handlers (prompt processing, interactive interfaces)
   - External service integrators (HTTP clients, web browsers, file downloaders)
   - External data processors (external file readers, remote data fetchers)

2. **STRONGLY AVOID**: 
   - Documentation files UNLESS they contain actual implementations or core information about tools/workflows
   - Configuration files unless they define tools/workflows
   - Test files unless analyzing tool testing

3. **COMPLETE DATAFLOW CHAIN FOCUS**: Prioritize files likely to show:
   - How EXTERNAL DATA enters the system (APIs, files, user input) - **ENTRY POINTS**
   - How data flows through internal processing - **PROCESSING CHAIN**
   - How processed data reaches LLM for decision making - **LLM INTEGRATION**
   - Complete dataflow validation and transformation pipeline

**COMPLETE CHAIN REQUIREMENT**: Analyze files that form the COMPLETE DATAFLOW CHAIN from external data sources to final LLM processing. Include necessary internal processing functions that are part of the dataflow, but prioritize external interaction points.


Respond in JSON format:
{{
    "priority_files": [
        {{
            "filename": "exact_filename_from_lists_above",
            "priority": "high",
            "reason": "likely contains EXTERNAL DATA INTERACTION tool or DATAFLOW CHAIN component (external→internal→LLM) for {focus}",
            "analysis_focus": "external_data_entry_point|dataflow_processing_chain|llm_integration_point"
        }}
    ],
    "analysis_strategy": "focus on COMPLETE DATAFLOW CHAINS from external data sources through internal processing to LLM decision points for {focus} analysis"
}}"""

    @staticmethod
    def get_security_analysis_prompt(file_path: str, content: str, language: str) -> str:
        """Focused security analysis prompt for tool use and dataflow analysis"""
        content_sample = content[:1500] + "..." if len(content) > 1500 else content

        return f"""Analyze this code for EXTERNAL DATA INTERACTION TOOLS and DATAFLOW patterns that could lead to injection vulnerabilities.

FILE: {file_path}
LANGUAGE: {language}

CODE CONTENT:
{content_sample}

**PRIMARY ANALYSIS FOCUS - External Data Interaction Tools and Data Flow:**

CRITICAL TOOL DEFINITION: **TOOLS** are components that interact with EXTERNAL DATA SOURCES or USER DIRECT INPUT (like browse_web, fetch_local_reference_file in gpt-researcher).

1. **EXTERNAL DATA INTERACTION TOOL IDENTIFICATION**: What external data interaction tools does this component provide or use?
   - Web browsing/scraping tools (HTTP requests, web crawling)
   - File system access tools (reading/writing external files)
   - Database/API clients (external data retrieval)
   - User input handlers (interactive prompts, user data processing)
   - External service integrators (third-party API calls)

2. **COMPLETE DATAFLOW CHAIN MAPPING**: How does data flow from external sources to final LLM processing?
   - **ENTRY POINTS**: External input sources (user input, external files, remote APIs, web sources)
   - **PROCESSING CHAIN**: Internal data processing/transformation steps that handle external data
   - **LLM INTEGRATION**: How processed external data reaches LLM for decision making
   - **VALIDATION POINTS**: Data validation/sanitization throughout the complete chain

3. **DATAFLOW CHAIN INJECTION ANALYSIS**: Where in the COMPLETE dataflow chain could malicious input cause problems?
   - External input sanitization gaps at entry points
   - Internal processing vulnerabilities in the dataflow chain
   - LLM prompt injection through processed external data
   - Data poisoning through the complete external→internal→LLM pipeline

Respond in JSON format:
{{
    "tool_analysis": {{
        "identified_tools": [
            {{
                "tool_name": "specific_tool_or_function_name",
                "tool_type": "web_browser|file_accessor|api_client|database_client|user_input_handler|external_service_integrator",
                "description": "what this external data interaction tool does",
                "external_data_sources": ["specific_external_sources_it_accesses"],
                "external_data_destinations": ["where_external_data_goes"]
            }}
        ],
        "dataflow_patterns": [
            {{
                "flow_id": "flow_1",
                "description": "brief description of this COMPLETE dataflow chain",
                "data_path": "external_source -> internal_processing -> llm_integration",
                "external_data_source": "specific external source (web_browse|local_document|user_query_input|api_endpoint|database|environment_variable)",
                "external_data_source_details": "specific details of the external source (URL, file path, user input field, etc.)",
                "internal_processing_steps": ["step1", "step2", "step3"],
                "llm_integration_point": "specific LLM integration method (GPTResearcher|create_chat_completion|prompt_building)",
                "llm_integration_details": "how exactly data reaches LLM (prompt parameter, context, message content)",
                "sanitization": "yes|no|partial - is data sanitized throughout the chain",
                "validation_points": ["where validation occurs in the chain"],
                "risk_level": "HIGH|MEDIUM|LOW"
            }}
        ]
    }},
    "injection_analysis": {{
        "potential_injection_points": [
            {{
                "location": "line_number_or_function_name",
                "injection_type": "external_data_injection|dataflow_chain_injection|llm_prompt_injection|internal_processing_injection",
                "severity": "HIGH|MEDIUM|LOW",
                "description": "specific vulnerability description",
                "attack_scenario": "how attacker could exploit this",
                "affected_dataflow": "flow_id from above"
            }}
        ],
        "overall_risk": "HIGH|MEDIUM|LOW"
    }},
    "summary": "Brief summary of COMPLETE DATAFLOW CHAIN from external data sources through internal processing to LLM integration and associated risks"
}}"""

    @staticmethod
    def get_llm_dataflow_analysis_prompt(dataflow_data: Dict) -> str:
        """Get prompt for LLM-driven comprehensive dataflow analysis"""
        prompt = f"""Analyze the following dataflow patterns and tools to understand complete data paths from external sources to LLM decisions.

REPOSITORY ANALYSIS CONTEXT:
- Total dataflows found: {dataflow_data.get('total_dataflows', 0)}
- Total external data interaction tools: {dataflow_data.get('total_tools', 0)}

CRITICAL TASK: Trace COMPLETE DATAFLOW CHAINS from external data sources through internal processing to final LLM decision points.

DATAFLOW PATTERNS DISCOVERED:
"""
        
        for i, flow in enumerate(dataflow_data.get('dataflows', [])[:15], 1):
            prompt += f"""
{i}. File: {flow.get('file', 'unknown')}
   Flow: {flow.get('flow_id', 'unknown')}
   Description: {flow.get('description', 'No description')}
   Data Path: {flow.get('data_path', 'unknown')}
   External Source: {flow.get('external_data_source', 'unknown')}
   Risk Level: {flow.get('risk_level', 'UNKNOWN')}
"""

        prompt += f"""
EXTERNAL DATA INTERACTION TOOLS DISCOVERED:
"""
        
        for i, tool in enumerate(dataflow_data.get('tools', [])[:20], 1):
            prompt += f"""
{i}. File: {tool.get('file', 'unknown')}
   Tool: {tool.get('tool_name', 'unknown')} ({tool.get('tool_type', 'unknown')})
   Description: {tool.get('description', 'No description')}
"""

        prompt += """
ANALYSIS REQUIREMENTS:

1. **EXTERNAL DATA SOURCE CATEGORIZATION**: Intelligently categorize all external data sources:
   - web_browse: Web scraping, HTTP requests, browser automation
   - local_document: File reading, document processing, local file access
   - user_query_input: User prompts, websocket input, CLI arguments, interactive input
   - api_endpoint: External API calls, third-party services, remote endpoints
   - database: Database queries, data retrieval from storage
   - environment_variable: Configuration from environment variables

2. **COMPLETE DATAFLOW CHAINS**: Identify and trace complete chains:
   - External Data Source → Internal Processing → LLM Decision
   - Show how external data flows through multiple files/components
   - Identify the specific LLM integration points

3. **CROSS-FILE DATAFLOW ANALYSIS**: Analyze dataflow spanning multiple files:
   - Entry point files (where external data enters the system)
   - Processing files (internal data transformation and validation)
   - LLM integration files (where processed data reaches LLM for decisions)

4. **VALIDATION AND RISK ASSESSMENT**: Analyze security implications:
   - Identify validation gaps in the dataflow chains
   - Assess injection risks at each step
   - Provide specific security recommendations

Respond in JSON format:
{{
    "external_data_source_categories": {{
        "web_browse": [{{"file": "file_path", "flow_description": "desc", "data_entry_point": "specific_entry", "tools_involved": ["tool1", "tool2"]}}],
        "local_document": [...],
        "user_query_input": [...],
        "api_endpoint": [...],
        "database": [...],
        "environment_variable": [...]
    }},
    "complete_dataflow_chains": [
        {{
            "chain_id": "unique_id",
            "external_data_source_category": "category",
            "external_data_source_details": "specific source details (URL, file path, input field, etc.)",
            "entry_point_file": "file_where_external_data_enters",
            "internal_processing_chain": ["file1: processing_step1", "file2: processing_step2"],
            "llm_integration_file": "file_where_llm_processes_data",
            "llm_integration_method": "specific_method (GPTResearcher, create_chat_completion, etc.)",
            "complete_flow_description": "detailed description of the complete external→internal→LLM flow",
            "validation_points": ["specific_locations_where_validation_occurs"],
            "risk_level": "HIGH|MEDIUM|LOW",
            "injection_risk": "specific_injection_risks_in_this_chain"
        }}
    ],
    "cross_file_dataflow_analysis": {{
        "entry_point_files": [{{"file": "file_path", "external_data_types": ["web", "user_input"], "tools": ["tool1", "tool2"]}}],
        "processing_files": [{{"file": "file_path", "processing_functions": ["func1", "func2"], "data_transformations": ["transform1", "transform2"]}}],
        "llm_integration_files": [{{"file": "file_path", "llm_methods": ["method1", "method2"], "integration_points": ["point1", "point2"]}}],
        "dataflow_completeness_assessment": "detailed_assessment_of_chain_completeness"
    }},
    "validation_and_risk_analysis": {{
        "validation_gaps": [{{"location": "file:function", "missing_validation": "what_validation_is_missing", "risk": "potential_risk"}}],
        "high_risk_dataflow_chains": [{{"chain_id": "id", "risk_description": "why_high_risk", "attack_scenarios": ["scenario1", "scenario2"]}}],
        "security_recommendations": ["specific_actionable_security_recommendations"]
    }}
}}"""
        
        return prompt

    @staticmethod
    def get_focus_aware_reassessment_prompt(current_state: Dict, security_findings: List,
                                          workflow_patterns: Dict, task_queue_info: Dict, 
                                          focus_summary: Dict, primary_focus) -> str:
        """Improved reassessment decision prompt"""
        
        recent_findings = security_findings[-3:] if security_findings else []
        high_risk_count = sum(1 for f in recent_findings if f.get('risk_level') == 'high')
        
        return f"""Make a strategic decision about task queue reassessment.

CURRENT STATE:
- Step: {current_state['step']}
- Files analyzed: {current_state['analyzed_files']}
- Recent high-risk findings: {high_risk_count}
- Pending tasks: {task_queue_info['pending_count']}

REASSESS DECISION CRITERIA:
- Reassess if: new high-risk findings discovered, stuck on low-value files
- Don't reassess if: progressing well, no significant new discoveries

Respond in JSON format:
{{
    "should_reassess": true/false,
    "reasoning": "brief explanation",
    "confidence": "high/medium/low"
}}"""

    @staticmethod
    def get_reassessment_decision_prompt(current_state: Dict, security_findings: List[Dict],
                                       workflow_patterns: Dict, task_queue_info: Dict) -> str:
        """Get prompt for LLM-driven reassessment decision"""
        
        recent_findings = security_findings[-3:] if security_findings else []
        high_risk_count = sum(1 for f in recent_findings if f.get('risk_level') in ['high', 'medium'])
        
        return f"""Make an intelligent reassessment decision based on recent discoveries.

CURRENT STATE:
- Step: {current_state.get('step', 0)}
- Files analyzed: {current_state.get('analyzed_files', 0)}
- Recent high/medium risk findings: {high_risk_count}

REASSESSMENT CRITERIA:
- Reassess if: significant new findings, analysis stuck on low-value files
- Don't reassess if: good progress, no major discoveries

Respond in JSON format:
{{
    "should_reassess": true/false,
    "confidence": "high/medium/low",
    "reasoning": "brief explanation",
    "priority_focus": "what to focus on if reassessing"
}}"""
