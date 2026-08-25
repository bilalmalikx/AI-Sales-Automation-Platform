"""
Test script for Phase 5 AI agents.

Tests LeadEnrichmentAgent, CompanyResearchAgent, and EmailGeneratorAgent.

Note: Requires OPENAI_API_KEY environment variable to be set.
Run with: python -m app.agents.test_ai_agents
"""

import asyncio
import os

from app.agents import (
    AgentConfig,
    CompanyResearchAgent,
    CompanyResearchInput,
    EmailGeneratorAgent,
    EmailGeneratorInput,
    LeadEnrichmentAgent,
    LeadEnrichmentInput,
)


async def test_lead_enrichment():
    """Test lead enrichment agent."""
    print("\n" + "=" * 70)
    print("TEST 1: LEAD ENRICHMENT AGENT")
    print("=" * 70)
    
    agent = LeadEnrichmentAgent(
        config=AgentConfig(
            temperature=0.1,
            confidence_threshold=0.5,
            max_retries=2,
        )
    )
    
    # Test case 1: Real company email
    print("\n[Case 1] Enrich lead with company email")
    print("-" * 70)
    
    input_data = LeadEnrichmentInput(
        email="john.doe@microsoft.com",
        first_name="John",
        last_name="Doe",
        company_domain="microsoft.com",
    )
    
    result = await agent.run(input_data)
    
    if result.success:
        print(f"✅ Success")
        print(f"   Company: {result.data.company_name}")
        print(f"   Industry: {result.data.company_industry}")
        print(f"   Size: {result.data.company_size}")
        print(f"   Job Title: {result.data.job_title}")
        print(f"   Location: {result.data.location}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Fields Enriched: {result.metadata.get('fields_enriched')}")
    else:
        print(f"❌ Failed: {result.error}")
    
    # Test case 2: Startup email
    print("\n[Case 2] Enrich lead from startup")
    print("-" * 70)
    
    input_data2 = LeadEnrichmentInput(
        email="sarah@techstartup.io",
        first_name="Sarah",
        company_domain="techstartup.io",
    )
    
    result2 = await agent.run(input_data2)
    
    if result2.success:
        print(f"✅ Success")
        print(f"   Company: {result2.data.company_name}")
        print(f"   Industry: {result2.data.company_industry}")
        print(f"   Confidence: {result2.confidence:.2f}")
    else:
        print(f"❌ Failed: {result2.error}")


async def test_company_research():
    """Test company research agent."""
    print("\n" + "=" * 70)
    print("TEST 2: COMPANY RESEARCH AGENT")
    print("=" * 70)
    
    agent = CompanyResearchAgent(
        config=AgentConfig(
            temperature=0.1,
            confidence_threshold=0.5,
            max_retries=2,
        )
    )
    
    # Test case: Research a well-known company
    print("\n[Case 1] Research established company")
    print("-" * 70)
    
    input_data = CompanyResearchInput(
        company_name="Salesforce",
        company_domain="salesforce.com",
        industry="CRM Software",
    )
    
    result = await agent.run(input_data)
    
    if result.success:
        print(f"✅ Success")
        print(f"   Description: {result.data.company_description[:100]}...")
        print(f"   Industry: {result.data.industry}")
        print(f"   Size: {result.data.size}")
        print(f"   Founded: {result.data.founded_year}")
        print(f"   HQ: {result.data.headquarters}")
        print(f"   Key Products: {', '.join(result.data.key_products[:3]) if result.data.key_products else 'N/A'}")
        print(f"   Recent News: {len(result.data.recent_news or [])} articles")
        print(f"   Tech Stack: {', '.join(result.data.tech_stack[:3]) if result.data.tech_stack else 'N/A'}")
        print(f"   Competitors: {', '.join(result.data.competitors[:3]) if result.data.competitors else 'N/A'}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Data Points: {result.metadata.get('data_points_found')}")
    else:
        print(f"❌ Failed: {result.error}")


