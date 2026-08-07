from enum import Enum


class InjectionStrategy(Enum):
    """Injection strategy types"""
    TECHNICAL = "technical"  # Technical Justification (default)
    DEBUG = "debug"          # Disguise as Debug Mode
    AUTHORITY = "authority"  # Authority-based Instruction


class CommandType(Enum):
    """Supported command types"""
    PKILL = "pkill"
    REVERSE_SHELL = "reverse-shell"
    CUSTOM = "custom" 


class CliOperation(Enum):
    """CLI operation types"""
    STATIC = "static"   # Analysis agent
    DYNAMIC = "dynamic" # Exploit agent with LLM-driven analysis