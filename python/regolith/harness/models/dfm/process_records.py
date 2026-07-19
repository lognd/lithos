"""The `std.process` record schema + DFM check-set contract (WO-168,
D269 items 1-2 and the same-day amendment).

A `ProcessRecord` is one manufacturing process's capability envelope
(materials, size limits, tolerance grades, surface finish, min feature
sizes, cost drivers, lead-time class) -- the schema WO-169/170/171
populate with real families (wire EDM, quench+temper, stamping, ...).
This module ships the schema and contract ONLY, plus two seed records
(deliverable 4) that exercise every schema branch end to end; bulk
population is explicitly out of scope (WO-168 non-goals).

Provenance posture (D269 amendment) is a REQUIRED, owner-visible field
on every record and every DFM check entry -- never optional, never a
silent default -- because the process-research recon
(`procres/rollup.md`'s provenance-class distribution) found most of
this domain's textbook capability knowledge is uncited engineering
consensus (GEK), a real state of the world this schema names plainly
rather than dressing up as cited. Three postures:

- `pd_gov`: a spot-verified public-domain/government/standards source,
  cited in `detail`.
- `gek`: general-engineering-consensus, no citable government/
  standards source -- `detail` states the consensus plainly, never
  phrased as if it were cited.
- `named_refusal`: a SPECIFIC copyrighted table/source is named and
  explicitly declined -- `refused_source` names it, `detail` says what
  was omitted, `lift_condition` says what would make the refusal
  liftable (e.g. "a licensed copy of <source> is obtained").

A record's `provenance` is a tuple of notes rather than one enum,
because the dossiers found ~20% of entries mix a GEK-dominant blanket
posture with a `named_refusal` sub-note for one specific field (a
`scope` of `"record"` is the blanket note; any other `scope` value
names the specific field/value-group it covers).

DFM checks cite MORE specifically than a record's blanket posture (a
record mostly `gek` can carry one specific DFM rule that is `pd_gov`),
so `DfmCheckEntry.provenance` is its own single `ProvenanceNote`, not
inherited from the record.

Boundary posture (charter 39 sec. 4, same as `records.py` next door):
every value here is DECLARED data with an explicit citation-or-honest-
consensus-or-named-refusal note -- this module computes nothing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from regolith.backends.quantity import DimensionedValue

# The three owner-visible provenance postures (D269 amendment): a
# record/check MUST say which one applies, never omit the marker.
# frob:doc docs/modules/py-harness.md#models-dfm-process
ProvenancePosture = Literal["pd_gov", "gek", "named_refusal"]


# frob:doc docs/modules/py-harness.md#models-dfm-process
class ProvenanceNote(BaseModel):
    """One posture marker, either for a whole record/check (`scope ==
    "record"`) or for one named field/value-group (`scope` names it,
    e.g. `"tolerance_grades"`).

    `pd_gov` requires a non-empty `detail` (the citation). `gek`
    requires a non-empty `detail` (the plain consensus statement --
    never phrased as if cited). `named_refusal` requires both
    `refused_source` (the specific copyrighted table/source declined)
    and `lift_condition` (what would make the refusal liftable);
    `detail` for a refusal states what was omitted and why.
    """

    model_config = ConfigDict(frozen=True)

    posture: ProvenancePosture
    scope: str
    detail: str
    refused_source: str = ""
    lift_condition: str = ""

    @model_validator(mode="after")
    def _posture_shape(self) -> ProvenanceNote:
        """Refuse a posture note missing the fields its own posture
        requires -- the same unreachability doctrine `DimensionedValue`
        applies to a missing unit, applied here to a missing citation
        (`pd_gov`/`gek`) or a missing refusal name/lift condition
        (`named_refusal`)."""
        if not self.scope.strip():
            raise ValueError("ProvenanceNote.scope must not be blank")
        if self.posture in ("pd_gov", "gek") and not self.detail.strip():
            raise ValueError(
                f"ProvenanceNote posture={self.posture!r} requires a non-blank "
                "detail (citation for pd_gov, plain consensus statement for gek)"
            )
        if self.posture == "named_refusal":
            if not self.refused_source.strip():
                raise ValueError(
                    "ProvenanceNote posture='named_refusal' requires a non-blank "
                    "refused_source naming the specific declined table/source"
                )
            if not self.lift_condition.strip():
                raise ValueError(
                    "ProvenanceNote posture='named_refusal' requires a non-blank "
                    "lift_condition naming what would make the refusal liftable"
                )
        return self


# frob:doc docs/modules/py-harness.md#models-dfm-process
class SizeLimit(BaseModel):
    """One unit-carrying min/max envelope entry (D262/INV-34: no bare
    float -- both bounds are `DimensionedValue`). `dimension` names
    what is bounded (e.g. `"part_thickness"`, `"kerf_width"`)."""

    model_config = ConfigDict(frozen=True)

    dimension: str
    min: DimensionedValue
    max: DimensionedValue


# frob:doc docs/modules/py-harness.md#models-dfm-process
class ToleranceGrade(BaseModel):
    """One achievable tolerance class under a stated `condition` (e.g.
    `"multi-pass skim cut"` vs `"single-pass rough cut"`); `achievable`
    is the +/- band as a `DimensionedValue` (magnitude carries the
    range text verbatim, e.g. `"+/-0.002-0.01"`, unit `"mm"`)."""

    model_config = ConfigDict(frozen=True)

    condition: str
    achievable: DimensionedValue


# frob:doc docs/modules/py-harness.md#models-dfm-process
class SurfaceFinishEntry(BaseModel):
    """One achievable Ra (or equivalent) range under a stated
    `condition` (e.g. `"first rough pass"` vs `"final skim pass"`)."""

    model_config = ConfigDict(frozen=True)

    condition: str
    ra: DimensionedValue


# frob:doc docs/modules/py-harness.md#models-dfm-process
class MinFeature(BaseModel):
    """One minimum-producible-feature-size entry (`feature` names what,
    e.g. `"internal corner radius"`, `"case depth"`)."""

    model_config = ConfigDict(frozen=True)

    feature: str
    value: DimensionedValue


# frob:doc docs/modules/py-harness.md#models-dfm-process
class CostDriver(BaseModel):
    """One qualitative/quantitative cost-class factor, matching the
    dossier's own cost-driver framing (setup, per-part, tooling-
    amortization class) rather than inventing a new taxonomy.
    `driver` names the factor (e.g. `"setup"`, `"tooling_amortization"`);
    `driver_class` is the qualitative class (e.g. `"near-zero fixed
    tooling"`); `note` carries the dossier's own supporting text."""

    model_config = ConfigDict(frozen=True)

    driver: str
    driver_class: str
    note: str = ""


