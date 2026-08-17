"""Static configuration: the pinned upstream data source.

The BSI repository is a work in progress without releases, so we pin a concrete
commit. Bumping this value is a deliberate, tested action (see the update
strategy in the project briefing), never an implicit moving target.
"""

from __future__ import annotations

# Pinned commit of BSI-Bund/Stand-der-Technik-Bibliothek.
# HEAD of `main` as of 2026-08-13, verified via /verify-oscal on 2026-08-16.
BSI_REPO = "BSI-Bund/Stand-der-Technik-Bibliothek"
BSI_PINNED_COMMIT = "80694713a7a430d12eb2099893de23ad8bb6f780"

# Path to the Grundschutz++ compendium (OSCAL/JSON) inside the repo.
# Verified against the real repo tree on 2026-08-16 (note the literal "++").
#
# Upstream moved this in 7ea20849 ("Migrate public library to layer-based
# structure", 2026-07-27): Anwenderkataloge/ became control_layer/ and the
# resolved artifact gained the "-resolved_catalog" suffix, with the source
# catalogs and the profile now under control_layer/Grundschutz++/sources/.
# The path was read off the tree, not off documentation/OSCAL.md -- that file
# is a general OSCAL FAQ, documents none of the BSI-specific field paths, and
# still links to a third variant (Kompendien/...) that 404s.
BSI_COMPENDIUM_PATH = "control_layer/Grundschutz++/Grundschutz++-resolved_catalog.json"

# Raw content base. Pinning by commit (not branch) makes loads reproducible.
RAW_BASE = "https://raw.githubusercontent.com"


def compendium_url() -> str:
    """Return the raw URL of the pinned compendium file."""
    return f"{RAW_BASE}/{BSI_REPO}/{BSI_PINNED_COMMIT}/{BSI_COMPENDIUM_PATH}"
