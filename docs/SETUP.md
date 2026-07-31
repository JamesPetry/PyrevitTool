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

## 2. Get this repository onto your machine

Either clone it:

```
git clone https://github.com/JamesPetry/PyrevitTool.git
```

…or download the ZIP from GitHub (**Code → Download ZIP**) and extract it.

Note the folder path. It needs to be somewhere that stays put — `C:\Dev\` or
your Documents folder, not Downloads or a temp folder.

The folder you want is the one **containing** `HDR.extension`, for example
`C:\Dev\PyrevitTool`.

---

## 3. Point pyRevit at the extension

In Revit:

1. **pyRevit tab → Settings**
2. Scroll to **Custom Extension Directories**
3. Click **+** and select the folder from step 2 — `C:\Dev\PyrevitTool`
   (the folder that *contains* `HDR.extension`, not `HDR.extension` itself)
4. **Save Settings and Reload**

An **HDR** tab should appear with two panels:

| Panel | Button | What it is |
|---|---|---|
| Issue | Export Issue | The real tool. Currently dry-run only. |
| Dev | Probe Export | The diagnostic described below. |

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

Once the probe results are in, `Export Issue` becomes usable. It is currently
**dry-run only** — it will show you every file it would create and write
nothing. That default flips once the probe confirms export behaviour.

---

## Troubleshooting

**No pyRevit tab after installing.** Revit blocks add-ins it does not trust.
Check **Add-Ins → Add-in Manager**, or look for a "third-party add-in" security
prompt on startup and allow it. A reinstall with Revit fully closed fixes most
cases.

**No HDR tab after adding the directory.** Almost always the wrong folder
level. pyRevit wants the folder *containing* `HDR.extension`. If you selected
`HDR.extension` itself, go back one level. Then **Save Settings and Reload**.

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
