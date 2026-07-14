"""The engineer-injection override ledger (AD-40, charter 42 sec. 2, WO-129A).

ONE home for the ``overrides.toml`` format: a diffable, ASCII,
source-controlled ledger of engineer injections against declared design
inputs and choices. Charter 42's load-bearing rule (sec. 1) is that an
override changes an INPUT or a CHOICE, never a verdict, an evidence
value, or a margin -- this module owns only the DATA shape and its
content hash; the D246 claims/evidence boundary (what a target may
legitimately name) lives in :mod:`regolith.orchestrator.override_resolve`,
and the value-source integration (``cause: engineer_override(...)``)
lives in :mod:`regolith.orchestrator.override_apply`.

Text shape (sorted by target, ASCII, deterministic -- AD-6/INV-10)::

    # overrides.toml
    [[override]]
    target = "printer_k1.Carriage.rail_span"
    value = "240mm"
    mode = "pin"
    author = "logan"
    reason = "matches the extrusion we already stock"

``author`` and ``reason`` are REQUIRED on every entry -- an override
missing either is refused (E1001, WO-131's reserved code for "unexplained
override"; the constant is not yet on this branch, see the module-level
TODO), never given a silent default. The rendered ledger's content hash
enters the build's inputs (:func:`ledger_content_hash`) so a package
built with overrides is reproducible and one built without them is
byte-different (AD-6/INV-10).
"""

from __future__ import annotations

import tomllib
from enum import StrEnum

import blake3
from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# TODO(WO-131): once the E10xx injection/override diagnostic family lands
# on this branch, replace this bare string with the generated constant
# (WO-131 reserved E1001 for exactly this case: an override missing
# author/reason). Using the code value directly per the WO-129A dispatch
# note -- do not invent a second code registry.
E1001_UNEXPLAINED_OVERRIDE = "E1001"

_LEDGER_FILENAME = "overrides.toml"


class OverrideMode(StrEnum):
    """Whether an override REMOVES its slot from an optimizer search
    (``pin``, the default -- "optimization removal", D243.3) or keeps it
    searchable from that starting point (``seed``). The actual optimizer
    domain-removal wiring is WO-129B; this module only carries the mode
    a caller declared."""

    pin = "pin"
    seed = "seed"


class OverrideEntry(BaseModel):
    """One audited engineer injection: a resolvable target, a value, a
    mode, and the REQUIRED author + reason (charter 42 sec. 2).

    ``target`` is a dotted ``design.subject.slot`` path resolved against
    the same surfaces the census and optimizer read
    (:mod:`regolith.orchestrator.override_resolve`). ``value`` is the
    injected literal (a quantity string, a record ref, or a select
    choice) -- this module does not interpret it; interpretation is the
    consumer's (e.g. a quantity parse for a bounded slot).
    """

    model_config = ConfigDict(frozen=True)

    target: str
    value: str
    mode: OverrideMode = OverrideMode.pin
    author: str
    reason: str


class OverrideLedger(BaseModel):
    """The full ``overrides.toml``: an unordered set of entries, rendered
    in sorted-target order for determinism (AD-6)."""

    model_config = ConfigDict(frozen=True)

    overrides: tuple[OverrideEntry, ...] = ()

    def entry_for(self, target: str) -> OverrideEntry | None:
        """The entry naming ``target``, if any (targets are unique by
        construction -- :func:`parse`/:func:`set_override` enforce it)."""
        for entry in self.overrides:
            if entry.target == target:
                return entry
        return None


def _render_entry(entry: OverrideEntry) -> str:
    """Render one ``[[override]]`` table in the canonical field order."""
    lines = [
        "[[override]]",
        f'target = "{entry.target}"',
        f'value = "{entry.value}"',
        f'mode = "{entry.mode.value}"',
        f'author = "{entry.author}"',
        f'reason = "{entry.reason}"',
    ]
    return "\n".join(lines)


def render(ledger: OverrideLedger) -> str:
    """Render ``ledger`` to its canonical ASCII text form.

    Deterministic (AD-6): entries in sorted-target order, one blank line
    between tables -- identical inputs give byte-identical output, so the
    ledger's content hash (:func:`ledger_content_hash`) is a stable build
    input (INV-10).
    """
    entries = sorted(ledger.overrides, key=lambda e: e.target)
    blocks = [_render_entry(e) for e in entries]
    text = "\n\n".join(blocks)
    return text + "\n" if text else ""


def require_explained(
    target: str, author: str | None, reason: str | None
) -> Result[None, OrchestratorError]:
    """The ONE E1001 check: ``author``/``reason`` non-empty strings.
    Shared by :func:`parse` (the ledger-file path) and the CLI's
    ``override set`` (the direct-construction path) so a caller cannot
    bypass the refusal by skipping TOML parsing (D243.2/D221's "an
    unexplained override is refused" spirit)."""
    missing = [
        name
        for name, value in (("author", author), ("reason", reason))
        if not isinstance(value, str) or not value.strip()
    ]
    if missing:
        return Err(
            OrchestratorError(
                kind=E1001_UNEXPLAINED_OVERRIDE,
                message=(
                    f"override target={target!r} is missing required field(s) "
                    f"{missing}: an unexplained override is refused, never "
                    "given a silent default -- add author and reason"
                ),
            )
        )
    return Ok(None)


