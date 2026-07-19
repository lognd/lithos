"""Generates `stdlib/std.elec/records/e_series.toml` (parametric
passive families) from the committed `tools/stdlib/data/e_series.toml`
table (WO-66, D174). Emits ONE record per series x package x tolerance
(the ratified parametric family shape -- design-log
2026-07-09-cycle-31.md addendum), carrying the value GRID as a field,
never one record per discrete resistor/capacitor part.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.stdlib.render import render_records_file

# frob:doc docs/modules/tools.md#stdlib-gen-eseries
REPO_ROOT = Path(__file__).resolve().parents[2]
# frob:doc docs/modules/tools.md#stdlib-gen-eseries
DATA_FILE = REPO_ROOT / "tools" / "stdlib" / "data" / "e_series.toml"
# frob:doc docs/modules/tools.md#stdlib-gen-eseries
OUT_FILE = REPO_ROOT / "stdlib" / "std.elec" / "records" / "e_series.toml"

_IEC_REF = (
    "IEC 60063:2015 (preferred number series for resistors and "
    "capacitors), the series' own published per-decade value list"
)


# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def _resistor_families(data: dict) -> list[dict]:
    rows = []
    for entry in data["resistor_family"]:
        series_values = data[entry["series"]]
        key = f"resistor_{entry['series']}_{entry['package']}"
        rows.append(
            {
                "key": key,
                "component_class": "resistor",
                "series": entry["series"].upper(),
                "package": entry["package"],
                "decade_values": series_values,
                "decade_min_ohm": entry["decade_min_ohm"],
                "decade_max_ohm": entry["decade_max_ohm"],
                "tolerance_pct": entry["tolerance_pct"],
                "evidence": {
                    "method": "catalog",
                    "trust_tier": "community",
                    "reference": _IEC_REF,
                },
            }
        )
    return sorted(rows, key=lambda r: r["key"])


# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def _capacitor_families(data: dict) -> list[dict]:
    rows = []
    for entry in data["capacitor_family"]:
        series_values = data[entry["series"]]
        dielectric_suffix = entry["dielectric"].lower()
        key = f"capacitor_{entry['series']}_{entry['package']}_{dielectric_suffix}"
        rows.append(
            {
                "key": key,
                "component_class": "capacitor",
                "series": entry["series"].upper(),
                "package": entry["package"],
                "dielectric": entry["dielectric"],
                "decade_values": series_values,
                "decade_min_f": entry["decade_min_f"],
                "decade_max_f": entry["decade_max_f"],
                "tolerance_pct": entry["tolerance_pct"],
                "voltage_max_v": entry["voltage_max_v"],
                "evidence": {
                    "method": "catalog",
                    "trust_tier": "community",
                    "reference": (
                        f"{_IEC_REF}; voltage/dielectric class per common "
                        "MLCC manufacturer general catalog ratings for the "
                        "stated package/dielectric combination"
                    ),
                },
            }
        )
    return sorted(rows, key=lambda r: r["key"])


# frob:doc docs/modules/tools.md#stdlib-gen-eseries
def generate() -> dict[str, str]:
    with DATA_FILE.open("rb") as f:
        data = tomllib.load(f)
    rows = _resistor_families(data) + _capacitor_families(data)
    content = render_records_file(
        script="tools/stdlib/gen_eseries.py",
        source="tools/stdlib/data/e_series.toml",
        header_comment=(
            "# E-series parametric passive families (WO-66, D174): one "
            "record per series x package x tolerance, carrying the "
            "IEC 60063 value grid -- NOT one record per discrete part "
            "(the ratified parametric family shape, design-log "
            "2026-07-09-cycle-31.md addendum)."
        ),
        kind="passive_family",
        rows=rows,
    )
    return {str(OUT_FILE): content}


# frob:doc docs/modules/tools.md#stdlib-gen-eseries
# frob:waive TEST001 reason="CLI entry point; see tests/tools/test_stdlib_gen_drift.py"
# frob:waive TEST005 reason="measured 16.7% branch on 2026-07-19; backfill T-0036"
# frob:waive PERF002 reason="one-shot index/count over a small per-call set"
def main() -> None:
    for path_str, content in generate().items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="ascii")
        print(f"wrote {path.relative_to(REPO_ROOT)} ({content.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
