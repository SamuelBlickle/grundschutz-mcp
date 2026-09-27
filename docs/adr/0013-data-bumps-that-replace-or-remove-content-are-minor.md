# 0013. Data bumps that remove or replace content are MINOR, not only those that add it

- Status: accepted (refines ADR-0010)
- Date: 2026-09-27

## Context and problem statement
ADR-0010 maps a BSI data bump onto SemVer by content impact: MINOR when it
**adds content**, PATCH when it is **only text corrections**. Two kinds of
upstream change fall between those two rules:

- **Removal.** The 47de2824 re-pin (#28, released as 1.1.0) withdrew 26
  requirement ids. That adds nothing and corrects nothing.
- **Replacement.** The 367d7750 re-pin (#60, released as 1.3.0) added and
  removed nothing, but gave KONF.7.14 a requirement text with a different
  subject and rewrote three guidance texts. That is more than a correction, yet
  under ADR-0010's wording alone it could be argued down to PATCH.

VERSIONING.md was widened in #28 to "adds, removes, or replaces content" and has
been applied that way since. The recorded decision in ADR-0010 was never updated
to match, so the rulebook and the decision behind it disagree.

## Considered options
- Keep ADR-0010 literal: removal and replacement are PATCH unless something is
  also added.
- Treat removal as MAJOR, since a consumer that persisted a withdrawn id breaks.
- Treat any data bump that adds, removes or replaces content as MINOR, and keep
  PATCH for pure text corrections.

## Decision
A BSI data bump is **MINOR** when it **adds, removes, or replaces** content:
requirements, modules, tags, or fields. It is **PATCH** only when it is
**purely text corrections** (typos, spelling, formatting, a garbled sentence
restored) that leave what a requirement asks for unchanged. A release that
removes requirement ids or modules must list every removed id and module in its
release notes.

Everything else in ADR-0010 stands. In particular, requirement content stays
outside the stability contract.

## Rationale
The version level is how a compliance user decides whether a release deserves
a look. Both removal and replacement change what a requirement asks for, or
whether it exists at all. A consumer who mapped a control to KONF.7.14 has to
review that mapping, and a PATCH would tell them the opposite. MAJOR is wrong
for the same reason ADR-0010 gives: requirement content is not part of the
software contract, so a third party's editorial decisions must not drive MAJOR
bumps. The listed-ids rule covers the one real hazard of removal, persisted ids,
without breaking that contract.

The line between "replace" and "correct" needs judgement: ask whether a reader
would do anything differently. A title change from "Überwachung" to "Überprüfung"
does change the meaning; a restored hyphen does not.

## Consequences
- Positive: the decision matches VERSIONING.md again, and the level carries
  meaning for the users who read it.
- Negative / cost accepted: more data bumps are MINOR, so the minor number moves
  faster. The replace-versus-correct judgement still has to be made from the
  drift diff on every re-pin.
- Enforced by: VERSIONING.md (the rulebook) and convention. Every re-pin
  gets a semantic diff and an `architecture-guardian` review of the level it
  proposes; nothing checks the level mechanically.

## Revisit when
The BSI publishes a changelog or change classification of its own that could
decide the level mechanically, or consumers ask for the data axis to be
versioned separately from the package.
