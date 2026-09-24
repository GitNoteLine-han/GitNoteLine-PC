"""Application routes and API endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, send_from_directory

main_bp = Blueprint("main", __name__)


# ── HTML page ──────────────────────────────────────────────────────


@main_bp.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── API endpoints ──────────────────────────────────────────────────
# Method signatures here serve as the API contract.
# The desktop (pywebview) js_api class will mirror these methods.


@main_bp.route("/api/hello")
def api_hello():
    return jsonify({"message": "Hello from GitNoteLine!"})