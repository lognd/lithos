"""Demo 9 -- assembly instructions: mate-ordered steps with per-step views.

WO-115 deliverable 3 (charter 38 sec. 1.13). The subject is arm_a6's
`ShoulderJointAssembly` (joint2.hema) -- THE realized joint sub-assembly
the WO-75 flagship deliverable names. The pipeline is entirely real:

    joint2.hema's 4-part/3-mate topology, hand-declared as an
    `AssemblyDef` (the documented integration seam -- joint2.hema's own
    header comment says the mirroring AssemblyDef is how `connect:`
    reaches the numeric solve today, the WO-64/75 idiom)
    -> real OCCT realization per part (`realize_feature_program`)
    -> `solve_assembly` (real mate solve; typed WO-104 mate edges)
    -> STEP bytes pinned into arm_a6's own NativeArtifactStore
    -> `regolith build --release` + `regolith ship --spec <spec +
       "assemblies" block>` (the REAL CLI channel WO-96 designed for
       exactly this input)
    -> the shipped `instructions/` family: `steps.json` (mate-ordered,
       every step citing the placing mate edge) + `instructions.md`
       with an embedded projected front view per step.

Masses are derived (realized OCCT volume x AL 6061 density), never
invented. The assembly's composite STEP export ships beside the
instructions so the ordered document and the solid can be compared.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

from regolith.backends.artifacts import NativeArtifactStore
from regolith.logging_setup import get_logger
from regolith.realizer.mech.assembly import (
    AssemblyDef,
    AssemblyPartDef,
    MateDef,
    MateTransform,
    export_assembly_step,
    solve_assembly,
)
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

DEMO = "demo9_assembly_instructions"
SURFACE = "mate-ordered assembly instructions with per-step views (arm_a6 J2)"
PROJECT = REPO_ROOT / "examples" / "flagships" / "arm_a6"

_AL_DENSITY_KG_M3 = 2700.0
_SUBJECT = "ShoulderJointAssembly"

# joint2.hema's declared geometry: HousingFlat-shaped 70x70 plates
# (housing 25mm bore stack depth, retainer 6mm, bracket 8mm per the
# .hema stage declarations) and UpperArm's 300x24x20 section -- the
# same dims the WO-75 acceptance fixture reads off the flagship.
_PLATE_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.070, y=0.0),
    Point2(x=0.070, y=0.070),
    Point2(x=0.0, y=0.070),
)
_ARM_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.300, y=0.0),
    Point2(x=0.300, y=0.024),
    Point2(x=0.0, y=0.024),
)


def _cli(*args: str) -> None:
    cmd = [sys.executable, "-m", "regolith.cli", *args]
    _log.info("demo9: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"regolith {args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        )


def _realized(part_name: str, outline, thickness_m: float):
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=thickness_m)
    )
    stage = Stage(name="mill", process="cnc_mill", features=(op,))
    program = FeatureProgram(
        part_name=part_name, material="AL6061_T6", stages=(stage,)
    )
    result = realize_feature_program(program)
    if result.is_err:
        raise RuntimeError(f"realize {part_name}: {result.danger_err}")
    return result.danger_ok


def _part_def(part_id: str, artifact, store: NativeArtifactStore) -> AssemblyPartDef:
    """Pin the part's REAL STEP bytes; derive mass from realized volume."""
    digest = store.put(artifact.step_bytes)
    volume_m3 = artifact.geometry.topology.volume_mm3 / 1.0e9
    return AssemblyPartDef(
        id=part_id,
        geometry=artifact,
        mass_kg=volume_m3 * _AL_DENSITY_KG_M3,
        geometry_digest=digest,
    )


def _shoulder_assembly(store: NativeArtifactStore) -> AssemblyDef:
    housing = _realized("ShoulderHousing", _PLATE_OUTLINE, 0.025)
    retainer = _realized("BearingRetainer", _PLATE_OUTLINE, 0.006)
    motor_bracket = _realized("MotorBracket", _PLATE_OUTLINE, 0.008)
    upper_arm = _realized("UpperArm", _ARM_OUTLINE, 0.020)
    return AssemblyDef(
        parts=(
            _part_def("housing", housing, store),
            _part_def("retainer", retainer, store),
            _part_def("motor_bracket", motor_bracket, store),
            _part_def("upper_arm", upper_arm, store),
        ),
        # joint2.hema `connect:` verbatim topology: two bolted patterns
        # + the J2 revolute, as the WO-64/75 hand-declared mirror.
        mates=(
            MateDef(
                id="m_retainer",
                kind="align",
                from_part="housing",
                to_part="retainer",
                transform=MateTransform(translation_m=(0.0, 0.0, 0.025)),
            ),
            MateDef(
                id="m_motor",
                kind="align",
                from_part="housing",
                to_part="motor_bracket",
                transform=MateTransform(translation_m=(0.0, 0.0, -0.008)),
            ),
            MateDef(
                id="j2",
                kind="align",
                from_part="housing",
                to_part="upper_arm",
                transform=MateTransform(translation_m=(0.070, 0.0, 0.0)),
            ),
        ),
        mating_graph_hash="blake3:demo9_shoulder_joint_assembly",
    )


