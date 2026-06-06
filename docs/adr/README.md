# Architectural Decision Records

This directory records the significant architectural decisions for
grundschutz-mcp, using the [MADR](https://adr.github.io/madr/) format.

An ADR captures one decision: its context, the options considered, the choice,
and its consequences. ADRs are immutable once accepted. To change a decision,
write a new ADR that supersedes the old one and update the old one's status.

The architecture invariants enforced in CLAUDE.md and by the hooks trace back to
these records. If you want to change an invariant, you are changing a decision:
write the superseding ADR first.

## Index
- [0001](0001-record-architecture-decisions.md) - Record architecture decisions
- [0002](0002-runtime-load-pinned-bsi-data.md) - Load BSI data at runtime from a pinned commit
- [0003](0003-anti-corruption-layer-for-oscal.md) - Isolate OSCAL knowledge in a mapper layer
- [0004](0004-internal-model-is-a-projection.md) - Keep the internal model a projection
- [0005](0005-keep-bsi-texts-in-german.md) - Return BSI requirement texts in German only
- [0006](0006-license-boundary-apache-ccbysa.md) - Separate code (Apache 2.0) and data (CC BY-SA 4.0)
- [0007](0007-python-mcp-sdk-stack.md) - Build on Python and the official MCP SDK
- [0008](0008-model-fields-from-verified-bsi-data.md) - Model the fields the real BSI data carries
- [0009](0009-resolve-oscal-parameter-placeholders.md) - Resolve OSCAL parameter placeholders (refines 0005)

## Template
Copy [template.md](template.md) for new records. Number sequentially.
