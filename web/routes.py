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
    "/init/2",
    "/init/2/1",
    "/init/2/2",
    "/init/2/3",
    "/init/2/4",
    "/apitest",
    "/api/hello",
    "/api/init/prefill",
    "/api/init/step1",
    "/api/init/step2/1",
    "/api/init/step2/2",
    "/api/init/step2/3",
    "/api/init/step2/3/check",
    "/api/init/step2/4",
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


@main_bp.route("/apitest")
def apitest():
    return current_app.send_static_file("index.html")


@main_bp.route("/")
def index():
    """Main page - note management interface."""
    return current_app.send_static_file("main.html")


@main_bp.route("/editor")
def editor():
    """Editor page for editing notes."""
    return current_app.send_static_file("editor.html")


@main_bp.route("/setting")
def setting():
    """Settings page."""
    return current_app.send_static_file("setting.html")


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
def init_step2_2_page():
    return current_app.send_static_file("init-2-2.html")


@main_bp.route("/init/2/3")
def init_step2_3_page():
    return current_app.send_static_file("init-2-3.html")


@main_bp.route("/init/2/4")
def init_step2_4_page():
    return current_app.send_static_file("init-2-4.html")


# ── API ─────────────────────────────────────────────────────────────


@main_bp.route("/api/hello")
def api_hello():
    return jsonify({"message": "Hello from GitNoteLine!"})


@main_bp.route("/api/settings")
def api_settings():
    """Get user settings (git name, email)."""
    db_path = current_app.config.get("DB_PATH", "")

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    git_name = conn.execute("SELECT value FROM settings WHERE key = 'git_name'").fetchone()
    git_email = conn.execute("SELECT value FROM settings WHERE key = 'git_email'").fetchone()

    conn.close()

    return jsonify({
        "ok": True,
        "git_name": git_name["value"] if git_name else "",
        "git_email": git_email["value"] if git_email else "",
    })


@main_bp.route("/api/settings", methods=["POST"])
def api_settings_update():
    """Update a setting value."""
    from flask import request

    data = request.get_json()
    key = data.get("key")
    value = data.get("value")

    if not key or value is None:
        return jsonify({"ok": False, "error": "缺少参数"}), 400

    if key not in ("git_name", "git_email"):
        return jsonify({"ok": False, "error": "无效的设置项"}), 400

    db_path = current_app.config.get("DB_PATH", "")

    import sqlite3
    conn = sqlite3.connect(db_path)

    # Check if setting exists
    existing = conn.execute("SELECT key FROM settings WHERE key = ?", (key,)).fetchone()

    if existing:
        conn.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    else:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()

    return jsonify({"ok": True})


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


@main_bp.route("/api/init/step2/2/default-path")
def api_init_step2_2_default_path():
    """Get default local path based on remote URL (same as 2/1)."""
    remote_url = request.args.get("remote_url", "").strip()

    from core.services import get_default_repo_path
    default_path = get_default_repo_path(remote_url)

    return jsonify({"ok": True, "default_path": default_path})


@main_bp.route("/api/init/step2/2", methods=["POST"])
def api_init_step2_2():
    """Clone an existing remote repository."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    remote_url = (data.get("remote_url") or "").strip()
    local_path = (data.get("local_path") or "").strip()
    credential_name = (data.get("credential_name") or "").strip()
    credential_type = (data.get("credential_type") or "").strip()
    credential_secret = (data.get("credential_secret") or "").strip()

    # Validation
    if not remote_url:
        return jsonify({"ok": False, "error": "远程仓库 URL 不能为空"}), 400
    if not local_path:
        return jsonify({"ok": False, "error": "本地路径不能为空"}), 400
    if not credential_name:
        return jsonify({"ok": False, "error": "凭证名称不能为空"}), 400
    if credential_type not in ("password", "fine_grained"):
        return jsonify({"ok": False, "error": "凭证类型无效"}), 400
    if not credential_secret:
        return jsonify({"ok": False, "error": "凭证不能为空"}), 400

    db_path = current_app.config.get("DB_PATH", "")
    from core.services import init_step2_2

    result = init_step2_2(
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


@main_bp.route("/api/init/step2/3/check", methods=["POST"])
def api_init_step2_3_check():
    """Check if a path is a valid Git repo and if it has a remote."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    local_path = (data.get("local_path") or "").strip()
    if not local_path:
        return jsonify({"ok": False, "error": "本地路径不能为空"}), 400

    from pathlib import Path
    import subprocess

    repo_path = Path(local_path)

    # Verify it's a valid Git repository
    if not repo_path.exists():
        return jsonify({"ok": False, "error": "路径不存在"})

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return jsonify({"ok": False, "error": "不是有效的 Git 仓库"})

    # Check if remote (origin) exists
    remote_result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path, capture_output=True, text=True, timeout=5,
    )

    has_remote = remote_result.returncode == 0
    remote_url = remote_result.stdout.strip() if has_remote else ""

    return jsonify({
        "ok": True,
        "has_remote": has_remote,
        "remote_url": remote_url,
    })


