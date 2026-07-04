"""Typed facade over the ``rockhead._core`` extension (AD-4).

This module is the ONE door to the compiler core: no other module may
import ``rockhead._core`` (enforced by a grep in ``make check``). Every
Python-facing API returns a typani ``Result`` per house style; only
``CoreBug`` (an unrecoverable programmer bug from the boundary) ever
propagates as an exception.

WO-01 exposes just the smoke-test surface; WO-18 grows the real
``check``/``compile`` facade and the schema-version assertion.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Result

from rockhead import _core
from rockhead.errors import CoreFailure

# Bridge Rust `tracing`/`log` records into Python `logging` exactly once
# (AD-8). Done at import of the single door so every consumer inherits it.
_core.init_logging()


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


def check(paths: tuple[str, ...]) -> Result[BuildOutcome, CoreFailure]:
    """Run the static ``check`` pipeline over ``paths`` through the core.

    The ONE door: opens a ``_core.CoreSession``, calls ``check()`` under
    ``allow_threads``, and converts a ``CoreError`` into an ``Err`` value
    (``CoreBug`` alone propagates). A failing check is an ``Ok`` outcome
    with ``ok=False`` -- claims-as-data (AD-7), not an error.
    """
    raise NotImplementedError(
        "STUB WO-18: open _core.CoreSession(paths); check(); marshal to BuildOutcome"
    )
