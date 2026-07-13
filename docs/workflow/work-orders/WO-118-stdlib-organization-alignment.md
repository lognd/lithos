# WO-118 -- Stdlib organization alignment + enforcement (D227/AD-37)

Status: open
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
