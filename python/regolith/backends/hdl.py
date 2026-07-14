"""The HDL manufacturing package: verified build products for a digital
design (WO-102 deliverable 2).

The WO-82 `std.hdl` tiers (`hdl.build`/`hdl.sim_assert`/
`hdl.equiv_directed`) already produce evidence through the ordinary
discharge/harness path; nothing here re-runs verilator or ghdl (AD-22 --
no compiler/synthesizer invocation at ship time). This backend only
SERIALIZES what a build already proved: the pinned HDL source set
(``HdlBuildProducts.sources``, caller-supplied like `assemblies`/
`opt_traces` -- an `hdl_source` payload carries no `PayloadRef` any
obligation cites, so there is nothing to derive from `report.
realized_inputs`) and the per-claim tier report the caller already
discharged (``HdlBuildProducts.tiers``). The verilated build directory
itself is a CACHE (`tempfile`, `verilator_adapter`) -- never packaged.
A synthesis tier that never ran (no synthesis model exists in `std.hdl`
today) is a NAMED absence in the tier report, never a fabricated
netlist; a caller that DOES hold a legitimately synthesized netlist may
attach it (``HdlBuildProducts.netlist``) and it ships unchanged.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Ok, Result

from regolith.backends.debug_taps import TapSet, tap_marker
from regolith.backends.framework import BackendInputs, OutputFile
from regolith.errors import BackendError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The WO-82/D202 claim-kind vocabulary this backend reports over; a
# synthesis-to-netlist claim kind does not exist yet (no model registers
# one), so it is never in this tuple -- its absence in a tier report is
# therefore an honest "no such tier" rather than a probed-and-missing
# tool.
KNOWN_TIER_KINDS = ("hdl.build", "hdl.sim_assert", "hdl.equiv_directed")


class HdlSourceFile(BaseModel):
    """One pinned HDL source file: its package-relative filename + bytes."""

    model_config = ConfigDict(frozen=True)

    filename: str
    content: bytes


class HdlTierRow(BaseModel):
    """One discharged `std.hdl` claim's already-decided evidence.

    Mirrors the shape `ship.si_rows_from_report` extracts for the `si`
    drawing track -- this backend never recomputes a verdict, it only
    serializes the caller-supplied evidence fields (regolith/07 sec. 6).
    """

    model_config = ConfigDict(frozen=True)

    claim: str = Field(description="The `std.hdl` claim kind, e.g. `hdl.build`.")
    status: str
    model_id: str
    value: float
    margin: float
    tool: str
    tool_version: str | None = None


class HdlBuildProducts(BaseModel):
    """One subject's shippable HDL package content: source set + tier report.

    ``netlist``/``netlist_filename`` are ``None`` unless a synthesis
    tier legitimately produced one (no such tier exists in this repo
    today -- see module docstring); never invented here.
    """

    model_config = ConfigDict(frozen=True)

    sources: tuple[HdlSourceFile, ...] = ()
    tiers: tuple[HdlTierRow, ...] = ()
    netlist: bytes | None = None
    netlist_filename: str | None = None


def _source_manifest(products: HdlBuildProducts) -> bytes:
    rows = [
        {
            "filename": src.filename,
            "sha256": hashlib.sha256(src.content).hexdigest(),
            "bytes": len(src.content),
        }
        for src in sorted(products.sources, key=lambda s: s.filename)
    ]
    payload = json.dumps(
        {"sources": rows}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return payload.encode("ascii")


def _tier_report(products: HdlBuildProducts) -> bytes:
    present = {row.claim for row in products.tiers}
    rows = [
        {
            "claim": row.claim,
            "status": row.status,
            "model_id": row.model_id,
            "value": row.value,
            "margin": row.margin,
            "tool": row.tool,
            "tool_version": row.tool_version,
        }
        for row in sorted(products.tiers, key=lambda r: r.claim)
    ]
    absent = [
        {
            "claim": kind,
            "reason": "no evidence supplied for this claim kind on this subject",
        }
        for kind in KNOWN_TIER_KINDS
        if kind not in present
    ]
    netlist = (
        {"filename": products.netlist_filename, "present": True}
        if products.netlist is not None
        else {
            "present": False,
            "reason": (
                "no synthesis-to-netlist model exists in std.hdl (WO-82/D202) "
                "-- hdl.build/hdl.sim_assert/hdl.equiv_directed are lint/sim/"
                "equivalence tiers only; a netlist ships only when a caller "
                "supplies one a synthesis tier legitimately produced"
            ),
        }
    )
    payload = json.dumps(
        {"tiers": rows, "absent_tiers": absent, "netlist": netlist},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return payload.encode("ascii")


def _sanitize_verilog_ident(name: str) -> str:
    """A Verilog-legal identifier for a scope-qualified target path
    (dots and any other non-word character become underscores)."""
    ident = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return ident if ident and not ident[0].isdigit() else f"_{ident}"


def debug_tap_module(tap_set: TapSet, debug_pins: tuple[str, ...]) -> str:
    """Render the generated ``debug_taps.v`` tap module (WO-125
    deliverable 6, charter 40 sec. 1): tapped internal signals routed
    to the DECLARED debug pins, in channel order.

    Capacity is the declared-pin count: a tap beyond it is a NAMED
    absence in the module's trailing comment block (charter 40 sec. 5
    -- never a silent drop; the tap map records the same absence).
    Each routed channel carries the INV-32 ``REGOLITH-TAP`` marker.
    """
    routed = list(zip(tap_set.taps, debug_pins, strict=False))
    lines = [
        "// generated by regolith ship --emit-profile debug "
        "(WO-125, charter 40 sec. 1)",
        "// routes tapped internal signals to the design's declared "
        "debug pins",
        "module regolith_debug_taps (",
    ]
    ports: list[str] = []
    for tap, pin in routed:
        tap_port = f"tap_ch{tap.channel}_{_sanitize_verilog_ident(tap.target_path)}"
        ports.append(
            f"    // {tap_marker(tap.channel, tap.target_path)}\n"
            f"    input  wire {tap_port},  // {tap.kind} -- {tap.why}\n"
            f"    output wire {pin}"
        )
    lines.append(",\n".join(ports))
    lines.append(");")
    for tap, pin in routed:
        tap_port = f"tap_ch{tap.channel}_{_sanitize_verilog_ident(tap.target_path)}"
        lines.append(f"    assign {pin} = {tap_port};")
    lines.append("endmodule")
    dropped = tap_set.taps[len(debug_pins) :]
    if dropped:
        lines.append("")
        lines.append(
            "// NAMED ABSENCES (charter 40 sec. 5): taps with no spare "
            "declared debug pin --"
        )
        for tap in dropped:
            lines.append(
                f"// unrouted: ch={tap.channel} target={tap.target_path} "
                f"reason=no_spare_debug_pin"
            )
    lines.append("")
    return "\n".join(lines)


class HdlBackend:
    """Produces the HDL manufacturing package: source set + tier report
    (+ any legitimately-synthesized netlist) per subject in
    ``BackendInputs.hdl``.
    """

    def produce(
        self, inputs: BackendInputs
    ) -> Result[tuple[OutputFile, ...], BackendError]:
        """Emit ``hdl/<subject>/src/*``, ``source_manifest.json``,
        ``tier_report.json``, and ``netlist.*`` when one was supplied.
        """
        files: list[OutputFile] = []
        for subject, products in sorted(inputs.hdl.items()):
            base = f"hdl/{subject}"
            for src in products.sources:
                files.append(OutputFile.of(f"{base}/src/{src.filename}", src.content))
            # WO-125 (charter 40 sec. 1): the debug profile's generated
            # tap module, routed to the subject's DECLARED debug pins;
            # no declaration is an honest named absence (sec. 5), never
            # a silent drop. Release ships never reach either branch
            # (`inputs.debug_taps` is None then, by construction).
            if inputs.debug_taps is not None:
                pins = inputs.hdl_debug_pins.get(subject, ())
                if pins:
                    files.append(
                        OutputFile.of(
                            f"{base}/src/debug_taps.v",
                            debug_tap_module(inputs.debug_taps, pins).encode(
                                "ascii"
                            ),
                        )
                    )
                    _log.info(
                        "hdl backend: debug_taps.v for %s (%d pin(s))",
                        subject,
                        len(pins),
                    )
                else:
                    absence = json.dumps(
                        {
                            "present": False,
                            "reason": (
                                "no declared debug pins for this subject "
                                '(ship spec "debug".hdl_debug_pins) -- the '
                                "tap module is a named absence, never an "
                                "invented pin (charter 40 secs. 1, 5)"
                            ),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    )
                    files.append(
                        OutputFile.of(
                            f"{base}/debug_taps_absent.json",
                            absence.encode("ascii"),
                        )
                    )
                    _log.info(
                        "hdl backend: no declared debug pins for %s -- "
                        "named absence emitted",
                        subject,
                    )
            files.append(
                OutputFile.of(
                    f"{base}/source_manifest.json", _source_manifest(products)
                )
            )
            files.append(
                OutputFile.of(f"{base}/tier_report.json", _tier_report(products))
            )
            if products.netlist is not None:
                name = products.netlist_filename or "netlist.v"
                files.append(OutputFile.of(f"{base}/{name}", products.netlist))
        _log.info("hdl backend: emitted %d file(s)", len(files))
        return Ok(tuple(files))
