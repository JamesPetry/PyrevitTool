# HDR pyRevit Tool Suite

A pyRevit extension for HDR, built on the AECFlow pipeline architecture.
**Revit 2025.**

> **Status: M1 built, unverified against Revit.** All five pipeline stages,
> both rule sets, four op executors and three gates are implemented, with 86
> tests passing without Revit. Nothing has yet been run inside Revit — the
> export executors are written from the API documentation and are **unproven
> until the spike in [ADR-003](docs/adr/ADR-003-one-export-call-per-file.md)
> has run.** `DRY_RUN = True` is the default until then.

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

Ryann's nine actions are split across **two** buttons rather than one, so the
reversible half can ship without waiting on the destructive half:

| Button | Actions | Risk | Milestone |
|---|---|---|---|
| `Export Issue` | 1–4 — folders, PDF, DWG, IFC, detached RVT | Writes new files only | **M1–M2** |
| `Archive & Close` | 5–9 — archive, purge, audit, save-as, close | Moves files, mutates the model | M3 |

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

```
HDR.extension/
├── HDR.tab/
│   └── Issue.panel/
│       └── Export Issue.pushbutton/
│           ├── script.py          # thin: 5 stage calls + 3 gates, no logic
│           └── bundle.yaml
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
└── adr/
tests/
```

`HDR.tab` is branding; `lib/aecflow/` is client-neutral architecture.

---

## Tests

The naming convention and the pipeline contracts run without Revit — that is
the point of keeping them pure.

```bash
python -m pytest tests/ -q
```

Golden-file tests over captured Snapshot fixtures follow in M1:

```
tests/fixtures/<case>/snapshot.json → propose → intent.json
                                    → resolve → changeset.json
                                    → check   → verdict.json
```

Only Extract and Commit need Revit, and both are thin.

---

## Installation (once M1 lands)

```
pyrevit extend ui HDR <repo-url> --dest="%APPDATA%\pyRevit\Extensions"
pyrevit reload
```

---

## Open questions

Eight items need Ryann's answer before M1 closes — the two blocking ones are
what "sheet creation" means (files vs. `ViewSheet` elements) and how the issue
revision selects sheets. See §12 of the design doc.
