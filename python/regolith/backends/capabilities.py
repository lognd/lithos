"""The realizer capability registry (WO-164, AD-47 sec. 5, charter 44).

Adding a manufacturing/generation capability today means touching an
unwritten list of places: a program IR, a realized-kind put seam, an
artifact family, a tool-adapter tier ladder, a stdlib process-record
namespace, a DFM check set, and a claim-kind vocabulary. This module
names the list as ONE typed record (:class:`RealizerCapability`) and a
registry (:class:`CapabilityRegistry`) that REFUSES an incomplete
registration at registration time -- "wire EDM support" (WO-166) cannot
land as a code path without its process records, DFM checks, and
provenance story landing with it, because every field is required.

Home: beside :mod:`regolith.backends.registry` (the producer/renderer/
artifact-family registries) rather than a new top-level module or
under :mod:`regolith.realizer` -- this is a registry-shaped concept in
the same family as the three registries `registry.py` already owns,
and it directly references that module's ``ArtifactFamilyRegistry``
family names and :mod:`regolith.backends.framework`'s
``ArtifactProvenance`` tier vocabulary (WO-160), so living in
``backends/`` avoids a realizer -> backends import (the AD-43 layer
model runs L3 REALIZE -> L4 EMIT, never the reverse) while still being
importable from realizer-side callers (WO-165/166/167) the same way
they already import ``regolith.backends.framework``.

This WO retrofits the two existing domains (mech, elec) as the first
two registrations, DESCRIPTIVELY -- naming their existing scattered
pieces field-by-field, no behavior change to either realizer. It does
NOT add a third domain (fluid, civil retrofits are each capability
program's own scope, per the WO's non-goals) and does NOT grow the DFM
check set or claim vocabulary (it references the EXISTING sets only).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import FeatureProgram
from regolith.logging_setup import get_logger
from regolith.realizer.elec.kicad import LayoutRequest

_log = get_logger(__name__)

#: The AD-45 provenance tier vocabulary (`regolith.backends.framework.
#: ArtifactProvenance.tier`), reused here rather than re-declared -- ONE
#: home for the tier strings (the tripwire rule applied to provenance
#: words).
ProvenanceTier = Literal["real_tool", "deterministic"]


# frob:doc docs/modules/py-backends.md#backends-capabilities
class ToolAdapterDescriptor(BaseModel):
    """One tier of a capability's tool-adapter ladder (AD-45): ``name``
    identifies the adapter (a real external tool's name for
    ``tier="real_tool"``, or a short descriptive tag for a
    ``"deterministic"`` in-process/fallback tier); ``tier`` is the
    provenance tier that tool-adapted output is stamped with. Ordered
    within :attr:`RealizerCapability.tool_adapters`: ``real_tool``
    tiers first (the tool actually attempted), ``deterministic``
    fallback tiers after (what runs when the real tool is unavailable
    or the domain has no external tool at all)."""

    model_config = ConfigDict(frozen=True)

    name: str
    tier: ProvenanceTier


# frob:doc docs/modules/py-backends.md#backends-capabilities
class RealizerCapability(BaseModel):
    """One domain's realizer capability registration (AD-47 sec. 5): the
    full checklist a NEW manufacturing/generation capability must
    supply, all seven fields required (no field is ``Optional`` with a
    silent default -- a domain with a legitimately empty set, e.g. no
    ``dfm_checks`` at all, supplies an explicit empty tuple, never an
    implicit one).

    - ``domain``: the short domain tag (``"mech"``, ``"elec"``,
      ``"fluid"``, ``"civil"``, or a future domain's own tag) -- a
      plain ``str`` rather than a closed enum, since AD-47 names this
      as an open extension seam (WO-165/166/167 each add one).
    - ``program_kind``: the L1/L2 program IR CLASS this domain's
      realizer consumes (e.g. ``FeatureProgram`` for mech) -- the
      actual type object, not a string, so a caller can
      ``isinstance``-check against it.
    - ``realized_kind``: the ``put_realized_*`` kind-string this
      domain's realizer emits (AD-25 discipline; e.g.
      ``"geometry.realized"`` for mech, matching
      ``regolith.orchestrator.orchestrate.put_realized_geometry``'s
      payload-store kind).
    - ``artifact_families``: the AD-36 family names (as registered in
      ``regolith.backends.registry.default_artifact_family_registry``)
      this capability's emission brings.
    - ``tool_adapters``: the ordered tier ladder (real_tool tiers
      first, deterministic fallback after), each an explicit
      :class:`ToolAdapterDescriptor`.
    - ``process_records``: the stdlib namespace globs (AD-37 naming)
      this domain's realizer/DFM machinery consults.
    - ``dfm_checks``: the check identifiers (module-qualified function
      names) from the EXISTING DFM check-set machinery that gate this
      domain's realize.
    - ``claim_kinds``: the claim-kind identifiers from the EXISTING
      claims vocabulary this domain discharges evidence for.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    domain: str
    program_kind: type[BaseModel]
    realized_kind: str
    artifact_families: tuple[str, ...]
    tool_adapters: tuple[ToolAdapterDescriptor, ...]
    process_records: tuple[str, ...]
    dfm_checks: tuple[str, ...]
    claim_kinds: tuple[str, ...]


