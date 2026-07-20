"""The `sim/` manufacturing package: a `hdl.sim_assert` discharge's own
artifact family (WO-155 deliverable 7, T-0068).

Mirrors `backends/hdl.py`'s AD-22 posture exactly: nothing here
invokes verilator. The harness-side discharge
(`harness.models.hdl.models.HdlSimAssertGenericModel.estimate`) already
ran the tool (or produced an honest tool-absence `Err`) and cached its
own content-addressed family
(`harness.models.hdl.sim_artifacts.SimArtifactCache`); this backend
only SERIALIZES what a caller already holds (``SimProducts``, the
backend-local mirror of that family -- kept backend-local rather than
importing the harness type directly, matching `HdlBuildProducts`'
precedent of never re-exporting a harness/evidence shape verbatim
across the backends boundary).

Provenance tier is ``model_derived`` (AD-45): a sim family is
DISCHARGE evidence, not a raw manufacturing-tool pass over pinned
geometry (the ``real_tool`` tier) and not regolith's own deterministic
serialization (the ``deterministic`` tier) -- see `framework.
ArtifactProvenance`'s docstring. ``source_refs`` cites the exact
stimulus ref the discharge resolved (WO-155 acceptance criterion 2),
threaded through `artifact_index.build_index`'s own ``source_refs``
parameter by whatever caller assembles the ship-time index (this
backend does not build the index itself, `HdlBackend`'s own
precedent).
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict
from typani.result import Ok, Result

from regolith.backends.framework import (
    ArtifactProvenance,
    BackendInputs,
    OutputFile,
    ToolIdentity,
)
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


# frob:doc docs/modules/py-backends.md#backends-sim
class SimMismatchRow(BaseModel):
    """One directed vector's failed expectation, backend-local mirror of
    `harness.models.hdl.sim_artifacts.SimMismatch` (kept a separate type
    so a backend never depends on a harness evidence shape verbatim,
    `HdlTierRow`'s own precedent)."""

    model_config = ConfigDict(frozen=True)

    vector: str
    cycle: int
    expected: str
    got: str


# frob:doc docs/modules/py-backends.md#backends-sim
class SimProducts(BaseModel):
    """One subject's already-discharged `hdl.sim_assert` sim family:
    the report fields + the trace bytes (``None`` iff
    ``trace_present`` is ``False``, the honest named-absence posture,
    D264 ruling 2 -- never a fabricated trace)."""

    model_config = ConfigDict(frozen=True)

    tool: str = "verilator"
    tool_version: str
    src_digest: str
    stimulus_digest: str
    stimulus_ref: str
    content_address: str
    vectors_run: int
    vectors_passed: int
    mismatches: tuple[SimMismatchRow, ...] = ()
    trace_present: bool
    trace_absent_reason: str | None = None
    trace_vcd: bytes | None = None


def _sim_report_bytes(subject: str, products: SimProducts) -> bytes:
    """The `sim_report.json` shape (deliverable 7): vectors run/passed,
    the structured mismatch table, tool+version, stimulus provenance,
    and the content address -- shape precedent `backends/hdl.py`'s
    `_tier_report`."""
    payload = {
        "subject": subject,
        "tool": products.tool,
        "tool_version": products.tool_version,
        "src_digest": products.src_digest,
        "stimulus_digest": products.stimulus_digest,
        "stimulus_ref": products.stimulus_ref,
        "content_address": products.content_address,
        "vectors_run": products.vectors_run,
        "vectors_passed": products.vectors_passed,
        "mismatches": [
            {
                "vector": m.vector,
                "cycle": m.cycle,
                "expected": m.expected,
                "got": m.got,
            }
            for m in products.mismatches
        ],
        "trace": {
            "present": products.trace_present,
            "reason": products.trace_absent_reason,
        },
    }
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


# frob:doc docs/modules/py-backends.md#backends-sim
class SimBackend:
    """Produces the `sim/` manufacturing package: `trace.vcd` (when the
    discharge actually captured one) + `sim_report.json`, per subject
    in ``BackendInputs.sim`` (WO-155 deliverable 7, T-0068)."""

    # frob:doc docs/modules/py-backends.md#backends-sim
    # frob:tests tests/backends/test_sim.py::test_sim_backend_ships_trace_and_report_with_model_derived_tier
    # frob:tests tests/backends/test_sim.py::test_sim_backend_honest_absence_when_trace_unavailable
    # frob:tests tests/backends/test_sim.py::test_sim_backend_reports_full_mismatch_table
    # frob:tests tests/backends/test_sim.py::test_sim_backend_no_subjects_ships_nothing
    # frob:tests tests/backends/test_sim.py::test_sim_backend_output_registers_in_the_artifact_index
    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit ``sim/<subject>/trace.vcd`` (present iff the discharge
        captured one) and ``sim/<subject>/sim_report.json``, both
        tagged ``model_derived`` provenance citing the verilator
        version the discharge actually ran (AD-45)."""
        files: list[OutputFile] = []
        for subject, products in sorted(inputs.sim.items()):
            base = f"sim/{subject}"
            provenance = ArtifactProvenance(
                tier="model_derived",
                tool=ToolIdentity(
                    name=products.tool, version_digest=products.tool_version
                ),
            )
            if products.trace_present and products.trace_vcd is not None:
                files.append(
                    OutputFile.of(
                        f"{base}/trace.vcd",
                        products.trace_vcd,
                        provenance=provenance,
                    )
                )
                _log.info("sim backend: trace.vcd for %s", subject)
            else:
                _log.info(
                    "sim backend: no trace.vcd for %s (%s)",
                    subject,
                    products.trace_absent_reason,
                )
            files.append(
                OutputFile.of(
                    f"{base}/sim_report.json",
                    _sim_report_bytes(subject, products),
                    provenance=provenance,
                )
            )
        _log.info("sim backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))


__all__ = ["SimBackend", "SimMismatchRow", "SimProducts"]
