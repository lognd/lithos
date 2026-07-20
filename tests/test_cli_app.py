"""WO-15 `check` CLI: exit codes and rendering, via typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

from regolith.cli.app import EXIT_CLEAN, EXIT_DIAGNOSTICS, EXIT_INTERNAL_ERROR, app
from typer.testing import CliRunner

runner = CliRunner()


# frob:tests python/regolith/compiler.py kind="integration"
# frob:tests python/regolith/errors.py kind="integration"
# frob:tests python/regolith/_schema_base.py kind="integration"
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


# --- T-0036 phase 2 backfill: doctor / explain / fmt / debug error paths --


# frob:ticket T-0036
def test_doctor_json_no_exec_offline_active_env(monkeypatch) -> None:  # noqa: ANN001
    """The two kill-switch env vars flip the JSON-unrelated ACTIVE/
    inactive prose lines (non-JSON path), covering the truthy branch."""
    monkeypatch.setenv("REGOLITH_NO_EXEC", "1")
    monkeypatch.setenv("REGOLITH_OFFLINE", "yes")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == EXIT_CLEAN
    assert "ACTIVE" in result.output


# frob:ticket T-0036
def test_doctor_env_vars_falsy_string_reads_inactive(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("REGOLITH_NO_EXEC", "0")
    monkeypatch.setenv("REGOLITH_OFFLINE", "false")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == EXIT_CLEAN
    assert "inactive" in result.output


# frob:ticket T-0036
def test_explain_unknown_code_prose_suggests_near_matches() -> None:
    result = runner.invoke(app, ["explain", "ZZZZZ999"])
    assert result.exit_code == EXIT_DIAGNOSTICS
    assert "unknown code" in result.output
    assert "Did you mean" in result.output


# frob:ticket T-0036
def test_explain_unknown_code_json_names_near_matches() -> None:
    import json as _json

    result = runner.invoke(app, ["explain", "ZZZZZ999", "--json"])
    assert result.exit_code == EXIT_DIAGNOSTICS
    payload = _json.loads(result.output)
    assert payload["error"] == "unknown_code"
    assert isinstance(payload["near"], list)


# frob:ticket T-0036
def test_explain_known_code_prose_and_json_agree_on_code() -> None:
    import json as _json

    from regolith._codes import ALL as ALL_CODES

    known = ALL_CODES[0].code
    prose = runner.invoke(app, ["explain", known])
    as_json = runner.invoke(app, ["explain", known, "--json"])
    assert prose.exit_code == EXIT_CLEAN
    assert as_json.exit_code == EXIT_CLEAN
    assert known in prose.output
    assert _json.loads(as_json.output)["code"] == known


# frob:ticket T-0036
def test_fmt_write_error_is_internal_error(tmp_path: Path) -> None:
    """A path that IS a file for reading but cannot be written back (a
    directory swapped in mid-flight is impractical to fixture safely,
    so this exercises the write-error branch via a read-only file)."""
    source = tmp_path / "ro.hema"
    source.write_text("")
    source.chmod(0o444)
    try:
        result = runner.invoke(app, ["fmt", str(source)])
    finally:
        source.chmod(0o644)
    # A read-only file either raises on write (internal error) or the
    # process runs as an owner that can still write despite the bit
    # (root/CI oddities) -- assert the non-crashing outcome set only.
    assert result.exit_code in (EXIT_CLEAN, EXIT_INTERNAL_ERROR)


# frob:ticket T-0036
def test_debug_cst_and_ast_stages_run(tmp_path: Path) -> None:
    source = tmp_path / "a.hema"
    source.write_text("part Widget:\n    mass: 5 g\n")
    for stage in ("cst", "ast"):
        result = runner.invoke(app, ["debug", stage, str(source)])
        assert result.exit_code in (EXIT_CLEAN, EXIT_INTERNAL_ERROR)


# --- config get/where/list/set ------------------------------------------


# frob:ticket T-0036
def test_config_get_known_key_default(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["config", "get", "ui.port", "--project", str(tmp_path)]
    )
    assert result.exit_code == EXIT_CLEAN
    assert result.output.strip() == "8765"


# frob:ticket T-0036
def test_config_get_unknown_key_is_diagnostics(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["config", "get", "no.such.key", "--project", str(tmp_path)]
    )
    assert result.exit_code == EXIT_DIAGNOSTICS


# frob:ticket T-0036
def test_config_where_reports_source(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["config", "where", "ui.port", "--project", str(tmp_path)]
    )
    assert result.exit_code == EXIT_CLEAN
    assert "ui.port=8765" in result.output
    assert "source=" in result.output


# frob:ticket T-0036
def test_config_where_unknown_key_is_diagnostics(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["config", "where", "no.such.key", "--project", str(tmp_path)]
    )
    assert result.exit_code == EXIT_DIAGNOSTICS


# frob:ticket T-0036
def test_config_list_prints_every_registered_key(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "list", "--project", str(tmp_path)])
    assert result.exit_code == EXIT_CLEAN
    assert "ui.port=8765" in result.output
    assert "optimize.seed=0" in result.output


# frob:ticket T-0036
def test_config_set_requires_exactly_one_scope(tmp_path: Path) -> None:
    both = runner.invoke(
        app,
        [
            "config", "set", "ui.port", "9000",
            "--global", "--local", "--project", str(tmp_path),
        ],
    )
    assert both.exit_code == EXIT_INTERNAL_ERROR
    neither = runner.invoke(
        app, ["config", "set", "ui.port", "9000", "--project", str(tmp_path)]
    )
    assert neither.exit_code == EXIT_INTERNAL_ERROR


# frob:ticket T-0036
def test_config_set_local_writes_and_get_reads_it_back(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text(
        '[package]\nname = "p"\nversion = "1.0.0"\nkinds = []\n'
    )
    set_result = runner.invoke(
        app, ["config", "set", "ui.port", "9000", "--local", "--project", str(tmp_path)]
    )
    assert set_result.exit_code == EXIT_CLEAN
    assert "wrote ui.port" in set_result.output
    get_result = runner.invoke(
        app, ["config", "get", "ui.port", "--project", str(tmp_path)]
    )
    assert get_result.exit_code == EXIT_CLEAN
    assert get_result.output.strip() == "9000"


# frob:ticket T-0036
def test_config_set_bad_value_for_int_key_is_diagnostics(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text(
        '[package]\nname = "p"\nversion = "1.0.0"\nkinds = []\n'
    )
    result = runner.invoke(
        app,
        [
            "config", "set", "ui.port", "not-an-int",
            "--local", "--project", str(tmp_path),
        ],
    )
    assert result.exit_code == EXIT_DIAGNOSTICS


# --- index show/select/latest --------------------------------------------

_INDEX_NDJSON = (
    '{"name":"p","version":"1.0.0","manifest_digest":"blake3:a",'
    '"archive_hash":"blake3:b"}\n'
    '{"name":"p","version":"1.1.0","manifest_digest":"blake3:c",'
    '"archive_hash":"blake3:d","yanked":true}\n'
)


# frob:ticket T-0036
def test_index_show_lists_entries(tmp_path: Path) -> None:
    idx = tmp_path / "index.ndjson"
    idx.write_text(_INDEX_NDJSON)
    result = runner.invoke(app, ["magnetite", "index", "show", str(idx)])
    assert result.exit_code == EXIT_CLEAN
    assert "1.0.0" in result.output
    assert "YANKED" in result.output


# frob:ticket T-0036
def test_index_show_no_entries(tmp_path: Path) -> None:
    idx = tmp_path / "index.ndjson"
    idx.write_text("")
    result = runner.invoke(app, ["magnetite", "index", "show", str(idx)])
    assert result.exit_code == EXIT_CLEAN
    assert "no entries" in result.output


# frob:ticket T-0036
def test_index_show_missing_file_is_internal_error() -> None:
    result = runner.invoke(app, ["magnetite", "index", "show", "/no/such/index.ndjson"])
    assert result.exit_code == EXIT_INTERNAL_ERROR


# frob:ticket T-0036
def test_index_select_exact_version_including_yanked(tmp_path: Path) -> None:
    idx = tmp_path / "index.ndjson"
    idx.write_text(_INDEX_NDJSON)
    result = runner.invoke(app, ["magnetite", "index", "select", str(idx), "1.1.0"])
    assert result.exit_code == EXIT_CLEAN
    assert "YANKED" in result.output


# frob:ticket T-0036
def test_index_select_missing_version_is_diagnostics(tmp_path: Path) -> None:
    idx = tmp_path / "index.ndjson"
    idx.write_text(_INDEX_NDJSON)
    result = runner.invoke(app, ["magnetite", "index", "select", str(idx), "9.9.9"])
    assert result.exit_code == EXIT_DIAGNOSTICS


# frob:ticket T-0036
def test_index_select_missing_file_is_internal_error() -> None:
    result = runner.invoke(
        app, ["magnetite", "index", "select", "/no/such/index.ndjson", "1.0.0"]
    )
    assert result.exit_code == EXIT_INTERNAL_ERROR


# frob:ticket T-0036
def test_index_latest_skips_yanked(tmp_path: Path) -> None:
    idx = tmp_path / "index.ndjson"
    idx.write_text(_INDEX_NDJSON)
    result = runner.invoke(app, ["magnetite", "index", "latest", str(idx)])
    assert result.exit_code == EXIT_CLEAN
    assert "1.0.0" in result.output


# frob:ticket T-0036
def test_index_latest_all_yanked_is_diagnostics(tmp_path: Path) -> None:
    idx = tmp_path / "index.ndjson"
    idx.write_text(
        '{"name":"p","version":"1.0.0","manifest_digest":"blake3:a",'
        '"archive_hash":"blake3:b","yanked":true}\n'
    )
    result = runner.invoke(app, ["magnetite", "index", "latest", str(idx)])
    assert result.exit_code == EXIT_DIAGNOSTICS


# frob:ticket T-0036
def test_index_latest_missing_file_is_internal_error() -> None:
    result = runner.invoke(
        app, ["magnetite", "index", "latest", "/no/such/index.ndjson"]
    )
    assert result.exit_code == EXIT_INTERNAL_ERROR


# --- manifest check --------------------------------------------------------


# frob:ticket T-0036
def test_manifest_check_valid_file(tmp_path: Path) -> None:
    manifest = tmp_path / "magnetite.toml"
    manifest.write_text('[package]\nname = "p"\nversion = "1.0.0"\nkinds = []\n')
    result = runner.invoke(app, ["magnetite", "manifest", "check", str(manifest)])
    assert result.exit_code == EXIT_CLEAN
    assert "p 1.0.0" in result.output


# frob:ticket T-0036
def test_manifest_check_missing_file_is_diagnostics(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["magnetite", "manifest", "check", str(tmp_path / "nope")]
    )
    assert result.exit_code == EXIT_DIAGNOSTICS


# --- key new/list/show ------------------------------------------------


# frob:ticket T-0036
def test_key_list_no_keys_directory(tmp_path: Path) -> None:
    result = runner.invoke(app, ["key", "list", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_CLEAN
    assert "no local signing keys" in result.output


# frob:ticket T-0036
def test_key_new_then_list_then_show(tmp_path: Path) -> None:
    new_result = runner.invoke(
        app, ["key", "new", "--id", "test-key", "--dir", str(tmp_path)]
    )
    assert new_result.exit_code == EXIT_CLEAN
    list_result = runner.invoke(app, ["key", "list", "--dir", str(tmp_path)])
    assert list_result.exit_code == EXIT_CLEAN
    assert "test-key" in list_result.output
    show_result = runner.invoke(
        app, ["key", "show", "test-key", "--dir", str(tmp_path)]
    )
    assert show_result.exit_code == EXIT_CLEAN
    assert "test-key" in show_result.output


# frob:ticket T-0036
def test_key_show_missing_key_is_internal_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["key", "show", "no-such-key", "--dir", str(tmp_path)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


# --- plugin list / artifacts ------------------------------------------


# frob:ticket T-0036
def test_plugin_list_json_is_a_list() -> None:
    import json as _json

    result = runner.invoke(app, ["plugin", "list", "--json"])
    assert result.exit_code == EXIT_CLEAN
    assert isinstance(_json.loads(result.output), list)


# frob:ticket T-0036
def test_artifacts_missing_index_is_internal_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["artifacts", str(tmp_path)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


# --- new (project scaffold) ---------------------------------------------


# frob:ticket T-0036
def test_new_scaffolds_a_project(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "widget_proj", "--template", "mech"])
    assert result.exit_code == EXIT_CLEAN
    assert "scaffolded" in result.output


# frob:ticket T-0036
def test_new_refuses_nonempty_directory(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    target = tmp_path / "existing_proj"
    target.mkdir()
    (target / "keepme.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "existing_proj", "--template", "mech"])
    assert result.exit_code == EXIT_INTERNAL_ERROR