#: One CapabilityRegistry error: which field(s) were missing/empty, and
#: which domain's registration was refused (never a generic message --
#: the caller must be able to name exactly what to fill in).
# frob:doc docs/modules/py-backends.md#backends-capabilities
class IncompleteCapabilityError(Exception):
    """Raised by :func:`register_capability` when a
    :class:`RealizerCapability` has one or more empty required fields.
    A load-time programmer error (a capability module registering
    itself with a hole in its own checklist), not a caller-recoverable
    condition -- the house Result-vs-exception doctrine reserves
    exceptions for exactly this: an unrecoverable authoring bug caught
    at import/registration time, never surfaced to an end user as a
    value they could branch on."""

    def __init__(self, domain: str, empty_fields: tuple[str, ...]) -> None:
        """Name ``domain`` and every ``empty_fields`` entry in the message
        (never just the first one -- a retry-after-fix loop wants the
        whole list in one pass)."""
        self.domain = domain
        self.empty_fields = empty_fields
        super().__init__(
            f"capability registration for domain {domain!r} is incomplete: "
            f"empty required field(s) {list(empty_fields)!r} -- AD-47 refuses "
            "a capability missing any field of the checklist"
        )


#: The tuple-valued fields checked for emptiness (every field on
#: `RealizerCapability` except `domain`/`program_kind`/`realized_kind`,
#: which are non-tuple and validated non-empty by pydantic's own
#: min-length-1 `str` requirement -- a `domain`/`realized_kind` of `""`
#: is already rejected structurally below).
_TUPLE_FIELDS: tuple[str, ...] = (
    "artifact_families",
    "tool_adapters",
    "process_records",
    "dfm_checks",
    "claim_kinds",
)


# frob:doc docs/modules/py-backends.md#backends-capabilities
def _missing_fields(capability: RealizerCapability) -> tuple[str, ...]:
    """Every required field of ``capability`` that is empty: ``domain``/
    ``realized_kind`` empty strings, plus any `_TUPLE_FIELDS` entry that
    is an empty tuple. `program_kind` cannot be "empty" (a type object
    always exists once pydantic accepts it), so it is not checked here."""
    missing: list[str] = []
    if not capability.domain:
        missing.append("domain")
    if not capability.realized_kind:
        missing.append("realized_kind")
    for name in _TUPLE_FIELDS:
        if not getattr(capability, name):
            missing.append(name)
    return tuple(missing)


