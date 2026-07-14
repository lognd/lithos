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
- **Dimensions**: two extension lines projecting from the measured
  edges, a dimension line spanning between them with arrowheads at
  BOTH ends, and human-readable `value unit` text (2-decimal, e.g.
  `80.00 mm`, plus `+/-lo/hi` when the payload carries a tolerance)
  centered on the line -- never a payload-path prefix, never a
  floating text label painted over the geometry. A dimension whose
  anchor sits on a vertical view edge renders as a vertical dimension
  beside that edge. A principal dimension with no projection in the
  drawn view (e.g. height on a single front view) is a row in a small
  `Dimensions (not projected)` notes table, never an orphan
  annotation.
- **View labels + zones**: every view carries a `NAME  scale` caption
  under its cell (e.g. `FRONT  1:1`), and the sheet border carries
  zone reference marks (digits along the top/bottom, letters along
  the sides) for callouts.
- **Tables**: a ruled header row + body rows, numeric columns
  right-aligned, text columns left-aligned; a cell that would overrun
  the sheet width wraps onto multiple lines (an unbroken token like a
  content address hard-splits) rather than clipping or running off
  the page; a table that would reach the title-block band narrows to
  stay clear of it. No table cell is ever pipe-delimited prose, and a
  ruled table with a header but zero body rows is an audit refusal.
- **Charts** (opt traces): axes with tick labels, unit-labeled axis
  titles (`candidate index`, `objective`), gridlines at a lighter
  minor-emphasis weight, integer tick steps on integer domains
  (labels always distinct), the series plotted inside the axes, the
  winner marked ON the chart with a short `winner: #N` label
  (short-hash in plot captions; the full trace digest lives in the
  candidate-table caption), and the termination caption clamped ON
  the chart -- never a bare polyline.
- **Calc sheets**: four typeset sections -- `Claim / Model` (claim
  text, subject, model id/version, citation, solver, tier,
  attestation), `Inputs` (symbol, value, provenance pin: `record_ref`
  / `declared_literal` / `derived` -- inline numeric claim kwargs
  appear as `declared_literal` rows), `Result` (value and margin WITH
  the claim's own unit, verdict), and `Evidence chain` (hashes).

If a sheet looks wrong (clipped text, overlapping labels, a raw
`key|value` dump), that is exactly what the GATING drafting audit
(`backends/drawings/audit.py`, INV-31) refuses at `regolith ship` time
for the mech/fluid/civil/elec/opt-trace/calc families; a
`drafting_audit_refused` error names the failing rule and sheet.
