"""Runtime loader: fetch the pinned OSCAL data and map it into the model.

Data is loaded from the pinned BSI commit and passed through unmodified, so the
CC BY-SA 4.0 share-alike terms do not extend to this code. No transformed data
artifact is shipped with the package.

This module is OSCAL-ignorant by design (Invariant 1): it performs IO only and
delegates all knowledge of the BSI/OSCAL shape to the mapper.
"""

from __future__ import annotations

import json

import httpx

from . import config
from .mapper import OscalMappingError, map_catalog
from .model import Catalog

# The compendium is ~4MB; this 50MB cap leaves generous headroom while bounding
# memory against a pathological or compromised upstream body. Pure size guard:
# the bytes that pass are handed to the mapper unchanged (Invariant 5).
_MAX_COMPENDIUM_BYTES = 50 * 1024 * 1024


async def load_catalog() -> Catalog:
    """Fetch the pinned compendium and return an indexed Catalog.

    The download is streamed under a byte cap so a pathological upstream body
    fails loudly instead of being read into memory wholesale (Invariant 6).
    Redirects are not followed: the pinned source is a single fixed host, and a
    redirect to a foreign host would silently break that trust boundary.
    """
    url = config.compendium_url()
    async with (
        httpx.AsyncClient(timeout=30, follow_redirects=False) as client,
        client.stream("GET", url) as resp,
    ):
        resp.raise_for_status()
        declared = resp.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > _MAX_COMPENDIUM_BYTES:
            raise OscalMappingError(
                f"compendium content-length {declared} exceeds cap {_MAX_COMPENDIUM_BYTES}",
                path="<download>",
            )
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes():
            total += len(chunk)
            if total > _MAX_COMPENDIUM_BYTES:
                raise OscalMappingError(
                    f"compendium download exceeds cap {_MAX_COMPENDIUM_BYTES} bytes",
                    path="<download>",
                )
            chunks.append(chunk)
    raw = b"".join(chunks)
    return map_catalog(json.loads(raw), commit=config.BSI_PINNED_COMMIT, repo=config.BSI_REPO)
