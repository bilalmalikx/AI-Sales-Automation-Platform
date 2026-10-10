"""Discovery orchestration never invents emails, repeats a paid start or bypasses review."""

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings
from app.providers import apify, website
from app.services import discovery

BASE = "/api/v1/discovery"


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(settings, "APIFY_API_TOKEN", "test-token")
    monkeypatch.setattr(settings, "APIFY_DATASET_ID", "test-dataset")
    monkeypatch.setattr(settings, "DISCOVERY_DAILY_LIMIT", 100)

    async def start(params):
        return {"id": "test-run", "defaultDatasetId": "test-dataset"}

    async def get_run(identifier):
        return {"status": "SUCCEEDED", "defaultDatasetId": "test-dataset", "usageTotalUsd": 0.02}

    async def items(identifier, limit):
        return [
            {
                "title": "Studio Wash",
                "website": "https://wash.example.com",
                "countryCode": "GB",
                "placeId": "place-1",
            }
        ]

    async def inspect(url):
        return {
            "pages": [{"url": url, "excerpt": "Customer booking and memberships"}],
            "emails": [{"email": "hello@wash.example.com", "source_url": url + "/contact"}],
            "app_links": [],
            "text": "Customer booking and memberships",
            "error": None,
        }

    async def verify(*args):
        return {
            "status": "app_not_found",
            "checks": ["test website and app catalogs"],
            "matches": [],
            "limitations": ["Absence is not confirmed"],
        }

    async def qualify(*args):
        return {
            "score": 80,
            "suitable": True,
            "summary": "A membership-based car wash",
            "opportunity": "Mobile booking and loyalty",
            "provider": "test",
        }

    for mod, name, value in [
        (apify, "start", start),
        (apify, "get_run", get_run),
        (apify, "items", items),
        (website, "inspect", inspect),
        (discovery, "verify_app", verify),
        (discovery, "qualify", qualify),
    ]:
        monkeypatch.setattr(mod, name, value)
    return monkeypatch


