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

from typing import TYPE_CHECKING

from typani.result import Err, Ok, Result

from regolith._schema.models import Evidence
from regolith.harness import MODEL_REGISTRY_VERSION
from regolith.harness.errors import (
    ADAPTER_ERROR_ID,
    MalformedResponse,
    NoModelMatch,
    NonzeroExit,
    SchemaVersionMismatch,
    SpawnFailed,
    Timeout,
)
from regolith.harness.evidence import build_evidence
from regolith.harness.model import DischargeRequest, Model
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.harness.plugin import PackInfo, PackLoadError
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# The synthetic model id used when nothing matches -- an honest,
# greppable marker that this evidence is a "no model available" verdict.
NO_MODEL_ID = "harness.no_model"

# The pack name built-in models carry in every evidence hash (AD-19);
# their pack VERSION is the registry version itself.
BUILTIN_PACK_NAME = "regolith"

# The adapter failure arms the WO-20 subprocess seam maps to the
# explicit `harness.adapter_error` indeterminate evidence value.
_ADAPTER_ERROR_TYPES = (
    SpawnFailed,
    Timeout,
    MalformedResponse,
    SchemaVersionMismatch,
    NonzeroExit,
)

# D94 (sec. 8.1): a claim kind names WHAT is claimed, never a method,
# tool, or tier. Registration lints kind strings against this deny
# list of method/tool words -- a violation is a registration error,
# not a warning (`plugin.MethodNamedKind`, the `PackLoadError` family).
METHOD_WORD_DENY_LIST: tuple[str, ...] = (
    "fea",
    "spice",
    "cfd",
    "ngspice",
    "ccx",
    "abaqus",
    "ansys",
)


def method_named_kind_violation(claim_kind: str) -> str | None:
    """The offending deny-listed word in ``claim_kind``, or ``None``.

    D94: a claim kind is segmented on `.`/`_` boundaries; any segment
    equal to a method/tool word (`fea`, `spice`, ...) is a bootstrap
    error (`mech.fea.static_stress` was one) -- method/tier are model
    attributes, never part of the vocabulary-owned kind name.
    """
    segments = claim_kind.replace(".", "_").split("_")
    for word in METHOD_WORD_DENY_LIST:
        if word in segments:
            return word
    return None


