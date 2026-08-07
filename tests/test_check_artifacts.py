"""Regression tests for the artifact matcher in scripts/check_artifacts.py.

Three versions of that control shipped and were defeated in review, each by a
different way of writing the same prose. None of the defeats would have survived
a test, because each is a one-line property: reproduced prose must be detected
however it is laid out. That property is what these tests pin.

Offline and synthetic on purpose -- the point is the matcher's behaviour under
reformatting, not the real catalog, which the network drift test covers.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import textwrap
from collections.abc import Callable
from types import ModuleType

import pytest


def _load() -> ModuleType:
    """Import the script by path: scripts/ is not a package."""
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "check_artifacts.py"
    spec = importlib.util.spec_from_file_location("check_artifacts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_artifacts"] = module
    spec.loader.exec_module(module)
    return module


check = _load()

# Long enough to yield several n-grams, and shaped like real requirement prose.
PROSE = (
    "Die Institution MUSS Verfahren und Regelungen zur Errichtung und "
    "Aufrechterhaltung eines Informationssicherheitsmanagementsystems "
    "verankern und deren Wirksamkeit regelmäßig überprüfen sowie die "
    "Ergebnisse nachvollziehbar dokumentieren und der Leitung berichten."
)


def _needles() -> set[str]:
    return check.ngrams(PROSE)


def test_verbatim_prose_is_detected() -> None:
    assert check.ngrams(PROSE) & _needles()


def _hard_wrap(text: str) -> str:
    return textwrap.fill(text, 79)


def _blockquote(text: str) -> str:
    """The shape that defeated v3 — and the one README.md itself uses."""
    return textwrap.fill(text, 72, initial_indent="> ", subsequent_indent="> ")


def _bullets(text: str) -> str:
    return textwrap.fill(text, 60, initial_indent="- ", subsequent_indent="  ")


def _numbered(text: str) -> str:
    """Counters between the words — this is what forced letters-only tokens."""
    return "\n".join(f"{i}| {line}" for i, line in enumerate(textwrap.wrap(text, 50)))


def _table(text: str) -> str:
    return "| " + " | ".join(textwrap.wrap(text, 40)) + " |"


def _crlf(text: str) -> str:
    return text.replace(" ", "\r\n")


def _offset(text: str) -> str:
    """Dropping one character shifted every prefix needle in v2."""
    return text[1:]


def _double_spaced(text: str) -> str:
    return text.replace(" ", "  ")


RENDERERS: dict[str, Callable[[str], str]] = {
    "hard wrap": _hard_wrap,
    "blockquote": _blockquote,
    "bullet list": _bullets,
    "numbered lines": _numbered,
    "table row": _table,
    "crlf": _crlf,
    "offset by one char": _offset,
    "double spaced": _double_spaced,
}


@pytest.mark.parametrize("label", sorted(RENDERERS))
def test_reformatted_prose_is_still_detected(label: str) -> None:
    """Matching must survive any layout that leaves the words in order.

    Character-level matching failed several of these; word-level n-grams do not
    care what sits between the words.
    """
    rendered = RENDERERS[label](PROSE)
    needles = _needles()
    # A fraction, not "non-empty": one surviving n-gram would let 99.9% evasion
    # pass, which is how the earlier assertion could not tell full detection from
    # near-total escape.
    recovered = len(check.ngrams(rendered) & needles) / len(needles)
    assert recovered >= 0.9, f"{label} recovered only {recovered:.1%} of needles"


def test_unrelated_german_prose_does_not_match() -> None:
    """The needle length has to be long enough not to collide with ordinary text."""
    unrelated = (
        "Dieses Projekt ist ein unabhängiges Open-Source-Vorhaben und steht in "
        "keiner Verbindung zum Bundesamt für Sicherheit in der Informationstechnik."
    )
    assert not (check.ngrams(unrelated) & _needles())


def test_short_text_yields_no_needles() -> None:
    """Documented limit: fewer than NGRAM words cannot be matched this way."""
    assert check.ngrams("Errichtung und Aufrechterhaltung eines ISMS") == set()


def test_escape_neutralises_workflow_commands() -> None:
    """Member names reach an Actions log; a newline must not forge a command."""
    assert "\n" not in check.escape("evil\n::error::forged")


def test_canonical_strips_only_the_version_bearing_root() -> None:
    """The wheel and the sdist have different roots, and conflating them is a bug.

    Removing the first path component blindly turns the wheel's
    `grundschutz_mcp/README.md` into `README.md`, handing it the excerpt budget
    meant for the real README. That shipped in an earlier version.
    """
    assert check.canonical(".tar.gz", "grundschutz_mcp-1.0.0/README.md") == "README.md"
    assert check.canonical(".tar.gz", "grundschutz_mcp-1.0.0/docs/adr/README.md") == (
        "docs/adr/README.md"
    )
    assert check.canonical(".whl", "grundschutz_mcp-1.0.0.dist-info/METADATA") == (
        "<dist-info>/METADATA"
    )
    # Must NOT become a bare "README.md" and inherit the budget.
    assert check.canonical(".whl", "grundschutz_mcp/README.md") == "grundschutz_mcp/README.md"


def test_excerpt_budget_keys_are_canonical_paths() -> None:
    """A budget key that is a bare basename would follow the filename around."""
    for key in check.EXCERPT_BUDGET:
        assert key in {"README.md", "PKG-INFO", "<dist-info>/METADATA"}, key
