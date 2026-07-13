# WO-115 -- Feature proof packs: demos v2 (D222)

Status: open
Language: Python (demos/ scripts + harness; no product-code changes
  except real bugs found, which are fixed at root cause).
Spec: D222; WO-108 (the harness, manifest, PROOF.md idiom --
  REUSE, never a second harness); D219 (health demos leg covers
  the union).

## Goal

Every user-facing feature family has a runnable physical proof:
a script that drives the REAL pipeline on a REAL fleet design and
leaves inspectable physical artifacts (files a human opens) plus a
hashed manifest and a PROOF.md explaining what was proven and how
to re-run it.

## Deliverables (one demo each, extending demos/ 7..N; survey
`regolith --help` + charter 38's artifact families and cover them
ALL -- the list below is the known floor)

1. Drawings: projected multi-view SVG/PDF sheets (real HLR views,
   dimensions visible) for a mech part + a civil plan sheet.
2. BOM + cost + schedule: derived BOM with real masses + cost
   columns + member schedule, CSV/PDF forms.
3. Assembly instructions: mate-ordered steps with per-step views.
4. 3D: deterministic GLB + the offline viewer.html (proof opens
   standalone).
5. Boards: real KiCad gerber set from a BoardOutline (kicad-cli
   where resolvable, fake-tier fallback labeled).
6. Firmware + HDL: shipped ELF/netlist evidence (or the named-
   absence surface) for the computer-track projects.
7. Test runner: `regolith test` over a corpus net with the cache
   proving incremental replay.
8. Preview: spec-less `regolith preview` artifact set vs ship
   byte-parity where designed.
9. Calc package + audit index (after WO-114 merges): the calc book
   for one project, with the audit walk demonstrated (every
   obligation row resolves).
10. Doctor/config/toolenv: environment report + config precedence
    demonstration (text artifacts are fine here).
11. run_all.py + make demos + the health demos leg cover the new
    set; each demo's manifest is content-hashed and committed.

## Acceptance

- `make demos` green with every pack live; artifacts regenerate
  byte-identically where the underlying family is deterministic
  (label the honestly-nondeterministic ones with why).
- PROOF.md per demo states: feature proven, pipeline path
  exercised, artifact inventory, re-run command.
- `make check` + health green.

## Escalation

A feature that CANNOT produce a physical artifact end-to-end is a
finding (placeholder number) -- report it, do not paper over it
with a synthetic artifact.
