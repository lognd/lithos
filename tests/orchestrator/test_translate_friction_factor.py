"""WO-139 (D258.3/F158 GAP a1/a3): the fluids.dp friction-factor
input chain -- a missing `friction_factor` DERIVES from the std.fluid
`[[roughness]]` record (WO-138) + the claim's own diameter/density/
velocity/viscosity, via `FrictionFactorModel`, INSTEAD OF only
accepting an inline declaration (AD-22: an inline `friction_factor=`
kwarg still wins when present -- unchanged, checked here too).
Fixtures against the REAL stdlib `roughness.toml`/`media.toml` rows.
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

# stdlib/std.fluid/records/roughness.toml: commercial_steel, e = 4.6e-5 m.
_COMMERCIAL_STEEL_ROUGHNESS_M = 4.6e-5
# stdlib/std.fluid/records/media.toml: water_iapws_liquid mu = 5.96e-4 Pa*s.
_WATER_MU = 5.96e-4


def _fluid_context() -> FluidContext:
    payload = {
        "flownets": {
            "TestLoop": {
                "medium": {"records": [{"name": "water_iapws_liquid", "digest": ""}]}
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


def _dp_obligation(args_text: str, loads: tuple[str, ...] = ()) -> Obligation:
    return Obligation.model_validate(
        {
            "claim": {
                "name": "supply_dp",
                "form": {
                    "form": "comparison",
                    "lhs": f"fluids.dp({args_text})",
                    "op": "<=",
                    "rhs": "300",
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
            "payloads": [{"kind": "flownet", "digest": "d" * 64, "origin": "TestLoop"}],
        }
    )


class TestDerivedFrictionFactor:
    def test_friction_factor_derives_from_the_roughness_record(self) -> None:
        """Turbulent Re, commercial_steel roughness: friction_factor
        resolves without an inline declaration, and the roughness
        record's INV-22 pin is consumed."""
        ctx = _fluid_context()
        args = (
            "a -> b, material=commercial_steel, length_m=2.0, "
            "diameter_m=0.05, density_kgm3=990.0, velocity_ms=2.0"
        )
        result = translate(_dp_obligation(args), fluid_context=ctx)
        assert result.is_ok, result
        request = result.danger_ok
        f = request.inputs["friction_factor"]
        assert f.lo > 0.0
        assert f.hi >= f.lo
        # Sanity: turbulent commercial-steel water flow sits in the
        # ordinary 0.01-0.05 Darcy-factor band (Moody chart range).
        assert 0.005 < f.lo < 0.1

        pins = dict(fluid_record_pins(ctx))
        assert "std.fluid.roughness.commercial_steel@1" in pins
        assert "std.fluid.medium.water_iapws_liquid@1" in pins

    def test_inline_friction_factor_still_wins_ad22(self) -> None:
        """An inline `friction_factor=` declaration is the AD-22
        override -- the derivation is never attempted, and no
        roughness record is consumed."""
        ctx = _fluid_context()
        args = (
            "a -> b, friction_factor=0.03, material=commercial_steel, "
            "length_m=2.0, diameter_m=0.05, density_kgm3=990.0, "
            "velocity_ms=2.0"
        )
        result = translate(_dp_obligation(args), fluid_context=ctx)
        assert result.is_ok, result
        request = result.danger_ok
        assert request.inputs["friction_factor"].lo == 0.03
        assert fluid_record_pins(ctx) == ()

    def test_no_material_kwarg_leaves_friction_factor_undetermined(self) -> None:
        """A claim naming no `material=` keeps the prior behavior: no
        derivation is attempted, and a still-missing friction_factor
        defers exactly as before WO-139."""
        ctx = _fluid_context()
        args = (
            "a -> b, length_m=2.0, diameter_m=0.05, density_kgm3=990.0, velocity_ms=2.0"
        )
        result = translate(_dp_obligation(args), fluid_context=ctx)
        assert result.is_err
        assert "friction_factor" in result.danger_err.detail

    def test_transition_band_defers_honestly_never_a_numeric_value(self) -> None:
        """A derived Re landing in [2300, 4000] (D258 ruling 3) never
        yields a numeric friction_factor -- the claim defers, naming
        the honest indeterminate reason."""
        ctx = _fluid_context()
        # Re = rho*v*D/mu = 990 * v * 0.02 / 5.96e-4; pick v so Re ~ 3000.
        velocity = 3000.0 * _WATER_MU / (990.0 * 0.02)
        args = (
            f"a -> b, material=commercial_steel, length_m=1.0, "
            f"diameter_m=0.02, density_kgm3=990.0, velocity_ms={velocity:.6f}"
        )
        result = translate(_dp_obligation(args), fluid_context=ctx)
        assert result.is_err
        deferral = result.danger_err
        assert "friction_factor" in deferral.detail
        assert "transition" in deferral.detail.lower()
