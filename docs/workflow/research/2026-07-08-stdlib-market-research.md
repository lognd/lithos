# Standard-library and solver market research (WO-45/53/54, feldspar waves)

Date: 2026-07-08. Author: market-research sub-orchestrator (cycle 27).
Status: advisory input, non-normative. Binds to AD-26/27/28/29, the
pattern charter (toolchain/26), the costing charter (toolchain/27),
WO-45/53/54, feldspar WO-17/20/21, and the D135 catalog
(regolith/11 sec. 8).

## Purpose and how to read this

This memo answers one question for the implementation agents: given
what practicing engineers actually reach for, WHAT should the v1
stdlib, pattern packs, feldspar solver wraps, and costing records
ship so that v1 is credible without over-scoping. Every shortlist is
ordered by "an engineer expects this first." Each recommendation is
checked against the EXISTING spec surface -- packages, records,
two-halved models, `advise:` rules, `profile=` claim, unit tables --
and anything needing new core surface is flagged OUT-OF-V1 so it
does not silently expand a WO.

Scope discipline (the tripwire): recommendations here are CONTENT
and CURATION, never new compiler paths. The regolith already carries
patterns (contracts + `spec:` + `parts` kind + rule engine +
`advise:`), costing (claims + D95 sweeps + records + INV-22 pins +
budgets + policy), and the solver seam (feldspar packs, AD-19). If a
shortlist item cannot be expressed in that surface, it is called out.

## Table of contents

1. std.mech.mechanisms -- mechanism/machine-element shortlist
2. std.elec.patterns -- circuit-pattern shortlist
3. std.fluid.circuits -- fluid sub-circuit shortlist
4. std.civil.assemblies -- civil/architectural assembly shortlist
5. Solver landscape for feldspar (WO-17/20/21 wrap-or-skip)
6. Costing data -- profile/record structures and pricing sources
7. Prior art for pattern libraries -- recognition/advise UX
8. Cross-cutting v1 flags (out-of-v1 surface asks)
9. Top v1 recommendations (highest confidence)

---

## 1. std.mech.mechanisms -- the mechanical canon

The canonical corpus is Sclater and Chironis, "Mechanisms and
Mechanical Devices Sourcebook" (>1700 tested mechanisms: linkages,
cams, gears, belts, flexures, springs, screws, clutches/brakes)
[1], with load/stress design content from Shigley and the machine-
element handbooks. WO-53 already fixes `four_bar` as the mechanical
seed; the list below is the catalog `std.mech.mechanisms` should
grow toward, prioritized for a credible v1 batch after the seed.

Each entry ships as the charter's package shape: interface (params +
`spec:` behavioral law), zero-or-more `parts` reference impls, and a
harness-half model discharging the law (kinematics closed-form now;
the feldspar `dynamics` tier registers under the same kinds later).

1. **four_bar (Grashof linkage)** -- seed (WO-53). Coupler law +
   transmission-angle + range promise; the canonical planar linkage
   every ME knows. Recognition over pivot pairs.
2. **slider_crank** -- reciprocating <-> rotary conversion; the
   engine/press primitive. Same kinematic-law shape as four_bar.
3. **lead_screw / ball_screw** -- linear actuation; law is
   lead/efficiency/back-drive with a self-locking predicate. High
   value: ubiquitous in machine design, closed-form.
4. **belt_drive (V / synchronous)** -- speed ratio + tension + wrap
   angle; the power-transmission default. Records for standard
   pitches.
5. **gear_train (spur/helical + planetary)** -- ratio, mesh, and
   torque-density law; planetary carrier kinematics. Anchor of the
   drivetrain vocabulary.
6. **rolling_bearing_arrangement (fixed/floating, back/face)** --
   the charter's connection-discipline example: a mating pattern,
   not a part; L10 life + preload promise. Distinct because it rides
   `matings`, exercising a second pack kind.
7. **toggle / over-center linkage** -- clamping/latching mechanical
   advantage; the detent and press-clamp workhorse.
