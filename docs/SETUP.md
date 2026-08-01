# Setup — running these tools in Revit

For anyone who has not used Python inside Revit before. About 15 minutes,
most of it waiting for an installer.

You do not need to know Python to run these. pyRevit turns a folder of scripts
into ribbon buttons; you click them like any other Revit command.

---

## 1. Install pyRevit

Download the latest installer from
<https://github.com/pyrevitlabs/pyRevit/releases> — the file named
`pyRevit_<version>_signed.exe`. Run it with **Revit closed** and accept the
defaults.

> **If HDR IT blocks the installer**, that is the constraint behind ADR-002 and
> worth knowing about early. Nothing in this toolset needs network access or
> extra Python packages, which should make it an easier approval than most.

Open Revit. You should see a **pyRevit** tab on the ribbon. If you do not, see
Troubleshooting below.

---

## 2. Install the extension

**The quick way.** pyRevit ships a command line tool that does the download and
the wiring in one step. Open a Command Prompt and run:

```
pyrevit extend ui HDR https://github.com/JamesPetry/PyrevitTool.git
pyrevit reload
```

That is the whole of steps 2 and 3 — skip to step 4. It also means
`pyrevit extensions update HDR` picks up later changes.

> If `pyrevit` is not a recognised command, the CLI was not added to your PATH.
> Use the manual route below, or reinstall pyRevit with the CLI option ticked.

**The manual way.** Clone the repository — and note the folder name, it
matters:

```
git clone https://github.com/JamesPetry/PyrevitTool.git HDR.extension
```

…or download the ZIP from GitHub (**Code → Download ZIP**), extract it, and
**rename the extracted folder to `HDR.extension`**. pyRevit identifies
extensions by that `.extension` suffix and will not see the folder without it.

Put it somewhere that stays put — `C:\Dev\` or your Documents folder, not
Downloads or a temp folder. You should end up with something like:

```
C:\Dev\                     <-- this is the path pyRevit needs
└── HDR.extension\
    ├── HDR.tab\
    ├── lib\
    └── extension.json
```

---

## 3. Point pyRevit at the extension

Manual route only — the CLI in step 2 already did this.

In Revit:

1. **pyRevit tab → Settings**
2. Scroll to **Custom Extension Directories**
3. Click **+** and select the **parent** folder — `C:\Dev`, the folder that
   *contains* `HDR.extension`, not `HDR.extension` itself
4. **Save Settings and Reload**

An **HDR** tab should appear with two panels and four buttons:

| Panel | Button | What it is |
|---|---|---|
| Issue | Export Issue | The real tool. Writes files once you approve the review table. |
| Issue | Archive Superseded | Moves superseded exports into a dated Archive folder. Never deletes. |
| Dev tools | Probe Export | Read-only diagnostic, described below. Safe on any model. |
| Dev tools | Seed Revisions | **Modifies the model.** Sample and scratch models only. |

Everything on the Issue panel only ever *reads* your model — the files it
writes go to disk, not into the project. `Seed Revisions` is the single
exception in the suite, which is why it sits on the Dev panel behind its own
confirmation dialog.

---

## 4. Run the probe

Open a **test project** — ideally workshared, with a real revision history, on
a normal network path. Then:

**HDR tab → Dev → Probe Export**

A pyRevit output window opens and fills with a report. It takes one to three
minutes depending on how many sheets the model has.

**What it does:** reads your model and writes a handful of test PDFs to
`%TEMP%\aecflow_spike`. It opens no transaction, modifies nothing, and never
writes to your project folders. It is safe on a live workshared model.

**When it finishes:** use the copy button at the top of the output window and
send the whole report back. Every section answers something the code currently
guesses at:

- whether this project uses Revit 2025 Sheet Collections, which is what "sheet
  series" should map to
- whether the revision properties the code reads are the right ones
- **whether Revit honours an exact export filename** — the decision the whole
  export stage rests on
- how long per-sheet export takes against one batch call

Delete `%TEMP%\aecflow_spike` afterwards.

---

## 5. Which folder do I pick?

When Export Issue asks where to export, **pick the project folder — not an
Exports folder.** The tool builds the structure underneath whatever you give it:

```
C:\Projects\12345\          <-- PICK THIS
├── Exports\                  <-- created for you
│   ├── PDF\  DWG\  IFC\  RVT\
└── Archive\                  <-- created for you
    └── 26-07-31_Archive\
```

Picking the `Exports` folder itself gives you `Exports\Exports\PDF`. The tool
now spots this and offers to use the parent, but it is worth knowing.

**Use the same folder every time for a given project.** Archiving looks for
`<folder>\Exports` and writes `<folder>\Archive`. Point it somewhere different
on the next run and it will report "nothing superseded" while the superseded
files sit exactly where you left them.

---

## 6. Export Issue

`Export Issue` writes real files. Nothing is written until you approve the
review table it shows you first — that table is the last point at which you can
back out, and rows it has flagged are never included unless you ask for them.

Two things to know before your first real run:

- **PDF is the only format proven against a live model.** DWG, IFC and detached
  RVT are implemented but have never produced a file. Try them on a test
  project before an issue deadline depends on them.
- **Exports are not undoable with Ctrl+Z.** The tool never touches the model,
  so Revit has nothing to undo. To reverse a run, delete the export folder —
  the summary screen names it.

[`KNOWN-LIMITATIONS.md`](KNOWN-LIMITATIONS.md) is the full list, and it is
worth ten minutes before you rely on this.

---

## Troubleshooting

**No pyRevit tab after installing.** Revit blocks add-ins it does not trust.
Check **Add-Ins → Add-in Manager**, or look for a "third-party add-in" security
prompt on startup and allow it. A reinstall with Revit fully closed fixes most
cases.

**No HDR tab after adding the directory.** Two causes, both common.

*Wrong folder level.* pyRevit wants the folder *containing* `HDR.extension`.
If you selected `HDR.extension` itself, go back one level. Then **Save Settings
and Reload**.

*Folder not named `HDR.extension`.* A plain `git clone` or a GitHub ZIP gives
you a folder called `PyrevitTool` or `PyrevitTool-main`. pyRevit finds
extensions by the `.extension` suffix and ignores anything else. Rename the
folder to `HDR.extension` and reload. You should see `HDR.tab` and `lib`
directly inside it — if instead you see another folder before those, you picked
one level too shallow.

**"Probe Export" errors immediately.** Send the error text — it is as useful as
a successful run. The most likely cause is an API difference between Revit
versions; these tools target **Revit 2025**.

**Output window is blank.** The script prints as it goes, so a blank window
usually means it failed before the first section. Check pyRevit's output for a
traceback, and send that.

---

## Reloading after a code change

`pyRevit tab → Reload`. No need to restart Revit unless the folder structure
itself changed.
