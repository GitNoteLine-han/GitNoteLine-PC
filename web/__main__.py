"""Entry point:  python -m web [--debug] [--port PORT] [--db PATH] [--no-browser]

Listens on both IPv4 (127.0.0.1) and IPv6 ([::1]) loopback via a dual-stack
IPv6 socket bound to ::1 (Linux default: IPV6_V6ONLY=0).
Opens the user's browser to http://gitnoteline.localhost:<port>.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

# Ensure the project root is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from core.config import config
from core.database import get_db_path
from web.app import create_app
from werkzeug.serving import run_simple

# ── helpers ─────────────────────────────────────────────────────────


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("::1", 0))
        return s.getsockname()[1]


def _open_browser(url: str, delay: float = 1.0) -> None:
    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Timer(delay, _open).start()


# ── CLI ─────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitNoteLine Web")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (reloader + Werkzeug debugger)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Specific port (default: random available port)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="",
        help="Custom path to userdata.db (directory or .db file)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically",
    )
    parser.add_argument(
        "--only-server",
        action="store_true",
        help="Server-only mode: listen on 0.0.0.0:8080, no browser",
    )
    return parser.parse_args(argv)


# ── main ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # ── Server-only mode ────────────────────────────────────────
    if args.only_server:
        # Try 0.0.0.0:8080, fall back to random port
        host = "0.0.0.0"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, 8080))
            port = 8080
        except OSError:
            port = _find_free_port()
        
        db_path = str(
            Path(args.db).resolve() if args.db else get_db_path()
        )
        config.db_path = db_path
        app = create_app(db_path=db_path)
        
        db_status = "未初始化" if not os.path.exists(db_path) else "就绪"
        print(
            f"\n"
            f" 🌐 GitNoteLine Web (Server Mode)\n"
            f" ─────────────────────────────────\n"
            f" URL:     http://{host}:{port}\n"
            f" DB:      {db_path}  [{db_status}]\n"
            f" Mode:    production\n"
            f" PID:     {os.getpid()}\n"
        )
        
        run_simple(host, port, app, threaded=True)
        return

    # ── Resolve port ────────────────────────────────────────────
    if args.port:
        port = args.port
    elif args.debug and "GITNOTELINE_PORT" in os.environ:
        port = int(os.environ["GITNOTELINE_PORT"])
    else:
        port = _find_free_port()
        if args.debug:
            os.environ["GITNOTELINE_PORT"] = str(port)

    # ── Resolve DB path ─────────────────────────────────────────
    db_path = str(
        Path(args.db).resolve() if args.db else get_db_path()
    )
    config.db_path = db_path

    # ── Application ─────────────────────────────────────────────
    app = create_app(db_path=db_path)

    # ── Banner ──────────────────────────────────────────────────
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not args.debug or is_reloader_child:
        db_status = "未初始化" if not os.path.exists(db_path) else "就绪"
        print(
            f"\n"
            f" 🌐 GitNoteLine Web\n"
            f" ─────────────────\n"
            f" URL:     http://gitnoteline.localhost:{port}\n"
            f" DB:      {db_path}  [{db_status}]\n"
            f" Mode:    {'DEBUG' if args.debug else 'production'}\n"
            f" PID:     {os.getpid()}\n"
        )

    # ── Browser ─────────────────────────────────────────────────
    if not args.no_browser:
        if not args.debug or is_reloader_child:
            _open_browser(f"http://gitnoteline.localhost:{port}")

    # ── Serve ───────────────────────────────────────────────────
    run_simple(
        "::1",
        port,
        app,
        use_reloader=args.debug,
        use_debugger=args.debug,
        use_evalex=args.debug,
        threaded=True,
    )


if __name__ == "__main__":
    main()