# frob:doc docs/modules/py-backends.md#backends-capabilities
class CapabilityRegistry:
    """Domain -> :class:`RealizerCapability`, loud on both an incomplete
    registration (raises :class:`IncompleteCapabilityError`) and a
    duplicate domain (raises the same error type, distinct message --
    both are load-time authoring bugs, never a silent shadow)."""

    def __init__(self) -> None:
        """Start empty; built-ins are added via
        :func:`default_capability_registry`."""
        self._by_domain: dict[str, RealizerCapability] = {}

    # frob:doc docs/modules/py-backends.md#backends-capabilities
    def register(self, capability: RealizerCapability) -> None:
        """Add ``capability``; raises :class:`IncompleteCapabilityError`
        if any required field is empty, or if ``capability.domain`` is
        already registered (named as an ``["<domain>: duplicate
        registration"]`` empty-fields entry so the one error type
        covers both refusal reasons)."""
        missing = _missing_fields(capability)
        if capability.domain in self._by_domain:
            missing = (*missing, "domain: duplicate registration")
        if missing:
            _log.error(
                "capability registry: refusing domain %r -- missing %s",
                capability.domain,
                missing,
            )
            raise IncompleteCapabilityError(capability.domain, missing)
        self._by_domain[capability.domain] = capability
        _log.debug("capability registry: registered domain %r", capability.domain)

    # frob:doc docs/modules/py-backends.md#backends-capabilities
    def get(self, domain: str) -> RealizerCapability | None:
        """The registration for ``domain``, or ``None`` if unregistered."""
        return self._by_domain.get(domain)

    # frob:doc docs/modules/py-backends.md#backends-capabilities
    def domains(self) -> tuple[str, ...]:
        """Every registered domain, in registration order (deterministic)."""
        return tuple(self._by_domain)


# frob:doc docs/modules/py-backends.md#backends-capabilities
def register_capability(
    registry: CapabilityRegistry, capability: RealizerCapability
) -> Result[None, str]:
    """Caller-facing wrapper over :meth:`CapabilityRegistry.register`:
    a `Result` for call sites that want to compose this with other
    fallible setup instead of catching an exception (the house
    doctrine's caller-facing half). The underlying refusal is still an
    :class:`IncompleteCapabilityError` -- callers that want the raw
    typed error (e.g. to inspect ``empty_fields``) should call
    ``registry.register`` directly and catch it; this wrapper's `Err`
    carries the exception's message string."""
    try:
        registry.register(capability)
    except IncompleteCapabilityError as exc:
        return Err(str(exc))
    return Ok(None)


# frob:doc docs/modules/py-backends.md#backends-capabilities
def get_capability(
    registry: CapabilityRegistry, domain: str
) -> RealizerCapability | None:
    """Lookup/query surface WO-165/166/167 use to discover a domain's
    process records / DFM checks / tool adapters instead of hard-coding
    them: ``registry.get(domain)`` by another name, kept as a module
    function so a caller can import ``get_capability`` the same way it
    already imports other backend lookup helpers (parallel to
    ``ArtifactFamilyRegistry.get``'s call convention)."""
    return registry.get(domain)


# --- built-in registrations (WO-164 deliverable 3: mech + elec retrofit) --


def _mech_capability() -> RealizerCapability:
    """The mech domain, named field-by-field from its EXISTING scattered
    pieces (a descriptive retrofit -- no behavior change):

    - ``program_kind``: `FeatureProgram`, the v1 L1/L2 program IR the
      build123d/OCCT interpreter consumes
      (`regolith.realizer.mech.interpreter`).
    - ``realized_kind``: ``"geometry.realized"``, the
      `put_realized_geometry` payload-store kind
      (`regolith.orchestrator.orchestrate`).
    - ``artifact_families``: the mech-owned families in
      `regolith.backends.registry.default_artifact_family_registry`
      (``mech`` for the STEP+fab-notes package, ``3d`` for the
      GLB+viewer, ``drawings`` for the projected multi-view drawing,
      ``bom``/``cost`` for the mech BOM/cost legs).
    - ``tool_adapters``: ONE deterministic tier -- build123d/OCCT runs
      in-process (never a `procio` subprocess invocation), so it is
      the ``deterministic`` tier by this repo's own AD-45 definition
      (`real_tool` means procio-invoked), not a two-tier real/fallback
      ladder like elec's KiCad path.
    - ``process_records``: the stdlib namespaces `dfm_staging`'s
      mill-family grounding consults for `[[tool]]`/`[[machine]]`
      records, plus `std.mech` for the part's own material/feature
      records.
    - ``dfm_checks``: `check_stock_fit`/`check_tool_fit`
      (`regolith.harness.models.dfm.checks`), the hematite DFM doctrine
      pair this WO's charter section generalizes to every domain.
    - ``claim_kinds``: `"geometry_realizable"`
      (`regolith.realizer.mech.model.CLAIM_KIND`) and
      `"mfg.manufacturable"`
      (`regolith.harness.models.dfm.models.CLAIM_KIND`).
    """
    return RealizerCapability(
        domain="mech",
        program_kind=FeatureProgram,
        realized_kind="geometry.realized",
        artifact_families=("mech", "3d", "drawings", "bom", "cost"),
        tool_adapters=(
            ToolAdapterDescriptor(name="build123d_occt", tier="deterministic"),
        ),
        process_records=(
            "std.mech/records/**",
            "std.tooling/records/**",
            "std.machines/records/**",
        ),
        dfm_checks=(
            "regolith.harness.models.dfm.checks:check_stock_fit",
            "regolith.harness.models.dfm.checks:check_tool_fit",
        ),
        claim_kinds=("geometry_realizable", "mfg.manufacturable"),
    )


