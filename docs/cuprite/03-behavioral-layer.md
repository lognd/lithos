# The Behavioral Layer: Abstract Blocks, Concrete Realizations

> cuprite spec 0.10. The middle altitude -- the elec binding of L3. An HDL
> superset: the synchronous discrete subset is RTL-equivalent; the
> continuous subset is DAE relations over physical quantities; and --
> new in this revision -- **blocks are contracts, realizations are
> impls**, with equivalence as an obligation.

## 1. Abstract blocks: `block` + `spec:`

A `block` is a **functional contract**: ports, parameters, a behavioral
specification, and claims. It says *what*, never *out of which parts*.
(A block whose spec spans several of its own clock domains also carries
a `connect:` block declaring the crossings -- the crossing is part of
the contract, since without it the spec's cross-domain references would
be E0420; see `examples/elec/fpga_mcu_board.cupr`.)

```
block Mux<sel_w: int = 6, out_w: int = 64>:
    ports:
        sel: digital(in, width=sel_w)
        en:  digital(in)
        out: digital(out, width=out_w)
    spec:
        out = onehot(sel) when en else 0
    promises:
        timing.prop(sel -> out): allocated
```

A 6->64 mux with enable is exactly this: an abstract block. What it is
*made of* -- a synthesized LUT netlist, a tree of 74xx 3->8 decoders, a
vendor part -- is a separate declaration.

`spec:` bodies use two sublanguages, freely mixed:

- **Discrete:** `on <event>:` bodies with non-blocking `<=`; the
  synthesizable subset is deliberately boring. (Renamed from
  `process on` in cycle 1: `process` is [S] regolith vocabulary for
  manufacturing modules and appeared in the same language as
  `stage bare: process=pcb_fab(...)` -- a flagrant one-word-one-idea
  violation. The `on` overload is registered: the context guarding a
  body, spatial (regions) or temporal (events).)
- **Continuous:** DAE relations over quantities (`v(out) ' = (i(l1) -
  i(load)) / C`; `'` = d/dt), Modelica/Verilog-AMS lineage, typed by the
  quantity core -- you cannot add a voltage to a current.

Mixed-signal boundaries (`adc`, `dac`, `comparator` port kinds) declare
the conversion explicitly, with an error contribution that feeds error
budgets.

## 1a. Synchronization semantics [SETTLED in shape, cycle 3; was EOPEN-7]

Event-bounded hybrid semantics, forced by
`examples/elec/sampled_buck.cupr` (continuous plant + sampled control
loop):

1. **Within a clock domain: synchronous-reactive.** All `on <event>:`
   bodies of a domain fire atomically at the event instant; `<=`
   commits at instant end, so every body sees one coherent pre-instant
   state. Combinational `=` networks must be acyclic (compile error).
2. **The continuous subset evolves as a DAE between event instants.**
3. **Coupling is exclusively through converter ports** (`adc`,
   `comparator`, `dac`, `pwm`, clocked `digital` drive), each
   declaring its sampling/update event and its error contribution.
   Reading `v(node)` inside a clocked body without a converter port is
   a compile error naming the port kinds -- the continuous/discrete
   analog of an undeclared clock-domain crossing.
4. **Converters are non-instantaneous by construction**: a sample
   takes the pre-instant continuous value; an update takes effect
   after the instant (ZOH). Algebraic loops across the boundary
   therefore cannot form -- legality needs no causality analysis.
5. **Continuous-to-event**: `v(x).crosses(th)` derived events (quantity
   core) are the zero-crossing mechanism; `comparator` ports are their
   port-kind form.
6. Independent clock domains interact only through crossings and
   converters, so simultaneous-event ordering across domains is
   unobservable.

**Formal sketch** (cycle 4; pays EOPEN-7's residue). Model a design as
a set of SR islands {D_i} (one per clock domain), a continuous system
C, and a set of coupling elements (crossing matings and converter
ports), each with the delta property: its output at instant t depends
only on inputs strictly before t. Define observable state as the
traces at coupling-element outputs. Claim: for any two schedulings of
simultaneous events in independent domains D_i, D_j, observable traces
are identical. Argument: D_i and D_j share no variables (domain
membership is a partition, enforced by typing); every inter-domain
path passes a coupling element; by the delta property, the value a
coupling element emits at t is fixed by pre-t history regardless of
intra-instant ordering; within one domain, SR semantics make the
instant's result order-free by construction (non-blocking commit,
acyclic combinational networks). Hence the composed trace is
schedule-invariant. Corner: a crossing mating with handshake semantics
serializes the two domains' events it relates -- ordering there is
*defined by the mating*, not by the scheduler. EOPEN-7 is closed.

