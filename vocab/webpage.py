"""Safely download a public webpage and extract its readable text."""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup

# News homepages often embed several megabytes of scripts and JSON in their
# HTML. The extractor discards those resources, but it must first receive the
# document containing the readable main section.
MAX_WEBPAGE_BYTES = 25 * 1024 * 1024
_FETCH_TIMEOUT_SECONDS = 45
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/136.0 Safari/537.36 WordCollection/1.0"
)


class WebpageFetchError(ValueError):
    """Raised when a webpage cannot be downloaded or converted to text."""


@dataclass(frozen=True, slots=True)
class WebpageText:
    """Readable text and metadata extracted from one webpage."""

    url: str
    title: str
    text: str


def fetch_webpage_text(url: str) -> WebpageText:
    """Download a public HTTP(S) webpage and return only its readable text."""

    url = validate_public_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
        },
    )
    opener = build_opener(_PublicRedirectHandler())
    try:
        with opener.open(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:
            final_url = validate_public_url(response.geturl())
            content_type = response.headers.get_content_type().lower()
            if content_type != "application/xhtml+xml" and not content_type.startswith(
                "text/"
            ):
                raise WebpageFetchError(
                    f"unsupported webpage content type: {content_type}"
                )
            raw = response.read(MAX_WEBPAGE_BYTES + 1)
            if len(raw) > MAX_WEBPAGE_BYTES:
                raise WebpageFetchError("webpage document is larger than 25 MB")
            charset = response.headers.get_content_charset() or "utf-8"
    except WebpageFetchError:
        raise
    except HTTPError as exc:
        raise WebpageFetchError(f"website returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise WebpageFetchError(f"could not download webpage: {reason}") from exc

    try:
        source = raw.decode(charset, errors="replace")
    except LookupError:
        source = raw.decode("utf-8", errors="replace")

    hostname = urlsplit(final_url).hostname or "Online webpage"
    if content_type == "text/plain":
        text = _normalise_text(source)
        title = hostname
    else:
        title, text = extract_readable_html(source, fallback_title=hostname)
    if not text:
        raise WebpageFetchError("no readable text found on webpage")
    return WebpageText(url=final_url, title=title, text=text)


def validate_public_url(url: str) -> str:
    """Validate an HTTP(S) URL and reject local/private network destinations."""

    value = url.strip()
    if not value:
        raise WebpageFetchError("empty URL")
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"}:
        raise WebpageFetchError("URL must start with http:// or https://")
    if not parts.hostname:
        raise WebpageFetchError("URL must include a hostname")
    if parts.username or parts.password:
        raise WebpageFetchError("URLs containing credentials are not supported")
    try:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise WebpageFetchError("URL contains an invalid port") from exc

    try:
        addresses = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebpageFetchError("website hostname could not be resolved") from exc
    if not addresses:
        raise WebpageFetchError("website hostname could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise WebpageFetchError("local or private network URLs are not allowed")
    return value


def extract_readable_html(source: str, fallback_title: str = "Online webpage") -> tuple[str, str]:
    """Return ``(title, text)`` from HTML without navigation or page chrome."""

    soup = BeautifulSoup(source, "lxml")
    title = _normalise_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "template",
            "svg",
            "canvas",
            "form",
            "nav",
            "footer",
            "header",
            "aside",
        ]
    ):
        tag.decompose()

    content = soup.find("article") or soup.find("main") or soup.body or soup
    text = _normalise_text(content.get_text("\n", strip=True))
    return title or fallback_title, text


def _normalise_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n\n".join(line for line in lines if line)


class _PublicRedirectHandler(HTTPRedirectHandler):
    """Revalidate every redirect before urllib follows it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
