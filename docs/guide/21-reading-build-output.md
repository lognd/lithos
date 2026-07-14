# Reading build output

`regolith build`, `check`, and every other verb split their output across
two streams, and the split is a hard rule (AD-8):

- **stdout is DATA.** The ONE renderer's diagnostics, the build summary,
  `--json` reports -- everything a downstream tool parses. It is
  byte-identical no matter how you set `--color`, so `regolith build ...
  | jq` and golden tests never see a stray escape code.
- **stderr is the LOG stream.** Human-facing progress: phases, warnings,
  the final verdict. Colored and abbreviated for reading at a glance;
  never parse it.

## The default stream (WO-107 / D217)

At default verbosity the log stream is tuned for a human on a color
terminal:

- **Leveled colors.** A cyan subsystem prefix (`orchestrator.discharge`,
  `harness.registry`, `lower.lints`), dimmed `key=` keys, yellow
  `warning:` and red `error:` tags, and dim DEBUG detail.
- **A LOUD final verdict.** `build: clean` renders bold green;
  `build: refused (N unresolved)` renders bold red. It is the one line
  you cannot miss.
- **Aggregated deferrals.** Instead of one line per deferred obligation,
  a single `discharge: N obligation(s) deferred: <reason> X, ...`
  summarizes the pass by reason bucket.
- **Quiet re-lowers.** The staged build re-lowers the whole pipeline to a
  fixed point; iterations after the first collapse to one
  `staged build: re-lower iteration N (detail at -v)` header.
- **Abbreviated hashes** (12 chars), **escaped newlines** (multi-line
  bounds stay one record), **width-truncated** long records, and
  **collapsed** consecutive duplicates (`... (x3)`).

Colors follow the ONE color policy (`--color auto|always|never`,
`NO_COLOR`, TTY -- the same decision the renderer uses). Under `NO_COLOR`
or a non-TTY stderr the stream is plain, with zero escape bytes, and
stable across runs. None of the noise reduction touches stdout.

## Verbosity flags

- `-v` / `--verbose` restores the full verbatim firehose: DEBUG records,
  span-enter lines, full hashes, no truncation, no dedup, per-obligation
  deferral detail. Nothing is ever deleted -- everything visible at any
  time is reachable here.
- `-q` / `--quiet` drops the stream to `WARNING` and above.
- `REGOLITH_LOG=DEBUG` (environment) is the pre-flag equivalent of `-v`
  for records emitted before the CLI parses its arguments; an explicit
  `-v`/`-q` flag wins over it (D163: the CLI flag is strongest).

## When to reach for `-v`

Default output tells you *what happened*; `-v` tells you *why a specific
obligation deferred*. If the summary says `deferred 12: no_model 8,
unresolved_limit 4` and you need the exact claim behind one of them,
re-run with `-v` and search the per-obligation `obligation <hash>
deferred: <reason> (<detail>)` lines.

## Reading the sheets (WO-123 / charter 41)

Every emitted PDF/SVG sheet -- mech/civil/fluid/elec drawings, opt
traces, calc sheets, BOM/cost/schedule/SI tables -- follows ONE grammar
(charter 41 sec. 1), so once you can read one sheet you can read all
of them:

- **Title block** (bottom-right box): each field is a small caption-face
  LABEL line (`TITLE`, `DWG NO.`, `REV`, `SCALE`, `SUBJECT`, `SHEET`)
  over a larger body-face VALUE line -- never a bare unlabeled string.
  `SHEET n / N` is the sheet's position in its `DrawingModel`'s own
  sheet list.
- **Provenance footer** (bottom-left, small caption text): `design
  <content-address>` (the model's own content digest, AD-6 -- pins
  exactly what was rendered), `schema v<N>`, and `style <pack id>`.
  No wall-clock timestamp ever appears here (determinism, AD-6/INV-10).
- **Dimensions**: a witness/extension line off the dimensioned point, a
  short dimension line with an arrowhead, and `role=value unit` text
  (plus `+/-lo/hi` when the payload carries a tolerance) -- never a
  floating text label painted over the geometry.
- **Tables**: a ruled header row + body rows, numeric columns
  right-aligned, text columns left-aligned; a cell that would overrun
  the sheet width wraps onto multiple lines rather than clipping or
  running off the page. No table cell is ever pipe-delimited prose.
- **Charts** (opt traces): axes with tick labels and gridlines, the
  series plotted inside the axes, and the winner/termination captions
  clamped ON the chart -- never a bare polyline.

If a sheet looks wrong (clipped text, overlapping labels, a raw
`key|value` dump), that is exactly what the GATING drafting audit
(`backends/drawings/audit.py`, INV-31) refuses at `regolith ship` time
for the mech/fluid/civil/elec/opt-trace/calc families; a
`drafting_audit_refused` error names the failing rule and sheet.
