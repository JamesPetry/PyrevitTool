# Traceability — Export Issue

**Purpose.** Every quality of the tool traced to the line in the brief that asked for it, so
the design can be checked against the source rather than taken on trust. Where the design
departs from the brief, that is stated in §3 rather than hidden.

**Sources.**

| Tag | Source |
|---|---|
| `MN` | Meeting notes, HDR PyRevit Tool Suite kickoff, 2026-07-27 |
| `RS` | Ryann's phase structure and folder layout, supplied 2026-07-27 |
| `PC` | [`docs/00-aecflow-pipeline-context.md`](00-aecflow-pipeline-context.md), cited by line |

---

## 1. Core function

### 1.1 Batch sheet export from one button

> `MN` — "delivery of an initial Python script for sheet creation and printing"

> `MN` — "Leo instructed James to focus first on delivering the specific Python script
> requested by Ryann"

The whole tool. Everything else in this document is subordinate to it.

### 1.2 Creates the folder tree automatically

> `RS` — "Action 1 - Create Export Folder"

> `MN` — "ongoing testing of Python scripts for tasks like automatic folder creation and
> batch PDF printing"

Implemented as an implicit precondition of every path-producing op rather than an op in its
own right — see §4 of the design doc.

### 1.3 Naming convention applied to every file

> `MN` — "automating sheet creation and batch printing with **proper folder and naming
> conventions**"

> `RS` — `12345-A101-RevP04.pdf`, `12345_Model_RevP04.ifc`, `26-07-22_Archive`

Lives in `lib/aecflow/naming.py` as a single config dict. Unit tested, including against
Revit's own illegal-character set.

### 1.4 Exports PDF, DWG, IFC and a detached RVT

> `RS` — "Action 3 - IFC Export"

> `RS` — "Action 4 - Detached Revit Model and save Revit"

> `RS` — folder tree showing `PDF`, `DWG`, `IFC`, `RVT`

Four op kinds, one per format.

### 1.5 Reads project information to build names

> `RS` — "Read Project Information │ Project Number │ Project Name │ Current Revision │
> File Location"

Maps one-to-one onto the `ModelSnapshot` fields in `contracts.py`. This line of the brief is
effectively the Extract specification.

### 1.6 Revit 2025

> `MN` — "The team discussed which Revit version to use for development, ultimately deciding
> on version 2025, with James confirming access and readiness to proceed."

### 1.7 `Document.Export`, not `PrintManager`

> `MN` — "the need to adapt previous EXE-based solutions to Python for better integration"

The EXE-based solutions existed largely to work around `PrintManager` and its printer-driver
dependency. Revit 2022+ exposes `Document.Export(folder, name, PDFExportOptions)`, which
removes the reason those workarounds existed. See ADR-003 for the filename-control
consequences.

---

## 2. Architecture

### 2.1 Deterministic Propose — no LLM in v1

> `PC:57` — "May be an LLM, a heuristic, or a **rules engine** — the contract is identical
> either way, so the stage is swappable."

Explicitly permitted, not a workaround. Consequence: no network access anywhere in the tool,
which also serves `MN` — "security issues in the HDR environment".

### 2.2 The review table is the primary gate

> `PC:171` — "**Nothing commits without passing through this table.** Low-confidence rows
> default to unchecked."

> `PC:177` — "it is where this architecture earns practitioner trust. Design it first, not
> last."

Followed: G2 is the largest element of the proposal and the first UI to be built.

### 2.3 Dry-run is the default

> `PC:120` — "Every run is dry-runnable. `--dry-run` produces the full ChangeSet and Verdict
> with zero mutations. This is the default in development."

### 2.4 A blocked check stops the whole run

> `PC:126` — "A blocked Check is terminal for the run. No partial-apply on block, no 'apply
> the passing ones anyway' without an explicit second human confirmation."

### 2.5 Identity is UniqueId

> `PC:117` — "Identity is `UniqueId`, never `ElementId`. ElementIds are not stable across
> sessions or documents; UniqueId is."

Followed for elements. Extended for documents and files — see §3.3.

### 2.6 The interesting logic is testable without Revit

> `PC:124` — "Stages 2–4 never import `Autodesk.Revit.DB`. If they need model data, it
> belongs in the Snapshot."

> `PC:192` — "Golden-file tests over fixture snapshots run in CI. Only Extract and Commit
> need Revit, and both are thin."

30 unit tests currently run with no Revit dependency.

### 2.7 Modal, blocking execution

> `PC:143` — "Modal / blocking — Extract, close, call Propose synchronously behind a progress
> bar, then Commit. ... Simplest; start here."

Additionally justified here because Propose makes no network call at all, so the modeless
`ExternalEvent` pattern buys nothing.

