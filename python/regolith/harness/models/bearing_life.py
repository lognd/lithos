"""Closed-form rolling-bearing basic L10 rating-life model (ISO 281:2007).

Discharges the corpus's bearing-life claim -- ``mech.bearing.l10_hours``
(``examples/systems/reaction_wheel/shaft_bearings.hema``'s ``b10``,
``examples/systems/dune_buggy/upright_hub_front.hema``'s ``life``): a
rolling bearing under a known equivalent dynamic load and rotational
speed must clear a minimum service life in hours, or the bearing wears
out before the design life.

Model (ISO 281:2007 sec. 6.2, basic -- unmodified, 90%-reliability --
rating life):

    L10  = (C / P)**p               (millions of revolutions, eq. 4)
    L10h = L10 * 1e6 / (60 * n)     (hours at constant speed n rpm, eq. 5)

``C`` is the bearing's basic dynamic load rating, ``P`` the equivalent
dynamic bearing load, ``p`` the load-life exponent (3 for ball bearings,
10/3 for roller bearings per the standard's own fixed values -- an
engineering constant, not a measured quantity). This lithos model does
NOT bake ``p`` per bearing kind (unlike feldspar's
``library/bearing_life.py`` reference, which registers one solver route
per kind): the caller supplies ``p_exponent`` directly, so one model
serves both kinds without an ambiguous same-claim-kind registration
(D94 keying warns against that when nothing in the request payload
disambiguates the kind).

Feldspar route (checked, not taken): feldspar's ``pack.register()``
(``feldspar/pack/models.py``) exposes exactly six ``regolith.harness``
models through the plugin seam (WO-44/AD-26) --
``FeaStaticStressModel``/``FeaStaticDeflectionModel``/
``FeaStaticDeflectionFromGeometryModel``/``MechStiffnessModel``/two
``ElecRailModel`` instances. ``feldspar.library.bearing_life`` DOES
exist (ISO 281 L10/L10h, cited to the same standard) but is registered
only into feldspar's own internal ``feldspar.solve.SolverRegistry``
(consumed by the generic FEA/stress/deflection models' TARGET-kind
dispatch), never surfaced as a ``mech.bearing.l10_hours``-claim-kind
``regolith.harness.Model``. So today there is no live route through the
plugin seam for this claim kind -- landing a thin in-tree model (this
file) is the honest choice; re-exposing feldspar's own bearing_life
route through the plugin seam is a feldspar-side follow-up (own repo,
own WO), not a lithos-side fix.

NAMED CUT (mirrors feldspar's own bearing_life scope note, docs/
benchmarks-memo.md sec. 11): no ISO 281:2007 sec. 6.3 modified-life
``a_iso`` factor (reliability/contamination/lubrication) is applied --
this is the BASIC (unmodified) L10/L10h only. Static load safety
(``C0/P0``, ISO 76) is a separate standard and is not evaluated here.
Corner conservatism (INV-9, regolith/07 sec. 3-5, the D158 precedent):
the model evaluates ALL 2**k interval corners and takes the WORST
(min) hours, and additionally charges a conservative 50% haircut into
``eps`` as a stand-in for the omitted ``a_iso`` factor -- a1/aISO can
run well under 1.0 under ordinary contamination/lubrication, and
without a contamination-factor record to consume this model would
otherwise silently overstate life. The 50% figure is a documented,
deliberately blunt placeholder (not a derived bound); tightening it
needs its own citation trail (ISO 281:2007 annex) -- named cut, same
shape as feldspar's own.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "mech.bearing.l10_hours"

# Required inputs (SI-ish: N, N, rev/min, dimensionless load-life
# exponent). Public so the orchestrator's translate routing can build a
# matching `inputs` dict without duplicating the field-name list.
INPUTS = ("c_rating", "p_load", "speed_rpm", "p_exponent")
_INPUTS = INPUTS

# Conservative haircut standing in for the un-applied ISO 281:2007 sec.
# 6.3 a_iso modification factor (see module doc's NAMED CUT).
_EPS_REL = 0.50


class BearingL10HoursModel(Model):
    """Closed-form basic L10 rating life of a rolling bearing (ISO 281:2007)."""

    @property
    def signature(self) -> ModelSignature:
        """Lower-bound rating-life claim over the four ISO 281 inputs."""
        return ModelSignature(
            name="bearing_basic_rating_life_l10h",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=_INPUTS,
            domain=("rolling_bearing", "iso281", "basic_l10_no_aiso"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Evaluate worst-corner L10h over the interval-boxed inputs."""
        c_rating = request.inputs["c_rating"]
        p_load = request.inputs["p_load"]
        speed_rpm = request.inputs["speed_rpm"]
        p_exponent = request.inputs["p_exponent"]

        # Domain: a real bearing has positive load rating, positive
        # equivalent load, positive speed, and a positive load-life
        # exponent (ISO 281 bakes 3 or 10/3, but this model accepts
        # any positive value -- see module doc on why p is caller-set).
        if c_rating.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"C must be strictly positive: c_rating.lo={c_rating.lo}",
                )
            )
        if p_load.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"P must be strictly positive: p_load.lo={p_load.lo}",
                )
            )
        if speed_rpm.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"speed must be strictly positive: speed_rpm.lo={speed_rpm.lo}"
                    ),
                )
            )
        if p_exponent.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "load-life exponent must be strictly positive: "
                        f"p_exponent.lo={p_exponent.lo}"
                    ),
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9). L10h
        # shrinks with lower C, higher P, higher speed, or a lower
        # exponent, but rather than hand-prove the monotonicity every
        # corner is evaluated and the worst (min) taken.
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (c_rating, p_load, speed_rpm, p_exponent)
        ]
        worst = np.inf
        for c, p, n, p_exp in itertools.product(*axes):
            l10_million_revs = (c / p) ** p_exp
            l10h = l10_million_revs * 1.0e6 / (60.0 * n)
            worst = min(worst, float(l10h))

        # The a_iso stand-in haircut (module doc NAMED CUT): charged
        # against the worst-corner value itself so it scales with the
        # prediction, same shape as bolted_joint's preload-relative eps.
        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
