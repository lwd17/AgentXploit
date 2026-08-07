import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfiguration:
    """Configuration for individual agents in the Agent-as-a-Tool architecture"""

    # Model configuration - will be set from settings
    model_name: str = None
    model_provider: str = "openai"
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    timeout_seconds: int = 120
    
    # Agent behavior
    skip_summarization: bool = True
    enable_tracing: bool = False
    log_level: str = "INFO"
    
    # Performance tuning
    max_concurrent_tools: int = 5
    tool_timeout_seconds: int = 60
    retry_attempts: int = 3
    
    # Security settings
    enable_content_filtering: bool = True
    max_content_length: int = 100000
    allowed_domains: list = None


@dataclass
class RootAgentConfig(AgentConfiguration):
    """Configuration specific to the root orchestrator agent"""
    
    # Override defaults for root agent
    skip_summarization: bool = False
    enable_tracing: bool = True
    
    # Decision-making configuration
    decision_timeout: int = 30
    max_delegation_depth: int = 3
    enable_parallel_execution: bool = False
    
    # Session management
    session_timeout_minutes: int = 30
    max_session_memory: int = 10000


@dataclass
class AnalysisAgentConfig(AgentConfiguration):
    """Configuration specific to the analysis agent"""

    # Analysis-specific settings - will be set from settings
    max_files_per_analysis: int = None
    analysis_depth: str = "comprehensive"
    enable_security_focus: bool = True
    
    # Performance optimization
    parallel_analysis: bool = True
    cache_analysis_results: bool = True
    cache_duration_hours: int = 24


@dataclass
class InjectionAgentConfig(AgentConfiguration):
    """Configuration specific to the injection agent"""
    
    # Injection-specific settings
    default_command_type: str = "pkill"
    default_injection_strategy: str = "technical"
    enable_llm_injection: bool = True
    
    # Safety and verification
    verify_injection_success: bool = True
    enable_fallback_injection: bool = True
    max_injection_attempts: int = 3
    
    # Batch processing
    batch_processing_enabled: bool = True
    max_batch_size: int = 100
    max_concurrent_injections: int = 3


class AgentConfigManager:
    """Centralized configuration manager for Agent-as-a-Tool architecture"""
    
    def __init__(self):
        self._configs = {}
        self._load_default_configs()
        self._load_environment_overrides()
    
    def _load_default_configs(self):
        """Load default configurations for all agents"""
        self._configs = {
            "root": RootAgentConfig(),
            "analysis": AnalysisAgentConfig(),
            "injection": InjectionAgentConfig()
        }
    
    def _load_environment_overrides(self):
        """Load configuration overrides from environment variables"""
        
        # Root agent overrides
        if os.getenv("ROOT_AGENT_MODEL"):
            self._configs["root"].model_name = os.getenv("ROOT_AGENT_MODEL")
        if os.getenv("ROOT_AGENT_TIMEOUT"):
            self._configs["root"].timeout_seconds = int(os.getenv("ROOT_AGENT_TIMEOUT"))
        
        # Analysis agent overrides
        if os.getenv("ANALYSIS_AGENT_MODEL"):
            self._configs["analysis"].model_name = os.getenv("ANALYSIS_AGENT_MODEL")
        if os.getenv("ANALYSIS_MAX_FILES"):
            self._configs["analysis"].max_files_per_analysis = int(os.getenv("ANALYSIS_MAX_FILES"))
        if os.getenv("ANALYSIS_DEPTH"):
            self._configs["analysis"].analysis_depth = os.getenv("ANALYSIS_DEPTH")
        
        # Injection agent overrides
        if os.getenv("EXPLOIT_AGENT_MODEL"):
            self._configs["injection"].model_name = os.getenv("EXPLOIT_AGENT_MODEL")
        if os.getenv("INJECTION_COMMAND_TYPE"):
            self._configs["injection"].default_command_type = os.getenv("INJECTION_COMMAND_TYPE")
        if os.getenv("INJECTION_STRATEGY"):
            self._configs["injection"].default_injection_strategy = os.getenv("INJECTION_STRATEGY")
        if os.getenv("INJECTION_MAX_BATCH"):
            self._configs["injection"].max_batch_size = int(os.getenv("INJECTION_MAX_BATCH"))
    
    def get_config(self, agent_type: str) -> AgentConfiguration:
        """Get configuration for a specific agent type"""
        if agent_type not in self._configs:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return self._configs[agent_type]
    
    def update_config(self, agent_type: str, **kwargs):
        """Update configuration for a specific agent"""
        if agent_type not in self._configs:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        config = self._configs[agent_type]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                raise ValueError(f"Invalid configuration key: {key}")
    
    def export_config(self, agent_type: str) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        config = self.get_config(agent_type)
        return {
            field.name: getattr(config, field.name)
            for field in config.__dataclass_fields__.values()
        }
    
    def validate_configs(self) -> Dict[str, list]:
        """Validate all configurations and return any issues"""
        issues = {}
        
        for agent_type, config in self._configs.items():
            agent_issues = []
            
            # Validate timeouts
            if config.timeout_seconds <= 0:
                agent_issues.append("timeout_seconds must be positive")
            
            # Validate retry attempts
            if config.retry_attempts < 0:
                agent_issues.append("retry_attempts must be non-negative")
            
            # Validate model configuration
            if not config.model_name:
                agent_issues.append("model_name cannot be empty")
            
            # Agent-specific validations
            if agent_type == "analysis" and config.max_files_per_analysis <= 0:
                agent_issues.append("max_files_per_analysis must be positive")
            
            if agent_type == "injection" and config.max_batch_size <= 0:
                agent_issues.append("max_batch_size must be positive")
            
            if agent_issues:
                issues[agent_type] = agent_issues
        
        return issues


# Global configuration manager instance
config_manager = AgentConfigManager()