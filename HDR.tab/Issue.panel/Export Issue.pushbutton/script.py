# -*- coding: utf-8 -*-
# ! python3
"""Export Issue -- Actions 1-4 of the HDR export pipeline.

Every sheet in the chosen series goes out at its OWN current revision as PDF,
DWG and IFC, named to the HDR convention and filed in the right folder.

This file is deliberately thin: five stage calls and three gates. Any logic
that accumulates here belongs in lib/aecflow/.

See docs/01-design-issue-export.md.
"""

import os

from pyrevit import forms, revit, script

from aecflow import (check, commit, contracts, extract, flows, propose, record,
                     resolve)
from aecflow import series as series_module
from aecflow.gates import g1_scope, g2_diff, g3_summary

logger = script.get_logger()

# Was True while export behaviour was unproven. The ADR-003 probe confirmed on
# 2026-07-29 that Combine=True with a single sheet honours FileName exactly, so
# real exports are now enabled. The G2 review table remains the gate: nothing is
# written without explicit per-row approval.
DRY_RUN = False

# Q9 is still open -- Sheet Collections is the Revit 2025 default.
SERIES_STRATEGY = series_module.SHEET_COLLECTION
SERIES_PARAM = None


def default_export_root(doc):
    """Alongside the .rvt until Q4 settles on something project-specific.

    Sample models live under Program Files, which is not writable, so the
    default falls back to Documents rather than offering a root that rule R6
    will only reject later.
    """
    path = doc.PathName
    folder = os.path.dirname(path) if path else ""
    if folder and os.access(folder, os.W_OK):
        return folder
    return os.path.join(os.path.expanduser("~"), "Documents", "HDR Exports")


def main():
    doc = revit.doc
    print("Export Issue starting...")
    print("Model: {0}".format(doc.Title))

    # Fail fast, before any work, rather than at commit time.
    if doc.IsReadOnly:
        forms.alert("This model is read-only. Open it for editing and retry.",
                    title="Export Issue")
        return
    if not doc.PathName:
        forms.alert("Save the model before exporting -- the export folder is "
                    "derived from its location.", title="Export Issue")
        return

    root = default_export_root(doc)
    print("Export root: {0}".format(root))

    # A cheap pre-read of series names, so G1 can offer a real list before the
    # full Extract runs.
    print("Reading model...")
    preview = extract.capture(doc, root, SERIES_STRATEGY, SERIES_PARAM)
    print("  {0} sheets, {1} revisions".format(
        len(preview["model"]["sheets"]), len(preview["model"]["revisions"])))

    available = series_module.available(preview["model"]["sheets"])
    print("  series found: {0}".format(
        [s if s else "(none)" for s in available]))
    if preview["model"].get("series_fallback"):
        print("  (Sheet Collections empty -- grouped by sheet number prefix)")
    print("")
    print("A dialog should now be open. If you cannot see it, check behind")
    print("this window (Alt+Tab).")

    # --- G1: scope -------------------------------------------------------
    scope = g1_scope.prompt(doc, available, root,
                            preview["model"].get("series_fallback"))
    if scope is None:
        print("Cancelled at scope.")
        return
    print("Scope: series={0} formats={1}".format(
        scope["series"], scope["formats"]))

    # --- EXTRACT ---------------------------------------------------------
    snapshot = (preview if scope["export_root"] == root
                else extract.capture(doc, scope["export_root"],
                                     SERIES_STRATEGY, SERIES_PARAM))

    # --- PROPOSE ---------------------------------------------------------
    intent = propose.build(snapshot, scope)

    # --- RESOLVE ---------------------------------------------------------
    changeset = resolve.bind(doc, snapshot, intent)

    # --- CHECK -----------------------------------------------------------
    verdict = check.evaluate(snapshot, changeset)
    print("Proposed {0} file(s); set verdict: {1}".format(
        len(changeset["operations"]), verdict["set_verdict"]))

    # --- G2: review ------------------------------------------------------
    selected = g2_diff.review(snapshot, changeset, verdict, dry_run=DRY_RUN)
    if selected is None:
        record.write(scope["export_root"], snapshot, intent, changeset, verdict,
                     {"status": "cancelled_at_review", "written": [],
                      "failed": [], "skipped": [], "dry_run": DRY_RUN,
                      "attempted": 0})
        return

    approved = check.approved_operations(changeset, verdict, set(selected))
    if not approved:
        forms.alert("Nothing selected.", title="Export Issue")
        return

    # --- COMMIT ----------------------------------------------------------
    # The only stage that writes. No transaction is opened -- see design doc
    # 7.1 on why Invariant 5 is scoped rather than claimed.
    with forms.ProgressBar(title="Exporting {value} of {max_value}",
                           cancellable=True) as bar:

        def progress(index, total, op):
            bar.update_progress(index + 1, total)
            return not bar.cancelled

        outcome = commit.apply(doc, approved, dry_run=DRY_RUN, progress=progress)

    # --- RECORD ----------------------------------------------------------
    audit_path = record.write(scope["export_root"], snapshot, intent,
                              changeset, verdict, outcome)

    # --- ARCHIVE (optional, ticked at G1) --------------------------------
    archived = None
    if scope.get("archive_after") and outcome["written"]:
        archived = archive_superseded(doc, scope["export_root"])

    # --- G3: summary -----------------------------------------------------
    g3_summary.show(outcome, audit_path, scope["export_root"], archived)


def archive_superseded(doc, root):
    """Tidy Exports after a successful export. Returns an outcome or None.

    The review table is shown only when Check flags something. Ticking the
    option at G1 is the user's consent for the clean case, and a second table
    mid-flow would make the "one button" pointless. Anything flagged still
    stops for a decision -- automatic when it is safe, gated when it is not.

    Files are moved rather than deleted, and G3 says where they went, so a
    silent clean run stays reversible.
    """
    print("")
    print("Archiving superseded files...")

    snapshot, intent, changeset, verdict = flows.plan_archive(doc, root)
    if not changeset["operations"]:
        print("  nothing superseded")
        return None

    print("  {0} file(s) superseded; verdict: {1}".format(
        len(changeset["operations"]), verdict["set_verdict"]))

    if verdict["set_verdict"] == contracts.PASS:
        approved = check.approved_operations(changeset, verdict)
    else:
        selected = g2_diff.review(snapshot, changeset, verdict, dry_run=DRY_RUN)
        if selected is None:
            print("  archive cancelled -- exports are untouched")
            return None
        approved = check.approved_operations(changeset, verdict, set(selected))

    if not approved:
        return None

    with forms.ProgressBar(title="Archiving {value} of {max_value}",
                           cancellable=True) as bar:

        def progress(index, total, op):
            bar.update_progress(index + 1, total)
            return not bar.cancelled

        result = commit.apply(doc, approved, dry_run=DRY_RUN, progress=progress)

    record.write(root, snapshot, intent, changeset, verdict, result)
    print("  {0} file(s) moved to Archive".format(len(result["written"])))
    return result


def run():
    """Entry point with reporting, so a silent failure cannot look like a
    blank window."""
    try:
        main()
    except Exception:
        import traceback
        print("")
        print("FAILED:")
        print(traceback.format_exc())
        raise


run()
