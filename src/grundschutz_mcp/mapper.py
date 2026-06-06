"""Anti-corruption layer: the ONLY component that knows the BSI OSCAL format.

Tools never touch raw OSCAL. They work against the internal model. When the BSI
changes its format, only this file changes. The mapper validates aggressively
and raises a clear, located error rather than letting malformed data flow
through silently.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal, cast

from .model import Catalog, CatalogMetadata, Requirement

_MAX_GROUP_DEPTH = 32


class OscalMappingError(RuntimeError):
    """Raised when the OSCAL data does not match the expected structure.

    Carrying the offending path makes upstream format drift obvious instead of
    surfacing as a cryptic failure deep inside a tool.
    """

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(f"{message} (at {path})")
        self.path = path


def _require(obj: dict[str, Any], key: str, *, path: str) -> Any:
    if key not in obj:
        raise OscalMappingError(f"missing expected key '{key}'", path=path)
    return obj[key]


def _require_list(obj: dict[str, Any], key: str, *, path: str) -> list[Any]:
    """Return obj[key] as a list, [] if absent, raising if present but not a list."""
    value = obj.get(key, [])
    if not isinstance(value, list):
        raise OscalMappingError(f"expected '{key}' to be a list", path=f"{path}.{key}")
    return cast("list[Any]", value)


def map_requirement(
    control: dict[str, Any], *, module: str, module_title: str, path: str
) -> Requirement:
    """Translate a single OSCAL control into the internal Requirement model.

    This is the single place that knows the BSI OSCAL field paths. All field
    extraction is validated up front so that a malformed shape surfaces as an
    OscalMappingError with the offending path (Invariant 6) rather than as a
    later Pydantic ValidationError that has lost the OSCAL context.
    """
    rid = _require(control, "id", path=path)
    title = _require(control, "title", path=f"{path}.title")

    text = _extract_part_prose(control, "statement", path=f"{path}.parts")
    guidance = _extract_part_prose(control, "guidance", path=f"{path}.parts")
    security_level = _extract_security_level(control, path=f"{path}.props")
    effort_level = _extract_effort_level(control, path=f"{path}.props")
    tags = _extract_tags(control, path=f"{path}.props")
    related = _extract_links(control, "related", path=f"{path}.links")
    required = _extract_links(control, "required", path=f"{path}.links")

    return Requirement(
        id=str(rid),
        title=str(title),
        text=text,
        guidance=guidance,
        module=module,
        module_title=module_title,
        security_level=security_level,
        effort_level=effort_level,
        tags=tags,
        related=related,
        required=required,
    )


def _extract_part_prose(control: dict[str, Any], part_name: str, *, path: str) -> str:
    """Return the non-empty prose of the named part. German, verbatim (Invariant 4)."""
    for raw_part in _require_list(control, "parts", path=path):
        if not isinstance(raw_part, dict):
            continue
        part = cast("dict[str, Any]", raw_part)
        if part.get("name") == part_name:
            prose = part.get("prose")
            if isinstance(prose, str) and prose.strip():
                return prose
    raise OscalMappingError(f"no non-empty '{part_name}' prose found", path=path)


def _extract_security_level(
    control: dict[str, Any], *, path: str
) -> Literal["normal-SdT", "erhöht"]:
    """Return the sec_level prop value, validated against the known enum.

    An unknown or missing value is a drift signal and fails loudly with the
    path so the validation error carries OSCAL context, not a Pydantic one.
    """
    for raw_prop in _require_list(control, "props", path=path):
        if not isinstance(raw_prop, dict):
            continue
        prop = cast("dict[str, Any]", raw_prop)
        if prop.get("name") == "sec_level":
            value = prop.get("value")
            if value == "normal-SdT" or value == "erhöht":
                return value
            raise OscalMappingError(f"unexpected sec_level value {value!r}", path=path)
    raise OscalMappingError("missing 'sec_level' prop", path=path)


def _extract_effort_level(control: dict[str, Any], *, path: str) -> int:
    """Return the effort_level prop value as an int in 0..5, failing loudly otherwise."""
    for raw_prop in _require_list(control, "props", path=path):
        if not isinstance(raw_prop, dict):
            continue
        prop = cast("dict[str, Any]", raw_prop)
        if prop.get("name") == "effort_level":
            value = prop.get("value")
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                raise OscalMappingError(f"non-integer effort_level value {value!r}", path=path)
            try:
                level = int(value)
            except ValueError:
                raise OscalMappingError(
                    f"non-integer effort_level value {value!r}", path=path
                ) from None
            if not 0 <= level <= 5:
                raise OscalMappingError(f"effort_level {level} out of range 0..5", path=path)
            return level
    raise OscalMappingError("missing 'effort_level' prop", path=path)


def _extract_tags(control: dict[str, Any], *, path: str) -> list[str]:
    """Return tags from all 'tags' props (comma-separated values), [] if absent."""
    tags: list[str] = []
    for raw_prop in _require_list(control, "props", path=path):
        if not isinstance(raw_prop, dict):
            continue
        prop = cast("dict[str, Any]", raw_prop)
        if prop.get("name") == "tags":
            value = prop.get("value")
            if not isinstance(value, str):
                raise OscalMappingError(f"non-string tags value {value!r}", path=path)
            tags.extend(token.strip() for token in value.split(",") if token.strip())
    return tags


def _extract_links(control: dict[str, Any], rel: str, *, path: str) -> list[str]:
    """Return hrefs of links with the given rel, stripping a leading '#'."""
    refs: list[str] = []
    for raw_link in _require_list(control, "links", path=path):
        if not isinstance(raw_link, dict):
            continue
        link = cast("dict[str, Any]", raw_link)
        if link.get("rel") == rel:
            href = link.get("href")
            if isinstance(href, str) and href:
                refs.append(href[1:] if href.startswith("#") else href)
    return refs


def map_metadata(catalog: dict[str, Any], *, commit: str, repo: str, count: int) -> CatalogMetadata:
    meta = catalog.get("metadata", {})
    return CatalogMetadata(
        version=str(meta.get("version", "unknown")),
        source_repo=repo,
        source_commit=commit,
        requirement_count=count,
    )


def _walk_controls(
    group: dict[str, Any], *, module: str, module_title: str, path: str, depth: int = 0
) -> Iterator[Requirement]:
    if depth > _MAX_GROUP_DEPTH:
        raise OscalMappingError(f"group nesting exceeds {_MAX_GROUP_DEPTH}", path=path)
    for i, control in enumerate(_require_list(group, "controls", path=path)):
        if not isinstance(control, dict):
            raise OscalMappingError("expected a control object", path=f"{path}.controls[{i}]")
        yield map_requirement(
            cast("dict[str, Any]", control),
            module=module,
            module_title=module_title,
            path=f"{path}.controls[{i}]",
        )
    for j, sub in enumerate(_require_list(group, "groups", path=path)):
        if not isinstance(sub, dict):
            raise OscalMappingError("expected a group object", path=f"{path}.groups[{j}]")
        sub_group = cast("dict[str, Any]", sub)
        sub_module = str(sub_group.get("id", ""))
        sub_module_title = str(sub_group.get("title", ""))
        yield from _walk_controls(
            sub_group,
            module=sub_module,
            module_title=sub_module_title,
            path=f"{path}.groups[{j}]",
            depth=depth + 1,
        )


def map_catalog(raw: object, *, commit: str, repo: str) -> Catalog:
    """Map raw OSCAL into an indexed Catalog. Pure function for easy testing.

    `raw` is the parsed JSON body (typically from `resp.json()`). It is typed
    `object` so the structural guards below are real, type-checked checks: they
    fail loudly with a path rather than letting malformed top-level shapes
    (None, a list, a missing catalog) surface as a cryptic AttributeError deeper
    in the walk (Invariant 6).
    """
    if not isinstance(raw, dict):
        raise OscalMappingError("expected a JSON object at the top level", path="catalog")
    body = cast("dict[str, Any]", raw)
    inner: object = body.get("catalog", body)
    if not isinstance(inner, dict):
        raise OscalMappingError("expected a 'catalog' object", path="catalog")
    catalog = cast("dict[str, Any]", inner)
    requirements: list[Requirement] = []
    for i, group in enumerate(_require_list(catalog, "groups", path="catalog")):
        if not isinstance(group, dict):
            raise OscalMappingError("expected a group object", path=f"catalog.groups[{i}]")
        top_group = cast("dict[str, Any]", group)
        module = str(top_group.get("id", ""))
        module_title = str(top_group.get("title", ""))
        requirements.extend(
            _walk_controls(
                top_group,
                module=module,
                module_title=module_title,
                path=f"catalog.groups[{i}]",
                depth=0,
            )
        )
    metadata = map_metadata(catalog, commit=commit, repo=repo, count=len(requirements))
    return Catalog(requirements, metadata)
