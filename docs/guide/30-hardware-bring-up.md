# Hardware bring-up: the debug profile + the harness pack

STATUS: WORKING (WO-125, WO-126). `regolith build`/`regolith ship`
accept `--emit-profile {release,debug}` (default `release`, today's
behavior, byte-for-byte). A **debug** ship augments the release
artifact set with a tap header on the board, labeled test points, a
firmware trace-hook table, an HDL tap module, and a new `harness/`
artifact family: everything a technician with the physical board, the
jig, and a logic analyzer needs to VERIFY the design by hand.

Source: design-log D237 (charter `docs/spec/toolchain/
40-debug-and-bring-up.md`, AD-38), D224 (expectation provenance).
Machinery: tap deriver + INV-32 check
`python/regolith/backends/debug_taps.py`; board placement
`python/regolith/realizer/elec/debug_placement.py`; the harness pack
`python/regolith/backends/harness_pack.py`; wired into
`python/regolith/backends/ship.py`.

## Why this exists

Cycle 35 made the fleet's claims discharge through real models with an
audit trail (the calc package, guide `24-calc-package.md`). That is a
PAPER proof. Charter 40 closes the physical half: after something is
built, a debug ship tells a technician exactly where to put a probe,
what they should see, and why -- with the same D224 honesty discipline
the calc package uses (an expectation with no discharged claim behind
it is a named absence, never a fabricated number).

## Running a debug build/ship

```
regolith build --release <project> --spec <ship.spec.json> --out <build_dir>
regolith ship <project> --build <build_dir> --spec <ship.spec.json> \
  --out <ship_dir> --emit-profile debug
```

`--emit-profile` is distinct from `--profile` (the WO-54 COST profile).
A release ship (the default) never populates any of this machinery --
the release artifact set is byte-identical whether or not the ship
spec carries a `"debug"` block.

## The tap model (recap, WO-125)

A **tap** is `(channel, kind, target_path, why)`: one physical
net/signal a debug build exposes for probing. Taps derive from two
sources, merged deterministically:

- **derived** -- every net/signal a CLAIM names in the design (the
  same routing truth the census reads), ranked rails < clocks < buses
  < everything else, truncated to the tap header's channel capacity;
- **explicit** -- the ship spec's `"debug"` block (`"taps": [...]`)
  names nets directly and wins channels first.

Overflow candidates are named `unallocated` rows, never silently
dropped. The tap header itself (connector, pinout, keying) is ONE
published stdlib record (`stdlib/std.elec/records/dft.toml`, `class =
"tap_header"`) both the board placement and the WO-127 exemplar jig
reference -- charter 40's "one shared home" rule (AD-37 spirit).

## The `harness/` family (WO-126)

```
dist/<project>/
  harness/
    tap_map.json              channel -> kind -> target -> connector pin
    expected_signals.json     per tap: quantity, expected value, units, provenance
    bringup.md                the ordered probe procedure
    capture_rails.sigrok-cli  (one per tap-kind group with allocated channels)
    capture_clocks.sigrok-cli
    capture_buses.sigrok-cli
```

Present on every DEBUG ship (never on release); absent taps/families
are always a NAMED reason, never silence -- e.g. a project with no
board layout still gets a `harness/` family (`tap_map.json` with zero
capacity and a stated reason, `expected_signals.json` with zero rows,
a `bringup.md` that says so).

### `tap_map.json`

The canonical, hashed map: one row per allocated channel (kind, target
path, connector pin, which artifact families carry it), the published
header record it cites, and named `unallocated`/`family_absences`
rows. `INV-32` (tap-map/artifact agreement) is checked over the
EMITTED bytes before the ship completes -- every map row appears in at
least one artifact (a `REGOLITH-TAP ch=<n> target=<path>` marker) and
every marker is a map row; a mismatch refuses the ship.

### `expected_signals.json` -- the D224 provenance rule

One row per allocated tap:

```json
{
  "channel": 0,
  "target_path": "CarrierSi.refclk",
  "kind": "clock",
  "quantity": "clock presence",
  "expected": "45",
  "units": "",
  "provenance": {"kind": "calc_sheet", "ref": "local-blake3:...", "reason": ""}
}
```

`provenance.kind` is exactly one of:

- `calc_sheet` -- the tap's originating claim DISCHARGED (the calc
  book, guide `24-calc-package.md`, carries a matching sheet); `ref` is
  that sheet's content digest, re-verifiable inside the SAME package;
