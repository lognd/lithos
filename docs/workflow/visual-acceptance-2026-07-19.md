# Coordinator visual acceptance -- 2026-07-19 (T-0030, AD-39 ruling 3)

The AD-39 sign-off mechanism is a human/coordinator EYE on the
shipped artifacts, not a test count. This record covers the cycle-36
residual (WO-123/WO-124 integration) plus the cycle-38 capability
demos, inspected directly this session by the coordinator.

## What was viewed, and the verdicts

- graphite dashboard screenshot (docs/screenshots/dashboard.png,
  regenerated this session via make screenshots -- real Playwright
  captures over the committed fixture): fleet table renders honest
  per-project verdicts (fresh vs STALE report flags, discharge/
  accepted/deferred/violated counts, rigor bars, release gate).
  ACCEPTED.
- graphite calc-sheet screenshot (calc-sheet.png): a discharged
  mfg.cost claim renders with model id + version, citation posture
  (uncited built-in shown AS uncited -- honesty preserved in the UI),
  tier, attestation, margin bar, the Inputs table with provenance
  column, the evidence chain digests with copy affordances, and the
  PDF download path. ACCEPTED.
- demo19 (wire-EDM die set) proof pack: artifact table with sha256
  per file; honesty labels verified present and correct
  (tier=deterministic everywhere, punch-die clearance as a NAMED
  REFUSAL in the checks report, shot-peen optional and unclaimed);
  the SCOPE NOTE names the source-language follow-up rather than
  hiding it. ACCEPTED.
- demo18 (perf-board) proof pack: same shape; no-autorouting and
  no-copper claims stated; every net covered exactly once. ACCEPTED.
- WO-123/124 integration residue: the presentation/fab residuals are
  precisely re-ticketed (T-0056/61/62/63) with F141's audit gating
  now LIVE (a failing calc sheet refuses the ship -- witnessed via
  the demo20/F-WO137-3 incident and its fix this same day).
  ACCEPTED as integrated.

## Bounds of this acceptance

This is an artifact-level acceptance of presentation honesty and
integration, not a dimensional review of every sheet; the drafting
audit (charter 41) remains the mechanical gate, and T-0056's
ChartGeometry generalization remains the named residual for chart-
class sheets.
