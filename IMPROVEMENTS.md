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

## 10) Tags, filtering & search
- Add tags (labels) on links or feeds:
  - Many-to-many or comma-separated tags on `Link` (or a `Tag` table for normalization).
- Filter the feed by one or more tags (AND/OR behavior—pick one and document it).
- Search:
  - Full-text or simple `ILIKE` on title, notes, URL, and tag names.
- UI:
  - Tag chips on cards, a tag filter bar, and clear “reset filters” behavior.

## 11) Download video / image
- Let users download attached media where policy and tech allow:
  - Prefer official APIs or documented embed metadata; respect Terms of Service and copyright.
  - For platforms that forbid re-hosting or bulk download, offer “open original” / save-from-browser instead of server-side ripping.
- Implementation options (choose per platform):
  - Direct file URL from oEmbed/API when exposed.
  - Deferred: server-side fetch only if legally and technically viable; otherwise link out.

## 12) More social platforms & connections
- Expand beyond current integrations (e.g. YouTube, X, TikTok) with the same pattern:
  - URL parsing → oEmbed or provider API → stored source ids + cached embed.
- Examples to consider:
  - Instagram, Facebook public posts, LinkedIn, Bluesky, Reddit, Pinterest—each needs its own URL rules and often API keys or Meta/developer setup.
- “Connect” accounts (optional, later):
  - OAuth with a platform to import bookmarks or list recent posts, not just paste URLs.
  - Treated as a major feature: tokens, refresh, scopes, and revocation.

## 13) Make more SWE (engineering maturity)
- **Refactoring**
  - Split “god” modules as the app grows (routes vs services vs embed/platform adapters).
  - Keep URL parsing, oEmbed calls, and rendering on clear boundaries so tests can target them without Flask.
  - Pay down tech debt in small passes (rename for clarity, remove dead code) instead of big-bang rewrites.
- **Database**
  - Move from `create_all()` only to **Alembic / Flask-Migrate** so schema changes are versioned and reviewable.
  - Use PostgreSQL (or your production engine) in staging so migrations and queries match prod (SQLite quirks differ).
  - Backup strategy before risky migrations; document how to roll back a bad migration.
- **Docker**
  - Add a **Dockerfile** for a repeatable runtime (pinned base image, non-root user, `EXPOSE` + `CMD` for gunicorn or similar).
  - Optional **docker-compose** for local dev: app + Postgres + env file, so new contributors aren’t blocked by machine-specific DB paths.
  - CI can later `docker build` to catch “works on my laptop” drift.
- **Build**
  - Pin dependencies (`requirements.txt` with version ranges or lockfile workflow) so installs are reproducible.
  - Optional: `Makefile` or `invoke` tasks for `test`, `lint`, `run` so commands are documented in one place.
  - If you add front-end build steps later, same idea: one command that always produces the same artifacts.
- **Ship (deploy & ops)**
  - One clear path to production: env vars (`SECRET_KEY`, `DATABASE_URL`), process model (gunicorn workers), static files.
  - Health check endpoint for load balancers; graceful restarts; log aggregation (stdout is fine on many hosts).
  - Rollback plan: redeploy previous image/release or revert migration with a documented down revision.
- **CI/CD (small but real)**
  - On every push/PR: install deps, run **`python -m unittest discover -s tests -v`** (same as local with `.venv` activated).
  - Optional next: lint/format (`ruff`, `black`), then a deploy job only after tests pass on `main` or tags.
  - Branch protection: require green CI before merge so main stays shippable.
  - Secrets in CI only for deploy or live API tests—not needed for plain unit tests against in-memory SQLite.

## Suggested roadmap (ordered)
1. Caching + stale refresh (`fetched_at`, `expires_at`) for oEmbed.
2. Security: sanitize embed_html + URL allowlist validation.
3. UX polish: inline errors + better card actions.
4. Sharing with a public/unlisted feed slug.
5. Login + ownership (Flask-Login + `user_id` on links).
6. Migrations + production DB + deployment hardening.

For a fuller **order of building and writing** (including tags, downloads, and new platforms), see `BUILD_ORDER.md`.

