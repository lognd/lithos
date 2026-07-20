"""Stress-life fatigue damage model: Marin-corrected Goodman + Basquin.

Discharges the mech corpus's `mech.fatigue.damage` claim -- dune_buggy's
`upright_hub_front.hema` `spindle_life` (rotating-bending spindle,
Marin-corrected endurance + Peterson Kt at the flange fillet, Miner
over the duty spectrum -- module doc's own words) and `halfshaft.hema`
`spline_fatigue` (torsion fatigue on the splines): both currently
`waive`d as `"no registered harness model for label kind ...
(F126.1 model gap)"`, a real harness gap (not the D103 entity-derived-
bound residual `weldment_frame.hema`'s `weld_static` waiver names --
that family is blocked at lowering, not at the harness, so it is
NOT landed by this model; see the WO-111 close-out survey).

Model (Shigley's Mechanical Engineering Design, 10th ed.):

    Se = ka*kb*kc*kd*ke*kf_marin * Se'          (sec. 6-9, Marin equation)
    sigma_ar = (Kf * sigma_a) / (1 - sigma_m/Sut)   (sec. 6-12, Goodman)
    a = (f*Sut)**2 / Se, b = -log10(f*Sut/Se) / 3   (sec. 6-14, Basquin fit
        through the two S-N anchor points: f*Sut at 10**3 cycles, Se at
        10**6 cycles)
    N = (sigma_ar / a) ** (1/b)                 (Basquin, cycles to failure)
    damage = n_applied / N                      (Miner's rule, ONE block)

Feldspar route (checked, not taken): as of this WO's survey, feldspar's
`crates/feldspar-library/src/mech/` carries `frame.rs`, `sections.rs`,
`statics.rs`, `vibration.rs` -- no fatigue/Marin/Goodman/Basquin module
exists there today, and no `regolith.harness`-surfaced fatigue model is
registered in feldspar's pack (`feldspar.pack:register` exposes six
FEA/stiffness/rail models only, `bearing_life.py`'s module doc's own
census). The physics-in-feldspar half of WO-111 (its own repo, own WO)
has not landed; this thin in-tree model is the same honest choice
`bearing_life.py`/`fluid_pressure_drop.py` already made for their
claim kinds -- land a citable closed-form here now, re-home it behind
the pack seam later if/when feldspar exposes the same physics (own
follow-up, not this file's job).

NAMED CUT (D250.3, no fabricated default): this is a SINGLE-BLOCK
(constant-amplitude) Miner calculation -- `n_applied` cycles at ONE
stress level. The corpus's `over=boundary.spectrum` duty-spectrum
payload (multi-block Miner summation over a hash-pinned load
spectrum, D96 payload channel) is NOT consumed here; a caller with a
real duty spectrum must reduce it to an equivalent single block (or
call this model once per block and sum damage upstream) until a
spectrum-consuming follow-up lands -- same shape as `bearing_life.py`'s
un-applied ISO 281 `a_iso` factor: a documented, deliberately scoped
gap, not silent wrongness. `Kf_notch`/every Marin factor/`f` (the
Basquin strength fraction, Shigley Fig. 6-23) are declared inputs,
never derived defaults -- refusing by name (a `DomainError`) rather
than guessing is the D250.3 discipline the whole corpus follows.

Corner conservatism (INV-9): damage is an UPPER-bound claim (`< 1.0`);
worst corner is found by exhaustive corner search (same technique
`bearing_life.py` uses) rather than a hand monotonicity proof, since
the Goodman/Basquin composition is not obviously monotonic in every
input over its whole domain.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges.
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "mech.fatigue.damage"

# Required inputs (SI: Pa, Pa, --, Pa, Pa, six Marin factors --, --, --).
# frob:doc docs/modules/py-harness.md#models
INPUTS = (
    "sigma_a_pa",
    "sigma_m_pa",
    "kf_notch",
    "sut_pa",
    "se_prime_pa",
    "marin_ka",
    "marin_kb",
    "marin_kc",
    "marin_kd",
    "marin_ke",
    "marin_kf",
    "basquin_f",
    "cycles_applied",
)
_INPUTS = INPUTS


# frob:doc docs/modules/py-harness.md#models
class FatigueDamageModel(Model):
    """Single-block Miner damage from a Marin-corrected Goodman/Basquin
    stress-life estimate."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound damage-fraction claim over the thirteen fatigue inputs."""
        return ModelSignature(
            name="fatigue_goodman_marin_basquin_damage",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("steel_shaft_or_member", "stress_life", "single_block_miner"),
        )

    @property
    # frob:doc docs/modules/py-harness.md#models
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    # frob:doc docs/modules/py-harness.md#models
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    @property
    # frob:doc docs/modules/py-harness.md#models
    def citation(self) -> str | None:
        """The module doc's Marin/Goodman/Basquin source."""
        return (
            "Shigley's Mechanical Engineering Design, 10th ed., "
            "sec. 6-9 (Marin), 6-12 (Goodman), 6-14 (Basquin)"
        )

    # frob:doc docs/modules/py-harness.md#models
    # frob:waive PERF004 reason="one-shot corner-axis sorts during request assembly (one sorted() per <=4-corner interval in a comprehension); nothing re-sorts the same collection per iteration"
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Evaluate worst-corner Miner damage over the interval-boxed inputs."""
        keys = _INPUTS
        vals = {k: request.inputs[k] for k in keys}

        if vals["sut_pa"].lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"Sut must be strictly positive: lo={vals['sut_pa'].lo}",
                )
            )
        if vals["se_prime_pa"].lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"Se' must be strictly positive: lo={vals['se_prime_pa'].lo}"
                    ),
                )
            )
        for marin_key in (
            "marin_ka",
            "marin_kb",
            "marin_kc",
            "marin_kd",
            "marin_ke",
            "marin_kf",
        ):
            if vals[marin_key].lo <= 0.0 or vals[marin_key].hi > 1.0:
                return Err(
                    DomainError(
                        model_id=self.model_id,
                        message=(
                            f"{marin_key} must lie in (0, 1]: "
                            f"lo={vals[marin_key].lo}, hi={vals[marin_key].hi}"
                        ),
                    )
                )
        if vals["basquin_f"].lo <= 0.0 or vals["basquin_f"].hi >= 1.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "basquin_f (fatigue strength fraction at 10**3 cycles) "
                        f"must lie in (0, 1): lo={vals['basquin_f'].lo}, "
                        f"hi={vals['basquin_f'].hi}"
                    ),
                )
            )
        if vals["kf_notch"].lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"kf_notch must be strictly positive: lo={vals['kf_notch'].lo}"
                    ),
                )
            )
        if vals["sigma_a_pa"].lo < 0.0 or vals["cycles_applied"].lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "sigma_a_pa must be non-negative and "
                        "cycles_applied strictly positive"
                    ),
                )
            )
        if vals["sigma_m_pa"].hi >= vals["sut_pa"].lo:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "sigma_m_pa reaches or exceeds Sut: the Goodman line is "
                        f"invalid (sigma_m.hi={vals['sigma_m_pa'].hi}, "
                        f"sut.lo={vals['sut_pa'].lo})"
                    ),
                )
            )

        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in vals.values()
        ]
        worst = -math.inf
        for corner in itertools.product(*axes):
            point = dict(zip(keys, corner, strict=True))
            se = (
                point["marin_ka"]
                * point["marin_kb"]
                * point["marin_kc"]
                * point["marin_kd"]
                * point["marin_ke"]
                * point["marin_kf"]
                * point["se_prime_pa"]
            )
            sut = point["sut_pa"]
            sigma_m = point["sigma_m_pa"]
            if sigma_m >= sut:
                continue
            sigma_ar = (point["kf_notch"] * point["sigma_a_pa"]) / (1.0 - sigma_m / sut)
            f_frac = point["basquin_f"]
            a_coef = (f_frac * sut) ** 2 / se
            b_coef = -math.log10(f_frac * sut / se) / 3.0
            if sigma_ar <= 0.0 or a_coef <= 0.0:
                n_cycles = math.inf
            else:
                n_cycles = (sigma_ar / a_coef) ** (1.0 / b_coef)
            damage = point["cycles_applied"] / n_cycles if n_cycles > 0.0 else math.inf
            worst = max(worst, damage)

        return Ok(Prediction(value=worst, eps=0.0, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "INPUTS", "FatigueDamageModel"]
