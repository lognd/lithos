# WO-22: Mech geometry realizer (feature IR -> OCCT -> STEP)

Status: todo
Depends: WO-19 (lowering emits the typed stage/feature structure),
WO-20 (the realizer registers as a model pack)
Language: Python (realizer adapter per AD-1: "OCCT via build123d");
Rust `regolith-api`/`regolith-oblig` only if BuildOutput needs a
serialized feature-program payload it does not already expose
Spec: hematite/05 (L3->L4->L6), hematite/06 Phase C items 8-9;
regolith/08 sec. L4; regolith/07 sec. 6 (planning as evidence)

## Goal

A `.hem` part's stage pipeline realizes to real geometry: feature IR
drives build123d/OCCT, exports STEP, and a post-geometry verification
pass confirms the static topology predictions the compiler made.
This is roadmap Phase C items 8-9 -- the first time the toolchain
produces an artifact a machine shop can open.

## Deliverables

- Feature-program extraction: a serialized, deterministic feature
  program per part from the lowering output (stages, setups, feature
  ops with resolved parameters and Cause-typed resolutions). If
  `BuildOutput` lacks the payload, add it Rust-side (schema-versioned,
  AD-5) -- the Python realizer consumes ONLY the serialized form,
  never the CST (AD-4 coarse boundary).
- `regolith.realizer.mech`: build123d interpreter for the v1 feature
  set actually used by the corpus (`examples/` is the contract:
  sketch profiles, Extrude/Pocket/Fillet/Hole/Bend and the weldment/
  pattern forms the goldens exercise). Registered as a model pack
  (AD-19) discharging `geometry_realizable`-shaped obligations; the
  realized-geometry record (STEP hash, mass properties, topology
  summary) is content-addressed EVIDENCE, cached like any evidence.
- STEP export (AP242 baseline; PMI carry-through tracked as a cut if
  build123d's PMI surface is insufficient -- record, do not fake).
- Post-geometry verification pass: recompute mass/volume/bbox and the
  declared-measures the static core predicted (geom role kit,
  regolith/10 sec. 3a) from the realized solid; disagreement beyond
  model eps is a VIOLATED evidence value on the prediction claim
  (the static prediction was wrong -- loud, exactly the point).
- Determinism: same source -> byte-identical feature program and
  STEP content hash on one platform; cross-platform the HASH of the
  topology summary (not the STEP bytes -- OCCT bytes may differ) is
  the golden (extends the AD-6 determinism job honestly).
- Docs: realizer doc under `docs/implementation/`; TODO ledger flip.

## Acceptance

- `regolith build` on `examples/mech/sheet_bracket.hem` (and the
  corpus parts the v1 feature set covers) emits STEP files a fresh
  OCCT session re-imports cleanly; mass properties match the entity
  DB's predictions within declared eps.
- A deliberately-wrong prediction fixture (predicted volume edited)
  yields violated post-geometry evidence, release-gated.
- Corpus parts OUTSIDE the v1 feature set defer honestly
  (indeterminate `geometry_realizable`, named unsupported op) --
  never a crash, never a silent skip.
- `make check` green; goldens updated in the same change.
