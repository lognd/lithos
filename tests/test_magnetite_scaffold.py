"""WO-41 `magnetite new`: template scaffolding + generation check.

The load-bearing test is ``test_every_template_checks_green``: every
template must generate a project whose sources pass ``regolith check``
by construction (the WO's acceptance criterion), so a template that
drifts out of the language is caught here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith import compiler
from regolith.magnetite.scaffold import VALID_TEMPLATES, scaffold_project


@pytest.mark.parametrize("template", VALID_TEMPLATES)
def test_every_template_checks_green(template: str, tmp_path: Path) -> None:
    result = scaffold_project("demo", template, parent=tmp_path)
    assert result.is_ok, f"scaffold({template}) returned Err: {result}"
    project = result.danger_ok
    assert (project / "magnetite.toml").is_file()
    assert (project / ".gitignore").is_file()
    assert (project / ".github" / "workflows" / "ci.yml").is_file()

    outcome = compiler.check((str(project),))
    assert outcome.is_ok, f"check errored on template {template!r}: {outcome}"
    assert outcome.danger_ok.ok, (
        f"template {template!r} does not check green: {outcome.danger_ok.rendered}"
    )


def test_generated_source_extensions_come_from_registry(tmp_path: Path) -> None:
    """The tripwire: a generated source FILE's extension is always one the
    registry knows -- the scaffold derives it, never bakes it in."""
    registry_exts = {ext for ext, _lang in compiler.extensions()}
    result = scaffold_project("demo", "system", parent=tmp_path)
    assert result.is_ok
    project = result.danger_ok
    source_exts = {
        p.suffix.lstrip(".")
        for p in project.iterdir()
        if p.is_file() and p.suffix and p.name != "magnetite.toml"
    }
    source_exts.discard("gitignore")  # `.gitignore` has no real extension
    assert source_exts <= registry_exts


def test_scaffold_code_hardcodes_no_extension() -> None:
    """The scaffold module and its manifest data must not spell any
    extension literally (ground rule 6) -- they route through the
    registry. Source template bodies legitimately name the `std.*`
    packages and are excluded."""
    import re

    from regolith.magnetite import scaffold

    scaffold_src = Path(scaffold.__file__).read_text()
    templates = Path(scaffold.__file__).parent / "templates"
    to_scan = [scaffold_src]
    to_scan += [p.read_text() for p in (templates / "manifests").iterdir()]
    to_scan += [p.read_text() for p in (templates / "common").iterdir()]
    registry_exts = {ext for ext, _lang in compiler.extensions()}
    for text in to_scan:
        for ext in registry_exts:
            # A file-extension use is `.<ext>` not followed by more
            # letters (so the `std.fluorite` package path -- `.fluo`
            # followed by `rite` -- is correctly NOT a match).
            assert not re.search(rf"\.{ext}(?![a-z])", text), f"hard-coded .{ext}"


def test_scaffold_refuses_nonempty_directory(tmp_path: Path) -> None:
    first = scaffold_project("demo", "mech", parent=tmp_path)
    assert first.is_ok
    second = scaffold_project("demo", "mech", parent=tmp_path)
    assert second.is_err
    assert second.danger_err.kind == "target_exists"


def test_scaffold_refuses_unknown_template(tmp_path: Path) -> None:
    result = scaffold_project("demo", "spaceship", parent=tmp_path)
    assert result.is_err
    assert result.danger_err.kind == "unknown_template"


def test_scaffold_into_empty_existing_dir_is_allowed(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    result = scaffold_project("demo", "mech", parent=tmp_path)
    assert result.is_ok


def test_manifest_carries_project_name(tmp_path: Path) -> None:
    result = scaffold_project("widget", "mech", parent=tmp_path)
    assert result.is_ok
    manifest = (result.danger_ok / "magnetite.toml").read_text()
    assert 'name = "widget"' in manifest
    assert "__PROJECT__" not in manifest
