"""Material-state representation (WO-166 slice a, D268 item 3, AD-47
sec. 5 charter 44).

The recon dossier's finding: hematite's material-reference grammar
(`crates/regolith-syntax`'s `Material` list-of-record-refs shape,
mirrored at `regolith._schema.models.Material`) names WHICH record a
part cites but has NO representation of a material's metallurgical
STATE (as-rolled vs. quenched-and-tempered vs. through-hardened) --
today `std.materials/records/metallurgy.toml` fakes this with
SEPARATE static records per condition (`AISI_D2_ANN` vs `AISI_D2_QT`),
which cannot express a parameterized variant (a caller-declared temper
temperature or target hardness) without minting a new record per value.

Per this WO's own escalation clause ("escalate to a design-log entry if
the existing hematite material-reference grammar cannot express a
parameterized state variant without a grammar change -- do not invent
grammar unilaterally") AND the dispatch's schema-frozen posture (D272
spent; realized kinds follow the T-0043 plain-pydantic posture,
promotable later): this module supplies the state representation as a
PLAIN pydantic type at the harness/realizer layer, NOT a hematite
grammar addition -- no `crates/regolith-syntax` change, no
`SCHEMA_VERSION` bump. This is the same posture
`RealizedBoardAssignment` (WO-163) and `PerfboardNetlist` (WO-165) took
for their own new surface: usable today, promotable into parsed
hematite grammar + a schemars-sourced type later if a real WO opens
that seam (named here, not invented).

`HeatTreatState` names the three variants the WO's goal text asks for
(`as_rolled`, `quenched_and_tempered(temper_temp)`,
`through_hardened(HRC)`) as one discriminated-by-`kind` model (mirrors
`CamOutcome`'s "one model, optional fields gated by a validator" shape
rather than a pydantic tagged union, since only one extra field is ever
required per variant). `HeatTreatStep` is an explicit PROGRAM STEP (a
material's declared state transition, e.g. as-rolled -> quenched-and-
tempered) that the die-set assembly (slice c) and its DFM gate
(:func:`check_heat_treat_transition`) consume -- the transition is
never silently assumed; a state cannot be claimed without the step that
produced it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from regolith.harness.models.cam.checks import CamOutcome
from regolith.harness.models.dfm.checks import (
    check_process_sequencing,
    check_quench_section_uniformity,
)
from regolith.harness.models.dfm.process_seeds import QUENCH_TEMPER_RECORD
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: The three state-kind tags the WO's goal text names verbatim.
# frob:doc docs/modules/py-harness.md#models-material-state
HeatTreatKind = Literal["as_rolled", "annealed", "quenched_and_tempered", "through_hardened"]

#: State kinds that are a valid PRECURSOR to a quench+temper transition
#: (a die-set blank is machined/EDM-profiled in a soft, machinable
#: state before hardening -- `through_hardened` re-entering quench+
#: temper is not a real heat-treat sequence and is refused by
#: :func:`check_heat_treat_transition`).
# frob:doc docs/modules/py-harness.md#models-material-state
_QUENCH_TEMPER_PRECURSORS: tuple[HeatTreatKind, ...] = ("as_rolled", "annealed")


# frob:doc docs/modules/py-harness.md#models-material-state
class HeatTreatState(BaseModel):
    """One material-state variant on a part's material reference.

    `temper_temp_c` is REQUIRED (and only meaningful) for
    `kind="quenched_and_tempered"`; `target_hrc` is REQUIRED (and only
    meaningful) for `kind="through_hardened"` -- the validator below
    refuses a state that declares the wrong field for its own kind
    (D250.3/D262: no synthesized defaults standing in for an unstated
    parameter)."""

    model_config = ConfigDict(frozen=True)

    kind: HeatTreatKind
    temper_temp_c: float | None = None
    target_hrc: float | None = None

    # frob:doc docs/modules/py-harness.md#models-material-state
    @model_validator(mode="after")
    def _check_kind_fields(self) -> HeatTreatState:
        """Refuse a state whose declared fields do not match its kind."""
        if self.kind == "quenched_and_tempered" and self.temper_temp_c is None:
            raise ValueError(
                "quenched_and_tempered state requires temper_temp_c "
                "-- no synthesized default temper temperature (D250.3)"
            )
        if self.kind != "quenched_and_tempered" and self.temper_temp_c is not None:
            raise ValueError(
                f"temper_temp_c is only meaningful for quenched_and_tempered, "
                f"not {self.kind!r}"
            )
        if self.kind == "through_hardened" and self.target_hrc is None:
            raise ValueError(
                "through_hardened state requires target_hrc -- no "
                "synthesized default hardness target (D250.3)"
            )
        if self.kind != "through_hardened" and self.target_hrc is not None:
            raise ValueError(
                f"target_hrc is only meaningful for through_hardened, "
                f"not {self.kind!r}"
            )
        return self


# frob:doc docs/modules/py-harness.md#models-material-state
class HeatTreatStep(BaseModel):
    """One explicit heat-treat program step: a material reference
    transitioning `from_state` -> `to_state` via a declared
    `process_record_key` (a `std.process/*` `ProcessRecord.key`, e.g.
    `QUENCH_TEMPER_RECORD.key`) -- the step IS the evidence a later
    claim (die-set fit/wear reasoning) cites; a state is never asserted
    without the step that produced it."""

    model_config = ConfigDict(frozen=True)

    material_ref: str
    from_state: HeatTreatState
    to_state: HeatTreatState
    process_record_key: str


# frob:doc docs/modules/py-harness.md#models-material-state
def check_heat_treat_transition(
    step: HeatTreatStep,
    section_thicknesses_mm: tuple[float, ...] = (),
    max_ratio: float = 3.0,
) -> CamOutcome:
    """Gate one :class:`HeatTreatStep` against the two REAL checks this
    repo already carries for quench+temper (WO-169 wave 1) rather than
    inventing a new predicate:

    1. sequencing (:func:`check_process_sequencing`): a transition
       INTO `quenched_and_tempered` must declare
       `process_record_key == QUENCH_TEMPER_RECORD.key`, and its
       `from_state.kind` must be a valid precursor
       (:data:`_QUENCH_TEMPER_PRECURSORS`) -- re-quenching an already
       `through_hardened` state is refused as a non-transition.
    2. section-uniformity (:func:`check_quench_section_uniformity`):
       the declared section thicknesses (die-plate geometry) must stay
       within `max_ratio` of thinnest:thickest (MIL-H-6875's
       qualitative distortion/cracking risk, procres/heat_treatment.md
       #77 DFM rule 2).

    Non-quench-and-temper transitions (e.g. `as_rolled` ->
    `as_rolled`, a no-op state declaration) pass vacuously -- this
    function only gates the ONE transition WO-169 landed a real check
    for; other transitions are named out of scope, not silently
    passed off as verified.
    """
    if step.to_state.kind != "quenched_and_tempered":
        return CamOutcome(
            excess=0.0,
            note=(
                f"transition to {step.to_state.kind!r} is not a "
                "quench+temper transition; no WO-169 check applies "
                "(vacuous pass, not a verified claim)"
            ),
        )
    if step.from_state.kind not in _QUENCH_TEMPER_PRECURSORS:
        _log.error(
            "heat treat transition: invalid precursor state %r for "
            "quench+temper (material %r)",
            step.from_state.kind,
            step.material_ref,
        )
        return CamOutcome(
            excess=1.0,
            note=(
                f"quench+temper transition declared from "
                f"{step.from_state.kind!r}, not one of "
                f"{_QUENCH_TEMPER_PRECURSORS} -- not a real heat-treat "
                "sequence"
            ),
        )
    sequencing = check_process_sequencing(
        required_upstream=QUENCH_TEMPER_RECORD.key,
        declared_upstream=(step.process_record_key,),
    )
    if sequencing.violated:
        return sequencing
    return check_quench_section_uniformity(section_thicknesses_mm, max_ratio)


__all__ = [
    "HeatTreatKind",
    "HeatTreatState",
    "HeatTreatStep",
    "check_heat_treat_transition",
]
