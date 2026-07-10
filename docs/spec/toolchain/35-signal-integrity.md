# 35 -- Signal integrity: impedance, termination, stackup choice (design charter; D186, cycle 32)

> Charter for calculated, auditable board-level SI: controlled
> impedance as a discharged claim, termination/bypass as a sized
> discipline, layer count as an optimized selection -- every number
> visible with its formula and inputs. Machinery: feldspar WO-25
> (models), lithos WO-78 (records, claim forms, wiring, the SI
> sheet). Where this doc and a WO body conflict, this doc wins.

## 1. Design decisions (load-bearing)

1. **Stackup records** (`std.elec.stackups`, AD-34 law): fab-
   published stackups (layer count, per-layer dielectric height,
   Dk/Df, copper weight, impedance-table citations). A stackup a
   fab does not publish is not a record.
2. **Impedance claims**: `elec.impedance(<net|class>) within
   [lo, hi] ohm` (single-ended and differential forms) discharged
   by cited closed-form models over (stackup record, trace
   width/gap, layer assignment). Pre-layout: width/gap are
   `in [lo, hi]` slots the engine solves against the claim
   (boundary-finding, D184) -- the pinned width IS the calculated
   design rule, cause-attributed. Post-layout: the same claim
   re-discharges over RealizedLayout-extracted geometry (T2); a
   layout that drifted from the pinned rule fails loudly.
3. **Termination/bypass discipline**: `elec.termination(<net>,
   scheme=series|parallel|thevenin|ac_shunt)` claims sized by cited
   formulas (Zo, driver Ro, rise time -> R/C with arithmetic in
   evidence); AD-21 `erc:` rules demand presence on declared net
   classes (supply-pin shunt-C within a distance bound once layout
   exists; declared high-speed nets carry their scheme statically).
   Two severities only, waive ladder only, per AD-21.
4. **Layer-count selection**: stackup candidates declared
   (`by select` over stackup-bearing board impls or a stackup slot
   with a registry domain -- WO-78 decides the spelling against the
   landed grammar, escalating if neither fits); feasibility = all
   impedance claims achievable on the candidate (+ density screens
   from the rule pack's capability table); objective = cost.
   Routability remains post-layout evidence -- the selection
   evidence says "impedance-feasible + screen-passed", never
   "routable", honestly.
5. **The SI sheet**: a DrawingModel `tables` producer (the schedule
   mechanism) per board: net/class, target, chosen stackup + layer,
   width/gap, computed Zo, margin, model id, cause. Golden-enrolled,
   graphite-browsable. The parity report classes every sized value.
6. **Models are feldspar's** (WO-25): Hammerstad-Jensen microstrip,
   symmetric stripline, edge-coupled differential (IPC-2141-class
   forms), termination sizing; memo-calibrated against published
   fab calculator values within stated tolerances; validity
   predicates narrow (w/h ranges, Dk ranges, TEM assumption).

## 2. Non-goals (reopen criteria attached)

- Full-wave/2.5D field solving: reopen on a claim class the
  closed-form validity domains cannot cover (then it enters as an
  AD-19 pack, like FEA).
- Crosstalk/eye-diagram/jitter analysis: post-v1; needs coupled-
  line models with their own calibration story.
- Auto-placement of termination components: sizing yes, placement
  is layout's job; presence-within-distance is checked, not
  synthesized.
- Length matching/delay tuning: needs routed lengths (the WO-34
  extraction seam carries them) -- chartered as the natural
  follow-on once a flagship demands it, not built now.

## 3. Acceptance shape

feldspar WO-25: the model set calibrated against >= 2 published
fab impedance tables within stated tolerance. lithos WO-78: a
corpus board with declared net classes where (a) the engine pins
trace width against a 50-ohm claim with the calculation in
evidence, (b) an ac_shunt bypass rule fires on a violating fixture
and passes on the fixed one with sized values, (c) a `by select`
stackup choice flips with the cost policy (test), (d) the SI sheet
renders it all, golden-enrolled, and the parity report accounts
every sized value.
