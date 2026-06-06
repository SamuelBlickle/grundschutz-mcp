"""Internal model: a small, stable projection of the BSI compendium.

This is deliberately NOT a full reimplementation of the OSCAL structure. It
contains only the fields the MCP tools actually need. The model is our own
source of truth and changes only when we decide it should, never because the
BSI changed an OSCAL field name.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """A single Grundschutz++ requirement or practice.

    The `text` and `guidance` fields hold the original German wording from the
    BSI source and are never translated.
    """

    id: str = Field(..., description="Stable BSI requirement/practice ID.")
    title: str
    text: str = Field(..., description="Original German requirement text.")
    guidance: str = Field(..., description="Original German implementation guidance.")
    module: str = Field(..., description="Module (group) ID this belongs to.")
    module_title: str = Field(..., description="Module (group) title this belongs to.")
    security_level: Literal["normal-SdT", "erhöht"]
    effort_level: int = Field(..., description="Ordinal implementation effort, 0-5.")
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(
        default_factory=list,
        description="IDs of related requirements (internal cross-references).",
    )
    required: list[str] = Field(
        default_factory=list,
        description="IDs of required requirements (internal cross-references).",
    )


class CatalogMetadata(BaseModel):
    """Provenance and licensing of the loaded catalog."""

    version: str
    source_repo: str
    source_commit: str
    license: str = "CC BY-SA 4.0"
    requirement_count: int


class Catalog:
    """In-memory, indexed view of the compendium for fast tool access."""

    def __init__(self, requirements: list[Requirement], metadata: CatalogMetadata) -> None:
        self._by_id: dict[str, Requirement] = {r.id: r for r in requirements}
        self._all: list[Requirement] = requirements
        self.metadata = metadata

    def get(self, rid: str) -> Requirement | None:
        return self._by_id.get(rid)

    def by_module(self, module: str) -> list[Requirement]:
        return [r for r in self._all if r.module == module]

    def search(self, query: str) -> list[Requirement]:
        q = query.casefold()
        return [
            r
            for r in self._all
            if q in r.title.casefold()
            or q in r.text.casefold()
            or any(q in t.casefold() for t in r.tags)
        ]

    def all(self) -> list[Requirement]:
        return list(self._all)
