"""Flask application factory."""

from __future__ import annotations

from flask import Flask


def create_app() -> Flask:
    """Build and return a configured Flask application."""
    app = Flask(__name__, static_folder="static", static_url_path="")

    # Register blueprints
    from web.routes import main_bp

    app.register_blueprint(main_bp)

    return app