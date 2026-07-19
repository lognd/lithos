"""Top-level orchestration (deliverable 6): design -> content-addressed generated tree.

INV-10 shape: the same lockfile (the same :class:`FirmwareDesign`)
produces a byte-identical generated tree, twice -- ``realize_firmware``
is a pure function of its input, no clock/random/filesystem-order
dependence. INV-21: every generated symbol traces to a lockfile cause
(the contract header's provenance comments); this module does not add
that guarantee, it composes the pieces (:mod:`contract`, :mod:`bsp`,
:mod:`linker`, :mod:`bindings`) that already hold it individually.

The generated tree hash feeds the ship manifest (WO-25 backend rules)
exactly like any other realized artifact -- this WO stops at producing
:class:`FirmwareTree`; WO-25 consumes its ``content_hash``.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.realizer.firmware import bindings, bsp, contract, linker
from regolith.realizer.firmware.contract import FirmwareDesign
from regolith.realizer.firmware.errors import (
    InterruptCapabilityMissing,
    PartitionOverlap,
    UnknownFamily,
)

_log = get_logger(__name__)

FirmwareError = UnknownFamily | InterruptCapabilityMissing | PartitionOverlap


# frob:doc docs/modules/py-realizer.md#firmware-realize
class FirmwareTree(BaseModel):
    """The full generated output: `{filename: content}` plus its content address."""

    model_config = ConfigDict(frozen=True)

    files: dict[str, str]

    # frob:doc docs/modules/py-realizer.md#firmware-realize
    def content_hash(self) -> str:
        """A sha256 content address over the canonical JSON form (AD-6 style).

        Mirrors `realizer.elec.netlist.NetlistModel.content_hash`: sorted
        keys, no whitespace, ASCII -- so two calls over the same
        `FirmwareDesign` are byte-identical (INV-10).
        """
        canonical = json.dumps(self.files, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        return f"sha256:{digest}"


# frob:doc docs/modules/py-realizer.md#firmware-realize
def realize_firmware(
    design: FirmwareDesign, *, emit_rust_sys: bool = False
) -> Result[FirmwareTree, FirmwareError]:
    """Generate the full firmware tree: header + BSP + linker (+ bindings).

    Fails honest-indeterminate on the first blocking fact (unknown
    family, missing interrupt capability, or overlapping partitions)
    -- never partially emits a tree that silently drops a symbol.
    """
    overlap = linker.check_partition_overlap(design)
    if overlap.is_err:
        return Err(overlap.danger_err)

    bsp_result = bsp.generate_bsp(design)
    if bsp_result.is_err:
        return Err(bsp_result.danger_err)
    bsp_files = bsp_result.danger_ok

    files: dict[str, str] = {
        f"{design.name}_contract.h": contract.generate_contract_header(design),
        **bsp_files,
        f"{design.name}.ld": linker.generate_linker_script(design),
        "Makefile.fragment": linker.generate_build_fragment(design),
    }
    if emit_rust_sys:
        files[f"{design.name}_contract_sys.rs"] = bindings.generate_rust_sys_binding(
            design
        )

    tree = FirmwareTree(files=files)
    _log.info(
        "realized firmware tree for %s: %d files, hash=%s",
        design.name,
        len(files),
        tree.content_hash(),
    )
    return Ok(tree)
