"""
Mock test for AI agents (no API key required).

Tests agent framework with mock LLM responses.
Run with: python -m app.agents.test_ai_agents_mock
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from app.agents import (
    AgentConfig,
    CompanyResearchAgent,
    CompanyResearchInput,
    EmailGeneratorAgent,
    EmailGeneratorInput,
    LeadEnrichmentAgent,
    LeadEnrichmentInput,
)


# Mock LLM responses
MOCK_LEAD_ENRICHMENT_RESPONSE = json.dumps({
    "company_name": "Microsoft Corporation",
    "company_domain": "microsoft.com",
    "company_industry": "Technology / Cloud Computing",
    "company_size": "10000+",
    "company_description": "Global technology company providing software, cloud services, and hardware",
    "job_title": "Senior Software Engineer",
    "linkedin_url": "https://linkedin.com/in/johndoe",
    "phone": None,
    "location": "Redmond, WA, USA",
    "confidence_score": 0.85,
    "sources": ["Email domain analysis", "Company database"]
})

MOCK_COMPANY_RESEARCH_RESPONSE = json.dumps({
    "company_description": "Salesforce is a leading customer relationship management (CRM) platform that helps businesses connect with customers through cloud-based solutions.",
    "industry": "CRM Software / Cloud Computing",
    "size": "10000+",
    "founded_year": 1999,
    "headquarters": "San Francisco, CA, USA",
    "key_products": ["Sales Cloud", "Service Cloud", "Marketing Cloud"],
    "recent_news": [
        {"title": "Salesforce announces AI integration", "date": "2026-08-15", "summary": "New AI features for CRM"},
        {"title": "Q2 earnings beat expectations", "date": "2026-08-01", "summary": "Strong growth in cloud revenue"}
    ],
    "tech_stack": ["Java", "Apex", "Lightning Web Components", "Heroku"],
    "social_media": {
        "linkedin": "https://linkedin.com/company/salesforce",
        "twitter": "https://twitter.com/salesforce"
    },
    "funding_info": "Public company (NYSE: CRM), market cap $250B",
    "competitors": ["Microsoft Dynamics", "HubSpot", "Oracle CX"],
    "confidence_score": 0.9
})

MOCK_EMAIL_RESPONSE = json.dumps({
    "subject_line": "Quick question about TechCorp's sales automation",
    "email_body": """Hi Jane,

I noticed TechCorp recently raised $50M Series C—congratulations! As your team scales, managing sales processes can become complex.

We help cloud infrastructure companies like yours automate repetitive sales tasks, and our customers typically see 3x conversion rate improvements within 90 days.

Would you be open to a quick 15-minute call next week to explore if this could help TechCorp's growth?

