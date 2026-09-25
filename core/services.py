"""Business-logic services shared by web and desktop entry points."""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from core.database import ensure_db, set_setting, get_data_dir
from core.credentials import store_credential, get_credential


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


def _extract_repo_name(remote_url: str) -> str:
    """Extract repository name from remote URL.
    
    Examples:
        https://github.com/user/my-notes.git -> my-notes
        git@github.com:user/my-notes.git -> my-notes
        my-notes -> my-notes
    """
    if not remote_url:
        return "notes"
    
    # Handle SSH URLs like git@github.com:user/repo.git
    if remote_url.startswith("git@"):
        parts = remote_url.split(":")
        if len(parts) == 2:
            remote_url = parts[1]
    
    # Parse URL
    parsed = urlparse(remote_url)
    path = parsed.path if parsed.path else remote_url
    
    # Extract last component
    name = path.rstrip("/").split("/")[-1]
    
    # Remove .git suffix
    if name.endswith(".git"):
        name = name[:-4]
    
    # Fallback
    if not name:
        name = "notes"
    
    return name


def get_default_repo_path(remote_url: str = "") -> str:
    """Get default local repository path.
    
    Returns: <data_dir>/repos/<repo_name>
    """
    repo_name = _extract_repo_name(remote_url)
    data_dir = get_data_dir()
    return str(data_dir / "repos" / repo_name)


def _get_device_name() -> str:
    """Get the current device name."""
    return platform.node() or os.getenv("HOSTNAME") or "unknown-device"


