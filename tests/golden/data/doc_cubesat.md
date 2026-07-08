# Package documentation

## `examples/systems/cubesat/adcs.cupr`

- [board `AdcsPcb`](#board-adcspcb)

<a id="board-adcspcb"></a>
#### board `AdcsPcb`

Claims:

- `Actuation`:
  - `dipole`: `forall` -- (unbuilt)
  - `no_stuck`: `(empty)` -- (unbuilt)
- `Sensing`:
  - `mag_floor`: `rms(b(u_mag), band=[0.1Hz, 10Hz]) < 30nT` -- (unbuilt)

## `examples/systems/cubesat/antenna.hema`

- [interface `PivotBore`](#interface-pivotbore)
- [part `DeployerBody`](#part-deployerbody)
- [assembly `Antenna`](#assembly-antenna)

<a id="interface-pivotbore"></a>
#### interface `PivotBore`

- `frame`: `origin: bore.axis`
- `roles`: `bore: cylindrical(d=d), internal`
- `tolerances`: `bore: tol_class(H7)`

<a id="part-deployerbody"></a>
#### part `DeployerBody`

- `material`: `AL6061_T6`

<a id="assembly-antenna"></a>
#### assembly `Antenna`

Claims:

- `Stowed`:
  - `retention`: `peak(mech.force(hold), during boundary.launch)` -- (unbuilt)
  - `no_rattle`: `mech.gap(element.tip, body.channel) <= 0.15mm` -- (unbuilt)
- `Deployment`:
  - `torque`: `forall` -- (unbuilt)
  - `settle`: `settles(root.theta, to=90deg +- 2deg` -- (unbuilt)
- `Deployed`:
  - `pattern_clear`: `mech.envelope(element, during deploy = deployed)` -- (unbuilt)

## `examples/systems/cubesat/comms.cupr`

- [board `CommsPcb`](#board-commspcb)

<a id="board-commspcb"></a>
#### board `CommsPcb`

Claims:

- `Rf`:
  - `pa_out`: `elec.power(assembled.rf_conn) >= 26dBm` -- (unbuilt)
  - `harmonics`: `stays_within(emissions, mask=fcc_part25)` -- (unbuilt)
- `Deploy`:
  - `burn_energy`: `elec.energy(q_burn.out, over=burn_pulse) >= 4J` -- (unbuilt)
  - `one_shot`: `forall` -- (unbuilt)

## `examples/systems/cubesat/contracts.cupr`

- [interface `AntennaPort`](#interface-antennaport)
- [interface `CardBay`](#interface-cardbay)
- [interface `StackCard`](#interface-stackcard)
- [interface `StackHarness`](#interface-stackharness)
- [interface `Umbilical`](#interface-umbilical)
- [mating `AntennaMate`](#mating-antennamate)
- [mating `CardMount`](#mating-cardmount)
- [mating `StackMate`](#mating-stackmate)

<a id="interface-antennaport"></a>
#### interface `AntennaPort`

- `frame`: `gnd: reference`
- `roles`: `rf:      analog(elec.power, z=50ohm)     # the coax role`
- `demands`: `rf: geom.position(+-0.3mm, to=frame)`

<a id="interface-cardbay"></a>
#### interface `CardBay`

- `frame`: `origin: posts.pattern_center`
- `roles`: `posts: geom.boss_pattern(tapped=M3, n=4, rect(90mm x 90mm))`
- `promises`: `thermal.sink: conductive, >= 0.5 W/K   # card-to-rail conduction`

<a id="interface-stackcard"></a>
#### interface `StackCard`

- `frame`: `origin: mounts.pattern_center     # kit-derived datums`
- `roles`: `outline: geom.plate(96mm x 96mm, t=1.6mm)`
- `demands`: `mounts: geom.position(+-0.1mm, to=frame)`
- `promises`: `mass:  <= 90g                     # per-card ceiling; impls refine`

<a id="interface-stackharness"></a>
#### interface `StackHarness`

- `frame`: `gnd:   reference`
- `roles`: `v3v3:  supply(out, 3.3V +- 3%, i <= 4.5A)`
- `demands`: `sys: pullup(scl): required, pullup(sda): required`

<a id="interface-umbilical"></a>
#### interface `Umbilical`

- `frame`: `gnd: reference`
- `roles`: `chg:  supply(in, [7V, 9V], i <= 1.5A)`

<a id="mating-antennamate"></a>
#### mating `AntennaMate`

- `between`: `a`
- `align`: `a.frame = b.frame`
- `couples`: `a.release = b.release`

<a id="mating-cardmount"></a>
#### mating `CardMount`

- `between`: `a`
- `align`: `a.frame = b.frame`
- `dof`: `removed=[all]`
- `effects`: `(empty)`

<a id="mating-stackmate"></a>
#### mating `StackMate`

- `between`: `a`
- `align`: `a.frame = b.frame`
- `couples`: `a.sys = b.sys`
- `capability`: `i_3v3: per harness promise, summed over cards`

Claims:

- `State`:
  - `no_contention`: `arbitration(a.sys.sda) = lossless` -- (unbuilt)

## `examples/systems/cubesat/eps.cupr`

- [system `Eps`](#system-eps)
- [board `EpsPcb`](#board-epspcb)

<a id="system-eps"></a>
#### system `Eps`

- `intents`:
  harvest: convert(solar -> dc_bus):
              array:  4 x panel(80mm x 80mm, eff >= 28%)
              mppt:   required

Claims:

- `Battery`:
  - `temp_window`: `thermo.temperature(store.cells)` -- (unbuilt)
  - `dod`: `elec.depth_of_discharge(store) <= 30` -- (unbuilt)
  - `never_flat`: `forall` -- (unbuilt)
- `Harvest`:
  - `worst_orbit`: `elec.energy(harvest, over=boundary.illumination.` -- (unbuilt)

<a id="board-epspcb"></a>
#### board `EpsPcb`

Claims:

- `Protection`:
  - `ovp`: `stays_within(v(vbatt), mask=cell_ovp(4.2V, 2))` -- (unbuilt)
  - `ocp`: `(empty)` -- (unbuilt)
  - `rbf_kill`: `elec.power(all) <= 50uW` -- (unbuilt)

## `examples/systems/cubesat/kestrel.cupr`

- [system `Kestrel`](#system-kestrel)
- [computer `FlightCore`](#computer-flightcore)
- [decl `architecture`](#decl-architecture)
- [decl `bind`](#decl-bind)
- [image `flight_fw`](#image-flight-fw)
- [target `flatsat`](#target-flatsat)

<a id="system-kestrel"></a>
#### system `Kestrel`

- `reserves`: `mass:  80g`
- `intents`:
  sense_att: sense(geom.orientation) hosted_on adcs:
              accuracy: <= 1deg
              rate:     >= 4Hz

Claims:

- `Modes`:
  - `safe_floor`: `elec.power(all) <= 400mW` -- (unbuilt)
  - `detumble_in`: `(empty)` -- (unbuilt)
  - `fault_safe`: `(empty)` -- (unbuilt)
- `Thermal`:
  - `batt_window`: `thermo.temperature(eps.store.cells)` -- (unbuilt)
  - `fpga_ceiling`: `thermo.temperature(payload.u_fpga.junction)` -- (unbuilt)
- `Link`:
  - `margin`: `comms.pa_out + antenna.gain` -- (unbuilt)

Budgets:

- ``: `require: mech.mass(all) <= 1330g     # 1U + margin per LSP`
- ``: `require: elec.energy(all, over=boundary.orbit.profile)
                     <= elec.energy(eps.harvest, over=boundary.orbit.profile),
                     sf=1.15`
- ``: `require: error(sense_att -> decide) <= 1deg`

<a id="computer-flightcore"></a>
#### computer `FlightCore`

Claims:

- `Capacity`:
  - `headroom`: `info.utilization(all) <= 55` -- (unbuilt)

<a id="decl-architecture"></a>
#### decl `architecture`

- `resources`: `cpu0:  executor(promises: >= 20Mops f32 sustained)`
- `memories`: `sram:  memory(320kB, promises: latency <= 2 cycles)`
- `schedule`: `(empty)`

<a id="decl-bind"></a>
#### decl `bind`

<a id="image-flight-fw"></a>
#### image `flight_fw`

- `realizes`: `schedule(FlightCore)`
- `toolchain`: `gcc_arm(13.2, -O2)`
- `partitions`: `boot: flash[0 .. 32kB]`

Claims:

- `Resources`:
  - `fit`: `size(text + ro) <= partitions.appA.size` -- (unbuilt)
  - `stack`: `info.stack_depth(att) <= 6kB` -- (unbuilt)
  - `wcet`: `info.wcet(att,` -- (unbuilt)
- `Boot`:
  - `alive`: `(empty)` -- (unbuilt)

<a id="target-flatsat"></a>
#### target `flatsat`

- `intents`: `console:   debug_access(eps.Umbilical.dbg, uart_log)`
- `draws`: `reserves`

## `examples/systems/cubesat/obc.cupr`

- [board `ObcPcb`](#board-obcpcb)

<a id="board-obcpcb"></a>
#### board `ObcPcb`

FINDING F83: the firmware image is declared at intent altitude
(kestrel.cupr, `realizes: schedule(FlightCore)`) but loading it is a
construction step of THIS board -- an upward import would be a
cycle. Resolved with an artifact-typed caller parameter: the board
takes the image like a variant choice at binding
(`obc: ObcPcb(fw=flight_fw)`). Ledgered as D54 [LEANING]: `<...>`
params may be artifact-typed (image, part), not only quantities.

Claims:

- `Supervision`:
  - `kick`: `(empty)` -- (unbuilt)
  - `latchup`: `(empty)` -- (unbuilt)
- `Storage`:
  - `wear`: `elec.write_endurance(u_sd, over=design_life,` -- (unbuilt)

## `examples/systems/cubesat/payload.cupr`

- [block `TileCompressor`](#block-tilecompressor)
- [board `PayloadPcb`](#board-payloadpcb)
- [image `tile_bits`](#image-tile-bits)
- [impl `TileCompressor`](#impl-tilecompressor)

<a id="block-tilecompressor"></a>
#### block `TileCompressor`

- `ports`: `cam_in:   bus(sublvds_4lane, domain=pix_clk)   # 2.5V differential`
- `spec`:
  on pix_clk.rise:
              line_buf[wr] <= cam_in.data when cam_in.valid
              wr <= wr + 1 when cam_in.valid
- `promises`: `(empty)`

<a id="board-payloadpcb"></a>
#### board `PayloadPcb`

<a id="image-tile-bits"></a>
#### image `tile_bits`

- `realizes`: `(empty)`
- `toolchain`: `yosys_nextpnr(0.7)`

Claims:

- `Resources`:
  - `fit`: `info.utilization(u_fpga) <= 70` -- (unbuilt)
  - `fmax`: `info.fmax(core_clk) >= 120MHz` -- (unbuilt)

<a id="impl-tilecompressor"></a>
#### impl `TileCompressor`

## `examples/systems/cubesat/structure.hema`

- [interface `PanelSeat`](#interface-panelseat)
- [part `Rail`](#part-rail)
- [part `SidePanel`](#part-sidepanel)
- [assembly `Frame`](#assembly-frame)
- [profile `PanelOutline`](#profile-paneloutline)
- [profile `RailSection`](#profile-railsection)

<a id="interface-panelseat"></a>
#### interface `PanelSeat`

- `frame`: `origin: holes.pattern_center`
- `roles`: `holes: PatternOf<TappedHole<screw>, n, along>`

<a id="part-rail"></a>
#### part `Rail`

- `material`: `AL7075_T6`

Claims:

- `Structural`:
  - `trust`: `>= certified` -- (unbuilt)
  - `rail_stress`: `peak(mech.stress.von_mises, during boundary.launch)` -- (unbuilt)

<a id="part-sidepanel"></a>
#### part `SidePanel`

- `material`: `AL6061_T6`

<a id="assembly-frame"></a>
#### assembly `Frame`

Claims:

- `Stiffness`:
  - `first_mode`: `mech.first_mode > 120Hz` -- (unbuilt)
- `Mass`:
  - `frame_total`: `mech.mass(all) <= 210g` -- (unbuilt)

<a id="profile-paneloutline"></a>
#### profile `PanelOutline`

<a id="profile-railsection"></a>
#### profile `RailSection`
