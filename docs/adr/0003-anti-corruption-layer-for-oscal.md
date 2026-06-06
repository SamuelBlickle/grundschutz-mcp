# 0003. Isolate OSCAL knowledge in a mapper layer

- Status: accepted
- Date: 2026-06-06

## Context and problem statement
The BSI OSCAL format is external, detailed, and volatile during the transition
period. Multiple MCP tools need requirement data. If each tool reads the raw
OSCAL structure directly, every upstream field change forces edits in many
places, and the format's instability leaks into the whole codebase.

## Considered options
- Tools read raw OSCAL directly where needed.
- A shared helper module of OSCAL accessor functions.
- A full anti-corruption layer: a mapper translates OSCAL into an internal
  model; tools touch only the model.

## Decision
Introduce an anti-corruption layer. Only mapper.py knows the OSCAL format. Tools
and the loader operate exclusively on the internal model.

## Rationale
With multiple tools over a volatile source, confining format knowledge to one
component turns any upstream change into a single-site edit. The pattern is the
classic anti-corruption layer from domain-driven design and is justified here
precisely because there are several consumers and a moving source.

## Consequences
- Format drift is contained to mapper.py; tools are insulated.
- Slight indirection cost; in calm periods the mapper looks near one-to-one.
- Enforced by the enforce_layering hook (regex) and the architecture-guardian
  subagent (semantics the regex cannot see).

## Revisit when
The source becomes stable and single-consumer, making the layer pure overhead.
