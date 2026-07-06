# WO-25: Manufacturing backends + the ship pipeline (L6)

Status: todo
Depends: WO-22 (mech geometry), WO-24 (elec layout), WO-14
(lockfile), WO-21 (release gate trust floors)
Language: Python (`regolith.backends`, `regolith.cli`)
Spec: hematite/05 L6; cuprite/06 L6; regolith/07 sec. 6 ("backends
serialize evidence; they never decide"); regolith/09 (build,
lockfile, release semantics, INV-24)

## Goal

`regolith ship` produces the complete manufacturing package for a
release-gated design: mech STEP + BOM + fab notes, elec gerbers/
drill/pick-and-place/BOM -- every file a serialization of pinned
evidence and lockfile state, none of it decision-making. This is the
"send it to the manufacturer tomorrow" WO.

## Deliverables

- Backend framework (`regolith.backends`): a backend consumes ONLY
  (lockfile, evidence cache, realized artifacts) -- enforced by
  construction (no compiler/CST imports); every output file is
  hash-recorded in a ship manifest.
- Mech package: STEP (from WO-22, re-serialized per config), BOM
  (assembly tree + registry-record part numbers + materials, CSV +
  JSON), fab notes (material, finish, tolerance table from allocated
  tolerances, quantity). Drawings: TRACKED CUT for v1 (STEP+PMI and
  notes cover CNC quoting; reopen when a fab actually demands 2D).
- Elec package: gerber + drill + pick-and-place + BOM emitted by
  driving kicad-cli against the WO-24 pinned layout (the backend
  serializes the pinned artifact's outputs; KiCad decided nothing new
  -- decisions were pinned at WO-24); assembly BOM merges registry
  vendor refs. Panelization: planner-model stub honoring regolith/07
  sec. 6 (single-board pass-through in v1; the panel plan slot exists
  and defers honestly).
- `regolith ship [--out DIR]` CLI: refuses unless `build --release`
  passes (INV-24 totality: every obligation discharged or an
  acknowledged deviation; trust floors per WO-21 enforced); emits the
  package + a signed ship manifest (design hash, lockfile hash,
  evidence roll-up, per-file hashes) -- the manifest is the package's
  attestation, signed with the project key (WO-21 machinery).
- Docs: `docs/regolith/` gets the ship-manifest schema section;
  CLI docs; TODO ledger flip.

## Acceptance

- End-to-end on a corpus design pair (sheet bracket + one Kestrel
  board): `regolith build --release && regolith ship` produces a
  directory a human can upload to a CNC shop / board house: STEP,
  BOM, gerbers, drill, PnP, BOM, manifest. Gerbers re-open in a
  reference viewer (gerbv/kicad) without errors.
- Ship REFUSES (named diagnostics, nonzero exit) when: an obligation
  is indeterminate; an assume!/todo! is unacknowledged; a trust
  floor is unmet; the lockfile is stale against source.
- Manifest verification round-trip: `regolith ship --verify DIR`
  re-hashes every file and checks the manifest signature.
- Determinism: two ship runs from the same lockfile produce
  byte-identical packages (timestamps normalized), asserted in CI.
- `make check` green.
