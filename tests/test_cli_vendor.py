"""`regolith magnetite vendor` end to end (regolith/11 sec. 10.2-10.3).

Drives the real CLI verb against a local, on-disk fixture registry
addressed via `file://` URLs -- the CLI's real `httpx.Client` mounts a
`file://` transport (see `regolith.cli.app._FileTransport`), so this
never touches the network, per the sandbox rule.
"""

from __future__ import annotations

from pathlib import Path

import blake3
from regolith.cli.app import EXIT_CLEAN, EXIT_DIAGNOSTICS, app
from typer.testing import CliRunner

runner = CliRunner()


def _hash(data: bytes) -> str:
    return "blake3:" + blake3.blake3(data).hexdigest()


def _write_fixture_registry(root: Path, package: str, version: str, data: bytes) -> str:
    """A minimal on-disk sparse-index + archive store; returns its archive hash."""
    archive_hash = _hash(data)
    digest = archive_hash.split(":", 1)[1]
    index_dir = root / "index"
    archive_dir = root / "archive"
    index_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    (index_dir / package).write_text(
        f'{{"name":"{package}","version":"{version}",'
        f'"manifest_digest":"blake3:aa","archive_hash":"{archive_hash}"}}\n'
    )
    (archive_dir / digest).write_bytes(data)
    return archive_hash


def _write_project(
    project: Path, registry_root: Path, package: str, version: str, archive_hash: str
) -> None:
    project.mkdir(parents=True)
    (project / "magnetite.toml").write_text(
        f"""[package]
name = "consumer"
version = "0.1.0"

[sources]
default = "fixture"

[sources.registries.fixture]
index_url = "file://localhost{registry_root}/index"
archive_url = "file://localhost{registry_root}/archive"
"""
    )
    (project / "regolith.lock").write_text(
        "# regolith.lock tool_version=0.1.0\n"
        '\n[section ""]\n'
        f"pin {package}@{version} = {archive_hash}\n"
    )


def test_vendor_happy_path_copies_archive(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    project = tmp_path / "project"
    data = b"vendored-archive-bytes"
    archive_hash = _write_fixture_registry(registry_root, "p", "1.0.0", data)
    _write_project(project, registry_root, "p", "1.0.0", archive_hash)

    result = runner.invoke(app, ["magnetite", "vendor", str(project)])

    assert result.exit_code == EXIT_CLEAN, result.output
    vendored = project / "vendor" / archive_hash.split(":", 1)[1]
    assert vendored.is_file()
    assert vendored.read_bytes() == data


def test_vendor_alias_matches_magnetite_vendor(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    project = tmp_path / "project"
    data = b"aliased-archive-bytes"
    archive_hash = _write_fixture_registry(registry_root, "p", "1.0.0", data)
    _write_project(project, registry_root, "p", "1.0.0", archive_hash)

    result = runner.invoke(app, ["vendor", str(project)])

    assert result.exit_code == EXIT_CLEAN, result.output
    assert (project / "vendor" / archive_hash.split(":", 1)[1]).is_file()


def test_vendor_missing_lockfile_is_honest_nonzero_exit(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "magnetite.toml").write_text(
        '[package]\nname = "consumer"\nversion = "0.1.0"\n'
    )

    result = runner.invoke(app, ["magnetite", "vendor", str(project)])

    assert result.exit_code == EXIT_DIAGNOSTICS
    assert "lockfile" in result.output


def test_vendor_hash_mismatch_is_honest_nonzero_exit(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    project = tmp_path / "project"
    data = b"original-bytes"
    archive_hash = _write_fixture_registry(registry_root, "p", "1.0.0", data)
    # tamper with the served archive bytes after the hash was computed
    digest = archive_hash.split(":", 1)[1]
    (registry_root / "archive" / digest).write_bytes(b"tampered-bytes")
    _write_project(project, registry_root, "p", "1.0.0", archive_hash)

    result = runner.invoke(app, ["magnetite", "vendor", str(project)])

    assert result.exit_code == EXIT_DIAGNOSTICS
    assert "hash" in result.output.lower() or "drift" in result.output.lower()


def test_fetch_with_dot_dot_package_name_is_refused(tmp_path: Path) -> None:
    """M1: a `..`-laden package name must not walk the resolved file://
    path outside the registry's own index/archive directories (e.g.
    reading a file that is a sibling of the registry root)."""
    registry_root = tmp_path / "registry"
    project = tmp_path / "project"
    data = b"fetchable-bytes"
    archive_hash = _write_fixture_registry(registry_root, "p", "1.0.0", data)
    _write_project(project, registry_root, "p", "1.0.0", archive_hash)
    # A file that exists as a SIBLING of the registry's index dir --
    # confinement must refuse this even though it exists on disk.
    secret = registry_root / "secret.txt"
    secret.write_text("do not serve me")

    result = runner.invoke(
        app,
        [
            "magnetite",
            "fetch",
            "../secret.txt",
            "1.0.0",
            "--path",
            str(project),
        ],
    )

    assert result.exit_code == EXIT_DIAGNOSTICS
    assert "do not serve me" not in result.output


def test_fetch_prints_resolved_archive(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    project = tmp_path / "project"
    data = b"fetchable-bytes"
    archive_hash = _write_fixture_registry(registry_root, "p", "1.0.0", data)
    _write_project(project, registry_root, "p", "1.0.0", archive_hash)

    result = runner.invoke(
        app, ["magnetite", "fetch", "p", "1.0.0", "--path", str(project)]
    )

    assert result.exit_code == EXIT_CLEAN, result.output
    assert archive_hash in result.output
    assert str(len(data)) in result.output
