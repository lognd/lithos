# Verification harness -- Phase C status

Home: `python/rockhead/harness/` (AD-1: the harness is Python; registry
and model versions are Python-side). Spec: substrate/07 (claims,
obligations, evidence, the model registry, margin-driven discharge);
roadmap `docs/mech/06-roadmap.md` Phase C/D. This is TODO.md "PATH TO
DONE" section 6.

## What exists (this cycle)

The registry + matching spine and the FIRST closed-form model pack:

| module | role |
|---|---|
| `harness/quantity.py` | `Interval` (worst-case corner, INV-9) + exact `f64<->bits` for evidence serialization |
| `harness/signature.py` | `ModelSignature` (claim kind, `ClaimSense`, required inputs, domain tags) -- the harness-side match contract |
| `harness/evidence.py` | the ONE margin rule (`value +- eps` vs limit, sec. 4) + the evidence content hash |
| `harness/model.py` | `Model` ABC + `DischargeRequest`/`Prediction`; the shared discharge driver (no per-model duplication) |
| `harness/registry.py` | `ModelRegistry`: register / deterministic `candidates` / total `select` / `discharge`; `default_registry()` |
| `harness/models/buck_ripple.py` | the reference pack: CCM buck output-voltage ripple |

Properties held:

- **Total + honest selection.** `select` returns a typani `Result`; a
  no-match is `Err(NoModelMatch)`, and `discharge` maps it to an explicit
  `harness.no_model` **indeterminate** evidence value -- never a silent
  pass (substrate/07 sec. 4: indeterminate is not violated).
- **Deterministic (INV-10).** Same inputs -> byte-identical `Evidence`
  (hash + every bit field). Floats hash as exact `f64` bits; the model's
  `deterministic` flag and (for non-deterministic models) a settings
  digest are hash inputs.
- **Versioned keying (BE-1/INV-1).** The registry carries
  `harness.MODEL_REGISTRY_VERSION`, folded into every evidence hash;
  it aligns with the Rust core, which threads the same version into the
  obligation/evidence-cache key at discharge time. Bump invalidates
  cached evidence.
- **Corner conservatism (INV-9, harness-model side).** The buck pack
  evaluates the ripple formula at every interval-box corner in numpy and
  reports the worst -- sound for any input box, no hand-proved
  monotonicity.

## The reference pack

`elec.buck.output_voltage_ripple` discharges `require Regulation: ripple`
in `examples/elec/buck_converter.cupr`. Textbook CCM buck, ESR neglected
(the neglected term is charged into a conservative 5% `eps`):

    delta_i_L = v_out * (v_in - v_out) / (v_in * f_sw * L)
    v_ripple  = delta_i_L / (8 * f_sw * C_out)

Known-answer (v_in=12V, v_out=5V, f_sw=500kHz, L=22uH, C_out=47uF):
~1.4104 mV, discharged with ~18.5 mV margin under the 20 mV limit.

## Not yet built (tracked TODOs)

Extension points are `# TODO(harness)` markers in
`harness/models/__init__.py`, and the section-6 checklist in `TODO.md`:
bolted-joint preload diagram (VDI 2230), Euler-Bernoulli beam, thick-wall
Lame, sheet-metal DFM rule pack, link budget, and the buck efficiency +
transient claims. Also deferred: extracting a `DischargeRequest` from a
serialized `Obligation` (the quantity expressions are text until the
orchestrator resolves them -- orchestrator territory, AD-1), numeric /
reduced tiers, and the planner adapters.

## Invariant tests

The harness makes the INV-09 (corner) / INV-10 (determinism) guarantees
reachable on the model side, exercised directly in `tests/harness/`. The
`tests/invariants/` INV-09/10/16/19 modules stay as they are: their
xfail stubs assert deliberate-violation fixtures against the Rust
mechanisms (WO-03/11/12) and the end-to-end ladder/release layers, which
are out of this scope -- flipping them needs those layers, not the model
pack.
