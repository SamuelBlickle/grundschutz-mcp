# 0008. Model the fields the real BSI data actually carries

- Status: accepted
- Date: 2026-06-06

> **Erratum (2026-06-20):** the tool named `get_mapping` below was later renamed
> to `get_cross_references` (pre-1.0 API polish). This record is left unchanged
> as a historical artifact; see VERSIONING.md for the current tool surface.

## Context and problem statement
The initial scaffold modelled each requirement with CIA protection goals
(`confidentiality`/`integrity`/`availability` point scores) and ISO 27001
references (`iso27001_refs`), and exposed a `get_mapping("iso27001")` tool.
Verifying the mapper against the real pinned compendium
(`Anwenderkataloge/Grundschutz++/Grundschutz++-catalog.json`, 651 controls)
showed that neither concept exists in the data: there are no CIA props and no
structured ISO 27001 mapping (ISO appears only as incidental prose). The lenient
mapper would not have failed on this — it would have returned empty CIA scores
and empty ISO refs for every requirement, a silently hollow result that violates
the fail-loudly principle (ADR-0003) in spirit.

## Considered options
- Keep the scaffold fields; accept that they are always empty against real data.
- Drop the unfounded fields and stop there (minimal model).
- Drop the unfounded fields and replace them with the classification axes the
  data actually carries.

## Decision
Replace the fictional fields with verified ones. `Requirement` now carries:
`id`, `title`, `text` (statement prose), `guidance`, `module` (group id),
`module_title` (group title), `security_level` (`normal-SdT` | `erhöht`),
`effort_level` (0–5), `tags`, `related`, `required`. `ProtectionGoals` and
`iso27001_refs` are removed. `get_mapping` is repurposed from ISO mapping to the
real internal control-to-control cross-references it does have:
`get_mapping(relation: "related" | "required")`.

## Rationale
A model field must reflect data that exists and that a tool consumes
(ADR-0004). CIA scores and ISO refs fail the first test. `security_level`,
`effort_level`, `tags`, and the related/required links are present on real
controls and are useful for ISMS tooling (prioritisation, filtering,
navigation). Keeping empty fields would ship a tool that lies by omission;
removing them without replacement would discard genuinely useful, available
classification. The model stays a projection, not a mirror (ADR-0004): the
deliberately excluded fields are `params`, `alt-identifier`, `oscal-version`,
prop namespaces, `class`, and `back-matter`.

## Consequences
- Positive: tools return real, populated data; the network drift test asserts the
  new fields, so a hollow result is caught loudly.
- Negative / costs accepted: `module` semantics changed from group title to group
  id (`by_module` now keys on the id); the `get_mapping` tool contract changed
  (ISO → related/required). README/docs must reflect this in Phase 3.
- `security_level` is a strict `Literal`: an unknown upstream value fails loudly
  as a drift signal rather than passing silently.
- Enforced by: the mapper's per-field `OscalMappingError` (fail loudly), the
  network schema test, and the architecture-guardian / security-reviewer gate.

## Revisit when
The BSI adds a third `security_level`, introduces a structured ISO 27001 (or
other framework) mapping, or changes the prop/part/link names — any of which the
network drift test will surface. Bump the pinned commit and adjust the mapper.
