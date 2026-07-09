"""Typed facade over the ``regolith._core`` extension (AD-4).

This module is the ONE door to the compiler core: no other module may
import ``regolith._core`` (enforced by a grep in ``make check``). Every
Python-facing API returns a typani ``Result`` per house style; only
``CoreBug`` (an unrecoverable programmer bug from the boundary) ever
propagates as an exception.

WO-01 exposes just the smoke-test surface; WO-18 grows the real
``check``/``compile`` facade and the schema-version assertion.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import _core
from regolith._schema import SCHEMA_VERSION
from regolith.errors import CoreFailure
from regolith.harness import MODEL_REGISTRY_VERSION

# Bridge Rust `tracing`/`log` records into Python `logging` exactly once
# (AD-8). Done at import of the single door so every consumer inherits it.
_core.init_logging()

# Belt over the single-wheel suspenders (AD-5): the wheel bundles both
# halves so this can never actually mismatch, but a build-tooling bug
# (stale extension, mixed install) must fail loudly at import, not with
# a silent payload-parsing error deep in a build.
_core_schema_version = _core.schema_version()
if _core_schema_version != SCHEMA_VERSION:
    raise RuntimeError(
        f"schema version mismatch: regolith._core speaks "
        f"{_core_schema_version}, regolith._schema was generated for "
        f"{SCHEMA_VERSION} (stale extension or stale generated models; "
        "rerun `make schema` and rebuild)"
    )

# Matches the `Debug` rendering of a Rust `CoreError` variant, e.g.
# `Io { path: "x", message: "..." }` -> kind "Io". Falls back to the
# whole text when the shape doesn't match (still surfaced verbatim).
_CORE_ERROR_KIND = re.compile(r"^(\w+)")

_log = logging.getLogger(__name__)


def _map_core_error(exc: BaseException) -> CoreFailure:
    """Convert a raised ``_core.CoreError`` into the Python error value."""
    text = str(exc)
    match = _CORE_ERROR_KIND.match(text)
    kind = match.group(1) if match else "unknown"
    return CoreFailure(kind=kind, message=text, path=None)


def core_version() -> str:
    """Return the compiler core version (the Rust->Python smoke test)."""
    return _core.core_version()


class RealizedInput(BaseModel):
    """One caller-resolved realized-domain IR (WO-42 deliverable 3,
    AD-25/D128): the orchestrator has already resolved ``digest`` against
    the WO-30 content store into ``payload_bytes`` -- this facade does no
    IO of its own, only marshals the resolved content across the ONE
    coarse FFI crossing (AD-4). ``kind`` is a D96 payload kind (e.g.
    ``"geometry.realized"``); ``subject`` is the part/block the IR was
    realized for (matched against a flownet edge's ``from=`` ref).
    """

    model_config = ConfigDict(frozen=True)

    digest: str
    kind: str
    subject: str
    payload_bytes: bytes


def _realized_input_tuples(
    realized_inputs: tuple[RealizedInput, ...],
) -> list[tuple[str, str, str, bytes]]:
    """Marshal typed [`RealizedInput`]s into the raw
    ``(digest, kind, subject, bytes)`` tuples the `_core` extension
    speaks (the one door's job: no other module touches this shape)."""
    return [
        (ri.digest, ri.kind, ri.subject, ri.payload_bytes) for ri in realized_inputs
    ]


class BuildOutcome(BaseModel):
    """The Python-side envelope over a Rust ``BuildOutput`` (AD-4).

    A transport wrapper, not a mirror of a core domain type: ``ok`` is the
    verdict, ``rendered`` is the ONE renderer's text (printed verbatim,
    never re-rendered), and ``payload_json`` is the structured bytes that
    parse into the generated ``_schema`` models on demand (WO-18).
    """

    model_config = ConfigDict(frozen=True)

    ok: bool
    rendered: str
    payload_json: bytes


def _run(
    paths: tuple[str, ...], method: str, *args: object
) -> Result[BuildOutcome, CoreFailure]:
    """Shared body for ``check``/``compile``: open a session, call
    ``method`` on it (forwarding ``args``), and marshal the result (or the
    infra error)."""
    try:
        session = _core.CoreSession(list(paths))
        output = getattr(session, method)(*args)
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))
    return Ok(
        BuildOutcome(
            ok=output.ok(),
            rendered=output.rendered(ansi=False),
            payload_json=output.payload_json(),
        )
    )


