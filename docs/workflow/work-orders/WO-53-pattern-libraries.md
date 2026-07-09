# WO-53: pattern libraries v1 (seed packs + recognition/recommendation machinery)

Status: todo
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
