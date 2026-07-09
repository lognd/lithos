# The Quantity Core

> Regolith spec. The keystone package: both modeling languages and the
> harness depend on it; it depends on nothing. Changes here are breaking
> changes everywhere.

## 1. Quantities

Physical quantities are declared in namespaces, typed with a unit and a
tensor rank:

```
namespace mech:
    quantity stress:        Pa,   tensor(2)
    quantity displacement:  m,    vector
    quantity stiffness:     N/m,  scalar

namespace elec:
    quantity voltage:       V,    scalar
    quantity current:       A,    scalar
    quantity impedance:     ohm,  complex        # frequency-indexed
    quantity energy:        J,    scalar

namespace thermo:
    quantity temperature:   K,    scalar
    quantity heat_flux:     W/m2, scalar

namespace info:                                  # computer track
    quantity data_rate:     bit/s, scalar
    quantity storage:       bit,   scalar
    quantity op_rate:       op/s,  scalar        # typed by op kind at use
```

- Dimensional analysis runs at parse time; unit errors never reach a
  solver. Arithmetic between incompatible quantities is a type error.
- Namespaces are shared across domains. A thermal quantity means the same
  thing in a mechanical claim and an electrical one -- this is the hook
  for cross-domain contracts.

## 2. Equality ban

`==` on continuous quantities is a **compile error**. Legal forms:

- `within(a, b, tol)`
- constraint declarations (`coincident`, `equal_within`)
- exact equality on discrete types (integers, enums, names) only.

## 3. Intervals

Anywhere a scalar is legal, an interval is legal: `[300K, 900K]`,
`[0.75, 1.25] * P0`, `3.3V +- 5%`. Intervals are the source-of-truth
representation for tolerances, scatter, environment ranges, and process
corners. Checks are evaluated at their own worst-case corner; which corner
is worst is per-check, not global (corner discipline -- see
`07-claims-and-evidence.md`).

**Interval vs range notation.** [SETTLED, cycle 1] Two bracket forms,
never mixed:

- `[a, b]` (comma) -- a **closed interval**: continuous quantities
  (`[300K, 900K]`) and closed discrete domains (`in [2, 6]` over
  integers monomorphizes 2,3,4,5,6).
- `[i .. j]` (dots) -- a **half-open positional range** over
  semantically ordered discrete positions: bus bits (`sel[0 .. 3]` =
  bits 0,1,2), memory addresses (`flash[0 .. 32kB]`). Positional
  ranges are legal only where position is semantic content (a bit's
  binary weight, an address) -- they are semantic addressing, not the
  banned positional indexing of entity sets.

**Counts.** `n x thing` (`battery(2 x AA_alkaline)`, `pwm x 4`) is the
count constructor: a discrete quantity of identical members, forming an
orbit where the members are entities.

## 4. Zones

A quantity value may be zone-indexed over an artifact: different regions
carry different values of the same field:

```
thermal: zones(tip: [700K, 950K], base: [300K, 400K])
```

Zone boundaries are datums (see `05-ownership-and-queries.md`); zone
extents are owned regions. Declaration syntax (`zones over <set>:`,
partition rules, `remainder`) is settled in mech `02-language.md`
section 7 and generalizes to any domain with spatial extent.

## 4a. Computed indexed fields (D98, WO-33)

A claim may COMPUTE a named, indexed quantity -- a field over zones,
or a curve over a declared config variable -- that sibling claims
consume through ordinary projections, closing the "worst-point scalar
with hand-carried conservatism" degeneration:

```
compute wall_T: thermo.wall_temperature over liner.zones
compute camber: vehicle.camber over travel in [-80mm, 120mm]
```

- `compute <name>: <quantity kind> over <index domain>` lowers to ONE
  obligation whose successful evidence carries a `field` payload (the
  discretized values over the index domain, plus the domain encoding
  itself -- the same `CoverageAxis` type sec. 2's swept obligations
  use: interval or enumerated). The produced name enters the datum
  ledger, borrow-exempt, exactly like events (sec. 5).
- Consumption is ordinary claim vocabulary: `max(wall_T) < 800K`,
  `wall_T at zone(tip) < 900K`, `slope(camber, travel) in [-0.05,
  0]deg/mm`. Projections lower to derived quantities whose givens
  carry the producing obligation's field payload ref (the
  promise-chain mechanism, `07-claims-and-evidence.md` sec. 2). A
  sibling `compute` may itself consume another computed field as a
  given, forming an ordinary promise DAG; a compute-compute cycle is
  a compile diagnostic naming the chain.
- Honesty rule: a projection over a field whose evidence is
  indeterminate is indeterminate (chain rule of the ledger). Until a
  field-producing model is registered, compute obligations -- and
  every consumer that projects them -- stay honestly indeterminate;
  no fake data path. Full shape, grammar, and schema in
  `../../workflow/work-orders/WO-33-computed-fields.md`.

## 5. Time structure, events, windows, masks

[SETTLED] (resolves the former SOPEN-1 and mech OPEN-9): time-domain
vocabulary is quantity-core, shared by both tracks.

**Structure on loads/signals**, propagated through derivations:

```
structure: static                    # default
structure: alternating(R=-1, f=120Hz)
structure: spectrum(ref)             # hash-pinned load/duty spectrum
structure: transient(profile_ref)    # explicit time profile (from_table/from_fn)
```

