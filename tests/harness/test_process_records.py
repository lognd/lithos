"""WO-168: the `std.process` record schema + DFM check-set contract.

Proves the acceptance criteria: `ProcessRecord`/`DfmCheckSet` require
`provenance` with no default (a bare-float, a missing posture, and a
dangling-lookalike DFM id are all refused); a round-trip constructs
one instance of every posture value (`pd_gov`, `gek`, `named_refusal`,
and the combined case) and asserts (de)serialization; the two seed
records (wire EDM, quench+temper) load and validate, including at
least one NAMED REFUSAL entry each; and a dummy `RealizerCapability`
registration can reference a seed record/check-set's identifiers
without type mismatch (WO-164 integration).
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

import pytest
from pydantic import ValidationError
from regolith._schema.models import FeatureProgram
from regolith.backends.capabilities import (
    CapabilityRegistry,
    RealizerCapability,
    ToolAdapterDescriptor,
)
from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    DfmCheckEntry,
    DfmCheckSet,
    MinFeature,
    ProcessRecord,
    ProvenanceNote,
    SizeLimit,
)
from regolith.harness.models.dfm.process_seeds import (
    QUENCH_TEMPER_CHECKS,
    QUENCH_TEMPER_RECORD,
    WIRE_EDM_CHECKS,
    WIRE_EDM_RECORD,
)


class _ProcessRecordKwargs(TypedDict):
    """Mirrors `ProcessRecord`'s field set precisely (not
    `dict[str, object]`) so `**kwargs` construction below type-checks
    against the model's real per-field types. `provenance` is
    `NotRequired` only so `test_process_record_requires_provenance`
    below can `del` it to prove the schema itself refuses the
    omission -- every other test still supplies it."""

    key: str
    name: str
    din_8580_class: str
    materials: tuple[str, ...]
    size_limits: tuple[SizeLimit, ...]
    tolerance_grades: tuple[object, ...]
    surface_finish: tuple[object, ...]
    min_features: tuple[MinFeature, ...]
    cost_drivers: tuple[object, ...]
    lead_class: str
    provenance: NotRequired[tuple[ProvenanceNote, ...]]
    dfm_check_ids: tuple[str, ...]


def _minimal_kwargs() -> _ProcessRecordKwargs:
    """A fully-populated `ProcessRecord` kwargs dict a test can
    selectively break."""
    return {
        "key": "std.process/toy",
        "name": "Toy process",
        "din_8580_class": "0.0.0",
        "materials": ("std.materials/toy",),
        "size_limits": (
            SizeLimit(
                dimension="thickness",
                min=DimensionedValue.of("1", "mm"),
                max=DimensionedValue.of("10", "mm"),
            ),
        ),
        "tolerance_grades": (),
        "surface_finish": (),
        "min_features": (
            MinFeature(feature="corner radius", value=DimensionedValue.of("0.1", "mm")),
        ),
        "cost_drivers": (),
        "lead_class": "hours",
        "provenance": (
            ProvenanceNote(posture="gek", scope="record", detail="toy consensus value"),
        ),
        "dfm_check_ids": ("toy.module:check_toy",),
    }


# --- schema refusals -------------------------------------------------


def test_process_record_requires_provenance() -> None:
    """A `ProcessRecord` with no `provenance` argument is refused (the
    field carries no default -- omission is a construction error, not
    a silently-empty tuple)."""
    kwargs = _minimal_kwargs()
    del kwargs["provenance"]
    with pytest.raises(ValidationError):
        ProcessRecord(**kwargs)


def test_process_record_requires_nonempty_provenance() -> None:
    """An explicit empty `provenance` tuple is refused too (the D269
    amendment: required means "at least one note", not "field present
    but empty")."""
    kwargs = _minimal_kwargs()
    kwargs["provenance"] = ()
    with pytest.raises(ValidationError):
        ProcessRecord(**kwargs)


def test_size_limit_refuses_bare_float() -> None:
    """`SizeLimit.min`/`.max` require a `DimensionedValue` (D262/
    INV-34) -- a bare float is a type error, not a silently-accepted
    unitless magnitude."""
    with pytest.raises(ValidationError):
        SizeLimit(dimension="thickness", min=1.0, max=10.0)  # type: ignore[arg-type]


def test_provenance_note_missing_posture_is_refused() -> None:
    """Constructing a `ProvenanceNote` with no `posture` at all is
    refused (the required-field, no-default posture marker)."""
    with pytest.raises(ValidationError):
        ProvenanceNote(scope="record", detail="x")  # ty: ignore[missing-argument]  # proving pydantic refuses the omission at runtime


def test_provenance_note_pd_gov_requires_citation_detail() -> None:
    with pytest.raises(ValidationError):
        ProvenanceNote(posture="pd_gov", scope="record", detail="")


def test_provenance_note_named_refusal_requires_source_and_lift() -> None:
    with pytest.raises(ValidationError):
        ProvenanceNote(
            posture="named_refusal",
            scope="record",
            detail="omitted a table",
        )


def test_dfm_check_set_requires_nonempty_checks() -> None:
    with pytest.raises(ValidationError):
        DfmCheckSet(family="toy", checks=())


def test_dfm_check_entry_dangling_id_is_a_plain_string() -> None:
    """`check_id` is a bare string cross-link (matching
    `RealizerCapability.dfm_checks`'s own string-tuple convention) --
    a DANGLING id (one naming no real callable) is still a valid
    `DfmCheckEntry` at the schema layer; resolving it against a real
    registry is a WO-169/170/171-era integration concern, not this
    schema's job. This test pins that boundary: a nonsense id
    round-trips cleanly, proving the schema does not silently invent
    a resolution check it was not asked to make."""
    entry = DfmCheckEntry(
        check_id="nonexistent.module:does_not_exist",
        provenance=ProvenanceNote(posture="gek", scope="record", detail="x"),
    )
    assert entry.check_id == "nonexistent.module:does_not_exist"


# --- provenance posture round-trip (all four combinations) -----------


@pytest.mark.parametrize(
    "note",
    [
        ProvenanceNote(posture="pd_gov", scope="record", detail="MIL-H-6875"),
        ProvenanceNote(posture="gek", scope="record", detail="engineering consensus"),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="omitted a copyrighted table",
            refused_source="ASM Handbook chart",
            lift_condition="a licensed copy is obtained",
        ),
    ],
)
def test_provenance_note_round_trips(note: ProvenanceNote) -> None:
    dumped = note.model_dump()
    restored = ProvenanceNote(**dumped)
    assert restored == note


