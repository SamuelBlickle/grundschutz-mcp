"""Schema/drift test against the pinned BSI data.

Run in CI to surface upstream format drift loudly. Marked network-dependent so
the fast unit suite stays offline; CI runs it explicitly.
"""

from __future__ import annotations

import re
from typing import Any, cast

import httpx
import pytest

from grundschutz_mcp.config import compendium_url
from grundschutz_mcp.loader import load_catalog


@pytest.mark.network
async def test_pinned_data_still_maps() -> None:
    """The pinned compendium must parse cleanly into the internal model.

    If this fails, the BSI OSCAL shape has likely drifted from what the mapper
    expects. Review upstream, adjust the mapper, bump the pinned commit.
    """
    catalog = await load_catalog()
    assert catalog.metadata.requirement_count > 0
    sample = catalog.all()[0]
    assert sample.id
    assert sample.text
    # Guard against "green but hollow": the new mandatory fields must actually
    # be populated with values in the documented ranges, not silently empty.
    assert sample.guidance
    assert sample.security_level in {"normal-SdT", "erhöht"}
    assert 0 <= sample.effort_level <= 5


@pytest.mark.network
async def test_no_oscal_parameter_placeholder_survives() -> None:
    """Invariant 5's content clause, as a check rather than a claim.

    The prose returned to clients must contain no OSCAL assembly machinery: every
    `{{ insert: param, <id> }}` span is resolved to the value the BSI defines
    (ADR-0009), and that substitution is the *only* sanctioned difference from
    upstream prose. A leaked placeholder means either the resolver missed a
    syntax variant or upstream changed the insertion form -- both make NOTICE's
    description of what this software does to the data untrue.
    """
    # Deliberately broader than the resolver's own pattern in mapper.py. Matching
    # the resolver exactly would make this test blind wherever the resolver is:
    # a syntax variant it fails to substitute would also fail to be detected.
    # This matches any insertion-looking span, so a missed variant surfaces here.
    leak = re.compile(r"\{\{\s*insert")

    catalog = await load_catalog()
    leaked = [r.id for r in catalog.all() if leak.search(r.text) or leak.search(r.guidance)]
    assert not leaked, f"unresolved OSCAL parameter placeholders in: {leaked[:10]}"


@pytest.mark.network
async def test_prose_is_byte_identical_where_no_parameter_is_inserted() -> None:
    """Invariant 5's byte-for-byte clause, on the subset where it is checkable.

    The substitution is the only sanctioned difference between upstream prose and
    what the tools return. Verifying that on controls that *contain* a
    placeholder would mean re-implementing the resolver here — which is either a
    copy of the mapper's regex, and so blind wherever the mapper is, or a second
    implementation to keep in step. Neither proves anything.

    Controls with no placeholder need no substitution, so for them the clause is
    plain equality, over ~1170 prose fields at the pinned commit.

    What this does and does not catch, measured rather than assumed: a
    truncation, a prefix, an insertion or a replacement shows up on every field.
    A `.strip()` or a CRLF normalisation shows up on none — not because the test
    is weak, but because the pinned prose carries no leading or trailing
    whitespace and no newlines, so those transformations are no-ops on this data.
    A transformation that is a no-op today can become visible after a re-pin;
    this test will catch it then, not before.

    Reads raw OSCAL on purpose: Invariant 1 confines that to the mapper for
    production code, and a drift test that went through the mapper to check the
    mapper would be circular.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(compendium_url())
        response.raise_for_status()
        raw: Any = response.json()

    upstream: dict[str, dict[str, str]] = {}

    def children(node: dict[str, Any], key: str) -> list[dict[str, Any]]:
        return cast("list[dict[str, Any]]", node.get(key, []))

    def collect(group: dict[str, Any]) -> None:
        for control in children(group, "controls"):
            parts = {
                str(part.get("name")): str(part.get("prose", ""))
                for part in children(control, "parts")
            }
            upstream[str(control["id"])] = {
                "text": parts.get("statement", ""),
                "guidance": parts.get("guidance", ""),
            }
            collect(control)
        for sub in children(group, "groups"):
            collect(sub)

    for group in children(cast("dict[str, Any]", raw["catalog"]), "groups"):
        collect(group)

    catalog = await load_catalog()
    has_placeholder = re.compile(r"\{\{\s*insert")
    compared = 0
    for req in catalog.all():
        source = upstream.get(req.id)
        assert source is not None, f"{req.id} is not in the upstream catalog"
        for field in ("text", "guidance"):
            original = source[field]
            if has_placeholder.search(original):
                continue  # substitution expected here; see the docstring
            assert getattr(req, field) == original, (
                f"{req.id}.{field} differs from upstream prose without a parameter "
                f"substitution to account for it"
            )
            compared += 1

    # If the subset ever collapses, the assertions above pass vacuously.
    assert compared > 800, f"only {compared} prose fields compared — subset too small"
