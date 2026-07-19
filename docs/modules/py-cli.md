# py-cli

The CLI surface: `regolith` entry point (`app.py`), terminal color
handling, and tool/design discovery helpers. See
`docs/spec/toolchain/00-architecture.md` for the CLI's place as the
outermost seam over the orchestrator/harness/backends.

## app

<a id="app"></a>
### `python/regolith/cli/app.py`

The typer application object and its subcommands (AD-10).

Rich/terminal output lives only in this layer; libraries return data.
WO-15 adds ``check``/``build``/``debug``/``fmt``; WO-01 provides
``version`` so the installed console script is exercisable end to end.

## color

<a id="color"></a>
### `python/regolith/cli/color.py`

The one CLI color-decision seam (owner directive: optional ANSI
colors when the terminal supports them).

Color is decided at the EDGE, never in the renderer (`regolith-diag`
stays the ONE renderer, AD-7; it only accepts a bool switch). This
module implements the `auto` policy -- isatty on the stream diagnostics
are actually printed to (stdout, per the house "stdout is data" rule:
rendered diagnostics are `check`/`build`'s command output, not a log
line) AND no `NO_COLOR` env var AND `TERM` is not `dumb` -- with
`always`/`never` as explicit overrides that win outright. NO_COLOR
(https://no-color.org) beats `auto` but loses to an explicit
`--color always`.

## discovery

<a id="discovery"></a>
### `python/regolith/cli/discovery.py`

Manifest-anchored project-root discovery (WO-43 deliverable 1).

Mirrors ``crates/regolith-ls/src/workspace.rs::discover_root`` exactly
(WO-38 deliverable 1) so the CLI and the language server agree on what
"the project" means from a single opened path: walk upward from the
given file/directory looking for ``magnetite.toml``; if none is found
anywhere up to the filesystem root, the opened path itself is the root.
This is a second READER of the same house convention, not a second
implementation of a different one -- the algorithm is deliberately
byte-for-byte the same walk, kept in Python because `regolith.cli` is
Python (AD-14) and the Rust crate is not on the FFI boundary (AD-4).
