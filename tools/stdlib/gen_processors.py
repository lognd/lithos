"""Generates `stdlib/ti.mcu/records/msp430fr5_*.toml` (WO-145, D257
ruling 4) from the committed, human-confirmed transcription
`tools/stdlib/data/ti_mcu_msp430fr5.toml` (WO-66/AD-34 pattern: a
deterministic generator over a committed input table, no network at
generation time, reviewable diffs).

FIVE separate record families, one per file, per D257 ruling 2: a
record-wide citation cannot honestly claim one `page`/`table` for data
that actually spans several datasheet sections, so `package`/
`abs_max`/`operating`/`thermal` each get their own file+evidence
(family-wide, one row -- SLASE54D's abs-max/operating/thermal tables
do not vary by part) and `peripherals` gets one row per part (the
family's actual per-part variation: FRAM size, LEA presence, BSL
protocol). Every row's `evidence` carries BOTH the house prose
`reference` (existing `load_toml_records`/`check_citations` contract,
unchanged) and the D257 ruling 2 structured fields (`manufacturer`,
`document`, `revision`, `date`, `page`, `table`, `url`) the
`organization.py` structured-citation check tightens against.

Scope note (WO-145 close-out, honest partial, per the recon's own
sec. 3.7 ragged-edge taxonomy): only ONE package variant (PM0064A,
64-pin LQFP) is transcribed. Electrical/timing matrices (active-mode
supply current vs frequency, LPM currents, I/O DC characteristics),
the alternate-function pin-mux table, and the other three package
variants (PN/ZVW/RGZ) are RAGGED and explicitly out of this slice
(WO-145 body, "Out of scope").
"""

# frob:waive TEST005 reason="measured 40.0% line on 2026-07-19; backfill T-0036"

from __future__ import annotations

import tomllib
from pathlib import Path

from tools.stdlib.render import render_records_file

# frob:doc docs/modules/tools.md#stdlib-gen-processors
REPO_ROOT = Path(__file__).resolve().parents[2]
# frob:doc docs/modules/tools.md#stdlib-gen-processors
DATA_FILE = REPO_ROOT / "tools" / "stdlib" / "data" / "ti_mcu_msp430fr5.toml"
# frob:doc docs/modules/tools.md#stdlib-gen-processors
OUT_DIR = REPO_ROOT / "stdlib" / "ti.mcu" / "records"

_HEADER = (
    "# See tools/stdlib/data/ti_mcu_msp430fr5.toml's own header for the\n"
    "# fetch/confirm provenance (WO-145, D257 ruling 3: every value below\n"
    "# was confirmed against a rendered datasheet page before transcription).\n"
    "# tier=community (D58): transcribed vendor datasheet data, unsigned.\n"
)


def _evidence(doc: dict, section: dict, *, method: str = "catalog") -> dict:
    """The one place a section's evidence table is assembled: the shared
    `[document]` identity merged with the section's own page+table, plus
    the house prose `reference` `load_toml_records` requires."""
    reference = (
        f"TI {doc['document']} Rev. {doc['revision']} "
        f"({doc['date']}), {section['table']}, p.{section['page']}"
    )
    return {
        "method": method,
        "trust_tier": "community",
        "reference": reference,
        "manufacturer": doc["manufacturer"],
        "document": doc["document"],
        "revision": doc["revision"],
        "date": doc["date"],
        "page": section["page"],
        "table": section["table"],
        "url": doc["url"],
    }


def _section_row(doc: dict, section: dict) -> dict:
    """One family-wide row: every data field from `section` minus its
    own `page`/`table` bookkeeping keys (folded into `evidence`
    instead), plus `confirmed = true` and the assembled evidence."""
    row = {k: v for k, v in section.items() if k not in ("page", "table")}
    row["confirmed"] = True
    row["evidence"] = _evidence(doc, section)
    return row


