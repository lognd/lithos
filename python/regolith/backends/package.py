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

# frob:doc docs/modules/py-backends.md#backends-package
INDEX_NAME = "index.md"
# frob:doc docs/modules/py-backends.md#backends-package
GATE_SUMMARY_NAME = "gate_summary.json"
# frob:doc docs/modules/py-backends.md#backends-package
PARITY_LEDGER_NAME = "parity_ledger.json"
# frob:doc docs/modules/py-backends.md#backends-package
ACCEPTANCE_LEDGER_NAME = "acceptance_ledger.json"

# The families charter 38 sec. 1.3 names. Present-or-explicitly-absent:
# `index.md` records which of these directories the package actually
# carries, so a missing family is a visible, reasoned absence rather
# than silent drift (WO-106's fleet gate reads this).
#
# WO-130 (D244/AD-41): this is the SAME family vocabulary
# `regolith.backends.registry.default_artifact_family_registry` carries
# viewer hints for (plus that registry's own `"ledgers"` family for the
# top-level side files below, which have no directory of their own) --
# `tests/backends/test_artifact_index.py` asserts the two never drift
# apart.
# frob:doc docs/modules/py-backends.md#backends-package
FAMILY_DIRS = (
    "drawings",
    "3d",
    "bom",
    # WO-130 (D244/AD-41) close-out finding (F-WO130-5): the CLI's own
    # `builtin_backends["mech"] = mech` (STEP + fab notes + a bom.csv/
    # json duplicate of `MechBackend`'s own producer) was landed WITHOUT
    # ever joining this list -- exactly the "hardcoded list falls
    # behind" failure mode F145 named, just at the family-DIRECTORY
    # layer instead of the viewer layer. Added here in the same change
    # that gives it a viewer hint.
    "mech",
    "instructions",
    "boards",
    "firmware",
    "hdl",
    "cost",
    "evidence",
    # WO-114 (D221): the calc package + audit index -- the audit trail.
    "calc",
    # WO-125 (charter 40 sec. 3, D237.3): the bring-up harness family --
    # the tap map lands with WO-125; procedure/expected-signals/capture
    # configs land with WO-126. Absent on every release-profile package.
    "harness",
    # WO-165 (AD-47 sec. 5, D268 item 3): the perf-board program's two
    # families -- the wiring map (rendered svg + json) and the wire
    # cut list (CSV + board-dimensions JSON). Absent on any package
    # whose spec names no perf-board substrate.
    "wiring_map",
    "cutlist",
    # WO-166 (AD-47 sec. 5, D268 item 1): the wire-EDM die-set
    # program's two families -- the profile-cut DXF+setup-sheet
    # package and the die-set assembly's check-result package. Absent
    # on any package whose spec names no wire-EDM die-set program.
    "edm_profile",
    "die_set",
    # WO-167 (AD-47 sec. 5, D268 item 4): the dwelling/house-wiring
    # program's two families -- the cable schedule (one row per
    # branch circuit) and the panel schedule (breaker-slot/load rows
    # plus the panel siting verdict). Absent on any package whose
    # spec names no dwelling-wiring program.
    "cable_schedule",
    "panel_schedule",
    # F-WO137-1 (T-0064): the power one-line diagram package (svg +
    # its underlying DrawingModel json). Absent on any package whose
    # spec/inputs name no power net subject.
    "power_oneline",
)


# frob:doc docs/modules/py-backends.md#backends-package
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


def _boards_family_label(artifact_files: tuple[OutputFile, ...]) -> str | None:
    """The boards family's honest status label (WO-103 deliverable 3).

    Reads the FIRST (sorted-relpath, deterministic) `board_status.json`
    the boards family carries -- written by
    `regolith.backends.elec.ElecBackend` -- and returns its "label"
    string; ``None`` (no annotation, never a guess) when the family has
    no status file or the file is not the expected shape.
    """
    for f in sorted(artifact_files, key=lambda x: x.relpath):
        parts = f.relpath.split("/")
        if parts[0] == "boards" and parts[-1] == "board_status.json":
            try:
                doc = json.loads(f.content.decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                _log.warning(
                    "index: %s is not parseable board-status JSON; "
                    "boards family left unlabeled",
                    f.relpath,
                )
                return None
            label = doc.get("label")
            return label if isinstance(label, str) else None
    return None


# frob:doc docs/modules/py-backends.md#backends-package
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
    boards_label = _boards_family_label(artifact_files)
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
        if family == "boards" and family in present and boards_label is not None:
            # WO-103 deliverable 3: gerbers of an unrouted-but-real-
            # outline board are fab-shape evidence, labeled AS SUCH
            # here (the label comes from the backend's own honest
            # `board_status.json`, never invented by the index).
            mark = f"present ({boards_label})"
        lines.append(f"- {family}/: {mark}")
    lines += ["", "## Artifacts", ""]
    for f in sorted(artifact_files, key=lambda x: x.relpath):
        lines.append(f"- `{f.relpath}`  sha256:{f.sha256}")
    lines.append("")
    return "\n".join(lines).encode("ascii")


# frob:doc docs/modules/py-backends.md#backends-package
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
