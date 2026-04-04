"""Link model for stored social media embeds."""
from app import db


class Link(db.Model):
    """A stored social media link (YouTube, X, TikTok, Instagram) with embed data."""

    __tablename__ = "links"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False)
    platform = db.Column(db.String(32), nullable=False)
    embed_html = db.Column(db.Text, nullable=True)
    video_id = db.Column(db.String(64), nullable=True)  # YouTube only
    title = db.Column(db.String(512), nullable=True)
    # Order within the same platform (lower = earlier). Drag-and-drop updates this.
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=db.func.now())
    # oEmbed fetch time and cache expiry (YouTube uses iframe + video_id; expires_at is null).
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Link {self.platform} {self.url[:50]!r}>"
