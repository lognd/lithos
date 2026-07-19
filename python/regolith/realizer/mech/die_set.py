"""Die-set assembly composition + stamping DFM (WO-166 slice c, D268
item 1, D269 amendment).

Per the recon dossier's own finding (cited in the WO), a bolted stack
of flat plates is ALREADY expressible by the existing hematite mating/
contract-assembly machinery (`docs/spec/hematite/03-contracts-and-
assemblies.md`) -- this module adds NO new assembly primitive, only
the die-set-SPECIFIC numeric checks the WO names (guide-pin/bushing
alignment tolerance stack, shut height, press tonnage) plus the wiring
of the stamping/punch-die-clearance and shot-peen-remediation DFM
checks WO-169 wave 1 already landed. Same plain-pydantic posture as
`wire_edm.py`/`material_state.py` (T-0043/D272): a new capability's own
composition type lives here, not as a `crates/regolith-syntax`
addition.

Press-tonnage model (:func:`required_tonnage_blanking_n`): the
STANDARD blanking-force formula (perimeter x thickness x shear
strength -- basic sheet-metal-forming mechanics, e.g. Boljanovic
"Sheet Metal Forming Processes and Die Design" ch. 2; NOT a
copyrighted lookup table, a first-principles force balance), fed into
the EXISTING `check_press_tonnage` containment check (WO-169).

Punch-die clearance (:func:`check_die_set_punch_die_clearance`):
`check_punch_die_clearance` (WO-169) ALREADY exists and takes
caller-declared `min_pct`/`max_pct` bounds rather than a hard-coded
constant -- but `std.process/stamping_blanking`
(`process_seeds_wave1_sheet.py`) records NO numeric clearance-percent
bounds itself (a NAMED REFUSAL: "Machinery's Handbook / ASM Sheet Metal
Forming Handbook punch-die clearance tables" are not transcribed). This
module therefore REFUSES to invent `min_pct`/`max_pct` -- callers who
have no cited bounds get an explicit refusal outcome (never a
fabricated number); a caller who DOES have a cited public-domain bound
may pass it and get a real containment check.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from regolith.harness.models.cam.checks import CamOutcome
from regolith.harness.models.dfm.checks import (
    check_press_tonnage,
    check_punch_die_clearance,
    check_shot_peen_recast_remediation,
)
from regolith.harness.models.material_state import HeatTreatState
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: Standard shear-strength-to-tensile-strength ratio (mild-steel/tool-
#: steel shearing, general sheet-metal-forming consensus: shear
#: strength is approximately 0.7-0.8x the ultimate tensile strength).
#: NOT used to invent a strength value -- callers supply their own
#: cited shear-strength MPa directly to :func:`required_tonnage_blanking_n`;
#: this constant is exposed only for a caller deriving shear strength
#: from a tensile-strength record and wanting the SAME conversion
#: factor this module's own docstring cites (one home, not re-derived
#: per caller).
# frob:doc docs/modules/py-realizer.md#mech-die-set
SHEAR_TO_TENSILE_RATIO = 0.75


# frob:doc docs/modules/py-realizer.md#mech-die-set
def required_tonnage_blanking_n(
    perimeter_mm: float, thickness_mm: float, shear_strength_mpa: float
) -> float:
    """Required blanking force, Newtons: `perimeter x thickness x
    shear_strength` -- the standard first-principles blanking-force
    balance (the punch shears the material along its cut perimeter;
    force = shear area x shear strength, shear area = perimeter x
    thickness). Citable general sheet-metal-forming mechanics (e.g.
    Boljanovic ch. 2), not a proprietary lookup table."""
    return perimeter_mm * thickness_mm * shear_strength_mpa


# frob:doc docs/modules/py-realizer.md#mech-die-set
def newtons_to_us_tons(force_n: float) -> float:
    """Newtons -> US (short) tons: `force_n / 8896.44` (1 US ton-force
    = 8896.44 N, a unit-conversion constant, not an engineering
    judgment call)."""
    return force_n / 8896.44


# frob:doc docs/modules/py-realizer.md#mech-die-set
class GuidePin(BaseModel):
    """One guide-pin/bushing pair: its nominal diameter and the
    declared worst-case radial clearance between pin and bushing (the
    per-pin contributor to the assembly's alignment tolerance
    stack)."""

    model_config = ConfigDict(frozen=True)

    diameter_mm: float = Field(gt=0.0)
    bushing_radial_clearance_mm: float = Field(ge=0.0)


# frob:doc docs/modules/py-realizer.md#mech-die-set
class DiePlate(BaseModel):
    """One plate in the stack: its material state (slice a) and
    thickness -- the shut-height and heat-treat-sequencing inputs."""

    model_config = ConfigDict(frozen=True)

    name: str
    material_ref: str
    heat_treat: HeatTreatState
    thickness_mm: float = Field(gt=0.0)


# frob:doc docs/modules/py-realizer.md#mech-die-set
class DieSetAssembly(BaseModel):
    """A two-(or-more)-plate bolted die-set stack (punch plate + die
    plate, hardened tool steel, bolted to a mild-steel backing plate --
    the existing bolted-flat-plate mating graph, no new primitive) plus
    the die-set-specific numeric inputs the WO names."""

    model_config = ConfigDict(frozen=True)

    plates: tuple[DiePlate, ...] = Field(min_length=2)
    guide_pins: tuple[GuidePin, ...] = Field(min_length=1)
    fastener_refs: tuple[str, ...] = Field(min_length=1)


# frob:doc docs/modules/py-realizer.md#mech-die-set
def shut_height_mm(assembly: DieSetAssembly) -> float:
    """The stack's shut height: the sum of every plate's declared
    thickness (v1 has no separate shim/spacer stack -- an honest
    simplification, not a claimed die-shoe/heel-block model)."""
    return sum(p.thickness_mm for p in assembly.plates)


# frob:doc docs/modules/py-realizer.md#mech-die-set
def check_die_set_shut_height(
    assembly: DieSetAssembly, press_min_shut_height_mm: float, press_max_shut_height_mm: float
) -> CamOutcome:
    """The stack's shut height must fall within the declared press's
    daylight-adjustment window -- a containment predicate over the
    press's own declared bounds (caller-supplied, never invented
    here), mirroring `check_stock_fit`'s extents-vs-travel shape."""
    height = shut_height_mm(assembly)
    low_excess = press_min_shut_height_mm - height
    high_excess = height - press_max_shut_height_mm
    excess = max(low_excess, high_excess)
    _log.debug(
        "die set shut height: height=%.3f min=%.3f max=%.3f excess=%.3f",
        height,
        press_min_shut_height_mm,
        press_max_shut_height_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"shut height {height:.3f}mm is outside the press's "
                f"[{press_min_shut_height_mm:.3f}, "
                f"{press_max_shut_height_mm:.3f}]mm window"
            ),
        )
    return CamOutcome(excess=excess, note="shut height within the press's window")


