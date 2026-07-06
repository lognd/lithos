"""Conformance-refinement model (INV-13 discharge half).

Discharges the *conformance* obligation the compiler emits by
construction for every ``impl ... for``/extern/import binding (INV-13,
regolith/07 sec. 8): given an UPPER contract (the interface/spec
promise) and a LOWER realization (the hand-written impl's declared
promise), it checks the impl is a SOUND REFINEMENT of the spec -- the
impl promises a bound no *weaker* than the spec's. A spec contradicted by
its impl (the impl promising *less* -- a wider window than the spec) FAILS
equivalence: a ``violated`` evidence value, never a silent pass.

This is a PROMISE comparison, not a physics prediction (INV-19,
promises-not-actuals): the impl's declared bound IS the predicted
quantity, and the spec's demanded bound IS the limit, so the whole check
folds onto the harness's single margin rule (:mod:`regolith.harness.
evidence`) with ``eps = 0`` -- no model error to charge, the comparison
is exact. Refinement direction is the claim's sense:

- **upper** (``value < limit``, e.g. ripple, stress, mass): the impl
  refines iff its ceiling is no *higher* than the spec's
  (``impl_bound <= spec_bound``). Worst corner of the impl bound is its
  MAX.
- **lower** (``value > limit``, e.g. efficiency, clamp, margin): the impl
  refines iff its floor is no *lower* than the spec's
  (``impl_bound >= spec_bound``). Worst corner is its MIN.

Soundness (never a false pass): if either side is not a finite,
comparable magnitude the request is out of domain and the discharge is
``indeterminate`` (regolith/07 sec. 4), not ``discharged``. Extracting
the two bounds from a serialized conformance ``Obligation`` (whose claim
form carries the ``conforms`` structure, not the resolved numeric
windows) is orchestrator territory (AD-1); the harness consumes the
resolved :class:`DischargeRequest`.
"""

from __future__ import annotations

import math

from typani.result import Ok, Result

from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The two registry keys this pack discharges -- one per refinement
# direction. One home for each string (the sense is fixed per key so the
# shared discharge path stays a single margin rule).
CLAIM_KIND_UPPER = "harness.conformance.upper_bound"
CLAIM_KIND_LOWER = "harness.conformance.lower_bound"

# The single required input: the LOWER realization's declared bound (the
# impl's promise). The UPPER contract's demanded bound arrives as the
# request's ``limit``.
_IMPL_BOUND = "impl_bound"


class ConformanceRefinementModel(Model):
    """Refinement check of a lower impl promise against an upper spec promise."""

    def __init__(self, *, upper: bool) -> None:
        """Build the model for one refinement direction (``upper``/lower sense)."""
        self._upper = upper

    @property
    def signature(self) -> ModelSignature:
        """The conformance claim (per-sense key) over the single impl bound."""
        return ModelSignature(
            name=f"conformance_refinement_{'upper' if self._upper else 'lower'}",
            claim_kind=CLAIM_KIND_UPPER if self._upper else CLAIM_KIND_LOWER,
            sense=(
                ClaimSense.upper_bound() if self._upper else ClaimSense.lower_bound()
            ),
            inputs=(_IMPL_BOUND,),
            domain=("conformance", "refinement", "promise_comparison"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any refinement-rule change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """A bare magnitude comparison: the cheapest tier."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Take the impl bound's worst corner as the predicted quantity.

        The impl's declared promise is the prediction (INV-19); the shared
        discharge rule then charges it against the spec's ``limit`` with a
        zero ``eps`` -- an exact refinement comparison. A non-finite bound
        or limit is not comparable, so the request is out of domain and
        the discharge is ``indeterminate``, never a false pass.
        """
        impl_bound = request.inputs[_IMPL_BOUND]
        lo, hi = impl_bound.corners()

        comparable = all(math.isfinite(v) for v in (lo, hi, request.limit))
        if not comparable:
            return Ok(Prediction(value=0.0, eps=0.0, coverage=1.0, in_domain=False))

        # Worst corner of the impl's promised window: its highest point
        # for an upper-bound claim (weakest ceiling), its lowest for a
        # lower-bound claim (weakest floor). Sound for any interval box
        # (INV-9).
        worst = hi if self._upper else lo
        return Ok(Prediction(value=worst, eps=0.0, coverage=1.0, in_domain=True))
