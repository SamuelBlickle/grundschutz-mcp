# grundschutz-mcp

[![CI](https://github.com/SamuelBlickle/grundschutz-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelBlickle/grundschutz-mcp/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Code: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](./LICENSE)
[![Data: CC BY-SA 4.0](https://img.shields.io/badge/Data-CC%20BY--SA%204.0-lightgrey.svg)](./NOTICE)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-server-purple.svg)](https://modelcontextprotocol.io)

A Model Context Protocol (MCP) server that makes the German BSI IT-Grundschutz++
compendium queryable for AI agents and ISMS tooling. Instead of pasting
requirements into prompts or letting a model guess from stale training data,
agents query the exact, current requirement text from the official BSI source,
addressable by ID.

> **Disclaimer:** This is an independent, community project. It is **not**
> affiliated with, endorsed by, or certified by the BSI (Bundesamt für
> Sicherheit in der Informationstechnik). It only makes the BSI's publicly
> released, machine-readable data accessible over MCP.

## Why

Compliance work breaks when an AI hallucinates requirements that never existed.
This server removes that failure mode:

- **Correct.** Every requirement is traceable to a real BSI ID, not to training data.
- **Current.** Data is loaded from a pinned commit of the official BSI repository; updates flow to every agent without prompt changes.
- **Token-efficient.** Agents fetch only the few requirements a step needs, not the whole compendium.
- **Reusable.** One implementation, usable by any MCP client (your own audit pipeline, Claude Code, ISMS tools).

> **Note on language:** The technical surface (tool names, parameters, errors)
> is English. The **content** this server returns, the BSI requirement texts,
> stays in the German original and is never translated. Translating security
> requirements would lose the precision compliance work depends on.

## Quick start

Add the server to Claude Code:

```bash
claude mcp add grundschutz -- uvx grundschutz-mcp
```

Or configure it manually in your MCP client (STDIO transport):

```json
{
  "mcpServers": {
    "grundschutz": {
      "command": "uvx",
      "args": ["grundschutz-mcp"]
    }
  }
}
```

## Tools

| Tool | Purpose |
| --- | --- |
| `list_modules` | List all modules (Bausteine) with requirement counts — the entry point for exploring the catalog. |
| `list_requirements_by_module` | List the requirements in a given module. |
| `get_requirement_by_id` | Fetch a single requirement or practice by its ID. |
| `search_requirements` | Full-text search across requirement titles, texts, and tags. |
| `get_mapping` | Internal cross-references between requirements (`related` or `required`). |
| `get_catalog_metadata` | Catalog version, source commit, and license info. |

Each requirement carries its German `text` and `guidance`, its module, a
`security_level` (`normal-SdT` / `erhöht`), an `effort_level` (0–5), tags, and
its `related` / `required` cross-references. Requirement texts are the original
German wording from the BSI source.

## Usage examples

Once the server is connected, an agent answers questions by calling these tools.
Every answer is the exact BSI wording, traceable to the pinned source — no
guessing from training data. (Examples below are illustrative snapshots from the
pinned BSI version; run `get_catalog_metadata` for the live state.)

**Explore the catalogue**

> *"Which modules does Grundschutz++ cover?"* → `list_modules`
> → e.g. `ARCH.2` — Netzdesign (6 requirements), `GC.1` — Grundlagen (2), … one
> `ModuleSummary` per Baustein.

**Fetch a specific requirement**

> *"What does GC.1.1 require?"* → `get_requirement_by_id("GC.1.1")`
> → *"Governance und Compliance MUSS Verfahren und Regelungen zur Errichtung und
> Aufrechterhaltung eines ISMS nach BSI Grundschutz++ verankern."*
> (`security_level: normal-SdT`, `effort_level: 0`), plus its German `guidance`.

**Work through a module**

> *"List the requirements in GC.2."* → `list_requirements_by_module("GC.2")`
> → `GC.2.1` Festlegung des externen Kontextes, `GC.2.2` Festlegung des internen
> Kontextes — each with its security level and effort score for prioritisation.

**Search the content**

> *"What does Grundschutz say about Verschlüsselung?"* → `search_requirements("Verschlüsselung")`
> → matches such as `DLS.2.2` Transportverschlüsselung, `DLS.2.3`
> Vollverschlüsselung, `SENS.2.3` Verschlüsselung und Signatur. Searches titles,
> texts, and tags.

**Follow cross-references**

> *"What is related to GC.2.1?"* → `get_mapping("related")`
> → `GC.2.1 → GC.2.2`. Use `get_mapping("required")` for prerequisite
> requirements.

**Check provenance**

> *"How current is the data, and where is it from?"* → `get_catalog_metadata`
> → the requirement count, BSI source repository, the exact pinned commit, and
> the data license (CC BY-SA 4.0).

## Data source and license

- **Source:** [`BSI-Bund/Stand-der-Technik-Bibliothek`](https://github.com/BSI-Bund/Stand-der-Technik-Bibliothek), pinned to a specific commit.
- **Format:** OSCAL (a NIST standard), serialized as JSON.
- **Data license:** the BSI data is licensed **CC BY-SA 4.0**. This server loads it at runtime and passes it through unmodified, so the BSI's attribution and share-alike terms apply to the data. See [NOTICE](./NOTICE).
- **Code license:** the server code is **Apache 2.0**. See [LICENSE](./LICENSE).

## Design notes

The server does not bind its tools directly to the raw OSCAL structure. A single
mapping layer translates OSCAL into a small internal model; the tools work only
against that model. When the BSI changes its format, only the mapper changes,
not the tools. A CI schema test surfaces format drift loudly instead of
returning silently wrong data, and a periodic drift monitor reports when the
upstream BSI data has moved beyond the pinned commit.

## Security

This is a security-adjacent tool, so supply-chain integrity matters. Releases
are versioned (SemVer) and signed; dependencies are pinned. To report a
vulnerability, see [SECURITY.md](./SECURITY.md).

## Maintainer

Maintained by Samuel Blickle, who advises organizations on information security
and compliance ([samuelblickle.de](https://samuelblickle.de)). This is an
independent open-source project (see the disclaimer above). Contributions are
welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

Code under Apache 2.0. BSI data under CC BY-SA 4.0 (attribution in NOTICE).
