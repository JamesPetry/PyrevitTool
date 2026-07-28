# -*- coding: utf-8 -*-
"""Export probe -- answers every unverified assumption in the M1 build.

WHAT IT DOES
    Reads your model and writes a handful of test PDFs to a temp folder.
    It does NOT modify the model, does not touch your project folders, and
    opens no transaction. Safe to run on a live workshared model.

WHERE TO RUN IT
    RevitPythonShell, or pyRevit's Python console. Paste the whole file and
    run. Works under both IronPython 2.7 and CPython 3.

WHAT TO SEND BACK
    All of the printed output. Every section is a question the code currently
    guesses at.

Roughly 1-3 minutes depending on sheet count.
"""

import os
import shutil
import tempfile
import time

from Autodesk.Revit.DB import (
    ElementId, FilteredElementCollector, PDFExportOptions, Revision, ViewSheet,
)
from System.Collections.Generic import List

# How many sheets to use for the timing comparison.
SAMPLE = 10

# The parameter name aecflow/series.py assumes for Revit 2025 Sheet Collections.
SHEET_COLLECTION_PARAM = "Sheet Collection"


def get_doc():
    try:
        return __revit__.ActiveUIDocument.Document  # RevitPythonShell
    except NameError:
        from pyrevit import revit                    # pyRevit console
        return revit.doc


def rule(title):
    print("")
    print("=" * 68)
    print(title)
    print("=" * 68)


