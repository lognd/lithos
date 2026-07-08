"""Typed models over the ``doc_extract`` JSON payload (WO-41).

Mirrors the shape ``regolith_api::docextract`` emits (kind/name/doc/
fields/claims/budgets per top-level declaration); a thin pydantic
parse so the renderer never touches raw ``dict`` payloads.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FieldDoc(BaseModel):
    """One ``name: value`` structured statement (a field or budget row)."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: str


class ClaimGroupDoc(BaseModel):
    """One ``require <Group>:`` claim group and its claim lines."""

    model_config = ConfigDict(frozen=True)

    group: str
    claims: tuple[FieldDoc, ...] = ()


class DeclDoc(BaseModel):
    """One top-level declaration's extracted public surface."""

    model_config = ConfigDict(frozen=True)

    kind: str
    name: str
    doc: str | None = None
    fields: tuple[FieldDoc, ...] = ()
    claims: tuple[ClaimGroupDoc, ...] = ()
    budgets: tuple[FieldDoc, ...] = ()


class SourceDoc(BaseModel):
    """One source file's declarations, in source order."""

    model_config = ConfigDict(frozen=True)

    path: str
    decls: tuple[DeclDoc, ...] = ()


class PackageDoc(BaseModel):
    """A whole package's extracted doc model: every source file, sorted."""

    model_config = ConfigDict(frozen=True)

    sources: tuple[SourceDoc, ...] = ()
