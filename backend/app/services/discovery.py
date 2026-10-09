"""Hybrid orchestrator: deterministic constraints, evidence tools, AI qualification."""

import hashlib
from copy import deepcopy
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import func, select

from app.agents.mobile_app import qualify, verify_app
from app.core.config import settings
from app.core.exceptions import ConflictException, RateLimitException, ValidationException
from app.models.discovery import DiscoveryRun, Prospect
from app.models.domain import Lead
from app.models.sales import Campaign, CampaignLead, Job
from app.providers import apify, website
from app.repositories.sales import SalesRepository
from app.schemas.lead import LeadCreate
from app.schemas.sales import WorkflowInput
from app.services.lead import LeadService
from app.services.sales import SalesService, now


async def start(db, value, key):
    repo = SalesRepository(db)
    await repo.settings(lock=True)
    existing = await db.scalar(select(DiscoveryRun).where(DiscoveryRun.idempotency_key == key))
    if existing:
        if existing.parameters != value.model_dump():
            raise ConflictException("Idempotency key belongs to different discovery parameters")
        return existing
    if not settings.APIFY_API_TOKEN:
        raise ValidationException("Configure APIFY_API_TOKEN before starting discovery")
    if value.mode == "dataset" and not settings.APIFY_DATASET_ID:
        raise ValidationException("Configure an Apify dataset ID or choose fresh search")
    midnight = now().replace(hour=0, minute=0, second=0, microsecond=0)
    runs = (await db.scalars(select(DiscoveryRun).where(DiscoveryRun.created_at >= midnight))).all()
    if sum(r.parameters["limit"] for r in runs) + value.limit > settings.DISCOVERY_DAILY_LIMIT:
        raise RateLimitException("Daily discovery limit reached; retry tomorrow (UTC)")
    run = DiscoveryRun(
        parameters=value.model_dump(), idempotency_key=key, status="queued", stage="discovery"
    )
    db.add(run)
    await db.flush()
    await SalesService(db).enqueue("discovery", run, f"discovery:{run.id}:start")
    await db.commit()
    return run


async def poll_later(db, run):
    db.add(
        Job(
            kind="discovery",
            resource_id=str(run.id),
            dedupe_key=f"discovery:{run.id}:{uuid4()}",
            available_at=now() + timedelta(seconds=5),
        )
    )
    await db.commit()


async def discover(identifier):
    from app.tasks.worker import sessions

    async with sessions()() as db:
        repo = SalesRepository(db)
        await repo.settings(lock=True)
        run = await repo.get(DiscoveryRun, identifier, lock=True)
        if run.status in {
            "completed",
            "completed_with_errors",
            "cancelled",
            "failed",
            "inspecting",
        }:
            return
        params = dict(run.parameters)
        if not run.provider_run_id and params["mode"] == "fresh":
            if run.status == "starting":
                run.status = "failed"
                run.error = "Apify start outcome uncertain; check account runs before starting another search"
                await db.commit()
                return
            run.status = "starting"
            await db.commit()
            try:
                provider = await apify.start(params)
            except Exception:
                run.status = "failed"
                run.error = (
                    "Apify start failed or outcome uncertain; check token, credits and account runs"
                )
                await db.commit()
                return
            await db.refresh(run)
            run.provider_run_id = provider["id"]
            run.dataset_id = provider.get("defaultDatasetId")
            if run.status == "cancelled":
                await db.commit()
                return
            run.status = "discovering"
            await db.commit()
        if params["mode"] == "fresh":
            provider = await apify.get_run(run.provider_run_id)
            await db.refresh(run)
            if run.status == "cancelled":
                return
            run.dataset_id = provider.get("defaultDatasetId") or run.dataset_id
            run.provider_cost = float(provider.get("usageTotalUsd") or 0)
            if provider["status"] not in {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}:
                run.stage = "maps_discovery"
                await poll_later(db, run)
                return
            if provider["status"] != "SUCCEEDED":
                run.status = "failed"
                run.error = "Apify discovery did not succeed: " + provider["status"]
                await db.commit()
                return
        else:
            run.dataset_id = settings.APIFY_DATASET_ID
        rows = await apify.items(run.dataset_id, params["limit"])
        await db.refresh(run)
        if run.status == "cancelled":
            return
        seen = set()
        for row in rows:
            name = str(row.get("title") or row.get("name") or "Unnamed business")[:300]
            url = row.get("website")
            if url and not str(url).startswith(("https://", "http://")):
                url = "https://" + str(url)
            domain = urlsplit(str(url or "")).hostname or ""
            source = str(
                row.get("placeId")
                or row.get("url")
                or hashlib.sha256((name + domain).encode()).hexdigest()
            )[:500]
            if source in seen:
                continue
            seen.add(source)
            prior = await db.scalar(
                select(Prospect.id).where(Prospect.run_id == run.id, Prospect.source_key == source)
            )
            if prior:
                continue
            country = str(row.get("countryCode") or params["country"]).upper()
            p = Prospect(
                run_id=run.id,
                source_key=source,
                company=name,
                website=str(url)[:2000] if url else None,
                country=country,
                city=str(row.get("city") or "")[:200],
                phone=str(row.get("phone") or "")[:100],
                evidence={
                    "maps": {
                        "url": row.get("url"),
                        "place_id": row.get("placeId"),
                        "address": row.get("address"),
                        "country_inferred_from_query": not bool(row.get("countryCode")),
                    },
                    "checked_at": now().isoformat() + "Z",
                },
            )
            if row.get("permanentlyClosed") or row.get("temporarilyClosed"):
                p.status = "excluded"
                p.reason = "Business is marked closed"
                p.stage = "complete"
            elif country not in {"GB", "UK", "US"}:
                p.status = "excluded"
                p.reason = "Outside UK/USA target"
                p.stage = "complete"
            elif not url:
                p.status = "missing_website"
                p.reason = "No website provided by source"
                p.stage = "complete"
            db.add(p)
            await db.flush()
            if p.status == "queued":
                await SalesService(db).enqueue("inspect", p, f"inspect:{p.id}")
        await db.flush()
        run.total = await db.scalar(
            select(func.count()).select_from(Prospect).where(Prospect.run_id == run.id)
        )
        run.processed = await db.scalar(
            select(func.count())
            .select_from(Prospect)
            .where(Prospect.run_id == run.id, Prospect.stage == "complete")
        )
        run.status = "completed" if run.total == run.processed else "inspecting"
        run.stage = "complete" if run.status == "completed" else "website_inspection"
        await db.commit()


