# py-regolith

Package top level (compiler seam, config/errors/plugins/proc-io/
progress/toolenv/logging). This is the thin Python shell around the
Rust core: only `compiler.py` may import `regolith._core` (AD-4,
`make guard-core`); everything else here is marshalling, config
doctrine, or cross-cutting infrastructure shared by orchestrator/
harness/cli/docgen. Full architecture: `docs/spec/toolchain/00-architecture.md`.
This doc is a symbol-level index into that design, not a restatement.

## _schema_base

<a id="_schema_base"></a>
### `python/regolith/_schema_base.py`

The frozen pydantic base class every generated `_schema` model uses.

Hand-written (the ONE exception to "everything under `_schema/` is
generated") so `make schema` can point datamodel-code-generator's
`--base-class` at a stable import path (AD-5: pydantic v2 frozen).

## compiler

<a id="compiler"></a>
### `python/regolith/compiler.py`

Typed facade over the ``regolith._core`` extension (AD-4).

This module is the ONE door to the compiler core: no other module may
import ``regolith._core`` (enforced by a grep in ``make check``). Every
Python-facing API returns a typani ``Result`` per house style; only
``CoreBug`` (an unrecoverable programmer bug from the boundary) ever
propagates as an exception.

WO-01 exposes just the smoke-test surface; WO-18 grows the real
``check``/``compile`` facade and the schema-version assertion.

## config

<a id="config"></a>
### `python/regolith/config.py`

One configuration doctrine (AD-31, D163/D164; toolchain/29 sec. 1).

Precedence, weakest first: global user file (platformdirs user-config
``regolith/config.toml``) < project ``magnetite.toml`` ``[tool.regolith]``
tables < environment (``REGOLITH_*``) < explicit CLI flag. This module is
the ONLY reader/writer of either file; ``regolith config get|set|list|where``
(cli/app.py) is the surface, and ``get_effective``/``list_effective``
attribute every resolved value to the level that won.

Config is tool preference only (charter sec. 1.1): default optimize
budgets/seed, UI host/port, lint-level passthrough. Nothing here may reach
the margin math -- see ``tests/test_config_import_boundary.py`` for the
import-direction assertion (harness/discharge never import this module).

## errors

<a id="errors"></a>
### `python/regolith/errors.py`

Shared Python-side error VALUES (AD-7 / house style).

Every fallible Python API returns a typani ``Result[T, E]`` whose ``E`` is
one of these frozen error models -- never a bare exception. Exceptions are
reserved for programmer bugs; ``CoreBug`` from the FFI boundary is the one
that propagates.

## logging_setup

<a id="logging_setup"></a>
### `python/regolith/logging_setup.py`

One logging configuration point for the whole toolchain (AD-8).

All log records go to STDERR; stdout is reserved for command output
(results, JSON) so a caller can pipe it cleanly. This adapts the house
logging reference for a compiler CLI, where stdout is the data channel.
Rust ``tracing`` events arrive here through the pyo3-log bridge under the
``regolith._core``/``regolith_*`` logger hierarchy (and span-enter records
under the ``tracing.span`` logger), so they render identically to Python
records. Root level is read from ``REGOLITH_LOG`` (default ``INFO``).

WO-107 (D217) makes the default stream readable at a glance: severity-
colored level tags, a cyan subsystem prefix, dimmed ``key=`` keys,
abbreviated content hashes, escaped newlines, width-truncated records,
demoted span-enter noise, collapsed consecutive duplicates, and a LOUD
final verdict. None of that deletes a record -- ``-v`` restores the full
verbatim firehose (full hashes, no truncation, no dedup, span records
back). Colorization is the ONLY color-gated layer; the noise reductions
apply in plain mode too, so ``NO_COLOR``/non-TTY output stays plain and
byte-stable while still being readable. The color DECISION is the ONE
D191.2 policy (`regolith.cli.color.resolve_color`), handed in by the CLI
edge -- never re-decided here.

This is a single module (not a subpackage) so the dictConfig payload
travels with the code and cannot go missing in an installed wheel.

## plugins

<a id="plugins"></a>
### `python/regolith/plugins.py`

The ONE typed discovery seam for out-of-wheel extensions (AD-26/WO-44).

Generalizes WO-20's proven model-pack discipline to every kind of
out-of-wheel extension: model packs, rule packs, MCU-family packs, and
manufacturing backends. Exactly one entry-point group,
``regolith.plugins``; each entry point resolves to a :class:`PluginManifest`
(frozen, self-describing: id, kind, version, and a kind-specific
``register_fn`` callable). Composition is deterministic (sorted by
entry-point name); a duplicate id within a kind, a malformed manifest, or
an entry point that raises while loading are all loud typed error
values -- never a crash and never last-wins (mirroring
``regolith.harness.plugin``'s pre-WO-44 pack discipline, which this
module now backs).

Trust is unaffected by this seam (INV-14/INV-28): installing a plugin
confers no trust, its evidence/attestation is signed by ITS OWN key.
Distribution is ordinary magnetite/PyPI packaging; this module only
discovers what is already installed in the environment.

## procio

<a id="procio"></a>
### `python/regolith/procio.py`

The ONE process-invocation seam (WO-153, D264 ruling 1).

Design precedent: ``../lograder``'s process module (``TypedExecutable``/
``CLIArgs``) proved two ideas worth adopting -- typed-argv models instead
of hand-built flag lists, and invocation-as-data (every spawn logged as a
structured packet). This module adopts BOTH ideas fresh, in house idiom,
without depending on or vendoring lograder: typani ``Result`` everywhere
(lograder vendors its own), no auto-install (`regolith.toolenv`'s
honest-absence + teaching-message posture, never a host mutation), no
ambient global config (every parameter threaded explicitly).

