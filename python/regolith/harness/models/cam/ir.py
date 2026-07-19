"""The std.cam toolpath IR + dialect front-ends (WO-67 deliverable 2).

Spec: toolchain/33-cam-verification.md sec. 1 D2 (`cam.parse`); AD-35.
Two dialects share ONE typed IR (:class:`Move`/:class:`ToolChange`/
:class:`Toolpath`): `gcode_fanuc` (G0/G1/G2/G3 + tool changes + work
offsets; canned cycles G81/G82/G73/G83/... are REJECTED with a named
diagnostic, never silently skipped) and `gcode_marlin` (the FDM subset:
G0/G1 + extrusion `E`, no arcs/tool-changes required). Parse failure is
data, never an exception (INDETERMINATE citing the offending line) --
this module is deliberately fed arbitrary bytes by the fuzz test in
`tests/harness/test_cam_parse.py` and must never raise on them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Canned-cycle G-codes (drilling/boring/tapping cycles): v1 REJECTS these
# outright rather than silently modeling their motion (sec. 1 D2). G80
# (cancel canned cycle -- a harmless modal reset, not a cycle itself)
# is deliberately NOT in this set.
_CANNED_CYCLE_NUMS = frozenset(
    {"73", "74", "76", "81", "82", "83", "84", "85", "86", "87", "88", "89"}
)

_AXIS_LETTERS = ("X", "Y", "Z", "A", "B", "C")


# frob:doc docs/modules/py-harness.md#models-cam
class Dialect(StrEnum):
    """The two supported plan dialects (charter sec. 1 D2/D5)."""

    fanuc = "gcode_fanuc"
    marlin = "gcode_marlin"


# frob:doc docs/modules/py-harness.md#models-cam
class MoveKind(StrEnum):
    """The motion class a parsed line carries."""

    rapid = "rapid"  # G0
    linear = "linear"  # G1
    arc_cw = "arc_cw"  # G2
    arc_ccw = "arc_ccw"  # G3


# frob:doc docs/modules/py-harness.md#models-cam
class Move(BaseModel):
    """One parsed motion command: target position + the commanded feed.

    Positions are absolute machine-frame coordinates (v1: G90 absolute
    mode assumed -- incremental G91 is a declared exclusion, see the
    ``incremental_mode_unsupported`` issue kind). ``line`` is the
    1-based source line this move was parsed from (every downstream
    citation traces back through this field, never a re-derived index).
    """

    model_config = ConfigDict(frozen=True)

    line: int
    kind: MoveKind
    x: float | None = None
    y: float | None = None
    z: float | None = None
    feed: float | None = None
    extrude: float | None = None  # marlin `E` (cumulative filament position)
    tool: int | None = None  # active tool id at this move


# frob:doc docs/modules/py-harness.md#models-cam
class ToolChange(BaseModel):
    """A `T<n> M6` tool-change event (fanuc) -- cited by line."""

    model_config = ConfigDict(frozen=True)

    line: int
    tool: int


# frob:doc docs/modules/py-harness.md#models-cam
class ParseIssue(BaseModel):
    """One INDETERMINATE-causing parse issue, always line-cited."""

    model_config = ConfigDict(frozen=True)

    line: int
    kind: str
    detail: str


# frob:doc docs/modules/py-harness.md#models-cam
class Toolpath(BaseModel):
    """The typed toolpath IR: parsed moves + tool changes + any issues.

    ``issues`` is non-empty exactly when the plan could not be fully
    understood; callers (the downstream models) treat a non-empty
    ``issues`` list as grounds for INDETERMINATE, never partial trust
    in the moves that DID parse (conservative-or-silent, charter D3).
    """

    model_config = ConfigDict(frozen=True)

    dialect: Dialect
    moves: tuple[Move, ...] = ()
    tool_changes: tuple[ToolChange, ...] = ()
    issues: tuple[ParseIssue, ...] = ()

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def ok(self) -> bool:
        """True iff nothing prevented full understanding of the plan."""
        return not self.issues


_LINE_COMMENT_RE = re.compile(r"\(([^)]*)\)|;.*$")
_WORD_RE = re.compile(r"([A-Za-z])\s*(-?[0-9]*\.?[0-9]+)")


def _strip_comment(line: str) -> str:
    """Drop parenthetical and `;` comments (both dialects use these)."""
    return _LINE_COMMENT_RE.sub(" ", line)


def _words(line: str) -> list[tuple[str, str]]:
    """Tokenize a stripped line into (letter, number-text) word pairs.

    Never raises: a line with no recognizable words yields an empty
    list, letting the caller decide whether that is a blank/skippable
    line or a genuine parse issue.
    """
    return [(m.group(1).upper(), m.group(2)) for m in _WORD_RE.finditer(line)]


def _to_float(text: str, *, line: int, field: str) -> Result[float, ParseIssue]:
    """Parse one numeric word, as an INDETERMINATE-shaped ``Result``."""
    try:
        return Ok(float(text))
    except ValueError:
        return Err(
            ParseIssue(
                line=line,
                kind="malformed_number",
                detail=f"field {field!r} value {text!r} is not a number",
            )
        )


# frob:doc docs/modules/py-harness.md#models-cam
def parse_toolpath(text: str, dialect: Dialect) -> Toolpath:
    """Parse raw plan text into a :class:`Toolpath`.

    Total and non-raising by construction: malformed lines and
    canned-cycle rejections become :class:`ParseIssue` entries citing
    their line rather than exceptions (charter D2/D3). Lightly fuzzed
    in `tests/harness/test_cam_parse.py` -- arbitrary bytes reach this
    function only as ``str`` (the caller decodes with
    ``errors="replace"``), and every branch below is total over any
    string input.
    """
    moves: list[Move] = []
    tool_changes: list[ToolChange] = []
    issues: list[ParseIssue] = []
    active_tool: int | None = None
    # Running position carries forward (G-code omits unchanged axes);
    # `None` until the first move sets it, so an omitted axis on line 1
    # stays `None` rather than fabricating a phantom zero.
    pos: dict[str, float | None] = dict.fromkeys(_AXIS_LETTERS)
    modal_motion: MoveKind | None = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        words = _words(line)
        if not words:
            # A non-blank line with no recognizable G/M/axis words: flag
            # it rather than silently ignoring unknown syntax.
            issues.append(
                ParseIssue(line=lineno, kind="unrecognized_line", detail=raw_line[:120])
            )
            continue

        codes = {letter: value for letter, value in words if letter in ("G", "M", "T")}
        motion_kind: MoveKind | None = None
        skip_line = False

        if "G" in codes:
            gnum = codes["G"].split(".")[0].lstrip("0") or "0"
            if gnum in _CANNED_CYCLE_NUMS:
                issues.append(
                    ParseIssue(
                        line=lineno,
                        kind="canned_cycle_rejected",
                        detail=f"canned cycle G{codes['G']} is not supported in v1",
                    )
                )
                skip_line = True
            elif gnum == "0":
                motion_kind = MoveKind.rapid
            elif gnum == "1":
                motion_kind = MoveKind.linear
            elif gnum == "2":
                motion_kind = MoveKind.arc_cw
            elif gnum == "3":
                motion_kind = MoveKind.arc_ccw
            elif gnum == "91":
                issues.append(
                    ParseIssue(
                        line=lineno,
                        kind="incremental_mode_unsupported",
                        detail="G91 incremental positioning is a declared v1 exclusion",
                    )
                )
                skip_line = True
            # else: an accepted mode setter (G90/G17-19/G20/G21/G94/...)
            # or an unrecognized G-code we neither reject nor model.

        if skip_line:
            continue

        # `T<n>` is read BEFORE `M6` on this same line: a real plan's
        # "T1 M6" tool-change couplet names the tool and changes to it
        # in one line, so the T-word must be live before the M6 check
        # asks "which tool is active".
        if "T" in codes:
            parsed_tool = _to_float(codes["T"], line=lineno, field="T")
            if parsed_tool.is_err:
                issues.append(parsed_tool.danger_err)
            else:
                active_tool = int(parsed_tool.danger_ok)

        if "M" in codes and codes["M"].lstrip("0") in {"6", ""}:
            if active_tool is None:
                issues.append(
                    ParseIssue(
                        line=lineno,
                        kind="tool_change_missing_tool",
                        detail="M6 with no preceding T<n> word",
                    )
                )
            else:
                tool_changes.append(ToolChange(line=lineno, tool=active_tool))

        if motion_kind is not None:
            modal_motion = motion_kind
        elif (
            any(letter in ("X", "Y", "Z") for letter, _ in words)
            and modal_motion is not None
        ):
            motion_kind = modal_motion

        axis_updates: dict[str, float] = {}
        feed: float | None = None
        extrude: float | None = None
        malformed = False
        for letter, value in words:
            if letter in _AXIS_LETTERS:
                parsed = _to_float(value, line=lineno, field=letter)
                if parsed.is_err:
                    issues.append(parsed.danger_err)
                    malformed = True
                    continue
                axis_updates[letter] = parsed.danger_ok
            elif letter == "F":
                parsed = _to_float(value, line=lineno, field="F")
                if parsed.is_err:
                    issues.append(parsed.danger_err)
                    malformed = True
                    continue
                feed = parsed.danger_ok
            elif letter == "E":
                parsed = _to_float(value, line=lineno, field="E")
                if parsed.is_err:
                    issues.append(parsed.danger_err)
                    malformed = True
                    continue
                extrude = parsed.danger_ok

        if malformed:
            continue

        if axis_updates:
            for axis, value in axis_updates.items():
                pos[axis] = value

        if motion_kind is not None and (
            axis_updates or feed is not None or extrude is not None
        ):
            moves.append(
                Move(
                    line=lineno,
                    kind=motion_kind,
                    x=pos["X"],
                    y=pos["Y"],
                    z=pos["Z"],
                    feed=feed,
                    extrude=extrude,
                    tool=active_tool,
                )
            )

    _log.info(
        "cam.parse: dialect=%s lines=%d moves=%d tool_changes=%d issues=%d",
        dialect.value,
        len(text.splitlines()),
        len(moves),
        len(tool_changes),
        len(issues),
    )
    return Toolpath(
        dialect=dialect,
        moves=tuple(moves),
        tool_changes=tuple(tool_changes),
        issues=tuple(issues),
    )


# frob:doc docs/modules/py-harness.md#models-cam
# frob:waive TEST001 reason="CAM helper, tested transitively via cam model tests"
def decode_plan_bytes(raw: bytes) -> str:
    """Decode plan bytes for parsing -- never raises (fuzz-safety root).

    ``errors="replace"`` turns any byte sequence into SOME string; the
    parser above is total over strings, so this is the one place
    bytes-level fuzzing needs to be proven safe.
    """
    return raw.decode("utf-8", errors="replace")


# frob:doc docs/modules/py-harness.md#models-cam
def parse_plan(raw: bytes, dialect: Dialect) -> Toolpath:
    """Bytes-in, IR-out: the whole `cam.parse` model's pure arithmetic."""
    return parse_toolpath(decode_plan_bytes(raw), dialect)


# frob:doc docs/modules/py-harness.md#models-cam
# frob:waive TEST001 reason="CAM helper, tested transitively via cam model tests"
# frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
def line_citations(issues: Sequence[ParseIssue]) -> str:
    """Render issues as a stable, human-readable citation string."""
    return "; ".join(f"line {i.line}: {i.kind} ({i.detail})" for i in issues)
