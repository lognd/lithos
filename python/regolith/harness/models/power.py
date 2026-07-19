"""Closed-form facility power-distribution models (WO-135/D248.3/AD-42).

The lithos half of the shared boundary rule (AD-37, charter 43 sec. 3):
pad-check closed forms live here as harness built-ins; numerics/
certified solving (load flow, IEC 60909/ANSI short circuit with motor
contribution, IEEE 1584 arc flash, coordination, IEEE 519 harmonics)
is feldspar's, in its own repo -- ONE home per physics, no double-homes.
This module never claims ``elec.power.arc_flash``, ``coordination``,
or ``harmonics`` (a test in ``tests/harness/test_power_models.py``
proves the default registry has no model for those kinds, so a claim
of that kind cannot reach release trust through a built-in -- D250.4).

D250.3 (safety honesty, the rule that outranks convenience): AN
UNVERIFIABLE INPUT IS A NAMED ABSENCE, NEVER A DEFAULT. Every model
below declares its safety-critical fields (available %Z, locked-rotor
kVA, ...) as REQUIRED ``ModelSignature.inputs`` ports with no fallback
value anywhere in this file -- the shared ``Model.discharge`` (see
``regolith.harness.model``) already refuses a request missing a
required port with an honest ``InputError`` naming exactly which
input is absent, before this module's ``estimate`` ever runs. A
declared-record author who has no real utility letter, nameplate, or
datasheet value for a field simply does not populate that port; there
is no "typical value" anywhere in this module (charter 43 sec. 5.3).

Every model cites its governing standard and edition (D250.1) and every
model's ``estimate`` docstring/citation notes carries the "not a
stamped study" posture (charter 43 sec. 5.2) implicitly by NEVER
producing an arc-flash, coordination, or harmonics verdict -- those
claims simply have no matching lithos model (``harness.no_model``).
"""

from __future__ import annotations

import math

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# ---------------------------------------------------------------------------
# 1. NEC Art. 220 demand load (connected -> demand, by load class).
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
DEMAND_LOAD_KIND = "elec.power.demand_load"
# frob:doc docs/modules/py-harness.md#models
DEMAND_LOAD_INPUTS = ("connected_kva", "demand_factor")