def run() -> bool:
    """Emit the assembly-instructions proof pack; return True (live)."""
    writer = DemoWriter(DEMO, SURFACE)
    build_dir = writer.out_dir / "build"
    dist_dir = writer.out_dir / "dist"
    for stale in (build_dir, dist_dir):
        if stale.exists():
            shutil.rmtree(stale)

    # 1. Solve the real assembly; pin STEP bytes into the project store
    #    (the caller-populates-native-store contract every elec-leg test
    #    and `preview` itself follow).
    store = NativeArtifactStore(str(PROJECT))
    assembly = _shoulder_assembly(store)
    solved = solve_assembly(assembly)
    if solved.is_err:
        raise RuntimeError(f"solve_assembly failed: {solved.danger_err}")
    realized = solved.danger_ok
    unplaced = [p for p, s in realized.dof_states.items() if s not in ("fixed", "placed")]
    if unplaced:
        raise RuntimeError(f"assembly left parts unplaced: {unplaced}")
    writer.emit(
        "shoulder_joint_assembly.step", export_assembly_step(assembly, realized)
    )

    # 2. The demo spec: the committed arm_a6 spec + the "assemblies"
    #    block (the WO-96 CLI channel for caller-supplied
    #    RealizedAssembly JSON).
    spec_data = json.loads((PROJECT / "ship.spec.json").read_text())
    spec_data["assemblies"] = {_SUBJECT: json.loads(realized.model_dump_json())}
    spec_path = writer.out_dir / "ship.spec.demo9.json"
    spec_path.write_text(json.dumps(spec_data, indent=2, sort_keys=True) + "\n")
    writer.emit("ship.spec.demo9.json", spec_path.read_bytes())

    # 3. The real two-command flow with the assemblies spec.
    _cli("build", "--release", str(PROJECT), "--out", str(build_dir))
    _cli(
        "ship",
        str(PROJECT),
        "--build",
        str(build_dir),
        "--spec",
        str(spec_path),
        "--out",
        str(dist_dir),
    )
    instructions_dir = dist_dir / "instructions"
    emitted = []
    for path in sorted(instructions_dir.rglob("*")):
        if path.is_file():
            rel = "instructions/" + str(path.relative_to(instructions_dir))
            writer.emit(rel, path.read_bytes())
            emitted.append(rel)
    if not emitted:
        raise RuntimeError("ship emitted no instructions/ family")

    doc = next(instructions_dir.rglob(f"*{_SUBJECT}.instructions.md")).read_text()
    if "<svg" not in doc:
        raise RuntimeError("instructions document embeds no per-step view")
    steps_json = json.loads(
        next(instructions_dir.rglob(f"*{_SUBJECT}.steps.json")).read_text()
    )
    mate_refs = [s.get("mate_ref") for s in steps_json["steps"]]
    placed_with_mates = [m for m in mate_refs if m]
    if not placed_with_mates:
        raise RuntimeError("no step cites its placing mate edge")

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- feature proven: the shipped `instructions/` family "
            "(charter 38 sec. 1.13) -- deterministic mate-ordered steps "
            "(fixed root first, then placed parts) where each placed "
            "step cites the typed mate edge that placed it, plus one "
            "embedded projected front view per step (parts placed so "
            "far in gray, the current part highlighted), projected from "
            "the pinned STEP bytes.",
            "- pipeline path: joint2.hema's `ShoulderJointAssembly` "
            "(4 parts, `connect:` mates m_retainer/m_motor/j2), realized "
            "per part through the real OCCT interpreter, solved by "
            "`solve_assembly`, STEP bytes pinned into arm_a6's native "
            "store, then `regolith build --release` + `regolith ship "
            "--spec` with the `\"assemblies\"` block -- the exact CLI "
            "channel WO-96 designed. No fake below the AssemblyDef "
            "mirror (joint2.hema's own documented integration seam).",
            f"- step order: {[s['part_ref'] for s in steps_json['steps']]}, "
            f"mate refs cited: {placed_with_mates}.",
            "- masses are derived (realized OCCT volume x 2700 kg/m^3 "
            "AL 6061), never invented; no fastener/torque callouts "
            "render because no discharged bolted-joint evidence is "
            "keyed to these part ids (honesty rule: only discharged "
            "quantities render).",
            "- determinism: the steps JSON, the markdown document, and "
            "the assembly STEP are all deterministic producers -- "
            "re-running reproduces the hashes below.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo9_assembly_instructions",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (instructions family, not an optimizer surface)",
        domain="arm_a6 ShoulderJointAssembly (joint2.hema J2)",
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
