#!/usr/bin/env python3
"""PreToolUse hook: block dangerous Bash and protect critical files.

Reads the hook event from stdin. Denies destructive commands, secret leakage,
forced history rewrites, and unsupervised publishing. This is a security-
adjacent OSS tool, so supply-chain discipline is enforced, not merely asked for.
"""

from __future__ import annotations

import json
import re
import sys

DENY_BASH = [
    r"\brm\s+-rf?\b",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-z]*f",
    r"\b(uv\s+publish|twine\s+upload|python\s+-m\s+twine)\b",  # release is a human, signed step
    r"\bcurl\s+.*\|\s*(ba)?sh",
    r"\bwget\s+.*\|\s*(ba)?sh",
    r"(AKIA|ASIA)[A-Z0-9]{16}",
    r"\bpip\s+install\b",  # use uv; keep deps pinned and reproducible
]

# Files the agent must not silently overwrite/delete.
PROTECTED = [r"(^|/)LICENSE$", r"(^|/)NOTICE$", r"(^|/)\.env$", r"(^|/)SECURITY\.md$"]


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


def main() -> None:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    inp = event.get("tool_input", {})

    if tool == "Bash":
        cmd = inp.get("command", "")
        for pat in DENY_BASH:
            if re.search(pat, cmd):
                deny(f"Blocked by policy: command matches /{pat}/. See CLAUDE.md.")

    if tool in ("Write", "Edit", "MultiEdit"):
        path = inp.get("file_path", "").replace("\\", "/")
        for pat in PROTECTED:
            if re.search(pat, path):
                deny(
                    f"{path} is protected. License/security files change only via "
                    "a deliberate, human-reviewed step."
                )

    print("{}")
    sys.exit(0)


if __name__ == "__main__":
    main()
