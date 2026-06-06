"""MCP server: the five tools, defined only against the internal model.

The tools never see raw OSCAL. They call into the Catalog, which is fed by the
mapper. Returned requirement texts are the original German wording.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from .loader import load_catalog
from .model import Catalog, CatalogMetadata, Requirement

mcp = FastMCP("grundschutz")

_catalog: Catalog | None = None


async def _get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = await load_catalog()
    return _catalog


@mcp.tool()
async def get_requirement_by_id(id: str) -> Requirement | None:
    """Fetch a single Grundschutz++ requirement or practice by its ID."""
    return (await _get_catalog()).get(id)


@mcp.tool()
async def list_requirements_by_module(module: str) -> list[Requirement]:
    """List all requirements belonging to a given Baustein/practice."""
    return (await _get_catalog()).by_module(module)


@mcp.tool()
async def search_requirements(query: str) -> list[Requirement]:
    """Full-text search across requirement titles and texts (German)."""
    return (await _get_catalog()).search(query)


@mcp.tool()
async def get_mapping(relation: Literal["related", "required"]) -> dict[str, list[str]]:
    """Return internal requirement-to-requirement cross-references ('related' or 'required')."""
    catalog = await _get_catalog()
    if relation == "related":
        return {r.id: r.related for r in catalog.all() if r.related}
    return {r.id: r.required for r in catalog.all() if r.required}


@mcp.tool()
async def get_catalog_metadata() -> CatalogMetadata:
    """Return catalog version, source commit, and license information."""
    return (await _get_catalog()).metadata
