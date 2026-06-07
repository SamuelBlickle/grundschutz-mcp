"""Tests for the MCP tools in server.py.

Designed from the public tool surface, not the implementation. The tools read
from a module-level catalog populated by the loader; these tests seed an
in-memory Catalog directly so the offline suite stays fully offline and
deterministic (no network).
"""

from __future__ import annotations

import logging
from typing import Literal, cast

import pytest

from grundschutz_mcp import server
from grundschutz_mcp.model import Catalog, CatalogMetadata, CatalogStats, Requirement

LOGGER_NAME = "grundschutz_mcp"


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


# ---------------------------------------------------------------------------
# G1 — Input caps live at the MCP/FastMCP (Pydantic) boundary.
#
# A direct Python call to a tool function bypasses Pydantic, so the caps are
# asserted against the *published* tool input schema (minLength/maxLength),
# exactly as get_mapping's Literal is checked via the schema — not by calling
# the function with an out-of-range value.
# ---------------------------------------------------------------------------


async def _tool_param_schema(tool_name: str, param: str) -> dict[str, object]:
    tools = await server.mcp.list_tools()
    tool = next(t for t in tools if t.name == tool_name)
    properties = tool.inputSchema["properties"]
    return properties[param]


@pytest.mark.parametrize(
    ("tool_name", "param", "max_length"),
    [
        ("get_requirement_by_id", "id", 128),
        ("list_requirements_by_module", "module", 64),
        ("search_requirements", "query", 200),
    ],
)
async def test_string_param_caps_in_tool_schema(
    tool_name: str, param: str, max_length: int
) -> None:
    schema = await _tool_param_schema(tool_name, param)
    assert schema.get("type") == "string"
    assert schema.get("minLength") == 1, f"{tool_name}.{param} must reject empty strings"
    assert schema.get("maxLength") == max_length, (
        f"{tool_name}.{param} must be capped at {max_length}"
    )


# ---------------------------------------------------------------------------
# filter_requirements (HANDOFF-021) — happy-path delegation, all-None guard,
# and input caps asserted at the published tool schema (not via direct calls
# with out-of-range values, which bypass Pydantic).
# ---------------------------------------------------------------------------


async def test_filter_requirements_delegates_happy_path() -> None:
    # The seeded catalog: A.1, A.2 in ORP.1; B.1 in SYS.1. Filtering by module
    # returns ORP.1's requirements, sorted by id.
    reqs = await server.filter_requirements(module="ORP.1")
    assert [r.id for r in reqs] == ["A.1", "A.2"]


async def test_filter_requirements_tag_case_insensitive() -> None:
    # A.1 carries the "Rollen" tag; a lower-case filter must still match it.
    reqs = await server.filter_requirements(tag="rollen")
    assert [r.id for r in reqs] == ["A.1"]


async def test_filter_requirements_no_match_returns_empty_not_error() -> None:
    assert await server.filter_requirements(module="NO.SUCH") == []


async def test_filter_requirements_all_none_raises_before_catalog() -> None:
    # Spec: with every parameter None the tool raises rather than dumping the
    # whole catalogue. The guard runs in the tool, before Catalog.filter.
    with pytest.raises(ValueError):
        await server.filter_requirements()


def _typed_branch(schema: dict[str, object], json_type: str) -> dict[str, object]:
    """Return the non-null constraint branch of an optional (anyOf) param schema.

    An optional MCP parameter (`X | None`) is published as an `anyOf` of the
    real type and `{"type": "null"}`; the length/range/enum constraints live in
    the non-null branch. Falls back to the schema itself for non-optional params.
    """
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        branches = cast("list[object]", any_of)
        for branch in branches:
            if isinstance(branch, dict):
                typed = cast("dict[str, object]", branch)
                if typed.get("type") == json_type:
                    return typed
    return schema