8. **cam_follower (radial disc)** -- displacement/velocity/accel
   profile law; the timed-motion primitive. Profile records.
9. **flexure_pivot (notch / cross-blade)** -- frictionless limited-
   rotation; precision-mechanism canon (D64 kinematics closure).
10. **helical / leaf spring** -- rate + travel + stress law; the
    energy-storage element every mechanism composes with.
11. **coupling (jaw/Oldham/bellows)** -- shaft misalignment
    accommodation; law is misalignment capacity + torsional stiffness.
12. **detent / latch** -- discrete-position holding; recognition
    target for the toggle/latch shapes engineers hand-roll.

v1 batch (after four_bar seed): items 2-6 plus 10. Rationale: these
are the drivetrain-and-actuation core an ME reaches for daily, all
closed-form (no feldspar dependency), and each exercises a distinct
`spec:` law shape. Cams, flexures, couplings, latches follow by
ordinary publishing. All shippable under the existing surface.

## 2. std.elec.patterns -- the circuit-pattern canon

Canon is Horowitz and Hill, "The Art of Electronics" (the charter's
cited authority), plus TI/ADI app-note practice and the IPC
derating discipline the stdlib already tracks. WO-53 fixes
`level_shifter` as the seed. Each pattern is an abstract block +
`spec:` (e.g. conversion ratio, ripple) + one reference impl +
`advise:` recognition over the hand-rolled discrete equivalent.

1. **level_shifter** -- seed (WO-53). MOSFET/translator block;
   recognition over the discrete two-transistor shape.
2. **decoupling network** -- per-rail bulk + local ceramic; the most
   universal pattern in existence. Recognition: an IC power pin with
   no local cap in reach. Extremely high advise hit-rate.
3. **linear_regulator (LDO)** -- Vin/Vout/dropout/thermal `spec:`;
   the simplest supply block, and the calibration partner for the
   buck. Reference impl + dropout promise.
4. **buck_converter** -- the charter's converter exemplar; ratio +
   ripple + efficiency law with a harness ripple model. The switching
   canon; pairs with feldspar/ngspice later for the ripple half.
5. **RC / RC_debounce** -- filter and mechanical-switch debounce;
   time-constant law. Recognition over hand-rolled RC on an input.
6. **reverse_polarity_protection** -- series FET / diode block;
   protection canon, one-transistor recognition target.
7. **TVS / ESD_protection** -- clamp at a connector/port; `spec:` is
   standoff/clamp vs interface rail. Recognition: an exposed port
   with no clamp.
8. **current_sense (high/low-side)** -- shunt + amp block; sense
   voltage + bandwidth law. Ubiquitous in power/motor design.
9. **NTC / sensor_frontend** -- the existing NtcFrontend example
   generalized (charter names it); divider + linearization `spec:`.
10. **gate_driver** -- level/current drive for a power switch;
    completes the buck/motor stack.

v1 batch (after level_shifter seed): decoupling, LDO, RC_debounce,
reverse-polarity, TVS. Rationale: these are the protection-and-power
hygiene patterns whose ABSENCE is the most common real defect, so
their `advise:` recognition rules deliver the clearest value with
purely structural queries (no numeric half required) -- they ship
today. Buck/current-sense/gate-driver want the feldspar ripple/AC
half and should land with or after WO-17. All under existing surface.

## 3. std.fluid.circuits -- fluid sub-circuit canon

Canon is Idelchik (loss coefficients, already the stdlib's fitting-
record basis), Crane TP-410, and process/hydraulic practice. These
are connection-discipline patterns over fluorite `flownet` shapes;
recognition matches fitting/component arrangements. Harness halves
are feldspar `fluids` network entries (WO-20).

1. **relief / bypass leg** -- pressure-limit protection around a pump
   or vessel; `spec:` is set-pressure + reseat. The safety canon;
   recognition over an unprotected positive-displacement outlet.
