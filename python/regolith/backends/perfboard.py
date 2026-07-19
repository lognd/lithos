"""The perf-board manufacturing package: wiring-map + cut-list (WO-165,
AD-47 sec. 5, D268 item 3).

Mirrors `regolith.backends.elec.ElecBackend`'s shape (subject-bound,
`produce(inputs) -> Result[tuple[OutputFile, ...], BackendError]`) but
for the `board_assignment.realized` kind (WO-163) instead of
`layout.realized`: no copper board, no `kicad-cli` -- the assignment
algorithm (`regolith.realizer.elec.perfboard`) runs entirely in-process,
so EVERY file this backend emits is `tier="deterministic"` (WO-160,
AD-45) -- a `real_tool` tier is never claimed here (the WO's own
framing: "no external tool -- the assignment algorithm is in-process").

The wiring map is rendered through the SAME `DrawingModel` -> svg
renderer path every other track uses
(`regolith.backends.drawings.producers.perfboard_wiring_map` +
`regolith.backends.drawings.renderer.render_svg`, AD-27) -- this
module never invents its own rendering. The cut list is the simplest
honest tabular format for a wire-length bill: CSV, one row per wire,
`length_mm` carried as a `DimensionedValue` (D262/INV-34: every
rendered magnitude carries an explicit unit, never a bare float) before
being flattened to CSV text.
"""

from __future__ import annotations

import csv
import io

from typani.result import Err, Ok, Result

from regolith.backends.drawings.producers import perfboard_wiring_map
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.framework import ArtifactProvenance, BackendInputs, OutputFile
from regolith.backends.quantity import DimensionedValue
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.realizer.elec.perfboard import PERFBOARD_HOLE_PITCH_MM

_log = get_logger(__name__)

#: The single wire gauge v1 assumes for every jumper (a named
#: simplification: no per-net gauge selection, an honest v1 scope --
#: 22 AWG solid hookup wire is the common perf-board jumper gauge).
# frob:doc docs/modules/py-backends.md#backends-perfboard
DEFAULT_JUMPER_GAUGE_AWG = "22"

# frob:doc docs/modules/py-backends.md#backends-perfboard
_DETERMINISTIC = ArtifactProvenance(tier="deterministic")


# frob:doc docs/modules/py-backends.md#backends-perfboard
class PerfboardBackend:
    """Produces the perf-board manufacturing package (wiring map +
    cut list) for one `board_assignment.realized` subject."""

    def __init__(self, subject: str) -> None:
        """Bind the board ``subject`` (a key of `BackendInputs.board_assignments`)."""
        self._subject = subject

    # frob:doc docs/modules/py-backends.md#backends-perfboard
    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit ``wiring_map/wiring_map.svg`` + ``wiring_map/wiring_map.json``
        and ``cutlist/cutlist.csv`` + ``cutlist/board_dimensions.json``."""
        assignment = inputs.board_assignments.get(self._subject)
        if assignment is None:
            return Err(
                BackendError(
                    kind="board_assignment_ir_unavailable",
                    message=(
                        "no RealizedBoardAssignment supplied for subject "
                        f"{self._subject!r}"
                    ),
                )
            )

        model = perfboard_wiring_map(self._subject, assignment)
        svg_bytes = render_svg(model)
        json_bytes = model.model_dump_json(by_alias=True, indent=2).encode("utf-8")

        files = [
            OutputFile.of(
                "wiring_map/wiring_map.svg", svg_bytes, provenance=_DETERMINISTIC
            ),
            OutputFile.of(
                "wiring_map/wiring_map.json", json_bytes, provenance=_DETERMINISTIC
            ),
            OutputFile.of(
                "cutlist/cutlist.csv",
                self._cutlist_csv(assignment),
                provenance=_DETERMINISTIC,
            ),
            OutputFile.of(
                "cutlist/board_dimensions.json",
                self._board_dimensions_json(assignment),
                provenance=_DETERMINISTIC,
            ),
        ]
        _log.info(
            "perfboard backend: emitted %d file(s) for %s",
            len(files),
            self._subject,
        )
        return Ok(tuple(files))

    def _cutlist_csv(self, assignment) -> bytes:  # noqa: ANN001 (RealizedBoardAssignment)
        """The wire cut list: one row per jumper, length + gauge, plus a
        totals row summing every wire's length (all one gauge, v1 --
        see :data:`DEFAULT_JUMPER_GAUGE_AWG`)."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["net", "from_hole", "to_hole", "length_mm", "gauge_awg"])
        total_mm = 0.0
        for wire in assignment.wires:
            length = DimensionedValue.of(wire.length_mm, "mm")
            writer.writerow(
                [
                    wire.net,
                    wire.from_hole,
                    wire.to_hole,
                    length.magnitude,
                    DEFAULT_JUMPER_GAUGE_AWG,
                ]
            )
            total_mm += wire.length_mm
        total = DimensionedValue.of(total_mm, "mm")
        writer.writerow(["TOTAL", "", "", total.magnitude, DEFAULT_JUMPER_GAUGE_AWG])
        return buf.getvalue().encode("utf-8")

    def _board_dimensions_json(self, assignment) -> bytes:  # noqa: ANN001
        """Board-edge dimensions + trim instructions (WO-165 deliverable
        4's cut-list "board size, any board-edge trims" clause):
        deriving the substrate footprint from the assignment's own
        component anchor holes (its bounding hole span) plus the
        standard pitch -- v1 has no separate edge-margin allowance
        beyond the outermost hole (an honest simplification, matching
        `PerfboardSubstrate`'s own board-footprint model)."""
        import json

        rows: list[int] = []
        cols: list[int] = []
        for comp in assignment.components:
            row_s, _, col_s = comp.anchor_hole.partition(",")
            rows.append(int(row_s))
            cols.append(int(col_s))
        if rows:
            width_mm = (max(cols) - min(cols)) * PERFBOARD_HOLE_PITCH_MM
            height_mm = (max(rows) - min(rows)) * PERFBOARD_HOLE_PITCH_MM
        else:
            width_mm = 0.0
            height_mm = 0.0
        payload = {
            "board_outline_ref": assignment.board_outline_ref,
            "substrate_kind": assignment.substrate_kind,
            "hole_pitch_mm": DimensionedValue.of(
                PERFBOARD_HOLE_PITCH_MM, "mm"
            ).model_dump(mode="json"),
            "width_mm": DimensionedValue.of(width_mm, "mm").model_dump(mode="json"),
            "height_mm": DimensionedValue.of(height_mm, "mm").model_dump(mode="json"),
            "trim_instructions": (
                "cut the substrate flush to the outermost occupied hole row/"
                "column on each edge; no additional edge margin is modeled "
                "in v1 (an honest simplification, not a claimed fab clearance)"
            ),
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, indent=2
        ).encode("ascii")
