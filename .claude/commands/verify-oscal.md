---
description: Resolve the open OSCAL verification points against the real BSI data.
---

Drive the resolution of the TODO verification points. Do not invent field paths.

1. Read the BSI repo documentation on the OSCAL structure:
   https://github.com/BSI-Bund/Stand-der-Technik-Bibliothek/blob/main/Dokumentation/OSCAL.md
   and inspect the actual compendium file in the repo.
2. Determine the real values for:
   - config.py: BSI_PINNED_COMMIT (a concrete, current commit SHA),
     BSI_COMPENDIUM_PATH (the actual file path in the repo).
   - mapper.py: the true OSCAL field paths for id, title, statement prose,
     protection-goal props, and ISO 27001 links.
3. Update config.py and mapper.py accordingly. Only mapper.py changes for field
   paths; tools and model stay untouched unless a genuinely new field is needed.
4. Run `uv run pytest -m network` to confirm the pinned data maps cleanly.
5. Hand off to security-reviewer (loader/mapper changed) and architecture-guardian.

Report exactly which assumptions in the scaffold were correct and which you had
to correct, so the mapper's assumptions are documented.
