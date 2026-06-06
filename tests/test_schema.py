"""Schema/drift test against the pinned BSI data.

Run in CI to surface upstream format drift loudly. Marked network-dependent so
the fast unit suite stays offline; CI runs it explicitly.
"""

from __future__ import annotations

import pytest

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
