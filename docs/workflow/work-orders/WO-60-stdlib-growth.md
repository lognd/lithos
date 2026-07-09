# WO-60: stdlib growth batch C (selection catalogs + recorded growth)

Status: done
Depends: WO-45/WO-53 conventions (landed): catalog rows, TOML record
loaders, de-phantoming tests, two-halved pattern packs. Independent
of every other cycle-30 WO; feeds WO-56's ebi_decode demo (soft).
NO SCHEMA_VERSION bump; no Rust.
Language: records (TOML/`.cupr`/`.hema`/`.fluo`/`.calx` pack
content) + Python only for loader/test touch-ups.
Spec: docs/spec/toolchain/26-pattern-libraries.md (AD-28),
regolith/11 (packages/stdlib), design-log 2026-07-09-cycle-30 D166;
the cycle-28 MCU-registry verification precedent (INV-14: tier is
earned by signature, never by text cross-check -- everything here
stays community tier with in-file verification notes).

## Goal

The recorded WO-53/WO-45 growth lands, with the catalogs the
cycle-30 optimizer needs: an address-decode/glue-logic family (the
D161 demo candidates), wider civil section/material tables (a real
section-search domain), fluid component records, and the
mech-mechanisms remainder.

## Deliverables

1. **std.elec.patterns batch C -- glue-logic/address-decode
   family**: records + two-halved packs for at least: 74HC02 (quad
   NOR), 74HC138 (3-to-8 decoder), 74HC688 (8-bit comparator), one
   CPLD candidate (e.g. ATF1502ASL -- verify the real, current
   part), and an MCU chip-select pattern (EBI/FSMC-style, cited to
   a real MCU family reference manual). Each record: real datasheet
   citation WITH revision, key electrical facts (propagation delay,
   supply range, package options), cost-surface fields the landed
   costing records support.
2. **std.civil widening**: extend `sections.toml` (more W/HSS/pipe
   shapes across the depth range) and `materials.toml` per the
   landed schema; every row cites its source table (AISC shapes DB
   edition or equivalent public source) in-file. Enough shapes that
   the WO-56 section search is a real choice (>= 15 sections per
   family used by the corpus).
3. **std.fluid batch**: pump/valve/orifice/filter records per the
   landed fluid record shapes, real-catalog cited.
4. **std.mech.mechanisms remainder**: the batch-C members the WO-53
   ledger names as recorded growth.
5. **Research protocol**: facts verified against real, current
   datasheets/catalogs (web research in-dispatch); no invented
   numbers -- a fact that cannot be verified is OMITTED with a note,
   never guessed (feldspar's no-invented-physics discipline applied
   to records). Verification notes in-file per the MCU-registry
   precedent.
6. **Tests/wiring**: catalog rows, loader round-trips,
   de-phantoming (every referenced record exists; every record is
   referenced or listed), fixtures where WO-45/53 conventions add
   them.
7. **Docs**: stdlib README sections, WO-53/45 ledger cross-notes,
   WO ledger.

## Acceptance criteria

- Every new record loads through the landed loaders; de-phantoming
  green; catalog rows complete.
- Spot-check hooks: each record's citation names document + revision
  + the fields it sourced (reviewable without the datasheet).
