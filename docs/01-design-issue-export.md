# Design Plan — HDR Issue Export & Archive Tool

**Status:** Draft for review
**Date:** 2026-07-27
**Target:** Revit 2025 · pyRevit
**Architecture:** AECFlow pipeline (see `docs/00-aecflow-pipeline-context.md`)

---

## 1. What we are building first

Leo's instruction was explicit: deliver the specific script Ryann asked for — automated
sheet export and batch printing with correct folder and naming conventions — before any
work on consolidating third-party pyRevit scripts into an HDR suite.

This document designs that script, and only that script, against the four-phase structure
Ryann supplied. Everything about the wider HDR suite is deferred to §11.

**Job to be done (practitioner's voice):**
> "At issue time, put every sheet in this series out at its current revision, into the right
> folder, named to our standard — without me clicking Print 80 times."

---

## 2. The single most important recommendation: split it into two tools

Ryann's nine actions span two fundamentally different risk profiles:

| Actions | What they touch | Reversible? |
|---|---|---|
| 1–4 — folders, PDF, DWG, IFC, detached RVT | **Writes new files.** Model untouched. | Trivially — delete the output |
| 5–9 — archive, purge, audit, save-as, close | **Moves existing files. Mutates the model.** | Archive moves are recoverable; purge is not |

Shipping these as one button means the low-risk half cannot be released until the
high-risk half is trusted. It also blows the op-vocabulary budget (§4 of the pipeline
context caps a first release at six op kinds; nine actions needs eight or more).

**Proposal — two buttons, one shared library:**

- **`Export Issue`** — Actions 1–4. Ships first. Reversible, testable, low-consequence.
- **`Archive & Close`** — Actions 5–9. Ships second, once Export is trusted in the field.

They share `lib/aecflow/` entirely: same Snapshot, same contracts, same Check engine, same
audit record. This is a packaging decision, not an architectural one — and it means we have
something real in front of Ryann next week instead of something half-finished across nine
actions.

**The rest of this document specifies `Export Issue`.** `Archive & Close` is sketched in §10.

---

## 3. Pipeline instantiation

Mapping Ryann's phases onto the AECFlow stage model:

```
EXTRACT [D]          PROPOSE [D]           RESOLVE [D]        CHECK [D]         COMMIT [D]
──────────────       ──────────────        ──────────────     ──────────────    ──────────────
Project info         Select sheets in      Bind sheet UIDs    8 rules over      Create folders
Sheet list           the chosen series,    Build full paths   (Snapshot,        Document.Export
Revision table       each at its own       Coerce export      ChangeSet)        SaveAs detached
Existing exports     Decide folder tree    options                              Write audit
on disk
      │                     │                     │                 │                 │
      └─────────────────────┴─────────────────────┴─────────────────┴─────────────────┘
                                    RECORD [D] — JSON audit per run
```

### 3.1 There is no probabilistic stage in v1

PROPOSE is a **pure rules engine**. Nothing here is a judgement call: "which sheets carry
revision P04" is a query, "what is this file called" is a template, "where does it go" is a
constant. §2 of the pipeline context explicitly permits a heuristic or rules engine behind
the PROPOSE contract, and the contract is identical either way.

Consequences worth stating at the meeting:

- Invariants 1 and 2 (no unvalidated probabilistic output, no LLM inside a transaction) are
  **satisfied trivially** — there is no model call anywhere in the tool.
- The tool needs **no network access at all**. This matters directly for the HDR security
  constraints Ryann raised (§8).
- Every stage is golden-file testable with zero Revit dependency.
- The seam stays open. If a later version wants "export the sheets for the coordination
  issue" from a natural-language request, PROPOSE is swapped and nothing else moves.

We keep the full five-stage structure anyway. The cost is one afternoon of scaffolding; the
benefit is that Check, Record, and the review gate exist from day one, and the tools that
follow inherit them.

---

## 4. Op vocabulary (closed)

Four kinds. All four are file-producing; none mutate the open document.

| `kind` | Target | Args | Executor |
|---|---|---|---|
| `export_sheet_pdf` | element (sheet UniqueId) | `dest_path`, `pdf_options` | `Document.Export(dir, name, PDFExportOptions)` |
| `export_sheet_dwg` | element (sheet UniqueId) | `dest_path`, `dwg_options` | `Document.Export(dir, name, views, DWGExportOptions)` |
| `export_model_ifc` | document | `dest_path`, `ifc_options` | `Document.Export(dir, name, IFCExportOptions)` |
| `save_detached_rvt` | document | `dest_path`, `detach_option` | `Document.SaveAs(path, SaveAsOptions)` |

Folder creation is not an op — it is an implicit precondition of every path-producing op,
executed as `makedirs(exist_ok=True)` and written to the audit record. Making it an op adds
a fifth kind and a fifth validator to express `mkdir -p`.

Every kind has one validator and one executor, colocated in `lib/aecflow/ops/`. Adding a
kind requires both plus a negative test — no exceptions.

### 4.1 Identity: one extension to Invariant 3

Invariant 3 fixes identity as `UniqueId`, never `ElementId`. That holds for elements, and we
enforce it. But two of our four ops target the document and one class of Check rule targets
files on disk, neither of which has a UniqueId. We therefore use a **tagged target**:

```python
{"kind": "element",  "uid": "8f3a...-000a1b2c"}   # Revit element — UniqueId only
{"kind": "document"}                               # the active document
{"kind": "path",     "path": "P:/12345/Exports/PDF/12345-A101-RevP03.pdf"}
```

`path` targets appear only in `Archive & Close`. This is an instantiation-level extension of
the invariant, not a relaxation of it: element identity is still UniqueId-exclusive, and
ElementIds appear nowhere outside Resolve.

---

## 5. Naming and folder convention

### 5.1 Templates

From Ryann's example structure:

| Artefact | Example | Template |
|---|---|---|
| Sheet PDF | `12345-A101-RevP04.pdf` | `{project_number}-{sheet_number}-Rev{revision}.pdf` |
| Sheet DWG | `12345-A101-RevP04.dwg` | `{project_number}-{sheet_number}-Rev{revision}.dwg` |
| Model IFC | `12345_Model_RevP04.ifc` | `{project_number}_Model_Rev{revision}.ifc` |
| Detached RVT | `12345_Model_RevP04.rvt` | `{project_number}_Model_Rev{revision}.rvt` |
| Archive folder | `26-07-22_Archive` | `{YY}-{MM}-{DD}_Archive` |

**Open question for Ryann (Q3):** sheet names use hyphens, model names use underscores. If
that is deliberate we will keep it; if it is incidental we should pick one now, because
`Archive & Close` has to parse these filenames back into `(sheet_number, revision)` to
decide what to archive, and a stable separator makes that parse reliable.

Templates live in a config dict in `lib/aecflow/naming.py`, not scattered through the code,
so the convention is one edit away from changing per office or per project.

### 5.2 Folder tree

```
<export_root>/
├── Exports/
│   ├── PDF/   ├── DWG/   ├── IFC/   └── RVT/
└── Archive/
    └── 26-07-22_Archive/
```

**Open question for Ryann (Q4):** where is `<export_root>`? Three candidates — sibling of
the `.rvt`, a fixed network location per project, or read from a project parameter. The tool
supports all three; we need to know the default. Recommend a project parameter with a
sibling-of-RVT fallback, so the convention travels with the model.

### 5.3 Filename sanitisation

Revit sheet numbers legally contain characters Windows forbids in filenames (`/` is common
in `A-101/1`). Sanitisation is deterministic — a fixed substitution table, applied once, in
`naming.py` — and any sheet whose sanitised name collides with another's is **blocked**, not
silently renamed (rule R1).

---

## 6. Check rules

Pure functions over `(Snapshot, ChangeSet)`. One per file in `lib/aecflow/rules/`.

| ID | Rule | Verdict on failure |
|---|---|---|
| R1 | No two ops write the same destination path | **block** |
| R2 | No op overwrites an existing file (Export never overwrites; that is Archive's job) | **block** |
| R3 | Every element target resolves to a sheet still present in the Snapshot | **block** |
| R4 | Full destination path ≤ 260 chars | **block** |
| R5 | Sanitised filename contains no illegal characters and is non-empty | **block** |
| R6 | Export root exists, is writable, and is not a disconnected UNC path | **block** |
| R7 | Sheet is not a placeholder and has at least one placed view | **warn** |
| R8 | Every sheet in the series has at least one revision to name the file with | **warn** |

R4 is not theoretical. HDR project paths on network drives are deep, and `12345-A101-RevP04.pdf`
plus a nested `Exports/PDF/` eats the budget quickly. Failing at Check with a clear message
beats failing at op 60 of 80 with a Revit exception.

R2 is the rule that makes the two-tool split safe: `Export Issue` **cannot** destroy a
previous issue, because overwriting is a blocking failure. Archiving is a separate,
explicitly-invoked action.

Default policy per the pipeline context: any `block` blocks the whole set. No partial apply.

---

## 7. Human-in-the-loop gates

**G1 — Scope.** Before Extract. A dialog confirming: the **sheet series** to export, which
formats are enabled (PDF/DWG/IFC/RVT checkboxes), and the resolved export root. Shows the
sheet count that will be affected. This prevents an accidental whole-project export.

**G2 — Diff review.** The primary gate, and the one to build first. A table:

| ✓ | Sheet | Name | Revision | Format | Destination | Check |
|---|---|---|---|---|---|---|
| ☑ | A101 | Ground Floor Plan | P04 | PDF | `…/Exports/PDF/12345-A101-RevP04.pdf` | pass |
| ☑ | A102 | First Floor Plan | P04 | PDF | `…/Exports/PDF/12345-A102-RevP04.pdf` | pass |
| ☑ | A103 | Roof Plan | P03 | PDF | `…/Exports/PDF/12345-A103-RevP03.pdf` | pass |
| ☐ | A104 | Site Plan | — | PDF | — | **warn** R8: no revision on sheet |

Note row A103. Under the per-sheet rule confirmed in §12, a sheet at an older revision than
its neighbours is a **correct** export, not a warning — mixed revisions in one folder are the
expected output. The revision column is what makes that legible at a glance.

Sortable, per-row opt-out, warn rows visible and unchecked by default. Nothing writes
without passing through this table. pyRevit's `forms.SelectFromList` with a custom template
gets us most of the way without a WPF build.

**G3 — Post-commit.** What was written, where the audit JSON landed, and — since filesystem
writes are *not* Ctrl+Z-reversible — an explicit statement of which folder to delete to undo
the run.

### 7.1 Invariant 5 is scoped, not satisfied

The pipeline context requires every commit to be a single undo via `TransactionGroup`.
`Export Issue` opens **no transaction at all** — it reads the document and writes files. There
is nothing for Ctrl+Z to reverse.

We do not pretend otherwise. The compensating controls are: dry-run is the default (Invariant
4), G2 shows every destination path before anything is written, R2 makes overwriting a
previous issue impossible, and G3 names the exact folder to delete. Invariant 5 comes back
into force in `Archive & Close`, which does open transactions.

---

## 8. Runtime decisions

### 8.1 Revit 2025 gives us the modern export API — use it

Revit 2022+ exposes `Document.Export(folder, name, PDFExportOptions)`. This replaces the old
`PrintManager` + virtual-PDF-printer approach entirely: no printer driver dependency, no
per-machine print setup, no modal print dialogs, and paper size derived from the sheet's
titleblock. Ryann's earlier EXE-based solutions existed largely to work around
`PrintManager`; on 2025 that workaround is unnecessary.

**This is the single biggest technical win from standardising on 2025** and worth stating
plainly in the meeting.

### 8.2 Engine: target CPython 3, stay IronPython-compatible

`#! python3` in the shebang, per the pipeline context. But the library code is written to
run under IronPython 2.7 as well — no f-strings, no `dataclasses`, no annotations in
signatures, `.format()` throughout.

The reason is Ryann's security point. If HDR IT will not approve the CPython 3 engine in the
SOE, a tool that depends on it is dead. This tool needs **zero third-party packages and zero
network access** — only the Revit API, `os`, and `shutil` — so IronPython is a genuine
fallback rather than a theoretical one. The cost of staying compatible is a coding standard;
the benefit is that an environment veto does not restart the project. See `ADR-002`.

### 8.3 Execution pattern: modal, blocking, cancellable

Modal with a progress bar. There is no network call and no LLM, so the only latency is
Revit's own export, which must run on the API thread regardless. An 80-sheet PDF export runs
in minutes — long enough to need a cancellable progress bar (`pyrevit.forms.ProgressBar`),
not long enough to justify a modeless window and `ExternalEvent` plumbing.

Cancellation is checked between ops, never mid-op. A cancelled run is recorded, and the ops
completed before cancellation stay on disk — reported explicitly at G3.

### 8.4 Worksharing and read-only

Assume every production model is workshared. Guard before Extract on `doc.IsReadOnly` and
fail fast. Export ops need no element checkout — they only read — so the ownership drops
described in the pipeline context apply to `Archive & Close`, not here. `save_detached_rvt`
writes to a new path and never touches central.

---

## 9. What ships when

| Milestone | Contents | For |
|---|---|---|
| **M0** | This design agreed. Repo scaffold, contracts, naming module, op vocabulary frozen. | Today's meeting |
| **M1** | `Export Issue` — dry-run end to end, PDF export live, G1/G2/G3, audit record, golden fixtures from a real HDR model. | **Ryann's review next week** |
| **M2** | DWG, IFC, detached RVT. Config for naming/root. | +1 week |
| **M3** | `Archive & Close` — actions 5–9. | +2–3 weeks |
| **M4** | HDR suite consolidation begins (§11). | After M3 |

M1 is the deliverable in the follow-up task. Getting PDF working end-to-end with the review
gate demonstrates the whole architecture; the remaining three formats are the same shape with
different options objects.

**What we need from Ryann to hit M1:** answers to Q1 and Q2 (§12), and a test model — ideally
a workshared one with a real revision history and deep network path, since that is what R4 and
the worksharing guards are for.

---

## 10. Sketch — `Archive & Close` (actions 5–9)

Not designed in detail yet; recorded here so the shared library is built to accommodate it.

**Ops (4):** `archive_file` (path target — **move, never delete**), `purge_unused`,
`audit_save_as`, `close_model`.

**Additional rules:** archive destination must not pre-exist (date collision → suffix, never
merge into an existing archive folder); purge must be preceded by a successful save-as so the
live central is never purged in place; no op may affect elements checked out by another user;
`close_model` relinquishes.

**Changed by Q2's answer.** Supersession is now per-sheet, not per-issue. With every sheet
carrying its own revision, `12345-A101-RevP03.pdf` is superseded when `…-RevP04.pdf` appears,
while `12345-A102-RevP03.pdf` beside it may still be current. Archive therefore has to compare
each existing file against the incoming set sheet-by-sheet, rather than sweeping a whole
previous issue. `naming.parse_export_filename()` already returns `(sheet_number, revision)`
for exactly this.

**Invariant 5 applies here.** Purge and audit-save-as open transactions and must assimilate
into a single undo.

The riskiest action is Purge — it is not reversible and is the one most likely to surprise a
user. Recommend it be opt-in at G1 and default off.

---

## 11. The wider HDR suite (deferred)

Ryann's longer-term vision — consolidating EF Tools, PI Architect, and other open-source
pyRevit scripts into a single HDR collection — is real work but explicitly sequenced after
this tool. Two structural decisions made now that make it cheaper later:

1. **`HDR.tab` is branding; `lib/aecflow/` is architecture.** The library carries no HDR
   specifics, so imported third-party tools can adopt the Snapshot/Check/Record spine
   incrementally without a rewrite.
2. **Licensing is checked before adoption, not after.** EF Tools, PI Architect and similar
   carry their own licences. Each candidate script gets a licence note in `docs/adr/` before
   it enters the repo — cheap now, expensive to unpick later.

---

## 12. Open questions — meeting agenda

**Q1 — "Sheet creation": files or elements?** ⚠ *Highest impact — still open*
The meeting notes say "sheet creation and printing", but the phase structure Ryann supplied
contains no sheet-creation action — every one of the nine actions is export, archive, or
housekeeping. Two readings:
 - (a) "sheet creation" means creating the exported files. The phase structure supports this,
   and this document assumes it.
 - (b) it means creating `ViewSheet` elements in the model from a list or schedule.
That is a different tool with a different op vocabulary (`create_sheet`, `place_view`,
`set_sheet_param`) and it *does* mutate the model, so it needs the transaction machinery this
one does not. It is also where an LLM PROPOSE stage would first earn its place.
**Recommend confirming (a) for v1.** If (b) is wanted, it is a third tool, and we should scope
it separately rather than fold it in.

**Q2 — Revision selection rule.** ✅ *Answered 2026-07-27*
**Per-sheet latest, scoped by sheet series.** Every sheet in the chosen series exports at its
own current revision; the series defines the package, not the revision. Mixed revisions in one
folder are therefore the expected and correct output.

Consequences, all now applied:
 - R8 no longer warns on mixed revisions. It warns when a sheet has *no* revision at all,
   because there is then nothing to build a filename from (see Q9).
 - G1 selects a series, not a revision.
 - The Snapshot carries each sheet's series membership.
 - Archiving becomes per-sheet supersession rather than per-issue, which changes
   `Archive & Close` — noted in §10.

This resolves the contradiction recorded in `docs/02-traceability.md` §3.4: "Action 2 - Export
Sheets with Latest Revision" was the operative line; the uniform `RevP04` filenames were an
artefact of the example.

**Q3 — Naming separators.** Hyphens for sheets, underscores for models — deliberate or
incidental? Where, if anywhere, do project name and discipline appear? (§5.1)

**Q4 — Export root.** Sibling of the `.rvt`, fixed network path, or project parameter? (§5.2)

**Q5 — PDF settings.** Partly answered 2026-07-27: **one PDF per sheet**, confirming the
export strategy in ADR-003. Still open: colour vs. monochrome, raster quality, and whether to
hide crop regions, scope boxes and reference planes.

**Q9 — What is a "sheet series" in an HDR model?** ⚠ *New, blocks M1*
Q2's answer introduces the concept but not its mechanism. Four candidates:
 - **Sheet Collections** — native to Revit 2025, new in this release. Sheets are assigned to
   flexible named groupings via a `Sheet Collection` parameter, and Revit's own Export/Print
   dialog already exposes each collection as a filter toggle. Best fit for the term, and it
   arrives in exactly the version we standardised on.
 - **A print set** (`ViewSheetSet`) — the classic mechanism, works in every version, but is a
   manually curated list that drifts out of date.
 - **A custom shared parameter** on sheets, if HDR already has one.
 - **Sheet number prefix** convention (`A1xx` = plans, `A2xx` = elevations).
**Recommend Sheet Collections**, with print sets as a fallback for older models. We need to
know which HDR projects actually use before Extract can be written.

**Q10 — What happens to a sheet with no revision at all?** *New*
Per-sheet-latest makes this reachable: a brand-new sheet in the series with an empty revision
schedule has nothing to put in the `Rev{revision}` slot. Options are to skip it (current
behaviour, R8 warn), export it with the token omitted, or block the run.
**Recommend skip with a warning** — it is visible at G2 and the user can opt in.

**Q6 — Archive trigger.** Archive on every run, or only when a prior issue at a different
revision exists?

**Q7 — Worksharing workflow.** Run against local or central? Sync before export? Does
`close_model` relinquish?

**Q8 — Environment.** Can the pyRevit CPython 3 engine be approved in the HDR SOE? Not a
blocker (§8.2) but it determines whether the compatibility constraint stays permanent.

---

## 13. Definition of done for M1

Adapted from §9 of the pipeline context:

- [ ] Golden fixtures for three snapshots, including one adversarial (illegal chars, long
      paths, mixed revisions, placeholder sheets)
- [ ] Each of the four op kinds has a validator, an executor, and a negative test
- [ ] Dry-run produces a full ChangeSet and Verdict with zero files written
- [ ] Grep confirms `propose`/`resolve`/`check` do not import `Autodesk.Revit.DB`
- [ ] Runs clean against a workshared model on a deep network path
- [ ] Audit record written for every run, including cancelled and blocked ones
- [ ] G2 table renders 80+ rows without freezing
