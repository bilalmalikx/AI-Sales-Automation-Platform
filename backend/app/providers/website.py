"""Small public-site crawler with bounded pages, robots and pinned public DNS."""

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import EmailStr, TypeAdapter

from app.core.config import settings

USER_AGENT = "CodelpsResearch/1.0"
PUBLIC_MAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "icloud.com",
    "aol.com",
    "live.com",
}


def affiliated_email(email, host):
    """Avoid contacting vendors whose addresses appear in site footers."""
    domain = email.rsplit("@", 1)[1].lower()
    host = host.lower().removeprefix("www.")
    return (
        domain in PUBLIC_MAIL_DOMAINS
        or domain == host
        or host.endswith("." + domain)
        or domain.endswith("." + host)
    )


MAX_BYTES = 1000000


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.links = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


async def public_address(host):
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise ValueError("Website DNS lookup failed") from exc
    ips = list(dict.fromkeys(a[4][0] for a in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Only public website addresses are allowed")
    return ips[0]


async def fetch(url):
    for _ in range(4):
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.port not in {None, 80, 443}
        ):
            raise ValueError("Invalid public website URL")
        ip = await public_address(parts.hostname)
        authority = ("[" + ip + "]") if ":" in ip else ip
        if parts.port:
            authority += ":" + str(parts.port)
        pinned = urlunsplit((parts.scheme, authority, parts.path or "/", parts.query, ""))
        async with httpx.AsyncClient(
            timeout=settings.WEBSITE_TIMEOUT_SECONDS, trust_env=False
        ) as client:
            async with client.stream(
                "GET",
                pinned,
                headers={"Host": parts.netloc, "User-Agent": USER_AGENT},
                extensions={"sni_hostname": parts.hostname},
            ) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code != 200:
                    raise ValueError(f"Website HTTP {r.status_code}")
                data = bytearray()
                async for chunk in r.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError("Page exceeds crawl size limit")
                return url, data.decode(r.encoding or "utf-8", errors="replace")
    raise ValueError("Too many website redirects")


async def inspect(url):
    home = urlsplit(url)
    robots = RobotFileParser()
    try:
        _, body = await fetch(urljoin(url, "/robots.txt"))
        robots.parse(body.splitlines())
    except ValueError as exc:
        if "HTTP 404" not in str(exc):
            # Honor explicit crawler restrictions; absent robots files allow inspection.
            if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                return {
                    "pages": [],
                    "emails": [],
                    "app_links": [],
                    "text": "",
                    "error": "Website blocks crawler access",
                }
        robots.parse([])
    redirects = []
    queue = [url]
    seen = set()
    pages = []
    emails = {}
    app_links = set()
    phones = {}
    contact_links = set()
    text = []
    while queue and len(seen) < settings.WEBSITE_MAX_PAGES:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if not robots.can_fetch(USER_AGENT, current):
            continue
        try:
            final, body = await fetch(current)
        except (ValueError, httpx.HTTPError):
            continue
        # A source homepage may redirect to its new canonical domain. Preserve the
        # source-to-canonical chain and honor the destination's robots before crawling.
        if urlsplit(final).hostname.removeprefix("www.") != home.hostname.removeprefix("www."):
            if current != url or pages:
                continue
            canonical_robots = RobotFileParser()
            try:
                _, rules = await fetch(urljoin(final, "/robots.txt"))
                canonical_robots.parse(rules.splitlines())
            except ValueError as exc:
                if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                    continue
                canonical_robots.parse([])
            if not canonical_robots.can_fetch(USER_AGENT, final):
                continue
            redirects.append({"source_url": url, "canonical_url": final})
            home = urlsplit(final)
            robots = canonical_robots
        parser = PageParser()
        parser.feed(body)
        clean = " ".join(parser.parts)
        text.append(clean[:5000])
        pages.append({"url": final, "excerpt": clean[:1600]})
        candidates = re.findall(
            r"[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", clean
        )
        candidates += [
            link[7:].split("?")[0] for link in parser.links if link.lower().startswith("mailto:")
        ]
        for email in candidates:
            email = email.lower().strip(".,;")
            try:
                email = str(TypeAdapter(EmailStr).validate_python(email))
            except ValueError:
                continue
            if email.split("@")[1] in {
                "example.com",
                "example.org",
                "domain.com",
                "sentry.io",
            } or email.startswith(("noreply", "no-reply")):
                continue
            if affiliated_email(email, home.hostname):
                emails[email] = final
        for link in parser.links:
            if link.lower().startswith("tel:"):
                phone = link[4:].split("?")[0].strip()
                if 7 <= len(re.sub(r"\D", "", phone)) <= 15:
                    phones[phone] = final
            absolute = urljoin(final, link)
            p = urlsplit(absolute)
            if (
                p.hostname == "play.google.com"
                and p.path == "/store/apps/details"
                and "id=" in p.query
            ) or (p.hostname == "apps.apple.com" and re.search(r"/id\d+", p.path)):
                app_links.add(absolute)
            if (
                p.scheme in {"http", "https"}
                and p.hostname
                and p.hostname.removeprefix("www.") == home.hostname.removeprefix("www.")
                and re.search(
                    "contact|about|services|booking|membership|download|mobile|/app", p.path, re.I
                )
            ):
                cleaned = urlunsplit((p.scheme, p.netloc, p.path, "", ""))
                queue.append(cleaned)
                if "contact" in p.path.lower():
                    contact_links.add(cleaned)
        if len(seen) == 1:
            queue += [urljoin(final, "/contact"), urljoin(final, "/about")]
        # Contact and app pages take priority over generic services/about links.
        queue = sorted(
            dict.fromkeys(queue),
            key=lambda u: 0
            if "contact" in urlsplit(u).path.lower()
            else 1
            if re.search("download|mobile|/app", urlsplit(u).path, re.I)
            else 2,
        )
    return {
        "pages": pages,
        "redirects": redirects,
        "phones": [{"phone": k, "source_url": v} for k, v in phones.items()][:10],
        "contact_links": sorted(contact_links)[:10],
        "emails": [{"email": k, "source_url": v} for k, v in emails.items()][:10],
        "app_links": sorted(app_links),
        "text": "\n".join(text)[:14000],
        "error": None if pages else "No accessible public website pages",
    }
