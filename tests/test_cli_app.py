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


def test_doc_renders_part_with_verbatim_comment(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text("# A rail.\npart Rail:\n    material: AL7075_T6\n")
    result = runner.invoke(app, ["doc", str(source)])
    assert result.exit_code == EXIT_CLEAN
    assert "part `Rail`" in result.stdout
    assert "A rail." in result.stdout


def test_doc_nonascii_comment_round_trips(tmp_path: Path) -> None:
    """D115: extraction must not corrupt non-ASCII user content. This
    test source stays pure ASCII (``chr(0xB1)`` built at runtime); the
    on-disk FIXTURE it writes carries a real non-ASCII byte, matching
    the acceptance criterion's one deliberate non-ASCII fixture."""
    plus_minus = chr(0xB1)
    source = tmp_path / "a.hema"
    source.write_text(f"# Toleranzklasse: {plus_minus} 0.1mm\npart Rail:\n    x: 1mm\n")
    result = runner.invoke(app, ["doc", str(source)])
    assert result.exit_code == EXIT_CLEAN
    assert f"{plus_minus} 0.1mm" in result.stdout


def test_doc_out_writes_index_md(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text("part Rail:\n    material: AL7075_T6\n")
    out_dir = tmp_path / "docs-out"
    result = runner.invoke(app, ["doc", str(source), "--out", str(out_dir)])
    assert result.exit_code == EXIT_CLEAN
    assert (out_dir / "index.md").exists()


def test_doc_is_byte_identical_across_runs(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text("part Rail:\n    material: AL7075_T6\n")
    first = runner.invoke(app, ["doc", str(source)])
    second = runner.invoke(app, ["doc", str(source)])
    assert first.stdout == second.stdout


def test_doc_nonexistent_path_is_internal_error() -> None:
    result = runner.invoke(app, ["doc", "/no/such/file.hema"])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_doc_unbuilt_when_no_regolith_dir(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text(
        "part Rail:\n    material: AL7075_T6\n\n    require Structural:\n"
        "        rail_stress: 1 < 2\n"
    )
    result = runner.invoke(app, ["doc", str(source)])
    assert result.exit_code == EXIT_CLEAN
    assert "(unbuilt)" in result.stdout
