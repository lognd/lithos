# WO-41: Docs generation + project scaffolding

Status: done
Depends: WO-05 (typed CST -- doc extraction walks it), WO-16
(magnetite manifest/templates), WO-18 (facade). Independent of
everything else; touches only new CLI modules + a small CST walk.
Language: Python (`regolith doc`, `magnetite new`); Rust only if doc
extraction needs a facade accessor that does not exist (prefer the
existing debug/AST surface; escalate a design-log note before adding
API).
Spec: `../../spec/toolchain/24-developer-tooling.md` sec. 6 (NORMATIVE); design-log
`2026-07-07-cycle-22.md` D115/D116; regolith/11 (packages -- the
unit docs render per).

## Goal

`regolith doc` renders a package's public surface to deterministic
markdown -- interfaces, parts/blocks/flownets, claims with build
status when artifacts exist -- using the existing `#` comment
convention as doc text; `magnetite new` scaffolds a working project
from templates that pass `regolith check` by construction. The last
two "every language has this" gaps close.

## Deliverables

1. **Doc extraction**: leading `#` comment block attached to a
   declaration (no blank line between) is its doc text (D115: no
   new syntax); extraction from the lossless CST preserves the
   block verbatim minus comment markers. Undocumented public decls
   are counted (ties into WO-40's inventory advisory family later;
   no new lint here).
2. **`regolith doc [--out DIR]`**: one markdown file per source
   package: interfaces (roles, params, flow decls), public decls by
   kind (parts, blocks, flownets, media, budgets), claims with
   obligation status + margin + evidence tier when `.regolith/`
   artifacts are present (else "(unbuilt)"), registry records with
   pinned provenance. Deterministic ordering; internal links;
   snapshot-tested against a corpus package (updatable only via
   `make snapshots`).
3. **`magnetite new <name> --template mech|elec|fluid|system`**:
   emits `magnetite.toml`, one source file per track in the template
   with an honest example claim, house `.gitignore`, and a CI
   snippet. Templates live as data under `python/regolith/magnetite/
   templates/` (package data, wheel-included); a generation test
   runs `regolith check` on every template output (pass = green,
   asserted).
4. **Docs**: CLI reference entries; charter sec. 6 marked
   implemented; a guide pointer ("starting a project"); TODO
   ledger flip.

## Acceptance criteria

- `regolith doc` over `examples/systems/cubesat/` renders every public
  interface/part/claim; running twice is byte-identical; with a
  built workspace the claim rows show status/margin, after deleting
  `.regolith/` they show "(unbuilt)" (no error).
- Doc text round-trips verbatim from the comment block (ASCII
  fixtures + one non-ASCII user-content fixture -- extraction must
  not corrupt it even though repo files are ASCII).
- Every template generates, checks green, and contains zero
  hard-coded extension strings (read from the registry -- the
  tripwire).
- `magnetite new` refuses to overwrite an existing non-empty directory
  with a constructive error.
- `make check` green; snapshots via `make snapshots` only.

## Non-goals

- HTML/site rendering (charter sec. 7: reopen with a registry UI
  work); doc COVERAGE enforcement (a future lint, not this WO);
  cross-package link resolution through the registry (needs
  the registry; markdown links stay package-local); template
  marketplace/user templates (reopen on demand).

## Addendum: cycle-33 docsgen-formatting SIMPLE (D199.2)

Owner reported `regolith doc` output formatting was subpar.
Assess-then-fix pass over `python/regolith/docgen/render.py`, run
against `stdlib/std.civil`, `examples/registry/rp2040.cupr`, and
`examples/flagships/printer_k1`. Inventory, ranked by reader impact:

1. FIXED -- heading hierarchy jump: source headings render `##`, but
   every declaration rendered `####`, skipping `###` entirely (an
   invalid heading-hierarchy jump in every single doc page). Decls
   now render at `###`.
2. FIXED -- empty declaration/budget names rendered as a bare ` `` `
   (empty code span) -- visible in every unnamed `require` block and
   every budget row (budgets carry no `name` field in the grammar, so
   this hit `printer_k1.cupr`'s entire Budgets section). Now renders
   a readable fallback (`(unnamed)`, `(unnamed budget)`, etc.)
   instead of empty backticks.
3. FIXED -- embedded backticks corrupt the code span: a field value
   containing a literal backtick (e.g. `std.civil`'s `BasePlate`
   mating, whose `capability` note quotes `` `anchors=` ``)
   prematurely closed a single-backtick span and broke every
   character after it. The renderer now widens the backtick fence
   past the longest run already in the value (CommonMark's own
   escaping convention).
4. FIXED -- multi-line field/claim values (e.g. a `spec:` predicate
   block on `printer_k1`'s `ControllerMcu`, or `rp2040`'s `packages:`
   block) were spliced into the list item as raw, unfenced newlines
   -- reads as a wall of misindented text and breaks GFM list
   continuation. Now rendered as an indented fenced code block.
5. DEFERRED, out of scope -- claim expression VALUES that span
   multiple source lines are truncated at extraction time (Rust side,
   `regolith_api::docextract`'s `field_json`/`Field::value().text()`
   path), before the Python renderer ever sees them: e.g.
   `antenna.hema`'s `settle` claim extracts as
   `"settles(root.theta, to=90deg +- 2deg"` (missing the rest of the
   expression and its closing paren), and `rp2040.cupr`'s `class`
   field extracts as `"mcu(cortex_m0plus"`. This is a data-loss bug
   in extraction, not a Python formatting defect, and this dispatch
   was scoped Python-only; escalate as a follow-up WO/design-log item
   before touching `regolith-api`.

Snapshot: `tests/golden/data/doc_cubesat.md` regenerated via
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_doc_snapshot.py`.
Unit coverage for the four fixed defects (plus determinism) lives in
`tests/test_docgen_render.py`.
