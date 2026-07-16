# WO-146 -- traced-profile format spec + `.rgp` ratification (D261.3/D259)

Status: open (docs-only; NOT window-gated -- may run before or
  parallel to the D256 hash window since it touches no code and no
  goldens)
Language: docs (spec sections + design-log ratification entry). No
  Rust, no Python.
Spec: D259 (`docs/workflow/design-log/2026-07-16-cycle-37.md`: the
  structural boundary -- graphite authors NEW source, never edits
  semantics; a trace's provenance record is CITED GEOMETRY in the
  D257 structured-citation family; the calibration ladder -- uniform
  scale, projective homography, N-point grid + non-linear distortion
  -- and its provenance requirements); D260 (authoring-surface family
  rules: admission test, NO BLIND FEATURES post-completion feature
  audit, evidence-posture honesty); D261 rulings 1-5 (the extern seam
  is ALREADY SETTLED -- hematite 02's extern profile slot, a
  transparent TOML format, schemars-single-sourced, image-space
  points + calibration transform stored SEPARATELY, provenance a
  required field; calibration rungs A+B in v1, rung C is WO-G14/v1.1;
  edge-detect assist deferred; `pitch_basis` in provenance; the
  trust-tier/method vocabulary word settled here in coordination with
  D257's citation model); `docs/spec/hematite/02-language.md:155-159`
  (the settled extern-profile seam this WO elaborates, not
  redesigns); `docs/spec/toolchain/08-lowering-architecture.md` sec.
  4 (L3 external-link row: "by extern on transparent formats ...
  elaborated into design IR; full static checks run" -- names `dxf`
  today, this WO adds `rgp` beside it); `scratch_recon_graphite_cad.md`
  secs. 6-7 (the `.rgp` schema sketch, the calibration-ladder design,
  and the WO decomposition this WO elaborates verbatim -- NOTE the
  recon's internal numbering (WO-138..141) is SUPERSEDED by D261's
  renumbering to WO-146..149; this file uses the D261 numbers
  throughout).

## Goal

The `.rgp` ("regolith profile") format is a ratified, spec-first
design: a named extension beside `dxf` in the two already-settled
sections, its own spec section carrying the full schema (geometry,
calibration block, mandatory provenance), the accuracy/consistency
diagnostics it requires, and the design-log entry recording the
ratification -- so WO-147 has a normative document to implement
against with zero remaining design decisions.

## Deliverables

1. New spec section (`docs/spec/toolchain/44-traced-profiles.md`,
   or a hematite 02 subsection plus a regolith format appendix --
   coordinator's placement call at dispatch time, recorded in the
   close-out) containing:
   - The `.rgp` TOML schema: units; closed outline of vertices + arc
     records; named hole loops (ONE nesting level, per
     `02-language.md:150-152`); named exported datum points/axes;
     all stored in IMAGE-SPACE pixel coordinates.
   - The `[calibration]` block: `model` (`scale` | `homography` |
     `homography+radial`), `target` (kind, grid_pitch, grid_count,
     `pitch_basis` = `measured` | `certified` | `printed`),
     `observations` (image-space points, confirmed), `params`
     (mm_per_px | H | H+k1,k2[,p1,p2]), `residual_rms_mm`,
     `residual_max_mm`, `accuracy_bound_mm` -- stored SEPARATELY from
     the mm geometry, which elaboration DERIVES deterministically
     (never hand-carried).
   - The `[provenance]` table (mandatory, every field required --
     uncited traced geometry is unrepresentable): `method =
     "traced_scan"`, `trust_tier` (the word ratified by ruling 4
     below), `scan { file, content_hash, captured, capture_kind }`,
     the `[calibration]` block above, `tracer { by, date, assisted,
     confirmed }`.
   - The accuracy/consistency diagnostics named in the recon sec.
     7c: a consuming claim/fit whose tolerance is tighter than
     `accuracy_bound_mm`; `accuracy_bound_mm < residual_max_mm`
     (a declared bound tighter than the calibration's own error);
     `capture_kind = photo` with `model = scale` (an uncorrected
     perspective image cannot honestly claim uniform scale) -- each
     a real diagnostic code (E-family assigned at WO-147, this spec
     names the RULE, not the code number).
2. Two one-line amendments naming `rgp` beside `dxf`:
   `docs/spec/hematite/02-language.md:155-159` and
   `docs/spec/toolchain/08-lowering-architecture.md` sec. 4's L3 row.
3. A design-log entry (new cycle-37 `D-*` number, coordinator-assigned
   at integration) recording the D259 sec. 5 structural-boundary
   ruling VERBATIM (the recon already drafted it, sec. 5) as the
   normative statement of why this format is source-only-compliant --
   this is the ratification act, not a re-argument.
4. The trust-tier/method vocabulary word for traced geometry, settled
   in coordination with the D257 `Citation`/`Cited[T]` structured-
   citation model (WO-145) so ONE citation family spans stdlib
   records and traced profiles -- named explicitly in the new spec
   section, not left as a strawman.
5. A stub `.rgp` example fixture (hand-written, no graphite involved)
   demonstrating a human can author one directly -- proving the
   declarative non-GUI path holds per D259/D260's admission test.

## Out of scope

- Any Rust schema code, schemars derive, or SCHEMA_VERSION change --
  that is WO-147.
- Any Python realizer/lowering consumption -- WO-148.
- Any graphite-side code -- WO-G11/G12/G13/G14 (separate repo,
  separate worktree).
- Redesigning the calibration ladder, the extern seam, or the
  source-representation choice -- D259/D261 already settled these;
  this WO documents them, it does not re-litigate them.

## Acceptance

- The new spec section exists and is grep-checkable for every
  required schema field named above: `grep -n
  "residual_rms_mm\|accuracy_bound_mm\|pitch_basis" docs/spec/toolchain/44-traced-profiles.md`
  (or wherever placed) returns all three.
- `grep -n "rgp" docs/spec/hematite/02-language.md
  docs/spec/toolchain/08-lowering-architecture.md` shows the
  extension named beside `dxf` in both files.
- A design-log entry exists for this cycle recording the D259 sec. 5
  ratification verbatim, cross-referenced by its own D-number.
- The trust-tier/method word is named in the spec text (not a TBD
  placeholder): `grep -n "trust_tier" docs/spec/toolchain/44-traced-profiles.md`
  shows a concrete value, not a bracketed placeholder.
- The stub `.rgp` fixture exists, is valid TOML, and a human reading
  only this WO's spec section could have hand-authored it:
  `python -c "import tomllib; tomllib.load(open('<fixture-path>','rb'))"`
  parses without error.
- `make check` green (docs-only, but the gate still runs).

## Escalation

If the coordinator's placement call (new charter file vs. hematite
02 subsection) turns out to conflict with an existing charter
numbering convention, escalate to `00-architecture.md`'s charter
list rather than inventing a numbering scheme; this is a
documentation-organization question, not a design question -- the
schema content itself is not reopened by this escalation.
