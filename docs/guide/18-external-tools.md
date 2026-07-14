# External tools

WORKING (`regolith doctor` + the `regolith.toolenv` registry; the
per-tool call-site wiring varies -- each tool's entry below says
what is wired up in this repo today).

The toolchain shells out to a handful of OPTIONAL external binaries
for the higher evidence tiers (real layout, real simulation, real
FEA), and loads one optional Python plugin pack (feldspar). None of
them are required to install regolith or to run `regolith check`.
Two rules govern every one of them:

1. If a design does NOT need a tool, its absence is a graceful,
   honest skip -- the affected claims render INDETERMINATE (deferred,
   with a named reason), never a broken build, never a crash.
2. If a design DOES need a tool (e.g. it makes an elec layout claim,
   which needs `kicad-cli`), a missing tool is a LOUD, constructive
   diagnostic: the tool's name, why THIS design needs it, and exact
   install guidance -- never a bare traceback, never a silent pass.

Every tool's identity, capability wording, and install-hint COMMAND
strings are single-sourced in ONE module,
`python/regolith/toolenv.py`. This guide quotes them for reading
convenience, but the registry is authoritative: `regolith doctor`
prints the live strings, and a drift test
(`tests/test_toolenv.py::test_guide_quotes_registry_capabilities`)
keeps this guide's capability wording in sync with the code.

## `regolith doctor` -- start here

```
regolith doctor
```

Prints one row per registered tool: found/MISSING, the resolved
path, the probed version, the capability the tool unlocks, and (for
anything missing) the install guidance -- the same strings this
guide quotes, from the same registry. `regolith doctor --json`
emits the identical data as JSON for CI environment probes.

`regolith doctor` is the FIRST thing to run on any "nothing
discharges" symptom (see the feldspar troubleshooting entry below).

## The tools

### kicad-cli (+ pcbnew)

- Unlocks: elec layout tier for cuprite designs
  (placement/routing/DRC/export). Without it, layout realization and
  the elec manufacturing backend (`regolith ship`'s gerber/drill/pos
  exports) return an honest `tool_unavailable` error value, and
  `elec.layout.drc_clean` claims cannot be discharged.
- Wired up today: yes -- `regolith.realizer.elec.kicad` and
  `regolith.backends.elec`.
- Real board outlines (WO-103, charter 38 sec. 1.10): the real KiCad
  wrapper (`regolith.realizer.elec.kicad_wrapper`) draws the DESIGN'S
  own rectangular board outline (`LayoutRequest.outline_w_mm`/
  `outline_d_mm` -- the same geometry the deterministic fake tier
  already renders; the old fixed 50mm placeholder square is retired).
  `kicad-cli pcb export gerbers|drill|pos` then re-exports that real,
  outline-shaped (but unrouted -- no footprint-library resolution
  machinery exists yet, routing is a separate scope) board; in a
  `regolith ship` release package these land in the `boards/` family
  beside the pinned `board.kicad_pcb` and an honest
  `board_status.json`, and the package index labels the family with
  that status (unrouted gerbers are fab-shape evidence, labeled as
  such). The fake tier (`regolith.realizer.elec.fake_kicad`) remains
  the deterministic, no-install CI leg, always stamped
  `generator regolith-fake-kicad`; it never claims to be the real
  leg's output.
- Install: `sudo apt install kicad` (the KiCad PPA for KiCad 10).
  The `pcbnew` python API additionally needs `make kicad-link` to
  link the system module into the venv; `kicad-cli` alone does not
  open the real-tool gate
  (`regolith.realizer.elec.kicad.real_kicad_available()`).

### verilator

- Unlocks: HDL sim-tier evidence for cuprite digital designs
  (`hdl.build`, `hdl.sim_assert`, `hdl.equiv_directed` for
  Verilog/SystemVerilog fixtures). Without it, every hdl.* claim
  renders indeterminate with the install hint cited in the deferral
  message.
- Wired up today: yes -- `regolith.harness.models.hdl` (the std.hdl
  pack, WO-82).
- Install: `sudo apt install verilator`.

### ghdl

- Unlocks: VHDL sim-tier evidence for cuprite digital designs.
  Registered so the VHDL deferral message can honestly report ghdl's
  live PATH status; note that TODAY no ghdl adapter is implemented
  (a WO-82 scope cut) -- VHDL hdl.* claims defer even with ghdl
  installed, and the deferral message says which case you are in.
- Install: `sudo apt install ghdl`.

### ngspice

