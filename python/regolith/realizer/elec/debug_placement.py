"""Debug-profile tap placements (WO-125 deliverable 4, charter 40 sec. 1).

The layout-request seam's debug half: given an allocated
:class:`~regolith.backends.debug_taps.TapSet` and THE tap-header
pinout record (charter 40 sec. 4), derive the board augmentation DATA
-- one placed tap header plus one labeled test point per allocated tap
-- as the wire ``Placement`` shape REUSED as emission-layer data (no
schema change, D239) plus silkscreen channel-label rows for the WO-124
renderer.

Honesty (D224): the positions below are a placement DECISION this
seam makes and DECLARES (``placement_rule``, carried verbatim on the
emitted artifact), exactly like any placer's output -- never a
measured/verified geometry claim. WO-124's silkscreen rendering seam
is in flight in parallel and is NOT on this branch: the label rows
land as DATA here and the rendering handoff is a named cross-WO note
(``silkscreen_rendering`` on the emitted JSON + the WO-125 close-out
ledger).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from regolith._schema.models import BoardSide1, Placement
from regolith.backends.debug_taps import TapHeaderRecord, TapSet, tap_marker
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: The test-point pattern record every per-tap pad cites --
#: `stdlib/std.elec/records/dft.toml`'s existing `class="test_point"`
#: row (IPC-2221B-sized probe pad), the same DFT home the header lives in.
# frob:doc docs/modules/py-realizer.md#elec-debug-placement
TEST_POINT_RECORD_KEY = "tp_probe_pad_1mm2"

#: The declared placement rule (emitted verbatim; D224: a decision,
#: named as one). Offsets are from the board-outline origin corner.
# frob:doc docs/modules/py-realizer.md#elec-debug-placement
PLACEMENT_RULE = (
    "deterministic debug-placement rule v1 (WO-125): tap header at "
    "(5.0, 7.5)mm from the board-outline origin corner, rotation 0, "
    "top side; test point for channel N at (5.0 + N*2.54, 2.5)mm, top "
    "side; silkscreen channel label 1.0mm below each test point. A "
    "placement decision declared by the toolchain, not a verified "
    "geometry claim; refined by a real placer when one lands."
)

_HEADER_AT_MM = (5.0, 7.5)
_TP_ROW_Y_MM = 2.5
_TP_START_X_MM = 5.0
_TP_PITCH_MM = 2.54
_LABEL_DROP_MM = 1.0


# frob:doc docs/modules/py-realizer.md#elec-debug-placement
class SilkscreenLabel(BaseModel):
    """One channel-label row for the silkscreen renderer (WO-124 seam):
    pure DATA (text + position + layer), rendered by that WO's landing."""

    model_config = ConfigDict(frozen=True)

    text: str
    at_mm: tuple[float, float]
    layer: str = "F.Silkscreen"
    for_reference: str = ""


# frob:doc docs/modules/py-realizer.md#elec-debug-placement
class TapTestPoint(BaseModel):
    """One allocated tap's probe pad: its placement, channel identity,
    label text, and the INV-32 marker the emitted JSON embeds."""

    model_config = ConfigDict(frozen=True)

    channel: int
    target_path: str
    kind: str
    why: str
    record: str = TEST_POINT_RECORD_KEY
    placement: Placement
    label: str
    marker: str


# frob:doc docs/modules/py-realizer.md#elec-debug-placement
class TapPlacementPlan(BaseModel):
    """The whole board augmentation for one subject: the placed header,
    every test point, the silkscreen label DATA, and the declared rule."""

    model_config = ConfigDict(frozen=True)

    subject: str
    header_record: str
    header_placement: Placement
    test_points: tuple[TapTestPoint, ...]
    silkscreen_labels: tuple[SilkscreenLabel, ...]
    placement_rule: str = PLACEMENT_RULE


# frob:doc docs/modules/py-realizer.md#elec-debug-placement
def derive_tap_placements(
    subject: str,
    tap_set: TapSet,
    header: TapHeaderRecord,
) -> TapPlacementPlan:
    """Place the tap header + one labeled test point per allocated tap.

    Deterministic (AD-6): positions follow :data:`PLACEMENT_RULE`
    verbatim, references are ``J_DBG1``/``TP_DBG<channel>``, and the
    channel order is the tap set's own. The header footprint cites the
    pinout record's connector; each test point cites the DFT
    test-point record.
    """
    header_placement = Placement(
        footprint=f"{header.key} ({header.connector})",
        reference="J_DBG1",
        position_mm=list(_HEADER_AT_MM),
        rotation_deg=0.0,
        side=BoardSide1.top,
    )
    test_points: list[TapTestPoint] = []
    labels: list[SilkscreenLabel] = []
    for tap in tap_set.taps:
        x = _TP_START_X_MM + tap.channel * _TP_PITCH_MM
        label_text = f"CH{tap.channel}"
        reference = f"TP_DBG{tap.channel}"
        test_points.append(
            TapTestPoint(
                channel=tap.channel,
                target_path=tap.target_path,
                kind=tap.kind,
                why=tap.why,
                placement=Placement(
                    footprint=TEST_POINT_RECORD_KEY,
                    reference=reference,
                    position_mm=[x, _TP_ROW_Y_MM],
                    rotation_deg=0.0,
                    side=BoardSide1.top,
                ),
                label=f"{label_text} {tap.target_path}",
                marker=tap_marker(tap.channel, tap.target_path),
            )
        )
        labels.append(
            SilkscreenLabel(
                text=label_text,
                at_mm=(x, _TP_ROW_Y_MM - _LABEL_DROP_MM),
                for_reference=reference,
            )
        )
    plan = TapPlacementPlan(
        subject=subject,
        header_record=header.key,
        header_placement=header_placement,
        test_points=tuple(test_points),
        silkscreen_labels=tuple(labels),
    )
    _log.info(
        "derive_tap_placements: %s -> header %s + %d test point(s)",
        subject,
        header.key,
        len(test_points),
    )
    return plan