### 2.8 Worksharing and read-only guards

> `PC:156` — "Assume every production model is workshared."

> `PC:158` — "Guard on `doc.IsReadOnly` and on linked-document targets before Extract, and
> fail fast with a clear message rather than at Commit."

### 2.9 Four op kinds per tool

> `PC:249` — "The closed list of `kind` values this tool may emit. Keep it under six for a
> first release."

Satisfied only because of the two-tool split — see §3.1.

### 2.10 CPython 3, with an IronPython fallback

> `PC:133` — "Use the CPython 3 engine (`#! python3` shebang at the top of `script.py`)."

> `MN` — "challenges related to time constraints and **security issues in the HDR
> environment**"

The shebang follows `PC`. The compatibility constraint is a hedge against the second quote.
See ADR-002.

### 2.11 A client-neutral library under HDR branding

> `MN` — "developing a comprehensive HDR toolset by amalgamating various PyRevit scripts"

> `MN` — "future tasks including refactoring for usability and maintaining a consistent
> folder structure for GitHub repositories"

`HDR.tab` carries the branding; `lib/aecflow/` carries no HDR specifics, so scripts adopted
later can take on the Snapshot/Check/Record spine without a rewrite.

---

## 3. Where the design departs from the brief

Four departures. Each is a decision that could reasonably be reversed.

### 3.1 The two-tool split is not in the brief

`RS` presents a single linear run:

> `RS` — "START ├─ Read Project Information ... ├─ Purge Unused ├─ Save-As Audited Model
> └─ Close Model END"

Nothing in the source asks for this to be split. The split is inferred from two things: the
risk asymmetry between actions 1–4 (create files) and 5–9 (move files, mutate the model),
and the six-op cap at `PC:249`, which nine actions cannot meet in one tool.

**This is the decision most likely to be rejected, and the one to raise first.** If Ryann
wants a single button, the fallback is one tool with an op kind per format and a Purge that
is opt-in and defaulted off — at the cost of the export half not shipping until the
destructive half is trusted.

See ADR-001.

### 3.2 Invariant 5 cannot be satisfied

> `PC:122` — "Every commit is a single undo. Wrap in `TransactionGroup` and `Assimilate()` so
> the user's Ctrl+Z reverses the whole operation, not the last sub-step."

`Export Issue` opens no transaction — it reads the model and writes files. There is nothing
for Ctrl+Z to reverse. Recorded as scoped rather than claimed, with dry-run, the no-overwrite
rule and the G2 table as compensating controls. The invariant returns in force for
`Archive & Close`.

### 3.3 Tagged targets extend Invariant 3

> `PC:117` — "Identity is `UniqueId`, never `ElementId`."

Two of four ops target the document and one class of Check rule targets files on disk;
neither has a UniqueId. Targets are therefore tagged `element` / `document` / `path`. Element
identity remains UniqueId-exclusive and ElementIds appear nowhere outside Resolve, so this is
an instantiation of the invariant rather than a relaxation — but it is an addition, and it is
recorded as one.

### 3.4 The brief specifies both answers to Q2

The revision-selection rule cannot be read unambiguously from the source, because two lines
of `RS` disagree.

> `RS` — "Action 2 - Export Sheets with **Latest Revision**"

reads as *each sheet at its own latest revision*. But:

> `RS` — "12345-A101-Rev**P04**.pdf" and "12345-A102-Rev**P04**.pdf"

shows every sheet carrying the *same* revision, which is issue-based selection. On any
project where sheets have diverged, these produce different file sets.

Q2 existed because the brief genuinely specifies both and the code must pick one.

**Resolved 2026-07-27 in Ryann's favour, against our recommendation.** The operative line is
"Export Sheets with **Latest Revision**" — per-sheet latest. The uniform `RevP04` filenames
were an artefact of the example, not a specification. A **sheet series** scopes the package
instead, so the selection is "every sheet in this series, each at its own current revision".

Mixed revisions in one folder are therefore correct output. R8 was inverted accordingly: it no
longer warns on mixed revisions, it warns when a sheet has no revision at all. Our stated
recommendation was wrong, and the design has been changed rather than the answer argued with.

---

## 4. Unsourced additions

Everything not listed in §3 traces to a direct quote. The remaining additions are minor and
listed here for completeness:

- **The naming-separator question (Q3).** Not raised in the brief; it comes from an
  inconsistency between the sheet examples (hyphens) and the model examples (underscores).
- **Check rules R4 and R5** (path length, filename legality). Not requested. Added because
  HDR network paths are deep and Revit sheet numbers legally contain characters Windows
  forbids in filenames.
- **The audit record.** `PC:75` requires it architecturally; no line of `MN` or `RS` asks for
  it.
