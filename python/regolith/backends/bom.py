"""Derived BOM v2 + cost join, with real record-pinned mass (WO-101).

The first-generation BOM (``regolith.backends.mech.MechBackend``) shipped
a hand-supplied part table whose only "mass" column was the realized
solid's SURFACE AREA mislabeled ``mass_hint`` -- a correctness landmine
(a number that looks like mass and is not). This module replaces it with
a DERIVED bill of materials (charter 38 sec. 1.7, D208):

- rows are derived from the design graph the build already produced --
  mech parts (`RealizedGeometry`), assembly members (`RealizedAssembly`),
  frame members (`FramePayload`), elec block instances
  (`BlockRequirement`), and flownet fittings (`FlownetPayload`) -- never
  invented (regolith/07 sec. 6: a backend serializes, never decides);
- part numbers come ONLY from a caller `AssemblyLine` (which overrides or
  augments a derived row by subject key) or a hash-pinned record; a row
  with neither ships a loud ``unsourced`` marker, never a fabricated
  number;
- mass is REAL: material-record density x realized solid volume, both
  pins carried as provenance. Where either input is missing the mass cell
  is honestly empty WITH a reason (D204: an honest empty cell beats a
  mislabeled number). Volume is the realized ``TopologySummary.volume_mm3``
  -- OCCT's own GProp volume of the pinned STEP solid, captured at realize
  time and designated the cross-platform-stable golden by the schema
  (INV-10/AD-6: STEP bytes are deliberately NOT byte-stable cross-
  platform, so re-running GProp over them at ship time would break the
  byte-identical-golden guarantee; ``step_content_hash`` is carried as the
  geometry provenance pin instead);
- cost columns join the persisted itemized-estimate evidence
  (`ItemizedEstimate`) by subject; a row with no estimate ships an empty
  cost cell with a reason.

Formats (csv/json/md/pdf) render through WO-99's `RendererRegistry`
under the ``bom`` model family, exactly as the `DrawingModel` renderers
render under theirs.
"""

from __future__ import annotations

import csv
import io
import json
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Ok, Result

from regolith._schema.models import (
    BlockRequirement,
    ItemizedEstimate,
    RealizedGeometry,
)
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.backends.mech import AssemblyLine
from regolith.backends.registry import RendererRegistration, RendererRegistry
from regolith.errors import BackendError
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_records import row_hash

_log = get_logger(__name__)

# The model family the BOM renderers register under (charter 38 sec. 1.2:
# the realized-IR renderer families coexist in the ONE `RendererRegistry`
# keyed by a distinct `over` string; `DrawingModel`'s is `"drawing"`).
BOM_FAMILY = "bom"

# The stdlib record table this module reads for density (the std.materials
# `[[material]]` rows; `density_kg_m3` is SI base, kg/m^3).
_MATERIAL_TABLE = "material"
# The fixed starter revision the stdlib loader pins records at (mirrors
# `regolith.orchestrator.costing.record_pins`).
_RECORD_REV = 1


class MaterialRecord(BaseModel):
    """One std.materials record's mass-relevant fields + its row digest.

    ``density_kg_m3`` is ``None`` when the record row carries no density
    (an honest gap -- the consuming mass cell then states the reason
    rather than inventing a figure)."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    density_kg_m3: float | None = None


class MaterialRecordSet(BaseModel):
    """Every loaded std.materials record, keyed by record key for lookup."""

    model_config = ConfigDict(frozen=True)

    by_key: dict[str, MaterialRecord] = {}

    def density_of(self, material: str) -> MaterialRecord | None:
        """The record for ``material`` (exact key), or ``None`` if absent."""
        return self.by_key.get(material)


class BomRow(BaseModel):
    """One derived BOM row: identity, quantity, real mass, cost -- with
    every provenance pin a downstream auditor needs, and an explicit
    honesty marker (``unsourced``/``mass_reason``/``cost_reason``) wherever
    a value could not be sourced (never a blank cell passing as a fact).
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    kind: str = Field(
        description="part/assembly_member/frame_member/elec_block/fitting"
    )
    quantity: int = Field(ge=1)
    part_number: str = ""
    unsourced: bool = Field(
        default=False,
        description="True when no record and no caller line named a part number.",
    )
    material: str = ""
    description: str = ""
    material_pin: str = Field(default="", description="Density record ref (key@rev).")
    geometry_pin: str = Field(default="", description="STEP content hash provenance.")
    mass_g: str = Field(default="", description="Real mass in grams, or '' if unknown.")
    mass_reason: str = Field(default="", description="Why the mass cell is empty.")
    unit_cost: str = ""
    total_cost: str = ""
    currency: str = ""
    cost_ref: str = Field(default="", description="Estimate/record provenance digest.")
    cost_reason: str = Field(default="", description="Why the cost cell is empty.")


