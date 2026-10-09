"""Existing agents execute against deterministic LLM responses, never live billing."""

import json

import pytest

from app.agents.base import AgentConfig, AgentResult, BaseAgent
from app.agents.company_research import CompanyResearchAgent
from app.agents.email_generator import EmailGeneratorAgent
from app.agents.lead_enrichment import LeadEnrichmentAgent
from app.agents.schemas import CompanyResearchInput, EmailGeneratorInput, LeadEnrichmentInput


class FakeLLM:
    def __init__(self, output):
        self.output = output

    async def generate(self, **kwargs):
        return json.dumps(self.output), {"model": "test", "latency_ms": 1}


@pytest.mark.parametrize(
    "module,agent,input_data,output",
    [
        (
            "app.agents.lead_enrichment",
            LeadEnrichmentAgent,
            LeadEnrichmentInput(email="alex@example.com"),
            {"company_name": "Example", "company_industry": "Design", "confidence_score": 0.9},
        ),
        (
            "app.agents.company_research",
            CompanyResearchAgent,
            CompanyResearchInput(company_name="Example"),
            {
                "company_description": "An example studio.",
                "industry": "Design",
                "confidence_score": 0.9,
            },
        ),
        (
            "app.agents.email_generator",
            EmailGeneratorAgent,
            EmailGeneratorInput(recipient_name="Alex", recipient_company="Example"),
            {
                "subject_line": "A simpler workflow for Example",
                "email_body": "Hi Alex, we help teams simplify repetitive reporting. Would a short discovery call be useful next week? Best, Sales Team.",
                "call_to_action": "Book a call",
                "personalization_elements": ["Example"],
                "confidence_score": 0.9,
                "estimated_readability_score": 75,
            },
        ),
    ],
)
async def test_agent_execution_and_validation(monkeypatch, module, agent, input_data, output):
    monkeypatch.setattr(module + ".LLMService", lambda **kwargs: FakeLLM(output))
    result = await agent(AgentConfig(max_retries=0)).run(input_data)
    assert result.success, result.error
    assert result.data is not None and result.confidence >= 0.7


class RetryAgent(BaseAgent):
    def __init__(self, fail=False, confidence=0.9):
        super().__init__(
            "test", AgentConfig(max_retries=1, retry_delay=0, confidence_threshold=0.7)
        )
        self.calls = 0
        self.cleaned = False
        self.fail = fail
        self.confidence = confidence

    async def execute_impl(self, value, context):
        self.calls += 1
        if self.fail or self.calls == 1:
            raise ValueError("Temporary error")
        context.metadata["confidence"] = self.confidence
        return {"value": value}

    async def validate_output(self, value, context):
        return value

    async def cleanup_impl(self, context):
        self.cleaned = True


async def test_retry_cleanup_and_confidence_guard():
    success = RetryAgent()
    result = await success.run("test")
    assert result.success and success.calls == 2 and success.cleaned
    failed = RetryAgent(fail=True)
    result = await failed.run("test")
    assert not result.success and failed.cleaned
    low = RetryAgent(confidence=0.1)
    result = await low.run("test")
    assert not result.success and "confidence" in result.error


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": 3},
        {"max_tokens": 0},
        {"timeout": 0},
        {"max_retries": -1},
        {"confidence_threshold": 2},
    ],
)
def test_agent_configuration_validation(kwargs):
    with pytest.raises(ValueError):
        AgentConfig(**kwargs)


def test_agent_result_consistency():
    with pytest.raises(ValueError):
        AgentResult(success=True)
    with pytest.raises(ValueError):
        AgentResult(success=False)
    with pytest.raises(ValueError):
        AgentResult(success=True, data={}, confidence=2)