- `claim` -- the tap traces to a real claim, but it never discharged
  (deferred/violated/indeterminate, or a discharge with no calc sheet)
  -- `expected`/`units` stay EMPTY, `reason` states the claim's status.
  This is the WO117-F2 escalation case: a claim-covered quantity the
  calc book carries no resolved numeric for. NEVER a fabricated
  number;
- `none` -- no obligation traces this tap's target path at all (should
  not happen -- every allocated tap derives from a claim by
  construction; recorded honestly if it ever does).

The ship path RE-CHECKS every `calc_sheet`/`claim` ref against the same
package's own `calc/calc_book.json`/`calc/audit_index.json` bytes
(never trusting the in-memory objects that produced them) -- an
unresolved ref refuses the ship, exactly like INV-32.

### `bringup.md`

The ordered, human-readable procedure (the WO-96 instructions idiom):
power-on order is SAFETY-FIRST -- rails, then clocks, then buses, then
everything else -- one line per tap naming the connector pin, the
target, and either the calc-sheet-backed expectation or the honest "no
verified expectation" callout with its reason. The tap header's own
pinout/keying/ground scheme is stated up front; the unallocated
candidate list (if any) closes the document.

### Capture configs

One `sigrok-cli` command file per tap-kind group that has at least one
allocated channel (`capture_rails.sigrok-cli`, etc.): a ready-to-edit
`sigrok-cli` invocation naming the group's channels. The `--driver`
line is a TEMPLATE (`sigrok-cli --scan` finds the real analyzer) --
never a claimed physical fact. `sigrok-cli` joins the toolenv catalog
(`python/regolith/toolenv.py`) and `regolith doctor` reports it; its
absence degrades honestly -- the capture configs still ship, unusable
until the tool is installed (the config-only tier).

## Honesty rules (charter 40 sec. 5, recap)

- A tap that cannot be placed (no room, no spare pin, unrouted net) is
  a NAMED absence with a reason.
- Expected signals carry provenance or are named absences (D224).
- The debug profile NEVER upgrades a verdict, waives an obligation, or
  silences a diagnostic -- census/verdict output is IDENTICAL between
  profiles (re-verified by the WO-125/WO-126 test suites, over both the
  manifest evidence rollup and `gate_summary.json`).

## The probe on the other end of the cable (WO-127)

The tap header is only half of a bring-up story: something has to MATE
it. That something is `examples/flagships/la_jig8/` -- an 8-channel
logic-analyzer-class tap jig, and it is a lithos design like any other,
shipped through the same pipeline (census, calc book, complete gerbers,
firmware, and its own `harness/` family).

That is the dogfood proof of this charter: the test hardware is not
exempt from the bar it exists to enforce. The jig ships release-clean,
its `--emit-profile debug` works on ITSELF, and it is fleet-enrolled
(the fleet went 15 -> 16 when it landed).

The seam is one record. `stdlib/std.elec/records/dft.toml`'s
`tap_header_2x08_254` is the ONE published pinout; the debug profile
PLACES it on a target, and the jig MATES it. Neither side restates
channel ordering, ground interleave, or keying, so neither can drift.

`demos/demo17_physical_bringup_pack` is the paper proof: it ships
`mainboard_mx` with `--emit-profile debug` AND the jig, then emits a
PROOF.md cross-referencing target tap channel -> jig channel (header
pin) -> expected signal -> provenance. Run it:

```
uv run python -m demos.demo17_physical_bringup_pack
```

Read its verdict honestly. Today that table's `expected` column is
EMPTY for every tap -- six honest `no_verified_expectation` absences,
each carrying its reason. The pack can tell a technician where to probe
and why; it cannot yet tell them what they should see, because the
claims behind those taps are indeterminate rather than discharged. It
refuses to print a number it cannot stand behind (D224), and that
refusal is the feature. Closing that gap is what makes the next tap map
worth carrying to the bench.

## Deferred (named, not landed here)

- Live capture ingestion (comparing a real analyzer capture against
  `expected_signals.json` in-toolchain) -- the FORMAT lands now so
  captures are checkable by hand; reopen criterion: the WO-127
  exemplar jig exists and an owner-run physical capture is on the
  table.
- Grammar-level `tap` statements -- reopen criterion: a real design
  produces a tap need that cannot be named by net path from the ship
  spec's `"debug"` block.
