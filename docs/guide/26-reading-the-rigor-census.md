# Reading the rigor census

STATUS: WORKING for the census data itself (`tests/golden/data/fleet_census.json`,
the `fleet` health leg); the PER-CLASS waiver breakdown named below as
"not yet split" is WO-117 (`Status: open`), the last WO of cycle 35 --
this guide describes what the census reports TODAY and names the
pending upgrade honestly rather than inventing it.

Source: design-log `2026-07-13-cycle-35.md` D220 (the rigor doctrine,
the law this whole guide walks), F133 (the cycle's enrichment-campaign
result); `tools/health/fleet.py` (the leg that produces the census);
`docs/guide/23-health-gate.md` (the surrounding gate).

## Why this exists

"Engineering-firm rigor" (D220) means every claim whose physical
content is modelable actually DISCHARGES through a real model over
real declared inputs, and everything that cannot discharge stays in a
CLOSED, named set of waiver classes rather than an open-ended pile of
"we'll get to it." The rigor census is the fleet-wide accounting that
makes this auditable at a glance: for every shipped project, how many
of its obligations are real, how many are accepted deviations, and
whether any are outright violated.

## What the census reports today

`tools/health/fleet.py`'s `fleet` leg runs `regolith build --release`
+ `regolith ship` for every fleet project and derives one row per
project into `tests/golden/data/fleet_census.json`:

```json
"arm_a6": {
  "obligations": 54,
  "discharged": 10,
  "accepted_deviation": 34,
  "violated": 0,
  "families": ["3d", "bom", "calc", "drawings", "mech"]
}
```

- **`obligations`** -- the total obligation count the build reported.
- **`discharged`** -- results with `deferral == None`: a real model
  resolved the claim over real declared inputs (`_census_from_report`
  in `tools/health/fleet.py`).
- **`accepted_deviation`** -- the count of the WO-98 acceptance
  ledger's `accepted_hashes`: an obligation the design owner has
  formally waived with a memo, verdict math untouched.
- **`violated`** -- results whose deferral reason is literally
  `"violated"`: a real model ran, over real inputs, and the claim
  failed. Fleet-wide this is 0 today (F133) -- see the
  `authoring-for-discharge` guide for what happens when it is not.
- **`families`** -- which shipped backend families (mech, boards,
  bom, drawings, calc, 3d, firmware, hdl) this project's package
  actually produced.

The health `fleet` leg fails if any project's live census diverges
from this committed golden (regeneration is the ordinary golden flow:
diff-review, never blind overwrite).

## What the leg enforces (D220)

1. **No regression on discharge.** An obligation moving from
   `discharged` back into `accepted_deviation` (or a brand-new
   deviation appearing outside the closed waiver classes) is a health
   failure, not a quiet drift -- the golden pins the count.
2. **Zero violated, fleet-wide, is the standing bar.** Any project
   whose census shows `violated > 0` fails the fleet leg; D224.3
   requires the DESIGN to be fixed (see the next guide), never the
   model or the window.
3. **`release_ok=true` and zero stale waivers (E0701)** per project
   -- an obligation whose waiver's provenance has gone stale (the
   design changed underneath it) is a build-cleanliness failure, not
   a census nuance.

## The closed waiver classes (D220.2)

Everything that is not discharged must fall into one of exactly four
named classes -- an obligation waived for any other reason is a rigor
regression:

- **(a) structural conformance edges** -- Class A, the geometry-level
  boundary cases the conformance windows track;
- **(b) D195-gated conformance windows** -- owner-queue territory,
  untouched this cycle;
- **(c) named machinery exclusions** -- carry a design-log F-number
  and a reopen criterion (the F133 residue list -- WO113-F1..F5,
  WO110-F3 -- is this class, enumerated, not hidden);
- **(d) author-intent exclusions** -- e.g. the two tracks' own
  corpus intended-behavior files, deliberately excluded by design.

Today's `fleet_census.json` reports the raw `accepted_deviation`
count without splitting it into these four classes per-row; that
per-class split (discharged / waived-by-class(a..d) / deferred) is
D220.3's census flip, scoped to WO-117 (`Status: open` as of this
guide) -- the LAST WO of the cycle-35 queue. When it lands, this
section gets the per-class table; until then, the F133 design-log
entry is the authoritative enumeration of what the current
`accepted_deviation` pile actually contains.

## Walking one project's residue: arm_a6

F133 records arm_a6 going from 0 discharged bearing/bolt/deflection
claims to 10, through real ISO 281 bearing records, VDI 2230 bolt
sizing, and declared-geometry deflections. Its remaining
`accepted_deviation` rows are enumerated machinery gaps (class (c)),
not silence -- see `docs/guide/27-authoring-for-discharge.md` for the
worked provenance trail on its `j1_bearing`/`j2_bearing`/`j3_bearing`
claims.

## See also

- `docs/guide/27-authoring-for-discharge.md` -- how a claim actually
  moves from deferred/accepted-deviation into `discharged`.
- `docs/guide/24-calc-package.md` -- the per-obligation audit index a
  shipped package carries; the census is the fleet-wide summary of
  exactly the same dispositions the audit index lists per-project.
- `docs/guide/23-health-gate.md` -- the `fleet` leg in its full
  context alongside `check`/`consistency`/`demos`.
