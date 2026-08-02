# 0002. Load BSI data at runtime from a pinned commit

- Status: accepted (refined by ADR-0011 on the scope of "unmodified")
- Date: 2026-06-06

> **Amendment (2026-08-02):** "unmodified" is too strong — in the Decision as
> well as the Rationale below. ADR-0009 later
> sanctioned resolving OSCAL parameter placeholders in the requirement prose, so
> the pass-through is not literal. The licence conclusion is unaffected, because
> it never rested on "we do not modify" but on "we ship no transformed artifact"
> — the substitution happens in memory, in the user's own process, and nothing
> derived is packaged. Read the rationale below with that substitution excepted;
> NOTICE states it for redistributors, and ADR-0011 records the corrected scope.

## Context and problem statement
The server needs the BSI Grundschutz++ compendium. The BSI publishes it as
machine-readable OSCAL under CC BY-SA 4.0 in a repository that is an explicit
work in progress, without releases, updated continuously through a transition
period lasting until roughly 2029. We must choose how the data reaches the
server and how to handle its volatility and license.

## Considered options
- Vendor a copy of the data inside the package.
- Vendor a transformed/pre-indexed artifact of the data.
- Load the raw data at runtime from a pinned upstream commit.

## Decision
Load the raw OSCAL data at runtime from a pinned commit of the BSI repository,
and pass it through unmodified.

## Rationale
Pinning to a commit (not a branch) keeps loads reproducible despite upstream
churn. Passing data through unmodified keeps the CC BY-SA 4.0 share-alike
obligation on the data only, leaving the server code free to be Apache 2.0
(see ADR-0006). Vendoring a transformed artifact would create a derivative work
and entangle the license boundary.

## Consequences
- Reproducible behaviour; updates are a deliberate commit bump (see CLAUDE.md
  update strategy), not an implicit moving target.
- Requires network at load time; a drift monitor in CI catches upstream change.
- Enforced by the enforce_layering hook (blocks data files inside the package).

## Revisit when
The BSI publishes versioned, stable releases, or offers a redistribution that
removes the share-alike concern.
