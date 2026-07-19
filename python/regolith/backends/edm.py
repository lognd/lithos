"""The wire-EDM manufacturing package: profile-cut DXF + setup sheet
(WO-166 slice b, AD-47 sec. 5, D268 item 1).

Mirrors `regolith.backends.perfboard.PerfboardBackend`'s shape
(subject-bound, `produce(inputs) -> Result[tuple[OutputFile, ...],
BackendError]`) for the `edm_profile.realized` kind (WO-166) instead of
`board_assignment.realized`: no external EDM-machine tool adapter is
claimed (v1 has no real toolpath post-processor), so EVERY file this
backend emits is `tier="deterministic"` (WO-160, AD-45), named
explicitly, never a claimed `real_tool` tier.

The profile-cut geometry is rendered through the SAME `DrawingModel`
-> DXF renderer path every other drawing-producing track uses
(`regolith.realizer.mech.wire_edm.profile_drawing_model` +
`regolith.backends.drawings.renderer_dxf.render_dxf`, AD-27) -- this
module never draws bytes itself. The setup sheet is the simplest
honest tabular format for the machine-operator-facing cut parameters:
JSON, one document per profile (kerf, spark gap, lead-in, per-vertex
corner radii, and the two DFM outcomes the realize step already
computed -- never re-derived here).
"""

from __future__ import annotations

import json

from typani.result import Err, Ok, Result

from regolith.backends.drawings.renderer_dxf import render_dxf
from regolith.backends.framework import ArtifactProvenance, BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.realizer.mech.wire_edm import RealizedWireEdmProfile, profile_drawing_model

_log = get_logger(__name__)

# frob:doc docs/modules/py-backends.md#backends-edm
_DETERMINISTIC = ArtifactProvenance(tier="deterministic")

#: This backend's one `BackendError.kind` (D247.1: a named constant,
#: never a bare string literal, per `tools/health/diag_codes.py`'s
#: sweep over `python/regolith/backends/`).
# frob:doc docs/modules/py-backends.md#backends-edm
EDM_PROFILE_IR_UNAVAILABLE = "edm_profile_ir_unavailable"


# frob:doc docs/modules/py-backends.md#backends-edm
class WireEdmBackend:
    """Produces the wire-EDM profile-cut manufacturing package (DXF +
    setup sheet) for one `edm_profile.realized` subject."""

    def __init__(self, subject: str) -> None:
        """Bind the profile ``subject`` (a key of `BackendInputs.edm_profiles`)."""
        self._subject = subject

    # frob:doc docs/modules/py-backends.md#backends-edm
    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit ``edm_profile/profile.dxf`` and
        ``edm_profile/setup_sheet.json``."""
        realized = inputs.edm_profiles.get(self._subject)
        if realized is None:
            return Err(
                BackendError(
                    kind=EDM_PROFILE_IR_UNAVAILABLE,
                    message=(
                        "no RealizedWireEdmProfile supplied for subject "
                        f"{self._subject!r}"
                    ),
                )
            )

        model = profile_drawing_model(realized)
        dxf_bytes = render_dxf(model)
        setup_sheet_bytes = self._setup_sheet_json(realized)

        files = (
            OutputFile.of(
                "edm_profile/profile.dxf", dxf_bytes, provenance=_DETERMINISTIC
            ),
            OutputFile.of(
                "edm_profile/setup_sheet.json",
                setup_sheet_bytes,
                provenance=_DETERMINISTIC,
            ),
        )
        _log.info(
            "wire-EDM backend: emitted %d file(s) for %s", len(files), self._subject
        )
        return Ok(files)

    def _setup_sheet_json(self, realized: RealizedWireEdmProfile) -> bytes:
        """The operator-facing cut-parameter setup sheet: kerf, spark
        gap, lead-in, per-vertex corner radii, and the two DFM outcomes
        the realize step already discharged (never re-derived here --
        the SAME `CamOutcome` objects `realize_wire_edm_profile`
        computed)."""
        profile = realized.profile
        payload = {
            "profile_ref": profile.profile_ref,
            "material_ref": profile.material_ref,
            "closed": profile.closed,
            "kerf_mm": profile.kerf_mm,
            "spark_gap_mm": profile.spark_gap_mm,
            "lead_in": {
                "start_x_mm": profile.lead_in.start_x_mm,
                "start_y_mm": profile.lead_in.start_y_mm,
                "has_start_hole": profile.lead_in.has_start_hole,
            },
            "vertices": [
                {
                    "x_mm": v.x_mm,
                    "y_mm": v.y_mm,
                    "corner_radius_mm": v.corner_radius_mm,
                }
                for v in profile.vertices
            ],
            "dfm_outcomes": {
                "corner_radius": [
                    {
                        "excess": o.excess,
                        "violated": o.violated,
                        "note": o.note,
                    }
                    for o in realized.corner_radius_outcomes
                ],
                "start_hole": {
                    "excess": realized.start_hole_outcome.excess,
                    "violated": realized.start_hole_outcome.violated,
                    "note": realized.start_hole_outcome.note,
                },
            },
            "provenance_tier": "deterministic",
            "provenance_note": (
                "no real EDM-machine toolpath post-processor is claimed -- "
                "this profile/parameter set is computed in-process (WO-166 v1)"
            ),
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, indent=2
        ).encode("ascii")


__all__ = ["EDM_PROFILE_IR_UNAVAILABLE", "WireEdmBackend"]
