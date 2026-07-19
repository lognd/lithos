"""Registry + signature/impl matching (harness Phase C).

Covers: registration + deterministic candidate order, matching by claim
kind + inputs, the honest no-model outcome (a value, never a silent
pass), and version threading into the registry.
"""

from __future__ import annotations

from regolith.harness import (
    MODEL_PIN_UNMATCHED_ID,
    MODEL_REGISTRY_VERSION,
    NO_MODEL_ID,
    DischargeRequest,
    Interval,
    Model,
    ModelRegistry,
    ModelSignature,
    Prediction,
    default_registry,
)
from regolith.harness.errors import HarnessError, NoModelMatch
from regolith.harness.models.buck_ripple import CLAIM_KIND
from regolith.harness.signature import ClaimSense
from typani.result import Ok, Result


def _buck_request(claim_kind: str = CLAIM_KIND) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=claim_kind,
        limit=0.02,
        inputs={
            "v_in": Interval.point(12.0),
            "v_out": Interval.point(5.0),
            "f_sw": Interval.point(500e3),
            "l": Interval.point(22e-6),
            "c_out": Interval.point(47e-6),
        },
    )


class _FakeExpensive(Model):
    """A second model for CLAIM_KIND, higher cost -- tie-break fodder."""

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="fake_expensive",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=("v_in", "v_out", "f_sw", "l", "c_out"),
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        return 99

    # frob:waive TEST005 reason="test-file fixture/helper with environment-gated branches (tool-absent paths unreachable in a kicad-less env); TEST005 measuring test code is a tool quirk (TEST001 skips test files, TEST005 does not) -- FROBLEMS 2026-07-19"
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        return Ok(Prediction(value=0.0, eps=0.0))


def test_default_registry_stamped_with_model_registry_version() -> None:
    """The registry version is the harness constant (BE-1/INV-1)."""
    assert default_registry().version == MODEL_REGISTRY_VERSION


def test_select_matches_by_claim_kind_and_inputs() -> None:
    """A request whose kind + inputs match selects the buck model."""
    selected = default_registry().select(_buck_request())
    assert selected.is_ok
    assert selected.danger_ok.signature.claim_kind == CLAIM_KIND


def test_candidates_ordered_by_cost_then_id() -> None:
    """Selection is deterministic: cheapest model wins the tie."""
    reg = default_registry()
    reg.register(_FakeExpensive())
    candidates = reg.candidates(CLAIM_KIND)
    assert [m.cost for m in candidates] == sorted(m.cost for m in candidates)
    # The cheap real model (cost 1) is chosen over the fake (cost 99).
    assert reg.select(_buck_request()).danger_ok.cost == 1


def test_select_no_match_is_an_explicit_value() -> None:
    """An unknown claim kind yields Err(NoModelMatch), not an exception."""
    result = default_registry().select(_buck_request(claim_kind="does.not.exist"))
    assert result.is_err
    err = result.danger_err
    assert isinstance(err, NoModelMatch)
    assert err.claim_kind == "does.not.exist"


def test_select_missing_input_is_no_match() -> None:
    """A matching kind but absent required input does not silently match."""
    req = _buck_request().model_copy(update={"inputs": {"v_in": Interval.point(12.0)}})
    assert default_registry().select(req).is_err


def test_discharge_no_model_is_indeterminate_not_pass() -> None:
    """No model -> an honest indeterminate evidence value (never a pass)."""
    evidence = default_registry().discharge(_buck_request(claim_kind="nope"))
    assert evidence.model_id == NO_MODEL_ID
    assert evidence.status.value == "indeterminate"


def test_try_discharge_reports_no_model_value() -> None:
    """try_discharge surfaces the NoModelMatch value for inspection."""
    result = default_registry().try_discharge(_buck_request(claim_kind="nope"))
    assert result.is_err
    assert isinstance(result.danger_err, NoModelMatch)


def test_empty_registry_matches_nothing() -> None:
    """A fresh registry has no models; every select is a no-match."""
    assert ModelRegistry().select(_buck_request()).is_err


# WO-80 deliverable 3 (regolith/12 sec. 2 rung 5): a `model=<ident>` pin
# honors exact-id lookup, skips cost order, and a no-match is an honest
# `harness.model_pin_unmatched` indeterminate -- NEVER a fallback to a
# different (unpinned) model.


def test_pinned_request_selects_by_signature_name_ignoring_cost() -> None:
    """A pin naming the EXPENSIVE model's bare signature name wins over
    the normally-cheaper default, because cost order is skipped
    entirely once a request is pinned."""
    reg = default_registry()
    reg.register(_FakeExpensive())
    req = _buck_request().model_copy(update={"model_pin": "fake_expensive"})
    selected = reg.select(req)
    assert selected.is_ok
    assert selected.danger_ok.model_id == "fake_expensive@1"


def test_pinned_request_selects_by_full_model_id() -> None:
    """A pin naming the full `name@version` model id also matches."""
    reg = default_registry()
    reg.register(_FakeExpensive())
    req = _buck_request().model_copy(update={"model_pin": "fake_expensive@1"})
    selected = reg.select(req)
    assert selected.is_ok
    assert selected.danger_ok.model_id == "fake_expensive@1"


def test_pinned_request_with_no_match_is_honest_indeterminate() -> None:
    """A pin naming a model this registry never registered NEVER falls
    back to another model for the same claim kind -- it is an explicit
    `NoModelMatch` carrying `pinned`, and `discharge` stamps the
    DISTINCT `harness.model_pin_unmatched` marker (not the generic
    `harness.no_model`, not a pass)."""
    req = _buck_request().model_copy(update={"model_pin": "fea_contact"})
    selected = default_registry().select(req)
    assert selected.is_err
    err = selected.danger_err
    assert isinstance(err, NoModelMatch)
    assert err.pinned == "fea_contact"

    evidence = default_registry().discharge(req)
    assert evidence.model_id == MODEL_PIN_UNMATCHED_ID
    assert evidence.status.value == "indeterminate"


def test_pin_never_forges_a_pass_even_with_a_cheaper_match_available() -> None:
    """The un-pinned cheap default model matches this request's kind,
    but the pin names a DIFFERENT (unregistered) model -- rung 5's law:
    a forced model that cannot close the margin yields indeterminate,
    never silently substituting the model the author did not pin."""
    req = _buck_request().model_copy(update={"model_pin": "not_registered_anywhere"})
    reg = default_registry()
    # Sanity: the un-pinned request WOULD match (the cheap default).
    assert reg.select(_buck_request()).is_ok
    selected = reg.select(req)
    assert selected.is_err
    assert selected.danger_err.pinned == "not_registered_anywhere"