def check(
    paths: tuple[str, ...],
    realized_inputs: tuple[RealizedInput, ...] = (),
) -> Result[BuildOutcome, CoreFailure]:
    """Run the static ``check`` pipeline over ``paths`` through the core.

    The ONE door: opens a ``_core.CoreSession``, calls ``check()`` under
    ``allow_threads``, and converts a ``CoreError`` into an ``Err`` value
    (``CoreBug`` alone propagates). A failing check is an ``Ok`` outcome
    with ``ok=False`` -- claims-as-data (AD-7), not an error.

    ``realized_inputs`` (WO-42 deliverable 3, AD-25/D128) is the caller-
    resolved realized-domain IR channel; empty by default (the pre-
    realization placeholder path -- every dependent obligation stays
    honestly indeterminate, naming the missing IR).
    """
    return _run(paths, "check", _realized_input_tuples(realized_inputs))


def compile(
    paths: tuple[str, ...],
    registry_version: str = MODEL_REGISTRY_VERSION,
    realized_inputs: tuple[RealizedInput, ...] = (),
) -> Result[BuildOutcome, CoreFailure]:
    """Run the full ``compile`` pipeline over ``paths`` through the core.

    Same marshalling contract as :func:`check`. ``registry_version`` (the
    harness model-registry version, AD-1) is folded into every evidence-
    cache key so a model upgrade forces re-verification instead of reusing
    stale cached evidence (BE-1/INV-1); it defaults to the harness's
    declared :data:`MODEL_REGISTRY_VERSION`. ``realized_inputs`` is the
    same channel :func:`check` takes.
    """
    return _run(
        paths, "compile", registry_version, _realized_input_tuples(realized_inputs)
    )


def format(text: str) -> str:
    """Format source ``text`` into its canonical spelling (never fails;
    an unparseable input still normalizes -- error recovery, AD-3)."""
    return _core.format(text)


def debug_dump(stage: str, path: str) -> Result[str, CoreFailure]:
    """Dump an intermediate pipeline stage of ``path``'s source as text."""
    try:
        return Ok(_core.debug_dump(stage, path))
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))


def debug_ir(
    paths: tuple[str, ...],
    realized_inputs: tuple[RealizedInput, ...] = (),
) -> Result[str, CoreFailure]:
    """Dump the ``regolith debug ir`` report over ``paths`` (WO-42
    deliverable 3, AD-25 inspectability): the compiler's own IR-stage
    summary plus a section listing every realized-domain IR supplied to
    the build (kind, digest, subject) -- ``(none supplied)`` when
    ``realized_inputs`` is empty, the D128 placeholder path.
    """
    try:
        return Ok(_core.debug_ir(list(paths), _realized_input_tuples(realized_inputs)))
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))


def doc_extract(path: str) -> Result[str, CoreFailure]:
    """Extract ``path``'s public-surface doc model as JSON (WO-41).

    One entry per top-level declaration: kind, name, leading ``#`` doc
    comment (verbatim, ``None`` when absent), fields, ``require`` claim
    groups, and ``budget`` statements. The ONE Rust accessor `regolith
    doc` walks (``regolith.docgen`` parses the JSON into typed models).
    """
    try:
        return Ok(_core.doc_extract(path))
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))


def extensions() -> tuple[tuple[str, str], ...]:
    """Every recognized ``(extension, language)`` pair (ground rule 6 /
    AD-14) -- the ONE registry, read through the FFI so no other layer
    (``quarry new`` included) ever hard-codes an extension string."""
    return tuple(_core.extensions())


