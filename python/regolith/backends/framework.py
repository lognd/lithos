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

from regolith._schema.models import (
    ContractGraphPayload,
    Evidence,
    FlownetPayload,
    FramePayload,
    HarnessPayload,
    OptimizationTrace,
    RealizedGeometry,
    RealizedLayout,
)
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
        flownets: Mapping[str, FlownetPayload] = {},  # noqa: B006 (frozen inputs)
        frames: Mapping[str, FramePayload] = {},  # noqa: B006 (frozen inputs)
        harnesses: Mapping[str, HarnessPayload] = {},  # noqa: B006 (frozen inputs)
        contract_graph: ContractGraphPayload | None = None,
        opt_traces: Mapping[str, OptimizationTrace] = {},  # noqa: B006 (frozen inputs)
    ) -> None:
        """Bind the inputs a backend may ever read.

        ``evidence``/``geometry``/``layouts``/``flownets``/``frames``/
        ``harnesses``/``opt_traces`` are keyed by subject (the same
        subject strings the orchestrator's discharge/staged-build
        layers already use), never re-derived here. ``flownets``
        (WO-50) is the fluid P&ID drawing producer's input; ``frames``
        (WO-50 civil leg, calcite/03 sec. 4) is the civil plan/section
        drawing producer's input; ``harnesses`` (WO-58 deliverable 1,
        D99's `HarnessPayload`) is the `diagram.elec_blocks` producer's
        input. ``contract_graph`` (WO-61 deliverable 3) is the
        `diagram.contract_graph` producer's input -- a SINGLE value,
        not a per-subject map, because `regolith-lower` emits exactly
        one `ContractGraphPayload` per build
        (`BuildPayload.contract_graph`, D165/D167) rather than one per
        named subject the way flownets/frames/harnesses are (each of
        those has its own per-file elaboration seam; the contract
        graph is the whole build's L2 surface). ``opt_traces`` (WO-58
        deliverable 4, gated on WO-55) is the `diagram.opt_trace`
        producer's input: an `OptimizationTrace` is NOT part of
        `BuildPayload` (it is `optimize`'s own T2-tier output, AD-30)
        so, unlike the other maps, it has no
        `report.final.payload_json`-derived source in `ship` -- a
        caller supplies it explicitly, keyed by whatever subject name
        the caller chooses to label the run.
        """
        self.lockfile = lockfile
        self.evidence = evidence
        self.geometry = geometry
        self.layouts = layouts
        self.native = native
        self.flownets = flownets
        self.frames = frames
        self.harnesses = harnesses
        self.contract_graph = contract_graph
        self.opt_traces = opt_traces


class Backend(Protocol):
    """A manufacturing backend: ``BackendInputs`` in, ``OutputFile``s out."""

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Serialize ``inputs`` into this backend's package files (Result-total)."""
        ...
