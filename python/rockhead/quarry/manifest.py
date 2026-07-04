"""quarry.toml manifest model and local path resolution (WO-16).

Spec: substrate/11 (all). A quarry package declares its kind, what it
provides, its dependencies and halves, and evidence hashes. Resolution
is local-path only here -- no network, no publishing. Two versions of
one package in a resolution is an error.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Result

from rockhead.errors import QuarryError


class PackageDep(BaseModel):
    """A dependency edge: a package name pinned to a version requirement."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class Manifest(BaseModel):
    """A parsed ``quarry.toml``: package identity, provides, and depends."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    kinds: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    depends: tuple[PackageDep, ...] = ()
    halves: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()


def load_manifest(path: str) -> Result[Manifest, QuarryError]:
    """Parse a ``quarry.toml`` at ``path`` into a :class:`Manifest`.

    Record and manifest *parsing* is the Rust front-end (WO-16 note); this
    reads the TOML shell and validates the package identity.
    """
    raise NotImplementedError(
        "STUB WO-16: read quarry.toml, validate identity, build Manifest"
    )


def resolve_dependencies(
    root: Manifest, search_paths: tuple[str, ...]
) -> Result[tuple[Manifest, ...], QuarryError]:
    """Resolve ``root``'s dependency closure from local ``search_paths``.

    Two versions of one package anywhere in the closure is an error.
    """
    raise NotImplementedError(
        "STUB WO-16: walk depends over local paths; two-versions-of-one-pkg -> error"
    )
