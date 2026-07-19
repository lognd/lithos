"""The ONE sanctioned import surface for external UIs (AD-44, charter
`docs/spec/toolchain/44-boundary-charter.md` sec. 4; design-log D267).

graphite (and any future UI) imports ``regolith.surface`` and NOTHING
else from ``regolith``. Every name below is re-exported BY VALUE --
``from regolith.orchestrator.X import Y`` -- never a reach-through
re-export (``from regolith.surface import orchestrate as orchestrate``
would let a consumer walk back INTO the module it names; a flat value
import does not), so this file's own import lines are the single audit
point for what crosses the L2/L5 seam (charter sec. 1: "crossings are
artifacts, not calls"). Enforced twice, by machine: graphite's
``frob.toml`` ``[[policy.forbidden-import]]`` rules ban
``regolith.orchestrator``/``harness``/``realizer``/``backends``/
``compiler`` imports under ``graphite/**``, and (lithos side, tracked
separately) a strata flow claim asserts the graphite consumer node's
only inbound edge is from this module.

D259's two-contact statement is amended to three by AD-44: (a) read the
D244 artifact index, (b) save L0 source text, (c) import this module
for typed read models. No new read capability lives here -- additions
are reviewed API changes (WO-159 non-goals), not silent growth of
``__all__``.
"""

from __future__ import annotations

from regolith.backends.artifact_index import ArtifactIndex, ArtifactRow, build_index
from regolith.backends.calc import (
    AuditIndex,
    AuditRow,
    AuditSummary,
    CalcBook,
    CalcSheet,
)
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.lockfile import parse as parse_lockfile
from regolith.orchestrator.orchestrate import BuildReport, StagedBuildReport

__all__ = [
    # D244 artifact index (charter sec. 3): the one family/kind/viewer
    # description of every emitted file, and the row shape it is made
    # of -- a UI never needs a hardcoded family list to render a build.
    "ArtifactIndex",
    "ArtifactRow",
    "build_index",
    # Calc-book read models (AD-44 addition, reviewed 2026-07-19): the
    # calc audit/sheet views graphite renders -- read models only,
    # never the producers that compute them.
    "AuditIndex",
    "AuditRow",
    "AuditSummary",
    "CalcBook",
    "CalcSheet",
    # The report read models (not the orchestration functions that
    # produce them from a live build): a UI reads a finished build's
    # outcome, it never re-triggers or re-derives one.
    "BuildReport",
    "StagedBuildReport",
    # Lockfile parse: the resolved-slot record and its own text-format
    # parser, so no consumer re-implements the lockfile grammar.
    "Lockfile",
    "parse_lockfile",
]
