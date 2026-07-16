"""Generates `stdlib/std.fluid/records/gas_cp_glenn.toml` (WO-138,
D258.1/F158 GAP c2) from the committed NASA Glenn coefficient table
`tools/stdlib/data/nasa_glenn_cp.toml` (WO-66/AD-34 pattern).

Representation class (D258 ruling 1): COEFFICIENT ROW. NASA/TP-2002-
211556 itself publishes these 7 numbers per species/T-range as the
species' thermodynamic representation -- committing them is
transcription, not a fit this package invents. The starter set is air
constituents (N2, O2, Ar) + CO2 + H2O(g), low-temperature range
(200-1000 K) only, per the WO's deliverable 3.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.stdlib.render import render_records_file

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = REPO_ROOT / "tools" / "stdlib" / "data" / "nasa_glenn_cp.toml"
OUT_FILE = REPO_ROOT / "stdlib" / "std.fluid" / "records" / "gas_cp_glenn.toml"

_REFERENCE = (
    "McBride, B. J., Zehe, M. J., and Gordon, S., 'NASA Glenn "
    "Coefficients for Calculating Thermodynamic Properties of "
    "Individual Species', NASA/TP-2002-211556, Sept 2002 (public "
    "domain, US government work); 7-term cp/R polynomial, low-"
    "temperature range (200-1000 K); coefficient values transcribed "
    "from the NASA CEA thermodynamic database (thermo.inp) the TP "
    "documents the format of"
)

_COEFF_KEYS = ("a1", "a2", "a3", "a4", "a5", "a6", "a7", "b1", "b2")


def _rows(data: dict) -> list[dict]:
    rows = []
    for species, entry in data.items():
        row = {"key": species, "species": species.upper()}
        row["molar_mass_kg_mol"] = entry["molar_mass_kg_mol"]
        row["t_min_k"] = entry["t_min_k"]
        row["t_max_k"] = entry["t_max_k"]
        for coeff in _COEFF_KEYS:
            row[coeff] = entry[coeff]
        row["evidence"] = {
            "method": "catalog",
            "trust_tier": "community",
            "reference": _REFERENCE,
        }
        rows.append(row)
    return sorted(rows, key=lambda r: r["key"])


def generate() -> dict[str, str]:
    with DATA_FILE.open("rb") as f:
        data = tomllib.load(f)
    rows = _rows(data)
    content = render_records_file(
        script="tools/stdlib/gen_nasa_glenn_cp.py",
        source="tools/stdlib/data/nasa_glenn_cp.toml",
        header_comment=(
            "# NASA Glenn ideal-gas cp/R polynomial coefficients (WO-138, "
            "D258.1/F158 GAP c2): COEFFICIENT ROW representation "
            "(D258 ruling 1) -- transcribed verbatim from NASA/TP-2002-"
            "211556, never a fit this package invents. "
            "cp/R = a1*T^-2 + a2*T^-1 + a3 + a4*T + a5*T^2 + a6*T^3 + "
            "a7*T^4, low-temperature range (200-1000 K) only."
        ),
        kind="gas_cp_glenn",
        rows=rows,
    )
    return {str(OUT_FILE): content}


def main() -> None:
    for path_str, content in generate().items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="ascii")
        print(f"wrote {path.relative_to(REPO_ROOT)} ({content.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