async def checkpoint(db, p, stage, evidence=None, analysis=None):
    if evidence is not None:
        p.evidence = deepcopy(evidence)
    if analysis is not None:
        p.analysis = analysis
    p.stage = stage
    await db.commit()


async def inspect_prospect(identifier):
    from app.tasks.worker import sessions

    async with sessions()() as db:
        repo = SalesRepository(db)
        p = await repo.get(Prospect, identifier)
        if p.stage == "complete":
            return
        run = await repo.get(DiscoveryRun, p.run_id)
        params = dict(run.parameters)
        if run.status == "cancelled":
            p.status = "cancelled"
            p.stage = "complete"
            await db.commit()
            return
        p.status = "processing"
        await db.commit()
        evidence = dict(p.evidence)
        try:
            if "website" not in evidence:
                site = await website.inspect(p.website)
                evidence["website"] = site
                p.emails = site["emails"]
                await checkpoint(db, p, "app_verification", evidence)
            site = evidence["website"]
            p.contact_available = bool(
                site.get("pages") and (p.emails or site.get("phones") or site.get("contact_links"))
            )
            if not site.get("pages"):
                p.status = "inspection_failed"
                p.reason = site.get("error") or "No accessible website pages"
            elif not p.contact_available:
                p.status = "missing_contact"
                p.reason = "No public email, website phone or contact page found"
            else:
                if "app" not in evidence:
                    evidence["app"] = await verify_app(
                        p.company, p.website, site, params["country"]
                    )
                    p.app_status = evidence["app"]["status"]
                    await checkpoint(db, p, "qualification", evidence)
                if p.app_status == "app_found":
                    p.status = "excluded"
                    p.reason = "Existing mobile app found"
                else:
                    if not p.analysis:
                        await repo.settings(lock=True)
                        run = await repo.get(DiscoveryRun, p.run_id, lock=True)
                        await db.refresh(run)
                        if run.status == "cancelled":
                            p.status = "cancelled"
                            p.stage = "complete"
                            await db.commit()
                            return
                        if (
                            settings.AI_PROVIDER != "local"
                            and run.ai_calls >= settings.DISCOVERY_AI_MAX_CALLS
                        ):
                            p.analysis = {
                                "summary": "Evidence collected; AI call limit reached",
                                "opportunity": "Manual qualification required",
                                "score": 0,
                                "suitable": False,
                                "provider": "not_called",
                            }
                        else:
                            run.ai_calls += 1
                            await db.commit()
                            p.analysis = await qualify(
                                p.company, params["industry"], site, evidence["app"]
                            )
                        p.score = int(p.analysis.get("score", 0))
                        await checkpoint(db, p, "contact_validation", analysis=p.analysis)
                    # No fabricated addresses. Keep email-less businesses visible as prospects.
                    if not p.emails:
                        p.status = "missing_email"
                        p.reason = "No public business email found; outreach is blocked"
                    elif not p.analysis.get("suitable") or p.score < 50:
                        p.status = "needs_review"
                        p.reason = "Qualification requires review"
                    else:
                        p.status = (
                            "qualified" if p.app_status == "app_not_found" else "needs_review"
                        )
                        p.reason = (
                            "Review app absence evidence before outreach"
                            if p.app_status != "app_not_found"
                            else "No matching app found; human review still required"
                        )
                        await promote(db, p, params)
        except Exception as exc:
            p.status = "inspection_failed"
            p.reason = "Inspection failed (" + type(exc).__name__ + "); retry from saved evidence"
        p.stage = "complete"
        await repo.settings(lock=True)
        run = await repo.get(DiscoveryRun, p.run_id, lock=True)
        await db.refresh(run)
        await db.flush()
        run.processed = await db.scalar(
            select(func.count())
            .select_from(Prospect)
            .where(Prospect.run_id == run.id, Prospect.stage == "complete")
        )
        if run.status == "cancelled":
            p.status = "cancelled"
        elif run.processed >= run.total:
            failures = await db.scalar(
                select(func.count())
                .select_from(Prospect)
                .where(Prospect.run_id == run.id, Prospect.status == "inspection_failed")
            )
            run.status = "completed_with_errors" if failures else "completed"
            run.stage = "complete"
        await db.commit()


