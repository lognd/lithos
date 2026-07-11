"""``regolith preview``: viewable artifacts without weakening INV-24 (D197).

``ship`` stays total (INV-24: a signed manufacturing package must be
total, no draft flag, no gate bypass, ever) -- but the drawing/diagram
producers (WO-50/58/61: sheets, contract graphs, opt traces) are only
reachable inside ``ship --spec``, so a design in progress has no way to
see its own review artifacts before the release gate is clean. This
module runs the SAME producer set `regolith.backends.ship` drives
(:func:`regolith.backends.ship.derive_producer_inputs`,
:func:`regolith.backends.drawings.backend.model_for_spec`,
:func:`regolith.backends.instructions.steps_for_assembly` -- WO-96),
stamps every sheet/document with the honest gate state through its own
model (never by post-editing a rendered file), and writes them to an
output directory alongside a machine-readable ``gate_summary.json`` --
no signing, no manifest, no BOM/fab-note packages (those stay
ship-only, regolith/07 sec. 6).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Ok, Result

from regolith._schema.models import RealizedAssembly
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.backend import (
    DrawingSpec,
    files_for_model,
    model_for_spec,
    stamp_model,
)
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.backends.instructions import (
    files_for_steps,
    stamp_steps,
    steps_for_assembly,
)
from regolith.backends.ship import derive_producer_inputs
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.orchestrate import (
    GateSummary,
    StagedBuildReport,
    gate_summary_for,
)

_log = get_logger(__name__)

_GATE_SUMMARY_NAME = "gate_summary.json"


class PreviewOutcome(BaseModel):
    """What `run_preview` wrote: the relpaths of every artifact file
    (drawing quintets plus ``gate_summary.json``), which `DrawingSpec`s
    (if any) could not resolve an input and were honestly skipped (never
    crashed on), and the `GateSummary` stamped onto every sheet.
    """

    model_config = ConfigDict(frozen=True)

    files: tuple[str, ...]
    skipped: tuple[str, ...]
    gate: GateSummary


def auto_specs(inputs: BackendInputs) -> tuple[DrawingSpec, ...]:
    """The drawing set derivable with NO ``--spec`` (D197): one spec per
    subject already present in `inputs`' geometry/flownet/frame/harness
    maps (every one of those is populated straight from the build's own
    realized-domain IRs/payload, never invented -- regolith/07 sec. 6),
    plus the single contract-graph sheet when the build emitted one.
    `opt_traces` is never included here: an `OptimizationTrace` is
    `optimize`'s own separate T2 output, never part of a build payload
    (`derive_producer_inputs`'s own docstring), so there is nothing to
    auto-derive it from -- only an explicit ``--spec`` can supply one.
    """
    specs: list[DrawingSpec] = [
        DrawingSpec(subject=subject, track="mech")
        for subject in sorted(inputs.geometry)
    ]
    specs += [
        DrawingSpec(subject=subject, track="fluid")
        for subject in sorted(inputs.flownets)
    ]
    specs += [
        DrawingSpec(subject=subject, track="civil") for subject in sorted(inputs.frames)
    ]
    specs += [
        DrawingSpec(subject=subject, track="elec_blocks")
        for subject in sorted(inputs.harnesses)
    ]
    # WO-78: the SI table sheet, auto-derived per subject carrying SI
    # rows (populated from the build's own obligations + evidence in
    # `ship.si_rows_from_report`, never invented).
    specs += [
        DrawingSpec(subject=subject, track="si") for subject in sorted(inputs.si_rows)
    ]
    if inputs.contract_graph is not None:
        specs.append(DrawingSpec(subject="contract_graph", track="contract_graph"))
    return tuple(specs)


def run_preview(
    report: StagedBuildReport,
    specs: tuple[DrawingSpec, ...] | None,
    out_dir: str,
    *,
    project_root: str,
    native: NativeArtifactStore | None = None,
    assemblies: Mapping[str, RealizedAssembly] = {},  # noqa: B006 (frozen input)
) -> Result[PreviewOutcome, BackendError]:
    """Run the shared producer set over ``report``, stamp every sheet/
    document with the honest gate state, and write the drawing quintets
    plus WO-96 assembly instructions plus ``gate_summary.json`` under
    ``out_dir``.

    ``specs`` is the caller-decided drawing set (parsed from ``--spec``
    exactly like `ship`'s own `_drawings_backend_from_spec`) or ``None``
    to auto-derive (:func:`auto_specs`) everything honestly derivable
    with no spec. Never refuses on a missing IR for one spec -- an
    individual `DrawingSpec` whose subject has no matching payload is
    logged and named in `PreviewOutcome.skipped`, and every other spec
    still produces (never a wholesale draft-mode crash the way a ship
    package would with a comparable gap; `preview` is diagnostic, not a
    release artifact).

    ``assemblies`` (WO-96) is always caller-supplied (see
    :func:`regolith.backends.ship.derive_producer_inputs`'s docstring):
    when non-empty, `preview --out` includes the instructions steps
    JSON + rendered document for every subject it names, stamped
    exactly like a drawing sheet.
    """
    store = native if native is not None else NativeArtifactStore(project_root)
    inputs = derive_producer_inputs(
        report,
        lockfile=Lockfile(tool_version="preview"),
        native=store,
        assemblies=assemblies,
    )
    effective_specs = auto_specs(inputs) if specs is None else specs

    gate = gate_summary_for(report.final)
    stamp_text = gate.stamp_text

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    skipped: list[str] = []
    for spec in sorted(effective_specs, key=lambda s: (s.subject, s.track)):
        model_result = model_for_spec(spec, inputs)
        if model_result.is_err:
            _log.warning(
                "preview: skipping %s/%s: %s",
                spec.subject,
                spec.track,
                model_result.danger_err.message,
            )
            skipped.append(f"{spec.subject}:{spec.track}")
            continue
        stamped = stamp_model(model_result.danger_ok, stamp_text)
        files: tuple[OutputFile, ...] = files_for_model(spec.subject, stamped)
        for f in files:
            f.write_under(out_path)
            written.append(f.relpath)

    for subject in sorted(inputs.assemblies):
        assembly = inputs.assemblies[subject]
        steps = steps_for_assembly(subject, assembly, inputs.evidence)
        stamped_steps = stamp_steps(steps, stamp_text)
        for f in files_for_steps(subject, stamped_steps):
            f.write_under(out_path)
            written.append(f.relpath)

    # WO-71 continuation slice 2: the routed/outline-only `.kicad_pcb`
    # itself (never the ship-only gerber/BOM/fab-note manufacturing
    # package, regolith/07 sec. 6 -- that stays `ship`'s exclusive
    # territory) is a legitimate REVIEW artifact, so a board whose
    # elec leg ran this build gets its pinned board file written
    # alongside the drawing sheets. A subject whose pinned bytes are
    # not (yet) in the native store is logged and skipped honestly,
    # never crashed on -- same "never refuse on one missing input"
    # discipline the drawing loop above already follows.
    for subject in sorted(inputs.layouts):
        layout = inputs.layouts[subject]
        resolved = store.resolve(layout.kicad_pcb_content_hash)
        if resolved.is_err:
            _log.warning(
                "preview: layout for %s not resolvable from the native "
                "store (%s); skipping its board file",
                subject,
                resolved.danger_err.message,
            )
            skipped.append(f"{subject}:layout")
            continue
        pcb_file = OutputFile.of(f"{subject}/board.kicad_pcb", resolved.danger_ok)
        pcb_file.write_under(out_path)
        written.append(pcb_file.relpath)

    gate_bytes = gate.model_dump_json(indent=2).encode("ascii")
    (out_path / _GATE_SUMMARY_NAME).write_bytes(gate_bytes)
    written.append(_GATE_SUMMARY_NAME)

    _log.info(
        "preview: wrote %d file(s) to %s (%d spec(s) skipped, stamp=%r)",
        len(written),
        out_dir,
        len(skipped),
        stamp_text,
    )
    return Ok(
        PreviewOutcome(files=tuple(sorted(written)), skipped=tuple(skipped), gate=gate)
    )
