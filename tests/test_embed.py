"""Tests for embed detection and oEmbed cache helpers."""
import unittest
from datetime import timedelta
from unittest.mock import patch

from app import create_app, db
from app.models import Link
from app.services.embed import (
    apply_oembed_cache_fields,
    detect_platform,
    extract_youtube_video_id,
    refresh_embed_if_stale,
    utcnow,
)


class TestDetectPlatform(unittest.TestCase):
    def test_youtube_watch(self) -> None:
        self.assertEqual(
            detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "youtube",
        )

    def test_youtu_be(self) -> None:
        self.assertEqual(
            detect_platform("https://youtu.be/dQw4w9WgXcQ"),
            "youtube",
        )

    def test_x_status(self) -> None:
        self.assertEqual(
            detect_platform("https://x.com/user/status/1234567890"),
            "twitter",
        )

    def test_tiktok(self) -> None:
        self.assertEqual(
            detect_platform("https://www.tiktok.com/@user/video/123"),
            "tiktok",
        )

    def test_unsupported(self) -> None:
        self.assertIsNone(detect_platform("https://example.com/"))


class TestExtractYoutube(unittest.TestCase):
    def test_id(self) -> None:
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/watch?v=abcDEF12345"),
            "abcDEF12345",
        )


class TestOembedCache(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_apply_oembed_cache_youtube_no_expiry(self) -> None:
        link = Link(
            url="https://youtu.be/dQw4w9WgXcQ",
            platform="youtube",
            embed_html=None,
            video_id="dQw4w9WgXcQ",
            title=None,
        )
        apply_oembed_cache_fields(link, "youtube")
        self.assertIsNotNone(link.fetched_at)
        self.assertIsNone(link.expires_at)

    def test_apply_oembed_cache_twitter_has_expiry(self) -> None:
        link = Link(
            url="https://x.com/a/status/1",
            platform="twitter",
            embed_html="<p>x</p>",
            video_id=None,
            title=None,
        )
        apply_oembed_cache_fields(link, "twitter")
        self.assertIsNotNone(link.fetched_at)
        self.assertIsNotNone(link.expires_at)
        self.assertGreater(link.expires_at, link.fetched_at)

    def test_refresh_skips_when_fresh(self) -> None:
        link = Link(
            url="https://x.com/a/status/1",
            platform="twitter",
            embed_html="<p>old</p>",
            video_id=None,
            title=None,
        )
        now = utcnow()
        link.fetched_at = now
        link.expires_at = now + timedelta(days=365)
        out = refresh_embed_if_stale(link)
        self.assertFalse(out)

    @patch("app.services.embed.fetch_embed")
    def test_refresh_when_expired(self, mock_fetch) -> None:
        mock_fetch.return_value = ("<blockquote>new</blockquote>", None, "Author")
        link = Link(
            url="https://x.com/a/status/1",
            platform="twitter",
            embed_html="<p>old</p>",
            video_id=None,
            title="Old",
        )
        link.fetched_at = utcnow()
        link.expires_at = utcnow().replace(year=2000)
        out = refresh_embed_if_stale(link)
        self.assertTrue(out)
        self.assertIn("blockquote", link.embed_html or "")
        mock_fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
