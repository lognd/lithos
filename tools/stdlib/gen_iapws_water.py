"""Generates `stdlib/std.fluid/records/water_saturation.toml` (WO-138,
D258.1/F158 GAP c1) from the committed IAPWS-IF97 Region 4 (saturation
curve) coefficient table `tools/stdlib/data/iapws_water_saturation.toml`
(WO-66/AD-34 pattern: a deterministic generator over a committed input
table, reviewable diffs, no network at generation time).

Representation class (D258 ruling 1): POINT TABLE. Every row is the
published Eq 30 (IAPWS R7-97(2012)) EVALUATED at one named T -- this
package never re-derives or fits the saturation curve; the equation
and its coefficients are the source's own. Valid range 273.15 K to
647.096 K (Tc); the generation grid never leaves that range, so no
row is an extrapolation.

Scope note (WO-138 close-out, honest partial): only the SATURATION
PRESSURE pv(T) family is generated this dispatch. The companion
rho(T)/mu(T)/cp(T) liquid-water point tables (IF97 Region 1 + the
IAPWS viscosity release) are NOT included -- Region 1's 34-term
gamma-equation coefficient table was not independently sourced and
cross-checked to this session's evidence bar (the same bar applied to
Eq 30 below via the `iapws` package doctest), so shipping placeholder
rho/mu/cp numbers would be exactly the invented-fit D250 forbids.
Named cut, not a silent drop: a future batch widening this record
needs the Region 1 `n`/`I`/`J` coefficient table sourced and
cross-checked the same way, then a sibling `gen_iapws_water_liquid.py`
generator.
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

from tools.stdlib.render import render_records_file

# frob:doc docs/modules/tools.md#stdlib-gen-iapws-water
REPO_ROOT = Path(__file__).resolve().parents[2]
# frob:doc docs/modules/tools.md#stdlib-gen-iapws-water
DATA_FILE = REPO_ROOT / "tools" / "stdlib" / "data" / "iapws_water_saturation.toml"
# frob:doc docs/modules/tools.md#stdlib-gen-iapws-water
OUT_FILE = REPO_ROOT / "stdlib" / "std.fluid" / "records" / "water_saturation.toml"

_REFERENCE = (
    "IAPWS R7-97(2012), 'Revised Release on the IAPWS Industrial "
    "Formulation 1997 for the Thermodynamic Properties of Water and "
    "Steam', Region 4 (saturation-line) auxiliary equation, Eq 30, "
    "evaluated at T; coefficients cross-checked against the jjgomera/ "
    "iapws (MIT) reference implementation's own doctest "
    "(_PSat_T(500) == 2.63889776 MPa)"
)

_TC_K = 647.096  # the equation's own upper validity bound (critical point)
_T_MIN_K = 273.15


def _p_sat_mpa(t_k: float, n: list[float]) -> float:
    """Eq 30 evaluated at one temperature; n is 1-indexed (n[0] unused)."""
    theta = t_k + n[9] / (t_k - n[10])
    a = theta**2 + n[1] * theta + n[2]
    b = n[3] * theta**2 + n[4] * theta + n[5]
    c = n[6] * theta**2 + n[7] * theta + n[8]
    return (2 * c / (-b + math.sqrt(b**2 - 4 * a * c))) ** 4


def _rows(data: dict) -> list[dict]:
    n: list[float] = [0.0] + [data[f"n{i}"] for i in range(1, 11)]
    rows = []
    for t_k in data["t_grid_k"]:
        assert _T_MIN_K <= t_k <= _TC_K, f"T={t_k} outside IF97 Region 4 domain"
        p_sat_pa = _p_sat_mpa(t_k, n) * 1.0e6
        rows.append(
            {
                "key": f"water_psat_{t_k:g}k".replace(".", "_"),
                "t_k": t_k,
                "p_sat_pa": p_sat_pa,
                "evidence": {
                    "method": "derivation",
                    "trust_tier": "community",
                    "reference": _REFERENCE,
                },
            }
        )
    return rows


# frob:doc docs/modules/tools.md#stdlib-gen-iapws-water
def generate() -> dict[str, str]:
    with DATA_FILE.open("rb") as f:
        data = tomllib.load(f)
    rows = _rows(data)
    content = render_records_file(
        script="tools/stdlib/gen_iapws_water.py",
        source="tools/stdlib/data/iapws_water_saturation.toml",
        header_comment=(
            "# Water saturation pressure pv(T) (WO-138, D258.1/F158 GAP "
            "c1): POINT TABLE, each row is IAPWS R7-97(2012) Eq 30 "
            "EVALUATED at T, never a fitted curve (D258 ruling 1). "
            "Valid 273.15-647.096 K; a claim's corner temperature "
            "outside this range is a named out-of-domain result, never "
            "a silent clamp (fluid_resolve.py bracketing)."
        ),
        kind="water_saturation",
        rows=rows,
    )
    return {str(OUT_FILE): content}


# frob:doc docs/modules/tools.md#stdlib-gen-iapws-water
# frob:waive TEST001 reason="CLI entry point; see tests/tools/test_stdlib_gen_drift.py"
def main() -> None:
    for path_str, content in generate().items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="ascii")
        print(f"wrote {path.relative_to(REPO_ROOT)} ({content.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
