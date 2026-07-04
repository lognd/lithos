"""The lockfile: the reviewable pin surface (WO-14).

Spec: substrate/09 sec. 2-3; substrate/03 sec. 2. Every non-literal
resolution lands here with its cause, so a number that changes in review
names why it changed. The text format is line-oriented, sorted, ASCII,
and bit-reproducible: identical inputs produce byte-identical output.
Resolutions come from the Rust core (WO-04 ``Resolution`` via the WO-18
facade); this module authors the TOML/text surface only.

Text shape (one lockfile, sections in sorted-name order, rows in
sorted-slot order within a section, record pins in sorted-key order):

    # rockhead.lock tool_version=0.1.0
    [section ""]
    flange.radius = 2.4mm         cause: dfm(sheet.min_bend_radius)
    seat.runout = +-0.015         cause: budget(mesh_alignment)
                                   policy: prefer(low_cost)
    pin jlc.pcb@2.3.0 = sha256:aa10f3

    [section "flight"]
    net.vdd.width = 0.3mm         cause: drc(jlc_2l.current_capacity)

Each row is ``<slot> = <value>         cause: <cause>`` with an optional
trailing ``         policy: <note>``; the double-space gap keeps the
columns diff-stable without needing fixed-width padding. A ``pin`` line
is ``pin <package>@<version> = <revision hash>``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from rockhead.errors import LockfileError
from rockhead.logging_setup import get_logger

_log = get_logger(__name__)

_HEADER_PREFIX = "# rockhead.lock tool_version="
_SECTION_PREFIX = "[section "
_SECTION_SUFFIX = "]"
_PIN_PREFIX = "pin "
_COL_GAP = "         "  # 9 spaces: fixed, ASCII-stable column gap


class LockRow(BaseModel):
    """One resolved pin: a slot, its value, and its resolving cause.

    Renders as substrate/03 sec. 2's shape::

        flange.radius = 2.4mm         cause: dfm(sheet.min_bend_radius)
    """

    model_config = ConfigDict(frozen=True)

    slot: str
    value: str
    cause: str  # rendered cause, e.g. "dfm(sheet.min_bend_radius)"
    policy_note: str | None = None  # policy: prefer(...) when decisive


class LockSection(BaseModel):
    """A per-target or per-variant section of rows plus record pins."""

    model_config = ConfigDict(frozen=True)

    name: str  # "" for the base section; target/variant name otherwise
    rows: tuple[LockRow, ...] = ()
    record_pins: tuple[tuple[str, str], ...] = ()  # (package@version, revision hash)


class Lockfile(BaseModel):
    """The full lockfile: tool/registry versions plus ordered sections."""

    model_config = ConfigDict(frozen=True)

    tool_version: str
    sections: tuple[LockSection, ...] = ()


def _render_row(row: LockRow) -> str:
    """Render one row: slot = value, cause, and an optional policy note."""
    line = f"{row.slot} = {row.value}{_COL_GAP}cause: {row.cause}"
    if row.policy_note is not None:
        line += f"{_COL_GAP}policy: {row.policy_note}"
    return line


def _render_pin(pin: tuple[str, str]) -> str:
    """Render one record pin: ``pin <package@version> = <revision hash>``."""
    package_version, revision_hash = pin
    return f"{_PIN_PREFIX}{package_version} = {revision_hash}"


def _render_section(section: LockSection) -> list[str]:
    """Render a section header followed by its sorted rows and pins."""
    lines = [f'{_SECTION_PREFIX}"{section.name}"{_SECTION_SUFFIX}']
    for row in sorted(section.rows, key=lambda r: r.slot):
        lines.append(_render_row(row))
    for pin in sorted(section.record_pins, key=lambda p: p[0]):
        lines.append(_render_pin(pin))
    return lines


def render(lockfile: Lockfile) -> str:
    """Render a lockfile to its canonical text form.

    Deterministic (AD-6): sections in sorted-name order, rows in
    sorted-slot order, record pins in sorted-key order, ASCII only --
    identical inputs give byte-identical output.
    """
    lines = [f"{_HEADER_PREFIX}{lockfile.tool_version}"]
    for section in sorted(lockfile.sections, key=lambda s: s.name):
        lines.append("")
        lines.extend(_render_section(section))
    text = "\n".join(lines) + "\n"
    _log.debug(
        "rendered lockfile: %d sections, tool_version=%s",
        len(lockfile.sections),
        lockfile.tool_version,
    )
    return text


def _parse_row(line: str) -> Result[LockRow, LockfileError]:
    """Parse one ``slot = value         cause: ...[         policy: ...]`` line."""
    if " = " not in line:
        return Err(
            LockfileError(kind="malformed_row", message=f"missing ' = ' in: {line!r}")
        )
    slot, rest = line.split(" = ", 1)
    if _COL_GAP + "cause: " not in rest:
        return Err(
            LockfileError(
                kind="malformed_row", message=f"missing cause column in: {line!r}"
            )
        )
    value, cause_and_rest = rest.split(_COL_GAP + "cause: ", 1)
    policy_note: str | None = None
    if _COL_GAP + "policy: " in cause_and_rest:
        cause, policy_note = cause_and_rest.split(_COL_GAP + "policy: ", 1)
    else:
        cause = cause_and_rest
    return Ok(LockRow(slot=slot, value=value, cause=cause, policy_note=policy_note))


def _parse_pin(line: str) -> Result[tuple[str, str], LockfileError]:
    """Parse one ``pin <package@version> = <revision hash>`` line."""
    body = line[len(_PIN_PREFIX) :]
    if " = " not in body:
        return Err(
            LockfileError(kind="malformed_pin", message=f"missing ' = ' in: {line!r}")
        )
    package_version, revision_hash = body.split(" = ", 1)
    return Ok((package_version, revision_hash))


def parse(text: str) -> Result[Lockfile, LockfileError]:
    """Parse a lockfile's text form back into the model."""
    lines = text.split("\n")
    if not lines or not lines[0].startswith(_HEADER_PREFIX):
        return Err(
            LockfileError(
                kind="malformed_header",
                message=f"missing lockfile header (expected {_HEADER_PREFIX!r})",
            )
        )
    tool_version = lines[0][len(_HEADER_PREFIX) :]

    sections: list[LockSection] = []
    section_name: str | None = None
    rows: list[LockRow] = []
    pins: list[tuple[str, str]] = []

    def _flush() -> None:
        if section_name is not None:
            sections.append(
                LockSection(
                    name=section_name, rows=tuple(rows), record_pins=tuple(pins)
                )
            )

    for line in lines[1:]:
        if line == "":
            continue
        if line.startswith(_SECTION_PREFIX):
            _flush()
            name = line[len(_SECTION_PREFIX) : -len(_SECTION_SUFFIX)]
            if not (name.startswith('"') and name.endswith('"')):
                return Err(
                    LockfileError(
                        kind="malformed_section",
                        message=f"malformed section header: {line!r}",
                    )
                )
            section_name = name[1:-1]
            rows = []
            pins = []
        elif line.startswith(_PIN_PREFIX):
            if section_name is None:
                return Err(
                    LockfileError(
                        kind="pin_before_section",
                        message=f"pin line before any section: {line!r}",
                    )
                )
            pin_result = _parse_pin(line)
            if pin_result.is_err:
                return Err(pin_result.danger_err)
            pins.append(pin_result.danger_ok)
        else:
            if section_name is None:
                return Err(
                    LockfileError(
                        kind="row_before_section",
                        message=f"row line before any section: {line!r}",
                    )
                )
            row_result = _parse_row(line)
            if row_result.is_err:
                return Err(row_result.danger_err)
            rows.append(row_result.danger_ok)

    _flush()
    _log.debug(
        "parsed lockfile: %d sections, tool_version=%s", len(sections), tool_version
    )
    return Ok(Lockfile(tool_version=tool_version, sections=tuple(sections)))
