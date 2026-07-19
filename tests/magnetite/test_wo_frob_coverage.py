"""Unit-test coverage closing frob's TEST001 gate for
`python/regolith/magnetite` (wave-agent frob-adoption pass, W2b).

Each test below targets one flagged, previously-untested public symbol
directly; the `frob:tests` binding comment sits immediately above the
test function that covers it. Additive-only: this file does not modify
any existing test.
"""

from __future__ import annotations

import json

import httpx
from regolith.magnetite.client import RegistryClient
from regolith.magnetite.index import index_path
from regolith.magnetite.lints import resolve_lint_config
from regolith.magnetite.manifest import Manifest
from regolith.magnetite.records_payload import component_field_rows
from regolith.magnetite.sources import Registry
from regolith.magnetite.stdlib_records import load_toml_records, row_hash
from regolith.magnetite.stdlib_resolve import resolve_records_roots_for_paths
from regolith.magnetite.trust import KeyDesignation, TrustTier, generate_signing_key


# frob:tests python/regolith/magnetite/lints.py::resolve_lint_config kind="unit"
def test_resolve_lint_config_defaults_empty_with_no_manifest() -> None:
    assert resolve_lint_config(None) == ()


def test_resolve_lint_config_reads_the_manifest_table() -> None:
    manifest = Manifest(name="pkg", version="1.0.0", lints=(("DUP001", "deny"),))
    assert resolve_lint_config(manifest) == (("DUP001", "deny"),)


# frob:tests python/regolith/magnetite/trust.py::KeyDesignation.public_key kind="unit"
def test_key_designation_public_key_round_trips_the_signing_key(tmp_path) -> None:
    result = generate_signing_key(str(tmp_path), "reviewer-1")
    assert result.is_ok
    signing_key = result.danger_ok
    designation = KeyDesignation(
        key_id="reviewer-1",
        public_key_base64=signing_key.public_key_base64(),
        confers=TrustTier.CERTIFIED,
    )
    public_key = designation.public_key()
    message = b"evidence content address"
    public_key.verify(signing_key.sign(message), message)


# frob:tests python/regolith/magnetite/trust.py::keys_dir kind="unit"
def test_keys_dir_is_under_dot_regolith(tmp_path) -> None:
    from regolith.magnetite.trust import keys_dir

    path = keys_dir(str(tmp_path))
    assert path == tmp_path / ".regolith" / "keys"


# frob:tests python/regolith/magnetite/stdlib_records.py::row_hash kind="unit"
def test_row_hash_is_stable_and_order_independent() -> None:
    a = row_hash("material", {"key": "al6061", "density": 2.70})
    b = row_hash("material", {"density": 2.70, "key": "al6061"})
    assert a == b
    assert a.startswith("sha256:")
    assert row_hash("material", {"key": "al6061"}) != a


# frob:tests python/regolith/magnetite/stdlib_records.py::load_toml_records kind="unit"
def test_load_toml_records_parses_array_of_tables(tmp_path) -> None:
    toml_path = tmp_path / "materials.toml"
    toml_path.write_text(
        '[[material]]\n'
        'key = "al6061"\n'
        '[material.evidence]\n'
        'method = "catalog"\n'
        'trust_tier = "T1"\n'
        'reference = "MMPDS"\n'
    )
    result = load_toml_records(str(toml_path), "std.materials")
    assert result.is_ok
    records = result.danger_ok
    assert len(records) == 1
    assert records[0].address.key == "al6061"
    assert records[0].address.package == "std.materials"


def test_load_toml_records_missing_file_is_an_error(tmp_path) -> None:
    result = load_toml_records(str(tmp_path / "no_such_file.toml"), "std.materials")
    assert result.is_err
    assert result.danger_err.kind == "not_found"


# frob:tests python/regolith/magnetite/records_payload.py::component_field_rows kind="unit"
def test_component_field_rows_reads_scalar_fields(tmp_path) -> None:
    pkg_dir = tmp_path / "mcu" / "records"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "parts.toml").write_text(
        '[[component]]\n'
        'key = "stm32g474"\n'
        'executor = 25000000.0\n'
        'dma_capable = true\n'
    )
    rows = component_field_rows((str(tmp_path),))
    assert rows["stm32g474"]["executor"] == "25000000"
    assert rows["stm32g474"]["dma_capable"] == "1"


def test_component_field_rows_missing_root_is_empty_not_fatal(tmp_path) -> None:
    assert component_field_rows((str(tmp_path / "nowhere"),)) == {}


# frob:tests python/regolith/magnetite/index.py::index_path kind="unit"
def test_index_path_is_the_bare_package_name() -> None:
    assert index_path("std.materials") == "std.materials"


# frob:tests python/regolith/magnetite/client.py::RegistryClient.fetch_index kind="unit"
def test_registry_client_fetch_index_parses_served_ndjson() -> None:
    entry = {
        "name": "std.materials",
        "version": "1.0.0",
        "manifest_digest": "sha256:aaaa",
        "archive_hash": "blake3:bbbb",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/index/std.materials"
        return httpx.Response(200, text=json.dumps(entry))

    client = RegistryClient(
        Registry(
            name="magnetite",
            index_url="https://reg.test/index",
            archive_url="https://reg.test/archive",
        ),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.fetch_index("std.materials")
    assert result.is_ok
    entries = result.danger_ok
    assert len(entries) == 1
    assert entries[0].name == "std.materials"
    assert entries[0].version == "1.0.0"


def test_registry_client_fetch_index_missing_package_is_an_error() -> None:
    client = RegistryClient(
        Registry(
            name="magnetite",
            index_url="https://reg.test/index",
            archive_url="https://reg.test/archive",
        ),
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
    )
    result = client.fetch_index("no.such.package")
    assert result.is_err
    assert result.danger_err.kind == "index_not_found"


# frob:tests python/regolith/magnetite/stdlib_resolve.py::resolve_records_roots_for_paths kind="unit"
def test_resolve_records_roots_for_paths_empty_with_no_manifest_ancestor(
    tmp_path,
) -> None:
    bare_file = tmp_path / "design.cupr"
    bare_file.write_text("")
    assert resolve_records_roots_for_paths((str(bare_file),)) == ()
