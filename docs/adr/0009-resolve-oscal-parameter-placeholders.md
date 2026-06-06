# 0009. Resolve OSCAL parameter placeholders to BSI-defined values

- Status: accepted (refines ADR-0005)
- Date: 2026-06-06

## Context and problem statement
ADR-0005 requires returning the original German requirement text unchanged. An
end-to-end test against the pinned compendium revealed that ~20% of controls
(130 of 651) carry OSCAL parameter-insertion machinery in their statement prose,
e.g. `…ISMS nach {{ insert: param, gc.1.1-prm1 }} verankern.`. Returning that
string verbatim ships a non-authoritative, machine-mangled text: the reader sees
OSCAL templating, not the requirement. So a strict literal reading of "unchanged"
actually defeats the purpose of ADR-0005 (authoritative wording).

## Considered options
- Return the raw prose including `{{ insert: param, … }}` (literal "unchanged").
- Strip the placeholder token (produces grammatically broken text).
- Resolve each placeholder to the BSI-defined value the parameter supplies.

## Decision
The mapper resolves every `{{ insert: param, <id> }}` placeholder in part prose
to the BSI-supplied value: `", ".join(values)` if the parameter has a non-empty
`values` list, otherwise its `label`. Nothing is added, translated, paraphrased,
or summarized. A placeholder that references an unknown parameter, or a parameter
that has neither `values` nor `label`, fails loudly (`OscalMappingError` with a
path). Parameters are read transiently in the mapper and never enter the model.

## Rationale
`{{ insert: param, … }}` is OSCAL assembly machinery, not authored prose.
Expanding it to the value the BSI itself defined reconstructs the wording the BSI
authored — it introduces no editorial content. This refines, not overturns,
ADR-0005: "unchanged" means the authored German wording, with parameter
machinery expanded to its defined values, not the literal raw template. The core
of ADR-0005 (never translate, paraphrase, or summarize) is untouched.

## Consequences
- Positive: requirement texts read as the real, authoritative German wording.
- Negative / cost accepted: the mapper now performs a bounded, defined
  substitution on prose (no longer a pure pass-through); an empty `values: []`
  is treated as "not provided" and falls back to `label`.
- `re.sub` runs once over the original string, so a value that itself looks like
  a placeholder is emitted verbatim and never re-resolved (no injection loop).
- Enforced by: the mapper's per-placeholder fail-loudly (Inv. 6), the offline
  test suite, the network drift test, and the security-reviewer /
  architecture-guardian gate.

## Revisit when
The BSI introduces `select`/choice parameters, multi-value insertions with
non-trivial join semantics, or changes the insertion syntax — the network drift
test and the fail-loudly guards will surface it; adjust the resolver and bump the
pinned commit.
