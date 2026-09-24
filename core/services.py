"""Business-logic services shared by web and desktop entry points."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from core.database import ensure_db, set_setting
from core.credentials import store_credential


# ── Identity helpers ────────────────────────────────────────────────


def _get_git_global_config() -> dict[str, str]:
    """Read Git global ``user.name`` and ``user.email``."""
    result: dict[str, str] = {"name": "", "email": ""}

    try:
        r = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            result["name"] = r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        r = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            result["email"] = r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result


def _get_system_username() -> str:
    for var in ("SUDO_USER", "USER", "USERNAME"):
        val = os.environ.get(var)
        if val:
            return val
    return "user"


# ── Public API ───────────────────────────────────────────────────────


def get_identity_prefill() -> dict:
    """Return best-guess identity for the init form.

    Returns
    -------
    dict with keys ``name``, ``email``, ``source``.
    ``source`` is ``"git"`` when both fields come from Git config,
    ``"system"`` otherwise.
    """
    git = _get_git_global_config()
    username = _get_system_username()

    if git.get("name") and git.get("email"):
        return {"name": git["name"], "email": git["email"], "source": "git"}
    return {
        "name": git.get("name") or username,
        "email": git.get("email") or "",
        "source": "system",
    }


def init_step1(db_path: str, name: str, email: str, source: str = "manual") -> None:
    """Create the database and persist identity settings."""
    conn = ensure_db(db_path)
    set_setting(conn, "git_name", name)
    set_setting(conn, "git_email", email)
    set_setting(conn, "identity_source", source)
    conn.close()


def init_step2_1(
    db_path: str,
    remote_url: str,
    local_path: str,
    credential_name: str,
    credential_type: str,
    credential_secret: str,
) -> dict:
    """Initialize a repository with remote and credentials.
    
    Args:
        db_path: Path to the database
        remote_url: Remote git URL (e.g., https://github.com/user/repo.git)
        local_path: Local path for the repository
        credential_name: User-friendly name for the credential
        credential_type: "password" or "fine_grained"
        credential_secret: The token/password
        
    Returns:
        dict with 'ok', 'error', 'credential_id', 'repo_id'
    """
    # Extract host from URL
    host = ""
    if remote_url:
        try:
            parsed = urlparse(remote_url)
            host = parsed.netloc
        except Exception:
            pass
    
    conn = ensure_db(db_path)
    
    try:
        # Create credential record
        cursor = conn.execute(
            "INSERT INTO credentials (name, type, host) VALUES (?, ?, ?)",
            (credential_name, credential_type, host),
        )
        credential_id = cursor.lastrowid
        
        # Store encrypted secret in database
        if not store_credential(conn, credential_id, credential_secret):
            conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            return {"ok": False, "error": "无法加密存储凭证"}
        
        # Create local repository directory
        repo_path = Path(local_path)
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Git init
        result = subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"Git 初始化失败: {result.stderr}"}
        
        # Add remote if URL provided
        if remote_url:
            result = subprocess.run(
                ["git", "remote", "add", "origin", remote_url],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {"ok": False, "error": f"添加远程仓库失败: {result.stderr}"}
        
        # Create repository record
        cursor = conn.execute(
            "INSERT INTO repositories (path, remote_url, credential_id) VALUES (?, ?, ?)",
            (str(repo_path), remote_url, credential_id),
        )
        repo_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return {"ok": True, "credential_id": credential_id, "repo_id": repo_id}
        
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}
