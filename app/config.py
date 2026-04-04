"""Application configuration."""
import os
from pathlib import Path


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # oEmbed HTML (X, TikTok, Instagram): refetch after this many seconds when serving the feed.
    OEMBED_CACHE_TTL_SECONDS = int(os.environ.get("OEMBED_CACHE_TTL_SECONDS", "86400"))

    # Optional: Instagram oEmbed (Phase 2)
    INSTAGRAM_APP_ID = os.environ.get("INSTAGRAM_APP_ID")
    INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    BASE_DIR = Path(__file__).resolve().parent.parent
    _db_path = BASE_DIR / "instance" / "links.db"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + str(_db_path).replace("\\", "/"),
    )


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///links.db")


class TestingConfig(Config):
    """Test configuration (in-memory SQLite)."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
