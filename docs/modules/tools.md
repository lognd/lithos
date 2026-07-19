# tools/ -- repo-maintenance and generation scripts

These are the Python scripts under `tools/` that keep the repo's health
gates and generated stdlib records honest. They are NOT part of the
`regolith` package (no core import boundary applies here) -- they are
maintainer-facing tooling invoked via `make` targets.

## tools/health -- the repo health gate (WO-106 / D219)

`python -m tools.health` composes four cheapest-first "legs" -- `check`,
`consistency`, `demos`, `fleet` -- into the ONE command that proves the
owner's bar and keeps it proven (`make health`).

<a id="health-package"></a>
### `tools/health/__init__.py`
Package entry point; re-exports the health-leg composition surface.

<a id="health-main"></a>
### `tools/health/__main__.py`
Runs the four legs in order (`check` -> `consistency` -> `demos` ->
`fleet`), cheapest first, and aggregates their `LegResult`s into the
health command's exit status.

<a id="health-check-leg"></a>
### `tools/health/check.py`
The `check` leg: calls the EXISTING code gates unchanged (D219 refactor
rule -- this leg never re-implements a gate, only invokes it).

<a id="health-consistency-leg"></a>
### `tools/health/consistency.py`
The `consistency` leg: cheap, build-free standardization sweeps that
prove the repo still hangs together (naming, doc-agreement, `std.`
organization, unit-literal hygiene) without invoking a full build.

<a id="health-demos-leg"></a>
### `tools/health/demos.py`
The `demos` leg: reuses the WO-108 proof-pack machinery verbatim to
prove every live demo proof pack is still proven, without
re-implementing the proof-pack runner.

<a id="health-diag-codes"></a>
### `tools/health/diag_codes.py`
The `diag_codes` sub-check (D247.4b, WO-131): fails if any user-facing
failure is raised with a bare string `kind` instead of a registered
diagnostic code.

<a id="health-docs-agreement"></a>
### `tools/health/docs_agreement.py`
The docs-agreement sweeps (WO-121, D230): standalone, mechanically
checkable agreement rules between committed docs and the repo they
describe, folded into the `consistency` leg.

<a id="health-fleet-leg"></a>
### `tools/health/fleet.py`
The `fleet` leg: proves every D210 fleet project (an `examples/`
directory with a census entry) still ships green.

<a id="health-report-shape"></a>
### `tools/health/report.py`
The ONE standardized `LegResult`-style report shape every health leg
returns, regardless of how heavy or cheap its internals are.

<a id="health-units-sweep"></a>
### `tools/health/units.py`
The `units` consistency sub-check (WO-150, D262 ruling 2): a
bare-numeral rot guard over the emitted artifact corpus, catching
unit-less literals that should carry an explicit unit.

<a id="health-waiver-classes"></a>
### `tools/health/waiver_classes.py`
The D220.2 waiver-class vocabulary (WO-117, D220.3): the ONE home every
accepted fleet deviation (waiver) must classify itself against.

## tools/stdlib -- WO-66 stdlib generation framework

Deterministic, cached, cited record generators over committed input
tables (D174 sourcing law). Every generator is additive-only and
idempotent: rerunning with no input-table change produces
byte-identical output. See `tools/stdlib/SOURCES.md` for the per-family
citation ledger.

<a id="stdlib-package"></a>
### `tools/stdlib/__init__.py`
Package entry point for the WO-66 generation framework.

<a id="stdlib-gen-civil-sections"></a>
### `tools/stdlib/gen_civil_sections.py`
Generates `stdlib/std.civil/records/sections_channels_angles.toml` from
the committed AISC C/L dimension table.

<a id="stdlib-gen-eseries"></a>
### `tools/stdlib/gen_eseries.py`
Generates `stdlib/std.elec/records/e_series.toml` (parametric passive
families) from the committed E-series table; one record per
series x package x tolerance.

<a id="stdlib-gen-fasteners"></a>
### `tools/stdlib/gen_fasteners.py`
Generates `stdlib/std.fasteners/records/*.toml` from the committed ISO
dimension table (D174 sourcing law rule 3: standard-table families are
GENERATED, not hand-authored).

<a id="stdlib-gen-iapws-water"></a>
### `tools/stdlib/gen_iapws_water.py`
Generates `stdlib/std.fluid/records/water_saturation.toml` (WO-138,
D258.1/F158 gap c1) from the committed IAPWS-IF97 Region 4 saturation
curve coefficient table.

<a id="stdlib-gen-nasa-glenn-cp"></a>
### `tools/stdlib/gen_nasa_glenn_cp.py`
Generates `stdlib/std.fluid/records/gas_cp_glenn.toml` (WO-138, D258.1/
F158 gap c2) from the committed NASA Glenn coefficient table.

<a id="stdlib-gen-processors"></a>
### `tools/stdlib/gen_processors.py`
Generates `stdlib/ti.mcu/records/msp430fr5_*.toml` (WO-145, D257 ruling
4) from the committed, human-confirmed MSP430FR5 transcription table.

<a id="stdlib-generate-all"></a>
### `tools/stdlib/generate_all.py`
The `make stdlib-gen` entry point: runs every generator script in
sequence and writes its output; idempotent given unchanged inputs.

<a id="stdlib-organization-sweeps"></a>
### `tools/stdlib/organization.py`
The `std.` organization sweeps (WO-118, D227/AD-37, charter 39 sec.
5.4): mechanically-checkable rules folded into the health
`consistency` leg.

<a id="stdlib-render"></a>
### `tools/stdlib/render.py`
Deterministic TOML record rendering shared by every WO-66 generator
script -- one rendering home so every generator writes the exact same
byte layout for the same logical record (D174 sourcing law rule 2).

## tools/codegen -- GENERATED-artifact codegen drivers

Precedent: `make schema`-style drivers that regenerate committed,
GENERATED Python modules from a Rust export -- never hand-edited (see
CLAUDE.md Tripwires).

<a id="codegen-package"></a>
### `tools/codegen/__init__.py`
Package entry point; currently hosts `generate_codes` (WO-131/D247).

<a id="codegen-generate-codes"></a>
### `tools/codegen/generate_codes.py`
The `make codes` driver (WO-131/D247): regenerates the GENERATED Python
diagnostic-code module from the Rust `regolith-export-codes` export.
