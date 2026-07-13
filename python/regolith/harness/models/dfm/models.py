"""The `mfg.manufacturable` Model (WO-110 headline; F130 census item 4).

Discharges the corpus's 40-row `makeable: manufacturable(<process>)`
claim family: the realized part, its FeatureProgram-derived features,
and the build's declared `[[machine]]`/`[[tool]]` records (the SAME
records the `std.cam` pack consumes -- `plan_staging`'s loader, one
home) ground the two envelope checks in `checks.py` (stock/travel fit,
tool fit/reach). The claim is an upper bound over the combined excess:
``value = max(check excesses) <= 0`` -- exactly the cam family's
outcome-to-margin mapping, so a genuine misfit is a VIOLATED verdict
with the worst feature named, never a silent fail.

v1 grounds the MILL process family only (the only family the existing
record vocabulary can ground; `orchestrator/dfm_staging.py` names the
deferral every other family takes, and the WO close-out routes their
remainder). The process family arrives as a required REGIME tag
(`mill`), the cam-dialect precedent (D97), so future families compete
as separate model instances rather than widening this one.

Payload ports (all kind `"table"`, the std.cost/std.cam staged-doc
kind): `dfm_part` (a `DfmPart`), `dfm_machine` (a `MachineRecord`,
verbatim the cam shape), `dfm_tools` (a `DfmToolSet`). All three are
REQUIRED: translate defers naming whichever is missing before a
request is ever formed, so a matched request always carries them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.models.cam.models import _resolve_model
from regolith.harness.models.cam.records import MachineRecord
from regolith.harness.models.dfm.checks import check_stock_fit, check_tool_fit
from regolith.harness.models.dfm.records import MILL_FAMILY, DfmPart, DfmToolSet
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# The registry key this model discharges. One home for the string.
CLAIM_KIND = "mfg.manufacturable"

PART_PORT = "dfm_part"
MACHINE_PORT = "dfm_machine"
TOOLS_PORT = "dfm_tools"
TABLE_KIND = "table"


class ManufacturableModel(Model):
    """Realized-part manufacturability vs declared machine/tool records."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound excess claim over the three staged DFM payloads."""
        return ModelSignature(
            name=f"mfg_manufacturable_{MILL_FAMILY}",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("dfm", "envelope", MILL_FAMILY),
            payload_kinds={
                PART_PORT: TABLE_KIND,
                MACHINE_PORT: TABLE_KIND,
                TOOLS_PORT: TABLE_KIND,
            },
            required_regimes=(MILL_FAMILY,),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any check-arithmetic change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form containment arithmetic: the cheapest tier."""
        return 1

    @property
    def citation(self) -> str | None:
        """Declared-record containment checks; capability values cite
        their own [[machine]]/[[tool]] record `source` fields."""
        return (
            "declared [[machine]]/[[tool]] record envelope comparison "
            "(charter 39 sec. 4 pad-check; record source fields carry "
            "the per-value citations)"
        )

    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        """Run stock-fit + tool-fit over the staged records; worst excess."""
        resolved_parts: list[object] = []
        for port, cls in (
            (PART_PORT, DfmPart),
            (MACHINE_PORT, MachineRecord),
            (TOOLS_PORT, DfmToolSet),
        ):
            ref = request.payloads.get(port)
            if ref is None:  # pragma: no cover -- signature match guarantees it
                return Err(
                    DomainError(model_id=self.model_id, message=f"no {port!r} payload")
                )
            record = _resolve_model(resolver, ref.digest, cls, model_id=self.model_id)
            if record.is_err:
                return Err(record.danger_err)
            resolved_parts.append(record.danger_ok)
        part, machine, toolset = resolved_parts
        assert isinstance(part, DfmPart)
        assert isinstance(machine, MachineRecord)
        assert isinstance(toolset, DfmToolSet)

        stock = check_stock_fit(part.bbox_mm, machine.travel)
        tool = check_tool_fit(part.features, toolset.tools)
        _log.debug(
            "%s: part=%s stock(%s) tool(%s)",
            self.model_id,
            part.part_name,
            stock.note,
            tool.note,
        )
        for outcome in (stock, tool):
            if outcome.indeterminate:
                return Err(DomainError(model_id=self.model_id, message=outcome.note))
        excess = max(stock.excess, tool.excess)
        return Ok(Prediction(value=excess, eps=0.0, coverage=1.0, in_domain=True))


__all__ = [
    "CLAIM_KIND",
    "MACHINE_PORT",
    "PART_PORT",
    "TABLE_KIND",
    "TOOLS_PORT",
    "ManufacturableModel",
]
# NOTE (WO-110): `CLAIM_KIND`/port constants are imported by
# `orchestrator/translate.py` (the `_translate_manufacturable` route)
# -- one home for the strings, the cam/hdl models' own convention.