def _write_gitnoteline_yaml(repo_path: Path) -> None:
    """Write or update .gitnoteline.yaml in the repository.
    
    Adds this device to the devices list with joined and last_sync timestamps.
    """
    yaml_path = repo_path / ".gitnoteline.yaml"
    device_name = _get_device_name()
    now = datetime.now().strftime("%Y-%m-%d")
    
    # Read existing YAML if present
    data = {"version": 1, "devices": []}
    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or data
        except Exception:
            pass
    
    # Find or add this device
    devices = data.get("devices", [])
    device_entry = None
    for device in devices:
        if device.get("name") == device_name:
            device_entry = device
            break
    
    if device_entry:
        # Update last_sync for existing device
        device_entry["last_sync"] = now
    else:
        # Add new device
        devices.append({
            "name": device_name,
            "joined": now,
            "last_sync": now,
        })
    
    data["devices"] = devices
    
    # Write YAML
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _rollback_repo(conn, repo_path: Path, repo_id: int, credential_id: int) -> None:
    """Rollback: delete repo directory and database records on failure."""
    import shutil
    
    # Delete local repository directory
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)
    
    # Delete repository record
    conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
    
    # Delete credential record
    conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
    
    conn.commit()


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
            # Rollback: delete credential and directory
            conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            import shutil
            shutil.rmtree(repo_path, ignore_errors=True)
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
                # Rollback: delete credential and directory
                conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
                conn.commit()
                conn.close()
                import shutil
                shutil.rmtree(repo_path, ignore_errors=True)
                return {"ok": False, "error": f"添加远程仓库失败: {result.stderr}"}
        
        # Create repository record
        cursor = conn.execute(
            "INSERT INTO repositories (path, remote_url, credential_id) VALUES (?, ?, ?)",
            (str(repo_path), remote_url, credential_id),
        )
        repo_id = cursor.lastrowid

        conn.commit()

        # ── Verification flow: pull → write YAML → push ──────────
        if remote_url:
            # Get identity settings for git config
            git_name = conn.execute("SELECT value FROM settings WHERE key = 'git_name'").fetchone()
            git_email = conn.execute("SELECT value FROM settings WHERE key = 'git_email'").fetchone()
            
            if git_name and git_email:
                # Configure git user for this repo
                subprocess.run(
                    ["git", "config", "user.name", git_name["value"]],
                    cwd=repo_path, capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["git", "config", "user.email", git_email["value"]],
                    cwd=repo_path, capture_output=True, timeout=5,
                )
            
            # Get credential for authentication
            token = get_credential(conn, credential_id)
            
            if token:
                # Build authenticated URL for HTTPS
                parsed = urlparse(remote_url)
                if parsed.scheme in ("http", "https"):
                    # Insert token into URL: https://token@github.com/...
                    auth_url = remote_url.replace(
                        f"{parsed.scheme}://{parsed.netloc}",
                        f"{parsed.scheme}://{token}@{parsed.netloc}"
                    )
                else:
                    auth_url = remote_url

                # Set environment to disable interactive credential prompts
                git_env = os.environ.copy()
                git_env["GIT_TERMINAL_PROMPT"] = "0"

                # Temporarily set authenticated remote
                subprocess.run(
                    ["git", "remote", "set-url", "origin", auth_url],
                    cwd=repo_path, capture_output=True, timeout=5,
                )

                # Step 1: Check if remote is empty
                ls_remote_result = subprocess.run(
                    ["git", "ls-remote", "origin"],
                    cwd=repo_path, capture_output=True, text=True, timeout=10,
                    env=git_env,
                )
                
                # If ls-remote failed, check if it's an auth/network error
                if ls_remote_result.returncode != 0:
                    stderr = ls_remote_result.stderr.lower()
                    # Log the actual error for debugging
                    import sys
                    print(f"[DEBUG] ls-remote failed: {ls_remote_result.stderr}", file=sys.stderr)
                    # Rollback before returning error
                    _rollback_repo(conn, repo_path, repo_id, credential_id)
                    conn.close()
                    if ("authentication" in stderr or "403" in stderr or "401" in stderr or
                        "could not read password" in stderr or "terminal prompts disabled" in stderr):
                        return {"ok": False, "error": "认证失败，请检查凭证是否正确"}
                    elif "could not resolve" in stderr or "unable to access" in stderr:
                        return {"ok": False, "error": "网络错误，无法连接远程仓库"}
                    else:
                        return {"ok": False, "error": f"无法访问远程仓库: {ls_remote_result.stderr}"}
                
                remote_is_empty = not ls_remote_result.stdout.strip()
                
                # Step 2: git pull only if remote is not empty
                if not remote_is_empty:
                    pull_result = subprocess.run(
                        ["git", "pull", "origin", "main", "--allow-unrelated-histories"],
                        cwd=repo_path, capture_output=True, text=True, timeout=30,
                        env=git_env,
                    )

                    # Check if pull failed
                    if pull_result.returncode != 0:
                        stderr = pull_result.stderr.lower()
                        # Rollback before returning error
                        _rollback_repo(conn, repo_path, repo_id, credential_id)
                        conn.close()
                        if ("authentication" in stderr or "403" in stderr or "401" in stderr or
                            "could not read password" in stderr or "terminal prompts disabled" in stderr):
                            return {"ok": False, "error": "认证失败，请检查凭证是否正确"}
                        elif "could not resolve" in stderr or "network" in stderr:
                            return {"ok": False, "error": "网络错误，无法连接远程仓库"}
                        else:
                            return {"ok": False, "error": f"拉取失败: {pull_result.stderr}"}

                # Step 3: Write .gitnoteline.yaml
                try:
                    _write_gitnoteline_yaml(repo_path)
                except Exception as e:
                    # Rollback before returning error
                    _rollback_repo(conn, repo_path, repo_id, credential_id)
                    conn.close()
                    return {"ok": False, "error": f"写入配置文件失败: {str(e)}"}
                
                # Step 4: git add + commit + push
                subprocess.run(
                    ["git", "add", ".gitnoteline.yaml"],
                    cwd=repo_path, capture_output=True, timeout=5,
                )
                
                commit_result = subprocess.run(
                    ["git", "commit", "-m", "Initialize GitNoteLine repository"],
                    cwd=repo_path, capture_output=True, text=True, timeout=10,
                )

                # Commit might fail if nothing to commit (YAML already existed and unchanged)
                # That's OK, continue with push

                # Get current branch name
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_path, capture_output=True, text=True, timeout=5,
                )
                current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

                push_result = subprocess.run(
                    ["git", "push", "-u", "origin", current_branch],
                    cwd=repo_path, capture_output=True, text=True, timeout=30,
                    env=git_env,
                )
                
                if push_result.returncode != 0:
                    # Rollback before returning error
                    _rollback_repo(conn, repo_path, repo_id, credential_id)
                    conn.close()
                    stderr = push_result.stderr.lower()
                    if ("authentication" in stderr or "403" in stderr or "401" in stderr or
                        "could not read password" in stderr or "terminal prompts disabled" in stderr):
                        return {"ok": False, "error": "推送失败，认证失败，请检查凭证"}
                    else:
                        return {"ok": False, "error": f"推送失败: {push_result.stderr}"}
                
                # Restore original URL (without token)
                subprocess.run(
                    ["git", "remote", "set-url", "origin", remote_url],
                    cwd=repo_path, capture_output=True, timeout=5,
                )

        conn.close()
        return {"ok": True, "credential_id": credential_id, "repo_id": repo_id}

    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def init_step2_2(
    db_path: str,
    remote_url: str,
    local_path: str,
    credential_name: str,
    credential_type: str,
    credential_secret: str,
) -> dict:
    """Clone an existing remote repository.

    Args:
        db_path: Path to the database
        remote_url: Remote git URL to clone
        local_path: Local path for the cloned repository
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

        # Get identity settings for git config
        git_name = conn.execute("SELECT value FROM settings WHERE key = 'git_name'").fetchone()
        git_email = conn.execute("SELECT value FROM settings WHERE key = 'git_email'").fetchone()

        # Get credential for authentication
        token = get_credential(conn, credential_id)

        if not token:
            conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            return {"ok": False, "error": "无法获取凭证"}

        # Build authenticated URL for HTTPS clone
        parsed = urlparse(remote_url)
        if parsed.scheme in ("http", "https"):
            auth_url = remote_url.replace(
                f"{parsed.scheme}://{parsed.netloc}",
                f"{parsed.scheme}://{token}@{parsed.netloc}"
            )
        else:
            auth_url = remote_url

        # Set environment to disable interactive credential prompts
        git_env = os.environ.copy()
        git_env["GIT_TERMINAL_PROMPT"] = "0"

        # Git clone
        repo_path = Path(local_path)
        clone_result = subprocess.run(
            ["git", "clone", auth_url, str(repo_path)],
            capture_output=True, text=True, timeout=60,
            env=git_env,
        )

        if clone_result.returncode != 0:
            conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            stderr = clone_result.stderr.lower()
            if ("authentication" in stderr or "403" in stderr or "401" in stderr or
                "could not read password" in stderr or "terminal prompts disabled" in stderr):
                return {"ok": False, "error": "认证失败，请检查凭证是否正确"}
            elif "could not resolve" in stderr or "unable to access" in stderr:
                return {"ok": False, "error": "网络错误，无法连接远程仓库"}
            else:
                return {"ok": False, "error": f"克隆失败: {clone_result.stderr}"}

        # Configure git user for this repo
        if git_name and git_email:
            subprocess.run(
                ["git", "config", "user.name", git_name["value"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.email", git_email["value"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )

        # Restore original URL (without token)
        subprocess.run(
            ["git", "remote", "set-url", "origin", remote_url],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        # Create repository record
        cursor = conn.execute(
            "INSERT INTO repositories (path, remote_url, credential_id) VALUES (?, ?, ?)",
            (str(repo_path), remote_url, credential_id),
        )
        repo_id = cursor.lastrowid

        conn.commit()

        # ── Verification flow: write YAML → push ──────────
        # Set authenticated URL temporarily
        subprocess.run(
            ["git", "remote", "set-url", "origin", auth_url],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        # Step 1: Write .gitnoteline.yaml
        try:
            _write_gitnoteline_yaml(repo_path)
        except Exception as e:
            # Rollback: delete credential and repo record, but preserve cloned repo
            conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            subprocess.run(
                ["git", "remote", "set-url", "origin", remote_url],
                cwd=repo_path, capture_output=True, timeout=5,
            )
            return {"ok": False, "error": f"写入配置文件失败: {str(e)}"}

        # Step 2: git add + commit + push
        subprocess.run(
            ["git", "add", ".gitnoteline.yaml"],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        subprocess.run(
            ["git", "commit", "-m", "Add GitNoteLine configuration"],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )

        # Get current branch name
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

        push_result = subprocess.run(
            ["git", "push", "-u", "origin", current_branch],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
            env=git_env,
        )

        if push_result.returncode != 0:
            # Rollback: delete credential and repo record, but preserve cloned repo
            conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            subprocess.run(
                ["git", "remote", "set-url", "origin", remote_url],
                cwd=repo_path, capture_output=True, timeout=5,
            )
            stderr = push_result.stderr.lower()
            if ("authentication" in stderr or "403" in stderr or "401" in stderr or
                "could not read password" in stderr or "terminal prompts disabled" in stderr):
                return {"ok": False, "error": "推送失败，认证失败，请检查凭证"}
            else:
                return {"ok": False, "error": f"推送失败: {push_result.stderr}"}

        # Restore original URL (without token)
        subprocess.run(
            ["git", "remote", "set-url", "origin", remote_url],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        conn.close()
        return {"ok": True, "credential_id": credential_id, "repo_id": repo_id}

    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def init_step2_3(
    db_path: str,
    local_path: str,
    credential_name: str = "",
    credential_type: str = "",
    credential_secret: str = "",
) -> dict:
    """Link an existing local repository.

    Args:
        db_path: Path to the database
        local_path: Path to existing Git repository
        credential_name: Optional - user-friendly name for the credential
        credential_type: Optional - "password" or "fine_grained"
        credential_secret: Optional - the token/password

    Returns:
        dict with 'ok', 'error', 'credential_id', 'repo_id'
    """
    repo_path = Path(local_path)

    # Verify it's a valid Git repository
    if not repo_path.exists():
        return {"ok": False, "error": "路径不存在"}

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return {"ok": False, "error": "不是有效的 Git 仓库"}

    # Check if remote (origin) exists
    remote_result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path, capture_output=True, text=True, timeout=5,
    )

    has_remote = remote_result.returncode == 0
    remote_url = remote_result.stdout.strip() if has_remote else ""

    conn = ensure_db(db_path)

    try:
        credential_id = None

        # If has remote and credentials provided, store them
        if has_remote and credential_name and credential_secret:
            # Extract host from URL
            host = ""
            if remote_url:
                try:
                    parsed = urlparse(remote_url)
                    host = parsed.netloc
                except Exception:
                    pass

            # Create credential record
            cursor = conn.execute(
                "INSERT INTO credentials (name, type, host) VALUES (?, ?, ?)",
                (credential_name, credential_type or "password", host),
            )
            credential_id = cursor.lastrowid

            # Store encrypted secret in database
            if not store_credential(conn, credential_id, credential_secret):
                conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
                conn.commit()
                conn.close()
                return {"ok": False, "error": "无法加密存储凭证"}

        # Create repository record
        cursor = conn.execute(
            "INSERT INTO repositories (path, remote_url, credential_id) VALUES (?, ?, ?)",
            (str(repo_path), remote_url if has_remote else None, credential_id),
        )
        repo_id = cursor.lastrowid

        conn.commit()

        # Write .gitnoteline.yaml
        try:
            _write_gitnoteline_yaml(repo_path)
        except Exception as e:
            # Rollback
            conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            if credential_id:
                conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            conn.close()
            return {"ok": False, "error": f"写入配置文件失败: {str(e)}"}

        # If has remote and credentials, do push test
        if has_remote and credential_id:
            # Get identity settings for git config
            git_name = conn.execute("SELECT value FROM settings WHERE key = 'git_name'").fetchone()
            git_email = conn.execute("SELECT value FROM settings WHERE key = 'git_email'").fetchone()

            if git_name and git_email:
                subprocess.run(
                    ["git", "config", "user.name", git_name["value"]],
                    cwd=repo_path, capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["git", "config", "user.email", git_email["value"]],
                    cwd=repo_path, capture_output=True, timeout=5,
                )

            # Get credential for authentication
            token = get_credential(conn, credential_id)

            if token:
                # Build authenticated URL for HTTPS
                parsed = urlparse(remote_url)
                if parsed.scheme in ("http", "https"):
                    auth_url = remote_url.replace(
                        f"{parsed.scheme}://{parsed.netloc}",
                        f"{parsed.scheme}://{token}@{parsed.netloc}"
                    )
                else:
                    auth_url = remote_url

                # Set environment to disable interactive credential prompts
                git_env = os.environ.copy()
                git_env["GIT_TERMINAL_PROMPT"] = "0"

                # Temporarily set authenticated remote
                subprocess.run(
                    ["git", "remote", "set-url", "origin", auth_url],
                    cwd=repo_path, capture_output=True, timeout=5,
                )

                # git add + commit + push
                subprocess.run(
                    ["git", "add", ".gitnoteline.yaml"],
                    cwd=repo_path, capture_output=True, timeout=5,
                )

                subprocess.run(
                    ["git", "commit", "-m", "Add GitNoteLine configuration"],
                    cwd=repo_path, capture_output=True, text=True, timeout=10,
                )

                # Get current branch name
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_path, capture_output=True, text=True, timeout=5,
                )
                current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

                push_result = subprocess.run(
                    ["git", "push", "-u", "origin", current_branch],
                    cwd=repo_path, capture_output=True, text=True, timeout=30,
                    env=git_env,
                )

                # Restore original URL (without token)
                subprocess.run(
                    ["git", "remote", "set-url", "origin", remote_url],
                    cwd=repo_path, capture_output=True, timeout=5,
                )

                if push_result.returncode != 0:
                    # Rollback: delete credential and repo record, but preserve user's repo
                    conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
                    conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
                    conn.commit()
                    conn.close()
                    stderr = push_result.stderr.lower()
                    if ("authentication" in stderr or "403" in stderr or "401" in stderr or
                        "could not read password" in stderr or "terminal prompts disabled" in stderr):
                        return {"ok": False, "error": "推送失败，认证失败，请检查凭证"}
                    else:
                        return {"ok": False, "error": f"推送失败: {push_result.stderr}"}

        elif not has_remote:
            # No remote, just commit the YAML
            subprocess.run(
                ["git", "add", ".gitnoteline.yaml"],
                cwd=repo_path, capture_output=True, timeout=5,
            )

            subprocess.run(
                ["git", "commit", "-m", "Add GitNoteLine configuration"],
                cwd=repo_path, capture_output=True, text=True, timeout=10,
            )

        conn.close()
        return {"ok": True, "credential_id": credential_id, "repo_id": repo_id}

    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def init_step2_4(
    db_path: str,
    local_path: str,
) -> dict:
    """Create a local-only repository (no remote).

    Args:
        db_path: Path to the database
        local_path: Local path for the repository

    Returns:
        dict with 'ok', 'error', 'repo_id'
    """
    conn = ensure_db(db_path)

    try:
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
            conn.close()
            import shutil
            shutil.rmtree(repo_path, ignore_errors=True)
            return {"ok": False, "error": f"Git 初始化失败: {result.stderr}"}

        # Get identity settings for git config
        git_name = conn.execute("SELECT value FROM settings WHERE key = 'git_name'").fetchone()
        git_email = conn.execute("SELECT value FROM settings WHERE key = 'git_email'").fetchone()

        if git_name and git_email:
            subprocess.run(
                ["git", "config", "user.name", git_name["value"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.email", git_email["value"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )

        # Create repository record (no remote, no credential)
        cursor = conn.execute(
            "INSERT INTO repositories (path, remote_url, credential_id) VALUES (?, NULL, NULL)",
            (str(repo_path),),
        )
        repo_id = cursor.lastrowid

        conn.commit()

        # Write .gitnoteline.yaml
        try:
            _write_gitnoteline_yaml(repo_path)
        except Exception as e:
            # Rollback
            conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            conn.commit()
            conn.close()
            import shutil
            shutil.rmtree(repo_path, ignore_errors=True)
            return {"ok": False, "error": f"写入配置文件失败: {str(e)}"}

        # git add + commit (no push)
        subprocess.run(
            ["git", "add", ".gitnoteline.yaml"],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        subprocess.run(
            ["git", "commit", "-m", "Initialize GitNoteLine repository"],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )

        conn.close()
        return {"ok": True, "repo_id": repo_id}

    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


# ── Sync operations ────────────────────────────────────────────────


def _get_repo_with_credential(db_path: str, repo_id: int) -> dict | None:
    """Get repo info with decrypted credential."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    repo = conn.execute(
        "SELECT id, path, remote_url, credential_id FROM repositories WHERE id = ?",
        (repo_id,)
    ).fetchone()

    if not repo:
        conn.close()
        return None

    result = {
        "id": repo["id"],
        "path": Path(repo["path"]),
        "remote_url": repo["remote_url"],
        "credential_id": repo["credential_id"],
        "token": None,
    }

    # Get decrypted credential if exists
    if repo["credential_id"]:
        token = get_credential(conn, repo["credential_id"])
        result["token"] = token

    # Get git identity
    git_name = conn.execute("SELECT value FROM settings WHERE key = 'git_name'").fetchone()
    git_email = conn.execute("SELECT value FROM settings WHERE key = 'git_email'").fetchone()
    result["git_name"] = git_name["value"] if git_name else ""
    result["git_email"] = git_email["value"] if git_email else ""

    conn.close()
    return result


