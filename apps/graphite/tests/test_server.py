"""`graphite serve` http tests (WO-59 acceptance): sheet listing + SVG
serving, payload pretty-print, zero external references, localhost-only
bind refusal.
"""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest
from graphite.server import make_server, no_external_urls


@pytest.fixture
def running_server(tmp_path):
    drawings = tmp_path / "drawings"
    drawings.mkdir()
    (drawings / "board.drawing.json").write_text(json.dumps({"track": "elec_blocks"}))
    (drawings / "board.drawing.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'><title>board</title></svg>"
    )
    payloads = tmp_path / ".regolith" / "payloads"
    payloads.mkdir(parents=True)
    (payloads / "blake3:deadbeef").write_text(json.dumps({"hello": "world"}))
    build_dir = tmp_path / ".regolith" / "build"
    build_dir.mkdir(parents=True)
    trace_path = build_dir / "opt_trace_1.json"
    trace_path.write_text(json.dumps({"strategy_id": "x"}))

    server = make_server("127.0.0.1", 0, tmp_path)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", tmp_path
    finally:
        server.shutdown()
        server.server_close()


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_refuses_non_localhost_host(tmp_path):
    with pytest.raises(ValueError):
        make_server("0.0.0.0", 0, tmp_path)


def test_index_serves_viewer_html(running_server):
    base, _ = running_server
    status, body = _get(base + "/")
    assert status == 200
    assert b"<title>graphite</title>" in body


def test_sheet_listing(running_server):
    base, _ = running_server
    status, body = _get(base + "/api/sheets")
    assert status == 200
    items = json.loads(body)
    assert len(items) == 1
    assert items[0]["track"] == "elec_blocks"
    assert items[0]["svg_url"] is not None


def test_svg_served_verbatim(running_server):
    base, root = running_server
    status, body = _get(base + "/api/sheets")
    items = json.loads(body)
    svg_url = items[0]["svg_url"]
    status2, svg_body = _get(base + svg_url)
    assert status2 == 200
    assert b"<title>board</title>" in svg_body


def test_payload_pretty_print(running_server):
    base, _ = running_server
    status, body = _get(base + "/api/payloads")
    items = json.loads(body)
    assert len(items) == 1
    status2, payload_body = _get(base + items[0]["json_url"])
    assert status2 == 200
    assert json.loads(payload_body) == {"hello": "world"}


def test_trace_listing(running_server):
    base, _ = running_server
    status, body = _get(base + "/api/traces")
    items = json.loads(body)
    assert len(items) == 1


def test_artifact_outside_workspace_refused(running_server, tmp_path):
    base, root = running_server
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}")
    status, _ = _get(base + f"/artifact?path={outside}")
    assert status == 404


def test_no_external_urls_in_served_bytes(running_server):
    base, _ = running_server
    status, body = _get(base + "/")
    assert status == 200
    assert no_external_urls(body.decode("utf-8"))


def test_no_external_urls_predicate():
    assert no_external_urls("fetch('/api/sheets')")
    assert no_external_urls("http://localhost:8765/artifact")
    assert not no_external_urls("https://cdn.example.com/lib.js")
