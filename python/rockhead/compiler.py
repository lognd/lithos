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

from rockhead import _core

# Bridge Rust `tracing`/`log` records into Python `logging` exactly once
# (AD-8). Done at import of the single door so every consumer inherits it.
_core.init_logging()


def core_version() -> str:
    """Return the compiler core version (the Rust->Python smoke test)."""
    return _core.core_version()
