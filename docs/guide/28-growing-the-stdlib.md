# Growing the stdlib

STATUS: WORKING. `docs/spec/toolchain/39-stdlib-organization.md`
(charter 39, D227/AD-37) is the NORMATIVE home for everything in this
guide -- this is a teaching view of it. The same charter's boundary
rule (sec. 4) is shared verbatim with feldspar's own
`feldspar:docs/spec/12-solver-organization.md`; the two must never drift, and
`tools/stdlib/organization.py`'s `charter_drift` check enforces that
byte-for-byte, in the health consistency leg.

Source: charter 39 (namespace taxonomy sec. 1, package anatomy sec. 2,
content classes sec. 3, the boundary rule sec. 4, naming/growth
discipline sec. 5); `stdlib/README.md` (the working index of packages
that exist today, D135/D58 history); `tools/stdlib/organization.py`
(the machine-checked half).

## Where does my new content go? A decision tree

Ask, in order:

1. **Is it transcribed real-world data** (a datasheet row, a handbook
   table, a code-mandated section property)? -> a `records/*.toml`
   row under the right `stdlib/std.<domain>/` package, `tier=community`
   (charter 39 sec. 3.1). Cite the source and edition IN-ROW. If you
   cannot cite a field, OMIT it with a note -- never guess a plausible
   number (the fabricated-precision rule, same posture as D224.1).
2. **Is it a closed-form check** -- the calculation an engineer does
   on a pad: deterministic, non-iterative (or bounded fixed
   iteration), a single formula family? -> a lithos built-in module in
   `python/regolith/harness/models/`, named by the `std.models`
   manifest (charter 39 sec. 3.2, the code-does-not-move rule, D153).
   Every model module carries its citation in the docstring and a
   calibration test against a published worked example.
3. **Does it need iteration to convergence, discretization (FEA/CFD),
   solver-graph planning/routing, or an external engine
   (spice/verilator-class), or is it intended to discharge at
   `certified` tier?** -> it belongs in the **feldspar** solver pack
   (its own repo, github.com/lognd/feldspar), organized per feldspar
   spec 12, reached through the plugin seam (AD-26). Lithos never
   grows a private numeric solver (charter 39 sec. 3.3).
4. **Is it a recognition/advice pattern** (a mount shape, a decoupling
   topology) rather than a verification claim? -> an `advise:`-only
   pack under `std.<domain>.<family>` (D144/AD-28); these never gate
   a build.
5. **Is it a generated catalog batch** (E-series resistors, AISC
   steel sections)? -> a `tools/stdlib` generator, its output marked
   generated in-file, covered by the `generated_drift` check --
   regenerate, never hand-edit (WO-66).

## The boundary rule, restated (charter 39 sec. 4)

A model belongs in lithos `harness/models/` iff ALL of these hold:
closed form from a citable source; deterministic with at most bounded
fixed iteration; inputs/outputs are scalars-with-units already in the
claim vocabulary; community tier suffices. Otherwise it belongs in
feldspar. Moving a model across the boundary is a MIGRATION with a
design-log entry, never a copy -- the same physics is never
resolvable from two homes. If both a built-in and a pack model could
answer the same claim kind, the router prefers the pack, and the
built-in is retired in the SAME change. `tools/stdlib/organization.py`'s
`double_home` check enforces this against a sibling feldspar checkout
(best-effort: it degrades honestly, never fails, when no sibling
checkout is present).

## Namespace taxonomy (charter 39 sec. 1)

- `std.` is a RESERVED registry prefix -- only lithos publishes under
  it (`prefix` check).
- `std.<domain>` -- one engineering domain per package (`std.mech`,
  `std.elec`, `std.fluid`, `std.civil`, `std.materials`, `std.cost`,
  ...): that domain's records, interface/mating packs, process packs.
- `std.<domain>.<family>` -- pattern/family libraries under their
  domain (`std.mech.mechanisms`, `std.elec.patterns`): D144/AD-28
  recognition-and-advice packs and parametric family catalogs.
- Vendor/fab content is NEVER under `std.`: it rides beside it,
  same layout, same metadata bar (`jlc_2l`, `ti.logic`, `st.mcu`,
  `microchip.cpld` are the standing examples).
- Nominal packages (namespace declared, content lives elsewhere for a
  recorded load-bearing reason) are permitted only with the reason in
  the package README -- the two standing cases: `std.quantities` (the
  math is in `regolith-qty`, L1 load-bearing) and `std.models` (the
  code is in `python/regolith/harness/models/`).

## Package anatomy (charter 39 sec. 2)

Each `stdlib/<package>/` is a real magnetite package: a
`magnetite.toml` manifest, `records/*.toml` (ONE family per file --
`sections.toml`, `bearings.toml`, `e_series.toml`; ADDITIVE-ONLY once
published), track-source packs (`.hema`/`.cupr`/`.fluo`/`.calx`) for
interface/mating/verb/rule/advice content, and a package README only
where a nominal-package reason or a generation note must be recorded
-- content documentation otherwise lives in the records themselves,
citations in-row.

## Naming (charter 39 sec. 5)

Claim kinds and model ids are dotted lowercase paths
`<domain>.<family>.<quantity>` (`mech.bearing.l10_hours`,
`mech.beam.cantilever_deflection`) -- the id IS the routing key
(WO-109), so it never encodes tier, solver home, or vendor. Built-in
model modules are flat `<domain>_<topic>.py` files in `harness/models/`;
a family earning more than ~three modules graduates to a subdirectory
(`cam/`, `hdl/` are the standing examples) in a structure-only commit.

## What's machine-checked (WO-118, charter 39 sec. 5.4)

`tools/stdlib/organization.py`, folded into the health `consistency`
leg's `organization` sub-check, and independently runnable
(`python -m tools.stdlib.organization [--check NAME]`):

| check | enforces |
|---|---|
| `prefix` | every `std.*` package lives under `stdlib/<name>/` |
| `one_family` | one array-of-tables key per `records/*.toml` (pre-existing multi-family files are a named, non-gating baseline: WO118-F1) |
| `citations` | every record row and every registered built-in model carries a citation (pre-existing uncited built-ins are a named, non-gating baseline: WO118-F2) |
| `generated_drift` | every generated catalog batch matches its generator's committed output |
| `models_manifest` | `std.models`'s manifest names every module a built-in actually registers, nothing phantom |
| `double_home` | no claim kind resolvable from both a built-in and a feldspar pack model without a recorded router preference |
| `charter_drift` | charter 39 sec. 4 and feldspar spec 12 sec. 4 (the shared boundary rule) are byte-identical modulo heading |

## feldspar, summarized

The full organization doctrine for numerics-grade content is
feldspar's own `feldspar:docs/spec/12-solver-organization.md`
-- read it there for the solver-pack-side anatomy. The one law worth
repeating here: **calibration-first**. A feldspar model is not
considered to exist until it has a calibration test against a
published closed-form worked example; a solver that has not been
checked against a known-good answer is not yet a model, it is a
guess with extra steps.

## See also

- `docs/guide/27-authoring-for-discharge.md` -- the corpus-authoring
  half (D224): using a `std.*` record you just added to declare a
  claim's inputs.
- `docs/guide/25-manufacturability-and-models.md` -- a worked example
  of the boundary rule in practice (the realized-geometry DFM channel
  stays in lithos; deeper numerics escalate to feldspar).
