"""Shared Python-side error VALUES (AD-7 / house style).

Every fallible Python API returns a typani ``Result[T, E]`` whose ``E`` is
one of these frozen error models -- never a bare exception. Exceptions are
reserved for programmer bugs; ``CoreBug`` from the FFI boundary is the one
that propagates.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CoreFailure(BaseModel):
    """An infrastructure failure surfaced from the compiler core (AD-4).

    The Python image of a Rust ``CoreError`` (unreadable file, corrupt
    cache) -- distinct from a failing build, which is data in a
    ``BuildOutput``.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str
    path: str | None = None


class QuarryError(BaseModel):
    """A package/registry resolution failure (WO-16)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


class LockfileError(BaseModel):
    """A lockfile read/write/parse failure (WO-14)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str
