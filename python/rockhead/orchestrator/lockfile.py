"""The lockfile: the reviewable pin surface (WO-14).

Spec: substrate/09 sec. 2-3; substrate/03 sec. 2. Every non-literal
resolution lands here with its cause, so a number that changes in review
names why it changed. The text format is line-oriented, sorted, ASCII,
and bit-reproducible: identical inputs produce byte-identical output.
Resolutions come from the Rust core (WO-04 ``Resolution`` via the WO-18
facade); this module authors the TOML/text surface only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Result

from rockhead.errors import LockfileError


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


def render(lockfile: Lockfile) -> str:
    """Render a lockfile to its canonical text form.

    Deterministic (AD-6): sections and rows in a fixed sorted order, ASCII
    only, so identical inputs give byte-identical output.
    """
    raise NotImplementedError(
        "STUB WO-14: sorted ASCII diff-friendly render; cause column per substrate/03"
    )


def parse(text: str) -> Result[Lockfile, LockfileError]:
    """Parse a lockfile's text form back into the model."""
    raise NotImplementedError("STUB WO-14: line-oriented parse back into Lockfile")
