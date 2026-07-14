# Charter 42 -- The engineer-injection channel and the universal artifact surface (AD-40, AD-41)

Decided cycle 36 (D243/D244/D245, owner directive 2026-07-15 with
delegated design authority; recon F145). Machinery: WO-129
(injection channel), WO-130 (universal artifact surface + edit
models); the graphite consumers are that repo's WO-G9/G10. This
charter wins over the WO bodies it governs.

The owner's bar: graphite must be able to render ANY output the
toolchain emits, let a person move things around, and let a
high-skill engineer inject decisions at the intermediate steps --
including overriding what the optimizer chose, which is permitted
but never silent. The ALLOWANCES land in lithos first: graphite
consumes only public surfaces (D234), so it can only render what
lithos describes and only edit what lithos accepts back.

This charter is the machine half of the project's north star
(docs/README): "write a declarative file, inject a high-skill
engineer at the intermediate steps only if necessary, and get
something out the end that just works."

## 1. Injections are DECLARED DATA, never evidence (D243.1)

The one load-bearing rule, from which everything else follows:

> An injection changes an INPUT or a CHOICE. It never changes a
> verdict, an evidence value, or a margin. The pipeline re-derives
> every obligation from the injected inputs exactly as it would
> from hand-authored ones.

So an override cannot launder a failing claim into a passing one:
if the injected value makes a claim VIOLATED, the build says
VIOLATED and the release gate refuses (D206/D220.1 untouched, INV-24
unchanged). This is what makes the channel safe enough to expose to
a GUI at all.

## 1a. What is injectable, and what is source-only (D246 -- the claims/evidence boundary)

The claim/evidence vocabulary (regolith/07; the mantra table) is
NOT an injection surface. Every one of its forms is either claim
SEMANTICS (what is being promised) or EVIDENCE PROVENANCE (how a
promise is proved) -- and both are authored in source, reviewed by
diff, and versioned with the design. A GUI that can retune them is a
GUI that can quietly weaken a design.

INJECTABLE (design inputs and choices -- the "intermediate steps" an
engineer legitimately decides):

- dimensions and bounded/minimize slots (`in [a, b] minimize`),
- component/record selects and `by select` choice points,
- section-search family selections,
- placements and poses (sec. 4),
- `@hint(...)` guidance -- and note WHY this one is safe: the
  language already defines a hint as droppable and NEVER
  load-bearing, so a hint injection cannot change a verdict by
  construction. It is the language's own channel for exactly this.

SOURCE-ONLY (an override naming one of these is REFUSED with a
constructive diagnostic telling the author to edit the source):

- claim structure and semantics: `require <Group>`, `forall <cfg>
  [in <domain>]`, `all`, `during` / `within .. after` / `until`,
  `event` / `mask`, `peak`, `settles`, `overshoot`, `rms(band=)`,
  `stays_within(mask)`, `equilibrium(...): stable`,
  `manufacturable(stage)` / `mfg.*`;
- the evidence ladder: `trust: >= <tier>`, `by analysis /
  catalog(ref) / test(ref)`, `model=<impl>`, `assume!(expr,
  basis=)`, `todo!`, `waive ... basis:`;
- the safety multipliers `sf=` / `scatter_factor=`.

The two hardest cases make the rule obvious. `model=<impl>` exists
precisely because pinning the discharge model CANNOT forge a pass --
so the channel does not get to touch it at all; the property is
preserved by unreachability, not by good behavior. And `sf=` /
`scatter_factor=` are safety multipliers: an injected LOWER factor
would weaken a claim without weakening any verdict machinery, which
is laundering by another name. Deviations from a claim as written
have exactly ONE sanctioned path, and it is evidence-carrying and
audited: the waiver machinery (WO-98's acceptance ledger, D207
memos), never the injection channel.

This boundary is what lets INV-33 (sec. 8) be proved by
construction rather than by review: overrides cannot name an
evidence-ladder or claim-semantics target, so no override can reach
a trust floor, a model pin, a safety factor, a waiver, or a verdict.

