# The cuprite guide (electrical + computer design)

cuprite describes electrical and computational artifacts the same way
hematite describes mechanical ones: contracts and claims first,
realization derived. If you read the hematite guide, most of this
language is already familiar -- the load-bearing words are shared
regolith vocabulary. This guide covers what is elec-specific.
Normative sources: `docs/spec/cuprite/` 01-08 (esp.
`07-vocabulary-sketch.md`), `docs/spec/regolith/`.

## 1. The altitude ladder

cuprite works at three altitudes, and you choose per problem:

1. **Intent** (`system`): WHAT the product does -- sense, actuate,
   communicate, convert -- with flows and budgets. Architecture is
   derived.
2. **Behavioral** (`block` + `spec:`): WHAT a subsystem does over
   its domain -- regulation laws, logic, timing -- with
   implementations proven equivalent.
3. **Structural** (`impl by circuit`, `board`): the actual
   components, nets, and physical board -- still contract-checked.

You can enter at any altitude; a real design mixes them.

## 2. Blocks and specs (the behavioral layer)

```
block Buck<v_out: voltage = 5.0V, i_max: current = 2A>:
    ports:
        vin: supply(in, [7V, 24V])
        out: supply(out, v_out +- 2%, i <= i_max)
        gnd: reference
        en:  digital(in, family=cmos_3v3)
    params:
        f_sw: frequency = in [300kHz, 1.2MHz]   # impl-chosen
    spec:
        forall i(out) in [0A, i_max], v(vin) in [7V, 24V]:
            v(out) = v_out +- 2%
    event load_step: step(i(out), 1A/us)
    require Regulation:
        ripple:    rms(v(out), band=[100kHz, 10MHz]) < 20mV
        transient: settles(v(out), to=+-2%, within 500us after load_step)
```

- `<...>` parameters are CALLER-chosen; `params:` are IMPL-chosen
  (the implementer picks `f_sw` anywhere in the window).
- `ports:` are contract roles, not pins: `supply(in|out)`,
  `reference`, `analog()`, `digital(family=)`, `clock()`, `bus()`,
  `adc/dac/comparator`. There are NO pin numbers in source, ever.
- `spec:` is the behavioral truth any impl must satisfy. Discrete
  bodies are `on <event>:` (clocked, `<=` non-blocking, an
  RTL-equivalent subset); continuous bodies are `continuous:` (DAE
  relations, `'` = d/dt).
- `event` declares time datums; claims use the shared window/mask
  vocabulary (`during`, `within .. after`, `stays_within(mask)`).

## 3. Impls (realization strategies)

```
impl Buck by circuit:
    then:
        u1    = vendor(tps54331)
        l1    = Inductor(l=in [10uH, 47uH], i_sat >= 1.3 * i_max)
        c_out = Capacitor(c=in [22uF, 100uF], v_rated >= 10V, x7r)
        fb    = ResistorDivider(ratio=derived, z=in [10kohm, 100kohm])
    nets:
        swn:  (u1.sw, l1.a)
        outn: (l1.b, c_out.a, fb.top, out)
        gndn: (gnd, c_in.b, c_out.b, fb.bottom, u1.gnd)
```

The strategies: `impl <Block> by spec` (realizable specs get this
implicitly -- synthesis realizes it), `by composing` (out of other
blocks), `by circuit` (components + `nets:`), `by vendor(ref)`
(catalog part), `by extern(ref, fmt)` (foreign Verilog/netlist,
checked against the contract, never merged). Equivalence of any impl
to its `spec:` is an ordinary obligation -- a contradicting impl
FAILS the build.

Net discipline (v1): terminal ledger (everything connected or
explicitly `discard`ed), reference reachability, one voltage-imposer
per net, supply-short check. Shared drive is never an accident:
`arbitrate` declares tri-state / open-drain wired-AND /
`bidir(granted_by=)` / `parallel(<share>)`.

## 4. Systems and intents

```
system Kestrel:
    intents:
        downlink: communicate(radio, >= 9.6kbit/s)
        imaging:  sense(image, 5MP, hosted_on payload_pcb)
    flows:
        imaging -> downlink
    boundary:
        supply: battery(2 x AA_alkaline)
        ambient: [-20degC, 60degC]
    reserves:
        mass: 50g
    budget power: kind=power
        members: [radio, mcu, payload]
        allocate: cost_optimal
    require Link:
        margin: elec.link_margin >= 6dB
```

- Boundary verbs (`sense`, `actuate`, `communicate`, `interact`,
  `convert`) declare product functions; interior verbs (`compute`,
  `store`) declare demands. Internal buses are DERIVED from flows,
  never declared.
- `hosted_on <part>` pins where derived content lands (otherwise the
  planner allocates); `discard` is the explicit sink for unconsumed
  outputs and unconnected terminals.
- `target <name> of <system>` overlays debug/bring-up content
  (`indicate`, `probe`, `debug_access`), consuming declared
  `reserves:` -- a flatsat without touching the flight design.

## 5. Computers, workloads, images

The computational track types computation like everything else:

