# 32 -- The stdlib depth program (design charter; D174, cycle 31; cross-repo)

> Charter for growing BOTH standard libraries -- lithos std.* record/
> pattern packages and feldspar's solver/model library -- from seed
> catalogs to a powerful, reasonably-exhaustive engineering commons.
> Ledger rule: AD-34 (00-architecture.md). Machinery: lithos WO-66
> (tooling + generation batches), feldspar WO-24 (solver depth).
> Where this doc and a WO body conflict, this doc wins.

## 1. The sourcing law (normative, both repos)

1. Every record cites: source document + revision/edition + license
   posture + which fields it sourced. Unverifiable fields are
   OMITTED with a note (D166 discipline, now law).
2. Collection scripts live in-repo (`tools/stdlib/`), are
   deterministic (same input tables -> byte-identical records),
   polite (rate-limited, cached, identified User-Agent), and use
   ONLY official/open sources: published standards tables,
   manufacturer datasheets and official APIs, license-clean open
   datasets. TOS-violating scraping is forbidden -- a family whose
   only source is closed stays SMALL and hand-cited rather than
   large and stolen.
3. Where the source IS a standard's dimension table (ISO/DIN/ANSI/
   AISC), exhaustiveness comes by GENERATION: a tools/ script
   renders the standard's own grid into records + the citation;
   committed output, reviewable diffs, no thousand-row hand files.
4. Tier honesty unchanged (INV-14): everything community tier;
   scripts and volume confer no trust. Signing remains the only
   tier ladder.
5. Records must load through the LANDED loaders and de-phantoming
   tests; a new family needs its record shape ratified (design-log
   entry) before bulk generation.

## 2. lithos std.* target taxonomy (coverage plan)

Existing seeds grow to, family by family (targets are v1
"reasonably exhaustive" bars, not caps; each batch = one WO slice):

- **std.materials**: metals (structural/aluminum/stainless grades
  per ASTM/EN tables), polymers (common FDM/injection grades),
  woods (structural, per NDS tables) -- ~80 records, full
  mechanical + thermal fields where published.
- **std.fasteners** (NEW): ISO metric machine screws/bolts/nuts/
  washers (ISO 4762/4014/4032/7089 grids M2-M24 x standard
  lengths x property classes 8.8/10.9/12.9), generated from the
  standards' tables; imperial UNC/UNF seed set. Thread math stays
  a MODEL (feldspar/std.models), records carry dimensions +
  ratings only.
- **std.bearings** (NEW): deep-groove ball (60xx/62xx/608 class),
  angular contact seed, linear (LM_UU class) -- dims + static/
  dynamic load ratings from manufacturer general catalogs, cited.
- **std.motion** (NEW): NEMA stepper frames (17/23 classes, torque
  curves as rated points), leadscrews (Tr8x8 class), GT2 belts/
  pulleys, linear rails (MGN class) -- the flagship's own demand
  list drives the exact members.
- **std.elec** (grow): passives E-series grids (generated: E24
  values x common packages x tolerance classes as PARAMETRIC
  record families, not one record per resistor -- the record shape
  question to ratify in the WO), regulators/MOSFETs/drivers seed
  sets around the flagship board, connectors (JST-XH/PH, Molex
  KK, screw terminals), the existing MCU/glue families widened.
- **std.fluid** (grow): fittings (NPT/BSPP/push-fit classes),
  tubing, pumps/valves widened; hotend/nozzle class for
  flagship-1.
- **std.civil** (grow): full AISC v16 W/HSS/C/L grids (generated),
  CSA metric families IF a parseable licensed source is found
  (else the WO-60 honesty note stands), timber sections per NDS.
- **std.machines / std.tooling** (NEW, feeds AD-35 CAM): machine
  envelope/kinematics/spindle records (3-axis mill class, FDM
  printer class, laser class), tool geometry records (end mills,
  drills: diameter/flutes/stickout grids from manufacturer
  catalogs).
- **std.processes** (grow): DFM capability tables per process
  (milling/laser/sheet/FDM/turning) -- the AD-21 capability: seam,
  widened to the machines the flagships use.
- **Patterns/mechanisms** (AD-28, grow per D144): the recorded
  Batch C+ growth continues as designs demand.

## 3. feldspar library target taxonomy (its WO-24; its citation law governs)

Solver/model coverage grows by claim-form demand: bolted-joint
group analysis (VDI 2230-class single bolt + bolt-group shear/
tension distribution), weld group statics, bearing life (L10, ISO
281 form), shaft fatigue tier (Goodman/Soderberg with cited factor
tables), beam/plate deflection catalog completion (Roark cases the
memo already cites), thermal transient lumped tier, belt/leadscrew
drive sizing checks, press-fit/interference (grow the landed
contact seed), column buckling completion. Every model: memo-cited
equations, calibration cases within stated tolerances, validity-
domain predicates (its symbolic core), NO invented physics.

## 4. Interaction with the rest of the system

Records feed: candidate domains for `by select`/section search
(AD-30), DFM eager resolution, costing profiles, CAM verification
(AD-35), pattern packs, and the flagships' BOMs. Nothing here adds
mechanism -- this charter is CONTENT + the tooling to produce it
honestly at scale.

## 5. Acceptance shape

WO-66: tools/stdlib generation framework (deterministic, cached,
cited) + the first exhaustive generated families (fasteners, AISC
grids, E-series shape ratified + generated, bearings/motion seed
batches, std.machines/std.tooling seeds) -- all loaders/
de-phantoming green, licenses recorded, zero unverified numbers.
feldspar WO-24: the sec. 3 model set landed under its calibration
law, each with benchmark-memo cases.
