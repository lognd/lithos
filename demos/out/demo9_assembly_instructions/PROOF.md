# PROOF: mate-ordered assembly instructions with per-step views (arm_a6 J2)

- feature proven: the shipped `instructions/` family (charter 38 sec. 1.13) -- deterministic mate-ordered steps (fixed root first, then placed parts) where each placed step cites the typed mate edge that placed it, plus one embedded projected front view per step (parts placed so far in gray, the current part highlighted), projected from the pinned STEP bytes.
- pipeline path: joint2.hema's `ShoulderJointAssembly` (4 parts, `connect:` mates m_retainer/m_motor/j2), realized per part through the real OCCT interpreter, solved by `solve_assembly`, STEP bytes pinned into arm_a6's native store, then `regolith build --release` + `regolith ship --spec` with the `"assemblies"` block -- the exact CLI channel WO-96 designed. No fake below the AssemblyDef mirror (joint2.hema's own documented integration seam).
- step order: ['housing', 'motor_bracket', 'retainer', 'upper_arm'], mate refs cited: ['m_motor', 'm_retainer', 'j2'].
- masses are derived (realized OCCT volume x 2700 kg/m^3 AL 6061), never invented; no fastener/torque callouts render because no discharged bolted-joint evidence is keyed to these part ids (honesty rule: only discharged quantities render).
- determinism: the steps JSON, the markdown document, and the assembly STEP are all deterministic producers -- re-running reproduces the hashes below.

## Re-run

```
uv run python -m demos.demo9_assembly_instructions
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `instructions/instructions/ShoulderJointAssembly.instructions.md` | 3996 | `sha256:b955d2e100c05a2873549aa06a10315ccd6ca2261980588f6b993dd389f78498` |
| `instructions/instructions/ShoulderJointAssembly.steps.json` | 484 | `sha256:3511ce4b1badf7e83d93b3b2e96607ec69f03bca556d27bfb3660ff937669a79` |
| `ship.spec.demo9.json` | 4261 | `sha256:d02e953eeff647b6b52b4121b1e5f155260aa039c296b653172e04099ef6d21d` |
| `shoulder_joint_assembly.step` | 64436 | `sha256:8bc0deb1c914662d88a113f2ae47249055f4504a93b8b44c59d4d4a8a83d06ad` |
