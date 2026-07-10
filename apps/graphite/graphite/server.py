"""`graphite serve`: a localhost-only stdlib http server (D164 GUI half).

Serves ONE self-contained, hand-written ASCII HTML/JS/CSS viewer
(`viewer.html`) plus a small JSON API over disk artifacts discovered by
`graphite.artifacts` -- sheet SVGs/JSON, payload-store files, and trace
JSON dumps. Every response is bytes read from disk or produced by
`json.dumps`; nothing here imports `regolith.orchestrator`/`regolith.harness`
(the artifact-only channel, AD-24/AD-22 applied to UI).

stdout is data (the one line printed on startup names the bound address);
every other message goes to stderr via `graphite.logging_setup`.
"""

from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from graphite.artifacts import (
    find_drawings_dirs,
    find_trace_files,
    list_payload_files,
    list_sheets,
    read_json,
)
from graphite.logging_setup import get_logger

_log = get_logger(__name__)

_VIEWER_HTML_PATH = Path(__file__).with_name("viewer.html")


def _sheet_items(root: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for drawings_dir in find_drawings_dirs(root):
        for sheet in list_sheets(drawings_dir):
            items.append(
                {
                    "label": sheet.subject,
                    "track": sheet.track,
                    "svg_url": f"/artifact?path={sheet.svg_path}"
                    if sheet.svg_path
                    else None,
                    "json_url": f"/artifact?path={sheet.json_path}"
                    if sheet.json_path
                    else None,
                }
            )
    return items


def _payload_items(root: Path) -> list[dict[str, object]]:
    payload_dir = root / ".regolith" / "payloads"
    items: list[dict[str, object]] = []
    for path in list_payload_files(payload_dir):
        items.append({"label": path.name, "json_url": f"/artifact?path={path}"})
    return items


def _trace_items(root: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in find_trace_files(root):
        items.append(
            {"label": str(path.relative_to(root)), "json_url": f"/artifact?path={path}"}
        )
    return items


def no_external_urls(text: str) -> bool:
    """True if `text` contains no scheme-bearing URL other than
    localhost/127.0.0.1/relative (the GUI acceptance-criteria regex;
    exported so the test suite reuses this one predicate)."""
    for match in re.finditer(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\"'<>]+", text):
        url = match.group(0)
        if url.startswith(
            ("http://localhost", "http://127.0.0.1", "https://localhost")
        ):
            continue
        return False
    return True


class ArtifactRequestHandler(BaseHTTPRequestHandler):
    """Routes: `/` (viewer HTML), `/api/sheets|payloads|traces` (JSON
    listings scoped to `self.workspace_root`), `/artifact?path=...`
    (raw bytes of one file UNDER `self.workspace_root` only -- path
    traversal outside the workspace root is refused, mirroring the
    `_FileTransport` confinement precedent in `regolith.cli.app`)."""

    workspace_root: Path = Path(".")
    server_version = "graphite/0.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Route BaseHTTPRequestHandler's access log through graphite's
        own logger (stderr), never stdout."""
        _log.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, payload: object) -> None:
        body = json.dumps(payload).encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_text(self, code: int, message: str) -> None:
        body = message.encode("ascii", errors="replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _confined_path(self, raw: str) -> Path | None:
        candidate = Path(unquote(raw))
        try:
            resolved = candidate.resolve()
            root = self.workspace_root.resolve()
        except OSError:
            return None
        if not resolved.is_relative_to(root):
            return None
        if not resolved.is_file():
            return None
        return resolved

    def do_GET(self) -> None:  # noqa: N802 (stdlib override)
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = _VIEWER_HTML_PATH.read_bytes()
            self._send_bytes(body, "text/html; charset=us-ascii")
            return
        if parsed.path == "/api/sheets":
            self._send_json(_sheet_items(self.workspace_root))
            return
        if parsed.path == "/api/payloads":
            self._send_json(_payload_items(self.workspace_root))
            return
        if parsed.path == "/api/traces":
            self._send_json(_trace_items(self.workspace_root))
            return
        if parsed.path == "/artifact":
            query = dict(
                pair.split("=", 1) for pair in parsed.query.split("&") if "=" in pair
            )
            raw_path = query.get("path")
            if raw_path is None:
                self._send_error_text(400, "missing path query param")
                return
            resolved = self._confined_path(raw_path)
            if resolved is None:
                _log.warning(
                    "graphite serve: refused path outside workspace: %s", raw_path
                )
                self._send_error_text(404, "not found")
                return
            content_type, _ = mimetypes.guess_type(str(resolved))
            if resolved.suffix == ".json":
                self._send_bytes(
                    read_json(resolved).encode("utf-8"), "application/json"
                )
            else:
                self._send_bytes(
                    resolved.read_bytes(), content_type or "application/octet-stream"
                )
            return
        self._send_error_text(404, "not found")


def make_server(host: str, port: int, workspace_root: Path) -> ThreadingHTTPServer:
    """Build the bound server (does not call `serve_forever` -- the caller
    decides run-vs-test lifecycle). Refuses a non-localhost host outright
    (AD-31: `graphite serve` binds localhost only, no remote/multi-user
    serving -- toolchain/29 sec. 3)."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        _log.error("graphite serve: refused non-localhost host %r", host)
        raise ValueError(f"graphite serve binds localhost only, got host={host!r}")
    handler = type(
        "_BoundArtifactRequestHandler",
        (ArtifactRequestHandler,),
        {"workspace_root": workspace_root},
    )
    server = ThreadingHTTPServer((host, port), handler)
    _log.info("graphite serve: bound %s:%d, workspace=%s", host, port, workspace_root)
    return server