# frob:doc docs/modules/py-harness.md#models-dfm-process
class ProcessRecord(BaseModel):
    """One `std.process` capability-envelope record (WO-168
    deliverable 1). `key` is the record's stdlib key (AD-37 naming);
    `din_8580_class` is the DIN 8580 classification code (process
    identity); `materials` references `std.materials` keys by name
    (never free text -- T-0038's scope owns the actual material
    records); `dfm_check_ids` cross-links this record's process family
    to a `DfmCheckSet.checks[*].check_id` (the family's check-set
    contract, wired below).

    `provenance` is REQUIRED (no default) and non-empty -- the D269
    amendment's owner-visible posture marker, one or more
    `ProvenanceNote` entries (a `scope == "record"` blanket note, any
    number of field-scoped notes layered on top)."""

    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    din_8580_class: str
    materials: tuple[str, ...]
    size_limits: tuple[SizeLimit, ...]
    tolerance_grades: tuple[ToleranceGrade, ...]
    surface_finish: tuple[SurfaceFinishEntry, ...]
    min_features: tuple[MinFeature, ...]
    cost_drivers: tuple[CostDriver, ...]
    lead_class: str
    provenance: tuple[ProvenanceNote, ...]
    dfm_check_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _provenance_required(self) -> ProcessRecord:
        """Refuse a record with an empty `provenance` tuple -- required
        per D269 amendment means "at least one note", not "field
        present with an empty default"."""
        if not self.provenance:
            raise ValueError(
                f"ProcessRecord {self.key!r} must carry at least one "
                "ProvenanceNote (D269 amendment: provenance posture is "
                "required, never a silent default)"
            )
        return self


# frob:doc docs/modules/py-harness.md#models-dfm-process
class DfmCheckEntry(BaseModel):
    """One DFM check identifier within a family's check set (WO-168
    deliverable 2). `check_id` is a module-qualified callable name
    (`"module.path:function_name"`, the SAME convention
    `RealizerCapability.dfm_checks` already uses), resolving to a
    callable conforming to the uniform check contract: pure, takes
    declared-data keyword arguments specific to the family (mirroring
    `check_stock_fit`/`check_tool_fit`'s shape -- geometry/record
    inputs in, no hidden state), returns a `CamOutcome` (the ONE
    verdict shape every check family reuses -- excess/eps/
    indeterminate/citations/note, never a bespoke per-family result
    type). `provenance` is this check's OWN citation, independent of
    its record's blanket posture (a family record mostly `gek` can
    still carry one `pd_gov`-cited DFM rule)."""

    model_config = ConfigDict(frozen=True)

    check_id: str
    provenance: ProvenanceNote


# frob:doc docs/modules/py-harness.md#models-dfm-process
class DfmCheckSet(BaseModel):
    """One process family's DFM check-set CONTRACT (WO-168 deliverable
    2): the shape a family's check set must conform to (a non-empty
    tuple of `DfmCheckEntry`), not the checks' implementations
    themselves -- population of the actual callables is WO-169/170/171
    (or the mech/elec retrofits already landed). `family` is the
    process-family tag this check set gates (matching the family's
    `ProcessRecord.dfm_check_ids` entries)."""

    model_config = ConfigDict(frozen=True)

    family: str
    checks: tuple[DfmCheckEntry, ...]

    @model_validator(mode="after")
    def _checks_required(self) -> DfmCheckSet:
        """Refuse an empty check set -- a family with genuinely no DFM
        checks yet is a WO-169/170/171 population gap, not a valid
        contract instance (mirrors `RealizerCapability`'s own
        no-silent-empty-tuple discipline in `backends/capabilities.py`)."""
        if not self.checks:
            raise ValueError(
                f"DfmCheckSet {self.family!r} must carry at least one "
                "DfmCheckEntry (an empty check set is a population gap, "
                "not a valid contract instance)"
            )
        return self


__all__ = [
    "CostDriver",
    "DfmCheckEntry",
    "DfmCheckSet",
    "MinFeature",
    "ProcessRecord",
    "ProvenanceNote",
    "ProvenancePosture",
    "SizeLimit",
    "SurfaceFinishEntry",
    "ToleranceGrade",
]
