"""Independent DFM manufacturability oracle (D226; the WO-110 channel).

Recomputes the ``mfg.manufacturable`` excess from the RAW payload JSON
a captured discharge consumed (part / machine / tool-set records as
plain dicts -- no regolith record classes), fresh from the check
definitions the design log dispositioned (F132/D232.2):

* stock fit -- the realized part's bounding-box EXTENTS must fit the
  machine's travel extents, axis-order preserved; the excess is the
  worst per-axis overhang.
* tool fit -- every hole feature must be producible by SOME declared
  tool: a cutter no larger than the hole (a tool cannot cut a feature
  smaller than itself) that reaches the hole's depth within its
  stickout. Per hole the BEST tool governs (exists-quantifier); per
  part the WORST hole governs (forall-quantifier). No hole features =
  vacuous pass; the true (negative) margin is reported, not a clamped
  zero.

The claim's value is the worst excess over both checks (upper bound
vs 0: any positive excess is a violation).
"""

from __future__ import annotations

import json


def _extents(box: dict) -> tuple[float, float, float]:
    """(dx, dy, dz) extents of an axis-aligned box record."""
    return (
        box["x_max"] - box["x_min"],
        box["y_max"] - box["y_min"],
        box["z_max"] - box["z_min"],
    )


def manufacturable_excess(payloads: dict[str, bytes]) -> float:
    """The worst stock/tool-fit excess (mm) from the raw payload JSON."""
    part = json.loads(payloads["dfm_part"])
    machine = json.loads(payloads["dfm_machine"])
    toolset = json.loads(payloads["dfm_tools"])

    part_ext = _extents(part["bbox_mm"])
    travel_ext = _extents(machine["travel"])
    stock_excess = max(p - t for p, t in zip(part_ext, travel_ext, strict=True))

    tools = toolset["tools"]
    features = part.get("features", [])
    if not features:
        tool_excess = 0.0
    else:
        assert tools, "empty tool set must have been indeterminate upstream"
        tool_excess = float("-inf")
        for feat in features:
            best = float("inf")
            for tool in tools:
                terms = [tool["diameter_mm"] - feat["dia_mm"]]
                if feat.get("depth_mm") is not None:
                    terms.append(feat["depth_mm"] - tool["stickout_mm"])
                best = min(best, max(terms))
            tool_excess = max(tool_excess, best)

    return max(stock_excess, tool_excess)
