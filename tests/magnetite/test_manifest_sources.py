"""``[sources]`` parsing in ``load_manifest`` (regolith/11 sec. 10.2).

Sources are declared in the manifest -- there is no ambient default
inside the languages. These tests cover the happy path, the "no
[sources] table at all" case (empty Sources, not an error), and a
handful of malformed shapes (each a named `MagnetiteError`, never an
exception).
"""

from __future__ import annotations

from pathlib import Path

from regolith.magnetite.manifest import load_manifest

_PACKAGE_HEADER = '[package]\nname = "p"\nversion = "0.1.0"\n'


def _write(tmp_path: Path, body: str) -> Path:
    manifest_path = tmp_path / "magnetite.toml"
    manifest_path.write_text(_PACKAGE_HEADER + body)
    return manifest_path


def test_missing_sources_table_is_empty_not_an_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "")
    result = load_manifest(str(path))
    assert result.is_ok
    sources = result.danger_ok.sources
    assert sources.registries == ()
    assert sources.routes == ()


def test_parses_registries_routes_and_default(tmp_path: Path) -> None:
    body = """
[sources]
default = "reg1"

[sources.routes]
std = "reg1"
acme = "reg2"

[sources.registries.reg1]
index_url = "https://pub.example/index"
archive_url = "https://pub.example/archive"

[sources.registries.reg2]
index_url = "https://corp.example/index"
archive_url = "https://corp.example/archive"
"""
    path = _write(tmp_path, body)
    result = load_manifest(str(path))
    assert result.is_ok
    sources = result.danger_ok.sources
    assert sources.default == "reg1"
    assert {r.name for r in sources.registries} == {"reg1", "reg2"}
    assert sources.route("acme.widgets").danger_ok.name == "reg2"
    assert sources.route("std.materials").danger_ok.name == "reg1"


def test_sources_not_a_table_is_malformed(tmp_path: Path) -> None:
    manifest_path = tmp_path / "magnetite.toml"
    manifest_path.write_text("sources = 3\n" + _PACKAGE_HEADER)
    result = load_manifest(str(manifest_path))
    assert result.is_err
    assert result.danger_err.kind == "malformed_sources"


def test_registry_missing_archive_url_is_malformed(tmp_path: Path) -> None:
    body = """
[sources.registries.reg1]
index_url = "https://pub.example/index"
"""
    path = _write(tmp_path, body)
    result = load_manifest(str(path))
    assert result.is_err
    assert result.danger_err.kind == "malformed_sources"


def test_route_naming_undeclared_registry_is_malformed(tmp_path: Path) -> None:
    body = """
[sources]
default = "reg1"

[sources.registries.reg1]
index_url = "https://pub.example/index"
archive_url = "https://pub.example/archive"

[sources.routes]
acme = "ghost"
"""
    path = _write(tmp_path, body)
    result = load_manifest(str(path))
    assert result.is_err
    assert result.danger_err.kind == "unknown_source"


def test_default_naming_undeclared_registry_is_malformed(tmp_path: Path) -> None:
    body = """
[sources]
default = "ghost"

[sources.registries.reg1]
index_url = "https://pub.example/index"
archive_url = "https://pub.example/archive"
"""
    path = _write(tmp_path, body)
    result = load_manifest(str(path))
    assert result.is_err
    assert result.danger_err.kind == "unknown_default_source"
