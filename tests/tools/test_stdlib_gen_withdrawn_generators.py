"""Unit tests for the D266-withdrawn-data generators' PURE parse/
transform functions (T-0036 backfill): `gen_nasa_glenn_cp`,
`gen_iapws_water`, `gen_processors`. D266 (2026-07-16) withdrew the
COMMITTED input tables pending counsel review, so
`tests/tools/test_stdlib_gen_drift.py` no longer exercises these three
generators' body at all (`generate()` raises `FileNotFoundError` at
`DATA_FILE.open()` before a single row is built). These tests never
touch the withdrawn tables or reintroduce real transcribed values --
each uses a small SYNTHETIC fixture (arbitrary numbers, schema-shaped
only) to exercise `_rows`/`_evidence`/`_section_row` and the
`generate()`/`main()` write path against a `tmp_path` redirect,
independent of D266's counsel-review gate.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tools.stdlib import gen_iapws_water, gen_nasa_glenn_cp, gen_processors

# --- gen_nasa_glenn_cp -----------------------------------------------


# frob:tests tools/stdlib/gen_nasa_glenn_cp.py::_rows kind="unit"
# frob:ticket T-0036
def test_nasa_glenn_rows_are_sorted_by_key_and_carry_every_coeff() -> None:
    """`_rows` sorts by species key and copies all 7 coefficients plus
    the b1/b2 terms and a catalog-tier evidence block per species."""
    data = {
        "o2": {
            "molar_mass_kg_mol": 0.032,
            "t_min_k": 200.0,
            "t_max_k": 1000.0,
            **{f"a{i}": float(i) for i in range(1, 8)},
            "b1": 1.0,
            "b2": 2.0,
        },
        "ar": {
            "molar_mass_kg_mol": 0.040,
            "t_min_k": 200.0,
            "t_max_k": 1000.0,
            **{f"a{i}": float(i) * 2 for i in range(1, 8)},
            "b1": 3.0,
            "b2": 4.0,
        },
    }
    rows = gen_nasa_glenn_cp._rows(data)
    assert [r["key"] for r in rows] == ["ar", "o2"]
    assert rows[0]["species"] == "AR"
    assert rows[0]["a1"] == 2.0
    assert rows[0]["b2"] == 4.0
    assert rows[0]["evidence"]["method"] == "catalog"
    assert rows[0]["evidence"]["trust_tier"] == "community"


# frob:tests tools/stdlib/gen_nasa_glenn_cp.py::generate kind="unit"
# frob:ticket T-0036
def test_nasa_glenn_generate_writes_rendered_content_via_synthetic_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`generate()` reads `DATA_FILE`, builds rows, renders one TOML
    file keyed under `OUT_FILE` -- proven with a synthetic fixture, not
    the D266-withdrawn table."""
    data_file = tmp_path / "in.toml"
    data_file.write_text(
        "[n2]\n"
        'molar_mass_kg_mol = 0.028\n'
        "t_min_k = 200.0\n"
        "t_max_k = 1000.0\n"
        "a1 = 1.0\na2 = 2.0\na3 = 3.0\na4 = 4.0\na5 = 5.0\na6 = 6.0\na7 = 7.0\n"
        "b1 = 8.0\nb2 = 9.0\n",
        encoding="ascii",
    )
    out_file = tmp_path / "out" / "gas_cp_glenn.toml"
    monkeypatch.setattr(gen_nasa_glenn_cp, "DATA_FILE", data_file)
    monkeypatch.setattr(gen_nasa_glenn_cp, "OUT_FILE", out_file)

    result = gen_nasa_glenn_cp.generate()

    assert str(out_file) in result
    content = result[str(out_file)]
    assert "[[gas_cp_glenn]]" in content
    assert 'key = "n2"' in content


