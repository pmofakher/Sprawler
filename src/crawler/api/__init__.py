"""API package containing FastAPI routes, models, and application factory."""

from crawler.api.app import app, create_app

__all__ = ["app", "create_app"]
