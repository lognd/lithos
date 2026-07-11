"""`DrawingsBackend`: rides the WO-25 framework to emit the drawing set
(`DrawingModel` JSON + SVG + DXF + PDF + the audit report) for a
configured list of mech/fluid/civil subjects (WO-50 deliverable 2/3).

Mirrors `regolith.backends.mech.MechBackend`'s shape: a caller-supplied,
already-decided list of subjects to produce for (never invents which
subjects to draw -- regolith/07 sec. 6), reading only
`BackendInputs.geometry`/`.flownets`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import Annotation, DrawingModel
from regolith.backends.drawings.audit import explain_report, run_drafting_rules
from regolith.backends.drawings.producers import (
    civil_plan_section,
    elec_blocks,
    fluid_pid,
    mech_part_drawing,
    si_table,
)
from regolith.backends.drawings.producers import (
    contract_graph as contract_graph_producer,
)
from regolith.backends.drawings.producers import (
    opt_trace as opt_trace_producer,
)
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_dxf import render_dxf
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


class DrawingSpec(BaseModel):
    """One drawing to produce: a subject and which producer track reads
    it (`"mech"` reads `BackendInputs.geometry`, `"fluid"` reads
    `.flownets`, `"civil"` reads `.frames`, `"elec_blocks"` reads
    `.harnesses`, WO-58 deliverable 1; `"contract_graph"` reads the
    single `.contract_graph` (WO-61 deliverable 3); `"opt_trace"` reads
    `.opt_traces`, WO-58 deliverable 4; `"si"` reads `.si_rows`, the
    WO-78 SI table sheet).
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    track: str


def model_for_spec(
    spec: DrawingSpec, inputs: BackendInputs
) -> Result[DrawingModel, BackendError]:
    """Run the ONE per-track producer dispatch (D197: the shared
    producer set `regolith ship` and `regolith preview` both call --
    never a second copy of this if/elif ladder) and return the raw
    `DrawingModel`, before any file is rendered. `DrawingsBackend.produce`
    (the ship-only consumer) renders it straight to files; the preview
    driver (`regolith.backends.preview`) stamps it with the honesty
    annotation first (D197's "through the model, not by post-editing
    rendered files" rule) before rendering the SAME way.
    """
    if spec.track == "mech":
        geometry = inputs.geometry.get(spec.subject)
        if geometry is None:
            _log.warning("drawings: no realized geometry for %s", spec.subject)
            return Err(
                BackendError(
                    kind="geometry_ir_unavailable",
                    message=(
                        f"no RealizedGeometry supplied for subject {spec.subject!r}"
                    ),
                )
            )
        return Ok(mech_part_drawing(spec.subject, geometry))
    if spec.track == "fluid":
        flownet = inputs.flownets.get(spec.subject)
        if flownet is None:
            _log.warning("drawings: no flownet payload for %s", spec.subject)
            return Err(
                BackendError(
                    kind="flownet_ir_unavailable",
                    message=f"no FlownetPayload supplied for subject {spec.subject!r}",
                )
            )
        return Ok(fluid_pid(spec.subject, flownet))
    if spec.track == "civil":
        frame = inputs.frames.get(spec.subject)
        if frame is None:
            _log.warning("drawings: no frame payload for %s", spec.subject)
            return Err(
                BackendError(
                    kind="frame_ir_unavailable",
                    message=f"no FramePayload supplied for subject {spec.subject!r}",
                )
            )
        return Ok(civil_plan_section(spec.subject, frame))
    if spec.track == "elec_blocks":
        harness = inputs.harnesses.get(spec.subject)
        if harness is None:
            _log.warning("drawings: no harness payload for %s", spec.subject)
            return Err(
                BackendError(
                    kind="harness_ir_unavailable",
                    message=(
                        f"no HarnessPayload supplied for subject {spec.subject!r}"
                    ),
                )
            )
        return Ok(elec_blocks(spec.subject, harness))
    if spec.track == "contract_graph":
        graph = inputs.contract_graph
        if graph is None:
            _log.warning("drawings: no contract graph payload for %s", spec.subject)
            return Err(
                BackendError(
                    kind="contract_graph_ir_unavailable",
                    message=(
                        f"no ContractGraphPayload supplied for subject {spec.subject!r}"
                    ),
                )
            )
        return Ok(contract_graph_producer(spec.subject, graph))
    if spec.track == "si":
        rows = inputs.si_rows.get(spec.subject)
        if rows is None:
            _log.warning("drawings: no SI rows for %s", spec.subject)
            return Err(
                BackendError(
                    kind="si_rows_unavailable",
                    message=f"no SI table rows derived for subject {spec.subject!r}",
                )
            )
        return Ok(si_table(spec.subject, rows))
    if spec.track == "opt_trace":
        trace = inputs.opt_traces.get(spec.subject)
        if trace is None:
            _log.warning("drawings: no optimization trace for %s", spec.subject)
            return Err(
                BackendError(
                    kind="opt_trace_ir_unavailable",
                    message=(
                        f"no OptimizationTrace supplied for subject {spec.subject!r}"
                    ),
                )
            )
        return Ok(opt_trace_producer(spec.subject, trace))
    return Err(
        BackendError(
            kind="unknown_drawing_track",
            message=f"unknown drawing track {spec.track!r} for {spec.subject!r}",
        )
    )


