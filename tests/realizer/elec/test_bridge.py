"""The binding-requirement bridge (WO-29 deliverable 4, Python half).

D90 split: the Rust lowering emits raw capability demands
(``_schema.models.BlockRequirement``); this bridge screens -- mapping
them to numeric ``binding.BlockRequirement`` minimums and deriving
``ComponentCandidate``s from magnetite records -- then WO-24's EXISTING
``bind_all`` runs end to end with no hand-built requirement fixture.
"""

from __future__ import annotations

from regolith._schema.models import BlockRequirement as RawBlockRequirement
from regolith._schema.models import CapabilityDemand
from regolith.magnetite.records import Evidence, Record, RecordKey, RecordStore
from regolith.realizer.elec.binding import bind_all
from regolith.realizer.elec.bridge import (
    candidates_by_block,
    parse_magnitude,
    screening_requirement,
    screening_requirements,
)


def test_parse_magnitude_scales_si_prefixes() -> None:
    assert parse_magnitude("20Mops f32 sustained") == 20e6
    assert parse_magnitude("40MB/s") == 40e6
    assert parse_magnitude("1Gops fixed") == 1e9
    assert parse_magnitude("2 cycles") == 2.0
    assert parse_magnitude("320kB") == 320e3
    assert parse_magnitude("no number here") is None
    assert parse_magnitude("") is None


# frob:tests python/regolith/realizer/elec/bridge.py::screening_requirement kind="unit"
def test_primary_bound_keys_by_contract_kind() -> None:
    """A bare ``>= 20Mops`` on an executor keys by the contract kind."""
    raw = RawBlockRequirement(
        owner="FlightCore",
        block="cpu0",
        contract="executor",
        demands=[
            CapabilityDemand(
                capability="", comparator=">=", value="20Mops f32 sustained"
            )
        ],
    )
    req = screening_requirement(raw)
    assert req.block == "cpu0"
    assert req.min_capabilities == {"executor": 20e6}


def test_named_minimum_demand_keys_by_capability_name() -> None:
    raw = RawBlockRequirement(
        owner="A",
        block="dma",
        contract="mover",
        demands=[
            CapabilityDemand(capability="bandwidth", comparator=">", value="40MB/s")
        ],
    )
    assert screening_requirement(raw).min_capabilities == {"bandwidth": 40e6}


def test_ceiling_demands_are_skipped_not_reversed() -> None:
    """`<=`/`==` demands are a screen direction WO-24 does not model."""
    raw = RawBlockRequirement(
        owner="A",
        block="sram",
        contract="memory",
        demands=[
            CapabilityDemand(capability="latency", comparator="<=", value="2 cycles")
        ],
    )
    assert screening_requirement(raw).min_capabilities == {}


def _component(pkg: str, key: str, rev: int, caps: dict[str, float]) -> Record:
    return Record(
        address=RecordKey(package=pkg, key=key, revision=rev),
        kind="component",
        content_hash="sha256:deadbeef",
        evidence=Evidence(method="catalog", trust_tier="T1", reference="ds"),
        capabilities=caps,
    )


def test_candidates_by_block_resolves_through_the_store() -> None:
    rec = _component("mcu", "stm32g474", 1, {"executor": 25e6})
    store = RecordStore((rec,))
    result = candidates_by_block(
        store, {"cpu0": [RecordKey(package="mcu", key="stm32g474", revision=1)]}
    )
    assert result.is_ok
    table = result.danger_ok
    assert table["cpu0"][0].record_key == "mcu/stm32g474@1"
    assert table["cpu0"][0].capabilities == {"executor": 25e6}


def test_missing_record_is_an_error_value() -> None:
    store = RecordStore(())
    result = candidates_by_block(
        store, {"cpu0": [RecordKey(package="mcu", key="absent", revision=1)]}
    )
    assert result.is_err


# frob:tests python/regolith/realizer/elec/bridge.py::screening_requirements kind="unit"
def test_end_to_end_raw_payload_drives_wo24_search() -> None:
    """Raw payload demands + records -> screening models -> a bound pin,
    with no hand-built requirement/candidate fixture in the loop."""
    raws = [
        RawBlockRequirement(
            owner="FlightCore",
            block="cpu0",
            contract="executor",
            demands=[
                CapabilityDemand(
                    capability="", comparator=">=", value="20Mops f32 sustained"
                )
            ],
        )
    ]
    weak = _component("mcu", "tiny", 1, {"executor": 5e6})
    strong = _component("mcu", "stm32g474", 1, {"executor": 25e6})
    store = RecordStore((weak, strong))

    requirements = screening_requirements(raws)
    table_result = candidates_by_block(
        store,
        {
            "cpu0": [
                RecordKey(package="mcu", key="tiny", revision=1),
                RecordKey(package="mcu", key="stm32g474", revision=1),
            ]
        },
    )
    assert table_result.is_ok
    table = table_result.danger_ok

    result = bind_all(requirements, table)
    assert result.is_ok
    pins = result.danger_ok.pins
    assert len(pins) == 1
    # The weak 5Mops part fails the 20Mops screen; the search lands on
    # the 25Mops part.
    assert pins[0].record_key == "mcu/stm32g474@1"
