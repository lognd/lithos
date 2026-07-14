# WO-125 -- The debug emission profile + signal taps (D237.1/.2, AD-38, charter 40 secs. 1-2)

Status: open
Language: Python (cli build/ship, orchestrator emission path,
  realizer/elec placement seam, backends firmware/hdl); NO wire
  schema change without coordinator adjudication (D239 -- report
  your needs, do not bump).
Spec: charter 40 secs. 1, 2, 5 (NORMATIVE); D237; AD-38; AD-6/
  INV-10 (per-profile determinism); WO-102 (spec-block idiom the
  `"debug"` entry follows); WO-37 (firmware realizer surface);
  charter 41 sec. 3 (silkscreen labeling seam WO-124 lands);
  regolith/13-invariants.md (INV-32 lands here WITH proof
  argument).

## Goal

`regolith build --profile debug` / `ship --profile debug` emits
tap-instrumented artifacts -- board tap header + labeled test
points, firmware trace-hook table, HDL tap module -- from a
deterministic tap set derived from claim-named nets/signals plus
explicit spec-block taps, while the default (release) artifact set
stays byte-identical to today.

## Deliverables

1. Profile plumbing: `--profile {release,debug}` (default release)
   on build/ship; profile recorded in manifest + package index;
   the release gate REFUSES a debug package as ship evidence
   (named diagnostic); a release run's outputs are byte-identical
   to pre-WO output (CI-proven golden equality).
2. Tap model + deriver (`(channel, kind, target_path, why)`):
   derived candidates from claim-named nets/signals (the census
   truth surface), ranked per charter 40 sec. 2 (rails, clocks,
   buses, rest), capacity-limited by the header record with
   `unallocated` named rows; explicit `"debug"` spec-block taps
   win channels first; unknown net path in an explicit tap is a
   diagnostic. Deterministic ordering; unit-tested on fixtures.
3. Tap header pinout RECORD: one std.elec pattern record (channel
   count, ordering, ground/keying, connector) -- the ONE home
   (charter 40 sec. 4) both this WO's placement and WO-127's jig
   reference. Cited/dimensioned like any std record (AD-37).
4. Board augmentation: tap header placed through the layout
   request seam + one labeled test point per tap; silkscreen
   channel labels through WO-124's labeling seam (if WO-124 has
   not merged first, land the data on the placement and ledger the
   label rendering as a named cross-WO handoff).
5. Firmware augmentation: generated `debug_taps.h` / trace-hook
   table mapping channels to the signals the taps name; compiles
   to nothing in release; rides the WO-102 firmware backend
   (named absence when a design has no firmware).
6. HDL augmentation: generated tap module routing tapped internal
   signals to declared debug pins; honest named absence when no
   spare pins (charter 40 sec. 1) -- never silently drop.
7. INV-32 tap agreement check in the ship path (every tap-map row
   exists in emitted artifacts and vice versa; the map is emitted
   here as the machine record even before WO-126's full harness
   family) + proof argument in regolith/13-invariants.md, SAME
   change.
8. Docs: charter 40 cross-refs; guide stub section in
   17-design-testing.md pointing at the coming WO-126 guide.

## Acceptance

- Fleet-wide: `--profile debug` succeeds on every project that
  ships today; verdict/census output IDENTICAL between profiles
  (D206 untouchable -- test asserts census equality).
- Release byte-identity proven by golden equality.
- mainboard_mx + one more elec-bearing project emit: placed tap
  header + test points, firmware tap table (where firmware
  exists), tap map passing INV-32.
- Determinism per profile; `make check` green.

## Escalation

If the tap set genuinely needs a WIRE schema slot (emission-layer
records insufficient), STOP and report -- the coordinator
adjudicates the D239 bundle (taps + WO112-F4 vias). Grammar wants
(a tap unnameable by net path): ledger the evidence against
charter 40 sec. 6's reopen criterion, do not add grammar.