**Events** are named time datums -- the temporal analog of geometric
datums, and equally borrow-exempt:

- boundary-declared: `event drop: shock(50g, 11ms, half_sine)`,
  `event load_step: step(i(load), 2A/us)`, `event supply.on`
- derived: `clk.rise`, `mode.enter(sleep)`, `pivot.theta.crosses(45deg)`

**Windows** are intervals over time built from events:

```
during <event-or-config-domain>      # while it holds / over its span
within <duration> after <event>      # bounded response window
until <event>
```

**Masks** are piecewise envelopes over a window (registry objects,
`from_table`/`from_fn`, hash-pinned): shock response spectra and
vibration profiles (mech); eye masks, power-sequencing masks, emissions
limits (elec). The claim form is `stays_within(x, mask)`.

**Claim forms** built on these (see `07-claims-and-evidence.md`):
`peak(x, during w)`, `settles(x, to=tol, within d after e)`,
`overshoot(x, after e)`, `rms(x, band=[f1, f2])`, `stays_within(x, m)`.

Frequency-domain claims (`band=`, modal frequencies, PSD limits) are the
Fourier view of the same machinery; mech modal claims
(`first_mode > 120Hz`) and elec noise claims (`rms(v(out),
band=[10Hz, 100kHz]) < 1mV`) are one claim family with different
harness models.

Jitter and scatter on events are intervals on the event's time, nothing
new: `clk.rise +- 50ps` follows ordinary corner discipline.

**Profile windows** [SETTLED, cycle 7 -- part of closing EOPEN-18]:
`over=` in accumulation claims (`energy`, `damage`, `write_endurance`)
accepts a duration (`over=1yr`), an event window, or a hash-pinned
**periodic profile** (`over=boundary.orbit.profile`, a `spectrum(ref)`
with mode/duty structure). With a profile, the claim integrates
mode-weighted over one period and scales to the comparison window;
worst-case phase within the period follows corner discipline. This is
the orbit-average energy claim, the duty-cycled fatigue claim, and the
duty-limited endurance claim as one mechanism.

## 5a. Logarithmic unit views

[SETTLED, cycle 7; closes SOPEN-5] Link budgets, gains, and noise
figures are natively decibel arithmetic. Rule: **log units are views
of linear quantities** -- the stored, solved, and cached value is
always linear; `dB`-family units affect parsing and printing plus one
extra L1 legality check.

- **Unreferenced** log units view dimensionless ratios: `dB` (power
  ratio), `dBc` (vs carrier), `dBi` (vs isotropic).
- **Referenced** log units carry a reference and view a quantity of
  the reference's dimension: `dBm` (1mW), `dBW` (1W), `dBuV` (1uV).
  References are unit-table content, extensible like any unit.
- **Sum legality = linear product legality**: a sum of log terms is
  legal iff, after cancelling subtracted references against added ones
  (`P_rx - P_sens` is a ratio), **at most one referenced term
  remains**; the sum has that reference's dimension, or ratio if none.
  `p_tx + g_ant - l_path` (dBm + dBi - dB) is a power; `dBm + dBm` is
  a compile error (the linear product mW^2 is not a power) -- the
  classic link-budget bug, dead at L1. An uncancelled *subtracted*
  reference (an inverse dimension) is likewise rejected.
- Log views are strictly monotone, so **interval corners commute with
  the view**: corner discipline and margin math run in linear space,
  untouched. `margin` may be *reported* in dB; it is computed linear.
- The `==` ban applies to the underlying continuous quantity,
  view or no view.

## 6. Property registries

Shared, hash-pinned databases of real-world facts, owned by neither
compiler nor harness. All follow one pattern: **class hierarchy + concrete
records + unordered-pair records + evidence-gated overrides** (the trait
coherence rules, `09-build-and-lockfile.md` section 5).

| registry | mech binding | elec binding |
|---|---|---|
| `class` hierarchy | material classes (`steel: metal`) | component classes (`mosfet: transistor`), logic families |
| concrete record | `material AISI_4140: E: f(T) interval, ...` | `component NE555: ...` datasheet limits as intervals |
| `contact { A, B }` | friction, conductance, wear per material pair | connector mating records, galvanic compatibility |
| `process` | machining/forming capability + DFM rules | fab capability (trace/space, drills) + DRC rules; assembly capability |

Registry values are interval-valued functions of environment where reality
demands it (`E: f(T) interval`; `R_ds_on: f(T, V_gs) interval`). Users
write only the reference (`material: AISI_4140`, `part: vendor(ne555)`);
overrides must cite evidence and stay intervals:

```
override contact{steel, steel}.mu_static by test(report_tr114): [0.12, 0.14]
```

## 7. Signatures

The linker symbol between modeling language and harness -- a physics model
*contract*:

```
signature bolted_joint_state:
    inputs:  preload: N interval, stiffness_ratio: ratio, f_ext: N interval
    outputs: separation_margin: N, slip_margin: N
    domain:  clamped, linear
```

Modeling-side constructs reference signatures (`model<bolted_joint_state>(...)`);
harness packs provide `impl <signature> by <name>` with cost, error model,
and `domain:`. Neither side sees the other's internals. Signatures are
quantity-core citizens so both domains' packs share one mechanism.