def test_provenance_combined_gek_and_named_refusal_round_trips() -> None:
    """A record MAY combine a blanket `gek` posture with a
    `named_refusal` sub-note for one specific field (the dossier's
    ~20% mixed-posture finding) -- both notes coexist in one
    `provenance` tuple and round-trip."""
    kwargs = _minimal_kwargs()
    kwargs["provenance"] = (
        ProvenanceNote(posture="gek", scope="record", detail="blanket consensus"),
        ProvenanceNote(
            posture="named_refusal",
            scope="tolerance_grades",
            detail="omitted a specific vendor table",
            refused_source="vendor speeds/feeds table",
            lift_condition="a licensed copy is obtained",
        ),
    )
    record = ProcessRecord(**kwargs)
    dumped = record.model_dump()
    restored = ProcessRecord(**dumped)
    assert restored == record
    assert len(restored.provenance) == 2
    assert {n.posture for n in restored.provenance} == {"gek", "named_refusal"}


# --- seed records ------------------------------------------------------


@pytest.mark.parametrize("record", [WIRE_EDM_RECORD, QUENCH_TEMPER_RECORD])
def test_seed_record_round_trips(record: ProcessRecord) -> None:
    dumped = record.model_dump()
    restored = ProcessRecord(**dumped)
    assert restored == record


@pytest.mark.parametrize("check_set", [WIRE_EDM_CHECKS, QUENCH_TEMPER_CHECKS])
def test_seed_check_set_round_trips(check_set: DfmCheckSet) -> None:
    dumped = check_set.model_dump()
    restored = DfmCheckSet(**dumped)
    assert restored == check_set


def test_wire_edm_seed_carries_a_named_refusal() -> None:
    """Deliverable 4's demonstrated NAMED REFUSAL entry, wire EDM half
    (procres/subtractive.md #13: vendor EDM parameter tables refused)."""
    refusals = [n for n in WIRE_EDM_RECORD.provenance if n.posture == "named_refusal"]
    assert refusals, "wire EDM seed must carry at least one named_refusal note"
    assert "vendor" in refusals[0].refused_source.lower()


def test_quench_temper_seed_carries_a_named_refusal() -> None:
    """The quench+temper half's NAMED REFUSAL (ASM Handbook tempering
    curves, procres/heat_treatment.md #77)."""
    postures = QUENCH_TEMPER_RECORD.provenance
    refusals = [n for n in postures if n.posture == "named_refusal"]
    assert refusals, "quench+temper seed must carry at least one named_refusal note"
    assert "asm" in refusals[0].refused_source.lower()


def test_quench_temper_seed_carries_pd_gov_anchor() -> None:
    """Q&T is the dossier's strongest-sourced entry (MIL-H-6875) --
    the seed must preserve that pd_gov posture, not flatten it to gek."""
    postures = {n.posture for n in QUENCH_TEMPER_RECORD.provenance}
    assert "pd_gov" in postures


# --- WO-164 capability-registry integration ---------------------------


def test_seed_record_and_check_set_wire_into_a_capability() -> None:
    """A dummy `RealizerCapability` registration can reference the
    wire-EDM seed record's key and its check-set's check ids without
    type mismatch -- the `process_records`/`dfm_checks` string-tuple
    fields accept exactly the identifiers a real `ProcessRecord`/
    `DfmCheckSet` carries."""
    capability = RealizerCapability(
        domain="wire_edm_toy",
        program_kind=FeatureProgram,
        realized_kind="wire_edm_toy.realized",
        artifact_families=("mech",),
        tool_adapters=(ToolAdapterDescriptor(name="toy", tier="deterministic"),),
        process_records=(WIRE_EDM_RECORD.key,),
        dfm_checks=tuple(entry.check_id for entry in WIRE_EDM_CHECKS.checks),
        claim_kinds=("wire_edm_toy.profile_cut",),
    )
    registry = CapabilityRegistry()
    registry.register(capability)
    assert registry.domains() == ("wire_edm_toy",)
    assert capability.process_records == ("std.process/wire_edm",)
    assert set(capability.dfm_checks) == set(WIRE_EDM_RECORD.dfm_check_ids)