## 2. The override ledger (D243.2)

Overrides live in ONE diffable, ASCII, source-controlled home per
project: `overrides.toml` at the project root (magnetite-adjacent,
never inside `dist/`, never inside `.regolith/`). One entry per
injection:

```toml
[[override]]
target = "printer_k1.Carriage.rail_span"   # dotted path: design.subject.slot
value  = "240mm"                            # a quantity, a record ref, or a select choice
mode   = "pin"                              # "pin" (default) | "seed"
author = "logan"                            # required
reason = "matches the extrusion we already stock"   # required, non-empty
```

Rules:

- `author` and `reason` are REQUIRED. An override with either
  missing is a diagnostic (never a silent default) -- an
  unexplained override is the exact thing an audit trail exists to
  prevent (D221 spirit).
- The target path resolves against the SAME surfaces the census and
  the optimizer read (choice points, sketch dimensions, bounded
  slots, placements, section selects). An unresolvable target is a
  constructive diagnostic naming the nearest valid paths -- never a
  silent no-op.
- The ledger's content hash enters the build's inputs, so a package
  built with overrides is reproducible and a package built without
  them is byte-different (AD-6/INV-10 holds).

## 3. Overriding the optimizer (D243.3 -- the "optimization removal" allowance)
> **PARKED by D253 (2026-07-15).** This section is preserved thinking,
> NOT shipped behavior. The machinery it describes is removed from
> master and kept in full on the branch `experimental/injection-channel`.
> The owner's rethink is coming (the aesthetic/semantic split: a GUI may
> rearrange a picture, never move an engineering quantity). Do not cite
> this section as implemented.

An override on a slot the optimizer would search is PERMITTED and
EXPLICIT:

- `mode = "pin"` (default) REMOVES that variable from the search.
  The optimizer treats it as fixed. This is optimization removal;
  it is allowed, it is recorded, and it is never inferred.
- `mode = "seed"` keeps the variable in the search and uses the
  value as the starting point (the optimizer may move it).

The value source's `cause` becomes
`engineer_override(author, reason)`, which OUTRANKS
`optimize(...)`'s pin in the provenance ladder (INV-30's attribution
still holds -- the trace records that the search was superseded, not
that it ran). Every pinned-away variable appears:

1. in the parity report (`ship --explain`) as an
   `optimization_removed` row with author + reason,
2. in the acceptance ledger shipped in the package,
3. in the calc book's audit index, on every obligation whose inputs
   the override touched.

A build whose optimizer was overridden is still release-clean if and
only if its obligations discharge. Nothing about the gate softens.

## 4. Moving things around (D243.4)
> **PARKED by D253 (2026-07-15).** This section is preserved thinking,
> NOT shipped behavior. The machinery it describes is removed from
> master and kept in full on the branch `experimental/injection-channel`.
> The owner's rethink is coming (the aesthetic/semantic split: a GUI may
> rearrange a picture, never move an engineering quantity). Do not cite
> this section as implemented.

"Move this part / this annotation / this placement" is an override
like any other -- a POSE injection against the editable model
(sec. 6), written to the same ledger:

```toml
[[override]]
target = "mainboard_mx.board.placements.J_DBG1.pose"
value  = { x = "12.0mm", y = "8.5mm", rot = "90deg" }
author = "logan"
reason = "clear of the heatsink keepout"
```

Artifacts stay DERIVED: nothing is edited in place inside `dist/`.
A GUI edit writes the ledger entry and re-runs the pipeline; the
new artifact is emitted from the new input. That is what keeps the
content addresses meaningful and the audit trail intact.

## 5. Injection is a public CLI surface (D243.5)
> **PARKED by D253 (2026-07-15).** This section is preserved thinking,
> NOT shipped behavior. The machinery it describes is removed from
> master and kept in full on the branch `experimental/injection-channel`.
> The owner's rethink is coming (the aesthetic/semantic split: a GUI may
> rearrange a picture, never move an engineering quantity). Do not cite
> this section as implemented.