@main_bp.route("/api/init/step2/3", methods=["POST"])
def api_init_step2_3():
    """Link an existing local repository."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    local_path = (data.get("local_path") or "").strip()
    credential_name = (data.get("credential_name") or "").strip()
    credential_type = (data.get("credential_type") or "").strip()
    credential_secret = (data.get("credential_secret") or "").strip()

    # Validation
    if not local_path:
        return jsonify({"ok": False, "error": "本地路径不能为空"}), 400

    # Credentials are optional for 2/3 (depends on whether repo has remote)
    # But if provided, all must be present
    if credential_name or credential_secret:
        if not credential_name:
            return jsonify({"ok": False, "error": "凭证名称不能为空"}), 400
        if credential_type and credential_type not in ("password", "fine_grained"):
            return jsonify({"ok": False, "error": "凭证类型无效"}), 400
        if not credential_secret:
            return jsonify({"ok": False, "error": "凭证不能为空"}), 400

    db_path = current_app.config.get("DB_PATH", "")
    from core.services import init_step2_3

    result = init_step2_3(
        db_path=db_path,
        local_path=local_path,
        credential_name=credential_name,
        credential_type=credential_type,
        credential_secret=credential_secret,
    )

    if not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result)


@main_bp.route("/api/init/step2/4", methods=["POST"])
def api_init_step2_4():
    """Create a local-only repository."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    local_path = (data.get("local_path") or "").strip()

    # Validation
    if not local_path:
        return jsonify({"ok": False, "error": "本地路径不能为空"}), 400

    db_path = current_app.config.get("DB_PATH", "")
    from core.services import init_step2_4

    result = init_step2_4(
        db_path=db_path,
        local_path=local_path,
    )

    if not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result)


# ── Notes API ───────────────────────────────────────────────────────


@main_bp.route("/api/repos/list")
def api_repos_list():
    """List all repositories."""
    db_path = current_app.config.get("DB_PATH", "")
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    repos = conn.execute("SELECT id, name, path FROM repositories").fetchall()
    conn.close()
    
    return jsonify({
        "ok": True,
        "repos": [
            {
                "id": repo["id"],
                "name": repo["name"] or Path(repo["path"]).name,
                "path": repo["path"],
            }
            for repo in repos
        ],
    })


@main_bp.route("/api/repo/info")
def api_repo_info():
    """Get current repository information."""
    db_path = current_app.config.get("DB_PATH", "")

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get the first repository (current version only supports one)
    repo = conn.execute("SELECT id, name, path, remote_url FROM repositories LIMIT 1").fetchone()
    conn.close()

    if not repo:
        return jsonify({"ok": False, "error": "未配置仓库"}), 404

    return jsonify({
        "ok": True,
        "id": repo["id"],
        "name": repo["name"],
        "path": repo["path"],
        "remote_url": repo["remote_url"] or "",
    })


