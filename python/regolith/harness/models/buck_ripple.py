"""Closed-form buck-converter output-voltage-ripple model (reference pack).

Discharges the corpus claim ``require Regulation: ripple`` in
``examples/tracks/cuprite/buck_converter.cupr`` -- the peak-to-peak output ripple of
a synchronous/CCM buck must stay below a limit. This is the FIRST
closed-form pack and the reference for every later one: signature ->
worst-corner numpy evaluation -> ``Prediction`` -> the shared discharge
rule.

Model (textbook CCM buck, ESR neglected):

    D          = v_out / v_in                      (duty cycle)
    delta_i_L  = v_out * (v_in - v_out) / (v_in * f_sw * L)   (inductor ripple)
    v_ripple   = delta_i_L / (8 * f_sw * C_out)    (capacitor charge ripple)

Corner conservatism (INV-9): ripple grows as f_sw, L, and C_out shrink
and (for fixed v_out) as v_in grows, but rather than hand-prove the
monotonicity the model evaluates ALL 2**k interval corners in numpy and
takes the worst (max) -- sound for any interval box. The ESR term this
neglects is folded into ``eps`` as a conservative relative error.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import numpy as np
from typani.result import Err, Ok, Result

from regolith._schema.models import ConverterGraph
from regolith.harness.converter_topology import BuckTopology, derive_buck_topology
from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "elec.buck.output_voltage_ripple"

# WO-88 (F112): the OPTIONAL converter-graph payload port/kind. Optional,
# not a required `payload_kinds` entry -- a buck design with no behavioral
# `spec:` body (`examples/tracks/cuprite/buck_converter.cupr`) carries no
# graph and still discharges from hand-supplied inputs (the fallback the
# WO keeps). The kind string mirrors `regolith-lower/src/claims.rs`'s
# `CONVERTER_GRAPH_KIND` verbatim (hand-kept in sync, the flownet-kind
# convention). This is the buck FAMILY's shared consumption seam; the
# numeric-tier siblings (`buck_efficiency`/`buck_transient`) adopt it when
# `NumericReducedTierModel` grows a resolver hook (a base-class change out
# of this WO's scope -- recorded, not silently dropped).
GRAPH_PORT = "converter_graph"
GRAPH_KIND = "converter_graph"

# Required inputs (SI base units: V, V, Hz, H, F). Public alias
# (`INPUTS`) so `orchestrator.translate`'s call-form route reads the
# model's own input names, one home (F152, the `fluid_pressure_drop`
# convention).
INPUTS = ("v_in", "v_out", "f_sw", "l", "c_out")
_INPUTS = INPUTS

# Conservative relative error for the neglected ESR / higher-order terms.
_EPS_REL = 0.05


class BuckRippleModel(Model):
    """Closed-form peak-to-peak output ripple of a CCM buck converter."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound ripple claim over the five converter inputs."""
        return ModelSignature(
            name="buck_output_ripple_ccm",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("buck", "ccm", "esr_neglected"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    def _resolve_topology(
        self, request: DischargeRequest, resolver: PayloadResolver | None
    ) -> BuckTopology | None:
        """Derive the buck topology from a carried converter-graph
        payload, or ``None`` when the design supplies none (WO-88).

        Optional and total: a request with no ``converter_graph`` port,
        or one whose payload cannot be resolved, falls back to ``None``
        (the hand-supplied path). A present-and-resolvable graph is read
        into a :class:`BuckTopology` -- the graph-derived provenance that
        replaces the model's hand-supplied CCM-buck assumption.
        """
        ref = request.payloads.get(GRAPH_PORT)
        if ref is None or ref.kind != GRAPH_KIND:
            return None
        if resolver is None:
            _log.debug(
                "%s: converter_graph payload present but no resolver configured; "
                "falling back to hand-supplied topology",
                self.model_id,
            )
            return None
        resolved = resolver(ref.digest)
        if resolved.is_err:
            _log.warning(
                "%s: converter_graph payload %s did not resolve (%s); "
                "falling back to hand-supplied topology",
                self.model_id,
                ref.digest,
                resolved.danger_err.message,
            )
            return None
        graph = ConverterGraph.model_validate_json(resolved.danger_ok)
        return derive_buck_topology(graph)

    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        """Evaluate worst-corner ripple over the interval-boxed inputs.

        WO-88 (F112): when the request carries a resolvable
        ``converter_graph`` payload, the buck topology is CONFIRMED from
        the compiled graph (switch/sense nodes, switching clock) rather
        than assumed -- and a graph that does NOT describe a switching
        converter is an honest out-of-domain result, never a silent pass.
        Absent a graph, the hand-supplied numeric operating point remains
        the fallback (an unchanged pre-WO-88 discharge).
        """
        topology = self._resolve_topology(request, resolver)
        if topology is not None and not topology.is_switching_converter:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "converter graph does not confirm a switching-converter "
                        f"topology: {topology.provenance()}"
                    ),
                )
            )

        v_in = request.inputs["v_in"]
        v_out = request.inputs["v_out"]
        f_sw = request.inputs["f_sw"]
        ind = request.inputs["l"]
        c_out = request.inputs["c_out"]

        # Domain: a buck steps DOWN, so v_out must be below the whole v_in
        # range, and every reactive value must be strictly positive.
        if v_out.hi >= v_in.lo:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"not a buck operating point: v_out.hi={v_out.hi} "
                        f">= v_in.lo={v_in.lo}"
                    ),
                )
            )
        if min(f_sw.lo, ind.lo, c_out.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="f_sw, L, and C_out must be strictly positive",
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (v_in, v_out, f_sw, ind, c_out)
        ]
        worst = 0.0
        for vin, vout, fsw, lh, cout in itertools.product(*axes):
            delta_i_l = vout * (vin - vout) / (vin * fsw * lh)
            v_ripple = delta_i_l / (8.0 * fsw * cout)
            worst = max(worst, float(v_ripple))

        eps = _EPS_REL * worst
        if topology is not None:
            _log.debug(
                "%s: topology confirmed from compiled graph -- %s",
                self.model_id,
                topology.provenance(),
            )
        else:
            _log.debug(
                "%s: no converter graph supplied; topology is the hand-supplied "
                "CCM-buck assumption (signature domain=%s)",
                self.model_id,
                self.signature.domain,
            )
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
