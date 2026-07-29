# -*- coding: utf-8 -*-
# ! python3
"""Seed Revisions -- put test revisions onto sheets in a SAMPLE model.

WARNING: THIS ONE MODIFIES YOUR MODEL. Everything else in this toolset only
reads. Run it on a sample or scratch model, never on live project work.

WHY IT EXISTS
    Sample models ship with no revisions applied to sheets, so Export Issue
    correctly refuses to export anything from them -- there is no revision to
    build a filename from. Assigning revisions by hand means creating revision
    clouds on every sheet, which is tedious. This does it through the API
    instead, using the same call the "Revisions on Sheet" dialog uses.

WHAT IT CREATES
    Two revisions, then spreads them across the first few sheets so the model
    exercises the real selection rule:

        - most sheets on the newer revision
        - some deliberately left on the OLDER revision, which must export as a
          normal passing row, not a warning
        - one sheet left with NO revision, which must warn under rule R8

    That mix is the point. A model where every sheet is on the same revision
    cannot demonstrate the rule Ryann confirmed.

UNDO
    The whole thing is wrapped in a TransactionGroup and assimilated, so a
    single Ctrl+Z reverses it -- Hard Invariant 5, which the export tool cannot
    honour but this one can.
"""

from Autodesk.Revit.DB import (
    ElementId, FilteredElementCollector, Revision, RevisionNumberType,
    Transaction, TransactionGroup, ViewSheet,
)
from System.Collections.Generic import List

from pyrevit import forms, revit

# How many sheets to touch, and how to split them.
SHEETS_TO_SEED = 8
OLDER_REVISION_SHEETS = 2   # left on the previous revision on purpose
UNREVISED_SHEETS = 1        # left with nothing, to exercise rule R8

REVISIONS = [
    {"description": "Planning Issue", "date": "01.06.26", "number": "P03"},
    {"description": "Planning Submission", "date": "27.07.26", "number": "P04"},
]


def set_custom_number(doc, revision, wanted):
    """Try to give the revision a specific label like "P04".

    Revit's numbering is sequence-driven and not straightforward to force. If
    this fails the revision still works -- extract.py falls back to the
    sequence number, so filenames read Rev1/Rev2 instead of RevP03/RevP04.
    Reported either way rather than failing silently.
    """
    try:
        # "None" is a Python keyword, so this enum member cannot be written as
        # RevisionNumberType.None -- it has to be fetched by name.
        revision.NumberType = getattr(RevisionNumberType, "None")
    except Exception:
        pass
    for attribute in ("RevisionNumber", "Number"):
        try:
            setattr(revision, attribute, wanted)
            return True
        except Exception:
            continue
    return False


def main():
    doc = revit.doc

    if not forms.alert(
        "This MODIFIES your model.\n\n"
        "It creates two revisions and assigns them to the first {0} sheets, so "
        "Export Issue has something real to work with.\n\n"
        "Only run this on a sample or scratch model.\n\n"
        "One Ctrl+Z undoes all of it.".format(SHEETS_TO_SEED),
        title="Seed Revisions", ok=False, yes=True, no=True,
    ):
        return

    sheets = sorted(
        [s for s in FilteredElementCollector(doc).OfClass(ViewSheet)
         if not s.IsPlaceholder],
        key=lambda s: s.SheetNumber,
    )[:SHEETS_TO_SEED]

    if not sheets:
        forms.alert("No sheets in this model.", title="Seed Revisions")
        return

    report = []
    group = TransactionGroup(doc, "Seed test revisions")
    group.Start()
    try:
        # --- create the revisions ---
        created = []
        transaction = Transaction(doc, "Create revisions")
        transaction.Start()
        for spec in REVISIONS:
            revision = Revision.Create(doc)
            revision.Description = spec["description"]
            revision.RevisionDate = spec["date"]
            numbered = set_custom_number(doc, revision, spec["number"])
            created.append((revision, spec, numbered))
        transaction.Commit()

        older, newer = created[0][0], created[1][0]

        # --- assign them to sheets ---
        transaction = Transaction(doc, "Assign revisions to sheets")
        transaction.Start()
        for index, sheet in enumerate(sheets):
            if index < UNREVISED_SHEETS:
                report.append((sheet.SheetNumber, "(none -- will warn R8)"))
                continue

            use_older = index < UNREVISED_SHEETS + OLDER_REVISION_SHEETS
            revision = older if use_older else newer

            ids = List[ElementId]()
            ids.Add(revision.Id)
            sheet.SetAdditionalRevisionIds(ids)

            report.append((sheet.SheetNumber,
                           "older" if use_older else "newer"))
        transaction.Commit()

        group.Assimilate()
    except Exception as error:
        group.RollBack()
        forms.alert("Failed, nothing changed:\n\n{0}: {1}".format(
            type(error).__name__, error), title="Seed Revisions")
        raise

    lines = ["Seeded {0} sheets.".format(len(sheets)), ""]
    for revision, spec, numbered in created:
        actual = ""
        try:
            actual = revision.RevisionNumber or "(sequence {0})".format(
                revision.SequenceNumber)
        except Exception:
            actual = "(sequence {0})".format(revision.SequenceNumber)
        lines.append("  {0} -> {1}{2}".format(
            spec["number"], actual,
            "" if numbered else "   [custom number not accepted]"))

    lines.append("")
    for number, which in report:
        lines.append("  {0:<10} {1}".format(number, which))

    lines.append("")
    lines.append("Now run Probe Export to confirm, then Export Issue.")
    lines.append("Ctrl+Z undoes all of this in one step.")

    print("\n".join(lines))
    forms.alert("\n".join(lines[:2] + lines[-3:]), title="Seed Revisions")


main()