Prior art: Ptolemy's CT+SR composition and hybrid automata -- the
difference is that the *type system* (port kinds, domain frames)
enforces the composition discipline instead of convention.

## 2. Concrete realizations: `impl <Block> by <strategy>`

```
impl Mux by spec                          # synthesize the spec directly
impl Mux by composing as DecoderTree:     # structural: out of other blocks
    then:                                 # (named with `as`, only needed
        root   = Decoder<3, 8>()          #  when several impls coexist)
        leaves = PatternOf<Decoder<3, 8>>(n=8)
    connect:
        sel[0 .. 3] -> leaves.instances.sel        # half-open bit range
        sel[3 .. 6] -> root.sel
        en          -> root.en
        pairwise(root.out.bits, leaves.instances.en)
        flatten(leaves.instances.out) -> out
impl Mux by vendor(nxp_74hc4514_bank)     # purchased
```

- **`by spec`** is legal when the spec lies in the directly realizable
  subset (synthesizable RTL; catalog-mappable passives networks). A
  block with a realizable spec and no explicit impl gets an implicit
  `by spec` -- the common case costs zero ceremony.
- **`by composing`** instantiates other blocks (which recursively have
  their own impls). **Equivalence of the composition to the spec is a
  T3 obligation**: formal equivalence checking for discrete logic;
  analytic or simulation comparison with declared coverage for
  continuous specs (an RC filter's `H(s)` vs its R/C realization
  discharges by AC analysis). Insufficient coverage = `indeterminate`,
  honestly.
- **`by circuit`** realizes a block at component level (the analog
  path). [SETTLED -- shape cycle 1, net discipline cycle 2; worked in
  `examples/elec/buck_converter.cupr`]: circuit bodies instantiate
  *component classes* with value-source parameters
  (`Inductor(l=in [10uH, 47uH], i_sat >= 3A)`) in ordinary
  construction scopes, and join terminals in a `nets:` block
  (`swn: (u1.sw, l1.a)`). Component classes resolve to catalog parts at
  L4 (E-series snapping, availability policy).

  **The analog net discipline** [SETTLED for v1, cycle 2; resolves
  EOPEN-16]. Relational (KCL) nets do not fit the digital
  single-driver ledger; instead, four static checks at L3:
  1. *Terminal ledger*: every terminal of every instantiated component
     appears in exactly one net; intentionally unconnected terminals
     are `discard`ed (registered overload: explicit sink for an
     intentionally unconsumed output or terminal).
  2. *Reference reachability*: every net conductively reachable to a
     `reference` port (catches isolated islands).
  3. *At most one voltage-imposing terminal* (`supply(out)`) per net;
     paralleling supplies requires `arbitrate ... parallel(<share
     discipline>)`.
  4. *Supply shorts*: two distinct `supply(out)` nets joined is an
     error in supply vocabulary.
  Beyond these static checks, KCL/DAE well-posedness of the continuous
  system between event instants (index, solvability) is a harness
  concern under the settled event-bounded semantics (sec. 1a): an
  ill-posed DAE is an `indeterminate` discharge naming the net set,
  never a silent pass.
- **`by vendor`** discharges equivalence and promises by catalog
  evidence.
- **`by extern(ref, format)`** links a foreign source or netlist as
  the realization (hand-written Verilog, a SPICE deck, an encrypted IP
  block) -- regolith `08-lowering-architecture.md` section 4.
  Transparent formats elaborate into this layer and get the full
  static tier plus the ordinary equivalence obligation; opaque ones
  enter measured-or-evidenced at L4. Hand-written does not mean less
  checked.
- Multiple impls of one block may coexist (per target, per assembly
  choice); selection is the ordinary `use <impl>` pin, lockfile-caused.

This is the regolith interface/impl story verbatim (regolith
`04-contracts.md`, behavioral specifications) -- buy-vs-build, and
abstract-vs-concrete, are one mechanism.

## 3. Ports are contract roles

Port kinds: `supply(in|out, v, i)`, `reference`, `analog(q, range, z)`,
`digital(family, dir, width)`, `clock(f, domain)`, `bus(class)`,
`adc/dac/comparator`. Supply ports carry direction (a converter's
output rail is `supply(out, 5V +- 2%, i <= 2A)`; cycle 1). Every
electrical value is interval-capable (`3.3V +- 5%` is one value);
direction, domain membership, drive/load envelopes, and protocol class
are part of the type. Pins do not exist at this layer. Parameters
follow the regolith rule (`04-contracts.md`): `<...>` are
caller-chosen, `params:` are impl-chosen (existential in `spec:`).

## 4. Ownership, domains, connection

