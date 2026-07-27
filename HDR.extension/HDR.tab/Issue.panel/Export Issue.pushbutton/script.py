# -*- coding: utf-8 -*-
# ! python3
"""Export Issue -- Actions 1-4 of the HDR export pipeline.

Creates the export folder tree and writes PDF / DWG / IFC / detached RVT for
every sheet on the chosen issue revision, named to the HDR convention.

This file is deliberately thin: five stage calls and three gates. Any logic
that accumulates here belongs in lib/aecflow/. See docs/01-design-issue-export.md.

STATUS: skeleton. Stage bodies land in M1.
"""

from pyrevit import revit, script

from aecflow import extract, propose, resolve, check, commit, record
from aecflow import contracts
from aecflow.gates import g1_scope, g2_diff, g3_summary

logger = script.get_logger()

# Hard Invariant 4: dry-run is the default in development.
DRY_RUN = True


def main():
    doc = revit.doc

    # Fail fast, before doing any work, rather than at commit time.
    if doc.IsReadOnly:
        script.exit("This model is read-only. Open it for editing and retry.")

    # --- G1: scope -------------------------------------------------------
    # Which revision, which formats, which export root. Nothing is read from
    # the model until the user has confirmed what will be looked at.
    scope = g1_scope.prompt(doc)
    if scope is None:
        return

    # --- EXTRACT [D] -----------------------------------------------------
    # The only stage that touches the Revit API for reads. Everything
    # downstream sees the Snapshot and nothing else.
    snapshot = extract.capture(doc, scope)

    # --- PROPOSE [D] -----------------------------------------------------
    # Deterministic rules engine in v1: select sheets on the issue revision,
    # compute filenames, route to folders. No network call, no transaction.
    intent = propose.build(snapshot, scope)

    # --- RESOLVE [D] -----------------------------------------------------
    # Bind UniqueIds against the live document, absolutise paths, coerce
    # export options. Anything not fully bindable is dropped with a reason.
    changeset = resolve.bind(doc, snapshot, intent)

    # --- CHECK [D] -------------------------------------------------------
    # Pure rules over (snapshot, changeset). A single block blocks the set.
    verdict = check.evaluate(snapshot, changeset)

    # --- G2: diff review -------------------------------------------------
    # The primary gate. Nothing is written without passing through this table.
    approved = g2_diff.review(snapshot, changeset, verdict, dry_run=DRY_RUN)
    if approved is None:
        record.write(snapshot, intent, changeset, verdict, outcome="cancelled")
        return

    if verdict["set_verdict"] == contracts.BLOCK:
        record.write(snapshot, intent, changeset, verdict, outcome="blocked")
        script.exit("Blocked by Check. See the review table for the failing rules.")

    # --- COMMIT [D] ------------------------------------------------------
    # The only stage that writes anything. Export Issue writes files and
    # opens no transaction -- see design doc section 7.1 on Invariant 5.
    outcome = commit.apply(doc, approved, dry_run=DRY_RUN)

    # --- RECORD [D] ------------------------------------------------------
    audit_path = record.write(
        snapshot, intent, changeset, verdict, outcome=outcome
    )

    # --- G3: post-commit -------------------------------------------------
    g3_summary.show(outcome, audit_path, dry_run=DRY_RUN)


if __name__ == "__main__":
    main()
