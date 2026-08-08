#!/usr/bin/env python3
"""Assert the built artifacts carry no BSI content.

ADR-0011 puts the whole CC BY-SA boundary on one property: we ship nothing
derived from BSI content. This is the control that property rests on. It runs on
every pull request and again in the release workflow before provenance is
attested.

## The primary control is the manifest, not the matcher

`artifact-manifest.toml` lists the exact members of each artifact. A file that is
not listed cannot ship, whatever it contains and however it is encoded. That is
what makes this control structural rather than heuristic, and it is the lesson of
four earlier versions that all tried to detect content across an unbounded set of
files:

- v1 sized its caps against the compendium's raw 5.4 MB. Artifacts are
  compressed; the catalogue gzips to 514 KB, so a 2 MiB sdist cap admitted four
  copies of it.
- v2 matched raw bytes. `textwrap.fill(text, 79)` shipped 502 KB as "clean".
- v3 normalised whitespace and matched character shingles. A Markdown blockquote
  shipped 548 KB as "clean", because `> ` is not whitespace.
- v4 matched 12-word n-grams. That survives any reformatting, but the needle
  length had been calibrated against `guidance`, which is 97% of the corpus:
  422 of 1000 `Requirement.text` values are shorter than 12 words and produced no
  needle at all, so one requirement per file shipped 242 normative sentences
  verbatim. A zlib+base64 copy of the whole catalogue also fit under the caps.

Each fix closed one bypass and exposed the next, because detecting arbitrary
content in arbitrary files is an unbounded problem. Constraining *which files
exist* is a bounded one. With the manifest in place, BSI content can only enter
through a file that is already approved, and the checks below are adequate for
that small, known surface.

## The matcher, as a second layer

Text becomes a lowercased sequence of letter-only tokens and needles are 12-word
n-grams, so line prefixes, bullets, blockquote markers, table pipes, wrapping,
quoting and line numbers all vanish in tokenisation. Verified against each of
those; the payload that defeated v3 now matches every needle.

Known limits, stated rather than implied: runs shorter than 12 words are not
matched, and neither is prose that has been reworded, re-encoded, or broken up
with invisible characters. Those are what the manifest and the caps stand
behind, not the matcher.

## The other checks

Size caps, compressed and uncompressed, calibrated from the current artifact
size. They are a change detector -- "someone must justify this" -- not a content
control: headroom sized for legitimate growth is also headroom sized for prose.

An id and title census, aggregated across the whole artifact rather than per
member, because an index split over one file per module evades a per-file check.

Member names are checked for path traversal, and the manifest comparison runs in
both directions -- an unlisted member fails, and so does a listed one that stops
shipping, so LICENSE or NOTICE cannot quietly disappear.

Diagnostics deliberately report counts and member names, never the matched text.
Actions logs are public; printing the span would publish BSI prose from CI.
"""

from __future__ import annotations

import asyncio
import pathlib
import re
import stat
import sys
import tarfile
import tomllib
import zipfile

# Current artifacts: 21 KB / 63 KB compressed, 54 KB / 226 KB uncompressed.
MAX_COMPRESSED = {".whl": 128 * 1024, ".tar.gz": 256 * 1024}
MAX_UNCOMPRESSED = {".whl": 384 * 1024, ".tar.gz": 786 * 1024}

MANIFEST = pathlib.Path(__file__).with_name("artifact-manifest.toml")
DIST_INFO = re.compile(r"^grundschutz_mcp-[^/]+\.dist-info/")

# Letters only: digits are excluded on purpose, so injected line numbers,
# list counters and table indices cannot break a run apart. Applied to both
# sides, so the numbers inside real requirement prose drop out consistently.
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
NGRAM = 12

# 79815 needles at the current pin (1000 requirements). Recalibrated with the
# corpus: at the old floor of 45000, a regression back to the pre-fix walk --
# which read 652 of 1000 controls and still yielded ~55000 needles -- would have
# passed. A floor sized against a smaller corpus stops detecting the exact
# degradation it exists to catch.
MIN_NEEDLES = 70000

# ADR-0011 accounts for README.md quoting a requirement as an example. Keys are
# canonical member paths, not basenames: the sdist ships a second README.md under
# docs/adr, and the wheel could ship one inside the package directory -- an
# exemption that follows a filename around is not an exemption for *the* README.
# METADATA and PKG-INFO are the wheel's and the sdist's generated copies of it.
# Today's README scores 6, which is the one quoted GC.1.1 sentence.
EXCERPT_BUDGET = {"README.md": 12, "<dist-info>/METADATA": 12, "PKG-INFO": 12}

