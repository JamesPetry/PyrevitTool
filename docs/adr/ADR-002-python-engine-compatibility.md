# ADR-002 — Target CPython 3, stay IronPython 2.7 compatible

**Status:** Proposed (for review 2026-07-27)

## Context

The pipeline context specifies the CPython 3 engine (`#! python3`), because
IronPython 2.7 cannot practically run modern HTTP clients, `pydantic`, or
current TLS.

None of those apply here. `Export Issue` has no probabilistic stage, so it
makes no network calls and needs no third-party packages — only the Revit API,
`os`, `shutil`, `re` and `json`.

Against that, the client raised security constraints in the HDR environment.
Approving a new Python engine in a locked-down SOE is an IT process with an
uncertain outcome and no timeline we control. A tool that hard-depends on
CPython 3 is blocked entirely if that approval does not come.

## Decision

Ship `#! python3` — it is the better engine and the pipeline context's default.
But write everything under `lib/aecflow/` to run unchanged on IronPython 2.7:

- `.format()`, never f-strings
- No type annotations in signatures; shapes documented in docstrings
- No `dataclasses`, no `typing.TypedDict`, no `pathlib`
- No `enum`; module-level string constants instead
- Explicit `# -*- coding: utf-8 -*-` headers

Falling back is then a shebang change, not a rewrite.

## Consequences

**Good.** An environment veto costs one line, not the project. The constraint
is cheap because the tool genuinely needs nothing modern.

**Cost.** The library reads slightly older than it needs to, and contracts are
validated by hand (`contracts.validate_op`) rather than by a type checker. The
validator is needed regardless — runtime data comes from the Revit API, which
a static checker cannot vouch for.

**Boundary.** The constraint applies to `lib/aecflow/` only. `tests/` targets
CPython 3 freely, since it never runs inside Revit.

**Revisit when.** Q8 is answered. If the CPython 3 engine is approved for the
SOE and no fallback is wanted, drop the constraint and modernise the library in
one pass — it is small.
