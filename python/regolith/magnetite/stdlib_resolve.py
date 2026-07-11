"""Resolves ``std.*`` record search paths for CLI builds.

The CLI verbs that run discharge (``build``/``ship``/``test``) supply
``cost_record_paths``/``frame_record_paths``/``plan_record_paths`` to
:func:`regolith.orchestrator.orchestrate.build` -- but until this module
existed, nothing ever populated them: a project's own ``[depends]``
table names ``std.civil``/``std.cost``/etc, and the loaders
(``load_cost_records``/``load_frame_records``/``load_plan_records``)
gladly walk a search-path root's package subdirectories for
``records/*.toml``, but no caller ever pointed them at the `stdlib/`
tree outside the project root. Only the test suite discharged std.*
claims, by hard-coding ``("stdlib",)`` from the repo root.

:func:`resolve_record_search_paths` closes that gap: given a project
root, it reads the project's ``[depends]`` table, and -- IF at least
one ``std.*`` package is declared -- locates the stdlib root directory
(the directory whose children are ``std.civil/``, ``std.cost/``, etc,
each carrying its own ``magnetite.toml``) by trying, in order:

1. an explicit ``records.stdlib_root`` config key (the ordinary
   4-level `regolith.config` doctrine: global file < project
   ``[tool.regolith]`` < env < an explicit override passed here);
2. a vendored copy under ``<project_root>/vendor/`` (vendoring pins
   win: an air-gapped/reproducible build should never silently fall
   back past what it vendored);
3. the development fallback: walk upward from the project root, and
   independently from this module's own installed location, looking
   for a ``stdlib/`` directory containing the sentinel package
   ``std.quantities`` (present in every stdlib tree, WO-45).

A project with no ``std.*`` dependency resolves to ``()`` (no search
path is added -- nothing to look for). A ``std.*`` dependency that
resolves to NO stdlib root ALSO returns ``()``, not an error: the
existing honest-deferral posture (`frame_section_family_not_landed`,
`cost_record_unresolved`, ...) already names the missing record at
discharge time, and resolution failure is not the layer that should
turn that into a hard error.
"""

from __future__ import annotations

from pathlib import Path

from regolith import config
from regolith.logging_setup import get_logger
from regolith.magnetite.manifest import load_manifest

_log = get_logger(__name__)

#: Present in every real stdlib tree (WO-45) -- the cheapest directory
#: check that reliably tells "this is a stdlib root" from "this is not".
_STDLIB_SENTINEL_PACKAGE = "std.quantities"
_VENDOR_DIRNAME = "vendor"
_STD_DEP_PREFIX = "std."
_CONFIG_KEY = "records.stdlib_root"


def _is_stdlib_root(candidate: Path) -> bool:
    """``candidate`` looks like a stdlib root: it has the sentinel
    package with its own manifest directly beneath it."""
    return (candidate / _STDLIB_SENTINEL_PACKAGE / "magnetite.toml").is_file()


def _config_override(project_root: Path) -> Path | None:
    """The ``records.stdlib_root`` config value, if set and it actually
    names a stdlib root (a stale/typo'd override is logged and ignored,
    never a hard error -- the dev-walk fallback still has a chance)."""
    resolved = config.get_effective(_CONFIG_KEY, project_root)
    if resolved.is_err:
        # Unregistered key or bad file -- config.py itself already
        # logged the detail; treat as "no override" here.
        return None
    effective = resolved.danger_ok
    value = effective.value
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if _is_stdlib_root(candidate):
        _log.debug(
            "stdlib resolve: config override source=%s path=%s",
            effective.source,
            candidate,
        )
        return candidate
    _log.warning(
        "stdlib resolve: %s=%r (source=%s) has no %s package beneath it; ignoring",
        _CONFIG_KEY,
        value,
        effective.source,
        _STDLIB_SENTINEL_PACKAGE,
    )
    return None


