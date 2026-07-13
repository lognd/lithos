# WO-119 -- Progress event channel, producer half (D228; reframed by D234)

Status: open
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
