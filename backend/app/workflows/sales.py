"""LangGraph pipeline with database checkpoints and mandatory human email approval."""

from dataclasses import asdict
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base import AgentConfig
from app.core.config import settings
from app.core.exceptions import ExternalServiceException


class State(TypedDict, total=False):
    enrichment: dict
    research: dict
    draft: dict


async def generate(lead: dict, campaign: dict, prefs: dict, checkpoint: dict, persist) -> dict:
    local = settings.AI_PROVIDER == "local"
    config = AgentConfig(
        model=settings.OPENAI_MODEL,
        timeout=settings.AGENT_DEFAULT_TIMEOUT_SECONDS,
        max_retries=settings.AGENT_MAX_RETRIES,
        confidence_threshold=0,
    )

    async def enrich(state):
        if "enrichment" in state:
            return {}
        if lead.get("website_research"):
            result = {
                "company_name": lead["company"],
                "confidence_score": 1,
                "sources": ["Public website evidence"],
            }
        elif local:
            result = {
                "company_name": lead["company"],
                "company_industry": lead.get("industry"),
                "job_title": lead.get("title"),
                "confidence_score": 0.8,
                "sources": ["Local deterministic test provider; not verified research"],
            }
        else:
            from app.agents.lead_enrichment import LeadEnrichmentAgent
            from app.agents.schemas import LeadEnrichmentInput

            result = await LeadEnrichmentAgent(config).run(
                LeadEnrichmentInput(
                    email=lead["email"],
                    company_domain=lead.get("domain"),
                    first_name=lead.get("first_name"),
                    last_name=lead.get("last_name"),
                )
            )
            if not result.success:
                raise ExternalServiceException("Lead enrichment failed")
            result = asdict(result.data)
            result["sources"] = ["LLM inference; not externally verified"]
        await persist("enrichment", result)
        return {"enrichment": result}

    async def research(state):
        if "research" in state:
            return {}
        if lead.get("website_research"):
            result = {**lead["website_research"], "confidence_score": 1, "verified": False}
        elif local:
            result = {
                "company_description": f"Local test context for {lead['company']}; no external research was performed.",
                "industry": lead.get("industry"),
                "confidence_score": 0.8,
                "verified": False,
            }
        else:
            from app.agents.company_research import CompanyResearchAgent
            from app.agents.schemas import CompanyResearchInput

            result = await CompanyResearchAgent(config).run(
                CompanyResearchInput(
                    company_name=lead["company"],
                    company_domain=lead.get("domain"),
                    industry=lead.get("industry"),
                )
            )
            if not result.success:
                raise ExternalServiceException("Company research failed")
            result = asdict(result.data)
            result["verified"] = False
        await persist("research", result)
        return {"research": result}

    async def draft(state):
        if "draft" in state:
            return {}
        if local:
            result = {
                "subject_line": f"A simpler workflow for {lead['company']}",
                "email_body": f"Hi {lead['name']},\n\n{campaign['offer']}\n\nWould a short conversation next week be useful?\n\nBest,\n{prefs['sender']}",
                "confidence_score": 0.8,
            }
        else:
            from app.agents.email_generator import EmailGeneratorAgent
            from app.agents.schemas import EmailGeneratorInput

            # Restrict personalization to operator-provided facts. Inferred news is not fact.
            result = await EmailGeneratorAgent(config).run(
                EmailGeneratorInput(
                    recipient_name=lead["name"],
                    recipient_company=lead["company"],
                    recipient_title=lead.get("title"),
                    company_industry=lead.get("industry"),
                    sender_name=prefs["sender"],
                    sender_company=prefs["company"],
                    product_value_prop=campaign["offer"]
                    + (
                        "\nEvidence-based opportunity: "
                        + lead["website_research"].get("opportunity", "")
                        + "\nDo not claim the company has no app or wants to buy an app; ask whether this is relevant."
                        if lead.get("website_research")
                        else ""
                    ),
                    tone=campaign["tone"],
                )
            )
            if not result.success:
                raise ExternalServiceException("Email generation failed")
            result = asdict(result.data)
        await persist("draft", result)
        return {"draft": result}

    graph = StateGraph(State)
    graph.add_node("enrich", enrich)
    graph.add_node("research", research)
    graph.add_node("draft", draft)
    graph.add_edge(START, "enrich")
    graph.add_edge("enrich", "research")
    graph.add_edge("research", "draft")
    graph.add_edge("draft", END)
    return await graph.compile().ainvoke(checkpoint)
