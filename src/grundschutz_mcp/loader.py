"""Runtime loader: fetch the pinned OSCAL data and map it into the model.

Data is loaded from the pinned BSI commit and passed through unmodified, so the
CC BY-SA 4.0 share-alike terms do not extend to this code. No transformed data
artifact is shipped with the package.

This module is OSCAL-ignorant by design (Invariant 1): it performs IO only and
delegates all knowledge of the BSI/OSCAL shape to the mapper.
"""

from __future__ import annotations

import httpx

from . import config
from .mapper import map_catalog
from .model import Catalog


async def load_catalog() -> Catalog:
    """Fetch the pinned compendium and return an indexed Catalog."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(config.compendium_url())
        resp.raise_for_status()
        return map_catalog(resp.json(), commit=config.BSI_PINNED_COMMIT, repo=config.BSI_REPO)