# frob:doc docs/modules/py-harness.md#models
class DemandLoadModel(Model):
    """NEC Art. 220 connected-to-demand load conversion.

    ``demand_kva = connected_kva * demand_factor`` (NFPA 70 (NEC), 2023
    ed., Art. 220 -- the demand-factor tables themselves are the
    withdrawn std.power record set, D266; this model consumes an
    AUTHOR-DECLARED ``demand_factor`` rather than transcribing any
    table, exactly the "declared, not derived" posture
    ``civil.bearing_pressure``'s reaction/area inputs already take).
    Upper bound (``<= panel/service rating``): both inputs grow the
    demand, so the worst corner is ``connected_kva.hi * demand_factor.
    hi`` (INV-9).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound demand-load claim over connected kVA + factor."""
        return ModelSignature(
            name="elec_power_demand_load",
            claim_kind=DEMAND_LOAD_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=DEMAND_LOAD_INPUTS,
            domain=("power", "nec_220"),
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
        """The NEC demand-load article and edition (D250.1)."""
        return "NFPA 70 (NEC), 2023 ed., Art. 220 -- demand load"

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner demand kVA."""
        connected = request.inputs["connected_kva"]
        factor = request.inputs["demand_factor"]

        if connected.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"connected_kva must be non-negative: lo={connected.lo}",
                )
            )
        if factor.lo < 0.0 or factor.hi > 1.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"demand_factor must lie in [0, 1]: got [{factor.lo}, "
                    f"{factor.hi}]",
                )
            )

        demand = connected.hi * factor.hi
        return Ok(Prediction(value=demand, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# 2. Conductor voltage drop (single/three phase, PF, run length).
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
VOLTAGE_DROP_KIND = "elec.power.voltage_drop"
# frob:doc docs/modules/py-harness.md#models
VOLTAGE_DROP_INPUTS = (
    "current_a",
    "length_m",
    "resistance_ohm_per_m",
    "reactance_ohm_per_m",
    "power_factor",
    "phase_multiplier",
)


# frob:doc docs/modules/py-harness.md#models
class VoltageDropModel(Model):
    """Conductor voltage drop over a declared run (IEEE 141 sec. 3).

    ``vd = phase_multiplier * I * L * (R * pf + X * sqrt(1 - pf**2))``
    -- the standard line-to-neutral drop times the author-declared
    phase multiplier (``2.0`` single-phase round-trip, ``sqrt(3)``
    three-phase; IEEE Std 141-1993 (IEEE Red Book), ch. 3). ``R``/``X``
    are the conductor's declared per-length resistance/reactance (a
    real conductor record's ohms/length, never a table transcription
    here). Upper bound: I/L/R/X/multiplier all push the drop up (HI);
    ``power_factor`` is not monotone over its declared interval, so
    the conservative corner takes the MAX of the two endpoint
    evaluations (a documented 2-point search, not a full interval
    optimization -- the same reduced-tier posture the numeric base
    uses elsewhere in this pack).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound voltage-drop claim over the six run inputs."""
        return ModelSignature(
            name="elec_power_voltage_drop",
            claim_kind=VOLTAGE_DROP_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=VOLTAGE_DROP_INPUTS,
            domain=("power", "conductor_run"),
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
        """The IEEE Red Book voltage-drop formula (D250.1)."""
        return "IEEE Std 141-1993 (IEEE Red Book), ch. 3 -- conductor voltage drop"

    @staticmethod
    def _drop_at(
        current: float,
        length: float,
        resistance: float,
        reactance: float,
        pf: float,
        multiplier: float,
    ) -> float:
        """The line-to-neutral drop formula at one pinned power factor."""
        sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
        return multiplier * current * length * (resistance * pf + reactance * sin_phi)

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner voltage drop."""
        current = request.inputs["current_a"]
        length = request.inputs["length_m"]
        resistance = request.inputs["resistance_ohm_per_m"]
        reactance = request.inputs["reactance_ohm_per_m"]
        pf = request.inputs["power_factor"]
        multiplier = request.inputs["phase_multiplier"]

        if current.lo < 0.0 or length.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="current_a/length_m must be non-negative",
                )
            )
        if resistance.lo < 0.0 or reactance.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="resistance_ohm_per_m/reactance_ohm_per_m must be "
                    "non-negative",
                )
            )
        if pf.lo <= 0.0 or pf.hi > 1.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"power_factor must lie in (0, 1]: got [{pf.lo}, {pf.hi}]",
                )
            )
        if multiplier.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="phase_multiplier must be strictly positive",
                )
            )

        candidates = [
            self._drop_at(
                current.hi, length.hi, resistance.hi, reactance.hi, pf_corner,
                multiplier.hi,
            )
            for pf_corner in (pf.lo, pf.hi)
        ]
        drop = max(candidates)
        return Ok(Prediction(value=drop, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# 3. Ampacity with derating (NEC 310.15: temperature + conduit fill).
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
AMPACITY_KIND = "elec.power.ampacity"
# frob:doc docs/modules/py-harness.md#models
AMPACITY_INPUTS = (
    "base_ampacity_a",
    "temperature_correction_factor",
    "fill_adjustment_factor",
)


# frob:doc docs/modules/py-harness.md#models
class AmpacityModel(Model):
    """Ampacity with NEC 310.15 temperature/fill derating.

    ``derated = base_ampacity_a * temperature_correction_factor *
    fill_adjustment_factor`` (NFPA 70 (NEC), 2023 ed., sec. 310.15(B)
    temperature correction / (C) adjustment for more than three
    current-carrying conductors). ``base_ampacity_a`` is the
    conductor record's declared table row (the WO-134 std.power
    record itself, not transcribed here -- see this pack's module doc
    for the withdrawn-table posture); the two factors are the run's
    own declared derating multipliers. Lower bound (the claim compares
    this AVAILABLE ampacity against a required load current, ``value
    >= limit``): derating only ever reduces capacity, so the
    conservative corner takes the MIN of all three factors (INV-9).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Lower-bound derated-ampacity claim over the three inputs."""
        return ModelSignature(
            name="elec_power_ampacity",
            claim_kind=AMPACITY_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=AMPACITY_INPUTS,
            domain=("power", "nec_310_15"),
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
        """The NEC 310.15 derating provisions and edition (D250.1)."""
        return "NFPA 70 (NEC), 2023 ed., sec. 310.15(B)/(C) -- ampacity derating"

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner (minimum) derated ampacity."""
        base = request.inputs["base_ampacity_a"]
        temp_factor = request.inputs["temperature_correction_factor"]
        fill_factor = request.inputs["fill_adjustment_factor"]

        if base.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"base_ampacity_a must be non-negative: lo={base.lo}",
                )
            )
        if temp_factor.lo < 0.0 or fill_factor.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="temperature_correction_factor/fill_adjustment_factor "
                    "must be non-negative",
                )
            )

        derated = base.lo * temp_factor.lo * fill_factor.lo
        return Ok(Prediction(value=derated, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# 4. Transformer %Z single-source bus fault (the screening estimate).
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
FAULT_CURRENT_KIND = "elec.power.fault_current"
# frob:doc docs/modules/py-harness.md#models
FAULT_CURRENT_INPUTS = ("transformer_kva", "pct_z", "secondary_voltage_v")


# frob:doc docs/modules/py-harness.md#models
class TransformerFaultCurrentScreeningModel(Model):
    """Transformer %Z single-source three-phase bus fault SCREENING estimate.

    ``I_fault = (kva * 1000) / (sqrt(3) * v_secondary) / (pct_z / 100)``
    (IEEE Std 242-2001 (IEEE Buff Book), sec. 4 -- the single-source,
    infinite-primary-bus screening formula every protection textbook
    opens with). THIS IS A SCREENING ESTIMATE, NOT A CERTIFIED SHORT-
    CIRCUIT STUDY: it ignores motor contribution, network topology
    beyond the one transformer, and utility source impedance -- exactly
    what feldspar's IEC 60909/ANSI short-circuit model adds (AD-42,
    charter 43 sec. 3). It NEVER discharges ``elec.power.arc_flash``
    (a distinct claim kind this pack does not register a model for,
    D250.4). ``pct_z`` is REQUIRED with no default (D250.3): a
    transformer with no declared nameplate %Z has no port to supply,
    so the shared discharge path refuses with a named ``InputError``
    rather than assuming a "typical" nameplate %Z. Upper bound (the
    claim compares fault current against equipment withstand/
    interrupting rating): the worst corner is max kVA, MIN %Z (a
    stiffer transformer trips higher fault current), MIN secondary
    voltage (INV-9).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound screening fault-current claim over the three inputs."""
        return ModelSignature(
            name="elec_power_fault_current_screening",
            claim_kind=FAULT_CURRENT_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=FAULT_CURRENT_INPUTS,
            domain=("power", "single_source", "screening_estimate"),
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
        """The Buff Book screening formula, edition, and its scope limit."""
        return (
            "IEEE Std 242-2001 (IEEE Buff Book), sec. 4 -- single-source "
            "transformer %Z fault-current SCREENING ESTIMATE, not a "
            "certified short-circuit study (AD-42/D250.4; certified "
            "short-circuit/arc-flash routes to feldspar)"
        )

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner single-source fault current."""
        kva = request.inputs["transformer_kva"]
        pct_z = request.inputs["pct_z"]
        voltage = request.inputs["secondary_voltage_v"]

        if kva.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"transformer_kva must be non-negative: lo={kva.lo}",
                )
            )
        if pct_z.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"pct_z must be strictly positive: lo={pct_z.lo}",
                )
            )
        if voltage.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"secondary_voltage_v must be strictly positive: "
                    f"lo={voltage.lo}",
                )
            )

        full_load_current = (kva.hi * 1000.0) / (math.sqrt(3.0) * voltage.lo)
        fault_current = full_load_current / (pct_z.lo / 100.0)
        return Ok(
            Prediction(value=fault_current, eps=0.0, coverage=1.0, in_domain=True)
        )