The shape it generalizes is `regolith.harness.adapter.solve_via_subprocess`
(AD-19): JSON envelope in, one pydantic-validated document out, stderr as
logs, an explicit timeout, typed failure values, never a bare exception.
That contract stays untouched at its own call site (only its spawn moves
onto this seam) -- this module gives every OTHER tool invocation the same
discipline instead of three restatements of it.

Three layers:

- :func:`run_argv`: the raw spawn primitive. Any already-resolved argv,
  MANDATORY explicit timeout, captured stdout/stderr/returncode. A
  nonzero exit is NOT an error here -- callers with their own exit-code
  semantics (AD-19's adapter, the layout wrapper) need the raw
  :class:`ToolOutput` to decide. Only not-found/timeout are infrastructure
  failures at this layer.
- :func:`run_tool`: the toolenv-resolved wrapper. Resolves ``name``
  through `regolith.toolenv.resolve` (missing binary -> :class:`ToolFailure`
  carrying the EXISTING teaching message verbatim, never an auto-install
  attempt), spawns the typed :class:`ToolArgs`' emitted argv, and ALSO
  treats a nonzero exit as a :class:`ToolFailure` (the generalized
  one-shot-pass-fail shape most tool verbs -- verilator, kicad-cli --
  actually want).
- :func:`expect_json`: validates a :class:`ToolOutput`'s stdout as a given
  pydantic model, wrapping a ``ValidationError`` into :class:`ToolFailure`
  rather than letting it escape.

:func:`legacy_bytes_runner` is a compatibility shim for the two call
sites (`regolith.toolenv.resolve`'s version probe, `regolith.realizer.
elec.kicad.run_layout`'s default runner) that were built around an
injectable ``runner`` callable matching ``subprocess.run``'s own contract
(bytes-mode ``CompletedProcess``, ``check=False`` semantics: a nonzero
exit is returned, never raised) -- swapping ONLY this default value
routes their real (non-test, non-fake) spawn through this seam without
touching either function's own body or its test-injected fakes.

## progress

<a id="progress"></a>
### `python/regolith/progress.py`

The D228/D234.3 progress-event channel, producer half (WO-119).

A typed progress event -- phase, subject, done/total (or indeterminate),
elapsed seconds -- derived from the SAME instrumentation the D217/WO-107
log stream already carries. This is NOT a second bookkeeping system: an
emit site is an ordinary DEBUG log record on the dedicated
``regolith.progress`` logger (a child of root, so it flows through the
ONE stderr formatter/handler exactly like every other record -- visible
under ``-v``/``REGOLITH_LOG=DEBUG``, invisible and behavior-neutral at
the default level, per D228.2: presentation only, stdout untouched,
goldens byte-identical).

Two consumption modes over the SAME wire shape:

* in-process subscription (:func:`subscribe`) -- a `logging.Handler`
  filtered to records carrying a `progress_event` attribute, for a
  caller running regolith in the same process (a test, a future
  in-process host).
* subprocess stderr-stream parsing (:func:`parse_line`/:func:`parse_stream`)
  -- the graphite/editor mode: a consumer runs `regolith build --release`
  (or any long verb) as a subprocess with `-v`/`REGOLITH_LOG=DEBUG`,
  reads stderr line by line, and recovers the same :class:`ProgressEvent`
  sequence a Python subscriber would see in-process.

## Wire shape (STABLE, cite verbatim -- graphite WO-G5/WO-G7 and lithos
## WO-120 read this)

Each progress record renders as one line (ANSI, if any, must be
stripped before parsing -- :func:`parse_line` does this; wrapped below
only for this docstring's line length, always emitted as ONE line)::

    progress v=1 phase=<phase> subject=<subject>
        done=<done|-> total=<total|-> elapsed=<elapsed>

- ``v`` -- wire format version (int). Bump ``PROGRESS_WIRE_VERSION`` and
  document the change here on any incompatible change to this line
  shape; consumers key off ``v`` and may refuse an unknown version.
- ``phase`` -- a short stable phase tag (``fleet``, ``discharge``,
  ``ship``, ...). New phases may be added freely; existing tags are
  never renamed or repurposed without a version bump.
- ``subject`` -- the unit of work's identifier (a project name, an
  obligation ref, a backend family name). Free text with no internal
  whitespace (callers must not pass a subject containing spaces).
- ``done``/``total`` -- 1-based progress counters, or literal ``-`` for
  both when the phase is indeterminate (unknown total).
- ``elapsed`` -- seconds since the phase's :func:`start` call, formatted
  to 3 decimal places.

Nothing here replaces the D217 formatter or adds a parallel logging
config: :func:`log_progress` is a thin, single-home wrapper around the
ordinary ``logging.Logger.debug`` call, kept in ONE module so every
emit site shares the exact same wire shape (house rule: no duplication).

## toolenv

<a id="toolenv"></a>
### `python/regolith/toolenv.py`

The ONE external-tool registry (owner directive, optional-tool posture).

Every optional external binary the toolchain may shell out to (KiCad,
HDL simulators, SPICE, FEA meshers/solvers) is described exactly ONCE
here: its canonical name, how to locate it (`shutil.which`, cached),
how to probe its version, what capability tier it unlocks (human
phrasing, for diagnostics and `regolith doctor`), and per-platform
install guidance. Install-hint strings live ONLY in this module --
no call site may hard-code an apt/conda incantation.

Posture (owner directive): a design that does NOT need a tool must
never see its absence (honest skip/indeterminate, the existing WO-24/
35 `ToolUnavailable` discipline); a design that DOES need a tool gets
a loud, teaching diagnostic -- tool name, why this design needs it,
and exact install guidance -- never a bare traceback and never a
silent pass. Call sites ask this module WHAT to say; they never
compose the message themselves (no duplication of hint text).