def main():
    doc = get_doc()
    workdir = os.path.join(tempfile.gettempdir(), "aecflow_spike")
    if os.path.isdir(workdir):
        shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)

    rule("0. ENVIRONMENT")
    app = doc.Application
    print("Revit          : {0}  (build {1})".format(
        app.VersionNumber, app.VersionBuild))
    print("Model          : {0}".format(doc.Title))
    print("Workshared     : {0}".format(doc.IsWorkshared))
    print("Read-only      : {0}".format(doc.IsReadOnly))
    print("Path length    : {0} chars".format(len(doc.PathName or "")))
    print("Temp workdir   : {0}".format(workdir))

    sheets = sorted(
        [s for s in FilteredElementCollector(doc).OfClass(ViewSheet)
         if not s.IsPlaceholder],
        key=lambda s: s.SheetNumber,
    )
    print("Sheets (real)  : {0}".format(len(sheets)))
    if not sheets:
        print("\nNo sheets. Run this on a model with sheets.")
        return

    # ---------------------------------------------------------------- Q9
    rule("1. SHEET SERIES  (design doc Q9)")
    print("Does this model use Revit 2025 Sheet Collections?")
    print("")
    values = {}
    param_found = False
    for sheet in sheets:
        try:
            p = sheet.LookupParameter(SHEET_COLLECTION_PARAM)
        except Exception as err:
            print("  LookupParameter raised: {0}".format(err))
            break
        if p is None:
            continue
        param_found = True
        try:
            value = (p.AsString() or p.AsValueString() or "").strip()
        except Exception:
            value = "<unreadable>"
        values[value] = values.get(value, 0) + 1

    if not param_found:
        print("  '{0}' parameter NOT FOUND on any sheet.".format(
            SHEET_COLLECTION_PARAM))
        print("  -> series.py needs a different strategy. Prefixes present:")
        prefixes = {}
        for sheet in sheets:
            head = "".join(c for c in sheet.SheetNumber[:3] if c.isalpha())
            prefixes[head] = prefixes.get(head, 0) + 1
        for key in sorted(prefixes):
            print("       {0!r:12} {1} sheets".format(key, prefixes[key]))
    else:
        print("  Parameter found. Values in use:")
        for key in sorted(values, key=lambda k: -values[k]):
            print("       {0!r:30} {1} sheets".format(key or "(blank)",
                                                      values[key]))

    # ------------------------------------------------------------ revisions
    rule("2. REVISIONS  (extract.py assumptions)")
    revisions = list(FilteredElementCollector(doc).OfClass(Revision))
    print("Revisions in model: {0}".format(len(revisions)))
    print("")
    print("Checking that RevisionNumber is what belongs in a filename:")
    for revision in sorted(revisions, key=lambda r: r.SequenceNumber)[:6]:
        try:
            number = revision.RevisionNumber
        except AttributeError:
            number = "<NO RevisionNumber PROPERTY>"
        print("   seq {0:<4} RevisionNumber={1!r:12} date={2!r}".format(
            revision.SequenceNumber, number, revision.RevisionDate))

    print("")
    print("Checking GetCurrentRevision() on the first 8 sheets:")
    for sheet in sheets[:8]:
        try:
            rev_id = sheet.GetCurrentRevision()
            if rev_id is None or rev_id.IntegerValue < 0:
                label = "(none)"
            else:
                rev = doc.GetElement(rev_id)
                label = rev.RevisionNumber if rev else "(missing)"
        except Exception as err:
            label = "ERROR: {0}".format(err)
        try:
            views = len(list(sheet.GetAllPlacedViews()))
        except Exception:
            views = "?"
        print("   {0:<10} current={1!r:8} placed_views={2}".format(
            sheet.SheetNumber, label, views))

    # ------------------------------------------------------------- ADR-003
    rule("3. FILENAME CONTROL  (ADR-003 -- the critical one)")
    target = sheets[0]
    wanted = "12345-{0}-RevP04".format(
        target.SheetNumber.replace("/", "-").replace("\\", "-"))
    print("Exporting ONE sheet with Combine=True, FileName={0!r}".format(wanted))
    print("Sheet: {0} - {1}".format(target.SheetNumber, target.Name))

    single_dir = os.path.join(workdir, "single")
    os.makedirs(single_dir)

    options = PDFExportOptions()
    options.Combine = True
    options.FileName = wanted

    views = List[ElementId]()
    views.Add(target.Id)

    started = time.time()
    try:
        doc.Export(single_dir, views, options)
        export_error = None
    except Exception as err:
        export_error = "{0}: {1}".format(type(err).__name__, err)
    elapsed = time.time() - started

    produced = os.listdir(single_dir)
    print("")
    print("  Export call     : {0}".format(export_error or "OK"))
    print("  Took            : {0:.2f}s".format(elapsed))
    print("  Files produced  : {0}".format(produced))
    if produced == [wanted + ".pdf"]:
        print("  RESULT          : EXACT MATCH -- ADR-003 approach confirmed")
    elif produced:
        print("  RESULT          : MISMATCH -- wanted {0!r}".format(
            wanted + ".pdf"))
        print("                    Revit chose its own name; commit.py needs")
        print("                    an export-then-rename step.")
    else:
        print("  RESULT          : NOTHING WRITTEN -- investigate before M2")

    # --------------------------------------------------------------- timing
    rule("4. TIMING  (per-sheet vs batch)")
    sample = sheets[:SAMPLE]
    print("Sample size: {0} sheets".format(len(sample)))

    per_dir = os.path.join(workdir, "per_sheet")
    os.makedirs(per_dir)
    started = time.time()
    per_sheet_ok = 0
    for index, sheet in enumerate(sample):
        opts = PDFExportOptions()
        opts.Combine = True
        opts.FileName = "per-{0:03d}".format(index)
        ids = List[ElementId]()
        ids.Add(sheet.Id)
        try:
            doc.Export(per_dir, ids, opts)
            per_sheet_ok += 1
        except Exception:
            pass
    per_sheet_time = time.time() - started

    batch_dir = os.path.join(workdir, "batch")
    os.makedirs(batch_dir)
    opts = PDFExportOptions()
    opts.Combine = False          # Revit names these itself, via NamingRule
    ids = List[ElementId]()
    for sheet in sample:
        ids.Add(sheet.Id)
    started = time.time()
    try:
        doc.Export(batch_dir, ids, opts)
        batch_error = None
    except Exception as err:
        batch_error = "{0}: {1}".format(type(err).__name__, err)
    batch_time = time.time() - started

    print("")
    print("  Per-sheet ({0} calls) : {1:.1f}s  ({2} succeeded)".format(
        len(sample), per_sheet_time, per_sheet_ok))
    print("  Batch (1 call)       : {0:.1f}s  {1}".format(
        batch_time, batch_error or ""))
    if batch_time > 0:
        print("  Per-sheet is {0:.1f}x slower".format(per_sheet_time / batch_time))
    if per_sheet_time > 0 and len(sample):
        each = per_sheet_time / len(sample)
        print("  Extrapolated to 64 sheets: {0:.0f}s per-sheet".format(each * 64))

    print("")
    print("  Names Revit chose in batch mode:")
    for name in sorted(os.listdir(batch_dir))[:5]:
        print("       {0}".format(name))

    rule("DONE")
    print("Send back everything above.")
    print("Test files are in {0} -- delete when you're done.".format(workdir))
    print("Your model was not modified.")


main()
