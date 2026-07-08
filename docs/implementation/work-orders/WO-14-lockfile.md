# WO-14: Lockfile

Status: done
Depends: WO-04, WO-12, WO-13
Language: Python (`regolith.orchestrator`; consumes Rust resolutions via WO-18) -- see `../00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: regolith/09 sec. 2-3; regolith/03 sec. 2

## Goal

The reviewable pin surface: every resolution with its cause,
bit-reproducible.

## Deliverables

- Lockfile model + text format (line-oriented, diff-friendly, sorted,
  ASCII): resolved variables w/ causes (WO-04 `Resolution`), allocated
  tolerances/shares, fit/standard expansions, `any` canonical choices,
  evidence hashes, tool/registry versions, package pins
  (version + record revision hash), planner plan hashes, waivers.
- Per-target and per-variant sections; reserve consumption
  materialized as budget shares.
- Cycle-3 rows: `policy: prefer(...)` annotations on rows where a
  preference was decisive; waiver/deviation entries; `extern` pins
  (`cause: extern(<ref>)` with content hash) for linked impls,
  profiles, plans, and images (regolith 12 sec. 6; regolith 08
  sec. 4). Consider waiver expiry semantics here (design log cycle 3,
  carried item) -- flag, do not invent.
- Reader/writer with stable ordering (bit-identical output for
  identical inputs); `diff`-oriented golden tests.
- Cause rendering exactly as regolith/03 sec. 2's excerpt shape.

## Acceptance

- Golden lockfiles for two example builds (static-tier resolutions
  only); rerun produces byte-identical output.
- A changed input produces a minimal, localized diff naming the cause.
