# WO-11: Profile walks -- grammar + static ledger

Status: in-progress (ledger half done; profile-walk grammar is heuristic pending WO-05 full statement grammar)
Depends: WO-05
Language: Rust (`rockhead-syntax` grammar half + `rockhead-sem` ledger half) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: mech/02 sec. 5; mech/07 OPEN-5 closed (cycle 8, D65): the
constraint vocabulary is the closed SolveSpace-equivalent set; solver
interaction is implementation-owned and OUT of scope here

## Goal

Parse walk bodies (the WO-05 opaque islands) and run the static
checks: branch-pin completeness and the sketch DOF ledger. NO
constraint solving.

## Deliverables

- Walk AST: `from <datum>`, `line`/`arc` with direction words,
  `tangent`/`perpendicular` joins, `bulge=left|right`,
  `close [via axis]`, `hole <name>:` (one nesting level), `regions:`
  expressions, `constraints:` items, `exports:`.
- Branch-pin completeness check: every discrete solver branch pinned,
  else E-diagnostic listing the unpinned joints.
- Sketch DOF ledger: entities' freedoms minus constraints; remainder
  must be zero or declared free variables (value sources).
- Export model: placeless datums; feature-first re-anchoring hook
  (mech/02 sec. 5 export-anchoring rule) -- the profile value exposes
  exports only through an instantiation context object.
- Direction words validate as uniqueness hints (statically: the check
  that a hint disambiguates is deferred to solve time; record the
  hint).

## Acceptance

- All example profiles parse and their ledgers close (or close via
  declared free variables).
- A walk with an unpinned arc branch and a profile with a leftover DOF
  produce the documented diagnostics.
- Referencing an export through the profile value (not a feature)
  errors with the anchoring rule's message.
