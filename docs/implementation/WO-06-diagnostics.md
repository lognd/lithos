# WO-06: Diagnostics framework

Status: done
Depends: WO-01
Language: Rust (`regolith-diag`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/09 sec. 4; substrate/05 sec. 6

## Goal

Rust-style constructive diagnostics with stable code families, batch
emission, and cross-references -- built before any check exists so no
check ever grows an ad-hoc error path.

## Deliverables

- `Diagnostic` model: code (`E0301`...), family, severity, message,
  source span(s), matched-entity table (origin + measures), 2-3
  `Fix` suggestions (structured, not prose), related-diagnostic refs.
- Code registry: families E01xx parse/types/units, E03xx
  references/ownership/structure, E04xx contracts, E05xx
  instances/symmetry, E06xx rule packs, E07xx evidence. Codes are
  data (one module), never inline literals.
- `DiagnosticSink`: batch collection, dedup, ordering, `--explain`
  cross-reference rendering; text renderer (plain + ANSI).
- typani integration: checks return `Result[T, Diagnostics]`;
  never-first-error-stops is a sink property, not per-check effort.

## Acceptance

- Snapshot tests of rendered output (plain text goldens).
- A demo check emitting 3 cross-referenced diagnostics renders as the
  spec's "edit blast radius at once" shape.
