"""The repo health gate (`make health`, WO-106 / D219).

ONE command that proves the owner's bar and keeps it proven, composing
four legs cheapest-first -- each also runnable alone, each emitting ONE
standardized typed summary row (:class:`~tools.health.report.LegSummary`:
leg, ok, counts, evidence pointer) and, together, a machine-readable
``health_report.json``:

* ``check``       -- the existing code gates (fmt, clippy, ruff, ty,
  guard-core, schema drift, Rust + Python tests); this leg CALLS the
  existing ``make check`` rather than re-implementing any gate (D219
  refactor rule).
* ``fleet``       -- every D210 fleet project builds ``--release`` green,
  ships a hash-verified package, and its census matches the committed
  golden (``tests/golden/data/fleet_census.json``).
* ``demos``       -- every live WO-108 proof pack's manifest is complete
  and deterministic (reuses the WO-108 runner + completeness test).
* ``consistency`` -- the standardization sweeps (D/F-number uniqueness,
  WO-Status-vs-TODO agreement, extension single-sourcing, golden
  byte-drift, memo/waiver ledger integrity, stale-worktree detection).

Detail is DEBUG; each leg logs exactly one INFO row and a loud verdict
(WO-107 posture). stdout is data; all logs go to stderr.
"""

from __future__ import annotations
