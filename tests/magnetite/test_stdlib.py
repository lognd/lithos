"""WO-45 stdlib v1 (D135): manifest validity, record round-trips, the
corpus de-phantoming enumeration, and trust-tier honesty.

Scope note (escalated in the WO-45 close-out report, not invented):
two corpus import namespaces, `std.compute` and `std.fluorite`, are
used bare in examples but are NOT in the D135 sec. 8 catalog this WO
builds against; they read as pre-existing language-builtin surface
(capability namespace / fluorite primitive component kinds), not
stdlib packages, so building a package home for them would be scope
creep this WO's body does not authorize. They are excluded from the
enumeration below with this note as the paper trail; a future WO/
design-log entry should settle their status. `std.civil` (WO-48
slice C) has since landed and is no longer excluded (D153-style
finding: it belongs in the catalog like every other real package).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from regolith.magnetite.manifest import load_manifest, resolve_dependencies
from regolith.magnetite.stdlib_records import load_package_records
from regolith.magnetite.trust import tier_from_name

REPO_ROOT = Path(__file__).resolve().parents[2]
STDLIB_ROOT = REPO_ROOT / "stdlib"
EXAMPLES_ROOT = REPO_ROOT / "examples"

# Namespaces intentionally NOT covered by this enumeration (see the
# module docstring): compute/fluorite are a language-builtin escalation.
_OUT_OF_SCOPE_NAMESPACES = {"std.compute", "std.fluorite"}

_STDLIB_PACKAGES = sorted(p.name for p in STDLIB_ROOT.iterdir() if p.is_dir())


# --- manifest validity ----------------------------------------------------


@pytest.mark.parametrize("package", _STDLIB_PACKAGES)
def test_stdlib_manifest_loads(package: str) -> None:
    """Every stdlib package's magnetite.toml parses and names itself."""
    result = load_manifest(str(STDLIB_ROOT / package))
    assert result.is_ok, f"{package}: {result}"
    manifest = result.danger_ok
    assert manifest.name == package
    assert manifest.kinds, f"{package}: magnetite.toml declares no [package].kinds"


def test_stdlib_dependency_closure_resolves_locally() -> None:
    """std.mech's declared depends resolve against stdlib/ with no network."""
    root = load_manifest(str(STDLIB_ROOT / "std.mech")).danger_ok
    result = resolve_dependencies(root, (str(STDLIB_ROOT),))
    assert result.is_ok, result
    names = {m.name for m in result.danger_ok}
    assert names == {"std.quantities", "std.materials"}


# --- record round-trips ----------------------------------------------------


_PACKAGES_WITH_RECORDS = sorted(
    p.name for p in STDLIB_ROOT.iterdir() if (p / "records").is_dir()
)


@pytest.mark.parametrize("package", _PACKAGES_WITH_RECORDS)
# frob:tests python/regolith/magnetite/stdlib_records.py::load_package_records kind="unit"
def test_stdlib_records_round_trip(package: str) -> None:
    """Every stdlib TOML record file loads into real Record values with a
    valid (INV-22-shaped) content hash."""
    result = load_package_records(str(STDLIB_ROOT / package), package)
    assert result.is_ok, f"{package}: {result}"
    records = result.danger_ok
    assert records, f"{package}: no records loaded"
    for record in records:
        assert record.content_hash.startswith("sha256:")
        assert record.address.package == package


# --- trust-tier honesty (D58) ----------------------------------------------


@pytest.mark.parametrize("package", _PACKAGES_WITH_RECORDS)
# frob:tests python/regolith/magnetite/trust.py::tier_from_name kind="unit"
def test_stdlib_record_tiers_are_honest_and_known(package: str) -> None:
    """Every record's in-file tier claim parses as a real trust tier, and
    (D58) none of this starter content claims `certified` -- it is all
    transcribed/community per the WO-45 body's own instruction."""
    records = load_package_records(str(STDLIB_ROOT / package), package).danger_ok
    for record in records:
        tier_result = tier_from_name(record.evidence.trust_tier)
        assert tier_result.is_ok, (
            f"{package}/{record.address.key}: unknown trust tier "
            f"{record.evidence.trust_tier!r}"
        )
        assert record.evidence.trust_tier == "community", (
            f"{package}/{record.address.key}: v1 starter content must not "
            f"claim tier={record.evidence.trust_tier!r} (D58)"
        )
        assert record.evidence.reference, (
            f"{package}/{record.address.key}: evidence reference is empty"
        )


# --- corpus de-phantoming ---------------------------------------------------


def _stdlib_provides_index() -> dict[str, set[str]]:
    """package/category -> {names} from every stdlib manifest's [provides]."""
    index: dict[str, set[str]] = {}
    for package in _STDLIB_PACKAGES:
        manifest_path = STDLIB_ROOT / package / "magnetite.toml"
        with manifest_path.open("rb") as f:
            data = tomllib.load(f)
        for category, names in data.get("provides", {}).items():
            if isinstance(names, list):
                index.setdefault(category, set()).update(str(n) for n in names)
    return index


_IMPORT_RE = re.compile(r"import (std\.[\w.]+)(?:\s*\(([^)]*)\))?")
_MATERIAL_RE = re.compile(r"\bmaterial:\s*([A-Za-z_][A-Za-z0-9_]*)")


def _corpus_files() -> list[Path]:
    files: list[Path] = []
    for ext in ("*.hema", "*.cupr", "*.fluo"):
        files.extend(EXAMPLES_ROOT.rglob(ext))
    return files


def test_corpus_std_imports_are_not_phantom() -> None:
    """Every `import std.<sub> (Name, ...)` in examples/ (excluding the
    out-of-scope namespaces named in the module docstring) resolves to a
    name some stdlib package actually [provides] -- D135 deliverable 4.
    """
    provides = _stdlib_provides_index()
    missing: list[str] = []
    for file_path in _corpus_files():
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for match in _IMPORT_RE.finditer(text):
            module, names_blob = match.group(1), match.group(2) or ""
            if module in _OUT_OF_SCOPE_NAMESPACES:
                continue
            # `import std.intents` / `import std.debug` are bare (no
            # parenthesized names) -- checked at the package level.
            if not names_blob.strip():
                category = module.removeprefix("std.")
                if category not in provides and module not in {
                    "std.intents",
                    "std.debug",
                }:
                    missing.append(f"{file_path}: {module} (bare import, no package)")
                continue
            category = module.removeprefix("std.")
            provided_names = provides.get(category, set())
            for name in (n.strip() for n in names_blob.split(",")):
                if name and name not in provided_names:
                    missing.append(f"{file_path}: {module}.{name}")
    assert not missing, "phantom std references:\n" + "\n".join(sorted(set(missing)))


def test_corpus_bare_materials_resolve_against_std_materials() -> None:
    """Every `material: <Name>` bare reference in examples/*.hema resolves
    to a std.materials or std.contact record, EXCEPT `vendor(...)`
    supplied-part references (not a stdlib material at all)."""
    materials_records = load_package_records(
        str(STDLIB_ROOT / "std.materials"), "std.materials"
    ).danger_ok
    known = {r.address.key for r in materials_records}
    missing: list[str] = []
    for file_path in EXAMPLES_ROOT.rglob("*.hema"):
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for match in _MATERIAL_RE.finditer(text):
            name = match.group(1)
            if name == "vendor":
                continue  # `material: vendor(...)` -- a supplied part, not a record
            if name not in known:
                missing.append(f"{file_path}: material {name}")
    assert not missing, "phantom material references:\n" + "\n".join(
        sorted(set(missing))
    )
