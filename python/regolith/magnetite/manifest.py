"""magnetite.toml manifest model and local path resolution (WO-16).

Spec: regolith/11 (all). A magnetite package declares its kind, what it
provides, its dependencies and halves, and evidence hashes. Resolution
is local-path only here -- no network, no publishing. Two versions of
one package in a resolution is an error.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import MagnetiteError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_MANIFEST_FILENAME = "magnetite.toml"


class PackageDep(BaseModel):
    """A dependency edge: a package name pinned to a version requirement."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class Manifest(BaseModel):
    """A parsed ``magnetite.toml``: package identity, provides, and depends."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    kinds: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    depends: tuple[PackageDep, ...] = ()
    halves: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()
    lints: tuple[tuple[str, str], ...] = ()


def _flatten_provides(table: dict[str, object]) -> tuple[str, ...]:
    """Flatten ``[provides]`` (category -> names) into ``category:name`` rows."""
    rows: list[str] = []
    for category, names in table.items():
        if not isinstance(names, list):
            continue
        for name in names:
            rows.append(f"{category}:{name}")
    return tuple(sorted(rows))


def _flatten_halves(table: dict[str, object]) -> tuple[str, ...]:
    """Flatten ``[halves]`` (role -> path) into ``role=path`` rows."""
    return tuple(sorted(f"{role}={path}" for role, path in table.items()))


def _flatten_evidence(table: dict[str, object]) -> tuple[str, ...]:
    """Flatten ``[evidence]`` (reference -> hash) into ``reference=hash`` rows."""
    return tuple(sorted(f"{ref}={digest}" for ref, digest in table.items()))


def _flatten_lints(table: dict[str, object]) -> tuple[tuple[str, str], ...]:
    """Flatten ``[lints]`` (code -> action) into ``(code, action)`` rows
    (WO-40 deliverable 4). A non-string action is dropped here; an
    action string outside ``allow``/``warn``/``deny`` is kept (named,
    not silently normalized) so the Rust boundary's own drop-and-log is
    the single place it is ever discarded (see
    `regolith.magnetite.lints` for the corresponding waive-ladder
    assertion)."""
    rows: list[tuple[str, str]] = []
    for code, action in table.items():
        if not isinstance(action, str):
            continue
        rows.append((str(code).lower(), action))
    return tuple(sorted(rows))


def load_manifest(path: str) -> Result[Manifest, MagnetiteError]:
    """Parse a ``magnetite.toml`` at ``path`` into a :class:`Manifest`.

    Record and manifest *parsing* is the Rust front-end (WO-16 note); this
    reads the TOML shell and validates the package identity.
    """
    manifest_path = Path(path)
    if manifest_path.is_dir():
        manifest_path = manifest_path / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        _log.warning("magnetite.toml not found at %s", manifest_path)
        return Err(
            MagnetiteError(kind="not_found", message=f"no manifest at {manifest_path}")
        )
    try:
        with manifest_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        _log.warning("malformed magnetite.toml at %s: %s", manifest_path, exc)
        return Err(MagnetiteError(kind="malformed_toml", message=str(exc)))

    package = data.get("package")
    if not isinstance(package, dict) or "name" not in package:
        return Err(
            MagnetiteError(
                kind="missing_identity",
                message=f"{manifest_path}: [package] table missing or has no name",
            )
        )

    depends_table = data.get("depends", {})
    if not isinstance(depends_table, dict):
        return Err(
            MagnetiteError(
                kind="malformed_depends",
                message=f"{manifest_path}: [depends] must be a table",
            )
        )
    depends = tuple(
        sorted(
            (
                PackageDep(name=name, version=str(version))
                for name, version in depends_table.items()
            ),
            key=lambda d: d.name,
        )
    )

    lints_table = data.get("lints", {})
    if not isinstance(lints_table, dict):
        return Err(
            MagnetiteError(
                kind="malformed_lints",
                message=f"{manifest_path}: [lints] must be a table",
            )
        )

    manifest = Manifest(
        name=package["name"],
        version=str(package.get("version", "")),
        kinds=tuple(package.get("kinds", ())),
        provides=_flatten_provides(data.get("provides", {})),
        depends=depends,
        halves=_flatten_halves(data.get("halves", {})),
        evidence_hashes=_flatten_evidence(data.get("evidence", {})),
        lints=_flatten_lints(lints_table),
    )
    _log.debug(
        "loaded manifest %s@%s from %s", manifest.name, manifest.version, manifest_path
    )
    return Ok(manifest)


def resolve_dependencies(
    root: Manifest, search_paths: tuple[str, ...]
) -> Result[tuple[Manifest, ...], MagnetiteError]:
    """Resolve ``root``'s dependency closure from local ``search_paths``.

    Two versions of one package anywhere in the closure is an error.
    """
    resolved: dict[str, Manifest] = {}
    requested_versions: dict[str, str] = {}
    pending: list[PackageDep] = list(root.depends)

    while pending:
        dep = pending.pop(0)
        if (
            dep.name in requested_versions
            and requested_versions[dep.name] != dep.version
        ):
            _log.warning(
                "two versions of %s requested: %s and %s",
                dep.name,
                requested_versions[dep.name],
                dep.version,
            )
            return Err(
                MagnetiteError(
                    kind="version_conflict",
                    message=(
                        f"two versions of package {dep.name!r} requested: "
                        f"{requested_versions[dep.name]!r} and {dep.version!r}"
                    ),
                )
            )
        requested_versions[dep.name] = dep.version
        if dep.name in resolved:
            continue
        found: Manifest | None = None
        for search_path in search_paths:
            candidate = Path(search_path) / dep.name / _MANIFEST_FILENAME
            if candidate.is_file():
                loaded = load_manifest(str(candidate))
                if loaded.is_err:
                    return Err(loaded.danger_err)
                found = loaded.danger_ok
                break
        if found is None:
            _log.warning("dependency %s not found in search paths", dep.name)
            return Err(
                MagnetiteError(
                    kind="unresolved_dependency",
                    message=f"dependency {dep.name!r} not found in search paths",
                )
            )
        resolved[dep.name] = found
        pending.extend(found.depends)

    _log.debug("resolved %d dependencies for %s", len(resolved), root.name)
    return Ok(tuple(resolved[name] for name in sorted(resolved)))
