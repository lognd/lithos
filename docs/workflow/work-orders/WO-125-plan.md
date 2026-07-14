# WO-125 dispatch plan (working checklist, agent-authored)

Read: docs/workflow/README.md dispatch protocol, 00-architecture.md
(AD-1..31, esp AD-4/5/6/17/22/25), WO-125 body, charter 40 secs 1/2/5,
D237/D239 (cycle-36 design log).

## Leaf decomposition

Deliverable 1 (profile plumbing):
- [x] `ShipManifest.profile: Literal["release","debug"]="release"` field
      (manifest.py), threaded through `build_manifest`.
- [x] `ship()` gains `profile: Literal["release","debug"]="release"` kwarg;
      records on manifest.
- [x] CLI: `regolith ship --profile {release,debug}` (no collision --
      `ship` has no existing `--profile`).
- [x] CLI: `regolith build` already owns `--profile` for the WO-54 COST
      profile (different concept, same flag name) -- collision. Resolved
      by naming this WO's build-side flag `--emit-profile` (build's
      emission augmentation is a build-time concept too, per charter 40
      sec 1's `build --profile debug` wording, but the existing flag
      cannot be repurposed without breaking WO-54). Documented here, not
      escalated to coordinator: pure CLI-ergonomics naming call, no
      schema/architecture stakes.
- [x] `release_gate_refuses_debug_evidence()` helper (manifest.py or
      ship.py): a debug-profile manifest fails `verify_manifest`'s
      release-evidence check with a named `BackendError` kind
      (`debug_not_release_evidence`).
- [x] package index (package.py) records profile alongside gate/parity.
- [ ] CUT: full mainboard_mx + one more elec fleet-wide `--profile
      debug` run producing placed tap header + test points (needs
      deliverables 3/4 below).

Deliverable 2 (tap model + deriver) -- full leaf, pure + unit tested:
- [x] `regolith.backends.debug_taps` module: `Tap` (frozen pydantic:
      channel, kind, target_path, why, source: derived|explicit),
      `TapSet` (allocated + named `unallocated`).
- [x] `derive_taps(claims, explicit, capacity)`: rank by claim family
      (rails, clocks, buses, rest), dedup by target_path, explicit wins
      channels first, unknown explicit net path -> diagnostic (Result/
      Err, never silent), deterministic ordering (sorted target_path
      tiebreak), capacity-limited with `unallocated` rows for overflow.
- [x] unit tests on fixtures (tests/backends/test_debug_taps.py).

Deliverable 3 (tap header pinout record): CUT -- needs a new std.elec
pattern record (authoring + citation infra, AD-37 spirit). Escalate as
F-placeholder; too large for this pass without the record authoring
seam already in front of me. Recorded, not silently dropped.

Deliverable 4 (board augmentation): CUT -- depends on 3. Escalate.

