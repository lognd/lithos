"""WO-54 deliverable 3: ``[profiles.cost.<name>]`` manifest parsing
(toolchain/27 sec. 1.2): the quantity basis, rate/pricing record refs,
markup, currency, the ``default`` pick, and every loud malformed-table
error path."""

from __future__ import annotations

from pathlib import Path

from regolith.magnetite.manifest import load_manifest

_PROFILED = """\
[package]
name = "profiled"
version = "0.1.0"

[profiles.cost.prototype]
quantity = 1
labor    = "rates.us_midwest_2026"
pricing  = ["digikey.spot_2026q3", "mcmaster.catalog_2026"]
markup   = 1.0

[profiles.cost.construction]
quantity = 1
labor    = "rates.us_midwest_union_2026"
process_rates = ["rates.pcb_assembly_2026"]
pricing  = ["rsmeans.bldg_2026", "sqd.distributor_2026"]
markup   = 1.18
currency = "USD"

[profiles.cost.default]
profile = "prototype"
"""


def _load(tmp_path: Path, text: str):
    (tmp_path / "magnetite.toml").write_text(text)
    return load_manifest(str(tmp_path))


def test_cost_profiles_parse_with_default(tmp_path: Path) -> None:
    result = _load(tmp_path, _PROFILED)
    assert result.is_ok, result
    manifest = result.danger_ok
    assert manifest.default_cost_profile == "prototype"
    by_name = {p.name: p for p in manifest.cost_profiles}
    assert set(by_name) == {"prototype", "construction"}
    proto = by_name["prototype"]
    assert proto.quantity == 1.0
    assert proto.labor == ("rates.us_midwest_2026",)
    assert proto.pricing == ("digikey.spot_2026q3", "mcmaster.catalog_2026")
    assert proto.markup == 1.0
    assert proto.currency == "USD"
    construction = by_name["construction"]
    assert construction.markup == 1.18
    assert construction.process_rates == ("rates.pcb_assembly_2026",)


def test_manifest_without_profiles_has_none(tmp_path: Path) -> None:
    result = _load(tmp_path, '[package]\nname = "bare"\n')
    assert result.is_ok
    manifest = result.danger_ok
    assert manifest.cost_profiles == ()
    assert manifest.default_cost_profile is None


def test_default_naming_unknown_profile_is_an_error(tmp_path: Path) -> None:
    text = (
        '[package]\nname = "bad"\n\n'
        "[profiles.cost.prototype]\nquantity = 1\n\n"
        '[profiles.cost.default]\nprofile = "production"\n'
    )
    result = _load(tmp_path, text)
    assert result.is_err
    assert result.danger_err.kind == "unknown_default_profile"
    assert "production" in result.danger_err.message


def test_non_positive_quantity_is_an_error(tmp_path: Path) -> None:
    text = '[package]\nname = "bad"\n\n[profiles.cost.p]\nquantity = 0\n'
    result = _load(tmp_path, text)
    assert result.is_err
    assert result.danger_err.kind == "malformed_profiles"


def test_non_positive_markup_is_an_error(tmp_path: Path) -> None:
    text = '[package]\nname = "bad"\n\n[profiles.cost.p]\nmarkup = -1.0\n'
    result = _load(tmp_path, text)
    assert result.is_err
    assert result.danger_err.kind == "malformed_profiles"


def test_boolean_quantity_is_rejected_not_coerced_to_one(tmp_path: Path) -> None:
    # isinstance(True, int) is True in Python, so `quantity = true`
    # would otherwise silently coerce to 1.0 (L1, cycle-28).
    text = '[package]\nname = "bad"\n\n[profiles.cost.p]\nquantity = true\n'
    result = _load(tmp_path, text)
    assert result.is_err
    assert result.danger_err.kind == "malformed_profiles"


def test_boolean_markup_is_rejected_not_coerced_to_one(tmp_path: Path) -> None:
    text = '[package]\nname = "bad"\n\n[profiles.cost.p]\nmarkup = true\n'
    result = _load(tmp_path, text)
    assert result.is_err
    assert result.danger_err.kind == "malformed_profiles"


def test_malformed_default_table_is_an_error(tmp_path: Path) -> None:
    text = '[package]\nname = "bad"\n\n[profiles.cost.default]\nquantity = 1\n'
    result = _load(tmp_path, text)
    assert result.is_err
    assert result.danger_err.kind == "malformed_profiles"
    assert "default" in result.danger_err.message


def test_small_office_flagship_profiles_parse() -> None:
    """The corpus flagship's real manifest is the pressure test (D147)."""
    repo_root = Path(__file__).resolve().parents[2]
    result = load_manifest(str(repo_root / "examples" / "flagships" / "small_office"))
    assert result.is_ok, result
    manifest = result.danger_ok
    assert manifest.default_cost_profile == "prototype"
    names = {p.name for p in manifest.cost_profiles}
    assert names == {"prototype", "construction"}