def _elec_capability() -> RealizerCapability:
    """The elec domain, named field-by-field from its EXISTING
    scattered pieces (a descriptive retrofit -- no behavior change):

    - ``program_kind``: `LayoutRequest`
      (`regolith.realizer.elec.kicad`), the resolved bind->netlist
      payload the two-tier KiCad adapter consumes to produce a layout.
    - ``realized_kind``: ``"layout.realized"``, the
      `put_realized_layout` payload-store kind
      (`regolith.realizer.elec.realized`).
    - ``artifact_families``: the elec-owned families (``boards`` for
      the gerber/excellon fab set, ``3d``/``drawings``/``bom``/``cost``
      the same shared families mech also brings, each independently
      populated by the elec producers/renderers).
    - ``tool_adapters``: the real KiCad tier (`kicad-cli`, procio-
      invoked, `real_tool`) tried first, the fake/deterministic fab-set
      exporter fallback second (`regolith.backends.elec_fabset`) --
      the actual two-tier ladder `registry.py`'s own module docstring
      already names ("the fake/real KiCad fork").
    - ``process_records``: `std.elec`/`std.elec.stackups` (component,
      footprint, and stackup records the netlist/layout pipeline
      consults).
    - ``dfm_checks``: the KiCad DRC discharge
      (`regolith.realizer.elec.kicad.LayoutDrcModel`'s signature name,
      `"elec_layout_kicad_drc"`) -- elec's DFM gate is DRC-clean-ness
      rather than the mech stock/tool-fit pair, the hematite doctrine
      generalized to this domain's own real gate.
    - ``claim_kinds``: `"elec.layout.drc_clean"`
      (`regolith.realizer.elec.kicad.CLAIM_KIND_DRC_CLEAN`).
    """
    return RealizerCapability(
        domain="elec",
        program_kind=LayoutRequest,
        realized_kind="layout.realized",
        artifact_families=("boards", "3d", "drawings", "bom", "cost"),
        tool_adapters=(
            ToolAdapterDescriptor(name="kicad-cli", tier="real_tool"),
            ToolAdapterDescriptor(name="fake_kicad_fallback", tier="deterministic"),
        ),
        process_records=("std.elec/records/**", "std.elec.stackups/records/**"),
        dfm_checks=("regolith.realizer.elec.kicad:elec_layout_kicad_drc",),
        claim_kinds=("elec.layout.drc_clean",),
    )


# frob:doc docs/modules/py-backends.md#backends-capabilities
def default_capability_registry() -> CapabilityRegistry:
    """The two built-in registrations (WO-164 deliverable 3): mech and
    elec, retrofit from their existing scattered pieces. A collision
    here is a built-in authoring bug (both domain tags are hard-coded
    distinct strings), so it is allowed to raise straight through
    rather than being caught -- the same posture the other
    `default_*_registry` factories in `registry.py` take with their own
    `assert result.is_ok` built-in-collision guards."""
    registry = CapabilityRegistry()
    registry.register(_mech_capability())
    registry.register(_elec_capability())
    return registry
