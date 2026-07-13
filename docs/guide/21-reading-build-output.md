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
