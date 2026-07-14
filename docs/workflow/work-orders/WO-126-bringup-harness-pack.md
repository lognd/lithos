# WO-126 -- The bring-up harness pack (D237.3, AD-38, charter 40 sec. 3)

Status: done
Language: Python (new backends/harness.py family through the AD-36
  registry seam; toolenv addition); no schema bump (D225/D239).
Spec: charter 40 sec. 3 (NORMATIVE) + sec. 5 (honesty rules);
  D237; D224 (expectation provenance -- the load-bearing law
  here); WO-96 (instructions idiom bringup.md follows); WO-114
  (calc book -- the expectation source); WO-125 (tap map + INV-32,
  the gate for this WO); guide 18-external-tools.md (toolenv).
Depends: WO-125 merged.

## Goal

A debug-profile ship emits `dist/<proj>/harness/` -- everything a
technician with the target board, the jig, and a logic analyzer
needs to physically verify the design: tap map, ordered bring-up
procedure, analyzer capture configs, and an expected-signal
manifest where EVERY expectation traces to a discharged claim,
calc sheet, or declared record, or is a named absence.

## Deliverables

1. `harness/` registered artifact family (registry seam, package
   index rows, canonical digests) emitted for debug-profile ships
   of any project with a tap map.
2. `tap_map.json` (canonical, hashed): the WO-125 map extended
   with connector pin + expected-signal refs -- one file, one
   truth (WO-125's emission moves INTO this family; no second
   copy).
3. `expected_signals.json`: per tap -- quantity, expected value or
   window, units, provenance ref (calc-sheet hash | claim id |
   record ref); `no_verified_expectation` named absences with
   reasons otherwise (D224: fabricating an expectation is the
   one unforgivable failure mode of this WO).
4. `bringup.md` (WO-96 instructions idiom): power-on order,
   per-channel probe procedure ("probe TP3 / channel 2: expect
   3.3 V rail, calc sheet <hash>"), safety-relevant claims first,
   claim/calc cross-references throughout, honest gaps stated.
5. Analyzer capture configs: sigrok-compatible command/config
   files per capture group (rails, clocks, buses); `sigrok-cli`
   joins the toolenv catalog + `regolith doctor` row; absence
   degrades to the honest config-only tier (files still emitted,
   doctor says the tool is missing).
6. Ship-path checks: harness family present iff debug profile +
   taps; every expected-signal provenance ref RESOLVES inside the
   package (audit-index spirit, zero unexplained rows).
7. Docs: guide `30-hardware-bring-up.md` (user-facing: the debug
   profile, the harness pack, how to run a capture against it);
   charter 40 cross-refs.

## Acceptance

- mainboard_mx + printer_k1 debug ships emit complete harness/
  families, golden-enrolled, byte-stable; every expectation row
  provenance-resolves (test asserts zero unexplained).
- Expectations agree with the calc book where both speak (test
  cross-checks values against calc sheets).
- Census/verdicts untouched (test asserts equality with release).
- `make check` green; `regolith doctor` reports sigrok-cli.

## Escalation

If a tap's quantity is claim-covered but the calc book carries no
resolved numeric for it (WO117-F2 territory), emit the claim-ref
expectation WITHOUT a number plus a named note -- and ledger the
count as a finding for the WO117-F2 seed item. Never invent the
number.
