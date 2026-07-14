"""`regolith override set|list|clear` (D243.5, WO-129A deliverable 6-partial).

The `typer.testing.CliRunner` pattern this repo's other CLI tests use.
"""

from __future__ import annotations

from regolith.cli.app import app
from typer.testing import CliRunner

runner = CliRunner()


def test_set_requires_reason(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "override",
            "set",
            "--project",
            str(tmp_path),
            "foo.bar",
            "1mm",
            "--author",
            "logan",
            "--reason",
            "",
        ],
    )
    assert result.exit_code != 0
    assert "E1001" in result.output
    assert not (tmp_path / "overrides.toml").exists()


def test_set_list_clear_round_trip(tmp_path) -> None:
    set_result = runner.invoke(
        app,
        [
            "override",
            "set",
            "--project",
            str(tmp_path),
            "foo.bar",
            "24mm",
            "--author",
            "logan",
            "--reason",
            "matches stock",
        ],
    )
    assert set_result.exit_code == 0, set_result.output

    list_result = runner.invoke(app, ["override", "list", "--project", str(tmp_path)])
    assert list_result.exit_code == 0
    assert "foo.bar = 24mm" in list_result.output

    json_result = runner.invoke(
        app, ["override", "list", "--project", str(tmp_path), "--json"]
    )
    assert json_result.exit_code == 0
    assert '"target": "foo.bar"' in json_result.output

    clear_result = runner.invoke(
        app, ["override", "clear", "--project", str(tmp_path), "foo.bar"]
    )
    assert clear_result.exit_code == 0

    empty_list = runner.invoke(app, ["override", "list", "--project", str(tmp_path)])
    assert empty_list.exit_code == 0
    assert empty_list.output.strip() == ""


def test_clear_missing_target_is_a_reported_noop(tmp_path) -> None:
    result = runner.invoke(
        app, ["override", "clear", "--project", str(tmp_path), "nope.slot"]
    )
    assert result.exit_code == 0
    assert "nothing to clear" in result.output


def test_set_with_check_refuses_d246_boundary_target(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "override",
            "set",
            "--project",
            str(tmp_path),
            "--check",
            "examples/tracks/cuprite/ebi_decode.cupr",
            "decoder_board.require",
            "nor_glue",
            "--author",
            "logan",
            "--reason",
            "boundary probe",
        ],
    )
    assert result.exit_code != 0
    assert "E1002" in result.output
    assert not (tmp_path / "overrides.toml").exists()


def test_set_with_check_resolves_real_choice_point(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "override",
            "set",
            "--project",
            str(tmp_path),
            "--check",
            "examples/tracks/cuprite/ebi_decode.cupr",
            "decoder_board.AddressDecodeGlue",
            "nor_glue",
            "--author",
            "logan",
            "--reason",
            "known-good glue variant",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "overrides.toml").exists()


def test_set_with_check_refuses_unresolvable_target(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "override",
            "set",
            "--project",
            str(tmp_path),
            "--check",
            "examples/tracks/cuprite/ebi_decode.cupr",
            "nonexistent.slot.here",
            "nor_glue",
            "--author",
            "logan",
            "--reason",
            "probe",
        ],
    )
    assert result.exit_code != 0
    assert "E1003" in result.output
