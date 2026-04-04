"""Embed service: platform detection and oEmbed/iframe fetch."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Tuple
from urllib.parse import urlparse

import requests
from flask import current_app

if TYPE_CHECKING:
    from app.models.link import Link

logger = logging.getLogger(__name__)

# Some oEmbed endpoints reject Python's default urllib UA; use a normal browser-like string.
_OEMBED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

YOUTUBE_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})"),
]
TWITTER_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(\d+)",
    re.I,
)
# Canonical /@user/video/<id>; other paths handled via _host_is_tiktok.
TIKTOK_VIDEO_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?tiktok\.com/@[^/]+/video/(\d+)",
    re.I,
)
INSTAGRAM_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)",
    re.I,
)


def _host_is_tiktok(url: str) -> bool:
    """True if URL host is tiktok.com or a subdomain (e.g. www, m, vm, vt)."""
    try:
        host = (urlparse(url).netloc or "").lower()
        if "@" in host:  # userinfo accidentally parsed — rare for paste URLs
            host = host.split("@")[-1]
        return host == "tiktok.com" or host.endswith(".tiktok.com")
    except Exception:
        return False


def detect_platform(url: str) -> str | None:
    """Return platform name (youtube, twitter, tiktok, instagram) or None if unsupported."""
    url = (url or "").strip()
    if not url:
        return None
    for p in YOUTUBE_PATTERNS:
        if p.search(url):
            return "youtube"
    if TWITTER_PATTERN.search(url):
        return "twitter"
    if TIKTOK_VIDEO_PATTERN.search(url) or _host_is_tiktok(url):
        return "tiktok"
    if INSTAGRAM_PATTERN.search(url):
        return "instagram"
    return None


def extract_youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    for p in YOUTUBE_PATTERNS:
        m = p.search(url)
        if m:
            return m.group(1)
    return None


def fetch_embed(url: str, platform: str) -> Tuple[str | None, str | None, str | None]:
    """
    Fetch embed HTML or YouTube video_id for the given URL and platform.
    Returns (embed_html, video_id, title). YouTube returns (None, video_id, None).
    Raises ValueError on invalid URL or fetch error.
    """
    if platform == "youtube":
        video_id = extract_youtube_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
        return None, video_id, None

    if platform == "twitter":
        r = requests.get(
            "https://publish.twitter.com/oembed",
            params={"url": url, "omit_script": True},
            headers=_OEMBED_HEADERS,
            timeout=10,
        )
        data = _oembed_json(r, "X (Twitter)")
        html = data.get("html")
        if not html:
            raise ValueError(
                "X did not return embed HTML. The post may be protected or unavailable."
            )
        return html, None, data.get("author_name")

    if platform == "tiktok":
        r = requests.get(
            "https://www.tiktok.com/oembed",
            params={"url": url},
            headers=_OEMBED_HEADERS,
            timeout=10,
        )
        data = _oembed_json(r, "TikTok")
        html = data.get("html")
        if not html:
            raise ValueError(
                "TikTok did not return embed HTML. Try the full video link "
                "(www.tiktok.com/@…/video/…); short vm/vt links sometimes fail if the video "
                "is private or region-restricted."
            )
        return html, None, data.get("title")

    if platform == "instagram":
        app_id = current_app.config.get("INSTAGRAM_APP_ID")
        app_secret = current_app.config.get("INSTAGRAM_APP_SECRET")
        if not app_id or not app_secret:
            raise ValueError(
                "Instagram not configured. Set INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET."
            )
        token_r = requests.get(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        token_r.raise_for_status()
        token = token_r.json().get("access_token")
        if not token:
            raise ValueError("Failed to get Instagram access token")
        r = requests.get(
            "https://graph.facebook.com/v21.0/instagram_oembed",
            params={"url": url, "access_token": token},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("html"), None, None

    raise ValueError(f"Unsupported platform: {platform}")


def _raise_for_oembed_http(r: requests.Response, provider: str) -> None:
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise ValueError(
            f"{provider} returned HTTP {r.status_code}. The post may be private, deleted, "
            "region-blocked, or the URL is invalid. Try opening the link in a browser and "
            "copying the address bar again."
        ) from e


def _oembed_json(r: requests.Response, provider: str) -> dict:
    _raise_for_oembed_http(r, provider)
    try:
        return r.json()
    except Exception as e:
        raise ValueError(
            f"{provider} did not return valid embed data (unexpected response format)."
        ) from e


def utcnow() -> datetime:
    """Timezone-aware UTC \"now\" for cache timestamps."""
    return datetime.now(timezone.utc)


def normalize_utc(dt: datetime | None) -> datetime | None:
    """Treat naive datetimes as UTC (matches SQLite round-trips); aware values → UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def apply_oembed_cache_fields(link: Link, platform: str) -> None:
    """Set fetched_at / expires_at after a successful embed fetch (mutates link in place)."""
    link.fetched_at = utcnow()
    if platform == "youtube":
        link.expires_at = None
        return
    ttl_sec = int(current_app.config.get("OEMBED_CACHE_TTL_SECONDS", 86400))
    link.expires_at = link.fetched_at + timedelta(seconds=ttl_sec)


def refresh_embed_if_stale(link: Link) -> bool:
    """
    For oEmbed-backed platforms, refetch if cache is missing or past expires_at.
    YouTube is unchanged (iframe uses video_id). Returns True if link was updated.
    """
    if link.platform == "youtube":
        return False
    now = utcnow()
    expires = normalize_utc(link.expires_at)
    if expires is not None and expires > now:
        return False
    try:
        embed_html, video_id, title = fetch_embed(link.url, link.platform)
    except Exception as e:
        logger.warning("oEmbed refresh failed for link id=%s: %s", link.id, e)
        return False
    link.embed_html = embed_html
    link.video_id = video_id
    if title is not None:
        link.title = title
    apply_oembed_cache_fields(link, link.platform)
    return True
