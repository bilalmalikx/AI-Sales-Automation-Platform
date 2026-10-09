"""
Input/output schemas for AI agents.

These Pydantic models define the structure for agent inputs and outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Lead Enrichment Agent ─────────────────────────────────────────────────────


@dataclass
class LeadEnrichmentInput:
    """Input for lead enrichment agent."""

    email: str
    company_domain: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass
class LeadEnrichmentOutput:
    """Output from lead enrichment agent."""

    company_name: str | None = None
    company_domain: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    company_description: str | None = None
    job_title: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    location: str | None = None
    confidence_score: float = 0.0
    sources: list[str] | None = None


# ── Company Research Agent ────────────────────────────────────────────────────


@dataclass
class CompanyResearchInput:
    """Input for company research agent."""

    company_name: str
    company_domain: str | None = None
    industry: str | None = None


@dataclass
class CompanyResearchOutput:
    """Output from company research agent."""

    company_description: str | None = None
    industry: str | None = None
    size: str | None = None
    founded_year: int | None = None
    headquarters: str | None = None
    key_products: list[str] | None = None
    recent_news: list[dict[str, str]] | None = (
        None  # [{"title": "...", "date": "...", "summary": "..."}]
    )
    tech_stack: list[str] | None = None
    social_media: dict[str, str] | None = None  # {"linkedin": "...", "twitter": "..."}
    funding_info: str | None = None
    competitors: list[str] | None = None
    confidence_score: float = 0.0


# ── Email Generator Agent ─────────────────────────────────────────────────────


@dataclass
class EmailGeneratorInput:
    """Input for email generator agent."""

    recipient_name: str
    recipient_company: str
    recipient_title: str | None = None
    company_description: str | None = None
    company_industry: str | None = None
    recent_news: str | None = None
    sender_name: str = "Sales Team"
    sender_company: str = "Your Company"
    product_value_prop: str | None = None
    tone: str = "professional"  # professional, casual, friendly
    max_length: int = 200  # words


@dataclass
class EmailGeneratorOutput:
    """Output from email generator agent."""

    subject_line: str
    email_body: str
    call_to_action: str
    personalization_elements: list[str]  # What made it personalized
    estimated_readability_score: float = 0.0  # 0-100, Flesch reading ease
    confidence_score: float = 0.0


# ── Agent Metadata ────────────────────────────────────────────────────────────


@dataclass
class AgentExecutionMetadata:
    """
    Metadata about agent execution for tracking and analytics.

    This can be included in AgentResult.metadata.
    """

    model_used: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    retry_count: int = 0
    cost_estimate: float = 0.0  # USD
    sources_consulted: list[str] | None = None
    errors_encountered: list[str] | None = None
