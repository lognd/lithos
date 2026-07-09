"""Post-route extraction surface (WO-24 deliverable 4).

Shapes layout-dependent measurements (net lengths, copper areas) as
model-pack inputs so a claim like IPC-2221 current capacity can
discharge once a board is placed and routed. Extracting these numbers
from a real `.kicad_pcb` needs the `pcbnew` python API.

ENVIRONMENT NOTE (updated WO-24 close-out; the original sandbox cut is
LIFTED on a host where `make install`'s `kicad-link` step succeeded --
`regolith.realizer.elec.kicad.pcbnew_importable()` reports the same
gate this module uses): :func:`extract_from_pcb` walks the board's
tracks and copper zones for real when `pcbnew` is importable. On a
`pcbnew`-less host it remains an honest ``Err(ToolUnavailable)`` --
never a faked measurement.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.harness.quantity import Interval
from regolith.logging_setup import get_logger
from regolith.realizer.elec.errors import LayoutFailed, ToolUnavailable

_log = get_logger(__name__)

PCBNEW_TOOL = "pcbnew"


class LayoutExtraction(BaseModel):
    """Post-route measurements keyed by net/copper-region name."""

    model_config = ConfigDict(frozen=True)

    net_lengths_mm: Mapping[str, float] = {}
    copper_areas_mm2: Mapping[str, float] = {}


def _walk_board(path: Path) -> LayoutExtraction:
    """Real `pcbnew` walk: per-net track length sums + per-zone areas.

    A board with no tracks/zones (e.g. the outline-only board
    `kicad_wrapper.py` produces, WO-24's own honest "unrouted" case)
    legitimately yields empty maps -- this is not a fallback path, it
    is the correct measurement of an unrouted board.
    """
    import pcbnew

    board = pcbnew.LoadBoard(str(path))
    net_lengths_mm: dict[str, float] = {}
    for track in board.GetTracks():
        net_name = track.GetNetname()
        length_mm = pcbnew.ToMM(track.GetLength())
        net_lengths_mm[net_name] = net_lengths_mm.get(net_name, 0.0) + length_mm
    copper_areas_mm2: dict[str, float] = {}
    for zone in board.Zones():
        name = zone.GetZoneName() or zone.GetNetname() or f"zone_{zone.GetId()}"
        # `GetFilledArea()` is in IU^2 (nm^2, KiCad 7+); `pcbnew.ToMM`
        # only converts a LENGTH, so an area needs the length scale
        # squared -- never double-apply `ToMM` (that scales wrongly).
        length_scale_mm_per_iu = pcbnew.ToMM(1)
        area_mm2 = zone.GetFilledArea() * (length_scale_mm_per_iu**2)
        copper_areas_mm2[name] = copper_areas_mm2.get(name, 0.0) + area_mm2
    return LayoutExtraction(
        net_lengths_mm=net_lengths_mm, copper_areas_mm2=copper_areas_mm2
    )


def extract_from_pcb(
    path: Path,
) -> Result[LayoutExtraction, ToolUnavailable | LayoutFailed]:
    """Measure net lengths / copper areas from a routed `.kicad_pcb`.

    Real when `pcbnew` is importable (walks tracks/zones); an honest
    ``Err(ToolUnavailable)`` on a `pcbnew`-less host -- never a faked
    measurement either way. A missing/unreadable file is a distinct
    honest ``Err(LayoutFailed)`` (an infrastructure gap, not a tool
    absence) -- checked BEFORE the `pcbnew` call so a bad path never
    depends on how the vendored C++ binding happens to fail.
    """
    try:
        import pcbnew  # noqa: F401  (import-probe only, see below)
    except ImportError:
        _log.warning(
            "extract_from_pcb(%s): pcbnew unavailable -- honest cut, no fake "
            "measurement",
            path,
        )
        return Err(
            ToolUnavailable(tool=PCBNEW_TOOL, message="pcbnew python API not installed")
        )
    if not path.is_file():
        _log.warning("extract_from_pcb(%s): file does not exist", path)
        return Err(LayoutFailed(stage="extract", message="file does not exist"))
    extraction = _walk_board(path)
    _log.info(
        "extract_from_pcb(%s): %d net(s), %d zone(s) measured",
        path,
        len(extraction.net_lengths_mm),
        len(extraction.copper_areas_mm2),
    )
    return Ok(extraction)


def to_discharge_inputs(
    extraction: LayoutExtraction, net: str
) -> Mapping[str, Interval]:
    """Shape one net's extracted length as a `DischargeRequest.inputs` entry.

    The port name a current-capacity model would require
    (`net_length_mm`); a point interval since the measurement is exact
    once extracted.
    """
    length = extraction.net_lengths_mm.get(net, 0.0)
    return {"net_length_mm": Interval(lo=length, hi=length)}
