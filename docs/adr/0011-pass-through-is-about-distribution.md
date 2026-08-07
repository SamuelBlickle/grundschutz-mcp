# 0011. The pass-through guarantee is about distribution, not literal immutability

- Status: accepted (refines ADR-0002 and ADR-0006)
- Date: 2026-08-02

## Context and problem statement
ADR-0002 decided to load the BSI data at runtime "and pass it through
unmodified", and ADR-0006 grounded the Apache 2.0 / CC BY-SA 4.0 boundary in the
claim that "the code never modifies or redistributes a transformed copy of the
data". Invariant 5 in CLAUDE.md repeats the same wording.

ADR-0009 then sanctioned resolving OSCAL parameter placeholders in requirement
prose. Measured at commit `b4e1ee40`, that substitution touches 130 of 651
controls (136 placeholders, 135 of them resolved from a `label`). The literal
claim has therefore been false since ADR-0009 was accepted, in three places at
once: two ADR rationales, a binding invariant, and the NOTICE attribution file
that a CC BY-SA licensor relies on.

The mapper also normalises structured metadata — splitting a comma-separated
`tags` string, stripping a leading `#` from link hrefs, coercing `effort_level`
to `int`. Those are transformations too, which is why the corrected wording has
to be scoped to content rather than stated as an absolute.