class BomModel(BaseModel):
    """The derived bill of materials (the ``bom`` renderer family's IR):
    deterministically-ordered rows plus the build-level cost profile and
    rolled-up totals, all derived -- never authored."""

    model_config = ConfigDict(frozen=True)

    rows: tuple[BomRow, ...] = ()
    cost_profile: str | None = None
    currency: str = ""
    total_mass_g: str = ""
    total_cost: str = ""
    unsourced_count: int = 0


# --- material record loading -------------------------------------------


def _load_material_file(path: Path, out: dict[str, MaterialRecord]) -> None:
    """Load one records TOML's `[[material]]` rows into ``out`` (first key
    wins, deterministic); a table this loader does not own is skipped."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _log.warning("bom: material records unreadable at %s (%s)", path, exc)
        return
    rows = data.get(_MATERIAL_TABLE)
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict) or "key" not in row:
            continue
        key = str(row["key"])
        if key in out:
            continue
        density = row.get("density_kg_m3")
        out[key] = MaterialRecord(
            key=key,
            digest=row_hash(_MATERIAL_TABLE, row),
            density_kg_m3=float(density) if isinstance(density, (int, float)) else None,
        )


def load_material_records(search_paths: tuple[str, ...]) -> MaterialRecordSet:
    """Load every std.materials record under ``search_paths`` (the local-
    path posture the cost loader uses: each path's own ``records/*.toml``
    plus every package subdir's, sorted, first-key-wins)."""
    out: dict[str, MaterialRecord] = {}
    for base_str in search_paths:
        base = Path(base_str)
        candidates = [base / "records"]
        if base.is_dir():
            candidates.extend(
                sub / "records"
                for sub in sorted(base.iterdir())
                if sub.is_dir() and (sub / "magnetite.toml").is_file()
            )
        for records_dir in candidates:
            if not records_dir.is_dir():
                continue
            for toml_file in sorted(records_dir.glob("*.toml")):
                _load_material_file(toml_file, out)
    _log.debug("bom: loaded %d material record(s)", len(out))
    return MaterialRecordSet(by_key=out)


# --- mass -----------------------------------------------------------------


def _mass_grams(density_kg_m3: float, volume_mm3: float) -> float:
    """Real mass in grams: density (kg/m^3) x volume (mm^3).

    1 mm^3 = 1e-9 m^3, and 1 kg = 1e3 g, so grams = density * volume_mm3 *
    1e-9 * 1e3 = density * volume_mm3 * 1e-6.
    """
    return density_kg_m3 * volume_mm3 * 1e-6


def _mech_mass(
    geometry: RealizedGeometry, material: str, materials: MaterialRecordSet
) -> tuple[str, str, str, str]:
    """(mass_g, mass_reason, material_pin, geometry_pin) for a mech part.

    Honest empties: no material named, or the named material resolves to
    no record, or that record carries no density -- each states its
    reason instead of a number (D204)."""
    geometry_pin = geometry.step_content_hash
    if not material:
        return "", "no material named for this part", "", geometry_pin
    record = materials.density_of(material)
    if record is None:
        return "", f"no density record for material {material!r}", "", geometry_pin
    pin = f"{record.key}@{_RECORD_REV}"
    if record.density_kg_m3 is None:
        return "", f"material record {material!r} carries no density", pin, geometry_pin
    grams = _mass_grams(record.density_kg_m3, geometry.topology.volume_mm3)
    return f"{grams:.3f}", "", pin, geometry_pin


# --- cost join ------------------------------------------------------------


def _cost_cells(estimate: ItemizedEstimate | None) -> tuple[str, str, str, str, str]:
    """(unit_cost, total_cost, currency, cost_ref, cost_reason) for a row.

    The estimate's grand total is the row's cost; ``cost_ref`` cites the
    profile so the number is never an unattributable figure. No estimate
    -> empty cost with a reason (never a zero passing as priced)."""
    if estimate is None:
        return "", "", "", "", "no cost estimate for this subject"
    total = estimate.total
    total_text = (
        f"{total.lo:.2f}" if total.lo == total.hi else f"{total.lo:.2f}-{total.hi:.2f}"
    )
    return "", total_text, total.unit, f"profile:{estimate.profile}", ""


# --- derivation -----------------------------------------------------------


def _lines_by_subject(lines: Iterable[AssemblyLine]) -> dict[str, AssemblyLine]:
    """Caller `AssemblyLine`s keyed by subject (last wins, then we sort);
    each overrides or augments a derived row by that key."""
    return {line.subject: line for line in lines}


def derive_bom_rows(
    inputs: BackendInputs,
    *,
    assembly_lines: tuple[AssemblyLine, ...] = (),
    materials: MaterialRecordSet | None = None,
    block_requirements: tuple[BlockRequirement, ...] = (),
    estimates: Mapping[str, ItemizedEstimate] = {},  # noqa: B006 (frozen input)
    cost_profile: str | None = None,
) -> BomModel:
    """Derive the bill of materials from the design graph (charter 38
    sec. 1.7): mech parts + assembly members + frame members + elec
    blocks + flownet fittings, with caller `AssemblyLine`s overriding or
    augmenting by subject key, real record-pinned mass, and joined cost.

    Deterministic: every source is walked in sorted-subject order and the
    row list is finally sorted by ``(subject, kind)`` (AD-6).
    """
    mats = materials if materials is not None else MaterialRecordSet()
    by_subject = _lines_by_subject(assembly_lines)
    consumed_lines: set[str] = set()
    rows: list[BomRow] = []

    def _identity(subject: str) -> tuple[str, str, str, bool, str]:
        """(part_number, material, description, unsourced, material_from_line)."""
        line = by_subject.get(subject)
        if line is not None:
            consumed_lines.add(subject)
            return (
                line.part_number,
                line.material,
                line.description,
                False,
                line.material,
            )
        return "", "", "", True, ""

    # 1. mech parts (RealizedGeometry) -- the only source with real volume.
    for subject in sorted(inputs.geometry):
        geometry = inputs.geometry[subject]
        line = by_subject.get(subject)
        pn, material, desc, unsourced, _ = _identity(subject)
        mass_g, mass_reason, material_pin, geometry_pin = _mech_mass(
            geometry, material, mats
        )
        unit_cost, total_cost, currency, cost_ref, cost_reason = _cost_cells(
            estimates.get(subject)
        )
        rows.append(
            BomRow(
                subject=subject,
                kind="part",
                quantity=line.quantity if line is not None else 1,
                part_number=pn,
                unsourced=unsourced,
                material=material,
                description=desc,
                material_pin=material_pin,
                geometry_pin=geometry_pin,
                mass_g=mass_g,
                mass_reason=mass_reason,
                unit_cost=unit_cost,
                total_cost=total_cost,
                currency=currency,
                cost_ref=cost_ref,
                cost_reason=cost_reason,
            )
        )

    # 2. assembly members (RealizedAssembly) -- each placed instance.
    for asm_subject in sorted(inputs.assemblies):
        assembly = inputs.assemblies[asm_subject]
        for part in sorted(assembly.parts, key=lambda p: p.id):
            subject = f"{asm_subject}.{part.id}"
            if subject in inputs.geometry:
                continue  # already a mech-part row; no double count
            pn, material, desc, unsourced, _ = _identity(subject)
            uc, tc, cur, cref, creason = _cost_cells(estimates.get(subject))
            rows.append(
                BomRow(
                    subject=subject,
                    kind="assembly_member",
                    quantity=1,
                    part_number=pn,
                    unsourced=unsourced,
                    material=material,
                    description=desc or f"member of {asm_subject}",
                    mass_reason="no realized solid volume for assembly member",
                    unit_cost=uc,
                    total_cost=tc,
                    currency=cur,
                    cost_ref=cref,
                    cost_reason=creason,
                )
            )

    # 3. frame members (FramePayload) -- section/material by name.
    for frame_subject in sorted(inputs.frames):
        frame = inputs.frames[frame_subject]
        for member in frame.members:
            subject = member.id
            pn, material, desc, unsourced, line_mat = _identity(subject)
            member_mat = line_mat or _frame_material(member)
            uc, tc, cur, cref, creason = _cost_cells(estimates.get(subject))
            rows.append(
                BomRow(
                    subject=subject,
                    kind="frame_member",
                    quantity=1,
                    part_number=pn,
                    unsourced=unsourced,
                    material=member_mat,
                    description=desc or _frame_desc(member),
                    mass_reason="no realized solid volume for frame member",
                    unit_cost=uc,
                    total_cost=tc,
                    currency=cur,
                    cost_ref=cref,
                    cost_reason=creason,
                )
            )

    # 4. elec block instances (BlockRequirement) -- keyed by owning decl.
    for req in sorted(block_requirements, key=lambda r: r.owner):
        subject = req.owner
        pn, material, desc, unsourced, _ = _identity(subject)
        uc, tc, cur, cref, creason = _cost_cells(estimates.get(subject))
        rows.append(
            BomRow(
                subject=subject,
                kind="elec_block",
                quantity=1,
                part_number=pn,
                unsourced=unsourced,
                material=material,
                description=desc or f"{req.block} ({req.contract})",
                mass_reason="no realized solid volume for elec block",
                unit_cost=uc,
                total_cost=tc,
                currency=cur,
                cost_ref=cref,
                cost_reason=creason,
            )
        )

    # 5. flownet fittings (FlownetPayload edges).
    for flow_subject in sorted(inputs.flownets):
        flownet = inputs.flownets[flow_subject]
        for edge in flownet.edges:
            subject = edge.id
            pn, material, desc, unsourced, _ = _identity(subject)
            component = _edge_component(edge)
            uc, tc, cur, cref, creason = _cost_cells(estimates.get(subject))
            rows.append(
                BomRow(
                    subject=subject,
                    kind="fitting",
                    quantity=1,
                    part_number=pn,
                    unsourced=unsourced,
                    material=material,
                    description=desc or component or f"{_edge_kind(edge)} fitting",
                    mass_reason="no realized solid volume for fitting",
                    unit_cost=uc,
                    total_cost=tc,
                    currency=cur,
                    cost_ref=cref,
                    cost_reason=creason,
                )
            )

    # 6. augment: caller lines matching no derived subject add a row.
    for subject in sorted(set(by_subject) - consumed_lines):
        line = by_subject[subject]
        uc, tc, cur, cref, creason = _cost_cells(estimates.get(subject))
        rows.append(
            BomRow(
                subject=subject,
                kind="part",
                quantity=line.quantity,
                part_number=line.part_number,
                unsourced=False,
                material=line.material,
                description=line.description,
                mass_reason="no realized geometry for caller-supplied line",
                unit_cost=uc,
                total_cost=tc,
                currency=cur,
                cost_ref=cref,
                cost_reason=creason,
            )
        )

    rows.sort(key=lambda r: (r.subject, r.kind))
    return _rollup(tuple(rows), cost_profile)


def _rollup(rows: tuple[BomRow, ...], cost_profile: str | None) -> BomModel:
    """Seal the model: sum real masses and (single-currency) costs, count
    unsourced rows -- a mixed-currency cost roll-up honestly abstains."""
    total_mass = 0.0
    any_mass = False
    total_cost = 0.0
    any_cost = False
    currencies: set[str] = set()
    for row in rows:
        if row.mass_g:
            total_mass += float(row.mass_g) * row.quantity
            any_mass = True
        if row.total_cost and "-" not in row.total_cost:
            total_cost += float(row.total_cost)
            any_cost = True
            currencies.add(row.currency)
    currency = next(iter(currencies)) if len(currencies) == 1 else ""
    cost_text = f"{total_cost:.2f}" if any_cost and currency else ""
    return BomModel(
        rows=rows,
        cost_profile=cost_profile,
        currency=currency,
        total_mass_g=f"{total_mass:.3f}" if any_mass else "",
        total_cost=cost_text,
        unsourced_count=sum(1 for r in rows if r.unsourced),
    )


# --- payload-shape accessors (raw FramePayload/FlowEdge helpers) ----------


def _frame_material(member: object) -> str:
    """A frame member's material name (empty when unresolved)."""
    material = getattr(member, "material", None)
    return str(getattr(material, "name", "") or "") if material is not None else ""


def _frame_desc(member: object) -> str:
    """A short frame-member description: role + section name."""
    role = str(getattr(member, "role", "") or "")
    section = getattr(member, "section", None)
    section_name = (
        str(getattr(section, "name", "") or "") if section is not None else ""
    )
    parts = [p for p in (role, section_name) if p]
    return " ".join(parts) or "frame member"


def _edge_component(edge: object) -> str:
    """A flownet edge's first bound component-record name (empty if none)."""
    curves = getattr(edge, "curves", None) or []
    if curves:
        return str(getattr(curves[0], "name", "") or "")
    return ""


def _edge_kind(edge: object) -> str:
    """A flownet edge's kind label (empty when absent)."""
    kind = getattr(edge, "kind", "")
    return str(getattr(kind, "value", kind) or "")


# --- renderers (the `bom` family) -----------------------------------------

_CSV_COLUMNS = (
    "subject",
    "kind",
    "part_number",
    "unsourced",
    "material",
    "description",
    "quantity",
    "mass_g",
    "mass_reason",
    "material_pin",
    "geometry_pin",
    "total_cost",
    "currency",
    "cost_ref",
    "cost_reason",
)


def render_bom_csv(model: BomModel) -> bytes:
    """The BOM as CSV (one row per part, a trailing TOTALS row)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    for row in model.rows:
        writer.writerow(
            [
                row.subject,
                row.kind,
                "UNSOURCED" if row.unsourced else row.part_number,
                str(row.unsourced).lower(),
                row.material,
                row.description,
                str(row.quantity),
                row.mass_g,
                row.mass_reason,
                row.material_pin,
                row.geometry_pin,
                row.total_cost,
                row.currency,
                row.cost_ref,
                row.cost_reason,
            ]
        )
    writer.writerow(
        [
            "TOTAL",
            "",
            "",
            "",
            "",
            "",
            "",
            model.total_mass_g,
            "",
            "",
            "",
            model.total_cost,
            model.currency,
            model.cost_profile or "",
            "",
        ]
    )
    return buf.getvalue().encode("ascii")


def render_bom_json(model: BomModel) -> bytes:
    """The BOM as canonical JSON (sorted keys, ascii, no whitespace)."""
    payload = model.model_dump(mode="json")
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def render_bom_md(model: BomModel) -> bytes:
    """The BOM as a GitHub-flavored markdown table + totals line."""
    header = "| subject | kind | part | qty | material | mass (g) | cost |"
    sep = "| --- | --- | --- | --- | --- | --- | --- |"
    lines = ["# Bill of Materials", ""]
    if model.cost_profile:
        lines.append(f"Cost profile: `{model.cost_profile}`")
        lines.append("")
    lines.extend([header, sep])
    for row in model.rows:
        part = "UNSOURCED" if row.unsourced else (row.part_number or "-")
        mass = row.mass_g or f"(empty: {row.mass_reason})"
        cost = row.total_cost or f"(empty: {row.cost_reason})"
        lines.append(
            f"| {row.subject} | {row.kind} | {part} | {row.quantity} "
            f"| {row.material or '-'} | {mass} | {cost} |"
        )
    lines.append("")
    lines.append(
        f"**Total mass:** {model.total_mass_g or '-'} g  "
        f"**Total cost:** {model.total_cost or '-'} {model.currency}  "
        f"**Unsourced rows:** {model.unsourced_count}"
    )
    lines.append("")
    return "\n".join(lines).encode("ascii")


def render_bom_pdf(model: BomModel) -> bytes:
    """The BOM as a PDF table, routed through the existing `DrawingModel`
    PDF renderer (charter 38 sec. 1.7: bom.pdf is a `DrawingModel` table
    through the existing renderer -- one PDF engine, never a second)."""
    from regolith.backends.drawings.renderer_pdf import render_pdf

    return render_pdf(bom_drawing_model(model))


def bom_drawing_model(model: BomModel):  # type: ignore[no-untyped-def]
    """Project the BOM into a one-table `DrawingModel` (the shared table/
    sheet IR) so the PDF renderer draws it exactly like any schedule."""
    from regolith._schema.models import (
        DrawingModel,
        Sheet,
        SheetSize1,
        Table,
        TableRow,
        TitleBlock,
    )

    columns = ["subject", "kind", "part", "qty", "material", "mass_g", "cost"]
    table_rows = [
        TableRow(
            cells=[
                row.subject,
                row.kind,
                "UNSOURCED" if row.unsourced else (row.part_number or "-"),
                str(row.quantity),
                row.material or "-",
                row.mass_g or "-",
                row.total_cost or "-",
            ]
        )
        for row in model.rows
    ]
    table_rows.append(
        TableRow(
            cells=[
                "TOTAL",
                "",
                "",
                "",
                "",
                model.total_mass_g or "-",
                model.total_cost or "-",
            ]
        )
    )
    sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title="Bill of Materials",
            drawing_number="BOM-1",
            revision="A",
            scale_label="NTS",
            subject="bom",
        ),
        views=[],
        entities=[],
        dimensions=[],
        annotations=[],
        tables=[Table(title="Bill of Materials", columns=columns, rows=table_rows)],
    )
    return DrawingModel(subject="bom", sheets=[sheet])


def register_bom_renderers(registry: RendererRegistry) -> Result[None, str]:
    """Register the four BOM renderers into ``registry`` under the ``bom``
    family (charter 38 sec. 1.2: one registration, zero dispatch edits)."""
    for reg in (
        RendererRegistration("csv", "bom.csv", BOM_FAMILY, render_bom_csv),
        RendererRegistration("json", "bom.json", BOM_FAMILY, render_bom_json),
        RendererRegistration("md", "bom.md", BOM_FAMILY, render_bom_md),
        RendererRegistration("pdf", "bom.pdf", BOM_FAMILY, render_bom_pdf),
    ):
        result = registry.register(reg)
        if result.is_err:
            return result
    return Ok(None)


# --- the backend ----------------------------------------------------------


class BomBackend:
    """The derived-BOM manufacturing backend: derive rows, render the four
    formats through the `bom` renderer family. Constructed with the
    caller's already-decided part lines + resolved records + estimates
    (regolith/07 sec. 6: it serializes what the build decided)."""

    def __init__(
        self,
        *,
        assembly_lines: tuple[AssemblyLine, ...] = (),
        materials: MaterialRecordSet | None = None,
        block_requirements: tuple[BlockRequirement, ...] = (),
        estimates: Mapping[str, ItemizedEstimate] = {},  # noqa: B006 (frozen input)
        cost_profile: str | None = None,
    ) -> None:
        """Bind the BOM's caller-decided inputs (see the class docstring)."""
        self._assembly_lines = assembly_lines
        self._materials = materials if materials is not None else MaterialRecordSet()
        self._block_requirements = block_requirements
        self._estimates = dict(estimates)
        self._cost_profile = cost_profile
        self._renderers = RendererRegistry()
        registered = register_bom_renderers(self._renderers)
        assert registered.is_ok, "built-in BOM renderer collision"

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Derive the BOM and emit ``bom.{csv,json,md,pdf}`` (deterministic)."""
        model = derive_bom_rows(
            inputs,
            assembly_lines=self._assembly_lines,
            materials=self._materials,
            block_requirements=self._block_requirements,
            estimates=self._estimates,
            cost_profile=self._cost_profile,
        )
        files: list[OutputFile] = []
        for reg in self._renderers.for_family(BOM_FAMILY):
            files.append(OutputFile.of(reg.suffix, reg.render(model)))
        _log.info(
            "bom backend: %d row(s), %d unsourced, emitted %d file(s)",
            len(model.rows),
            model.unsourced_count,
            len(files),
        )
        return Ok(tuple(files))
