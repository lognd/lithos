# WO-53: pattern libraries v1 (seed packs + recognition/recommendation machinery)

Status: done (seed batch; catalog-growth batches from the market
research memo recorded as CUT below, not silently dropped)
Depends: WO-45 (stdlib v1 -- pattern packs are stdlib packages),
WO-44 (plugin seam), WO-41 (scaffolding + docsgen surfaces this
extends), WO-28 engine remainder (recognition rules ride the rule
engine; the `advise:` severity exists -- if structural predicates
the recognition rules need are missing from the query surface,
ESCALATE per AD-22, never grow a side path).
Language: package content (stdlib/) + Python (template + datasheet
wiring) + Rust only if an escalated query predicate is approved.
Spec: docs/spec/toolchain/26-pattern-libraries.md (NORMATIVE
charter), 00-architecture.md AD-28 (+ AD-21/24/26), design-log
2026-07-08-cycle-27 D144; regolith/04 (contracts + spec:),
regolith/11 secs. 2/8 (parts kind, catalog); hematite/04 sec. 1
(vocabulary discipline for pattern names).

## Goal

The pattern-library machinery proven end to end on one mechanical
and one electrical pattern: packaged contracts with behavioral laws
and model halves, `advise:`-only recognition rules, scaffolding
templates, and rendered datasheets -- the seed the catalog grows
from by ordinary publishing.

## Deliverables

1. `stdlib/std.mech.mechanisms/`: `four_bar` -- interface (link
   lengths as params, coupler-law `spec:`, range + transmission-
   angle promises), harness-half model node (closed-form kinematics;
   the feldspar `dynamics` tier registers under the same kinds when
   its phase lands), and a recognition rule (`forall` over pivot
   matings whose `couples:` law matches; `advise:` names the
   pattern + gains; `per:` cites Norton/Sclater).
2. `stdlib/std.elec.patterns/`: `level_shifter` -- abstract block +
   `spec:`, one reference impl, recognition rule over the discrete
   equivalent (the corpus's hand-rolled shape), `per:` cites
   Horowitz & Hill.
3. `magnetite new --template <pattern>` (WO-41 scaffolding seam):
   emits a consuming artifact skeleton with the pattern imported and
   its params stubbed `free`/`in [...]`.
4. `regolith doc` pattern datasheets: params, promises, spec law,
   model coverage, citations (the watchlisted "connection
   datasheet" view; charter sec. 1.4).
5. Fixtures proving INV-3: recognition advice is verdict-inert
   (violated-advice build still passes; `--release` unaffected);
   pack fixtures per the AD-21 `expect:` discipline.

## Acceptance criteria

- Charter sec. 4 verbatim (both patterns end to end: recognize,
  scaffold, datasheet, verdict-inert by test).
- Recognition uses only the existing query/rule surface OR carries
  an approved escalation -- zero private compiler paths (AD-22).
- Pattern names collide with nothing (hematite/04 registry checked);
  `make check` green.

## Non-goals

- Catalog breadth (two seed patterns prove the machinery; the rest
  is publishing).
- Auto-substitution, pattern DSLs (charter sec. 3).
- The feldspar-side numeric mechanism solvers (its phase WOs).

## Close-out (dispatch of 2026-07-09)

Both seed patterns landed end to end, real source (not phantom
references), verified against the live compiler:

1. `stdlib/std.mech.mechanisms/four_bar.hema`: `mating FourBar<ground,
   input, coupler, output>` (coupler law via `couples:`, promises
   `range`/`transmission_angle`), plus a `dfm:` recognition rule
   (`four_bar_shape`, `advise:` severity, `per:` Norton/Sclater &
   Chironis) with both `expect:` cases green under `regolith rules
   test`.
2. `stdlib/std.elec.patterns/level_shifter.cupr`: `block
   LevelShifter<v_lo, v_hi>` + `spec:` + one `impl ... by circuit`
   reference impl (BSS138-class FET + dividers), plus an `erc:`
   recognition rule (`level_shifter_shape`, `advise:`, `per:` Horowitz
   & Hill) with both `expect:` cases green.
3. `magnetite new --template four_bar|level_shifter`
   (`python/regolith/magnetite/scaffold.py`, new
   `_PATTERN_TEMPLATE_LANGUAGE` seam beside the existing track
   templates; `templates/patterns/<pattern>/{manifest.toml,source}`)
   emits a project whose source imports the pattern and stubs its
   params `free`; both check green by construction
   (`tests/magnetite/test_scaffold.py`'s existing
   `test_every_template_checks_green` covers them for free via
   `VALID_TEMPLATES`).
4. `regolith doc` renders both datasheets with ZERO docgen code
   changes: WO-41's extractor/renderer are already generic over any
   package source (params/fields, promises, spec/couples law, the
   leading doc comment as citation text) -- confirmed by running
   `regolith doc` over both pack files.
5. INV-3 fixtures: `examples/tracks/hematite/four_bar_pattern_advice.hema`
   and `examples/tracks/cuprite/level_shifter_pattern_advice.cupr`
   attach each pack bare (`process=<pack>`, the `wire_ampacity`
   precedent) and check clean; `tests/golden/test_pattern_libraries.py`
   proves both `expect:` fixtures green, the `fail` case reproducing
   the promised advisory verdict, and pack attachment never blocking
   `check`.

Escalation checked, none needed: recognition rules quantify
(`forall p in pivots` / `forall n in nets`) over `EntityKind::Other`
domains exactly as `jlc_2l`'s reference pack already does for
`traces`/`vias`/`buses` (`base_selector` maps any unrecognized kind
word to `Other`, WO-28's own documented escape valve) -- no new query
predicate, no side path. Real corpus population of a queryable
"coupled pivot pair" / "discrete level-shift" domain does not exist
yet (mech has no mating/connect entity structuring; elec nets/
instances carry no fields, per WO-28's own close-out note on the elec
static tier) -- both recognition rules defer honestly in a from-
primitives build exactly like jlc_2l's rules do today. This is a
scoped residual, not a silent gap: the fired-advisory half of INV-3 is
proven through `rules test`'s `expect: fail` fixture (deliverable 5,
item 5 above), which is the same tractable proof WO-28 itself relied
on before real entity structuring existed. Reopens when a future WO
structures mating/connect or net/instance entities as real
`EntityKind`s (the same reopen door WO-28's close-out already named).

Cut (catalog growth, not this WO's seed, charter sec. 3 non-goal):
the market-research v1 batches -- mech (slider_crank, lead/ball screw,
belt drive, gear train, bearing arrangement, spring) and elec
(decoupling, LDO, RC_debounce, reverse-polarity, TVS) -- and all of
`std.fluid.circuits`/`std.civil.assemblies` (the latter also gated on
WO-48/feldspar per the memo). Each is the same package shape as the
two seed patterns and is ordinary catalog growth by publishing, not a
blocked dependency; recorded here rather than silently left off the
README.

`make check`: green (fmt, clippy, ruff, ty, cargo test, pytest --
no Rust surface touched by this WO, per its own `Language:` header).
No new negative fixtures (nothing in this WO's scope produces a
compile ERROR; the two positive advice fixtures above are the new
corpus content, listed for the record: none in `examples/negative/`).
