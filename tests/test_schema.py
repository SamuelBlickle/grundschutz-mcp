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
    requirements = catalog.all()

    # Identity, not just well-formedness. The pinned artifact sits next to its
    # own source catalogs in control_layer/Grundschutz++/sources/, and those map
    # cleanly too -- the Kernel catalog yields 596 requirements, so a mistyped
    # re-pin would sail through a "> 0" check and even through a count floor.
    #
    # What identifies the resolved compendium is that it is the MERGE of the two
    # layers: the Kernel catalog carries no method-layer modules and the Methodik
    # catalog carries no technical ones. Requiring both is a structural check
    # that no single source artifact can satisfy.
    prefixes = {summary.module.split(".")[0] for summary in catalog.modules()}
    assert {"GC", "RISK", "UMS"} <= prefixes, (
        f"method-layer modules missing ({sorted(prefixes)}) — pinned a source catalog "
        "instead of the resolved compendium?"
    )
    assert {"BER", "KONF", "GEB"} <= prefixes, (
        f"technical modules missing ({sorted(prefixes)}) — pinned the Methodik catalog?"
    )

    # Loose volume floor as a second signal, well below the 652/140 at the
    # pinned commit so ordinary upstream churn does not trip it.
    assert len(requirements) >= 500, f"only {len(requirements)} requirements — truncated?"
    assert catalog.metadata.requirement_count == len(requirements)

    # Guard against "green but hollow" across the WHOLE catalog, not one sample:
    # a single well-formed control says nothing about the other 651.
    for req in requirements:
        where = f"requirement {req.id!r}"
        assert req.id, "requirement without an id"
        assert req.text.strip(), f"{where} has empty text"
        assert req.guidance.strip(), f"{where} has empty guidance"
        assert req.module, f"{where} has no module"
        assert req.security_level in {"normal-SdT", "erhöht"}, (
            f"{where} has unexpected security_level {req.security_level!r}"
        )
        assert 0 <= req.effort_level <= 5, (
            f"{where} has effort_level {req.effort_level} outside 0..5"
        )

    # Ids must be unique: the tools index by id, so a duplicate would make
    # get_requirement_by_id silently return whichever won the index.
    ids = [r.id for r in requirements]
    assert len(ids) == len(set(ids)), "duplicate requirement ids in the pinned data"