@pytest.mark.parametrize(
    ("param", "max_length"),
    [
        ("module", 64),
        ("tag", 64),
    ],
)
async def test_filter_requirements_string_caps_in_schema(param: str, max_length: int) -> None:
    branch = _typed_branch(await _tool_param_schema("filter_requirements", param), "string")
    assert branch.get("maxLength") == max_length, f"filter_requirements.{param} cap"
    assert branch.get("minLength") == 1, f"filter_requirements.{param} rejects empty"


@pytest.mark.parametrize("param", ["min_effort", "max_effort"])
async def test_filter_requirements_effort_bounds_in_schema(param: str) -> None:
    branch = _typed_branch(await _tool_param_schema("filter_requirements", param), "integer")
    assert branch.get("minimum") == 0, f"filter_requirements.{param} minimum 0"
    assert branch.get("maximum") == 5, f"filter_requirements.{param} maximum 5"


async def test_filter_requirements_security_level_is_enum_in_schema() -> None:
    branch = _typed_branch(
        await _tool_param_schema("filter_requirements", "security_level"), "string"
    )
    allowed = branch.get("enum") or branch.get("const")
    assert isinstance(allowed, list), "security_level must be constrained, not a free string"
    assert set(cast("list[object]", allowed)) == {"normal-SdT", "erhöht"}


# ---------------------------------------------------------------------------
# get_requirements_by_ids (HANDOFF-021) — order/dedup/missing over the seeded
# catalog; list and item caps asserted at the published tool schema.
# ---------------------------------------------------------------------------


async def test_get_requirements_by_ids_preserves_order_and_dedups() -> None:
    reqs = await server.get_requirements_by_ids(["B.1", "A.1", "B.1"])
    assert [r.id for r in reqs] == ["B.1", "A.1"]


async def test_get_requirements_by_ids_skips_missing() -> None:
    reqs = await server.get_requirements_by_ids(["A.1", "GHOST", "B.1"])
    assert [r.id for r in reqs] == ["A.1", "B.1"]


async def test_get_requirements_by_ids_all_missing_returns_empty() -> None:
    assert await server.get_requirements_by_ids(["X", "Y"]) == []


async def test_get_requirements_by_ids_list_caps_in_schema() -> None:
    tools = await server.mcp.list_tools()
    tool = next(t for t in tools if t.name == "get_requirements_by_ids")
    ids_schema = tool.inputSchema["properties"]["ids"]
    assert ids_schema.get("type") == "array"
    assert ids_schema.get("minItems") == 1, "ids must require at least one entry"
    assert ids_schema.get("maxItems") == 200, "ids list must be capped at 200"


async def test_get_requirements_by_ids_item_cap_in_schema() -> None:
    tools = await server.mcp.list_tools()
    tool = next(t for t in tools if t.name == "get_requirements_by_ids")
    items = tool.inputSchema["properties"]["ids"]["items"]
    assert items.get("type") == "string"
    assert items.get("maxLength") == 128, "each id must be capped at 128 chars"
    assert items.get("minLength") == 1, "each id must be non-empty"


# ---------------------------------------------------------------------------
# get_catalog_stats (HANDOFF-021) — returns CatalogStats consistent with the
# seeded catalog; empty catalog yields zeros and empty dicts.
# ---------------------------------------------------------------------------


async def test_get_catalog_stats_consistent_with_seed(seed_catalog: Catalog) -> None:
    stats = await server.get_catalog_stats()
    assert isinstance(stats, CatalogStats)
    assert stats.total == len(seed_catalog.all()) == 3
    # All three seeded requirements are normal-SdT, effort 1.
    assert stats.by_security_level == {"normal-SdT": 3}
    assert sum(stats.by_security_level.values()) == stats.total
    assert stats.by_effort_level == {1: 3}
    assert sum(stats.by_effort_level.values()) == stats.total
    # Only A.1 carries a tag ("Rollen").
    assert stats.by_tag == {"Rollen": 1}


async def test_get_catalog_stats_empty_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_catalog", _catalog([]))
    stats = await server.get_catalog_stats()
    assert stats.total == 0
    assert stats.by_security_level == {}
    assert stats.by_effort_level == {}
    assert stats.by_tag == {}


