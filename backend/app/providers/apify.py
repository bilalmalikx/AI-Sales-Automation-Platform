"""Bounded Apify discovery. Starting a paid run is never blindly retried."""

import re
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceException

BASE = "https://api.apify.com/v2"


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z0-9_~/-]+", value):
        raise ExternalServiceException("Invalid Apify identifier")
    return quote(value.replace("/", "~"), safe="~")


async def request(method, path, **kwargs):
    if not settings.APIFY_API_TOKEN:
        raise ExternalServiceException("APIFY_API_TOKEN is not configured")
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.request(
            method,
            BASE + path,
            headers={"Authorization": "Bearer " + settings.APIFY_API_TOKEN},
            **kwargs,
        )
        if response.status_code >= 400:
            raise ExternalServiceException(
                f"Apify request failed (HTTP {response.status_code}); check token, Actor and credits"
            )
        return response.json()


async def start(parameters):
    return (
        await request(
            "POST",
            f"/acts/{identifier(settings.APIFY_ACTOR_ID)}/runs",
            params={"timeout": 300, "maxTotalChargeUsd": settings.DISCOVERY_RUN_BUDGET_USD},
            json={
                "searchStringsArray": [parameters["industry"]],
                "locationQuery": parameters["location"]
                + ", "
                + ("United Kingdom" if parameters["country"] == "GB" else "United States"),
                "maxCrawledPlacesPerSearch": parameters["limit"],
                "language": "en",
                "skipClosedPlaces": True,
                "website": "withWebsite",
            },
        )
    )["data"]


async def get_run(run_id):
    return (await request("GET", f"/actor-runs/{identifier(run_id)}"))["data"]


async def items(dataset_id, limit):
    rows = []
    while len(rows) < limit:
        page = await request(
            "GET",
            f"/datasets/{identifier(dataset_id)}/items",
            params={
                "clean": "true",
                "format": "json",
                "offset": len(rows),
                "limit": min(50, limit - len(rows)),
            },
        )
        if not page:
            break
        rows.extend(page)
    return rows[:limit]
