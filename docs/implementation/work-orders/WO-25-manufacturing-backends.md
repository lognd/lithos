# WO-25: Manufacturing backends + the ship pipeline (L6)

Status: in-progress (backend framework + CLI landed, see "Progress"
below; end-to-end acceptance BLOCKED on three upstream walls named
there, none of them this WO's own scope)
Depends: WO-22 (mech geometry), WO-24 (elec layout), WO-14
(lockfile), WO-21 (release gate trust floors)
Language: Python (`regolith.backends`, `regolith.cli`)
Spec: hematite/05 L6; cuprite/06 L6; regolith/07 sec. 6 ("backends
serialize evidence; they never decide"); regolith/09 (build,
lockfile, release semantics, INV-24)

AMENDMENT (cycle 24, D128/AD-25): "realized artifacts" in the
backend framework's input triple means the WO-42 realized-domain IRs
(`RealizedGeometry`, `RealizedLayout`) plus the native artifacts
they pin. Derived outputs (BOM assembly trees, fab-note tolerance
tables, pick-and-place) read the IRs, never re-parse STEP or
`.kicad_pcb` (the parse happens once, producer-side). Dispatch after
WO-42; the "backends never decide" rule is unchanged.

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

## Progress

Backend framework + CLI landed this cycle; `make check` green on
everything shipped. Delivered:

- `regolith.backends` (framework, mech, elec, manifest, ship,
  artifacts): the `BackendInputs` triple (lockfile, evidence,
  realized IRs + a native-artifact store keyed by the IR's own
  SHA-256 hash, D131/AD-25 discipline) is the ONLY thing `MechBackend`/
  `ElecBackend` read -- enforced by a standing test
  (`tests/backends/test_framework.py::
  test_backend_implementations_never_import_the_compiler`) that greps
  both modules for a `regolith.compiler`/`regolith._core` import.
- `MechBackend`: STEP passthrough (the pinned bytes behind
  `RealizedGeometry.step_content_hash`) + `bom.csv`/`bom.json` +
  `fab_notes.json`, driven by caller-supplied `AssemblyLine`/
  `FabNoteSpec` rows (already-decided registry/lockfile data; the
  backend invents no part number or tolerance). Proven against a REAL
  `realize_feature_program` output (build123d/OCCT genuinely runs in
  this sandbox, unlike KiCad), including a determinism assertion.
- `ElecBackend`: drives `kicad-cli pcb export gerbers/drill/pos`
  against the pinned `.kicad_pcb` bytes behind
  `RealizedLayout.kicad_pcb_content_hash`, gated by
  `regolith.realizer.elec.kicad.real_kicad_available()` (the WO-35
  gate, reused rather than reinvented) -- closed in this sandbox
  (verified: no `kicad-cli` on PATH), so the honest-cut path is what a
  caller sees today; the real-export path is proven with a fake
  subprocess runner (`tests/backends/test_elec.py`, same
  dependency-injection discipline as `tests/realizer/elec/
  test_kicad.py`). Panelization: single-board `PanelPlan`
  pass-through per the WO body.
- `ShipManifest` + sign/verify: reuses `harness.attest`'s envelope
  discipline (domain-tagged blake3 content address, ed25519, never
  signs raw bytes) rather than inventing a second signing scheme;
  `verify_file_hashes` proves the `--verify` re-hash/tamper-detection
  path.
- `regolith.backends.ship.ship()`: runs a T3 `staged_build`
  (`orchestrator.orchestrate.release_gate`, INV-24 + WO-21 trust
  floors already enforced inside it -- this WO adds no second gate),
  refuses before writing anything if the gate is not clean, derives
  the geometry/layout maps from `StagedBuildReport.realized_inputs`
  first (WO-42 deliverable 3/5) so a caller need not re-supply what
  the build already resolved, writes every backend's files under
  `<out>/<backend-name>/`, and signs+writes `manifest.json`.
  `ship.verify()` is the `--verify` counterpart.
- CLI: `regolith ship [FILES] [--out DIR] [--spec FILE] [--key ID]
  [--verify DIR --trust-keys FILE]` in `regolith/cli/app.py`. `--spec`
  is a JSON file naming the mech/elec `AssemblyLine`/`FabNoteSpec`
  rows (a serialization format for ALREADY-DECIDED data, same
  category as the WO-20 subprocess wire JSON -- not a new design
  decision); omitting it ships a manifest-only release attestation
  with zero packaged files.
- Tests: `tests/backends/` (32 cases: artifacts, framework guard,
  mech, elec, manifest, ship) + 3 new `tests/test_cli_app.py` cases
  for the `ship` CLI's error paths. `docs/regolith/09-build-and-
  lockfile.md` gets the ship-manifest schema section below.

BLOCKED (not this WO's scope, escalated rather than invented around):

1. **No `regolith build`/`--release` CLI verb exists anywhere in this
   checkout** (`python/regolith/cli/app.py` has `check`/`fmt`/`debug`/
   `doc`/`ship` only -- grepped for `def build`, none found; `doc`'s
   own docstring references "elsewhere (`check`, `build`)" as if it
   existed, which is stale). Only the Python API
   (`orchestrator.orchestrate.staged_build`/`release_gate`) exists.
   `ship()` calls that API directly (legitimate: same layer
   `orchestrate.py` itself sits at, not a `Backend` implementation),
   so `ship` still enforces the gate correctly -- but the acceptance
   criterion's literal `regolith build --release && regolith ship` as
   TWO CHAINED CLI COMMANDS cannot be demonstrated because the first
   command does not exist. Reopen criterion MET: **WO-43**
   (cycle 26, D136) adds `regolith build [--release]`; re-dispatch
   this WO's close-out after WO-43 lands.
2. **`RealizedLayout`'s WO-42 `put` seam is not landed** (WO-42's own
   Status line, AD-25 sec. "IMPLEMENTED WHERE LANDED": "NOT YET
   landed: `RealizedLayout`'s `put` emission seam, blocked on a real
   KiCad-backed `regolith.realizer.elec` layout producer"). No real
   `.cupr` board build's `StagedBuildReport.realized_inputs` will
   ever carry a `layout.realized` entry until that lands, so
   `ElecBackend` can only be exercised against a hand-built
   `RealizedLayout` (as WO-24's own acceptance tests already do for
   the same reason) -- never end-to-end from a real board today.
3. **UPDATE (cycle 26): LIFTED -- kicad-cli 10.0.4 is on PATH and
   pcbnew imports under /usr/bin/python3 (not the uv venv); the
   real-run leg is dispatchable via the WO-24 remainder (wrapper
   under the system interpreter). Original cut text:**
   `kicad-cli`/`pcbnew` remain absent from this sandbox (WO-24/35's
   standing, re-verified cut: `real_kicad_available()` returns
   `False`). `ElecBackend`'s real-export path has never run against a
   real KiCad install; it is proven with a fake subprocess runner.

None of these three is a gap in `regolith.backends`/`regolith ship`
itself -- each is a named upstream wall with its own reopen criterion
in its owning WO. The acceptance criterion's corpus demo (sheet
bracket + Kestrel board -> uploadable package) becomes checkable the
moment (1) lands (a `build` CLI verb) and either (2) or (3) does (a
real layout IR or a real KiCad install to prove the elec half
end-to-end); the mech half is ALREADY checkable end-to-end today
modulo (1) alone, since `MechBackend` + real `realize_feature_program`
output both work in this sandbox.

Explicit cut carried over from the WO body: drawings (2D) stay
TRACKED CUT for v1, unchanged.