def start(client, **extra):
    return client.post(
        BASE + "/runs",
        json={
            "industry": "car wash",
            "location": "London",
            "country": "GB",
            "limit": 5,
            "mode": "fresh",
            "generate_drafts": True,
            **extra,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )


def test_discovery_to_evidence_contact_and_review_draft(client, drain, providers):
    r = start(client)
    assert r.status_code == 202, r.text
    drain()
    data = client.get(BASE + "/runs/" + r.json()["id"]).json()
    assert data["status"] == "completed", data
    p = client.get(BASE + "/prospects").json()["items"][0]
    assert p["lead_id"] and p["emails"][0]["email"] == "hello@wash.example.com"
    assert p["app_status"] == "app_not_found" and p["evidence"]["website"]["pages"]
    assert client.get("/api/v1/campaigns").json()["items"][0]["status"] == "draft"
    d = client.get("/api/v1/emails").json()["items"][0]
    assert d["status"] == "needs_review"
    assert client.post("/api/v1/emails/" + d["id"] + "/send").status_code == 409


def test_missing_website_and_email_remain_visible(client, drain, providers):
    async def rows(*args):
        return [
            {"title": "No website", "placeId": "one"},
            {"title": "No contact", "website": "https://empty.example.com", "placeId": "two"},
        ]

    async def inspect(*args):
        return {
            "pages": [{"url": "https://empty.example.com"}],
            "emails": [],
            "app_links": [],
            "text": "Car wash",
            "error": None,
        }

    providers.setattr(apify, "items", rows)
    providers.setattr(website, "inspect", inspect)
    start(client)
    drain()
    ps = client.get(BASE + "/prospects").json()["items"]
    assert {p["status"] for p in ps} == {"missing_website", "missing_contact"}
    assert client.get("/api/v1/leads").json()["total"] == 0


def test_app_found_and_outside_country_excluded(client, drain, providers):
    async def rows(*args):
        return [
            {
                "title": "App business",
                "website": "https://wash.example.com",
                "placeId": "one",
                "countryCode": "GB",
            },
            {
                "title": "Outside",
                "website": "https://other.example.com",
                "placeId": "two",
                "countryCode": "DE",
            },
        ]

    async def verify(*args):
        return {"status": "app_found", "matches": [{"url": "https://apps.apple.com/gb/app/id123"}]}

    providers.setattr(apify, "items", rows)
    providers.setattr(discovery, "verify_app", verify)
    start(client)
    drain()
    ps = client.get(BASE + "/prospects").json()["items"]
    assert all(p["status"] == "excluded" for p in ps)
    assert client.get("/api/v1/leads").json()["total"] == 0


def test_idempotent_start_daily_limit_and_duplicate_business(client, drain, providers):
    value = {
        "industry": "car wash",
        "location": "London",
        "country": "GB",
        "limit": 100,
        "generate_drafts": False,
    }
    headers = {"Idempotency-Key": "same-run"}
    a = client.post(BASE + "/runs", json=value, headers=headers)
    b = client.post(BASE + "/runs", json=value, headers=headers)
    assert a.json()["id"] == b.json()["id"]
    assert start(client).status_code == 429
    drain()
    assert client.get(BASE + "/prospects").json()["total"] == 1


def test_ambiguous_provider_start_not_repeated(client, drain, providers):
    calls = []

    async def ambiguous(*args):
        calls.append(1)
        raise TimeoutError()

    providers.setattr(apify, "start", ambiguous)
    r = start(client)
    drain()
    drain()
    assert len(calls) == 1
    assert client.get(BASE + "/runs/" + r.json()["id"]).json()["status"] == "failed"


def test_saved_dataset_never_starts_paid_actor(client, drain, providers):
    async def forbidden(*args):
        raise AssertionError("Should not start Actor")

    providers.setattr(apify, "start", forbidden)
    assert start(client, mode="dataset").status_code == 202
    drain()
    assert client.get(BASE + "/prospects").json()["total"] == 1


def test_private_network_targets_blocked(client):
    with pytest.raises(ValueError, match="public"):
        asyncio.run(website.public_address("127.0.0.1"))
    assert client.get(BASE + "/configuration").status_code == 200


def test_config_accepts_dataset_urls_and_smtp_aliases():
    from app.core.config import Settings

    s = Settings(
        _env_file=None,
        APIFY_DATASET_ID="https://api.apify.com/v2/datasets/mydataset/items?token=hidden",
        SMTP_FROM="hello@codelps.example",
        SMTP_SECURITY="ssl",
    )
    assert (
        s.APIFY_DATASET_ID == "mydataset"
        and s.DEFAULT_FROM_EMAIL == "hello@codelps.example"
        and s.SMTP_TLS == "ssl"
    )


def test_failed_inspection_retries_saved_evidence(client, drain, providers):
    calls = []

    async def fail(*args):
        calls.append(1)
        raise ValueError("Temporary AI failure")

    providers.setattr(discovery, "qualify", fail)
    start(client)
    drain()
    p = client.get(BASE + "/prospects").json()["items"][0]
    assert p["status"] == "inspection_failed"
    assert "app" in p["evidence"]

    async def no_crawl(*args):
        raise AssertionError("Saved website must not be fetched again")

    async def qualify(*args):
        return {"summary": "Wash", "opportunity": "Booking", "score": 80, "suitable": True}

    providers.setattr(website, "inspect", no_crawl)
    providers.setattr(discovery, "qualify", qualify)
    assert client.post(BASE + "/prospects/" + p["id"] + "/retry").status_code == 200
    drain()
    p = client.get(BASE + "/prospects/" + p["id"]).json()
    assert p["status"] == "qualified"
    assert p["lead_id"]
    assert client.post(BASE + "/prospects/" + p["id"] + "/retry").status_code == 409


def test_unrelated_footer_email_is_not_business_contact():
    assert website.affiliated_email("hello@wash.co.uk", "www.wash.co.uk")
    assert website.affiliated_email("wash@gmail.com", "wash.co.uk")
    assert not website.affiliated_email("support@webdesigner.com", "wash.co.uk")
    assert not website.affiliated_email("hello@notwash.co.uk", "wash.co.uk")


def test_cancel_during_ai_does_not_promote_contact(client, drain, providers):
    from sqlalchemy import update

    from app.models.discovery import DiscoveryRun
    from app.tasks.worker import sessions

    run_id = None

    async def qualify(*args):
        async with sessions()() as db:
            await db.execute(
                update(DiscoveryRun).where(DiscoveryRun.id == run_id).values(status="cancelled")
            )
            await db.commit()
        return {"summary": "Wash", "opportunity": "Booking", "score": 80, "suitable": True}

    providers.setattr(discovery, "qualify", qualify)
    from uuid import UUID

    run_id = UUID(start(client).json()["id"])
    drain()
    assert client.get(BASE + "/runs/" + str(run_id)).json()["status"] == "cancelled"
    assert client.get("/api/v1/leads").json()["total"] == 0


def test_retry_empty_crawl_rechecks_website(client, drain, providers):
    calls = []

    async def inspect(url):
        calls.append(url)
        if len(calls) == 1:
            return {
                "pages": [],
                "emails": [],
                "app_links": [],
                "text": "",
                "error": "Temporarily unavailable",
            }
        return {
            "pages": [{"url": url}],
            "emails": [{"email": "hello@wash.example.com", "source_url": url}],
            "app_links": [],
            "text": "Booking",
        }

    providers.setattr(website, "inspect", inspect)
    start(client)
    drain()
    p = client.get(BASE + "/prospects").json()["items"][0]
    assert client.post(BASE + "/prospects/" + p["id"] + "/retry").status_code == 200
    drain()
    assert len(calls) == 2
    assert client.get(BASE + "/prospects/" + p["id"]).json()["lead_id"]


def test_canonical_redirect_preserves_sources_and_contact_domain(client, monkeypatch):
    async def fetch(url):
        if "robots.txt" in url:
            return url, "User-agent: *\nAllow: /"
        return "https://newwash.co.uk/", "<p>Book a wash. hello@newwash.co.uk</p>"

    monkeypatch.setattr(website, "fetch", fetch)
    result = client.portal.call(website.inspect, "https://oldwash.co.uk/")
    assert result["emails"][0]["email"] == "hello@newwash.co.uk"
    assert result["redirects"][0]["source_url"] == "https://oldwash.co.uk/"
    assert result["pages"][0]["url"] == "https://newwash.co.uk/"


def test_contact_filter_keeps_verified_website_contacts_and_pagination(client, drain, providers):
    async def rows(*args):
        return [
            {"title": "Contact Wash", "website": "https://wash.example.com", "placeId": "one"},
            {"title": "Empty Wash", "website": "https://empty.example.com", "placeId": "two"},
        ]

    async def inspect(url):
        return {
            "pages": [{"url": url}],
            "emails": []
            if "empty" in url
            else [{"email": "hello@wash.example.com", "source_url": url}],
            "text": "Booking",
            "app_links": [],
        }

    providers.setattr(apify, "items", rows)
    providers.setattr(website, "inspect", inspect)
    start(client)
    drain()
    assert client.get(BASE + "/prospects").json()["total"] == 2
    results = client.get(BASE + "/prospects?contact_only=true&page_size=1").json()
    assert results["total"] == results["pages"] == 1
    assert results["items"][0]["company"] == "Contact Wash"
    assert results["items"][0]["contact_available"]


def test_website_phone_is_visible_but_never_used_for_email_outreach(client, drain, providers):
    async def inspect(url):
        return {
            "pages": [{"url": url}],
            "emails": [],
            "phones": [{"phone": "+44 161 123 4567", "source_url": url}],
            "contact_links": [url + "/contact"],
            "text": "Booking",
            "app_links": [],
        }

    providers.setattr(website, "inspect", inspect)
    start(client)
    drain()
    result = client.get(BASE + "/prospects?contact_only=true").json()
    assert result["total"] == 1
    assert result["items"][0]["status"] == "missing_email"
    assert client.get("/api/v1/leads").json()["total"] == 0


def test_operator_can_prepare_review_draft_from_public_email_prospect(client, drain, providers):
    async def weak(*args):
        return {
            "summary": "Wash",
            "opportunity": "Review booking potential",
            "score": 35,
            "suitable": False,
        }

    providers.setattr(discovery, "qualify", weak)
    start(client)
    drain()
    p = client.get(BASE + "/prospects").json()["items"][0]
    assert not p["lead_id"]
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Mobile app review",
            "audience": "UK businesses",
            "offer": "Build mobile booking apps",
            "lead_ids": [],
        },
    ).json()
    path = BASE + "/prospects/" + p["id"] + "/prepare-outreach"
    body = {"campaign_id": campaign["id"], "reviewed_contact": True}
    headers = {"Idempotency-Key": "review-selected-contact"}
    assert (
        client.post(path, json={**body, "reviewed_contact": False}, headers=headers).status_code
        == 422
    )
    r = client.post(path, json=body, headers=headers)
    assert r.status_code == 202, r.text
    assert client.post(path, json=body, headers=headers).json()["id"] == r.json()["id"]
    drain()
    assert client.get("/api/v1/emails").json()["items"][0]["status"] == "needs_review"
    p = client.get(BASE + "/prospects/" + p["id"]).json()
    assert p["lead_id"] and p["score"] == 35 and not p["analysis"]["suitable"]
    assert client.get("/api/v1/campaigns/" + campaign["id"]).json()["lead_ids"] == [p["lead_id"]]