- `computer`: workloads + architecture + bindings.
- `workloads:` declare demands as `loop` / `stream` / `event` /
  `batch` with quality parameters; `realizes <intent>` ties each to
  the compute intents it serves (exactly-one-realization is
  ledger-checked).
- `architecture`: promised resources (`executor`, `memory`, `mover`,
  `fabric`), a `peripherals:` demand vector, `schedule:`.
- `image`: the firmware artifact realizing a schedule contract;
  map/stack/WCET enter as MEASURED truth from the toolchain.
  `partitions:` owns memory-map regions (`app: flash[32kB .. 1MB]`).
- `bind <computer>:` groups the resource-to-implementation decisions
  into one reviewable block; `board` stages include
  `load(image_ref)` as a hash-pinned construction step.

## 6. What is deliberately absent

No pin numbers. No positional port maps. No `X`/`Z` logic values
(unknowns are modeling gaps -> indeterminate evidence; high-Z is an
`arbitrate` state). No side-file timing constraints. No freehand
wire drawing -- connection is by contract only.

## 7. Elec-specific vocabulary (learning view)

Normative: `docs/spec/cuprite/07-vocabulary-sketch.md`. Everything in the
hematite guide's shared tables ([S]) applies verbatim: claims,
value sources, queries, budgets, waive/policy/override, `interface`/
`mating` contracts. Elec adds:

### Registries

| keyword | purpose |
|---|---|
| `component` | catalog part: datasheet limits as intervals, derating, packages |
| `family` | logic family / IO standard (voltage windows, drive classes) |
| `protocol` | bus/link contract pack (roles, timing, conformance claims) |

### Intent layer

| keyword | purpose |
|---|---|
| `system` / `intents:` | top artifact and its named functions |
| `sense`, `actuate`, `communicate`, `interact`, `convert` | boundary verbs |
| `compute`, `store` | interior demand verbs |
| `indicate`, `probe`, `debug_access` | debug intents (inside targets) |
| `flows:` (`a -> b`) / `discard` | typed flows; explicit sinks |
| `workloads:` (`loop`/`stream`/`event`/`batch`) / `realizes` | computation demands and their intent ties |
| `hosted_on <part>` | pin derived content to a host |
| `computer` / `architecture` / `image` / `partitions:` / `bind <c>:` | the computational artifacts |

### Behavioral layer

| keyword | purpose |
|---|---|
| `block` / `ports:` / `params:` / `spec:` | abstract functional contract |
| `supply(in|out)`, `reference`, `analog()`, `digital()`, `clock()`, `bus()` | port roles |
| `on <event>:` / `continuous:` / `reset <event>` | discrete and continuous behavior |
| `impl ... by spec / composing / circuit / vendor(ref) / extern(ref, fmt)` | realization strategies |
| `nets:` / `arbitrate` | terminal joins; declared shared drive |
| `domain` | clock/voltage domain declaration |
| `strap` | boot/config pin role (bound or defaulted, never floating) |
| `board` / `load(image_ref)` | the physical artifact; pinned programming step |

### The converter graph (behavioral topology)

A `spec:` body with converter ports (`adc`/`comparator`/`dac`/`pwm`)
and clocked `on <clk>:` updates compiles to a **converter graph**:
domain-tagged signal nodes (one continuous frame plus one island per
clock) and kind-tagged dependency edges (combinational, converter, or
register). The compiler builds it to enforce INV-16 (no algebraic loop
crosses the continuous/discrete boundary) and, since WO-88, carries it
across the FFI on `BuildPayload.converter_graphs` (keyed by block name)
so a verification model reads a design's switching topology -- the
pwm/dac-driven switch node, the adc/comparator-sampled feedback node,
and the switching clock -- from the compiled graph instead of assuming
it. The buck model family (`std` `elec.buck.*`) consumes this: a
resolvable `converter_graph` payload confirms the switching-converter
topology; a design with no behavioral body keeps its hand-supplied
operating point. Nothing you author changes -- this is a compiler
output surface.

### Contract promise slots

| slot | purpose |
|---|---|
| `drive:` | output capability (source/sink, edge rates) |
| `timing:` | setup/hold/prop relative to a clock frame |
| `power:` | consumption envelope per mode |
| `protocol:` | conformance against a `protocol` pack |

Stdlib matings: `NetBind`, `BusAttach<proto>`,
`LevelShift<fam_a, fam_b>`, `cdc_sync`/`async_fifo`, `SupplyRail`,
`ConnectorMate<series>`.

### Elec selectors

| form | purpose |
|---|---|
| `nets.where(domain=, kind=)` | net queries |
| `x.instances.any` | orbit-checked channel selection |
| `routes(net_set)` / `.coupled_to(net)` | routed-geometry entities (L4) |
| `flatten(set.port) -> bus` / `port.bits` / `bus[i .. j]` | bus construction and semantic bit ranges |

## 8. Worked corpus tour

- `elec/buck_converter.cupr` -- block/spec/impl-by-circuit (this
  guide's example, complete).
- `elec/frame_grabber.cupr` -- `hosted_on`, IO banking.
- `cubesat/` -- a full system: four boards, FPGA payload, firmware
  image, flatsat target, cross-language contracts with the
  structure. Read `kestrel.cupr` last; it is the payoff.
