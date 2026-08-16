# 0012. Fail loudly means fail on unverified shapes, and completeness is part of it

- Status: accepted
- Date: 2026-08-05

## Context and problem statement
Invariant 6 ("fail loudly") was the only invariant with no record of its own. The
map in CLAUDE.md pointed at ADR-0002 and ADR-0003, and neither states it: 0002
decides runtime loading from a pinned commit, 0003 decides the anti-corruption
layer. Fail-loudly appears in both only as a consequence of a different decision.

That gap had a cost. `_walk_controls` recursed into `group["groups"]` but never
into `control["controls"]`, and OSCAL nests requirements under requirements. At
the pinned commit the catalog holds 1000 requirements; the model held 652. The
missing 348 were not sub-clauses -- `GC.3.1.1` "Gesetzliche Verpflichtungen"
carries its own normative MUSS statement, its own security and effort levels --
and `get_requirement_by_id` returned null for every one of them.
`get_catalog_stats().total` reported 652 for a catalog of 1000, and
`list_requirements_by_module`, documented as returning "all requirements",
returned two thirds. It shipped in v1.0.0.

Two things let that stand. The mapper raised loudly on every malformed control
it *reached*, so it looked like it was honouring invariant 6 while returning
silently partial data, which is the thing invariant 6 actually forbids. And the
network drift test asserted that every model requirement exists upstream --
trivially true for a subset, and structurally incapable of detecting the defect.
Nothing asserted the converse.

The fix then exposed a second instance of the same pattern. Feeding the missing
348 through the mapper, 346 mapped and 2 raised: `REA.2.6.1` and `REA.2.6.2.1`
have a `statement` part and no `guidance` part at all. The mapper had required
`guidance` unconditionally. All 652 controls it had been reading do carry
guidance, so the rule held for the subset it walked and was false for the
catalog. An assumption that was never checked against the whole tree had been
enforced as if it were a decision.

## Considered options
- Leave invariant 6 without a record and fix the recursion. Cheapest, and leaves
  the next unverified assumption free to harden into a rule the same way.
- Read "fail loudly" maximally: raise on any shape not already handled, including
  the missing guidance part. That makes the pinned catalog unloadable, so it
  trades partial data for no data.
- Record what fail-loudly is a rule *about*, and tie it to corpus verification.

## Decision
`OscalMappingError` is raised for shapes that are **unverified**, not merely for
shapes the mapper does not currently handle. A field or part may be treated as
legitimately optional only when three things hold:

1. its absence is verified against the **complete** traversed corpus -- not a
   sample, and not whichever subset the mapper happens to reach;
2. treating it as optional does not retype or default away a model field, which
   VERSIONING.md makes a MAJOR trigger and which would need its own decision;
3. a bounded regression assertion exists in the network drift suite, so the
   exception cannot widen silently.

Applied here: an absent `guidance` part yields `""`, a `guidance` part that is
present but blank still raises. The first is verified legitimate data; the second
is malformed data and remains the drift signal invariant 6 exists to catch.

Second, and this is the part that would have caught the defect: any mapper that
projects a **tree** rather than a flat list must be accompanied by a completeness
assertion in both directions -- every upstream id appears in the model, and every
model id appears upstream. Well-formedness over whichever subset the walk reaches
is not evidence that the walk reaches everything.

## Rationale
Returning 652 of 1000 requirements was a fail-loudly violation that raised no
error, so the invariant cannot mean "maximise the raise rate". It means: never
present partial or wrong data as if it were complete. Rejecting `REA.2.6.1` for
lacking guidance would have been the same mistake one layer up -- rejecting good
data on an assumption nobody had checked. ADR-0008 already reasoned this way when
it declined to make the CIA props required, because they are absent on the 56
method-layer controls; this record generalises that from a field decision into a
rule about evidence.

The bidirectional completeness assertion is the cheap part and the important
part. It is one set comparison, it needs no knowledge of what the mapper does,
and it would have failed on the day v1.0.0 shipped.

## Consequences
- Positive: invariant 6 has a record, and the map in CLAUDE.md resolves to
  something that states it.
- Positive: the catalog is internally consistent for the first time. All 36
  cross-references that previously dangled pointed at nested requirements; after
  the fix, zero dangle. That was read as upstream data quality and was ours.
- Positive: `get_catalog_stats().total` moves 652 -> 1000 and previously-null ids
  resolve. Content addition, MINOR per VERSIONING.md, and it must be called out
  in the release notes: anyone who persisted the old total or the old null
  results sees different answers.
- Negative / cost accepted: `guidance` can now be empty, so a consumer that
  assumed non-empty prose gets `""` for 2 of 1000 requirements. The field
  description says so, and the type is unchanged.
- Enforced by: `test_model_ids_equal_upstream_control_ids` (set equality against
  a raw upstream walk), `test_empty_guidance_count_stays_small` (bounds the
  carve-out at 10 against 2 today), the per-field assertions over the whole
  catalog in `test_pinned_data_still_maps`, and the architecture-guardian gate.

## Revisit when
A second optional part or field is proposed -- the three conditions above are the
test, and a proposal that cannot meet condition 1 is a proposal to guess. Also
revisit if the BSI introduces a containment relationship that tools need to
expose, since this record deliberately flattens nesting and projects no parent
link (ADR-0004: only fields a tool consumes).
