# Charter 40 -- Debug instrumentation and hardware bring-up (AD-38)

Decided cycle 36 (D237, owner directive 2026-07-15). Machinery:
WO-125 (debug profile + taps), WO-126 (bring-up harness pack),
WO-127 (logic-analyzer jig exemplar). This charter wins over the
WO bodies it governs; their acceptance criteria stand.

Motivation: cycle 35 made the fleet's claims discharge through
real models with an audit trail (D220/D221). The physical half of
that promise -- "after something is built, it is easy to TEST it"
-- has no machinery: no debug variant of the emitted artifacts, no
tap points, no bring-up procedure, no harness. This charter defines
that machinery.

## 1. The debug profile (D237.1)

`regolith build --profile debug` and `regolith ship --profile
debug` (default profile: `release`, today's behavior, byte-for-byte
-- CI proves the default artifact set is unchanged by this
charter's landing).

The debug profile AUGMENTS emission; it never changes design
source, semantics, obligations, claims, or verdicts. Verdict math
is untouchable (D206/D220.1) -- a debug build discharges exactly
what a release build discharges. Augmentations by family:

- boards: a tap header (the std tap-header pattern, sec. 4) placed
  on the layout request, plus a labeled test point per tap;
  silkscreen labels each tap with its channel number.
- firmware: a generated `debug_taps.h`/trace hook table mapping
  tap channels to the signals/variables the taps name; hooks
  compile to nothing in release.
- HDL: a generated tap module routing tapped internal signals to
  declared debug pins (honest named absence when the design has no
  spare pins -- never silently drop a tap).
- every family: the manifest and package index record the profile;
  a debug package is never mistakable for a release package (the
  release gate refuses to accept a debug package as ship evidence).

Determinism (AD-6/INV-10) holds PER PROFILE: two debug builds of
the same source are byte-identical.

## 2. Tap model (D237.2)

A tap is (channel, kind, target-path, why). Two sources, one
merged, deduplicated, deterministically ordered tap set:

1. DERIVED: every net/signal named by a claim in the design is a
   tap candidate (the same routing truth the census reads). The
   deriver ranks by claim family (power rails, clocks, buses,
   then the rest) and takes the first N (header capacity), the
   remainder recorded as named `unallocated` rows.
2. EXPLICIT: the ship spec block's `"debug"` entry lists taps by
   net path (the WO-102 spec-block idiom). Explicit taps win
   channels before derived ones; an explicit tap naming a
   nonexistent net is a diagnostic, never a silent skip.

No grammar change. Grammar-level `tap` statements are deferred;
reopen criterion: a real design produces a tap need that cannot be
named by net path from the spec block.

## 3. The bring-up harness pack (D237.3)

A new artifact family `harness/` in the dist/ package (registered
through the AD-36 registry seam like every family):

- `tap_map.json` -- canonical, hashed: channel -> tap kind ->
  target path -> connector pin -> expected-signal ref.
- `bringup.md` -- the ordered bring-up procedure (the WO-96
  instructions idiom): power-on order, per-tap what-to-probe /
  what-you-should-see, with claim/calc-sheet references.
- `expected_signals.json` -- per tap: quantity, expected value or
  window, units, and the PROVENANCE ref (calc sheet hash, claim
  id, or record ref). D224 governs: an expectation with no
  discharged claim / declared record behind it is emitted as a
  named absence (`no_verified_expectation`, with reason), NEVER a
  fabricated number.
- capture configs for the analyzer (sigrok-compatible command
  files; `sigrok-cli` joins the toolenv catalog and `regolith
  doctor` reports it; absence degrades to the honest
  config-only tier).

INV-32 (tap agreement): every `tap_map.json` row corresponds to a
tap actually present in the emitted debug artifacts, and every
emitted tap appears in the map -- enforced by a ship-path check;
proof argument lands in `13-invariants.md` with WO-125.

## 4. The harness hardware is a lithos design (D237.4)

The tap HEADER pinout (mechanical connector, channel ordering,
ground/keying) is ONE published record (std.elec pattern), the
single home both sides reference (AD-37 spirit): the debug profile
places it; the jig mates it.

The exemplar jig (WO-127) is a cuprite design in `examples/`:
logic-analyzer-class front end (input protection, level shifting),
MCU from the existing registry, streaming firmware -- shipped
through the full pipeline (census, calc book, complete gerbers,
firmware) like any fleet project. Dogfooding is the acceptance
test: the jig's own dist/ package plus a fleet target's debug
package together contain everything needed to physically test the
target.

## 5. Honesty rules

- A tap that cannot be placed (no room, no spare pin, unrouted
  net) is a NAMED absence with a reason -- the tap map never
  overstates the hardware.
- Expected signals carry provenance or are named absences (D224).
- The debug profile never upgrades a verdict, waives an
  obligation, or silences a diagnostic.

## 5a. Machinery cross-references (WO-125 landing)

Where each piece above lives, as landed:

- Profile flag: `--emit-profile {release,debug}` on BOTH `build` and
  `ship` (coordinator ruling at the WO-125 continuation dispatch;
  `--profile` stays the WO-54 COST profile everywhere).
- Header record (sec. 4): `stdlib/std.elec/records/dft.toml`,
  ``class = "tap_header"`` (`tap_header_2x08_254`) -- the ONE home.
- Tap model/deriver/sources + INV-32 check:
  `python/regolith/backends/debug_taps.py`; placement seam:
  `python/regolith/realizer/elec/debug_placement.py`.
- Emitted paths: `harness/tap_map.json` (sec. 3's family; WO-126
  adds its siblings), `boards/tap_placements.json` (placement + label
  DATA; silkscreen rendering is WO-124's seam, a named cross-WO
  handoff), `firmware/<subject>/generated/debug_taps.h`,
  `hdl/<subject>/src/debug_taps.v` (or the named
  `debug_taps_absent.json`).
- Explicit taps + declared HDL pins: the ship spec's `"debug"` block
  (`taps`, `hdl_debug_pins`) -- see
  `examples/flagships/mainboard_mx/ship.spec.json` and
  `examples/flagships/riscv_hart_rv1/ship.spec.json`.
- INV-32's entry + proof argument: `docs/spec/regolith/13-invariants.md`.

## 6. Deferred (named, with reopen criteria)

- Grammar-level `tap` statements (sec. 2 criterion).
- Live capture ingestion (comparing a real analyzer capture
  against `expected_signals.json` in-toolchain); reopen: the
  exemplar jig exists and an owner-run physical capture is on the
  table. The FORMAT lands now (sec. 3) so captures are checkable
  by hand from day one.
- Boundary-scan/JTAG chains, protocol decoders beyond the
  analyzer's native set.

## 7. Machinery cross-references (WO-126 landing)

- The `harness/` family's siblings (`expected_signals.json`,
  `bringup.md`, per-kind sigrok-cli capture configs) and the
  provenance-resolution ship-path check:
  `python/regolith/backends/harness_pack.py`, wired into
  `python/regolith/backends/ship.py` beside the sec. 5a WO-125
  landing.
- `sigrok-cli` toolenv catalog row + `regolith doctor`:
  `python/regolith/toolenv.py`.
- User-facing guide: `docs/guide/30-hardware-bring-up.md`.
