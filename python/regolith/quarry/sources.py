"""Registry sources: the manifest ``[sources]`` table (substrate/11 sec. 10.2).

Sources are declared in the manifest; there is no ambient default inside
the languages (sec. 6's no-ambient-state rule). The ``[sources]`` table
names each registry (the public lodestone, a vendor's, a company mirror)
and maps dependency namespaces onto them. The toolchain ships configured
with the public registry, so the common case is zero ceremony -- but the
resolution input is always the manifest.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import QuarryError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The public lodestone, shipped as the default source so a project needs
# no `[sources]` table for the common case (substrate/11 sec. 10.2). It is
# a plain default, not ambient state: it is materialized into the resolved
# `Sources` and thus reviewable, never consulted implicitly.
DEFAULT_SOURCE_NAME = "lodestone"


class Registry(BaseModel):
    """One named registry: its sparse-index and archive-store base URLs."""

    model_config = ConfigDict(frozen=True)

    name: str
    index_url: str
    archive_url: str


class Sources(BaseModel):
    """The resolved source map: namespace prefix -> registry, plus a default."""

    model_config = ConfigDict(frozen=True)

    registries: tuple[Registry, ...]
    # (namespace-prefix, registry-name); longest matching prefix wins.
    routes: tuple[tuple[str, str], ...] = ()
    default: str = DEFAULT_SOURCE_NAME

    def _registry(self, name: str) -> Registry | None:
        return next((r for r in self.registries if r.name == name), None)

    def route(self, package: str) -> Result[Registry, QuarryError]:
        """The registry a ``package`` resolves through (longest-prefix match).

        Namespace routes win by longest matching prefix; an unrouted
        package falls to the default source. A route or default that names
        an undeclared registry is an error (no silent misrouting).
        """
        best_name = self.default
        best_len = -1
        for prefix, reg_name in self.routes:
            if (package == prefix or package.startswith(prefix + ".")) and len(
                prefix
            ) > best_len:
                best_name, best_len = reg_name, len(prefix)
        registry = self._registry(best_name)
        if registry is None:
            return Err(
                QuarryError(
                    kind="unknown_source",
                    message=f"package {package!r} routes to undeclared source "
                    f"{best_name!r}",
                )
            )
        _log.debug("package %s routes to registry %s", package, registry.name)
        return Ok(registry)
