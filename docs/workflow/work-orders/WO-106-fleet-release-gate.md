# WO-106 -- The fleet release gate (make fleet + census goldens)

Status: open
Language: Python (tests + Makefile)
Spec: charter 38 sec. 4 (the acceptance shape -- this WO builds
  it); D210 (fleet definition); AD-11 (golden corpus tradeoff --
  fleet census joins it).

## Goal

One command proves the owner's bar and keeps it proven: every
fleet project builds `--release` green and ships a complete,
verifiable, deterministic package; the per-project proven/accepted
census is a golden so acceptance creep is a reviewed diff.

## Deliverables

1. `make fleet` + `tests/fleet/test_release_fleet.py`:
   discovers D210 fleet projects (by magnetite.toml presence,
   minus explicit exemptions), runs `build --release` + `ship`
   per project, asserts rc/release_ok/manifest-schema-valid/
   `ship --verify` clean/index present/every family
   present-or-named-absent.
2. Determinism leg: ship twice for one mech-heavy + one
   elec-heavy project; byte-compare every deterministic artifact
   (GLB, SVG, DXF, PDF, fake-tier kicad_pcb, index, ledgers).
3. Tracks leg: every `examples/tracks/**` non-advice file builds
   `--release` green; negative corpus still fails exactly as
   encoded (reuse the existing negative-corpus runner).
4. Census golden: `tests/golden/data/fleet_census.json` --
   per-project {obligations, discharged, accepted_deviation,
   violated, below_floor, families_shipped}; regeneration is the
   ordinary golden flow with the cycle-33 diff-review rule.
5. Wiring: `make check` gains a cheap fleet-smoke (one project);
   full `make fleet` is its own target (runtime documented);
   CI note in 10-test-infra-and-ci.md.
6. Docs: guide "shipping your project" chapter gains the fleet
   example; TODO/START-HERE one-liner update.

## Acceptance criteria

- `make fleet` green on final cycle-34 master, twice in a row,
  from a clean checkout.
- Census golden enrolled; a synthetic new bare waiver in a
  fixture project flips the census (proven by test) -- acceptance
  creep cannot land silently.
- `make check` green.