Best regards,
Alex Johnson
AI Sales Platform""",
    "call_to_action": "Schedule a 15-minute discovery call",
    "personalization_elements": [
        "Recent $50M funding",
        "VP of Sales title",
        "Cloud infrastructure industry",
        "TechCorp company name"
    ],
    "estimated_readability_score": 72.0,
    "confidence_score": 0.88
})


async def test_with_mock():
    """Test all agents with mock LLM responses."""
    
    print("=" * 70)
    print("PHASE 5: AI AGENTS MOCK TEST (No API Key Required)")
    print("=" * 70)
    
    # Patch both LLMService initialization and generate method
    with patch('app.agents.lead_enrichment.LLMService'), \
         patch('app.agents.company_research.LLMService'), \
         patch('app.agents.email_generator.LLMService'), \
         patch('app.services.llm.LLMService.generate') as mock_generate:
        
        # Configure mock to return different responses
        mock_generate.return_value = AsyncMock()
        
        # Test 1: Lead Enrichment
        print("\n[TEST 1] Lead Enrichment Agent")
        print("-" * 70)
        
        mock_generate.return_value = (
            MOCK_LEAD_ENRICHMENT_RESPONSE,
            {"model": "gpt-4o", "latency_ms": 1200.0, "prompt_length": 150, "response_length": 500}
        )
        
        agent1 = LeadEnrichmentAgent(
            config=AgentConfig(confidence_threshold=0.5)
        )
        
        result1 = await agent1.run(
            LeadEnrichmentInput(
                email="john.doe@microsoft.com",
                first_name="John",
                last_name="Doe",
                company_domain="microsoft.com",
            )
        )
        
        if result1.success:
            print("✅ Success")
            print(f"   Company: {result1.data.company_name}")
            print(f"   Industry: {result1.data.company_industry}")
            print(f"   Size: {result1.data.company_size}")
            print(f"   Job Title: {result1.data.job_title}")
            print(f"   Location: {result1.data.location}")
            print(f"   Confidence: {result1.confidence:.2f}")
            print(f"   Execution Time: {result1.metadata.get('elapsed_time', 0):.3f}s")
        else:
            print(f"❌ Failed: {result1.error}")
        
        # Test 2: Company Research
        print("\n[TEST 2] Company Research Agent")
        print("-" * 70)
        
        mock_generate.return_value = (
            MOCK_COMPANY_RESEARCH_RESPONSE,
            {"model": "gpt-4o", "latency_ms": 1500.0, "prompt_length": 200, "response_length": 800}
        )
        
        agent2 = CompanyResearchAgent(
            config=AgentConfig(confidence_threshold=0.5)
        )
        
        result2 = await agent2.run(
            CompanyResearchInput(
                company_name="Salesforce",
                company_domain="salesforce.com",
                industry="CRM Software",
            )
        )
        
        if result2.success:
            print("✅ Success")
            print(f"   Description: {result2.data.company_description[:80]}...")
            print(f"   Industry: {result2.data.industry}")
            print(f"   Size: {result2.data.size}")
            print(f"   Founded: {result2.data.founded_year}")
            print(f"   HQ: {result2.data.headquarters}")
            print(f"   Products: {', '.join(result2.data.key_products or [])}")
            print(f"   Recent News: {len(result2.data.recent_news or [])} articles")
            print(f"   Confidence: {result2.confidence:.2f}")
        else:
            print(f"❌ Failed: {result2.error}")
        
        # Test 3: Email Generator
        print("\n[TEST 3] Email Generator Agent")
        print("-" * 70)
        
        mock_generate.return_value = (
            MOCK_EMAIL_RESPONSE,
            {"model": "gpt-4o", "latency_ms": 1800.0, "prompt_length": 300, "response_length": 400}
        )
        
        agent3 = EmailGeneratorAgent(
            config=AgentConfig(confidence_threshold=0.6)
        )
        
        result3 = await agent3.run(
            EmailGeneratorInput(
                recipient_name="Jane Smith",
                recipient_title="VP of Sales",
                recipient_company="TechCorp Inc",
                company_description="Enterprise software company specializing in cloud infrastructure",
                company_industry="Cloud Computing",
                recent_news="Recently raised $50M Series C funding",
                sender_name="Alex Johnson",
                sender_company="AI Sales Platform",
                product_value_prop="AI-powered sales automation that increases conversion rates by 3x",
                tone="professional",
                max_length=150,
            )
        )
        
        if result3.success:
            print("✅ Success\n")
            print(f"Subject: {result3.data.subject_line}\n")
            print("Body:")
            print("-" * 70)
            print(result3.data.email_body)
            print("-" * 70)
            print(f"\nCTA: {result3.data.call_to_action}")
            print(f"Personalization: {len(result3.data.personalization_elements)} elements")
            print(f"Readability: {result3.data.estimated_readability_score:.1f}")
            print(f"Confidence: {result3.confidence:.2f}")
        else:
            print(f"❌ Failed: {result3.error}")
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ ALL MOCK TESTS COMPLETED")
        print("=" * 70)
        print(f"\nSummary:")
        print(f"  Lead Enrichment:  {'✅' if result1.success else '❌'} (confidence: {result1.confidence:.2f})")
        print(f"  Company Research: {'✅' if result2.success else '❌'} (confidence: {result2.confidence:.2f})")
        print(f"  Email Generator:  {'✅' if result3.success else '❌'} (confidence: {result3.confidence:.2f})")
        
        total_time = (
            result1.metadata.get('elapsed_time', 0) +
            result2.metadata.get('elapsed_time', 0) +
            result3.metadata.get('elapsed_time', 0)
        )
        print(f"  Total Execution:  {total_time:.3f}s")
        
        print("\n💡 To test with real LLM:")
        print("   1. Set OPENAI_API_KEY environment variable")
        print("   2. Run: python -m app.agents.test_ai_agents")


if __name__ == "__main__":
    asyncio.run(test_with_mock())