Because graphite (and any editor, and any script) may only touch
public surfaces:

```
regolith override list [--json]
regolith override set <target> <value> --author <who> --reason <why> [--mode pin|seed]
regolith override clear <target>
regolith override explain <target>      # what it supersedes, and what it costs
```

The CLI is the ONE writer of `overrides.toml` (so the format has one
home). `--json` everywhere, stdout is data, logs to stderr.

## 6. The universal artifact surface (D244; AD-41)

A viewer must never carry a hardcoded list of families -- that is
exactly how graphite fell behind this cycle (F145: two new families
and twelve new board layers landed with no consumer). So `ship`,
`preview`, and `build` emit ONE typed artifact index describing
EVERY file, and a new family is viewable the day it ships:

Per artifact: `family`, `kind`, `relpath`, `content_hash`, `bytes`,
`media_type`, a `viewer` hint from a CLOSED vocabulary (`svg` |
`raster` | `gerber` | `glb` | `table` | `markdown` | `json` |
`text` | `binary`), the `source_refs` (subject/claim/obligation ids
that produced it), and an optional `edit_model` ref (sec. 7).

Rules:

- The `viewer` vocabulary is closed and lives in ONE registry module
  (the AD-36 emission registry -- the same place the family is
  registered). A producer that registers a family declares its
  viewer hint there; forgetting to is a registration error, not a
  silent gap.
- EVERY file gets a hint. The honest fallback ladder is
  `table`/`json`/`text`/`binary` -- a viewer always has something
  truthful to show (a hash + size + reason beats a blank pane).
- `regolith artifacts <project> [--json]` publishes the index
  without re-running a build (it reads the shipped package).

## 7. Edit models (D244.2)
> **PARKED by D253 (2026-07-15).** This section is preserved thinking,
> NOT shipped behavior. The machinery it describes is removed from
> master and kept in full on the branch `experimental/injection-channel`.
> The owner's rethink is coming (the aesthetic/semantic split: a GUI may
> rearrange a picture, never move an engineering quantity). Do not cite
> this section as implemented.

Families whose content a person can legitimately move expose an
EDIT MODEL beside the rendered artifact: a canonical, hashed JSON
description of the movable entities and their current poses, plus,
for each, the override target path (sec. 4) that would change it.

Landed families and their movables:

- boards: component/test-point/tap-header placements (x, y, rot,
  side), keepouts as read-only context.
- drawing sheets: annotation and view anchors.
- assemblies: part poses the mate solve did not fix (a solved DOF is
  read-only -- moving it is a design change, not a nudge, and the
  editor says so).

