# WO-03: Intervals, ranges, corners

Status: done
Depends: WO-02
Language: Rust (`rockhead-qty`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/02 sec. 3 (incl. the cycle-1 interval-vs-range rule),
substrate/07 sec. 5 (corner discipline)

## Goal

The two bracket forms as distinct types, plus corner machinery.

## Deliverables

- `Interval[Qty]` -- closed `[a, b]`; constructors for `a +- t`,
  `a +- p%`, `[k1, k2] * x`. Interval arithmetic (add, sub, mul by
  scalar/interval, min/max, containment).
- `Range` -- half-open `[i .. j]` over discrete positions (int index or
  address Qty); open right end (`[1MB ..]` = to extent end). NEVER
  interconvertible with Interval implicitly.
- `Corner` enumeration helpers: given a set of named interval inputs,
  yield corner assignments; `worst_case(check_direction)` selector hook
  (which corner is worst is the *model's* job -- expose the mechanism,
  not a global policy).
- `within [lo, hi]` demanded-window type (`Window`), distinct from
  `Interval` (substrate/03: asserted scatter vs demanded window).

## Acceptance

- Property tests: interval arithmetic monotonicity, containment.
- Type-level tests: Interval/Range/Window are not interchangeable
  (mypy-checked negative cases in `tests/typing/`).
- Serialization round-trips.
