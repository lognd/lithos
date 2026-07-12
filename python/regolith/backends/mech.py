"""The mech manufacturing package: STEP + BOM + fab notes (WO-25).

Every value serialized here already exists upstream: the STEP bytes are
the WO-22 realizer's pinned native artifact (resolved by the
``RealizedGeometry.step_content_hash`` digest already on the IR), the
mass/topology figures are the IR's own ``topology`` block, and the BOM/
fab-note TEXT (part numbers, material, finish, tolerance allocations,
quantities) is supplied by the caller via :class:`AssemblyLine`/
:class:`FabNoteSpec` -- this backend never invents a part number or a
tolerance, it only serializes what the lockfile/registry already pinned
(regolith/07 sec. 6, "backends never decide"). Drawings are TRACKED CUT
for v1 per the WO body (STEP+PMI and fab notes cover CNC quoting).
"""

from __future__ import annotations

import csv
import io
import json

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


class AssemblyLine(BaseModel):
    """One BOM row: a realized part's registry-pinned identity + quantity.

    ``subject`` keys ``BackendInputs.geometry`` (the part whose STEP/
    topology this row's mass figures come from); everything else is
    already-decided registry/lockfile data handed in by the caller.
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    part_number: str
    description: str
    material: str
    quantity: int = Field(ge=1)


class ToleranceRow(BaseModel):
    """One fab-note tolerance-table row (an allocated tolerance, per part)."""

    model_config = ConfigDict(frozen=True)

    feature: str
    nominal_mm: float
    plus_mm: float
    minus_mm: float


class FabNoteSpec(BaseModel):
    """The caller-supplied, already-decided fab-note content for one part."""

    model_config = ConfigDict(frozen=True)

    subject: str
    material: str
    finish: str
    quantity: int = Field(ge=1)
    tolerances: tuple[ToleranceRow, ...] = ()


class MechBackend:
    """Produces the mech manufacturing package: STEP + BOM (CSV+JSON) + fab notes."""

    def __init__(
        self,
        assembly: tuple[AssemblyLine, ...],
        fab_notes: tuple[FabNoteSpec, ...] = (),
    ) -> None:
        """Bind the BOM's assembly tree and per-part fab-note specs.

        Both are sorted by ``subject`` before use so output is
        deterministic regardless of caller-supplied order (AD-6).
        """
        self._assembly = tuple(sorted(assembly, key=lambda a: a.subject))
        self._fab_notes = tuple(sorted(fab_notes, key=lambda f: f.subject))

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit ``step/<subject>.step``, ``bom.csv/json``, ``fab_notes.json``."""
        files: list[OutputFile] = []
        for line in self._assembly:
            geometry = inputs.geometry.get(line.subject)
            if geometry is None:
                _log.warning("mech backend: no realized geometry for %s", line.subject)
                return Err(
                    BackendError(
                        kind="geometry_ir_unavailable",
                        message="no RealizedGeometry supplied for subject "
                        f"{line.subject!r}",
                    )
                )
            resolved = inputs.native.resolve(geometry.step_content_hash)
            if resolved.is_err:
                return Err(resolved.danger_err)
            step_bytes = resolved.danger_ok
            files.append(OutputFile.of(f"step/{line.subject}.step", step_bytes))

        files.append(self._bom_csv())
        files.append(self._bom_json(inputs))
        files.append(self._fab_notes_json())
        _log.info("mech backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))

    def _bom_csv(self) -> OutputFile:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        # WO-101/D204: the `mass_hint = area_mm2` column is GONE -- it
        # labeled a surface area as a mass, a correctness landmine. Real
        # record-pinned mass lives in the derived BOM v2
        # (`regolith.backends.bom`); this legacy per-part table carries
        # only the caller-decided identity columns.
        writer.writerow(
            [
                "subject",
                "part_number",
                "description",
                "material",
                "quantity",
            ]
        )
        for line in self._assembly:
            writer.writerow(
                [
                    line.subject,
                    line.part_number,
                    line.description,
                    line.material,
                    str(line.quantity),
                ]
            )
        return OutputFile.of("bom.csv", buf.getvalue().encode("ascii"))

    def _bom_json(self, inputs: BackendInputs) -> OutputFile:
        rows = [
            {
                "subject": line.subject,
                "part_number": line.part_number,
                "description": line.description,
                "material": line.material,
                "quantity": line.quantity,
                "step_content_hash": inputs.geometry[line.subject].step_content_hash,
            }
            for line in self._assembly
        ]
        payload = json.dumps(
            {"assembly": rows}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return OutputFile.of("bom.json", payload.encode("ascii"))

    def _fab_notes_json(self) -> OutputFile:
        notes = [
            {
                "subject": spec.subject,
                "material": spec.material,
                "finish": spec.finish,
                "quantity": spec.quantity,
                "tolerances": [
                    {
                        "feature": row.feature,
                        "nominal_mm": row.nominal_mm,
                        "plus_mm": row.plus_mm,
                        "minus_mm": row.minus_mm,
                    }
                    for row in spec.tolerances
                ],
            }
            for spec in self._fab_notes
        ]
        payload = json.dumps(
            {"fab_notes": notes},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return OutputFile.of("fab_notes.json", payload.encode("ascii"))