# ---------------------------------------------------------------------------
# G2 — Audit logging: one logger.info per tool call, carrying the key
# parameter and the result size (hit/miss or count). No full requirement
# texts in the log.
# ---------------------------------------------------------------------------


async def test_log_get_requirement_by_id_hit(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_requirement_by_id("A.1")
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "A.1" in msg
    assert "hit" in msg


async def test_log_get_requirement_by_id_miss(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_requirement_by_id("NOPE")
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "NOPE" in msg
    assert "miss" in msg


async def test_log_list_requirements_by_module(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.list_requirements_by_module("ORP.1")
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "ORP.1" in msg
    assert "2" in msg  # count: A.1, A.2


async def test_log_search_requirements(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.search_requirements("Servereinsatz")
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "Servereinsatz" in msg
    assert "1" in msg  # count: B.1


@pytest.mark.parametrize("relation", ["related", "required"])
async def test_log_get_mapping(
    relation: Literal["related", "required"], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_mapping(relation)
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert relation in msg
    assert "1" in msg  # exactly one requirement carries each relation


async def test_log_list_modules(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.list_modules()
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "2" in msg  # two modules: ORP.1, SYS.1


async def test_log_get_catalog_metadata(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_catalog_metadata()
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "3" in msg  # requirement_count


async def test_log_filter_requirements(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.filter_requirements(module="ORP.1")
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "ORP.1" in msg  # key parameter
    assert "2" in msg  # count: A.1, A.2


async def test_log_get_requirements_by_ids_reports_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_requirements_by_ids(["A.1", "GHOST", "B.1"])
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "3" in msg  # requested count
    assert "2" in msg  # found count
    assert "1" in msg  # missing count


async def test_log_get_catalog_stats(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_catalog_stats()
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "3" in msg  # total requirements


async def test_log_never_contains_full_requirement_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # A.1's seeded text; no tool may leak the requirement body into the log.
    secret_text = "Verantwortlichkeiten MÜSSEN festgelegt werden."
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_requirement_by_id("A.1")
        await server.search_requirements("festgelegt")
        await server.list_requirements_by_module("ORP.1")
        await server.list_modules()
        await server.get_mapping("related")
        await server.get_catalog_metadata()
        await server.filter_requirements(module="ORP.1")
        await server.get_requirements_by_ids(["A.1", "A.2", "B.1"])
        await server.get_catalog_stats()
    assert secret_text not in caplog.text


# ---------------------------------------------------------------------------
# G2 — "catalog loaded: N requirements" is emitted exactly once, on the first
# _get_catalog that actually loads. Exercised without the network by forcing
# _catalog to None and mocking load_catalog to return a seeded Catalog.
# ---------------------------------------------------------------------------


async def test_catalog_loaded_logged_once_on_first_load(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    cat = _catalog([_req("X.1"), _req("X.2")])

    async def _fake_load() -> Catalog:
        return cat

    # Reset the cache so the next tool call triggers a (mocked) load. Exercised
    # through public tools — direct _get_catalog use stays out of the test.
    monkeypatch.setattr(server, "_catalog", None)
    monkeypatch.setattr(server, "load_catalog", _fake_load)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_catalog_metadata()  # first call: loads + logs
        await server.get_catalog_metadata()  # cached: must NOT log "loaded" again

    loaded = [
        r for r in caplog.records if r.name == LOGGER_NAME and "catalog loaded" in r.getMessage()
    ]
    assert len(loaded) == 1
    assert "2" in loaded[0].getMessage()  # N requirements


async def test_does_not_relog_catalog_loaded_when_already_seeded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # seed_catalog (autouse) already populated server._catalog, so a tool call
    # reuses the cache and emits no "catalog loaded" record.
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await server.get_catalog_metadata()
    loaded = [r for r in caplog.records if "catalog loaded" in r.getMessage()]
    assert loaded == []
