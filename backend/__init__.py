"""
Nexus Cortex — Backend Package
Enterprise Multi-Agent Data Analytics Platform
Powered by Ollama (llama3.2:latest)
"""

__version__ = "3.2.0"
__author__ = "Nexus Cortex Team"

from strict_prompts import AGENT_PROMPTS, validate_query_scope
from ram_optimizer import get_active_sub_agent_count, RAMProfile
from rag_mcp import (
    parse_csv_datasheet,
    extract_structured_context,
    RagContext,
)
from ai_engine import (
    AgentOrchestrator,
    MainAgent,
    SubAgent,
    AgentResponse,
)

__all__ = [
    "AGENT_PROMPTS",
    "validate_query_scope",
    "get_active_sub_agent_count",
    "RAMProfile",
    "parse_csv_datasheet",
    "extract_structured_context",
    "RagContext",
    "AgentOrchestrator",
    "MainAgent",
    "SubAgent",
    "AgentResponse",
]