# An artifact-wide census, not per member. The catalog has 140 modules and only
# seven hold more than 15 requirements, so a docs/module/<id>.md layout would
# carry the whole index past any per-file limit. README names 6 ids and 3 titles.
MAX_DISTINCT_IDS = 15
MAX_DISTINCT_TITLES = 10
# Case-insensitive: a lowercase index is still an index.
ID_PATTERN = re.compile(r"\b[A-Za-z]{2,5}\.\d+(?:\.\d+)*\b")


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def ngrams(text: str) -> set[str]:
    tokens = words(text)
    if len(tokens) < NGRAM:
        return set()
    return {" ".join(tokens[i : i + NGRAM]) for i in range(len(tokens) - NGRAM + 1)}


def artifact_kind(path: pathlib.Path) -> str:
    return ".tar.gz" if path.name.endswith(".tar.gz") else path.suffix


def canonical(kind: str, name: str) -> str:
    """Strip the version-bearing root so a member name is comparable across builds.

    The wheel has two roots -- the package directory, which stays, and
    `grundschutz_mcp-<version>.dist-info`, which becomes `<dist-info>`. The sdist
    has one, which is dropped. Doing this per kind matters: blindly removing the
    first path component would turn the wheel's `grundschutz_mcp/README.md` into
    `README.md` and hand it the excerpt budget meant for the real README.
    """
    if kind == ".whl":
        return DIST_INFO.sub("<dist-info>/", name)
    return name.split("/", 1)[1] if "/" in name else name


def expected_members() -> dict[str, set[str]]:
    """The approved member list per artifact kind."""
    manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    return {".whl": set(manifest["wheel"]), ".tar.gz": set(manifest["sdist"])}


def escape(text: str) -> str:
    """Neutralise control characters: this output is the compliance evidence."""
    return text.encode("unicode_escape").decode("ascii")


def members(path: pathlib.Path) -> tuple[dict[str, bytes], list[str]]:
    """Member contents, plus names of members that are not plain regular files."""
    content: dict[str, bytes] = {}
    rejected: list[str] = []

    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                # Zip carries unix mode bits that installers honour, and two
                # entries may share a name -- reading by name would silently keep
                # only the last, leaving the first unscanned.
                # The high bits are unix mode only when the zip was created on a
                # unix system; otherwise there are no mode bits to read and a
                # symlink check on them would silently always be false.
                mode = info.external_attr >> 16 if info.create_system == 3 else 0
                if stat.S_ISLNK(mode) or info.filename in content:
                    rejected.append(info.filename)
                    continue
                content[info.filename] = archive.read(info)
        return content, rejected

    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile() or member.name in content:
                # A symlink carries no content but would also bypass every check
                # below, so it is rejected rather than skipped.
                rejected.append(member.name)
                continue
            handle = archive.extractfile(member)
            if handle is not None:
                content[member.name] = handle.read()
    return content, rejected


def uncompressed_size(path: pathlib.Path) -> int:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return sum(info.file_size for info in archive.infolist())
    with tarfile.open(path) as archive:
        return sum(member.size for member in archive.getmembers())


def bsi_corpus() -> tuple[set[str], set[str], set[str]]:
    """Needles, requirement ids and titles from the pinned catalog.

    Goes through the loader and the internal model, so this script never touches
    raw OSCAL (Invariant 1). Nothing is written to disk: the corpus lives in
    memory for the length of the run, the same in-memory shape ADR-0011 already
    sanctions at runtime. A fetch failure propagates -- a control that silently
    degrades to nothing is worse than no control.
    """
    from grundschutz_mcp.loader import load_catalog

    catalog = asyncio.run(load_catalog())
    needles: set[str] = set()
    ids: set[str] = set()
    titles: set[str] = set()
    for requirement in catalog.all():
        ids.add(requirement.id)
        for prose in (requirement.title, requirement.text, requirement.guidance):
            needles |= ngrams(prose)
        # Titles are mostly shorter than NGRAM words, so they need an exact
        # channel. Five tokens, not three: 225 of 364 titles are three generic
        # German words ("Anpassung des ISMS") that collide with ordinary project
        # prose, and this repo's own test file already matched two by accident.
        title_words = words(requirement.title)
        if len(title_words) >= 5:
            titles.add(" ".join(title_words))
    return needles, ids, titles


def write_manifest(artifacts: list[pathlib.Path]) -> None:
    """Regenerate artifact-manifest.toml from the current build.

    Deliberately a separate, explicit invocation rather than something the check
    does on its own: the whole value of the manifest is that adding a member is a
    reviewed diff, and a control that rewrites its own baseline has none.
    """
    header = MANIFEST.read_text(encoding="utf-8").split("wheel = [")[0].rstrip()
    lines = [header, ""]
    for key, kind in (("wheel", ".whl"), ("sdist", ".tar.gz")):
        path = next(p for p in artifacts if artifact_kind(p) == kind)
        listed = sorted(canonical(kind, name) for name in members(path)[0])
        lines.append(f"{key} = [")
        lines += [f'    "{name}",' for name in listed]
        lines += ["]", ""]
    MANIFEST.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {MANIFEST.name}")


