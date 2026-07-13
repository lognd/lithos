# WO-119 -- Graphite live progress feedback (D228)

Status: open
Language: Python (progress channel + apps/graphite TUI/GUI);
  gates: after the wave-1..3 merges (the pipeline it instruments
  should be settled first); before WO-117.
Spec: D228 (the three rulings); D217/WO-107 (the log formatter +
  ONE color policy -- the instrumentation this piggybacks);
  AD-31/29-interaction-surface.md + guide 12-graphite.md (graphite
  doctrine); house rules (stdout data, logs stderr, LOG
  EVERYTHING).

## Goal

Long operations (build, ship, fleet runs, optimize, test) show
live phase-level progress bars in graphite's TUI and localhost
GUI, derived from the SAME instrumentation the logging system
already emits -- no second bookkeeping system, zero behavior
change for non-graphite consumers.

## Deliverables

1. Typed progress event derivation: a small adapter over the
   existing log/tracing stream (the D217 span enter/exit + phase
   records, Rust tracing bridged via pyo3-log included) yielding
   (phase, subject, done/total|indeterminate, elapsed). New emit
   sites ONLY where a long loop is currently silent (per-project
   fleet iteration, per-obligation discharge loop, per-artifact
   emission) -- added as ordinary DEBUG-level logs so `-v` users
   see them too (LOG EVERYTHING: additions, never a parallel
   channel).
2. Consumer-agnostic channel API (python/regolith side, one
   module): subscribe from the same process or from a subprocess's
   stderr stream; documented for graphite, LSP (WO-120), and CI.
3. Graphite TUI: per-phase progress bars (textual widgets) for
   build/ship/test/optimize/fleet, with the log tail view kept;
   color through the ONE D191.2/D217 policy.
4. Graphite GUI (localhost viewer): mirrored progress rendering,
   zero external requests (AD-31 doctrine unchanged).
5. Determinism/behavior proof: goldens byte-identical; stdout
   untouched; non-TTY and NO_COLOR behavior unchanged; tests for
   the adapter's parse of real captured streams.

## Acceptance

- Driving a real fleet project build/ship from graphite shows
  live per-phase progress; subprocess stream mode proven by test.
- `make check` + graphite's test target green; goldens
  byte-identical.

## Escalation

If the Rust tracing bridge drops span metadata the adapter needs,
escalate the bridge-field read-side increment (the WO-107
precedent) rather than double-instrumenting in Python.
