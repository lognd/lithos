# WO-106 -- The repo health gate: make health (fleet + demos + consistency)

Status: open (EXPANDED by D219, 2026-07-13: from fleet-gate-only
  to the one repo health gate)
Language: Python (tests + scripts/ + Makefile)
Spec: D219 (the health-gate ruling -- read first); charter 38
  sec. 4 (the fleet acceptance shape); D210 (fleet definition);
  D218.1/WO-108 (demo proof manifests); AD-11 (golden corpus
  tradeoff -- fleet census joins it).

## Goal

ONE command (`make health`) proves the owner's bar and keeps it
proven, composing four legs cheapest-first, each independently
runnable, each reporting one standardized typed summary row (leg,
ok, counts, evidence pointer): `check` (existing code gates),
`fleet` (every D210 project --release green + verify-clean
package, census golden), `demos` (every live WO-108 proof manifest
matches), `consistency` (D/F-number uniqueness, WO-Status-vs-TODO
agreement, extension single-sourcing, golden byte-drift, memo/
waiver ledger integrity incl. every `by doc(...)` resolving and
zero stale waivers, stale-worktree detection). Refactor existing
scattered checks INTO the legs rather than duplicating them.

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
