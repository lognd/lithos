"""Demo 19 -- wire-EDM die set: material states -> wire-EDM profile
cuts on the hardened D2/A2 plates -> bolted assembly with guide pins ->
press-tonnage/alignment/shut-height checks (WO-166 deliverable 7, D268
item 1).

A modest two-station blank-and-pierce die set on a small mild-steel
strip (D268 item 5's own instruction: "keep the demo's actual geometry
modest even though the underlying language surface is large"):

    punch plate (D2, quenched+tempered) -- wire-EDM profiled, station 1
    die plate   (A2, quenched+tempered) -- wire-EDM profiled, station 2
    backing plate (1018 mild steel, as-rolled) -- bolts the stack

SCOPE NOTE (an honest, named cut, mirroring demo18's own posture): this
demo drives the realizer + backend chain DIRECTLY from in-memory
`WireEdmProfile`/`DieSetAssembly` values rather than through
`regolith build`/`ship` against a `.cupr`/`.hema` source -- a real
source-language surface for a parameterized material-state variant or
a wire-EDM program verb would need either a hematite grammar change or
a staged-build integration point, both outside this dispatch's declared
scope (the schema-frozen posture named in `material_state.py`'s and
`wire_edm.py`'s own module docstrings: D272 spent, realized kinds stay
plain-pydantic, promotable later). Every OTHER deliverable (material-
state model, wire-EDM profile realize + DXF/setup-sheet emission,
die-set assembly composition, the five real numeric DFM gates, the
capability registration) is the REAL WO-166 code path, driven end to
end -- no invented constant anywhere below; the one check with no
citable public-domain bound (punch-die clearance) is an explicit named
refusal, never silently skipped or faked.
"""

from __future__ import annotations

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.edm import WireEdmBackend
from regolith.backends.framework import BackendInputs
from regolith.harness.models.dfm.process_seeds import QUENCH_TEMPER_RECORD
from regolith.harness.models.material_state import (
    HeatTreatState,
    HeatTreatStep,
    check_heat_treat_transition,
)
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.mech.die_set import (
    DiePlate,
    DieSetAssembly,
    GuidePin,
    NamedRefusal,
    check_die_set_alignment,
    check_die_set_press_tonnage,
    check_die_set_punch_die_clearance,
    check_die_set_shot_peen_remediation,
    check_die_set_shut_height,
    guide_pin_alignment_tolerance_stack_mm,
    shut_height_mm,
)
from regolith.realizer.mech.wire_edm import (
    LeadIn,
    ProfileVertex,
    WireEdmProfile,
    realize_wire_edm_profile,
)

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo19_wire_edm_die_set"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = (
    "wire-EDM die-set production program: material state -> profile cut -> "
    "bolted die-set assembly (WO-166)"
)
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SUBJECT_PUNCH = "die_set_punch_plate"
# frob:doc docs/modules/demos.md#the-proof-pack-demo-shape-every-demon_py
SUBJECT_DIE = "die_set_die_plate"

# A small two-station blank-and-pierce strip part: a 20x10mm rectangular
# blank cut (station 1, punch) and a 4mm-diameter pierce hole (station
# 2, die), a modest but genuine two-feature strip layout.
_PUNCH_PROFILE = WireEdmProfile(
    profile_ref=SUBJECT_PUNCH,
    material_ref="std.materials/tool_steel_d2",
    vertices=(
        ProfileVertex(x_mm=0.0, y_mm=0.0, corner_radius_mm=0.5),
        ProfileVertex(x_mm=20.0, y_mm=0.0, corner_radius_mm=0.5),
        ProfileVertex(x_mm=20.0, y_mm=10.0, corner_radius_mm=0.5),
        ProfileVertex(x_mm=0.0, y_mm=10.0, corner_radius_mm=0.5),
    ),
    closed=True,
    kerf_mm=0.25,
    spark_gap_mm=0.02,
    lead_in=LeadIn(start_x_mm=10.0, start_y_mm=5.0, has_start_hole=True),
)
_DIE_PROFILE = WireEdmProfile(
    profile_ref=SUBJECT_DIE,
    material_ref="std.materials/tool_steel_a2",
    vertices=(
        ProfileVertex(x_mm=-2.0, y_mm=0.0, corner_radius_mm=2.0),
        ProfileVertex(x_mm=2.0, y_mm=0.0, corner_radius_mm=2.0),
        ProfileVertex(x_mm=2.0, y_mm=4.0, corner_radius_mm=2.0),
        ProfileVertex(x_mm=-2.0, y_mm=4.0, corner_radius_mm=2.0),
    ),
    closed=True,
    kerf_mm=0.25,
    spark_gap_mm=0.02,
    lead_in=LeadIn(start_x_mm=0.0, start_y_mm=2.0, has_start_hole=True),
)


