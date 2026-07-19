"""CLI coverage for the `reg` alias, `new`/`magnetite new` parity, and the
magnetite `key`/`index`/`manifest` verbs added to expose the library's
existing functionality (owner ask: the CLI never exposed most of
regolith.magnetite beyond `new`)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from regolith.cli.app import EXIT_CLEAN, EXIT_DIAGNOSTICS, EXIT_INTERNAL_ERROR, app
from regolith.magnetite.trust import (
    KeyDesignation,
    TrustKeySet,
    TrustTier,
    load_signing_key,
)
from typer.testing import CliRunner

runner = CliRunner()


def test_reg_alias_registered_in_pyproject() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text())
    scripts = data["project"]["scripts"]
    assert scripts["reg"] == "regolith.cli:app"
    assert scripts["regolith"] == "regolith.cli:app"


def test_new_and_magnetite_new_produce_identical_results(tmp_path: Path) -> None:
    top = tmp_path / "top-proj"
    nested = tmp_path / "nested-proj"

    result_top = runner.invoke(app, ["new", str(top), "--template", "mech"])
    result_nested = runner.invoke(
        app, ["magnetite", "new", str(nested), "--template", "mech"]
    )

    assert result_top.exit_code == EXIT_CLEAN
    assert result_nested.exit_code == EXIT_CLEAN

    # File names embed the project name (`<name>.hema`), so compare
    # structure (relative paths with the project name stripped) rather
    # than exact names.
    top_files = sorted(
        str(p.relative_to(top)).replace("top-proj", "PROJ")
        for p in top.rglob("*")
        if p.is_file()
    )
    nested_files = sorted(
        str(p.relative_to(nested)).replace("nested-proj", "PROJ")
        for p in nested.rglob("*")
        if p.is_file()
    )
    assert top_files == nested_files
    assert (top / "magnetite.toml").is_file()
    assert (nested / "magnetite.toml").is_file()


def test_new_bad_template_is_internal_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["new", str(tmp_path / "bad"), "--template", "not-a-template"]
    )
    assert result.exit_code == EXIT_INTERNAL_ERROR


# frob:tests python/regolith/magnetite/trust.py::load_signing_key kind="unit"
def test_key_new_creates_a_usable_key(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["key", "new", "--id", "cli-key", "--dir", str(tmp_path)]
    )
    assert result.exit_code == EXIT_CLEAN
    assert (tmp_path / ".regolith" / "keys" / "cli-key.pem").is_file()

    loaded = load_signing_key(str(tmp_path), "cli-key")
    assert loaded.is_ok


def test_key_new_top_level_alias_matches_magnetite(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    r1 = runner.invoke(app, ["key", "new", "--id", "k", "--dir", str(dir_a)])
    r2 = runner.invoke(
        app, ["magnetite", "key", "new", "--id", "k", "--dir", str(dir_b)]
    )
    assert r1.exit_code == EXIT_CLEAN
    assert r2.exit_code == EXIT_CLEAN
    assert (dir_a / ".regolith" / "keys" / "k.pem").is_file()
    assert (dir_b / ".regolith" / "keys" / "k.pem").is_file()


def test_key_new_duplicate_id_is_internal_error(tmp_path: Path) -> None:
    runner.invoke(app, ["key", "new", "--id", "dup", "--dir", str(tmp_path)])
    result = runner.invoke(app, ["key", "new", "--id", "dup", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_key_show_prints_public_half_only(tmp_path: Path) -> None:
    runner.invoke(app, ["key", "new", "--id", "show-me", "--dir", str(tmp_path)])
    result = runner.invoke(app, ["key", "show", "show-me", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_CLEAN
    assert "show-me" in result.stdout
    assert "PRIVATE" not in result.stdout.upper()
    assert "BEGIN" not in result.stdout


def test_key_show_missing_key_is_internal_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["key", "show", "nope", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_key_list_reports_generated_ids(tmp_path: Path) -> None:
    runner.invoke(app, ["key", "new", "--id", "one", "--dir", str(tmp_path)])
    runner.invoke(app, ["key", "new", "--id", "two", "--dir", str(tmp_path)])
    result = runner.invoke(app, ["key", "list", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_CLEAN
    assert "one" in result.stdout
    assert "two" in result.stdout


def test_key_list_empty_dir_reports_none(tmp_path: Path) -> None:
    result = runner.invoke(app, ["key", "list", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_CLEAN
    assert "no local signing keys" in result.stdout


# frob:tests python/regolith/magnetite/trust.py::TrustKeySet.designation kind="unit"
# frob:tests python/regolith/magnetite/trust.py::TrustKeySet.designate kind="unit"
# frob:tests python/regolith/magnetite/trust.py::LocalSigningKey.public_key_base64 kind="unit"
def test_key_new_then_ship_accepts_it(tmp_path: Path) -> None:
    """Mirrors tests/packs/test_feldspar_conformance.py's key-then-ship
    pattern: a key minted via the CLI must be exactly what
    `load_signing_key` (and thus `ship --key`) reads back."""
    runner.invoke(app, ["key", "new", "--id", "ship-ready", "--dir", str(tmp_path)])
    loaded = load_signing_key(str(tmp_path), "ship-ready")
    assert loaded.is_ok
    key = loaded.danger_ok
    keys = TrustKeySet().designate(
        KeyDesignation(
            key_id=key.key_id,
            public_key_base64=key.public_key_base64(),
            confers=TrustTier.COMMUNITY,
        )
    )
    assert keys.designation("ship-ready") is not None


def test_index_show_lists_entries(tmp_path: Path) -> None:
    index_file = tmp_path / "pkg.ndjson"
    index_file.write_text(
        '{"name": "widget", "version": "1.0.0", '
        '"manifest_digest": "blake3:aa", "archive_hash": "blake3:bb"}\n'
        '{"name": "widget", "version": "2.0.0", '
        '"manifest_digest": "blake3:cc", "archive_hash": "blake3:dd", '
        '"yanked": true}\n'
    )
    result = runner.invoke(app, ["magnetite", "index", "show", str(index_file)])
    assert result.exit_code == EXIT_CLEAN
    assert "1.0.0" in result.stdout
    assert "2.0.0" in result.stdout
    assert "YANKED" in result.stdout


def test_index_show_malformed_file_is_internal_error(tmp_path: Path) -> None:
    index_file = tmp_path / "bad.ndjson"
    index_file.write_text("not json\n")
    result = runner.invoke(app, ["magnetite", "index", "show", str(index_file)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_index_select_exact_version(tmp_path: Path) -> None:
    index_file = tmp_path / "pkg.ndjson"
    index_file.write_text(
        '{"name": "widget", "version": "1.0.0", '
        '"manifest_digest": "blake3:aa", "archive_hash": "blake3:bb"}\n'
    )
    result = runner.invoke(
        app, ["magnetite", "index", "select", str(index_file), "1.0.0"]
    )
    assert result.exit_code == EXIT_CLEAN
    assert "1.0.0" in result.stdout


def test_index_select_missing_version_is_diagnostic(tmp_path: Path) -> None:
    index_file = tmp_path / "pkg.ndjson"
    index_file.write_text(
        '{"name": "widget", "version": "1.0.0", '
        '"manifest_digest": "blake3:aa", "archive_hash": "blake3:bb"}\n'
    )
    result = runner.invoke(
        app, ["magnetite", "index", "select", str(index_file), "9.9.9"]
    )
    assert result.exit_code == EXIT_DIAGNOSTICS


def test_index_latest_skips_yanked(tmp_path: Path) -> None:
    index_file = tmp_path / "pkg.ndjson"
    index_file.write_text(
        '{"name": "widget", "version": "1.0.0", '
        '"manifest_digest": "blake3:aa", "archive_hash": "blake3:bb"}\n'
        '{"name": "widget", "version": "2.0.0", '
        '"manifest_digest": "blake3:cc", "archive_hash": "blake3:dd", '
        '"yanked": true}\n'
    )
    result = runner.invoke(app, ["magnetite", "index", "latest", str(index_file)])
    assert result.exit_code == EXIT_CLEAN
    assert "1.0.0" in result.stdout


def test_manifest_check_valid(tmp_path: Path) -> None:
    result = runner.invoke(app, ["new", str(tmp_path / "proj"), "--template", "mech"])
    assert result.exit_code == EXIT_CLEAN
    check = runner.invoke(
        app, ["magnetite", "manifest", "check", str(tmp_path / "proj")]
    )
    assert check.exit_code == EXIT_CLEAN
    assert "provides=" in check.stdout


def test_manifest_check_missing_is_diagnostic(tmp_path: Path) -> None:
    result = runner.invoke(app, ["magnetite", "manifest", "check", str(tmp_path)])
    assert result.exit_code == EXIT_DIAGNOSTICS
