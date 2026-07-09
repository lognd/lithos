"""The regolith magnetite: manifests, records, coherence, and the registry.

Owns the package layer (AD-1): manifest parsing and local resolution
(:mod:`~regolith.magnetite.manifest`), immutable revisioned records
(:mod:`~regolith.magnetite.records`), trait coherence
(:mod:`~regolith.magnetite.coherence`), and the magnetite registry client
(regolith/11 sec. 10): a sparse index (:mod:`~regolith.magnetite.index`),
manifest-declared sources (:mod:`~regolith.magnetite.sources`), a
content-addressed httpx client with hash-pinned fetch
(:mod:`~regolith.magnetite.client`, INV-22), signature-carried trust
(:mod:`~regolith.magnetite.trust`, INV-14), and vendoring
(:mod:`~regolith.magnetite.vendor`). The `stdlib/` starter packages
(WO-45, D135) load their plain-TOML data records through
:mod:`~regolith.magnetite.stdlib_records`.
"""

from __future__ import annotations

from regolith.magnetite.client import RegistryClient, verify_archive
from regolith.magnetite.coherence import ContactKey, resolve_most_specific
from regolith.magnetite.index import (
    IndexEntry,
    latest_version,
    parse_index,
    select_version,
)
from regolith.magnetite.manifest import (
    Manifest,
    PackageDep,
    load_manifest,
    resolve_dependencies,
)
from regolith.magnetite.records import Evidence, Record, RecordKey, RecordStore
from regolith.magnetite.sources import Registry, Sources
from regolith.magnetite.stdlib_records import load_package_records, load_toml_records
from regolith.magnetite.trust import (
    KeyDesignation,
    KeySet,
    LocalSigningKey,
    Signature,
    TrustKeySet,
    TrustTier,
    generate_signing_key,
    keys_dir,
    load_signing_key,
    verify_trust,
)
from regolith.magnetite.vendor import VendorPin, VendorStore, vendor

__all__ = [
    "ContactKey",
    "Evidence",
    "IndexEntry",
    "KeyDesignation",
    "KeySet",
    "LocalSigningKey",
    "Manifest",
    "PackageDep",
    "Record",
    "RecordKey",
    "RecordStore",
    "Registry",
    "RegistryClient",
    "Signature",
    "Sources",
    "TrustKeySet",
    "TrustTier",
    "VendorPin",
    "VendorStore",
    "generate_signing_key",
    "keys_dir",
    "latest_version",
    "load_manifest",
    "load_package_records",
    "load_signing_key",
    "load_toml_records",
    "parse_index",
    "resolve_dependencies",
    "resolve_most_specific",
    "select_version",
    "vendor",
    "verify_archive",
    "verify_trust",
]
