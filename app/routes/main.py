"""Main routes: index and add link."""
from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, url_for

from app import db
from app.feed import (
    PLATFORM_LABELS,
    group_links_by_platform,
    next_sort_order_for_platform,
    ordered_platform_keys,
    sort_links_for_unified_view,
)
from app.models import Link
from app.services import (
    apply_oembed_cache_fields,
    detect_platform,
    fetch_embed,
    refresh_embed_if_stale,
)

main = Blueprint("main", __name__)

VIEW_MODE_COOKIE = "aggregator_view"
UNIFIED_SORT_COOKIE = "aggregator_unified_sort"


@main.route("/")
def index():
    """Home: list all embedded links; refresh stale oEmbed HTML before render."""
    links = Link.query.all()
    updated = False
    for link in links:
        if refresh_embed_if_stale(link):
            updated = True
    if updated:
        db.session.commit()

    view_mode = request.cookies.get(VIEW_MODE_COOKIE, "platform")
    unified_sort = request.cookies.get(UNIFIED_SORT_COOKIE, "recent")
    if view_mode not in ("platform", "unified"):
        view_mode = "platform"
    if unified_sort not in ("recent", "oldest"):
        unified_sort = "recent"

    link_groups = group_links_by_platform(links)
    platform_order = ordered_platform_keys(link_groups)
    unified_links = sort_links_for_unified_view(links, unified_sort) if links else []
    feed_has_links = bool(links)
    has_twitter_embeds = any(l.platform == "twitter" for l in links)

    html = render_template(
        "index.html",
        link_groups=link_groups,
        platform_order=platform_order,
        platform_labels=PLATFORM_LABELS,
        view_mode=view_mode,
        unified_sort=unified_sort,
        unified_links=unified_links,
        feed_has_links=feed_has_links,
        has_twitter_embeds=has_twitter_embeds,
    )
    resp = make_response(html)
    if current_app.debug:
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@main.route("/add", methods=["POST"])
def add_link():
    """Add a new link: validate URL, fetch embed, persist, then redirect or return JSON."""
    url = ""
    if request.is_json:
        url = (request.get_json(silent=True) or {}).get("url", "")
    else:
        url = request.form.get("url", "")

    url = url.strip()
    if not url:
        if request.is_json:
            return {"error": "URL is required"}, 400
        flash("URL is required.", "error")
        return redirect(url_for("main.index"))

    platform = detect_platform(url)
    if not platform:
        if request.is_json:
            return {
                "error": "Unsupported URL. Use YouTube, X (Twitter), or TikTok links.",
            }, 400
        flash("Unsupported URL. Use YouTube, X (Twitter), or TikTok links.", "error")
        return redirect(url_for("main.index"))

    try:
        embed_html, video_id, title = fetch_embed(url, platform)
    except Exception as e:
        if request.is_json:
            return {"error": str(e)}, 400
        flash(str(e), "error")
        return redirect(url_for("main.index"))

    link = Link(
        url=url,
        platform=platform,
        embed_html=embed_html,
        video_id=video_id,
        title=title,
        sort_order=next_sort_order_for_platform(platform),
    )
    apply_oembed_cache_fields(link, platform)
    db.session.add(link)
    db.session.commit()

    if request.is_json:
        return {"id": link.id, "url": link.url, "platform": link.platform}, 201
    return redirect(url_for("main.index"))


@main.post("/links/reorder")
def reorder_links():
    """Persist order of links within one platform (from drag-and-drop)."""
    data = request.get_json(silent=True) or {}
    platform = data.get("platform")
    ids = data.get("ids")
    if not platform or not isinstance(ids, list) or not ids:
        return {"error": "platform and ids[] required"}, 400
    for i, lid in enumerate(ids):
        try:
            lid_int = int(lid)
        except (TypeError, ValueError):
            return {"error": "invalid id"}, 400
        link = db.session.get(Link, lid_int)
        if not link:
            return {"error": f"unknown id {lid_int}"}, 404
        if link.platform != platform:
            return {"error": "platform mismatch"}, 400
        link.sort_order = i
    db.session.commit()
    return {"ok": True}


@main.post("/links/<int:link_id>/delete")
def delete_link(link_id: int):
    """Remove a stored embed."""
    link = db.session.get(Link, link_id)
    if not link:
        flash("Link not found.", "error")
        return redirect(url_for("main.index"))
    db.session.delete(link)
    db.session.commit()
    flash("Embed removed.", "success")
    return redirect(url_for("main.index"))
