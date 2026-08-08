"""Runtime loader: fetch the pinned OSCAL data and map it into the model.

Data is loaded from the pinned BSI commit. The only transformation to the
requirement prose is the OSCAL parameter substitution in mapper.py (ADR-0009);
structured metadata is normalised for query. No transformed data artifact is
shipped with the package, which is what keeps the CC BY-SA 4.0 share-alike terms
off this code. See NOTICE.

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
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as exc:
        # The mapper's depth cap bounds its own walk, but a document nested
        # deeply enough exhausts the interpreter here first, before the mapper
        # ever runs. Converting it keeps the promise that a malformed compendium
        # surfaces as an OscalMappingError with a path (Invariant 6) rather than
        # as an interpreter-level error the caller cannot interpret.
        raise OscalMappingError(
            f"compendium is not parseable JSON: {type(exc).__name__}", path="<download>"
        ) from None
    return map_catalog(parsed, commit=config.BSI_PINNED_COMMIT, repo=config.BSI_REPO)
