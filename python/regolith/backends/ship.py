"""``regolith ship``: the release gate + signed manufacturing package (WO-25).

The one driver that is ALLOWED to call the orchestrator (mirrors
`regolith.orchestrator.orchestrate`'s own layer): it runs a T3
``staged_build`` (INV-24 totality via ``release_gate``, WO-21 trust
floors already enforced inside it), refuses with a named diagnostic if
the gate fails, and otherwise drives every configured
:class:`~regolith.backends.framework.Backend` over the SAME
:class:`~regolith.backends.framework.BackendInputs`, folding every
emitted file into one signed :class:`~regolith.backends.manifest.ShipManifest`.

No individual backend decides anything; this module doesn't either --
it only gates and serializes what ``staged_build``/the lockfile/the
evidence cache already decided.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import blake3
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    ContractGraphPayload,
    Evidence,
    FlownetPayload,
    FramePayload,
    HarnessPayload,
    ItemizedEstimate,
    OptimizationTrace,
    RealizedAssembly,
    RealizedGeometry,
    RealizedLayout,
    WaiveLedger,
)
from regolith.backends import artifact_index
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.debug_taps import (
    TapHeaderRecord,
    TapSet,
    check_tap_agreement,
    derive_taps,
    explicit_taps_from_debug_spec,
    hdl_debug_pins_from_debug_spec,
    load_tap_header_record,
    resolve_explicit_taps,
    tap_candidates_from_payload,
)
from regolith.backends.drawings.producers import SiSheetRow
from regolith.backends.firmware import FirmwareArtifact
from regolith.backends.framework import Backend, BackendInputs, OutputFile
from regolith.backends.hdl import HdlBuildProducts
from regolith.backends.manifest import (
    ShipManifest,
    ShipProfile,
    build_manifest,
    sign_manifest,
    verify_file_hashes,
    verify_manifest,
)
from regolith.backends.package import package_side_files
from regolith.backends.parity import build_parity_report
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_resolve import resolve_record_search_paths
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet
from regolith.orchestrator.acceptance import acceptance_ledger_bytes
from regolith.orchestrator.lockfile import Lockfile, LockRow, render
from regolith.orchestrator.orchestrate import (
    ElecBoardInputs,
    StagedBuildReport,
    gate_summary_for,
    staged_build,
)
from regolith.orchestrator.tiers import BuildTier
from regolith.orchestrator.translate import si_sheet_fields
from regolith.progress import log_progress
from regolith.progress import start as progress_start
from regolith.realizer.elec.debug_placement import (
    TapPlacementPlan,
    derive_tap_placements,
)

_log = get_logger(__name__)

_MANIFEST_NAME = "manifest.json"
# WO-98 deliverable 3: the acceptance ledger written into every release
# package (D206 -- every accepted deviation, with basis + evidence pin,
# is auditable in the shipped bytes, content-addressed in the manifest).
_ACCEPTANCE_LEDGER_NAME = "acceptance_ledger.json"
# WO-125 (charter 40 sec. 3): the machine tap record, emitted into the
# `harness/` family a debug ship carries (WO-126 adds the family's
# procedure/expected-signal/capture siblings).
_TAP_MAP_RELPATH = "harness/tap_map.json"


def _design_hash(paths: tuple[str, ...], project_root: str) -> str:
    """A domain-tagged blake3 hash over every source path's bytes, sorted.

    Not a compiler-owned concept (none exists yet, checked
    `regolith._core`/`regolith.compiler`) -- this is WO-25's own
    "what exactly did we ship" pin, deliberately independent of the
    lockfile hash so a source edit that resolves to an unchanged
    lockfile (a no-op re-pin) still changes the design hash.

    Each source FILE is hashed by its ``project_root``-relative POSIX
    name plus its bytes, sorted by that name -- never by an absolute
    string, so the same design ships to the same ``design_hash`` from any
    checkout/worktree path (WO-106 determinism: the old absolute-path
    spelling drifted the manifest across environments for byte-identical
    content). A directory input is expanded to every recognized source
    file beneath it (a project root ships its whole design, not a
    content-free directory marker); a bare file is taken as-is. A path
    outside the project root falls back to its basename.
    """
    base = Path(project_root)
    if base.is_file():
        base = base.parent
    base = base.resolve()

    from regolith import compiler

    exts = frozenset(f".{ext}" for ext, _lang in compiler.extensions())

    def rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(base).as_posix()
        except (ValueError, OSError):
            return path.name

    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(f for f in p.rglob("*") if f.suffix in exts and f.is_file())
        else:
            files.append(p)

    hasher = blake3.blake3()
    hasher.update(b"regolith.backends.ship.design_hash")
    for path in sorted(files, key=rel):
        try:
            data = path.read_bytes()
        except OSError:
            data = rel(path).encode("utf-8", errors="replace")
        hasher.update(rel(path).encode("utf-8"))
        hasher.update(data)
    return "blake3:" + hasher.hexdigest()


def _lockfile_hash(lockfile: Lockfile) -> str:
    """The blake3 hash of the lockfile's own rendered (canonical) text."""
    return "blake3:" + blake3.blake3(render(lockfile).encode("ascii")).hexdigest()


