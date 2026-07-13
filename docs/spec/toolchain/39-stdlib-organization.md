# 39 -- stdlib organization (normative)

Decided cycle 35 (D227, owner directive 2026-07-13; AD-37). This
charter codifies how the `std.` catalog and its adjacent model/
solver homes are organized: where every kind of content GOES, what
it is NAMED, and the metadata bar it must meet. It promotes the
working rules already carried by `stdlib/README.md` (D135, D58),
WO-45/WO-66, and D153 into one normative surface. The feldspar
counterpart is feldspar `docs/spec/12-solver-organization.md`;
the two documents carry the SAME boundary rule (sec. 4) and must
not drift.

## 1. Namespace taxonomy

1. `std.` is a RESERVED registry prefix (regolith/11 sec. 8): only
   the lithos project publishes under it.
2. `std.<domain>` -- one engineering domain per package
   (`std.mech`, `std.elec`, `std.fluid`, `std.civil`,
   `std.materials`, `std.cost`, ...). A domain package holds that
   domain's records, interface/mating packs, and process packs.
3. `std.<domain>.<family>` -- pattern/family libraries under their
   domain (`std.mech.mechanisms`, `std.elec.patterns`,
   `std.elec.stackups`): D144/AD-28 recognition-and-advice packs
   and parametric family catalogs.
4. Vendor/fab content is NEVER under `std.`: vendor-named packages
   ride beside it (`jlc_2l`, `ti.logic`, `st.mcu`,
   `microchip.cpld`), same directory layout, same metadata bar.
5. Nominal packages (namespace declared, content lives elsewhere
   for a recorded load-bearing reason) are permitted only with the
   reason in the package README -- the two standing cases are
   `std.quantities` (math in `regolith-qty`, L1 load-bearing) and
   `std.models` (code in `python/regolith/harness/models/`,
   sec. 3.2).

## 2. Package anatomy

Each `stdlib/<package>/` is a real magnetite package:

1. `magnetite.toml` -- the manifest; the package resolves through
   the ordinary D192/D201 record-path machinery, no special-casing.
2. `records/*.toml` -- parametric record families; ONE family per
   file (`sections.toml`, `bearings.toml`, `e_series.toml`); files
   are ADDITIVE-ONLY once published (sec. 5.3).
3. Track-source packs (`.hema`/`.cupr`/`.fluo`/`.calx` files at
   package root) -- interface/mating/verb/rule/advice content in
   the language the consuming track reads.
4. A package README only where a nominal-package reason or a
   generation note must be recorded; content documentation
   otherwise lives in the records themselves (citations in-row).

## 3. Content classes and where each goes

1. TRANSCRIBED REAL-WORLD DATA (datasheet, handbook, code table):
   `records/*.toml` rows, `tier=community` (D58 -- unsigned
   content never claims higher), source + edition cited IN-ROW.
   A value that cannot be cited is OMITTED with a note, never
   guessed (the fabricated-precision rule).
2. CLOSED-FORM CHECKS -- the calculation an engineer does on a pad:
   deterministic, non-iterative (or bounded fixed iteration),
   single-formula-family -- live as lithos built-ins in
   `python/regolith/harness/models/`, and the `std.models`
   manifest NAMES them (the code-does-not-move rule, D153). Every
   model module carries its citation in the docstring and a
   calibration test against a published worked example.
3. NUMERICS AND EVIDENCE-GRADE SOLVING -- iteration to convergence,
   discretization (FEA/CFD), planning/routing over solver graphs,
   spice/verilator-class external engines, anything intended to
   discharge at `certified` tier -- belong to the feldspar solver
   pack, organized per feldspar spec 12, reached through the
   plugin seam (AD-26) and the pack contract
   (20-solver-abstraction.md sec. 7). Lithos never grows a private
   numeric solver.
4. RECOGNITION + ADVICE (pattern libraries): `advise:`-only packs
   under `std.<domain>.<family>` (D144/AD-28); they never gate.
5. GENERATED CATALOG BATCHES (E-series, AISC sections): produced
   by `tools/stdlib` generators, marked generated in-file, covered
   by the drift check -- regenerated, never hand-edited (WO-66).

## 4. The boundary rule (shared verbatim with feldspar spec 12)

A model belongs in lithos `harness/models/` iff ALL hold: closed
form from a citable source; deterministic with at most bounded
fixed iteration; inputs/outputs are scalars-with-units already in
the claim vocabulary; community tier suffices. Otherwise it belongs
in feldspar. A model moving across the boundary is a migration with
a design-log entry, never a copy -- the SAME physics must never be
resolvable from two homes (the duplication rule applied to models;
the router prefers the pack when both could answer, and the
built-in is retired in the same change).

## 5. Naming and growth discipline

1. Claim kinds and model ids are dotted lowercase paths
   `<domain>.<family>.<quantity>` (`mech.bearing.l10_hours`,
   `mech.beam.cantilever_deflection`); the id IS the routing key
   (WO-109), so it never encodes tier, solver home, or vendor.
2. Built-in model modules: flat `<domain>_<topic>.py` files in
   `harness/models/`; a family earning more than ~three modules
   graduates to a subdirectory (`cam/`, `hdl/` are the standing
   examples) in a structure-only commit.
3. Record files are additive-only: new rows append, new families
   get new files, renames/removals are migrations with a
   design-log entry and a corpus sweep in the same change.
4. Every organization rule in this charter is machine-checked
   where mechanically checkable (WO-118): std.-prefix reservation,
   one-family-per-file, citation presence on rows and model
   docstrings, generated-file drift, boundary-rule double-home
   detection (no claim kind resolvable from both a built-in and a
   pack without a recorded preference). The checks live in the
   health consistency leg.

## 6. Reopen criteria

Sec. 4's boundary moves only with evidence a closed-form built-in
genuinely needs pack machinery (or vice versa) -- recorded, per
model. Vendor-content policy (sec. 1.4) reopens only if the
registry gains a vendor-verification tier (INV-14 extension, owner
territory).
