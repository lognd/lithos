"""The `sim/` artifact family (WO-155 deliverable 7, T-0068): what a
`hdl.sim_assert` discharge PRODUCES beyond the bare pass/fail evidence
-- `trace.vcd` (a verilator `--trace` waveform, when the tool
environment supports it) and `sim_report.json` (vectors run/passed, a
structured mismatch table, tool+version, and the content address the
cache key already is), shape precedent `backends/hdl.py:103-144`'s
`tier_report.json`.

Provenance posture (AD-45, D264 ruling 5): a sim family is
``model_derived`` -- it is not a raw manufacturing-tool pass (the
``real_tool`` tier) and not regolith's own deterministic serialization
(the ``deterministic`` tier); it is evidence a DISCHARGING MODEL
produced by running verilator against an author-cited stimulus. The
family's report always names the exact stimulus/source digests and
tool version that produced it (INV-TBD leg (a) proof argument, recon
sec. 4e) -- never inferred post-hoc.

Content-address cache (deliverable 8): :func:`sim_artifact_cache_key`
folds ``(hdl_src digest, stimulus digest, model version)`` exactly the
way `orchestrator/cache.py`'s `obligation_cache_key` folds the harness
evidence key (same blake3 domain-tagged canonical-JSON law, INV-1/
INV-10) -- never a line number or other volatile identity (F154).
:class:`SimArtifactCache` is the lookup itself: a discharge that
produces a family under a key ALREADY populated is instructed to skip
straight to the model's own EvidenceStore-level cache hit (the
discharging model never even calls this module's producer twice for
the same key in one process) -- and any consumer holding the SAME key
re-links the identical family bytes without re-invoking verilator,
proven by `tests/harness/test_hdl_sim_artifacts.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import blake3
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.procio import ToolArgs

_log = get_logger(__name__)

# Domain tag prefixing every sim-artifact cache key (mirrors
# `orchestrator/cache.py`'s `_KEY_DOMAIN` law -- a distinct domain so
# this content address can never collide with the harness evidence
# cache's own key space, AD-18).
# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
SIM_ARTIFACT_KEY_DOMAIN = "regolith.harness.sim_artifacts"

# The generated testbench's trace output filename (relative to the
# verilator work directory) -- fixed so `$dumpfile(...)` and the
# post-run file read always agree.
_TRACE_FILENAME = "trace.vcd"

_FAIL_LINE_RE = re.compile(
    r"^ASSERT FAIL (\S+) cycle=(\d+) expected=(-?\d+) got=(-?\d+)$"
)


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
class SimMismatch(BaseModel):
    """One directed vector's failed expectation (a `sim_report.json`
    mismatch-table row): the vector name, the cycle it failed at, and
    the expected-vs-actual signal values -- parsed from the SAME
    `ASSERT FAIL` marker line `build_generated_testbench` emits."""

    model_config = ConfigDict(frozen=True)

    vector: str
    cycle: int
    expected: str
    got: str


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
class SimReport(BaseModel):
    """The `sim_report.json` shape (deliverable 7): vectors run/passed,
    the structured mismatch table, tool+version, stimulus provenance,
    and the cache key (``content_address``) this family was produced
    under -- shape precedent `backends/hdl.py`'s `tier_report.json`.

    ``trace_present``/``trace_absent_reason`` record the honest named
    absence when verilator's `--trace` passthrough did not produce a
    waveform in this tool environment (D264 ruling 2's "no fabricated
    trace" posture) -- never a silently-missing `trace.vcd` with no
    explanation on the report that shipped instead of it.
    """

    model_config = ConfigDict(frozen=True)

    subject: str
    tool: str = "verilator"
    tool_version: str
    src_digest: str
    stimulus_digest: str
    stimulus_ref: str
    content_address: str
    vectors_run: int
    vectors_passed: int
    mismatches: tuple[SimMismatch, ...] = ()
    trace_present: bool
    trace_absent_reason: str | None = None


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
class SimArtifactFamily(BaseModel):
    """One subject's whole `sim/` package content: the report plus the
    trace bytes (``None`` iff ``report.trace_present`` is ``False``)."""

    model_config = ConfigDict(frozen=True)

    subject: str
    report: SimReport
    trace_vcd: bytes | None = None


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_sim_artifact_cache_key_is_deterministic_and_domain_separated
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_sim_artifact_cache_key_changes_with_any_digest_or_version
def sim_artifact_cache_key(
    src_digest: str, stimulus_digest: str, model_version: str
) -> str:
    """Content-address a sim family under ``(src_digest, stimulus_digest,
    model_version)`` (deliverable 8): the SAME blake3 domain-tagged
    canonical-JSON law `orchestrator/cache.py::obligation_cache_key`
    uses for the harness evidence cache, applied one layer down. Never a
    line number or other volatile identity (F154) -- digests and the
    discharging model's own version string only."""
    canonical = json.dumps(
        {
            "domain": SIM_ARTIFACT_KEY_DOMAIN,
            "src_digest": src_digest,
            "stimulus_digest": stimulus_digest,
            "model_version": model_version,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "blake3:" + blake3.blake3(canonical.encode("ascii")).hexdigest()


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_render_sim_report_json_shape_and_determinism
def render_sim_report_json(report: SimReport) -> bytes:
    """Canonical deterministic JSON bytes for ``report`` (sorted keys,
    ASCII, no whitespace drift -- the same determinism law every other
    ship-path JSON producer in this repo follows, `backends/hdl.py`'s
    `_tier_report` precedent)."""
    payload = {
        "subject": report.subject,
        "tool": report.tool,
        "tool_version": report.tool_version,
        "src_digest": report.src_digest,
        "stimulus_digest": report.stimulus_digest,
        "stimulus_ref": report.stimulus_ref,
        "content_address": report.content_address,
        "vectors_run": report.vectors_run,
        "vectors_passed": report.vectors_passed,
        "mismatches": [
            {
                "vector": m.vector,
                "cycle": m.cycle,
                "expected": m.expected,
                "got": m.got,
            }
            for m in report.mismatches
        ],
        "trace": {
            "present": report.trace_present,
            "reason": report.trace_absent_reason,
        },
    }
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
class SimArtifactCache:
    """The in-process content-addressed lookup for produced `sim/`
    families (deliverable 8): a plain dict keyed by
    :func:`sim_artifact_cache_key`. Mirrors `orchestrator.cache.
    EvidenceStore`'s minimal get/put shape, but scoped to this module
    (never imported by `orchestrator/`, which is the wrong import
    direction -- `orchestrator` imports `harness`, never the reverse)."""

    def __init__(self) -> None:
        """Start empty; a fresh cache per test/process unless a caller
        shares one instance across discharges (see
        :func:`default_sim_artifact_cache`)."""
        self._entries: dict[str, SimArtifactFamily] = {}

    # frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
    # frob:tests tests/harness/test_hdl_sim_artifacts.py::test_sim_artifact_cache_get_put_roundtrip
    def get(self, key: str) -> SimArtifactFamily | None:
        """The cached family for ``key``, or ``None`` on a miss."""
        hit = self._entries.get(key)
        if hit is not None:
            _log.debug("sim artifact cache HIT for %s", key)
        else:
            _log.debug("sim artifact cache MISS for %s", key)
        return hit

    # frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
    # frob:tests tests/harness/test_hdl_sim_artifacts.py::test_sim_artifact_cache_get_put_roundtrip
    def put(self, key: str, family: SimArtifactFamily) -> None:
        """Store ``family`` under ``key`` (overwrites any prior entry --
        content-addressed, so a re-put under the same key is always
        byte-identical by construction)."""
        self._entries[key] = family
        _log.info(
            "sim artifact cache: stored family for %s (subject=%s, trace_present=%s)",
            key,
            family.subject,
            family.report.trace_present,
        )


_DEFAULT_CACHE = SimArtifactCache()


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_default_sim_artifact_cache_is_a_shared_singleton
def default_sim_artifact_cache() -> SimArtifactCache:
    """The process-wide default :class:`SimArtifactCache` -- ONE shared
    instance (unlike `registry.default_artifact_family_registry`, which
    intentionally rebuilds fresh: that registry is immutable config,
    this cache is the mutable content-address store itself, and a
    fresh instance per call would defeat the whole point of caching).
    Tests that need isolation construct their own `SimArtifactCache()`
    instead of calling this."""
    return _DEFAULT_CACHE


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
class VerilatorTraceBinaryArgs(ToolArgs):
    """``verilator --binary --trace ...`` -- the `hdl.sim_assert`
    generic model's traced testbench build (deliverable 7). Defined
    here rather than in `regolith.procio` (out of this ticket's scope,
    T-0068): a plain :class:`~regolith.procio.ToolArgs` subclass may
    live anywhere that imports the base, and `run_verilator`/`run_tool`
    only ever call ``args.emit()`` -- no procio change required."""

    top_module: str
    tb_filename: str
    hdl_filename: str
    mdir: str = "obj_dir"

    # frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
    # frob:tests tests/harness/test_hdl_sim_artifacts.py::test_verilator_trace_binary_args_emit_adds_trace_flag
    def emit(self) -> tuple[str, ...]:
        """`--binary --trace -Wno-fatal --timing -O2 --top-module <m>
        --Mdir <d> ...` -- identical to
        `regolith.procio.VerilatorBinaryArgs` plus `--trace`."""
        return (
            "--binary",
            "--trace",
            "-Wno-fatal",
            "--timing",
            "-O2",
            "--top-module",
            self.top_module,
            "--Mdir",
            self.mdir,
            self.tb_filename,
            self.hdl_filename,
        )


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_trace_dump_statements_names_the_trace_file_and_top
def trace_dump_statements(top: str = "tb") -> str:
    """The `$dumpfile`/`$dumpvars` pair `build_generated_testbench`
    inserts when asked to trace: verilator's `--trace` flag alone only
    enables the tracing INFRASTRUCTURE -- the design still has to call
    these to actually write `trace.vcd` (standard verilator `--binary`
    posture, not a lithos convention)."""
    return f'    $dumpfile("{_TRACE_FILENAME}");\n    $dumpvars(0, {top});\n'


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_read_trace_file_present
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_read_trace_file_absent_is_a_named_reason_not_a_crash
def read_trace_file(work_dir: Path) -> Result[bytes, str]:
    """Read ``work_dir / "trace.vcd"``, or an honest ``Err(reason)`` --
    never a fabricated trace (D264 ruling 2). A missing file after a
    traced run means this verilator invocation's environment did not
    actually emit one (e.g. an old verilator ignoring `--trace` in
    `--binary` mode); the caller records the reason verbatim in
    `sim_report.json` rather than silently shipping no trace with no
    explanation."""
    trace_path = work_dir / _TRACE_FILENAME
    if not trace_path.is_file():
        return Err(
            f"verilator --trace did not produce {_TRACE_FILENAME} in this "
            "tool environment -- named absence, not a fabricated trace"
        )
    return Ok(trace_path.read_bytes())


# frob:doc docs/modules/py-harness.md#models-hdl-sim-artifacts
# frob:tests tests/harness/test_hdl_sim_artifacts.py::test_parse_mismatches_collects_every_assert_fail_line
def parse_mismatches(stdout_text: str) -> tuple[SimMismatch, ...]:
    """Every `ASSERT FAIL` marker line in ``stdout_text`` as a structured
    :class:`SimMismatch` row (the full mismatch table, deliverable 7) --
    the SAME `_FAIL_RE` grammar `models.py` already parses for the
    single first-failure note, just collected in full rather than
    truncated to one."""
    rows: list[SimMismatch] = []
    for line in stdout_text.splitlines():
        m = _FAIL_LINE_RE.match(line)
        if m:
            name, cycle, expected, got = m.groups()
            rows.append(
                SimMismatch(vector=name, cycle=int(cycle), expected=expected, got=got)
            )
    return tuple(rows)


__all__ = [
    "SIM_ARTIFACT_KEY_DOMAIN",
    "SimArtifactCache",
    "SimArtifactFamily",
    "SimMismatch",
    "SimReport",
    "VerilatorTraceBinaryArgs",
    "default_sim_artifact_cache",
    "parse_mismatches",
    "read_trace_file",
    "render_sim_report_json",
    "sim_artifact_cache_key",
    "trace_dump_statements",
]