async def promote(db, p, params):
    repo = SalesRepository(db)
    await repo.settings(lock=True)
    run = await repo.get(DiscoveryRun, p.run_id, lock=True)
    await db.refresh(run)
    if run.status == "cancelled":
        p.status = "cancelled"
        p.reason = "Processing stopped before CRM promotion"
        return
    email = p.emails[0]["email"]
    existing = await db.scalar(select(Lead).where(func.lower(Lead.email) == email.lower()))
    if existing and p.lead_id != existing.id:
        p.lead_id = existing.id
        p.reason = "Existing CRM contact matched; no duplicate lead or automatic draft"
        return
    if existing:
        # Resume this prospect's own partially completed CRM/draft promotion.
        lead = existing
    else:
        value = await LeadService(db).create_lead(
            LeadCreate(
                email=email,
                first_name=p.company[:100],
                company_name=p.company[:200],
                company_domain=urlsplit(p.website).hostname,
                industry=params["industry"],
                source_name="Apify Google Maps",
                status="new",
            )
        )
        lead = await repo.get(Lead, value.id)
    lead.confidence = p.score / 100
    lead.research = {
        "source": "Website evidence + app checks",
        "summary": p.analysis.get("summary", ""),
        "opportunity": p.analysis.get("opportunity", ""),
        "app_status": p.app_status,
        "prospect_id": str(p.id),
        "evidence": p.evidence,
    }
    p.lead_id = lead.id
    if lead.status == "unsubscribed":
        p.status = "excluded"
        p.reason = "Email is suppressed from prior opt-out"
        await db.commit()
        return
    # A draft campaign is created; no automatic activation or delivery.
    if params.get("generate_drafts"):
        run = await repo.get(DiscoveryRun, p.run_id)
        prefs = await repo.settings(lock=True)
        c = await db.scalar(
            select(Campaign).where(
                Campaign.name == "Codelps mobile app opportunities " + str(run.id)[:8]
            )
        )
        if not c:
            c = Campaign(
                name="Codelps mobile app opportunities " + str(run.id)[:8],
                audience=params["industry"] + " in " + params["location"],
                offer=prefs.offer,
                tone="professional",
                status="draft",
            )
            db.add(c)
            await db.flush()
        if not await db.get(CampaignLead, (c.id, lead.id)):
            db.add(CampaignLead(campaign_id=c.id, lead_id=lead.id))
        p.campaign_id = c.id
        await db.commit()
        await SalesService(db).start_workflow(
            WorkflowInput(lead_id=lead.id, campaign_id=c.id), "prospect:" + str(p.id)
        )
    else:
        await db.commit()
