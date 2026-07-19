"""The `std.materials` metallurgy record schema (T-0038, D270 ruling 1
companion: "feldspar gets the MODELS ... lithos stdlib gets the
RECORDS"). This module defines the lithos-side pydantic MIRROR of the
shape `feldspar.materials.records.MaterialRecord` expects to consume
(same field names: composition, crystal_structure, condition,
cost_class) WITHOUT importing feldspar -- shipped stdlib-loading code
never depends on the feldspar checkout being present (the established
degrade-honestly posture, WO-109/D223). Structural compatibility with
the real feldspar schema is proven in `tests/tools/
test_materials_metallurgy.py`, which imports feldspar directly (tests
may; shipped code may not).

Compositions here are RANGES (`min`/`max`) with a `typical` point value
per element, per the D269/D270 licensing law: a stdlib record cites a
public-domain-verifiable RANGE (PD-GOV where a government/MIL-spec
document names the alloy, GEK-with-posture otherwise), never a
transcribed copyrighted per-standard table cell. `typical` is the
midpoint-class value this module's loader also uses to construct a
feldspar-shaped point composition for model consumption -- one
authored range, two honest views of it (row provenance vs. model
input), never two independently-maintained numbers (NO DUPLICATION).

Provenance posture vocabulary is shared verbatim with the sibling
`std.process` schema (WO-168, `docs/spec/toolchain/
45-process-record-schema.md` sec. 3, D269 amendment): `pd_gov` /
`gek` / `named_refusal`, so a reviewer learns one vocabulary across
both stdlib schemas, not two."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typani.result import Err, Ok, Result

__all__ = [
    "CrystalSystem",
    "MaterialCondition",
    "CostClass",
    "ProvenancePosture",
    "ProvenanceNote",
    "ElementRange",
    "CompositionRange",
    "CrystalStructureMirror",
    "MetallurgyRecord",
    "load_metallurgy_records",
]

#: Mirrors `feldspar.materials.records.CrystalSystem` exactly (scoped
#: BCC/FCC/HCP per the feldspar ticket's own scope line -- this module
#: never invents a system the model half cannot consume).
CrystalSystem = Literal["BCC", "FCC", "HCP"]

#: Mirrors `feldspar.materials.records.MaterialCondition` exactly.
MaterialCondition = Literal[
    "as_cast",
    "wrought",
    "annealed",
    "normalized",
    "as_quenched",
    "quenched_and_tempered",
    "case_hardened",
]

#: Mirrors `feldspar.materials.records.CostClass` exactly.
CostClass = Literal["low", "medium", "high", "specialty"]

#: Shared verbatim with `docs/spec/toolchain/45-process-record-schema.md`
#: sec. 3 (D269 amendment) -- one provenance-posture vocabulary across
#: both stdlib schemas.
ProvenancePosture = Literal["pd_gov", "gek", "named_refusal"]


# frob:doc docs/modules/tools.md#materials-metallurgy-schema
class ProvenanceNote(BaseModel):
    """One provenance posture marker (D269 amendment / D270 ruling 2).

    `pd_gov` requires `detail` to carry the citing government/MIL-spec/
    standards document name; `gek` requires `detail` to state the
    engineering consensus PLAINLY, never phrased as a citation it is
    not; `named_refusal` requires both `refused_source` (the specific
    copyrighted table declined) and `detail` (what was omitted) --
    a note missing its posture's required field is a construction
    error, mirroring `DimensionedValue`'s own missing-unit refusal."""

    model_config = ConfigDict(frozen=True)

    posture: ProvenancePosture
    scope: str
    detail: str
    refused_source: str | None = None
    lift_condition: str | None = None

    @model_validator(mode="after")
    def _shape_matches_posture(self) -> ProvenanceNote:
        if not self.detail.strip():
            raise ValueError("ProvenanceNote.detail must not be empty")
        if self.posture == "named_refusal" and not self.refused_source:
            raise ValueError(
                "named_refusal posture requires 'refused_source' (what "
                "copyrighted table/source is being declined)"
            )
        if self.posture != "named_refusal" and self.refused_source is not None:
            raise ValueError(
                f"refused_source is only meaningful for named_refusal, "
                f"not {self.posture!r}"
            )
        return self


# frob:doc docs/modules/tools.md#materials-metallurgy-schema
class ElementRange(BaseModel):
    """One alloying element's mass-fraction RANGE plus its `typical`
    point value (dimensionless, [0,1]). `typical` is what
    `to_feldspar_mass_fractions` extracts for feldspar-shaped model
    consumption; `min`/`max` are the cited, licensable range this
    record actually asserts (D270 ruling: ranges, never a single
    scraped/transcribed value presented as exact)."""

    model_config = ConfigDict(frozen=True)

    min: float
    max: float
    typical: float

    @model_validator(mode="after")
    def _range_sane(self) -> ElementRange:
        for name, value in (
            ("min", self.min),
            ("max", self.max),
            ("typical", self.typical),
        ):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"ElementRange.{name} out of [0,1]: {value!r}")
        if self.min > self.max:
            raise ValueError(f"min ({self.min!r}) > max ({self.max!r})")
        if not (self.min - 1e-9 <= self.typical <= self.max + 1e-9):
            raise ValueError(
                f"typical ({self.typical!r}) outside [min, max] "
                f"([{self.min!r}, {self.max!r}])"
            )
        return self


