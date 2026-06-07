# 0010. Version the software with SemVer, decoupled from the BSI data version

- Status: accepted
- Date: 2026-06-07

## Context and problem statement
The project has two independent version axes: the **software** (tool API, model
shape, behaviour) and the **BSI data snapshot** (the pinned upstream commit,
whose own version is a timestamp surfaced via `get_catalog_metadata`). Because
the pinned commit lives in `config.py`, bumping the data is itself a code change
and therefore a release — so a data bump still needs a version level. We must
define what a version communicates and how the two axes relate, especially since
we commit to `1.0.0` at the first public release.

## Considered options
- Couple the package version to the BSI data version (e.g. encode the data date).
- SemVer the software contract; keep the data version independent and surfaced
  via metadata; map data bumps onto SemVer by their content impact.
- Calendar-version the whole thing (e.g. `2026.06`).

## Decision
The package uses **Semantic Versioning for the software contract**. The BSI data
version is **independent** and exposed through `get_catalog_metadata`
(timestamp + pinned commit). Mapping:

- **MAJOR** — a breaking change to the software contract (tool removed/renamed,
  incompatible parameters/returns, model field removed/retyped, `get_mapping`
  semantics changed, incompatible error behaviour).
- **MINOR** — additive software change (new tool, new optional field) **or** a
  BSI data bump that **adds content** (new requirements/modules/tags/fields).
- **PATCH** — bug fix or internal change **or** a BSI data bump that is **only
  text corrections**.

The SemVer **stability contract covers the software** (tool names and
signatures, model field names and types, `get_mapping` semantics, fail-loudly
error behaviour, STDIO transport) and **not the data content** — the exact
requirement wording and the set of requirements track upstream BSI and are not
an API-stability promise. The **first public release is `1.0.0`**.

## Rationale
SemVer is the right contract for the *software*, which is what integrators code
against. Tying the package version to the data would force a `MAJOR` bump every
time the BSI renames or removes a requirement — churn driven by a third party,
not by our API. Decoupling keeps `1.0.0` honest: the API is what we keep stable,
while data freshness is a separate, traceable dimension (pin both package and
data version for reproducibility). The content-impact mapping (MINOR vs PATCH on
a data bump) keeps releases honest for compliance users without overstating a
typo fix. Going straight to `1.0.0` signals production-readiness; additive growth
stays within `1.x`, so the commitment is sustainable.

## Consequences
- Positive: integrators get a stable, SemVer-governed API; data freshness is
  visible and independent; `1.x` can grow additively for a long time.
- Negative / cost accepted: a genuinely breaking software change requires `2.0`
  (to be avoided/batched). Judging a data bump as MINOR vs PATCH requires reading
  the drift diff each time (the weekly drift monitor supports this).
- Data content is explicitly **not** under the stability promise; reproducibility
  is achieved by pinning a specific package version (which pins a data commit).
- Enforced by: this ADR, `VERSIONING.md`, the release runbook (`RELEASING.md`),
  and an API-freeze sanity check before the `1.0.0` tag.

## Revisit when
The BSI begins publishing stable, versioned data releases (then the data axis
could be pinned by release rather than commit), or a breaking software change is
unavoidable (the `2.0` trigger).
