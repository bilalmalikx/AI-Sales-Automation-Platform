"""
Company Research Agent - researches company background and details.

Uses LLM to gather company information for personalized outreach.
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent, AgentConfig, AgentExecutionContext
from app.agents.schemas import CompanyResearchInput, CompanyResearchOutput
from app.core.config import settings
from app.services.llm import LLMService


class CompanyResearchAgent(BaseAgent[CompanyResearchInput, CompanyResearchOutput]):
    """
    Agent that researches company background and details.
    
    Capabilities:
    - Company description and overview
    - Industry classification
    - Size and growth stage
    - Recent news and updates
    - Tech stack and tools
    - Competitive landscape
    
    Note: This is a mock implementation using LLM knowledge.
    In production, this would integrate with:
    - Crunchbase API
    - BuiltWith/Wappalyzer for tech stack
    - News APIs (Google News, NewsAPI)
    - LinkedIn Company Pages
    - SEC filings for public companies
    """
    
    def __init__(self, config: AgentConfig | None = None):
        """Initialize company research agent."""
        super().__init__(name="company_research_agent", config=config)
        
        # Initialize LLM service
        self.llm_service = LLMService(
            model=settings.OPENAI_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    
    async def prepare_impl(
        self,
        input_data: CompanyResearchInput,
        context: AgentExecutionContext,
    ) -> None:
        """Validate input data."""
        if not input_data.company_name:
            raise ValueError("Company name is required")
        
        context.metadata["company_name"] = input_data.company_name
        context.metadata["has_domain"] = input_data.company_domain is not None
    
    async def execute_impl(
        self,
        input_data: CompanyResearchInput,
        context: AgentExecutionContext,
    ) -> CompanyResearchOutput:
        """Research company using LLM knowledge."""
        
        # Build research prompt
        system_message = """You are a B2B company research analyst. Given a company name and optional details,
provide comprehensive research to help sales teams understand the company.

Provide your response in JSON format with these fields:
{
  "company_description": "2-3 sentence overview",
  "industry": "Primary industry",
  "size": "1-10|11-50|51-200|201-1000|1000+|10000+",
  "founded_year": 2020,
  "headquarters": "City, Country",
  "key_products": ["product1", "product2"],
  "recent_news": [
    {"title": "News title", "date": "2026-08-01", "summary": "Brief summary"}
  ],
  "tech_stack": ["technology1", "technology2"],
  "social_media": {
    "linkedin": "url",
    "twitter": "url"
  },
  "funding_info": "Funding stage and amount",
  "competitors": ["competitor1", "competitor2"],
  "confidence_score": 0.0-1.0
}

Be factual and realistic. If uncertain, indicate lower confidence. Recent news should be realistic."""
        
        prompt = f"""Research this company:

Company Name: {input_data.company_name}
Company Domain: {input_data.company_domain or 'Not provided'}
Industry: {input_data.industry or 'Not provided'}

Provide comprehensive research data for B2B sales context."""
        
        # Generate research
        response, llm_metadata = await self.llm_service.generate(
            prompt=prompt,
            system_message=system_message,
        )
        
        # Parse JSON response
        try:
            research_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                research_data = json.loads(json_match.group())
            else:
                raise ValueError("LLM response is not valid JSON")
        
        # Build output
        output = CompanyResearchOutput(
            company_description=research_data.get("company_description"),
            industry=research_data.get("industry"),
            size=research_data.get("size"),
            founded_year=research_data.get("founded_year"),
            headquarters=research_data.get("headquarters"),
            key_products=research_data.get("key_products", []),
            recent_news=research_data.get("recent_news", []),
            tech_stack=research_data.get("tech_stack", []),
            social_media=research_data.get("social_media", {}),
            funding_info=research_data.get("funding_info"),
            competitors=research_data.get("competitors", []),
            confidence_score=research_data.get("confidence_score", 0.5),
        )
        
        # Track metadata
        context.metadata["confidence"] = output.confidence_score
        context.metadata["model_used"] = llm_metadata["model"]
        context.metadata["latency_ms"] = llm_metadata["latency_ms"]
        context.metadata["data_points_found"] = (
            len(output.key_products or []) +
            len(output.recent_news or []) +
            len(output.tech_stack or []) +
            len(output.competitors or [])
        )
        
        return output
    
    async def validate_output(
        self,
        output: CompanyResearchOutput,
        context: AgentExecutionContext,
    ) -> CompanyResearchOutput:
        """Validate research data."""
        
        # Validate confidence score
        if not 0.0 <= output.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        
        # Must have at least description
        if not output.company_description:
            raise ValueError("Company description is required")
        
        # Validate founded year if provided
        if output.founded_year and (output.founded_year < 1800 or output.founded_year > 2030):
            raise ValueError(f"Invalid founded year: {output.founded_year}")
        
        context.metadata["validation_passed"] = True
        
        return output
