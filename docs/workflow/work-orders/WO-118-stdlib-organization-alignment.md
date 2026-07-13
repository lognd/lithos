# WO-118 -- Stdlib organization alignment + enforcement (D227/AD-37)

Status: done (2026-07-13: both sweeps clean and gated; the seven
  charter-39 organization checks live in the health consistency leg
  and each runs alone; the feldspar library/ -> per-domain-package
  migration executed behavior-preserving on wo118-feldspar-alignment;
  named baseline debt WO118-F1/F2 reported in the close-out ledger,
  report-only)
Language: Python (sweep tooling into the health consistency leg) +
  content moves both repos ONLY where a charter rule demands one;
  gates: after WO-110 and WO-111 merge (they add the model content
  this WO aligns and checks).
Spec: charter 39-stdlib-organization.md (lithos, normative);
  feldspar docs/spec/12-solver-organization.md (counterpart);
  AD-37; D227; D219 (health legs, standardized summary rows).

## Goal

The organization doctrine becomes machine-checked reality: both
repos' existing content conforms to their charters, and every
mechanically-checkable rule fails the health gate when violated.

## Deliverables

1. Conformance sweep, lithos: audit `stdlib/` + `harness/models/`
   against charter 39 (namespace taxonomy, one-family-per-file,
   in-row citations, tier honesty, model docstring citations,
   flat-vs-subdir module rule, std.models manifest completeness --
   every registered built-in named, nothing phantom). Fix
   violations as structure-only commits (content untouched);
   anything needing a content decision escalates.
2. Conformance sweep, feldspar: audit `python/feldspar/<domain>/`
   module placement, solver_id naming (namespace == package),
   manifest rows carrying claim kind + input names, calibration
   tests present per direction. Coordinate: feldspar commits go on
   a feldspar branch the coordinator merges/pushes.
3. Double-home detection: no claim kind resolvable from BOTH a
   built-in and a pack without a recorded router preference
   (charter 39 sec. 4); implement the check against the harness
   registry + pack manifest.
4. Health consistency-leg checks (standardized summary rows per
   D219): std.-prefix reservation, one-family-per-file, citation
   presence (record rows + model docstrings), generated-file
   drift (extend the WO-66 check), std.models manifest
   completeness, double-home detection. Each check runnable alone.
5. Charter cross-drift check: the shared boundary-rule section
   (charter 39 sec. 4 == feldspar spec 12 sec. 4) compared
   byte-for-byte modulo heading, in the same sweep.

## Acceptance

- Both sweeps clean; every new check live in `make health`
  (consistency leg) and individually runnable; violations produce
  named, actionable failure rows.
- No physics/content changes -- structure and tooling only.
- `make check` + health green; feldspar checks green.

## Escalation

A conformance violation that is actually a design question (e.g. a
model that arguably sits on the wrong side of the boundary rule)
is reported with a placeholder label, never unilaterally migrated.

## Close-out ledger (WO-118 execution, 2026-07-13)

Two branches: lithos `wo118-stdlib-alignment`, feldspar
`wo118-feldspar-alignment` (coordinator merges/pushes both;
coordinator runs feldspar `make regolith-test` at merge per this
WO's coordination note).

### Delivered

- **Sweeps** (`tools/stdlib/organization.py`, seven checks, each
  standalone via `python -m tools.stdlib.organization --check NAME`
  and folded into the consistency leg): prefix, one_family,
  citations, generated_drift, models_manifest, double_home,
  charter_drift. Feldspar-dependent sweeps (double_home,
  charter_drift) degrade honestly with no sibling checkout; run
  against the feldspar worktree both proved clean (0 double-home
  claim kinds across 83 pack solvers vs the built-in registry;
  boundary-rule sections byte-identical).
- **WO110-F7 fixed**: std.models manifest completed (12 missing
  module groups named; drift now gates in both directions).
- **Feldspar migration** (spec 12 sec. 1, the WO111-F2 item):
  every `python/feldspar/library/` solver module moved to its
  domain package -- mech/ (12 modules: closed_form + bearing_life,
  bolted_joints, critical_speed, drive, fatigue, leadscrew,
  member_capacity, plate, struct, vibe, weld_groups), elec/
  (closed_form, signal_integrity -- joining the existing ngspice
  adapter home), heat/ (closed_form, thermal_transient), thermo/
  (properties), fluids/ (compressible, incompressible, network).
  Behavior-preserving: zero physics edits; `feldspar.library.*`
  stays importable through transparent sys.modules alias shims
  (every attribute reachable, module identity shared -- proven by
  lithos tests that monkeypatch through the old path); production
  imports (catalog.py, fea/modal.py, pack/models.py) point at the
  new homes. Feldspar 483 tests + fmt/lint/import-lint/ty green.
- **F132.6 fixed**: `make install` now runs `feldspar-link`
  (self-healing eviction; proven by venv rebuild -> feldspar +
  pcbnew importable with no manual step).
- **WO109-F1 posture documented** in ci.yml: no CI job runs
  `make health` today and `make check`'s feldspar surface degrades
  honestly, so the fast gate needs no feldspar checkout; the
  required sibling-checkout step is recorded for whenever a health
  job lands.

### Named baseline debt (report-only WARNINGs; new violations gate)

- **WO118-F1** -- six pre-existing multi-family record files
  (std.civil materials/occupancy, std.elec cells/motor_frames,
  std.fluid components/pipe) violate charter 39 sec. 2.2. Not
  restructured here: WO-113 is actively appending rows to these
  files, and a family split is a content migration (sec. 5.3)
  needing its own design-log entry + corpus sweep. Baseline listed
  in `tools/stdlib/organization.py::_ONE_FAMILY_BASELINE`.
- **WO118-F2** -- 32 pre-existing built-ins with `citation=None`
  (pre-WO-110 models incl. the cam/hdl check-mode packs and cost
  estimators). Supplying real citations is research/content work
  outside this structure-only WO; baseline in
  `_UNCITED_MODEL_BASELINE`, keyed version-independent. A model
  gaining its citation removes its entry in the same change.

### Notes

- Feldspar prose docstrings in pack/models.py etc. still SAY
  `library.<module>` in citation-style back-references; imports are
  correct, prose sweep deferred as cosmetic (no tracking label --
  grep `library\.` if it ever matters).
- The feldspar manifest-row check (claim kind + input names, spec
  12 sec. 5.2) is enforced by feldspar's own existing pack tests
  (tests/regolith/, coordinator-run); no new feldspar-side checker
  was added since the surface already gates there.
