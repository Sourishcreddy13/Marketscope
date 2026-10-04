---
name: trace-ac-tests
description: Produce a deterministic trace from AC-01..AC-10 to implementation tests and applicable NFRs.
---

# /trace-ac-tests

Read `specs/app_spec.md` and all feature specifications.

For each AC-01 through AC-10:

1. locate at least one automated test explicitly containing the AC-NN identifier,
2. identify the implementation module that satisfies it,
3. identify the NFRs that constrain it,
4. report missing or orphaned coverage.

Output:

```text
AC-01 -> implementation -> test(s) -> NFRs
...
AC-10 -> implementation -> test(s) -> NFRs

MISSING: NONE | <entries>
ORPHAN_TESTS: NONE | <entries>
```

This command is reporting-only.
