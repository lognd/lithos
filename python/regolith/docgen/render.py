"""Deterministic markdown rendering of a :class:`PackageDoc` (WO-41).

The ONE renderer for ``regolith doc``: pure text assembly, no I/O.
Ordering is fixed (source path, then declaration kind, then name) so
two runs over the same inputs are byte-identical (an acceptance
criterion).
"""

from __future__ import annotations

from regolith.docgen.models import DeclDoc, PackageDoc, SourceDoc

# The declaration-kind grouping order (interfaces first, claims last);
# any kind this WO's grammar sweep didn't name explicitly still renders,
# sorted alphabetically, in an "other" bucket appended at the end.
_KIND_ORDER = (
    "interface",
    "part",
    "block",
    "flownet",
    "medium",
    "system",
    "assembly",
    "component",
    "profile",
    "require",
)


def _anchor(kind: str, name: str) -> str:
    """A stable, lower-case, hyphenated anchor for internal links."""
    slug = "".join(c if c.isalnum() else "-" for c in f"{kind}-{name}").lower()
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _sort_key(decl: DeclDoc) -> tuple[int, str, str]:
    try:
        rank = _KIND_ORDER.index(decl.kind)
    except ValueError:
        rank = len(_KIND_ORDER)
    return (rank, decl.kind, decl.name)


def _render_field(field_lines: list[str], name: str, value: str) -> None:
    value_text = value.strip() or "(empty)"
    if "\n" in value_text:
        field_lines.append(f"- `{name}`:")
        for line in value_text.splitlines():
            field_lines.append(f"  {line}")
    else:
        field_lines.append(f"- `{name}`: `{value_text}`")


def _render_decl(lines: list[str], decl: DeclDoc, statuses: dict[str, str]) -> None:
    anchor = _anchor(decl.kind, decl.name)
    lines.append(f'<a id="{anchor}"></a>')
    lines.append(f"#### {decl.kind} `{decl.name}`")
    lines.append("")
    if decl.doc:
        lines.append(decl.doc)
        lines.append("")
    if decl.fields:
        for field in decl.fields:
            _render_field(lines, field.name, field.value)
        lines.append("")
    if decl.claims:
        lines.append("Claims:")
        lines.append("")
        for group in decl.claims:
            label = f"`{group.group}`" if group.group else "(unnamed group)"
            lines.append(f"- {label}:")
            for claim in group.claims:
                status = statuses.get(claim.name, "(unbuilt)")
                value_text = claim.value.strip() or "(empty)"
                lines.append(f"  - `{claim.name}`: `{value_text}` -- {status}")
        lines.append("")
    if decl.budgets:
        lines.append("Budgets:")
        lines.append("")
        for budget in decl.budgets:
            lines.append(f"- `{budget.name}`: `{budget.value.strip()}`")
        lines.append("")


def _render_toc(lines: list[str], source: SourceDoc) -> None:
    decls = sorted(source.decls, key=_sort_key)
    for decl in decls:
        anchor = _anchor(decl.kind, decl.name)
        lines.append(f"- [{decl.kind} `{decl.name}`](#{anchor})")


def _render_source(
    lines: list[str], source: SourceDoc, statuses: dict[str, str]
) -> None:
    lines.append(f"## `{source.path}`")
    lines.append("")
    if not source.decls:
        lines.append("(no public declarations)")
        lines.append("")
        return
    _render_toc(lines, source)
    lines.append("")
    for decl in sorted(source.decls, key=_sort_key):
        _render_decl(lines, decl, statuses)


def render_markdown(
    package: PackageDoc,
    *,
    title: str = "Package documentation",
    statuses: dict[str, str] | None = None,
) -> str:
    """Render ``package`` to deterministic markdown (WO-41 deliverable 2).

    ``statuses`` maps a named claim to its rendered build-status text
    (:func:`regolith.docgen.status.claim_statuses`); a claim absent
    from the map renders ``(unbuilt)``.
    """
    statuses = statuses or {}
    lines: list[str] = [f"# {title}", ""]
    for source in sorted(package.sources, key=lambda s: s.path):
        _render_source(lines, source, statuses)
    # One trailing newline, no trailing blank-line runs: byte-identical
    # across runs (an acceptance criterion) and diff-friendly.
    text = "\n".join(lines)
    while text.endswith("\n\n\n"):
        text = text[:-1]
    if not text.endswith("\n"):
        text += "\n"
    return text
