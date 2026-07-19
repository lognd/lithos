# WO-159 -- `regolith.surface` UI read facade (AD-44)

Status: open (Depends: none new -- D244 artifact index, report read
  models, and lockfile parse are all already landed; this WO is the
  facade module + graphite migration + the enforcement pair, not new
  read machinery)
Language: Python (`python/regolith/surface.py`); the graphite half of
  this WO is a companion, filed and executed in graphite's OWN repo
  (its own `tickets.md`), not by this repo's ticket tree -- see
  "Companion (graphite side)" below.
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 4 (AD-44, the
  exact export list and the two machine-enforced rules); design-log
  `docs/workflow/design-log/2026-07-19-cycle-38.md` D267 (the
  "exactly three contacts" amendment).

## Goal

Give external UIs (graphite today, any future UI later) exactly ONE
sanctioned import surface into `regolith`: a new `regolith.surface`
module that re-exports, BY VALUE (not by reach-through re-export of
the underlying module), only:

- the D244 artifact index models + `build_index` (whatever
  `python/regolith/backends/artifact_index.py` currently exports as
  its public read surface: `ArtifactRow`, `ArtifactIndex`/equivalent,
  `build_index`),
- the report read models (`BuildReport`, `StagedBuildReport` --
  locate their current home, likely `orchestrator/orchestrate.py` or
  a report-specific module, and re-export the read-only types, not
  the orchestration functions that produce them from a live build),
- lockfile parse (`orchestrator/lockfile.py`'s parse entry point and
  its resulting model type).

## Deliverables

1. `python/regolith/surface.py`: a thin facade module. Public API is
   an explicit `__all__` naming every re-exported symbol; each import
   line is `from regolith.orchestrator.X import Y` (not `import *`),
   so the facade's own source is the single audit point for what
   crosses the seam. One-line docstring per re-export explaining WHY
   it is UI-visible (not restating the name).
2. Confirm (via grep, recorded in the close-out) that
   `python/regolith/backends/artifact_index.py`'s `build_index` and
   row models, and the report/lockfile read models, are the CURRENT
   real names -- if any of the charter's named types have moved or
   been renamed since 2026-07-19, note the actual current name in the
   facade and in this WO's close-out rather than silently aliasing.
3. Migrate `graphite/service/reports.py` and
   `graphite/server/routes/build.py` (the two files named in the
   charter's finding) onto `regolith.surface` imports. THIS IS THE
   GRAPHITE-REPO HALF OF THE WORK: since this dispatch runs from the
   lithos main checkout only, this WO's Rust/Python deliverable is
   items 1-2 and item 4 below; the graphite migration itself is
   filed as a companion ticket in graphite's OWN `tickets.md` by
   whatever lane picks up graphite work next (do not attempt to
   edit the graphite checkout from this WO if it is not a writable
   sibling checkout in the executing agent's worktree -- escalate
   instead of skipping silently).
4. Enforcement, both sides:
   - Lithos side: a strata flow claim (see `design/lithos.strata`
     for the existing claim DSL) asserting the graphite consumer
     node's only inbound edge is from the `regolith.surface` node --
     mirror the pattern of the existing sys-audit strata claims
     landed under T-0034/T-0037.
   - Graphite side (companion, not this repo's scope): a
     `[[policy.forbidden-import]]` rule in graphite's `frob.toml`
     forbidding `regolith.orchestrator`, `regolith.harness`,
     `regolith.realizer`, `regolith.backends`, `regolith.compiler`
     imports anywhere under `graphite/**`. Name this explicitly in
     the WO close-out as "graphite-side, filed as graphite ticket
     <id-once-known>" rather than silently marking it done from
     this repo.

## Companion (graphite side)

File, in graphite's own ticket queue: "migrate reports.py/build.py
routes onto regolith.surface; add frob.toml forbidden-import policy
for regolith.orchestrator/harness/realizer/backends/compiler under
graphite/**". Blocked on this WO's `regolith.surface` module existing
and being pip-installable/importable by graphite's environment.

## Non-goals

- No new read capability. If graphite needs a read model the D244
  index/report/lockfile trio does not already provide, that is a
  facade-addition ticket reviewed as an API change, not scope for
  this WO.
- No write-side change (D261's compiler-indistinguishability proof
  for the write side is unaffected).

## Acceptance

- `python -c "import regolith.surface"` succeeds and
  `regolith.surface.__all__` lists exactly the charter's named
  types/functions (no extras).
- `grep -rn "from regolith.orchestrator\|from regolith.harness\|from regolith.realizer\|from regolith.backends\|from regolith.compiler" python/regolith/surface.py` returns ONLY the facade's own controlled imports (i.e. the facade is the one file allowed to reach in; nothing else changes).
- A strata flow claim exists and is proved (`frob check` / the
  project's strata-audit test integration, same mechanism T-0034/
  T-0037 used) asserting the single-inbound-edge property for the
  graphite consumer node once the companion migration lands (this
  WO's own close-out may prove the claim against the FACADE side
  only if the graphite migration has not yet landed -- name that
  explicitly, do not claim proof of a migration this WO did not
  perform).
- `make check` green.
- Close-out names the graphite companion ticket id if filed, or
  states plainly that graphite-side filing is deferred to whichever
  lane next has a writable graphite checkout.
</content>
