#!/usr/bin/env python3
"""PreToolUse hook: enforce the architecture invariants on Edit/Write/MultiEdit.

Reads the Claude Code hook event from stdin. Denies edits that would violate the
binding invariants in CLAUDE.md, so a layering breach never reaches disk.

Invariants enforced here:
  1. Only mapper.py may navigate raw OSCAL structures.
  3. server.py / loader.py tool logic must not touch raw dict keys.
  5. No vendored/transformed BSI data artifact inside the package.
"""

from __future__ import annotations

import json
import re
import sys


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def allow() -> None:
    print("{}")
    sys.exit(0)


# Heuristic: raw OSCAL navigation. These keys belong to the BSI/OSCAL shape and
# must appear only in mapper.py (and tests).
OSCAL_KEYS = ("controls", "parts", "props", "groups", "statement", "prose", "links")
OSCAL_NAV = re.compile(
    r"""\[\s*["'](?:%s)["']\s*\]|\.get\(\s*["'](?:%s)["']"""
    % ("|".join(OSCAL_KEYS), "|".join(OSCAL_KEYS))
)

# Files that are allowed to know the OSCAL format.
OSCAL_ALLOWED = ("src/grundschutz_mcp/mapper.py", "tests/test_mapper.py", "tests/test_schema.py")

# No data catalogs shipped inside the package.
VENDORED_DATA = re.compile(r"src/grundschutz_mcp/.*\.(json|xml)$")


def edited_text(tool: str, inp: dict) -> str:
    if tool == "Write":
        return inp.get("content", "")
    if tool == "Edit":
        return inp.get("new_string", "")
    if tool == "MultiEdit":
        return "\n".join(e.get("new_string", "") for e in inp.get("edits", []))
    return ""


def main() -> None:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    inp = event.get("tool_input", {})
    path = inp.get("file_path", "")

    if VENDORED_DATA.search(path):
        deny(
            "Invariant 5: do not ship BSI data inside the package. Load it at "
            "runtime from the pinned commit instead (see loader.py)."
        )

    norm = path.replace("\\", "/")
    is_oscal_allowed = any(norm.endswith(p) for p in OSCAL_ALLOWED)
    if not is_oscal_allowed and norm.endswith(".py"):
        text = edited_text(tool, inp)
        if OSCAL_NAV.search(text):
            deny(
                f"Invariant 1/3: raw OSCAL navigation is not allowed in {norm}. "
                "OSCAL field access belongs in mapper.py; everything else works "
                "against the internal model (Requirement/Catalog)."
            )

    allow()


if __name__ == "__main__":
    main()
