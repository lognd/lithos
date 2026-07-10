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


def _name_label(name: str, *, fallback: str = "(unnamed)") -> str:
    """A display label for a declaration/budget name: backtick-quoted
    code span when non-empty, a plain parenthesized fallback otherwise
    (an empty ```` `` ```` pair renders as visual noise -- defect #2 of
    the cycle-33 docsgen formatting inventory, D199.2)."""
    return _code_span(name) if name else fallback


def _code_span(text: str) -> str:
    """A CommonMark-safe inline code span for ``text``.

    Picks a backtick-fence run one longer than the longest run of
    backticks already inside ``text`` (the standard technique for
    escaping embedded backticks, e.g. a captured ``` `anchors=` ```
    literal) and pads with a single space on each side when the text
    itself starts or ends with a backtick, per the CommonMark spec.
    Without this, an embedded backtick prematurely closes the span and
    corrupts every line after it (defect #3 of the inventory)."""
    value = text.strip() or "(empty)"
    longest_run = 0
    current_run = 0
    for ch in value:
        if ch == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    fence = "`" * (longest_run + 1)
    if value.startswith("`") or value.endswith("`") or value == "(empty)":
        return (
            f"{fence} {value} {fence}"
            if value != "(empty)"
            else f"{fence}{value}{fence}"
        )
    return f"{fence}{value}{fence}"


def _fenced_block(lines: list[str], value: str, *, indent: str = "  ") -> None:
    """A fenced code block for a multi-line value, indented to stay
    part of the enclosing list item (GFM list-continuation rule: the
    continuation must be indented to the marker width). Raw multi-line
    values dumped straight into a list item (the old behavior) break
    list structure and read as an unfenced wall of text -- defect #4."""
    body = value.strip("\n")
    longest_run = 0
    current_run = 0
    for ch in body:
        if ch == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    fence = "`" * max(3, longest_run + 1)
    lines.append("")
    lines.append(f"{indent}{fence}")
    for line in body.splitlines():
        lines.append(f"{indent}{line}" if line else "")
    lines.append(f"{indent}{fence}")
    lines.append("")


def _render_value(lines: list[str], label: str, value: str) -> None:
    """Render one ``- label: value`` list entry, fencing multi-line
    values instead of splicing raw newlines into the list item."""
    value_text = value.strip() or "(empty)"
    if "\n" in value_text:
        lines.append(f"- {label}:")
        _fenced_block(lines, value_text)
    else:
        lines.append(f"- {label}: {_code_span(value_text)}")


def _render_field(field_lines: list[str], name: str, value: str) -> None:
    _render_value(field_lines, _name_label(name, fallback="(unnamed field)"), value)


def _render_decl(lines: list[str], decl: DeclDoc, statuses: dict[str, str]) -> None:
    anchor = _anchor(decl.kind, decl.name)
    name_label = _name_label(decl.name, fallback="(unnamed)")
    lines.append(f'<a id="{anchor}"></a>')
    # One level below the source's `##` heading (defect #1: the old
    # `####` skipped `###` entirely, an invalid heading-hierarchy jump).
    lines.append(f"### {decl.kind} {name_label}")
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
            label = _name_label(group.group, fallback="(unnamed group)")
            lines.append(f"- {label}:")
            for claim in group.claims:
                status = statuses.get(claim.name, "(unbuilt)")
                claim_label = f"{_name_label(claim.name, fallback='(unnamed claim)')}"
                value_text = claim.value.strip() or "(empty)"
                if "\n" in value_text:
                    lines.append(f"  - {claim_label} -- {status}:")
                    _fenced_block(lines, value_text, indent="    ")
                else:
                    lines.append(
                        f"  - {claim_label}: {_code_span(value_text)} -- {status}"
                    )
        lines.append("")
    if decl.budgets:
        lines.append("Budgets:")
        lines.append("")
        for budget in decl.budgets:
            _render_value(
                lines,
                _name_label(budget.name, fallback="(unnamed budget)"),
                budget.value,
            )
        lines.append("")


def _render_toc(lines: list[str], source: SourceDoc) -> None:
    decls = sorted(source.decls, key=_sort_key)
    for decl in decls:
        anchor = _anchor(decl.kind, decl.name)
        name_label = _name_label(decl.name, fallback="(unnamed)")
        lines.append(f"- [{decl.kind} {name_label}](#{anchor})")


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
