# -*- coding: utf-8 -*-
# ! python3
"""Archive Superseded -- leave only the current issue in Exports.

Implements the Archive half of the client's folder structure. After exporting,
run this and Exports/ is left holding exactly what is current, with everything
it supersedes moved into a dated Archive folder:

    Exports/PDF/12345-A101-RevP04.pdf      <- stays
    Archive/26-07-22_Archive/
        12345-A101-RevP03.pdf              <- moved here

Supersession is worked out PER SHEET, because each sheet exports at its own
revision. A101 moving to P04 says nothing about whether A102 is still at P03.

Files are MOVED, never deleted, and only files whose names match the HDR
convention are touched -- anything else in the folder is left alone.

Same five stages and review gate as Export Issue.
"""

import datetime
import os

from pyrevit import forms, revit, script

from aecflow import archive, check, commit, contracts, extract, record, resolve
from aecflow import series as series_module
from aecflow.rules import archive_rules
from aecflow.gates import g1_scope, g2_diff, g3_summary

logger = script.get_logger()

DRY_RUN = False


def pick_root(doc):
    """Where to tidy. Defaults beside the model, same as Export Issue."""
    path = doc.PathName
    folder = os.path.dirname(path) if path else ""
    if not (folder and os.access(folder, os.W_OK)):
        folder = os.path.join(os.path.expanduser("~"), "Documents",
                              "HDR Exports")
    try:
        picked = forms.pick_folder(title="Which project folder?")
    except TypeError:
        picked = forms.pick_folder()
    except Exception:
        picked = None

    # Picking Exports/ instead of its parent is especially likely here, since
    # that is the folder the user was just looking at. Getting it wrong makes
    # the tool report "nothing superseded" while superseded files sit in plain
    # sight, which is worse than an error.
    return g1_scope.resolve_root(picked or folder)


def main():
    doc = revit.doc
    print("Archive Superseded starting...")

    root = pick_root(doc)
    if not root:
        return
    print("Project folder: {0}".format(root))

    # --- EXTRACT ---------------------------------------------------------
    # The model is read for its revision list, which ranks revisions far more
    # reliably than comparing labels as text.
    print("Reading model and export folder...")
    snapshot = extract.capture(doc, root, series_module.SHEET_COLLECTION, None)
    existing = snapshot["filesystem"].get("existing") or []
    print("  {0} existing export file(s)".format(len(existing)))

    if not existing:
        forms.alert(
            "No exported files found under:\n{0}\n\n"
            "Run Export Issue first.".format(
                os.path.join(root, "Exports")),
            title="Archive Superseded")
        return

    # --- PROPOSE ---------------------------------------------------------
    intent = archive.build(snapshot, datetime.datetime.now())
    print("  {0} superseded file(s) found".format(len(intent["ops"])))

    if not intent["ops"]:
        forms.alert(
            "Nothing is superseded -- Exports already holds only the current "
            "revision of each sheet.\n\nNothing to do.",
            title="Archive Superseded")
        return

    # --- RESOLVE / CHECK -------------------------------------------------
    changeset = resolve.bind(doc, snapshot, intent)
    verdict = check.evaluate(snapshot, changeset, archive_rules.ALL_RULES)
    print("  set verdict: {0}".format(verdict["set_verdict"]))

    # --- G2: review ------------------------------------------------------
    # Moving files is less reversible than writing them, so the same table
    # gates it and the default is still opt-in.
    selected = g2_diff.review(snapshot, changeset, verdict, dry_run=DRY_RUN)
    if selected is None:
        print("Cancelled at review.")
        return

    approved = check.approved_operations(changeset, verdict, set(selected))
    if not approved:
        forms.alert("Nothing selected.", title="Archive Superseded")
        return

    # --- COMMIT ----------------------------------------------------------
    with forms.ProgressBar(title="Archiving {value} of {max_value}",
                           cancellable=True) as bar:

        def progress(index, total, op):
            bar.update_progress(index + 1, total)
            return not bar.cancelled

        outcome = commit.apply(doc, approved, dry_run=DRY_RUN,
                               progress=progress)

    audit_path = record.write(root, snapshot, intent, changeset, verdict,
                              outcome)

    # --- G3 --------------------------------------------------------------
    written = len(outcome["written"])
    lines = [
        "{0} file(s) moved to Archive.".format(written),
        "",
        "Exports now holds only the current revision of each sheet.",
        "",
        "Files were MOVED, not deleted. To reverse this, move them back from:",
        "  {0}".format(os.path.join(root, "Archive")),
    ]
    if outcome["failed"]:
        lines.append("")
        lines.append("{0} failed:".format(len(outcome["failed"])))
        for failure in outcome["failed"][:8]:
            lines.append("  {0} -- {1}".format(
                os.path.basename(failure.get("dest_path") or "?"),
                failure.get("detail", "")))
    if audit_path:
        lines.append("")
        lines.append("Audit record: {0}".format(audit_path))

    print("\n".join(lines))
    forms.alert("\n".join(lines), title="Archive Superseded")


def run():
    try:
        main()
    except Exception:
        import traceback
        print("")
        print("FAILED:")
        print(traceback.format_exc())
        raise


run()
