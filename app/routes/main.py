"""Main routes: index and add link."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import db
from app.models import Link
from app.services import (
    apply_oembed_cache_fields,
    detect_platform,
    fetch_embed,
    refresh_embed_if_stale,
)

main = Blueprint("main", __name__)


@main.route("/")
def index():
    """Home: list all embedded links; refresh stale oEmbed HTML before render."""
    links = Link.query.order_by(Link.created_at.desc()).all()
    updated = False
    for link in links:
        if refresh_embed_if_stale(link):
            updated = True
    if updated:
        db.session.commit()
    return render_template("index.html", links=links)


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
    )
    apply_oembed_cache_fields(link, platform)
    db.session.add(link)
    db.session.commit()

    if request.is_json:
        return {"id": link.id, "url": link.url, "platform": link.platform}, 201
    return redirect(url_for("main.index"))