2. **filter loop (with bypass + dP)** -- filtration with a
   differential-pressure bypass; clogging/dP law.
3. **accumulator / plenum station** -- energy/pulsation storage;
   precharge + capacity law. Hydraulic and pneumatic canon.
4. **regulator tree (pressure-reducing cascade)** -- staged pressure
   letdown; droop law per stage. The gas-panel primitive (the
   gn2_purge corpus case).
5. **purge / vent path** -- inert purge + safe vent; the charter's
   fill-and-drain manifold generalized. Recognition over a deadleg.
6. **check-valve / anti-siphon** -- one-way isolation; recognition
   over a pump inlet with no non-return.
7. **manifold (parallel branch balancing)** -- flow-split with
   balancing; the distribution primitive.
8. **NPSH / suction protection** -- suction-side arrangement backing
   `fluids.npsh_margin` (feldspar WO-20 entry).

v1 batch: relief leg, filter loop, accumulator, regulator tree.
Rationale: relief and regulator trees are where fluid-system safety
and the gn2_purge/compressible corpus demand concentrate; each maps
to a `flownet` recognition shape plus a WO-20 network-model half. All
under existing surface; the numeric halves gate on feldspar WO-20.

## 4. std.civil.assemblies -- civil/architectural canon

Canon is AISC (steel), ASCE 7 (loads), IBC (egress/occupancy), and
the UL-shaped rated-assembly catalogs the charter names. NOTE: the
whole `std.civil` track is SCHEDULED as WO-48 content (D135/D145),
and the `std.civil.assemblies` pattern pack gates on both WO-48
(assemblies) and feldspar WO-21 (the `frame` numeric half). This
section is forward-looking; nothing here is WO-53/45 v1 scope.

1. **braced bay** -- lateral system; brace-config + drift `spec:`.
   The steel-frame lateral primitive.
2. **moment frame (portal)** -- ductile lateral system; drift +
   member-utilization law. Recognition over beam-column joints.
3. **shear wall** -- concrete/CMU lateral element; in-plane capacity
   law. The building lateral canon alongside braced bays.
4. **rated wall / floor / roof family** -- UL-shaped assembly record
   sets (fire/acoustic/thermal layers); the charter's explicit
   record-set example. Pure records, no numeric half -- earliest
   shippable civil content.
5. **stair / egress core** -- IBC occupancy/egress compliance
   assembly; the charter's stair/egress core.
6. **slab system (one/two-way, flat plate)** -- gravity floor;
   span/depth + reinforcement law.
7. **spread / strip footing** -- bearing-pressure assembly feeding
   the WO-21 reaction-to-bearing chain.
8. **retaining wall** -- Rankine/Coulomb earth-pressure assembly
   (feldspar WO-21 geotech consumer).

v1 batch (when WO-48/WO-21 land): rated assembly families first
(records only, no solver), then braced bay + moment frame + footing
(the small_office frame corpus). Rationale: rated-assembly record
sets are shippable the moment `std.civil` exists; the numeric
assemblies gate on the WO-21 direct-stiffness tier. All under
existing surface; flagged NOT-v1 for WO-45/53.

## 5. Solver landscape for feldspar (WO-17/20/21)

feldspar wraps external solvers as VALUES behind the stage pattern
(deck -> run -> parse -> eps), find/run/parse returning
ToolMissing/ToolFailed rather than throwing (spec 03/05). The
recommendation per wave:

### WO-17 -- ngspice electrical tier (M7)

- **ngspice** -- BSD-3-Clause [4]. Mature (the engine inside KiCad,
  EAGLE, Altium), batch/deck driven, raw-file output -- a textbook
  fit for the deck->run->parse->eps stage pattern the WO already
  specifies. Interface: write SPICE deck, run `ngspice -b`, parse
  rawfile. WRAP -- this is the reference discretized-tier proof and
  the WO's own plan. Env discovery `FELDSPAR_NGSPICE` then PATH.