def _assembly() -> DieSetAssembly:
    """The bolted die-set stack: hardened D2 punch plate, hardened A2
    die plate, mild-1018 backing plate -- the existing bolted-flat-
    plate mating shape (WO-72 precedent), no new assembly primitive."""
    return DieSetAssembly(
        plates=(
            DiePlate(
                name="punch_plate",
                material_ref="std.materials/tool_steel_d2",
                heat_treat=HeatTreatState(
                    kind="quenched_and_tempered", temper_temp_c=205.0
                ),
                thickness_mm=20.0,
            ),
            DiePlate(
                name="die_plate",
                material_ref="std.materials/tool_steel_a2",
                heat_treat=HeatTreatState(
                    kind="quenched_and_tempered", temper_temp_c=205.0
                ),
                thickness_mm=25.0,
            ),
            DiePlate(
                name="backing_plate",
                material_ref="std.materials/plate_1018",
                heat_treat=HeatTreatState(kind="as_rolled"),
                thickness_mm=12.0,
            ),
        ),
        guide_pins=(
            GuidePin(diameter_mm=12.0, bushing_radial_clearance_mm=0.01),
            GuidePin(diameter_mm=12.0, bushing_radial_clearance_mm=0.01),
        ),
        fastener_refs=("std.fasteners/socket_head_cap_screw_m8x30",),
    )


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
def run() -> bool:
    """Emit the die-set proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)

    # --- slice a: material-state transitions, both tool-steel plates ---
    heat_treat_steps = tuple(
        HeatTreatStep(
            material_ref=ref,
            from_state=HeatTreatState(kind="as_rolled"),
            to_state=HeatTreatState(kind="quenched_and_tempered", temper_temp_c=205.0),
            process_record_key=QUENCH_TEMPER_RECORD.key,
        )
        for ref in ("std.materials/tool_steel_d2", "std.materials/tool_steel_a2")
    )
    # Both tool-steel plates are 20mm/25mm thick sections, well within
    # MIL-H-6875's qualitative uniformity tolerance for a die-plate
    # blank -- declared here as the two plates' own thicknesses.
    section_thicknesses_mm = (20.0, 25.0)
    heat_treat_outcomes = tuple(
        check_heat_treat_transition(
            step, section_thicknesses_mm=section_thicknesses_mm, max_ratio=3.0
        )
        for step in heat_treat_steps
    )
    for step, outcome in zip(heat_treat_steps, heat_treat_outcomes, strict=True):
        if outcome.violated:
            raise RuntimeError(
                f"heat-treat transition for {step.material_ref} violated: "
                f"{outcome.note}"
            )

    # --- slice b: wire-EDM profile realize + DXF/setup-sheet emission ---
    punch_realized = realize_wire_edm_profile(_PUNCH_PROFILE)
    die_realized = realize_wire_edm_profile(_DIE_PROFILE)
    if punch_realized.is_err:
        raise RuntimeError(f"punch profile realize failed: {punch_realized.danger_err}")
    if die_realized.is_err:
        raise RuntimeError(f"die profile realize failed: {die_realized.danger_err}")

    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="demo19"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore(str(REPO_ROOT)),
        edm_profiles={
            SUBJECT_PUNCH: punch_realized.danger_ok,
            SUBJECT_DIE: die_realized.danger_ok,
        },
    )
    for subject, prefix in ((SUBJECT_PUNCH, "punch"), (SUBJECT_DIE, "die")):
        produced = WireEdmBackend(subject).produce(inputs)
        if produced.is_err:
            raise RuntimeError(
                f"EDM backend failed for {subject}: {produced.danger_err}"
            )
        for f in produced.danger_ok:
            relpath = f.relpath.replace("edm_profile/", f"edm_profile/{prefix}_")
            deterministic = (
                f.provenance is not None and f.provenance.tier == "deterministic"
            )
            writer.emit(relpath, f.content, deterministic=deterministic)

    # --- slice c: die-set assembly + numeric checks ---
    assembly = _assembly()
    height = shut_height_mm(assembly)
    shut_height_outcome = check_die_set_shut_height(assembly, 40.0, 80.0)
    alignment_stack_mm = guide_pin_alignment_tolerance_stack_mm(assembly)
    alignment_outcome = check_die_set_alignment(assembly, 0.05)

    # Strip perimeter x thickness x cited shear strength: 1018 mild
    # steel's shear strength is approximately 310 MPa (a common
    # engineering-consensus figure for low-carbon steel shearing,
    # SHEAR_TO_TENSILE_RATIO x ~410 MPa UTS -- an honest engineering
    # estimate, not a vendor spec sheet transcription).
    strip_perimeter_mm = 2 * (20.0 + 10.0)
    strip_thickness_mm = 2.0
    shear_strength_mpa = 310.0
    press_capacity_tons = 15.0
    required_tonnage, tonnage_outcome = check_die_set_press_tonnage(
        strip_perimeter_mm, strip_thickness_mm, shear_strength_mpa, press_capacity_tons
    )
    if tonnage_outcome.violated:
        raise RuntimeError(f"press tonnage check violated: {tonnage_outcome.note}")
    if shut_height_outcome.violated:
        raise RuntimeError(f"shut height check violated: {shut_height_outcome.note}")
    if alignment_outcome.violated:
        raise RuntimeError(f"alignment check violated: {alignment_outcome.note}")

    # Punch-die clearance: NO cited public-domain min_pct/max_pct bound
    # exists in this repo (see die_set.py's own module doc) -- this is
    # the D269-named refusal, never a silently invented number.
    clearance_result = check_die_set_punch_die_clearance(0.1, strip_thickness_mm)
    if not isinstance(clearance_result, NamedRefusal):
        raise RuntimeError("expected a named refusal for punch-die clearance")

    # Shot-peen recast-layer remediation: OPTIONAL per the WO's honest-
    # demo posture -- this demo does NOT invoke it (no shot-peen step is
    # declared), so no compressive-layer-depth claim is made anywhere
    # in this proof pack. Named here for completeness, not invoked.
    _ = check_die_set_shot_peen_remediation  # referenced, deliberately unused

    checks_report = {
        "heat_treat_transitions": [
            {
                "material_ref": step.material_ref,
                "to_state": step.to_state.kind,
                "violated": outcome.violated,
                "note": outcome.note,
            }
            for step, outcome in zip(heat_treat_steps, heat_treat_outcomes, strict=True)
        ],
        "shut_height_mm": height,
        "shut_height_check": {
            "violated": shut_height_outcome.violated,
            "note": shut_height_outcome.note,
        },
        "guide_pin_alignment_stack_mm": alignment_stack_mm,
        "alignment_check": {
            "violated": alignment_outcome.violated,
            "note": alignment_outcome.note,
        },
        "required_press_tonnage": required_tonnage,
        "press_capacity_tonnage": press_capacity_tons,
        "press_tonnage_check": {
            "violated": tonnage_outcome.violated,
            "note": tonnage_outcome.note,
        },
        "punch_die_clearance": {
            "status": "named_refusal",
            "refused_source": clearance_result.refused_source,
            "detail": clearance_result.detail,
        },
        "shot_peen_remediation": {
            "status": "not_invoked",
            "note": "optional per WO-166/D269; no shot-peen step declared "
            "in this demo, so no recast-remediation claim is made",
        },
    }
    import json

    checks_bytes = (
        json.dumps(checks_report, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    ).encode("ascii")
    writer.emit("die_set/checks_report.json", checks_bytes, deterministic=True)

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: `HeatTreatStep` (slice a) -> "
            "`regolith.harness.models.material_state.check_heat_treat_transition` "
            "-> `WireEdmProfile` (slice b) -> "
            "`regolith.realizer.mech.wire_edm.realize_wire_edm_profile` -> "
            "`regolith.backends.edm.WireEdmBackend.produce` (DXF via the "
            "existing `DrawingModel`/`render_dxf` path + setup sheet) -> "
            "`DieSetAssembly` (slice c) -> shut-height/alignment/press-"
            "tonnage/punch-die-clearance checks -- see the SCOPE NOTE below "
            "for why this demo drives that path directly rather than "
            "through `regolith build`/`ship`.",
            "- feature proven: two hardened tool-steel plates (D2 punch, "
            "A2 die) each state-transitioned as_rolled -> "
            "quenched_and_tempered (`std.process/quench_temper`, gated by "
            "the real `check_process_sequencing` + "
            "`check_quench_section_uniformity` pair, WO-169 wave 1) and "
            "each wire-EDM profiled (kerf 0.25mm, spark gap 0.02mm) with "
            "every declared corner radius passing "
            "`check_wire_edm_corner_radius` and the closed-profile start-"
            "hole gate passing `check_wire_edm_start_hole`; the three-"
            f"plate bolted stack (shut height {height:.1f}mm) passes its "
            "declared press-daylight window; the two-guide-pin alignment "
            f"stack ({alignment_stack_mm:.3f}mm worst-case) passes its "
            f"declared budget; the required press tonnage "
            f"({required_tonnage:.3f} tons, from the standard blanking-"
            "force formula perimeter x thickness x shear strength) passes "
            f"against the declared {press_capacity_tons:.1f}-ton press.",
            "- capability registration: `wire_edm` domain registered via "
            "`regolith.backends.capabilities.register_capability` (all "
            "seven `RealizerCapability` fields populated: `program_kind`="
            "`WireEdmProfile`, `realized_kind`=`edm_profile.realized`, "
            "`artifact_families`=(`edm_profile`, `die_set`), one "
            "`deterministic` tool-adapter tier -- no real EDM-machine "
            "toolpath post-processor is claimed -- `process_records` "
            "citing `std.process/wire_edm`/`quench_temper`/"
            "`stamping_blanking`, six real `dfm_checks`, and the "
            "`mfg.die_set_producible` claim kind).",
            "- honesty labels: `tier=deterministic` on every emitted file "
            "(no real EDM-machine tool adapter claimed, WO-160/AD-45); "
            "punch-die clearance is an explicit NAMED REFUSAL (no cited "
            "public-domain clearance-percent-by-material bound exists in "
            "this repo -- see `die_set/checks_report.json`'s own "
            "`punch_die_clearance` entry); the shot-peen recast-layer "
            "remediation step is named OPTIONAL and NOT invoked in this "
            "demo (no compressive-layer-depth claim is made).",
            "- SCOPE NOTE (see this script's module docstring): this demo "
            "drives the realizer + backend chain directly from in-memory "
            "IR values rather than through `regolith build`/`ship` "
            "against a `.cupr`/`.hema` source -- a hematite grammar "
            "addition for a parameterized material-state variant, or a "
            "new wire-EDM program verb in `regolith-syntax`/`regolith-"
            "lower`, is outside this dispatch's schema-frozen posture "
            "(D272 spent; realized kinds stay plain-pydantic, promotable "
            "later per the T-0043 posture) -- named here as a follow-up, "
            "never silently invented.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo19_wire_edm_die_set",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (die-set production program, not an optimizer surface)",
        domain=(
            "two-station wire-EDM stamping die set (D2 punch / A2 die / "
            "1018 backing plate) -- blank-and-pierce strip part"
        ),
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