# frob:tests tools/stdlib/gen_nasa_glenn_cp.py::main kind="unit"
# frob:ticket T-0036
def test_nasa_glenn_main_writes_file_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()` writes every `generate()` output to disk and reports a
    line count for each (the CLI entry point's actual side effect)."""
    out_file = tmp_path / "nested" / "gas_cp_glenn.toml"
    monkeypatch.setattr(gen_nasa_glenn_cp, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        gen_nasa_glenn_cp, "generate", lambda: {str(out_file): "hello\nworld\n"}
    )

    gen_nasa_glenn_cp.main()

    assert out_file.read_text(encoding="ascii") == "hello\nworld\n"
    assert "wrote" in capsys.readouterr().out


# --- gen_iapws_water --------------------------------------------------


# frob:tests tools/stdlib/gen_iapws_water.py::_p_sat_mpa kind="unit"
# frob:ticket T-0036
def test_p_sat_mpa_matches_the_reference_implementation_at_500k() -> None:
    """Eq 30 at T=500K reproduces the docstring's own cross-check value
    (`_PSat_T(500) == 2.63889776 MPa`, jjgomera/iapws doctest) -- the
    real IAPWS Region-4 coefficients, not the withdrawn generator table
    (these coefficients are published in the standard itself, not
    D266's counsel-review-gated transcription)."""
    n = [
        0.0,
        0.11670521452767e4,
        -0.72421316703206e6,
        -0.17073846940092e2,
        0.12020824702470e5,
        -0.32325550322333e7,
        0.14915108613530e2,
        -0.48232657361591e4,
        0.40511340542057e6,
        -0.23855557567849,
        0.65017534844798e3,
    ]
    p_mpa = gen_iapws_water._p_sat_mpa(500.0, n)
    assert math.isclose(p_mpa, 2.63889776, rel_tol=1e-6)


# frob:tests tools/stdlib/gen_iapws_water.py::_rows kind="unit"
# frob:ticket T-0036
def test_iapws_rows_reject_temperature_outside_region4_domain() -> None:
    """`_rows` asserts every grid temperature is inside [273.15, Tc] --
    an out-of-domain grid point is a programmer bug, not silently
    clamped or skipped."""
    n = [0.0] + [1.0] * 10
    data = {"t_grid_k": [900.0], **{f"n{i}": n[i] for i in range(1, 11)}}
    with pytest.raises(AssertionError, match="outside IF97 Region 4 domain"):
        gen_iapws_water._rows(data)


# frob:tests tools/stdlib/gen_iapws_water.py::_rows kind="unit"
# frob:ticket T-0036
def test_iapws_rows_builds_key_and_pressure_for_in_domain_grid() -> None:
    """A single in-domain grid temperature produces one row with a
    slug-safe `key`, the computed pressure, and derivation evidence."""
    n = [
        0.0,
        0.11670521452767e4,
        -0.72421316703206e6,
        -0.17073846940092e2,
        0.12020824702470e5,
        -0.32325550322333e7,
        0.14915108613530e2,
        -0.48232657361591e4,
        0.40511340542057e6,
        -0.23855557567849,
        0.65017534844798e3,
    ]
    data = {"t_grid_k": [500.0], **{f"n{i}": n[i] for i in range(1, 11)}}
    rows = gen_iapws_water._rows(data)
    assert len(rows) == 1
    row = rows[0]
    assert row["key"] == "water_psat_500k"
    assert math.isclose(row["p_sat_pa"], 2.63889776e6, rel_tol=1e-6)
    assert row["evidence"]["method"] == "derivation"


# frob:tests tools/stdlib/gen_iapws_water.py::generate kind="unit"
# frob:ticket T-0036
def test_iapws_water_generate_writes_rendered_content_via_synthetic_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`generate()` end to end against a synthetic single-point fixture."""
    data_file = tmp_path / "in.toml"
    data_file.write_text(
        "t_grid_k = [500.0]\n"
        "n1 = 0.11670521452767e4\n"
        "n2 = -0.72421316703206e6\n"
        "n3 = -0.17073846940092e2\n"
        "n4 = 0.12020824702470e5\n"
        "n5 = -0.32325550322333e7\n"
        "n6 = 0.14915108613530e2\n"
        "n7 = -0.48232657361591e4\n"
        "n8 = 0.40511340542057e6\n"
        "n9 = -0.23855557567849\n"
        "n10 = 0.65017534844798e3\n",
        encoding="ascii",
    )
    out_file = tmp_path / "out" / "water_saturation.toml"
    monkeypatch.setattr(gen_iapws_water, "DATA_FILE", data_file)
    monkeypatch.setattr(gen_iapws_water, "OUT_FILE", out_file)

    result = gen_iapws_water.generate()

    assert str(out_file) in result
    assert "[[water_saturation]]" in result[str(out_file)]


# frob:tests tools/stdlib/gen_iapws_water.py::main kind="unit"
# frob:ticket T-0036
def test_iapws_water_main_writes_file_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()` writes the generated content and reports a line count."""
    out_file = tmp_path / "water_saturation.toml"
    monkeypatch.setattr(gen_iapws_water, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gen_iapws_water, "generate", lambda: {str(out_file): "a\nb\n"})

    gen_iapws_water.main()

    assert out_file.read_text(encoding="ascii") == "a\nb\n"
    assert "wrote" in capsys.readouterr().out


# --- gen_processors -----------------------------------------------


# frob:ticket T-0036
def _doc() -> dict:
    return {
        "manufacturer": "TI",
        "document": "SLASE54D",
        "revision": "C",
        "date": "2020-01",
        "url": "https://example.invalid/slase54d",
    }


# frob:tests tools/stdlib/gen_processors.py::_evidence kind="unit"
# frob:ticket T-0036
def test_processors_evidence_assembles_reference_and_structured_fields() -> None:
    """`_evidence` merges the shared `[document]` identity with a
    section's own `page`/`table`, plus a house-prose `reference`."""
    section = {"page": 29, "table": "Table 8-1"}
    evidence = gen_processors._evidence(_doc(), section)
    assert evidence["reference"] == "TI SLASE54D Rev. C (2020-01), Table 8-1, p.29"
    assert evidence["manufacturer"] == "TI"
    assert evidence["page"] == 29
    assert evidence["table"] == "Table 8-1"
    assert evidence["method"] == "catalog"


