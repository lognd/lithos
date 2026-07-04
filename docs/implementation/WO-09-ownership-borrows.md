# WO-09: Ownership and borrow checking

Status: done
Depends: WO-07, WO-08
Language: Rust (`rockhead-sem`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/05 sec. 3; substrate/06 sec. 2

## Goal

The anti-toponaming machinery: single ownership, borrows, merge signs,
region conflicts -- on predicted deltas, before any realizer exists.

## Deliverables

- Borrow table per scope: query consumption = immutable borrow to
  stage end; impl role binding = permanent borrow (lifetime = artifact).
- Conflict detection: modified-set x borrowed-set intersection at
  commit; bidirectional E0302 reporting (at the modifier AND at the
  borrower), per the SEAM-1 resolution (mech/03 sec. 2.1).
- Merge analysis: same-sign overlap auto-merges (ownership demanded
  lazily -- only if a later query touches the contested region);
  mixed-sign overlap in one scope = hard error suggesting
  `merge(a before b)` / rescoping.
- Region ownership: placement/route/feature deltas intersecting owned
  exclusion regions = the same conflict machinery.
- `rebind()` re-evaluation and datum borrow-exemption.
- Single-driver as ownership (elec binding): one driving construct per
  net; `arbitrate` = declared join.

## Acceptance

- Scenario tests mirroring the spec's canonical bugs: later feature
  eats a bound face (E0302 both ends); two drivers on one net; a route
  into a keepout; stage boundary transfer with an interface-bound
  entity staying protected.