# frob:doc docs/modules/py-backends.md#backends-ship
def si_rows_from_report(report: StagedBuildReport) -> dict[str, tuple[SiSheetRow, ...]]:
    """Derive the SI table sheet's rows (WO-78 deliverable 5) from the
    final build's own obligations + discharge results: one row per SI
    claim, subject-keyed by the owning declaration (the payload's
    snapshot scope for the obligation's `subject_ref`), every value
    attributed (computed value + margin from the evidence bit channel,
    model id, `obligation(<claim>)` cause with the evidence hash;
    an undischarged claim's row states its honest deferral instead --
    never a blank cell, never an invented number).
    """
    from regolith._schema.models import Obligation
    from regolith.harness.quantity import bits_to_f64

    if not report.final.payload_json:
        return {}
    payload = json.loads(report.final.payload_json)
    scope_of = {snap["hash"]: snap["scope"] for snap in payload.get("snapshots", ())}
    obligations = [
        Obligation.model_validate(raw) for raw in payload.get("obligations", ())
    ]
    results = {i: r for i, r in enumerate(report.final.results)}
    rows: dict[str, list[SiSheetRow]] = {}
    for index, obligation in enumerate(obligations):
        fields = si_sheet_fields(obligation)
        if fields is None:
            continue
        subject = scope_of.get(obligation.subject_ref, obligation.subject_ref[:12])
        result = results.get(index)
        evidence = result.evidence if result is not None else None
        if evidence is not None:
            computed = f"{bits_to_f64(evidence.value_bits):g}"
            margin = f"{bits_to_f64(evidence.margin_bits):g}"
            status = evidence.status.value
            model_id = evidence.model_id
            cause = f"obligation({fields['claim']}) evidence={evidence.hash[:12]}"
        elif result is not None and result.deferral is not None:
            computed, margin = "-", "-"
            status = f"deferred: {result.deferral.reason}"
            model_id = "-"
            cause = f"obligation({fields['claim']})"
        else:
            computed, margin, status, model_id = "-", "-", "unresolved", "-"
            cause = f"obligation({fields['claim']})"
        rows.setdefault(subject, []).append(
            SiSheetRow(
                claim=fields["claim"],
                net=fields["net"],
                target=fields["target"],
                stackup=fields["stackup"],
                layer=fields["layer"],
                geometry=fields["geometry"],
                computed=computed,
                margin=margin,
                status=status,
                model_id=model_id,
                cause=cause,
            )
        )
    derived = {subject: tuple(items) for subject, items in rows.items()}
    if derived:
        _log.info(
            "si_rows_from_report: %d subject(s), %d row(s)",
            len(derived),
            sum(len(v) for v in derived.values()),
        )
    return derived


# frob:doc docs/modules/py-backends.md#backends-ship
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def resolve_cost_estimates(
    report: StagedBuildReport, project_root: str
) -> dict[str, ItemizedEstimate]:
    """Resolve `report.final.cost_estimates` digests through the discharge-
    time `PayloadStore` into ``{subject: ItemizedEstimate}`` (WO-101
    residual, F124 bundle).

    `persist_estimates` keyed each pair ``("<subject>/<profile>", digest)``
    and wrote the payload under `<project_root>/.regolith/payloads/`. The
    BOM keys by subject, so we pick the estimate whose profile matches the
    build's resolved `cost_profile` (else the subject's single/first
    estimate). A digest that no longer resolves is logged and skipped --
    an honest empty cost cell, never a fabricated number.
    """
    from regolith.orchestrator.payload_store import PayloadStore

    pairs = report.final.cost_estimates
    if not pairs:
        return {}
    store = PayloadStore(project_root)
    preferred = report.final.cost_profile
    # subject -> (profile -> estimate), so we can prefer the build's profile.
    by_subject: dict[str, dict[str, ItemizedEstimate]] = {}
    for key, digest in pairs:
        subject, _, profile = key.partition("/")
        resolved = store.resolve(digest)
        if resolved.is_err:
            _log.warning(
                "ship: cost estimate %s for %s vanished from the store; "
                "cost cell stays empty",
                digest,
                key,
            )
            continue
        estimate = ItemizedEstimate.model_validate_json(resolved.danger_ok)
        by_subject.setdefault(subject, {})[profile] = estimate
    out: dict[str, ItemizedEstimate] = {}
    for subject, by_profile in by_subject.items():
        if preferred is not None and preferred in by_profile:
            out[subject] = by_profile[preferred]
        else:
            out[subject] = by_profile[sorted(by_profile)[0]]
    _log.debug("ship: resolved %d subject cost estimate(s)", len(out))
    return out


def _literalize_searched_sections(
    frames: dict[str, FramePayload], frame_lock_rows: tuple[LockRow, ...]
) -> dict[str, FramePayload]:
    """WO-65 (D218.2): overlay each section-search winner onto its
    FramePayload so the civil plan + member schedule render the pinned
    section instead of the `free` placeholder.

    The winners are the build's OWN lockfile rows: slot
    `<frame>.<member>.section`, value `<member>=<key>`, cause
    `optimize(mass_per_length, trace=...)` (`optimize.winner_lock_row`).
    A row with no matching frame/member (or whose member is not a `free`
    placeholder) is skipped, never invented -- a searched member is the
    ONLY section this overlay literalizes, and the objects are frozen so
    each hit yields a fresh `model_copy` rather than a mutation.
    """
    if not frame_lock_rows:
        return frames
    literalized = dict(frames)
    for row in frame_lock_rows:
        if not row.slot.endswith(".section"):
            continue
        for frame_name, frame in literalized.items():
            prefix = f"{frame_name}."
            if not row.slot.startswith(prefix):
                continue
            member_id = row.slot[len(prefix) : -len(".section")]
            _, _, winner_key = row.value.partition("=")
            if not winner_key:
                continue
            new_members = []
            changed = False
            for member in frame.members:
                if member.id == member_id and member.section.name == "free":
                    new_members.append(
                        member.model_copy(
                            update={
                                "section": member.section.model_copy(
                                    update={"name": winner_key}
                                )
                            }
                        )
                    )
                    changed = True
                    _log.info(
                        "civil sheet: literalized %s.%s section -> %s (%s)",
                        frame_name,
                        member_id,
                        winner_key,
                        row.cause,
                    )
                else:
                    new_members.append(member)
            if changed:
                literalized[frame_name] = frame.model_copy(
                    update={"members": new_members}
                )
            break
    return literalized


