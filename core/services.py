"""Business-logic services shared by web and desktop entry points."""

from __future__ import annotations

import os
import subprocess

from core.database import ensure_db, set_setting


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