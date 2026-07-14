# demo17_physical_bringup_pack -- the physical bring-up pack

Charter 40's promise is that after something is built, it is easy
to physically TEST it. This is the paper proof: a fleet target's
DEBUG package and the la_jig8 tap jig's package, cross-referenced,
together contain everything needed to put a probe on the board.

## The seam

Both sides cite ONE published pinout record: `tap_header_2x08_254`
(`stdlib/std.elec/records/dft.toml`). The debug emission profile
PLACES it on the target; the jig MATES it. Neither side restates
the pinout, so neither can drift from the other.

- header: 2x8 2.54mm shrouded box header (Wurth WR-BHD 61201621621 class)
- channels: 8, positions: 16, pitch: 2.54mm
- ordering: channel N on odd pin 2N+1 (1,3,..,15); ground on every even pin (2,4,..,16)
- ground: interleaved return: one ground pin adjacent to every signal pin (ribbon-cable GS pairing)
- keying: shrouded polarizing notch + pin-1 corner marking

The jig's BOM carries that same record key, so the ribbon cable
between them is not a hope -- it is a checked cross-reference.

## Target tap channel -> jig channel -> expected signal

| ch | target net/signal | kind | jig channel (header pin) | quantity | expected | provenance |
|---|---|---|---|---|---|---|
| 0 | `CarrierSi.refclk` | clock | ch0 (pin 1) | impedance | _(no verified expectation)_ | calc_sheet: unit_unresolved (WO117-F2): the claim's declared threshold carries no unit token and no other Python-visible field (evidence, calc sheet, calc input) carries one for this claim shape |
| 1 | `Rail1V1.out` | rail | ch1 (pin 3) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 2 | `Rail1V8.out` | rail | ch2 (pin 5) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 3 | `Rail3V3.out` | rail | ch3 (pin 7) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 4 | `Rail5V.out` | rail | ch4 (pin 9) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 5 | `CarrierSi.usb_dp_dm` | bus | ch5 (pin 11) | impedance | _(no verified expectation)_ | claim: claim status=deferred: not model-backed discharged (calc book carries no resolved numeric for this tap |

**0 channel(s) carry a verified numeric expectation;
6 are HONEST NAMED ABSENCES** (`no_verified_expectation`).

Read that number honestly: today the target's debug package can
tell a technician WHERE to probe and WHY, but for most taps it
cannot yet tell them WHAT THEY SHOULD SEE. D224 governs -- an
expectation with no discharged claim or declared record behind it
is emitted as a named absence, NEVER a fabricated number -- so the
pack refuses to print a value it cannot stand behind. Every
absence still carries its reason and a ref to the evidence it
consulted; most trace to WO117-F2 (`unit_unresolved`: the claim's
threshold carries no unit token) and to the fleet's buck-rail
claims being indeterminate rather than discharged -- which is
F-WO127-5's lowering gap showing up again, one layer out.

This demo FAILS if it ever finds a bare expectation with no
provenance, or an absence with no reason; every calc-sheet ref is
resolved against the target's shipped calc book.

## The jig's own evidence

The jig ships 1 calc sheet(s) of its own --
it is held to the same bar as the thing it tests, not exempted
from it. Its `mcu_junction` claim discharges through the
registered thermal model over declared inputs.

## What this does NOT prove

No physical capture has been taken. Charter 40 sec. 6 defers live
capture ingestion (comparing a real analyzer trace against
`expected_signals.json`); the FORMAT lands now so a capture is
checkable BY HAND from day one. The jig also cannot yet be built
as drawn: it carries no level-shift buffer part, because no such
record class exists in the stdlib (F-WO127-1, ledgered in the
jig's README, not hidden here).

## Re-run

```
uv run python -m demos.demo17_physical_bringup_pack
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `jig/boards/gerbers/board-F_Silkscreen.gto` | 7350 | `sha256:c0fbc3c4daeff5e9351ec73d186472a190ef4e37f2bed57a2d603f504f1e5adb` |
| `jig/calc/calc_book.json` | 8368 | `sha256:505d68b86fa068a83668e3adaa5e10cc47569b2b21d9aca7ea03c6d87845c9f9` |
| `target-debug/boards/tap_placements.json` | 4724 | `sha256:dd8e6a10a6a1a2de2368858f87fd4f305a6e9bbf453d72666c92232accc192ec` |
| `target-debug/harness/bringup.md` | 3047 | `sha256:d733323d87852824947b9719f3162584a3a6c4f0ba2e9f1bb476ca975b64f5e0` |
| `target-debug/harness/expected_signals.json` | 3019 | `sha256:6d91d8b958c85ff5b4670e399e1b29bcd9d89892e85001cbdac0203474acd371` |
| `target-debug/harness/tap_map.json` | 3075 | `sha256:1b79353947fee71b689bdd0d335e2b2632de30b6c63cea29ccab9797ee6920ed` |
