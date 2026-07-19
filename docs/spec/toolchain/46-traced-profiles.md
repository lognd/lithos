# 46 -- Traced profiles: the `.rgp` format (WO-146, D261)

> Ratifies the `.rgp` ("regolith profile") format as the industrial-
> design handoff for scan-traced 2D geometry, entering through the
> ALREADY-SETTLED extern-profile seam (`docs/spec/hematite/
> 02-language.md` sec. on profiles; the `formats` package kind,
> `docs/spec/regolith/11-packages-and-stdlib.md` sec. 2). This is a
> paper ratification: the schema, the calibration ladder, the
> mandatory provenance, and the diagnostics named here have zero
> remaining design decisions for WO-147 (Rust schema + elaboration)
> to invent. Spec: D259 (structural boundary), D260 (authoring-
> surface family), D261 rulings 1-5 (this WO's charter).

## 1. What a `.rgp` file is

A `.rgp` file is a transparent TOML document, schema single-sourced
in Rust via schemars like every other extern payload (D261 ruling 1).
It is human-readable and hand-writable: a human with a ruler and a
text editor can author one directly, without graphite, without a
GUI, and without any tool the compiler could distinguish from a
hand-authored file. That indistinguishability is the D253/D259
compliance proof (D261 ruling 1) -- restated here verbatim as the
compliance statement this format must satisfy:

> "No new lithos surface accepts data from graphite at runtime. The
> lithos-side work is a file format + its elaboration in ordinary
> lowering -- the compiler cannot tell whether a traced-profile file
> was written by graphite, by hand, or by a vendor. (That
> indistinguishability is the proof the boundary is structural.)"
> -- `scratch_recon_graphite_cad.md` sec. 5, clause 3, adopted
> verbatim by D261.

A profile stored this way is a placeless value like any other
hematite profile (`docs/spec/hematite/02-language.md`'s "export
anchoring" rule): it acquires 3D existence only through an
instantiating feature.

## 2. Trust posture: traced profile = CITED GEOMETRY

A traced profile is CITED GEOMETRY (D259), in the same structured-
citation family as D257 ruling 2 (stdlib datasheet values) and the
`Cited[T]`/`Citation` model (WO-145). Its evidence posture is
AUTHORED, never model-backed or measured (D260 ruling 3): a trace
records what a human measured off a scanned object with a stated
calibration and residual, not a simulated or instrument-measured
quantity. The trust-tier/method vocabulary word ratified for traced
geometry, in coordination with the D257 citation model so ONE
citation family spans stdlib records and traced profiles, is:

- `method = "traced_scan"`
- `trust_tier = "authored"`

A trace without its scan provenance is as unrepresentable as a
datasheet value without its page (D259): every field of the
`[provenance]` table below is REQUIRED by the schema. There is no
constructor path that produces a `.rgp` geometry section without an
accompanying, complete provenance record.

## 3. Geometry (image-space)

The geometry sections store the trace in IMAGE-SPACE pixel
coordinates -- the confirmed clicks, never pre-corrected mm values.
The `[calibration]` block (sec. 4) is stored SEPARATELY; elaboration
(WO-147) applies the recorded transform deterministically at build
time to derive the mm outline. This split is load-bearing: it is
what lets a trace be re-calibrated (rung B -> rung C) by rewriting
only the `[calibration]` block, with zero re-tracing, and it is what
makes the correction auditable and re-runnable rather than hand-
carried (the same principle as never hand-editing a golden).

```toml
[profile]
name  = "group_gasket"
units = "mm"                      # the OUTPUT unit geometry derives to

[[outline]]                       # closed outline: line + arc records,
kind = "line"                     # in traced order
from = [u, v]                     # image-space pixel coordinates
to   = [u, v]

[[outline]]
kind   = "arc"
from   = [u, v]
to     = [u, v]
center = [u, v]
sense  = "cw"                     # cw | ccw

[[hole]]                          # named inner loop, ONE nesting level
name = "bolt_a"
# ... same line/arc record shape as [[outline]], nested under this hole

[[datum]]                         # named exported datum points/axes
name = "gasket_plane"
kind = "point"                    # point | axis
at   = [u, v]
```

Constraints on the closed set (matching `02-language.md`'s own
rules, not a new grammar):

- The outline is a single closed loop; holes are named inner loops
  at ONE nesting level (`02-language.md` sec. on hole/regions) --
  no nested holes-within-holes.
- Arcs are true circular arcs (center + sense); smooth traced curves
  that are not true arcs are arc-fit polylines with the fit residual
  recorded in provenance (`02-language.md`'s "freehand splines do
  not exist" rule; `scratch_recon_graphite_cad.md` sec. 7b).
- No constraint solving: v1 traces are measurements, fully pinned
  (sec. 7b of the recon). Promotion to a parametric native profile
  is v1.5, out of scope here.

## 4. The `[calibration]` block: the ladder

The calibration block records which rung was fitted, its
observations, its parameters, and its residual -- stored separately
from the geometry it corrects. Whatever the rung, the record always
carries the reprojection residual in mm AT THE OBJECT PLANE and a
declared accuracy bound (D259's owner addition).

```toml
[calibration]
model = "scale"                   # scale | homography | homography+radial

[calibration.target]
kind        = "grid"              # points | scale_bar | grid
grid_pitch  = "10mm"
grid_count  = [8, 6]               # [cols, rows], MxN
pitch_basis = "printed"           # measured | certified | printed

[[calibration.observations]]      # image-space, raw, CONFIRMED
image_px   = [u, v]
grid_index = [i, j]               # or omitted for non-grid targets
confirmed  = true

[calibration.params]
# exactly the fields the chosen model needs:
mm_per_px = 0.0                   # model = scale
# H = [[...]]                     # model = homography (3x3)
# H = [[...]]                     # model = homography+radial
# k1 = 0.0
# k2 = 0.0
# p1 = 0.0                        # tangential, only if residual demands it
# p2 = 0.0

residual_rms_mm    = 0.0
residual_max_mm    = 0.0
accuracy_bound_mm  = 0.0          # declared, conservative,
                                  # >= residual_max_mm
```

### 4a. The calibration ladder (D261 ruling 2)

Three rungs, each strictly more capable, each named in provenance:

- **Rung A, `scale`** -- 2+ reference points with a known distance
  -> similarity transform (uniform scale + rotation; least-squares
  over >=3 points). Flatbed-scan grade -- honest ONLY when the
  optics are orthographic. **v1.**
- **Rung B, `homography`** -- 4+ points on a known planar target (a
  reference rectangle, or any 4+ grid intersections of known pitch)
  -> projective homography via DLT. Corrects perspective/keystone
  for a planar object. Closed-form linear algebra, dependency-free.
  **v1.**
- **Rung C, `homography+radial`** -- an NxM grid of known pitch
  placed behind/under the object -> homography PLUS non-linear lens
  distortion (radial k1/k2; tangential p1/p2 only if the residual
  demands it), the standard Zhang-style planar-target formulation.
  **v1.1, WO-G14.** Grid observations are captured from day one
  (even at rung B), so a rung-B trace re-calibrates to rung C later
  with ZERO re-tracing (D261 ruling 2's staging argument).

`pitch_basis` (D261 ruling 4) is mandatory in `[calibration.target]`
because a printed paper grid's pitch error (0.2-0.5%) dominates the
accuracy budget and must be declared, not assumed away:
`measured` (the grid was itself measured with an instrument),
`certified` (a manufactured/certified target), or `printed`
(nominal print pitch, unverified -- the honest default for a
home-printed grid).

## 5. The `[provenance]` table (mandatory, every field required)

Uncited traced geometry is unrepresentable: every field below is
required by the schema, matching the house evidence shape
(`evidence = { method, trust_tier, reference }`,
`stdlib/std.power/records/conductor_ampacity.toml:24`) extended with
the structured fields D257's citation family uses.

```toml
[provenance]
method     = "traced_scan"
trust_tier = "authored"

[provenance.scan]
file         = "traced/scans/group_gasket.png"
content_hash = "blake3:..."
captured     = "2026-07-16"
capture_kind = "flatbed_scan"     # flatbed_scan | photo | drawing_scan

# [calibration] -- sec. 4 above, embedded here in the full record

[provenance.tracer]
by        = "j.doe"
date      = "2026-07-16"
assisted  = "none"                # none | edge_detect
confirmed = true
```

## 6. Diagnostics (rules named here; codes assigned at WO-147)

Each of the following is a real diagnostic, named as a RULE by this
spec; the concrete E-family code number is assigned when WO-147
elaborates the schema in Rust:

1. **Tolerance-tighter-than-accuracy.** A consuming claim/fit whose
   tolerance is tighter than the profile's `accuracy_bound_mm` is a
   diagnostic: the trace cannot honestly back a claim it was not
   calibrated to support.
2. **Inconsistent declared bound.** `accuracy_bound_mm <
   residual_max_mm` is a diagnostic: a declared bound tighter than
   the calibration's own measured error is a false confidence
   claim, not a stricter one.
3. **Uncorrected-perspective claim.** `capture_kind = "photo"` paired
   with `model = "scale"` is a diagnostic: an uncorrected
   perspective image cannot honestly claim a uniform-scale (rung A)
   transform; a photo demands at least rung B (homography).

## 7. The extern seam (elaboration, WO-147)

The trace enters through the settled hematite extern-profile slot:

```hematite
profile GroupGasket: extern("traced/group_gasket.rgp", rgp)
```

`rgp` is named beside `dxf` as a transparent format in the two
already-settled sections (`docs/spec/hematite/02-language.md`'s
profile-extern rule and the `formats` package-kind table,
`docs/spec/regolith/11-packages-and-stdlib.md` sec. 2). Elaboration
(WO-147) parses the TOML, checks closure/nesting/arc validity/
provenance completeness (each failure a real diagnostic per WO-131
law), applies the `[calibration]` transform deterministically to the
image-space points, and produces the resolved sketch-layer payload
the realizer already consumes (the `resolve_extrusion_outline`
shape) -- no promotion-surface change, no constraint solving.

## 8. Out of scope (elsewhere)

- Rust schema code, schemars derive, SCHEMA_VERSION change,
  elaboration diagnostics as real E-codes -- WO-147.
- Python realizer/citation/artifact-index consumption -- WO-148.
- graphite-side authoring tooling (the studio, calibration UI,
  trace tools) -- WO-G11..G14, separate repo.
- The calibration ladder's design, the extern seam's existence, or
  the source-representation choice -- D259/D261 already settled
  these; this document records them, it does not re-derive them.

## 9. Stub fixture

`examples/fixtures/traced_profiles/group_gasket_stub.rgp` is a
hand-written, non-graphite example demonstrating a human can author
one directly, proving the declarative non-GUI path holds per the
D259/D260 admission test.
