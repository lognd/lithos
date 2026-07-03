# The Intent Layer

> loom spec 0.10. The highest altitude: no chips, no pins, no nets, no
> buses. The governing distinction, settled in this revision: **intents
> describe the product's boundary; everything interior is derived.**

## 1. Boundary intents vs interior flows

The intent layer answers exactly two questions:

1. **What does the product do at its boundary?** Sense these physical
   quantities, actuate these loads, communicate with these external
   parties, present this human interface. These are product
   requirements; only a human can assert them.
2. **What must happen between those boundary functions?** Computation,
   storage, and information flow -- declared as `flows:` and `compute`/
   `store` intents with quality demands (latency, precision), never
   with mechanism.

Everything else -- which sensor chip, whether the link from the sensor
to the processor is I2C or SPI, which pins, whether two intents fold
into one SoC -- is **interior**, and interior structure is the
compiler's to derive and the lockfile's to report.

The worked consequence (the IMU rule): `sense(orientation, ...)` never
says TWI. Allocation picks an IMU component; its catalog record declares
its **port options** (`twi(400kHz) | spi(<=10MHz)`); the chosen
controller's record declares its bus resources and pin-mux table; the
flow realization solver picks the bus, the controller instance's port,
and the pins -- each choice lockfile-materialized
(`cause: planner(flow sense_att -> decide)`) and each verified by the
ledgers (drive/load, domain, capacity). The designer pins with `use`
only when they actually care.

`communicate` is therefore **reserved for boundary communication** --
links where the other end is not yours (BLE to a phone, RS-485 to a
plant bus, USB to a host). An internal bus is never an intent; if you
find yourself wanting to write one, you are describing mechanism, and
the language will make you either delete it or demote it to a `use` pin
on a flow.

## 2. A complete intent-level system

```
system Thermostat:
    boundary:
        supply:  battery(2 x AA_alkaline)
        ambient: [-10degC, 50degC]
        emc:     residential(CISPR_11_B)
        design_life: 1 yr

    reserves:                        # what targets may consume (sec. 6)
        gpio: 4
        power: 50mW avg

    intents:
        sense_temp: sense(thermo.temperature):
            range:    [0degC, 40degC]
            accuracy: +-0.5K
            rate:     >= 1/min
        decide: compute(hysteresis_law):
            latency: < 1s
            state:   setpoints(32B, persistent)
        report: communicate(ble_peripheral):
            role:     peripheral, bonded
            range:    >= 10m
            payload:  <= 20B at 1/min
        switch_heat: actuate(ac_load(24V, 1A), isolated)

    flows:
        sense_temp -> decide
        decide -> report
        decide -> switch_heat

    require Power:
        life: elec.energy(all, over=design_life)
                  <= supply.capacity(worst_case), sf=1.3
    require Accuracy:
        end_to_end: error(sense_temp -> decide) <= +-0.75K

    budget error_chain: kind=error
        require: end_to_end
        members: [sense_temp, decide]
        allocate: cost_optimal
```

Multi-parameter intents use the block form (colon + indented fields);
one-liners stay inline. Both are the same construct.

## 3. Intent verbs

Verbs are **package-defined** (`std.intents`, extensible per substrate
`11-packages-and-stdlib.md`); each ships a parameter schema in
quantity-core terms, a claim mapping, and a lowering skeleton. The core
set:

| verb | boundary? | declares | lowers to |
|---|---|---|---|
| `sense(q)` | yes | acquire a physical quantity: range, accuracy, rate, bandwidth | transducer contract + acquisition chain; accuracy seeds an error budget |
| `actuate(kind)` | yes | drive a physical load: characteristics, isolation, rates | driver contract + safety claims |
| `communicate(party)` | yes | a link whose far end is external: protocol *class*, range, payload, latency | radio/phy contracts + protocol conformance claims |
| `interact(modality)` | yes | human interface: displays, buttons, indicators | HMI contracts |
| `convert(envelopes)` | yes | power conversion *as the product function* (lab supply, charger) | power-stage contracts |
| `compute(law)` | no | transformation with quality demands: latency, rate, precision, state | a workload (computer track) |
| `store(schema)` | no | retained information: size, persistence, endurance, retention | memory contracts |

From `std.debug` (used by targets, section 6): `indicate(signal)`
(LEDs/beeper), `probe(net_set)` (test points), `debug_access(kinds)`
(SWD/JTAG/UART console).

**Every verb parameter is a claim in miniature.** `accuracy: +-0.5K`
lowers to an error-budget requirement attached to whatever chain
implements the intent; `rate: >= 1/min` to a timing claim; `isolated` to
a creepage/isolation demand on the actuation contract. The intent layer
is not a wish list; it is the top of the obligation tree.

