"""Loads `stdlib/` data records (WO-45, D135) into :class:`Record` values.

Package BODIES that are ordinary language source (interface/mating/
process declarations a track's own front end parses) live beside their
`magnetite.toml` exactly like `examples/registry/*.cupr`; this module
only loads the plain-TOML data records this WO introduces for packages
with no track-specific syntax yet (materials, contact pairs, fluid
media/pipe tables) -- Python-side data authoring, no new Rust grammar
(this WO's `Language:` header is Python + records, no Rust).

Every row becomes a :class:`regolith.magnetite.records.Record` whose
``content_hash`` is a ``sha256:`` digest of its own canonical TOML row
(so INV-22 pinning has something real to bind to even though nothing
here is signed) and whose ``evidence`` is read straight from the row's
mandatory ``evidence`` table (D58: every stdlib record cites its
tier honestly).
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

from typani.result import Err, Ok, Result

from regolith.errors import MagnetiteError
from regolith.logging_setup import get_logger
from regolith.magnetite.records import Evidence, Record, RecordKey

_log = get_logger(__name__)


def row_hash(table_name: str, row: dict[str, object]) -> str:
    """A stable content hash for one record row (sorted-key repr).

    Public (WO-54): the cost-record loader pins rate/pricing/unit-cost
    rows with the SAME rule this module already applies to every other
    stdlib record row -- one hashing home, never a second rule."""
    canonical = repr(sorted((table_name, str(sorted(row.items())))))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_toml_records(
    path: str, package: str
) -> Result[tuple[Record, ...], MagnetiteError]:
    """Parse every array-of-tables row in the TOML file at ``path``.

    Each top-level array key (``[[material]]``, ``[[contact]]``, ...)
    becomes the record ``kind``; a row's ``key`` field becomes the
    :class:`RecordKey.key`; revision is always 1 (stdlib starter
    content has no revision history yet). A row missing ``key`` or
    ``evidence`` is a loud error -- there is no partial load of one
    file.
    """
    file_path = Path(path)
    if not file_path.is_file():
        _log.warning("stdlib record file not found: %s", file_path)
        return Err(
            MagnetiteError(kind="not_found", message=f"no record file at {file_path}")
        )
    try:
        with file_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        _log.warning("malformed stdlib record TOML at %s: %s", file_path, exc)
        return Err(MagnetiteError(kind="malformed_toml", message=str(exc)))

    records: list[Record] = []
    for table_name, rows in data.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or "key" not in row:
                return Err(
                    MagnetiteError(
                        kind="missing_key",
                        message=f"{file_path}: a {table_name!r} row has no 'key'",
                    )
                )
            evidence_table = row.get("evidence")
            if not isinstance(evidence_table, dict):
                return Err(
                    MagnetiteError(
                        kind="missing_evidence",
                        message=(
                            f"{file_path}: {table_name}/{row['key']} has no "
                            "'evidence' table (D58: every stdlib record must "
                            "cite method/trust_tier/reference)"
                        ),
                    )
                )
            try:
                evidence = Evidence(
                    method=str(evidence_table["method"]),
                    trust_tier=str(evidence_table["trust_tier"]),
                    reference=str(evidence_table["reference"]),
                )
            except KeyError as exc:
                return Err(
                    MagnetiteError(
                        kind="malformed_evidence",
                        message=f"{file_path}: {table_name}/{row['key']}: {exc}",
                    )
                )
            records.append(
                Record(
                    address=RecordKey(package=package, key=str(row["key"]), revision=1),
                    kind=table_name,
                    content_hash=row_hash(table_name, row),
                    evidence=evidence,
                )
            )
    _log.debug(
        "loaded %d stdlib records from %s (package=%s)",
        len(records),
        file_path,
        package,
    )
    return Ok(tuple(records))


def load_package_records(
    package_dir: str, package: str
) -> Result[tuple[Record, ...], MagnetiteError]:
    """Load every ``*.toml`` file under ``package_dir/records/`` (if any)."""
    records_dir = Path(package_dir) / "records"
    if not records_dir.is_dir():
        return Ok(())
    all_records: list[Record] = []
    for toml_file in sorted(records_dir.glob("*.toml")):
        loaded = load_toml_records(str(toml_file), package)
        if loaded.is_err:
            return Err(loaded.danger_err)
        all_records.extend(loaded.danger_ok)
    return Ok(tuple(all_records))
