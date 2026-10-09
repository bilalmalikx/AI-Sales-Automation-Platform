"""Idempotent Google Calendar operations using a configured OAuth refresh token."""

from datetime import UTC
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceException


async def google_token(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    if response.status_code != 200:
        raise ExternalServiceException("Google OAuth refresh failed")
    return response.json()["access_token"]


async def sync(meeting, lead) -> dict:
    event_id = meeting.id.hex
    if settings.CALENDAR_PROVIDER == "local":
        return {"event_id": event_id, "join_url": None}
    if not settings.LIVE_DELIVERY_ENABLED:
        raise ExternalServiceException("Live calendar delivery is disabled")
    async with httpx.AsyncClient(timeout=30) as client:
        token = await google_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        base = f"https://www.googleapis.com/calendar/v3/calendars/{quote(settings.GOOGLE_CALENDAR_ID,safe='')}/events"
        url = f"{base}/{event_id}"
        if meeting.status == "cancelled":
            response = await client.delete(url, headers=headers, params={"sendUpdates": "all"})
            if response.status_code not in {200, 204, 404, 410}:
                raise ExternalServiceException("Google Calendar cancellation failed")
            return {"event_id": event_id, "join_url": None}
        # Check external availability, excluding this event when rescheduling/recovering.
        response = await client.get(
            base,
            headers=headers,
            params={
                "timeMin": meeting.start_at.replace(tzinfo=UTC).isoformat(),
                "timeMax": meeting.end_at.replace(tzinfo=UTC).isoformat(),
                "singleEvents": "true",
                "maxResults": 2500,
            },
        )
        if response.status_code != 200:
            raise ExternalServiceException("Google Calendar availability check failed")
        events = response.json()
        if events.get("nextPageToken") or any(
            e.get("id") != event_id
            and e.get("status") != "cancelled"
            and e.get("transparency") != "transparent"
            for e in events.get("items", [])
        ):
            raise ExternalServiceException("Google Calendar is busy at this time")
        body = {
            "summary": meeting.title,
            "start": {
                "dateTime": meeting.start_at.replace(tzinfo=UTC).isoformat(),
                "timeZone": meeting.timezone,
            },
            "end": {
                "dateTime": meeting.end_at.replace(tzinfo=UTC).isoformat(),
                "timeZone": meeting.timezone,
            },
            "attendees": [{"email": lead.email}],
            "conferenceData": {"createRequest": {"requestId": event_id}},
            "extendedProperties": {"private": {"salesway_meeting": str(meeting.id)}},
        }
        exists = await client.get(url, headers=headers)
        if exists.status_code == 200:
            response = await client.patch(
                url,
                headers=headers,
                json=body,
                params={"sendUpdates": "all", "conferenceDataVersion": 1},
            )
        elif exists.status_code == 404:
            response = await client.post(
                base,
                headers=headers,
                json={"id": event_id, **body},
                params={"sendUpdates": "all", "conferenceDataVersion": 1},
            )
            if response.status_code == 409:
                response = await client.patch(
                    url,
                    headers=headers,
                    json=body,
                    params={"sendUpdates": "all", "conferenceDataVersion": 1},
                )
        else:
            raise ExternalServiceException("Google Calendar event lookup failed")
        if response.status_code not in {200, 201}:
            raise ExternalServiceException("Google Calendar synchronization failed")
        data = response.json()
        return {"event_id": data["id"], "join_url": data.get("hangoutLink")}