**Energy-harvesting systems** [SETTLED, cycle 7; closes EOPEN-18,
worked in `examples/cubesat/`]:

- `supply:` in `boundary:` is reserved for **definite** electrical
  sources (a battery you are given, a wall adapter, a dc bus). A
  harvesting product instead declares the environmental **resource**
  as ordinary boundary truth, usually profile-structured:
  `illumination: solar(1361 W/m2, profile=spectrum(orbit_sun_ref))`.
- The `convert` verb's schema takes conversion **endpoints**:
  `convert(<from> -> <to>)` (`convert(solar -> dc_bus)`,
  `convert(dc_bus -> rails(3.3V, 5.0V))`), plus efficiency/array
  parameters. The arrow is the flow arrow: a conversion IS a typed
  flow with an efficiency claim attached.
- `store(q)` retains a **quantity** -- information or energy; one
  idea (retention), registered overload. Schema parameters follow the
  quantity: bits get size/persistence/retention; energy gets
  capacity/cycle-endurance/self-discharge
  (`store(energy(20Wh, cycles >= 12000))`).
- Accumulation claims close the loop over a **profile window**
  (substrate `02` sec. 5): `elec.energy(harvest,
  over=boundary.orbit.profile) >= 1.15 * elec.energy(all, over=...)`
  integrates mode-weighted over the period; `budget kind=energy`
  shares are per-period quantities.

## 4. Flows

`a -> b` declares directed information/energy flow, typed by endpoint
schemas (sample streams, events, energy). L2 flow-ledger checks: every
output consumed or explicitly `discard`ed; every input fed; rate
compatibility (a 1/min stream cannot feed a 10Hz law without a declared
rate adapter); accuracy budgets closeable along the chain.

A flow may realize as a trace, a bus transaction, a radio hop, a
shared-memory handoff, or nothing at all (endpoints folded into one
chip). Realization is recorded per flow in the lockfile:
`flow sense_temp->decide: realized=twi0(u_mcu.pb6/pb7 <- u_imu)`.

## 4a. Derived-structure handles [SETTLED, cycle 1]

Claims often need to name interior structure that only exists after
allocation (the radio's supply rail; the sensing chain's analog
output). No net name exists in source -- but the structure was realized
*for* an intent, so it is addressable **through the intent's
namespace**: `report.supply`, `report.tx_burst`,
`sense_temp.chain.out`, `spin.bridge`. Handles resolve at allocation;
an unresolvable handle is a constructive error naming the intent's
realization tree. This is the flow-realization lockfile philosophy
applied to naming: interior structure has no *source* names, but it
has *derived* names with intent-rooted provenance.

## 5. Allocation (intent -> block lowering)

Allocation assigns intents to blocks and blocks to catalog parts or
synthesis, choosing integration granularity. Per the substrate's
conflict-driven search (`07-claims-and-evidence.md` section 7):

- v1 policy remains declared-partition-first: the human may sketch the
  partition (or pin components with `use vendor(...)`); the compiler
  verifies and completes it. Full search is the same machinery with the
  human pins removed.
- **The partition pin has a spelling** [SETTLED, cycle 6, D48 -- the
  Kestrel example forced it]: inline `hosted_on <part>` on an intent
  (`sense_att: sense(geom.orientation) hosted_on adcs: ...`) pins
  which artifact hosts that intent's realization. Same lock-family
  word as synthesized-block hosting -- one idea, "this derived content
  lives on that part" -- rung 2: checks unchanged, lockfile-mirrored,
  spurious failure possible, silent pass impossible. Unpinned intents
  are planner-allocated as before.
- Screens during search are the cheap tier: capability arithmetic
  (does any port-option assignment fit the controller's resources?),
  budget sums (power, error), availability/cost policy.
- Failures backjump by blame set and learn nogoods ("any 1-cell
  supply + this radio's TX burst: droop budget infeasible").

## 6. Targets and reserves

Substrate mechanism (`04-contracts.md` section 6), and the answer to
"debug builds need indicator LEDs without invalidating the product's
verification":

```
target debug of Thermostat:
    intents:
        heartbeat: indicate(decide.status)
        console:   debug_access(swd, uart_log)
        probes:    probe(power_rails)
    draws: reserves
```

Targets only add; they consume declared `reserves:` (GPIO count, power,
board area); base evidence stays valid; `--release` verifies the base
with reserves genuinely spare. The debug LED that steals the pin your
release firmware needed is a compile error, not a bring-up discovery.

## 7. What the intent layer alone can verify (L0->L2)

With zero implementation: flow ledger closure, error/power/latency
budget arithmetic against catalog *classes* (is there any sensor class
meeting +-0.5K in this range?), boundary-protocol feasibility, reserve
accounting, schedulability of declared compute intents against candidate
executor classes. An infeasible product dies here, before anyone draws
anything.