def _vendor_candidate(project_root: Path) -> Path | None:
    """A vendored stdlib copy directly under ``<project_root>/vendor/``,
    if the vendoring convention (``magnetite vendor``) ever lays out an
    extracted package tree there rather than only content-addressed
    archives -- vendoring pins win over the dev-walk fallback."""
    candidate = project_root / _VENDOR_DIRNAME
    if _is_stdlib_root(candidate):
        return candidate
    return None


def _walk_up_for_stdlib(start: Path) -> Path | None:
    """Walk ``start`` and its ancestors looking for a ``stdlib/`` child
    that is a stdlib root."""
    candidate = start if start.is_dir() else start.parent
    seen: set[Path] = set()
    while candidate not in seen:
        seen.add(candidate)
        stdlib_dir = candidate / "stdlib"
        if _is_stdlib_root(stdlib_dir):
            return stdlib_dir
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _dev_walk_candidate(project_root: Path) -> Path | None:
    """The development fallback (precedence c): try walking up from the
    project root first (covers a project living inside this checkout),
    then independently from this module's own installed location
    (covers an out-of-tree project, or a build run from an overlay/temp
    copy of a project whose real stdlib is this checkout's own)."""
    found = _walk_up_for_stdlib(project_root)
    if found is not None:
        return found
    return _walk_up_for_stdlib(Path(__file__).resolve())


def resolve_record_search_paths(project_root: str) -> tuple[str, ...]:
    """The record search-path roots CLI discharge should pass as
    ``cost_record_paths``/``frame_record_paths``/``plan_record_paths``
    for the project at ``project_root``.

    Returns the minimal root set the loaders need: a single stdlib
    root when one resolves (the loaders already walk EVERY package
    subdirectory of a search-path root, so one root covers every
    ``std.*`` package), or ``()`` when the project declares no
    ``std.*`` dependency or none resolves.
    """
    root = Path(project_root)
    manifest_result = load_manifest(str(root))
    if manifest_result.is_err:
        # Routine for manifest-less roots and bare `check` files (the
        # WO-87 check-path resolver probes here on every run), so debug,
        # not info -- a declared-but-unresolved std.* dep below stays
        # info.
        _log.debug(
            "stdlib resolve: no manifest at %s (%s); no std.* search path added",
            root,
            manifest_result.danger_err.message,
        )
        return ()
    manifest = manifest_result.danger_ok
    std_deps = tuple(
        dep.name for dep in manifest.depends if dep.name.startswith(_STD_DEP_PREFIX)
    )
    if not std_deps:
        _log.debug(
            "stdlib resolve: project %s declares no std.* dependency", project_root
        )
        return ()

    override = _config_override(root)
    if override is not None:
        _log.info("stdlib resolve: using config override root=%s", override)
        return (str(override),)

    vendored = _vendor_candidate(root)
    if vendored is not None:
        _log.info("stdlib resolve: using vendored stdlib root=%s", vendored)
        return (str(vendored),)

    dev_found = _dev_walk_candidate(root)
    if dev_found is not None:
        _log.info("stdlib resolve: using dev-walk stdlib root=%s", dev_found)
        return (str(dev_found),)

    _log.info(
        "stdlib resolve: no stdlib root found for project=%s declared_std_deps=%s "
        "-- std.* records will defer honestly at discharge",
        project_root,
        std_deps,
    )
    return ()