- Skip: proprietary LTspice/PSpice (licensing, no headless contract),
  and Xyce (heavier, parallel-focused) for v1 -- ngspice covers
  op/dc/ac/tran with the widest install base.

### WO-20 -- thermal-fluids wave

- **CoolProp** -- MIT license [3]. The de facto open thermophysical
  property library (REFPROP-grade correlations, pure + pseudo-pure
  fluids, humid air). WRAP as the `thermo` property-table backend
  exactly as the WO states; interpolation eps + domain boxes
  declared at registration. No competitor is close on license +
  coverage.
- Fluid NETWORK tier -- no single dominant open tool; the WO
  correctly specifies IMPLEMENTING the network solve (series/parallel
  reduction + Hardy-Cross/Newton) in Rust formula homes over
  `flownet` payloads, with Colebrook/Haaland + Idelchik minor-K
  records. RECOMMEND build-not-wrap here (the algorithms are compact
  and citation-backed; wrapping EPANET/OpenModelica would drag a
  hydraulics/Modelica runtime for a 1-D network the WO can own). The
  compressible Fanno-line tier (D141) is likewise a formula home.
- Water hammer: Joukowsky + method-of-characteristics as formula
  homes (WO already lists). Build.

### WO-21 -- civil/structural wave

- Frame direct-stiffness -- BUILD in Rust matrix homes (the WO's
  plan): truss/beam/frame/grid assembly over `frame` payloads. A
  linear direct-stiffness solver is well within a formula home and
  avoids a license/runtime dependency.
- If a reference/calibration partner is wanted: **PyNite** (MIT-
  licensed pure-Python 3D FE frame library [2]) or **anaStruct** (2D)
  are clean calibration oracles -- permissive, pip-installable, no
  commercial-redistribution clause. **OpenSeesPy is NOT free for
  commercial redistribution** (UC Berkeley license; free only for
  research/education/internal use) [2] -- SKIP as a shipped
  dependency; usable at most as an out-of-band validation reference,
  never wrapped into a distributed pack.
- Member design checks (AISC/Eurocode interaction, LTB, connections):
  BUILD as cited formula homes -- these are clause-by-clause code
  formulas, not a solver, and must cite their manual clause per 03.
- Full-3D continuum FEA (CalculiX / code_aster / Elmer): OUT of the
  civil wave. CalculiX (Abaqus-format, GPL) and code_aster (GPL,
  nuclear-regulator accepted) are the mature open FEA options [5] and
  would be a FUTURE mech-continuum wrap if a solid-stress tier is
  demanded -- but the civil `frame` consumer needs direct stiffness,
  not continuum FEA. Flag CalculiX as the preferred future FEA wrap
  (Abaqus-compatible deck = clean stage pattern) when that wave is
  chartered.

## 6. Costing data -- profiles, records, pricing sources

WO-54/AD-29 fix the shape: the compiler ships NO prices; every number
is a profile-selected, hash-pinned, validity-windowed record; cost is
a claim, an itemized table is evidence. The market research below
informs WHAT the v1 record schemas must model and which public
sources the fixtures should mirror.

**Pricing-source landscape (what the records mirror):**

- **McMaster-Carr Product Information API** [6] -- catalog pricing
  for mechanical hardware (fasteners, bearings, stock). Client-
  certificate gated, publicly-priced catalog. The canonical
  "catalog price" record shape: item, price, retrieved-date. v1
  fixtures should mirror this shape (a pinned snapshot, `valid_until`).
- **PCB fab quotes** (JLCPCB/PCBWay/OSHPark-style): quantity-break
  pricing + a fab-parameter table (layers, area, finish). The elec
  BOM estimator's fab-table half. No universal public API; model as a
  pinned quote record with quantity breaks (the WO already specifies
  "quantity breaks + valid_until").
