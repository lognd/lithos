"""Layout adapter `realizer.elec.kicad`: KiCad as a subprocess pack (AD-19).

Design: mirrors `regolith.harness.adapter`'s wire discipline (WO-20/
design doc D-C) instead of reimplementing it -- a wrapper executable
(``argv``) owns translating the neutral netlist + board outline into
KiCad's native invocation (kicad-cli placement/routing/DRC, or the
pcbnew python API), reads ONE ``LayoutResponse`` JSON document off its
stdout, and every infrastructure failure (spawn/timeout/malformed
response) is a value, never an exception. stderr is logs.

ENVIRONMENT NOTE (updated cycle 26; the original sandbox cut is
LIFTED): `kicad-cli` 10.0.4 is on PATH, and `make install` links the
system KiCad's `pcbnew` module into the venv (`make kicad-link`, a
graceful no-op when KiCad is absent), so `real_kicad_available()`
reports OPEN on a full install and the `-m kicad` test tier runs
REAL. The fake-subprocess tier remains for KiCad-less environments
(the same dependency-injection point WO-20's own adapter tests use).
Upstream caution for the WO-24 remainder: KiCad deprecates the SWIG
`pcbnew` API in favor of the IPC API/kicad-cli -- prefer `kicad-cli`
where it can do the job.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typani.result import Err, Ok, Result

from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.registry import ModelRegistry
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger
from regolith.procio import KicadLayoutArgs, legacy_bytes_runner
from regolith.realizer.elec.errors import (
    LayoutFailed,
    LayoutImportError,
    ToolUnavailable,
)
from regolith.toolenv import resolve as resolve_tool

_log = get_logger(__name__)

# frob:doc docs/modules/py-realizer.md#elec-kicad
KICAD_CLI_TOOL = "kicad-cli"

# The single claim kind the layout DRC discharges (AD-19 pack shape).
# frob:doc docs/modules/py-realizer.md#elec-kicad
CLAIM_KIND_DRC_CLEAN = "elec.layout.drc_clean"
# The one required input port: a caller resolves the DRC blocking-
# violation count before building the DischargeRequest.
# frob:doc docs/modules/py-realizer.md#elec-kicad
VIOLATION_COUNT = "violation_count"


# frob:doc docs/modules/py-realizer.md#elec-kicad
class DrcViolation(BaseModel):
    """One DRC finding: the rule it cites and its severity."""

    model_config = ConfigDict(frozen=True)

    rule: str
    severity: str  # "error" | "warning"
    message: str = ""


# frob:doc docs/modules/py-realizer.md#elec-kicad
class DrcReport(BaseModel):
    """The DRC pass's total result: clean iff no `error`-severity finding."""

    model_config = ConfigDict(frozen=True)

    violations: tuple[DrcViolation, ...] = ()

    # frob:doc docs/modules/py-realizer.md#elec-kicad
    @property
    def clean(self) -> bool:
        """No `error`-severity violation (warnings do not block DRC-clean)."""
        return not any(v.severity == "error" for v in self.violations)

    # frob:doc docs/modules/py-realizer.md#elec-kicad
    @property
    def error_count(self) -> int:
        """The number of blocking (`error`-severity) violations."""
        return sum(1 for v in self.violations if v.severity == "error")


# frob:doc docs/modules/py-realizer.md#elec-kicad
class LayoutResponse(BaseModel):
    """The ONE wire document the layout wrapper writes to stdout.

    ``status`` is honest: ``routed`` (placement+routing succeeded, DRC
    ran), ``unrouted`` (the autorouter could not complete -- WO-24:
    "autorouting quality is NOT promised", this is indeterminate, never
    a failure the caller must treat as a crash).
    """

    model_config = ConfigDict(frozen=True)

    status: str  # "routed" | "unrouted"
    pcb_path: str = ""
    pcb_sha256: str = ""
    drc: DrcReport = Field(default_factory=DrcReport)