# frob:tests tools/stdlib/gen_processors.py::_section_row kind="unit"
# frob:ticket T-0036
def test_processors_section_row_drops_page_table_and_marks_confirmed() -> None:
    """`_section_row` copies every section field except `page`/`table`
    (folded into `evidence` instead) and stamps `confirmed = true`."""
    section = {"page": 7, "table": "Table 6-1", "vcc_min_v": 1.8}
    row = gen_processors._section_row(_doc(), section)
    assert row["confirmed"] is True
    assert row["vcc_min_v"] == 1.8
    assert "page" not in row
    assert "table" not in row
    assert row["evidence"]["page"] == 7


# frob:tests tools/stdlib/gen_processors.py::generate kind="unit"
# frob:ticket T-0036
def test_processors_generate_writes_five_files_via_synthetic_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`generate()` emits exactly the five section families, one file
    each, `peripherals` carrying one row per listed part."""
    data_file = tmp_path / "in.toml"
    data_file.write_text(
        "[document]\n"
        'manufacturer = "TI"\n'
        'document = "SLASE54D"\n'
        'revision = "C"\n'
        'date = "2020-01"\n'
        'url = "https://example.invalid/slase54d"\n'
        "\n"
        "[package]\n"
        "page = 1\n"
        'table = "T1"\n'
        'pins = 64\n'
        "\n"
        "[abs_max]\n"
        "page = 2\n"
        'table = "T2"\n'
        "vcc_max_v = 4.1\n"
        "\n"
        "[operating]\n"
        "page = 3\n"
        'table = "T3"\n'
        "vcc_min_v = 1.8\n"
        "\n"
        "[thermal]\n"
        "page = 4\n"
        'table = "T4"\n'
        "theta_ja_c_per_w = 60.0\n"
        "\n"
        "[[peripherals]]\n"
        "page = 5\n"
        'table = "T5"\n'
        'part = "MSP430FR5989"\n'
        "\n"
        "[[peripherals]]\n"
        "page = 5\n"
        'table = "T5"\n'
        'part = "MSP430FR5969"\n',
        encoding="ascii",
    )
    out_dir = tmp_path / "out"
    monkeypatch.setattr(gen_processors, "DATA_FILE", data_file)
    monkeypatch.setattr(gen_processors, "OUT_DIR", out_dir)

    result = gen_processors.generate()

    assert len(result) == 5
    assert str(out_dir / "msp430fr5_package.toml") in result
    peripherals = result[str(out_dir / "msp430fr5_peripherals.toml")]
    assert peripherals.count("[[processor_peripherals]]") == 2


# frob:tests tools/stdlib/gen_processors.py::main kind="unit"
# frob:ticket T-0036
def test_processors_main_writes_every_file_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()` writes each `generate()` output file and prints one
    `wrote ...` line per file."""
    out_a = tmp_path / "a.toml"
    out_b = tmp_path / "sub" / "b.toml"
    monkeypatch.setattr(gen_processors, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        gen_processors,
        "generate",
        lambda: {str(out_a): "x\n", str(out_b): "y\n"},
    )

    gen_processors.main()

    assert out_a.read_text(encoding="ascii") == "x\n"
    assert out_b.read_text(encoding="ascii") == "y\n"
    out = capsys.readouterr().out
    assert out.count("wrote") == 2
