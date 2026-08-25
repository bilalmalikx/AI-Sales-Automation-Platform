"""
Lead Enrichment Agent - enriches lead data from email and company domain.

Uses LLM to research and enrich lead information based on limited input.
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent, AgentConfig, AgentExecutionContext
from app.agents.schemas import LeadEnrichmentInput, LeadEnrichmentOutput
from app.core.config import settings
from app.services.llm import LLMService


class LeadEnrichmentAgent(BaseAgent[LeadEnrichmentInput, LeadEnrichmentOutput]):
    """
    Agent that enriches lead data from email and company domain.
    
    Capabilities:
    - Extract company name from domain
    - Infer job title from email/name patterns
    - Research company industry and size
    - Generate confidence scores
    
    Note: This is a mock implementation using LLM reasoning.
    In production, this would integrate with:
    - Clearbit, ZoomInfo, or similar enrichment APIs
    - LinkedIn Sales Navigator
    - Company databases
    """
    
    def __init__(self, config: AgentConfig | None = None):
        """Initialize lead enrichment agent."""
        super().__init__(name="lead_enrichment_agent", config=config)
        
        # Initialize LLM service
        self.llm_service = LLMService(
            model=settings.OPENAI_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    
    async def prepare_impl(
        self,
        input_data: LeadEnrichmentInput,
        context: AgentExecutionContext,
    ) -> None:
        """Validate input data."""
        if not input_data.email:
            raise ValueError("Email is required for lead enrichment")
        
        # Validate email format (basic)
        if "@" not in input_data.email:
            raise ValueError("Invalid email format")
        
        context.metadata["email_domain"] = input_data.email.split("@")[1]
        context.metadata["has_company_domain"] = input_data.company_domain is not None
    
    async def execute_impl(
        self,
        input_data: LeadEnrichmentInput,
        context: AgentExecutionContext,
    ) -> LeadEnrichmentOutput:
        """Enrich lead data using LLM reasoning."""
        
        # Build enrichment prompt
        system_message = """You are a B2B lead enrichment specialist. Given limited information about a lead, 
you research and infer additional details based on patterns and business context.

Provide your response in JSON format with these fields:
{
  "company_name": "Company name",
  "company_domain": "company.com",
  "company_industry": "Industry name",
  "company_size": "1-10|11-50|51-200|201-1000|1000+",
  "company_description": "Brief description",
  "job_title": "Inferred job title",
  "linkedin_url": "LinkedIn profile URL if inferable",
  "phone": "Phone number if available",
  "location": "City, Country",
  "confidence_score": 0.0-1.0,
  "sources": ["source1", "source2"]
}

Be realistic - if you cannot confidently infer something, use null. Confidence score should reflect certainty."""
        
        prompt = f"""Enrich this lead:

Email: {input_data.email}
Company Domain: {input_data.company_domain or 'Not provided'}
First Name: {input_data.first_name or 'Not provided'}
Last Name: {input_data.last_name or 'Not provided'}

Based on the email domain and available information, provide enriched data."""
        
        # Generate enrichment
        response, llm_metadata = await self.llm_service.generate(
            prompt=prompt,
            system_message=system_message,
        )
        
        # Parse JSON response
        try:
            enriched_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                enriched_data = json.loads(json_match.group())
            else:
                raise ValueError("LLM response is not valid JSON")
        
        # Build output
        output = LeadEnrichmentOutput(
            company_name=enriched_data.get("company_name"),
            company_domain=enriched_data.get("company_domain") or input_data.company_domain,
            company_industry=enriched_data.get("company_industry"),
            company_size=enriched_data.get("company_size"),
            company_description=enriched_data.get("company_description"),
            job_title=enriched_data.get("job_title"),
            linkedin_url=enriched_data.get("linkedin_url"),
            phone=enriched_data.get("phone"),
            location=enriched_data.get("location"),
            confidence_score=enriched_data.get("confidence_score", 0.5),
            sources=enriched_data.get("sources", ["LLM reasoning"]),
        )
        
        # Track metadata
        context.metadata["confidence"] = output.confidence_score
        context.metadata["model_used"] = llm_metadata["model"]
        context.metadata["latency_ms"] = llm_metadata["latency_ms"]
        context.metadata["fields_enriched"] = sum(
            1 for field in [
                output.company_name,
                output.company_industry,
                output.job_title,
                output.location,
            ] if field
        )
        
        return output
    
    async def validate_output(
        self,
        output: LeadEnrichmentOutput,
        context: AgentExecutionContext,
    ) -> LeadEnrichmentOutput:
        """Validate enriched data."""
        
        # Validate confidence score
        if not 0.0 <= output.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        
        # At least one field should be enriched
        fields_enriched = context.metadata.get("fields_enriched", 0)
        if fields_enriched == 0:
            raise ValueError("No fields were enriched")
        
        context.metadata["validation_passed"] = True
        
        return output
