"""Tests for `regolith.docgen.render` formatting fixes (D199.2, cycle
33 docsgen-formatting SIMPLE): heading hierarchy, empty-name display,
embedded-backtick escaping, and multi-line value fencing. Each test
pins the corrected shape for a defect found in the cycle-33 inventory
(see docs/workflow/work-orders/WO-41-docsgen-and-scaffolding.md
addendum) so it cannot silently regress.
"""

from __future__ import annotations

from regolith.docgen.models import (
    ClaimGroupDoc,
    DeclDoc,
    FieldDoc,
    PackageDoc,
    SourceDoc,
)
from regolith.docgen.render import render_markdown


def _package(decl: DeclDoc, path: str = "pkg/thing.hema") -> PackageDoc:
    return PackageDoc(sources=(SourceDoc(path=path, decls=(decl,)),))


# frob:tests python/regolith/docgen/render.py::render_markdown
def test_decl_heading_is_one_level_below_source_heading() -> None:
    """Defect #1: source headings are `##`; a decl heading of `####`
    skips `###` (an invalid heading-hierarchy jump). Decls must render
    at `###`."""
    decl = DeclDoc(kind="part", name="Widget")
    rendered = render_markdown(_package(decl))
    assert "## `pkg/thing.hema`" in rendered
    assert "### part `Widget`" in rendered
    assert "#### part `Widget`" not in rendered


def test_empty_name_renders_readable_fallback_not_bare_backticks() -> None:
    """Defect #2: an unnamed decl/budget used to render as a bare
    ` `` ` empty code span, which reads as visual noise."""
    decl = DeclDoc(
        kind="require", name="", budgets=(FieldDoc(name="", value="x <= 1"),)
    )
    rendered = render_markdown(_package(decl))
    assert "``" not in rendered
    assert "### require (unnamed)" in rendered
    assert "- (unnamed budget): `x <= 1`" in rendered


def test_embedded_backtick_in_field_value_does_not_break_code_span() -> None:
    """Defect #3: a field value containing a literal backtick (e.g. a
    captured identifier like `` `anchors=` ``) used to prematurely
    close a single-backtick code span and corrupt the rest of the
    line. The renderer must widen the fence."""
    decl = DeclDoc(
        kind="mating",
        name="BasePlate",
        fields=(
            FieldDoc(name="capability", value="note: keyed by `anchors=`, see D58"),
        ),
    )
    rendered = render_markdown(_package(decl))
    assert "``note: keyed by `anchors=`, see D58``" in rendered


def test_multiline_field_value_is_fenced_not_spliced_raw() -> None:
    """Defect #4: a multi-line field value (e.g. a `spec:` block) used
    to be spliced directly into the list item text with raw newlines,
    breaking list structure. It must render as an indented fenced code
    block instead."""
    decl = DeclDoc(
        kind="block",
        name="Mcu",
        fields=(
            FieldDoc(
                name="spec",
                value="forall f in [10kHz, 250kHz]:\n    settles(x, within 4us)",
            ),
        ),
    )
    rendered = render_markdown(_package(decl))
    assert "- `spec`:\n\n  ```\n  forall f in [10kHz, 250kHz]:\n" in rendered
    assert rendered.count("```") == 2


def test_multiline_claim_value_is_fenced_and_status_kept() -> None:
    """A multi-line claim expression must also be fenced (not spliced
    raw), and the build-status suffix must stay attached to the claim
    label line, not get swallowed into the block."""
    decl = DeclDoc(
        kind="assembly",
        name="Antenna",
        claims=(
            ClaimGroupDoc(
                group="Deployment",
                claims=(FieldDoc(name="settle", value="settles(x,\n    within 3s)"),),
            ),
        ),
    )
    rendered = render_markdown(_package(decl))
    assert "- `settle` -- (unbuilt):" in rendered
    assert "```\n    settles(x,\n" in rendered


def test_rendering_is_deterministic_across_repeated_calls() -> None:
    decl = DeclDoc(
        kind="part", name="Widget", fields=(FieldDoc(name="material", value="AL"),)
    )
    package = _package(decl)
    assert render_markdown(package) == render_markdown(package)
