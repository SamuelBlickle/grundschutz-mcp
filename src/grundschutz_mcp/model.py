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


class ModuleSummary(BaseModel):
    """A discovery-level summary of one module (Baustein) in the catalog."""

    module: str = Field(..., description="Module (group) ID, e.g. 'GC.1'.")
    module_title: str = Field(..., description="Module (group) title.")
    requirement_count: int = Field(..., description="Number of requirements in this module.")


class CatalogStats(BaseModel):
    """Aggregate counts over the catalog (a projection, not an OSCAL mirror)."""

    total: int = Field(..., description="Total number of requirements in the catalog.")
    by_security_level: dict[str, int] = Field(
        default_factory=dict,
        description="Requirement count per security level.",
    )
    by_effort_level: dict[int, int] = Field(
        default_factory=lambda: {},
        description="Requirement count per ordinal effort level (0-5).",
    )
    by_tag: dict[str, int] = Field(
        default_factory=dict,
        description="Requirement count per tag; also serves tag discovery.",
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

    def modules(self) -> list[ModuleSummary]:
        titles: dict[str, str] = {}
        counts: dict[str, int] = {}
        for r in self._all:
            if r.module not in titles:
                titles[r.module] = r.module_title
            counts[r.module] = counts.get(r.module, 0) + 1
        return [
            ModuleSummary(
                module=module,
                module_title=titles[module],
                requirement_count=counts[module],
            )
            for module in sorted(counts)
        ]

    def filter(
        self,
        *,
        module: str | None = None,
        security_level: str | None = None,
        min_effort: int | None = None,
        max_effort: int | None = None,
        tag: str | None = None,
    ) -> list[Requirement]:
        tag_folded = tag.casefold() if tag is not None else None
        result = [
            r
            for r in self._all
            if (module is None or r.module == module)
            and (security_level is None or r.security_level == security_level)
            and (min_effort is None or r.effort_level >= min_effort)
            and (max_effort is None or r.effort_level <= max_effort)
            and (tag_folded is None or tag_folded in {t.casefold() for t in r.tags})
        ]
        return sorted(result, key=lambda r: r.id)

    def by_ids(self, ids: list[str]) -> list[Requirement]:
        result: list[Requirement] = []
        seen: set[str] = set()
        for rid in ids:
            if rid in seen:
                continue
            seen.add(rid)
            requirement = self._by_id.get(rid)
            if requirement is not None:
                result.append(requirement)
        return result

    def stats(self) -> CatalogStats:
        by_security_level: dict[str, int] = {}
        by_effort_level: dict[int, int] = {}
        by_tag: dict[str, int] = {}
        for r in self._all:
            by_security_level[r.security_level] = by_security_level.get(r.security_level, 0) + 1
            by_effort_level[r.effort_level] = by_effort_level.get(r.effort_level, 0) + 1
            for t in r.tags:
                by_tag[t] = by_tag.get(t, 0) + 1
        return CatalogStats(
            total=len(self._all),
            by_security_level=by_security_level,
            by_effort_level=by_effort_level,
            by_tag=by_tag,
        )