# frob:doc docs/modules/tools.md#stdlib-gen-processors
# frob:waive TEST005 reason="measured 18.2% branch on 2026-07-19; backfill T-0036"
def generate() -> dict[str, str]:
    with DATA_FILE.open("rb") as f:
        data = tomllib.load(f)
    doc = data["document"]

    out: dict[str, str] = {}

    out[str(OUT_DIR / "msp430fr5_package.toml")] = render_records_file(
        script="tools/stdlib/gen_processors.py",
        source="tools/stdlib/data/ti_mcu_msp430fr5.toml",
        header_comment=(
            _HEADER
            + "#\n"
            + "# Package/pinout envelope (bounding box + pitch only -- the\n"
            + "# alternate-function pin-mux table is RAGGED, out of scope\n"
            + "# per the WO-145 body).\n"
        ),
        kind="processor_package",
        rows=[_section_row(doc, data["package"])],
    )

    out[str(OUT_DIR / "msp430fr5_abs_max.toml")] = render_records_file(
        script="tools/stdlib/gen_processors.py",
        source="tools/stdlib/data/ti_mcu_msp430fr5.toml",
        header_comment=(
            _HEADER
            + "#\n"
            + "# Absolute maximum ratings + ESD ratings (sec 8.1/8.2, p.29).\n"
            + '# The any-pin upper bound is symbolic ("VCC + 0.3 V"); both\n'
            + "# the symbolic form and the datasheet's own printed resolved\n"
            + "# worst case (4.1 V) are carried, never silently collapsed.\n"
        ),
        kind="processor_abs_max",
        rows=[_section_row(doc, data["abs_max"])],
    )

    out[str(OUT_DIR / "msp430fr5_operating.toml")] = render_records_file(
        script="tools/stdlib/gen_processors.py",
        source="tools/stdlib/data/ti_mcu_msp430fr5.toml",
        header_comment=(
            _HEADER
            + "#\n"
            + "# Recommended operating conditions (sec 8.3, p.30). fSYSTEM is\n"
            + "# carried under BOTH named wait-state conditions -- never\n"
            + "# collapsed to one number (the recon's MeasCondition case).\n"
        ),
        kind="processor_operating",
        rows=[_section_row(doc, data["operating"])],
    )

    out[str(OUT_DIR / "msp430fr5_thermal.toml")] = render_records_file(
        script="tools/stdlib/gen_processors.py",
        source="tools/stdlib/data/ti_mcu_msp430fr5.toml",
        header_comment=(
            _HEADER
            + "#\n"
            + "# Thermal packaging characteristics (sec 8.11, p.37), PM\n"
            + "# (64-pin LQFP) package row only -- the other three package\n"
            + "# rows (RGZ/PN/ZVW) are not transcribed this slice.\n"
        ),
        kind="processor_thermal",
        rows=[_section_row(doc, data["thermal"])],
    )

    out[str(OUT_DIR / "msp430fr5_peripherals.toml")] = render_records_file(
        script="tools/stdlib/gen_processors.py",
        source="tools/stdlib/data/ti_mcu_msp430fr5.toml",
        header_comment=(
            _HEADER
            + "#\n"
            + "# Peripheral inventory + memory sizes, one row per part\n"
            + "# (Table 6-1, p.7), PM (64-pin) package column only -- the\n"
            + "# 80-pin PN/87-pin ZVW/48-pin RGZ packages carry DIFFERENT\n"
            + "# eUSCI/ADC-channel/GPIO counts (named ragged edge, not\n"
            + "# transcribed this slice). The address/memory MAP (beyond\n"
            + "# bare sizes) is out of scope per the WO-145 body.\n"
        ),
        kind="processor_peripherals",
        rows=[_section_row(doc, part) for part in data["peripherals"]],
    )

    return out


# frob:doc docs/modules/tools.md#stdlib-gen-processors
# frob:waive TEST001 reason="CLI entry point; see tests/tools/test_stdlib_gen_drift.py"
# frob:waive TEST005 reason="measured 16.7% branch on 2026-07-19; backfill T-0036"
def main() -> None:
    for path_str, content in generate().items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="ascii")
        print(f"wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
