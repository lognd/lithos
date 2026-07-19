"""Closed-form worst-case tolerance-allocation stack-up model.

Discharges the local tolerance-allocation default (hematite/03 sec. 5):
tolerances are allocated *locally* by default -- the loosest process-
capable band that closes each contributor, per connection, with no
cross-part flow -- and the standard allocation policy is ``worst_case``
(hematite/04, D63). This model checks whether that local default
allocation actually closes a linear tolerance chain: it sums the
locally-allocated contributor tolerances at their worst corner and
charges the total against the assembly's demanded window.

Model (worst_case linear stack, the default allocation policy):

    stack = sum_i t_i                              (worst-case chain total)

where each ``t_i`` is a contributor's locally-allocated (loosest process-
capable) tolerance magnitude. The claim is an UPPER bound: the assembly
demands ``stack <= limit``. When the loosest local allocation already
sums past the limit, the local default CANNOT close the chain -- the
E0432 condition of hematite/03 sec. 5 -- and this surfaces as a loud
``violated`` verdict, never a silent pass (the default allocation was
wrong and the release gate refuses it).

Corner conservatism (INV-9): the stack total is maximized at each
contributor's largest magnitude, so the model evaluates every input at
its upper (``hi``) corner and sums -- sound worst-case over the box.
The ``rss`` policy would allocate less, so ``worst_case`` is the
conservative default; the neglected statistical slack is not credited
here (``eps`` stays 0), keeping the default strictly conservative.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "mech.tolerance.worst_case_stack"

# The contributors of the (three-link) tolerance chain. Each is a
# locally-allocated tolerance magnitude in SI metres.
_INPUTS = ("contrib_a", "contrib_b", "contrib_c")


# frob:doc docs/modules/py-harness.md#models
class ToleranceStackModel(Model):
    """Worst-case linear stack-up of a local tolerance allocation."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound stack-up claim over the chain's contributor bands."""
        return ModelSignature(
            name="tolerance_worst_case_stack",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("tolerance", "stackup", "worst_case", "local_allocation"),
        )

    @property
    # frob:doc docs/modules/py-harness.md#models
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    # frob:doc docs/modules/py-harness.md#models
    def cost(self) -> int:
        """Closed-form sum: the cheapest tier."""
        return 1

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Sum each contributor's worst-corner tolerance magnitude."""
        total = 0.0
        for name in _INPUTS:
            band = request.inputs[name]
            # Domain: a real allocated tolerance is a strictly positive
            # band; a non-positive contributor is a malformed chain.
            if band.lo <= 0.0:
                return Err(
                    DomainError(
                        model_id=self.model_id,
                        message=(
                            f"contributor {name} tolerance must be strictly "
                            f"positive: {name}.lo={band.lo}"
                        ),
                    )
                )
            # Worst corner for the sum is each contributor's largest band.
            total += band.hi

        # worst_case is already the conservative allocation policy: no
        # statistical slack is credited, so no error term is charged.
        return Ok(Prediction(value=total, eps=0.0, coverage=1.0, in_domain=True))
