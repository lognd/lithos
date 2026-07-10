# graphite

graphite (the drawing mineral) is the regolith interaction surface
(WO-59, AD-31): a textual TUI plus a localhost-only web GUI for
driving builds and reading their artifacts. It is its own
distribution over the `regolith` wheel (own `pyproject.toml`, console
script `graphite`) so the core toolchain stays dependency-lean --
install it separately:

```
make install-graphite          # from the repo root
# equivalent to: cd apps/graphite && uv sync
```

## Launch

```
graphite tui [project]         # terminal UI: Config / Driver / Report tabs
graphite serve [project]       # local web viewer (default 127.0.0.1:8765)
```

- **tui**: edit config keys in either scope, run
  `check`/`build`/`optimize` as a subprocess with its diagnostics
  shown verbatim (AD-7's one-renderer rule), and browse the last
  `.regolith/build/build_report.json`.
- **serve**: a stdlib HTTP server that refuses to bind anywhere but
  localhost and serves one self-contained ASCII HTML/JS/CSS viewer --
  no CDN, no build step, zero external requests. It lists and renders
  drawing sheets (`drawings/`), payloads (`.regolith/payloads/`), and
  optimization traces.

## Configuration

graphite's Config tab is the same `regolith config` doctrine the CLI
exposes: four levels, weakest first (global user file < project
`magnetite.toml` `[tool.regolith]` < `REGOLITH_*` env vars < explicit
CLI flag), with `python/regolith/config.py` as the only reader/writer.
See `regolith config get|where|list|set`.

## Boundaries

Artifact-only channel (AD-24/AD-22 applied to UI): graphite reads CLI
JSON and on-disk artifacts only -- it never imports
`regolith.orchestrator` or `regolith.harness` internals (enforced by
an import-graph test in `tests/`).

Full guide: `docs/guide/12-graphite.md` (repo root).
