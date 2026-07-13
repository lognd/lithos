"""WO-112 Class 3 (F131 item 1a): D102 `stays_within` scalar-mask
translation -- an inline `floor(...)`/`ceiling(...)` mask level (units
SI-resolved at Rust lowering) becomes a scalar request limit with the
WO-54 rider's window threaded as an input; a NAMED mask reference
keeps the honest named deferral, naming the mask.
"""

from __future__ import annotations

from regolith._schema.models import Obligation
from regolith.orchestrator.translate import translate


def _stays_within(mask: str, *, window: dict | None = None) -> Obligation:
    form: dict = {"form": "stays_within", "signal": "v(out)", "mask": mask}
    if window is not None:
        form["window"] = window
    return Obligation.model_validate(
        {
            "claim": {"name": "sag", "form": form, "forall": [], "hints": []},
            "subject_ref": "test-subject",
            "given": {"materials": [], "loads": [], "backing": [], "refs": []},
            "hints": [],
        }
    )


class TestScalarMaskLowers:
    def test_floor_mask_level_becomes_the_limit(self) -> None:
        # The Rust lowering already SI-resolved `floor(5.0V - 150mV)`.
        result = translate(_stays_within("floor(5 - 0.15)"))
        assert result.is_ok, result
        request = result.danger_ok
        assert request.limit == 4.85
        assert request.claim_kind == "sag"

    def test_window_duration_rides_as_an_input(self) -> None:
        result = translate(
            _stays_within(
                "floor(3.3 - 0.09)",
                window={"within_after": {"duration": "0.0003", "event": "load_step"}},
            )
        )
        assert result.is_ok, result
        request = result.danger_ok
        assert request.limit == 3.3 - 0.09
        assert request.inputs["window_s"].lo == 0.0003

    def test_ceiling_mask_lowers_too(self) -> None:
        result = translate(_stays_within("ceiling(8.4)"))
        assert result.is_ok, result
        assert result.danger_ok.limit == 8.4


class TestNamedMaskHonestDeferral:
    def test_named_mask_defers_naming_the_mask(self) -> None:
        result = translate(_stays_within("CISPR_11_A"))
        assert result.is_err
        deferral = result.danger_err
        assert deferral.reason == "temporal_containment_unmodeled"
        assert "CISPR_11_A" in deferral.detail

    def test_mask_constructor_call_defers_named(self) -> None:
        # `cell_ovp(4.2V, 2)` is a named constructor, not an inline
        # scalar level -- never guessed at.
        result = translate(_stays_within("cell_ovp(4.2V, 2)"))
        assert result.is_err
        assert result.danger_err.reason == "temporal_containment_unmodeled"

    def test_unresolved_unit_term_defers_rather_than_misreads(self) -> None:
        # A floor(...) whose term still carries a unit suffix (i.e. the
        # Rust resolver did not reduce it) must NOT parse as a bare
        # float -- deferral, never `5.0V` read as `5.0` minus `150mV`
        # read as `150`.
        result = translate(_stays_within("floor(5.0V - 150mV)"))
        assert result.is_err
        assert result.danger_err.reason == "temporal_containment_unmodeled"
