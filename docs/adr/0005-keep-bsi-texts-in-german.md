# 0005. Return BSI requirement texts in German only

- Status: accepted (refined by ADR-0009 on OSCAL parameter-placeholder resolution)
- Date: 2026-06-06

## Context and problem statement
The server's technical surface is English for reach and tooling consistency. The
requirement content, however, is authoritative German text from the BSI. We must
decide whether to translate it.

## Considered options
- Translate requirement texts to English for a uniform English experience.
- Offer both German original and a generated translation.
- Return the German original only; never translate.

## Decision
Return the original German requirement text unchanged. Never translate,
paraphrase, or summarize requirement content.

## Rationale
Compliance work depends on the exact authoritative wording. A translation,
machine or human, introduces drift from the legally and technically meaningful
source and would undermine the tool's core value. The English technical surface
and the German content are not in conflict; they serve different layers.

## Consequences
- The tool stays trustworthy for compliance use.
- Non-German-reading users get untranslated content, an accepted trade-off.
- Enforced by CLAUDE.md, the coder subagent rules, and review.

## Revisit when
The BSI itself publishes authoritative translations that could be passed through
with the same provenance guarantees.