def _build_auth_url(remote_url: str, token: str) -> str:
    """Build authenticated URL for HTTPS git operations."""
    parsed = urlparse(remote_url)
    if parsed.scheme in ("http", "https"):
        return remote_url.replace(
            f"{parsed.scheme}://{parsed.netloc}",
            f"{parsed.scheme}://{token}@{parsed.netloc}"
        )
    return remote_url


def _classify_git_error(stderr: str) -> str:
    """Classify git error into user-friendly message."""
    stderr_lower = stderr.lower()
    if any(kw in stderr_lower for kw in [
        "authentication", "403", "401", "could not read password",
        "terminal prompts disabled"
    ]):
        return "认证失败，请检查凭证"
    elif any(kw in stderr_lower for kw in [
        "could not resolve", "unable to access", "network"
    ]):
        return "网络错误，无法连接远程仓库"
    else:
        return f"Git 错误: {stderr.strip()}"


def sync_pull(db_path: str, repo_id: int) -> dict:
    """Pull from remote repository.

    Returns:
        dict with 'ok', 'error' (if failed)
    """
    repo_info = _get_repo_with_credential(db_path, repo_id)

    if not repo_info:
        return {"ok": False, "error": "仓库不存在"}

    if not repo_info["remote_url"]:
        return {"ok": False, "error": "仓库没有配置远程地址"}

    if not repo_info["token"]:
        return {"ok": False, "error": "仓库没有配置凭证"}

    repo_path = repo_info["path"]
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    # Build authenticated URL
    auth_url = _build_auth_url(repo_info["remote_url"], repo_info["token"])

    # Temporarily set authenticated remote
    subprocess.run(
        ["git", "remote", "set-url", "origin", auth_url],
        cwd=repo_path, capture_output=True, timeout=5,
    )

    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )

        if branch_result.returncode != 0:
            return {"ok": False, "error": "无法获取当前分支"}

        current_branch = branch_result.stdout.strip()

        # Check for uncommitted local changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )

        has_local_changes = bool(status_result.stdout.strip())

        # Git fetch to check if remote has new changes
        fetch_result = subprocess.run(
            ["git", "fetch", "origin", current_branch],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
            env=git_env,
        )

        if fetch_result.returncode != 0:
            error_msg = _classify_git_error(fetch_result.stderr)
            return {"ok": False, "error": error_msg}

        # Check if remote has new commits
        local_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        remote_head = subprocess.run(
            ["git", "rev-parse", f"origin/{current_branch}"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        if local_head == remote_head:
            # Already up to date, nothing to pull
            return {"ok": True}

        # If there are local changes, don't overwrite — commit them first
        if has_local_changes:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path, capture_output=True, timeout=5,
            )
            subprocess.run(
                ["git", "commit", "-m", "Auto-save before sync"],
                cwd=repo_path, capture_output=True, text=True, timeout=10,
            )

        # Git pull (merge fetched changes)
        pull_result = subprocess.run(
            ["git", "pull", "origin", current_branch, "--allow-unrelated-histories", "--no-edit"],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
            env=git_env,
        )

        if pull_result.returncode != 0:
            # Check if it's a merge conflict
            if "CONFLICT" in pull_result.stdout or "CONFLICT" in pull_result.stderr:
                # Auto-merge: add all and commit
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=repo_path, capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["git", "commit", "-m", "Auto-merge conflict resolution"],
                    cwd=repo_path, capture_output=True, text=True, timeout=10,
                )
            else:
                error_msg = _classify_git_error(pull_result.stderr)
                return {"ok": False, "error": error_msg}

        return {"ok": True}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "操作超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        # Restore original URL
        subprocess.run(
            ["git", "remote", "set-url", "origin", repo_info["remote_url"]],
            cwd=repo_path, capture_output=True, timeout=5,
        )


