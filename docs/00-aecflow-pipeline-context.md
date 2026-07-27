# AECFlow — Overarching Pipeline Context (pyRevit Instantiation)

**Purpose.** This is the architectural context for any AECFlow workflow tool built as a pyRevit
extension. It defines the stage model, the determinism boundary, the typed contracts between
stages, and the runtime constraints imposed by Revit. Fill the *Instantiation Slots* (§10) per
tool; everything above them is fixed across tools.

**How to use.** Load this as project context before spec'ing or building. If a design decision
conflicts with §4 (Hard Invariants), the invariant wins and the design changes.

---

## 1. What changed from the Tender-to-Task instantiation

The Tender-to-Task Scheduler runs `Extract → Schedule → Check` and emits an artefact (a
programme). The source is unstructured (tender docs) and the output is inert — nothing is
mutated, so a wrong answer is a wrong document.

A pyRevit tool inverts both properties:

| | Tender-to-Task | pyRevit tool |
|---|---|---|
| Source | Unstructured documents | The Revit model (structured, queryable) |
| Extraction | Probabilistic (LLM reads prose) | **Deterministic** (API read) |
| Output | An artefact | **A mutation of the source of truth** |
| Failure mode | Bad schedule, reviewable | Corrupted model, possibly synced to central |

Two consequences drive the whole architecture:

1. The probabilistic stage **moves downstream**. Extraction is now free of uncertainty; the
   uncertainty lives in deciding *what to change*.
2. A **Commit** stage and a rollback boundary are now mandatory. Check is no longer the last
   gate before a human reads a document — it is the last gate before the model is written to.

---

## 2. Stage Model

```
  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
  │ EXTRACT │──▶│ PROPOSE │──▶│ RESOLVE │──▶│  CHECK  │──▶│ COMMIT  │
  │   [D]   │   │   [P]   │   │   [D]   │   │   [D]   │   │   [D]   │
  └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
    Snapshot      Intent        ChangeSet     Verdict      Transaction
       │             │              │             │             │
       └─────────────┴──────────────┴─────────────┴─────────────┘
                              RECORD [D]  (cross-cutting audit)
```

`[D]` deterministic · `[P]` probabilistic

**EXTRACT [D]** — Read the model through the Revit API into a serialisable `Snapshot`.
No interpretation, no filtering beyond the declared scope. The Snapshot is the *only* thing
downstream stages see; nothing after Extract may touch the `Document` for reads.
*Rationale: this is what makes stages 2–4 testable outside Revit.*

**PROPOSE [P]** — The only stage permitted to be non-deterministic. Consumes a `Snapshot`,
emits an `Intent`: a list of operations drawn from a **closed vocabulary**, each carrying
target UniqueIds, a confidence, and a rationale string. May be an LLM, a heuristic, or a
rules engine — the contract is identical either way, so the stage is swappable.

**RESOLVE [D]** — Lowers `Intent` into a `ChangeSet`: concrete, fully-bound API operations
with all values coerced to their Revit types, units converted, and ElementIds re-bound from
UniqueIds against the live document. Any operation that cannot be fully bound is dropped
here with a recorded reason — never guessed at.

**CHECK [D]** — Evaluates the `ChangeSet` against the rule set. Produces a `Verdict` of
`pass` / `warn` / `block` per operation plus a set-level verdict. Rules are pure functions
over `(Snapshot, ChangeSet)`. A `block` on any operation blocks the whole set by default.

**COMMIT [D]** — Opens a `TransactionGroup`, applies the surviving operations inside a
`Transaction`, and either assimilates or rolls back. This is the only stage that mutates
anything.

**RECORD [D]** — Persists Snapshot hash, Intent, ChangeSet, Verdict, and commit outcome.
Every mutation must be reconstructable after the fact.

---

## 3. The Narrow Waist

The single most important element of this architecture is the boundary between PROPOSE and
RESOLVE. Everything upstream is untrusted; everything downstream is verified.

**The model never emits code, and never emits a value that is written directly.** It emits
operations from a fixed vocabulary. Example shape:

```python
# contracts.py
class Op(TypedDict):
    kind: Literal["set_param", "rename", "place_view", "set_type", "delete"]
    target_uid: str          # Element.UniqueId — never ElementId
    args: dict[str, Any]     # schema per kind, validated
    confidence: float        # 0.0–1.0
    rationale: str           # shown to the human at the review gate
```

Rules for the vocabulary:

- Every `kind` has exactly one validator and one executor, colocated.
- Adding a `kind` requires adding both, plus a negative test. No exceptions.
- Free-text fields are display-only (`rationale`) and never reach the API.
- If a task seems to need an op outside the vocabulary, that is a signal the task is out of
  scope for this tool — not a signal to add an escape hatch.

---

## 4. Hard Invariants

These are the pyRevit analogue of *deterministic date computation* in the scheduler.

1. **No probabilistic output reaches the Revit API unvalidated.** Every write traces back to
   a validated op in the closed vocabulary.
2. **No LLM call inside a `Transaction`.** Network latency inside an open transaction risks
   holding element locks for seconds and freezing the session. Propose runs with the document
   closed for reads and no transaction open.
3. **Identity is `UniqueId`, never `ElementId`.** ElementIds are not stable across sessions or
   documents; UniqueId is. Snapshots and ChangeSets store UniqueId exclusively and rebind at
   Resolve time.
4. **Every run is dry-runnable.** `--dry-run` produces the full ChangeSet and Verdict with
   zero mutations. This is the default in development.
5. **Every commit is a single undo.** Wrap in `TransactionGroup` and `Assimilate()` so the
   user's Ctrl+Z reverses the whole operation, not the last sub-step.
