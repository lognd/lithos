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

from regolith.backends.drawings.audit import explain_report, run_drafting_rules
from regolith.backends.drawings.producers import (
    civil_plan_section,
    elec_blocks,
    fluid_pid,
    mech_part_drawing,
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
    `.opt_traces`, WO-58 deliverable 4).
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    track: str


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
            if spec.track == "mech":
                geometry = inputs.geometry.get(spec.subject)
                if geometry is None:
                    _log.warning(
                        "drawings backend: no realized geometry for %s", spec.subject
                    )
                    return Err(
                        BackendError(
                            kind="geometry_ir_unavailable",
                            message=(
                                "no RealizedGeometry supplied for "
                                f"subject {spec.subject!r}"
                            ),
                        )
                    )
                model = mech_part_drawing(spec.subject, geometry)
            elif spec.track == "fluid":
                flownet = inputs.flownets.get(spec.subject)
                if flownet is None:
                    _log.warning(
                        "drawings backend: no flownet payload for %s", spec.subject
                    )
                    return Err(
                        BackendError(
                            kind="flownet_ir_unavailable",
                            message=(
                                "no FlownetPayload supplied for "
                                f"subject {spec.subject!r}"
                            ),
                        )
                    )
                model = fluid_pid(spec.subject, flownet)
            elif spec.track == "civil":
                frame = inputs.frames.get(spec.subject)
                if frame is None:
                    _log.warning(
                        "drawings backend: no frame payload for %s", spec.subject
                    )
                    return Err(
                        BackendError(
                            kind="frame_ir_unavailable",
                            message=(
                                f"no FramePayload supplied for subject {spec.subject!r}"
                            ),
                        )
                    )
                model = civil_plan_section(spec.subject, frame)
            elif spec.track == "elec_blocks":
                harness = inputs.harnesses.get(spec.subject)
                if harness is None:
                    _log.warning(
                        "drawings backend: no harness payload for %s", spec.subject
                    )
                    return Err(
                        BackendError(
                            kind="harness_ir_unavailable",
                            message=(
                                "no HarnessPayload supplied for subject "
                                f"{spec.subject!r}"
                            ),
                        )
                    )
                model = elec_blocks(spec.subject, harness)
            elif spec.track == "contract_graph":
                graph = inputs.contract_graph
                if graph is None:
                    _log.warning(
                        "drawings backend: no contract graph payload for %s",
                        spec.subject,
                    )
                    return Err(
                        BackendError(
                            kind="contract_graph_ir_unavailable",
                            message=(
                                "no ContractGraphPayload supplied for subject "
                                f"{spec.subject!r}"
                            ),
                        )
                    )
                model = contract_graph_producer(spec.subject, graph)
            elif spec.track == "opt_trace":
                trace = inputs.opt_traces.get(spec.subject)
                if trace is None:
                    _log.warning(
                        "drawings backend: no optimization trace for %s", spec.subject
                    )
                    return Err(
                        BackendError(
                            kind="opt_trace_ir_unavailable",
                            message=(
                                "no OptimizationTrace supplied for subject "
                                f"{spec.subject!r}"
                            ),
                        )
                    )
                model = opt_trace_producer(spec.subject, trace)
            else:
                return Err(
                    BackendError(
                        kind="unknown_drawing_track",
                        message=(
                            f"unknown drawing track {spec.track!r} for {spec.subject!r}"
                        ),
                    )
                )

            model_json = model.model_dump_json(by_alias=True).encode("utf-8")
            files.append(
                OutputFile.of(f"drawings/{spec.subject}.drawing.json", model_json)
            )
            files.append(
                OutputFile.of(f"drawings/{spec.subject}.svg", render_svg(model))
            )
            files.append(
                OutputFile.of(f"drawings/{spec.subject}.dxf", render_dxf(model))
            )
            files.append(
                OutputFile.of(f"drawings/{spec.subject}.pdf", render_pdf(model))
            )
            report = explain_report(model)
            files.append(
                OutputFile.of(
                    f"drawings/{spec.subject}.explain.txt", report.encode("ascii")
                )
            )
            failed = [r for r in run_drafting_rules(model) if not r.passed]
            if failed:
                _log.warning(
                    "drawings backend: %s failed %d drafting rule(s)",
                    spec.subject,
                    len(failed),
                )
        _log.info("drawings backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))