def _build_calc_book(report: StagedBuildReport, project_root: str):  # noqa: ANN201
    """Build the WO-114 `CalcBook` (D221) from a release report, or
    ``None`` when the obligation/result lists disagree in length (the
    honest skip `_calc_package_files` already logged). Shared by the
    calc package itself AND the WO-126 harness pack's expected-signal
    provenance (one build, two consumers -- D197's own idiom)."""
    from regolith._schema.models import Obligation
    from regolith.backends.calc import build_calc_book
    from regolith.harness.registry import default_registry

    payload = json.loads(report.final.payload_json or "{}")
    obligations = tuple(
        Obligation.model_validate(raw) for raw in payload.get("obligations", ())
    )
    snapshots = {snap["hash"]: snap["scope"] for snap in payload.get("snapshots", ())}
    results = tuple(report.final.results)
    if len(obligations) != len(results):
        _log.warning(
            "calc book: %d obligation(s) but %d result(s); calc book skipped",
            len(obligations),
            len(results),
        )
        return None
    project = Path(project_root).name or "package"
    registry = default_registry()
    return build_calc_book(
        project,
        obligations,
        results,
        report.final.acceptance,
        snapshots=snapshots,
        citations=registry.citations(),
        input_units=registry.input_units(),
        output_units=registry.output_units(),
        tier="release",
        # WO-139 (D258.3): the build's own INV-22 consumed-record
        # ledger rides into the calc package appendix so a
        # record-chain-DERIVED input (e.g. `fluids.dp`'s
        # roughness-derived `friction_factor`) leaves its record's
        # content hash in the SAME output the model citation renders
        # into, without needing a per-claim structural `given.
        # materials` channel (fluid claims never populate it).
        record_pins=report.final.fluid_record_pins,
        notes=report.final.fluid_derived_notes,
    )


def _calc_package_files(
    report: StagedBuildReport, project_root: str
) -> Result[tuple[OutputFile, ...], BackendError]:
    """Build the calc package (WO-114, D221) from a release report.

    Returns the ``calc/`` `OutputFile`s (empty when the calc book itself
    could not be built -- see :func:`_build_calc_book`) or `Err` when the
    WO-123 F141 drafting-audit gate refuses a calc sheet.
    """
    from regolith.backends.calc import calc_package_files

    book = _build_calc_book(report, project_root)
    if book is None:
        return Ok(())
    return calc_package_files(book)


