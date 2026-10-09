"""
AI Agent framework.

All agents inherit from BaseAgent and implement the standard lifecycle:
prepare() → execute() → validate() → cleanup()
"""

from app.agents.base import (
    AgentConfig,
    AgentExecutionContext,
    AgentResult,
    BaseAgent,
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
    "AgentConfig",
    "AgentExecutionContext",
    "AgentResult",
    # Base framework
    "BaseAgent",
    "CompanyResearchAgent",
    "CompanyResearchInput",
    "CompanyResearchOutput",
    "EmailGeneratorAgent",
    "EmailGeneratorInput",
    "EmailGeneratorOutput",
    # AI Agents
    "LeadEnrichmentAgent",
    # Schemas
    "LeadEnrichmentInput",
    "LeadEnrichmentOutput",
]
