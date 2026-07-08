# WO-04: Value-source grammar types

Status: done (the `free` source's eager-DFM resolution default is now
exercised end-to-end by INV-26: the shipped `sheet_bend` DFM pack resolves
a `free` bend radius to the manufacturable minimum through the discharge
facade, and a demanded window tighter than that resolved value surfaces
`violated` + release-gated -- a wrong default is loud, not a silent pass.
See `tests/invariants/test_inv_26_defaults_test_compliance_meta_invariant.py`.)
Depends: WO-02, WO-03
Language: Rust (`regolith-qty`) -- see `../00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: regolith/03-value-sources.md (all)

## Goal

The five-source grammar as a Rust enum (serde round-trip; schemars
export feeds the generated pydantic models via WO-18) every numeric
slot in every IR will carry.

## Deliverables

- `ValueSource` union: `Literal(qty | comparator | Window)` (one-sided
  comparators `>= x` / `<= x`; two-sided `within [lo, hi]`),
  `InDomain(interval | discrete_set, direction: minimize|maximize|None)`,
  `Free`, `Derived(sf: float | None)`, `Allocated(policy: str | None)`.
  Directions take NO argument (SOPEN-4).
- `Resolution` record: resolved value + `Cause` union (`dfm(rule)`,
  `drc(rule)`, `obligation(id)`, `budget(name)`, `topology(boundary)`,
  `planner(tag)`) -- the lockfile row shape (regolith/03 sec. 2).
- Monomorphization: `InDomain` over a discrete set (ints, enums --
  incl. `variant` axes, which are externally-chosen: flag
  `external=True`, all points must verify) expands to instantiation
  points with per-point identity for caching.
- Structure-boundary hook: a `DomainConstraint` callback slot so later
  passes can intersect domains with structure-preserving regions
  (regolith/03 sec. 4); implement the data shape only.

## Acceptance

- Round-trip serialization of every variant.
- Monomorphization tests incl. an enum/variant axis.
- A `Resolution` renders as the documented lockfile line format.