def resolve_pack_source_roots(project_root: str) -> tuple[str, ...]:
    """The rule-pack SOURCE roots a CLI build/check should add to its
    compile set for the project at ``project_root`` (D201, WO-87 close-
    out F118).

    A project's own ``[depends]`` table already gets its ``std.*``
    RECORD search path resolved by :func:`resolve_record_search_paths`
    (D192) -- but a design that ``attach``es a stdlib rule pack (e.g.
    ``std.board_correctness``'s ``pdn_decoupling``) still needed that
    pack's source file passed explicitly on the CLI or copied locally
    for the name to resolve, even though the dependency was already
    declared. This closes that gap the SAME way: reuse the resolved
    stdlib root, then return the per-dependency PACKAGE DIRECTORY (not
    the whole stdlib tree) for each declared ``std.*`` name that
    actually exists beneath it -- the core compiler walks a directory
    argument for recognized-extension source files exactly like a
    project root, so each returned directory contributes its pack
    sources (visibility) without attaching anything (attachment stays
    the design's own explicit ``attach``/``process=`` act -- D201).

    A project with no ``std.*`` dependency, or one that resolves to no
    stdlib root, returns ``()`` -- identical to today's behavior (the
    dependency's rules simply are not in session; the attachment site's
    existing unknown-pack diagnostic already names it).
    """
    root = Path(project_root)
    manifest_result = load_manifest(str(root))
    if manifest_result.is_err:
        return ()
    manifest = manifest_result.danger_ok
    std_deps = tuple(
        dep.name for dep in manifest.depends if dep.name.startswith(_STD_DEP_PREFIX)
    )
    if not std_deps:
        return ()

    stdlib_roots = resolve_record_search_paths(project_root)
    if not stdlib_roots:
        return ()
    # `resolve_record_search_paths` returns a single root today (one
    # stdlib tree covers every std.* package beneath it); walk it the
    # same way for forward compatibility if that ever changes.
    pack_roots: list[str] = []
    for stdlib_root in stdlib_roots:
        for dep_name in std_deps:
            candidate = Path(stdlib_root) / dep_name
            if candidate.is_dir():
                pack_roots.append(str(candidate))
    if pack_roots:
        _log.info(
            "stdlib resolve: pack source roots for project=%s -> %s",
            project_root,
            pack_roots,
        )
    else:
        _log.debug(
            "stdlib resolve: no pack source roots resolved for project=%s "
            "declared_std_deps=%s",
            project_root,
            std_deps,
        )
    return tuple(pack_roots)


def resolve_pack_source_roots_for_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Pack-source roots (D201) for a bare ``regolith check <files...>``
    invocation -- the :func:`resolve_pack_source_roots` counterpart to
    :func:`resolve_records_roots_for_paths`, walking for the nearest
    ``magnetite.toml`` ancestor exactly the same way. A ``check`` run
    with no manifest anywhere above its files resolves to ``()``, same
    as today.
    """
    for raw in paths:
        start = Path(raw).resolve()
        candidate = start if start.is_dir() else start.parent
        probe = candidate
        seen: set[Path] = set()
        while probe not in seen:
            seen.add(probe)
            if (probe / "magnetite.toml").is_file():
                resolved = resolve_pack_source_roots(str(probe))
                if resolved:
                    _log.debug(
                        "stdlib resolve (check): pack source manifest root %s -> %s",
                        probe,
                        resolved,
                    )
                    return resolved
                break
            parent = probe.parent
            if parent == probe:
                break
            probe = parent
    return ()


def resolve_records_roots_for_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Record search roots for a bare ``regolith check <files...>``
    invocation (WO-87/D198): unlike the build verbs, ``check`` takes
    loose files/roots with no guaranteed project manifest, so the
    resolution tries, per given path, the nearest ancestor directory
    carrying a ``magnetite.toml`` (then the ordinary
    :func:`resolve_record_search_paths` precedence), and falls back to
    the development stdlib walk from the path itself. First hit wins;
    no hit returns ``()`` and record-dependent rules defer honestly.
    """
    for raw in paths:
        start = Path(raw).resolve()
        candidate = start if start.is_dir() else start.parent
        probe = candidate
        seen: set[Path] = set()
        while probe not in seen:
            seen.add(probe)
            if (probe / "magnetite.toml").is_file():
                resolved = resolve_record_search_paths(str(probe))
                if resolved:
                    _log.debug(
                        "stdlib resolve (check): manifest root %s -> %s",
                        probe,
                        resolved,
                    )
                    return resolved
                break
            parent = probe.parent
            if parent == probe:
                break
            probe = parent
        dev_found = _walk_up_for_stdlib(candidate)
        if dev_found is not None:
            _log.debug("stdlib resolve (check): dev-walk root %s", dev_found)
            return (str(dev_found),)
    _log.debug("stdlib resolve (check): no records root for %s", paths)
    return ()
