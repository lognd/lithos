"""The std.cam `Model` pack (WO-67 deliverables 2-6; AD-19/AD-35).

Five ordinary `regolith.harness.model.Model`s, one per check-mode claim
kind (`cam.parse`/`cam.envelope`/`cam.collision_coarse`/`cam.removal`/
`cam.coverage`), all sharing the ONE discharge/margin path
(`Model.discharge`): each maps its `CamOutcome` (checks.py) onto
`value=excess, eps, limit=0.0` (upper-bound sense -- "excess stays at
or below zero"), and an indeterminate outcome short-circuits to
`Err(DomainError)` so the registry renders it as indeterminate evidence
rather than a false pass (conservative-or-silent, charter D3).

Payload ports (D96, all kind `"plan"`/`"table"` per the feldspar 09
sec. 4 vocabulary -- `table` is the SAME kind `std.cost`'s staged docs
already use, cost_common.COST_INPUTS_KIND):

- `plan` (kind `plan`): the raw G-code bytes, hash-pinned via the
  extern/format seam (see this WO's ledger note on what plumbing
  landed vs. was cut).
- `cam_machine` (kind `table`): a serialized `MachineRecord`.
- `cam_tooling` (kind `table`, OPTIONAL): a serialized `ToolRecord`
  (absent = stickout reach not accounted for; envelope still checks
  X/Y/Z travel).
- `cam_target` (kind `table`): a serialized `StockTarget` (removal/
  coverage only).

`cam.parse`/`cam.envelope`/`cam.collision_coarse` need only `plan` (+
`cam_machine` for the latter two); `cam.removal`/`cam.coverage` also
need `cam_target`. The dialect is carried as a required REGIME tag
(`gcode_fanuc`/`gcode_marlin`, D97) so the two dialects compete as
separate model instances the same way the two conformance-sense
models do (`ConformanceRefinementModel`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.models.cam.checks import (
    CamOutcome,
    check_collision_coarse,
    check_coverage,
    check_envelope,
    check_removal,
)
from regolith.harness.models.cam.ir import Dialect, Toolpath, parse_plan
from regolith.harness.models.cam.records import MachineRecord, StockTarget, ToolRecord
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# frob:doc docs/modules/py-harness.md#models-cam
PLAN_PORT = "plan"
# frob:doc docs/modules/py-harness.md#models-cam
PLAN_KIND = "plan"
# frob:doc docs/modules/py-harness.md#models-cam
MACHINE_PORT = "cam_machine"
# frob:doc docs/modules/py-harness.md#models-cam
TOOLING_PORT = "cam_tooling"
# frob:doc docs/modules/py-harness.md#models-cam
TARGET_PORT = "cam_target"
# frob:doc docs/modules/py-harness.md#models-cam
TABLE_KIND = "table"

# frob:doc docs/modules/py-harness.md#models-cam
CLAIM_PARSE = "cam.parse"
# frob:doc docs/modules/py-harness.md#models-cam
CLAIM_ENVELOPE = "cam.envelope"
# frob:doc docs/modules/py-harness.md#models-cam
CLAIM_COLLISION = "cam.collision_coarse"
# frob:doc docs/modules/py-harness.md#models-cam
CLAIM_REMOVAL = "cam.removal"
# frob:doc docs/modules/py-harness.md#models-cam
CLAIM_COVERAGE = "cam.coverage"


def _resolve_bytes(
    resolver: PayloadResolver | None, digest: str, *, model_id: str
) -> Result[bytes, HarnessError]:
    if resolver is None:
        return Err(
            DomainError(
                model_id=model_id, message="no payload store resolver configured"
            )
        )
    resolved = resolver(digest)
    if resolved.is_err:
        return Err(
            DomainError(
                model_id=model_id,
                message=(
                    f"payload {digest} did not resolve: {resolved.danger_err.message}"
                ),
            )
        )
    return Ok(resolved.danger_ok)


def _resolve_model[RecordT: BaseModel](
    resolver: PayloadResolver | None,
    digest: str,
    cls: type[RecordT],
    *,
    model_id: str,
) -> Result[RecordT, HarnessError]:
    raw = _resolve_bytes(resolver, digest, model_id=model_id)
    if raw.is_err:
        return Err(raw.danger_err)
    try:
        return Ok(cls.model_validate_json(raw.danger_ok))
    except ValidationError as exc:
        return Err(
            DomainError(model_id=model_id, message=f"malformed {cls.__name__}: {exc}")
        )


def _outcome_to_prediction(
    outcome: CamOutcome, *, model_id: str
) -> Result[Prediction, HarnessError]:
    if outcome.indeterminate:
        return Err(DomainError(model_id=model_id, message=outcome.note))
    return Ok(Prediction(value=outcome.excess, eps=outcome.eps, coverage=1.0))


class _CamModel(Model):
    """Shared spine: resolve the plan (+ records), run one check function."""

    _name: str
    _claim_kind: str
    _dialect: Dialect

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def signature(self) -> ModelSignature:
        raise NotImplementedError

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def version(self) -> str:
        """Model version (bump on any check-arithmetic change; INV-1)."""
        return "1"

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def cost(self) -> int:
        """cam.parse is cheapest; downstream checks cost more (cheapest-first)."""
        return 1

    # frob:doc docs/modules/py-harness.md#models-cam
    # frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        raise NotImplementedError


# frob:doc docs/modules/py-harness.md#models-cam
class CamParseModel(_CamModel):
    """`cam.parse`: the plan parses cleanly under its declared dialect."""

    def __init__(self, dialect: Dialect) -> None:
        self._dialect = dialect
        self._name = f"cam_parse_{dialect.value}"

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=self._name,
            claim_kind=CLAIM_PARSE,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("cam", "parse", self._dialect.value),
            payload_kinds={PLAN_PORT: PLAN_KIND},
            required_regimes=(self._dialect.value,),
        )

    # frob:doc docs/modules/py-harness.md#models-cam
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        ref = request.payloads.get(PLAN_PORT)
        if ref is None:  # pragma: no cover -- signature match guarantees it
            return Err(DomainError(model_id=self.model_id, message="no plan payload"))
        raw = _resolve_bytes(resolver, ref.digest, model_id=self.model_id)
        if raw.is_err:
            return Err(raw.danger_err)
        toolpath = parse_plan(raw.danger_ok, self._dialect)
        _log.debug(
            "%s: moves=%d issues=%d",
            self.model_id,
            len(toolpath.moves),
            len(toolpath.issues),
        )
        if not toolpath.ok:
            from regolith.harness.models.cam.ir import line_citations

            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"plan did not parse: {line_citations(toolpath.issues)}",
                )
            )
        return Ok(Prediction(value=0.0, eps=0.0, coverage=1.0))


class _CamCheckModel(_CamModel):
    """Shared spine for the four post-parse checks (envelope/collision/
    removal/coverage): parse, resolve records, run the check function."""

    def __init__(self, dialect: Dialect) -> None:
        self._dialect = dialect
        self._name = f"{self._claim_kind.replace('.', '_')}_{dialect.value}"

    @property
    # frob:doc docs/modules/py-harness.md#models-cam
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name=self._name,
            claim_kind=self._claim_kind,
            sense=ClaimSense.upper_bound(),
            inputs=self._scalar_inputs(),
            domain=("cam", self._claim_kind.split(".", 1)[1], self._dialect.value),
            payload_kinds=self._payload_kinds(),
            required_regimes=(self._dialect.value,),
        )

    def _scalar_inputs(self) -> tuple[str, ...]:
        return ()

    def _payload_kinds(self) -> dict[str, str]:
        raise NotImplementedError

    def _parse(
        self, request: DischargeRequest, resolver: PayloadResolver | None
    ) -> Result[Toolpath, HarnessError]:
        ref = request.payloads.get(PLAN_PORT)
        if ref is None:  # pragma: no cover -- signature match guarantees it
            return Err(DomainError(model_id=self.model_id, message="no plan payload"))
        raw = _resolve_bytes(resolver, ref.digest, model_id=self.model_id)
        if raw.is_err:
            return Err(raw.danger_err)
        return Ok(parse_plan(raw.danger_ok, self._dialect))

    def _record[RecordT: BaseModel](
        self,
        request: DischargeRequest,
        port: str,
        cls: type[RecordT],
        resolver: PayloadResolver | None,
    ) -> Result[RecordT, HarnessError]:
        """Resolve a REQUIRED payload record (a missing port is `Err`)."""
        ref = request.payloads.get(port)
        if ref is None:  # pragma: no cover -- signature match guarantees it
            return Err(
                DomainError(model_id=self.model_id, message=f"no {port!r} payload")
            )
        return _resolve_model(resolver, ref.digest, cls, model_id=self.model_id)

    def _optional_record[RecordT: BaseModel](
        self,
        request: DischargeRequest,
        port: str,
        cls: type[RecordT],
        resolver: PayloadResolver | None,
    ) -> Result[RecordT | None, HarnessError]:
        """Resolve an OPTIONAL payload record (absence is `Ok(None)`)."""
        ref = request.payloads.get(port)
        if ref is None:
            none_result: Result[RecordT | None, HarnessError] = Ok(None)
            return none_result
        resolved = _resolve_model(resolver, ref.digest, cls, model_id=self.model_id)
        if resolved.is_err:
            return Err(resolved.danger_err)
        ok_result: Result[RecordT | None, HarnessError] = Ok(resolved.danger_ok)
        return ok_result


# frob:doc docs/modules/py-harness.md#models-cam
class CamEnvelopeModel(_CamCheckModel):
    """`cam.envelope`: commanded positions + tool stickout vs travel."""

    _claim_kind = CLAIM_ENVELOPE

    def _payload_kinds(self) -> dict[str, str]:
        return {PLAN_PORT: PLAN_KIND, MACHINE_PORT: TABLE_KIND}

    # frob:doc docs/modules/py-harness.md#models-cam
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        toolpath = self._parse(request, resolver)
        if toolpath.is_err:
            return Err(toolpath.danger_err)
        machine = self._record(request, MACHINE_PORT, MachineRecord, resolver)
        if machine.is_err:
            return Err(machine.danger_err)
        tool = self._optional_record(request, TOOLING_PORT, ToolRecord, resolver)
        if tool.is_err:
            return Err(tool.danger_err)
        outcome = check_envelope(toolpath.danger_ok, machine.danger_ok, tool.danger_ok)
        _log.debug("%s: %s", self.model_id, outcome.note)
        return _outcome_to_prediction(outcome, model_id=self.model_id)


# frob:doc docs/modules/py-harness.md#models-cam
class CamCollisionCoarseModel(_CamCheckModel):
    """`cam.collision_coarse`: rapids vs uncut-stock AABB clearance."""

    _claim_kind = CLAIM_COLLISION

    def _payload_kinds(self) -> dict[str, str]:
        return {PLAN_PORT: PLAN_KIND, TARGET_PORT: TABLE_KIND}

    # frob:doc docs/modules/py-harness.md#models-cam
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        toolpath = self._parse(request, resolver)
        if toolpath.is_err:
            return Err(toolpath.danger_err)
        target = self._record(request, TARGET_PORT, StockTarget, resolver)
        if target.is_err:
            return Err(target.danger_err)
        outcome = check_collision_coarse(toolpath.danger_ok, target.danger_ok.stock)
        _log.debug("%s: %s", self.model_id, outcome.note)
        return _outcome_to_prediction(outcome, model_id=self.model_id)


# frob:doc docs/modules/py-harness.md#models-cam
class CamRemovalModel(_CamCheckModel):
    """`cam.removal`: conservative voxel stock-removal vs target envelope.

    ``resolution_mm`` is a required scalar input (the declared voxel
    error term, margin-driven per charter D3): the caller states the
    tier it is willing to pay for, and a thin margin at that tier stays
    indeterminate rather than an optimistic pass.
    """

    _claim_kind = CLAIM_REMOVAL

    def _scalar_inputs(self) -> tuple[str, ...]:
        return ("resolution_mm",)

    def _payload_kinds(self) -> dict[str, str]:
        return {PLAN_PORT: PLAN_KIND, TARGET_PORT: TABLE_KIND}

    # frob:doc docs/modules/py-harness.md#models-cam
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        toolpath = self._parse(request, resolver)
        if toolpath.is_err:
            return Err(toolpath.danger_err)
        target = self._record(request, TARGET_PORT, StockTarget, resolver)
        if target.is_err:
            return Err(target.danger_err)
        resolution_mm = request.inputs["resolution_mm"].hi
        outcome = check_removal(toolpath.danger_ok, target.danger_ok, resolution_mm)
        _log.debug("%s: %s", self.model_id, outcome.note)
        return _outcome_to_prediction(outcome, model_id=self.model_id)


# frob:doc docs/modules/py-harness.md#models-cam
class CamCoverageModel(_CamCheckModel):
    """`cam.coverage`: every FeatureProgram-declared feature is touched."""

    _claim_kind = CLAIM_COVERAGE

    def _payload_kinds(self) -> dict[str, str]:
        return {PLAN_PORT: PLAN_KIND, TARGET_PORT: TABLE_KIND}

    # frob:doc docs/modules/py-harness.md#models-cam
    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        toolpath = self._parse(request, resolver)
        if toolpath.is_err:
            return Err(toolpath.danger_err)
        target = self._record(request, TARGET_PORT, StockTarget, resolver)
        if target.is_err:
            return Err(target.danger_err)
        outcome = check_coverage(toolpath.danger_ok, target.danger_ok)
        _log.debug("%s: %s", self.model_id, outcome.note)
        return _outcome_to_prediction(outcome, model_id=self.model_id)
