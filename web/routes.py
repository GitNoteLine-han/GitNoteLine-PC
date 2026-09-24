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
    "/init/2/1",
    "/api/hello",
    "/api/init/prefill",
    "/api/init/step1",
    "/api/init/step2/1",
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
    db_path = current_app.config.get("DB_PATH", "")
    if db_path and os.path.exists(db_path):
        return redirect("/init/2")
    return current_app.send_static_file("init-1.html")


@main_bp.route("/init/2")
def init_step2():
    return current_app.send_static_file("init-2.html")


@main_bp.route("/init/2/1")
def init_step2_1_page():
    return current_app.send_static_file("init-2-1.html")


@main_bp.route("/init/2/2")
@main_bp.route("/init/2/3")
@main_bp.route("/init/2/4")
def init_step2_sub():
    return "", 204


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
    source = (data.get("source") or "manual").strip()

    if source not in ("git", "manual"):
        source = "manual"

    if not name:
        return jsonify({"ok": False, "error": "用户名不能为空"}), 400
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "邮箱格式不正确"}), 400

    db_path = current_app.config.get("DB_PATH", "")
    from core.services import init_step1
    init_step1(db_path, name, email, source)

    return jsonify({"ok": True})


@main_bp.route("/api/init/step2/1/default-path")
def api_init_step2_1_default_path():
    """Get default local path based on remote URL."""
    remote_url = request.args.get("remote_url", "").strip()
    
    from core.services import get_default_repo_path
    default_path = get_default_repo_path(remote_url)
    
    return jsonify({"ok": True, "default_path": default_path})


@main_bp.route("/api/init/step2/1", methods=["POST"])
def api_init_step2_1():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    remote_url = (data.get("remote_url") or "").strip()
    local_path = (data.get("local_path") or "").strip()
    credential_name = (data.get("credential_name") or "").strip()
    credential_type = (data.get("credential_type") or "").strip()
    credential_secret = (data.get("credential_secret") or "").strip()

    # Validation
    if not local_path:
        return jsonify({"ok": False, "error": "本地路径不能为空"}), 400
    if not credential_name:
        return jsonify({"ok": False, "error": "凭证名称不能为空"}), 400
    if credential_type not in ("password", "fine_grained"):
        return jsonify({"ok": False, "error": "凭证类型无效"}), 400
    if not credential_secret:
        return jsonify({"ok": False, "error": "凭证不能为空"}), 400

    db_path = current_app.config.get("DB_PATH", "")
    from core.services import init_step2_1
    
    result = init_step2_1(
        db_path=db_path,
        remote_url=remote_url,
        local_path=local_path,
        credential_name=credential_name,
        credential_type=credential_type,
        credential_secret=credential_secret,
    )
    
    if not result.get("ok"):
        return jsonify(result), 400
    
    return jsonify(result)