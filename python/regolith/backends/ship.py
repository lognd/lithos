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
    OptimizationTrace,
    RealizedAssembly,
    RealizedGeometry,
    RealizedLayout,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import Backend, BackendInputs, OutputFile
from regolith.backends.manifest import (
    ShipManifest,
    build_manifest,
    sign_manifest,
    verify_file_hashes,
    verify_manifest,
)
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_resolve import resolve_record_search_paths
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet
from regolith.orchestrator.lockfile import Lockfile, render
from regolith.orchestrator.orchestrate import (
    ElecBoardInputs,
    StagedBuildReport,
    staged_build,
)
from regolith.orchestrator.tiers import BuildTier

_log = get_logger(__name__)

_MANIFEST_NAME = "manifest.json"


def _design_hash(paths: tuple[str, ...]) -> str:
    """A domain-tagged blake3 hash over every source path's bytes, sorted.

    Not a compiler-owned concept (none exists yet, checked
    `regolith._core`/`regolith.compiler`) -- this is WO-25's own
    "what exactly did we ship" pin, deliberately independent of the
    lockfile hash so a source edit that resolves to an unchanged
    lockfile (a no-op re-pin) still changes the design hash.
    """
    hasher = blake3.blake3()
    hasher.update(b"regolith.backends.ship.design_hash")
    for path in sorted(paths):
        try:
            data = Path(path).read_bytes()
        except OSError:
            data = path.encode("utf-8", errors="replace")
        hasher.update(path.encode("utf-8"))
        hasher.update(data)
    return "blake3:" + hasher.hexdigest()


def _lockfile_hash(lockfile: Lockfile) -> str:
    """The blake3 hash of the lockfile's own rendered (canonical) text."""
    return "blake3:" + blake3.blake3(render(lockfile).encode("ascii")).hexdigest()


def derive_producer_inputs(
    report: StagedBuildReport,
    *,
    lockfile: Lockfile,
    evidence: Mapping[str, Evidence] = {},  # noqa: B006 (frozen input, never mutated)
    geometry: Mapping[str, RealizedGeometry] = {},  # noqa: B006
    layouts: Mapping[str, RealizedLayout] = {},  # noqa: B006
    flownets: Mapping[str, FlownetPayload] = {},  # noqa: B006
    frames: Mapping[str, FramePayload] = {},  # noqa: B006
    harnesses: Mapping[str, HarnessPayload] = {},  # noqa: B006
    contract_graph: ContractGraphPayload | None = None,
    opt_traces: Mapping[str, OptimizationTrace] = {},  # noqa: B006
    assemblies: Mapping[str, RealizedAssembly] = {},  # noqa: B006
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
    derived_harnesses.update(harnesses)
    if contract_graph is not None:
        derived_contract_graph = contract_graph

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
        native=native,
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
        native=store,
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

    rollup = tuple(
        sorted(
            (r.subject_ref, r.evidence.status if r.evidence else "indeterminate")
            for r in report.final.results
        )
    )
    manifest = build_manifest(
        design_hash=_design_hash(paths),
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
