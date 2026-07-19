"""Serializes loaded registry records for the Rust rule engine (WO-87, D198).

The ONE record loader is magnetite (this package); the Rust side never
reads TOML. This module walks the same ``<package>/records/*.toml``
files the stdlib loaders read and serializes every ``[[component]]``
row's scalar fields into the ``kind: "registry.records"`` realized-
input payload ``regolith-lower``'s ``registry`` module deserializes --
record key -> {field name -> value text}, content-hashed like every
realized input so INV-22 pinning holds unchanged.

Scoped to ``component`` rows deliberately: components are what a board
instantiates via ``vendor(<key>)``, and D198 scopes the payload to
"exactly the fields rule predicates dereference" -- materials, cost
rows, and section tables have their own typed loaders and never appear
in a rule predicate's record dereference.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: The realized-input kind carrying registry records (D198). The Rust
#: reader (`regolith-lower/src/registry.rs`) declares the same string;
#: the pytest suite pins the two against drift.
# frob:doc docs/modules/py-magnetite.md#magnetite-records-payload
REGISTRY_RECORDS_KIND = "registry.records"

#: The payload's `subject` (not per-board: the record slice is
#: session-wide input, matched by kind alone).
# frob:doc docs/modules/py-magnetite.md#magnetite-records-payload
REGISTRY_RECORDS_SUBJECT = "registry"


# frob:doc docs/modules/py-magnetite.md#magnetite-records-payload
def component_field_rows(record_paths: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Every ``[[component]]`` row's scalar fields under each search
    root's ``<package>/records/*.toml`` files, keyed by record key.

    Values are rendered as the value TEXT the Rust evaluator's quantity
    grammar parses (floats drop a trailing ``.0``; booleans render as
    ``1``/``0``). Non-scalar fields (the ``evidence`` table, lists) are
    skipped -- they are provenance, not rule facts. A malformed file is
    logged and skipped, never fatal: its records simply stay missing
    and dependent rules defer (the same posture as the Rust reader).
    """
    rows: dict[str, dict[str, str]] = {}
    for root in record_paths:
        root_path = Path(root)
        if not root_path.is_dir():
            _log.debug("records payload: search root %s is not a directory", root)
            continue
        for toml_file in sorted(root_path.glob("*/records/*.toml")):
            try:
                with toml_file.open("rb") as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                _log.warning(
                    "records payload: skipping malformed %s: %s", toml_file, exc
                )
                continue
            components = data.get("component")
            if not isinstance(components, list):
                continue
            for row in components:
                if not isinstance(row, dict):
                    continue
                key = row.get("key")
                if not isinstance(key, str):
                    continue
                fields = {
                    name: _value_text(value)
                    for name, value in row.items()
                    if name != "key" and isinstance(value, (str, int, float, bool))
                }
                rows[key] = fields
    _log.info("records payload: %d component record(s) serialized", len(rows))
    return rows


# frob:doc docs/modules/py-magnetite.md#magnetite-records-payload
def registry_records_payload(
    record_paths: tuple[str, ...],
) -> tuple[str, str, str, bytes] | None:
    """The ``(digest, kind, subject, payload_bytes)`` realized-input
    tuple carrying every component record under ``record_paths``, or
    ``None`` when no records resolve (the honest-absence path: rules
    then defer naming the missing fact, never a fabricated payload).

    Returned as primitives so this module stays import-light; the CLI/
    orchestrator wraps it in :class:`regolith.compiler.RealizedInput`.
    """
    rows = component_field_rows(record_paths)
    if not rows:
        return None
    payload = json.dumps({"records": rows}, sort_keys=True).encode("utf-8")
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    _log.debug("records payload: digest=%s bytes=%d", digest, len(payload))
    return (digest, REGISTRY_RECORDS_KIND, REGISTRY_RECORDS_SUBJECT, payload)


def _value_text(value: str | int | float | bool) -> str:
    """Render one scalar record field as evaluator-parseable text."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return str(value)
