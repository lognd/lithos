"""Post-route extraction surface (WO-24 deliverable 4).

Shapes layout-dependent measurements (net lengths, copper areas) as
model-pack inputs so a claim like IPC-2221 current capacity can
discharge once a board is placed and routed. Extracting these numbers
from a real `.kicad_pcb` needs the `pcbnew` python API, which this
sandbox does not have (`import pcbnew` -> ``ModuleNotFoundError``,
verified alongside the `kicad-cli` cut in :mod:`regolith.realizer.
elec.kicad`); :func:`extract_from_pcb` is therefore an honest
``Err(ToolUnavailable)`` stub -- the SHAPE callers build against, not a
faked measurement. Full SI extraction beyond this surface stays a
later pack per the WO.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Result

from regolith.harness.quantity import Interval
from regolith.logging_setup import get_logger
from regolith.realizer.elec.errors import ToolUnavailable

_log = get_logger(__name__)

PCBNEW_TOOL = "pcbnew"


class LayoutExtraction(BaseModel):
    """Post-route measurements keyed by net/copper-region name."""

    model_config = ConfigDict(frozen=True)

    net_lengths_mm: Mapping[str, float] = {}
    copper_areas_mm2: Mapping[str, float] = {}


def extract_from_pcb(path: Path) -> Result[LayoutExtraction, ToolUnavailable]:
    """Measure net lengths / copper areas from a routed `.kicad_pcb`.

    STUB (documented cut, reopen criterion: `pcbnew` importable in the
    execution environment): the real body needs the pcbnew python API
    to walk tracks/zones; faking numbers here would be worse than an
    honest gap, so this always returns the tool-unavailable value.
    """
    _log.warning(
        "extract_from_pcb(%s): pcbnew unavailable -- honest cut, no fake measurement",
        path,
    )
    return Err(
        ToolUnavailable(tool=PCBNEW_TOOL, message="pcbnew python API not installed")
    )


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