- The glue-logic family is sufficient for WO-56's
  `by select(nor_glue, cpld, mcu_chip_selects)` demo (named refs
  documented in this WO's ledger for WO-56 to consume).
- std.civil growth changes NO existing corpus golden (additive
  rows only; if a golden churns, the row collides -- rename, never
  regenerate around it).
- ASCII only; `make check` green; Status flipped in this change.

## Close-out (dispatch of 2026-07-09)

**Package-home escalation, checked, resolved by citation (not
invented):** deliverable 1 labels the glue-logic family
"std.elec.patterns batch C," matching WO-53's Batch A/B naming
convention, but its actual content (raw vendor datasheet
transcriptions -- propagation delay, supply range, package options,
no `spec:`/recognition-rule pattern half) does not match
`std.elec.patterns`'s shape (interface `block` + `impl` + `advise:`
rule, D144/AD-28). regolith/11 sec. 2's OWN package-kind table names
the correct home for exactly this content: `components` packages
`ti.logic`, `st.mcu` (its own worked examples) beside `jlc_2l`'s
vendor-named, non-`std.`-prefixed precedent. This dispatch follows
that normative table rather than force-fitting raw component records
into the pattern-pack shape: three new vendor-named `components`
packages, `stdlib/ti.logic/`, `stdlib/microchip.cpld/`,
`stdlib/st.mcu/`, each a real magnetite package (manifest + plain-TOML
records under `records/`, the WO-45 no-track-syntax-yet convention --
Python-side data authoring, no Rust grammar, matching this WO's own
`Language:` header).

**1. Glue-logic/address-decode family** (`stdlib/ti.logic/records/
glue_logic.toml`, `stdlib/microchip.cpld/records/atf1502.toml`,
`stdlib/st.mcu/records/fsmc_chip_selects.toml`):

- `ti.logic.sn74hc02` (quad 2-input NOR): TI SCLS076G, rev. December
  2020. Vcc 2V-6V, tpd typ 9ns/max 18ns @ Vcc=4.5V, packages
  D/DB/N/NS/PW (14-pin).
- `ti.logic.sn74hc138` (3-to-8 decoder): TI SCLS107G, rev. October
  2021. Vcc 2V-6V, tpd (A/B/C-to-Y) typ 18ns/max 36ns @ Vcc=4.5V,
  packages D/DB/N/NS/PW (16-pin).
- `ti.logic.sn74hc688` (8-bit identity comparator): TI SCLS010F, rev.
  May 2022. Vcc 2V-6V, tpd typ 14ns (Features page; the full
  switching-characteristics MAX row was not independently re-verified
  and is omitted), packages DW/N/PWR (20-pin).
- `microchip.cpld.atf1502asl_7` / `atf1502asl_25` (32-macrocell CPLD):
  Microchip DS20006619A, 2021 printing -- confirmed still a live
  catalog part as of this dispatch (2026-07-09). Vcc 5V +-5%(comm)/
  +-10%(ind), tPD1 max 7.5ns (-7 grade, fMAX 125MHz) / 25ns (-25
  grade, fMAX 50MHz), packages PLCC44/TQFP44.
- `st.mcu.stm32f4_fsmc_bank1` (MCU EBI/FSMC chip-select pattern): ST
  RM0090 Reference manual (STM32F405/415/407/417/427/437/429/439),
  Rev 22 (May 2026), ch. 36 -- Bank 1 split into 4x 64MB sub-banks
  selected by FSMC_NE1..FSMC_NE4 from address bits A[27:26]; the
  built-in-decode alternative to external NOR glue or a CPLD.

  **Refs for WO-56 to consume verbatim in its `by select(nor_glue,
  cpld, mcu_chip_selects)` demo:** `nor_glue` composes
  `ti.logic.sn74hc138` (address-range decode) with `ti.logic.sn74hc02`
  (glue/combine); `cpld` is `microchip.cpld.atf1502asl_7`;
  `mcu_chip_selects` is `st.mcu.stm32f4_fsmc_bank1`. Building the
  actual `AddressDecodeGlue`-shaped block + its three named impls
  (the `by select` grammar target) is WO-56's own grammar/lowering
  deliverable, not this WO's -- this WO's job (per its own acceptance
  criterion 3) stops at the verified component catalog + this
  documented ref list.

