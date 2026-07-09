"""`magnetite new` -- scaffold a working project from a template (WO-41).

Spec: `docs/spec/toolchain/24-developer-tooling.md` sec. 6;
regolith/11 (a project = manifest + source tree + one lockfile). Emits
``magnetite.toml``, one source file per track (with an honest example
claim that passes ``regolith check`` by construction), a house
``.gitignore``, and a CI snippet.

Templates live as package data under ``templates/`` (wheel-included via
the maturin ``python-source`` root). Source-file EXTENSIONS are read
from the ONE registry through the facade (``compiler.extensions()``,
ground rule 6 / AD-14) -- never hard-coded here or in the template
data, which is why the per-language source bodies are stored under
registry LANGUAGE names (``hematite``/``cuprite``/``fluorite``), not
under filenames carrying an extension.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from typani.result import Err, Ok, Result

from regolith import compiler
from regolith.errors import DocError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The name placeholder substituted in template bodies (magnetite.toml).
_PROJECT_PLACEHOLDER = "__PROJECT__"

# Each template's tracks, named by registry LANGUAGE (not extension --
# the tripwire): the generator maps each to its file extension through
# `compiler.extensions()` at generation time.
_TEMPLATE_TRACKS: dict[str, tuple[str, ...]] = {
    "mech": ("hematite",),
    "elec": ("cuprite",),
    "fluid": ("fluorite",),
    "system": ("hematite", "cuprite", "fluorite"),
}

# Pattern templates (WO-53 deliverable 3, charter sec. 1.4): one entry
# per seed pattern, keyed by pattern name (not track) so `magnetite new
# --template <pattern>` reads unambiguously as "scaffold a consumer of
# this pattern package" -- distinct from the track templates above, and
# read from `templates/patterns/<pattern>/` (own manifest + one source
# file) instead of `templates/{manifests,sources}/`. The catalog grows
# by publishing (charter sec. 3): a new pattern package adds one entry
# here, never new scaffolding machinery.
_PATTERN_TEMPLATE_LANGUAGE: dict[str, str] = {
    "four_bar": "hematite",
    "level_shifter": "cuprite",
}

VALID_TEMPLATES = tuple(_TEMPLATE_TRACKS) + tuple(_PATTERN_TEMPLATE_LANGUAGE)


def _templates_root() -> Path:
    """The bundled ``templates/`` package-data directory."""
    return Path(str(files("regolith.magnetite") / "templates"))


def _extension_for_language() -> dict[str, str]:
    """Map registry language name -> file extension (ground rule 6)."""
    return {lang: ext for ext, lang in compiler.extensions()}


def _dir_is_nonempty(path: Path) -> bool:
    """True if ``path`` exists and contains any entry."""
    return path.is_dir() and any(path.iterdir())


def scaffold_project(
    name: str, template: str, *, parent: Path | None = None
) -> Result[Path, DocError]:
    """Scaffold project ``name`` from ``template`` under ``parent`` (cwd
    by default). Returns the created project directory on success.

    Refuses (``Err``) an unknown template or an existing non-empty
    target directory -- a constructive error value, never an
    exception (house style). Every source file it writes passes
    ``regolith check`` by construction (asserted by a generation test).
    """
    is_pattern = template in _PATTERN_TEMPLATE_LANGUAGE
    if template not in _TEMPLATE_TRACKS and not is_pattern:
        valid = ", ".join(VALID_TEMPLATES)
        _log.error("magnetite new: unknown template %r", template)
        return Err(
            DocError(
                kind="unknown_template",
                message=f"unknown template {template!r}; choose one of: {valid}",
            )
        )

    parent = parent or Path.cwd()
    project_dir = parent / name
    if _dir_is_nonempty(project_dir):
        _log.error("magnetite new: %s exists and is non-empty", project_dir)
        return Err(
            DocError(
                kind="target_exists",
                message=(
                    f"refusing to scaffold into non-empty directory "
                    f"{project_dir}; choose a new name or empty the directory"
                ),
            )
        )

    root = _templates_root()
    ext_of = _extension_for_language()

    # Every file to write, assembled before touching disk so a bad
    # template never leaves a half-scaffolded tree.
    to_write: dict[Path, str] = {}

    if is_pattern:
        language = _PATTERN_TEMPLATE_LANGUAGE[template]
        ext = ext_of.get(language)
        if ext is None:  # pragma: no cover -- registry always has these
            return Err(
                DocError(
                    kind="unknown_language",
                    message=f"registry has no extension for language {language!r}",
                )
            )
        pattern_root = root / "patterns" / template
        manifest = (pattern_root / "manifest.toml").read_text()
        to_write[project_dir / "magnetite.toml"] = manifest.replace(
            _PROJECT_PLACEHOLDER, name
        )
        body = (pattern_root / "source").read_text()
        to_write[project_dir / f"{name}.{ext}"] = body
    else:
        tracks = _TEMPLATE_TRACKS[template]
        manifest = (root / "manifests" / f"{template}.toml").read_text()
        to_write[project_dir / "magnetite.toml"] = manifest.replace(
            _PROJECT_PLACEHOLDER, name
        )

        for language in tracks:
            ext = ext_of.get(language)
            if ext is None:  # pragma: no cover -- registry always has these
                return Err(
                    DocError(
                        kind="unknown_language",
                        message=f"registry has no extension for language {language!r}",
                    )
                )
            body = (root / "sources" / language).read_text()
            # `system` gets one file per track keyed by extension so the
            # three sources never collide; single-track templates use
            # the project name directly.
            stem = name if len(tracks) == 1 else f"{name}_{language}"
            to_write[project_dir / f"{stem}.{ext}"] = body

    to_write[project_dir / ".gitignore"] = (root / "common" / "gitignore").read_text()
    to_write[project_dir / ".github" / "workflows" / "ci.yml"] = (
        root / "common" / "ci.yml"
    ).read_text()

    for path, content in to_write.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        _log.info("magnetite new: wrote %s", path)

    _log.info("magnetite new: scaffolded %s from template %r", project_dir, template)
    return Ok(project_dir)
