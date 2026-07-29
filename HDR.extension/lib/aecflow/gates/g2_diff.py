# -*- coding: utf-8 -*-
"""G2 -- the review table. The primary gate.

Every file about to be created, with its exact destination and check verdict.
Nothing is written until the user approves here.

Flagged rows are opt-IN: they are held back from the main list and offered
separately, so the default action can never include them by accident. A sheet
on an older revision than its neighbours is NOT flagged -- under per-sheet
selection that is correct output, and it appears as an ordinary row.

Deliberately uses only long-standing pyRevit form arguments (title,
button_name, multiselect, name_attr). Pre-checking rows in a multiselect is
not reliably available across pyRevit versions, so the opt-in guarantee is
implemented by splitting the lists rather than by pre-checking them.
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
        return "{0:<9} {1:<6} {2}".format(sheet, revision, target)

    @property
    def flagged_name(self):
        return "{0}   [{1}] {2}".format(
            self.name, self.result["rule_id"], self.result["message"])

    def __str__(self):
        return self.name


def review(snapshot, changeset, verdict, dry_run=True):
    """Returns the list of approved op_ids, or None if cancelled."""
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
                "\n".join("  " + r.flagged_name for r in blocked[:12]),
            ),
            title="Cannot export",
        )
        return None

    passing = [r for r in rows if r.verdict == contracts.PASS]
    flagged = [r for r in rows if r.verdict == contracts.WARN]

    approved = []

    if passing:
        chosen = forms.SelectFromList.show(
            passing,
            title="Review {0} file(s){1}".format(
                len(passing), "  --  DRY RUN" if dry_run else ""),
            multiselect=True,
            name_attr="name",
            button_name="Preview" if dry_run else "Export",
        )
        if not chosen:
            return None
        approved.extend(row.op_id for row in chosen)

    # Flagged rows are offered only after the clean ones are settled, and only
    # if the user asks for them. Held back rather than pre-unchecked, so the
    # default path cannot include them.
    if flagged:
        include = forms.alert(
            "{0} row(s) were flagged and are NOT included:\n\n{1}\n\n"
            "Include them anyway?".format(
                len(flagged),
                "\n".join("  " + r.flagged_name for r in flagged[:12]),
            ),
            title="Flagged rows", ok=False, yes=True, no=True,
        )
        if include:
            extra = forms.SelectFromList.show(
                flagged,
                title="Which flagged rows?",
                multiselect=True,
                name_attr="flagged_name",
                button_name="Include",
            )
            if extra:
                approved.extend(row.op_id for row in extra)

    return approved or None