- **RSMeans** [7] -- the civil unit-cost standard: 97,000+ unit-cost
  line items across 16 CSI divisions, city cost indexes for 970
  locations, annual updates. Subscription/paywalled ($2,195+/seat),
  so v1 ships the SCHEMA (RSMeans-shaped assembly unit-cost record:
  assembly, unit, material/labor/equipment split, location index)
  and FIXTURE numbers, never RSMeans data itself. This is the
  unit-cost-record schema the charter names.

**v1 record schemas WO-54 should model (all under existing surface):**

1. **rate record** -- shop/labor/process/regional rate, per-unit-time
   or per-operation, cited, currency-tagged.
2. **pricing record** -- vendor price with QUANTITY BREAKS + a
   `valid_until` window (McMaster/JLC shape); expired -> indeterminate.
3. **unit-cost record** -- RSMeans-shaped assembly cost with
   material/labor/equipment decomposition and a location index axis.
4. **itemized-estimate payload** -- the `table`-kind evidence: line
   item (item, qty, unit cost + record ref, extended) + declared
   exclusions. Content-addressed, byte-deterministic.
5. **currency** -- unit-family machinery only (USD baseline);
   conversions are explicit cited records, never ambient (AD-29).

Profiles ({prototype, production, construction, ...}) live in each
project's `magnetite.toml [profiles.cost.<name>]`, sweepable via D95
`forall profile`. All expressible today; nothing needs new core
surface. The one honesty rule to fixture hard: consuming an EXPIRED
pricing record is indeterminate naming the record, waivable with
basis -- the expired-quote negative fixture proves it.

## 7. Prior art for pattern libraries (recognition/advise UX)

What users expect from a design-tool pattern library, mapped to
AD-28's advise-only, no-new-channel rules:

- **KiCad symbol/SPICE libraries** [8] -- users expect libraries to
  travel WITH the project (local project libs), addressable and
  version-pinned. Maps directly to magnetite packages + INV-22
  lockfile pinning: a consumed pattern is a pinned dependency, not a
  global. Lesson: portability = pinned package, which the regolith
  already enforces.