@main_bp.route("/api/notes/list")
def api_notes_list():
    """List all .md files in the repository (with subdirectory support)."""
    db_path = current_app.config.get("DB_PATH", "")
    repo_id = request.args.get("repo_id", type=int)
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get the specified repository or the first one
    if repo_id:
        repo = conn.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,)).fetchone()
    else:
        repo = conn.execute("SELECT path FROM repositories LIMIT 1").fetchone()
    conn.close()
    
    if not repo:
        return jsonify({"ok": False, "error": "未配置仓库"}), 404
    
    repo_path = Path(repo["path"])
    if not repo_path.exists():
        return jsonify({"ok": False, "error": "仓库路径不存在"}), 404
    
    # Find all .md files
    notes = []
    for md_file in repo_path.rglob("*.md"):
        # Skip hidden files and .git directory
        if any(part.startswith('.') for part in md_file.relative_to(repo_path).parts):
            continue
        
        # Get relative path from repo root
        rel_path = md_file.relative_to(repo_path)
        # Remove .md extension for display
        note_name = str(rel_path.with_suffix(''))
        
        notes.append({
            "name": note_name,
            "path": str(rel_path),
        })
    
    # Sort by filename
    notes.sort(key=lambda x: x["name"].lower())
    
    return jsonify({"ok": True, "notes": notes})


@main_bp.route("/api/notes/<path:note_path>")
def api_notes_get(note_path):
    """Get note content."""
    db_path = current_app.config.get("DB_PATH", "")
    repo_id = request.args.get("repo_id", type=int)
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get the specified repository or the first one
    if repo_id:
        repo = conn.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,)).fetchone()
    else:
        repo = conn.execute("SELECT path FROM repositories LIMIT 1").fetchone()
    conn.close()
    
    if not repo:
        return jsonify({"ok": False, "error": "未配置仓库"}), 404
    
    repo_path = Path(repo["path"])
    
    # Add .md extension if not present
    if not note_path.endswith('.md'):
        note_path = note_path + '.md'
    
    note_file = repo_path / note_path
    
    # Security check: ensure the file is within the repo
    try:
        note_file.resolve().relative_to(repo_path.resolve())
    except ValueError:
        return jsonify({"ok": False, "error": "无效的路径"}), 400
    
    if not note_file.exists():
        return jsonify({"ok": False, "error": "笔记不存在"}), 404
    
    try:
        content = note_file.read_text(encoding='utf-8')
        return jsonify({"ok": True, "content": content, "path": note_path})
    except Exception as e:
        return jsonify({"ok": False, "error": f"读取失败: {str(e)}"}), 500


@main_bp.route("/api/notes/<path:note_path>", methods=["PUT"])
def api_notes_update(note_path):
    """Update note content."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    content = data.get("content", "")
    repo_id = data.get("repo_id")

    db_path = current_app.config.get("DB_PATH", "")

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get the specified repository or the first one
    if repo_id:
        repo = conn.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,)).fetchone()
    else:
        repo = conn.execute("SELECT path FROM repositories LIMIT 1").fetchone()
    conn.close()

    if not repo:
        return jsonify({"ok": False, "error": "未配置仓库"}), 404

    repo_path = Path(repo["path"])

    # Add .md extension if not present
    if not note_path.endswith('.md'):
        note_path = note_path + '.md'

    note_file = repo_path / note_path

    # Security check: ensure the file is within the repo
    try:
        note_file.resolve().relative_to(repo_path.resolve())
    except ValueError:
        return jsonify({"ok": False, "error": "无效的路径"}), 400

    if not note_file.exists():
        return jsonify({"ok": False, "error": "笔记不存在"}), 404

    try:
        note_file.write_text(content, encoding='utf-8')
        return jsonify({"ok": True, "path": note_path})
    except Exception as e:
        return jsonify({"ok": False, "error": f"保存失败: {str(e)}"}), 500


@main_bp.route("/api/repo/<int:repo_id>/images")
def api_repo_images(repo_id):
    """List all images in the repository's img/ directory."""
    db_path = current_app.config.get("DB_PATH", "")
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    repo = conn.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,)).fetchone()
    conn.close()
    
    if not repo:
        return jsonify({"ok": False, "error": "仓库不存在"}), 404
    
    repo_path = Path(repo["path"])
    img_dir = repo_path / "img"
    
    if not img_dir.exists():
        return jsonify({"ok": True, "images": []})
    
    # List all image files
    images = []
    for img_file in img_dir.iterdir():
        if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']:
            images.append({
                "name": img_file.name,
                "path": f"img/{img_file.name}",
                "size": img_file.stat().st_size,
                "modified": img_file.stat().st_mtime,
            })
    
    # Sort by modification time (newest first)
    images.sort(key=lambda x: x["modified"], reverse=True)
    
    return jsonify({"ok": True, "images": images})