def stamp_model(model: DrawingModel, stamp_text: str) -> DrawingModel:
    """D197's honesty stamp, applied THROUGH the model (never by
    post-editing a rendered SVG/DXF/PDF): every sheet gets one extra
    `Annotation` carrying ``stamp_text`` (``"PREVIEW -- NOT RELEASED:
    <n> unresolved"`` or ``"RELEASE-CLEAN"``, see `GateSummary
    .stamp_text`), anchored well clear of any producer's own content
    (``[-20.0, -20.0]``, ahead of every producer's `[0, 0]`-rooted
    layout) so it never trips the drafting audit's no-overlap rule.
    `Sheet`/`DrawingModel` are frozen pydantic models -- `model_copy`
    rebuilds each one with the stamp appended, everything else
    byte-identical to what the producer returned.
    """
    stamp = Annotation(
        text=stamp_text,
        anchor=[-20.0, -20.0],
        text_height_mm=5.0,
        datum_refs=[],
        per=None,
    )
    stamped_sheets = [
        sheet.model_copy(update={"annotations": [stamp, *sheet.annotations]})
        for sheet in model.sheets
    ]
    return model.model_copy(update={"sheets": stamped_sheets})


def files_for_model(subject: str, model: DrawingModel) -> tuple[OutputFile, ...]:
    """The `<subject>.drawing.json` + `.svg` + `.dxf` + `.pdf` +
    `.explain.txt` quintet for an already-built `DrawingModel`, under
    `drawings/` -- the ONE rendering tail both `DrawingsBackend.produce`
    and the preview driver call, so a stamped preview sheet renders
    through the exact same code as a ship sheet.
    """
    files: list[OutputFile] = []
    model_json = model.model_dump_json(by_alias=True).encode("utf-8")
    files.append(OutputFile.of(f"drawings/{subject}.drawing.json", model_json))
    files.append(OutputFile.of(f"drawings/{subject}.svg", render_svg(model)))
    files.append(OutputFile.of(f"drawings/{subject}.dxf", render_dxf(model)))
    files.append(OutputFile.of(f"drawings/{subject}.pdf", render_pdf(model)))
    report = explain_report(model)
    files.append(
        OutputFile.of(f"drawings/{subject}.explain.txt", report.encode("ascii"))
    )
    failed = [r for r in run_drafting_rules(model) if not r.passed]
    if failed:
        _log.warning("drawings: %s failed %d drafting rule(s)", subject, len(failed))
    return tuple(files)


class DrawingsBackend:
    """Produces `drawings/<subject>.drawing.json` + `.svg` + `.dxf` +
    `.pdf` + `.explain.txt` for every configured `DrawingSpec`.
    """

    def __init__(self, specs: tuple[DrawingSpec, ...]) -> None:
        """Bind the sorted (by subject) list of drawings to produce."""
        self._specs = tuple(sorted(specs, key=lambda s: s.subject))

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit every configured drawing's IR/SVG/audit-report triple."""
        files: list[OutputFile] = []
        for spec in self._specs:
            model_result = model_for_spec(spec, inputs)
            if model_result.is_err:
                return Err(model_result.danger_err)
            files.extend(files_for_model(spec.subject, model_result.danger_ok))
        _log.info("drawings backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))
