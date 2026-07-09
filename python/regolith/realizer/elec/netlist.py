"""Netlist emission: bound design -> neutral model -> KiCad writer (cuprite/06).

The neutral :class:`NetlistModel` is derived L4 data: content-addressed
(its hash feeds the lockfile pin) and independent of the emitter
backend. cuprite/06's lowering table requires the single-driver /
arbitration check to run BEFORE emission -- a net with more than one
driver pin is an honest error, never silently emitted.

The single-driver ledger itself is the AD-23 "one net core" elec
discipline: this module only serializes :class:`NetlistModel` to the
wire shape and calls :func:`regolith.compiler.check_elec_single_driver`
(the ONE door to ``regolith._core``, AD-4) -- it does not reimplement
the check. See ``docs/spec/toolchain/00-architecture.md`` sec. 23 (the
AD-23 CLARIFICATION records the Python -> Rust move).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import compiler
from regolith.logging_setup import get_logger
from regolith.realizer.elec.errors import ArbitrationError

_log = get_logger(__name__)


class Pin(BaseModel):
    """One component pin: its owning component ref and pin name."""

    model_config = ConfigDict(frozen=True)

    component: str
    pin: str
    is_driver: bool = False


class Net(BaseModel):
    """One electrical net: its name and every pin attached to it."""

    model_config = ConfigDict(frozen=True)

    name: str
    pins: tuple[Pin, ...]


class Component(BaseModel):
    """One placed-but-unrouted component reference in the netlist."""

    model_config = ConfigDict(frozen=True)

    ref: str
    record_key: str
    footprint: str


class NetlistModel(BaseModel):
    """The neutral, backend-independent netlist (derived L4 data)."""

    model_config = ConfigDict(frozen=True)

    components: tuple[Component, ...]
    nets: tuple[Net, ...]

    def content_hash(self) -> str:
        """A sha256 content address over the canonical JSON form.

        Magnetite-style ``sha256:<hex>`` (matches
        `regolith.magnetite.records.Record.content_hash` shape) so a
        netlist can be pinned exactly like a registry record.
        """
        canonical = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        return f"sha256:{digest}"


def _nets_wire_json(model: NetlistModel) -> str:
    """Serialize ``model.nets`` to the AD-23 net_core wire shape."""
    return json.dumps(
        [
            {
                "name": net.name,
                "pins": [
                    {"component": p.component, "pin": p.pin, "is_driver": p.is_driver}
                    for p in net.pins
                ],
            }
            for net in model.nets
        ]
    )


def check_single_driver(model: NetlistModel) -> Result[NetlistModel, ArbitrationError]:
    """Reject any net with more than one driver pin (cuprite/06).

    Runs before emission (WO-24 deliverable 2): two drivers on one net
    is a design error the realizer must not paper over. The ledger
    itself is the AD-23 net core's elec discipline (Rust
    ``regolith-sem::net_core``); this function only marshals the model
    to its wire shape and reports the (already Rust-checked) result.
    """
    result = compiler.check_elec_single_driver(_nets_wire_json(model))
    if result.is_err:
        # `_nets_wire_json` always produces well-formed input, so a
        # `CoreFailure` here is a programmer bug at the boundary, not a
        # design error the caller must handle.
        raise RuntimeError(f"elec single-driver check: {result.danger_err}")
    violation = result.danger_ok
    if violation is None:
        return Ok(model)
    _log.warning(
        "net %s has %d drivers: %s",
        violation.net,
        len(violation.drivers),
        violation.drivers,
    )
    return Err(
        ArbitrationError(
            net=violation.net,
            drivers=violation.drivers,
            message=violation.message,
        )
    )


def _footprint_ref(component: Component) -> str:
    """The KiCad-legal footprint field (lib:footprint), from the record."""
    return component.footprint


def to_kicad_netlist(model: NetlistModel) -> str:
    """Render ``model`` to a KiCad-legacy s-expression netlist (v1 writer).

    A minimal but structurally valid `.net` document: component and net
    sections in deterministic (name-sorted) order, ASCII only. This is
    the "KiCad netlist writer" half of WO-24 deliverable 2; it does not
    depend on kicad-cli (pure text emission).
    """
    lines = ["(export (version D)", "  (components"]
    for comp in sorted(model.components, key=lambda c: c.ref):
        lines.append(
            f'    (comp (ref "{comp.ref}") (value "{comp.record_key}") '
            f'(footprint "{_footprint_ref(comp)}"))'
        )
    lines.append("  )")
    lines.append("  (nets")
    for idx, net in enumerate(sorted(model.nets, key=lambda n: n.name), start=1):
        lines.append(f'    (net (code "{idx}") (name "{net.name}")')
        for pin in net.pins:
            lines.append(f'      (node (ref "{pin.component}") (pin "{pin.pin}"))')
        lines.append("    )")
    lines.append("  )")
    lines.append(")")
    text = "\n".join(lines) + "\n"
    _log.info(
        "emitted KiCad netlist: %d components, %d nets, hash=%s",
        len(model.components),
        len(model.nets),
        model.content_hash(),
    )
    return text


def emit(model: NetlistModel) -> Result[tuple[str, str], ArbitrationError]:
    """Run the pre-emission checks, then emit ``(kicad_text, content_hash)``.

    The ONE entry point deliverable 2 names: arbitration check first,
    KiCad text second, content hash last (the lockfile pin value).
    """
    checked = check_single_driver(model)
    if checked.is_err:
        return Err(checked.danger_err)
    text = to_kicad_netlist(model)
    return Ok((text, model.content_hash()))


def apply_pinout(net: Net, instance_to_pin: Mapping[str, str]) -> Net:
    """Rewrite ``net``'s pin fields from function-instance ids to real pins.

    WO-35 deliverable 4: the netlist gains real pin numbers where it
    previously carried port names -- a caller that ran
    `regolith.realizer.elec.pinmux.assign_pinmux` passes its
    `PinmuxResult.instance_to_pin()` table here. A `Pin` whose
    ``pin`` field is not a known function-instance id (e.g. a passive's
    plain numeric pad, never pin-mux'd) passes through unchanged --
    this function only resolves pins that ARE mux'd instance ids.
    """
    return net.model_copy(
        update={
            "pins": tuple(
                p.model_copy(update={"pin": instance_to_pin.get(p.pin, p.pin)})
                for p in net.pins
            )
        }
    )


def apply_pinout_to_nets(
    nets: Sequence[Net], instance_to_pin: Mapping[str, str]
) -> tuple[Net, ...]:
    """`apply_pinout` over every net, in source order (AD-6 determinism)."""
    return tuple(apply_pinout(net, instance_to_pin) for net in nets)


def merge_bindings_into_netlist(
    components: Mapping[str, Component], nets: tuple[Net, ...]
) -> NetlistModel:
    """Assemble a :class:`NetlistModel` from bound component refs + nets.

    Thin convenience: a caller that already ran
    `regolith.realizer.elec.binding.bind_all` builds ``components`` by
    ref, and this just packages them with the design's net list.
    """
    return NetlistModel(components=tuple(components.values()), nets=nets)