# ---------------------------------------------------------------------------
# 5. Motor starting voltage dip.
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
MOTOR_START_DIP_KIND = "elec.power.motor_start_dip"
# frob:doc docs/modules/py-harness.md#models
MOTOR_START_DIP_INPUTS = ("motor_locked_rotor_kva", "source_available_kva")


# frob:doc docs/modules/py-harness.md#models
class MotorStartDipModel(Model):
    """Motor-starting voltage-dip screening estimate (IEEE 141 ch. 5).

    ``dip_pct = 100 * lra_kva / (lra_kva + source_available_kva)`` (IEEE
    Std 141-1993 (IEEE Red Book), ch. 5's source-impedance-divider
    approximation for the instantaneous voltage sag at motor start).
    ``motor_locked_rotor_kva`` is the declared locked-rotor kVA (from a
    nameplate/datasheet's code letter -- a motor with no declared code
    letter has no port to supply this input, D250.3: the shared
    discharge path refuses by name rather than assuming a "typical"
    code letter). Upper bound: dip grows with the motor's LRA (HI) and
    shrinks with more available source capacity, so the conservative
    corner takes MIN source_available_kva (INV-9).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound voltage-dip claim over the two kVA inputs."""
        return ModelSignature(
            name="elec_power_motor_start_dip",
            claim_kind=MOTOR_START_DIP_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=MOTOR_START_DIP_INPUTS,
            domain=("power", "motor_starting", "screening_estimate"),
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
        """The Red Book motor-starting voltage-dip approximation."""
        return (
            "IEEE Std 141-1993 (IEEE Red Book), ch. 5 -- motor starting "
            "voltage-dip screening estimate"
        )

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner percent voltage dip."""
        lra = request.inputs["motor_locked_rotor_kva"]
        source = request.inputs["source_available_kva"]

        if lra.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"motor_locked_rotor_kva must be non-negative: "
                    f"lo={lra.lo}",
                )
            )
        if source.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"source_available_kva must be strictly positive: "
                    f"lo={source.lo}",
                )
            )

        dip = 100.0 * lra.hi / (lra.hi + source.lo)
        return Ok(Prediction(value=dip, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# 6a. Transformer loading.
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
TRANSFORMER_LOADING_KIND = "elec.power.transformer_loading"
# frob:doc docs/modules/py-harness.md#models
TRANSFORMER_LOADING_INPUTS = ("actual_kva", "rated_kva")


# frob:doc docs/modules/py-harness.md#models
class TransformerLoadingModel(Model):
    """Transformer percent-of-nameplate loading (IEEE C57.91 sec. 1).

    ``loading_pct = 100 * actual_kva / rated_kva`` (IEEE Std
    C57.91-2011, sec. 1 -- the nameplate loading-guide's basic percent-
    of-rating definition). Upper bound: loading grows with the actual
    demand (HI) and shrinks with a larger nameplate rating, so the
    worst corner takes MIN rated_kva (INV-9).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound transformer-loading claim over the two kVA inputs."""
        return ModelSignature(
            name="elec_power_transformer_loading",
            claim_kind=TRANSFORMER_LOADING_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=TRANSFORMER_LOADING_INPUTS,
            domain=("power", "transformer"),
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
        """The IEEE loading-guide percent-of-rating definition (D250.1)."""
        return "IEEE Std C57.91-2011, sec. 1 -- transformer percent-of-rating loading"

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner percent loading."""
        actual = request.inputs["actual_kva"]
        rated = request.inputs["rated_kva"]

        if actual.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"actual_kva must be non-negative: lo={actual.lo}",
                )
            )
        if rated.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"rated_kva must be strictly positive: lo={rated.lo}",
                )
            )

        loading = 100.0 * actual.hi / rated.lo
        return Ok(Prediction(value=loading, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# 6b. Power factor.
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
POWER_FACTOR_KIND = "elec.power.power_factor"
# frob:doc docs/modules/py-harness.md#models
POWER_FACTOR_INPUTS = ("real_power_kw", "apparent_power_kva")


# frob:doc docs/modules/py-harness.md#models
class PowerFactorModel(Model):
    """Displacement power factor from real and apparent power.

    ``pf = real_power_kw / apparent_power_kva`` (IEEE Std 141-1993
    (IEEE Red Book), ch. 2 -- the basic real/apparent power-factor
    definition). Lower bound (the claim compares pf against a minimum,
    e.g. a utility tariff threshold, ``value >= limit``): pf shrinks
    with less real power and more apparent power, so the worst corner
    takes MIN real_power_kw / MAX apparent_power_kva (INV-9).
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Lower-bound power-factor claim over the two power inputs."""
        return ModelSignature(
            name="elec_power_power_factor",
            claim_kind=POWER_FACTOR_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=POWER_FACTOR_INPUTS,
            domain=("power",),
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
        """The Red Book power-factor definition and edition (D250.1)."""
        return "IEEE Std 141-1993 (IEEE Red Book), ch. 2 -- power factor"

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner (minimum) power factor."""
        real = request.inputs["real_power_kw"]
        apparent = request.inputs["apparent_power_kva"]

        if real.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"real_power_kw must be non-negative: lo={real.lo}",
                )
            )
        if apparent.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"apparent_power_kva must be strictly positive: "
                    f"lo={apparent.lo}",
                )
            )

        pf = real.lo / apparent.hi
        return Ok(Prediction(value=pf, eps=0.0, coverage=1.0, in_domain=True))


# ---------------------------------------------------------------------------
# 7. Working clearance (WO-136/D249/AD-42): the calcite tandem.
# ---------------------------------------------------------------------------

# frob:doc docs/modules/py-harness.md#models
WORKING_CLEARANCE_KIND = "elec.power.working_clearance"
# frob:doc docs/modules/py-harness.md#models
# ``room_dim_m``: the calcite space's real declared linear dimension on
# the checked face (depth/width/headroom -- whichever the claim names);
# ``footprint_dim_m``: the apparatus's own declared footprint on that
# same face. Both are DECLARED quantities the orchestrator resolves
# through the entity DB across the elec/calcite file boundary (D103's
# general-comparison reference machinery, `_translate_working_clearance`
# in `regolith.orchestrator.translate` -- the exact "reuse, do not
# reinvent" instruction of D102), never re-declared/copied by hand.
WORKING_CLEARANCE_INPUTS = ("room_dim_m", "footprint_dim_m")


# frob:doc docs/modules/py-harness.md#models
class WorkingClearanceModel(Model):
    """NEC 110.26 working-space depth/width/headroom check (D249/D250.3).

    ``available_m = room_dim_m - footprint_dim_m`` (the real clear
    dimension left in front of/beside/above the apparatus once its own
    footprint is subtracted from the room's real declared extent on
    that face) compared against the claim's own bound: the REQUIRED
    clearance for the apparatus's voltage class/condition, an
    AUTHOR-DECLARED literal cited to its exact NEC 110.26 table row
    (e.g. ``>= 1.0m # NFPA 70 (NEC), 2023 ed., Table 110.26(A)(1),
    Condition 2, 0-150V``) -- never transcribed as a lithos table
    (D250.3/D266 posture: the dimensional CLASS is declared by the
    author who reads the real table for their real voltage/condition,
    exactly the ``demand_factor``/``site.soil.bearing`` "declared, not
    derived" precedent this charter already set).

    Lower bound (``available_m >= required_m``): the available
    clearance shrinks with a SMALLER room dimension and a LARGER
    footprint, so the worst corner is ``room_dim.lo - footprint_dim.hi``
    (INV-9); ``eps`` is zero -- both inputs are exact declared reads,
    no model-side approximation.
    """

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Lower-bound available-clearance claim over the two linear inputs."""
        return ModelSignature(
            name="elec_power_working_clearance",
            claim_kind=WORKING_CLEARANCE_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=WORKING_CLEARANCE_INPUTS,
            domain=("power", "working_clearance", "calcite_tandem"),
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
        """NEC 110.26's working-space depth/width/headroom rule (D250.1).

        The specific table row (voltage class, condition 1/2/3) is the
        author's own citation on the claim's declared bound, not this
        model's job to name -- see the class docstring's D250.3 note.
        """
        return (
            "NFPA 70 (NEC), 2023 ed., Art. 110.26 -- working space "
            "about electrical equipment"
        )

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner (minimum) available clearance."""
        room = request.inputs["room_dim_m"]
        footprint = request.inputs["footprint_dim_m"]

        if room.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"room_dim_m must be strictly positive: lo={room.lo}",
                )
            )
        if footprint.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"footprint_dim_m must be non-negative: lo={footprint.lo}",
                )
            )

        available = room.lo - footprint.hi
        return Ok(Prediction(value=available, eps=0.0, coverage=1.0, in_domain=True))


__all__ = [
    "AMPACITY_INPUTS",
    "AMPACITY_KIND",
    "DEMAND_LOAD_INPUTS",
    "DEMAND_LOAD_KIND",
    "FAULT_CURRENT_INPUTS",
    "FAULT_CURRENT_KIND",
    "MOTOR_START_DIP_INPUTS",
    "MOTOR_START_DIP_KIND",
    "POWER_FACTOR_INPUTS",
    "POWER_FACTOR_KIND",
    "TRANSFORMER_LOADING_INPUTS",
    "TRANSFORMER_LOADING_KIND",
    "VOLTAGE_DROP_INPUTS",
    "VOLTAGE_DROP_KIND",
    "WORKING_CLEARANCE_INPUTS",
    "WORKING_CLEARANCE_KIND",
    "AmpacityModel",
    "DemandLoadModel",
    "MotorStartDipModel",
    "PowerFactorModel",
    "TransformerFaultCurrentScreeningModel",
    "TransformerLoadingModel",
    "VoltageDropModel",
    "WorkingClearanceModel",
]