# frob:doc docs/modules/py-realizer.md#mech-die-set
def guide_pin_alignment_tolerance_stack_mm(assembly: DieSetAssembly) -> float:
    """Worst-case LINEAR sum of every guide pin's bushing radial
    clearance -- the conservative (never optimistic) tolerance-stack
    convention `bolted_joint.py`'s own module doc names for interval
    corners: sum the worst case rather than an RSS statistical
    estimate, since v1 has no declared process-capability data to
    justify a statistical stack-up."""
    return sum(pin.bushing_radial_clearance_mm for pin in assembly.guide_pins)


# frob:doc docs/modules/py-realizer.md#mech-die-set
def check_die_set_alignment(
    assembly: DieSetAssembly, max_alignment_tolerance_mm: float
) -> CamOutcome:
    """The worst-case guide-pin alignment stack must stay within a
    declared maximum (caller-supplied, from the punch/die clearance
    budget the die design targets -- never invented here)."""
    stack = guide_pin_alignment_tolerance_stack_mm(assembly)
    excess = stack - max_alignment_tolerance_mm
    _log.debug(
        "die set alignment stack: stack=%.4f max=%.4f excess=%.4f",
        stack,
        max_alignment_tolerance_mm,
        excess,
    )
    if excess > 0.0:
        return CamOutcome(
            excess=excess,
            note=(
                f"guide-pin alignment stack {stack:.4f}mm exceeds the "
                f"{max_alignment_tolerance_mm:.4f}mm budget"
            ),
        )
    return CamOutcome(excess=excess, note="alignment stack within budget")


