"""The ``geometry_realizable`` model pack (AD-19): realized vs. predicted.

WO-22 deliverable 4 (post-geometry verification), wired through the
SAME harness ``Model``/``DischargeRequest``/registry path every other
verification model uses (NO DUPLICATION -- the shared margin rule in
``regolith.harness.evidence`` is the ONE discharge implementation).

Integration seam (recorded honestly -- see the WO file's cuts section):
a real obligation for this claim kind would need the orchestrator to
thread a per-part ``FeatureProgram`` reference through
``DischargeRequest`` the way every other model's scalar inputs are
threaded (``regolith.orchestrator.translate``). That wiring does not
exist yet because `regolith-lower` does not emit `geometry_realizable`
obligations at all (no feature-program producer, per
``regolith.realizer.mech.schema``'s module docstring). Until then, this
model is exercised by calling :func:`register_realized_geometry`
directly (see ``tests/realizer/mech/test_model.py``) with a realized
geometry produced by :mod:`regolith.realizer.mech.interpreter`, then
discharging a ``DischargeRequest`` carrying the SAME content hash in
``settings_digest`` and the static core's predicted measures as point
intervals in ``inputs`` -- exactly the shape a future
``translate.py`` route would build.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.realizer.mech.interpreter import RealizedGeometryArtifact

# The registry key this pack discharges (AD-19; one home for the string).
CLAIM_KIND = "geometry_realizable"

# Required inputs: the static core's predicted measures, SI (m / m^3),
# as point intervals (INV-9 corner discipline degenerates to a point
# here -- the prediction is a single number, not a tolerance band).
_INPUTS = ("volume_m3", "bbox_x_m", "bbox_y_m", "bbox_z_m")

# Content-addressed cache of realized geometry, keyed by the realized
# ``FeatureProgram``'s content hash (threaded via ``settings_digest``).
# A process-local dict is the honest MVP seam until an orchestrator-side
# evidence cache (WO-20 precedent) owns this; realized geometry itself
# is already cheap to recompute deterministically from the same program.
_REALIZED: dict[str, RealizedGeometryArtifact] = {}


def register_realized_geometry(realized: RealizedGeometryArtifact) -> None:
    """Make ``realized`` available to :class:`GeometryRealizableModel`.

    Keyed by ``realized.geometry.feature_program_hash`` -- the caller's
    ``DischargeRequest.settings_digest`` must carry the same hash.
    """
    _REALIZED[realized.geometry.feature_program_hash] = realized


def clear_realized_geometry_cache() -> None:
    """Drop every cached realization (test isolation)."""
    _REALIZED.clear()


def _relative_error(actual: float, predicted: float) -> float:
    """``|actual - predicted| / max(|predicted|, 1e-12)`` -- a scale-free margin."""
    return abs(actual - predicted) / max(abs(predicted), 1e-12)


class GeometryRealizableModel(Model):
    """Compares a realized solid's measures to the static-core prediction."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound claim: worst relative error must stay under eps_rel."""
        return ModelSignature(
            name="mech_geometry_realized_measures",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("hematite", "mech", "geometry"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any change to the comparison rule)."""
        return "1"

    @property
    def cost(self) -> int:
        """Cheapest tier: pure comparison, no solve (realization already ran)."""
        return 0

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Worst relative error of {volume, bbox_x/y/z} vs. the realized solid.

        No cached realization for ``request.settings_digest`` is an
        honest out-of-domain deferral (INDETERMINATE, never a fabricated
        pass) -- e.g. the part uses an op outside the v1 feature set and
        was never realized.
        """
        realized = _REALIZED.get(request.settings_digest)
        if realized is None:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "no realized geometry cached for settings_digest "
                        f"{request.settings_digest!r}"
                    ),
                )
            )
        topo = realized.geometry.topology
        actual = {
            "volume_m3": topo.volume_mm3 / 1_000_000_000.0,
            "bbox_x_m": (topo.bbox_max_mm[0] - topo.bbox_min_mm[0]) / 1000.0,
            "bbox_y_m": (topo.bbox_max_mm[1] - topo.bbox_min_mm[1]) / 1000.0,
            "bbox_z_m": (topo.bbox_max_mm[2] - topo.bbox_min_mm[2]) / 1000.0,
        }
        worst = 0.0
        for port in _INPUTS:
            interval = request.inputs[port]
            for corner in interval.corners():
                worst = max(worst, _relative_error(actual[port], corner))
        return Ok(Prediction(value=worst, eps=0.0, coverage=1.0, in_domain=True))