class ModelRegistry:
    """A versioned lookup of verification models keyed by claim kind."""

    def __init__(self, version: str = MODEL_REGISTRY_VERSION) -> None:
        """Create an empty registry stamped with ``version`` (BE-1/INV-1)."""
        self._version = version
        self._by_kind: dict[str, list[Model]] = {}
        self._order: list[Model] = []
        self._pack_of: dict[str, tuple[str, str]] = {}
        # D94: the registry key is (claim_kind, model_id) -- one model
        # MAY register under two kinds; the duplicate-id error is
        # per-kind (tracked here for plugin.py's collision check).
        self._keys: set[tuple[str, str]] = set()
        self._packs: tuple[PackInfo, ...] = ()
        self._plugin_errors: tuple[PackLoadError, ...] = ()

    @property
    def version(self) -> str:
        """The registry version folded into every evidence hash."""
        return self._version

    def register(
        self,
        model: Model,
        *,
        pack_name: str = BUILTIN_PACK_NAME,
        pack_version: str | None = None,
    ) -> None:
        """Add ``model`` under its signature's claim kind.

        ``pack_name``/``pack_version`` record which model pack the model
        came from (AD-19); the defaults are the built-in identity
        ``("regolith", <registry version>)``. ``load_packs`` passes the
        discovered pack's identity when merging.
        """
        kind = model.signature.claim_kind
        self._by_kind.setdefault(kind, []).append(model)
        self._order.append(model)
        self._keys.add((kind, model.model_id))
        resolved_pack = (
            pack_name,
            pack_version if pack_version is not None else self._version,
        )
        self._pack_of[model.model_id] = resolved_pack
        _log.debug(
            "registered model %s for claim kind %s (cost=%d, pack=%s@%s)",
            model.model_id,
            kind,
            model.cost,
            resolved_pack[0],
            resolved_pack[1],
        )

    def model_ids(self) -> frozenset[str]:
        """Every registered model id (duplicate detection surface).

        Kept for callers that only need the flat id set; D94 kind
        competition means the SAME id may legitimately appear under
        several kinds -- use :meth:`registered_keys` for the per-kind
        duplicate check.
        """
        return frozenset(self._pack_of)

    def registered_keys(self) -> frozenset[tuple[str, str]]:
        """Every registered ``(claim_kind, model_id)`` pair (D94 keying)."""
        return frozenset(self._keys)

    def all_models(self) -> tuple[Model, ...]:
        """Every registered model, in registration order (deterministic)."""
        return tuple(self._order)

    def pack_of(self, model_id: str) -> tuple[str, str]:
        """The ``(pack_name, pack_version)`` a model was registered from.

        An unknown id resolves to the built-in identity -- the honest
        default for synthetic ids like ``harness.no_model``.
        """
        return self._pack_of.get(model_id, (BUILTIN_PACK_NAME, self._version))

    def record_packs(
        self, loaded: tuple[PackInfo, ...], skipped: tuple[PackLoadError, ...]
    ) -> None:
        """Record one pack-composition outcome for the build report."""
        self._packs = loaded
        self._plugin_errors = skipped

    @property
    def packs(self) -> tuple[PackInfo, ...]:
        """The packs loaded into this registry (composition order)."""
        return self._packs

    @property
    def plugin_errors(self) -> tuple[PackLoadError, ...]:
        """The packs skipped LOUDLY at composition (named in the report).

        Named ``plugin_errors`` (WO-44/AD-26 rename of the WO-20
        ``pack_errors`` field): model packs are one of the four kinds the
        one ``regolith.plugins`` seam discovers.
        """
        return self._plugin_errors

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
        available_payloads = request.payload_ports()
        available_regimes = request.regimes
        for model in candidates:
            sig = model.signature
            if (
                sig.accepts(available)
                and sig.accepts_payloads(available_payloads)
                and sig.accepts_regimes(available_regimes)
            ):
                _log.debug(
                    "selected model %s for %s", model.model_id, request.claim_kind
                )
                return Ok(model)
        considered = tuple(m.model_id for m in candidates)
        reason = (
            "no model for claim kind"
            if not candidates
            else "no candidate's required inputs/payloads/regimes are satisfied"
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
        self,
        request: DischargeRequest,
        *,
        resolver: PayloadResolver | None = None,
    ) -> Result[Evidence, NoModelMatch]:
        """Discharge ``request``, or report the no-match value.

        Note a matched model that hits a missing-input/out-of-domain
        condition still resolves to an indeterminate ``Evidence`` (via
        :meth:`discharge`); this method's ``Err`` is reserved for the
        no-model case a caller may want to inspect. ``resolver`` (D96/
        D154) is forwarded to the selected model exactly as
        :meth:`discharge` forwards it.
        """
        selected = self.select(request)
        if selected.is_err:
            return Err(selected.danger_err)
        return Ok(self._discharge_with(selected.danger_ok, request, resolver=resolver))

    def discharge(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Evidence:
        """Discharge ``request`` to an ``Evidence`` value, TOTALLY.

        Never a silent pass: no model, a missing input, or an
        out-of-domain corner all resolve to an honest ``indeterminate``
        evidence value with a descriptive model id. ``resolver`` (D96/
        D154) is the orchestrator payload-store handle
        :func:`regolith.orchestrator.discharge.discharge_one` threads
        down; it reaches only the model :meth:`select` picks, and only
        if that model's ``estimate`` override opts in (`Model.discharge`'s
        capability check).
        """
        selected = self.select(request)
        if selected.is_err:
            return self._no_model_evidence(request)
        return self._discharge_with(selected.danger_ok, request, resolver=resolver)

    def _discharge_with(
        self,
        model: Model,
        request: DischargeRequest,
        *,
        resolver: PayloadResolver | None = None,
    ) -> Evidence:
        """Run one model's discharge, mapping its error value to evidence."""
        pack_name, pack_version = self.pack_of(model.model_id)
        result = model.discharge(
            request,
            registry_version=self._version,
            pack_name=pack_name,
            pack_version=pack_version,
            resolver=resolver,
        )
        if result.is_ok:
            return result.danger_ok
        err = result.danger_err
        # A subprocess-adapter infrastructure failure (spawn/timeout/
        # malformed/version-skew/nonzero-exit, WO-20) is the explicit
        # `harness.adapter_error` indeterminate value -- never a pass,
        # never an exception.
        if isinstance(err, _ADAPTER_ERROR_TYPES):
            _log.warning(
                "adapter failure for model %s: %r -> %s indeterminate",
                model.model_id,
                err,
                ADAPTER_ERROR_ID,
            )
            return self._indeterminate_evidence(
                request,
                model_id=ADAPTER_ERROR_ID,
                pack=(pack_name, pack_version),
            )
        # A matched-but-unusable model (missing input / out of domain) is
        # an honest indeterminate, tagged with the model that abstained.
        _log.info("model %s abstained: %r", model.model_id, err)
        return self._indeterminate_evidence(
            request,
            model_id=f"{model.model_id}#abstained",
            pack=(pack_name, pack_version),
        )

    def _no_model_evidence(self, request: DischargeRequest) -> Evidence:
        """The explicit no-model indeterminate evidence value."""
        return self._indeterminate_evidence(request, model_id=NO_MODEL_ID)

    def _indeterminate_evidence(
        self,
        request: DischargeRequest,
        *,
        model_id: str,
        pack: tuple[str, str] | None = None,
    ) -> Evidence:
        """Build an indeterminate evidence value (coverage 0, out of domain).

        ``pack`` attributes the evidence to the pack of the model that
        failed/abstained (AD-19 keying); ``None`` is the built-in
        identity (the no-model case).
        """
        pack_name, pack_version = (
            pack
            if pack is not None
            else (
                BUILTIN_PACK_NAME,
                self._version,
            )
        )
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
            pack_name=pack_name,
            pack_version=pack_version,
        )


def default_registry() -> ModelRegistry:
    """Build the registry: built-ins first, then discovered packs (AD-19).

    The ONE composition point: ``register_all`` registers the shipped
    built-ins, then ``load_packs`` merges every ``model_pack`` plugin
    from the one ``regolith.plugins`` seam, in sorted-by-name order
    (deterministic composition, design doc D-B). Bad packs are skipped
    loudly and recorded on the registry for the build report.
    """
    # Function-local imports: models/plugin both import this module.
    from regolith.harness.models import register_all
    from regolith.harness.plugin import load_packs

    registry = ModelRegistry()
    register_all(registry)
    load_packs(registry)
    return registry
