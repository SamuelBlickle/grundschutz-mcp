# 0001. Record architecture decisions

- Status: accepted
- Date: 2026-06-06

## Context and problem statement
This project encodes several non-obvious architectural constraints (an
anti-corruption layer, a deliberately small model, a license boundary). Hooks
and CLAUDE.md enforce them, but enforcement without recorded rationale invites
future maintainers, including the author, to remove a constraint whose reason
has been forgotten.

## Considered options
- No formal records; rely on CLAUDE.md and commit messages.
- A single freeform DECISIONS.md file.
- Numbered ADRs in the MADR format.

## Decision
Use numbered ADRs in the MADR format under docs/adr.

## Rationale
ADRs make decisions discoverable, dated, and immutable. MADR is lightweight,
Markdown-native, and widely understood, so contributors recognise it. A single
freeform file does not scale and loses the one-decision-per-record clarity.

## Consequences
- Each significant decision gets a record; invariants trace back to one.
- Small ongoing discipline cost when making architectural changes.
- Enforced by convention and reinforced in CONTRIBUTING.md.

## Revisit when
Never for the practice itself; individual ADRs are superseded as needed.
