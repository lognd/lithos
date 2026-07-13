# WO-107 -- Readable, colorized log output (D217)

Status: open
Language: Python (logging_setup + CLI edge; regolith-py bridge
  field read-side only if needed)
Spec: D217 (owner directive + shape ruling); D191.2 (the ONE color
  policy: --color auto|always|never + NO_COLOR + TTY, already at
  the CLI edge for diagnostics -- REUSE, never a second policy);
  AD-7 (one diagnostic renderer -- untouched); house logging rules
  (stdout is data, logs to stderr, LOG EVERYTHING -- demote and
  aggregate, never delete).

## Goal

`regolith build` (and every verb) emits a log stream a human can
read at a glance on a color terminal: leveled colors, span-aware
structure, deduplicated repeats, abbreviated hashes, single-line
records -- with `-v` restoring today's full verbatim firehose and
non-TTY/NO_COLOR output staying plain and stable.

## The named sins (from the owner's espresso transcript)

1. Bare span-enter records (`lower.lints;` twice per phase) drown
   the signal.
2. The same deferral record prints 2-4x per obligation, and the
   whole lower pipeline logs twice across staged iterations.
3. Full-width content hashes dominate every obligation line.
4. Multi-line bounds (embedded source comments, `\n`s) dump raw
   into single log records.
5. No visual hierarchy: phase boundaries, warnings, and the final
   verdict all render at the same weight; `build: clean` is
   invisible.

## Deliverables

1. One shared color-policy helper (factored from the D191.2 CLI
   edge; diagnostics and logs consume the SAME decision). ANSI
   only when the policy says color.
2. A single stderr log formatter (Python logging_setup, applied to
   both Python module loggers and the pyo3-log bridge records):
   - severity-colored level tags (DEBUG dim, INFO default, WARNING
     yellow, ERROR red); subsystem/span prefix in cyan; key=value
     keys dimmed.
   - hashes abbreviated to 12 chars at INFO (full at `-v`).
   - embedded newlines escaped; records over a named width
     truncated with `...` at INFO (full at `-v`).
3. Noise reduction (demote + aggregate, NEVER delete -- house
   rule):
   - span-enter/exit records -> DEBUG.
   - per-obligation deferral/no-model detail -> DEBUG; one INFO
     aggregate per discharge pass: counts by reason bucket
     (`deferred 122: conformance_windows 74, no_model 24, ...`).
   - consecutive exact-duplicate records collapse to one line with
     an `(xN)` suffix.
   - staged-build iterations > 1: the re-lower detail rides DEBUG;
     the iteration header line stays INFO.
4. The final verdict line renders loud: green when
   ok/release_ok/clean, red counts otherwise (same accounting, no
   new math).
5. `-v/--verbose` (DEBUG + full hashes + no truncation + no dedup)
   and `-q/--quiet` (WARNING+) on the CLI; wired through the
   regolith config doctrine (D163) like --color.
6. Tests: formatter units (color on/off, dedup counts, truncation,
   hash abbreviation, newline escaping); CLI e2e -- stderr carries
   ANSI when forced and none under NO_COLOR/non-TTY; stdout
   byte-identical either way; goldens untouched; `-v` restores
   every record (count parity against a captured baseline).
7. Docs: guide section (reading build output) + logging refs note.

## Acceptance criteria

- The espresso build transcript at default verbosity fits the
  sins above: no span noise, no duplicate deferral lines, one
  aggregate per pass, short hashes, colored phases/verdict.
- `NO_COLOR=1` or non-TTY: zero ANSI bytes on stderr; stdout
  byte-identical in all modes; `make check` green with goldens
  unchanged.
- No log record is unreachable: everything visible today is
  visible under `-v`.
