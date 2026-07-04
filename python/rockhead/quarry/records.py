"""Registry record store and schemas (WO-16).

Spec: substrate/11; substrate/09 sec. 5. Records are addressed by
``(package, key, revision)`` with append-only revisions and hash pinning;
every record carries a mandatory evidence clause (``by catalog/test/
analysis`` + trust tier). The record *shapes* mirror the corpus
(examples/registry/); the concrete record BODIES are parsed by the Rust
front-end like any source.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Result

from rockhead.errors import QuarryError


class Evidence(BaseModel):
    """The mandatory evidence clause on every record."""

    model_config = ConfigDict(frozen=True)

    method: str  # catalog | test | analysis
    trust_tier: str
    reference: str


class RecordKey(BaseModel):
    """A record address: package, key, and revision."""

    model_config = ConfigDict(frozen=True)

    package: str
    key: str
    revision: int


class Record(BaseModel):
    """One registry record with its content hash and evidence.

    ``kind`` selects the schema the ``body`` conforms to (material,
    contact, process, component, family, protocol, intent-verb); the body
    is opaque here and typed by the Rust front-end.
    """

    model_config = ConfigDict(frozen=True)

    address: RecordKey
    kind: str
    content_hash: str
    evidence: Evidence


class RecordStore:
    """An append-only, revision-addressed store of registry records."""

    def get(self, key: RecordKey) -> Result[Record, QuarryError]:
        """Fetch the record at ``key`` (exact revision)."""
        raise NotImplementedError(
            "STUB WO-16: revision-addressed lookup, hash-verified"
        )

    def latest(self, package: str, key: str) -> Result[Record, QuarryError]:
        """Fetch the highest revision of ``(package, key)``."""
        raise NotImplementedError(
            "STUB WO-16: max-revision lookup over the append-only log"
        )
