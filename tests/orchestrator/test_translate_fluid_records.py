"""WO-112 Class 4 (F131.4): the fluids.dp medium record-chain walk --
a missing `density_kgm3` resolves through obligation -> flownet
payload -> `medium.records` -> the std.fluid `[[medium]]` row, pinned
INV-22; a named-but-unloaded record stays an honest NAMED gap and a
declared given always beats the record. Fixtures both ways, against
the REAL stdlib records (the `water` row).
"""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import Obligation
from regolith.orchestrator.fluid_resolve import (
    FluidContext,
    fluid_record_pins,
    load_fluid_context,
)
from regolith.orchestrator.translate import translate

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# stdlib/std.fluid/records/media.toml: water at 293.15K/101325Pa.
_WATER_RHO = 998.2

# The model's full input set minus density (fluid_pressure_drop.INPUTS).
_OTHER_INPUTS = (
    "friction_factor: 0.02",
    "length_m: 2.0",
    "diameter_m: 0.004",
    "velocity_ms: 1.2",
)


def _fluid_context(medium_records: list[str]) -> FluidContext:
    payload = {
        "flownets": {
            "BrewPath": {
                "medium": {
                    "records": [{"name": n, "digest": ""} for n in medium_records]
                }
            }
        }
    }
    result = load_fluid_context(
        str(REPO_ROOT),
        build_payload=payload,
        record_search_paths=(str(REPO_ROOT / "stdlib"),),
    )
    assert result.is_ok, result
    return result.danger_ok


def _dp_obligation(loads: tuple[str, ...]) -> Obligation:
    return Obligation.model_validate(
        {
            "claim": {
                "name": "supply_dp",
                "form": {
                    "form": "comparison",
                    "lhs": "fluids.dp(pump_out -> boiler_in)",
                    "op": "<=",
                    "rhs": "30000",
                },
                "forall": [],
                "hints": [],
            },
            "subject_ref": "test-subject",
            "given": {
                "materials": [],
                "loads": list(loads),
                "backing": [],
                "refs": [],
            },
            "hints": [],
            "payloads": [{"kind": "flownet", "digest": "d" * 64, "origin": "BrewPath"}],
        }
    )


class TestDensityWalks:
    def test_density_resolves_from_the_medium_record(self) -> None:
        ctx = _fluid_context(["water"])
        result = translate(_dp_obligation(_OTHER_INPUTS), fluid_context=ctx)
        assert result.is_ok, result
        request = result.danger_ok
        assert request.inputs["density_kgm3"].lo == _WATER_RHO
        pins = fluid_record_pins(ctx)
        assert len(pins) == 1
        assert pins[0][0] == "std.fluid.medium.water@1"

    def test_declared_given_beats_the_record(self) -> None:
        ctx = _fluid_context(["water"])
        loads = (*_OTHER_INPUTS, "density_kgm3: 1050.0")
        result = translate(_dp_obligation(loads), fluid_context=ctx)
        assert result.is_ok, result
        assert result.danger_ok.inputs["density_kgm3"].lo == 1050.0
        # Nothing consumed: the record never supplied the input.
        assert fluid_record_pins(ctx) == ()


class TestHonestGaps:
    def test_unloaded_record_defers_naming_the_record(self) -> None:
        # The corpus shape today: the design names a record
        # (`egw_60_40`, the glycol mix) no search path carries -- the
        # WO-113 close-out's refused record (no offline-verifiable
        # table; water_iapws_liquid landed in stdlib that pass, so it
        # no longer serves as the unloaded fixture). The deferral
        # names both the missing input AND the unloaded record.
        ctx = _fluid_context(["egw_60_40"])
        result = translate(_dp_obligation(_OTHER_INPUTS), fluid_context=ctx)
        assert result.is_err
        deferral = result.danger_err
        assert deferral.reason == "fluids.dp_inputs_missing"
        assert "density_kgm3" in deferral.detail
        assert "egw_60_40" in deferral.detail

    def test_no_context_defers_exactly_as_before(self) -> None:
        result = translate(_dp_obligation(_OTHER_INPUTS))
        assert result.is_err
        assert result.danger_err.reason == "fluids.dp_inputs_missing"

    def test_other_missing_inputs_still_defer_after_density_walks(self) -> None:
        # The walk closes ONLY what the record honestly carries: with
        # no declared length/velocity/...' the claim still defers,
        # naming exactly those (never fabricated).
        ctx = _fluid_context(["water"])
        result = translate(_dp_obligation(()), fluid_context=ctx)
        assert result.is_err
        deferral = result.danger_err
        assert deferral.reason == "fluids.dp_inputs_missing"
        missing_part = deferral.detail.split("(need")[0]
        assert "density_kgm3" not in missing_part
        assert "length_m" in missing_part
