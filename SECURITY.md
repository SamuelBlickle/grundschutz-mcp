# Security Policy

grundschutz-mcp is a security-adjacent tool: its value rests on the integrity of
the requirement data it serves and of the supply chain that delivers it. Please
report vulnerabilities responsibly.

## Reporting

Do not open a public issue for security problems. Use GitHub's private
"Report a vulnerability" feature, or contact the maintainer via
[samuelblickle.de](https://samuelblickle.de).

## Trust model and deployment

- **Read-only, public data.** The server only reads the BSI compendium (public,
  CC BY-SA 4.0) and serves it. It performs no writes and executes no user-supplied code.
- **Local STDIO by design.** It is meant to run as a local STDIO MCP server for a
  single client. It ships no authentication because it exposes only public data
  over a local channel.
- **Do not expose it unauthenticated over a network.** If you ever place it behind
  a network transport, put authentication and authorization in front of it.
- **Constrained egress.** The only outbound call is an HTTPS GET to the pinned BSI
  source URL, assembled from constants — there are no user-controlled URLs (no SSRF surface).
- **Input validation.** Tool parameters are length-bounded and type-constrained at
  the MCP boundary.
- **Audit logging.** Each tool call logs the tool, its key parameter, and the result
  size to stderr; requirement text is never logged, and stdout (the protocol
  channel) is never used for logging.
- **Fail loudly.** Unexpected upstream data shape raises a located error rather than
  returning silently wrong data.

## Supply chain

- Runtime and development dependencies are pinned.
- CI third-party actions are pinned to commit SHAs, and the CI token runs with
  least privilege (`contents: read`).
- The BSI data source is pinned to a reviewed commit and loaded at runtime, never
  vendored — so loads are reproducible and the data license stays separate from the
  code (see [NOTICE](./NOTICE)).
- Releases follow SemVer. Published release artifacts are signed, and publishing
  is intended to use a tokenless trusted-publishing flow (PyPI OIDC) so that no
  long-lived publishing credentials exist.

## Secrets handling

- The server itself requires no secrets: it reads public data without authentication.
- Any release or publishing credentials live only in the CI provider's secret store,
  never in the repository. `.env` files, private keys, and similar material are
  git-ignored.
