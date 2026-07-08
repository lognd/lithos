"""WO-16 package/registry loader: manifest, records, coherence."""

from __future__ import annotations

from pathlib import Path

from regolith.magnetite.coherence import ContactKey, resolve_most_specific
from regolith.magnetite.manifest import Manifest, load_manifest, resolve_dependencies
from regolith.magnetite.records import Evidence, Record, RecordKey, RecordStore


def _write_manifest(root: Path, name: str, version: str, depends: str = "") -> None:
    pkg_dir = root / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "magnetite.toml").write_text(
        f'[package]\nname = "{name}"\nversion = "{version}"\n{depends}\n'
    )


# --- manifest -----------------------------------------------------------


def test_load_manifest_reads_identity_and_depends(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text(
        '[package]\nname = "kestrel"\n\n'
        '[depends]\n"std.quantities" = "^1"\n"std.mech" = "^0.9"\n\n'
        '[evidence]\n"doc.pdf" = "sha256:aa10f3"\n'
    )
    result = load_manifest(str(tmp_path))
    assert result.is_ok
    manifest = result.danger_ok
    assert manifest.name == "kestrel"
    assert manifest.version == ""
    assert manifest.depends == (
        __import__("regolith.magnetite.manifest", fromlist=["PackageDep"]).PackageDep(
            name="std.mech", version="^0.9"
        ),
        __import__("regolith.magnetite.manifest", fromlist=["PackageDep"]).PackageDep(
            name="std.quantities", version="^1"
        ),
    )
    assert manifest.evidence_hashes == ("doc.pdf=sha256:aa10f3",)


def test_load_manifest_accepts_direct_file_path(tmp_path: Path) -> None:
    manifest_file = tmp_path / "magnetite.toml"
    manifest_file.write_text('[package]\nname = "leaf"\nversion = "1.0.0"\n')
    result = load_manifest(str(manifest_file))
    assert result.is_ok
    assert result.danger_ok.name == "leaf"


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    result = load_manifest(str(tmp_path / "nope"))
    assert result.is_err
    assert result.danger_err.kind == "not_found"


def test_load_manifest_malformed_toml(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text("this is not [valid toml")
    result = load_manifest(str(tmp_path))
    assert result.is_err
    assert result.danger_err.kind == "malformed_toml"


def test_load_manifest_missing_package_table(tmp_path: Path) -> None:
    (tmp_path / "magnetite.toml").write_text('[depends]\n"x" = "^1"\n')
    result = load_manifest(str(tmp_path))
    assert result.is_err
    assert result.danger_err.kind == "missing_identity"


def test_resolve_dependencies_walks_local_paths(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    _write_manifest(registry, "a", "1.0.0", '[depends]\nb = "^1"\n')
    _write_manifest(registry, "b", "1.0.0")
    root = Manifest(
        name="root",
        version="1.0.0",
        depends=(
            __import__(
                "regolith.magnetite.manifest", fromlist=["PackageDep"]
            ).PackageDep(name="a", version="^1"),
        ),
    )
    result = resolve_dependencies(root, (str(registry),))
    assert result.is_ok
    names = {m.name for m in result.danger_ok}
    assert names == {"a", "b"}


def test_resolve_dependencies_rejects_two_versions(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    _write_manifest(registry, "a", "1.0.0", '[depends]\nc = "^1"\n')
    _write_manifest(registry, "b", "1.0.0", '[depends]\nc = "^2"\n')
    _write_manifest(registry, "c", "1.0.0")
    from regolith.magnetite.manifest import PackageDep

    root = Manifest(
        name="root",
        version="1.0.0",
        depends=(
            PackageDep(name="a", version="^1"),
            PackageDep(name="b", version="^1"),
        ),
    )
    result = resolve_dependencies(root, (str(registry),))
    assert result.is_err
    assert result.danger_err.kind == "version_conflict"


def test_resolve_dependencies_unresolved(tmp_path: Path) -> None:
    from regolith.magnetite.manifest import PackageDep

    root = Manifest(
        name="root",
        version="1.0.0",
        depends=(PackageDep(name="missing", version="^1"),),
    )
    result = resolve_dependencies(root, (str(tmp_path),))
    assert result.is_err
    assert result.danger_err.kind == "unresolved_dependency"


# --- records --------------------------------------------------------------


def _record(
    package: str, key: str, revision: int, content_hash: str = "sha256:abc"
) -> Record:
    return Record(
        address=RecordKey(package=package, key=key, revision=revision),
        kind="material",
        content_hash=content_hash,
        evidence=Evidence(
            method="catalog", trust_tier="certified", reference="doc.pdf"
        ),
    )


def test_record_store_get_exact_revision() -> None:
    store = RecordStore(
        (_record("mmpds", "AISI_4140", 1), _record("mmpds", "AISI_4140", 2))
    )
    result = store.get(RecordKey(package="mmpds", key="AISI_4140", revision=1))
    assert result.is_ok
    assert result.danger_ok.address.revision == 1


def test_record_store_get_missing() -> None:
    store = RecordStore()
    result = store.get(RecordKey(package="mmpds", key="AISI_4140", revision=1))
    assert result.is_err
    assert result.danger_err.kind == "not_found"


def test_record_store_latest_picks_max_revision() -> None:
    store = RecordStore(
        (
            _record("mmpds", "AISI_4140", 1),
            _record("mmpds", "AISI_4140", 3),
            _record("mmpds", "AISI_4140", 2),
        )
    )
    result = store.latest("mmpds", "AISI_4140")
    assert result.is_ok
    assert result.danger_ok.address.revision == 3


def test_record_store_rejects_malformed_hash() -> None:
    store = RecordStore((_record("mmpds", "AISI_4140", 1, content_hash="not-a-hash"),))
    result = store.get(RecordKey(package="mmpds", key="AISI_4140", revision=1))
    assert result.is_err
    assert result.danger_err.kind == "invalid_hash"


# --- coherence --------------------------------------------------------------


def test_contact_key_canonical_is_order_independent() -> None:
    assert ContactKey(a="A", b="B").canonical() == ContactKey(a="B", b="A").canonical()


def test_resolve_most_specific_unique_winner() -> None:
    bare = _record("std.materials", "AISI_4140", 1)
    qualified = _record("mmpds", "mmpds.AISI_4140", 1)
    result = resolve_most_specific((bare, qualified), pins=())
    assert result.is_ok
    assert result.danger_ok is qualified


def test_resolve_most_specific_ambiguous_without_pin() -> None:
    a = _record("pkg_a", "AISI_4140", 1)
    b = _record("pkg_b", "AISI_4140", 1)
    result = resolve_most_specific((a, b), pins=())
    assert result.is_err
    assert result.danger_err.kind == "ambiguous"


def test_resolve_most_specific_use_pin_disambiguates() -> None:
    a = _record("pkg_a", "AISI_4140", 1)
    b = _record("pkg_b", "AISI_4140", 1)
    result = resolve_most_specific((a, b), pins=("pkg_b",))
    assert result.is_ok
    assert result.danger_ok is b


def test_resolve_most_specific_no_candidates() -> None:
    result = resolve_most_specific((), pins=())
    assert result.is_err
    assert result.danger_err.kind == "no_candidates"
