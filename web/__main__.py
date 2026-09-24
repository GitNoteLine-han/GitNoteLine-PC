"""Entry point:  python -m web [--debug] [--port PORT] [--no-browser]

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

# Ensure the project root is importable (supports `python -m web` from anywhere).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from web.app import create_app
from werkzeug.serving import run_simple

# ── helpers ─────────────────────────────────────────────────────────


def _find_free_port() -> int:
    """Ask the OS for a random available port on the loopback interface.

    There is a tiny TOCTOU window between releasing the probe socket and
    the real bind in run_simple — acceptable for local development.
    """
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("::1", 0))
        return s.getsockname()[1]


def _open_browser(url: str, delay: float = 1.0) -> None:
    """Open *url* in the default browser after a short delay."""

    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # headless / no desktop — just print the URL

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
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically",
    )
    return parser.parse_args(argv)


# ── main ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # ── Resolve port ────────────────────────────────────────────
    # reloader re-executes the process; communicate the port via env.
    if args.port:
        port = args.port
    elif args.debug and "GITNOTELINE_PORT" in os.environ:
        port = int(os.environ["GITNOTELINE_PORT"])
    else:
        port = _find_free_port()
        if args.debug:
            os.environ["GITNOTELINE_PORT"] = str(port)

    # ── Application ─────────────────────────────────────────────
    app = create_app()

    # ── Banner ──────────────────────────────────────────────────
    # The reloader runs our code twice (parent-reloader + child-server).
    # Only print the banner in the *child* so it doesn't re-appear on
    # every reload, but non-debug mode has no reloader so print always.
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not args.debug or is_reloader_child:
        print(
            f"\n"
            f" 🌐 GitNoteLine Web\n"
            f" ─────────────────\n"
            f" URL:  http://gitnoteline.localhost:{port}\n"
            f" Mode: {'DEBUG' if args.debug else 'production'}\n"
            f" PID:  {os.getpid()}\n"
        )

    # ── Browser ─────────────────────────────────────────────────
    if not args.no_browser:
        # Non-debug  → open once in the main (and only) process.
        # Debug      → open only in the reloader child (one shot).
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