"""Tests for the anti-corruption layer.

These also serve as the regression net for upstream format drift: if the BSI
changes the OSCAL shape, the mapper must fail loudly here.

Designed from the SPEC and the public surface (map_requirement / map_catalog /
Catalog), not from the mapper's internals. The real value ranges come from
findings.md §Phase 1: sec_level in {normal-SdT, erhöht}, effort_level 0-5,
tags comma-separated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from grundschutz_mcp.mapper import OscalMappingError, map_catalog, map_requirement
from grundschutz_mcp.model import (
    Catalog,
    CatalogMetadata,
    CatalogStats,
    ModuleSummary,
    Requirement,
)

# Provenance values for map_catalog tests. Arbitrary but fixed: the mapper must
# pass them through into metadata unchanged.
_COMMIT = "deadbeefcafef00ddeadbeefcafef00ddeadbeef"
_REPO = "BSI-Bund/Stand-der-Technik-Bibliothek"


# ---------------------------------------------------------------------------
# Fixtures — the new OSCAL form
#
# A control the mapper accepts now needs: a "statement" AND a "guidance" part
# (both non-empty prose); a sec_level prop (normal-SdT|erhöht) and an
# effort_level prop ("0".."5"); optional tags prop (comma-separated) and
# optional related/required links. Helpers are typed dict[str, object] so they
# add no pyright reportMissingTypeArgument noise.
# ---------------------------------------------------------------------------


def _valid_control() -> dict[str, object]:
    """A minimal but complete control covering every mapped field."""
    return {
        "id": "APP.1.1.A1",
        "title": "Sichere Konfiguration",
        "parts": [
            {"name": "statement", "prose": "Die Anwendung MUSS sicher konfiguriert werden."},
            {"name": "guidance", "prose": "Hierzu SOLLTEN Härtungsmaßnahmen geprüft werden."},
        ],
        "props": [
            {"name": "sec_level", "value": "normal-SdT"},
            {"name": "effort_level", "value": "2"},
            {"name": "tags", "value": "Konfiguration, Härtung"},
        ],
        "links": [
            {"rel": "related", "href": "#APP.1.1.A2"},
            {"rel": "required", "href": "#APP.1.1.A3"},
        ],
    }


def _control(
    rid: str,
    title: str,
    prose: str,
    *,
    guidance: str = "Hinweise zur Umsetzung.",
    sec_level: str = "normal-SdT",
    effort_level: str = "0",
    tags: str | None = None,
    related: list[str] | None = None,
    required: list[str] | None = None,
) -> dict[str, object]:
    """A minimal but complete OSCAL control the mapper accepts."""
    props: list[dict[str, object]] = [
        {"name": "sec_level", "value": sec_level},
        {"name": "effort_level", "value": effort_level},
    ]
    if tags is not None:
        props.append({"name": "tags", "value": tags})
    links: list[dict[str, object]] = []
    for href in related or []:
        links.append({"rel": "related", "href": href})
    for href in required or []:
        links.append({"rel": "required", "href": href})
    return {
        "id": rid,
        "title": title,
        "parts": [
            {"name": "statement", "prose": prose},
            {"name": "guidance", "prose": guidance},
        ],
        "props": props,
        "links": links,
    }


# ---------------------------------------------------------------------------
# map_requirement — valid control: assert every mapped field
# ---------------------------------------------------------------------------


def test_maps_valid_control_all_fields() -> None:
    req = map_requirement(
        _valid_control(), module="APP.1.1", module_title="Allgemeine Anwendung", path="root"
    )
    assert req.id == "APP.1.1.A1"
    assert req.title == "Sichere Konfiguration"
    assert req.text == "Die Anwendung MUSS sicher konfiguriert werden."
    assert req.guidance == "Hierzu SOLLTEN Härtungsmaßnahmen geprüft werden."
    assert req.module == "APP.1.1"
    assert req.module_title == "Allgemeine Anwendung"
    assert req.security_level == "normal-SdT"
    assert req.effort_level == 2
    assert req.tags == ["Konfiguration", "Härtung"]
    assert req.related == ["APP.1.1.A2"]
    assert req.required == ["APP.1.1.A3"]


def test_maps_valid_control_text_and_guidance_verbatim() -> None:
    # Inv. 4: German wording is preserved, untranslated and unaltered (umlauts).
    req = map_requirement(
        _valid_control(), module="APP.1.1", module_title="Allgemeine Anwendung", path="root"
    )
    assert req.text == "Die Anwendung MUSS sicher konfiguriert werden."
    assert req.guidance == "Hierzu SOLLTEN Härtungsmaßnahmen geprüft werden."


def test_missing_id_fails_loudly() -> None:
    control = _valid_control()
    del control["id"]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="APP.1.1", module_title="t", path="root")
    assert "id" in str(exc.value)


def test_missing_title_fails_loudly() -> None:
    control = _valid_control()
    del control["title"]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="APP.1.1", module_title="t", path="root")
    assert "title" in str(exc.value)


# ---------------------------------------------------------------------------
# statement / guidance parts
# ---------------------------------------------------------------------------


def test_missing_statement_fails_loudly() -> None:
    control = _valid_control()
    control["parts"] = [{"name": "guidance", "prose": "Nur Guidance."}]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="APP.1.1", module_title="t", path="root")
    assert "statement" in str(exc.value)


def test_missing_guidance_fails_loudly() -> None:
    control = _valid_control()
    control["parts"] = [{"name": "statement", "prose": "Nur Statement."}]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="APP.1.1", module_title="t", path="root")
    assert "guidance" in str(exc.value)


def test_empty_statement_prose_fails_loudly() -> None:
    control = _valid_control()
    control["parts"] = [
        {"name": "statement", "prose": "   "},
        {"name": "guidance", "prose": "Hinweise."},
    ]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="APP.1.1", module_title="t", path="root")
    assert "statement" in str(exc.value)


# ---------------------------------------------------------------------------
# security_level (sec_level prop) — enum from findings.md
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["normal-SdT", "erhöht"])
def test_security_level_accepts_both_valid_values(value: str) -> None:
    control = _control("X.A1", "T", "Text.", sec_level=value)
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.security_level == value


def test_security_level_missing_fails_loudly() -> None:
    control = _valid_control()
    control["props"] = [{"name": "effort_level", "value": "1"}]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert "sec_level" in str(exc.value)
    assert exc.value.path == "root.props"


def test_security_level_unknown_value_fails_loudly_with_path() -> None:
    control = _control("X.A1", "T", "Text.", sec_level="sehr hoch")
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props"
    assert "sec_level" in str(exc.value)


# ---------------------------------------------------------------------------
# effort_level (effort_level prop) — ordinal 0..5 from findings.md
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "5"])
def test_effort_level_accepts_range_bounds(value: str) -> None:
    control = _control("X.A1", "T", "Text.", effort_level=value)
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.effort_level == int(value)


@pytest.mark.parametrize("value", ["6", "-1"])
def test_effort_level_out_of_range_fails_loudly(value: str) -> None:
    control = _control("X.A1", "T", "Text.", effort_level=value)
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props"


def test_effort_level_non_numeric_string_fails_loudly() -> None:
    control = _control("X.A1", "T", "Text.", effort_level="x")
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props"


def test_effort_level_missing_fails_loudly() -> None:
    control = _valid_control()
    control["props"] = [{"name": "sec_level", "value": "normal-SdT"}]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert "effort_level" in str(exc.value)


def test_effort_level_none_value_fails_loudly() -> None:
    control = _valid_control()
    control["props"] = [
        {"name": "sec_level", "value": "normal-SdT"},
        {"name": "effort_level", "value": None},
    ]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props"


def test_effort_level_bool_not_treated_as_int() -> None:
    # True is an int subclass; the mapper must NOT silently accept it as 1.
    control = _valid_control()
    control["props"] = [
        {"name": "sec_level", "value": "normal-SdT"},
        {"name": "effort_level", "value": True},
    ]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props"


# ---------------------------------------------------------------------------
# tags (tags prop) — comma-separated, [] default
# ---------------------------------------------------------------------------


def test_tags_single_value() -> None:
    control = _control("X.A1", "T", "Text.", tags="Lieferketten")
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.tags == ["Lieferketten"]


def test_tags_comma_separated_trimmed() -> None:
    control = _control("X.A1", "T", "Text.", tags="Lieferketten,  Exit-Strategie ")
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.tags == ["Lieferketten", "Exit-Strategie"]


def test_tags_multiple_props_concatenated() -> None:
    control = _valid_control()
    control["props"] = [
        {"name": "sec_level", "value": "normal-SdT"},
        {"name": "effort_level", "value": "1"},
        {"name": "tags", "value": "A, B"},
        {"name": "tags", "value": "C"},
    ]
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.tags == ["A", "B", "C"]


def test_tags_absent_yields_empty_list() -> None:
    control = _control("X.A1", "T", "Text.", tags=None)
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.tags == []


def test_tags_non_string_value_fails_loudly() -> None:
    control = _valid_control()
    control["props"] = [
        {"name": "sec_level", "value": "normal-SdT"},
        {"name": "effort_level", "value": "1"},
        {"name": "tags", "value": ["A", "B"]},
    ]
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props"


# ---------------------------------------------------------------------------
# related / required links — href '#' handling, [] default
# ---------------------------------------------------------------------------


def test_links_strip_leading_hash() -> None:
    control = _control("X.A1", "T", "Text.", related=["#X.A2"], required=["#X.A3"])
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.related == ["X.A2"]
    assert req.required == ["X.A3"]


def test_links_without_hash_kept_unchanged() -> None:
    control = _control("X.A1", "T", "Text.", related=["X.A2"], required=["X.A3"])
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.related == ["X.A2"]
    assert req.required == ["X.A3"]


def test_links_absent_yield_empty_lists() -> None:
    control = _control("X.A1", "T", "Text.", related=[], required=[])
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.related == []
    assert req.required == []


# ---------------------------------------------------------------------------
# _require_list — non-list parts/props/links/controls/groups fail loudly
# ---------------------------------------------------------------------------


def test_non_list_parts_fails_with_path() -> None:
    control = _valid_control()
    control["parts"] = "nope"
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.parts.parts"


def test_non_list_props_fails_with_path() -> None:
    control = _valid_control()
    control["props"] = "nope"
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.props.props"


def test_non_list_links_fails_with_path() -> None:
    control = _valid_control()
    control["links"] = "nope"
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert exc.value.path == "root.links.links"


def test_non_list_controls_fails_with_path() -> None:
    body: dict[str, object] = {"groups": [{"id": "G", "title": "G", "controls": "nope"}]}
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog.groups[0].controls"


def test_non_list_groups_fails_with_path() -> None:
    body: dict[str, object] = {"groups": "nope"}
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog.groups"


def test_non_list_subgroups_fails_with_path() -> None:
    body: dict[str, object] = {
        "groups": [{"id": "G", "title": "G", "controls": [], "groups": "nope"}]
    }
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog.groups[0].groups"


# ---------------------------------------------------------------------------
# Depth cap — deep group nesting raises OscalMappingError, not RecursionError
# ---------------------------------------------------------------------------


def test_deep_group_nesting_fails_loudly() -> None:
    # Build a chain of nested groups deeper than the documented cap (32).
    innermost: dict[str, object] = {"id": "G", "title": "G", "controls": []}
    node = innermost
    for _ in range(40):
        node = {"id": "G", "title": "G", "controls": [], "groups": [node]}
    body: dict[str, object] = {"groups": [node]}
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert "nesting" in str(exc.value).lower() or "depth" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# map_catalog — multi-level catalog body
# ---------------------------------------------------------------------------


def _catalog_body() -> dict[str, object]:
    """A multi-level catalog body (no top-level 'catalog' wrapper).

    One top group ORP.1 with one control and a nested sub-group ORP.1.SUB with
    one control; a second top group SYS.1 with one control. Groups carry an id
    (-> module) and a title (-> module_title). German wording is verbatim.
    """
    return {
        "metadata": {"version": "2024.1"},
        "groups": [
            {
                "id": "ORP.1",
                "title": "Organisation",
                "controls": [
                    _control(
                        "ORP.1.A1",
                        "Festlegung von Verantwortlichkeiten",
                        "Verantwortlichkeiten MÜSSEN festgelegt werden.",
                        tags="Organisation, Rollen",
                    )
                ],
                "groups": [
                    {
                        "id": "ORP.1.SUB",
                        "title": "Untergruppe",
                        "controls": [
                            _control(
                                "ORP.1.SUB.A1",
                                "Geltungsbereich",
                                "Der Geltungsbereich MUSS abgegrenzt werden.",
                            )
                        ],
                    }
                ],
            },
            {
                "id": "SYS.1",
                "title": "Server",
                "controls": [
                    _control(
                        "SYS.1.A1",
                        "Planung des Servereinsatzes",
                        "Der Servereinsatz MUSS geplant werden.",
                    )
                ],
            },
        ],
    }


def _wrapped_body() -> dict[str, object]:
    """The same body nested under a top-level 'catalog' key."""
    return {"catalog": _catalog_body()}


def test_map_catalog_requirement_count_counts_all_levels() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    # 1 (ORP.1) + 1 (ORP.1.SUB, nested) + 1 (SYS.1) = 3
    assert cat.metadata.requirement_count == 3
    assert len(cat.all()) == 3


def test_map_catalog_get_hits_top_and_nested() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    top = cat.get("ORP.1.A1")
    nested = cat.get("ORP.1.SUB.A1")
    assert top is not None and top.title == "Festlegung von Verantwortlichkeiten"
    assert nested is not None and nested.id == "ORP.1.SUB.A1"


def test_map_catalog_get_miss_returns_none() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    assert cat.get("DOES.NOT.EXIST") is None


def test_map_catalog_search_matches_title_and_text() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    # Substring in a title.
    by_title = cat.search("Server")
    assert [r.id for r in by_title] == ["SYS.1.A1"]
    # Substring in the German body text (casefold-insensitive).
    by_text = cat.search("geltungsbereich")
    assert [r.id for r in by_text] == ["ORP.1.SUB.A1"]


def test_map_catalog_search_matches_tag_substring() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    # "Rollen" only appears as a tag on ORP.1.A1, not in any title or text.
    by_tag = cat.search("rollen")
    assert [r.id for r in by_tag] == ["ORP.1.A1"]


def test_map_catalog_search_no_match_returns_empty() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    assert cat.search("Quantenkryptografie") == []


def test_map_catalog_preserves_german_text_verbatim() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    req = cat.get("ORP.1.A1")
    assert req is not None
    # Inv. 4: text is the original wording, untranslated and unaltered.
    assert req.text == "Verantwortlichkeiten MÜSSEN festgelegt werden."


def test_map_catalog_accepts_wrapped_and_direct_body_alike() -> None:
    wrapped = map_catalog(_wrapped_body(), commit=_COMMIT, repo=_REPO)
    direct = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    assert wrapped.metadata.requirement_count == direct.metadata.requirement_count
    assert [r.id for r in wrapped.all()] == [r.id for r in direct.all()]
    assert wrapped.metadata.version == direct.metadata.version


# ---------------------------------------------------------------------------
# module inheritance — module is the group ID, module_title the group title
# ---------------------------------------------------------------------------


def test_map_catalog_module_is_group_id_and_module_title_is_group_title() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    top = cat.get("ORP.1.A1")
    sys = cat.get("SYS.1.A1")
    assert top is not None and top.module == "ORP.1" and top.module_title == "Organisation"
    assert sys is not None and sys.module == "SYS.1" and sys.module_title == "Server"
    assert cat.by_module("ORP.1") == [top]
    assert cat.by_module("SYS.1") == [sys]


def test_map_catalog_subgroup_module_is_subgroup_id() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    nested = cat.get("ORP.1.SUB.A1")
    assert nested is not None
    # The nested control inherits the SUB-group id/title, not the parent's.
    assert nested.module == "ORP.1.SUB"
    assert nested.module_title == "Untergruppe"
    assert cat.by_module("ORP.1.SUB") == [nested]


def test_map_catalog_by_module_empty_for_unknown_module() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    assert cat.by_module("NO.SUCH.MODULE") == []


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_map_catalog_metadata_fields() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    assert cat.metadata.version == "2024.1"
    assert cat.metadata.source_commit == _COMMIT
    assert cat.metadata.source_repo == _REPO
    assert cat.metadata.license == "CC BY-SA 4.0"
    assert cat.metadata.requirement_count == len(cat.all())


def test_map_catalog_metadata_version_defaults_when_absent() -> None:
    body: dict[str, object] = {"groups": []}
    cat = map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert cat.metadata.version == "unknown"


# ---------------------------------------------------------------------------
# Fail loudly (Invariant 6) — top-level shapes, table-driven
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(None, id="none"),
        pytest.param([], id="empty-list"),
        pytest.param(["catalog"], id="list"),
        pytest.param("catalog", id="string"),
        pytest.param(42, id="int"),
    ],
)
def test_map_catalog_non_dict_top_level_fails_loudly(raw: object) -> None:
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(raw, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog"
    assert "catalog" in str(exc.value)


@pytest.mark.parametrize(
    "inner",
    [
        pytest.param(None, id="none"),
        pytest.param([], id="list"),
        pytest.param("x", id="string"),
        pytest.param(7, id="int"),
    ],
)
def test_map_catalog_non_dict_catalog_value_fails_loudly(inner: object) -> None:
    with pytest.raises(OscalMappingError) as exc:
        map_catalog({"catalog": inner}, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog"


def test_map_catalog_non_dict_group_fails_loudly_with_index() -> None:
    body: dict[str, object] = {
        "groups": [
            {"id": "ORP.1", "title": "ORP.1", "controls": []},
            "not-a-dict",  # index 1
        ]
    }
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog.groups[1]"


def test_map_catalog_control_without_id_propagates_tree_path() -> None:
    # A control missing its id, buried in a nested sub-group, must surface as a
    # loud error carrying the tree path down to the offending control.
    bad = _control("X.A1", "Ohne ID", "Text.")
    del bad["id"]
    body: dict[str, object] = {
        "groups": [
            {
                "id": "ORP.1",
                "title": "ORP.1",
                "controls": [],
                "groups": [
                    {
                        "id": "ORP.1.SUB",
                        "title": "ORP.1.SUB",
                        "controls": [bad],
                    }
                ],
            }
        ]
    }
    with pytest.raises(OscalMappingError) as exc:
        map_catalog(body, commit=_COMMIT, repo=_REPO)
    assert exc.value.path == "catalog.groups[0].groups[0].controls[0]"
    assert "id" in str(exc.value)


# ---------------------------------------------------------------------------
# Deliberately-retained behaviour (documented, NOT bugs)
# ---------------------------------------------------------------------------


def test_map_catalog_missing_groups_yields_empty_catalog() -> None:
    # No "groups" key at all: empty catalog, no error (documented).
    cat = map_catalog({"metadata": {"version": "2024.1"}}, commit=_COMMIT, repo=_REPO)
    assert cat.all() == []
    assert cat.metadata.requirement_count == 0


def test_map_catalog_duplicate_ids_last_wins_but_count_keeps_both() -> None:
    body: dict[str, object] = {
        "groups": [
            {
                "id": "DUP",
                "title": "DUP",
                "controls": [
                    _control("DUP.A1", "Erster", "Erster Text."),
                    _control("DUP.A1", "Zweiter", "Zweiter Text."),
                ],
            }
        ]
    }
    cat = map_catalog(body, commit=_COMMIT, repo=_REPO)
    # all()/count keep both entries...
    assert len(cat.all()) == 2
    assert cat.metadata.requirement_count == 2
    # ...but get() (backed by _by_id) returns the last one seen.
    won = cat.get("DUP.A1")
    assert won is not None and won.title == "Zweiter"


# ---------------------------------------------------------------------------
# OSCAL parameter resolution (HANDOFF-011, Phase 2)
#
# ~20% of real controls embed "{{ insert: param, <id> }}" tokens in their
# statement (and potentially guidance) prose. Spec (findings.md §Phase 2 +
# HANDOFF-010-return): the mapper resolves each token to the BSI-defined wording
# — ", ".join(values) if the param carries a non-empty `values` list, else its
# `label`. params come from control["params"] = [{"id", "label", values?}].
# Invariant 2: params are transient; they never appear on Requirement.
# Invariant 4: only the placeholder is substituted; surrounding text (umlauts
# included) stays byte-for-byte verbatim. fail-loudly (Inv. 6): a dangling
# param id raises with a .parts path; a param missing both values and label
# raises with a .params path.
#
# These tests drive the public map_requirement only; the param-carrying form is
# built by a dedicated helper so the existing placeholder-free fixtures (and
# their tests) are untouched.
# ---------------------------------------------------------------------------


def _param_control(
    *,
    statement: str,
    guidance: str = "Hinweise zur Umsetzung.",
    params: list[dict[str, object]] | None = None,
    include_params_key: bool = True,
) -> dict[str, object]:
    """A complete control whose prose may carry '{{ insert: param, id }}' tokens.

    `params` is the raw OSCAL params list ([{id, label, values?}, ...]). When
    `include_params_key` is False the 'params' key is omitted entirely, modelling
    a control that defines no parameters at all.
    """
    control: dict[str, object] = {
        "id": "X.A1",
        "title": "Titel",
        "parts": [
            {"name": "statement", "prose": statement},
            {"name": "guidance", "prose": guidance},
        ],
        "props": [
            {"name": "sec_level", "value": "normal-SdT"},
            {"name": "effort_level", "value": "0"},
        ],
        "links": [],
    }
    if include_params_key:
        control["params"] = params if params is not None else []
    return control


# --- (1) resolved via label (param has only a label, no values) ------------


def test_param_resolved_via_label_in_statement() -> None:
    control = _param_control(
        statement="Das ISMS MUSS nach {{ insert: param, p1 }} verankert werden.",
        params=[{"id": "p1", "label": "BSI Grundschutz++"}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Das ISMS MUSS nach BSI Grundschutz++ verankert werden."
    assert "{{" not in req.text


# --- (2) resolved via values; values win over label; multi-value join ------


def test_param_values_win_over_label() -> None:
    control = _param_control(
        statement="Wert: {{ insert: param, p1 }}.",
        params=[{"id": "p1", "label": "FALLBACK", "values": ["echter Wert"]}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    # values present and non-empty -> the label is NOT used.
    assert req.text == "Wert: echter Wert."
    assert "FALLBACK" not in req.text


def test_param_multiple_values_joined_with_comma_space() -> None:
    control = _param_control(
        statement="Werte: {{ insert: param, p1 }}.",
        params=[{"id": "p1", "values": ["A", "B", "C"]}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Werte: A, B, C."


def test_param_empty_values_list_falls_back_to_label() -> None:
    # An empty values list is not "present" for resolution purposes -> label wins.
    control = _param_control(
        statement="Wert: {{ insert: param, p1 }}.",
        params=[{"id": "p1", "label": "Etikett", "values": []}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Wert: Etikett."


# --- (3) guidance prose is resolved too ------------------------------------


def test_param_resolved_in_guidance_prose() -> None:
    control = _param_control(
        statement="Statement ohne Platzhalter.",
        guidance="Siehe {{ insert: param, p1 }} für Details.",
        params=[{"id": "p1", "label": "Referenzdokument"}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.guidance == "Siehe Referenzdokument für Details."
    assert "{{" not in req.guidance


# --- (4) several distinct placeholders; same placeholder twice -------------


def test_param_several_distinct_placeholders_in_one_prose() -> None:
    control = _param_control(
        statement="Von {{ insert: param, p1 }} bis {{ insert: param, p2 }}.",
        params=[
            {"id": "p1", "label": "Anfang"},
            {"id": "p2", "label": "Ende"},
        ],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Von Anfang bis Ende."


def test_param_same_placeholder_twice_both_replaced() -> None:
    control = _param_control(
        statement="{{ insert: param, p1 }} und nochmals {{ insert: param, p1 }}.",
        params=[{"id": "p1", "label": "Wert"}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Wert und nochmals Wert."
    assert "{{" not in req.text


# --- (5) unknown / dangling param id -> OscalMappingError with .parts path --


def test_param_unknown_id_in_statement_fails_loudly_with_parts_path() -> None:
    control = _param_control(
        statement="Verweis auf {{ insert: param, ghost }}.",
        params=[{"id": "p1", "label": "vorhanden"}],
    )
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert ".parts" in exc.value.path
    assert "ghost" in str(exc.value)


def test_param_unknown_id_with_no_params_defined_fails_loudly() -> None:
    # A placeholder but the control defines no params at all -> dangling ref.
    control = _param_control(
        statement="Verweis auf {{ insert: param, p1 }}.",
        include_params_key=False,
    )
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert ".parts" in exc.value.path


# --- (6) param with neither values nor label -> OscalMappingError .params ---


def test_param_without_values_and_without_label_fails_loudly_with_params_path() -> None:
    control = _param_control(
        statement="Text mit {{ insert: param, p1 }}.",
        params=[{"id": "p1"}],
    )
    with pytest.raises(OscalMappingError) as exc:
        map_requirement(control, module="X", module_title="t", path="root")
    assert ".params" in exc.value.path


# --- (7) no params key + prose without placeholders -> unchanged, no error --


def test_no_params_key_and_no_placeholder_passes_through_unchanged() -> None:
    control = _param_control(
        statement="Ein gewöhnlicher Satz ohne Maschinerie.",
        guidance="Auch hier kein Platzhalter.",
        include_params_key=False,
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Ein gewöhnlicher Satz ohne Maschinerie."
    assert req.guidance == "Auch hier kein Platzhalter."


# --- (8) Inv. 4: prose without placeholders byte-verbatim; surrounding text -


def test_param_prose_without_placeholder_is_byte_for_byte_verbatim() -> None:
    original = "Größe, Übersicht und Maßnahmen — alles bleibt unverändert (ÄÖÜß)."
    control = _param_control(statement=original, params=[{"id": "p1", "label": "X"}])
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == original


def test_param_text_around_resolved_placeholder_is_verbatim_with_umlauts() -> None:
    control = _param_control(
        statement="Für Prüfungen MÜSSEN {{ insert: param, p1 }} berücksichtigt werden.",
        params=[{"id": "p1", "label": "Größenklassen"}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert req.text == "Für Prüfungen MÜSSEN Größenklassen berücksichtigt werden."


# --- (9) Inv. 2: Requirement has no params field ---------------------------


def test_requirement_has_no_params_field() -> None:
    control = _param_control(
        statement="Text mit {{ insert: param, p1 }}.",
        params=[{"id": "p1", "label": "Wert"}],
    )
    req = map_requirement(control, module="X", module_title="t", path="root")
    assert "params" not in type(req).model_fields
    assert not hasattr(req, "params")


# ---------------------------------------------------------------------------
# Catalog.modules() / ModuleSummary (HANDOFF-013, Phase 2 discovery tool)
#
# Spec (HANDOFF-013/-014): Catalog.modules() aggregates requirements by their
# `module` (group id) into one ModuleSummary{module, module_title,
# requirement_count} per module. module_title is the first-seen title for that
# module id; the result is sorted by module id and is independent of input
# order. An empty catalog yields []. Inv. 2: ModuleSummary is a tiny projection
# with exactly three fields.
#
# Tested through the public surface: ModuleSummary built either via map_catalog
# (the real path) or by constructing a Catalog directly from Requirements (for
# first-seen-title and ordering edge cases that need precise control).
# ---------------------------------------------------------------------------


def _summary_req(rid: str, *, module: str, module_title: str) -> Requirement:
    """A minimal valid Requirement for direct Catalog construction."""
    return Requirement(
        id=rid,
        title="Titel",
        text="Text.",
        guidance="Hinweise.",
        module=module,
        module_title=module_title,
        security_level="normal-SdT",
        effort_level=0,
        tags=[],
        related=[],
        required=[],
    )


def _direct_catalog(reqs: list[Requirement]) -> Catalog:
    meta = CatalogMetadata(
        version="2024.1",
        source_repo=_REPO,
        source_commit=_COMMIT,
        requirement_count=len(reqs),
    )
    return Catalog(reqs, meta)


def test_modules_aggregates_one_summary_per_module_with_counts() -> None:
    # _catalog_body has three modules: ORP.1 (1 ctrl), ORP.1.SUB (1, nested),
    # SYS.1 (1). Add a fixture exercising a module with >= 2 requirements.
    cat = _direct_catalog(
        [
            _summary_req("A.1", module="A.1", module_title="Alpha"),
            _summary_req("A.2", module="A.1", module_title="Alpha"),
            _summary_req("B.1", module="B.1", module_title="Beta"),
        ]
    )
    summaries = cat.modules()
    assert [(s.module, s.module_title, s.requirement_count) for s in summaries] == [
        ("A.1", "Alpha", 2),
        ("B.1", "Beta", 1),
    ]


def test_modules_module_title_is_first_seen_on_conflict() -> None:
    # Two requirements share a module id but disagree on the title; the first
    # one encountered (in catalog order) wins.
    cat = _direct_catalog(
        [
            _summary_req("M.1", module="M", module_title="Erster Titel"),
            _summary_req("M.2", module="M", module_title="Zweiter Titel"),
        ]
    )
    summaries = cat.modules()
    assert len(summaries) == 1
    assert summaries[0].module_title == "Erster Titel"
    assert summaries[0].requirement_count == 2


def test_modules_sorted_by_module_id_regardless_of_input_order() -> None:
    # Input order is intentionally jumbled; output must always sort by module id.
    cat = _direct_catalog(
        [
            _summary_req("b1", module="B.2", module_title="B2"),
            _summary_req("c1", module="B.1", module_title="B1"),
            _summary_req("a1", module="A.1", module_title="A1"),
            _summary_req("b2", module="B.2", module_title="B2"),
        ]
    )
    summaries = cat.modules()
    assert [s.module for s in summaries] == ["A.1", "B.1", "B.2"]


def test_modules_empty_catalog_yields_empty_list() -> None:
    cat = _direct_catalog([])
    assert cat.modules() == []


def test_modules_counts_sum_to_total_requirements() -> None:
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    summaries = cat.modules()
    assert sum(s.requirement_count for s in summaries) == len(cat.all())


def test_module_summary_has_exactly_three_fields() -> None:
    # Inv. 2: ModuleSummary is a small projection, not a mirror of the source.
    assert set(ModuleSummary.model_fields) == {
        "module",
        "module_title",
        "requirement_count",
    }


def test_modules_from_map_catalog_covers_nested_subgroups() -> None:
    # The real path: modules built from a mapped catalog include nested
    # sub-group modules (ORP.1.SUB) as distinct modules, sorted by id.
    cat = map_catalog(_catalog_body(), commit=_COMMIT, repo=_REPO)
    summaries = cat.modules()
    assert [(s.module, s.module_title, s.requirement_count) for s in summaries] == [
        ("ORP.1", "Organisation", 1),
        ("ORP.1.SUB", "Untergruppe", 1),
        ("SYS.1", "Server", 1),
    ]


# ---------------------------------------------------------------------------
# Catalog.filter / by_ids / stats + CatalogStats (HANDOFF-021, Phase 2+)
#
# Spec (2026-06-07-additional-query-tools-design.md §Tools/§Edge cases) +
# HANDOFF-019/-020. These exercise the three new pure Catalog methods through
# the public surface, by constructing a Catalog directly from Requirements so
# the classification fields (security_level, effort_level, tags) can be set
# precisely. No raw OSCAL is involved.
#
#   - filter(*, module, security_level, min_effort, max_effort, tag): AND of
#     every non-None predicate; module/security_level exact; min/max_effort
#     inclusive bounds; tag case-insensitive exact; result sorted by id;
#     all-None -> the full catalog (a pure, composable identity).
#   - by_ids(ids): one Requirement per distinct found id, first-seen order;
#     missing ids skipped; all-missing -> [].
#   - stats() -> CatalogStats{total, by_security_level, by_effort_level,
#     by_tag}; empty catalog -> total 0 and three empty dicts.
# ---------------------------------------------------------------------------


def _full_req(
    rid: str,
    *,
    module: str = "M",
    module_title: str = "Modul",
    security_level: Literal["normal-SdT", "erhöht"] = "normal-SdT",
    effort_level: int = 0,
    tags: list[str] | None = None,
) -> Requirement:
    """A Requirement with full control over the filter/stats classification fields."""
    return Requirement(
        id=rid,
        title="Titel",
        text="Text.",
        guidance="Hinweise.",
        module=module,
        module_title=module_title,
        security_level=security_level,
        effort_level=effort_level,
        tags=tags or [],
        related=[],
        required=[],
    )


# --- Catalog.filter — each criterion in isolation --------------------------


def test_filter_module_exact_match() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", module="ORP.1"),
            _full_req("B.1", module="SYS.1"),
        ]
    )
    assert [r.id for r in cat.filter(module="ORP.1")] == ["A.1"]


def test_filter_module_no_partial_match() -> None:
    # module is an exact match, not a prefix/substring match.
    cat = _direct_catalog([_full_req("A.1", module="ORP.1")])
    assert cat.filter(module="ORP") == []


def test_filter_security_level_exact() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", security_level="normal-SdT"),
            _full_req("B.1", security_level="erhöht"),
        ]
    )
    assert [r.id for r in cat.filter(security_level="erhöht")] == ["B.1"]


def test_filter_min_effort_is_inclusive_lower_bound() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", effort_level=1),
            _full_req("A.2", effort_level=2),
            _full_req("A.3", effort_level=3),
        ]
    )
    assert [r.id for r in cat.filter(min_effort=2)] == ["A.2", "A.3"]


def test_filter_max_effort_is_inclusive_upper_bound() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", effort_level=1),
            _full_req("A.2", effort_level=2),
            _full_req("A.3", effort_level=3),
        ]
    )
    assert [r.id for r in cat.filter(max_effort=2)] == ["A.1", "A.2"]


def test_filter_min_equals_max_is_exact_effort() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", effort_level=1),
            _full_req("A.2", effort_level=2),
            _full_req("A.3", effort_level=3),
        ]
    )
    assert [r.id for r in cat.filter(min_effort=2, max_effort=2)] == ["A.2"]


def test_filter_effort_band() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.0", effort_level=0),
            _full_req("A.1", effort_level=1),
            _full_req("A.2", effort_level=2),
            _full_req("A.3", effort_level=3),
            _full_req("A.4", effort_level=4),
        ]
    )
    assert [r.id for r in cat.filter(min_effort=1, max_effort=3)] == ["A.1", "A.2", "A.3"]


def test_filter_inverted_effort_range_yields_empty() -> None:
    # Spec edge case: min_effort > max_effort matches nothing (not an error).
    cat = _direct_catalog(
        [
            _full_req("A.1", effort_level=1),
            _full_req("A.2", effort_level=4),
        ]
    )
    assert cat.filter(min_effort=4, max_effort=1) == []


def test_filter_tag_case_insensitive_exact_match() -> None:
    # "Rollen" filter matches a "rollen" tag (case-insensitive exact)...
    cat = _direct_catalog([_full_req("A.1", tags=["rollen"])])
    assert [r.id for r in cat.filter(tag="Rollen")] == ["A.1"]


def test_filter_tag_is_exact_not_substring() -> None:
    # ...but "roll" must NOT match the "rollen" tag (exact, not substring).
    cat = _direct_catalog([_full_req("A.1", tags=["Rollen"])])
    assert cat.filter(tag="roll") == []


def test_filter_tag_matches_any_of_multiple_tags() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", tags=["Organisation", "Rollen"]),
            _full_req("B.1", tags=["Server"]),
        ]
    )
    assert [r.id for r in cat.filter(tag="rollen")] == ["A.1"]


# --- Catalog.filter — combined AND -----------------------------------------


def test_filter_combines_criteria_with_and() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", module="ORP.1", security_level="erhöht", effort_level=3),
            _full_req("A.2", module="ORP.1", security_level="normal-SdT", effort_level=3),
            _full_req("A.3", module="SYS.1", security_level="erhöht", effort_level=3),
        ]
    )
    # Only A.1 satisfies module AND security_level AND effort together.
    result = cat.filter(module="ORP.1", security_level="erhöht", min_effort=3)
    assert [r.id for r in result] == ["A.1"]


def test_filter_three_criteria_with_tag() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", module="ORP.1", effort_level=2, tags=["Rollen"]),
            _full_req("A.2", module="ORP.1", effort_level=2, tags=["Server"]),
        ]
    )
    result = cat.filter(module="ORP.1", max_effort=2, tag="rollen")
    assert [r.id for r in result] == ["A.1"]


# --- Catalog.filter — deterministic sort by id -----------------------------


def test_filter_result_is_sorted_by_id_regardless_of_input_order() -> None:
    cat = _direct_catalog(
        [
            _full_req("C.1", module="M"),
            _full_req("A.1", module="M"),
            _full_req("B.1", module="M"),
        ]
    )
    assert [r.id for r in cat.filter(module="M")] == ["A.1", "B.1", "C.1"]


# --- Catalog.filter — no match and all-None identity -----------------------


def test_filter_no_match_returns_empty_list() -> None:
    cat = _direct_catalog([_full_req("A.1", module="ORP.1")])
    assert cat.filter(module="DOES.NOT.EXIST") == []


def test_filter_all_none_returns_every_requirement_sorted() -> None:
    # The Catalog method itself is a pure, composable identity when given no
    # criteria: it returns the whole catalog (sorted by id). The "at least one
    # criterion" guard lives in the tool layer (server.py), not here.
    cat = _direct_catalog(
        [
            _full_req("B.1"),
            _full_req("A.1"),
            _full_req("C.1"),
        ]
    )
    assert [r.id for r in cat.filter()] == ["A.1", "B.1", "C.1"]


# --- Catalog.by_ids --------------------------------------------------------


def test_by_ids_preserves_first_seen_input_order() -> None:
    cat = _direct_catalog([_full_req("A.1"), _full_req("B.1"), _full_req("C.1")])
    result = cat.by_ids(["C.1", "A.1", "B.1"])
    assert [r.id for r in result] == ["C.1", "A.1", "B.1"]


def test_by_ids_deduplicates_keeping_first_occurrence() -> None:
    cat = _direct_catalog([_full_req("A.1"), _full_req("B.1")])
    result = cat.by_ids(["A.1", "B.1", "A.1", "A.1"])
    assert [r.id for r in result] == ["A.1", "B.1"]


def test_by_ids_skips_missing_ids() -> None:
    cat = _direct_catalog([_full_req("A.1"), _full_req("B.1")])
    result = cat.by_ids(["A.1", "GHOST", "B.1"])
    assert [r.id for r in result] == ["A.1", "B.1"]


def test_by_ids_all_missing_returns_empty_list() -> None:
    cat = _direct_catalog([_full_req("A.1")])
    assert cat.by_ids(["X", "Y", "Z"]) == []


# --- Catalog.stats ---------------------------------------------------------


def test_stats_total_equals_len_all() -> None:
    cat = _direct_catalog([_full_req("A.1"), _full_req("B.1"), _full_req("C.1")])
    stats = cat.stats()
    assert stats.total == len(cat.all()) == 3


def test_stats_by_security_level_counts_sum_to_total() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", security_level="normal-SdT"),
            _full_req("A.2", security_level="normal-SdT"),
            _full_req("A.3", security_level="erhöht"),
        ]
    )
    stats = cat.stats()
    assert stats.by_security_level == {"normal-SdT": 2, "erhöht": 1}
    assert sum(stats.by_security_level.values()) == stats.total


def test_stats_by_effort_level_counts_sum_to_total_and_keys_are_str() -> None:
    cat = _direct_catalog(
        [
            _full_req("A.1", effort_level=0),
            _full_req("A.2", effort_level=2),
            _full_req("A.3", effort_level=2),
            _full_req("A.4", effort_level=5),
        ]
    )
    stats = cat.stats()
    # API-freeze: by_effort_level is dict[str, int] with keys '0'-'5'.
    assert stats.by_effort_level == {"0": 1, "2": 2, "5": 1}
    assert sum(stats.by_effort_level.values()) == stats.total
    # Keys must be stringified effort levels (dict[str, int]).
    assert all(isinstance(k, str) for k in stats.by_effort_level)


def test_stats_by_tag_exact_per_tag_counts_multi_tag_counts_in_each() -> None:
    # A requirement with multiple tags is counted once per tag, so the by_tag
    # values can sum to more than total. Assert exact per-tag counts, not a sum.
    cat = _direct_catalog(
        [
            _full_req("A.1", tags=["Rollen", "Organisation"]),
            _full_req("A.2", tags=["Organisation"]),
            _full_req("A.3", tags=[]),
        ]
    )
    stats = cat.stats()
    assert stats.by_tag == {"Rollen": 1, "Organisation": 2}
    # The multi-tag requirement makes the tag total exceed the requirement total.
    assert sum(stats.by_tag.values()) >= stats.total


def test_stats_empty_catalog_is_zero_and_empty_dicts() -> None:
    cat = _direct_catalog([])
    stats = cat.stats()
    assert stats.total == 0
    assert stats.by_security_level == {}
    assert stats.by_effort_level == {}
    assert stats.by_tag == {}


def test_catalog_stats_has_exactly_four_fields() -> None:
    # Inv. 2: CatalogStats is an aggregate projection, not an OSCAL mirror.
    assert set(CatalogStats.model_fields) == {
        "total",
        "by_security_level",
        "by_effort_level",
        "by_tag",
    }


# ---------------------------------------------------------------------------
# Loader canary (regression guard for Invariant 1) — UNCHANGED.
#
# Lives in test_mapper.py because that file is in the hook's OSCAL_ALLOWED list;
# referencing the OSCAL key literals here does not trip enforce_layering.py.
# This asserts loader.py does not perform raw OSCAL dict navigation.
# ---------------------------------------------------------------------------


def test_loader_source_has_no_raw_oscal_navigation() -> None:
    loader = Path(__file__).resolve().parent.parent / "src" / "grundschutz_mcp" / "loader.py"
    source = loader.read_text(encoding="utf-8")
    oscal_keys = ("controls", "parts", "props", "groups", "statement", "prose", "links")
    for key in oscal_keys:
        assert f'["{key}"]' not in source, f'loader.py navigates raw OSCAL: ["{key}"]'
        assert f"['{key}']" not in source, f"loader.py navigates raw OSCAL: ['{key}']"
        assert f'.get("{key}"' not in source, f'loader.py navigates raw OSCAL: .get("{key}"'
        assert f".get('{key}'" not in source, f"loader.py navigates raw OSCAL: .get('{key}'"
