---
description: Run every gate that must pass before tagging a release.
---

Run all release gates and report a single GO / NO-GO. Do not fix issues here;
report them. NO-GO if any gate fails.

1. No unresolved verification placeholders:
   grep for REPLACE_WITH and TODO in config.py and mapper.py. Any hit -> NO-GO.
2. Lint + format: `uv run ruff check . && uv run ruff format --check .`
3. Types: `uv run pyright` (strict, zero errors)
4. Offline tests: `uv run pytest -m "not network"`
5. Drift/schema test: `uv run pytest -m network`
6. License hygiene: LICENSE contains the full canonical Apache 2.0 text (not the
   placeholder header); NOTICE present with BSI CC BY-SA 4.0 attribution.
7. Supply chain: dependencies pinned; GitHub Actions pinned by SHA.
8. Invariant gate: architecture-guardian returns GO on the release diff.

Output a checklist with PASS/FAIL per item and the overall verdict.