6. **Stages 2–4 never import `Autodesk.Revit.DB`.** If they need model data, it belongs in
   the Snapshot. This is enforceable by a lint rule and worth enforcing.
7. **A blocked Check is terminal for the run.** No partial-apply on block, no "apply the
   passing ones anyway" without an explicit second human confirmation.

---

## 5. Runtime & Execution Constraints

**Engine.** Use the CPython 3 engine (`#! python3` shebang at the top of `script.py`).
IronPython 2.7 is pyRevit's default and cannot practically run modern HTTP clients,
`pydantic`, or current TLS. If any stage needs `requests`/`httpx`, CPython 3 is required.
Note that some older pyRevit and Revit API interop patterns behave differently under
pythonnet — verify `clr` imports early rather than at integration time.

**Threading.** The Revit API is main-thread and context-bound: it may only be called from
within a valid API context (a command execution, or an `IExternalEventHandler.Execute`).
Two viable patterns:

- **Modal / blocking** — Extract, close, call Propose synchronously behind a progress bar,
  then Commit. Acceptable when Propose completes in a few seconds. Simplest; start here.
- **Modeless + ExternalEvent** — a non-modal WPF window; a worker thread runs Propose;
  `ExternalEvent.Raise()` hands the ChangeSet back into a valid API context for Resolve/Check/
  Commit. Required for anything conversational, iterative, or long-running. The handler must
  be the *only* thing that touches the document.

**Failures.** Register an `IFailuresPreprocessor` on the transaction so expected warnings are
resolved deterministically rather than surfacing modal dialogs mid-commit. Unexpected failures
roll the group back.

**Worksharing.** In any workshared model, check element ownership before including an op:
`WorksharingUtils.GetCheckoutStatus()`. Elements owned by another user are dropped at Resolve
with a recorded reason. Assume every production model is workshared.

**Read-only documents.** Guard on `doc.IsReadOnly` and on linked-document targets before
Extract, and fail fast with a clear message rather than at Commit.

---

## 6. Human-in-the-Loop Gates

Three gates, matching the AECFlow HITL posture:

- **G1 — Scope.** The user confirms what the tool will look at (selection, view, category,
  whole model) before Extract. Prevents whole-model runs by accident.
- **G2 — Diff review.** The primary gate. Present the ChangeSet as a table: target, property,
  current value → proposed value, confidence, rationale, Check verdict. Sortable, with
  per-row opt-out. **Nothing commits without passing through this table.** Low-confidence
  rows default to unchecked.
- **G3 — Post-commit.** Summary of what was written, the audit record location, and an
  explicit reminder that a single undo reverses it.

G2 is the direct analogue of schedule review in the Tender-to-Task tool, and it is where this
architecture earns practitioner trust. Design it first, not last.

---

## 7. Testability

Because Extract emits a serialisable Snapshot and stages 2–4 never touch the API, the
interesting logic is testable without Revit at all:

```
tests/fixtures/<case>/snapshot.json   →  propose  →  intent.json
                                      →  resolve  →  changeset.json   (expected)
                                      →  check    →  verdict.json     (expected)
```

Golden-file tests over fixture snapshots run in CI. Only Extract and Commit need Revit, and
both are thin. Capture real snapshots from live models and commit them as fixtures — this is
the highest-leverage testing investment in the project.

---

## 8. Extension Layout

```
AECFlow.extension/
  AECFlow.tab/
    <Tool>.panel/
      <Tool>.pushbutton/
        script.py            # thin: gates + orchestration only, no logic
        bundle.yaml
        icon.png
  lib/                       # pyRevit auto-adds this to sys.path
    aecflow/
      contracts.py           # Snapshot, Intent, Op, ChangeSet, Verdict
      extract.py             # [D] Revit reads only
      propose.py             # [P] the only module aware of an LLM
      resolve.py             # [D]
      check.py               # [D]
      rules/                 # one rule per file, pure functions
      commit.py              # [D] transactions, failure preprocessor
      record.py              # audit persistence
```

`script.py` should read as a sequence of five calls plus three gates. If logic accumulates
there, it belongs in `lib/`.

---

## 9. Definition of Done

- [ ] Golden fixtures for at least three representative snapshots, including one adversarial
- [ ] Every op `kind` has a validator, an executor, and a negative test
- [ ] Dry-run produces a full ChangeSet with zero document mutations
- [ ] Grep confirms no `Transaction` opened in the same call stack as a network request
- [ ] Grep confirms stages 2–4 do not import the Revit API
- [ ] Commit is reversible by a single Ctrl+Z on a workshared test model
- [ ] Ownership conflicts drop cleanly with a user-visible reason
- [ ] Audit record written for every run, including aborted ones

---

## 10. Instantiation Slots

Fill these per tool. Everything above is fixed.

**Tool name / trigger.** _____

**Job to be done.** One sentence, from the practitioner's point of view. _____

**Scope of Extract.** Which categories, parameters, views, and relationships enter the
Snapshot — and explicitly what does not. _____

**Op vocabulary.** The closed list of `kind` values this tool may emit. Keep it under six
for a first release. _____

**Rules.** The Check rule set, one per line, each expressible as a pure function over
`(Snapshot, ChangeSet)`. _____

**Propose implementation.** Heuristic, LLM, or hybrid — and if LLM, what exactly is in the
prompt context and what the refusal path is when the model is uncertain. _____

**Confidence policy.** Threshold below which a row is unchecked by default at G2. _____

**Execution pattern.** Modal blocking or modeless + ExternalEvent, with the latency estimate
that justifies the choice. _____

**Out of scope.** What this tool will refuse to do, so the vocabulary stays closed. _____
