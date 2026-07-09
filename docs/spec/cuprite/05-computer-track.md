# The Computer Track

> cuprite spec 0.10. Computation as a designed artifact. A vocabulary pack
> over the same altitudes: workloads (intent) -> architecture of promised
> capabilities (contract) -> implementation you buy or build (behavioral/
> structural) -> firmware as a realized, measured artifact.

## 1. Workloads (intent altitude)

Workloads are the boundary truth of computation -- demand, declared
implementation-free:

```
computer FlightController:
    workloads:
        control:   loop(rate=1kHz, work=200kops f32, jitter <= 50us,
                        state: 64kB)
        estimator: loop(rate=500Hz, work=1.2Mops f32)
        telemetry: stream(out, 20kB/s, latency <= 100ms)
        logging:   stream(store, 100kB/s, retention >= 2h)
        events:    event(rate <= 200/s, deadline 2ms)      # RC input, failsafe
    require Timing:
        control_deadline: info.latency(control) < 1ms, sf=2
    require Capacity:
        headroom: info.utilization(all) <= 60%
```

- Kinds: `loop` (periodic), `stream` (throughput + latency), `event`
  (sporadic + deadline), `batch`. Parameters are claims in miniature,
  like intent verbs.
- **Intent linkage** [SETTLED, cycle 2; resolves EOPEN-15]. Three
  rules, all L2 arithmetic:
  1. `realizes <intent>[, <intent>...]` claims a workload serves those
     compute intents. A workload may realize several; every compute
     intent must be realized by **exactly one** workload across the
     system's computers -- a ledger, like flows.
  2. The workload must *imply* each realized intent's demands.
     Rates and state compare directly (rate >= intent rate; state >=
     intent state). Latency reconciles through the flow ledger's
     latency budget -- an intent's latency is end-to-end over its
     flow chain, so the check is workload latency + realized
     transport latencies <= intent latency (the same machinery as
     accuracy chains; naive "workload <= intent" would be
     under-conservative -- audited in cycle 4, F55). Failure is an
     E04xx naming both sides. Demand flows down; a workload cannot
     weaken it.
  3. An unrealized compute intent is completed by allocation as a
     **derived workload**: the intent's demands copied verbatim
     (conservative), lockfile `cause: derived(intent <name>)`.
  Standalone `computer` artifacts (no enclosing system) declare
  workloads directly, as below.
- `work` is typed operation counts (`200kops f32`) -- the computational
  load case: interval-friendly, implementation-free. Unknown work is
  `assume!(work <= ..., basis="profiled on eval board")`; profiling
  reports are `by test` evidence that later replaces the assumption.
- Peripheral needs arrive from the system's flows (an IMU attach, four
  PWM outputs, one boundary radio), not from workload declarations --
  the intent layer feeds this track.

## 2. Architecture (contract altitude)

Execution resources are **abstract blocks with promises** -- `executor`,
`memory`, `mover`, `fabric` are stdlib block contracts:

```
architecture for FlightController:
    resources:
        cpu0: executor(promises: >= 4Mops f32 sustained,
                       context_switch <= 5us)
        dma:  mover(promises: >= 1MB/s, independent of cpu0)
    memories:
        sram:  memory(64kB, promises: latency <= 2 cycles)
        flash: memory(2MB, persistent, endurance >= 1e5 cycles)
    peripherals:                     # demand vector, derived from flows
        buses: spi(>= 8MHz) x 1, twi x 1
        timers: pwm x 4
        analog: adc(12bit, >= 10ksps) x 2
    schedule:
        control -> cpu0: static_priority(highest)
        estimator -> cpu0
        telemetry -> dma
```

L2 verification on promises alone -- the track's ledger:

- **Schedulability**: utilization bounds and response-time analysis
  (closed-form harness models); `forall mode:` when modes exist.
- **Capacity sums**: memory, bandwidth on movers and fabric.
- **Peripheral matching**: the demand vector against candidate resource
  bundles (feasibility now, concrete pin-mux later at L4).
- Jitter claims against promised preemption/context-switch bounds.

An infeasible workload set dies here, before any silicon is chosen --
the DOF-ledger moment of this track.

## 3. Implementation (binding)

Contract substitution, per the abstract/concrete block rules, grouped in
a `bind` block so the buy/build decision is one reviewable unit
(example-driven; see `examples/tracks/cuprite/flight_controller.cupr`):

```
bind FlightController:
    cpu0  = vendor(stm32g474)
    dma   = vendor(stm32g474).dma.instances.any
```

- **Buy:** `cpu0 = vendor(stm32g474)`. The record's promises (benchmark-
  backed ops/s `by test(coremark_ref)`, memory, peripheral bundle with
  pin-mux tables) discharge the architecture demands with catalog
  evidence. On-chip peripherals are sub-interfaces in orbits
  (`uarts.instances.any`).
- **Build:** `cpu0 = impl Executor by spec` -- a soft core (RTL spec)
  synthesized at L4; promises discharged by synthesis-report models
  (fmax, utilization) and equivalence obligations for its spec.
- **Mixed** is normal: MCU + FPGA coprocessor under one contract system;
  ISA compatibility is `refines` (rv32imc refines rv32i), so a core
  upgrade is a checked substitution.
