"""Tests for the MCP tools in server.py.

Designed from the public tool surface, not the implementation. The tools read
from a module-level catalog populated by the loader; these tests seed an
in-memory Catalog directly so the offline suite stays fully offline and
deterministic (no network).
"""

from __future__ import annotations

import pytest

from grundschutz_mcp import server
from grundschutz_mcp.model import Catalog, CatalogMetadata, Requirement


def _req(
    rid: str,
    *,
    module: str = "M",
    module_title: str = "Modul",
    related: list[str] | None = None,
    required: list[str] | None = None,
    tags: list[str] | None = None,
    title: str = "Titel",
    text: str = "Text.",
) -> Requirement:
    return Requirement(
        id=rid,
        title=title,
        text=text,
        guidance="Hinweise.",
        module=module,
        module_title=module_title,
        security_level="normal-SdT",
        effort_level=1,
        tags=tags or [],
        related=related or [],
        required=required or [],
    )


def _catalog(reqs: list[Requirement]) -> Catalog:
    meta = CatalogMetadata(
        version="2024.1",
        source_repo="BSI-Bund/Stand-der-Technik-Bibliothek",
        source_commit="deadbeef",
        requirement_count=len(reqs),
    )
    return Catalog(reqs, meta)


@pytest.fixture(autouse=True)
def seed_catalog(monkeypatch: pytest.MonkeyPatch) -> Catalog:
    """Seed server._catalog so tools never hit the network."""
    cat = _catalog(
        [
            _req(
                "A.1",
                module="ORP.1",
                module_title="Organisation",
                related=["A.2"],
                required=["A.3"],
                tags=["Rollen"],
                title="Verantwortlichkeiten",
                text="Verantwortlichkeiten MÜSSEN festgelegt werden.",
            ),
            _req("A.2", module="ORP.1", module_title="Organisation"),
            _req("B.1", module="SYS.1", module_title="Server", title="Servereinsatz"),
        ]
    )
    monkeypatch.setattr(server, "_catalog", cat)
    return cat


# ---------------------------------------------------------------------------
# get_requirement_by_id
# ---------------------------------------------------------------------------


async def test_get_requirement_by_id_hit() -> None:
    req = await server.get_requirement_by_id("A.1")
    assert req is not None and req.id == "A.1"


async def test_get_requirement_by_id_miss_returns_none() -> None:
    assert await server.get_requirement_by_id("NOPE") is None


async def test_get_requirement_by_id_is_case_sensitive() -> None:
    assert await server.get_requirement_by_id("a.1") is None


# ---------------------------------------------------------------------------
# list_requirements_by_module
# ---------------------------------------------------------------------------


async def test_list_requirements_by_module_populated() -> None:
    reqs = await server.list_requirements_by_module("ORP.1")
    assert {r.id for r in reqs} == {"A.1", "A.2"}


async def test_list_requirements_by_module_empty() -> None:
    assert await server.list_requirements_by_module("NO.SUCH") == []


# ---------------------------------------------------------------------------
# list_modules
# ---------------------------------------------------------------------------


async def test_list_modules_returns_one_summary_per_module() -> None:
    summaries = await server.list_modules()
    # The seeded catalog has two modules: ORP.1 (A.1, A.2) and SYS.1 (B.1).
    assert [(s.module, s.module_title, s.requirement_count) for s in summaries] == [
        ("ORP.1", "Organisation", 2),
        ("SYS.1", "Server", 1),
    ]


async def test_list_modules_is_sorted_by_module_id() -> None:
    summaries = await server.list_modules()
    ids = [s.module for s in summaries]
    assert ids == sorted(ids)


async def test_list_modules_counts_sum_to_total_requirements(seed_catalog: Catalog) -> None:
    summaries = await server.list_modules()
    total = sum(s.requirement_count for s in summaries)
    assert total == len(seed_catalog.all())


# ---------------------------------------------------------------------------
# search_requirements
# ---------------------------------------------------------------------------


async def test_search_matches_title() -> None:
    reqs = await server.search_requirements("Servereinsatz")
    assert [r.id for r in reqs] == ["B.1"]


async def test_search_matches_text() -> None:
    reqs = await server.search_requirements("festgelegt")
    assert [r.id for r in reqs] == ["A.1"]


async def test_search_matches_tag() -> None:
    reqs = await server.search_requirements("rollen")
    assert [r.id for r in reqs] == ["A.1"]


async def test_search_casefold() -> None:
    reqs = await server.search_requirements("VERANTWORTLICHKEITEN")
    assert [r.id for r in reqs] == ["A.1"]


async def test_search_no_match() -> None:
    assert await server.search_requirements("xyzzy") == []


# ---------------------------------------------------------------------------
# get_mapping
# ---------------------------------------------------------------------------


async def test_get_mapping_related() -> None:
    mapping = await server.get_mapping("related")
    assert mapping == {"A.1": ["A.2"]}


async def test_get_mapping_required() -> None:
    mapping = await server.get_mapping("required")
    assert mapping == {"A.1": ["A.3"]}


async def test_get_mapping_relation_is_literal_in_tool_schema() -> None:
    # The relation parameter is validated at the FastMCP boundary: the
    # registered tool advertises a Literal/enum, so an unsupported value
    # ("iso27001") is rejected before the body runs. Assert the contract via
    # the tool's published input schema rather than the raw function (which,
    # called directly, bypasses Pydantic validation).
    tools = await server.mcp.list_tools()
    tool = next(t for t in tools if t.name == "get_mapping")
    schema = tool.inputSchema
    relation = schema["properties"]["relation"]
    allowed = relation.get("enum") or relation.get("const")
    assert allowed is not None, "relation must be constrained, not a free string"
    assert set(allowed) == {"related", "required"}


# ---------------------------------------------------------------------------
# get_catalog_metadata
# ---------------------------------------------------------------------------


async def test_get_catalog_metadata_fields_present() -> None:
    meta = await server.get_catalog_metadata()
    assert meta.source_commit == "deadbeef"
    assert meta.license == "CC BY-SA 4.0"
    assert meta.requirement_count == 3
