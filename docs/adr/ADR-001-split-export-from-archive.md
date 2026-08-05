# ADR-001 — Split the nine actions into two tools

**Status:** Proposed (for review 2026-07-27)

## Context

The client's structure defines nine actions across four phases, presented as one
automation run. Delivered as a single button, actions 1–4 (create folders,
export PDF/DWG/IFC, save detached RVT) cannot be released until actions 5–9
(archive, purge, audit, save-as, close) are trusted — despite having a
completely different risk profile.

Actions 1–4 only ever create new files. Actions 5–9 move existing files and
mutate the model; Purge in particular is not reversible.

The pipeline context also caps a first release at six op kinds. Nine actions
needs eight or more, which either blows the budget or forces a single `export`
kind with a `format` argument — hiding the per-format validation complexity
inside one validator rather than removing it.

## Decision

Two pushbuttons sharing one library:

- **`Export Issue`** — actions 1–4. Four op kinds. Ships first.
- **`Archive & Close`** — actions 5–9. Four op kinds. Ships once Export is
  trusted in the field.

Both stay under the six-kind budget. Both use the same Snapshot, contracts,
Check engine, and audit record.

## Consequences

**Good.** Something real is in front of the client at M1 rather than nine
half-finished actions. The destructive half gets its own review cycle. Check
rule R2 (`Export Issue` never overwrites) becomes enforceable, which means the
export tool structurally cannot destroy a previous issue.

**Cost.** A user wanting the full nine-action run presses two buttons. If that
proves annoying in practice, a third "Run All" button can orchestrate both once
each is independently trusted — but not before.

**Risk.** Two tools can drift. Mitigated by the shared library: the tools own
their op vocabulary and gates, nothing else.
