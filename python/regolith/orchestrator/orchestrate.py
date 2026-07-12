"""The build driver: tiers -> discharge -> loop -> release gate (AD-1).

This is the top of the orchestrator: it drives the compiler facade to get
obligations, routes them through the harness at the tiers that discharge
(T1+), runs the lazy loop at the optimizing tier (T2+), and enforces
release-gate totality at T3 (INV-24). It owns the caching and ordering;
the harness owns selection and physics; the core owns everything static.

The release gate is the load-bearing honesty property: a ``--release``
report contains zero unaccepted ``violated`` or ``indeterminate``
obligations. This layer has no waiver/assume ledger yet (regolith/12
rungs 6-7 land later), so it accepts nothing -- every non-``discharged``
obligation fails the gate and is named. That is strictly conservative:
adding acceptances can only ever let MORE builds pass, never fewer.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import compiler
from regolith._schema.models import (
    ConverterGraph,
    FlownetPayload,
    FramePayload,
    Obligation,
    RealizedAssembly,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.errors import OrchestratorError
from regolith.harness import ModelRegistry, default_registry
from regolith.harness.attest import conferred_tier
from regolith.harness.plugin import PackLoadError
from regolith.logging_setup import get_logger
from regolith.magnetite.records_payload import (
    REGISTRY_RECORDS_KIND,
    registry_records_payload,
)
from regolith.magnetite.stdlib_resolve import resolve_pack_source_roots
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet, tier_from_name
from regolith.orchestrator.cache import CacheStats, EvidenceStore
from regolith.orchestrator.costing import (
    load_cost_context,
    persist_estimates,
    record_pins,
)
from regolith.orchestrator.discharge import ObligationResult, discharge_all
from regolith.orchestrator.frame_resolve import (
    frame_record_pins,
    frame_winner_rows,
    load_frame_context,
)
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.loop import LoopOutcome, SensitivityHook, lazy_loop
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.plan_staging import load_plan_context
from regolith.orchestrator.plan_staging import record_pins as plan_record_pins
from regolith.orchestrator.programs import emitted_realizer_programs
from regolith.orchestrator.si_stackups import load_si_context
from regolith.orchestrator.tiers import BuildTier
from regolith.realizer.elec.kicad import LayoutRequest
from regolith.realizer.elec.realized import (
    put_realized_layout,
    realize_elec_board,
    realize_elec_board_fake,
)
from regolith.realizer.mech.interpreter import (
    RealizedGeometryArtifact,
    realize_feature_program,
)
from regolith.realizer.mech.schema import FeatureProgram

_log = get_logger(__name__)

# WO-42 deliverable 5 / INV-21: the realizer pack name folded into a
# realized-IR lockfile row's `cause: realizer(<pack>)`.
REALIZER_PACK_MECH = "mech"
# The elec leg's own pack name (WO-24 close-out's residual, closed by
# this dispatch): the real-KiCad `layout.realized` producer, gated the
# same way the realizer itself is (`real_kicad_available()`).
REALIZER_PACK_ELEC = "elec"

# The D96 payload kind -> realizer pack name this WO-42 deliverable 5
# extension folds a mixed `realized_inputs` tuple's lockfile rows by
# (:func:`realized_lock_rows`): every kind names its own producer pack,
# never a caller-supplied blanket pack once more than one kind exists.
_REALIZER_PACK_BY_KIND: Mapping[str, str] = {
    "geometry.realized": REALIZER_PACK_MECH,
    "layout.realized": REALIZER_PACK_ELEC,
}
# The lockfile slot suffix per realized-IR kind (`<subject>.<suffix>`).
_LOCK_SLOT_SUFFIX_BY_KIND: Mapping[str, str] = {
    "geometry.realized": "geometry",
    "layout.realized": "layout",
}


class ElecBoardInputs(BaseModel):
    """One caller-supplied elec board's staged-build-loop realize inputs.

    Mirrors `feature_programs`' role for the mech leg: the staged build
    loop has no in-payload discovery signal for which subjects need a
    real-KiCad layout (unlike the flownet `GeomExtract` placeholder the
    mech leg scans for -- `layout.realized` is not yet consumed by any
    re-lowering pass, WO-24's own close-out note), so a caller supplies
    the board's identity + layout request directly.
    """

    model_config = ConfigDict(frozen=True)

    netlist_hash: str
    board_outline_ref: str
    request: LayoutRequest
    # WO-71 continuation slice 2: an EXPLICIT opt-in into the
    # deterministic, no-KiCad-install layout tier
    # (`regolith.realizer.elec.realized.realize_elec_board_fake`).
    # Defaults False -- the real leg's "never a faked layout"
    # discipline stays the default for every board that does not ask
    # for this tier by name. Outline geometry (WO-103) lives on
    # `request.outline_w_mm`/`outline_d_mm` -- the ONE source both the
    # real and the fake tier read, never duplicated here.
    deterministic: bool = False


# WO-42 deliverable 5: a safety cap on staged-build iterations, well
# above any real subject count, so a producer bug that never converges
# (repeatedly claims a "new" digest for an unchanging input) fails loud
# with a logged warning instead of looping forever. Normal convergence
# is bounded by `len(feature_programs)` (each iteration resolves at
# least one previously-unresolved subject or stops), so this is a
# backstop, not the expected exit path.
_STAGED_BUILD_MAX_ITERATIONS = 16


class BuildReport(BaseModel):
    """The outcome of one orchestrated build at a given tier."""

    model_config = ConfigDict(frozen=True)

    tier: BuildTier
    ok: bool  # the core's static verdict (diagnostics-clean)
    results: tuple[ObligationResult, ...] = ()
    unresolved: tuple[ObligationResult, ...] = ()
    cache_stats: CacheStats = CacheStats()
    release_ok: bool = True
    loop_iterations: int = 0
    # Plugins skipped LOUDLY at registry composition (WO-20/AD-19,
    # renamed WO-44/AD-26 with the one-seam generalization): a bad
    # plugin is named here, never a silent partial load.
    plugin_errors: tuple[PackLoadError, ...] = ()
    # The raw `BuildOutput.payload_json()` bytes this build produced
    # (WO-42 deliverable 5): populated for every tier, including T0
    # `check`, so a caller (the staged build loop) can inspect the
    # lowered flownet edges for pending `GeomExtract` placeholders
    # without a second core call.
    payload_json: bytes = b""
    # The ONE renderer's text (AD-7) for this build's diagnostics, exactly
    # as `BuildOutcome.rendered` returned it -- WO-43's `regolith build`
    # prints this verbatim (never a second renderer) for its human-default
    # stdout form, the same precedent `check` already established.
    rendered: str = ""
    # WO-54: the build-level cost profile that applied (`--profile` beats
    # the manifest default; None when the project declares no profiles),
    # the INV-22 pins for every consumed cost record, and the persisted
    # itemized-estimate payload digests (`<subject>/<profile>` -> digest).
    cost_profile: str | None = None
    cost_record_pins: tuple[tuple[str, str], ...] = ()
    cost_estimates: tuple[tuple[str, str], ...] = ()
    # WO-65: the INV-22 pins for every consumed std.civil frame record
    # and the section-search winners' `cause: optimize(...)` rows
    # (INV-21) -- collected AFTER discharge, exactly the cost-pin
    # posture above.
    frame_record_pins: tuple[tuple[str, str], ...] = ()
    frame_lock_rows: tuple[LockRow, ...] = ()
    # WO-69: the INV-22 pins for every consumed `plan:` linkage --
    # the extern plan ref itself (`extern(<ref>)` key, INV-13 lockfile
    # cause) plus every declared `machine`/`tooling`/`stock_target`
    # record a `cam.*` obligation actually resolved -- collected AFTER
    # discharge, the cost/frame-pin posture above.
    plan_record_pins: tuple[tuple[str, str], ...] = ()

    @property
    def obligations_discharged(self) -> int:
        """How many obligations a model discharged (status ``discharged``)."""
        return sum(1 for r in self.results if r.is_resolved)


class GateSummary(BaseModel):
    """The machine-readable gate state `regolith preview` writes as
    ``gate_summary.json`` (D197): reuses :class:`GateCounts` (the SAME
    accounting ``--release``/:func:`release_gate` already computes) plus
    the tier the build ran at and its own ``clean``/``release_ok``
    verdict, so a caller never has to re-derive "was this build clean"
    from raw obligation results.
    """

    model_config = ConfigDict(frozen=True)

    tier: str
    ok: bool
    release_ok: bool
    counts: GateCounts

    @property
    def stamp_text(self) -> str:
        """The honesty-stamp annotation text (D197): ``"RELEASE-CLEAN"``
        when the gate is clean, else ``"PREVIEW -- NOT RELEASED: <n>
        unresolved"`` naming the violated+indeterminate count (below-
        trust-floor results are also "not released" but are folded into
        the same honest total -- the stamp never claims more precision
        than the gate itself draws)."""
        if self.release_ok:
            return "RELEASE-CLEAN"
        n = self.counts.unresolved + self.counts.below_trust_floor
        return f"PREVIEW -- NOT RELEASED: {n} unresolved"


def gate_summary_for(report: BuildReport) -> GateSummary:
    """Build a :class:`GateSummary` from a finished :class:`BuildReport`
    (`regolith preview`'s own gate read, D197) -- ``release_ok`` mirrors
    whatever the report already decided (T3 runs the real gate;
    lower tiers default ``release_ok=True`` on the report itself, so a
    non-release-tier preview's stamp reports on the gate AS IF `--release`
    ran, using the SAME :func:`gate_counts` accounting, never a
    softened one).
    """
    counts = gate_counts(report.results)
    return GateSummary(
        tier=report.tier.name,
        ok=report.ok,
        release_ok=counts.clean,
        counts=counts,
    )


def _meets_trust_floor(result: ObligationResult) -> bool:
    """True iff ``result``'s conferred tier satisfies its claim trust floor.

    A claim without a floor always passes. An unparseable floor is treated
    conservatively as unmet (it is a floor the gate cannot certify). An
    indeterminate attestation confers no tier, so any floor is unmet
    (INV-14/INV-28: below-floor computed evidence is not a pass).
    """
    if result.trust_floor is None:
        return True
    floor = tier_from_name(result.trust_floor)
    if floor.is_err:
        _log.warning(
            "claim %s has an unparseable trust floor %r; treating as unmet",
            result.subject_ref,
            result.trust_floor,
        )
        return False
    conferred = conferred_tier(result.attestation)
    if conferred is None:
        return False
    return conferred.meets(floor.danger_ok)


class GateCounts(BaseModel):
    """The release gate's own accounting (D197: the shape `regolith
    preview`'s ``gate_summary.json`` reuses so it never re-derives "is
    this build clean" a second way): how many results are ``violated``,
    ``indeterminate``/deferred, or below their claim's trust floor. All
    three are zero iff :func:`release_gate` returns ``Ok``.
    """

    model_config = ConfigDict(frozen=True)

    violated: int
    indeterminate: int
    below_trust_floor: int

    @property
    def unresolved(self) -> int:
        """``violated + indeterminate`` -- every result that is not a clean pass."""
        return self.violated + self.indeterminate

    @property
    def clean(self) -> bool:
        """True iff nothing is violated, indeterminate, or below floor."""
        return (
            self.violated == 0
            and self.indeterminate == 0
            and self.below_trust_floor == 0
        )


def gate_counts(results: tuple[ObligationResult, ...]) -> GateCounts:
    """The single place that turns a result set into violated/
    indeterminate/below-floor counts -- :func:`release_gate`'s own
    computation, factored out so `regolith preview`'s honesty stamp and
    ``gate_summary.json`` (D197) read the SAME accounting ``--release``
    gates on, never a second reimplementation that could drift from it.
    """
    unresolved = tuple(r for r in results if not r.is_resolved)
    below_floor = tuple(
        r for r in results if r.is_resolved and not _meets_trust_floor(r)
    )
    violated = sum(1 for r in unresolved if r.is_violated)
    indeterminate = len(unresolved) - violated
    return GateCounts(
        violated=violated,
        indeterminate=indeterminate,
        below_trust_floor=len(below_floor),
    )


def release_gate(
    results: tuple[ObligationResult, ...],
) -> Result[None, OrchestratorError]:
    """Enforce INV-24 totality plus INV-28 trust floors on computed evidence.

    Returns ``Ok`` iff every obligation discharged AND every discharged
    result meets its claim's ``trust: >= tier`` floor. Otherwise ``Err``
    names the counts, keeping trust-floor refusals DISTINCT from violated
    and indeterminate/deferred (report/exit-code distinction, D-E).
    Deferrals count as indeterminate (an obligation that never formed is
    not proven).
    """
    counts = gate_counts(results)
    if counts.clean:
        return Ok(None)
    _log.warning(
        "release gate FAILED: %d violated, %d indeterminate/deferred, "
        "%d below trust floor",
        counts.violated,
        counts.indeterminate,
        counts.below_trust_floor,
    )
    return Err(
        OrchestratorError(
            kind="release_gate_failed",
            message=(
                f"--release refused: {counts.violated} violated, "
                f"{counts.indeterminate} indeterminate/deferred, and "
                f"{counts.below_trust_floor} below-trust-floor obligation(s) "
                "unaccepted (no waiver/assume ledger)"
            ),
        )
    )


def _parse_obligations(payload: dict[str, object]) -> tuple[Obligation, ...]:
    """Extract the obligation list from a parsed build payload (source order)."""
    raw = payload.get("obligations", [])
    if not isinstance(raw, list):
        return ()
    return tuple(Obligation.model_validate(o) for o in raw)


def _project_root(paths: tuple[str, ...]) -> str:
    """The `.regolith/`-rooting directory for `paths[0]` (AD-10).

    `paths[0]` is a single source FILE for a one-file build (every test
    fixture in this repo passes one); `.regolith/` roots beside the
    project, not inside a file. Falls back to the path itself when it
    is already a directory (or does not exist yet), matching the one
    convention this module and `EvidenceStore` both need.
    """
    candidate = Path(paths[0])
    if candidate.is_file():
        return str(candidate.parent)
    return paths[0]


def _put_flownet_payloads(
    store: PayloadStore,
    payload: dict[str, object],
    obligations: tuple[Obligation, ...],
) -> None:
    """Store every flownet a `kind: flownet` `PayloadRef` resolves to,
    into the caller-supplied `store` (D96/D154: `build()`'s one shared
    `PayloadStore` instance, the same one later threaded to discharge).

    WO-32 D4b: the FIRST orchestrator `PayloadStore` producer. Each
    obligation's `payloads` may carry a `PayloadRef{ kind: "flownet",
    digest, origin }` (D129); `BuildPayload.flownets` (name -> payload,
    AD-6 source order) is where the referenced content actually lives.
    The digest was already computed Rust-side through the AD-18
    canonical encoder (`FlownetPayload.content_digest()`) -- this
    function stores bytes under that EXACT digest via
    `PayloadStore.put_at` rather than recomputing one, so a later
    `resolve(digest)` at discharge time is a hit (per fluorite/03 sec.
    2 / D129's payload-ref channel).

    A `PayloadRef` naming a flownet absent from `payload["flownets"]`
    is logged and skipped, not raised: the referenced obligation's
    discharge will honestly fail to resolve the payload later (a
    recoverable, already-modeled outcome -- `PayloadStore.resolve`
    returns `Err(payload_not_found)`), rather than crashing the build
    over a producer-side inconsistency that should not occur but is
    not this function's job to treat as fatal.
    """
    flownets_raw = payload.get("flownets", {})
    if not isinstance(flownets_raw, dict) or not flownets_raw:
        return
    seen_digests: set[str] = set()
    for obligation in obligations:
        for ref in obligation.payloads or ():
            if ref.kind != "flownet" or ref.digest in seen_digests:
                continue
            raw = flownets_raw.get(ref.origin)
            if raw is None:
                _log.warning(
                    "flownet payload ref origin=%r digest=%s names no "
                    "flownet in this build's payload; skipping store put",
                    ref.origin,
                    ref.digest,
                )
                continue
            flownet = FlownetPayload.model_validate(raw)
            data = flownet.model_dump_json().encode("utf-8")
            store.put_at(ref.digest, data)
            seen_digests.add(ref.digest)
    _log.debug(
        "payload store: put %d flownet payload(s) for this build",
        len(seen_digests),
    )


def _put_frame_payloads(
    store: PayloadStore,
    payload: dict[str, object],
    obligations: tuple[Obligation, ...],
) -> None:
    """Store every calcite frame a `kind: frame` `PayloadRef` resolves
    to, into the caller-supplied `store` (mirrors
    :func:`_put_flownet_payloads` verbatim -- WO-48 deliverable 3/4,
    calcite/03 sec. 4/5).

    Each obligation's `payloads` may carry a `PayloadRef{ kind: "frame",
    digest, origin }`; `BuildPayload.frames` (name -> payload, AD-6
    source order) is where the referenced content actually lives. The
    digest was already computed Rust-side through the AD-18 canonical
    encoder (`FramePayload.content_digest()`) -- this function stores
    bytes under that EXACT digest via `PayloadStore.put_at` rather than
    recomputing one, so a later `resolve(digest)` at discharge time is a
    hit.

    A `PayloadRef` naming a frame absent from `payload["frames"]` is
    logged and skipped, not raised -- same recoverable-outcome
    reasoning as the flownet producer.
    """
    frames_raw = payload.get("frames", {})
    if not isinstance(frames_raw, dict) or not frames_raw:
        return
    seen_digests: set[str] = set()
    for obligation in obligations:
        for ref in obligation.payloads or ():
            if ref.kind != "frame" or ref.digest in seen_digests:
                continue
            raw = frames_raw.get(ref.origin)
            if raw is None:
                _log.warning(
                    "frame payload ref origin=%r digest=%s names no "
                    "structure in this build's payload; skipping store put",
                    ref.origin,
                    ref.digest,
                )
                continue
            frame = FramePayload.model_validate(raw)
            data = frame.model_dump_json().encode("utf-8")
            store.put_at(ref.digest, data)
            seen_digests.add(ref.digest)
    _log.debug(
        "payload store: put %d frame payload(s) for this build",
        len(seen_digests),
    )


def _put_converter_graph_payloads(
    store: PayloadStore,
    payload: dict[str, object],
    obligations: tuple[Obligation, ...],
) -> None:
    """Store every elec behavioral converter graph a `kind:
    converter_graph` `PayloadRef` resolves to, into the caller-supplied
    `store` (WO-88 deliverable 2/3, F112 -- mirrors
    :func:`_put_flownet_payloads` verbatim).

    Each obligation on a decl with a `spec:` body carries a `PayloadRef{
    kind: "converter_graph", digest, origin }` (attached Rust-side,
    `regolith-lower/src/claims.rs`); `BuildPayload.converter_graphs`
    (name -> graph, AD-6 source order) is where the referenced graph
    actually lives. The digest was already computed Rust-side through the
    AD-18 canonical encoder (`content_address("converter_graph", graph)`)
    -- this function stores the graph's JSON bytes under that EXACT
    digest via `PayloadStore.put_at` (not a recomputed one), so a later
    `resolve(digest)` at discharge time is a hit and the buck model
    reads the design's topology from the compiled graph.

    A `PayloadRef` naming a graph absent from `payload["converter_graphs"]`
    is logged and skipped, not raised -- same recoverable-outcome
    reasoning as the flownet/frame producers.
    """
    graphs_raw = payload.get("converter_graphs", {})
    if not isinstance(graphs_raw, dict) or not graphs_raw:
        return
    seen_digests: set[str] = set()
    for obligation in obligations:
        for ref in obligation.payloads or ():
            if ref.kind != "converter_graph" or ref.digest in seen_digests:
                continue
            raw = graphs_raw.get(ref.origin)
            if raw is None:
                _log.warning(
                    "converter_graph payload ref origin=%r digest=%s names no "
                    "graph in this build's payload; skipping store put",
                    ref.origin,
                    ref.digest,
                )
                continue
            graph = ConverterGraph.model_validate(raw)
            # `by_alias` so the `Edge.from_` field serializes back to its
            # wire name `from` -- the shape `ConverterGraph.
            # model_validate_json` (and the buck model's resolver) expects.
            data = graph.model_dump_json(by_alias=True).encode("utf-8")
            store.put_at(ref.digest, data)
            seen_digests.add(ref.digest)
    _log.debug(
        "payload store: put %d converter-graph payload(s) for this build",
        len(seen_digests),
    )


def put_realized_geometry(
    store: PayloadStore, artifact: RealizedGeometryArtifact
) -> str:
    """Store ``artifact.geometry`` (kind ``geometry.realized``) into the
    WO-30 payload store, returning its content digest.

    WO-42 deliverable 4's realizer emission seam: the mech realizer
    (`regolith.realizer.mech.interpreter.realize_feature_program`) has
    no Rust-computed AD-18 canonical digest to pin, unlike
    :func:`_put_flownet_payloads`'s flownets -- a `RealizedGeometry` is
    produced standalone, before any compile pass has referenced it in
    an `Obligation.payloads` ref (there is no upstream digest to
    reproduce). This function therefore uses :meth:`PayloadStore.put`
    (fresh blake3 digest of the JSON bytes), not `put_at`: the RETURNED
    digest becomes the identity a later staged build (WO-42 deliverable
    5, not built by this dispatch) supplies as a `RealizedInput` key
    when re-lowering with this geometry.

    The staged-loop wiring that calls this after a `realize_feature_program`
    success and feeds the returned digest back into the next `lower()`
    pass is WO-42 deliverable 5's job (out of this dispatch's scope,
    per design-log 2026-07-08-cycle-25's "Dispatch effects" -- (c) needs
    only the validate-and-emit pass + this emission seam, not the loop).
    """
    data = artifact.geometry.model_dump_json().encode("utf-8")
    digest = store.put(data)
    _log.debug(
        "payload store: put geometry.realized for part=%s digest=%s",
        artifact.geometry.feature_program_hash,
        digest,
    )
    return digest


def put_realized_assembly(store: PayloadStore, realized: RealizedAssembly) -> str:
    """Store ``realized`` (kind ``assembly.realized``) into the WO-30
    payload store, returning its content digest.

    WO-62 slice B deliverable 5's realizer emission seam, mirroring
    :func:`put_realized_geometry` exactly (same reasoning: a
    `RealizedAssembly` is produced standalone by
    `regolith.realizer.mech.assembly.solve_assembly`, before any
    compile pass has referenced it in an `Obligation.payloads` ref --
    there is no upstream Rust-computed digest to reproduce, so this
    uses :meth:`PayloadStore.put`, not `put_at`).
    """
    data = realized.model_dump_json().encode("utf-8")
    digest = store.put(data)
    _log.debug(
        "payload store: put assembly.realized mating_graph_hash=%s digest=%s",
        realized.mating_graph_hash,
        digest,
    )
    return digest


def _with_registry_records(
    realized_inputs: tuple[compiler.RealizedInput, ...],
    record_paths: tuple[str, ...],
) -> tuple[compiler.RealizedInput, ...]:
    """``realized_inputs`` plus the registry-records payload built from
    ``record_paths`` (WO-87/D198), unless one is already present (a
    caller-supplied payload wins) or no records resolve (no payload --
    dependent rules defer honestly)."""
    if any(ri.kind == REGISTRY_RECORDS_KIND for ri in realized_inputs):
        return realized_inputs
    payload = registry_records_payload(record_paths)
    if payload is None:
        return realized_inputs
    digest, kind, subject, payload_bytes = payload
    _log.debug("build: registry-records payload attached digest=%s", digest)
    return (
        *realized_inputs,
        compiler.RealizedInput(
            digest=digest, kind=kind, subject=subject, payload_bytes=payload_bytes
        ),
    )


def build(
    paths: tuple[str, ...],
    tier: BuildTier,
    *,
    registry: ModelRegistry | None = None,
    hooks: tuple[SensitivityHook, ...] = (),
    persist: bool = False,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
    realized_inputs: tuple[compiler.RealizedInput, ...] = (),
    cost_profile: str | None = None,
    cost_record_paths: tuple[str, ...] = (),
    cost_as_of: datetime.date | None = None,
    frame_record_paths: tuple[str, ...] = (),
    plan_record_paths: tuple[str, ...] = (),
    si_record_paths: tuple[str, ...] = (),
    color: bool = False,
) -> Result[BuildReport, OrchestratorError]:
    """Run an orchestrated build of ``paths`` at ``tier``.

    T0 (``check``) is the static core pass only. T1+ additionally routes
    obligations through the harness (with the evidence cache). T2+ runs the
    lazy loop over ``hooks``. T3 (``release``) applies the release gate and
    fails the build if any obligation is unresolved (INV-24). A core
    infrastructure failure is an ``Err`` value (``CoreFailure`` mapped);
    a failing *check* is a report with ``ok=False`` (claims-as-data).

    ``realized_inputs`` (WO-42 deliverable 3, AD-25/D128) is the caller-
    resolved realized-domain IR channel threaded straight through to the
    core; empty by default (the pre-realization placeholder path). The
    staged build loop (deliverable 5, :func:`staged_build`) is the only
    caller that supplies a non-empty set today.

    ``cost_profile``/``cost_record_paths``/``cost_as_of`` (WO-54) select
    the build-level cost profile (`--profile`), extend the local cost-
    record search paths beyond the project root, and pin the expiry
    clock date (None reads today at the ONE `costing` seam). An unknown
    ``cost_profile`` is a loud `Err`, never a silent default.

    ``frame_record_paths`` (WO-48 close-out follow-up) extends the local
    std.civil section/material record search paths beyond the project
    root (the `cost_record_paths` posture, applied to frame resolution).

    ``plan_record_paths`` (WO-69) extends the local `machine`/`tool`/
    `stock_target` record search paths beyond the project root (the
    same posture, applied to `plan:` linkage resolution).

    ``si_record_paths`` (WO-78) extends the local `[[stackup]]` record
    search paths beyond the project root (the same posture, applied to
    signal-integrity impedance resolution).

    ``color`` (owner directive: optional TTY colors) selects the ANSI-
    colored rendering of ``BuildReport.rendered`` instead of plain text;
    threaded straight through to :func:`regolith.compiler.check`/
    :func:`~regolith.compiler.compile`. Defaults to ``False`` so every
    existing caller (goldens included) stays byte-identical; the CLI
    edge is the only caller expected to pass ``True``.
    """
    registry = registry or default_registry()

    # WO-87 (D198): the registry-records payload rides the realized-
    # input channel into every build. The record search roots are the
    # SAME ones the cost/frame/plan loaders already receive (D192's
    # resolution), so a project whose `[depends]` resolves stdlib
    # records gets rule-eval record dereference with no new knob; no
    # resolvable records means no payload and dependent rules defer.
    realized_inputs = _with_registry_records(
        realized_inputs,
        tuple(
            dict.fromkeys(
                cost_record_paths
                + frame_record_paths
                + plan_record_paths
                + si_record_paths
            )
        ),
    )

    # D201: a project's `[depends]` also contributes each declared
    # std.* dependency's rule-pack SOURCE files to the compile set --
    # visibility only (attachment stays the design's own explicit
    # `attach`/`process=` act). One home: the pack-source roots ride
    # straight onto the paths handed to the core, same as every
    # caller-supplied path. A project with no std.* pack dep, or one
    # that resolves nowhere, is byte-identical (empty addition).
    pack_source_roots = resolve_pack_source_roots(_project_root(paths))
    compile_paths = tuple(dict.fromkeys(paths + pack_source_roots))

    if tier.runs_discharge:
        outcome = compiler.compile(
            compile_paths,
            registry_version=registry.version,
            realized_inputs=realized_inputs,
            color=color,
        )
    else:
        outcome = compiler.check(
            compile_paths, realized_inputs=realized_inputs, color=color
        )
    if outcome.is_err:
        return Err(
            OrchestratorError(
                kind="core_failure", message=str(outcome.danger_err.message)
            )
        )
    built = outcome.danger_ok

    if not tier.runs_discharge:
        _log.debug("tier %s: static-only, no harness discharge", tier.name)
        return Ok(
            BuildReport(
                tier=tier,
                ok=built.ok,
                plugin_errors=registry.plugin_errors,
                payload_json=built.payload_json,
                rendered=built.rendered,
            )
        )

    build_payload = json.loads(built.payload_json)
    obligations = _parse_obligations(build_payload)
    # D96/D154: one PayloadStore for this build, shared by the flownet
    # producer AND the discharge path -- the digest a producer puts under
    # is exactly the digest `discharge_one` later threads a resolver over
    # (WO-32 D4b's producer, D154's consumer, same store instance).
    payload_store = PayloadStore(_project_root(paths))
    # WO-32 D4b: put every referenced flownet payload into the WO-30
    # store BEFORE discharge, so a model's `resolve(digest)` call
    # (harness/registry, D96 sec. 8.3) can find it.
    _put_flownet_payloads(payload_store, build_payload, obligations)
    # WO-48 deliverable 3/4: put every referenced frame payload into the
    # store BEFORE discharge, same reasoning as the flownet producer.
    _put_frame_payloads(payload_store, build_payload, obligations)
    # WO-88 deliverable 2/3 (F112): put every referenced converter-graph
    # payload into the store BEFORE discharge, same reasoning as the
    # flownet/frame producers -- the buck model resolves it at discharge.
    _put_converter_graph_payloads(payload_store, build_payload, obligations)
    # WO-54 deliverable 4: the build's cost context (profiles + records
    # + the frame/flownet quantity bases), threaded to every discharge
    # like the payload store. `Ok(None)` is the honest costless-build
    # state -- cost claims then defer naming the missing configuration.
    cost_context_result = load_cost_context(
        _project_root(paths),
        payload_store=payload_store,
        build_payload=build_payload,
        cli_profile=cost_profile,
        record_search_paths=cost_record_paths,
        as_of=cost_as_of,
    )
    if cost_context_result.is_err:
        return Err(cost_context_result.danger_err)
    cost_context = cost_context_result.danger_ok
    # WO-48 close-out follow-up: the build's frame-resolution context
    # (std.civil section/material records), threaded to every discharge
    # like the cost context. `Ok(None)` is the honest no-frames state --
    # a build with no calcite structures never forms a frame claim.
    frame_context_result = load_frame_context(
        _project_root(paths),
        build_payload=build_payload,
        record_search_paths=frame_record_paths,
        payload_store=payload_store,
    )
    if frame_context_result.is_err:
        return Err(frame_context_result.danger_err)
    frame_context = frame_context_result.danger_ok
    # WO-69: the build's plan-resolution context (machine/tooling/
    # stock-target records), threaded to every discharge like the cost
    # and frame contexts. Always `Ok` (a plan-less build simply has no
    # records loaded; `cam.*` obligations then defer honestly).
    plan_context_result = load_plan_context(
        _project_root(paths),
        payload_store=payload_store,
        record_search_paths=plan_record_paths,
    )
    if plan_context_result.is_err:
        return Err(plan_context_result.danger_err)
    plan_context = plan_context_result.danger_ok
    # WO-78: the build's SI stackup context (fab-published records),
    # threaded to every discharge like the cost/frame/plan contexts.
    # Always `Ok` for a stackup-less build; an impedance claim naming a
    # stackup this build never loaded defers honestly at translate time.
    si_context_result = load_si_context(
        _project_root(paths),
        record_search_paths=si_record_paths,
    )
    if si_context_result.is_err:
        return Err(si_context_result.danger_err)
    si_context = si_context_result.danger_ok
    store_result = EvidenceStore.load(paths[0]) if persist else Ok(EvidenceStore())
    if store_result.is_err:
        return Err(store_result.danger_err)
    store = store_result.danger_ok

    if tier.runs_loop:
        loop_result = lazy_loop(
            obligations,
            registry=registry,
            store=store,
            hooks=hooks,
            signer=signer,
            trust_keys=trust_keys,
            payload_store=payload_store,
            cost_context=cost_context,
            frame_context=frame_context,
            plan_context=plan_context,
            si_context=si_context,
        )
        if loop_result.is_err:
            return Err(loop_result.danger_err)
        loop: LoopOutcome = loop_result.danger_ok
        results, iterations = loop.results, loop.iterations
    else:
        results = discharge_all(
            list(obligations),
            registry=registry,
            store=store,
            signer=signer,
            trust_keys=trust_keys,
            payload_store=payload_store,
            cost_context=cost_context,
            frame_context=frame_context,
            plan_context=plan_context,
            si_context=si_context,
        )
        iterations = 1

    if persist:
        saved = store.save(paths[0])
        if saved.is_err:
            return Err(saved.danger_err)

    # WO-54: persist the itemized estimates (toolchain/27 sec. 1.5) and
    # collect the INV-22 record pins AFTER discharge, so the pin ledger
    # covers exactly what the staged requests consumed.
    resolved_cost_profile = None
    cost_pins: tuple[tuple[str, str], ...] = ()
    cost_estimates: tuple[tuple[str, str], ...] = ()
    if cost_context is not None:
        resolved_cost_profile = cost_context.build_profile
        cost_pins = record_pins(cost_context)
        cost_estimates = persist_estimates(cost_context, registry)
    # WO-65: the frame-record pins + section-search winner rows, also
    # collected AFTER discharge so the ledger covers exactly what the
    # staged requests consumed (INV-21/INV-22).
    frame_pins: tuple[tuple[str, str], ...] = ()
    frame_rows: tuple[LockRow, ...] = ()
    if frame_context is not None:
        frame_pins = frame_record_pins(frame_context)
        frame_rows = frame_winner_rows(frame_context)
    # WO-69: the plan-record pins, same AFTER-discharge posture.
    plan_pins: tuple[tuple[str, str], ...] = ()
    if plan_context is not None:
        plan_pins = plan_record_pins(plan_context)

    unresolved = tuple(r for r in results if not r.is_resolved)
    release_ok = True
    if tier.is_release:
        gate = release_gate(results)
        release_ok = gate.is_ok

    _log.debug(
        "build tier=%s obligations=%d discharged=%d unresolved=%d release_ok=%s",
        tier.name,
        len(results),
        sum(1 for r in results if r.is_resolved),
        len(unresolved),
        release_ok,
    )
    return Ok(
        BuildReport(
            tier=tier,
            ok=built.ok,
            results=results,
            unresolved=unresolved,
            cache_stats=store.stats,
            release_ok=release_ok,
            loop_iterations=iterations,
            plugin_errors=registry.plugin_errors,
            payload_json=built.payload_json,
            rendered=built.rendered,
            cost_profile=resolved_cost_profile,
            cost_record_pins=cost_pins,
            cost_estimates=cost_estimates,
            frame_record_pins=frame_pins,
            frame_lock_rows=frame_rows,
            plan_record_pins=plan_pins,
        )
    )


def _pending_geom_extract_subjects(payload_json: bytes) -> frozenset[str]:
    """Subjects still lowered to the pre-realization ``GeomExtract``
    placeholder (AD-25/D128) across every flownet in ``payload_json``.

    A `from=<ref>` flow edge lowers to ``EdgeParams::GeomExtract{record,
    selector}`` (`regolith-lower::flownet_lower`) with an EMPTY
    ``record.digest`` exactly when no realized-geometry input matched
    its subject (`RealizedFlownetInputs::geometry`, deliverable 3); a
    non-empty digest means a prior iteration's realized input already
    backs it (whether or not `extract_path` itself then succeeded --
    an extraction failure is D5's own diagnostic, not this loop's
    concern: re-realizing an unchanged subject would not change the
    outcome, INV-10). ``record.name``/``selector`` both carry the exact
    `from=` ref text, which is also the subject string
    `compiler.RealizedInput.subject` must match byte-for-byte
    (`RealizedFlownetInputs::geometry`'s `input.subject == from_ref`).
    """
    if not payload_json:
        return frozenset()
    payload = json.loads(payload_json)
    flownets = payload.get("flownets", {})
    if not isinstance(flownets, dict):
        return frozenset()
    subjects: set[str] = set()
    for flownet in flownets.values():
        if not isinstance(flownet, dict):
            continue
        for edge in flownet.get("edges", []) or []:
            params = edge.get("params") or {}
            if params.get("source") != "geom_extract":
                continue
            record = params.get("record") or {}
            if record.get("digest"):
                continue  # already backed by a realized-input digest
            name = record.get("name") or ""
            if name:
                subjects.add(name)
    return frozenset(subjects)


def realized_lock_rows(
    realized_inputs: tuple[compiler.RealizedInput, ...],
    pack: str | None = None,
) -> tuple[LockRow, ...]:
    """Lockfile rows for realized-domain IRs supplied to a build (WO-42
    deliverable 5, INV-21): each row's cause is ``realizer(<pack>)``,
    following the existing ``dfm(...)``/``drc(...)``/``budget(...)``
    cause-string convention documented in ``lockfile.py``. ``slot``
    names the subject's realized-IR pin (``<subject>.geometry`` for the
    D96 ``geometry.realized`` kind, ``<subject>.layout`` for
    ``layout.realized``); ``value`` is the payload-store digest a
    re-``check``/``compile`` pass supplies back as that subject's
    ``RealizedInput.digest``. Rows are returned in subject-sorted order
    (AD-6: deterministic lockfile row order is `render`'s own job, but a
    stable INPUT order keeps this function's output reproducible
    independent of dict iteration order too).

    ``pack`` overrides EVERY row's pack name when given (back-
    compatible with a caller that already knows a single-kind tuple's
    producer); the default (``None``) derives each row's pack from its
    own ``kind`` via ``_REALIZER_PACK_BY_KIND`` -- the mixed mech+elec
    tuple this WO-42 extension's staged build loop now produces needs
    a per-row pack, not one blanket name.
    """
    rows = []
    for ri in sorted(realized_inputs, key=lambda r: r.subject):
        resolved_pack = (
            pack
            if pack is not None
            else _REALIZER_PACK_BY_KIND.get(ri.kind, REALIZER_PACK_MECH)
        )
        suffix = _LOCK_SLOT_SUFFIX_BY_KIND.get(ri.kind, "geometry")
        rows.append(
            LockRow(
                slot=f"{ri.subject}.{suffix}",
                value=ri.digest,
                cause=f"realizer({resolved_pack})",
            )
        )
    return tuple(rows)


class StagedBuildReport(BaseModel):
    """The outcome of WO-42 deliverable 5's staged build loop (AD-25/D128):
    lower -> realize (producing new realized-domain IRs) -> re-lower with
    them, to a fixed point.

    ``final`` is the last :class:`BuildReport` (the fixed-point build --
    the one whose ``payload_json`` no longer names a realizable pending
    subject). ``iterations`` counts how many core ``check``/``compile``
    passes ran (always >= 1: the loop always runs at least once, even
    with no ``feature_programs`` supplied). ``realized_inputs`` is every
    realized-domain IR supplied to the FINAL pass, and ``lock_rows`` are
    their INV-21 lockfile rows (:func:`realized_lock_rows`).
    """

    model_config = ConfigDict(frozen=True)

    final: BuildReport
    iterations: int
    realized_inputs: tuple[compiler.RealizedInput, ...] = ()
    lock_rows: tuple[LockRow, ...] = ()


def staged_build(
    paths: tuple[str, ...],
    tier: BuildTier,
    feature_programs: Mapping[str, FeatureProgram] = MappingProxyType({}),
    *,
    elec_boards: Mapping[str, ElecBoardInputs] = MappingProxyType({}),
    registry: ModelRegistry | None = None,
    hooks: tuple[SensitivityHook, ...] = (),
    persist: bool = False,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
    max_iterations: int = _STAGED_BUILD_MAX_ITERATIONS,
    cost_profile: str | None = None,
    cost_record_paths: tuple[str, ...] = (),
    cost_as_of: datetime.date | None = None,
    frame_record_paths: tuple[str, ...] = (),
    plan_record_paths: tuple[str, ...] = (),
    si_record_paths: tuple[str, ...] = (),
    color: bool = False,
) -> Result[StagedBuildReport, OrchestratorError]:
    """Run the WO-42 deliverable 5 staged build loop over ``paths``.

    lower -> realize -> re-lower to a fixed point (AD-25/D128):

    1. Run :func:`build` with the realized inputs collected so far
       (initially empty -- the pre-realization placeholder path).
    2. Scan the resulting payload for subjects still lowered to the
       ``GeomExtract`` placeholder (:func:`_pending_geom_extract_subjects`)
       that a ``FeatureProgram`` backs: PIPELINE-PRODUCED first (WO-51
       deliverable 4 -- ``lower.programs`` emits programs with
       cavity-derived ``flow_paths``, promoted into the realizer
       contract by :func:`emitted_realizer_programs`, subject =
       selector), with the caller-supplied ``feature_programs`` mapping
       kept as an OVERRIDE channel (tests, hand fixtures -- the AD-22
       posture). A program the emitted IR cannot honestly complete is
       skipped by the converter with a named reason and its subject
       stays pending.
    3. Realize every such subject not already realized or already known
       to have failed realization this call (`realize_feature_program`,
       WO-42 deliverable 4's validate-and-emit pass), `put` each result
       into the WO-30 store (:func:`put_realized_geometry`), and fold it
       into the next iteration's realized-input set.
    4. Repeat from (1) until an iteration adds no new realized input --
       the fixed point. Termination proof (AD-25): a subject once
       realized is never re-realized by this loop (its digest is fixed
       going forward, matching D128's "unchanged realized-IR digest ->
       byte-identical re-lower", INV-10), and each iteration either
       realizes >= 1 previously-unrealized-or-unattempted subject or
       stops -- so the loop closes in at most
       ``len(feature_programs) + 1`` iterations, well inside
       ``max_iterations``'s safety cap (which exists only to fail loudly
       on a producer bug, not as the expected exit path).

    A subject whose realization fails (:class:`RealizeError`) is logged
    and left pending permanently for this call (never retried in a
    later iteration -- retrying an input that has not changed cannot
    produce a different outcome, and retrying forever would never
    converge); its dependent obligations stay honestly indeterminate,
    naming the missing IR, exactly as the D128 placeholder rule
    requires for a subject with no ``FeatureProgram`` supplied at all.

    Every iteration is logged with the subjects realized and the
    digests that changed (AD-25's own observability requirement).

    ``elec_boards`` (WO-24 close-out's residual, closed by this
    dispatch) is the elec leg's own caller-supplied realize-input map:
    unlike the mech leg, no in-payload placeholder marks a subject as
    "needs a real-KiCad layout" (`layout.realized` is not yet consumed
    by any re-lowering pass), so every supplied board is realized once,
    up front, rather than discovered from the build payload. A board
    whose real-KiCad gate is closed (:func:`real_kicad_available`) or
    whose layout run fails is left pending permanently for this call
    (never retried, same discipline as a failed mech subject) --
    `ship`'s elec backend then sees no `RealizedLayout` for that
    subject and reports the honest gap itself.

    ``frame_record_paths``/``plan_record_paths``/``si_record_paths`` mirror
    ``cost_record_paths`` exactly (same default, same forwarding into
    every iteration's inner :func:`build` call) -- the CLI-level record
    search-path gap this closes applies identically to all three
    contexts (cost/frame/plan), so `staged_build` accepts and forwards
    all three the same way.

    ``color`` (owner directive: optional TTY colors) is threaded
    straight through to every :func:`build` call this loop makes;
    defaults to ``False`` (byte-identical to before this parameter
    existed).
    """
    project_root = _project_root(paths)
    store = PayloadStore(project_root)
    # WO-99 deliverable 5 (charter 38 sec. 1.11): the realizer persists
    # its native side-artifact bytes (STEP, `.kicad_pcb`) into the
    # content-addressed `NativeArtifactStore` AT REALIZE TIME, so a later
    # `ship --build <report>` reading the SAME `.regolith/artifacts/`
    # root can never fail `native_artifact_not_found` for a subject the
    # report says it realized (the fresh-build path resolves the bytes
    # this same process wrote; the from-report path resolves the bytes
    # this call persisted to disk). Rooted at `project_root`, exactly
    # where `ship`'s own `NativeArtifactStore(artifact_root)` reads.
    native_store = NativeArtifactStore(project_root)
    realized_by_subject: dict[str, compiler.RealizedInput] = {}
    failed_subjects: set[str] = set()
    report: BuildReport | None = None
    iteration = 0

    while True:
        iteration += 1
        build_result = build(
            paths,
            tier,
            registry=registry,
            hooks=hooks,
            persist=persist,
            signer=signer,
            trust_keys=trust_keys,
            realized_inputs=tuple(realized_by_subject.values()),
            cost_profile=cost_profile,
            cost_record_paths=cost_record_paths,
            cost_as_of=cost_as_of,
            frame_record_paths=frame_record_paths,
            plan_record_paths=plan_record_paths,
            si_record_paths=si_record_paths,
            color=color,
        )
        if build_result.is_err:
            return Err(build_result.danger_err)
        report = build_result.danger_ok

        pending = _pending_geom_extract_subjects(report.payload_json)
        # WO-51 d4: pipeline-produced programs from the emitted payload,
        # with the caller channel as the override (caller wins per key).
        # ``paths`` (the same source set the core just built) lets a
        # cavity-less stock/saw_stock part's solid be recovered from
        # source text when the IR carries no op for it (a realizer
        # feature gap fix; see `programs.emitted_realizer_programs`'s
        # `source_paths` docstring paragraph).
        effective_programs: dict[str, FeatureProgram] = {
            **emitted_realizer_programs(report.payload_json, paths),
            **dict(feature_programs),
        }
        # A subject is realizable this iteration when either (a) a
        # pending `GeomExtract` flow edge names it (the D130 cavity-
        # query case), or (b) it has no flow_paths at all -- the WO-62
        # D171/AD-32 cavity-less convention (`<part>.<op_name>` keying,
        # `programs.emitted_realizer_programs`'s own docstring): such a
        # subject has nothing for a fluorite edge to ever consume, so
        # gating it on `pending` would mean it NEVER realizes.
        to_realize = sorted(
            subject
            for subject, program in effective_programs.items()
            if subject not in realized_by_subject
            and subject not in failed_subjects
            and (subject in pending or not program.flow_paths)
        )
        # The elec leg (WO-24 close-out residual): no in-payload
        # placeholder to scan for, so every caller-supplied board not
        # yet realized (or already known to have failed) is attempted
        # exactly once -- see the docstring's `elec_boards` paragraph.
        elec_to_realize = sorted(
            subject
            for subject in elec_boards
            if subject not in realized_by_subject and subject not in failed_subjects
        )
        if not to_realize and not elec_to_realize:
            _log.debug(
                "staged build: fixed point reached after %d iteration(s), "
                "%d realized input(s) supplied",
                iteration,
                len(realized_by_subject),
            )
            break
        if iteration >= max_iterations:
            _log.warning(
                "staged build: hit max_iterations=%d with %d subject(s) "
                "still pending realization: %s -- stopping without "
                "realizing them (dependent obligations stay indeterminate)",
                max_iterations,
                len(to_realize) + len(elec_to_realize),
                to_realize + elec_to_realize,
            )
            break

        changed_digests: list[str] = []
        for subject in to_realize:
            realized = realize_feature_program(effective_programs[subject])
            if realized.is_err:
                _log.warning(
                    "staged build: realization failed for subject=%r: %r "
                    "(not retried; dependent obligations stay indeterminate)",
                    subject,
                    realized.danger_err,
                )
                failed_subjects.add(subject)
                continue
            artifact = realized.danger_ok
            digest = put_realized_geometry(store, artifact)
            # Persist the native STEP bytes under the IR's own
            # `step_content_hash` (WO-99 d5) -- `put_at`, not a recompute,
            # so the store key never desyncs from the digest the backend
            # later resolves by.
            native_store.put_at(
                artifact.geometry.step_content_hash, artifact.step_bytes
            )
            realized_by_subject[subject] = compiler.RealizedInput(
                digest=digest,
                kind="geometry.realized",
                subject=subject,
                payload_bytes=artifact.geometry.model_dump_json().encode("utf-8"),
            )
            changed_digests.append(digest)

        for subject in elec_to_realize:
            board = elec_boards[subject]
            layout_result = (
                realize_elec_board_fake(
                    netlist_hash=board.netlist_hash,
                    board_outline_ref=board.board_outline_ref,
                    request=board.request,
                )
                if board.deterministic
                else realize_elec_board(
                    netlist_hash=board.netlist_hash,
                    board_outline_ref=board.board_outline_ref,
                    request=board.request,
                )
            )
            if layout_result.is_err:
                _log.warning(
                    "staged build: elec realization failed for subject=%r: "
                    "%r (not retried; dependent obligations stay "
                    "indeterminate)",
                    subject,
                    layout_result.danger_err,
                )
                failed_subjects.add(subject)
                continue
            layout = layout_result.danger_ok
            digest = put_realized_layout(store, layout)
            # Persist the native `.kicad_pcb` bytes the realizer wrote to
            # `output_pcb_path` into the content-addressed store (WO-99
            # d5), under the layout IR's own `kicad_pcb_content_hash`.
            # `put_verified` re-hashes the on-disk bytes and refuses a
            # mismatch (the file may have been touched between write and
            # read); a genuinely-missing file is logged, never crashed on
            # (an unrouted/failed export leaves the store un-primed, and
            # the backend's own `native_artifact_not_found` arm reports
            # it honestly at ship time).
            pcb_path = Path(board.request.output_pcb_path)
            if pcb_path.is_file():
                persisted = native_store.put_verified(
                    layout.kicad_pcb_content_hash, pcb_path.read_bytes()
                )
                if persisted.is_err:
                    _log.warning(
                        "staged build: native pcb persist failed for %s: %s",
                        subject,
                        persisted.danger_err.message,
                    )
            else:
                _log.warning(
                    "staged build: no pcb file at %s for %s; "
                    "native store not primed for it",
                    pcb_path,
                    subject,
                )
            realized_by_subject[subject] = compiler.RealizedInput(
                digest=digest,
                kind="layout.realized",
                subject=subject,
                payload_bytes=layout.model_dump_json().encode("utf-8"),
            )
            changed_digests.append(digest)

        _log.info(
            "staged build iteration %d: realized %d subject(s) subjects=%s digests=%s",
            iteration,
            len(changed_digests),
            to_realize + elec_to_realize,
            changed_digests,
        )

    assert report is not None  # the loop always runs >= 1 iteration
    realized_inputs = tuple(realized_by_subject.values())
    return Ok(
        StagedBuildReport(
            final=report,
            iterations=iteration,
            realized_inputs=realized_inputs,
            lock_rows=realized_lock_rows(realized_inputs),
        )
    )
