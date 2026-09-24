"""Flask application factory."""

from __future__ import annotations

from flask import Flask

from core.database import get_db_path


def create_app(db_path: str | None = None) -> Flask:
    """Build and return a configured Flask application."""
    app = Flask(__name__, static_folder="static", static_url_path="")

    # Disable static file caching in development.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Persist DB path so before_request can reference it.
    if db_path is None:
        db_path = str(get_db_path())
    app.config["DB_PATH"] = db_path

    # Register blueprints
    from web.routes import main_bp

    app.register_blueprint(main_bp)

    return app