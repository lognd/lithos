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
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Result

from regolith._schema.models import (
    ContractGraphPayload,
    Evidence,
    FlownetPayload,
    FramePayload,
    HarnessPayload,
    ItemizedEstimate,
    OptimizationTrace,
    PowerNetPayload,
    RealizedAssembly,
    RealizedGeometry,
    RealizedLayout,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.errors import BackendError
from regolith.orchestrator.lockfile import Lockfile

if TYPE_CHECKING:
    # Annotation-only: the producers module is a CONSUMER of
    # `BackendInputs` at runtime (via backend.py); a runtime import
    # here would be the layering inversion. `RealizedBoardAssignment`
    # (WO-165) is annotation-only for a DIFFERENT reason: a runtime
    # import cycles back through `regolith.orchestrator` (which itself
    # imports `regolith.backends.artifacts`, i.e. this package) --
    # `board_assignment.py` needs `PayloadStore` from the orchestrator
    # package, so this direction must stay type-only.
    from regolith.backends.debug_taps import TapHeaderRecord, TapSet
    from regolith.backends.drawings.producers import SiSheetRow
    from regolith.backends.firmware import FirmwareArtifact
    from regolith.backends.hdl import HdlBuildProducts
    from regolith.backends.sim import SimProducts
    from regolith.realizer.elec.board_assignment import RealizedBoardAssignment
    from regolith.realizer.elec.debug_placement import TapPlacementPlan
    from regolith.realizer.mech.wire_edm import RealizedWireEdmProfile


# frob:doc docs/modules/py-backends.md#backends-framework
class ToolIdentity(BaseModel):
    """The real tool that produced an artifact (WO-160, AD-45): its name
    and a version identity string (a digest of the observed version
    output, or the version string itself when no digest scheme exists
    yet -- this WO uses the raw version string)."""

    model_config = ConfigDict(frozen=True)

    name: str
    version_digest: str


# frob:doc docs/modules/py-backends.md#backends-framework
class ArtifactProvenance(BaseModel):
    """One artifact's provenance tier (WO-160, AD-45): ``real_tool``
    (produced by an actual third-party tool invocation, ``tool``
    required), ``deterministic`` (produced by regolith's own
    deterministic logic with no external tool, ``tool`` is ``None``),
    or ``model_derived`` (WO-155 deliverable 7, T-0068: evidence a
    DISCHARGING MODEL produced -- e.g. the `sim/` family's `trace.vcd`/
    `sim_report.json`, built by running a real tool [``tool`` present]
    against an author-cited stimulus rather than a raw manufacturing
    pass over pinned geometry). Never inferred post-hoc from relpath
    naming or toolenv state -- a producer supplies this at construction
    time (``OutputFile.of``'s ``provenance`` kwarg)."""

    model_config = ConfigDict(frozen=True)

    tier: Literal["real_tool", "deterministic", "model_derived"]
    tool: ToolIdentity | None = None


# frob:doc docs/modules/py-backends.md#backends-framework
class OutputFile(BaseModel):
    """One backend-emitted file: its package-relative path, bytes, and hash.

    Every manufacturing output is one of these -- the ship manifest
    (``regolith.backends.manifest``) is exactly the sorted list of every
    backend's ``OutputFile``s, hashed. ``provenance`` (WO-160) is
    ``None`` when a producer has not tagged it -- the artifact index
    (:mod:`regolith.backends.artifact_index`) resolves an untagged file
    to the honest ``deterministic`` default at index-build time, never
    an invented ``real_tool`` claim.
    """

    model_config = ConfigDict(frozen=True)

    relpath: str = Field(description="Path relative to the ship package root.")
    content: bytes = Field(description="The file's exact bytes (repr=False by size).")
    sha256: str = Field(description="SHA-256 hex digest of ``content``.")
    provenance: ArtifactProvenance | None = Field(
        default=None,
        description="Real-tool vs. deterministic tier (WO-160); None until "
        "the artifact index resolves the honest default.",
    )

    # frob:doc docs/modules/py-backends.md#backends-framework
    @classmethod
    def of(
        cls,
        relpath: str,
        content: bytes,
        *,
        provenance: ArtifactProvenance | None = None,
    ) -> OutputFile:
        """Construct an ``OutputFile``, computing its digest from ``content``."""
        return cls(
            relpath=relpath,
            content=content,
            sha256=hashlib.sha256(content).hexdigest(),
            provenance=provenance,
        )

    # frob:doc docs/modules/py-backends.md#backends-framework
    def write_under(self, out_dir: Path) -> None:
        """Write ``content`` to ``out_dir / relpath``, creating parents."""
        path = out_dir / self.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.content)


