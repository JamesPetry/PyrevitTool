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
    ElementId, FilteredElementCollector, NumericRevisionSettings, Revision,
    RevisionNumberingSequence, RevisionNumberType, Transaction,
    TransactionGroup, ViewSheet,
)
from System.Collections.Generic import List

from pyrevit import forms, revit

# How many sheets to touch, and how to split them.
SHEETS_TO_SEED = 8
OLDER_REVISION_SHEETS = 2   # left on the previous revision on purpose
UNREVISED_SHEETS = 1        # left with nothing, to exercise rule R8

REVISIONS = [
    {"description": "Planning Issue", "date": "01.06.26"},
    {"description": "Planning Submission", "date": "27.07.26"},
]

# HDR-style labels come from a numbering sequence, not from writing a string
# onto the revision. Prefix "P" with two digits starting at 3 gives P03, P04.
SEQUENCE_NAME = "HDR Planning"
SEQUENCE_PREFIX = "P"
SEQUENCE_START = 3
SEQUENCE_DIGITS = 2

# Collected API failures, printed at the end. Silent except-blocks are what
# hid the numbering problem through two runs.
DIAGNOSTICS = []


def make_numbering_sequence(doc):
    """Create a P03/P04-style numbering sequence, or None if Revit refuses.

    Setting revision.RevisionNumber directly does not work -- Revit owns the
    numbering and overwrites it, which is why the first attempt produced "2"
    and "3". Numbering is driven by a RevisionNumberingSequence instead.

    Returns the sequence's ElementId, or None. A failure here is not fatal:
    revisions still get Revit's default numbers and extract.py's sequence
    fallback keeps filenames valid, just less realistic.

    Failures are collected into DIAGNOSTICS rather than swallowed. Two attempts
    at this API have been refused silently; the exception text is what will
    actually identify the problem.
    """
    # Reuse ours if a previous run already made it -- this button is expected
    # to be pressed more than once, and duplicate sequences accumulate.
    try:
        for existing in FilteredElementCollector(doc).OfClass(
                RevisionNumberingSequence):
            if existing.Name == SEQUENCE_NAME:
                DIAGNOSTICS.append("reused existing sequence")
                return existing.Id
    except Exception as error:
        DIAGNOSTICS.append("collector failed: {0}: {1}".format(
            type(error).__name__, error))

    try:
        settings = NumericRevisionSettings()
    except Exception as error:
        DIAGNOSTICS.append("NumericRevisionSettings() failed: {0}: {1}".format(
            type(error).__name__, error))
        return None

    for attribute, value in (("Prefix", SEQUENCE_PREFIX),
                             ("StartNumber", SEQUENCE_START),
                             ("MinimumDigits", SEQUENCE_DIGITS)):
        try:
            setattr(settings, attribute, value)
        except Exception as error:
            DIAGNOSTICS.append("settings.{0} failed: {1}: {2}".format(
                attribute, type(error).__name__, error))

    try:
        sequence = RevisionNumberingSequence.CreateNumericSequence(
            doc, SEQUENCE_NAME, settings
        )
        DIAGNOSTICS.append("created sequence {0}".format(SEQUENCE_NAME))
        return sequence.Id
    except Exception as error:
        DIAGNOSTICS.append("CreateNumericSequence failed: {0}: {1}".format(
            type(error).__name__, error))
        return None


def apply_sequence(revision, sequence_id):
    """Point a revision at our numbering sequence. True if it took."""
    if sequence_id is None:
        return False
    ok = True
    try:
        revision.NumberType = RevisionNumberType.Numeric
    except Exception as error:
        DIAGNOSTICS.append("NumberType failed: {0}: {1}".format(
            type(error).__name__, error))
        ok = False
    try:
        revision.RevisionNumberingSequenceId = sequence_id
    except Exception as error:
        DIAGNOSTICS.append("RevisionNumberingSequenceId failed: {0}: {1}".format(
            type(error).__name__, error))
        ok = False
    return ok


def main():
    doc = revit.doc

    existing_revisions = len(list(
        FilteredElementCollector(doc).OfClass(Revision)))

    if not forms.alert(
        "This MODIFIES your model.\n\n"
        "It creates two revisions and assigns them to the first {0} sheets, so "
        "Export Issue has something real to work with.\n\n"
        "This model already has {1} revision(s). Each run adds two more -- "
        "Ctrl+Z after each run if you are experimenting.\n\n"
        "Only run this on a sample or scratch model.\n\n"
        "One Ctrl+Z undoes all of it.".format(
            SHEETS_TO_SEED, existing_revisions),
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
        sequence_id = make_numbering_sequence(doc)
        for spec in REVISIONS:
            revision = Revision.Create(doc)
            revision.Description = spec["description"]
            revision.RevisionDate = spec["date"]
            numbered = apply_sequence(revision, sequence_id)
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
        try:
            actual = revision.RevisionNumber or "(seq {0})".format(
                revision.SequenceNumber)
        except Exception:
            actual = "(seq {0})".format(revision.SequenceNumber)
        lines.append("  {0:<22} -> {1}{2}".format(
            spec["description"], actual,
            "" if numbered else "   [numbering sequence refused]"))

    lines.append("")
    for number, which in report:
        lines.append("  {0:<10} {1}".format(number, which))

    if DIAGNOSTICS:
        lines.append("")
        lines.append("Numbering diagnostics:")
        for note in DIAGNOSTICS:
            lines.append("  {0}".format(note))

    lines.append("")
    lines.append("Now run Probe Export to confirm, then Export Issue.")
    lines.append("Ctrl+Z undoes all of this in one step.")

    print("\n".join(lines))
    forms.alert("\n".join(lines[:2] + lines[-3:]), title="Seed Revisions")


main()
