"""The backend framework: the (lockfile, evidence, realized-artifacts)
input triple every manufacturing backend consumes, and nothing else.

"Backends serialize evidence; they never decide" (regolith/07 sec. 6):
a :class:`Backend` reads ONLY :class:`BackendInputs` and returns
:class:`OutputFile` records -- it never imports ``regolith.compiler`` or
``regolith._core`` (enforced by construction: grep this package, there is
no such import anywhere in it; `tests/backends/test_framework.py` pins
that as a standing check) and never invents a value ``BackendInputs``
does not already carry.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Result

from regolith._schema.models import Evidence, RealizedGeometry, RealizedLayout
from regolith.backends.artifacts import NativeArtifactStore
from regolith.errors import BackendError
from regolith.orchestrator.lockfile import Lockfile


class OutputFile(BaseModel):
    """One backend-emitted file: its package-relative path, bytes, and hash.

    Every manufacturing output is one of these -- the ship manifest
    (``regolith.backends.manifest``) is exactly the sorted list of every
    backend's ``OutputFile``s, hashed.
    """

    model_config = ConfigDict(frozen=True)

    relpath: str = Field(description="Path relative to the ship package root.")
    content: bytes = Field(description="The file's exact bytes (repr=False by size).")
    sha256: str = Field(description="SHA-256 hex digest of ``content``.")

    @classmethod
    def of(cls, relpath: str, content: bytes) -> OutputFile:
        """Construct an ``OutputFile``, computing its digest from ``content``."""
        return cls(
            relpath=relpath, content=content, sha256=hashlib.sha256(content).hexdigest()
        )

    def write_under(self, out_dir: Path) -> None:
        """Write ``content`` to ``out_dir / relpath``, creating parents."""
        path = out_dir / self.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.content)


class BackendInputs:
    """The ONE triple a backend may read: lockfile, evidence, realized
    artifacts (AD-25's IRs plus the native side-artifact store).

    Deliberately not a pydantic model: it holds a live
    :class:`NativeArtifactStore` handle (IO), not just data, mirroring
    the harness's `DischargeRequest` resolver-handle pattern
    (`payload_store.PayloadResolver`) rather than re-reading files
    itself.
    """

    def __init__(
        self,
        *,
        lockfile: Lockfile,
        evidence: Mapping[str, Evidence],
        geometry: Mapping[str, RealizedGeometry],
        layouts: Mapping[str, RealizedLayout],
        native: NativeArtifactStore,
    ) -> None:
        """Bind the four/five inputs a backend may ever read.

        ``evidence`` and ``geometry``/``layouts`` are keyed by subject
        (the same subject strings the orchestrator's discharge/staged-
        build layers already use), never re-derived here.
        """
        self.lockfile = lockfile
        self.evidence = evidence
        self.geometry = geometry
        self.layouts = layouts
        self.native = native


class Backend(Protocol):
    """A manufacturing backend: ``BackendInputs`` in, ``OutputFile``s out."""

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Serialize ``inputs`` into this backend's package files (Result-total)."""
        ...
