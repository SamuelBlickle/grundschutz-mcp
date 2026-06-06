# grundschutz-mcp

[![License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](./LICENSE)
[![Data: CC BY-SA 4.0](https://img.shields.io/badge/Data-CC%20BY--SA%204.0-lightgrey.svg)](./NOTICE)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](#)
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
| `get_requirement_by_id` | Fetch a single requirement or practice by its ID. |
| `list_requirements_by_module` | List requirements for a given Baustein/practice. |
| `search_requirements` | Full-text search across requirements. |
| `get_mapping` | Mapping to ISO 27001:2022, where present in the data. |
| `get_catalog_metadata` | Version, source commit, and license info. |

Returned requirement texts are the original German wording from the BSI source.

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

## Who's behind this

Built and maintained by Samuel Blickle, working in Informationssicherheit
(CISO, ISMS, BSI IT-Grundschutz, NIS-2). More at
[samuelblickle.de](https://samuelblickle.de). Contributions welcome, see
[CONTRIBUTING.md](./CONTRIBUTING.md).

## License

Code under Apache 2.0. BSI data under CC BY-SA 4.0 (attribution in NOTICE).
