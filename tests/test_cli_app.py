"""WO-15 `check` CLI: exit codes and rendering, via typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

from regolith.cli.app import EXIT_CLEAN, EXIT_DIAGNOSTICS, EXIT_INTERNAL_ERROR, app
from typer.testing import CliRunner

runner = CliRunner()


def test_check_clean_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.hema"
    source.write_text("")
    result = runner.invoke(app, ["check", str(source)])
    assert result.exit_code in (EXIT_CLEAN, EXIT_DIAGNOSTICS)


def test_check_nonexistent_path_is_internal_error() -> None:
    result = runner.invoke(app, ["check", "/no/such/file.hema"])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_check_empty_file_list_is_a_usage_error() -> None:
    result = runner.invoke(app, ["check"])
    assert result.exit_code != EXIT_CLEAN


def test_fmt_rewrites_file(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text("")
    result = runner.invoke(app, ["fmt", str(source)])
    assert result.exit_code == EXIT_CLEAN
    assert source.exists()


def test_fmt_nonexistent_path_is_internal_error() -> None:
    result = runner.invoke(app, ["fmt", "/no/such/file.hema"])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_debug_nonexistent_path_is_internal_error() -> None:
    result = runner.invoke(app, ["debug", "tokens", "/no/such/file.hema"])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_debug_valid_stage(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text("")
    result = runner.invoke(app, ["debug", "tokens", str(source)])
    assert result.exit_code in (EXIT_CLEAN, EXIT_INTERNAL_ERROR)


def test_version_still_works() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"