# frob:doc docs/modules/py-realizer.md#elec-kicad
class LayoutRequest(BaseModel):
    """The inputs one layout invocation needs: netlist + board outline.

    ``outline_w_mm``/``outline_d_mm`` are the design's real rectangular
    board-outline geometry (WO-103: the same dimensions the fake tier
    already draws, threaded here so the REAL wrapper draws them too --
    this is the ONE outline shape the spec carries today, a rect
    w/d; a richer outline language is not invented, see
    `kicad_wrapper.py`'s module docstring). Required (no placeholder
    default): every caller names a real board size.
    """

    model_config = ConfigDict(frozen=True)

    netlist_path: str
    board_outline_path: str
    output_pcb_path: str
    outline_w_mm: float = Field(gt=0.0)
    outline_d_mm: float = Field(gt=0.0)
    board_name: str = Field(
        default="",
        description="Board identity text for the silkscreen block (WO-124, "
        "charter 41 sec. 3); empty is a legitimate 'not supplied' -- no "
        "identity text is drawn.",
    )
    design_hash: str = Field(
        default="",
        description="Design short-hash for the silkscreen identity block "
        "(WO-124); empty is a legitimate 'not supplied'.",
    )


# frob:doc docs/modules/py-realizer.md#elec-kicad
class LayoutArtifact(BaseModel):
    """A content-addressed, lockfile-pinnable layout result (INV-22)."""

    model_config = ConfigDict(frozen=True)

    pcb_path: str
    content_hash: str  # "sha256:<hex>"
    drc: DrcReport


