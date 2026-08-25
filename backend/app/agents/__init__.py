"""
AI Agent framework.

All agents inherit from BaseAgent and implement the standard lifecycle:
prepare() → execute() → validate() → cleanup()
"""

from app.agents.base import (
    BaseAgent,
    AgentConfig,
    AgentResult,
    AgentExecutionContext,
)
from app.agents.company_research import CompanyResearchAgent
from app.agents.email_generator import EmailGeneratorAgent
from app.agents.lead_enrichment import LeadEnrichmentAgent
from app.agents.schemas import (
    CompanyResearchInput,
    CompanyResearchOutput,
    EmailGeneratorInput,
    EmailGeneratorOutput,
    LeadEnrichmentInput,
    LeadEnrichmentOutput,
)

__all__ = [
    # Base framework
    "BaseAgent",
    "AgentConfig",
    "AgentResult",
    "AgentExecutionContext",
    # AI Agents
    "LeadEnrichmentAgent",
    "CompanyResearchAgent",
    "EmailGeneratorAgent",
    # Schemas
    "LeadEnrichmentInput",
    "LeadEnrichmentOutput",
    "CompanyResearchInput",
    "CompanyResearchOutput",
    "EmailGeneratorInput",
    "EmailGeneratorOutput",
]
