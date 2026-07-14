# WO-127 -- The logic-analyzer jig exemplar: custom test hardware as a lithos design (D237.4, AD-38, charter 40 sec. 4)

Status: done
Language: corpus authoring (cuprite + firmware source) + Python
  (demo only); no toolchain changes -- gaps you hit are ledgered
  findings, never in-scope fixes.
Spec: charter 40 sec. 4 (NORMATIVE); D237; WO-125 (tap header
  record -- the ONE pinout home you mate, never copy); WO-126
  (harness pack the demo pairs with); D222 (demo/proof-pack
  idiom); D224 (every component/record cited or honestly
  refused).
Depends: WO-125 + WO-126 merged.

## Goal

A working logic-analyzer-class tap jig, authored in cuprite,
shipped through the full pipeline like any fleet project --
proving by dogfood that (a) the languages can express the test
hardware, and (b) a fleet target's debug package plus the jig's
package together contain everything needed to physically test the
target.

## Deliverables

1. `examples/flagships/la_jig8/`: 8-channel tap jig -- input
   protection + level shifting per channel, MCU from the existing
   std registry (st.mcu), USB-serial streaming out; the tap-header
   MATE references the WO-125 std.elec pinout record (single
   home). Claims: input voltage tolerance windows, sample-rate
   bound, channel count, rail integrity -- authored for discharge
   per guide 27 (real models over declared inputs where the model
   surface exists; honest named deferrals otherwise, D220 closed
   classes).
2. Firmware application source (the WO-37/WO-102 surface):
   capture/stream loop, channel config over serial; ships through
   the firmware backend.
3. Full ship: census + calc book + COMPLETE gerbers (WO-124 set,
   silkscreen with channel labels) + firmware product + harness
   family of its own (the jig is also a debuggable design --
   `--profile debug` on the jig itself must work; recursion ends
   there, no jig-for-the-jig).
4. demo17 "physical bring-up pack" (D222 idiom, `make demos`
   family): build printer_k1 (or mainboard_mx -- pick the target
   whose tap set exercises more kinds) with `--profile debug`,
   ship the jig, and emit one cross-referenced PROOF.md: target
   tap map channels -> jig channels -> expected signals ->
   calc-sheet hashes. The pack is the paper proof of charter 40's
   "easy to physically test" promise.
5. Fleet enrollment: la_jig8 joins the census/golden/health fleet
   like every example (15 -> 16 projects); README rows.

## Acceptance

- la_jig8 ships release-clean (gate green, zero violated, waivers
  in closed classes only) AND debug-clean; census enrolled;
  health fleet leg green at 16 projects.
- Every component/record cited per D224 (conservative catalog
  values fine; unverifiable parts honestly refused like the Ulka
  precedent).
- demo17 live in `make demos` with hashed manifest + PROOF.md.
- `make check` + `make health` green.

## Escalation

Language/model gaps the jig authoring hits (e.g. a front-end
construct cuprite cannot express, a missing analog model) are
EXACTLY the findings this exemplar exists to surface: ledger each
with a placeholder F-number and author around it honestly. Do not
extend the toolchain in this WO.