# frob:doc docs/modules/py-realizer.md#elec-kicad
def discover_kicad_cli(
    which_fn: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """Locate the `kicad-cli` executable, or ``None`` if unavailable.

    Resolved through `regolith.toolenv` (the ONE tool registry) so the
    install-guidance text a required-tool caller shows stays in sync
    with this discovery -- ``which_fn`` stays injectable for tests
    (bypasses the registry's cache, always a fresh probe).
    """
    status = resolve_tool(
        "kicad-cli", which_fn=which_fn, probe_version=False, use_cache=False
    )
    if status.path is None:
        _log.warning(
            "kicad-cli not found on PATH (layout adapter cut, see module docstring)"
        )
    return status.path


# frob:doc docs/modules/py-realizer.md#elec-kicad
def pcbnew_importable() -> bool:
    """Whether the `pcbnew` python module can be imported (WO-35 deliverable 5).

    A plain ``try/import`` probe, same discipline as
    `regolith.realizer.elec.extraction`'s documented check: never
    faked, logged either way.
    """
    # Dynamic import: pcbnew is system-KiCad-shipped (make kicad-link),
    # so a static import is unresolvable in KiCad-less environments and
    # resolvable in linked ones -- importlib keeps ty happy in both.
    import importlib

    try:
        importlib.import_module("pcbnew")
    except ImportError:
        _log.debug("pcbnew not importable")
        return False
    return True


# frob:doc docs/modules/py-realizer.md#elec-kicad
def real_kicad_available(
    which_fn: Callable[[str], str | None] = shutil.which,
) -> bool:
    """The real-KiCad gate (WO-35 deliverable 5): both tools present.

    Both `kicad-cli` on PATH AND `pcbnew` importable are required
    before the placement/route/DRC step is allowed to run REAL; either
    one missing means the fake-subprocess tier is the only tier that
    can run (the honest cut WO-24 recorded, retired here behind this
    single gate function so a caller never re-derives the check).
    """
    available = discover_kicad_cli(which_fn) is not None and pcbnew_importable()
    _log.info("real KiCad gate: %s", "OPEN" if available else "closed")
    return available


# frob:doc docs/modules/py-realizer.md#elec-kicad
def real_wrapper_argv() -> tuple[str, ...]:
    """The `argv` for the real KiCad wrapper (`kicad_wrapper.py`).

    Runs as ``python -m regolith.realizer.elec.kicad_wrapper`` under the
    SAME interpreter (so it shares this process's linked `pcbnew`,
    `make kicad-link`'s venv seam) -- never a separately-discovered
    `python3`, which could resolve to an interpreter without the link.
    """
    return (sys.executable, *KicadLayoutArgs().emit())


# frob:doc docs/modules/py-realizer.md#elec-kicad
def run_layout(
    argv: tuple[str, ...],
    request: LayoutRequest,
    *,
    timeout_s: float = 120.0,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = legacy_bytes_runner,
) -> Result[LayoutResponse, ToolUnavailable | LayoutFailed]:
    """Run one wire exchange with the layout wrapper executable.

    Same shape as `regolith.harness.adapter.solve_via_subprocess`: the
    request is JSON on stdin, one `LayoutResponse` JSON document is
    expected on stdout, stderr is bridged to logging. A missing/
    unspawnable tool is :class:`ToolUnavailable`; a malformed response
    or a nonzero exit that is not a documented DRC-fail exit is
    :class:`LayoutFailed`.
    """
    payload = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    try:
        completed = runner(
            list(argv),
            input=payload.encode("ascii"),
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        _log.warning("layout tool %s not found: %s", argv, exc)
        return Err(ToolUnavailable(tool=argv[0] if argv else "", message=str(exc)))
    except OSError as exc:
        _log.warning("layout tool %s failed to spawn: %s", argv, exc)
        return Err(ToolUnavailable(tool=argv[0] if argv else "", message=str(exc)))
    except subprocess.TimeoutExpired:
        _log.warning("layout tool %s timed out after %gs", argv, timeout_s)
        return Err(
            LayoutFailed(stage="routing", message=f"timed out after {timeout_s}s")
        )

    for line in completed.stderr.decode("ascii", errors="replace").splitlines():
        if line:
            _log.info("layout %s: %s", argv[0] if argv else "?", line)

    if completed.returncode != 0:
        _log.warning("layout tool %s exited nonzero (%d)", argv, completed.returncode)
        return Err(
            LayoutFailed(
                stage="placement",
                message=f"exit {completed.returncode}: infrastructure failure "
                "(exit 0 covers all computed outcomes, including unrouted)",
            )
        )
    try:
        response = LayoutResponse.model_validate_json(completed.stdout)
    except ValidationError as exc:
        _log.warning("layout tool %s stdout is not a LayoutResponse: %s", argv, exc)
        return Err(LayoutFailed(stage="drc", message=f"malformed response: {exc}"))
    _log.info("layout tool %s: status=%s", argv[0] if argv else "?", response.status)
    return Ok(response)


# frob:doc docs/modules/py-realizer.md#elec-kicad
def run_real_layout(
    request: LayoutRequest,
    *,
    timeout_s: float = 120.0,
) -> Result[LayoutResponse, ToolUnavailable | LayoutFailed]:
    """`run_layout` against the real wrapper (`real_wrapper_argv`).

    The WO-24 close-out entry point: on a host where
    `real_kicad_available()` is OPEN (this repo's `-m kicad` gate), this
    drives real `pcbnew`/`kicad-cli` through `kicad_wrapper.py` -- the
    same `run_layout` wire discipline the fake-subprocess unit tests
    exercise, with a real `argv` in place of an injected fake runner.
    """
    return run_layout(real_wrapper_argv(), request, timeout_s=timeout_s)


# frob:doc docs/modules/py-realizer.md#elec-kicad
# frob:invariant INV-022
def hash_pcb_file(path: Path) -> str:
    """Content-address a `.kicad_pcb` file (INV-22 hash pin)."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


# frob:doc docs/modules/py-realizer.md#elec-kicad
# frob:waive TEST001 reason="WO-24 hand-edited-layout re-entry has no caller or fixture in this checkout; no synthetic hand-edited .kicad_pcb would honestly exercise the re-entry contract"
# frob:waive TEST005 reason="measured 11.1% branch on 2026-07-19; backfill T-0036"
def import_pinned_layout(path: Path) -> Result[LayoutArtifact, LayoutImportError]:
    """Re-enter a hand-edited layout as a pinned, verify-only artifact.

    WO-24: "a hand-edited layout re-enters as pinned import (regolith/08
    verify-only L4)" -- no DRC re-run is implied here, only the hash
    pin; a caller wanting fresh DRC evidence runs the layout pack's DRC
    stage separately against the imported file.
    """
    if not path.is_file():
        return Err(LayoutImportError(path=str(path), message="file does not exist"))
    try:
        content_hash = hash_pcb_file(path)
    except OSError as exc:
        return Err(LayoutImportError(path=str(path), message=str(exc)))
    _log.info("imported pinned layout %s (%s)", path, content_hash)
    return Ok(
        LayoutArtifact(pcb_path=str(path), content_hash=content_hash, drc=DrcReport())
    )


# frob:doc docs/modules/py-realizer.md#elec-kicad
def elec_layout_kicad_drc(violation_count: float) -> bool:
    """T-0053: a real, importable callable resolving the same predicate
    `LayoutDrcModel.estimate` already encodes (DRC-clean iff the
    blocking-violation count is under the 0.5 limit, i.e. < 1) --
    exposed at module scope so `RealizerCapability.dfm_checks`'s id
    (``"regolith.realizer.elec.kicad:elec_layout_kicad_drc"``, named
    after `LayoutDrcModel.signature.name`) resolves to something real
    instead of a bare `ModelSignature` name string. No behavior change
    to `LayoutDrcModel` itself -- this is a descriptive mirror, not a
    new gate."""
    return violation_count < 1


# frob:doc docs/modules/py-realizer.md#elec-kicad
class LayoutDrcModel(Model):
    """Discharges `elec.layout.drc_clean` from an already-run DRC report.

    Deliberately narrow (AD-19 pack shape, harness-side half): the
    subprocess invocation (:func:`run_layout`) is orchestrator territory
    because it needs filesystem paths a `DischargeRequest`'s numeric
    `inputs` cannot carry; this model consumes the RESOLVED violation
    count the same way `ConformanceRefinementModel` consumes a resolved
    bound. A route failure (``status="unrouted"``) is never fed to this
    model at all -- the caller reports honest indeterminate directly,
    matching the registry's own no-model-match path.
    """

    # frob:doc docs/modules/py-realizer.md#elec-kicad
    @property
    def signature(self) -> ModelSignature:
        """One required input: the DRC pass's blocking-violation count."""
        return ModelSignature(
            name="elec_layout_kicad_drc",
            claim_kind=CLAIM_KIND_DRC_CLEAN,
            sense=ClaimSense.upper_bound(),
            inputs=(VIOLATION_COUNT,),
            domain=("kicad", "layout", "drc"),
        )

    # frob:doc docs/modules/py-realizer.md#elec-kicad
    @property
    def version(self) -> str:
        """Model version (bump on any DRC-mapping rule change; INV-1)."""
        return "1"

    # frob:doc docs/modules/py-realizer.md#elec-kicad
    @property
    def cost(self) -> int:
        """Post-route evidence is the expensive tier (real board data)."""
        return 10

    # frob:doc docs/modules/py-realizer.md#elec-kicad
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """DRC-clean iff the blocking-violation count is < 1 (limit=0.5)."""
        count = request.inputs[VIOLATION_COUNT]
        lo, hi = count.corners()
        return Ok(Prediction(value=hi, eps=0.0, coverage=1.0, in_domain=True))


# frob:doc docs/modules/py-realizer.md#elec-kicad
# frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
def register(registry: ModelRegistry) -> None:
    """Register the layout DRC model (AD-19 pack entry point shape).

    Matches `python/regolith/harness/models/__init__.py::register_all`'s
    `register(model)` protocol; kept here (not a separate `packs/`
    distribution) since the realizer ships in-tree per WO-24's
    `Language:` header.
    """
    registry.register(LayoutDrcModel())
