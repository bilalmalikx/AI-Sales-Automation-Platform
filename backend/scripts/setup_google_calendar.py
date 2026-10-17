"""Authorize a Desktop OAuth client and save matching Calendar credentials privately."""

# ruff: noqa: T201
import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import set_key

SCOPE = "https://www.googleapis.com/auth/calendar.events"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path)
    args = parser.parse_args()
    candidates = list(ROOT.glob("client_secret*.json"))
    path = args.credentials or (
        candidates[0] if len(candidates) == 1 else ROOT / "credentials.json"
    )
    client = json.loads(path.read_text()).get("installed")
    if not client or not client.get("client_id") or not client.get("client_secret"):
        raise ValueError("A valid Desktop OAuth client JSON is required.")
    os.chmod(path, 0o600)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Authorization codes must never appear in request logs.

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            values = parse_qs(parsed.query)
            if parsed.path != "/oauth2callback" or not secrets.compare_digest(
                values.get("state", [""])[0], state
            ):
                self.send_error(400, "Invalid authorization callback")
                return
            result.update({k: v[0] for k, v in values.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(
                b"<h1>Codelps Calendar authorization received</h1><p>You can return to Codex. The connection will now be verified.</p>"
            )

    with HTTPServer(("127.0.0.1", 0), Callback) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/oauth2callback"
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": client["client_id"],
                "redirect_uri": redirect,
                "response_type": "code",
                "scope": SCOPE,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        private = ROOT.parent / ".local" / "google-calendar-auth-url.txt"
        private.parent.mkdir(exist_ok=True)
        fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(url)
        webbrowser.open(url)
        print("Awaiting Google account consent in the browser (15 minute timeout).", flush=True)
        deadline = time.monotonic() + 900
        while not result and time.monotonic() < deadline:
            server.handle_request()
        private.unlink(missing_ok=True)
    if result.get("error") or not result.get("code"):
        print("Authorization was declined or timed out; .env was not changed.")
        return 1
    with httpx.Client(timeout=30) as http:
        response = http.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "code": result["code"],
                "code_verifier": verifier,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
            },
        )
        if response.status_code != 200:
            print("Google token exchange failed; .env was not changed.")
            return 1
        tokens = response.json()
        if not tokens.get("refresh_token") or SCOPE not in tokens.get("scope", "").split():
            print("Calendar permission or refresh token missing; .env was not changed.")
            return 1
        check = http.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": "Bearer " + tokens["access_token"]},
            params={"maxResults": 1},
        )
        if check.status_code != 200:
            print(
                "Calendar API access failed. Enable Google Calendar API and retry; .env was not changed."
            )
            return 1
    env = ROOT / ".env"
    os.chmod(env, 0o600)
    for key, value in {
        "GOOGLE_CLIENT_ID": client["client_id"],
        "GOOGLE_CLIENT_SECRET": client["client_secret"],
        "GOOGLE_REFRESH_TOKEN": tokens["refresh_token"],
        "GOOGLE_CALENDAR_ID": "primary",
        "CALENDAR_PROVIDER": "google",
    }.items():
        set_key(env, key, value)
    print(
        "Calendar API verified. Matching client credentials and refresh token saved to backend/.env. No secrets printed."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Calendar setup stopped ({type(exc).__name__}); no credential details logged.")
        sys.exit(1)
