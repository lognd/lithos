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


def test_doctor_reports_every_catalog_tool() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == EXIT_CLEAN
    for name in ("kicad-cli", "verilator", "ghdl", "ngspice", "ccx", "gmsh"):
        assert name in result.output


def test_doctor_json_is_machine_readable_and_has_every_tool() -> None:
    import json

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == EXIT_CLEAN
    payload = json.loads(result.output)
    names = {row["name"] for row in payload}
    # `sigrok-cli` joined the catalog with WO-126 (charter 40 sec. 3: it
    # is reported by `regolith doctor`, and its absence degrades the
    # harness pack to the honest config-only tier). Its sibling test
    # above was updated then; this one was missed, so the JSON doctor
    # assertion was stale-red on master -- corrected here (WO-127).
    assert names == {
        "kicad-cli",
        "verilator",
        "ghdl",
        "ngspice",
        "ccx",
        "gmsh",
        "sigrok-cli",
    }
    for row in payload:
        assert "found" in row
        assert "capability" in row
        if not row["found"]:
            assert row["install_hint"]


def test_summary_line_and_clean_message_agree_on_non_l0_warning_count() -> None:
    """L3: single-shot's clean-summary and `check --watch`'s
    `_summary_line` must count warnings the same way, even for a
    non-L0 warning code."""
    from regolith.cli.app import _count_warnings, _summary_line

    rendered = "warning[L2-001]: something\nwarning[L0-003]: something else\n"
    single_shot_count = _count_warnings(rendered)
    watch_line = _summary_line(rendered, ok=True)
    assert single_shot_count == 2
    assert f"lints={single_shot_count}" in watch_line


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


def test_debug_ir_stage_lists_no_realized_inputs(tmp_path: Path) -> None:
    """WO-42 deliverable 3: `regolith debug ir` runs (unlike the
    previously-unimplemented `ir` stage) and names the realized-IR
    inspectability section, empty from the CLI today (no flag yet
    resolves realized-IR digests -- WO-42 deliverable 5's job)."""
    source = tmp_path / "a.hema"
    source.write_text("part Widget:\n  mass: 5 g\n")
    result = runner.invoke(app, ["debug", "ir", str(source)])
    assert result.exit_code == EXIT_CLEAN
    assert "realized IRs supplied" in result.stdout
    assert "(none supplied)" in result.stdout


def test_version_still_works() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


# frob:tests python/regolith/cli kind="integration"
# frob:tests python/regolith/docgen kind="integration"
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


def test_ship_missing_lockfile_is_named_diagnostic(tmp_path: Path) -> None:
    """`ship` needs a resolved `regolith.lock` before it will even attempt
    the release gate (WO-25); a project with neither a CWD-relative
    lockfile nor a `.regolith/build/regolith.lock` refuses with a NAMED
    diagnostic (nonzero exit, WO-25's own contract) that names both
    expected paths and suggests `regolith build --release`."""
    source = tmp_path / "a.hema"
    source.write_text("")
    result = runner.invoke(app, ["ship", str(source)])
    assert result.exit_code == EXIT_DIAGNOSTICS
    assert "regolith.lock" in result.output
    assert "build --release" in result.output


def test_ship_verify_without_trust_keys_is_internal_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ship", str(tmp_path), "--verify", str(tmp_path)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_ship_verify_nonexistent_package_is_diagnostics(tmp_path: Path) -> None:
    trust_file = tmp_path / "trust.json"
    trust_file.write_text('{"designations": []}')
    result = runner.invoke(
        app,
        [
            "ship",
            str(tmp_path),
            "--verify",
            str(tmp_path / "no-such-package"),
            "--trust-keys",
            str(trust_file),
        ],
    )
    assert result.exit_code == EXIT_DIAGNOSTICS