def test_review_draft_refuses_existing_app(client, drain, providers):
    async def found(*args):
        return {"status": "app_found", "matches": []}

    providers.setattr(discovery, "verify_app", found)
    start(client)
    drain()
    p = client.get(BASE + "/prospects").json()["items"][0]
    campaign = client.post(
        "/api/v1/campaigns",
        json={"name": "Review", "audience": "UK", "offer": "Mobile booking", "lead_ids": []},
    ).json()
    r = client.post(
        BASE + "/prospects/" + p["id"] + "/prepare-outreach",
        json={"campaign_id": campaign["id"], "reviewed_contact": True},
        headers={"Idempotency-Key": "excluded"},
    )
    assert r.status_code == 409
    assert client.get("/api/v1/leads").json()["total"] == 0


def test_review_draft_cannot_bypass_email_opt_out(client, drain, providers):
    async def weak(*args):
        return {"summary": "Wash", "score": 20, "suitable": False}

    providers.setattr(discovery, "qualify", weak)
    start(client)
    drain()
    p = client.get(BASE + "/prospects").json()["items"][0]
    lead = client.post(
        "/api/v1/leads",
        json={
            "email": "hello@wash.example.com",
            "company_name": "Studio Wash",
            "first_name": "Team",
        },
    ).json()
    assert client.post("/api/v1/leads/" + lead["id"] + "/unsubscribe").status_code == 200
    campaign = client.post(
        "/api/v1/campaigns",
        json={"name": "Review", "audience": "UK", "offer": "Mobile booking", "lead_ids": []},
    ).json()
    r = client.post(
        BASE + "/prospects/" + p["id"] + "/prepare-outreach",
        json={"campaign_id": campaign["id"], "reviewed_contact": True},
        headers={"Idempotency-Key": "opt-out-protected"},
    )
    assert r.status_code == 409
    assert client.get("/api/v1/emails").json()["total"] == 0
