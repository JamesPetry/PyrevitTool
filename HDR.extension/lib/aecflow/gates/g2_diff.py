# -*- coding: utf-8 -*-
"""G2 -- the review table. The primary gate.

Every file about to be created, with its exact destination and check verdict.
Nothing is written until the user presses Export here.

Warn rows are listed but PRE-UNSELECTED: the user opts in, never out. A sheet
on an older revision than its neighbours is NOT a warning -- under per-sheet
selection that is correct output -- so it appears as an ordinary passing row.
"""

import os

from pyrevit import forms

from aecflow import contracts


class Row(object):
    """One proposed file, as shown in the review list."""

    def __init__(self, op, result):
        self.op = op
        self.result = result
        self.op_id = op["op_id"]
        self.verdict = result["verdict"]

    @property
    def name(self):
        args = self.op["args"]
        dest = args.get("dest_path")
        target = os.path.basename(dest) if dest else "(no file)"
        sheet = args.get("sheet_number") or "model"
        revision = args.get("revision") or "--"
        status = "" if self.verdict == contracts.PASS else "   [{0}] {1}".format(
            self.result["rule_id"], self.result["message"]
        )
        return "{0:<8} {1:<6} {2}{3}".format(sheet, revision, target, status)

    def __str__(self):
        return self.name


def review(snapshot, changeset, verdict, dry_run=True):
    """Returns the list of op_ids the user approved, or None if cancelled."""
    by_id = dict((r["op_id"], r) for r in verdict["results"])
    rows = [Row(op, by_id[op["op_id"]]) for op in changeset["operations"]
            if op["op_id"] in by_id]

    if not rows:
        forms.alert("Nothing to export for this series.", title="Export Issue")
        return None

    blocked = [r for r in rows if r.verdict == contracts.BLOCK]
    if blocked:
        forms.alert(
            "Blocked by {0} problem(s). Nothing has been written.\n\n{1}".format(
                len(blocked),
                "\n".join("  {0}".format(r.name) for r in blocked[:12]),
            ),
            title="Cannot export",
        )
        return None

    passing = [r for r in rows if r.verdict == contracts.PASS]
    title = "Review {0} file(s){1}".format(
        len(rows), " -- DRY RUN, nothing will be written" if dry_run else ""
    )

    chosen = forms.SelectFromList.show(
        rows,
        title=title,
        multiselect=True,
        name_attr="name",
        button_name="Export" if not dry_run else "Preview",
        preselect=passing,
    )
    if not chosen:
        return None
    return [row.op_id for row in chosen]
