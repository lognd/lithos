"""T-0038 (D270 ruling 4 companion): validates
`stdlib/std.materials/records/metallurgy.toml` against
`tools/stdlib/materials_schema.py`'s pydantic mirror, and proves the
mirror is STRUCTURALLY COMPATIBLE with `feldspar.materials.records.
MaterialRecord`'s real consumption shape (D270 ruling 1: "feldspar
gets the MODELS ... lithos stdlib gets the RECORDS"). Only this test
module imports feldspar -- the schema module under test
(`tools/stdlib/materials_schema.py`) never does, so stdlib loading
stays feldspar-checkout-optional (WO-109/D223 degrade-honestly
posture); the editable feldspar link exists for tests per this
ticket's own dispatch brief.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.stdlib.materials_schema import (
    ProvenanceNote,
    load_metallurgy_records,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
METALLURGY_TOML = (
    REPO_ROOT / "stdlib" / "std.materials" / "records" / "metallurgy.toml"
)

_EXPECTED_KEYS = {
    "AISI_D2_ANN",
    "AISI_D2_QT",
    "AISI_A2_ANN",
    "AISI_A2_QT",
    "AISI_1018",
    "ASTM_A36",
}


def _load():
    result = load_metallurgy_records(METALLURGY_TOML)
    assert result.is_ok, result
    return result.danger_ok


# --- lithos-side schema validity --------------------------------------------


# frob:tests tools/stdlib/materials_schema.py::load_metallurgy_records kind="unit"
# frob:tests tools/stdlib/materials_schema.py kind="integration"
def test_metallurgy_file_loads_all_first_slice_keys() -> None:
    """The D268 die-set first slice (D2/A2 tool steel + 1018/A36 mild
    steel) loads with exactly the keys the ticket's acceptance names."""
    records = _load()
    keys = {r.key for r in records}
    assert keys == _EXPECTED_KEYS, keys


def _refusal_of(notes: tuple[ProvenanceNote, ...]) -> ProvenanceNote:
    refusals = [n for n in notes if n.posture == "named_refusal"]
    assert len(refusals) == 1, notes
    return refusals[0]


@pytest.mark.parametrize("key", sorted(_EXPECTED_KEYS))
# frob:tests tools/stdlib/materials_schema.py::CompositionRange.to_feldspar_mass_fractions kind="unit"
def test_metallurgy_record_provenance_is_named(key: str) -> None:
    """Every record carries three non-empty provenance-note TUPLES
    (composition/crystal/cost), each note with a real posture marker --
    no silent 'trust me' (D269 amendment: provenance is a tuple, not a
    single enum, since a blanket gek note commonly pairs with a
    named_refusal sub-note)."""
    records = {r.key: r for r in _load()}
    record = records[key]
    for notes in (
        record.composition_provenance,
        record.crystal_provenance,
        record.cost_provenance,
    ):
        assert notes, "provenance tuple must be non-empty"
        for note in notes:
            assert isinstance(note, ProvenanceNote)
            assert note.posture in {"pd_gov", "gek", "named_refusal"}
            assert note.detail.strip()


def test_tool_steel_composition_provenance_names_its_refusal() -> None:
    """D2/A2 rows carry a NAMED REFUSAL of the specific copyrighted
    ASTM A681 table they decline to transcribe (D270/D269 licensing
    law) -- not just a bare GEK claim with nothing named."""
    records = {r.key: r for r in _load()}
    for key in ("AISI_D2_ANN", "AISI_D2_QT", "AISI_A2_ANN", "AISI_A2_QT"):
        refusal = _refusal_of(records[key].composition_provenance)
        assert refusal.refused_source is not None
        assert "A681" in refusal.refused_source


def test_mild_steel_composition_provenance_names_its_refusal() -> None:
    """1018/A36 rows each name the specific copyrighted standard table
    (SAE J403 / ASTM A36) they decline to transcribe."""
    records = {r.key: r for r in _load()}
    refusal_1018 = _refusal_of(records["AISI_1018"].composition_provenance)
    assert refusal_1018.refused_source is not None
    assert "J403" in refusal_1018.refused_source
    refusal_a36 = _refusal_of(records["ASTM_A36"].composition_provenance)
    assert refusal_a36.refused_source is not None
    assert "A36" in refusal_a36.refused_source


def test_composition_ranges_bracket_typical() -> None:
    """Every element's typical point value lies within its own cited
    [min, max] range -- the invariant `ElementRange` enforces at
    construction, re-checked here against the real file content."""
    for record in _load():
        for element, rng in record.composition.elements.items():
            assert rng.min <= rng.typical <= rng.max, (record.key, element)


def test_tool_steel_and_mild_steel_cost_classes_differ() -> None:
    """The D268 die-set demo needs a real cost-class distinction between
    the alloyed tool steels and the commodity mild-steel plate --
    otherwise the 'cost class' column would carry no information."""
    records = {r.key: r for r in _load()}
    assert records["AISI_D2_ANN"].cost_class == "medium"
    assert records["AISI_1018"].cost_class == "low"
    assert records["ASTM_A36"].cost_class == "low"


# --- feldspar structural compatibility (T-0018 consumption contract) -------


def test_every_record_constructs_a_real_feldspar_material_record() -> None:
    """Structural-compatibility proof (D270 ruling 1): every lithos
    metallurgy record's (composition.typical, crystal_structure,
    condition, cost_class) constructs a REAL
    `feldspar.materials.records.MaterialRecord` with no validation
    error -- proving field-name and type compatibility without the
    shipped schema module importing feldspar."""
    from feldspar.materials.records import (
        Composition,
        CrystalStructure,
        MaterialRecord,
    )

    for record in _load():
        composition = Composition(
            base_element=record.composition.base_element,
            mass_fractions=record.composition.to_feldspar_mass_fractions(),
        )
        crystal_structure = CrystalStructure(
            system=record.crystal_structure.system,
            lattice_a_m=record.crystal_structure.lattice_a_m,
            lattice_c_m=record.crystal_structure.lattice_c_m,
        )
        feldspar_record = MaterialRecord(
            name=record.name,
            composition=composition,
            crystal_structure=crystal_structure,
            condition=record.condition,
            cost_class=record.cost_class,
        )
        assert feldspar_record.name == record.name
        assert feldspar_record.condition == record.condition
        assert feldspar_record.cost_class == record.cost_class
