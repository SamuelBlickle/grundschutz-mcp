# 0007. Build on Python and the official MCP SDK

- Status: accepted
- Date: 2026-06-06

## Context and problem statement
We need a language and framework for an MCP server whose core work is parsing
OSCAL and serving it as MCP tools. The choice should minimise bespoke parsing,
maximise maintainability, and minimise supply-chain surface for a public
security-adjacent tool.

## Considered options
- TypeScript with the MCP TypeScript SDK.
- Python with the official MCP SDK (FastMCP).

## Decision
Python 3.11+, the official mcp SDK (FastMCP), Pydantic v2 for the model and
validation, httpx for loading, uv for packaging, Ruff/Pyright/Pytest for quality.

## Rationale
The MCP SDKs are comparable, but the OSCAL tooling ecosystem is more mature in
Python, reducing bespoke parsing. Pydantic fits the projection model and gives
loud validation at the mapper boundary for free. The whole stack is mainstream
and boring by design: every extra exotic dependency is attack surface and
maintenance risk for a public tool.

## Consequences
- Low parsing effort, strong validation, familiar tooling.
- Ties the project to the Python MCP SDK's evolution.
- Reproducible, pinned dependencies; quality gates in CI.

## Revisit when
The OSCAL or MCP ecosystem shifts decisively, or a hard constraint requires
another runtime.
