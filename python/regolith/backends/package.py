"""The one `dist/<project>/` release-package layout (WO-99 d4, charter 38 sec. 1.3).

`regolith ship` writes every artifact family under one package root plus a
fixed set of top-level index/ledger files:

* ``manifest.json`` -- the signed blake3 (+ optional ed25519) manifest
  (unchanged, `regolith.backends.manifest`);
* ``index.md`` -- a DETERMINISTIC listing of every artifact with its
  sha256 digest, headed by the release-gate stamp;
* ``gate_summary.json`` -- the machine-readable gate verdict
  (`GateSummary`, the SAME accounting the gate itself draws);
* ``parity_ledger.json`` -- the AD-22 parity report over the lockfile +
  gate results + waive ledger;
* ``acceptance_ledger.json`` -- WO-98's territory: this WO writes only a
  placeholder (or the caller-supplied bytes when WO-98's writer runs),
  and NEVER computes gate/acceptance semantics itself.

This module owns only the SIDE files and the index; the per-family
artifact files come from the backends unchanged. Every side file is an
`OutputFile` so it is content-addressed in the manifest and re-verified
by `ship --verify` exactly like any artifact.
"""

from __future__ import annotations

import json

from regolith.backends.framework import OutputFile
from regolith.backends.parity import ParityReport
from regolith.logging_setup import get_logger
from regolith.orchestrator.orchestrate import GateSummary

_log = get_logger(__name__)

INDEX_NAME = "index.md"
GATE_SUMMARY_NAME = "gate_summary.json"
PARITY_LEDGER_NAME = "parity_ledger.json"
ACCEPTANCE_LEDGER_NAME = "acceptance_ledger.json"

# The families charter 38 sec. 1.3 names. Present-or-explicitly-absent:
# `index.md` records which of these directories the package actually
# carries, so a missing family is a visible, reasoned absence rather
# than silent drift (WO-106's fleet gate reads this).
FAMILY_DIRS = (
    "drawings",
    "3d",
    "bom",
    "instructions",
    "boards",
    "firmware",
    "hdl",
    "cost",
    "evidence",
)


def acceptance_ledger_placeholder() -> bytes:
    """The WO-98 hook: a schema-stable EMPTY acceptance ledger.

    WO-99 does NOT compute acceptance/deviation semantics (that is WO-98's
    release-gate work, and this file must never fold acceptances into
    passes); when WO-98's writer runs, it supplies its own bytes to
    :func:`package_side_files` and this placeholder is not used. Until
    then the package carries an honest empty ledger so the layout is
    complete and deterministic.
    """
    return json.dumps(
        {
            "entries": [],
            "note": (
                "placeholder -- populated by the WO-98 acceptance-ledger "
                "writer; no deviations/waivers/assumes recorded"
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        indent=2,
    ).encode("ascii")


def build_index(
    project: str,
    gate: GateSummary,
    artifact_files: tuple[OutputFile, ...],
) -> bytes:
    """Render the deterministic ``index.md``.

    Names every artifact file (sorted by relpath) with its sha256 digest,
    headed by the project name and the gate stamp, and a family-presence
    table (present/absent-with-reason). Never lists ``index.md`` itself
    (it cannot carry its own digest); every OTHER package file, side
    files included, is listed.
    """
    present = {
        family
        for family in FAMILY_DIRS
        for f in artifact_files
        if f.relpath.split("/", 1)[0] == family
    }
    lines: list[str] = [
        f"# Release package: {project}",
        "",
        f"gate: {gate.stamp_text}",
        f"tier: {gate.tier}  ok: {gate.ok}  release_ok: {gate.release_ok}",
        "",
        "## Families",
        "",
    ]
    for family in FAMILY_DIRS:
        mark = "present" if family in present else "absent (no such artifacts)"
        lines.append(f"- {family}/: {mark}")
    lines += ["", "## Artifacts", ""]
    for f in sorted(artifact_files, key=lambda x: x.relpath):
        lines.append(f"- `{f.relpath}`  sha256:{f.sha256}")
    lines.append("")
    return "\n".join(lines).encode("ascii")


def package_side_files(
    project: str,
    gate: GateSummary,
    parity: ParityReport,
    artifact_files: tuple[OutputFile, ...],
    *,
    acceptance_ledger: bytes | None = None,
) -> tuple[OutputFile, ...]:
    """The four top-level side files, as content-addressed `OutputFile`s.

    ``gate_summary.json``, ``parity_ledger.json``, and
    ``acceptance_ledger.json`` are listed IN the index (so ``index.md``
    is built last, over ``artifact_files`` plus these three). The index
    itself is the fourth file returned. ``acceptance_ledger`` defaults to
    the WO-98 placeholder.
    """
    gate_bytes = gate.model_dump_json(indent=2).encode("ascii")
    parity_bytes = parity.model_dump_json(indent=2).encode("ascii")
    accept_bytes = (
        acceptance_ledger
        if acceptance_ledger is not None
        else acceptance_ledger_placeholder()
    )
    side = (
        OutputFile.of(GATE_SUMMARY_NAME, gate_bytes),
        OutputFile.of(PARITY_LEDGER_NAME, parity_bytes),
        OutputFile.of(ACCEPTANCE_LEDGER_NAME, accept_bytes),
    )
    index_bytes = build_index(project, gate, (*artifact_files, *side))
    index_file = OutputFile.of(INDEX_NAME, index_bytes)
    _log.info(
        "package: assembled %d side file(s) (index over %d artifact(s))",
        len(side) + 1,
        len(artifact_files),
    )
    return (*side, index_file)
