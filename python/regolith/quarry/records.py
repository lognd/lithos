"""Registry record store and schemas (WO-16).

Spec: regolith/11; regolith/09 sec. 5. Records are addressed by
``(package, key, revision)`` with append-only revisions and hash pinning;
every record carries a mandatory evidence clause (``by catalog/test/
analysis`` + trust tier). The record *shapes* mirror the corpus
(examples/registry/); the concrete record BODIES are parsed by the Rust
front-end like any source.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import QuarryError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


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


def _verify_hash(record: Record) -> Result[Record, QuarryError]:
    """Structural hash-pinning check: the content hash must be non-empty
    and carry an algorithm tag (``<algo>:<digest>``), per INV-22 pinning.
    """
    if ":" not in record.content_hash or not record.content_hash.split(":", 1)[1]:
        return Err(
            QuarryError(
                kind="invalid_hash",
                message=(
                    f"{record.address.package}/{record.address.key}"
                    f"@{record.address.revision}: malformed content hash "
                    f"{record.content_hash!r}"
                ),
            )
        )
    return Ok(record)


class RecordStore:
    """An append-only, revision-addressed store of registry records."""

    def __init__(self, records: tuple[Record, ...] = ()) -> None:
        """Index ``records`` by ``(package, key)`` -> revision -> Record."""
        self._by_key: dict[tuple[str, str], dict[int, Record]] = {}
        for record in records:
            addr = record.address
            self._by_key.setdefault((addr.package, addr.key), {})[addr.revision] = (
                record
            )
        _log.debug("record store built with %d records", len(records))

    def get(self, key: RecordKey) -> Result[Record, QuarryError]:
        """Fetch the record at ``key`` (exact revision)."""
        revisions = self._by_key.get((key.package, key.key))
        if revisions is None or key.revision not in revisions:
            _log.warning(
                "record not found: %s/%s@%s", key.package, key.key, key.revision
            )
            return Err(
                QuarryError(
                    kind="not_found",
                    message=f"no record {key.package}/{key.key}@{key.revision}",
                )
            )
        return _verify_hash(revisions[key.revision])

    def latest(self, package: str, key: str) -> Result[Record, QuarryError]:
        """Fetch the highest revision of ``(package, key)``."""
        revisions = self._by_key.get((package, key))
        if not revisions:
            _log.warning("record not found: %s/%s (any revision)", package, key)
            return Err(
                QuarryError(
                    kind="not_found",
                    message=f"no record {package}/{key} at any revision",
                )
            )
        newest = revisions[max(revisions)]
        return _verify_hash(newest)
