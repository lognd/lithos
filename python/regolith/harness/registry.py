"""The versioned model registry and deterministic, total selection.

Regolith/07 sec. 3: the harness holds models keyed by the claim kind
they discharge. Selection is TOTAL and honest -- an obligation with no
matching model yields an explicit indeterminate evidence value
(``harness.no_model``), never a silent pass -- and DETERMINISTIC:
candidates are ordered by (cost, model id) so the same obligation always
picks the same model.

Version discipline (BE-1/INV-1): the registry carries
:data:`regolith.harness.MODEL_REGISTRY_VERSION`, and that string is folded
into every evidence hash (via :mod:`regolith.harness.evidence`). The Rust
core already threads this same version into the obligation/evidence-cache
key at discharge time; bumping it invalidates cached evidence so a model
upgrade forces re-verification.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith._schema.models import Evidence
from regolith.harness import MODEL_REGISTRY_VERSION
from regolith.harness.errors import NoModelMatch
from regolith.harness.evidence import build_evidence
from regolith.harness.model import DischargeRequest, Model
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The synthetic model id used when nothing matches -- an honest,
# greppable marker that this evidence is a "no model available" verdict.
NO_MODEL_ID = "harness.no_model"


class ModelRegistry:
    """A versioned lookup of verification models keyed by claim kind."""

    def __init__(self, version: str = MODEL_REGISTRY_VERSION) -> None:
        """Create an empty registry stamped with ``version`` (BE-1/INV-1)."""
        self._version = version
        self._by_kind: dict[str, list[Model]] = {}

    @property
    def version(self) -> str:
        """The registry version folded into every evidence hash."""
        return self._version

    def register(self, model: Model) -> None:
        """Add ``model`` under its signature's claim kind."""
        kind = model.signature.claim_kind
        self._by_kind.setdefault(kind, []).append(model)
        _log.debug(
            "registered model %s for claim kind %s (cost=%d)",
            model.model_id,
            kind,
            model.cost,
        )

    def candidates(self, claim_kind: str) -> tuple[Model, ...]:
        """Every model for ``claim_kind``, in deterministic (cost, id) order."""
        models = self._by_kind.get(claim_kind, [])
        return tuple(sorted(models, key=lambda m: (m.cost, m.model_id)))

    def select(self, request: DischargeRequest) -> Result[Model, NoModelMatch]:
        """Pick the cheapest in-signature model for ``request``, or a value.

        Deterministic: (cost, model id) order. Total: a no-match is an
        explicit ``Err(NoModelMatch)``, carrying every model considered.
        """
        candidates = self.candidates(request.claim_kind)
        available = request.input_ports()
        for model in candidates:
            if model.signature.accepts(available):
                _log.debug(
                    "selected model %s for %s", model.model_id, request.claim_kind
                )
                return Ok(model)
        considered = tuple(m.model_id for m in candidates)
        reason = (
            "no model for claim kind"
            if not candidates
            else "no candidate's required inputs are satisfied"
        )
        _log.info(
            "no model matched claim kind %s (considered=%s)",
            request.claim_kind,
            considered,
        )
        return Err(
            NoModelMatch(
                claim_kind=request.claim_kind,
                reason=reason,
                considered=considered,
            )
        )

    def try_discharge(
        self, request: DischargeRequest
    ) -> Result[Evidence, NoModelMatch]:
        """Discharge ``request``, or report the no-match value.

        Note a matched model that hits a missing-input/out-of-domain
        condition still resolves to an indeterminate ``Evidence`` (via
        :meth:`discharge`); this method's ``Err`` is reserved for the
        no-model case a caller may want to inspect.
        """
        selected = self.select(request)
        if selected.is_err:
            return Err(selected.danger_err)
        return Ok(self._discharge_with(selected.danger_ok, request))

    def discharge(self, request: DischargeRequest) -> Evidence:
        """Discharge ``request`` to an ``Evidence`` value, TOTALLY.

        Never a silent pass: no model, a missing input, or an
        out-of-domain corner all resolve to an honest ``indeterminate``
        evidence value with a descriptive model id.
        """
        selected = self.select(request)
        if selected.is_err:
            return self._no_model_evidence(request)
        return self._discharge_with(selected.danger_ok, request)

    def _discharge_with(self, model: Model, request: DischargeRequest) -> Evidence:
        """Run one model's discharge, mapping its error value to evidence."""
        result = model.discharge(request, registry_version=self._version)
        if result.is_ok:
            return result.danger_ok
        # A matched-but-unusable model (missing input / out of domain) is
        # an honest indeterminate, tagged with the model that abstained.
        err = result.danger_err
        _log.info("model %s abstained: %r", model.model_id, err)
        return self._indeterminate_evidence(
            request, model_id=f"{model.model_id}#abstained"
        )

    def _no_model_evidence(self, request: DischargeRequest) -> Evidence:
        """The explicit no-model indeterminate evidence value."""
        return self._indeterminate_evidence(request, model_id=NO_MODEL_ID)

    def _indeterminate_evidence(
        self, request: DischargeRequest, *, model_id: str
    ) -> Evidence:
        """Build an indeterminate evidence value (coverage 0, out of domain)."""
        return build_evidence(
            model_id=model_id,
            claim_kind=request.claim_kind,
            sense_upper=True,
            value=0.0,
            eps=0.0,
            limit=request.limit,
            coverage=0.0,
            cost=0,
            in_domain=False,
            deterministic=request.deterministic,
            registry_version=self._version,
            inputs_digest=request.inputs_digest(),
            settings_digest=request.settings_digest,
        )


def default_registry() -> ModelRegistry:
    """Build the registry with every shipped model pack registered.

    The one wiring point new packs plug into (see
    ``regolith.harness.models``).
    """
    from regolith.harness.models import register_all

    registry = ModelRegistry()
    register_all(registry)
    return registry