# frob:doc docs/modules/py-backends.md#backends-ship
def derive_producer_inputs(
    report: StagedBuildReport,
    *,
    lockfile: Lockfile,
    cost_estimates: Mapping[str, ItemizedEstimate] = {},  # noqa: B006
    cost_profile: str | None = None,
    evidence: Mapping[str, Evidence] = {},  # noqa: B006 (frozen input, never mutated)
    geometry: Mapping[str, RealizedGeometry] = {},  # noqa: B006
    layouts: Mapping[str, RealizedLayout] = {},  # noqa: B006
    flownets: Mapping[str, FlownetPayload] = {},  # noqa: B006
    frames: Mapping[str, FramePayload] = {},  # noqa: B006
    harnesses: Mapping[str, HarnessPayload] = {},  # noqa: B006
    contract_graph: ContractGraphPayload | None = None,
    opt_traces: Mapping[str, OptimizationTrace] = {},  # noqa: B006
    assemblies: Mapping[str, RealizedAssembly] = {},  # noqa: B006
    firmware: Mapping[str, FirmwareArtifact] = {},  # noqa: B006
    hdl: Mapping[str, HdlBuildProducts] = {},  # noqa: B006
    native: NativeArtifactStore,
) -> BackendInputs:
    """Build the ONE `BackendInputs` triple every drawing/manufacturing
    producer reads, from a `StagedBuildReport` (D197: the shared
    derivation `regolith ship` and `regolith preview` both call -- no
    duplicated extraction logic between the two CLI verbs).

    `staged_build` already resolved every realized-domain IR the FINAL
    pass consumed (WO-42 deliverable 3/5) -- the geometry/layout/
    flownet/frame maps are derived from `report.realized_inputs`
    first, and the harness/contract-graph maps from
    `report.final.payload_json`'s own `"harnesses"`/`"contract_graph"`
    fields (WO-58 d1/d5, WO-61 d3 -- neither carries a `PayloadRef`,
    so neither is ever in `realized_inputs`). An explicit
    `geometry=`/`layouts=`/.../`contract_graph=` argument (tests, or a
    caller pinning an IR the build itself did not re-resolve, or
    `opt_traces` which the build never produces at all -- WO-58 d4)
    overrides a same-subject derived entry. `assemblies` (WO-96) is
    ALWAYS caller-supplied, like `opt_traces` -- `assembly.realized`
    carries no `PayloadRef` an obligation cites either
    (`regolith.realizer.mech.assembly`'s own integration-seam note), so
    there is nothing in `report.realized_inputs` to derive it from.
    `firmware`/`hdl` (WO-102) are ALWAYS caller-supplied for the same
    reason -- neither a `FirmwareArtifact` nor an `HdlBuildProducts`
    carries a `PayloadRef` any obligation cites.
    """
    derived_geometry: dict[str, RealizedGeometry] = {}
    derived_layouts: dict[str, RealizedLayout] = {}
    derived_flownets: dict[str, FlownetPayload] = {}
    derived_frames: dict[str, FramePayload] = {}
    for realized in report.realized_inputs:
        if realized.kind == "geometry.realized":
            derived_geometry[realized.subject] = RealizedGeometry.model_validate_json(
                realized.payload_bytes
            )
        elif realized.kind == "layout.realized":
            derived_layouts[realized.subject] = RealizedLayout.model_validate_json(
                realized.payload_bytes
            )
        elif realized.kind == "flownet":
            derived_flownets[realized.subject] = FlownetPayload.model_validate_json(
                realized.payload_bytes
            )
        elif realized.kind == "frame":
            derived_frames[realized.subject] = FramePayload.model_validate_json(
                realized.payload_bytes
            )
    derived_geometry.update(geometry)
    derived_layouts.update(layouts)
    derived_flownets.update(flownets)
    derived_frames.update(frames)

    derived_harnesses: dict[str, HarnessPayload] = {}
    derived_contract_graph: ContractGraphPayload | None = None
    if report.final.payload_json:
        payload_dict = json.loads(report.final.payload_json)
        harnesses_raw = payload_dict.get("harnesses", {})
        if isinstance(harnesses_raw, dict):
            for name, raw in harnesses_raw.items():
                derived_harnesses[name] = HarnessPayload.model_validate(raw)
        contract_graph_raw = payload_dict.get("contract_graph")
        if isinstance(contract_graph_raw, dict):
            derived_contract_graph = ContractGraphPayload.model_validate(
                contract_graph_raw
            )
        # WO-94 (D196.1): fluorite flownets never carry a `PayloadRef`
        # into `report.realized_inputs` the way mech/elec geometry
        # does -- a fluid `PayloadRef{kind:"flownet"}` resolves through
        # the SEPARATE `PayloadStore`/`_put_flownet_payloads` channel
        # (discharge-time), not the WO-42 realizer-promotion one this
        # function's `derived_flownets` loop above reads. Without this
        # fallback, `regolith preview`'s auto-derive (and any `--spec`
        # naming a fluid subject) can NEVER produce a P&ID sheet for
        # ANY fluorite corpus -- mirrors the harnesses/contract_graph
        # fallback immediately above (same `payload_json` source, same
        # "an explicit argument overrides" precedence via `.update()`
        # below).
        flownets_raw = payload_dict.get("flownets", {})
        if isinstance(flownets_raw, dict):
            for name, raw in flownets_raw.items():
                derived_flownets.setdefault(name, FlownetPayload.model_validate(raw))
        # WO-94 close-out follow-up: a calcite/civil frame's `PayloadRef
        # {kind:"frame"}` resolves the SAME way a fluid flownet does --
        # through the discharge-time `PayloadStore` channel, never
        # `report.realized_inputs` (the WO-42 realizer-promotion one
        # `derived_frames`'s loop above reads). Without this fallback,
        # `regolith preview`'s spec-less civil plan/frame sheet is
        # unreachable for ANY calcite corpus -- mirrors the flownets
        # fallback immediately above (same `payload_json` source, same
        # "an explicit argument overrides" precedence via `.update()`
        # below).
        frames_raw = payload_dict.get("frames", {})
        if isinstance(frames_raw, dict):
            for name, raw in frames_raw.items():
                derived_frames.setdefault(name, FramePayload.model_validate(raw))
    derived_harnesses.update(harnesses)
    if contract_graph is not None:
        derived_contract_graph = contract_graph

    # WO-65 (D218.2): literalize each section-search winner into the
    # FramePayload the civil drawing/schedule producers consume, so the
    # plan + member schedule render the PINNED section
    # (`civil_plan_section` reads `member.section.name`, which is the
    # `free` placeholder until this overlay). The winners are read from
    # the build's OWN lockfile rows (`report.final.frame_lock_rows`, the
    # `optimize(mass_per_length, trace=...)` cause the search already
    # accumulated) -- one home, never a re-run of the evaluator.
    derived_frames = _literalize_searched_sections(
        derived_frames, report.final.frame_lock_rows
    )

    return BackendInputs(
        lockfile=lockfile,
        evidence=evidence,
        geometry=derived_geometry,
        layouts=derived_layouts,
        flownets=derived_flownets,
        frames=derived_frames,
        harnesses=derived_harnesses,
        contract_graph=derived_contract_graph,
        opt_traces=opt_traces,
        assemblies=assemblies,
        si_rows=si_rows_from_report(report),
        firmware=firmware,
        hdl=hdl,
        native=native,
        cost_estimates=cost_estimates,
        cost_profile=cost_profile,
    )