- **Single driver.** Each signal/net has exactly one driving `on` body,
  relation, or port. Multiple drivers = borrow conflict naming both.
  Shared drive (tri-state bus, open-drain wired-AND) requires
  `arbitrate` declaring the discipline -- which becomes a checkable
  claim (no two drivers enabled), not a hope.
- **Clock and voltage domains are frames.** Registered signals belong to
  their clock's domain; crossing without a declared crossing mating
  (`cdc_sync`, `async_fifo`, `level_shift`) is `E0420`-family at L3.
  Reset and power-domain membership are declared, not idiomatic.
- **Connection is by contract** (`connect:` matings), never by drawn
  wire. Floating inputs are compile errors; intentionally unused outputs
  are `discard`ed explicitly.
- **Orbit connections** [SETTLED, example-driven -- the mux composition
  needed them]: connecting instance sets has exactly three forms, all
  cardinality-checked statically:
  - *broadcast*: `scalar -> set.role` fans one source to every instance
    (fanout enters the drive ledger as the full set);
  - *zip*: `pairwise(set_a, set_b)` connects two equal-cardinality sets
    element-wise in their shared layout order (a checked join; unequal
    or unordered sets are compile errors);
  - *flatten*: `flatten(set.port) -> bus` concatenates per-instance
    ports into one bus in layout order (total width checked).
  Positional index wiring of *entity sets* does not exist, consistent
  with the no-index rule everywhere else. **Bus bit ranges are the
  blessed exception** (cycle 1): `sel[0 .. 3]` (half-open) addresses
  bits by *semantic* position -- a bit's binary weight or protocol lane
  is content, not creation-order accident -- and a slice splits the bus
  orbit like any special-role assignment. A width'd port's per-bit set
  is `.bits`.

## 5. The hardware-bug ledger

The bring-up bug taxonomy and the mechanism that makes each one a
compile-time or verification-time failure instead of a lab discovery:

| classic bug | killed by | tier |
|---|---|---|
| floating input / unconnected gate | every-input-fed ledger | L3 |
| two drivers fighting | single-driver ownership | L3 |
| level mismatch (1.8V out -> 3.3V CMOS in) | family fit check (VOH/VIH margin intervals) | L2 |
| fanout / bus capacitance vs edge or clock rate | connection capability: C_bus summed from member + route contributions, demand <= driver capability | L3 eager, L4 recheck on extracted parasitics |
| missing pull-up on open-drain bus | the bus mating *demands* a pull-up role; unbound role = error | L2 |
| I2C speed class vs bus RC | rise-time claim from pull-up value x C_bus interval | L5 (cheap RC model) |
| clock-domain crossing | domain frames + crossing ledger | L3 |
| power-sequencing violation | sequencing mask claims (`stays_within(.., mask, during startup)`) + supervisor demands | L5 |
| floating/wrong boot straps | component contracts declare `strap` roles; every role bound or explicitly defaulted | L2 |
| missing/starved decoupling | power-port demands (`decoupling: >= 100nF within 5mm`) -- presence at L3, proximity at L4 | L3/L4 |
| no return path under fast edges | return-path rule pack (eager, geometric) at L4; field solver when margins thin | L4/L5 |
| unterminated line vs edge rate | edge-rate x length rule -> termination demand | L4 |
| absolute-max under transient (inductive kick) | transient claims at corners | L5 |
| ESD on boundary connectors | boundary `emc:`/environment class -> protection demands on boundary-facing ports | L2 |
| brownout during radio burst | droop budget at worst corner (battery internal R interval, cold) | L5 |

Design rule for the stdlib: **every entry in this table must be owned by
a mating demand, a ledger, a rule pack, or a claim template** -- never by
designer vigilance. New bug classes get a row and an owner before they
get a workaround.

## 6. Symmetry and instances

Buses, identical channels, decoupling banks are orbits; `x.instances.any`
follows regolith rules; verify-one-instantiate-n discharges identical
channels. Assigning bit 0 a special role splits the orbit, exactly like
binding one hole of a mech pattern.

## 7. Waveform profiles (from the mech sketch machinery)

Masks and stimulus profiles reuse the profile idea: piecewise
segment sequences (`from_table`/`from_fn`, parameterizable; power-up
sequences, eye masks, test stimuli). They are values consumed by
claims (`stays_within`) and harness models. Full constraint-solving
over waveforms (the mech walk + DOF ledger analog) is **retired**
[cycle 5, D46; closes EOPEN-4]: every observed case -- sequencing
masks, eye masks parameterized by data rate, parameterized ramps --
is a `from_fn`/`from_table` mask with parameters, no solved
constraint system needed. Reopen only on a failing example (a mask
whose segments must be *solved for* jointly under claims).