# frob:doc docs/modules/py-backends.md#backends-framework
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
        assemblies: Mapping[str, RealizedAssembly] = {},  # noqa: B006 (frozen inputs)
        si_rows: Mapping[str, tuple[SiSheetRow, ...]] = {},  # noqa: B006 (frozen inputs)
        firmware: Mapping[str, FirmwareArtifact] = {},  # noqa: B006 (frozen inputs)
        hdl: Mapping[str, HdlBuildProducts] = {},  # noqa: B006 (frozen inputs)
        sim: Mapping[str, SimProducts] = {},  # noqa: B006 (frozen inputs)
        cost_estimates: Mapping[str, ItemizedEstimate] = {},  # noqa: B006 (frozen inputs)
        cost_profile: str | None = None,
        debug_taps: TapSet | None = None,
        tap_header: TapHeaderRecord | None = None,
        tap_placements: Mapping[str, TapPlacementPlan] = {},  # noqa: B006 (frozen inputs)
        hdl_debug_pins: Mapping[str, tuple[str, ...]] = {},  # noqa: B006 (frozen inputs)
        board_assignments: Mapping[str, RealizedBoardAssignment] = {},  # noqa: B006 (frozen inputs)
        edm_profiles: Mapping[str, RealizedWireEdmProfile] = {},  # noqa: B006 (frozen inputs)
        power_nets: Mapping[str, PowerNetPayload] = {},  # noqa: B006 (frozen inputs)
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
        the caller chooses to label the run. ``assemblies`` (WO-96, the
        `AssemblySteps` instructions producer's input) is a
        `RealizedAssembly` (WO-62) keyed by subject: like
        ``opt_traces``, it has no `report.realized_inputs`-derived
        source today (no `regolith-lower` pass emits a numeric mate
        graph an obligation could cite a `PayloadRef` to yet --
        `regolith.realizer.mech.assembly`'s own docstring), so a
        caller supplies it explicitly. ``firmware`` (WO-102, the
        `FirmwareBackend` input) is a `FirmwareArtifact` (the WO-37
        realizer's `FirmwareTree` plus an optional pinned-ELF/link-map
        pair) keyed by subject: like ``opt_traces``/``assemblies``, it
        carries no `PayloadRef` any obligation cites, so a caller
        always supplies it explicitly. ``hdl`` (WO-102, the
        `HdlBackend` input) is an `HdlBuildProducts` (source set +
        the WO-82 tier evidence already discharged for that subject)
        keyed by subject, caller-supplied for the same reason.
        ``sim`` (WO-155 deliverable 7, T-0068) is a `SimProducts`
        (trace/report already produced by a `hdl.sim_assert` discharge,
        `harness.models.hdl.sim_artifacts.SimArtifactFamily`'s
        backend-local mirror) keyed by subject -- the `SimBackend`'s
        input. Like ``hdl``, it carries no `PayloadRef` any obligation
        cites at THIS layer (the harness-side digests already resolved
        it), so a caller supplies it explicitly; AD-22 stands here too
        -- nothing in `SimBackend` re-invokes verilator, it only
        serializes what a discharge already produced (and, on a cache
        hit, RE-LINKS the identical family instead of asking the
        caller to re-run anything).
        ``power_nets`` (F-WO137-1, T-0064) is a `PowerNetPayload` keyed
        by subject -- the `power_oneline` producer's input. Like
        ``opt_traces``/``assemblies``/``firmware``/``hdl``, it is
        ALWAYS caller-supplied for now: `BuildPayload` (the
        `regolith-lower` -> orchestrator channel) has no `power_nets`
        field yet (the crates-side wiring is a separate, in-flight
        ticket), so there is nothing in `report.realized_inputs` or
        `report.final.payload_json` to derive it from today.
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
        self.assemblies = assemblies
        # WO-78: the per-subject SI table rows (derived from the build's
        # own obligations + evidence by `ship.si_rows_from_report`) --
        # the `si` drawing track's input.
        self.si_rows = si_rows
        # WO-102: the computer-track backends' realized inputs.
        self.firmware = firmware
        self.hdl = hdl
        # WO-155 deliverable 7 (T-0068): the sim/ family's caller-
        # supplied products, keyed by subject -- `SimBackend`'s input.
        self.sim = sim
        # WO-101 residual (F124 bundle): the build's persisted itemized cost
        # estimates, resolved from `report.cost_estimates` digests through
        # the discharge-time `PayloadStore` and keyed by subject (the BOM
        # backend's cost-column source on a real ship). `cost_profile` is
        # the build's resolved profile the totals row cites.
        self.cost_estimates = cost_estimates
        self.cost_profile = cost_profile
        # WO-125 (D237.1/.2, charter 40 sec. 1): the debug emission
        # profile's already-decided tap surface -- `None`/empty in a
        # release-profile ship (backends emit nothing extra, keeping
        # the release artifact set byte-identical by construction).
        # `debug_taps` is the derived+explicit TapSet; `tap_header` the
        # ONE pinout record (charter 40 sec. 4); `tap_placements` the
        # per-board-subject placement plans the realizer seam derived;
        # `hdl_debug_pins` the spec-declared spare pins per HDL subject.
        # Backends only SERIALIZE these (regolith/07 sec. 6) -- the
        # derivation lives in the ship path.
        self.debug_taps = debug_taps
        self.tap_header = tap_header
        self.tap_placements = tap_placements
        self.hdl_debug_pins = hdl_debug_pins
        # WO-165 (AD-47 sec. 5): the perf-board realizer's
        # `board_assignment.realized` payload, keyed by subject -- the
        # wiring-map/cut-list producers' input, mirroring `layouts`'
        # subject-keyed shape for the sibling `layout.realized` kind.
        self.board_assignments = board_assignments
        # WO-166 (AD-47 sec. 5): the wire-EDM profile-cut realizer's
        # `edm_profile.realized` payload, keyed by subject -- the
        # EDM backend's input, mirroring `board_assignments`' shape.
        self.edm_profiles = edm_profiles
        # F-WO137-1 (T-0064): the power-net payload, keyed by subject --
        # the `power_oneline` producer's input, mirroring `opt_traces`'/
        # `firmware`'s always-caller-supplied shape (see the docstring
        # above -- no `BuildPayload.power_nets` channel exists yet).
        self.power_nets = power_nets


# frob:doc docs/modules/py-backends.md#backends-framework
class Backend(Protocol):
    """A manufacturing backend: ``BackendInputs`` in, ``OutputFile``s out."""

    # frob:doc docs/modules/py-backends.md#backends-framework
    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Serialize ``inputs`` into this backend's package files (Result-total)."""
        ...
