# grundschutz-mcp

MCP server that makes the BSI IT-Grundschutz++ compendium queryable for AI
agents and ISMS tooling. Public OSS, Apache 2.0 code, CC BY-SA 4.0 data.

## Stack
- Python >= 3.11, official `mcp` SDK (FastMCP), Pydantic v2, httpx
- uv for env/packaging; Ruff (lint+format), Pyright (strict), Pytest
- Git + GitHub Actions. SemVer, signed releases, pinned dependencies

## Architecture invariants (BINDING, non-negotiable)
These are the reason this codebase stays maintainable. A change that violates
any of them is wrong even if it passes tests. The hooks enforce most of them;
do not try to work around the hooks. Each invariant traces to an Architectural
Decision Record in docs/adr; to change an invariant, write a superseding ADR
first (see docs/adr/README.md).

1. **Only `mapper.py` knows OSCAL.** No other module may navigate raw BSI/OSCAL
   structures (no `["controls"]`, `.get("parts")`, `["props"]`, etc. outside
   `mapper.py`). Tools and the loader work against the internal model only.
2. **The internal model is a projection, not a reimplementation.** `model.py`
   contains only fields the tools actually use. Do not mirror the full OSCAL
   schema. If the model starts approaching the source in size, push back.
3. **Tools touch the model, never raw dicts.** `server.py` tool bodies operate
   on `Requirement`/`Catalog`, never on parsed JSON.
4. **BSI requirement texts stay German.** The `text` field is the original
   wording. Never translate, summarize, or paraphrase requirement content.
5. **Data is loaded at runtime from the pinned commit and passed through
   unmodified.** Never vendor or ship a transformed BSI data artifact in the
   package. That would trigger CC BY-SA share-alike on the data and muddy the
   license boundary.
6. **Fail loudly.** The mapper raises `OscalMappingError` with a path on any
   unexpected shape. Never return silently wrong or partial data.
7. **License boundary is sacred.** Code is Apache 2.0; BSI data is CC BY-SA 4.0
   with attribution in NOTICE. Keep them separate.

Invariant-to-ADR map: (1,3) -> ADR-0003, (2) -> ADR-0004, (4) -> ADR-0005,
(5) -> ADR-0002, (6) -> ADR-0003/0002, (7) -> ADR-0006. Stack -> ADR-0007.

## Commands
- Setup:   `uv sync --extra dev`
- Lint:    `uv run ruff check . && uv run ruff format --check .`
- Types:   `uv run pyright`
- Tests:   `uv run pytest -m "not network"`  (offline unit suite)
- Drift:   `uv run pytest -m network`  (hits the pinned BSI source)
- All gates before shipping: run `/ship-check`

## Open verification points (must be resolved against real BSI data)
These are TODO in the code and must be set by reading the BSI repo's
`Dokumentation/OSCAL.md` and the actual compendium file:
- `config.py`: `BSI_PINNED_COMMIT`, `BSI_COMPENDIUM_PATH`
- `mapper.py`: the exact OSCAL field paths (`parts/statement`, `props`, `links`)
Use `/verify-oscal` to drive this. Do not invent field paths; verify them.

## Workflow
- Plan non-trivial changes with the `planner` subagent first.
- Implement with `coder`. Keep diffs minimal.
- Tests come from `test-writer`, designed from the spec, not the implementation.
- Any change to `mapper.py`, `model.py`, dependencies, CI, or release config
  MUST be reviewed by `security-reviewer` and pass `architecture-guardian`.
- Never silence Ruff/Pyright. Never weaken a hook to make a change pass.
