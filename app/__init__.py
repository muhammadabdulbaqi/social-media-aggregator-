"""Application factory and extensions."""
import os
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

from app.config import config_by_name

db = SQLAlchemy()


def _ensure_link_oembed_cache_columns() -> None:
    """Add fetched_at / expires_at to links when upgrading (create_all does not alter existing tables)."""
    engine = db.engine
    insp = inspect(engine)
    if "links" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("links")}
    dialect = engine.dialect.name
    ts = "DATETIME" if dialect == "sqlite" else "TIMESTAMP WITH TIME ZONE"
    stmts: list[str] = []
    if "fetched_at" not in cols:
        stmts.append(f"ALTER TABLE links ADD COLUMN fetched_at {ts}")
    if "expires_at" not in cols:
        stmts.append(f"ALTER TABLE links ADD COLUMN expires_at {ts}")
    if not stmts:
        return
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        instance_relative_config=True,
    )
    env = config_name or os.environ.get("FLASK_ENV", "default")
    app.config.from_object(config_by_name[env])

    # Ensure instance folder exists (for SQLite in dev)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from app.routes import main as main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        _ensure_link_oembed_cache_columns()

    return app
