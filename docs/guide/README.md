# The lithos guide

Learning-path documentation for the two design languages and their
toolchain. Read in order:

| doc | what you learn |
|---|---|
| `00-getting-started.md` | install, write a first part, run `regolith check`, read a diagnostic |
| `01-hematite-guide.md` | the mechanical language, by example, with the full vocabulary |
| `02-cuprite-guide.md` | the electrical/computer language, same treatment |
| `10-writing-dfm-rules.md` | authoring DFM/DRC/ERC rule packs (for manufacturing experts too) |

Numbering convention: 00 is getting started, 01-09 are per-track
guides in track order (hematite, cuprite, fluorite pending as 03,
calcite pending as 04 -- post-ratification, the fluorite-guide
precedent), 10+ are authoring guides.

Two ground rules for reading:

1. **These guides teach; the spec decides.** Every list here is a
   learning view of a normative document, and each section names its
   source (`docs/spec/hematite/`, `docs/spec/cuprite/`, `docs/spec/regolith/`). If a
   guide and the spec ever disagree, the spec wins and the guide has
   a bug -- please fix the guide.
2. **Status honesty.** The toolchain is under construction. What each
   guide shows is marked:
   - WORKING -- runs today (`regolith check`, `fmt`, `debug`, the
     static checks, obligation lowering, the closed-form harness).
   - DESIGNED -- specced and work-ordered, not yet runnable
     (geometry/layout realizers, `regolith build --release`/`ship`,
     the rule-pack engine; see `docs/workflow/work-orders/` WO-20..28).

The corpus in `examples/` is the best companion to these guides:
sixteen single-file designs plus the ten-file Kestrel cubesat
(`examples/systems/cubesat/`), all in real syntax, all compiled by CI.
