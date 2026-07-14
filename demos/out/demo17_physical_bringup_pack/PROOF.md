# demo17_physical_bringup_pack -- the physical bring-up pack

Charter 40's promise is that after something is built, it is easy
to physically TEST it. This is the paper proof: a fleet target's
DEBUG package and the la_jig8 tap jig's package, cross-referenced,
together contain everything needed to put a probe on the board.

## What drove this

- pipeline path: `regolith build --release --spec` + `regolith ship --emit-profile debug` on the TARGET, and the same pair at the release profile on the JIG -- both through the real CLI, no in-process shortcuts.

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
| 0 | `CarrierSi.refclk` | clock | ch0 (pin 1) | impedance | 45 ohm | calc_sheet: `local-blake3:0ca720a7353` |
| 1 | `Rail1V1.out` | rail | ch1 (pin 3) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 2 | `Rail1V8.out` | rail | ch2 (pin 5) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 3 | `Rail3V3.out` | rail | ch3 (pin 7) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 4 | `Rail5V.out` | rail | ch4 (pin 9) | voltage | _(no verified expectation)_ | claim: claim status=indeterminate: not model-backed discharged (calc book carries no resolved numeric for this tap |
| 5 | `CarrierSi.usb_dp_dm` | bus | ch5 (pin 11) | impedance | _(no verified expectation)_ | claim: claim status=deferred: not model-backed discharged (calc book carries no resolved numeric for this tap |

**1 channel(s) carry a verified numeric expectation;
5 are HONEST NAMED ABSENCES** (`no_verified_expectation`).

Read that number honestly: today the target's debug package can
tell a technician WHERE to probe and WHY, but for NOT ONE of these
taps can it yet tell them WHAT THEY SHOULD SEE. D224 governs -- an
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
| `jig/boards/gerbers/board-F_Silkscreen.gto` | 15415 | `sha256:839455c2f860f32952401bc546e9c9ce486fd2278d3b88ba6b77895bfa2eba72` |
| `jig/calc/calc_book.json` | 8431 | `sha256:c7a156cbcf3e21ead5b0827254ec18c5a5421e1a145e01e1d51506fb76bf0c89` |
| `target-debug/boards/tap_placements.json` | 4724 | `sha256:dd8e6a10a6a1a2de2368858f87fd4f305a6e9bbf453d72666c92232accc192ec` |
| `target-debug/harness/bringup.md` | 2769 | `sha256:2e765463696b2da834351923d99a3b7a0d3c233d7b1941980beb541f1cd03fb9` |
| `target-debug/harness/expected_signals.json` | 2747 | `sha256:8f4d526b5215f15b642eb2be1c56367975eb8949e064c8806c0e0650d99dbeab` |
| `target-debug/harness/tap_map.json` | 3075 | `sha256:1b79353947fee71b689bdd0d335e2b2632de30b6c63cea29ccab9797ee6920ed` |