An edit model NEVER contains a value the pipeline did not produce,
and an editor may only write back through sec. 5's CLI. Read-only
entities are marked read-only WITH their reason (e.g. "fixed by the
mate solve", "pinned by claim X").

## 8. Invariant (INV-33 -- WITHDRAWN, number RESERVED by D253.4)

> **PARKED by D253 (2026-07-15).** INV-33 is withdrawn from the invariant
> ledger and its number reserved (never reused). F150: the channel was
> inert, so this invariant's proof covered a pure function, not the
> pipeline -- and an invariant whose enforcement is parked must not sit in
> the ledger looking enforced. Preserved on `experimental/injection-channel`.

> No override can make the release gate pass a design whose
> obligations do not discharge under that override's own values.

Proof obligation: the override enters as a value source BEFORE
lowering; obligations are re-derived from the overridden inputs; the
gate reads only the resulting verdicts. There is no path from an
override to an evidence value, a margin, or an acceptance row. The
enforcing test set: an override that satisfies a claim discharges it
honestly; an override that violates a claim VIOLATES it and the gate
refuses; an override on a waived claim does not un-waive or
re-waive it.

## 9. Non-goals (named, with reopen criteria)

- Direct artifact editing (paint on the gerber, drag the STEP).
  Artifacts are derived; edit the model, not the output. Reopen: a
  real workflow that cannot be expressed as an override target.
- Overriding evidence, margins, verdicts, or waivers (that is
  laundering; the waiver machinery -- WO-98's acceptance ledger,
  D207 memos -- is the ONE sanctioned deviation path, and it is
  evidence-carrying).
- Multi-user concurrent editing/locking. One ledger, git is the
  merge tool. Reopen: a real team hits a real conflict.

## 10. The aesthetic layer (D254 -- graphite's ONE write surface)

Added cycle 36 (D254, after the owner parked the injection channel:
"make all configuration through graphite AESTHETIC ONLY"). Sections
3, 4, 5, and 7 above are PARKED; this section is what replaces them.

### 10.1 The test that decides every case

> Would a competent engineer need to RE-CHECK anything because of
> this edit?

If yes, it is SEMANTIC and a GUI may not write it. If no, it is
AESTHETIC and a GUI may.

Moving a component placement moves DRC clearances, thermal coupling,
and EMC behavior -- an engineer must re-check. Moving a BDF block on
a diagram moves ink. That is the whole distinction, and it is stable
under new artifact families because it asks about consequences, not
about file types.

### 10.2 What is aesthetic (the closed list)

- diagram layout: block/node positions and edge routing hints in the
  contract-graph, BDF-shaped pass diagrams, harness/elec block
  diagrams, P&IDs, one-lines;
- sheet composition: annotation and view ANCHORS on a drawing sheet
  (which corner a note sits in -- NOT what the note says);
- style: the style pack / theme selection (charter 41 sec. 5 already
  makes style hash-pinned record data);
- view state: zoom, pan, layer visibility, collapsed sections.

Anything not on this list is semantic until a charter amendment says
otherwise. The list is closed BY DESIGN: an open-ended "aesthetic"
category is how a GUI eventually writes a dimension.

### 10.3 Where it lives, and why the design hash cannot move

Aesthetic config is a hash-pinned RECORD, exactly like a style pack
(charter 41 sec. 5 is the precedent, and reusing it is the point):

- one `view.toml` per project (or a `std.view` pack ref), ASCII,
  diffable, source-controlled;
- its content hash is recorded in the manifest of any artifact whose
  RENDERING it influenced;
- it is an input to RENDERERS only. It never reaches the compiler,
  the payload, an obligation, an evidence value, a verdict, or the
  DESIGN hash.

Consequences, and they are the safety argument in full:

1. The design hash is INVARIANT under aesthetic config, by
   construction -- there is no code path from `view.toml` to the
   payload. Two packages whose designs are identical but whose
   diagrams are arranged differently carry the SAME design hash and
   DIFFERENT artifact hashes, and the manifest says exactly which
   view pin produced which picture.
2. Verdicts are untouchable, not by discipline but by unreachability
   (the same argument D246 makes for the claims/evidence boundary,
   and the reason both rules are safe to hand to a GUI).
3. Determinism holds per view pin (AD-6/INV-10): same design + same
   view pin -> byte-identical artifacts.

### 10.4 How a GUI writes it

Through ONE public verb -- graphite never writes the file directly:

```
regolith view set <target> <value> [--json]
regolith view list|reset [--json]
```

A target names an aesthetic entity from the artifact index's edit
model (the READ-ONLY descriptive half of sec. 7 survives for exactly
this: it describes what exists; it no longer offers semantic
write-back). A target that resolves to a SEMANTIC entity is REFUSED
with a coded diagnostic naming the source file to edit instead --
the same refusal shape D246 gives the evidence ladder, for the same
reason.

### 10.5 What this deliberately does NOT enable

An engineer who wants to pin a dimension, choose a component, or
supersede the optimizer edits the SOURCE and gets a diff, a review,
and git history. That is not friction to be smoothed away; it is the
audit trail. The parked injection channel (`experimental/
injection-channel`) exists if that judgment is ever revisited, and
its INV-33 machinery is preserved there -- but the default is, and
should be, that design changes look like design changes.
