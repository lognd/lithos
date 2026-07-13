"""WO-112 Class 1: the two F131 2(c)-excluded predicate families get
NAMED deferrals (ledger row + reopen criterion in the detail), and
every other unrecognized shape still reaches the generic
`unsupported_op` deferral -- fixtures both ways.
"""

from __future__ import annotations

from regolith._schema.models import Obligation
from regolith.orchestrator.translate import translate


def _require(rhs: str) -> Obligation:
    return Obligation.model_validate(
        {
            "claim": {
                "name": "c",
                "form": {"form": "comparison", "lhs": "c", "op": "require", "rhs": rhs},
                "forall": [],
                "hints": [],
            },
            "subject_ref": "test-subject",
            "given": {"materials": [], "loads": [], "backing": [], "refs": []},
            "hints": [],
        }
    )


class TestF131NamedExclusions:
    def test_temporal_state_form_is_named_f131_1(self) -> None:
        # The espresso controller / cnc estop corpus shape.
        result = translate(
            _require("within 0.1 after shot_start: state(cmd_v3) = brew")
        )
        assert result.is_err
        deferral = result.danger_err
        assert deferral.reason == "temporal_event_form_excluded"
        assert "F131.1" in deferral.detail

    def test_op_transition_form_is_named_f131_1(self) -> None:
        result = translate(_require("within 0.002 after limit_hit: op = estop"))
        assert result.is_err
        assert result.danger_err.reason == "temporal_event_form_excluded"

    def test_unit_word_duration_matches_too(self) -> None:
        # `within 1 cycle after amo_issued: settles(rdata, to=+-0)`
        # (the riscv atomicity shape) -- the duration may carry a unit
        # WORD, not only a suffixed quantity.
        result = translate(
            _require("within 1 cycle after amo_issued:\n    settles(rdata, to=+-0)")
        )
        assert result.is_err
        assert result.danger_err.reason == "temporal_event_form_excluded"

    def test_bits_legality_form_is_named_f131_2(self) -> None:
        result = translate(
            _require("forall v in bits(fcsr_rw)[0 .. 3]: v != 5 and v != 6")
        )
        assert result.is_err
        deferral = result.danger_err
        assert deferral.reason == "bitfield_legality_form_excluded"
        assert "F131.2" in deferral.detail
        assert "D202" in deferral.detail


class TestGenericFormsStayGeneric:
    def test_other_unrecognized_forms_keep_unsupported_op(self) -> None:
        result = translate(_require("assume!(vent_valve_seals(x) == true)"))
        assert result.is_err
        assert result.danger_err.reason == "unsupported_op"

    def test_plain_forall_without_bits_stays_generic(self) -> None:
        # A forall over a non-bits domain is NOT the F131.2 family.
        result = translate(_require("forall op in modes: elec.power(all) <= 5"))
        assert result.is_err
        assert result.danger_err.reason == "unsupported_op"
