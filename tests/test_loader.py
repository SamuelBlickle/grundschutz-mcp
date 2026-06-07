"""Offline tests for the loader-hardening (HANDOFF-029/-030).

`load_catalog()` performs the only network IO in the package. These tests run
fully offline and deterministically by injecting an `httpx.MockTransport` into
the AsyncClient the loader builds, so the REAL loader code path (streaming,
the byte cap, the content-length early-reject, and `follow_redirects=False`)
is exercised — none of that logic is mocked away.

Designed from the SPEC (HANDOFF-029-return / -030), not the loader internals:
the loader streams under `_MAX_COMPENDIUM_BYTES`, rejects an over-cap
content-length BEFORE reading the body, accumulates via `aiter_bytes` and
rejects on overflow, does NOT follow redirects, and otherwise parses the body
and hands it to `map_catalog` unchanged (Invariant 5).

No `network` marker: these never touch the real network.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from grundschutz_mcp import config, loader
from grundschutz_mcp.mapper import OscalMappingError
from grundschutz_mcp.model import Catalog

Handler = Callable[[httpx.Request], httpx.Response]


# ---------------------------------------------------------------------------
# A minimal but VALID OSCAL body that survives map_catalog.
#
# map_catalog requires (see test_mapper.py): a top-level catalog with groups,
# each control carrying id + title + non-empty statement/guidance parts + a
# sec_level prop (normal-SdT|erhöht) and an effort_level prop ("0".."5").
# This body maps to exactly one Requirement.
# ---------------------------------------------------------------------------


def _valid_oscal_body() -> dict[str, object]:
    return {
        "metadata": {"version": "2024.1"},
        "groups": [
            {
                "id": "ORP.1",
                "title": "Organisation",
                "controls": [
                    {
                        "id": "ORP.1.A1",
                        "title": "Festlegung von Verantwortlichkeiten",
                        "parts": [
                            {
                                "name": "statement",
                                "prose": "Verantwortlichkeiten MÜSSEN festgelegt werden.",
                            },
                            {"name": "guidance", "prose": "Hinweise zur Umsetzung."},
                        ],
                        "props": [
                            {"name": "sec_level", "value": "normal-SdT"},
                            {"name": "effort_level", "value": "0"},
                        ],
                    }
                ],
            }
        ],
    }


def _valid_oscal_bytes() -> bytes:
    return json.dumps(_valid_oscal_body()).encode("utf-8")


# ---------------------------------------------------------------------------
# MockTransport injection.
#
# The loader builds `httpx.AsyncClient(timeout=30, follow_redirects=False)` with
# no transport. We monkeypatch `httpx.AsyncClient` with a thin factory that adds
# `transport=httpx.MockTransport(handler)` while passing every loader-supplied
# argument (notably follow_redirects=False) straight through to the real client.
# The genuine stream/cap/redirect logic therefore runs unchanged against a
# scripted response — we mock the wire, not the loader.
# ---------------------------------------------------------------------------


def _install(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    """Point the loader's AsyncClient at a MockTransport, preserving its kwargs.

    The factory's signature mirrors exactly what `loader.load_catalog` passes
    (`timeout`, `follow_redirects`), so the loader's `follow_redirects=False`
    flows through to the real client untouched and no type suppression is
    needed to forward arguments.
    """

    # Capture the genuine class BEFORE patching: the loader resolves
    # `httpx.AsyncClient` through the same module object we patch, so the
    # factory must call the real constructor, not itself.
    real_async_client = httpx.AsyncClient

    def factory(*, timeout: float, follow_redirects: bool) -> httpx.AsyncClient:
        return real_async_client(
            timeout=timeout,
            follow_redirects=follow_redirects,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(loader.httpx, "AsyncClient", factory)


# ---------------------------------------------------------------------------
# (a) content-length > cap -> reject BEFORE reading the body
# ---------------------------------------------------------------------------


async def test_content_length_over_cap_rejects_without_reading_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(loader, "_MAX_COMPENDIUM_BYTES", 500)
    streamed = {"bytes": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        # Declare a length far above the cap, but ship a tiny VALID body. If the
        # loader read+parsed the body it would succeed; instead it must reject on
        # the declared content-length first. The body content is never the cause.
        body = _valid_oscal_bytes()
        streamed["bytes"] = len(body)
        return httpx.Response(
            200,
            headers={"content-length": "100000"},
            content=body,
        )

    _install(monkeypatch, handler)
    with pytest.raises(OscalMappingError) as exc:
        await loader.load_catalog()
    assert exc.value.path == "<download>"
    assert "content-length" in str(exc.value)
    # The declared length, not the actual body, triggered the reject: the real
    # (valid, small) body would otherwise have produced a Catalog.
    assert streamed["bytes"] < 100000


# ---------------------------------------------------------------------------
# (b) body > cap with no / small content-length -> aiter_bytes overflow reject
# ---------------------------------------------------------------------------


async def test_oversize_body_without_content_length_rejects_via_accumulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(loader, "_MAX_COMPENDIUM_BYTES", 200)

    def handler(_request: httpx.Request) -> httpx.Response:
        # 1000 bytes, far over the 200-byte cap. httpx serves this in chunks via
        # aiter_bytes; the loader's running total must trip the cap. No explicit
        # content-length header is set here (httpx may compute one for a bytes
        # body, but the accumulation guard is the backstop being exercised).
        return httpx.Response(200, content=b"x" * 1000)

    _install(monkeypatch, handler)
    with pytest.raises(OscalMappingError) as exc:
        await loader.load_catalog()
    assert exc.value.path == "<download>"


async def test_oversize_body_with_small_content_length_rejects_via_accumulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # content-length present but UNDER the cap (so the early reject does not
    # fire), while the actual streamed body exceeds the cap -> accumulation must
    # catch the lie.
    monkeypatch.setattr(loader, "_MAX_COMPENDIUM_BYTES", 200)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": "10"},
            content=b"y" * 1000,
        )

    _install(monkeypatch, handler)
    with pytest.raises(OscalMappingError) as exc:
        await loader.load_catalog()
    assert exc.value.path == "<download>"


# ---------------------------------------------------------------------------
# (c) follow_redirects=False -> a 3xx to a foreign host is NOT followed
# ---------------------------------------------------------------------------


async def test_redirect_is_not_followed_and_surfaces_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(str(request.url))
        # Redirect the pinned source to a foreign host. With follow_redirects
        # left at the loader's False, the client must NOT request the target.
        return httpx.Response(302, headers={"location": "https://evil.example/payload.json"})

    _install(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError) as exc:
        await loader.load_catalog()
    # raise_for_status surfaced the 3xx; no Catalog was produced.
    assert 300 <= exc.value.response.status_code < 400
    # Exactly one request was made: the pinned URL. The foreign target was not
    # fetched (no second, evil.example request).
    assert visited == [config.compendium_url()]


# ---------------------------------------------------------------------------
# (d) happy path: small valid body < cap -> a real Catalog
# ---------------------------------------------------------------------------


async def test_happy_path_small_valid_body_returns_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_valid_oscal_bytes())

    _install(monkeypatch, handler)
    catalog = await loader.load_catalog()
    assert isinstance(catalog, Catalog)
    assert catalog.metadata.requirement_count == 1
    req = catalog.get("ORP.1.A1")
    assert req is not None
    # Provenance is the pinned commit/repo, passed through unchanged.
    assert catalog.metadata.source_commit == config.BSI_PINNED_COMMIT
    assert catalog.metadata.source_repo == config.BSI_REPO
    # Invariant 4/5: the German wording is passed through verbatim.
    assert req.text == "Verantwortlichkeiten MÜSSEN festgelegt werden."


async def test_happy_path_with_honest_content_length_under_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An accurate content-length below the cap must not trip the early reject.
    body = _valid_oscal_bytes()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": str(len(body))},
            content=body,
        )

    _install(monkeypatch, handler)
    catalog = await loader.load_catalog()
    assert catalog.metadata.requirement_count == 1


# ---------------------------------------------------------------------------
# (e) boundary: body exactly == cap is OK; cap + 1 byte fails
#
# Sized with trailing-whitespace padding, which keeps the body valid JSON while
# letting us hit an exact byte length. The cap is patched small so no 50MB body
# is ever materialised.
# ---------------------------------------------------------------------------


def _body_of_exact_size(target: int) -> bytes:
    """Return a valid-OSCAL JSON body padded with trailing spaces to `target`."""
    base = _valid_oscal_bytes()
    assert len(base) <= target, "raise the boundary cap above the minimal body size"
    return base + b" " * (target - len(base))


async def test_body_exactly_at_cap_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    cap = 600
    monkeypatch.setattr(loader, "_MAX_COMPENDIUM_BYTES", cap)
    body = _body_of_exact_size(cap)
    assert len(body) == cap

    def handler(_request: httpx.Request) -> httpx.Response:
        # No content-length header -> the boundary is exercised on the
        # accumulation path (total == cap must NOT trip the strict '>' check).
        return httpx.Response(200, content=body)

    _install(monkeypatch, handler)
    catalog = await loader.load_catalog()
    assert catalog.metadata.requirement_count == 1


async def test_body_one_byte_over_cap_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    cap = 600
    monkeypatch.setattr(loader, "_MAX_COMPENDIUM_BYTES", cap)
    body = _body_of_exact_size(cap + 1)
    assert len(body) == cap + 1

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    _install(monkeypatch, handler)
    with pytest.raises(OscalMappingError) as exc:
        await loader.load_catalog()
    assert exc.value.path == "<download>"