def sync_push(db_path: str, repo_id: int) -> dict:
    """Commit all changes and push to remote.

    Updates .gitnoteline.yaml last_sync before pushing.

    Returns:
        dict with 'ok', 'error' (if failed)
    """
    repo_info = _get_repo_with_credential(db_path, repo_id)

    if not repo_info:
        return {"ok": False, "error": "仓库不存在"}

    if not repo_info["remote_url"]:
        return {"ok": False, "error": "仓库没有配置远程地址"}

    if not repo_info["token"]:
        return {"ok": False, "error": "仓库没有配置凭证"}

    repo_path = repo_info["path"]
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        # Configure git user for this repo
        if repo_info["git_name"]:
            subprocess.run(
                ["git", "config", "user.name", repo_info["git_name"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )
        if repo_info["git_email"]:
            subprocess.run(
                ["git", "config", "user.email", repo_info["git_email"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )

        # Update .gitnoteline.yaml
        _write_gitnoteline_yaml(repo_path)

        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        # Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )

        if status_result.stdout.strip():
            # Commit changes
            commit_result = subprocess.run(
                ["git", "commit", "-m", "Update notes"],
                cwd=repo_path, capture_output=True, text=True, timeout=10,
            )

            if commit_result.returncode != 0:
                return {"ok": False, "error": f"提交失败: {commit_result.stderr}"}

        # Build authenticated URL
        auth_url = _build_auth_url(repo_info["remote_url"], repo_info["token"])

        # Temporarily set authenticated remote
        subprocess.run(
            ["git", "remote", "set-url", "origin", auth_url],
            cwd=repo_path, capture_output=True, timeout=5,
        )

        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )

        if branch_result.returncode != 0:
            return {"ok": False, "error": "无法获取当前分支"}

        current_branch = branch_result.stdout.strip()

        # Git push
        push_result = subprocess.run(
            ["git", "push", "origin", current_branch],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
            env=git_env,
        )

        if push_result.returncode != 0:
            error_msg = _classify_git_error(push_result.stderr)
            return {"ok": False, "error": error_msg}

        return {"ok": True}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "操作超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        # Restore original URL
        subprocess.run(
            ["git", "remote", "set-url", "origin", repo_info["remote_url"]],
            cwd=repo_path, capture_output=True, timeout=5,
        )


def sync_full(db_path: str, repo_id: int) -> dict:
    """Smart sync: push local changes, pull remote changes.

    Logic:
    - If there are uncommitted changes → commit + push
    - If push fails (conflict) → pull + push again
    - If no local changes → just pull
    """
    repo_info = _get_repo_with_credential(db_path, repo_id)

    if not repo_info:
        return {"ok": False, "error": "仓库不存在"}

    if not repo_info["remote_url"]:
        return {"ok": False, "error": "仓库没有配置远程地址"}

    if not repo_info["token"]:
        return {"ok": False, "error": "仓库没有配置凭证"}

    repo_path = repo_info["path"]
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        # Configure git user
        if repo_info["git_name"]:
            subprocess.run(
                ["git", "config", "user.name", repo_info["git_name"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )
        if repo_info["git_email"]:
            subprocess.run(
                ["git", "config", "user.email", repo_info["git_email"]],
                cwd=repo_path, capture_output=True, timeout=5,
            )

        # Check for local changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        has_local_changes = bool(status_result.stdout.strip())

        if has_local_changes:
            # Commit local changes
            _write_gitnoteline_yaml(repo_path)
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path, capture_output=True, timeout=5,
            )
            subprocess.run(
                ["git", "commit", "-m", "Sync: update notes"],
                cwd=repo_path, capture_output=True, text=True, timeout=10,
            )

            # Build authenticated URL
            auth_url = _build_auth_url(repo_info["remote_url"], repo_info["token"])
            subprocess.run(
                ["git", "remote", "set-url", "origin", auth_url],
                cwd=repo_path, capture_output=True, timeout=5,
            )

            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path, capture_output=True, text=True, timeout=5,
            )
            if branch_result.returncode != 0:
                return {"ok": False, "error": "无法获取当前分支"}
            current_branch = branch_result.stdout.strip()

            # Try push
            push_result = subprocess.run(
                ["git", "push", "origin", current_branch],
                cwd=repo_path, capture_output=True, text=True, timeout=30,
                env=git_env,
            )

            if push_result.returncode != 0:
                # Push failed — pull first, then push again
                pull_result = subprocess.run(
                    ["git", "pull", "origin", current_branch, "--allow-unrelated-histories", "--no-edit"],
                    cwd=repo_path, capture_output=True, text=True, timeout=30,
                    env=git_env,
                )

                if pull_result.returncode != 0:
                    if "CONFLICT" in pull_result.stdout or "CONFLICT" in pull_result.stderr:
                        subprocess.run(
                            ["git", "add", "-A"],
                            cwd=repo_path, capture_output=True, timeout=5,
                        )
                        subprocess.run(
                            ["git", "commit", "-m", "Sync: auto-merge conflict"],
                            cwd=repo_path, capture_output=True, text=True, timeout=10,
                        )
                    else:
                        error_msg = _classify_git_error(pull_result.stderr)
                        return {"ok": False, "error": f"拉取失败: {error_msg}"}

                # Push again after pull
                push_result2 = subprocess.run(
                    ["git", "push", "origin", current_branch],
                    cwd=repo_path, capture_output=True, text=True, timeout=30,
                    env=git_env,
                )
                if push_result2.returncode != 0:
                    error_msg = _classify_git_error(push_result2.stderr)
                    return {"ok": False, "error": f"推送失败: {error_msg}"}

            return {"ok": True}

        else:
            # No local changes — just pull
            auth_url = _build_auth_url(repo_info["remote_url"], repo_info["token"])
            subprocess.run(
                ["git", "remote", "set-url", "origin", auth_url],
                cwd=repo_path, capture_output=True, timeout=5,
            )

            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path, capture_output=True, text=True, timeout=5,
            )
            if branch_result.returncode != 0:
                return {"ok": False, "error": "无法获取当前分支"}
            current_branch = branch_result.stdout.strip()

            pull_result = subprocess.run(
                ["git", "pull", "origin", current_branch, "--allow-unrelated-histories", "--no-edit"],
                cwd=repo_path, capture_output=True, text=True, timeout=30,
                env=git_env,
            )

            if pull_result.returncode != 0:
                if "CONFLICT" in pull_result.stdout or "CONFLICT" in pull_result.stderr:
                    subprocess.run(
                        ["git", "add", "-A"],
                        cwd=repo_path, capture_output=True, timeout=5,
                    )
                    subprocess.run(
                        ["git", "commit", "-m", "Sync: auto-merge conflict"],
                        cwd=repo_path, capture_output=True, text=True, timeout=10,
                    )
                else:
                    error_msg = _classify_git_error(pull_result.stderr)
                    return {"ok": False, "error": error_msg}

            return {"ok": True}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "操作超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        subprocess.run(
            ["git", "remote", "set-url", "origin", repo_info["remote_url"]],
            cwd=repo_path, capture_output=True, timeout=5,
        )


def get_sync_status(db_path: str, repo_id: int) -> dict:
    """Get sync status for a repository.

    Returns:
        dict with 'ok', 'has_remote', 'ahead' (commits ahead of remote), 'behind' (commits behind)
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    repo = conn.execute(
        "SELECT path, remote_url FROM repositories WHERE id = ?",
        (repo_id,)
    ).fetchone()
    conn.close()

    if not repo:
        return {"ok": False, "error": "仓库不存在"}

    repo_path = Path(repo["path"])
    has_remote = bool(repo["remote_url"])

    result = {
        "ok": True,
        "has_remote": has_remote,
        "ahead": 0,
        "behind": 0,
    }

    if not has_remote:
        return result

    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )

        if branch_result.returncode != 0:
            return result

        current_branch = branch_result.stdout.strip()

        # Get ahead/behind count
        status_result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", f"HEAD...origin/{current_branch}"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )

        if status_result.returncode == 0:
            parts = status_result.stdout.strip().split()
            if len(parts) == 2:
                result["ahead"] = int(parts[0])
                result["behind"] = int(parts[1])

    except Exception:
        pass

    return result

