# WO-139 -- friction-factor model + pipe-roughness consumption (D258.1/D258.3/F158)

Status: open (Depends: WO-138 -- needs the roughness record)
Language: Python (lithos harness built-in, `std.models` manifest
  entry) + a byte-check test against feldspar.
Spec: F158 (the friction-factor gap: `thermosiphon.fluo:76` declares
  `friction_factor=0.03` inline, "Moody-chart estimate folded
  upstream" -- nothing in the toolchain computes it); D258 ruling 1
  (representation); D258 ruling 3 (TRANSITION HONESTY: the
  laminar-turbulent transition, 2300 < Re < 4000, is declared
  INDETERMINATE via the D97 regime-tag channel, never interpolated
  through; the Haaland-vs-Colebrook deviation is folded into the
  model's stated `eps` rather than hidden); AD-37 ruling 1
  (`00-architecture.md:1095-1101`: closed forms live as harness
  built-ins named by `std.models`; numerics live in feldspar; the
  same closed form may live on both sides when a lithos claim needs
  pack-free discharge, WITH a byte-for-byte cross-check test -- the
  WO-94 precedent, `python/regolith/harness/models/
  fluid_pressure_drop.py:16-23`); AD-22 (declared-input override
  channel: an inline declaration always wins over a derived one);
  `docs/spec/fluorite/03-lowering.md` sec. 3 (the D97 regime-tag
  channel this model reports through).

## Goal

Friction factor becomes a real, cited, derivable model instead of a
hand-typed magic number -- while every existing corpus fixture that
declares `friction_factor=` inline keeps working unchanged, because
inline declaration is the AD-22 override, not a fallback this WO
removes.

## Deliverables

1. `fluids.friction_factor` harness built-in
   (`python/regolith/harness/models/friction_factor.py`):
   - Laminar branch: f = 64/Re (exact, Re < 2300; White sec. 6.4).
   - Turbulent branch: Haaland 1983 explicit form ("Simple and
     Explicit Formulas for the Friction Factor in Turbulent Pipe
     Flow", J. Fluids Eng. 105(1):89-90) -- the primary explicit
     correlation, chosen because feldspar already uses it as its
     Colebrook Newton-iteration seed
     (`feldspar:crates/feldspar-library/src/fluids/
     incompressible.rs:49-89`), giving the byte-check test a natural
     partner on both sides.
   - Transition branch (2300 <= Re <= 4000): reports INDETERMINATE
     via the D97 regime-tag channel -- no value is returned, no
     interpolation is attempted.
   - The model's stated `eps` (uncertainty band) folds in the
     documented Haaland-vs-Colebrook deviation (~1.5% max on f over
     the Moody range) -- an honest way to ship an explicit
     approximation of an implicit law, not a claim of exactness.
2. `std.models` manifest registration
   (`stdlib/std.models/magnetite.toml`) naming `fluids.friction_factor`
   beside the existing fluid/thermal entries.
3. Widen the `fluids.dp` input chain (`fluid_pressure_drop.py`) so
   the friction factor can resolve from (roughness record from
   WO-138, pipe diameter, Reynolds number) via this new model,
   INSTEAD OF only accepting an inline declaration. The inline
   declaration path (AD-22 override) is UNCHANGED and stays the
   precedence winner when present -- this WO adds a resolution path,
   it does not remove the existing one.
4. Byte-check test: the lithos Haaland/laminar branches produce
   numerically identical results (within a stated float tolerance)
   to feldspar's `incompressible.rs` Haaland-seeded and laminar
   paths, over a shared fixture of (Re, eps/D) pairs -- the WO-94
   precedent for `fluid_pressure_drop.py`.
5. A new corpus fixture (fluorite example, small_office-adjacent or
   a standalone tracks/fluorite fixture) that discharges `fluids.dp`
   with a DERIVED friction factor (not inline-declared), so the calc
   sheet cites Haaland 1983 and the roughness record's hash.

## Out of scope

- Minor losses / K-factors (WO-140).
- The Moody chart figure itself (WO-143) -- this WO only produces
  the numbers the figure will plot.
- Churchill 1977 all-regime form and Swamee-Jain 1976 -- named
  alternates in the recon, not adopted (redundant with Haaland; the
  two-branch honest-transition form is cleaner under D97).

## Acceptance

- `thermosiphon.fluo:76`'s existing inline `friction_factor=0.03`
  declaration still discharges unchanged: `regolith build
  examples/flagships/espresso_machine` stays green with no
  regression in that claim's verdict.
- A new fixture discharges `fluids.dp` with a DERIVED f; its calc
  sheet cites "Haaland 1983" and the roughness record's content
  hash -- checkable via `regolith ship --explain` on that fixture and
  grepping the calc-sheet output for both strings.
- The byte-check test (deliverable 4) passes:
  `uv run pytest <new test path> -q`.
- A Reynolds number in (2300, 4000) exclusive produces the regime
  tag INDETERMINATE, not a numeric f -- a unit test asserts this
  directly and asserts no interpolated value is ever returned in
  that band.
- `make check` green.

## Escalation

If the D97 regime-tag channel cannot express "indeterminate, no
value" cleanly for this model's callers, STOP and escalate to
`docs/spec/fluorite/03-lowering.md` sec. 3 rather than inventing a
new deferral shape.
