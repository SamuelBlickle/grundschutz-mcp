# 0006. Separate code (Apache 2.0) and data (CC BY-SA 4.0)

- Status: accepted
- Date: 2026-06-06

## Context and problem statement
The BSI data is licensed CC BY-SA 4.0, whose share-alike term can extend to
derivative works. The project's own code should be permissively licensed to
maximise adoption and protect the author's commercial use. We must keep the two
from contaminating each other.

## Considered options
- License the whole project under CC BY-SA 4.0.
- License code under a permissive license and keep data separate, loaded at
  runtime and unmodified.

## Decision
Code is Apache 2.0. BSI data stays under CC BY-SA 4.0 with attribution in
NOTICE, loaded at runtime and passed through unmodified (see ADR-0002).

## Rationale
Apache 2.0 maximises reuse and adds an explicit patent grant, appropriate for a
security-adjacent tool. Because the code never modifies or redistributes a
transformed copy of the data, the share-alike obligation does not reach the
code. Any shipped transformed data artifact would be a derivative and must carry
CC BY-SA 4.0, so we ship none.

## Consequences
- Clear, defensible license posture; commercial use of the code stays open.
- Attribution discipline required (NOTICE accurate, BSI credited).
- Enforced by the deny_dangerous hook (protects LICENSE/NOTICE) and the
  enforce_layering hook (no vendored data). Detail cases (e.g. whether local
  caching counts as a derivative) warrant legal review before shipping caches.

## Revisit when
The data license changes, or a feature genuinely requires shipping transformed
data.
