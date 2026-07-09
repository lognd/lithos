"""`DrawingsBackend`: rides the WO-25 framework to emit the drawing set
(`DrawingModel` JSON + SVG + the audit report) for a configured list of
mech/fluid subjects (WO-50 deliverable 2/3).

Mirrors `regolith.backends.mech.MechBackend`'s shape: a caller-supplied,
already-decided list of subjects to produce for (never invents which
subjects to draw -- regolith/07 sec. 6), reading only
`BackendInputs.geometry`/`.flownets`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.backends.drawings.audit import explain_report, run_drafting_rules
from regolith.backends.drawings.producers import fluid_pid, mech_part_drawing
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


class DrawingSpec(BaseModel):
    """One drawing to produce: a subject and which producer track reads
    it (`"mech"` reads `BackendInputs.geometry`, `"fluid"` reads
    `.flownets`).
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    track: str


class DrawingsBackend:
    """Produces `drawings/<subject>.drawing.json` + `.svg` + `.explain.txt`
    for every configured `DrawingSpec`.
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
