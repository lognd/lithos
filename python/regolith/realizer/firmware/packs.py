"""The MCU-family pack seam (deliverable 4): vendor HAL idiom as pack content.

D109: "vendor mapping is pack content -- abstract peripheral config ->
vendor HAL/register idiom comes from signed MCU-family packs (registry
records + templates, trust tiers apply); regolith core stays
vendor-neutral." Mirrors AD-19's model-pack shape (a registration
protocol, composition by name, core code contains no vendor-specific
strings -- the grep criterion in WO-37 acceptance). WO-44/AD-26 folded
external mcu-family discovery onto the one ``regolith.plugins`` seam
(``kind=mcu_pack``); built-ins are always composed first, then
discovered plugins, sorted-by-id, exactly mirroring the model-pack
seam's composition order.

``FamilyPack`` is the whole protocol: it turns one pin assignment (or
one clock, or one event) into vendor-idiom C lines. `regolith` ships
exactly one reference pack (deliverable 4's own instruction) proving
the seam; a design naming an unregistered family is honest
indeterminate (:class:`~regolith.realizer.firmware.errors.UnknownFamily`),
never a guess.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.plugins import (
    PluginDiscoveryError,
    PluginEntryPoint,
    PluginEntryPointRaised,
    PluginKind,
    discover_plugins,
)
from regolith.realizer.elec.pinmux import PinAssignment
from regolith.realizer.firmware.contract import ClockDecl, EventDecl
from regolith.realizer.firmware.errors import UnknownFamily

_log = get_logger(__name__)


class FamilyPack(ABC):
    """Vendor idiom for one MCU family: pin init, clock init, ISR stub lines.

    Every method returns plain C statement lines (no trailing
    newlines) -- the caller (:mod:`bsp`) owns file assembly and
    formatting. A pack never emits application logic: pin/clock init
    lines only, and ISR stub bodies that call a user hook by name,
    never contain a decision.
    """

    #: The registry key this pack answers for (cuprite/04's
    #: `mcu-family` record kind); never a vendor string outside a pack.
    family: str

    @abstractmethod
    def pin_init_lines(self, assignment: PinAssignment) -> tuple[str, ...]:
        """Vendor register/HAL calls configuring one assigned pin."""

    @abstractmethod
    def clock_init_lines(self, clock: ClockDecl) -> tuple[str, ...]:
        """Vendor register/HAL calls configuring one declared clock."""

    @abstractmethod
    def isr_stub(self, event: EventDecl) -> tuple[str, ...]:
        """The full ISR stub function for one event: signature + hook call only."""


class Stm32G0Pack(FamilyPack):
    """Reference pack for the stm32g0 lineage (deliverable 4's Kestrel fixture family).

    HAL idiom is illustrative (`LL_GPIO_*`/`LL_RCC_*`-shaped calls, the
    stm32g0 low-layer driver naming convention) -- proving the seam,
    not a complete vendor HAL binding.
    """

    family = "stm32g0"

    def pin_init_lines(self, assignment: PinAssignment) -> tuple[str, ...]:
        ident = assignment.flow.replace(".", "_").replace("-", "_").upper()
        return (
            f"    /* {assignment.flow} -> {assignment.pin} ({assignment.instance}) */",
            f"    LL_GPIO_SetPinMode(GPIO_PORT_OF(PIN_{ident}), "
            f"GPIO_NUM_OF(PIN_{ident}), LL_GPIO_MODE_ALTERNATE);",
            f"    LL_GPIO_SetAFPin(GPIO_PORT_OF(PIN_{ident}), "
            f"GPIO_NUM_OF(PIN_{ident}), INSTANCE_{ident});",
        )

    def clock_init_lines(self, clock: ClockDecl) -> tuple[str, ...]:
        ident = clock.name.replace(".", "_").replace("-", "_").upper()
        return (
            f"    /* {clock.name} = {clock.freq_hz} Hz */",
            f"    LL_RCC_SetClockFrequency(CLOCK_{ident}_HZ);",
        )

    def isr_stub(self, event: EventDecl) -> tuple[str, ...]:
        ident = event.name.replace(".", "_").replace("-", "_").upper()
        fn = f"on_{event.name.replace('.', '_').replace('-', '_').lower()}_isr"
        lines = [f"void {fn}(void)", "{"]
        if event.pin is not None:
            lines.append(f"    /* trigger pin: EVENT_{ident}_PIN */")
        lines.append(f"    regolith_hook_{event.name.replace('.', '_').lower()}();")
        lines.append("}")
        return tuple(lines)


#: The built-in pack registry: always composed first (AD-19 order).
_BUILTIN_PACKS: dict[str, FamilyPack] = {
    Stm32G0Pack.family: Stm32G0Pack(),
}


class McuFamilyPackOutcome(BaseModel):
    """The total result of one mcu-family plugin composition pass."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    packs: dict[str, FamilyPack] = {}
    errors: tuple[PluginDiscoveryError, ...] = ()


def _compose_mcu_packs(
    *, entry_points_override: Iterable[PluginEntryPoint] | None = None
) -> McuFamilyPackOutcome:
    """Built-ins first, then every ``mcu_pack`` plugin (sorted-by-id, WO-44).

    A plugin naming a family a built-in (or an earlier plugin) already
    owns is a loud duplicate-id error (the generic seam's own check, via
    ``discover_plugins``) -- never silent last-wins.
    """
    packs = dict(_BUILTIN_PACKS)
    discovery = discover_plugins(
        PluginKind.MCU_PACK, entry_points_override=entry_points_override
    )
    errors: list[PluginDiscoveryError] = list(discovery.errors)
    for manifest in discovery.manifests:
        staging: dict[str, FamilyPack] = {}
        try:
            manifest.register_fn(staging)
        except Exception as exc:  # noqa: BLE001 -- plugin boundary: their bugs are our data
            _log.warning("mcu-family plugin %r raised LOUDLY: %s", manifest.id, exc)
            errors.append(
                PluginEntryPointRaised(
                    source=manifest.id, message=f"register() raised: {exc}"
                )
            )
            continue
        packs.update(staging)
        _log.info("registered mcu-family plugin %s@%s", manifest.id, manifest.version)
    return McuFamilyPackOutcome(packs=packs, errors=tuple(errors))


def get_pack(
    family: str,
    *,
    entry_points_override: Iterable[PluginEntryPoint] | None = None,
) -> Result[FamilyPack, UnknownFamily]:
    """The registered pack for ``family`` (built-in or plugin), or an honest
    indeterminate.

    D109 / acceptance criterion 4: "no family pack installed -> honest
    indeterminate naming the family."
    """
    outcome = _compose_mcu_packs(entry_points_override=entry_points_override)
    pack = outcome.packs.get(family)
    if pack is None:
        _log.warning("no MCU-family pack registered for family=%s", family)
        return Err(
            UnknownFamily(
                family=family,
                message=f"no MCU-family pack registered for family {family!r}",
            )
        )
    return Ok(pack)
