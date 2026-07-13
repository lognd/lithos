# The progress channel

STATUS: WORKING (WO-119, D228). The producer half is
`python/regolith/progress.py`; every long-running verb
(`build`/`ship`/`test`/`optimize`/`health`'s `fleet` leg) that loops
over named units of work emits typed progress events on it.

Source: design-log `2026-07-13-cycle-35.md` D228 (the shape ruling);
`python/regolith/progress.py` (the module docstring is the STABLE wire
contract -- cite it verbatim, not this guide, for byte-level details).

## The one law: presentation only

D228's ruling is narrow on purpose: progress is derived from the SAME
D217/WO-107 log instrumentation that already exists, never a second
bookkeeping system. Concretely:

- stdout stays data -- progress never appears there;
- logs stay stderr, and progress events are ordinary DEBUG records on
  a dedicated `regolith.progress` logger (a child of root, so they
  flow through the ONE stderr formatter exactly like every other log
  line);
- goldens stay byte-identical -- a progress emit site is a `logging`
  call, never a state mutation a golden could observe;
- non-TTY behavior is unchanged -- nothing here assumes an interactive
  terminal.

## The wire shape (v1)

One line per event, always emitted on one line (wrapped here only for
this guide's width):

```
progress v=1 phase=<phase> subject=<subject>
    done=<done|-> total=<total|-> elapsed=<elapsed>
```

- `v` -- wire format version. Bumped only on an incompatible change to
  this line shape; a consumer may refuse an unknown version.
- `phase` -- a short stable tag (`fleet`, `discharge`, `ship`, ...).
  New phases may be added freely; existing ones are never renamed or
  repurposed without a version bump.
- `subject` -- the unit of work's identifier (a project name, an
  obligation ref, a backend family). Free text, no internal
  whitespace -- `log_progress` collapses any stray space to `_` so it
  can never corrupt the line.
- `done`/`total` -- 1-based counters, or literal `-` for both when the
  phase is indeterminate (unknown total).
- `elapsed` -- seconds since the phase's `start()` call, 3 decimal
  places.

## Two consumption modes over the same wire shape

1. **In-process subscription** (`progress.subscribe`) -- a
   `logging.Handler` filtered to records carrying a `progress_event`
   attribute, for a caller running regolith in the same process (a
   test, a future in-process host). It temporarily raises only the
   dedicated `regolith.progress` logger to DEBUG, never the whole
   toolchain's firehose.
2. **Subprocess stderr parsing** (`progress.parse_line` /
   `progress.parse_stream`) -- the graphite/editor mode: run
   `regolith build --release` (or any long verb) as a subprocess with
   `-v` / `REGOLITH_LOG=DEBUG`, read stderr line by line, and recover
   the identical `ProgressEvent` sequence an in-process subscriber
   would see. ANSI color escapes (WO-107's `--color always` output)
   are stripped before the line regex runs, so parsing is identical
   whether the captured stream came from a colorized or plain run.

Both modes yield the same `ProgressEvent` pydantic model (`v`, `phase`,
`subject`, `done`, `total`, `elapsed`; frozen), with `.indeterminate`
true when `total is None`.

## Consumers

- **graphite** (github.com/lognd/graphite, D233/D234) is the reference
  subprocess consumer: its run console (WO-G5, `Status: open` as of
  this guide) is designed to parse this exact stream for live phase
  progress, with a documented single-adapter upgrade path once the
  producer side is richer than log-derived phase boundaries.
- **The VS Code extension** (WO-120, `Status: open` as of this guide,
  D229) is chartered to bridge this same channel into the editor's
  native `$/progress` protocol for build/ship/optimize/test/health
  tasks -- not yet implemented; see `editors/vscode/README.md` for
  what the extension supports today.
- Any future consumer (CI, a different editor) reads the identical
  wire shape -- the channel is deliberately consumer-agnostic (D228.3).

## See also

- `docs/guide/21-reading-build-output.md` -- the surrounding D217/
  WO-107 log stream this channel piggybacks on.
- `docs/guide/12-graphite.md` -- graphite's own progress consumption,
  once it lands.
