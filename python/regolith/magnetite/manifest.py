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


class CostProfile(BaseModel):
    """One ``[profiles.cost.<name>]`` table (WO-54; toolchain/27 sec. 1.2).

    A profile names the records an estimate consumes: the quantity
    basis, rate-record refs (``labor``/``process_rates``), ordered
    pricing-source refs, the markup knob, and the currency unit.
    Everything priced is a record REF resolved and hash-pinned at
    build time (INV-22) -- the profile itself carries no prices.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    quantity: float = 1.0
    labor: tuple[str, ...] = ()
    process_rates: tuple[str, ...] = ()
    pricing: tuple[str, ...] = ()
    markup: float = 1.0
    currency: str = "USD"


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
    # WO-54 (toolchain/27 sec. 1.2): the project's declared cost
    # profiles, name-sorted, plus the `[profiles.cost.default]` pick.
    cost_profiles: tuple[CostProfile, ...] = ()
    default_cost_profile: str | None = None


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


def _ref_list(value: object) -> tuple[str, ...]:
    """A record-ref field's value as a tuple: a bare string or a list.

    ``labor = "rates.x"`` and ``pricing = ["a", "b"]`` are both legal
    (toolchain/27 sec. 1.2 writes both shapes); anything non-string is
    dropped here -- the profile parse below rejects structurally
    malformed tables loudly, this helper only normalizes shape.
    """
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(v) for v in value if isinstance(v, str))
    return ()


def _parse_cost_profiles(
    data: dict[str, object], manifest_path: Path
) -> Result[tuple[tuple[CostProfile, ...], str | None], MagnetiteError]:
    """Parse ``[profiles.cost.<name>]`` tables (WO-54, toolchain/27 sec. 1.2).

    Returns the name-sorted profile tuple plus the
    ``[profiles.cost.default]`` pick (its ``profile = "<name>"`` value).
    A structurally malformed table, a non-positive quantity/markup, or
    a default naming no declared profile is a loud, named error --
    never a silently-dropped profile.
    """
    profiles_table = data.get("profiles", {})
    if not isinstance(profiles_table, dict):
        return Err(
            MagnetiteError(
                kind="malformed_profiles",
                message=f"{manifest_path}: [profiles] must be a table",
            )
        )
    cost_table = profiles_table.get("cost", {})
    if not isinstance(cost_table, dict):
        return Err(
            MagnetiteError(
                kind="malformed_profiles",
                message=f"{manifest_path}: [profiles.cost] must be a table",
            )
        )

    profiles: list[CostProfile] = []
    default: str | None = None
    for name, table in cost_table.items():
        if not isinstance(table, dict):
            return Err(
                MagnetiteError(
                    kind="malformed_profiles",
                    message=(
                        f"{manifest_path}: [profiles.cost.{name}] must be a table"
                    ),
                )
            )
        if name == "default":
            picked = table.get("profile")
            if not isinstance(picked, str) or not picked:
                return Err(
                    MagnetiteError(
                        kind="malformed_profiles",
                        message=(
                            f"{manifest_path}: [profiles.cost.default] must "
                            'carry `profile = "<name>"`'
                        ),
                    )
                )
            default = picked
            continue
        quantity = table.get("quantity", 1.0)
        markup = table.get("markup", 1.0)
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or quantity <= 0
        ):
            return Err(
                MagnetiteError(
                    kind="malformed_profiles",
                    message=(
                        f"{manifest_path}: [profiles.cost.{name}] quantity "
                        f"must be a positive number, got {quantity!r}"
                    ),
                )
            )
        if (
            isinstance(markup, bool)
            or not isinstance(markup, (int, float))
            or markup <= 0
        ):
            return Err(
                MagnetiteError(
                    kind="malformed_profiles",
                    message=(
                        f"{manifest_path}: [profiles.cost.{name}] markup "
                        f"must be a positive number, got {markup!r}"
                    ),
                )
            )
        profiles.append(
            CostProfile(
                name=str(name),
                quantity=float(quantity),
                labor=_ref_list(table.get("labor")),
                process_rates=_ref_list(table.get("process_rates")),
                pricing=_ref_list(table.get("pricing")),
                markup=float(markup),
                currency=str(table.get("currency", "USD")),
            )
        )

    declared = {p.name for p in profiles}
    if default is not None and default not in declared:
        return Err(
            MagnetiteError(
                kind="unknown_default_profile",
                message=(
                    f"{manifest_path}: [profiles.cost.default] names "
                    f"{default!r}, but the declared profiles are "
                    f"{sorted(declared)}"
                ),
            )
        )
    _log.debug(
        "parsed %d cost profile(s) from %s (default=%s)",
        len(profiles),
        manifest_path,
        default,
    )
    return Ok((tuple(sorted(profiles, key=lambda p: p.name)), default))


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

    cost_result = _parse_cost_profiles(data, manifest_path)
    if cost_result.is_err:
        return Err(cost_result.danger_err)
    cost_profiles, default_cost_profile = cost_result.danger_ok

    manifest = Manifest(
        name=package["name"],
        version=str(package.get("version", "")),
        kinds=tuple(package.get("kinds", ())),
        provides=_flatten_provides(data.get("provides", {})),
        depends=depends,
        halves=_flatten_halves(data.get("halves", {})),
        evidence_hashes=_flatten_evidence(data.get("evidence", {})),
        lints=_flatten_lints(lints_table),
        cost_profiles=cost_profiles,
        default_cost_profile=default_cost_profile,
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
