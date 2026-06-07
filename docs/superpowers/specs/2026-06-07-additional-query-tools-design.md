# Design: additional query tools (filter, batch fetch, stats)

- Status: approved (brainstorming), pending implementation plan
- Date: 2026-06-07

## Context

The server currently exposes six tools: `get_requirement_by_id`,
`list_requirements_by_module`, `list_modules`, `search_requirements`,
`get_mapping`, `get_catalog_metadata`. Three access patterns are missing for
ISMS scoping/prioritisation and downstream automation that builds on the
structured catalog:

1. No way to query by the classification fields the model already carries
   (`security_level`, `effort_level`, `tags`) or to combine them with `module`.
   `search_requirements` is substring-only; `list_requirements_by_module` keys
   on module alone.
2. Following `related`/`required` cross-references means one call per id.
3. No catalogue overview (counts by level/effort) and no way to discover which
   tags exist before filtering by one.

All three are served from fields already in the internal model — no new OSCAL
field paths, no change to the mapper, no transformation of requirement text.

## Tools

### 1. `filter_requirements(...) -> list[Requirement]`

Combined, AND-composed filter over existing fields.

| Parameter | Type | Semantics |
|---|---|---|
| `module` | `str \| None` (1–64) | exact match on the group id (as `by_module`) |
| `security_level` | `Literal["normal-SdT", "erhöht"] \| None` | exact |
| `min_effort` | `int \| None` (0–5) | keep `effort_level >= min_effort` |
| `max_effort` | `int \| None` (0–5) | keep `effort_level <= max_effort` |
| `tag` | `str \| None` (1–64) | case-insensitive exact match against the tag list |

- Criteria combine with AND. Result sorted by requirement id (deterministic).
- **At least one criterion is required.** With all parameters `None` the tool
  raises a clear error rather than returning the whole catalogue (avoids an
  accidental full dump; bulk export is intentionally out of scope).
- `min_effort`/`max_effort` together express `<= n`, `>= n`, exactly `n`, or a
  band; either may be omitted.

### 2. `get_requirements_by_ids(ids) -> list[Requirement]`

| Parameter | Type | Semantics |
|---|---|---|
| `ids` | `list[str]` (1–200 items, each 1–128 chars) | requirement ids to fetch |

- Returns one `Requirement` per distinct found id, in first-seen input order.
- Ids not present in the catalogue are skipped; the count of misses is logged.
- Token-efficient retrieval when following `related`/`required` references.

### 3. `get_catalog_stats() -> CatalogStats`

Aggregate overview, computed over the internal model.

```
CatalogStats {
  total: int,
  by_security_level: dict[str, int],   # e.g. {"normal-SdT": 518, "erhöht": 133}
  by_effort_level:   dict[int, int],   # keys 0..5
  by_tag:            dict[str, int],   # tag -> count; also serves tag discovery
}
```

- Per-module counts are intentionally **not** included — `list_modules` already
  provides them. Tag discovery is the `by_tag` keys.

## Internal model changes (`model.py`)

- New `CatalogStats(BaseModel)` with the four fields above.
- New `Catalog` methods: `filter(...)`, `by_ids(...)`, `stats()` — pure
  aggregation/selection over `self._all` (`list[Requirement]`); no raw-dict or
  OSCAL access.

## Invariants

- **Inv. 1:** no OSCAL navigation added; `mapper.py`/`loader.py` untouched.
- **Inv. 2:** `CatalogStats` is an aggregate projection (counts), like
  `ModuleSummary` — not a schema mirror. No new requirement fields.
- **Inv. 3:** tools call only `Catalog` methods / model objects.
- **Inv. 4:** these tools filter and select; they never translate, summarise, or
  alter requirement text.
- `model.py` changes → security-reviewer + architecture-guardian gate.

## Edge cases

- `filter_requirements` with no criteria → error (see above).
- `filter_requirements` with criteria that match nothing → empty list (not an error).
- `min_effort > max_effort` → empty list (no match), not an error.
- `get_requirements_by_ids` with duplicate ids → de-duplicated, first-seen order.
- `get_requirements_by_ids` with all-missing ids → empty list.
- `get_catalog_stats` over an empty catalogue → zeros / empty dicts.
- Input bounds (lengths, effort range, list size) enforced at the MCP boundary
  via `Annotated`/`Field`, consistent with the existing tools.

## Out of scope (YAGNI)

- A bulk "export all requirements" tool (large payload; not requested).
- A separate `list_tags` tool (tag counts live in `get_catalog_stats.by_tag`).
- Transitive `related`/`required` closure traversal.
- MCP prompts/resources.

## Follow-on doc updates

- README tools table + usage examples extended with the three tools.
- `server.py` module docstring ("the five tools") corrected to the real count.

## Testing (from spec)

- `filter_requirements`: each criterion alone; combined AND; the
  at-least-one-criterion guard; effort range bounds (`<= n`, `>= n`, exact,
  band, inverted → empty); tag case-insensitivity; module exact; deterministic
  sort; no-match → empty.
- `get_requirements_by_ids`: input order preserved; duplicates de-duplicated;
  missing skipped; cap enforced at the boundary.
- `get_catalog_stats`: `total` equals `len(all())`; the level/effort/tag
  breakdowns sum consistently; tags appear with correct counts.
