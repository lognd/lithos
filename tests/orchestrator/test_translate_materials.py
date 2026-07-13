"""WO-112 Class 2: `material.<prop>` entity-derived bound resolution
(F131 item 2, the D103 residual F130 item 3 names).

Pure `translate()` behavior over synthetic obligations against the
REAL std.materials records (the corpus data path) -- both ways:

- a `material.sigma_y / <N>` bound literalizes from the pinned
  record (yield_MPa -> Pa, divided), the record pin lands on the
  context's INV-22 ledger, and the same resolution rides the D102
  temporal-reduction path (`peak(...)` claims);
- every named honest deferral (condition-call variants, unrecorded
  properties, missing/ambiguous keys, missing records) defers with
  its recorded reason, never a guess -- and a non-material bound
  still reaches the pre-existing generic `unresolved_limit`.
"""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import Obligation
from regolith.orchestrator.material_resolve import (
    MaterialContext,
    load_material_context,
    material_record_pins,
)
from regolith.orchestrator.translate import translate

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# AL_5052_H32 (stdlib/std.materials/records/aluminum.toml):
# yield_MPa = 193, ultimate_MPa = 228.
_AL5052_YIELD_PA = 193.0e6
_AL5052_ULTIMATE_PA = 228.0e6


def _material_context() -> MaterialContext:
    result = load_material_context(
        str(REPO_ROOT), record_search_paths=(str(REPO_ROOT / "stdlib"),)
    )
    assert result.is_ok, result
    return result.danger_ok


def _obligation(
    rhs: str,
    *,
    op: str = "<",
    materials: list[list[str]] | None = None,
    form: dict | None = None,
) -> Obligation:
    claim_form = form or {
        "form": "comparison",
        "lhs": "peak(mech.stress.von_mises, at=welded.tank.shell)",
        "op": op,
        "rhs": rhs,
    }
    return Obligation.model_validate(
        {
            "claim": {
                "name": "shell",
                "form": claim_form,
                "forall": [],
                "hints": [],
            },
            "subject_ref": "test-subject",
            "given": {
                "materials": materials
                if materials is not None
                else [["material", "AL_5052_H32"]],
                "loads": [],
                "backing": [],
                "refs": [],
            },
            "hints": [],
        }
    )


class TestMaterialBoundResolves:
    def test_sigma_y_with_divisor_literalizes(self) -> None:
        ctx = _material_context()
        result = translate(_obligation("material.sigma_y / 2.5"), material_context=ctx)
        assert result.is_ok, result
        assert result.danger_ok.limit == _AL5052_YIELD_PA / 2.5

    def test_sigma_y_bare_literalizes(self) -> None:
        ctx = _material_context()
        result = translate(_obligation("material.sigma_y"), material_context=ctx)
        assert result.is_ok, result
        assert result.danger_ok.limit == _AL5052_YIELD_PA

    def test_sigma_u_literalizes_from_ultimate(self) -> None:
        ctx = _material_context()
        result = translate(_obligation("material.sigma_u / 1.0"), material_context=ctx)
        assert result.is_ok, result
        assert result.danger_ok.limit == _AL5052_ULTIMATE_PA

    def test_trailing_given_suffix_is_tolerated(self) -> None:
        # The corpus rhs often carries the next-line `given p = ...`
        # suffix inside the lowered bound text.
        ctx = _material_context()
        rhs = "material.sigma_y / 1.5\n                   given p = 30000"
        result = translate(_obligation(rhs), material_context=ctx)
        assert result.is_ok, result
        assert result.danger_ok.limit == _AL5052_YIELD_PA / 1.5

    def test_resolution_pins_the_consumed_record(self) -> None:
        ctx = _material_context()
        translate(_obligation("material.sigma_y / 2.0"), material_context=ctx)
        pins = material_record_pins(ctx)
        assert len(pins) == 1
        key, digest = pins[0]
        assert key == "std.materials.material.AL_5052_H32@1"
        assert digest.startswith("sha256:")

    def test_temporal_reduction_path_resolves_the_same_bound(self) -> None:
        # The D102 `peak(x, within .. after ..)` reduction form's
        # entity-derived bound rides the SAME resolver (one home).
        ctx = _material_context()
        form = {
            "form": "peak",
            "signal": "mech.stress.von_mises",
            "window": {"within_after": {"duration": "0.002", "event": "spike"}},
            "op": "<",
            "rhs": "material.sigma_y / 1.8",
        }
        result = translate(_obligation("", form=form), material_context=ctx)
        assert result.is_ok, result
        assert result.danger_ok.limit == _AL5052_YIELD_PA / 1.8


class TestMaterialBoundHonestDeferrals:
    def test_condition_call_variant_defers_named(self) -> None:
        ctx = _material_context()
        result = translate(
            _obligation("material.sigma_y(T_local) / 1.4"), material_context=ctx
        )
        assert result.is_err
        assert result.danger_err.reason == "material_property_condition_unresolved"

    def test_unmapped_property_defers_named(self) -> None:
        ctx = _material_context()
        result = translate(
            _obligation("material.tau_allow / 1.25"), material_context=ctx
        )
        assert result.is_err
        assert result.danger_err.reason == "material_property_unrecorded"

    def test_missing_key_defers_named(self) -> None:
        ctx = _material_context()
        result = translate(
            _obligation("material.sigma_y / 2.0", materials=[]),
            material_context=ctx,
        )
        assert result.is_err
        assert result.danger_err.reason == "material_key_missing"

    def test_ambiguous_keys_defer_named(self) -> None:
        ctx = _material_context()
        result = translate(
            _obligation(
                "material.sigma_y / 2.0",
                materials=[["material", "AL_5052_H32"], ["material", "AISI_4140"]],
            ),
            material_context=ctx,
        )
        assert result.is_err
        assert result.danger_err.reason == "material_key_ambiguous"

    def test_unknown_record_defers_named(self) -> None:
        ctx = _material_context()
        result = translate(
            _obligation(
                "material.sigma_y / 2.0", materials=[["material", "UNOBTAINIUM_9"]]
            ),
            material_context=ctx,
        )
        assert result.is_err
        assert result.danger_err.reason == "material_record_missing"

    def test_no_context_defers_named(self) -> None:
        result = translate(_obligation("material.sigma_y / 2.0"))
        assert result.is_err
        assert result.danger_err.reason == "material_records_unconfigured"

    def test_arithmetic_beyond_divisor_falls_through(self) -> None:
        # `material.sigma_y + 10` is arithmetic this resolver does not
        # model: the pre-existing generic deferral stands (never a
        # silently wrong number).
        ctx = _material_context()
        result = translate(_obligation("material.sigma_y + 10"), material_context=ctx)
        assert result.is_err
        assert result.danger_err.reason == "unresolved_limit"

    def test_non_material_bound_keeps_generic_deferral(self) -> None:
        ctx = _material_context()
        result = translate(_obligation("design_life"), material_context=ctx)
        assert result.is_err
        assert result.danger_err.reason == "unresolved_limit"
