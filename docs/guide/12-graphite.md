# graphite: config, the TUI, and the local-web GUI

WORKING (WO-59, AD-31/D163-D165). `graphite` is its own distribution
over the `regolith` wheel (`apps/graphite/`, own `pyproject.toml`,
console script `graphite`) -- install it separately from the wheel
so the core toolchain stays dependency-lean.

## Install

```
make install-graphite
```

(equivalent to `cd apps/graphite && uv sync`; the package declares an
editable path dependency on the repo root so it always builds
against your local `regolith` wheel).

## Configuration: `regolith config`

One doctrine, four levels, weakest first: the global user file
(`~/.config/regolith/config.toml`, platformdirs-resolved) < the
project's `magnetite.toml` `[tool.regolith]` table < `REGOLITH_*`
environment variables < an explicit CLI flag. `python/regolith/config.py`
is the only reader/writer of either file.

```
regolith config get ui.port                # the effective value
regolith config where ui.port              # value + which level won it
regolith config list                       # every registered key
regolith config set ui.port 9000 --global  # or --local
```

Registered keys (v1): `optimize.budget_evals`, `optimize.seed`,
`ui.host`, `ui.port`, `lint.level`. An unregistered key is a
constructive error naming the registered set -- config never reaches
the margin math (charter sec. 1.1): nothing here can flip a
`check`/`build` verdict.

## `graphite tui`

```
graphite tui [project]
```

Three tabs: **Config** (edit a key in either scope, same module as
the CLI), **Driver** (run `check`/`build`/`optimize` as a subprocess
and see its diagnostics VERBATIM -- the exact bytes the CLI itself
would print, AD-7's one-renderer rule applied to the TUI pane), and
**Report** (browse the last `.regolith/build/build_report.json`).

## `graphite serve`

```
graphite serve [project] --host 127.0.0.1 --port 8765
```

A localhost-only stdlib http server (refuses to bind anywhere else)
serving one self-contained, hand-written ASCII HTML/JS/CSS viewer --
no CDN, no build step, zero external requests. It lists and renders:

- **Sheets**: every `<subject>.drawing.{json,svg,dxf,pdf,explain.txt}`
  set under any `drawings/` directory in the project, generic by
  track name (it does not hard-code `elec_blocks`/`contract_graph`/
  `opt_trace` -- whatever sheets exist on disk are listed). SVGs are
  inlined so their `<title>` elements render as native browser
  tooltips: provenance hover is a reading of the renderer's own
  metadata layers, never a second renderer.
- **Payloads**: every file under `.regolith/payloads/`,
  pretty-printed when it parses as JSON.
- **Traces**: any on-disk `OptimizationTrace` JSON dump
  (`*trace*.json` under `.regolith/`) -- WO-61's `opt_trace` sheet
  slots in here with no viewer change once it lands.

Artifact-only channel (AD-24/AD-22 applied to UI): graphite reads CLI
JSON and disk artifacts only -- it never imports
`regolith.orchestrator`/`regolith.harness` internals (enforced by an
import-graph test in `apps/graphite/tests/`).
