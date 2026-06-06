"""Static configuration: the pinned upstream data source.

The BSI repository is a work in progress without releases, so we pin a concrete
commit. Bumping this value is a deliberate, tested action (see the update
strategy in the project briefing), never an implicit moving target.
"""

from __future__ import annotations

# Pinned commit of BSI-Bund/Stand-der-Technik-Bibliothek.
# HEAD of `main` as of 2026-05-29, verified via /verify-oscal on 2026-06-06.
BSI_REPO = "BSI-Bund/Stand-der-Technik-Bibliothek"
BSI_PINNED_COMMIT = "b4e1ee402a94113a00978ecae3f397bc5bbce1b4"

# Path to the Grundschutz++ compendium (OSCAL/JSON) inside the repo.
# Verified against the real repo layout on 2026-06-06 (note the literal "++").
BSI_COMPENDIUM_PATH = "Anwenderkataloge/Grundschutz++/Grundschutz++-catalog.json"

# Raw content base. Pinning by commit (not branch) makes loads reproducible.
RAW_BASE = "https://raw.githubusercontent.com"


def compendium_url() -> str:
    """Return the raw URL of the pinned compendium file."""
    return f"{RAW_BASE}/{BSI_REPO}/{BSI_PINNED_COMMIT}/{BSI_COMPENDIUM_PATH}"
