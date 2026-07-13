# Package documentation

## `examples/flagships/cubesat/adcs.cupr`

- [board `AdcsPcb`](#board-adcspcb)

<a id="board-adcspcb"></a>
### board `AdcsPcb`

Claims:

- `Actuation`:
  - `dipole` -- (unbuilt):

    ```
    forall ch in coils.instances:
                          elec.dipole(ch) >= 0.18 A*m2
    ```

  - `no_stuck` -- (unbuilt):

    ```
    within 50ms after fault(u_drv.instances.any):
                          state(u_drv.instances.all) = coast
    ```

- `Sensing`:
  - `mag_floor`: `rms(b(u_mag), band=[0.1Hz, 10Hz]) < 30nT` -- (unbuilt)

## `examples/flagships/cubesat/antenna.hema`

- [interface `PivotBore`](#interface-pivotbore)
- [part `DeployerBody`](#part-deployerbody)
- [assembly `Antenna`](#assembly-antenna)

<a id="interface-pivotbore"></a>
### interface `PivotBore`

- `frame`:

  ```
  origin: bore.axis
          z: bore.axis
  ```

- `roles`: `bore: cylindrical(d=d), internal`
- `tolerances`: `bore: tol_class(H7)`

<a id="part-deployerbody"></a>
### part `DeployerBody`

- `material`: `AL6061_T6`

<a id="assembly-antenna"></a>
### assembly `Antenna`

Claims:

- `Stowed`:
  - `retention` -- (unbuilt):

    ```
    peak(mech.force(hold), during boundary.launch)
                           < loop.rated_tension / 2.0
    ```

  - `no_rattle` -- (unbuilt):

    ```
    mech.gap(element.tip, body.channel) <= 0.15mm
                           during deploy = stowed
    ```

- `Deployment`:
  - `torque` -- (unbuilt):

    ```
    forall root.theta:
                         mech.torque(element.root) >
                             2.5 * mech.friction_torque(root)
                             during deploy = released
    ```

  - `settle` -- (unbuilt):

    ```
    settles(root.theta, to=90deg +- 2deg,
                         within 3s after release_event)
    ```

- `Deployed`:
  - `pattern_clear` -- (unbuilt):

    ```
    mech.envelope(element, during deploy = deployed)
                               inside keepout(solar_array) = none
            # crossing envelope vs owned region: the deployed element must
            # not sweep the array's keepout -- region machinery at L4

        # WO-105 release residuals (D206/D207): memo-backed accepted
        # deviations; verdicts untouched (INV-2). See memos/release-residuals.md.
    ```


## `examples/flagships/cubesat/comms.cupr`

- [board `CommsPcb`](#board-commspcb)

<a id="board-commspcb"></a>
### board `CommsPcb`

Claims:

- `Rf`:
  - `pa_out`: `elec.power(assembled.rf_conn) >= 26dBm during op = downlink` -- (unbuilt)
  - `harmonics`: `stays_within(emissions, mask=fcc_part25)` -- (unbuilt)
- `Deploy`:
  - `burn_energy`: `elec.energy(q_burn.out, over=burn_pulse) >= 4J, sf=2` -- (unbuilt)
  - `one_shot`: `forall op: state(release) = held until fired(burn_pulse)` -- (unbuilt)

## `examples/flagships/cubesat/contracts.cupr`

- [interface `AntennaPort`](#interface-antennaport)
- [interface `CardBay`](#interface-cardbay)
- [interface `StackCard`](#interface-stackcard)
- [interface `StackHarness`](#interface-stackharness)
- [interface `Umbilical`](#interface-umbilical)
- [mating `AntennaMate`](#mating-antennamate)
- [mating `CardMount`](#mating-cardmount)
- [mating `StackMate`](#mating-stackmate)

<a id="interface-antennaport"></a>
### interface `AntennaPort`

- `frame`: `gnd: reference`
- `roles`:

  ```
  rf:      analog(elec.power, z=50ohm)     # the coax role
          release: discrete({held, released})      # the burn-wire linkage
  ```

- `demands`: `rf: geom.position(+-0.3mm, to=frame)`

<a id="interface-cardbay"></a>
### interface `CardBay`

- `frame`:

  ```
  origin: posts.pattern_center
          z: posts.plane.normal
  ```

- `roles`: `posts: geom.boss_pattern(tapped=M3, n=4, rect(90mm x 90mm))`
- `promises`: `thermal.sink: conductive, >= 0.5 W/K   # card-to-rail conduction`

<a id="interface-stackcard"></a>
### interface `StackCard`

- `frame`:

  ```
  origin: mounts.pattern_center     # kit-derived datums
          z:      outline.normal
          gnd:    reference                 # elec reference node
          logic:  domain(3.3V)              # voltage-domain frame entry
  ```

- `roles`:

  ```
  # mech-facing roles, quantity-core spelling (F76):
          outline: geom.plate(96mm x 96mm, t=1.6mm)
          mounts:  geom.hole_pattern(dia 3.2mm, n=4, rect(90mm x 90mm))
          conn:    connector(stack_50, at=geom.point(x=-40mm, y=0mm))
          # elec-facing roles (a card CONSUMES the rails):
          v3v3:  supply(in, 3.3V +- 3%, i <= 1.5A)
          vbatt: supply(in, [6.4V, 8.4V], i <= 2A)
          sys:   bus(i2c(fast))
  ```

- `demands`:

  ```
  mounts: geom.position(+-0.1mm, to=frame)
          conn:   geom.position(+-0.15mm, to=frame)
  ```

- `promises`:

  ```
  mass:  <= 90g                     # per-card ceiling; impls refine
          power: allocated                  # share of the energy budget

      # WO-105 release residuals (D206/D207): memo-backed accepted
      # deviations; verdicts untouched (INV-2). See memos/release-residuals.md.
  ```


<a id="interface-stackharness"></a>
### interface `StackHarness`

- `frame`:

  ```
  gnd:   reference
          logic: domain(3.3V)
  ```

- `roles`:

  ```
  v3v3:  supply(out, 3.3V +- 3%, i <= 4.5A)
          vbatt: supply(out, [6.4V, 8.4V], i <= 6A)
          sys:   bus(i2c(fast))
  ```

- `demands`: `sys: pullup(scl): required, pullup(sda): required`

<a id="interface-umbilical"></a>
### interface `Umbilical`

- `frame`: `gnd: reference`
- `roles`:

  ```
  chg:  supply(in, [7V, 9V], i <= 1.5A)
          dbg:  bus(uart(115200))
          rbf:  discrete({inhibit, flight})        # remove-before-flight
  ```


<a id="mating-antennamate"></a>
### mating `AntennaMate`

- `between`: `a: AntennaPort, b: AntennaPort`
- `align`: `a.frame = b.frame (contact)`
- `couples`: `a.release = b.release        # state coupling across the joint`

<a id="mating-cardmount"></a>
### mating `CardMount`

- `between`: `a: CardBay, b: StackCard`
- `align`: `a.frame = b.frame (contact)`
- `dof`: `removed=[all]`
- `effects`:

  ```
  model<bolted_stack_conduction>(n=4, torque=0.5 N*m)
              applies -> a: heat(b.power_dissipated)

  # ---- Antenna: RF + release linkage in one contract.
  ```


<a id="mating-stackmate"></a>
### mating `StackMate`

- `between`: `a: StackHarness, b: StackCard`
- `align`: `a.frame = b.frame (gnd shared, logic shared)`
- `couples`: `a.sys = b.sys                # one bus, many cards`
- `capability`: `i_3v3: per harness promise, summed over cards`

Claims:

- `State`:
  - `no_contention`: `arbitration(a.sys.sda) = lossless` -- (unbuilt)

## `examples/flagships/cubesat/eps.cupr`

- [system `Eps`](#system-eps)
- [board `EpsPcb`](#board-epspcb)

<a id="system-eps"></a>
### system `Eps`

- `intents`:

  ```
  harvest: convert(solar -> dc_bus):
              array:  4 x panel(80mm x 80mm, eff >= 28%)
              mppt:   required
          store: store(energy(20Wh, cycles >= 12000)):
              chemistry_class: li_ion
          feed: convert(dc_bus -> rails(3.3V, 5.0V)):
              eta: >= 88%
  ```


Claims:

- `Battery`:
  - `temp_window` -- (unbuilt):

    ```
    thermo.temperature(store.cells) within [0degC, 45degC]
                              during chg = bulk
    ```

  - `dod`: `elec.depth_of_discharge(store) <= 30%` -- (unbuilt)
  - `never_flat`: `forall op: elec.min(v(store.cells.any)) > 3.0V` -- (unbuilt)
- `Harvest`:
  - `worst_orbit` -- (unbuilt):

    ```
    elec.energy(harvest, over=boundary.illumination.profile)
                             >= 1.15 * elec.energy(all,
                                    over=boundary.illumination.profile)
            # profile windows are quantity-core vocabulary (substrate 02
            # sec. 5; F78 -> EOPEN-18 closed): mode-weighted integration
            # over one period, worst-case phase by corner discipline

        # WO-105 release residuals (D206/D207): memo-backed accepted
        # deviations; verdicts untouched (INV-2). See memos/release-residuals.md.
    ```


<a id="board-epspcb"></a>
### board `EpsPcb`

Claims:

- `Protection`:
  - `ovp`: `stays_within(v(vbatt), mask=cell_ovp(4.2V, 2))` -- (unbuilt)
  - `ocp`: `within 10us after overcurrent: state(sw_pl) = open` -- (unbuilt)
  - `rbf_kill`: `elec.power(all) <= 50uW during rbf = inhibit` -- (unbuilt)

## `examples/flagships/cubesat/kestrel.cupr`

- [system `Kestrel`](#system-kestrel)
- [computer `FlightCore`](#computer-flightcore)
- [decl `architecture`](#decl-architecture)
- [decl `bind`](#decl-bind)
- [image `flight_fw`](#image-flight-fw)
- [target `flatsat`](#target-flatsat)

<a id="system-kestrel"></a>
### system `Kestrel`

- `reserves`:

  ```
  mass:  80g
          power: 150mW avg
          gpio:  4
  ```

- `intents`:

  ```
  # Partition pins are the D48 inline `hosted_on` -- rung 2, the
          # lock family word EOPEN-17 already used for "this content
          # lives on that part". Unpinned intents are planner-allocated.
          image: sense(image(2048 x 1536, 12bit)) hosted_on payload:
              gsd:  <= 30m
              rate: >= 16/day
          sense_att: sense(geom.orientation) hosted_on adcs:
              accuracy: <= 1deg
              rate:     >= 4Hz
          decide: compute(adcs_law) hosted_on obc:
              rate:    4Hz
              latency: < 50ms
              state:   ephemeris(4kB, persistent)
          crunch: compute(tile_compression) hosted_on payload:
              rate:    >= 30MB/s in
              latency: <= 500ms
          point: actuate(magnetorquer(3 axis, >= 0.18 A*m2)) hosted_on adcs
          downlink: communicate(ground_station(uhf_437)) hosted_on comms:
              rate:   >= 9600bps
              volume: >= 15MB/day
          uplink: communicate(ground_station(uhf_437)) hosted_on comms:
              rate: >= 1200bps
          keep: store(images(2GB, retention >= 7 days)) hosted_on obc
          deploy_ant: actuate(burn_wire(4J, one_shot)) hosted_on comms
  ```


Claims:

- `Modes`:
  - `safe_floor`: `elec.power(all) <= 400mW during op = safe` -- (unbuilt)
  - `detumble_in` -- (unbuilt):

    ```
    within 3h after separation:
                             mech.rate(body) <= 0.5deg/s
    ```

  - `fault_safe`: `within 5s after anomaly: op = safe` -- (unbuilt)
- `Thermal`:
  - `batt_window` -- (unbuilt):

    ```
    thermo.temperature(eps.store.cells)
                             within [0degC, 45degC] forall op
    ```

  - `fpga_ceiling` -- (unbuilt):

    ```
    thermo.temperature(payload.u_fpga.junction)
                              <= 85degC during op = imaging
    ```

- `Link`:
  - `margin` -- (unbuilt):

    ```
    comms.pa_out + antenna.gain
                        - path_loss(boundary.orbit.slant_max)
                        >= gs_uhf437.sensitivity + 6dB
                        during op = downlink
    ```


Budgets:

- (unnamed budget): `require: mech.mass(all) <= 1330g     # 1U + margin per LSP`
- (unnamed budget):

  ```
  require: elec.energy(all, over=boundary.orbit.profile)
                       <= elec.energy(eps.harvest, over=boundary.orbit.profile),
                       sf=1.15
  ```

- (unnamed budget): `require: error(sense_att -> decide) <= 1deg`

<a id="computer-flightcore"></a>
### computer `FlightCore`

Claims:

- `Capacity`:
  - `headroom`: `info.utilization(all) <= 55%` -- (unbuilt)

<a id="decl-architecture"></a>
### decl `architecture`

- `resources`:

  ```
  cpu0:  executor(promises: >= 20Mops f32 sustained)
          fpga0: executor(promises: >= 1Gops fixed, kind=fabric)
          dma:   mover(promises: >= 40MB/s, independent of cpu0)
  ```

- `memories`:

  ```
  sram:  memory(320kB, promises: latency <= 2 cycles)
          flash: memory(1MB, persistent)
          bulk:  memory(8GB, persistent, endurance >= 1e4 cycles)
  ```

- `schedule`:

  ```
  att  -> cpu0: static_priority(highest)
          hk   -> cpu0
          comm -> cpu0
          tiles -> fpga0
          keepw -> dma
  ```


<a id="decl-bind"></a>
### decl `bind`

<a id="image-flight-fw"></a>
### image `flight_fw`

- `realizes`: `schedule(FlightCore)`
- `toolchain`: `gcc_arm(13.2, -O2)`
- `partitions`:

  ```
  boot: flash[0 .. 32kB]
          appA: flash[32kB .. 512kB]        # A/B images: brick-proof
          appB: flash[512kB .. 992kB]
          cfg:  remainder
  ```


Claims:

- `Resources`:
  - `fit`: `size(text + ro) <= 480kB` -- (unbuilt)
  - `stack`: `info.stack_depth(att) <= 6kB` -- (unbuilt)
  - `wcet`: `info.wcet(att, on=cpu0) <= 120ms` -- (unbuilt)
- `Boot`:
  - `alive`: `within 30s after supply.on: comm.beacon` -- (unbuilt)

<a id="target-flatsat"></a>
### target `flatsat`

- `intents`:

  ```
  console:   debug_access(eps.Umbilical.dbg, uart_log)
          heartbeat: indicate(decide.status)
          rails:     probe(power_rails)
  ```

- `draws`: `reserves`

## `examples/flagships/cubesat/kestrel.test.cupr`

(no public declarations)

## `examples/flagships/cubesat/obc.cupr`

- [board `ObcPcb`](#board-obcpcb)

<a id="board-obcpcb"></a>
### board `ObcPcb`

FINDING F83: the firmware image is declared at intent altitude
(kestrel.cupr, `realizes: schedule(FlightCore)`) but loading it is a
construction step of THIS board -- an upward import would be a
cycle. Resolved with an artifact-typed caller parameter: the board
takes the image like a variant choice at binding
(`obc: ObcPcb(fw=flight_fw)`). Ledgered as D54 [LEANING]: `<...>`
params may be artifact-typed (image, part), not only quantities.

Claims:

- `Supervision`:
  - `kick`: `within 1.6s after boot: state(u_wdt) = armed` -- (unbuilt)
  - `latchup`: `within 5us after overcurrent(v3v3): state(u_mcu.rail) = open` -- (unbuilt)
- `Storage`:
  - `wear` -- (unbuilt):

    ```
    elec.write_endurance(u_sd, over=design_life,
                      rate=image_store_rate) >= 1.0, sf=2
    ```


## `examples/flagships/cubesat/payload.cupr`

- [block `TileCompressor`](#block-tilecompressor)
- [board `PayloadPcb`](#board-payloadpcb)
- [image `tile_bits`](#image-tile-bits)
- [impl `TileCompressor`](#impl-tilecompressor)

<a id="block-tilecompressor"></a>
### block `TileCompressor`

- `ports`:

  ```
  cam_in:   bus(sublvds_4lane, domain=pix_clk)   # 2.5V differential
          cam_ctl:  bus(i2c(fast))                       # sensor config
          tiles:    bus(spi_slave(<= 40MHz))             # 3.3V, to OBC
          pix_clk:  clock(96MHz)
          core_clk: clock(120MHz)
  ```

- `spec`:

  ```
  on pix_clk.rise:
              line_buf[wr] <= cam_in.data when cam_in.valid
              wr <= wr + 1 when cam_in.valid
          on core_clk.rise:
              tiles.data <= rice_encode(line_buf[rd])
              rd <= rd + 1 when tiles.ready
  ```

- `promises`:

  ```
  timing.latency(cam_in -> tiles): <= 4 lines
          info.compression(tiles): >= 1.8   # lossless floor on test corpus

      # WO-105 release residuals (D206/D207): memo-backed accepted
      # deviations; verdicts untouched (INV-2). See memos/release-residuals.md.
  ```


<a id="board-payloadpcb"></a>
### board `PayloadPcb`

<a id="image-tile-bits"></a>
### image `tile_bits`

- `realizes`: `impl(TileCompressor)`
- `toolchain`: `yosys_nextpnr(0.7)`

Claims:

- `Resources`:
  - `fit`: `info.utilization(u_fpga) <= 70%` -- (unbuilt)
  - `fmax`: `info.fmax(core_clk) >= 120MHz` -- (unbuilt)

<a id="impl-tilecompressor"></a>
### impl `TileCompressor`

## `examples/flagships/cubesat/structure.hema`

- [interface `PanelSeat`](#interface-panelseat)
- [part `Rail`](#part-rail)
- [part `SidePanel`](#part-sidepanel)
- [assembly `Frame`](#assembly-frame)
- [profile `PanelOutline`](#profile-paneloutline)
- [profile `RailSection`](#profile-railsection)

<a id="interface-panelseat"></a>
### interface `PanelSeat`

- `frame`:

  ```
  origin: holes.pattern_center
          z: holes.plane.normal
  ```

- `roles`:

  ```
  holes: PatternOf<TappedHole<screw>, n, along>

      # WO-105 release residuals (D206/D207): memo-backed accepted
      # deviations; verdicts untouched (INV-2). See memos/release-residuals.md.
  ```


<a id="part-rail"></a>
### part `Rail`

- `material`: `AL7075_T6`

Claims:

- `Structural`:
  - `trust`: `>= community` -- (unbuilt)
  - `rail_stress` -- (unbuilt):

    ```
    peak(mech.stress.von_mises, during boundary.launch)
                             < 314.375MPa

        # WO-105 release residuals (D206/D207): memo-backed accepted
        # deviation; verdict untouched (INV-2). See memos/release-residuals.md.
    ```


<a id="part-sidepanel"></a>
### part `SidePanel`

- `material`: `AL6061_T6`

<a id="assembly-frame"></a>
### assembly `Frame`

Claims:

- `Stiffness`:
  - `first_mode`: `mech.first_mode > 120Hz during deploy = stowed` -- (unbuilt)
- `Mass`:
  - `frame_total`: `mech.mass(all) <= 210g` -- (unbuilt)

<a id="profile-paneloutline"></a>
### profile `PanelOutline`

<a id="profile-railsection"></a>
### profile `RailSection`

## `examples/flagships/cubesat/structure.test.hema`

(no public declarations)
