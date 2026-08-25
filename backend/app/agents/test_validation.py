"""
Simple validation test for AI agents (no LLM calls required).

Tests agent structure and framework integration.
Run with: python -m app.agents.test_validation
"""

import asyncio

from app.agents import (
    AgentConfig,
    CompanyResearchInput,
    EmailGeneratorInput,
    LeadEnrichmentInput,
)
from app.agents.base import AgentResult


async def main():
    """Validate agent framework structure."""
    
    print("=" * 70)
    print("PHASE 5: AI AGENTS VALIDATION TEST")
    print("=" * 70)
    
    tests_passed = []
    tests_failed = []
    
    # Test 1: Agent schemas validation
    print("\n[TEST 1] Agent Schemas")
    print("-" * 70)
    
    try:
        # Lead enrichment input
        lead_input = LeadEnrichmentInput(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            company_domain="example.com",
        )
        assert lead_input.email == "test@example.com"
        print("✅ LeadEnrichmentInput schema valid")
        tests_passed.append("LeadEnrichmentInput")
        
        # Company research input
        company_input = CompanyResearchInput(
            company_name="Test Corp",
            company_domain="testcorp.com",
            industry="Technology",
        )
        assert company_input.company_name == "Test Corp"
        print("✅ CompanyResearchInput schema valid")
        tests_passed.append("CompanyResearchInput")
        
        # Email generator input
        email_input = EmailGeneratorInput(
            recipient_name="Jane",
            recipient_company="ACME Inc",
            recipient_title="CEO",
            tone="professional",
        )
        assert email_input.recipient_name == "Jane"
        assert email_input.tone == "professional"
        print("✅ EmailGeneratorInput schema valid")
        tests_passed.append("EmailGeneratorInput")
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        tests_failed.append("Schemas")
    
    # Test 2: AgentConfig validation
    print("\n[TEST 2] AgentConfig")
    print("-" * 70)
    
    try:
        config = AgentConfig(
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000,
            timeout=60,
            max_retries=3,
            confidence_threshold=0.7,
        )
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.confidence_threshold == 0.7
        print("✅ AgentConfig validation passed")
        tests_passed.append("AgentConfig")
        
        # Test invalid temperature
        try:
            bad_config = AgentConfig(temperature=3.0)
            print("❌ Should have rejected invalid temperature")
            tests_failed.append("AgentConfig validation")
        except ValueError:
            print("✅ Temperature validation working")
            tests_passed.append("AgentConfig validation")
        
    except Exception as e:
        print(f"❌ AgentConfig test failed: {e}")
        tests_failed.append("AgentConfig")
    
    # Test 3: AgentResult structure
    print("\n[TEST 3] AgentResult")
    print("-" * 70)
    
    try:
        # Successful result
        success_result = AgentResult(
            success=True,
            data={"test": "data"},
            confidence=0.95,
            metadata={"model": "gpt-4"},
            agent_name="test_agent",
        )
        assert success_result.success is True
        assert success_result.data == {"test": "data"}
        assert success_result.confidence == 0.95
        print("✅ AgentResult (success) structure valid")
        tests_passed.append("AgentResult success")
        
        # Failed result
        failed_result = AgentResult(
            success=False,
            error="Test error",
            confidence=0.0,
            agent_name="test_agent",
        )
        assert failed_result.success is False
        assert failed_result.error == "Test error"
        print("✅ AgentResult (failure) structure valid")
        tests_passed.append("AgentResult failure")
        
    except Exception as e:
        print(f"❌ AgentResult test failed: {e}")
        tests_failed.append("AgentResult")
    
    # Test 4: Import all agents
    print("\n[TEST 4] Agent Imports")
    print("-" * 70)
    
    try:
        from app.agents import (
            CompanyResearchAgent,
            EmailGeneratorAgent,
            LeadEnrichmentAgent,
        )
        
        # Check they can be instantiated
        lead_agent = LeadEnrichmentAgent(config=AgentConfig())
        assert lead_agent.name == "lead_enrichment_agent"
        print("✅ LeadEnrichmentAgent imported and instantiable")
        tests_passed.append("LeadEnrichmentAgent import")
        
        research_agent = CompanyResearchAgent(config=AgentConfig())
        assert research_agent.name == "company_research_agent"
        print("✅ CompanyResearchAgent imported and instantiable")
        tests_passed.append("CompanyResearchAgent import")
        
        email_agent = EmailGeneratorAgent(config=AgentConfig())
        assert email_agent.name == "email_generator_agent"
        print("✅ EmailGeneratorAgent imported and instantiable")
        tests_passed.append("EmailGeneratorAgent import")
        
    except Exception as e:
        print(f"❌ Agent import failed: {e}")
        tests_failed.append("Agent imports")
    
    # Test 5: LLMService structure
    print("\n[TEST 5] LLMService")
    print("-" * 70)
    
    try:
        from app.services.llm import LLMService
        
        # Check it can be imported
        print("✅ LLMService imported successfully")
        tests_passed.append("LLMService import")
        
        # Check cost estimation
        service = LLMService(model="gpt-4")
        cost = service.estimate_cost(input_tokens=1000, output_tokens=500)
        assert cost > 0
        print(f"✅ Cost estimation working (1k input + 500 output ≈ ${cost:.4f})")
        tests_passed.append("LLMService cost estimation")
        
    except Exception as e:
        print(f"❌ LLMService test failed: {e}")
        tests_failed.append("LLMService")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"\n✅ Passed: {len(tests_passed)}")
    for test in tests_passed:
        print(f"   • {test}")
    
    if tests_failed:
        print(f"\n❌ Failed: {len(tests_failed)}")
        for test in tests_failed:
            print(f"   • {test}")
    else:
        print("\n🎉 All validation tests passed!")
    
    print(f"\nTotal: {len(tests_passed)}/{len(tests_passed) + len(tests_failed)} tests passed")
    
    print("\n💡 Next steps:")
    print("   • Set OPENAI_API_KEY to test with real LLM")
    print("   • Run: python -m app.agents.test_ai_agents")
    print("   • Agents are ready for Phase 6 (Workflows)")
    
    return len(tests_failed) == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