# frob:doc docs/modules/py-realizer.md#mech-die-set
def check_die_set_press_tonnage(
    perimeter_mm: float,
    thickness_mm: float,
    shear_strength_mpa: float,
    press_capacity_tonnage: float,
) -> tuple[float, CamOutcome]:
    """Compute the required tonnage (:func:`required_tonnage_blanking_n`
    + :func:`newtons_to_us_tons`) and gate it against the declared
    press capacity via the EXISTING `check_press_tonnage` (WO-169).
    Returns `(required_tonnage, outcome)` so a caller/demo can cite the
    computed number directly."""
    force_n = required_tonnage_blanking_n(perimeter_mm, thickness_mm, shear_strength_mpa)
    required_tonnage = newtons_to_us_tons(force_n)
    outcome = check_press_tonnage(required_tonnage, press_capacity_tonnage)
    return required_tonnage, outcome


# frob:doc docs/modules/py-realizer.md#mech-die-set
class NamedRefusal(BaseModel):
    """One honestly-refused check: the WO-166/D269 posture for
    punch-die clearance when no cited public-domain bound exists --
    never a silently-invented `min_pct`/`max_pct`."""

    model_config = ConfigDict(frozen=True)

    check: str
    refused_source: str
    detail: str


# frob:doc docs/modules/py-realizer.md#mech-die-set
def check_die_set_punch_die_clearance(
    clearance_mm: float,
    thickness_mm: float,
    min_pct: float | None = None,
    max_pct: float | None = None,
) -> CamOutcome | NamedRefusal:
    """Punch/die clearance-percent containment (`check_punch_die_clearance`,
    WO-169) if the caller supplies a CITED `min_pct`/`max_pct` bound;
    otherwise an explicit :class:`NamedRefusal` (D269 amendment: the
    Machinery's Handbook/ASM Sheet Metal Forming Handbook clearance
    tables are copyrighted and not transcribed anywhere in this repo's
    `std.process/stamping_blanking` record -- see that record's own
    `named_refusal` provenance note). Never invents a bound to force a
    pass/fail."""
    if min_pct is None or max_pct is None:
        _log.warning(
            "die set punch-die clearance: no cited min_pct/max_pct bound "
            "available -- refusing rather than inventing one"
        )
        return NamedRefusal(
            check="punch_die_clearance",
            refused_source=(
                "Machinery's Handbook / ASM Sheet Metal Forming Handbook "
                "punch-die clearance-percent-by-material tables"
            ),
            detail=(
                "std.process/stamping_blanking (process_seeds_wave1_sheet.py) "
                "records only the qualitative existence of a thickness-"
                "percent relationship, per its own named_refusal provenance "
                "note; no numeric min_pct/max_pct is cited anywhere in this "
                "repo, so this check is deferred rather than run against an "
                "invented bound"
            ),
        )
    return check_punch_die_clearance(clearance_mm, thickness_mm, min_pct, max_pct)


# frob:doc docs/modules/py-realizer.md#mech-die-set
def check_die_set_shot_peen_remediation(
    upstream_process: str,
    compressive_depth_mm: float,
    min_depth_mm: float,
) -> CamOutcome:
    """Optional post-EDM recast-layer remediation gate
    (`check_shot_peen_recast_remediation`, WO-169, D269 amendment):
    named OPTIONAL, per the WO's honest-demo posture -- a caller only
    invokes this if the die-set program actually declares a shot-peen
    step; it is never invoked to claim recast removal happened when it
    did not."""
    return check_shot_peen_recast_remediation(
        upstream_process, "wire_edm", compressive_depth_mm, min_depth_mm
    )


__all__ = [
    "DiePlate",
    "DieSetAssembly",
    "GuidePin",
    "NamedRefusal",
    "SHEAR_TO_TENSILE_RATIO",
    "check_die_set_alignment",
    "check_die_set_press_tonnage",
    "check_die_set_punch_die_clearance",
    "check_die_set_shot_peen_remediation",
    "check_die_set_shut_height",
    "guide_pin_alignment_tolerance_stack_mm",
    "newtons_to_us_tons",
    "required_tonnage_blanking_n",
    "shut_height_mm",
]
