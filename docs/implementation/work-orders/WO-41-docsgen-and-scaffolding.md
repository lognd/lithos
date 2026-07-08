# WO-41: Docs generation + project scaffolding

Status: done
Depends: WO-05 (typed CST -- doc extraction walks it), WO-16
(magnetite manifest/templates), WO-18 (facade). Independent of
everything else; touches only new CLI modules + a small CST walk.
Language: Python (`regolith doc`, `magnetite new`); Rust only if doc
extraction needs a facade accessor that does not exist (prefer the
existing debug/AST surface; escalate a design-log note before adding
API).
Spec: `../design/24-developer-tooling.md` sec. 6 (NORMATIVE); design-log
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
