# Manufacturability claims and the closed-form model channels (WO-110)

This guide covers the discharge channels WO-110 landed (F130 Class C,
D232): the `manufacturable(<process>)` claim over realized geometry,
the NPSH and shaft-torsion closed forms, the bare unit-cost adapter,
and the feldspar critical-speed adapter -- what each needs declared,
what its deferrals mean, and what to do about a VIOLATED verdict.
Everything here is WORKING.

## 1. `makeable: manufacturable(<process>)`

```
require Manufacture:
    makeable: manufacturable(milled)
```

The claim asks: can the REALIZED part actually be made by the named
process, with the shop resources this project declares? At discharge
the harness model `mfg_manufacturable_mill` grounds two envelope
checks in declared data only (charter 39 sec. 4 -- no invented
thresholds):

- **stock/travel fit** -- the realized part's bounding-box extents
  (from the staged build's own `RealizedGeometry`) must fit the
  declared `[[machine]]` record's travel extents.
- **tool fit/reach** -- every mill-stage hole (spelled `dia` +
  `depth`, or depth derived from the one spelled blank thickness)
  must be producible by SOME declared `[[tool]]` record: tool
  diameter at or under the hole's, stickout at or past its depth.

The records are the SAME `records/*.toml` `[[machine]]`/`[[tool]]`
rows the CAM verifier (guide 14) consumes -- declare them once. The
process token maps to a family (`milled`/`machined`/`mill`/`routed`
-> mill); v1 grounds the MILL family, and every other family defers
naming what would ground it (form-family physics already lives in
the rule packs, guide 10 -- one home per rule).

Deferral vocabulary (each names its exact gap):

| reason | fix |
|---|---|
| `mfg.manufacturable_inputs_missing` | spell the named feature scalars (`<feature>.diameter`, `.depth`) as literals, or realize the part (the staged build must produce its geometry) |
| `mfg.manufacturable_records_missing` | declare exactly one `[[machine]]` and at least one `[[tool]]` record |
| `mfg.manufacturable_ungrounded_process` | the family has no record-groundable envelope check yet (v1: mill only) |
| `mfg.manufacturable_process_mismatch` | the token names a family none of the part's stages spell |
| `mfg.manufacturable_unknown_process` | the token is outside the claim vocabulary |

A VIOLATED verdict is a FINDING, not a nuisance: the part genuinely
does not fit the declared machine, or a hole needs a tool the shop
does not stock. Fix the DESIGN or declare the real resource (D224.3)
-- never widen the claim or touch the model.

## 2. `fluids.npsh_margin` -- pump cavitation headroom

```
npsh: fluids.npsh_margin(pump, p_supply_pa=101325, p_vapor_pa=2339,
          density_kgm3=998, z_static_m=-3.0, h_friction_m=0.8,
          npshr_m=4.0) > 1.5m
```

Closed-form NPSH energy balance (White, Fluid Mechanics, 8th ed.,
ch. 11): `margin = (p_supply - p_vapor)/(rho g) + z_static -
h_friction - NPSHr`, worst interval corner. Every input is declared
data -- property records for vapor pressure/density, the pump curve
for NPSHr. Missing inputs defer `fluids.npsh_margin_inputs_missing`
naming them.

## 3. `mech.twist` -- shaft angle of twist

```
twist: mech.twist(turned.blank, torque_nm=100, length_m=1.0,
           g_modulus_pa=79.3e9, j_torsion_m4=3.835e-8) <= 0.05
```

`theta = T L / (G J)` (Shigley, 10th ed., ch. 4), radians, worst
corner. The bound and the prediction must agree on units (radians);
sub-radian spellings (`mrad`) are a known bound-resolution gap named
in the WO-110 close-out -- spell the bound in radians until it lands.

## 4. `mech.critical_speed` -- the feldspar-pack adapter

```
crit: mech.critical_speed(turned.body, stiffness_n_per_m=1.2e7,
          mass_kg=3.0) > 12000
```

The PHYSICS lives in the feldspar solver pack (D223; charter 39
sec. 4's one-home rule); regolith carries only the route. The
friendly kwargs map onto the pack's input ports; output is rpm.
An expression bound (`1.4 * 9200rpm`) defers `unresolved_limit`
naming the expression -- entity-derived bound resolution is WO-112's
class, and the adapter never truncates an expression to its leading
factor.

## 5. Bare `mfg.unit_cost(qty=...)`

The bare form now derives its subject from the enclosing part and
picks the declared `[profiles.cost.*]` profile whose `quantity`
matches `qty=`. Where a quantity basis exists the WO-54 estimators
price it and the margin rule compares against the bound; a part
subject currently has no basis on the bare form (a named deferral --
the Rust marker emission is escalated in the WO-110 close-out).

## 6. Excluded forms

`rms(<signal>, band=[...])` jitter/ripple-floor claims are sampled-
waveform statistics -- board-level evidence outside the closed-form
pad-check boundary. They defer `excluded_call_form` naming the form;
the solver-pack channel for them is named for WO-111.
