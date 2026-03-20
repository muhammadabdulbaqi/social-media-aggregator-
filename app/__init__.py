"""Application factory and extensions."""
import os
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.config import config_by_name

db = SQLAlchemy()


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

    return app
