"""std.cam parser tests (WO-67 deliverable 2): dialect front-ends,
canned-cycle rejection, malformed-input honesty, and the fuzz-safety
property (arbitrary bytes never raise)."""

from __future__ import annotations

from pathlib import Path

from regolith.harness.models.cam.ir import Dialect, parse_plan, parse_toolpath

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cam"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text()


def test_good_plan_parses_clean() -> None:
    toolpath = parse_toolpath(_read("good.nc"), Dialect.fanuc)
    assert toolpath.ok
    assert toolpath.moves
    assert len(toolpath.tool_changes) == 1  # exactly one T1 M6 tool change
    assert toolpath.tool_changes[0].tool == 1


def test_canned_cycle_rejected_with_named_diagnostic() -> None:
    toolpath = parse_toolpath(_read("canned_cycle.nc"), Dialect.fanuc)
    assert not toolpath.ok
    kinds = {issue.kind for issue in toolpath.issues}
    assert "canned_cycle_rejected" in kinds
    # Line-cited: the G81 line, not a generic failure.
    assert any(
        issue.line == 5
        for issue in toolpath.issues
        if issue.kind == "canned_cycle_rejected"
    )
    # G80 (cancel canned cycle) is a harmless modal reset, not itself a
    # rejected cycle -- it must not add a second spurious citation.
    assert all(issue.detail.find("G80") == -1 for issue in toolpath.issues)


def test_garbage_line_is_indeterminate_not_a_crash() -> None:
    """A line with no recognizable G/M/T/axis words is flagged as an
    honest `unrecognized_line` issue rather than silently dropped or
    raising (conservative-or-silent, charter D3)."""
    toolpath = parse_toolpath("@@@ not gcode @@@\n", Dialect.fanuc)
    assert not toolpath.ok
    assert toolpath.issues[0].kind == "unrecognized_line"
    assert toolpath.issues[0].line == 1


def test_unrecognized_line_is_indeterminate() -> None:
    toolpath = parse_toolpath("this is not gcode at all\n", Dialect.fanuc)
    assert not toolpath.ok
    assert toolpath.issues[0].kind == "unrecognized_line"


def test_marlin_dialect_parses_extrusion_moves() -> None:
    toolpath = parse_toolpath(_read("flagship1_print.gcode"), Dialect.marlin)
    assert toolpath.ok
    extruding = [m for m in toolpath.moves if m.extrude is not None]
    assert extruding


def test_incremental_mode_is_a_declared_exclusion() -> None:
    toolpath = parse_toolpath("G91\nG1 X10\n", Dialect.fanuc)
    assert not toolpath.ok
    assert toolpath.issues[0].kind == "incremental_mode_unsupported"


def test_fuzz_arbitrary_bytes_never_raise() -> None:
    """Lightly fuzz the parser (charter acceptance shape): arbitrary
    byte sequences must decode + parse without ever raising."""
    import random

    rng = random.Random(1337)
    for _ in range(200):
        length = rng.randint(0, 200)
        raw = bytes(rng.randrange(256) for _ in range(length))
        # Must not raise for either dialect.
        parse_plan(raw, Dialect.fanuc)
        parse_plan(raw, Dialect.marlin)
