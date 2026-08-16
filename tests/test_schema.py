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


async def _fetch_raw_compendium() -> dict[str, Any]:
    """Fetch and parse the pinned compendium as raw JSON (no mapping)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(compendium_url())
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())


def _collect_upstream_controls(raw: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Walk raw OSCAL groups/controls, return {control id: {text, guidance}}.

    Recurses into BOTH `group["groups"]` and `control["controls"]` -- OSCAL
    nests requirements under requirements, and the BSI catalog uses that
    heavily (348 of ~1000 requirements at the pinned commit). This walk is
    written directly against raw OSCAL on purpose: this file is on the
    OSCAL-allowed list (see enforce_layering.py), specifically so a drift test
    here does not depend on the mapper's own recursion being correct -- a test
    that walked the model to check the model's own walk would be circular.

    Shared by every test in this module that needs the upstream id/prose
    universe, so the recursion is written and gets it right exactly once.
    """
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
    return upstream


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

    # Loose volume floor as a second signal, well below the actual count at the
    # pinned commit so ordinary upstream churn does not trip it. Recalibrated
    # after the control-nesting fix (`_walk_control` now recurses into
    # `control["controls"]`, not just `group["groups"]`): the catalog now
    # yields 1000 requirements (verified against commit 47de2824), not the old
    # 652 that this floor was originally sized under -- 500 sat at ~77% of 652,
    # so 800 keeps a comparable ~80% margin under the new count rather than
    # reusing a constant sized for a corpus this fix doubled in effective size.
    assert len(requirements) >= 800, f"only {len(requirements)} requirements — truncated?"
    assert catalog.metadata.requirement_count == len(requirements)

    # Guard against "green but hollow" across the WHOLE catalog, not one sample:
    # a single well-formed control says nothing about the other 999.
    for req in requirements:
        where = f"requirement {req.id!r}"
        assert req.id, "requirement without an id"
        assert req.text.strip(), f"{where} has empty text"
        # guidance is NOT checked here: `test_empty_guidance_count_stays_small`
        # bounds the documented carve-out (2 of ~1000 legitimately carry no
        # guidance part) as its own, more precise assertion. Asserting
        # non-empty guidance for every requirement here would fail on exactly
        # the requirements the fix now correctly reads.
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
    plain equality, over ~1790 prose fields at the pinned commit (recalibrated
    after the control-nesting fix -- see the floor below).

    What this does and does not catch, measured rather than assumed: a
    truncation, a prefix, an insertion or a replacement shows up on every field.
    A `.strip()` or a CRLF normalisation shows up on none — not because the test
    is weak, but because the pinned prose carries no leading or trailing
    whitespace and no newlines, so those transformations are no-ops on this data.
    A transformation that is a no-op today can become visible after a re-pin;
    this test will catch it then, not before.

    Reads raw OSCAL on purpose (via `_collect_upstream_controls`): Invariant 1
    confines that to the mapper for production code, and a drift test that went
    through the mapper to check the mapper would be circular.
    """
    raw = await _fetch_raw_compendium()
    upstream = _collect_upstream_controls(raw)

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

    # If the subset ever collapses, the assertions above pass vacuously. Floor
    # recalibrated after the control-nesting fix: the old ">800" sat at ~68% of
    # the old ~1170-field subset it was measured against (which itself only
    # covered the 652 requirements the mapper read before the fix). The fixed
    # mapper now yields ~1790 comparable fields (verified against commit
    # 47de2824) -- reusing "800" here would leave a margin so wide it stopped
    # meaning anything, so this keeps a comparable ~67% margin under the actual
    # count instead.
    assert compared > 1200, f"only {compared} prose fields compared — subset too small"


@pytest.mark.network
async def test_model_ids_equal_upstream_control_ids() -> None:
    """The converse direction: nothing upstream is missing from the model.

    Every other test in this module (and its predecessor before this test was
    added) only checked model ⊆ upstream: that every requirement the mapper
    produced corresponds to something real upstream. That direction is
    trivially true of a mapper that reads a subset correctly and blind to one
    that reads too LITTLE -- which is exactly what happened. `_walk_controls`
    recursed into `group["groups"]` but never into `control["controls"]`, so
    the model silently held only 652 of the ~1000 real requirements, and every
    one of the 348 missing ones was invisible to a subset check: the 652 that
    *were* read all mapped cleanly, so the suite stayed green while a third of
    the catalog vanished unnoticed. Only the converse -- upstream ⊆ model, i.e.
    upstream == model -- would have caught it on day one.
    """
    raw = await _fetch_raw_compendium()
    upstream_ids = set(_collect_upstream_controls(raw))

    catalog = await load_catalog()
    model_ids = {r.id for r in catalog.all()}

    missing_from_model = upstream_ids - model_ids
    unexpected_in_model = model_ids - upstream_ids
    assert not missing_from_model, (
        f"{len(missing_from_model)} upstream control ids never made it into the "
        f"model (e.g. {sorted(missing_from_model)[:10]}) — the mapper is silently "
        "dropping requirements again"
    )
    assert not unexpected_in_model, (
        f"{len(unexpected_in_model)} model ids do not correspond to any upstream "
        f"control (e.g. {sorted(unexpected_in_model)[:10]})"
    )
    assert upstream_ids == model_ids


@pytest.mark.network
async def test_empty_guidance_count_stays_small() -> None:
    """Bounded regression on the guidance carve-out (`_extract_part_prose`'s
    `required=False` for the 'guidance' part only).

    Today exactly 2 of ~1000 requirements (REA.2.6.1, REA.2.6.2.1) carry a
    statement and no guidance part at all, verified against the whole catalog.
    That is a narrow, deliberate exception to Invariant 6's fail-loudly default,
    not a general assumption that empty guidance is fine. Headroom to 10 tolerates
    ordinary upstream churn (a few more requirements losing their guidance part);
    a MASS appearance of empty guidance -- e.g. upstream restructuring guidance
    into a different part name or dropping it catalog-wide -- is a real format
    change and must fail loudly here rather than let the exception widen far
    enough to become blind to that change.
    """
    catalog = await load_catalog()
    empty_guidance = [r.id for r in catalog.all() if r.guidance == ""]
    assert len(empty_guidance) <= 10, (
        f"{len(empty_guidance)} requirements have empty guidance (expected ~2: "
        f"{empty_guidance[:10]}) — review whether the guidance carve-out in "
        "_extract_part_prose still fits the data, or upstream changed shape"
    )
