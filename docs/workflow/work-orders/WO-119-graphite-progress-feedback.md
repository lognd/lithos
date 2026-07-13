# WO-119 -- Progress event channel, producer half (D228; reframed by D234)

Status: done
Language: Python (regolith progress adapter + emit sites); Rust
  tracing-bridge read-side only if needed (WO-107 precedent).
Spec: D228 (the three rulings); D234.3 (this WO is the PRODUCER
  half only -- the graphite TUI/GUI consumers moved to graphite's
  own WO-G5/WO-G7; VS Code consumption is WO-120); D217/WO-107
  (the log formatter this piggybacks); house rules (stdout data,
  logs stderr, LOG EVERYTHING).

## Goal

regolith's long operations emit a typed, consumer-agnostic
progress event stream derived from the SAME instrumentation the
logging system already carries -- one channel that graphite, the
VS Code extension, and CI all parse identically.

## Deliverables

1. Typed progress event (phase, subject, done/total or
   indeterminate, elapsed) derived from the D217 span/phase log
   records via ONE adapter module (`python/regolith/progress.py`
   or similar single home); Rust tracing records included via the
   existing pyo3-log bridge.
2. New emit sites ONLY where a long loop is currently silent
   (per-project fleet iteration, per-obligation discharge loop,
   per-artifact emission) -- landed as ordinary DEBUG log records
   (LOG EVERYTHING: additions, never a parallel bookkeeping
   system), shaped so the adapter parses them.
3. Consumption modes, both tested: in-process subscription and
   subprocess stderr-stream parsing (the graphite/editor mode);
   the event wire shape documented in one place with a stability
   note (graphite WO-G5 and lithos WO-120 cite it).
4. Determinism/behavior proof: goldens byte-identical, stdout
   untouched, non-TTY/NO_COLOR unchanged; adapter tests over real
   captured streams from a fleet build.

## Acceptance

- A `regolith build --release` on a fleet project yields a parsed
  phase-progress sequence in both consumption modes (tests).
- Zero behavior change for non-subscribers; `make check` green.

## Escalation

If the tracing bridge drops span metadata the adapter needs,
escalate the bridge-field read-side increment rather than
double-instrumenting in Python.

## Close-out ledger

### Adapter (`python/regolith/progress.py`)

One module, ONE home for the wire shape (module docstring, stability
note, `PROGRESS_WIRE_VERSION = 1`):

- `ProgressEvent` (pydantic, frozen): `v`, `phase`, `subject`,
  `done`/`total` (both `None` marks indeterminate), `elapsed`.
- `log_progress(phase, subject, done, total, started)` /
  `start()` -- the ONE emit helper every call site shares (no
  duplication); an ordinary `logging.debug` on a dedicated
  `regolith.progress` child logger (propagates normally through the
  ONE D217/WO-107 stderr formatter/handler).
- `parse_line`/`parse_stream` -- subprocess-mode parsing (ANSI-strip
  first, then a regex over the wire line); ignores every non-progress
  log line.
- `subscribe(callback)` -- in-process mode: a `logging.Handler`
  filtered on a `progress_event` record attribute, scoped to raising
  ONLY the dedicated progress logger's level (never root/other module
  loggers) for the context's lifetime.

Wire shape (v1, cite verbatim):
`progress v=1 phase=<phase> subject=<subject> done=<done|-> total=<total|-> elapsed=<elapsed>`.

### Emit sites (the three named silent loops)

- `tools/health/fleet.py::run` -- one DEBUG record per fleet project
  (`phase=fleet`, done/total over the whole fleet), before each
  project's existing build+ship+census work.
- `python/regolith/orchestrator/discharge.py::discharge_all` -- the
  obligation loop was a bare generator expression with zero
  per-iteration observability; converted to an explicit loop (same
  total behavior/order/return type) with one DEBUG record per
  obligation (`phase=discharge`, subject = the obligation's
  `subject_ref` or its content hash when the ref is empty).
- `python/regolith/backends/ship.py::ship` -- one DEBUG record per
  artifact FILE (`phase=ship`, subject = the file's namespaced
  relpath, done/total scoped to its own backend family since the
  total file count is only known per-backend as `produce()` runs one
  family at a time).

No existing log record was touched, demoted, or deleted; every site
above previously emitted nothing between its bracketing log lines.

### Tests (`tests/test_progress.py`)

- Unit: emit -> parse round trip, whitespace-in-subject collapse,
  indeterminate events, ANSI-color stripping (color-mode formatted
  record still parses), ordinary log noise correctly ignored.
- In-process subscription: `subscribe()` receives events emitted
  inside its context and nothing outside it; stdout untouched
  (`capsys`).
- Subprocess mode: `tests/fixtures/progress/discharge_stream.txt` is a
  REAL, verbatim `regolith build --release` stderr excerpt (10
  discharge-phase events) captured against the `timber_pavilion`
  fleet project with `REGOLITH_LOG=DEBUG`; `parse_stream` recovers the
  exact done/total/elapsed sequence and skips every real surrounding
  log line untouched.
- Manually verified against a real `regolith ship --spec ...` run
  (drawings backend, 10 artifact files) and a real
  `python -m tools.health.fleet --smoke` run: all three phases
  (`fleet`, `discharge`, `ship`) emit correctly-shaped lines.

### Determinism/behavior proof

- `uv run ruff format --check` / `ruff check` / `ty check` clean on
  every touched file.
- `tests/backends` (ship suite, 21 tests), `tests/orchestrator`, and
  `tests/test_logging_format.py` all still pass unmodified --
  goldens untouched, no behavior change for non-subscribers (the new
  records are DEBUG, invisible at the default INFO level exactly like
  any other WO-107 detail line).
- `capsys`-verified: emitting/subscribing to progress events never
  writes to stdout.
- `python -m tools.health.fleet --smoke` (real fleet leg) still PASSes
  with the census golden unchanged.

### Escalations

None. The Rust tracing bridge was not touched -- every new emit site
sits in Python loops that were already silent at the Python layer, so
no span-metadata gap was hit (the reserved WO119-F1 placeholder is
unused).