def _entry_from_table(
    table: dict[str, object],
) -> Result[OverrideEntry, OrchestratorError]:
    """Build one ``OverrideEntry`` from a parsed TOML table, refusing a
    missing/empty ``author`` or ``reason`` with E1001 (never a default --
    D243.2/D221's "an unexplained override is refused" spirit)."""
    target = table.get("target")
    author = table.get("author")
    reason = table.get("reason")
    explained = require_explained(
        str(target) if target is not None else "",
        author if isinstance(author, str) else None,
        reason if isinstance(reason, str) else None,
    )
    if explained.is_err:
        return Err(explained.danger_err)
    try:
        entry = OverrideEntry.model_validate(table)
    except ValidationError as exc:
        return Err(
            OrchestratorError(
                kind="malformed_override",
                message=f"malformed [[override]] table: {exc}",
            )
        )
    _log.debug("parsed override: target=%s mode=%s", entry.target, entry.mode.value)
    return Ok(entry)


def parse(text: str) -> Result[OverrideLedger, OrchestratorError]:
    """Parse ``overrides.toml`` text into an :class:`OverrideLedger`.

    Every ``[[override]]`` table is validated independently; the FIRST
    entry missing author/reason (or otherwise malformed) is returned as
    an ``Err`` (never a partially-loaded ledger -- a bad ledger is a
    build-blocking data error, not a warning)."""
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return Err(
            OrchestratorError(kind="malformed_toml", message=f"malformed TOML: {exc}")
        )
    raw_entries = doc.get("override", [])
    if not isinstance(raw_entries, list):
        return Err(
            OrchestratorError(
                kind="malformed_ledger",
                message="'override' key must be an array of tables ([[override]])",
            )
        )
    entries: list[OverrideEntry] = []
    seen_targets: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            return Err(
                OrchestratorError(
                    kind="malformed_override", message=f"not a table: {raw!r}"
                )
            )
        result = _entry_from_table(raw)
        if result.is_err:
            return Err(result.danger_err)
        entry = result.danger_ok
        if entry.target in seen_targets:
            return Err(
                OrchestratorError(
                    kind="duplicate_override_target",
                    message=f"target {entry.target!r} appears more than once "
                    "in the ledger",
                )
            )
        seen_targets.add(entry.target)
        entries.append(entry)
    _log.info("parsed override ledger: %d entr(ies)", len(entries))
    return Ok(OverrideLedger(overrides=tuple(entries)))


def ledger_content_hash(ledger: OverrideLedger) -> str:
    """The ``blake3:``-prefixed content hash of ``ledger``'s CANONICAL
    rendered text (the same digest convention as
    :func:`regolith.orchestrator.payload_store.payload_digest`).

    This is the hash charter 42 sec. 2 requires to enter the build's
    inputs: an empty ledger and a populated one hash differently, and two
    ledgers with the same entries in a different file order hash the
    SAME (render is sorted first) -- so the digest reflects the override
    CONTENT, not incidental file layout (AD-6/INV-10)."""
    return "blake3:" + blake3.blake3(render(ledger).encode("ascii")).hexdigest()


def read_ledger(project_root: str) -> Result[OverrideLedger, OrchestratorError]:
    """Read ``<project_root>/overrides.toml``, or an EMPTY ledger when no
    file exists yet (a project with no overrides is not an error -- most
    projects never inject anything)."""
    import os

    path = os.path.join(project_root, _LEDGER_FILENAME)
    if not os.path.isfile(path):
        return Ok(OverrideLedger())
    try:
        with open(path, encoding="ascii") as handle:
            text = handle.read()
    except OSError as exc:
        return Err(
            OrchestratorError(
                kind="ledger_read_failed", message=f"cannot read {path}: {exc}"
            )
        )
    return parse(text)


def write_ledger(
    project_root: str, ledger: OverrideLedger
) -> Result[str, OrchestratorError]:
    """Write ``ledger``'s canonical text to ``<project_root>/overrides.toml``
    (the ONE writer surface is the CLI, :mod:`regolith.cli.app`'s
    ``override`` command group -- this function is its implementation,
    never called directly by another producer)."""
    import os

    path = os.path.join(project_root, _LEDGER_FILENAME)
    try:
        with open(path, "w", encoding="ascii") as handle:
            handle.write(render(ledger))
    except OSError as exc:
        return Err(
            OrchestratorError(
                kind="ledger_write_failed", message=f"cannot write {path}: {exc}"
            )
        )
    _log.info("wrote override ledger: %s (%d entries)", path, len(ledger.overrides))
    return Ok(path)
