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

from aecflow import check, commit, contracts, extract, propose, record, resolve
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
    """Alongside the .rvt until Q4 settles on something project-specific."""
    path = doc.PathName
    return os.path.dirname(path) if path else ""


def main():
    doc = revit.doc

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

    # A cheap pre-read of series names, so G1 can offer a real list before the
    # full Extract runs.
    preview = extract.capture(doc, root, SERIES_STRATEGY, SERIES_PARAM)
    available = series_module.available(preview["model"]["sheets"])

    # --- G1: scope -------------------------------------------------------
    scope = g1_scope.prompt(doc, available, root,
                            preview["model"].get("series_fallback"))
    if scope is None:
        return

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

    # --- G3: summary -----------------------------------------------------
    g3_summary.show(outcome, audit_path, scope["export_root"])


if __name__ == "__main__":
    main()
