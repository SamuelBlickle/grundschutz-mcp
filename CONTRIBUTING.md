# Contributing

Contributions are welcome.

## Ground rules

- Code and comments in English. Returned BSI requirement texts stay in German.
- Keep the internal model small. It is a projection of the BSI compendium, not
  a reimplementation of it.
- Only `mapper.py` may know the OSCAL format. Tools work against the model.
- New behaviour needs tests. Format-relevant changes need a mapper test.

## Local setup

    uv sync --extra dev
    uv run ruff check .
    uv run pyright
    uv run pytest -m "not network"

The network-marked tests hit the pinned BSI source and run in CI.

All contributions are licensed under Apache 2.0 (code); any contributed data
artifacts under CC BY-SA 4.0.

## Architectural changes

Architectural decisions are recorded as ADRs in docs/adr (MADR format). If your
change alters or removes an architecture invariant, add a superseding ADR in the
same pull request, before or alongside the code change. See docs/adr/README.md.
