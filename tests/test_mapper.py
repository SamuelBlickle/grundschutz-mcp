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

import pytest

from grundschutz_mcp.mapper import OscalMappingError, map_catalog, map_requirement

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
