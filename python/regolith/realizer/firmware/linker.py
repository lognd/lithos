"""Linker memory map + build fragment (deliverable 3).

The image's declared `partitions:` (cuprite/05 sec. 4) emit the linker
script; a Make fragment builds BSP + user sources into the image. The
built image re-enters via the EXISTING `image`/`extern` hash-pin
machinery (fit/stack/WCET/boot claims verify it unchanged) -- this
module adds zero claim vocabulary, per the WO's own instruction.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.realizer.firmware.contract import (
    FirmwareDesign,
    PartitionDecl,
    c_identifier,
)
from regolith.realizer.firmware.errors import PartitionOverlap

_log = get_logger(__name__)

_BANNER = (
    "/* GENERATED FILE -- DO NOT EDIT. Produced by regolith.realizer.firmware\n"
    " * (WO-37) from the image's declared partitions:. */\n"
)


def check_partition_overlap(
    design: FirmwareDesign,
) -> Result[None, PartitionOverlap]:
    """First pair of partitions whose address ranges overlap, or Ok.

    Region-ownership discipline (cuprite/05 sec. 4): "two DMA buffers
    or partitions contesting a range is a borrow conflict, not a
    heisenbug." Checked per declared region.
    """
    by_region: dict[str, list[PartitionDecl]] = {}
    for p in design.partitions:
        by_region.setdefault(p.region, []).append(p)
    for region, parts in by_region.items():
        ordered = sorted(parts, key=lambda p: (p.start, p.name))
        for first, second in zip(ordered, ordered[1:], strict=False):
            if first.end > second.start:
                _log.warning(
                    "partition overlap in %s: %s and %s",
                    region,
                    first.name,
                    second.name,
                )
                return Err(
                    PartitionOverlap(
                        region=region,
                        first=first.name,
                        second=second.name,
                        message=(
                            f"partitions {first.name!r} and {second.name!r} in region "
                            f"{region!r} overlap: [{first.start}, {first.end}) vs "
                            f"[{second.start}, {second.end})"
                        ),
                    )
                )
    return Ok(None)


def generate_linker_script(design: FirmwareDesign) -> str:
    """A `MEMORY {}` linker script section, one entry per declared partition."""
    lines: list[str] = [_BANNER, "MEMORY", "{"]
    for p in sorted(design.partitions, key=lambda p: (p.region, p.start, p.name)):
        ident = c_identifier(p.name)
        lines.append(
            f"    {ident} ({p.region}) : ORIGIN = 0x{p.start:08X}, LENGTH = {p.size}"
        )
    lines.append("}")
    lines.append("")
    _log.info(
        "generated linker script for %s: %d partitions",
        design.name,
        len(design.partitions),
    )
    return "\n".join(lines)


def generate_build_fragment(design: FirmwareDesign) -> str:
    """A Make fragment building the BSP + user sources into `<design>.elf`."""
    lines = [
        _BANNER,
        f"{design.name}_SRCS := {design.name}_bsp.c {design.name}_isr.c",
        f"{design.name}_LDSCRIPT := {design.name}.ld",
        "",
        f"{design.name}.elf: $({design.name}_SRCS) $({design.name}_LDSCRIPT)",
        f"\t$(CC) -T $({design.name}_LDSCRIPT) -o $@ $({design.name}_SRCS)",
        "",
    ]
    return "\n".join(lines)
