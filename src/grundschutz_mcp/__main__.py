"""Entry point: run the MCP server over STDIO."""

from __future__ import annotations

import logging
import sys

from .server import mcp


def main() -> None:
    # Logs go to stderr only: stdout is the STDIO MCP JSON-RPC channel.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
