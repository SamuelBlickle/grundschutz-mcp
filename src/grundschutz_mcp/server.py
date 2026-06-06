"""MCP server: the five tools, defined only against the internal model.

The tools never see raw OSCAL. They call into the Catalog, which is fed by the
mapper. Returned requirement texts are the original German wording.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .loader import load_catalog
from .model import Catalog, CatalogMetadata, ModuleSummary, Requirement

logger = logging.getLogger("grundschutz_mcp")

mcp = FastMCP("grundschutz")

_catalog: Catalog | None = None


async def _get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = await load_catalog()
        logger.info("catalog loaded: %d requirements", len(_catalog.all()))
    return _catalog


@mcp.tool()
async def get_requirement_by_id(
    id: Annotated[str, Field(min_length=1, max_length=128)],
) -> Requirement | None:
    """Fetch a single Grundschutz++ requirement or practice by its ID."""
    result = (await _get_catalog()).get(id)
    logger.info("get_requirement_by_id id=%s %s", id, "hit" if result else "miss")
    return result


@mcp.tool()
async def list_requirements_by_module(
    module: Annotated[str, Field(min_length=1, max_length=64)],
) -> list[Requirement]:
    """List all requirements belonging to a given Baustein/practice."""
    result = (await _get_catalog()).by_module(module)
    logger.info("list_requirements_by_module module=%s count=%d", module, len(result))
    return result


@mcp.tool()
async def list_modules() -> list[ModuleSummary]:
    """List all modules (Bausteine) in the catalog: id, title, and requirement count.

    Use this to discover which modules exist before calling
    list_requirements_by_module.
    """
    result = (await _get_catalog()).modules()
    logger.info("list_modules count=%d", len(result))
    return result


@mcp.tool()
async def search_requirements(
    query: Annotated[str, Field(min_length=1, max_length=200)],
) -> list[Requirement]:
    """Full-text search across requirement titles and texts (German)."""
    result = (await _get_catalog()).search(query)
    logger.info("search_requirements query=%s count=%d", query, len(result))
    return result


@mcp.tool()
async def get_mapping(relation: Literal["related", "required"]) -> dict[str, list[str]]:
    """Return internal requirement-to-requirement cross-references ('related' or 'required')."""
    catalog = await _get_catalog()
    if relation == "related":
        mapping = {r.id: r.related for r in catalog.all() if r.related}
    else:
        mapping = {r.id: r.required for r in catalog.all() if r.required}
    logger.info("get_mapping relation=%s count=%d", relation, len(mapping))
    return mapping


@mcp.tool()
async def get_catalog_metadata() -> CatalogMetadata:
    """Return catalog version, source commit, and license information."""
    metadata = (await _get_catalog()).metadata
    logger.info("get_catalog_metadata requirement_count=%d", metadata.requirement_count)
    return metadata