# frob:doc docs/modules/tools.md#materials-metallurgy-schema
class CompositionRange(BaseModel):
    """Alloy composition as per-element `ElementRange`s, mirroring
    `feldspar.materials.records.Composition`'s `base_element` +
    element-keyed shape, but carrying a RANGE (+ `typical` point) per
    element instead of one bare fraction."""

    model_config = ConfigDict(frozen=True)

    base_element: str
    elements: dict[str, ElementRange]

    # frob:doc docs/modules/tools.md#materials-metallurgy-schema
    def to_feldspar_mass_fractions(self) -> dict[str, float]:
        """The `typical` point value per element -- the shape
        `feldspar.materials.records.Composition.mass_fractions` (a
        plain `dict[str, float]`) expects for model consumption."""
        return {element: rng.typical for element, rng in self.elements.items()}


# frob:doc docs/modules/tools.md#materials-metallurgy-schema
class CrystalStructureMirror(BaseModel):
    """Mirrors `feldspar.materials.records.CrystalStructure` field-for-
    field (`system`, `lattice_a_m`, `lattice_c_m`); this module never
    imports feldspar, so it re-validates the same HCP/cubic rule
    independently rather than sharing feldspar's class."""

    model_config = ConfigDict(frozen=True)

    system: CrystalSystem
    lattice_a_m: float
    lattice_c_m: float | None = None

    @field_validator("lattice_a_m")
    @classmethod
    def _positive_a(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError(f"lattice_a_m must be positive, got {value!r}")
        return value

    @model_validator(mode="after")
    def _c_matches_system(self) -> CrystalStructureMirror:
        if self.system == "HCP" and self.lattice_c_m is None:
            raise ValueError("HCP crystal structure requires lattice_c_m")
        if self.system != "HCP" and self.lattice_c_m is not None:
            raise ValueError(
                f"lattice_c_m is only meaningful for HCP, not {self.system}"
            )
        return self


# frob:doc docs/modules/tools.md#materials-metallurgy-schema
class MetallurgyRecord(BaseModel):
    """One `std.materials` metallurgy row: composition range, crystal
    structure, condition, cost class, and its provenance notes (one
    per field group, D270 ruling 2 / D269 amendment posture regime).
    This is the lithos-side RECORD half of the D270 MODEL/RECORD split
    -- structurally validated against feldspar's `MaterialRecord`
    consumption shape in `tests/tools/test_materials_metallurgy.py`,
    never by importing feldspar here."""

    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    composition: CompositionRange
    crystal_structure: CrystalStructureMirror
    condition: MaterialCondition
    cost_class: CostClass
    composition_provenance: tuple[ProvenanceNote, ...]
    crystal_provenance: tuple[ProvenanceNote, ...]
    cost_provenance: tuple[ProvenanceNote, ...]

    @field_validator("composition_provenance", "crystal_provenance", "cost_provenance")
    @classmethod
    def _provenance_non_empty(
        cls, value: tuple[ProvenanceNote, ...]
    ) -> tuple[ProvenanceNote, ...]:
        if not value:
            raise ValueError("provenance tuple must be non-empty")
        return value


def _provenance_from_row(
    row: dict[str, object], field: str
) -> tuple[ProvenanceNote, ...]:
    """Reads a `*_evidence` field as ONE OR MANY `ProvenanceNote`s (D269
    amendment: a blanket `gek` note commonly pairs with a `named_refusal`
    sub-note naming one specific declined source -- a TUPLE, never a
    single enum, matching the sibling `std.process` schema's own rule)."""
    table = row.get(field)
    if isinstance(table, dict):
        return (ProvenanceNote(**table),)  # type: ignore[arg-type]
    if isinstance(table, list):
        return tuple(ProvenanceNote(**t) for t in table)  # type: ignore[arg-type]
    raise ValueError(f"row {row.get('key')!r} missing {field!r} table/array")


# frob:doc docs/modules/tools.md#materials-metallurgy-schema
def load_metallurgy_records(
    path: str | Path,
) -> Result[tuple[MetallurgyRecord, ...], str]:
    """Parses `stdlib/std.materials/records/metallurgy.toml`'s
    `[[metallurgy]]` rows into typed `MetallurgyRecord` values.

    A malformed row (bad TOML, missing table, out-of-range value) is a
    loud `Err` -- there is no partial load of one file, matching the
    house `load_toml_records` convention this module deliberately does
    not duplicate (this schema's rows carry nested tables
    `load_toml_records`'s generic `Evidence` shape cannot express)."""
    file_path = Path(path)
    if not file_path.is_file():
        return Err(f"no metallurgy record file at {file_path}")
    try:
        with file_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return Err(f"malformed metallurgy TOML at {file_path}: {exc}")

    rows = data.get("metallurgy")
    if not isinstance(rows, list) or not rows:
        return Err(f"{file_path}: no [[metallurgy]] rows")

    records: list[MetallurgyRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            return Err(f"{file_path}: a metallurgy row is not a table")
        try:
            composition = CompositionRange(
                base_element=str(row["base_element"]),
                elements={
                    element: ElementRange(**bounds)
                    for element, bounds in row["composition"].items()
                },
            )
            crystal = CrystalStructureMirror(
                system=row["crystal_system"],
                lattice_a_m=float(row["lattice_a_m"]),
                lattice_c_m=(
                    float(row["lattice_c_m"]) if "lattice_c_m" in row else None
                ),
            )
            record = MetallurgyRecord(
                key=str(row["key"]),
                name=str(row["name"]),
                composition=composition,
                crystal_structure=crystal,
                condition=row["condition"],
                cost_class=row["cost_class"],
                composition_provenance=_provenance_from_row(
                    row, "composition_evidence"
                ),
                crystal_provenance=_provenance_from_row(row, "crystal_evidence"),
                cost_provenance=_provenance_from_row(row, "cost_evidence"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return Err(f"{file_path}: row {row.get('key')!r}: {exc}")
        records.append(record)
    return Ok(tuple(records))