class _DebugEmission(BaseModel):
    """The debug profile's derived tap surface, ready to thread onto
    `BackendInputs` and to serialize as the tap map (WO-125)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    tap_set: TapSet
    header: TapHeaderRecord | None
    capacity: int
    capacity_why: str
    placements: dict[str, TapPlacementPlan]
    hdl_pins: dict[str, tuple[str, ...]]
    board_subjects: tuple[str, ...]
    firmware_subjects: tuple[str, ...]
    hdl_subjects: tuple[str, ...]


def _prepare_debug_emission(
    report: StagedBuildReport,
    debug_spec: Mapping[str, object] | None,
    project_root: str,
    inputs: BackendInputs,
    backend_names: frozenset[str],
) -> Result[_DebugEmission, BackendError]:
    """Derive the debug profile's whole tap surface (D237.2) BEFORE any
    backend runs: candidates from the payload's own claim-named nets
    (the census truth), explicit taps + declared HDL pins from the ship
    spec's ``"debug"`` block, capacity from THE header record (charter
    40 sec. 4), placement plans through the realizer seam.

    Channel allocation only happens where an emitted artifact family
    can actually CARRY a tap (INV-32's own precondition: the map never
    overstates the hardware, charter 40 sec. 5): a board or firmware
    family carries every allocated channel; an HDL-only package is
    capped at its widest declared debug-pin set; a package with no
    augmentable family allocates zero channels, honestly.
    """
    payload = json.loads(report.final.payload_json or "{}")
    candidates = tap_candidates_from_payload(payload)

    block = debug_spec if isinstance(debug_spec, dict) else {}
    explicit_result = explicit_taps_from_debug_spec(block)
    if explicit_result.is_err:
        return Err(explicit_result.danger_err)
    resolved_result = resolve_explicit_taps(explicit_result.danger_ok, candidates)
    if resolved_result.is_err:
        return Err(resolved_result.danger_err)
    explicit = resolved_result.danger_ok
    hdl_pins_all = hdl_debug_pins_from_debug_spec(block)

    record_paths = resolve_record_search_paths(project_root)
    header_result = load_tap_header_record(project_root, record_paths)
    if header_result.is_err:
        return Err(header_result.danger_err)
    header = header_result.danger_ok

    # A family can only CARRY a tap when its emitting backend is
    # actually registered for this ship (a layout with no boards
    # backend emits nothing -- claiming carriage there would make
    # INV-32 refuse an honest package).
    board_subjects = tuple(sorted(inputs.layouts)) if "boards" in backend_names else ()
    firmware_subjects = (
        tuple(sorted(inputs.firmware)) if "firmware" in backend_names else ()
    )
    hdl_subjects = tuple(sorted(inputs.hdl)) if "hdl" in backend_names else ()
    hdl_pins = {
        subject: pins
        for subject, pins in hdl_pins_all.items()
        if subject in hdl_subjects and pins
    }

    if header is None:
        capacity = 0
        capacity_why = (
            "no std.elec tap_header record resolvable for this project "
            "(charter 40 sec. 4's ONE pinout home) -- zero channels "
            "allocatable, every candidate a named unallocated row"
        )
    elif board_subjects or firmware_subjects:
        capacity = header.channels
        capacity_why = (
            f"header record {header.key} provides {header.channels} "
            "channel(s); a board/firmware family carries every allocated "
            "channel"
        )
    elif hdl_pins:
        widest = max(len(pins) for pins in hdl_pins.values())
        capacity = min(header.channels, widest)
        capacity_why = (
            f"HDL-only package: capacity is min(header {header.channels}, "
            f"widest declared debug-pin set {widest}) so every allocated "
            "channel is actually routable (charter 40 sec. 5)"
        )
    else:
        capacity = 0
        capacity_why = (
            "no augmentable artifact family in this package (no board "
            "layout, no firmware, no HDL subject with declared debug "
            "pins) -- zero channels allocated, honestly (charter 40 "
            "sec. 5); candidates are named unallocated rows"
        )

    tap_result = derive_taps(candidates, explicit, capacity)
    if tap_result.is_err:
        return Err(tap_result.danger_err)
    tap_set = tap_result.danger_ok

    placements: dict[str, TapPlacementPlan] = {}
    if header is not None and tap_set.taps:
        for subject in board_subjects:
            placements[subject] = derive_tap_placements(subject, tap_set, header)

    _log.info(
        "debug emission: %d tap(s) allocated / %d unallocated "
        "(capacity=%d; boards=%d firmware=%d hdl-with-pins=%d)",
        len(tap_set.taps),
        len(tap_set.unallocated),
        capacity,
        len(board_subjects),
        len(firmware_subjects),
        len(hdl_pins),
    )
    return Ok(
        _DebugEmission(
            tap_set=tap_set,
            header=header,
            capacity=capacity,
            capacity_why=capacity_why,
            placements=placements,
            hdl_pins=hdl_pins,
            board_subjects=board_subjects,
            firmware_subjects=firmware_subjects,
            hdl_subjects=hdl_subjects,
        )
    )


def _tap_map_bytes(debug: _DebugEmission) -> bytes:
    """Serialize the canonical tap map (charter 40 sec. 3): channel ->
    kind -> target path -> connector pin, plus the header record it
    cites, per-family carriage, named unallocated rows, and named
    family absences. Deterministic (sorted keys, no timestamps)."""
    header_doc: dict[str, object]
    if debug.header is None:
        header_doc = {
            "present": False,
            "reason": debug.capacity_why,
        }
    else:
        header_doc = {
            "present": True,
            "record": debug.header.key,
            "source": "std.elec records (class=tap_header)",
            "channels": debug.header.channels,
            "positions": debug.header.positions,
            "pitch_mm": debug.header.pitch_mm,
            "connector": debug.header.connector,
            "ordering": debug.header.ordering,
            "ground": debug.header.ground,
            "keying": debug.header.keying,
            "reference": debug.header.reference,
        }
    taps: list[dict[str, object]] = []
    for tap in debug.tap_set.taps:
        hdl_carriers = {
            subject: pins[tap.channel]
            for subject, pins in sorted(debug.hdl_pins.items())
            if tap.channel < len(pins)
        }
        taps.append(
            {
                "channel": tap.channel,
                "kind": tap.kind,
                "target_path": tap.target_path,
                "why": tap.why,
                "source": tap.source,
                "connector_pin": (
                    debug.header.connector_pin(tap.channel)
                    if debug.header is not None
                    else None
                ),
                "artifacts": {
                    "board_test_points": list(debug.board_subjects),
                    "firmware_table": list(debug.firmware_subjects),
                    "hdl_pins": hdl_carriers,
                },
            }
        )
    absences = {
        "boards": (
            None
            if debug.board_subjects
            else "no board layout in this package (no tap header placed)"
        ),
        "firmware": (
            None
            if debug.firmware_subjects
            else "design ships no firmware (no trace-hook table)"
        ),
        "hdl": (
            None
            if debug.hdl_pins
            else (
                "no HDL subject with declared debug pins "
                '(ship spec "debug".hdl_debug_pins)'
                if debug.hdl_subjects
                else "design ships no HDL"
            )
        ),
    }
    doc = {
        "schema": "regolith.tap_map.v1",
        "profile": "debug",
        "header": header_doc,
        "capacity": {"channels": debug.capacity, "why": debug.capacity_why},
        "taps": taps,
        "unallocated": [
            {
                "target_path": row.target_path,
                "kind": row.kind,
                "why": row.why,
                "reason": row.reason,
            }
            for row in debug.tap_set.unallocated
        ],
        "family_absences": absences,
    }
    return json.dumps(
        doc,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        indent=2,
    ).encode("ascii")


# frob:doc docs/modules/py-backends.md#backends-ship
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def ship(
    paths: tuple[str, ...],
    backends: Mapping[str, Backend],
    out_dir: str,
    *,
    lockfile: Lockfile,
    geometry: Mapping[str, RealizedGeometry] = {},  # noqa: B006 (frozen input, never mutated)
    layouts: Mapping[str, RealizedLayout] = {},  # noqa: B006
    flownets: Mapping[str, FlownetPayload] = {},  # noqa: B006
    frames: Mapping[str, FramePayload] = {},  # noqa: B006
    harnesses: Mapping[str, HarnessPayload] = {},  # noqa: B006
    contract_graph: ContractGraphPayload | None = None,
    opt_traces: Mapping[str, OptimizationTrace] = {},  # noqa: B006
    assemblies: Mapping[str, RealizedAssembly] = {},  # noqa: B006
    firmware: Mapping[str, FirmwareArtifact] = {},  # noqa: B006
    hdl: Mapping[str, HdlBuildProducts] = {},  # noqa: B006
    evidence: Mapping[str, Evidence] = {},  # noqa: B006
    native: NativeArtifactStore | None = None,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
    prebuilt: StagedBuildReport | None = None,
    elec_boards: Mapping[str, ElecBoardInputs] = MappingProxyType({}),
    profile: ShipProfile = "release",
    debug_spec: Mapping[str, object] | None = None,
) -> Result[ShipManifest, BackendError]:
    """Run the T3 release gate, then every backend, then sign the manifest.

    ``backends`` maps a package name (``"mech"``, ``"elec"``) to its
    :class:`~regolith.backends.framework.Backend`; every backend's
    output lands under ``out_dir/<name>/``. Refuses (``Err``) before
    running any backend if the release gate fails -- the ship package
    never partially writes a release that was not actually clean
    (regolith/09, INV-24).

    ``prebuilt`` (WO-43 deliverable 3) is a :class:`StagedBuildReport`
    already produced by a prior ``regolith build --release`` run (read
    back from its ``--out`` directory by the CLI's ``ship --build``
    flag): when supplied, this call skips re-running :func:`staged_build`
    entirely and gates on ``prebuilt`` directly, so the same release
    pass is never repeated. ``None`` (the default) keeps the original
    behavior of running :func:`staged_build` itself.

    ``elec_boards`` (WO-42 deliverable 5's elec leg) is only consumed
    when ``prebuilt`` is ``None`` -- a caller supplying an already-run
    report owns whatever boards it realized when it ran ``staged_build``
    itself; passing ``elec_boards`` alongside ``prebuilt`` is a no-op.

    ``harnesses`` (WO-58 deliverable 1/5) is the `diagram.elec_blocks`
    producer's input. Unlike ``geometry``/``layouts``/``flownets``/
    ``frames``, a `HarnessPayload` carries no `PayloadRef` (WO-34's own
    D3 note: no obligation ever cites one), so it never enters
    ``report.realized_inputs`` through the WO-30 store -- it is derived
    straight from ``report.final.payload_json``'s ``"harnesses"`` field
    instead (that field is populated for every tier, WO-42 deliverable
    5), the same "derive first, explicit arg overrides" convention the
    other four maps already use.

    ``contract_graph`` (WO-61 deliverable 3) is the `diagram.
    contract_graph` producer's input: like ``harnesses``, a
    `ContractGraphPayload` carries no `PayloadRef` (D165/D167 -- no
    obligation ever cites one), so it is derived straight from
    ``report.final.payload_json``'s ``"contract_graph"`` field (single
    object, not a per-subject map -- `regolith-lower` emits exactly one
    per build); an explicit ``contract_graph=`` argument overrides the
    derived value.

    ``opt_traces`` (WO-58 deliverable 4) is the `diagram.opt_trace`
    producer's input. An `OptimizationTrace` is never part of
    `BuildPayload` (it is `optimize`'s own separate T2-tier output,
    AD-30) -- there is nothing to derive from ``report``, so this map
    is caller-supplied only.

    ``assemblies`` (WO-96) is the `instructions.AssemblySteps` producer's
    input, keyed by subject like ``opt_traces`` -- always caller-supplied
    (see :func:`derive_producer_inputs`'s docstring for why).

    ``firmware``/``hdl`` (WO-102) are the `FirmwareBackend`/`HdlBackend`
    inputs, keyed by subject like ``opt_traces``/``assemblies`` --
    always caller-supplied (same reason: no `PayloadRef`).

    ``profile`` (WO-125, D237.1) selects the EMISSION profile. It never
    changes what the release gate above already decided (verdict math
    is untouchable, D206/D220.1); a ``"debug"`` profile still requires
    a clean release gate to ship at all (the gate check above runs
    identically either way). With ``profile="debug"`` the emitted
    artifact set is AUGMENTED (charter 40 sec. 1): the derived tap set
    threads onto ``BackendInputs`` (board tap-placement plans, the
    firmware trace-hook table, the HDL tap module), the canonical
    ``harness/tap_map.json`` is emitted, and INV-32 (tap-map/artifact
    agreement) is checked over the EMITTED bytes -- a mismatch refuses
    the ship. A release-profile ship never populates any of it, so the
    release artifact set stays byte-identical by construction.

    ``debug_spec`` is the ship spec's ``"debug"`` block (the WO-102
    spec-block idiom): explicit taps (``taps``) win channels first and
    declared HDL debug pins (``hdl_debug_pins``) are the tap module's
    only routing targets. Ignored (with a log) on a release ship.
    """
    project_root = paths[0] if paths else "."
    if prebuilt is not None:
        report: StagedBuildReport = prebuilt
    else:
        record_paths = resolve_record_search_paths(project_root)
        gate = staged_build(
            paths,
            BuildTier.RELEASE,
            signer=signer,
            trust_keys=trust_keys,
            elec_boards=elec_boards,
            cost_record_paths=record_paths,
            frame_record_paths=record_paths,
            plan_record_paths=record_paths,
        )
        if gate.is_err:
            _log.error("ship: staged_build failed: %s", gate.danger_err.message)
            return Err(
                BackendError(kind="build_failed", message=gate.danger_err.message)
            )
        report = gate.danger_ok
    if not report.final.ok or not report.final.release_ok:
        unresolved = len(report.final.unresolved)
        _log.warning(
            "ship REFUSED: release gate not clean (build_ok=%s release_ok=%s "
            "unresolved=%d)",
            report.final.ok,
            report.final.release_ok,
            unresolved,
        )
        return Err(
            BackendError(
                kind="release_not_ready",
                message=f"regolith ship refused: build_ok={report.final.ok} "
                f"release_ok={report.final.release_ok} "
                f"unresolved={unresolved} (--release must pass first)",
            )
        )

    store = native if native is not None else NativeArtifactStore(project_root)
    # WO-101 residual (F124 bundle): resolve the build's persisted cost
    # estimates so the BOM backend's cost columns populate on a real ship
    # (was: an empty map -> honest-but-always-empty cost cells).
    cost_estimates = resolve_cost_estimates(report, project_root)
    inputs = derive_producer_inputs(
        report,
        lockfile=lockfile,
        evidence=evidence,
        geometry=geometry,
        layouts=layouts,
        flownets=flownets,
        frames=frames,
        harnesses=harnesses,
        contract_graph=contract_graph,
        opt_traces=opt_traces,
        assemblies=assemblies,
        firmware=firmware,
        hdl=hdl,
        native=store,
        cost_estimates=cost_estimates,
        cost_profile=report.final.cost_profile,
    )

    # WO-125 (charter 40 sec. 1): the debug profile derives its whole
    # tap surface ONCE here, then threads it onto the SAME
    # `BackendInputs` every backend reads -- backends only serialize it
    # (regolith/07 sec. 6). Assignment after construction is the plain
    # inputs-holder idiom (`BackendInputs` is deliberately not frozen);
    # a release ship leaves every field at its empty default, keeping
    # the release artifact set byte-identical by construction.
    debug: _DebugEmission | None = None
    if profile == "debug":
        debug_result = _prepare_debug_emission(
            report, debug_spec, project_root, inputs, frozenset(backends)
        )
        if debug_result.is_err:
            _log.error(
                "ship: debug emission refused: %s",
                debug_result.danger_err.message,
            )
            return Err(debug_result.danger_err)
        debug = debug_result.danger_ok
        inputs.debug_taps = debug.tap_set
        inputs.tap_header = debug.header
        inputs.tap_placements = debug.placements
        inputs.hdl_debug_pins = debug.hdl_pins
    elif debug_spec is not None:
        _log.info(
            'ship: a "debug" spec block is present but profile=%r -- '
            "ignored (taps are a debug-profile augmentation, D237.1)",
            profile,
        )

    all_files: list[OutputFile] = []
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    # WO-119 (D228): the per-artifact emission loop was silent -- a
    # multi-backend, multi-file ship gave a progress-agnostic consumer
    # nothing to render while files were written. One DEBUG progress
    # record per artifact file (done/total scoped to its own backend
    # family, since the total file count is only known per-backend --
    # `backend.produce` runs one family at a time).
    ship_started = progress_start()
    for name, backend in sorted(backends.items()):
        produced = backend.produce(inputs)
        if produced.is_err:
            _log.error("ship: backend %s failed: %s", name, produced.danger_err.message)
            return Err(produced.danger_err)
        files = tuple(produced.danger_ok)
        for i, output in enumerate(files, start=1):
            namespaced = output.model_copy(
                update={"relpath": f"{name}/{output.relpath}"}
            )
            log_progress(
                phase="ship",
                subject=namespaced.relpath,
                done=i,
                total=len(files),
                started=ship_started,
            )
            namespaced.write_under(out_path)
            all_files.append(namespaced)

    # WO-114 (D221): the calc package + audit index -- one calc sheet per
    # discharged obligation plus a total obligation accounting that maps
    # every obligation to exactly one disposition, cross-linking the
    # WO-98 acceptance ledger. Emitted for EVERY project (even the ones
    # that discharge zero), so the audit trail always ships. Built from
    # the report's own obligations/results/acceptance -- ship's layer is
    # allowed to read the report (it already does for the ledgers below).
    project = Path(project_root).name or "package"
    calc_files_result = _calc_package_files(report, project_root)
    if calc_files_result.is_err:
        _log.error(
            "ship: calc package failed the drafting audit: %s",
            calc_files_result.danger_err.message,
        )
        return Err(calc_files_result.danger_err)
    calc_files = calc_files_result.danger_ok
    for calc_file in calc_files:
        calc_file.write_under(out_path)
    all_files.extend(calc_files)

    # WO-125/WO-126 (charter 40 sec. 3): the whole `harness/` bring-up
    # pack -- the canonical tap map (WO-125's own bytes, unmodified: one
    # truth), the expected-signal manifest (D224 provenance or a named
    # absence), the bring-up procedure, and per-kind capture configs.
    # INV-32 (tap-map/artifact agreement) is checked over the EMITTED
    # bytes first -- every map row in at least one artifact, every
    # artifact tap in the map -- then the WO-126 provenance check (every
    # expected-signal ref resolves inside THIS package's `calc/` family).
    # Either mismatch REFUSES the ship (a package whose harness pack
    # overstates its own hardware or fabricates an expectation never
    # leaves this function).
    if debug is not None:
        from regolith.backends.harness_pack import check_expectation_provenance
        from regolith.backends.harness_pack import harness_files as _harness_files

        tap_map_bytes = _tap_map_bytes(debug)
        agreement = check_tap_agreement(tap_map_bytes, tuple(all_files))
        if agreement.is_err:
            _log.error("ship: %s", agreement.danger_err.message)
            return Err(agreement.danger_err)
        calc_book = _build_calc_book(report, project_root)
        harness = _harness_files(
            project,
            tap_map_bytes,
            debug.tap_set,
            debug.header,
            json.loads(report.final.payload_json or "{}"),
            tuple(report.final.results),
            calc_book,
        )
        expected_file = next(
            f for f in harness if f.relpath == "harness/expected_signals.json"
        )
        provenance_check = check_expectation_provenance(
            expected_file.content, calc_files
        )
        if provenance_check.is_err:
            _log.error("ship: %s", provenance_check.danger_err.message)
            return Err(provenance_check.danger_err)
        for hfile in harness:
            hfile.write_under(out_path)
        all_files.extend(harness)
        _log.info(
            "ship: harness pack emitted (%d file(s), %d tap(s), %d unallocated) "
            "-- INV-32 and provenance hold",
            len(harness),
            len(debug.tap_set.taps),
            len(debug.tap_set.unallocated),
        )

    # WO-99 d4: the one `dist/<project>/` layout -- fold the deterministic
    # index + gate/parity/acceptance ledgers in beside the per-family
    # artifact files, each content-addressed and re-verified by
    # `ship --verify` exactly like an artifact. The acceptance ledger is
    # the REAL WO-98 one (the placeholder default in package_side_files
    # is superseded by the gate's own AcceptanceOutcome).
    gate = gate_summary_for(report.final)
    final_payload = json.loads(report.final.payload_json or "{}")
    ledger = WaiveLedger.model_validate(final_payload.get("ledger", {"entries": []}))
    results = tuple(report.final.results) + tuple(report.final.unresolved)
    parity = build_parity_report(lockfile, results, ledger)
    side_files = package_side_files(
        project,
        gate,
        parity,
        tuple(all_files),
        acceptance_ledger=acceptance_ledger_bytes(report.final.acceptance),
    )
    for side in side_files:
        side.write_under(out_path)
    all_files.extend(side_files)
    if report.final.acceptance.deviations:
        _log.info(
            "ship: %d accepted deviation(s) recorded in %s",
            len(report.final.acceptance.deviations),
            _ACCEPTANCE_LEDGER_NAME,
        )

    # WO-130 (D244/AD-41): the universal artifact index -- one typed row
    # per emitted file, described well enough to render without a viewer
    # ever needing to know the family (charter 42 sec. 6). Built over
    # EVERY file emitted so far (per-family artifacts + this package's
    # own ledgers); an unregistered family REFUSES the ship (a loud
    # registration error, never a silently incomplete index, ruling 2).
    index_result = artifact_index.build_index(project, tuple(all_files))
    if index_result.is_err:
        _log.error("ship: %s", index_result.danger_err.message)
        return Err(index_result.danger_err)
    index = index_result.danger_ok
    # `artifact_index.json` never lists itself (its own hash cannot
    # describe its own bytes) -- the SAME "never lists itself" rule
    # `package.build_index`'s `index.md` docstring already states, now
    # shared by this second index file.
    consistency = artifact_index.check_index_consistency(index, tuple(all_files))
    if consistency.is_err:
        _log.error("ship: %s", consistency.danger_err.message)
        return Err(consistency.danger_err)
    index_file = OutputFile.of(
        artifact_index.INDEX_FILENAME, artifact_index.index_bytes(index)
    )
    index_file.write_under(out_path)
    all_files.append(index_file)
    _log.info("ship: artifact index built (%d row(s))", len(index.rows))

    rollup = tuple(
        sorted(
            (r.subject_ref, r.evidence.status if r.evidence else "indeterminate")
            for r in report.final.results
        )
    )
    manifest = build_manifest(
        design_hash=_design_hash(paths, project_root),
        lockfile_hash=_lockfile_hash(lockfile),
        evidence_rollup=rollup,
        files=tuple(all_files),
        profile=profile,
    )
    if signer is not None:
        manifest = sign_manifest(manifest, signer)
    else:
        _log.warning("ship: no signer supplied; manifest emitted UNSIGNED")

    manifest_bytes = json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        indent=2,
    ).encode("ascii")
    (out_path / _MANIFEST_NAME).write_bytes(manifest_bytes)
    _log.info(
        "ship: package written to %s (%d files, signed=%s)",
        out_dir,
        len(all_files),
        manifest.signature is not None,
    )
    return Ok(manifest)


# frob:doc docs/modules/py-backends.md#backends-ship
def verify(out_dir: str, trust_keys: TrustKeySet) -> Result[None, BackendError]:
    """``regolith ship --verify``: re-hash every file and check the signature."""
    out_path = Path(out_dir)
    manifest_path = out_path / _MANIFEST_NAME
    if not manifest_path.is_file():
        return Err(
            BackendError(
                kind="manifest_not_found", message=f"no manifest at {manifest_path}"
            )
        )
    manifest = ShipManifest.model_validate_json(manifest_path.read_text())

    sig_check = verify_manifest(manifest, trust_keys)
    if sig_check.is_err:
        return sig_check

    files: list[OutputFile] = []
    for entry in manifest.files:
        file_path = out_path / entry.relpath
        if not file_path.is_file():
            return Err(
                BackendError(
                    kind="file_missing",
                    message=f"manifest lists missing file {entry.relpath}",
                )
            )
        files.append(OutputFile.of(entry.relpath, file_path.read_bytes()))
    hash_check = verify_file_hashes(manifest, tuple(files))
    if hash_check.is_err:
        return hash_check
    _log.info("ship --verify: %s OK (%d files)", out_dir, len(files))
    return Ok(None)