- **Fusion 360 McMaster-Carr toolbox** [8] -- insert a real,
  parameterized standard component by search; "everyone works from
  the same reference data." Maps to `magnetite new --template
  <pattern>` scaffolding (WO-53/WO-41) and LSP completion from
  imported packs -- surfacing patterns through EXISTING channels
  (AD-24), no new discovery UI.
- **Revit family libraries** [8] -- nested families (LEGO-brick
  composition), centralized storage, and template-vs-library split
  (common families in template, heavy ones out). Maps to the
  two-halved package + `parts`/`interfaces` kinds; the lesson is
  curation discipline (what belongs in the seed vs published later),
  which the charter's "seed set, grow by publishing" already adopts.
- **SPICE model libraries** [8] -- the recommendation is INFORMATIVE
  and human-adopted: the tool offers a model, the engineer wires it.
  Maps precisely to AD-28's `advise:`-only, verdict-inert,
  no-auto-substitution rule -- adopting is a human source edit.

The consistent expectation across all four: recognition/recommendation
is ADVISORY and PORTABLE, never coercive and never global. AD-28 +
INV-22 already encode both. The `regolith explain <advice-code>`
surface (charter sec. 1.4) matches the "why is this recommended"
affordance users expect from datasheet views. No new UX surface is
needed; the risk is over-building discovery -- resist it (AD-28
rejects new severities and side query paths).

## 8. Cross-cutting v1 flags (out-of-v1 surface asks)

Everything recommended above is shippable under the existing surface
EXCEPT the following, which must be escalated, not silently built:

- **Recognition query predicates** (WO-53): if matching a hand-rolled
  four-bar or discrete level-shifter needs a structural predicate the
  AD-21 query surface does not expose, ESCALATE per AD-22 -- do not
  grow a side query path (charter sec. 2, WO-53 dep note).
- **Numeric harness halves** for buck/current-sense (elec),
  relief/regulator networks (fluid), and every civil frame assembly
  gate on feldspar WO-17/20/21 respectively. Ship the contract +
  `spec:` + recognition half now; the model half lands with the
  feldspar wave. Do NOT block the pattern pack on the solver.
- **std.civil.assemblies** entirely gates on WO-48 + WO-21 -- NOT
  WO-45/53 v1. Section 4 is forward-looking.
- **Cost profiles are project data, not stdlib** -- `std.cost` ships
  schemas + reference estimators + math; the numbers live in each
  project's manifest. Do not put any price in `stdlib/`.
- **No compiler special-casing of `std`** (D135 tripwire) -- all of
  the above is package content; grep `std.` in `crates/` must stay
  clean of new logic.

## 9. Top v1 recommendations (highest confidence)

1. **Elec decoupling + protection patterns first** (decoupling, LDO,
   reverse-polarity, TVS, RC-debounce): their `advise:` recognition
   is purely structural (no numeric half), and absent decoupling/
   protection is the single most common real defect -- highest
   value-per-effort, ships today alongside the level_shifter seed.
2. **Mech v1 batch = slider_crank, lead/ball screw, belt drive, gear
   train, bearing arrangement, spring** after the four_bar seed: the
   daily drivetrain/actuation core, all closed-form (no feldspar
   dependency), each a distinct `spec:` law shape.
3. **Wrap ngspice (BSD) and CoolProp (MIT); BUILD the fluid-network
   and frame direct-stiffness tiers; SKIP OpenSeesPy as a shipped
   dependency** (non-free for commercial redistribution) -- use
   PyNite (MIT) only as an out-of-band calibration oracle. CalculiX
   is the preferred FUTURE continuum-FEA wrap, out of v1.
4. **Cost v1 = three record schemas (rate, quantity-break pricing
   with `valid_until`, RSMeans-shaped unit-cost) + itemized-table
   evidence + currency-as-units**, mirroring McMaster/JLC/RSMeans
   SHAPES with fixture numbers only -- ship no real priced data, and
   fixture the expired-quote-indeterminate path hard.
5. **Keep recommendation advisory and portable** (AD-28 + INV-22):
   patterns are pinned packages surfaced through scaffolding/LSP/
   datasheet channels that already exist; resist any new discovery UI
   or severity. The prior-art lesson (KiCad/Fusion/Revit/SPICE) is
   uniform -- users expect advisory + version-pinned, which the
   regolith already provides.

---

## Sources

[1] Sclater and Chironis, "Mechanisms and Mechanical Devices
Sourcebook" (4th ed.), McGraw-Hill --
https://archive.org/details/mechanismsmechan0000scla
[2] PyNite (MIT), https://github.com/JWock82/PyNite ; OpenSeesPy
licensing (free for research/education/internal only),
https://openseespydoc.readthedocs.io/en/latest/ ; VIKTOR overview,
https://www.viktor.ai/blog/177/5-powerful-python-libraries-every-structural-engineer-should-know
[3] CoolProp (MIT), https://coolprop.org/ and
https://github.com/CoolProp/CoolProp
[4] ngspice (BSD-3-Clause), https://ngspice.sourceforge.io/ and
https://en.wikipedia.org/wiki/Ngspice
[5] Open FEA comparison (CalculiX/code_aster/Elmer),
https://cloudhpc.cloud/2025/09/15/decoding-performance-a-scalability-showdown-between-calculix-and-code_aster/
and https://fea4free.com/open-source-fem-software-review/
[6] McMaster-Carr Product Information API,
https://www.mcmaster.com/help/api/
[7] RSMeans unit-cost data guide,
https://www.rsmeans.com/resources/unit-cost-databases-construction-guide
and https://www.rsmeans.com/products/services/api.aspx
[8] Pattern-library prior art: KiCad SPICE,
https://www.kicad.org/discover/spice/ ; Fusion McMaster extension,
https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-90FD5419-A8AF-4A7C-AB1E-75D027077709 ;
Revit family reuse, https://bimheroes.com/creating-revit-families/
