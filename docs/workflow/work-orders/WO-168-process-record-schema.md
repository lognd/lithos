# WO-168 -- `std.process` record schema + DFM check-set contract (D269 item 1)

Status: open (Depends: WO-164 [capability registry -- this schema's
  fields must line up with `process_records`/`dfm_checks` on
  `RealizerCapability`])
Language: Python (pydantic schema under `stdlib/` tooling +
  `tools/stdlib/` per the existing stdlib organization,
  `docs/spec/toolchain/39-stdlib-organization.md`, AD-37).
Spec: `docs/workflow/design-log/2026-07-19-cycle-38.md` D269 items
  1-2 and the same-day amendment (GEK posture as a first-class
  marker); `docs/spec/toolchain/39-stdlib-organization.md` (AD-37
  naming/citation law -- read in full, this schema is an instance of
  it, not a replacement); the process-research dossiers under the
  session scratchpad (`procres/*.md` -- the reference pack for what
  fields a real process record needs; convert their
  PROVENANCE-CLASS marking scheme, described in `procres/rollup.md`'s
  "Provenance-class distribution" section, into a required posture
  field on the schema, per this WO's own directive).

## Goal

ONE `std.process` record schema (a capabilities envelope: materials,
size limits, tolerance grades, surface finish, min features, cost
drivers, lead-class) + a DFM check-set CONTRACT per family (not the
checks themselves -- the shape a family's check set must conform to),
both under AD-37 naming/citation law and feeding `RealizerCapability`'s
`process_records`/`dfm_checks` fields directly. Schema first, data
population is WO-169/170/171.

## Deliverables

1. `ProcessRecord` pydantic model (`ConfigDict(frozen=True)`):
   - `materials: list[str]` (references into `std.materials`, not
     free text),
   - `size_limits`: min/max envelope (unit-carrying, `DimensionedValue`
     per D262/WO-150 -- INV-34 covers dimensioned values, reuse it,
     do not invent bare floats),
   - `tolerance_grades`: achievable tolerance class(es),
   - `surface_finish`: achievable Ra range or equivalent,
   - `min_features`: minimum feature size(s) the process can produce,
   - `cost_drivers`: qualitative/quantitative cost-class factors
     (setup, per-part, tooling amortization class -- match the
     dossier's own cost-driver framing, do not invent a new taxonomy),
   - `lead_class`: qualitative lead-time class,
   - `provenance`: THE OWNER-VISIBLE POSTURE MARKER (required, not
     optional) -- one of `pd_gov` (a spot-verified public-domain/
     government source, with the citation), `gek` (general-
     engineering-consensus, no citable government/standards source --
     MUST say so plainly, never presented as if cited), or
     `named_refusal` (a specific copyrighted table/source is named
     and explicitly declined, with a note on what was omitted and
     why). A record MAY combine `gek` for most fields with a
     `named_refusal` sub-note for one specific field (mirror the
     dossier's finding that ~20% of entries carry both) -- model this
     as a list of per-field-or-whole-record posture notes, not a
     single enum forced to pick one.
2. `DfmCheckSet` contract: a check-set for a process family is a list
   of check identifiers, each with its OWN citation/provenance note
   (checks can cite more specifically than the record's blanket
   posture -- e.g. a record mostly `gek` but one specific DFM rule
   spot-verified `pd_gov`).
3. Wire both into `RealizerCapability.process_records`/`.dfm_checks`
   (WO-164) so a capability registration can point at real
   `std.process` records/check-sets once WO-169/170/171 populate
   them.
4. Docs: a new `docs/spec/toolchain/` addendum (or a `stdlib/`-local
   README) documenting the schema, cross-referencing AD-37 and this
   WO's provenance-marker rationale, so WO-169/170/171's population
   work has a written contract to conform to (not just this WO's
   body -- a genuinely dispatchable schema needs its own doc page per
   the "docs as part of done" principle).

## Non-goals

- No process DATA population in this WO -- schema and contract only.
- No change to `std.materials` (T-0038's scope) beyond referencing it
  by name in `materials: list[str]`.

## Acceptance

- `ProcessRecord`/`DfmCheckSet` pydantic models exist, `provenance`
  is a required field on both with no default, and a round-trip
  test constructs one instance of each posture value (`pd_gov`,
  `gek`, `named_refusal`, and the combined case) and asserts
  (de)serialization.
- `RealizerCapability.process_records`/`.dfm_checks` (WO-164) can
  reference a `ProcessRecord`/`DfmCheckSet` instance without type
  mismatch (a small integration test wiring one dummy record through
  a dummy capability registration).
- Docs page exists and is linked into the doc graph (DOC001 clean for
  it).
- `make check` green.
</content>
