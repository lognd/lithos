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
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.producers import SiSheetRow
from regolith.backends.firmware import FirmwareArtifact
from regolith.backends.framework import Backend, BackendInputs, OutputFile
from regolith.backends.hdl import HdlBuildProducts
from regolith.backends.manifest import (
    ShipManifest,
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

_log = get_logger(__name__)

_MANIFEST_NAME = "manifest.json"
# WO-98 deliverable 3: the acceptance ledger written into every release
# package (D206 -- every accepted deviation, with basis + evidence pin,
# is auditable in the shipped bytes, content-addressed in the manifest).
_ACCEPTANCE_LEDGER_NAME = "acceptance_ledger.json"


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


def _calc_package_files(
    report: StagedBuildReport, project_root: str
) -> tuple[OutputFile, ...]:
    """Build the calc package (WO-114, D221) from a release report.

    Aligns the payload's obligation list with ``final.results`` (index-
    aligned, the same pairing `si_rows_from_report` relies on), reads the
    acceptance outcome the gate already computed, and resolves the model
    citation map once from the default registry (the minimal accessor,
    D221 d4). Returns the ``calc/`` `OutputFile`s.
    """
    from regolith._schema.models import Obligation
    from regolith.backends.calc import build_calc_book, calc_package_files
    from regolith.harness.registry import default_registry

    payload = json.loads(report.final.payload_json or "{}")
    obligations = tuple(
        Obligation.model_validate(raw) for raw in payload.get("obligations", ())
    )
    snapshots = {snap["hash"]: snap["scope"] for snap in payload.get("snapshots", ())}
    results = tuple(report.final.results)
    if len(obligations) != len(results):
        _log.warning(
            "calc package: %d obligation(s) but %d result(s); calc book skipped",
            len(obligations),
            len(results),
        )
        return ()
    project = Path(project_root).name or "package"
    book = build_calc_book(
        project,
        obligations,
        results,
        report.final.acceptance,
        snapshots=snapshots,
        citations=default_registry().citations(),
        tier="release",
    )
    return calc_package_files(book)


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

    all_files: list[OutputFile] = []
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    for name, backend in sorted(backends.items()):
        produced = backend.produce(inputs)
        if produced.is_err:
            _log.error("ship: backend %s failed: %s", name, produced.danger_err.message)
            return Err(produced.danger_err)
        for output in produced.danger_ok:
            namespaced = output.model_copy(
                update={"relpath": f"{name}/{output.relpath}"}
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
    calc_files = _calc_package_files(report, project_root)
    for calc_file in calc_files:
        calc_file.write_under(out_path)
    all_files.extend(calc_files)

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
    project = Path(project_root).name or "package"
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
