# 0004. Keep the internal model a projection, not a reimplementation

- Status: accepted
- Date: 2026-06-06

## Context and problem statement
Given the anti-corruption layer (ADR-0003), the internal model could grow to
mirror the full OSCAL schema. That would recreate the BSI structure in our code,
doubling maintenance and defeating the point of the layer.

## Considered options
- Model the full OSCAL schema internally for completeness.
- Model only the fields the MCP tools actually consume (a projection).

## Decision
The internal model contains only the fields the tools use. It is a projection of
the compendium, not a reimplementation of it.

## Rationale
A projection is not a clone: modelling three to five consumed fields out of a
rich schema is a view, not a duplicate. The value of the mapper is decoupling
the timing of change, not mirroring the source. A model that approaches the
source in completeness has crossed from projection into duplication and should
be trimmed back.

## Consequences
- Small, legible model; low maintenance.
- New tool needs may require adding a field, a deliberate act.
- Enforced by the architecture-guardian subagent (flags growth toward parity).

## Revisit when
A genuinely new consumer needs substantially more of the schema; even then, add
only what is consumed.
