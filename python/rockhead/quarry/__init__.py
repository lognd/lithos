"""The rockhead quarry: manifests, records, coherence, and the registry.

Owns the package layer (AD-1): manifest parsing and local resolution
(:mod:`~rockhead.quarry.manifest`), immutable revisioned records
(:mod:`~rockhead.quarry.records`), trait coherence
(:mod:`~rockhead.quarry.coherence`), and the lodestone registry client
(substrate/11 sec. 10): a sparse index (:mod:`~rockhead.quarry.index`),
manifest-declared sources (:mod:`~rockhead.quarry.sources`), a
content-addressed httpx client with hash-pinned fetch
(:mod:`~rockhead.quarry.client`, INV-22), signature-carried trust
(:mod:`~rockhead.quarry.trust`, INV-14), and vendoring
(:mod:`~rockhead.quarry.vendor`).
"""

from __future__ import annotations

from rockhead.quarry.client import RegistryClient, verify_archive
from rockhead.quarry.coherence import ContactKey, resolve_most_specific
from rockhead.quarry.index import (
    IndexEntry,
    latest_version,
    parse_index,
    select_version,
)
from rockhead.quarry.manifest import (
    Manifest,
    PackageDep,
    load_manifest,
    resolve_dependencies,
)
from rockhead.quarry.records import Evidence, Record, RecordKey, RecordStore
from rockhead.quarry.sources import Registry, Sources
from rockhead.quarry.trust import KeySet, Signature, TrustTier, verify_trust
from rockhead.quarry.vendor import VendorPin, VendorStore, vendor

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
