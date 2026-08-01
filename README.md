# HDR pyRevit Tool Suite

A pyRevit extension for HDR, built on the AECFlow pipeline architecture.
**Revit 2025.**

> **Status: working end to end on a sample model.** All five pipeline stages,
> both rule sets, four op executors and three gates are implemented, with 155
> tests passing without Revit. **PDF export is verified against a live Revit
> 2025 model**, including exact filenames and per-sheet revision selection —
> the question [ADR-003](docs/adr/ADR-003-one-export-call-per-file.md) was
> opened to answer.
>
> **DWG, IFC and detached RVT export have never produced a file**, nothing has
> been run on a workshared model or over a network path, and nobody but the
> author has installed it. `DRY_RUN = False` — the buttons write for real once
> you approve the review table.
>
> **Read [`docs/KNOWN-LIMITATIONS.md`](docs/KNOWN-LIMITATIONS.md) before you
> point this at project work.** It is the honest inventory of what has and has
> not been proven.

---

## First deliverable — `Export Issue`

At issue time, put every sheet on a chosen revision into the right folder,
named to the HDR standard, with nothing overwritten.

```
PROJECT/
├── Exports/
│   ├── PDF/  12345-A101-RevP04.pdf
│   ├── DWG/  12345-A101-RevP04.dwg
│   ├── IFC/  12345_Model_RevP04.ifc
│   └── RVT/  12345_Model_RevP04.rvt
└── Archive/
    └── 26-07-22_Archive/
```

Ryann's nine actions are split across separate buttons rather than one, so the
reversible half can ship without waiting on the destructive half:

| Button | Actions | Risk | State |
|---|---|---|---|
| `Export Issue` | 1–4 — folders, PDF, DWG, IFC, detached RVT | Writes new files only | **Shipped** |
| `Archive Superseded` | 5 — supersede into a dated Archive folder | Moves files, never deletes | **Shipped** |
| `Close Out` | 6–9 — purge, audit, save-as, close | Mutates the model | Not built |

Nothing shipped so far modifies your model. The two buttons above read it and
write to disk; only the unbuilt `Close Out` half would change the model itself
(along with the `Seed Revisions` dev tool, which is for scratch models).

---

## Architecture

Five deterministic stages plus a cross-cutting audit record:

```
EXTRACT ──▶ PROPOSE ──▶ RESOLVE ──▶ CHECK ──▶ COMMIT
Snapshot     Intent     ChangeSet   Verdict   files on disk
   └────────────┴───────────┴──────────┴──────────┘
                      RECORD
```

Three properties are worth knowing before reading the code:

- **No probabilistic stage in v1.** `PROPOSE` is a pure rules engine — no LLM,
  no network, no third-party packages. The seam stays open if that changes.
- **Stages 2–4 never import the Revit API.** All model data arrives via the
  Snapshot, which makes the interesting logic testable without Revit.
- **Dry-run is the default.** A full ChangeSet and Verdict are produced with
  zero writes, and nothing commits without passing the G2 review table.

Full rationale, op vocabulary, and Check rules:
[`docs/01-design-issue-export.md`](docs/01-design-issue-export.md).
Fixed architectural context:
[`docs/00-aecflow-pipeline-context.md`](docs/00-aecflow-pipeline-context.md).

---

## Layout

**The repository root is the extension.** pyRevit's installer clones a repo
straight into `<name>.extension/`, so `HDR.tab/` and `lib/` sit at the top
level rather than under a `HDR.extension/` folder.

```
PyrevitTool/                       # cloned as HDR.extension/
├── extension.json                 # manifest for the Extensions Manager
├── HDR.tab/
│   ├── Issue.panel/               # the workflow
│   │   ├── Export Issue.pushbutton/
│   │   │   ├── script.py          # thin: 5 stage calls + 3 gates, no logic
│   │   │   ├── bundle.yaml
│   │   │   └── icon.png
│   │   └── Archive Superseded.pushbutton/
│   └── Dev.panel/                 # diagnostics, not the workflow
│       ├── Probe Export.pushbutton/       # read-only
│       └── Seed Revisions.pushbutton/     # MODIFIES THE MODEL, scratch only
└── lib/                           # pyRevit auto-adds this to sys.path
    └── aecflow/
        ├── contracts.py           # Snapshot, Intent, Op, ChangeSet, Verdict
        ├── naming.py              # every filename decision, one place
        ├── extract.py             # [D] the only Revit reads
        ├── propose.py             # [P] rules engine in v1
        ├── resolve.py             # [D] bind UniqueIds, absolutise paths
        ├── check.py               # [D] rules over (Snapshot, ChangeSet)
        ├── commit.py              # [D] the only writes
        ├── record.py              # audit persistence
        ├── rules/                 # one rule per file, pure functions
        ├── ops/                   # validator + executor per op kind
        └── gates/                 # G1 scope, G2 diff, G3 summary
docs/
├── 00-aecflow-pipeline-context.md
├── 01-design-issue-export.md
├── KNOWN-LIMITATIONS.md
├── SETUP.md
└── adr/
tests/
tools/                             # maintenance scripts, not shipped logic
```

pyRevit only looks at folders whose names carry a bundle postfix, so `docs/`,
`tests/` and `tools/` come along in the clone and are ignored at load time.

`HDR.tab` is branding; `lib/aecflow/` is client-neutral architecture.

---

## Tests

The naming convention and the pipeline contracts run without Revit — that is
the point of keeping them pure.

```bash
python -m pytest tests/ -q      # 155 passed
```

Only Extract and Commit need Revit, and both are thin.

Still outstanding: golden-file tests over captured Snapshot fixtures, which
would pin the whole chain against a recorded real model rather than a
hand-built one.

```
tests/fixtures/<case>/snapshot.json → propose → intent.json
                                    → resolve → changeset.json
                                    → check   → verdict.json
```

---

## Installation

Requires **pyRevit 4.8+** and **Revit 2025**. No network access, no third-party
Python packages.

**With the pyRevit CLI** — clones the repo and keeps it updatable with
`pyrevit extensions update HDR`:

```
pyrevit extend ui HDR https://github.com/JamesPetry/PyrevitTool.git
pyrevit reload
```

The extension name `HDR` sets the clone folder — pyRevit creates
`%APPDATA%\pyRevit\Extensions\HDR.extension\`, which is why this repository's
root *is* the extension.

**Without the CLI** — clone into a correctly named folder, then point pyRevit
at its parent:

```
git clone https://github.com/JamesPetry/PyrevitTool.git HDR.extension
```

Then **pyRevit → Settings → Custom Extension Directories → +**, select the
folder *containing* `HDR.extension`, and **Save Settings and Reload**.

Step-by-step, for anyone who has not run Python in Revit before:
[`docs/SETUP.md`](docs/SETUP.md).

---

## Open questions

See §12 of the design doc. How the issue revision selects sheets is settled —
each sheet exports at its own current revision, confirmed by Ryann and verified
on a live run. What "sheet creation" means (files vs. `ViewSheet` elements) is
still open, as is whether Sheet Collections will be populated or whether the
sheet-number prefix fallback is the intended grouping (Q9).

---

## Licence

Proprietary — copyright HDR, all rights reserved. Being able to read this
repository is not permission to use it; see [`LICENSE`](LICENSE).
