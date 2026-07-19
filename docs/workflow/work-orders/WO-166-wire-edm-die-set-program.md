# WO-166 -- wire-EDM die-set production program (D268 item 1, D269 sequencing)

Status: open (Depends: WO-164 [capability registry]; T-0038 [stdlib
  materials records -- die-set materials, D2/A2 tool steel, 1018/A36
  mild plate]; feldspar T-0018 [material-state/heat-treat MODELS --
  cross-repo, this WO consumes its outputs, does not implement them];
  WO-169 [process population wave 1 -- EDM/heat-treat/stamping/
  grinding/shot-peen records + DFM this program's slices consume];
  internally sequenced a -> b -> c -> d, see below)
Language: mixed per slice -- (a) is stdlib+records (data, no code
  language distinction beyond TOML/schema); (b) is Rust
  (`regolith-syntax`/`regolith-lower` for the new program-kind verb)
  + Python (realizer emission); (c) is Python (assembly composition,
  reusing WO-72's bolted-joint precedent); (d) is a demo, no new code
  beyond wiring the prior three together.
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 5 (AD-47);
  `docs/workflow/design-log/2026-07-19-cycle-38.md` D268 item 3 (the
  four named prerequisites: material-state modeling, profile-cut
  program kind, die-set assembly composition, EDM process records +
  DFM) and D269's amendment (shot peening enters this chain as
  recast-layer remediation; press-brake/stamping DFM lands with this
  wave); `docs/spec/hematite/03-contracts-and-assemblies.md` (existing
  mating/stackup machinery, reused not reinvented);
  `docs/workflow/work-orders/WO-72-flagship-cnc-router.md` (bolted-
  joint precedent); `docs/workflow/work-orders/WO-77-material-removal-
  vocabulary.md` (the Bore/CBore/Pierce/Bend verb idiom this program's
  new verb should mirror); the recon dossier
  `scratch_recon_cuprite_sim_gate.md`/`recon-capability-gaps.md`
  TARGET 1 section (this repo's session scratchpad -- the concrete
  "Missing" list this WO closes: wire EDM, heat treatment, D2/A2
  records, EDM-specific output emission, die-set assembly semantics).

## Goal

Produce, in an automated pass: a hardened tool-steel part profiled
on wire EDM, bolted to a mild-steel plate as a stamping die set --
end to end, honestly, with every claim (hardness, cut tolerance,
press fit) backed by a real model or a named refusal, never an
invented constant.

## Slice (a) -- material-state modeling

- Consumes feldspar T-0018 (TTT/CCT-class transformation models,
  Koistinen-Marburger martensite fraction, Grossmann ideal critical
  diameter, Jominy correlations, Hollomon-Jaffe tempering -- ALL
  MODELS, feldspar's side, not this WO's to implement) and lithos
  T-0038 (D2/A2 tool-steel + 1018/A36 mild-plate RECORDS -- also not
  this WO's to implement, but this slice's registration below reads
  their output shape).
- Deliverable: a material STATE representation in lithos (language +
  stdlib glue, not the model math itself) -- a `heat_treat_state`
  field/kind on a material reference (e.g. `as_rolled` vs.
  `quenched_and_tempered(temper_temp)` vs. `through_hardened(HRC)`),
  consumed by DFM checks and by the die-set assembly (item c) for
  fit/wear reasoning. This is genuinely new language/stdlib surface
  per the recon dossier's "zero representation anywhere" finding --
  escalate to a design-log entry if the existing hematite material-
  reference grammar cannot express a parameterized state variant
  without a grammar change (do not invent grammar unilaterally).

## Slice (b) -- profile-cut program kind

- A new feature-program verb (mirroring WO-77's `Ribs`/`PocketGrid`/
  `Shell`/`Lattice` idiom): `WireEdmProfile(profile_ref, kerf,
  lead_in)` or equivalent naming -- 2D contour + lead-ins, distinct
  from milling removal ops (this is a THROUGH-CUT along a closed or
  open profile, not a pocket/bore).
- Realizer emission: a wire-EDM-specific artifact family (an
  EDM-class DXF-profile-plus-cut-parameters format, or reuse of the
  existing DXF format per `docs/spec/toolchain/25-drawings-and-
  artifacts.md` extended with kerf/lead-in metadata -- prefer reusing
  DXF's existing role as a transparent output format over inventing a
  new file format, per the recon dossier's note that DXF today is
  INPUT-side only for sheet-metal flat patterns; this WO makes it (or
  a sibling) an OUTPUT format too). Registered via WO-161's
  path-pattern classification and WO-160's provenance tier
  (`deterministic` for v1 -- no real EDM-machine tool adapter is
  claimed unless a real toolpath post-processor exists; name this
  explicitly).

## Slice (c) -- die-set assembly composition + stamping DFM

- Die-set assembly: two (or more) plates in a bolted stack (reuse
  `std.fasteners` records + the existing contract/mating graph per
  `hematite/03-contracts-and-assemblies.md` -- no new assembly
  primitive needed per the recon dossier's own finding that the
  generic mating graph already expresses bolted flat plates
  geometrically). New DIE-SET-SPECIFIC checks: guide-pin/bushing
  alignment tolerance stack, shut height, and a press-tonnage check
  (tonnage vs. material/thickness/perimeter -- a real closed-form
  model, cited, or a named refusal if no citable closed-form exists
  at v1 scope; do not invent a tonnage formula without a source).
- Stamping/punch-die-clearance DFM per the D269-amendment finding
  (punch-die clearance is a NAMED REFUSAL family -- Machinery's
  Handbook/ASM Sheet Metal Forming Handbook class tables are NOT
  transcribed; use whatever closed-form clearance-percent-of-
  thickness guidance the WO-169 process records land with a citable
  public-domain source, and refuse (named, not silent) anything that
  would require transcribing the copyrighted table).
- Shot-peening recast-layer remediation step (D269 amendment): after
  wire-EDM cutting, the recast layer is a real metallurgical concern;
  model it as an optional post-process step consuming WO-169's
  shot-peen process record, not a hard requirement (name it as
  optional per the honest-demo posture -- do not claim recast removal
  happened if the demo does not actually invoke the step).

## Slice (d) -- demo: a two-station die set

- A modest two-station stamping die set (e.g. a simple blank-and-
  pierce pair on a small mild-steel workpiece) realized end to end:
  material states declared -> wire-EDM profile cuts on the D2/A2
  plates -> bolted assembly with guide pins -> press-tonnage check
  passes -> committed under `demos/out/` (PROOF.md/manifest.json,
  D265 posture). This is the LARGEST-language-surface program per
  D268 item 5's sequencing note -- keep the demo's actual geometry
  modest even though the underlying language surface is large.

## Non-goals

- No sinker-EDM (only wire-EDM, per D268's literal scope).
- No production-grade press-tonnage solver beyond a cited closed-form
  check -- a full stamping-mechanics solve is out of scope.
- No transcription of any copyrighted clearance/tolerance table --
  every such need is a named refusal, recorded in the DFM check's
  own citation field, not silently worked around with an invented
  constant.

## Acceptance

- Slices (a)-(d) each land with their own `make check`-green commit
  (this WO is large enough that ticket decomposition below splits it
  into four sub-tickets; each sub-ticket's Done report maps to one
  slice).
- The slice-(d) demo directory exists with real artifacts (EDM
  profile-cut files, assembly geometry, a press-tonnage check result)
  and provenance tiers stamped per WO-160.
- Every numeric claim (hardness target, kerf, press tonnage, punch-
  die clearance) in the demo either cites a real model/source or is
  explicitly refused/deferred in the demo's own PROOF.md -- no
  invented constants.
- `RealizerCapability` registration (WO-164) for the die-set/EDM
  domain has all seven fields populated, consuming WO-169's process
  records and DFM checks (not stubs, once WO-169 lands).
- `make check` green.
</content>