@main_bp.route("/api/repo/<int:repo_id>/images/upload", methods=["POST"])
def api_repo_images_upload(repo_id):
    """Upload images to the repository's img/ directory."""
    if 'images' not in request.files:
        return jsonify({"ok": False, "error": "没有图片文件"}), 400
    
    files = request.files.getlist('images')
    if not files:
        return jsonify({"ok": False, "error": "没有选择文件"}), 400
    
    db_path = current_app.config.get("DB_PATH", "")
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    repo = conn.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,)).fetchone()
    conn.close()
    
    if not repo:
        return jsonify({"ok": False, "error": "仓库不存在"}), 404
    
    repo_path = Path(repo["path"])
    img_dir = repo_path / "img"
    
    # Create img directory if it doesn't exist
    img_dir.mkdir(exist_ok=True)
    
    uploaded = []
    for file in files:
        if file and file.filename:
            # Generate unique filename with timestamp
            import time
            from pathlib import PurePosixPath
            original_name = PurePosixPath(file.filename).name
            timestamp = int(time.time() * 1000)
            name_parts = original_name.rsplit('.', 1)
            if len(name_parts) == 2:
                new_filename = f"{name_parts[0]}-{timestamp}.{name_parts[1]}"
            else:
                new_filename = f"{original_name}-{timestamp}"
            
            file_path = img_dir / new_filename
            file.save(file_path)
            
            uploaded.append({
                "name": new_filename,
                "path": f"img/{new_filename}",
            })
    
    return jsonify({"ok": True, "uploaded": uploaded})


@main_bp.route("/api/notes", methods=["POST"])
def api_notes_create():
    """Create a new note."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "请求体为空"}), 400

    note_name = (data.get("name") or "").strip()
    content = data.get("content", "")
    repo_id = data.get("repo_id")

    if not note_name:
        return jsonify({"ok": False, "error": "笔记名称不能为空"}), 400

    # Security check: prevent path traversal
    if '..' in note_name or note_name.startswith('/'):
        return jsonify({"ok": False, "error": "无效的笔记名称"}), 400

    db_path = current_app.config.get("DB_PATH", "")

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get the specified repository or the first one
    if repo_id:
        repo = conn.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,)).fetchone()
    else:
        repo = conn.execute("SELECT path FROM repositories LIMIT 1").fetchone()
    conn.close()
    
    if not repo:
        return jsonify({"ok": False, "error": "未配置仓库"}), 404
    
    repo_path = Path(repo["path"])
    
    # Add .md extension if not present
    if not note_name.endswith('.md'):
        note_name = note_name + '.md'
    
    note_file = repo_path / note_name
    
    # Security check: ensure the file is within the repo
    try:
        note_file.resolve().relative_to(repo_path.resolve())
    except ValueError:
        return jsonify({"ok": False, "error": "无效的路径"}), 400
    
    # Check if file already exists
    if note_file.exists():
        return jsonify({"ok": False, "error": "笔记已存在"}), 409
    
    try:
        # Create parent directories if needed
        note_file.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        note_file.write_text(content, encoding='utf-8')

        return jsonify({"ok": True, "path": note_name})
    except Exception as e:
        return jsonify({"ok": False, "error": f"创建失败: {str(e)}"}), 500


# ── Sync API ───────────────────────────────────────────────────────


@main_bp.route("/api/repo/<int:repo_id>/pull", methods=["POST"])
def api_repo_pull(repo_id):
    """Pull from remote repository."""
    db_path = current_app.config.get("DB_PATH", "")
    from core.services import sync_pull

    result = sync_pull(db_path, repo_id)

    if not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result)


@main_bp.route("/api/repo/<int:repo_id>/push", methods=["POST"])
def api_repo_push(repo_id):
    """Commit and push to remote repository."""
    db_path = current_app.config.get("DB_PATH", "")
    from core.services import sync_push

    result = sync_push(db_path, repo_id)

    if not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result)


@main_bp.route("/api/repo/<int:repo_id>/sync-status")
def api_repo_sync_status(repo_id):
    """Get sync status for a repository."""
    db_path = current_app.config.get("DB_PATH", "")
    from core.services import get_sync_status

    return jsonify(get_sync_status(db_path, repo_id))