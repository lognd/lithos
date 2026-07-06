"""The regolith quarry: manifests, records, coherence, and the registry.

Owns the package layer (AD-1): manifest parsing and local resolution
(:mod:`~regolith.quarry.manifest`), immutable revisioned records
(:mod:`~regolith.quarry.records`), trait coherence
(:mod:`~regolith.quarry.coherence`), and the lodestone registry client
(regolith/11 sec. 10): a sparse index (:mod:`~regolith.quarry.index`),
manifest-declared sources (:mod:`~regolith.quarry.sources`), a
content-addressed httpx client with hash-pinned fetch
(:mod:`~regolith.quarry.client`, INV-22), signature-carried trust
(:mod:`~regolith.quarry.trust`, INV-14), and vendoring
(:mod:`~regolith.quarry.vendor`).
"""

from __future__ import annotations

from regolith.quarry.client import RegistryClient, verify_archive
from regolith.quarry.coherence import ContactKey, resolve_most_specific
from regolith.quarry.index import (
    IndexEntry,
    latest_version,
    parse_index,
    select_version,
)
from regolith.quarry.manifest import (
    Manifest,
    PackageDep,
    load_manifest,
    resolve_dependencies,
)
from regolith.quarry.records import Evidence, Record, RecordKey, RecordStore
from regolith.quarry.sources import Registry, Sources
from regolith.quarry.trust import KeySet, Signature, TrustTier, verify_trust
from regolith.quarry.vendor import VendorPin, VendorStore, vendor

__all__ = [
    "ContactKey",
    "Evidence",
    "IndexEntry",
    "KeySet",
    "Manifest",
    "PackageDep",
    "Record",
    "RecordKey",
    "RecordStore",
    "Registry",
    "RegistryClient",
    "Signature",
    "Sources",
    "TrustTier",
    "VendorPin",
    "VendorStore",
    "latest_version",
    "load_manifest",
    "parse_index",
    "resolve_dependencies",
    "resolve_most_specific",
    "select_version",
    "vendor",
    "verify_archive",
    "verify_trust",
]
