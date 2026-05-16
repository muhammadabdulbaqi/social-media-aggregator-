"""Embed service: platform detection and oEmbed/iframe fetch."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Tuple
from urllib.parse import quote, urlparse

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
    re.compile(r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"),
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
    r"https?://(?:www\.|m\.)?instagram\.com/(?:p|reels?)/([a-zA-Z0-9_-]+)",
    re.I,
)
FACEBOOK_PATTERNS = [
    re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/.+/posts/", re.I),
    re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/share/", re.I),
    re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/permalink\.php", re.I),
    re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/photo\.php", re.I),
    re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/story\.php", re.I),
    re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/watch", re.I),
    re.compile(r"https?://(?:www\.)?fb\.watch/", re.I),
]


def normalize_paste_url(url: str) -> str:
    """Trim and ensure a scheme so detection works on bare domains."""
    url = (url or "").strip()
    if url and not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


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
    """Return platform name or None if unsupported."""
    url = normalize_paste_url(url)
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
    for p in FACEBOOK_PATTERNS:
        if p.search(url):
            return "facebook"
    return None


def _meta_credentials_configured() -> bool:
    return bool(
        current_app.config.get("INSTAGRAM_APP_ID")
        and current_app.config.get("INSTAGRAM_APP_SECRET")
    )


def _meta_app_access_token() -> str:
    """App access token for Meta Graph oEmbed (app_id|app_secret)."""
    app_id = current_app.config.get("INSTAGRAM_APP_ID")
    app_secret = current_app.config.get("INSTAGRAM_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("This embed type isn't available right now.")
    return f"{app_id}|{app_secret}"


def _facebook_oembed_endpoint(url: str) -> str:
    lower = url.lower()
    if "fb.watch" in lower or "/watch" in lower:
        return "oembed_video"
    return "oembed_post"


def _canonical_instagram_url(url: str) -> str:
    """Strip tracking params; use stable /p/ or /reel/ path for oEmbed."""
    m = INSTAGRAM_PATTERN.search(url)
    if not m:
        return url
    kind = "reel" if re.search(r"/reels?/", url, re.I) else "p"
    return f"https://www.instagram.com/{kind}/{m.group(1)}/"


def _instagram_iframe_embed(url: str) -> str:
    m = INSTAGRAM_PATTERN.search(url)
    if not m:
        raise ValueError("Couldn't embed this Instagram link.")
    kind = "reel" if re.search(r"/reels?/", url, re.I) else "p"
    src = f"https://www.instagram.com/{kind}/{m.group(1)}/embed/captioned/"
    return (
        f'<iframe src="{src}" class="instagram-embed-iframe w-full max-w-full" '
        f'width="400" height="480" frameborder="0" scrolling="no" '
        f'allowtransparency="true" allowfullscreen '
        f'style="border:0;overflow:hidden;min-height:480px;"></iframe>'
    )


def _facebook_iframe_embed(url: str) -> str:
    encoded = quote(url, safe="")
    if _facebook_oembed_endpoint(url) == "oembed_video":
        src = (
            f"https://www.facebook.com/plugins/video.php?href={encoded}"
            "&show_text=false&width=560"
        )
        height = 476
    else:
        src = (
            f"https://www.facebook.com/plugins/post.php?href={encoded}"
            "&show_text=true&width=500"
        )
        height = 600
    return (
        f'<iframe src="{src}" class="facebook-embed-iframe w-full max-w-full" '
        f'width="500" height="{height}" style="border:none;overflow:hidden" '
        f'scrolling="no" frameborder="0" allowfullscreen="true" '
        f'allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share">'
        f"</iframe>"
    )


def _fetch_meta_oembed(url: str, endpoint: str, provider: str) -> Tuple[str | None, str | None, str | None]:
    token = _meta_app_access_token()
    r = requests.get(
        f"https://graph.facebook.com/v22.0/{endpoint}",
        params={"url": url, "access_token": token, "omitscript": "true"},
        headers=_OEMBED_HEADERS,
        timeout=15,
    )
    if not r.ok:
        detail = _graph_error_message(r)
        logger.warning("Meta %s oEmbed HTTP %s: %s", provider, r.status_code, detail)
        raise ValueError(detail or f"{provider} embed request failed")
    data = r.json()
    html = data.get("html")
    if not html:
        raise ValueError(
            f"{provider} did not return embed HTML. The post may be private or unavailable."
        )
    return html, None, data.get("title") or data.get("author_name")


def _graph_error_message(r: requests.Response) -> str | None:
    try:
        err = r.json().get("error") or {}
        return err.get("message") or err.get("error_user_msg")
    except Exception:
        return None


def _fetch_instagram_embed(url: str) -> Tuple[str | None, str | None, str | None]:
    url = _canonical_instagram_url(url)
    if _meta_credentials_configured():
        try:
            return _fetch_meta_oembed(url, "instagram_oembed", "Instagram")
        except ValueError:
            pass
    return _instagram_iframe_embed(url), None, None


def _fetch_facebook_embed(url: str) -> Tuple[str | None, str | None, str | None]:
    if _meta_credentials_configured():
        try:
            endpoint = _facebook_oembed_endpoint(url)
            return _fetch_meta_oembed(url, endpoint, "Facebook")
        except ValueError:
            pass
    return _facebook_iframe_embed(url), None, None


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
    url = normalize_paste_url(url)
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
        return _fetch_instagram_embed(url)

    if platform == "facebook":
        return _fetch_facebook_embed(url)

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
