# WO-43: The `regolith build` CLI verb (pipeline UX completion)

Status: done
Depends: nothing open -- `orchestrator.orchestrate.build` /
`staged_build` / `release_gate` (WO-42 deliverable 5) and the
`regolith ship` verb (WO-25) are landed. Unblocks WO-25's first
named blocker (the two-command corpus demo).
Language: Python (`regolith.cli`); no schema changes.
Spec: regolith/09 (build tiers T0..T3, lockfile, deferral),
regolith/13 INV-24 (release-gate totality), design-log
2026-07-08-cycle-26 D136; WO-25's Progress section (the blocker
this closes); AD-10 (stdout is data, logs to stderr).

## Goal

The whole staged pipeline becomes drivable from the shell:
`regolith build [--release] [--tier N] [--out DIR]` runs the staged
build (lower -> realize -> re-lower to fixed point), writes the
lockfile + build report, and -- with `--release` -- runs the INV-24
release gate, so `regolith build --release && regolith ship` is a
real two-command demo over the corpus. No new semantics anywhere:
this verb surfaces the existing Python API exactly.

## Deliverables

1. `regolith build` in `python/regolith/cli/app.py`: project
   discovery (manifest-anchored, the same walk `regolith-ls` uses
   for `magnetite.toml`), tier selection (`--tier`, default per
   regolith/09), `--release` running `release_gate`, `--out DIR`
   for artifacts (default per regolith/09's build-dir convention).
2. Output contract: stdout carries the build report (human table by
   default, `--json` for the machine form -- the `check` verb's
   precedent); ALL logs to stderr; exit code 0 = gate passed /
   build clean, nonzero = gate refused or errors (documented
   per-code in `--help`).
3. `regolith ship` consumes the build's outputs without re-running
   the pipeline when `--build DIR` is given (the WO-25 input triple
   read from disk); `ship` with no flag keeps its current behavior.
4. End-to-end CLI test (subprocess, the system-tester pattern):
   `build --release` over a corpus project that passes, and over a
   deliberately violated fixture that must exit nonzero with the
   refusal on stdout as data.
5. Docs: a short "CLI" subsection in regolith/09 (build verb,
   tiers, exit codes); `docs/guide/00-getting-started.md` gains the
   two-command demo.

## Acceptance criteria

- `regolith build --release && regolith ship --out DIR` works from
  a corpus project directory with no Python-API knowledge.
- Exit codes and stdout/stderr split verified by the subprocess
  tests; no log line ever on stdout.
- `make check` green; WO-25's blocker list updated (its first
  blocker struck through with a pointer here) in the same change.

## Non-goals

- No new build semantics, tiers, or gate rules.
- No watch mode (WO-40 owns `check --watch`; `build --watch` waits
  for real demand).
- kicad-cli absence in the sandbox stays the WO-24/35 cut; the elec
  half of `ship` remains gated by `real_kicad_available()`.

## Progress

Landed: `regolith build [--release] [--tier ...] [--out DIR] [--json]`
in `python/regolith/cli/app.py`, driving
`orchestrator.orchestrate.staged_build` directly; manifest-anchored
project discovery (`python/regolith/cli/discovery.py`, mirroring
`regolith-ls`'s `workspace::discover_root` byte-for-byte); every run
writes `regolith.lock` (`realized_lock_rows`) + `build_report.json`
(the full `StagedBuildReport`) to `--out`; `BuildReport` gained a
`rendered` field (the ONE renderer's text, `BuildOutcome.rendered`
threaded through, Python-only, no schema change) so the CLI's human
default never needs a second renderer. `regolith ship` gained
`--build DIR` (deliverable 3): `backends.ship.ship()` gained an
optional `prebuilt: StagedBuildReport` parameter that, when supplied,
skips `staged_build` entirely; `ship` with no `--build` is
byte-for-byte its pre-WO-43 behavior. `docs/spec/regolith/09-build-
and-lockfile.md` sec. 8 and `docs/guide/00-getting-started.md` sec.
4a document the verb. Tests: `tests/test_cli_build.py` (subprocess,
the `test_smoke.py` pattern) -- a clean project reaching a T3 release
exits 0 and writes both artifacts, a statically-violated fixture exits
nonzero with the diagnostic on stdout (never only in a log line), the
`build --release --out DIR && ship --build DIR --out DIR2` two-command
chain runs end to end, and a standing assertion that no `lower.`-style
tracing text ever reaches stdout.

Interpretation notes (spec silent on the exact shape, decided here,
not escalated -- each is a direct, minimal reading of the deliverable
text, not new semantics): (1) "regolith/09's build-dir convention" for
`--out`'s default is read as the existing `.regolith/` project-local
house convention (evidence cache/payload store/native-artifact store
all already root there) -- `<project_root>/.regolith/build`; (2)
`--tier` takes the same verb spellings `TIER_BY_VERB` already defines
(`check|build|optimize|release`); `--release` is `--tier release` and
wins on conflict; (3) the acceptance criterion's literal `regolith
build --release && regolith ship --out DIR` reads as shorthand for the
concrete two-command form deliverable 3 itself names (`ship --build
DIR`) -- proven directly by
`test_build_release_then_ship_build_is_the_two_command_demo`.

WO-25's blocker 1 (no `build` CLI verb existed) is CLOSED by this
change; WO-25's own Progress section should strike it on its next
dispatch (edited in the same change here to avoid the two files
disagreeing).

`make check`: green (see dispatch report).
