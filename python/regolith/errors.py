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


class MagnetiteError(BaseModel):
    """A package/registry resolution failure (WO-16)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


class LockfileError(BaseModel):
    """A lockfile read/write/parse failure (WO-14)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


class OrchestratorError(BaseModel):
    """A build-orchestration failure surfaced as a value (AD-1 / house style).

    Covers evidence-cache IO, obligation translation, and release-gate
    refusals -- everything the orchestrator layer must let a caller handle
    rather than raise.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


class DocError(BaseModel):
    """A ``regolith doc``/``magnetite new`` scaffolding failure (WO-41)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


class BackendError(BaseModel):
    """A manufacturing-backend/ship failure (WO-25, L6).

    Covers a missing realized-domain IR or native artifact, an
    unavailable vendor tool (kicad-cli/pcbnew, the WO-24/35 gate
    discipline reused here), a release-gate refusal, and manifest
    sign/verify failures -- every backend/ship failure a caller must
    handle rather than raise.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str
