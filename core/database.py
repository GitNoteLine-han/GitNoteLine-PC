"""Data-directory and SQLite helpers.

Platform-specific defaults:
  Linux   → ~/.gitnoteline/
  macOS   → ~/Library/Application Support/GitNoteLine/
  Windows → %APPDATA%\GitNoteLine\
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def get_data_dir(custom_path: str | None = None) -> Path:
    """Resolve the platform-specific data directory.

    If *custom_path* looks like a file path (has a suffix),
    its parent directory is returned instead.
    """
    if custom_path:
        p = Path(custom_path)
        return p.parent if p.suffix else p

    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        return Path(base) / "GitNoteLine"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GitNoteLine"
    return Path.home() / ".gitnoteline"


def get_db_path(custom_path: str | None = None) -> Path:
    """Resolve the full path to ``userdata.db``."""
    if custom_path:
        p = Path(custom_path)
        if p.suffix:
            return p  # explicit file path like /foo/bar.db
        return p / "userdata.db"
    return get_data_dir() / "userdata.db"


def ensure_db(db_path: str | Path) -> sqlite3.Connection:
    """Create the data directory and ``userdata.db`` if missing.

    Returns an open connection (with ``row_factory`` set to ``Row``).
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    
    # Settings table (key-value store)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )"""
    )
    
    # Credentials table (encrypted secrets stored here)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            host TEXT,
            encrypted_secret TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    
    # Repositories table
    conn.execute(
        """CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            path TEXT NOT NULL,
            remote_url TEXT,
            credential_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (credential_id) REFERENCES credentials(id)
        )"""
    )
    
    conn.commit()
    return conn


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    """Read a single setting from the DB."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()