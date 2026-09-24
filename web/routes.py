"""Application routes and API endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, request

_STATIC = (Path(__file__).parent / "static").resolve()

main_bp = Blueprint("main", __name__)


# ── Init guard ──────────────────────────────────────────────────────

_ALLOWED_BEFORE_INIT = frozenset({
    "/init/1",
    "/api/hello",
    "/api/init/prefill",
    "/api/init/step1",
})


@main_bp.before_request
def _check_initialized():
    if request.path in _ALLOWED_BEFORE_INIT:
        return None

    db_path = current_app.config.get("DB_PATH", "")
    if db_path and not os.path.exists(db_path):
        return redirect("/init/1")
    return None


# ── HTML pages ──────────────────────────────────────────────────────


@main_bp.route("/")
def index():
    return current_app.send_static_file("index.html")


@main_bp.route("/init/1")
def init_page():
    return current_app.send_static_file("init-1.html")


@main_bp.route("/init/2")
def init_step2_placeholder():
    return current_app.send_static_file("init-2.html")


# ── API ─────────────────────────────────────────────────────────────


@main_bp.route("/api/hello")
def api_hello():
    return jsonify({"message": "Hello from GitNoteLine!"})


@main_bp.route("/api/init/prefill")
def api_init_prefill():
    from core.services import get_identity_prefill
    return jsonify(get_identity_prefill())


@main_bp.route("/api/init/step1", methods=["POST"])
def api_init_step1():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()

    if not name:
        return jsonify({"ok": False, "error": "用户名不能为空"}), 400
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "邮箱格式不正确"}), 400

    db_path = current_app.config.get("DB_PATH", "")
    from core.services import init_step1
    init_step1(db_path, name, email)

    return jsonify({"ok": True})