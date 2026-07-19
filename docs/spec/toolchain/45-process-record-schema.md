# 45 -- the `std.process` record schema + DFM check-set contract (WO-168)

Decided cycle 38 (D269 items 1-2, and the same-day amendment naming
the provenance posture as a first-class owner-visible marker). This
page is the written contract WO-169/170/171's process-family
population work conforms to (charter 39 sec. 3 names WHERE process
content goes; this page names WHAT SHAPE it takes). It amends
neither AD-37 (`39-stdlib-organization.md`) nor AD-47 (charter 44
sec. 5) -- it is the schema instance those two normative documents
already point at (`RealizerCapability.process_records`/`.dfm_checks`).

## 1. Why a schema page, not just a WO body

Charter 39's "docs as part of done" principle applies to a schema
the same as to a model module: a schema with no doc page is not
"done", it is a WO body nobody dispatched from WO-169/170/171 can
find without re-reading WO-168 itself. This page is that find point.

## 2. `ProcessRecord` (`regolith.harness.models.dfm.process_records`)

One process family's capability envelope:

| field | shape | notes |
|---|---|---|
| `key` | `str` | AD-37 stdlib key (`std.process/<family>`) |
| `name` | `str` | human name |
| `din_8580_class` | `str` | DIN 8580 classification code (process identity) |
| `materials` | `tuple[str, ...]` | `std.materials` keys, never free text |
| `size_limits` | `tuple[SizeLimit, ...]` | min/max envelope, `DimensionedValue`-carrying (D262/INV-34 -- bare floats refused) |
| `tolerance_grades` | `tuple[ToleranceGrade, ...]` | achievable tolerance class(es), per stated condition |
| `surface_finish` | `tuple[SurfaceFinishEntry, ...]` | achievable Ra range(s), per stated condition |
| `min_features` | `tuple[MinFeature, ...]` | minimum producible feature size(s) |
| `cost_drivers` | `tuple[CostDriver, ...]` | qualitative/quantitative cost-class factors (setup, per-part, tooling amortization -- matches the dossier's own framing, no invented taxonomy) |
| `lead_class` | `str` | qualitative lead-time class |
| `provenance` | `tuple[ProvenanceNote, ...]` | REQUIRED, non-empty (D269 amendment) |
| `dfm_check_ids` | `tuple[str, ...]` | cross-links into a `DfmCheckSet` for this family |

`size_limits`/`tolerance_grades`/`surface_finish`/`min_features` all
route their numeric content through `regolith.backends.quantity.
DimensionedValue` (WO-150/D262) -- a bare `float` is a construction
error at every one of these fields, not merely at top level.

## 3. Provenance posture (D269 amendment)

`ProvenanceNote` is the owner-visible posture marker, REQUIRED on
every `ProcessRecord` (as a non-empty tuple) and on every
`DfmCheckEntry` (singular, since a check can cite more specifically
than its record's blanket posture). Three postures, each with its
own required-field shape (a note missing the fields its posture
demands is refused at construction, mirroring `DimensionedValue`'s
own missing-unit refusal):

- `pd_gov` -- a spot-verified public-domain/government/standards
  source; `detail` carries the citation.
- `gek` -- general-engineering-consensus, no citable government/
  standards source; `detail` states the consensus plainly, NEVER
  phrased as if cited (the process-research recon found this is the
  dominant posture, ~78 of 100 dossier entries -- this schema names
  that reality rather than dressing it up).
- `named_refusal` -- a SPECIFIC copyrighted table/source is named and
  declined; `refused_source` names it, `detail` says what was
  omitted, `lift_condition` says what would make the refusal
  liftable.

A record's `provenance` is a TUPLE, not a single enum, because
roughly 20% of dossier entries mix a blanket `gek` posture with a
`named_refusal` sub-note for one specific field (`scope == "record"`
is the blanket note; any other `scope` value names the field/value-
group it covers).

## 4. `DfmCheckSet` (the check-set CONTRACT, not the checks)

`DfmCheckSet` names the shape a process family's DFM check set must
conform to: a non-empty tuple of `DfmCheckEntry`, each an AD-47-style
module-qualified `check_id` (`"module.path:function_name"`, the SAME
convention `RealizerCapability.dfm_checks` already uses) plus its OWN
`ProvenanceNote`. The checks THEMSELVES -- the actual callables named
by those ids -- are population work (WO-169/170/171, or an existing
family like mech's `check_stock_fit`/`check_tool_fit`
(`regolith.harness.models.dfm.checks`), which this contract
generalizes honestly: every check callable is pure, takes declared-
data arguments specific to its family, and returns the ONE reused
`CamOutcome` verdict shape (excess/eps/indeterminate/citations/note)
-- no bespoke per-family result type.

## 5. Wiring into the AD-47 capability registry

`RealizerCapability.process_records`/`.dfm_checks`
(`regolith.backends.capabilities`, WO-164) are plain string tuples;
a capability registration references a `ProcessRecord.key` and a
`DfmCheckSet`'s `check_id`s directly, with no type mismatch --
`tests/harness/test_process_records.py::
test_seed_record_and_check_set_wire_into_a_capability` proves the
wiring against a dummy `wire_edm_toy` domain registration.

## 6. Seed records (deliverable 4, schema exercise only)

Two seed `ProcessRecord`/`DfmCheckSet` pairs exercise the schema end
to end (`regolith.harness.models.dfm.process_seeds`), both D269
Tier-1 families, values transcribed verbatim from the process-
research recon dossiers with their provenance classes PRESERVED:

- `WIRE_EDM_RECORD`/`WIRE_EDM_CHECKS` -- wire EDM (DIN 8580 3.2.3),
  entirely `gek`-postured (no PD-GOV source was independently
  verified for wire-EDM process parameters) plus a `named_refusal`
  for vendor speeds/feeds/Ra-lookup tables.
- `QUENCH_TEMPER_RECORD`/`QUENCH_TEMPER_CHECKS` -- quench + temper
  (DIN 8580 4.2), the dossier's strongest-sourced entry (`pd_gov`,
  MIL-H-6875) plus a `named_refusal` for ASM Handbook per-alloy
  tempering-curve charts (the sanctioned path to a PREDICTED, not
  transcribed, curve is feldspar T-0018's Hollomon-Jaffe-class model
  per D270 ruling 1).

Bulk population across the rest of the priority list (heat-treat
family depth, stamping/blanking/press-brake, grinding, shot peening,
black oxide, PCB fab/SMT DFM formalization) is explicitly WO-169/
170/171's scope, not this WO's.

## 7. Reopen criteria

The three-posture vocabulary reopens only if the owner directs a
fourth posture (e.g. a "vendor-licensed" tier once a licensing path
exists) -- recorded as a new D-number, never silently added. The
`SizeLimit`/`ToleranceGrade`/`SurfaceFinishEntry`/`MinFeature`/
`CostDriver` per-value-group shapes reopen only with evidence a real
population wave (WO-169/170/171) hit a family that genuinely cannot
be expressed in one of them (recorded per family, not guessed ahead
of time).