class ElecNetViolation(BaseModel):
    """One net's elec-discipline single-driver violation (AD-23 D4).

    Deliberately domain-agnostic at this facade layer (net name, driver
    labels, rendered message) -- the realizer-shaped
    ``ArbitrationError`` is assembled by the caller
    (``regolith.realizer.elec.netlist``), not here; this module speaks
    only to the core, never to a specific realizer's error vocabulary.
    """

    model_config = ConfigDict(frozen=True)

    net: str
    drivers: tuple[str, ...]
    message: str


def check_elec_single_driver(
    nets_json: str,
) -> Result[ElecNetViolation | None, CoreFailure]:
    """Run the elec net discipline's single-driver check (AD-23 D4).

    ``nets_json`` is a JSON array of ``NetlistModel.nets``-shaped nets
    (``{"name","pins":[{"component","pin","is_driver"}]}``); the caller
    (``regolith.realizer.elec.netlist``) owns that serialization. Moved
    from a hand-written Python ledger into the shared Rust
    ``regolith-sem::net_core`` (cuprite/03 sec. 2, fluorite/02 sec. 4)
    per AD-23 -- one net core, not two parallel ledgers. Returns
    ``Ok(None)`` when every net is clean, ``Ok(violation)`` naming the
    first offending net (fail-fast, byte-identical to the retired
    Python behavior), or ``Err`` only for a malformed ``nets_json``
    (an infrastructure/programmer-facing failure, never a design
    error).
    """
    try:
        raw = _core.check_elec_single_driver(nets_json)
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))
    payload = json.loads(raw)
    if payload["ok"]:
        return Ok(None)
    return Ok(
        ElecNetViolation(
            net=payload["net"],
            drivers=tuple(payload["drivers"]),
            message=payload["message"],
        )
    )


class RuleExpectCase(BaseModel):
    """One `expect:` fixture case's run outcome (WO-28 `rules test`)."""

    model_config = ConfigDict(frozen=True)

    rule: str
    expected: str
    fixture: str
    outcome: str
    detail: str | None = None


class RulesTestReport(BaseModel):
    """One pack's `rules test` report: case outcomes + lint warnings."""

    model_config = ConfigDict(frozen=True)

    pack: str
    ok: bool
    cases: tuple[RuleExpectCase, ...]
    lints: tuple[str, ...]


class RulesTryMatch(BaseModel):
    """One `rules try` match: rule x entity with verdict and margin."""

    model_config = ConfigDict(frozen=True)

    rule: str
    subject: str
    entity: str
    verdict: str
    detail: str
    margin: float | None = None
    near_miss: bool


class RulesTryReport(BaseModel):
    """A whole `rules try` run: the pack, the design, every match."""

    model_config = ConfigDict(frozen=True)

    pack: str
    design: tuple[str, ...]
    matches: tuple[RulesTryMatch, ...]


def rules_test(paths: tuple[str, ...]) -> Result[tuple[RulesTestReport, ...], CoreFailure]:
    """Run every pack's `expect:` fixtures in ``paths`` (WO-28 D-H).

    A failing fixture is DATA in the returned reports (``ok=False``),
    never an ``Err`` -- only infrastructure failures (unreadable path)
    map to ``CoreFailure``.
    """
    _log.info("rules test over %d path(s)", len(paths))
    try:
        raw = _core.rules_test(list(paths))
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))
    reports = tuple(RulesTestReport.model_validate(entry) for entry in json.loads(raw))
    _log.info(
        "rules test complete: %d pack(s), ok=%s",
        len(reports),
        all(r.ok for r in reports),
    )
    return Ok(reports)


def rules_try(pack: str, design: str) -> Result[RulesTryReport, CoreFailure]:
    """Run ONE pack against one design file (WO-28 D-H), no build.

    Attachment is forced (that is `try`'s point); every match reports
    its verdict, evaluated detail, and near-miss margin.
    """
    _log.info("rules try: pack=%s design=%s", pack, design)
    try:
        raw = _core.rules_try(pack, design)
    except _core.CoreError as exc:
        return Err(_map_core_error(exc))
    report = RulesTryReport.model_validate(json.loads(raw))
    _log.info("rules try complete: %d match(es)", len(report.matches))
    return Ok(report)