- Unlocks: SPICE simulation tier for cuprite analog/power designs.
- Wired up today: no realizer in this repo invokes it yet;
  registered so `regolith doctor` reports the full optional surface
  and a future call site never re-derives install text.
- Install: `sudo apt install ngspice` (see troubleshooting for the
  KiCad-PPA conflict).

### ccx (CalculiX)

- Unlocks: FEA solve tier (CalculiX) for hematite/feldspar stress
  claims.
- Wired up today: invoked by the feldspar pack (its own repo), not
  by lithos directly; registered here so one `regolith doctor` run
  covers the whole environment.
- Install: `sudo apt install calculix-ccx`.

### gmsh

- Unlocks: FEA meshing tier for hematite/feldspar geometry-to-mesh.
- Wired up today: invoked by the feldspar pack, same note as ccx.
- Install: `sudo apt install gmsh` where apt can resolve it; on
  KiCad-PPA and/or arm64 hosts apt cannot -- see troubleshooting,
  conda-forge is the working route there.

### sigrok-cli

- Unlocks: logic-analyzer capture tier for the WO-126 bring-up
  harness pack (dist/<proj>/harness/ capture configs).
- Wired up today: the harness pack's capture configs are always
  emitted (config-only tier); `sigrok-cli` absence never blocks a
  ship -- it is only needed to actually RUN a capture by hand. See
  guide `30-hardware-bring-up.md`.
- Install: `sudo apt install sigrok-cli`.

### feldspar (plugin pack, not a binary)

- Unlocks: the external FEA/solver evidence tiers for hematite (and
  the mixed-domain flagships). It is a Python plugin distribution,
  not a PATH binary, so it is NOT in `regolith doctor`'s binary
  table; its absence-handling is the WO-27 skip-if-absent posture
  (`tests/packs/test_feldspar_conformance.py`): tests and harness
  runs that need it skip/defer honestly.
- Install (local dev): check the repo out beside this one and
  `uv pip install -e ../feldspar` into the ACTIVE venv.

## Troubleshooting

### ngspice: dpkg "trying to overwrite .../ngspice/analog.cm"

On a host with the KiCad PPA enabled, `sudo apt install ngspice`
can fail with dpkg refusing to overwrite
`.../ngspice/analog.cm` (or another `.cm` file): the
`libngspice-kicad` package ships the same XSPICE code models as the
ngspice CLI package. Fix:

```
sudo apt install ngspice -o Dpkg::Options::="--force-overwrite"
```

Caveat: the CLI package's (v36) code models then shadow the KiCad
lib's (v43) copies on disk. If KiCad's built-in simulator later
misbehaves, undo the shadowing with
`sudo apt install --reinstall libngspice-kicad`.

### gmsh: unmet OCCT dependencies (libocct-*-7.6 Breaks 7.5)

Ubuntu jammy's `gmsh` package needs OCCT 7.5, but a KiCad-10-PPA
host pins `libocct-*-7.6`, which declares `Breaks` on 7.5 -- apt
`gmsh` is unwinnable on such a host; do not fight the resolver.
Additionally, on arm64 there is NO pip wheel and NO upstream binary
tarball for gmsh. The working route:

```
micromamba create -n gmsh -c conda-forge gmsh
ln -s ~/micromamba/envs/gmsh/bin/gmsh /usr/local/bin/gmsh   # or ~/.local/bin
```

(the symlink gives global PATH visibility, which is what the
registry's `which()` resolution and every subprocess call site
need). On x86_64 the upstream Linux64 tarball from gmsh.info is an
alternative to conda-forge.

### calculix-ccx: apt refuses to install it

`calculix-ccx` has NO OCCT dependency. If apt refuses it, it was
almost certainly batched in one transaction with `gmsh` (whose OCCT
conflict poisons the whole transaction) -- install it alone:

```
sudo apt install calculix-ccx
```

### feldspar: every harness discharge defers (discharged=0)

Symptom: a build that used to discharge claims suddenly reports
zero discharged, all deferred, with NO error anywhere. Cause: a
rebuilt venv (e.g. `uv sync` after a lockfile change, or a fresh
clone) drops the editable feldspar install, and the plugin seam
skips the absent pack honestly -- which is exactly the graceful-skip
posture doing its job, but it looks like a silent regression if you
do not know to check. Fix:

```
uv pip install -e ../feldspar
```

Run `regolith doctor` FIRST on any "nothing discharges" symptom: it
shows the binary-tool half of the environment at a glance, and a
fully-green doctor table with zero discharges points you straight at
the plugin half (feldspar).
