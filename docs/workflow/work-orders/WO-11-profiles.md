# WO-11: Profile walks -- grammar + static ledger

Status: in-progress (grammar half done; ledger half landed: the
heuristic text-scan `parse_walk` is replaced by a structural CST
consumer -- `regolith_syntax::walk::parse_walk` reads the typed
`WalkBody`/`WalkStep` nodes and the sibling `HoleBlock`/`RegionsBlock`/
`ConstraintsBlock`/`ExportsBlock` nodes -- and drives the DOF ledger,
branch-pin completeness, and export-anchoring checks in `regolith-sem`
`profile`. Tests over the real corpus walk bodies + synthetic
balanced/imbalanced/branch-pin/anchoring fixtures pass. RESIDUAL CUT:
exact zero-residual closure of every corpus sketch is the constraint
solver's DOF analysis (hematite/07 OPEN-5, D65, implementation-owned, OUT
of scope); the ledger is the SOUND conservative half -- it never
invents a constraint the source did not write (INV-15 conservation:
participation is syntactic) and catches a DECLARED imbalance. The
INV-15 mechanism is unit-tested in Rust; the cross-boundary Python
INV-15 fixture stays xfail until WO-19 lowering feeds populated walks
end-to-end.)
NOTE (INV-16): the ORIGINAL `test_inv_16` cited "WO-11" as the mechanism
for converter non-instantaneity. That was a mis-attribution -- INV-16 is
the ELEC continuous/discrete converter graph, not the mech profile walk.
Its sound mechanism now lives in `regolith_sem::converter`
(`ConverterGraph` + ZOH delta rule + within-domain acyclicity -> E0105),
wired in `regolith-lower::checks`; end-to-end stays xfail on WO-05 elec
behavioral-body promotion. See the audit triage ledger (git history, deleted D137) and WO-19.
Depends: WO-05
Language: Rust (`regolith-syntax` grammar half + `regolith-sem` ledger half) -- see `../../spec/toolchain/00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: hematite/02 sec. 5; hematite/07 OPEN-5 closed (cycle 8, D65): the
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
  (hematite/02 sec. 5 export-anchoring rule) -- the profile value exposes
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