Deliverable 5 (firmware augmentation: debug_taps.h): CUT -- depends on
2 being wired into a real per-project build call site (which subject's
claims feed the deriver is a per-project decision I don't have fixture
data for beyond the corpus scan this pass didn't have budget for).
Escalate; deriver itself (deliverable 2) is ready for a follow-up WO to
wire in.

Deliverable 6 (HDL augmentation): CUT -- same dependency as 5. Escalate.

Deliverable 7 (INV-32): CUT -- an invariant with proof argument must
land WITH its real enforcing check (house rule: nothing converts
violated->discharged, and CLAUDE.md forbids a placeholder proof). Since
3/4/5/6 are cut, there is no real tap-map/artifact pair to check yet.
Do NOT touch 13-invariants.md this pass. Escalate.

Deliverable 8 (docs): partial -- charter 40 already exists (this WO's
own spec); add a short cross-ref note in charter 40 pointing at the cut
items + a one-line guide stub. Feasible, low risk.

## Acceptance criteria coverage

- Fleet-wide `--profile debug` succeeds / census identical: PARTIAL --
  covered for the plumbing (manifest/CLI/gate refusal), NOT for real
  tap emission (cut). Census/verdict equality is untouched by this
  pass (no obligation/claim path is touched at all -- pure emission-
  layer addition), so D206 is safe by construction, not by a new test
  asserting fleet-wide census equality across profiles (that test
  needs a real debug emission path to be meaningful; a no-op profile
  flag trivially passes it, which would be a hollow acceptance test --
  cut alongside 4/5/6, escalated rather than faked).
- Release byte-identity: covered by regenerated goldens (manifest.json
  gains a `profile` field; individual artifact FILE bytes unchanged --
  confirmed by diffing golden artifact files other than manifest.json).
- mainboard_mx tap header/test points/firmware table/INV-32: CUT,
  escalated.
- Determinism per profile / `make check` green: covered for the
  landed subset.

## Escalation record (for coordinator, placeholder F-number)

F-WO125-1: WO-125 deliverables 3-7 (tap header pinout record, board/
firmware/HDL augmentation, INV-32) are CUT from this pass -- they form
one dependent chain (pinout record -> placement -> firmware/HDL ->
INV-32) too large for this dispatch's budget beyond the foundational
profile plumbing (deliverable 1) and the pure tap deriver (deliverable
2, fully done + unit tested, ready to be wired in). Recommend a
follow-up WO-125b scoped to exactly that chain, starting from the
landed `regolith.backends.debug_taps.derive_taps`.

---

# WO-125 CONTINUATION plan (second dispatch: deliverables 3-7)

Read (this dispatch): ground rules, 00-architecture.md end-to-end
(AD-36/37/38 load-bearing), WO-125 body, charter 40 (NORMATIVE),
cycle-36 design log (D236..D240), the first dispatch's plan above +
close-out, ship.py/manifest.py/framework.py/elec.py/firmware.py/
hdl.py/package.py, realizer/elec (kicad.py/realized.py), stdlib
record conventions (std.elec/records/dft.toml, si_stackups loader
walk), fleet tooling (tools/health/fleet.py).

## Coordinator ruling (recorded)

The emission-profile flag is `--emit-profile {release,debug}` on BOTH
build and ship; `--profile` stays reserved for the WO-54 COST profile
everywhere. Ship's `--profile` (first dispatch) is renamed; D-number
assigned at integration.

- [ ] rename ship `--profile` -> `--emit-profile` (help text + error
      strings); build already uses `--emit-profile`.

## Leaf decomposition (whole tree before any leaf)

D3 -- tap header pinout record (the ONE home, charter 40 sec. 4):
- [ ] `stdlib/std.elec/records/dft.toml` gains one
      `class = "tap_header"` component record: key
      `tap_header_2x08_254`, 8 channels, 16 positions, 2.54mm pitch,
      signal-on-odd / ground-on-even ordering (channel N -> pin
      2N+1), pin-1 keying, shrouded box-header connector class,
      cited evidence rows (AD-37 posture; same file that already
      homes `test_point`/`debug_header` DFT parts).
- [ ] `TapHeaderRecord` model + `load_tap_header_record()` loader in
      `regolith.backends.debug_taps` (walk mirrors
      `si_stackups.load_si_context`'s records walk; duplicate key =
      loud error; no record = honest `Ok(None)` absence).

D2 extension -- candidate/spec sources for the deriver:
- [ ] `tap_candidates_from_payload(payload)` -- claim-named nets/
      signals from the payload's own obligations (the census truth):
      SI ClaimForm1 nets via `translate.si_sheet_fields` (the ONE SI
      claim-text home), temporal ClaimForm2/3/4/5/6 `signal`
      expressions (`v(x)` -> rail, `i(x)`/other -> signal; net token
      containing `clk`/`clock` -> clock), scope-qualified
      `target_path`, deterministic dedup/order.
- [ ] `explicit_taps_from_debug_spec` / `hdl_debug_pins_from_debug_spec`
      -- the ship spec's `"debug"` block (WO-102 spec-block idiom):
      `{"debug": {"taps": [...], "hdl_debug_pins": {"<subj>": [...]}}}`.
- [ ] explicit-tap resolution: exact `target_path` match, else UNIQUE
      bare-net suffix match, else named diagnostic (unknown or
      ambiguous), unit-tested.

D4 -- board augmentation (placement data through the realizer seam):
- [ ] `regolith/realizer/elec/debug_placement.py`: `derive_tap_placements
      (subject, tap_set, header)` -> `TapPlacementPlan` (header
      `Placement` + one labeled test-point `Placement` per allocated
      tap, wire `Placement` shape REUSED as emission-layer data -- no
      schema change, D239; silkscreen channel-label rows as DATA for
      WO-124's renderer; the deterministic placement rule declared in
      the artifact itself, never presented as verified geometry --
      D224).
- [ ] WO-124 is in flight in parallel and its silkscreen seam is NOT
      on this branch (verified: no silkscreen code under
      python/regolith/) -- land label DATA; ledger the rendering
      handoff as a named cross-WO note (close-out + artifact field).
- [ ] `ElecBackend` serializes `tap_placements.json` for its subject
      when the plan is present (backends serialize, never decide).

D5 -- firmware augmentation:
- [ ] `FirmwareBackend` emits `generated/debug_taps.h` per subject
      when taps are present: trace-hook table inside
      `#ifdef REGOLITH_DEBUG_TAPS`, hooks compile to nothing in
      release; stable `REGOLITH-TAP ch=<n>` markers for INV-32.
- [ ] a design with no firmware subjects: named absence row in the
      tap map (never a fabricated table).

D6 -- HDL augmentation:
- [ ] `HdlBackend` emits `src/debug_taps.v` per subject when taps
      AND declared debug pins exist (module routes tapped signals to
      the declared pins, in channel order, capacity = declared-pin
      count, overflow = named absence rows); no declared/spare pins
      -> `debug_taps_absent.json` named absence -- never a silent
      drop.

D7 -- INV-32 (tap-map/artifact agreement):
- [ ] ship emits `harness/tap_map.json` (charter 40 sec. 3's family;
      WO-126 adds siblings) -- canonical rows: channel, kind,
      target_path, why, source, connector_pin, per-family artifact
      locations; unallocated + family absences named.
- [ ] `check_tap_agreement(tap_map_bytes, files)` re-parses the
      EMITTED bytes (markers), both directions; failure = named
      diagnostic, ship refuses.
- [ ] `docs/spec/regolith/13-invariants.md` INV-32 entry WITH proof
      argument, SAME change as the check.

Wiring (ship path):
- [ ] `BackendInputs` gains `debug_taps`/`tap_header`/`tap_placements`/
      `hdl_debug_pins` (plain Python inputs class -- not wire schema).
- [ ] `ship(..., debug_spec=None)`: profile=="debug" derives the tap
      set (candidates + explicit + header capacity), allocation only
      when an augmentable family exists (else honest zero-allocation
      map), threads inputs, emits the tap map, runs INV-32.
- [ ] CLI ship passes `spec_data.get("debug")`.
- [ ] `package.py` FAMILY_DIRS += "harness" (index line; release
      goldens regenerated + diff reviewed).

Acceptance projects:
- [ ] mainboard_mx ship.spec.json gains a `"debug"` block (explicit
      tap on the claim-named refclk net); debug ship emits placed
      header + labeled test points + tap map passing INV-32.
- [ ] riscv_hart_rv1 ship.spec.json gains `"debug"` with
      `hdl_debug_pins` for `pc_incr_rtl`; debug ship emits the tap
      module + tap map passing INV-32 (no board -> placement is a
      named absence; the fleet has exactly one board-bearing project
      today, mainboard_mx -- WO-127's jig is the second, ledgered).

Tests:
- [ ] unit: header-record loader, candidate extraction, suffix
      resolution, placement plan determinism, generated .h/.v
      content, `check_tap_agreement` both failure directions.
- [ ] integration: synthetic ship debug vs release -- release file
      set byte-identical (debug adds files only), census/verdict
      equality asserted (manifest.evidence_rollup + gate summary),
      two debug runs byte-identical (per-profile determinism).
- [ ] end-to-end CLI: mainboard_mx + riscv_hart_rv1 build --release
      then ship --emit-profile debug; assert artifacts + INV-32 +
      census equality vs the release ship of the same build.
- [ ] goldens: `make demos` regenerated where the index family line
      lands; diff reviewed (no new error-level diagnostic rows).

Docs:
- [ ] charter 40 cross-ref note (record home + emitted paths);
      guide stub in docs/guide/17-design-testing.md; WO status flip
      in the close-out change.

## Escalation / D239 posture

No wire-schema slot is needed: taps, the header record, placements,
and the tap map all fit emission-layer records + the existing wire
`Placement` shape reused as data. D239 stays untouched (report
"no bump needed" to the coordinator).