The defect is not that the wrong thing is being done — ADR-0009's substitution is
correct and stays. It is that the guarantee was stated as a property of the
*data flow* ("we never modify") when the property that actually holds, and the
one the licence boundary depends on, is a property of *distribution* ("we ship no
transformed artifact"). Stating a stronger claim than the code honours is how a
compliance tool loses the argument it exists to make.

## Considered options
- Leave the wording and treat ADR-0009 as an implicit exception. Cheapest, but
  keeps a knowingly false statement in a licence-bearing file and forces every
  future reader to rediscover the exception.
- Reverse ADR-0009 so the literal claim becomes true again. Restores a clean
  invariant at the cost of shipping `{{ insert: param, ... }}` to ISMS users,
  which ADR-0009 rejected for good reasons that have not changed.
- Restate the guarantee in terms of what is distributed, and name the one
  in-memory transformation explicitly.

## Decision
Invariant 5 is restated in terms of content and distribution. `title`, `text`
and `guidance` are the upstream prose byte-for-byte, except that
`{{ insert: param, <id> }}` spans are replaced per ADR-0009. **Nothing derived
from BSI content is written to disk or shipped in the package**, and any other
difference between upstream prose and returned text, any on-disk cache, and any
field computed from prose needs its own ADR.

The exemption for metadata is bounded by an enumerated field set — `module`,
`security_level`, `effort_level`, `tags`, `related`, `required` — rather than by
the mechanism "structured metadata projection". A mechanism-shaped exemption
launders: if the BSI adds a prose-bearing prop and the mapper extracts and
normalises it into a new field, that is neither `text` nor "computed from
prose", so it would pass an unbounded exemption while shipping altered BSI
sentences. With the set enumerated, any new field carrying BSI prose lands on
the content side by default.

The exception is bound to the `{{ insert: param, <id> }}` syntax rather than to
ADR-0009 as a whole, because ADR-0009's own "Revisit when" invites adjusting the
resolver for new parameter kinds. Tying the invariant to the syntax means such a
change is measured against the invariant rather than absorbed by it.

The licence boundary rests on the shipping clause alone. The project distributes
no BSI data file: the substitution happens in memory, in the user's own process,
and no derived artifact is packaged. On that basis CC BY-SA 4.0 §3(a) does not
attach to our distribution of the package. NOTICE records the modification
regardless, so a downstream redistributor — or an operator serving an instance to
others, who does Share — can discharge their own attribution and
indicate-modifications duty.

Two honest qualifications. README.md quotes a small number of BSI requirement
sentences as examples, in their ADR-0009-substituted form, and README.md becomes
the wheel's `METADATA`; those are short attributed excerpts shipped alongside
NOTICE in the same artifact, not a copy of the catalogue, but they are the reason
this record says "no BSI data file" rather than "no BSI content". And this is the
maintainers' reading of the licence, not legal advice.

The invariant-to-ADR map in CLAUDE.md gains ADR-0009 and this record, so a reader
tracing invariant 5 reaches the decision that actually sanctions the
substitution.

## Rationale
"We ship no transformed artifact" is the claim that was always doing the work.
It is checkable against a built wheel and sdist, it is stable under any future
in-memory mapping decision, and it is the condition CC BY-SA share-alike actually
turns on. "We never modify" was a stronger claim that was never needed, and once
ADR-0009 landed it was simply untrue.

Naming the substitution in the invariant rather than hiding it behind a
reference means the exception cannot quietly widen: anything beyond the
`{{ insert: param, <id> }}` replacement violates invariant 5 as written and needs
its own record.

## Consequences
- Positive: invariant 4, invariant 5, ADR-0002, ADR-0006 and NOTICE agree with
  the code and with each other; the licence argument rests on a checkable
  property. Invariant 4 is restated in the same commit, since it carried the
  same literal falsehood ("the original wording").
- Positive: the invariant-to-ADR map no longer dead-ends — invariant 5 traces to
  ADR-0002/0006 for the decision, ADR-0009 for the substitution, and this record
  for the scope.
- Negative / cost accepted: the invariant is longer and no longer a slogan. That
  is the price of it being true.
- v1.0.0 shipped the pre-correction NOTICE: it was tagged 2026-06-07, one day
  after ADR-0009 was accepted, so the released artifact's attribution file
  already misdescribed the mapper. It should be corrected in a docs-only patch
  release rather than left standing on PyPI.
- This record changes no runtime behaviour. `mapper.py`, `model.py` and
  `server.py` are untouched; `loader.py` changes only its docstring, in the same
  PR stack.
- Automatically enforced, **the shipping clause**: `scripts/check_artifacts.py`
  runs on every pull request and again in the release workflow before provenance
  is attested. Its primary control is `scripts/artifact-manifest.toml`, which
  lists the exact members of each artifact: a file that is not listed cannot
  ship, whatever it contains and however it is encoded, and adding one is a
  reviewed diff rather than a side effect of the working tree. Behind that sit
  size caps, a 12-word prose matcher over letter-only tokens, an artifact-wide
  census of requirement ids and titles, and an assertion that LICENSE and NOTICE
  are present. The publish job then re-checks the artifacts it downloads against
  digests the build job recorded, so the guarantee covers the bytes PyPI
  receives rather than ending at the bytes that were attested.

  The manifest is primary because content detection alone was not enough, and
  the record should say why rather than leave the next maintainer to rediscover
  it. Four earlier versions of the matcher were each defeated in review with a
  real build: caps calibrated against the raw 5.4 MB rather than the 514 KB it
  gzips to; byte matching beaten by `textwrap.fill`; whitespace-normalised
  character shingles beaten by a Markdown blockquote; and word n-grams whose
  length had been calibrated against `guidance` (97% of the corpus) while 302 of
  652 `Requirement.text` values are shorter than the needle and produced none.
  Detecting arbitrary content in arbitrary files is unbounded; constraining
  which files exist is not.

- **Not automatically enforced:** a second transformation of BSI content, an
  on-disk cache, and a field computed from prose. Those rest on the
  architecture-guardian and security-reviewer gates, which are review, not CI.
  Within an already-approved file the matcher is also best-effort: it does not
  see runs shorter than 12 words, re-encoded content, or prose broken up with
  invisible characters — the caps are what stand behind it there. This control
  is built to stop an accidental leak and to make a deliberate addition visible,
  not to withstand someone with commit rights, who can edit the control itself.

  Two machine checks cover content elsewhere: the network drift test asserts no
  `{{ insert: param` survives into the model, and that prose is byte-identical to
  upstream wherever no parameter is inserted.

## Revisit when
A second transformation of BSI content is proposed — a normalisation, a
computed field derived from prose, a cache written to disk — or the project
starts distributing any artifact containing BSI content. Either would move the
licence analysis and needs a superseding record, not an amendment to this one.
