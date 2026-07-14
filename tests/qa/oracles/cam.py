"""Independent CAM-check oracle (D226; the std.cam family).

A FRESH minimal RS-274 (Fanuc-dialect) position tracker plus the four
check arithmetics, written from the standard G-code semantics (modal
group-1 motion, absolute positioning, per-axis carry-forward) and the
cam charter's check definitions -- never from the harness parser's
code. Consumes the RAW plan bytes + record JSON a captured discharge
resolved (plain dicts, no regolith classes).

Checks (each returns the claim's value -- an excess vs 0, upper
bound):

* envelope -- every commanded position within machine travel, with
  tool stickout extending the Z floor downward; worst per-axis excess.
* collision_coarse -- no rapid (G0) endpoint inside the uncut-stock
  box below its top face; excess = stock_top - z at the first hit.
* removal -- the deepest cutting Z vs the finished floor:
  ``|min_cut_z - finished.z_min|`` (undercut or overcut both count).
* coverage -- every declared feature's touch zone reached by some
  cutting move; excess = the number of missed features.
"""

from __future__ import annotations

import json
import re

_WORD = re.compile(r"([A-Za-z])\s*(-?[0-9]*\.?[0-9]+)")
_COMMENT = re.compile(r"\(([^)]*)\)|;.*$")

# Positions are tracked for the three linear axes only (3-axis mill).
_AXES = ("X", "Y", "Z")


def parse_moves(raw: bytes) -> list[dict]:
    """Track commanded positions through a Fanuc-dialect plan.

    Returns one record per motion line: ``{kind, x, y, z}`` with
    ``kind`` in ``rapid``/``cut`` (G0 vs G1/G2/G3, modal) and ``None``
    for any axis never commanded yet (no phantom zeros). Raises
    ``ValueError`` on constructs outside the supported subset (canned
    cycles, incremental mode) -- the model under test treats those as
    indeterminate, so a QA sample containing them is a sampling error,
    not a margin to compare.
    """
    text = raw.decode("utf-8", errors="replace")
    moves: list[dict] = []
    pos: dict[str, float | None] = dict.fromkeys(_AXES)
    modal: str | None = None
    for line in text.splitlines():
        stripped = _COMMENT.sub(" ", line).strip()
        if not stripped:
            continue
        words = [(m.group(1).upper(), m.group(2)) for m in _WORD.finditer(stripped)]
        motion: str | None = None
        for letter, number in words:
            if letter != "G":
                continue
            g = number.split(".")[0].lstrip("0") or "0"
            if g in {
                "73",
                "74",
                "76",
                "81",
                "82",
                "83",
                "84",
                "85",
                "86",
                "87",
                "88",
                "89",
            }:
                raise ValueError(f"canned cycle G{number} outside the oracle subset")
            if g == "91":
                raise ValueError("incremental mode (G91) outside the oracle subset")
            if g == "0":
                motion = "rapid"
            elif g in {"1", "2", "3"}:
                motion = "cut"
        axis_words = {
            letter: float(number) for letter, number in words if letter in _AXES
        }
        has_feed = any(letter in ("F", "E") for letter, _ in words)
        if motion is not None:
            modal = motion
        elif axis_words and modal is not None:
            motion = modal
        for axis, value in axis_words.items():
            pos[axis] = value
        if motion is not None and (axis_words or has_feed):
            moves.append({"kind": motion, "x": pos["X"], "y": pos["Y"], "z": pos["Z"]})
    return moves


def envelope_excess(payloads: dict[str, bytes]) -> float:
    """Worst commanded-position overrun of the machine travel (mm)."""
    moves = parse_moves(payloads["plan"])
    machine = json.loads(payloads["cam_machine"])
    travel = machine["travel"]
    stickout = 0.0
    if "cam_tooling" in payloads:
        stickout = json.loads(payloads["cam_tooling"])["stickout_mm"]
    worst = 0.0
    for move in moves:
        for axis, lo, hi in (
            ("x", travel["x_min"], travel["x_max"]),
            ("y", travel["y_min"], travel["y_max"]),
            ("z", travel["z_min"] - stickout, travel["z_max"]),
        ):
            value = move[axis]
            if value is None:
                continue
            worst = max(worst, lo - value, value - hi)
    return worst


def collision_excess(payloads: dict[str, bytes]) -> float:
    """First rapid-into-stock penetration depth (mm), else zero."""
    moves = parse_moves(payloads["plan"])
    stock = json.loads(payloads["cam_target"])["stock"]
    for move in moves:
        if move["kind"] != "rapid":
            continue
        x, y, z = move["x"], move["y"], move["z"]
        if x is None or y is None or z is None:
            continue
        if z >= stock["z_max"]:
            continue
        inside = (
            stock["x_min"] <= x <= stock["x_max"]
            and stock["y_min"] <= y <= stock["y_max"]
            and stock["z_min"] <= z <= stock["z_max"]
        )
        if inside:
            return stock["z_max"] - z
    return 0.0


def removal_excess(payloads: dict[str, bytes]) -> float:
    """|deepest cutting Z - finished floor| (mm); under/overcut both."""
    moves = parse_moves(payloads["plan"])
    finished = json.loads(payloads["cam_target"])["finished"]
    cut_zs = [m["z"] for m in moves if m["kind"] != "rapid" and m["z"] is not None]
    assert cut_zs, "a removal sample with no cutting moves was indeterminate upstream"
    depth_error = min(cut_zs) - finished["z_min"]
    return abs(depth_error) if abs(depth_error) > 0.0 else 0.0


def coverage_excess(payloads: dict[str, bytes]) -> float:
    """The number of declared features no cutting move touches."""
    moves = parse_moves(payloads["plan"])
    target = json.loads(payloads["cam_target"])
    cutting = [m for m in moves if m["kind"] != "rapid"]
    missing = 0
    for feature in target.get("features", []):
        zone = feature["touch_zone"]
        touched = any(
            m["x"] is not None
            and m["y"] is not None
            and m["z"] is not None
            and zone["x_min"] <= m["x"] <= zone["x_max"]
            and zone["y_min"] <= m["y"] <= zone["y_max"]
            and zone["z_min"] <= m["z"] <= zone["z_max"]
            for m in cutting
        )
        if not touched:
            missing += 1
    return float(missing)


def parse_clean(payloads: dict[str, bytes]) -> float:
    """``cam.parse``'s value: 0.0 for a plan the subset fully parses.

    ``parse_moves`` raises on out-of-subset constructs, so reaching the
    return IS the recomputation (the model discharges value 0.0 only
    for a cleanly parsed plan).
    """
    parse_moves(payloads["plan"])
    return 0.0
