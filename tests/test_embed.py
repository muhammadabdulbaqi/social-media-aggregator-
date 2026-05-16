"""Tests for embed detection and oEmbed cache helpers."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app, db
from app.models import Link
from app.services.embed import (
    apply_oembed_cache_fields,
    detect_platform,
    extract_youtube_video_id,
    fetch_embed,
    normalize_utc,
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

    def test_youtube_shorts(self) -> None:
        self.assertEqual(
            detect_platform("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "youtube",
        )

    def test_instagram_reel(self) -> None:
        self.assertEqual(
            detect_platform("https://www.instagram.com/reel/ABC123xyz/"),
            "instagram",
        )

    def test_instagram_mobile(self) -> None:
        self.assertEqual(
            detect_platform("https://m.instagram.com/p/ABC123xyz/"),
            "instagram",
        )

    def test_url_without_scheme(self) -> None:
        self.assertEqual(
            detect_platform("www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "youtube",
        )

    def test_facebook_post(self) -> None:
        self.assertEqual(
            detect_platform("https://www.facebook.com/page/posts/1234567890"),
            "facebook",
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

    def test_tiktok_short_or_vm_host(self) -> None:
        self.assertEqual(
            detect_platform("https://vm.tiktok.com/ZMabc123xyz/"),
            "tiktok",
        )

    def test_unsupported(self) -> None:
        self.assertIsNone(detect_platform("https://example.com/"))


class TestNormalizeUtc(unittest.TestCase):
    def test_naive_treated_as_utc(self) -> None:
        naive = datetime(2020, 1, 1, 12, 0, 0)
        n = normalize_utc(naive)
        self.assertIsNotNone(n)
        self.assertEqual(n.tzinfo, timezone.utc)
        self.assertEqual(n.year, 2020)

    def test_none_stays_none(self) -> None:
        self.assertIsNone(normalize_utc(None))


class TestExtractYoutube(unittest.TestCase):
    def test_id(self) -> None:
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/watch?v=abcDEF12345"),
            "abcDEF12345",
        )

    def test_shorts_id(self) -> None:
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/shorts/abcDEF12345"),
            "abcDEF12345",
        )


class TestMetaEmbedFallback(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.app.config["INSTAGRAM_APP_ID"] = "test-app-id"
        self.app.config["INSTAGRAM_APP_SECRET"] = "test-secret"

    def tearDown(self) -> None:
        self.ctx.pop()

    @patch("app.services.embed._fetch_meta_oembed")
    def test_instagram_falls_back_to_iframe_when_graph_fails(self, mock_meta) -> None:
        mock_meta.side_effect = ValueError("Graph API error")
        html, video_id, title = fetch_embed(
            "https://www.instagram.com/p/ABC123xyz/",
            "instagram",
        )
        self.assertIsNone(video_id)
        self.assertIsNone(title)
        self.assertIn("instagram.com/p/ABC123xyz/embed", html or "")

    @patch("app.services.embed._fetch_meta_oembed")
    def test_facebook_falls_back_to_iframe_when_graph_fails(self, mock_meta) -> None:
        mock_meta.side_effect = ValueError("Graph API error")
        url = "https://www.facebook.com/somepage/posts/1234567890"
        html, video_id, title = fetch_embed(url, "facebook")
        self.assertIsNone(video_id)
        self.assertIn("facebook.com/plugins/post.php", html or "")


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
    def test_refresh_skips_when_fresh_naive_expires_from_sqlite(self, mock_fetch) -> None:
        """SQLite returns naive datetimes; must not crash or refetch when still valid."""
        link = Link(
            url="https://x.com/a/status/1",
            platform="twitter",
            embed_html="<p>old</p>",
            video_id=None,
            title=None,
        )
        future = utcnow() + timedelta(days=365)
        link.fetched_at = future - timedelta(hours=1)
        link.expires_at = future.replace(tzinfo=None)
        out = refresh_embed_if_stale(link)
        self.assertFalse(out)
        mock_fetch.assert_not_called()

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
