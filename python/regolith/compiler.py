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


def _map_core_error(exc: BaseException) -> CoreFailure:
    """Convert a raised ``_core.CoreError`` into the Python error value."""
    text = str(exc)
    match = _CORE_ERROR_KIND.match(text)
    kind = match.group(1) if match else "unknown"
    return CoreFailure(kind=kind, message=text, path=None)


def core_version() -> str:
    """Return the compiler core version (the Rust->Python smoke test)."""
    return _core.core_version()


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


def check(paths: tuple[str, ...]) -> Result[BuildOutcome, CoreFailure]:
    """Run the static ``check`` pipeline over ``paths`` through the core.

    The ONE door: opens a ``_core.CoreSession``, calls ``check()`` under
    ``allow_threads``, and converts a ``CoreError`` into an ``Err`` value
    (``CoreBug`` alone propagates). A failing check is an ``Ok`` outcome
    with ``ok=False`` -- claims-as-data (AD-7), not an error.
    """
    return _run(paths, "check")


def compile(
    paths: tuple[str, ...],
    registry_version: str = MODEL_REGISTRY_VERSION,
) -> Result[BuildOutcome, CoreFailure]:
    """Run the full ``compile`` pipeline over ``paths`` through the core.

    Same marshalling contract as :func:`check`. ``registry_version`` (the
    harness model-registry version, AD-1) is folded into every evidence-
    cache key so a model upgrade forces re-verification instead of reusing
    stale cached evidence (BE-1/INV-1); it defaults to the harness's
    declared :data:`MODEL_REGISTRY_VERSION`.
    """
    return _run(paths, "compile", registry_version)


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
