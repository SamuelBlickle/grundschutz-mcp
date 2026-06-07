"""MCP server: the MCP tools, defined only against the internal model.

The tools never see raw OSCAL. They call into the Catalog, which is fed by the
mapper. Returned requirement texts are the original German wording.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .loader import load_catalog
from .model import Catalog, CatalogMetadata, CatalogStats, ModuleSummary, Requirement

logger = logging.getLogger("grundschutz_mcp")

# Map every C0 control char (U+0000-U+001F) plus DEL (U+007F) to its escaped
# repr. This neutralizes CR/LF (log-forging a second line) and other control
# chars while leaving printable Unicode -- including German umlauts -- readable.
_CONTROL_ESCAPE = {c: repr(chr(c))[1:-1] for c in (*range(0x20), 0x7F)}


def _safe_log(value: str) -> str:
    """Escape control chars so a logged user string cannot forge a log line."""
    return value.translate(_CONTROL_ESCAPE)


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
    """Fetch a single Grundschutz++ requirement or practice by its ID.

    Returns null if no requirement has that id.
    """
    result = (await _get_catalog()).get(id)
    logger.info("get_requirement_by_id id=%s %s", _safe_log(id), "hit" if result else "miss")
    return result


@mcp.tool()
async def list_requirements_by_module(
    module: Annotated[str, Field(min_length=1, max_length=64)],
) -> list[Requirement]:
    """List all requirements belonging to a given Baustein/practice, in catalog (source) order."""
    result = (await _get_catalog()).by_module(module)
    logger.info("list_requirements_by_module module=%s count=%d", _safe_log(module), len(result))
    return result


@mcp.tool()
async def list_modules() -> list[ModuleSummary]:
    """List all modules (Bausteine) in the catalog: id, title, and requirement count.

    Sorted by module id. Use this to discover which modules exist before calling
    list_requirements_by_module.
    """
    result = (await _get_catalog()).modules()
    logger.info("list_modules count=%d", len(result))
    return result


@mcp.tool()
async def search_requirements(
    query: Annotated[str, Field(min_length=1, max_length=200)],
) -> list[Requirement]:
    """Full-text search across requirement titles, texts, and tags (German).

    Results are returned in catalog (source) order.
    """
    result = (await _get_catalog()).search(query)
    logger.info("search_requirements query=%s count=%d", _safe_log(query), len(result))
    return result


@mcp.tool()
async def get_cross_references(relation: Literal["related", "required"]) -> dict[str, list[str]]:
    """Return internal requirement-to-requirement cross-references ('related' or 'required').

    Only requirements that have at least one such cross-reference appear as keys.
    """
    catalog = await _get_catalog()
    if relation == "related":
        mapping = {r.id: r.related for r in catalog.all() if r.related}
    else:
        mapping = {r.id: r.required for r in catalog.all() if r.required}
    logger.info("get_cross_references relation=%s count=%d", relation, len(mapping))
    return mapping


@mcp.tool()
async def filter_requirements(
    module: Annotated[str | None, Field(min_length=1, max_length=64)] = None,
    security_level: Literal["normal-SdT", "erhöht"] | None = None,
    min_effort: Annotated[int | None, Field(ge=0, le=5)] = None,
    max_effort: Annotated[int | None, Field(ge=0, le=5)] = None,
    tag: Annotated[str | None, Field(min_length=1, max_length=64)] = None,
) -> list[Requirement]:
    """Filter requirements by module, security level, effort range, and/or tag.

    Criteria combine with AND; the result is sorted by requirement id. At least
    one criterion is required. `security_level` is "normal-SdT" (standard) or
    "erhöht" (elevated). `min_effort`/`max_effort` express '>= n', '<= n',
    exactly n, or a band over the ordinal effort scale (0=mandatory/not assessed,
    1=quick win, ... 5=complex; see the effort_level field for the full scale).
    `tag` matches case-insensitively.
    """
    if (
        module is None
        and security_level is None
        and min_effort is None
        and max_effort is None
        and tag is None
    ):
        raise ValueError("filter_requirements requires at least one criterion.")
    result = (await _get_catalog()).filter(
        module=module,
        security_level=security_level,
        min_effort=min_effort,
        max_effort=max_effort,
        tag=tag,
    )
    logger.info(
        "filter_requirements module=%s security_level=%s min_effort=%s max_effort=%s "
        "tag=%s count=%d",
        _safe_log(module) if module is not None else None,
        security_level,
        min_effort,
        max_effort,
        _safe_log(tag) if tag is not None else None,
        len(result),
    )
    return result


@mcp.tool()
async def get_requirements_by_ids(
    ids: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=128)]],
        Field(min_length=1, max_length=200),
    ],
) -> list[Requirement]:
    """Fetch multiple requirements by id in a single call.

    Returns one requirement per distinct found id, in first-seen input order.
    Ids not present in the catalog are skipped. Useful for following the
    related/required cross-references token-efficiently.
    """
    result = (await _get_catalog()).by_ids(ids)
    missing = len(dict.fromkeys(ids)) - len(result)
    logger.info(
        "get_requirements_by_ids requested=%d found=%d missing=%d",
        len(ids),
        len(result),
        missing,
    )
    return result


@mcp.tool()
async def get_catalog_stats() -> CatalogStats:
    """Return aggregate catalog counts: totals by security level, effort, and tag.

    The by_tag keys also serve as tag discovery before filtering.
    """
    result = (await _get_catalog()).stats()
    logger.info(
        "get_catalog_stats total=%d levels=%d efforts=%d tags=%d",
        result.total,
        len(result.by_security_level),
        len(result.by_effort_level),
        len(result.by_tag),
    )
    return result


@mcp.tool()
async def get_catalog_metadata() -> CatalogMetadata:
    """Return catalog version, source commit, and license information."""
    metadata = (await _get_catalog()).metadata
    logger.info("get_catalog_metadata requirement_count=%d", metadata.requirement_count)
    return metadata