**2. std.civil widening** (additive only; `sections.toml` +
`materials.toml`): 16-member `w_shape` family (AISC Steel Construction
Manual 16th ed. / Shapes Database v16.0, ASTM A992, imperial) and
28-member `hss_square` family (same edition, ASTM A500 Grade C,
imperial) -- both well above the >= 15-per-family bar. `astm_a500_grc`
material row added (Fy=345MPa/Fu=427MPa/E=200GPa, Steel Tube Institute
A500 summary). VERIFICATION NOTE / omission: the corpus's existing
metric `section: registry(...)` keys (`w250x73`, `hss89x89x6.4`,
`hss127x127x8`, `steel_deck_38mm`, `alum_deck_25mm`) are CISC/metric
designations; this dispatch's WebFetch could not extract numeric
values from the primary CISC/CSA property pages (both
beamdimensions.com and dlubal.com returned JS-rendered pages with no
extractable numbers after repeated attempts) -- rather than guess a
metric conversion, those exact keys are left UNRESOLVED (unchanged
from before this WO; they were already unresolved, since WO-56's
section-search wiring has not landed yet) and the real, independently
verified imperial families above are added alongside as a distinct,
honestly-cited domain. Zero churn: `tests/golden/test_golden_corpus.py`
and `tests/magnetite/test_stdlib.py` both green, unchanged pass count
plus the new package/record parametrizations.

**3. std.fluid batch** (`stdlib/std.fluid/records/components.toml`):
`swagelok_ss_63ts8` (1/2in 3-piece ball valve, 0.406in orifice, 2200
psig @ 100F, Cv=7.5 -- Cv sourced from Swagelok's own valve-sizing
reference rather than the product page itself, noted in-file);
`swagelok_ss_8f_60` (1/2in in-line particulate filter, 60 micron pore,
316SS, -40F to 900F -- pressure-drop curve not published, omitted);
`sharp_edged_concentric` (Crane TP-410 orifice discharge coefficient,
Cd~=0.61, beta 0.2-0.75); `grundfos_up15_10su7p` (wet-rotor circulator
-- max head ~4.5ft/max flow ~5.5 US GPM duty-point endpoints
cross-checked across two independent distributor listings; the
primary Grundfos curve-booklet PDF exceeded this session's fetch size
limit and could not be parsed, so the full head-flow CURVE is
explicitly NOT transcribed and is noted as omitted rather than
guessed).

**4. std.mech.mechanisms remainder**: `flexure_pivot.hema`
(thin-blade rotational spring rate, Shigley ch. 4 beam-bending law)
and `toggle_linkage.hema` (mechanical-advantage singularity law,
Norton ch. 3) -- the two charter sec. 2 catalog entries ("flexure
pivots," "toggle linkages") not yet published after WO-53's seed +
Batch B; both mirror the landed `helical_spring.hema`/
`slider_crank.hema` shape exactly (`mating` + `couples:` + `promises:`
+ `dfm:` recognition rule) and were confirmed to `regolith check`
clean (the same "dead generic, declared but never instantiated"
E0503 warning every other standalone pattern pack file gets, `ok=True`
both times). Charter sec. 2's "detents/latches" and "counterbalances"
remain deferred catalog growth -- recorded here, not silently dropped.

**Tests/wiring**: `tests/magnetite/test_stdlib.py`'s existing
directory-driven parametrization (`_STDLIB_PACKAGES`,
`_PACKAGES_WITH_RECORDS`) auto-discovered all three new vendor
packages and the two widened std.civil/std.fluid files with ZERO test
file edits -- manifest-loads, record-round-trip, and trust-tier-
honesty tests all pass for the new content (43 passed, up from the
pre-dispatch count). `tests/golden/test_pattern_libraries.py` and
`tests/golden/test_golden_corpus.py` both green, unchanged (52
passed) -- confirms no existing corpus golden churned.

**Worktree note**: this dispatch's worktree branch had not yet picked
up the cycle-30 commit that authored this WO file (`43f7060`,
"docs(cycle-30): ... WO-55..60"); merged it in (a clean, purely
additive docs merge, no conflicts with this WO's own content changes)
before proceeding, per the dispatch protocol's "read the WO file
first" step.

`make check`: green (fmt, ruff, ty, pytest -- no Rust grammar surface
touched, per this WO's own `Language:` header; `cargo test` untouched
by this change but run as part of the full suite).