def main() -> int:
    dist = pathlib.Path("dist")
    artifacts = sorted(p for p in dist.iterdir() if artifact_kind(p) in MAX_COMPRESSED)
    if "--update-manifest" in sys.argv:
        write_manifest(artifacts)
        return 0
    failures: list[str] = []

    if len(artifacts) != 2:
        found = ", ".join(escape(p.name) for p in artifacts)
        failures.append(f"expected one wheel and one sdist, found [{found}]")
    for stray in sorted(set(dist.iterdir()) - set(artifacts)):
        if stray.name != ".gitignore":  # uv build writes its own
            failures.append(f"unexpected file in dist/: {escape(stray.name)}")

    approved = expected_members()

    needles, ids, titles = bsi_corpus()
    print(f"{len(needles)} needles of {NGRAM} words, {len(ids)} ids, {len(titles)} titles")
    if len(needles) < MIN_NEEDLES:
        print(f"::error::only {len(needles)} needles, expected >= {MIN_NEEDLES}")
        print("  the pinned catalog looks wrong; refusing to judge the artifacts against it")
        return 1

    for path in artifacts:
        kind = artifact_kind(path)
        compressed = path.stat().st_size
        if compressed > MAX_COMPRESSED[kind]:
            # Checked on stat() before anything is decompressed.
            print(f"{path.name}: {compressed} B compressed (cap {MAX_COMPRESSED[kind]})")
            failures.append(f"{path.name}: {compressed} B exceeds the compressed cap")
            continue
        uncompressed = uncompressed_size(path)
        print(
            f"{path.name}: {compressed} B compressed (cap {MAX_COMPRESSED[kind]}), "
            f"{uncompressed} B uncompressed (cap {MAX_UNCOMPRESSED[kind]})"
        )
        if uncompressed > MAX_UNCOMPRESSED[kind]:
            failures.append(f"{path.name}: {uncompressed} B exceeds the uncompressed cap")
            continue

        content, rejected = members(path)
        for name in rejected:
            failures.append(f"{path.name}: non-regular or duplicate member {escape(name)}")

        # The manifest is the primary control: an unlisted member cannot ship,
        # whatever it holds. Equality in both directions, so a dropped LICENSE or
        # NOTICE fails just as loudly as an added file.
        seen = {canonical(kind, name) for name in content}
        for added in sorted(seen - approved[kind]):
            failures.append(
                f"{path.name}: {escape(added)} is not in artifact-manifest.toml — "
                "add it there deliberately if it belongs in a published artifact"
            )
        for missing in sorted(approved[kind] - seen):
            failures.append(f"{path.name}: {escape(missing)} is in the manifest but not shipped")

        named_ids: set[str] = set()
        named_titles: set[str] = set()

        for name, blob in content.items():
            relative = canonical(kind, name)
            for part in pathlib.PurePosixPath(name).parts:
                if part == ".." or name.startswith("/"):
                    failures.append(f"{path.name}: path traversal in member {escape(name)}")
                    break
            try:
                text = blob.decode("utf-8")
            except UnicodeDecodeError:
                failures.append(f"{path.name}: non-UTF-8 member {escape(name)}")
                continue

            hits = len(ngrams(text) & needles)
            budget = EXCERPT_BUDGET.get(relative, 0)
            if hits > budget:
                failures.append(
                    f"{path.name}: BSI requirement prose in {escape(name)} "
                    f"({hits} matching {NGRAM}-word runs, budget {budget})"
                )

            folded = {i.casefold(): i for i in ids}
            named_ids |= {
                folded[token.casefold()]
                for token in ID_PATTERN.findall(text)
                if token.casefold() in folded
            }
            member_words = words(text)
            spans = {
                " ".join(member_words[i : i + n])
                for n in {len(words(title)) for title in titles}
                for i in range(len(member_words) - n + 1)
            }
            named_titles |= titles & spans

        if len(named_ids) > MAX_DISTINCT_IDS:
            failures.append(
                f"{path.name}: names {len(named_ids)} requirement ids across its members "
                f"(max {MAX_DISTINCT_IDS}) — looks like a catalogue index"
            )
        if len(named_titles) > MAX_DISTINCT_TITLES:
            failures.append(
                f"{path.name}: reproduces {len(named_titles)} requirement titles "
                f"(max {MAX_DISTINCT_TITLES})"
            )

    if failures:
        print("::error::artifact carries something it should not")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("artifacts clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
