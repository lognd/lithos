# WO-46: calcite spec elaboration (charter -> track docs + corpus)

Status: in-progress -- OUTPUT COMPLETE (cycle 27, D139,
coordinator-executed under owner directive): calcite 02/03/04 +
charter/README updates + the five-design corpus all exist. Flips to
done on owner ratification (the D93 pattern), per this WO's own
acceptance criteria.
Depends: nothing in-tree (docs + examples only; NO toolchain code,
NO extension-registry change -- that is WO-47). The charter decides
everything discretionary; this WO's authority is elaboration, not
design: any genuine gap is ESCALATED to a design-log entry per the
dispatch protocol, never resolved locally.
Language: docs + `.calx` example sources (not yet parseable -- like
every track's corpus predated its parser; they are the spec's
pressure tests first).
Spec: docs/spec/calcite/01-charter.md (NORMATIVE, SETTLED), design-log
2026-07-08-cycle-26 D133; the fluorite track docs
(docs/spec/fluorite/01..04) as the STRUCTURAL PATTERN to follow; the
regolith docs 01-13 (every construct must bind to existing
machinery -- the F90 discipline: prefer existing mechanism over new
surface, escalate if impossible); hematite/04 sec. 1 (one word one
idea; the homonym policy for any vocabulary the tracks share).

## Goal

`docs/spec/calcite/` grows from charter to ratifiable track spec:
02-language (spaces/members/assemblies, site/environment, claims),
03-lowering (L0-L6 per charter sec. 5, the load-path net binding,
the frame IR shape), 04-open-questions (deferrals with reopen
criteria ONLY -- the charter opens no COPENs and this WO may not
either without a design-log escalation), plus the five-example
corpus (charter sec. 8) written in the target surface.

## Deliverables

1. `docs/spec/calcite/02-language.md`: the construct set per charter
   sec. 2a-2c -- `space`, `member`, layered `assembly`, site
   declarations, adjacency/access contracts, circulation graphs,
   load-path net declarations -- each with grammar-in-prose +
   examples, every construct mapped to its regolith mechanism
   (contracts/04, nets AD-23, budgets D49, records/11). Vocabulary
   table in the hematite/04 style; zero collisions with the
   justified-overload registry unless argued there in the same
   change.
2. `docs/spec/calcite/03-lowering.md`: per-level table (charter sec. 5),
   the egress/occupancy L2 check definitions (precise enough to
   implement: inputs, diagnostic conditions, error family), the
   load-path conservation binding to the INV-15 ledger, the frame
   IR field list (AD-25 growth rule -- schema lands in WO-48, the
   FIELD LIST is decided here), claim-family -> obligation shapes.
3. `docs/spec/calcite/04-open-questions.md`: deferred items from charter
   sec. 7 restated with their reopen criteria; nothing OPEN.
4. Corpus (`examples/tracks/calcite/` + `examples/systems/
   small_office/`): the five charter sec. 8 designs, self-contained,
   record references pointing at `std.civil` names (phantom until
   WO-48 -- mark each with the corpus's established
   pending-convention comment).
5. `docs/spec/calcite/01-charter.md` gains a header note that 02/03/04
   now elaborate it; `docs/spec/calcite/README.md` and `docs/README.md`
   reading-order updated; `docs/guide/README.md` notes the future
   calcite guide (do not write the guide -- post-ratification, the
   fluorite-guide precedent).

## Acceptance criteria

- A reader of regolith/ + calcite/02-03 can hand-derive what WO-47's
  parser and WO-48's lowering must do without asking a question
  (the D107 zero-shot bar the fluorite docs met).
- Every construct cites its regolith mechanism; NO new machinery is
  introduced anywhere (F90 discipline) -- anything that seems to
  need it is escalated instead.
- All five corpus designs express every charter claim family at
  least once; ASCII only; the track versions on 02/03 headers start
  at 0.1.
- The design log gains a ratification entry (the D93 pattern) when
  the owner accepts this WO's output; the WO Status flips only then.

## Non-goals

- Toolchain code, extension registry, schemas (WO-47/48).
- The calcite teaching guide (post-ratification).
- `std.civil` content (WO-48); the corpus may NAME its packs.