async def test_email_generator():
    """Test email generator agent."""
    print("\n" + "=" * 70)
    print("TEST 3: EMAIL GENERATOR AGENT")
    print("=" * 70)
    
    agent = EmailGeneratorAgent(
        config=AgentConfig(
            temperature=0.8,  # More creative
            confidence_threshold=0.6,
            max_retries=2,
        )
    )
    
    # Test case: Generate email for enterprise prospect
    print("\n[Case 1] Generate professional email")
    print("-" * 70)
    
    input_data = EmailGeneratorInput(
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
    
    result = await agent.run(input_data)
    
    if result.success:
        print(f"✅ Success\n")
        print(f"Subject: {result.data.subject_line}\n")
        print("Body:")
        print("-" * 70)
        print(result.data.email_body)
        print("-" * 70)
        print(f"\nCTA: {result.data.call_to_action}")
        print(f"\nPersonalization: {', '.join(result.data.personalization_elements)}")
        print(f"Readability Score: {result.data.estimated_readability_score:.1f}")
        print(f"Word Count: {result.metadata.get('email_length_words')}")
        print(f"Confidence: {result.confidence:.2f}")
    else:
        print(f"❌ Failed: {result.error}")
    
    # Test case 2: Casual tone
    print("\n[Case 2] Generate casual tone email")
    print("-" * 70)
    
    input_data2 = EmailGeneratorInput(
        recipient_name="Mike Chen",
        recipient_title="Founder",
        recipient_company="StartupXYZ",
        company_description="Early-stage SaaS startup",
        sender_name="Sarah",
        sender_company="Growth Tools",
        tone="casual",
        max_length=100,
    )
    
    result2 = await agent.run(input_data2)
    
    if result2.success:
        print(f"✅ Success")
        print(f"Subject: {result2.data.subject_line}")
        print(f"Tone: Casual")
        print(f"Confidence: {result2.confidence:.2f}")
    else:
        print(f"❌ Failed: {result2.error}")


async def test_full_workflow():
    """Test full workflow: enrich → research → email."""
    print("\n" + "=" * 70)
    print("TEST 4: FULL WORKFLOW (Enrich → Research → Email)")
    print("=" * 70)
    
    # Step 1: Enrich lead
    print("\n[Step 1] Enriching lead...")
    print("-" * 70)
    
    enrichment_agent = LeadEnrichmentAgent()
    enrich_result = await enrichment_agent.run(
        LeadEnrichmentInput(
            email="cto@innovatetech.com",
            first_name="David",
            company_domain="innovatetech.com",
        )
    )
    
    if not enrich_result.success:
        print(f"❌ Enrichment failed: {enrich_result.error}")
        return
    
    print(f"✅ Lead enriched")
    print(f"   Company: {enrich_result.data.company_name}")
    print(f"   Title: {enrich_result.data.job_title}")
    
    # Step 2: Research company
    print("\n[Step 2] Researching company...")
    print("-" * 70)
    
    research_agent = CompanyResearchAgent()
    research_result = await research_agent.run(
        CompanyResearchInput(
            company_name=enrich_result.data.company_name or "InnovateTech",
            company_domain=enrich_result.data.company_domain,
            industry=enrich_result.data.company_industry,
        )
    )
    
    if not research_result.success:
        print(f"❌ Research failed: {research_result.error}")
        return
    
    print(f"✅ Company researched")
    print(f"   Industry: {research_result.data.industry}")
    print(f"   Size: {research_result.data.size}")
    
    # Step 3: Generate email
    print("\n[Step 3] Generating personalized email...")
    print("-" * 70)
    
    email_agent = EmailGeneratorAgent()
    email_result = await email_agent.run(
        EmailGeneratorInput(
            recipient_name="David",
            recipient_title=enrich_result.data.job_title or "CTO",
            recipient_company=enrich_result.data.company_name or "InnovateTech",
            company_description=research_result.data.company_description,
            company_industry=research_result.data.industry,
            recent_news=", ".join([n.get("title", "") for n in (research_result.data.recent_news or [])[:2]]),
            sender_name="Alex",
            sender_company="AI Platform",
            product_value_prop="AI-powered sales automation",
            tone="professional",
            max_length=150,
        )
    )
    
    if not email_result.success:
        print(f"❌ Email generation failed: {email_result.error}")
        return
    
    print(f"✅ Email generated\n")
    print(f"Subject: {email_result.data.subject_line}\n")
    print("Body:")
    print("-" * 70)
    print(email_result.data.email_body)
    print("-" * 70)
    
    print("\n📊 WORKFLOW SUMMARY")
    print(f"   Total Time: {enrich_result.metadata.get('elapsed_time', 0) + research_result.metadata.get('elapsed_time', 0) + email_result.metadata.get('elapsed_time', 0):.2f}s")
    print(f"   Avg Confidence: {(enrich_result.confidence + research_result.confidence + email_result.confidence) / 3:.2f}")


async def main():
    """Run all agent tests."""
    print("\n" + "=" * 70)
    print("PHASE 5: AI AGENTS TEST SUITE")
    print("=" * 70)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY environment variable not set!")
        print("   Tests will fail without a valid API key.")
        print("   Set it with: export OPENAI_API_KEY='your-key-here'\n")
        return
    
    try:
        # Run individual agent tests
        await test_lead_enrichment()
        await test_company_research()
        await test_email_generator()
        
        # Run full workflow
        await test_full_workflow()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
