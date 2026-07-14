"""Independent cost-estimate oracle (D226; the std.cost family).

Recomputes the ``mfg.cost`` value (the worst per-profile total's HIGH
corner) from the RAW ``cost_inputs`` staged-doc JSON a captured
discharge resolved, fresh from the estimating bases toolchain/27
sec. 1.4 defines (plain-dict arithmetic, no regolith classes):

* elec BOM basis -- each BOM line's priceable key (``vendor(<key>)``'s
  inner key, else the leading bare token) priced at its first
  source-order pricing record's best applicable quantity break at the
  profile's quantity basis (one unit per line); unpriced lines are
  exclusions, not zeros.
* civil takeoff basis -- each frame member's length (m) times the
  profile's first per-meter unit-cost record (lo*lo / hi*hi interval
  product).
* overhead markup -- ``subtotal * (markup - 1)`` added when the
  profile's markup is not 1.0.

The value compared is ``max over profiles of total.hi``.
"""

from __future__ import annotations

import json

# Length-unit -> meters (the takeoff basis's recognized length units).
_LENGTH_TO_M = {"m": 1.0, "mm": 1e-3, "cm": 1e-2}


def _item_key(ref: str) -> str:
    """A BOM line's priceable key: ``vendor(<key>)`` inner, else the
    leading bare token."""
    text = ref.strip()
    if text.startswith("vendor(") and text.endswith(")"):
        return text[len("vendor(") : -1].strip()
    parts = text.split()
    return parts[0] if parts else text


def _price_break(pricing: dict, quantity: float) -> dict | None:
    """The best applicable quantity break: the highest ``min_qty`` not
    exceeding the basis quantity."""
    best = None
    for brk in pricing.get("breaks", []):
        if brk["min_qty"] <= quantity and (
            best is None or brk["min_qty"] > best["min_qty"]
        ):
            best = brk
    return best


def _apply_markup(profile: dict, subtotal_hi: float) -> float:
    """The profile total's HIGH corner after the overhead markup line."""
    markup = profile.get("markup", 1.0)
    if markup == 1.0:
        return subtotal_hi
    return subtotal_hi + subtotal_hi * (markup - 1.0)


def _bom_total_hi(doc: dict, profile: dict) -> float:
    """The elec-BOM basis total (high corner) for one profile."""
    subtotal_hi = 0.0
    priced = 0
    for line in doc.get("bom", []):
        item = _item_key(line["ref"])
        record = next(
            (r for r in profile.get("pricing", []) if r["pricing"]["item"] == item),
            None,
        )
        if record is None:
            continue
        brk = _price_break(record["pricing"], profile["quantity"])
        if brk is None:
            continue
        subtotal_hi += brk["unit_price"]["hi"]
        priced += 1
    assert priced, "a discharged BOM estimate must have priced something"
    return _apply_markup(profile, subtotal_hi)


def _takeoff_total_hi(doc: dict, profile: dict) -> float:
    """The civil-takeoff basis total (high corner) for one profile."""
    per_meter = next(
        (
            e
            for e in profile.get("unit_costs", [])
            if e["unit_cost"]["unit_basis"] == "m"
        ),
        None,
    )
    assert per_meter is not None, "a discharged takeoff had a per-meter record"
    uc = per_meter["unit_cost"]["unit_cost"]
    subtotal_hi = 0.0
    for member in doc.get("frame_members", []):
        length = member["length"]
        scale = _LENGTH_TO_M.get(length["unit"])
        if scale is None:
            continue
        subtotal_hi += length["hi"] * scale * uc["hi"]
    return _apply_markup(profile, subtotal_hi)


def cost_value(payloads: dict[str, bytes], *, basis: str) -> float:
    """The ``mfg.cost`` claim value: worst per-profile total, high corner.

    ``basis`` picks the estimating arithmetic (``bom`` or ``takeoff``)
    -- mirroring which estimator model the captured call names.
    """
    doc = json.loads(payloads["cost_inputs"])
    totals = []
    for profile in doc["profiles"]:
        if basis == "takeoff":
            totals.append(_takeoff_total_hi(doc, profile))
        else:
            totals.append(_bom_total_hi(doc, profile))
    assert totals, "a discharged cost estimate had at least one profile"
    return max(totals)
