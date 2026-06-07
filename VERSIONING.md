# Versioning and roadmap

This project follows [Semantic Versioning](https://semver.org/) for the
**software contract**. The decision and its rationale are recorded in
[ADR-0010](docs/adr/0010-versioning-semver-decoupled-from-bsi-data.md).

## Two version axes

- **Package version (`X.Y.Z`)** — the software: tool API, model shape, behaviour.
- **BSI data version** — the pinned upstream commit and the compendium's own
  version (a timestamp), surfaced at runtime via `get_catalog_metadata`. It is
  independent of the package version.

The pinned data commit lives in `config.py`, so updating the data is a code
change and ships as a release — mapped onto SemVer by its content impact (below).

## SemVer rules

| Level | Triggers |
| --- | --- |
| **MAJOR** | Breaking change to the software contract: a tool removed or renamed; incompatible parameters or return shape; a model field removed or retyped; `get_mapping` semantics changed; incompatible error behaviour. |
| **MINOR** | Additive software change (new tool, new optional model field) **or** a BSI data bump that **adds content** (new requirements, modules, tags, or fields). |
| **PATCH** | Bug fix or internal change **or** a BSI data bump that is **only text corrections**. |

## Stability contract

**Covered (stable across `1.x`):** tool names and signatures, model field names
and types, `get_mapping` semantics, fail-loudly error behaviour, the STDIO
transport.

**Not covered (no stability promise):** the requirement **content** and exact
German wording (these track upstream BSI), the internal log format, and the
specific pinned commit. For a reproducible result, pin a specific **package**
version — it pins a specific **data** commit.

## Roadmap

- **1.0.0** — first public release: the nine tools and the verified internal
  model over pinned BSI data. The software contract is stable from here.
- **1.x (MINOR, additive):** convenience discovery/filter helpers, optional
  caching, and additional framework mappings **if** the BSI adds structured
  mappings upstream — driven by need and feedback. Content-adding data bumps
  land here.
- **1.x.z (PATCH):** bug fixes and text-correction data bumps; the weekly drift
  monitor surfaces upstream changes that trigger these.
- **2.0.0** — only if a genuinely breaking software change becomes necessary;
  avoided and batched where possible.

## Releasing a data update

1. The weekly drift monitor (CI) flags when upstream BSI has moved past the
   pinned commit, or that the pinned data no longer maps.
2. Review the upstream diff: content added → MINOR; corrections only → PATCH.
3. Bump `BSI_PINNED_COMMIT` in `config.py`, run the gates, and release per
   [RELEASING.md](RELEASING.md).

## Before the 1.0.0 tag

Run a brief **API-freeze check**: confirm the current tool and model surface is
one we are willing to keep stable across `1.x` (additive changes only until a
deliberate `2.0`). See `RELEASING.md` for the release steps.