- **Host binding** [SETTLED, cycle 6; closes EOPEN-17]: which
  programmable part hosts a `by spec` impl is an allocation decision --
  capability matching like pin-mux: synthesis-estimate demand vectors
  (LUT/FF/BRAM/DSP, IO count per standard) against the part record's
  resource table. **IO banking** is part of the match: each hosted
  port's IO standard and voltage domain must be satisfiable by some
  bank assignment -- banks are per-bank capability records (standards,
  Vccio, pin count) in the part record, and the assignment is
  lockfile-caused like pin-mux. Pinned with `hosted_on`; lockfile
  `cause: planner(host ...)`. Settled by the second worked example
  (`examples/systems/cubesat/payload.cupr`: sub-LVDS lanes and 3.3V SPI forced
  onto two DIFFERENT banks of one part) after the frame grabber's
  first. Multi-FPGA floorplanning and partial reconfiguration remain
  out of v1.
- **Prebuilt firmware links, too**: `image fw: extern("fw.elf", elf)`
  enters at L4 with the map data as its measured entity DB (regolith
  `08` section 4) -- fit/stack/WCET claims run on the linked binary
  exactly as on a toolchain-realized one.

## 4. Firmware as a realized artifact

The `programmed` stage loads an image; the image is itself an artifact
with an L4 "measured entity DB" -- the toolchain is its realizer:

```
image ctl_fw:
    realizes: schedule(FlightController)      # the binding contract
    toolchain: gcc_arm(13.2, -O2)             # hash-pinned
    require Resources:
        flash_fit: size(text+ro) <= partitions.app.size   # explicit .size;
                                                          # no region->size coercion
        stack:     info.stack_depth(control) <= 8kB
        wcet:      info.wcet(control, on=cpu0) <= 600us
```

- Map files, static stack analysis, and WCET analysis are **harness
  models over the compiled image** (with error models: WCET bounds are
  conservative by construction; measured traces are `by test`).
  "It'll probably fit" becomes a discharged, violated, or indeterminate
  claim like any other.
- Memory maps are declared as `partitions:` on the image (`boot:
  flash[0 .. 32kB]`) -- owned regions under the region-ownership
  machinery; two DMA buffers or partitions contesting a range is a
  borrow conflict, not a heisenbug. Unpartitioned remainder follows the
  `remainder` rule from zones.
- Boot and bring-up are time-domain claims spanning hardware and
  firmware: `within 500ms after supply.on: report.alive`, verified
  against the sequencing masks and the schedule.

Application logic beyond declared workloads stays out of scope
(EOPEN-6 closed, cycle 8, D70 -- a consequence of the host-language
ban, D60): v1 verifies the *platform* -- that the declared demands
fit, schedule, and boot -- with image-level evidence; it does not
synthesize your control law, and a workload body never becomes a
program in design source.

## 4a. Firmware codegen (D109, WO-37)

The design-determined layer of firmware -- pin configuration,
peripheral init, clock setup, ISR vectors, the linker memory map -- is
a GENERATED, content-addressed artifact, never hand-copied from the
design (`regolith.realizer.firmware`, WO-37):

- **The hardware contract header** (`<design>_contract.h`) is the
  load-bearing piece: symbolic constants for every pin assignment
  (from the pin-mux planner, cuprite/04 sec. 1 step 2), clock, event,
  and `partitions:` region, each carrying a provenance comment naming
  its lockfile cause. Application code (any language) references the
  design only through these symbols, so a re-plan BREAKS COMPILATION
  instead of silently misbehaving (the anti-staleness property).
- **BSP sources** (C) translate the pin-mux/binding lockfile rows
  through an MCU-FAMILY PACK (vendor HAL/register idiom as signed
  pack content, never regolith-core vendor strings); ISR vector stubs
  are typed from the event ledger and call user-provided hooks only
  -- zero application logic in any generated file.
  A design whose family has no pack is honest indeterminate on the
  codegen step, never a guess.
- **The linker memory map + build fragment** come from the image's
  declared `partitions:`; the built image re-enters through the
  EXISTING `image`/`extern` hash-pin machinery of sec. 3-4 above --
  fit/stack/WCET/boot claims verify it unchanged. This adds zero new
  claim vocabulary.
- **Cross-language bindings** are generated FROM the contract header
  (one source of truth): a Rust `-sys`-shaped binding ships behind an
  opt-in flag; other languages are follow-on demand, same rule.
- Generation runs at realize time; the ship backend (WO-25) records
  the generated tree's content hash in the ship manifest, same as any
  other realized artifact.

## 5. Why this belongs in the same language

- One claim chain spans domains: load inertia (mech) -> control
  bandwidth -> loop rate -> schedulability -> silicon choice -> pin-mux
  -> layout. Today it lives in five documents; here it is one
  lockfile-visible derivation, and editing the inertia re-verifies
  exactly the chain below it.
- Buy-vs-build for compute is the same vendor-vs-designed contract
  substitution as bearings and muxes.
- Margin-driven discharge gives sizing its missing discipline: fat
  utilization headroom discharges with arithmetic; thin headroom forces
  RTA, then WCET analysis, then measurement -- automatically.
