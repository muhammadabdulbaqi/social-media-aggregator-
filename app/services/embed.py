"""Embed service: platform detection and oEmbed/iframe fetch."""
import re
from typing import Tuple

import requests
from flask import current_app


YOUTUBE_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})"),
]
TWITTER_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(\d+)",
    re.I,
)
TIKTOK_PATTERN = re.compile(
    r"https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)",
    re.I,
)
INSTAGRAM_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)",
    re.I,
)


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
    if TIKTOK_PATTERN.search(url):
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
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("html"), None, data.get("author_name")

    if platform == "tiktok":
        r = requests.get(
            "https://www.tiktok.com/oembed",
            params={"url": url},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("html"), None, data.get("title")

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
