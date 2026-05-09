"""Feed grouping and per-platform ordering helpers."""
from __future__ import annotations

from collections import defaultdict

from app import db
from app.models import Link

DEFAULT_PLATFORM_ORDER = ["youtube", "twitter", "tiktok", "instagram"]

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "twitter": "X (Twitter)",
    "tiktok": "TikTok",
    "instagram": "Instagram",
}


def group_links_by_platform(links: list[Link]) -> dict[str, list[Link]]:
    """Group links by platform; within each platform sort by sort_order then id."""
    groups: dict[str, list[Link]] = defaultdict(list)
    for link in links:
        groups[link.platform].append(link)
    for plat in groups:
        groups[plat].sort(key=lambda L: (L.sort_order, L.id))
    return dict(groups)


def ordered_platform_keys(groups: dict[str, list[Link]]) -> list[str]:
    """Platforms that have links: canonical order first, then any other keys (legacy or future)."""
    canonical = [p for p in DEFAULT_PLATFORM_ORDER if p in groups and groups[p]]
    seen = set(canonical)
    rest = sorted(p for p in groups if groups[p] and p not in seen)
    return canonical + rest


def sort_links_for_unified_view(links: list[Link], unified_sort: str) -> list[Link]:
    """Single-feed order: newest or oldest first (stable tie-breaker by id)."""
    lst = list(links)
    reverse = unified_sort != "oldest"

    def sort_key(L: Link) -> tuple[float, int]:
        ts = L.created_at.timestamp() if L.created_at else 0.0
        return (ts, L.id)

    lst.sort(key=sort_key, reverse=reverse)
    return lst


def next_sort_order_for_platform(platform: str) -> int:
    """Next sort_order for a new link on this platform."""
    from sqlalchemy import func

    m = (
        db.session.query(func.max(Link.sort_order))
        .filter(Link.platform == platform)
        .scalar()
    )
    return (m if m is not None else -1) + 1


def backfill_sort_order_if_needed() -> None:
    """
    After adding sort_order column, rows may all be 0. Order by created_at once per platform.
    Skip if any link already has a non-zero sort_order (user or prior backfill).
    """
    groups: dict[str, list[Link]] = defaultdict(list)
    for link in Link.query.all():
        groups[link.platform].append(link)
    touched = False
    for _plat, lst in groups.items():
        if len(lst) <= 1:
            continue
        if max(x.sort_order for x in lst) != 0:
            continue
        if not all(x.sort_order == 0 for x in lst):
            continue
        lst.sort(key=lambda x: (x.created_at, x.id))
        for i, x in enumerate(lst):
            x.sort_order = i
            touched = True
    if touched:
        db.session.commit()
