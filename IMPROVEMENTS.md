# Social Media Link Aggregator – Improvements

## Goals
- Make embeds more reliable over time.
- Improve performance (fast initial load, fewer network calls).
- Add user accounts + ownership.
- Add sharing (public/unlisted feeds).
- Harden security around embedding third-party HTML.

## 1) Embedding reliability
- Rework storage from “embed_html forever” to “source data + cached embed”.
  - Store `platform`, `external_id` (YouTube video id, X status id, TikTok id), and `url`.
  - Store `embed_html` (or `embed_type + ids`) with `fetched_at` and `expires_at`.
- Add a “refresh embed” capability per link and a background refresh job (later).
- Improve URL parsing coverage:
  - YouTube: `shorts/`, playlists, `&t=`, `embed/` URLs.
  - X: quotes/reposts, additional URL formats, pinned tweets.
  - TikTok: variations like `/@user/video/<id>`, different domains.
  - Instagram (Phase 2): handle `p/`, `reel/`, `tv/` plus shared URLs.

## 2) Performance & caching
- Cache oEmbed results:
  - Avoid fetching on every page render.
  - Cache in DB with timestamps; refresh only when stale.
- Lazy load embeds:
  - Render placeholders first; load iframe/embed HTML when the card becomes visible.
- Reduce page weight:
  - Limit iframe dimensions consistently.
  - Use `loading="lazy"` where supported.

## 3) Security hardening
- Avoid unbounded `| safe` rendering for third-party HTML.
  - Sanitize oEmbed HTML with an allowlist (recommended).
  - Restrict allowed tags/attributes before inserting into templates.
- Validate and normalize user-submitted URLs:
  - Require `https://`
  - Enforce hostname allowlist per platform.
- Add CSRF protection for form submissions (next step).
- Implement a stricter Content Security Policy (CSP) once embed rendering is stable.

## 4) UI/UX improvements (professional polish)
- Inline validation:
  - Show errors under the input instead of flashes + redirects.
- Better empty states:
  - Examples for each platform (with copyable examples).
- Card improvements:
  - Consistent aspect ratios and spacing.
  - Add “Open original” and “Refresh embed” actions (later).
- Add responsive loading skeletons for embeds.

## 5) Sharing features
- Public share page:
  - Add a `share_slug` or token that maps to a feed (your “channel” concept).
  - Route examples:
    - `/s/<slug>` to view a shareable feed.
    - Optional: `/u/<username>` for profile-like feeds.
- Sharing UI:
  - “Copy link” button.
  - Open the share in a new tab.
- Privacy modes (when login exists):
  - `private` (only owner)
  - `unlisted` (token/slug)
  - `public`

## 6) Authentication & user ownership (next major step)
- Add login (recommended stack: `Flask-Login`).
- Data model changes:
  - `User` table.
  - `Link.user_id` (ownership).
  - Optional: `Feed` table if you want multiple feeds per user.
- User features:
  - Add/Delete links.
  - Refresh embed.
  - Reorder links.

## 7) Embed/Widget improvements
- Consider standardized “embed renderer”:
  - `youtube` → iframe renderer.
  - `twitter` → widget HTML loader (script once, `twttr.widgets.load()`).
  - `tiktok` → iframe-like embed HTML from oEmbed with proper container.
  - `instagram` → placeholder until Phase 2 Meta token is configured.
- Add provider error handling:
  - If one provider fails, show a friendly error in the card.
  - Store “embed_failed_at” and error message (sanitized).

## 8) Observability & maintainability
- Add basic logging:
  - Provider request latency and error counts.
  - Embed fetch failures per platform.
- Add tests:
  - Unit tests for URL detection/extraction.
  - Integration tests for oEmbed calls (optionally mocked).
- Add rate limiting:
  - Prevent abuse of `/add` endpoint.

## 9) Deployment readiness
- Add production database option (PostgreSQL) with migrations:
  - Use Alembic/Flask-Migrate instead of only `create_all()`.
- Add environment-based config:
  - `SECRET_KEY`, `DATABASE_URL`, Instagram credentials.
- Add a `Procfile` (or deployment config) for hosting services.

## Suggested roadmap (ordered)
1. Caching + stale refresh (`fetched_at`, `expires_at`) for oEmbed.
2. Security: sanitize embed_html + URL allowlist validation.
3. UX polish: inline errors + better card actions.
4. Sharing with a public/unlisted feed slug.
5. Login + ownership (Flask-Login + `user_id` on links).
6. Migrations + production DB + deployment hardening.

