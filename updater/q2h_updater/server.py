# updater/q2h_updater/server.py
"""Minimal HTTPS server for maintenance page + status endpoint.

Runs in a background thread. Serves:
- GET /            -> maintenance HTML page
- GET /upgrade-status -> upgrade-status.json content
"""

import json
import logging
import ssl
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from q2h_updater.maintenance import get_maintenance_html

logger = logging.getLogger("q2h_updater.server")


class MaintenanceHandler(BaseHTTPRequestHandler):
    """HTTP handler for maintenance page and status endpoint."""

    # Class-level attribute set by the server
    status_file: Path = None  # type: ignore

    def do_GET(self):
        if self.path == "/upgrade-status":
            self._serve_status()
        else:
            # Serve maintenance page for ALL routes (/, /api/..., /assets/..., etc.)
            self._serve_html()

    def _add_security_headers(self):
        """Add standard security headers to every response."""
        self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _serve_html(self):
        html = get_maintenance_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.send_header("Cache-Control", "no-cache")
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(html)

    def _serve_status(self):
        try:
            data = self.status_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            data = json.dumps({"state": "pending", "step": 0, "total_steps": 6,
                               "percent": 0, "error": None})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(data.encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default stderr logging -- use our logger instead."""
        logger.debug("HTTP %s", format % args)


def start_maintenance_server(
    port: int,
    cert_path: Path,
    key_path: Path,
    status_file: Path,
) -> tuple[HTTPServer, threading.Thread]:
    """Start HTTPS maintenance server in a background thread.

    Returns (server, thread) so the caller can shut down later.
    """
    MaintenanceHandler.status_file = status_file

    server = HTTPServer(("0.0.0.0", port), MaintenanceHandler)

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(str(cert_path), str(key_path))
    server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Maintenance server started on https://0.0.0.0:%d", port)

    return server, thread
