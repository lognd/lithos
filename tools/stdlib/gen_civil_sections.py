"""Generates `stdlib/std.civil/records/sections_channels_angles.toml`
from the committed AISC C/L dimension table
`tools/stdlib/data/aisc_channels_angles.toml` (WO-66). ADDITIVE ONLY:
this is a NEW file beside the hand-authored `sections.toml` WO-60
landed (16-member w_shape + 28-member hss_square) -- it never touches
or renames an existing `section` row (WO-66 acceptance criterion:
"zero existing-record renames").
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.stdlib.render import render_records_file

# frob:doc docs/modules/tools.md#stdlib-gen-civil-sections
REPO_ROOT = Path(__file__).resolve().parents[2]
# frob:doc docs/modules/tools.md#stdlib-gen-civil-sections
DATA_FILE = REPO_ROOT / "tools" / "stdlib" / "data" / "aisc_channels_angles.toml"
# frob:doc docs/modules/tools.md#stdlib-gen-civil-sections
OUT_FILE = (
    REPO_ROOT / "stdlib" / "std.civil" / "records" / "sections_channels_angles.toml"
)

_REFERENCE = (
    "AISC Steel Construction Manual 16th ed. / Shapes Database v16.0 "
    "(same edition WO-60's w_shape/hss_square families cite), imperial "
    "source dimensions converted to SI to match the existing "
    "sections.toml unit convention"
)


def _channels(data: dict) -> list[dict]:
    rows = []
    for entry in data["channel"]:
        rows.append(
            {
                "key": f"c_{entry['designation']}",
                "family": "steel_channel",
                "depth_mm": entry["depth_mm"],
                "flange_width_mm": entry["flange_width_mm"],
                "weight_kg_per_m": entry["weight_kg_per_m"],
                "area_mm2": entry["area_mm2"],
                "i_mm4": entry["ix_mm4"],
                "s_mm3": entry["sx_mm3"],
                "evidence": {
                    "method": "catalog",
                    "trust_tier": "community",
                    "reference": _REFERENCE,
                },
            }
        )
    return sorted(rows, key=lambda r: r["key"])


def _angles(data: dict) -> list[dict]:
    rows = []
    for entry in data["angle"]:
        rows.append(
            {
                "key": f"l_{entry['designation']}",
                "family": "steel_angle",
                "leg_mm": entry["leg_mm"],
                "thickness_mm": entry["thickness_mm"],
                "weight_kg_per_m": entry["weight_kg_per_m"],
                "area_mm2": entry["area_mm2"],
                "evidence": {
                    "method": "catalog",
                    "trust_tier": "community",
                    "reference": _REFERENCE,
                },
            }
        )
    return sorted(rows, key=lambda r: r["key"])


# frob:doc docs/modules/tools.md#stdlib-gen-civil-sections
def generate() -> dict[str, str]:
    with DATA_FILE.open("rb") as f:
        data = tomllib.load(f)
    rows = _channels(data) + _angles(data)
    content = render_records_file(
        script="tools/stdlib/gen_civil_sections.py",
        source="tools/stdlib/data/aisc_channels_angles.toml",
        header_comment=(
            "# C (channel) and L (angle) steel section families, "
            "generated (WO-66 D174); additive beside sections.toml's "
            "hand-authored w_shape/hss_square families, no existing "
            "row touched."
        ),
        kind="section",
        rows=rows,
    )
    return {str(OUT_FILE): content}


# frob:doc docs/modules/tools.md#stdlib-gen-civil-sections
# frob:waive TEST001 reason="CLI entry point; see tests/tools/test_stdlib_gen_drift.py"
def main() -> None:
    for path_str, content in generate().items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="ascii")
        print(f"wrote {path.relative_to(REPO_ROOT)} ({content.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
